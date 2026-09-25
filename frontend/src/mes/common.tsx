// MES 화면 공통: 목록 불러오기, 저장·삭제 요청(CSRF·멱등 키), 입력 오류, 삭제 2단계 버튼
import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import { EmptyState } from "../shared/components";

export const MES = "/api/v1/mes";

export type Site = {
  id: number;
  siteCode: string;
  name: string;
  timezone: string;
};
export type Place = {
  id: number;
  siteId: number;
  parentLocationId: number | null;
  locationCode: string;
  name: string;
  kind: "building" | "zone" | "workcenter";
};
export type Equipment = {
  id: number;
  locationId: number;
  equipmentCode: string;
  name: string;
  equipmentType: string;
  isActive: boolean;
};

export function MesOrder() {
  return (
    <ol className="master-order" aria-label="기준정보 등록 순서">
      <li>사업장 → 공간 → 설비</li>
      <li>공정 (허용 설비 필요)</li>
      <li>품목 → 단위 환산</li>
    </ol>
  );
}

export function fieldErrors(error: unknown): Record<string, string> {
  return error instanceof ApiError &&
    error.error.code === "VALIDATION_FAILED" &&
    error.error.details?.fields
    ? (error.error.details.fields as Record<string, string>)
    : {};
}

/** 수정 시 바뀐 값만 보낸다. */
export function changed(draft: object, current: object) {
  return Object.fromEntries(
    Object.entries(draft).filter(
      ([k, v]) =>
        JSON.stringify((current as Record<string, unknown>)[k]) !==
        JSON.stringify(v),
    ),
  );
}

export function moduleOff(error: unknown) {
  return (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  );
}

export function ModuleOff() {
  return (
    <EmptyState
      reason="MES를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

/** 여러 목록을 한 번에 불러온다. reload()로 다시 불러온다. */
export function useLists<T extends unknown[]>(paths: string[]) {
  const { fail } = useSession();
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    Promise.all(
      paths.map((p) =>
        api<unknown[]>(`${MES}${p}`, { signal: controller.signal }),
      ),
    )
      .then((responses) => setData(responses.map((r) => r.data) as T))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [tick]);
  return { data, error, reload: () => setTick((n) => n + 1) };
}

/** 저장·삭제 요청. 성공하면 onDone(보통 목록 다시 불러오기)을 부른다. */
export function useSend(onDone: () => void) {
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
      const r = await api<R>(`${MES}${path}`, {
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
