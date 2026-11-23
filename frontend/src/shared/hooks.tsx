// 솔루션 화면 공통 훅: 목록 불러오기, 저장·삭제 요청(CSRF·멱등 키), 입력 오류, 삭제 2단계 버튼.
// base는 솔루션 API 접두사(/api/v1/mes, /api/v1/erp).
import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "./api";

export function fieldErrors(error: unknown): Record<string, string> {
  const fields =
    error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
      ? (error.error.details.fields as Record<string, string>)
      : {};
  // 본문 검사(FastAPI)는 "body.rate"처럼 돌려준다. 입력 칸 이름과 맞춘다.
  return Object.fromEntries(
    Object.entries(fields).map(([key, message]) => [
      key.replace(/^body\./, ""),
      message,
    ]),
  );
}

export function moduleOff(error: unknown) {
  return (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  );
}

/** 여러 목록을 한 번에 불러온다. reload()로 다시 불러온다. */
export function useApiLists<T extends unknown[]>(
  base: string,
  paths: string[],
) {
  const { fail } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    Promise.all(
      paths.map((p) =>
        api<unknown[]>(`${base}${p}`, { signal: controller.signal }),
      ),
    )
      .then((responses) => setData(responses.map((r) => r.data) as T))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
    // 경로가 바뀌면 다시 부른다 — 기간·고른 행을 경로에 담는 조회 화면이 많다.
    // 배열은 렌더마다 새로 만들어지므로 내용으로 비교한다.
  }, [tick, paths.join("|"), base]);
  return { data, error, reload: () => setTick((n) => n + 1) };
}

/** 저장·삭제 요청. 성공하면 onDone(보통 목록 다시 불러오기)을 부른다. */
export function useApiSend(base: string, onDone: () => void) {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  const [confirmDelete, setConfirmDelete] = useState<string>();

  async function send<R = unknown>(
    path: string,
    method: string,
    body?: unknown,
  ): Promise<R | undefined> {
    const operation = `${method} ${path} ${JSON.stringify(body ?? null)}`;
    setPending(true);
    setError(undefined);
    try {
      const r = await api<R>(`${base}${path}`, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      onDone();
      return (r?.data ?? {}) as R;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(operation);
      setError(e);
      if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      return undefined;
    } finally {
      setPending(false);
      if (method === "DELETE") setConfirmDelete(undefined);
    }
  }

  function deleteButtons(key: string, path: string) {
    return confirmDelete === key ? (
      <>
        <button
          type="button"
          className="secondary"
          disabled={pending}
          onClick={() => void send(path, "DELETE")}
        >
          삭제 확정
        </button>
        <button
          type="button"
          className="link-button"
          onClick={() => setConfirmDelete(undefined)}
        >
          취소
        </button>
      </>
    ) : (
      <button
        type="button"
        className="link-button"
        onClick={() => {
          setConfirmDelete(key);
          setError(undefined);
        }}
      >
        삭제
      </button>
    );
  }

  return { send, pending, error, setError, deleteButtons };
}
