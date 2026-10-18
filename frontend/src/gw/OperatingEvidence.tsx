import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNotice, Loading } from "../shared/components";
import { ApiError } from "../shared/api";
import { useGet, useSend } from "./common";
type Entry = {
  id: string;
  runId: string;
  kind: string;
  result: string;
  finishedAt: string;
  revisionNo: number;
  currentPolicy: boolean;
};
export function OperatingEvidence({
  canEdit,
  disabled,
}: {
  canEdit: boolean;
  disabled: boolean;
}) {
  const [offset, setOffset] = useState(0);
  const history = useGet<{ total: number; items: Entry[] }>(
    `/operating-evidence?offset=${offset}&limit=20`,
  );
  const send = useSend();
  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setMessage("");
    try {
      if (file.size > 20000)
        throw new ApiError(400, {
          code: "VALIDATION_FAILED",
          message: "실행 증거 파일은 20KB 이내로 선택하세요.",
        });
      let body: unknown;
      try {
        body = JSON.parse(await file.text());
      } catch {
        throw new ApiError(400, {
          code: "VALIDATION_FAILED",
          message: "서명된 JSON 실행 증거 파일을 선택하세요.",
        });
      }
      const result = await send.send("/operating-evidence", "POST", body);
      if (!result) return;
      setFile(null);
      setMessage("실행 기록을 등록했습니다. 운영 준비 완료를 뜻하지 않습니다.");
      history.reload();
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  const kinds: Record<string, string> = {
    BACKUP: "백업",
    RESTORE: "복원",
    ACCEPTANCE: "인수",
    INCIDENT: "사건",
  };
  const results: Record<string, string> = {
    PASS: "통과",
    FAIL: "실패",
    PARTIAL: "일부 확인",
  };
  return (
    <section aria-label="운영 실행 기록">
      <h2>운영 실행 기록</h2>
      <p>
        실행 도구가 서명한 결과를 보관합니다. 실패 기록도 유지하며 현재 기준과
        다른 기록은 구분합니다. 파일 등록만으로 백업·복원이 실행되지는 않습니다.
      </p>
      <p>
        백업 통과는 실행자가 확인한 저장 범위의 결과입니다. 복원 일부 확인은
        운영 재개 승인이 아니며 외부 보관·실환경 인수는 별도로 확인합니다.
      </p>
      {canEdit && (
        <>
          <label>
            서명된 실행 증거 파일
            <input
              type="file"
              accept="application/json,.json"
              disabled={disabled || busy}
              onChange={(e) => {
                setFile(e.target.files?.[0] ?? null);
                setError(null);
                setMessage("");
              }}
            />
          </label>
          <button
            disabled={disabled || busy || !file}
            onClick={() => void upload()}
          >
            {busy ? "서명과 실행 결과 확인 중…" : "실행 증거 확인·등록"}
          </button>
          <p>
            최근 인증이 필요하면{" "}
            <Link to="/account/security" target="_blank" rel="noopener">
              내 계정 보안
            </Link>
            에서 본인 확인 후 다시 등록하세요.
          </p>
        </>
      )}
      {error || send.error ? <ErrorNotice error={error || send.error} /> : null}
      {message && <p role="status">{message}</p>}
      {history.error ? (
        <ErrorNotice error={history.error} retry={history.reload} />
      ) : !history.data ? (
        <Loading />
      ) : (
        <>
          <p>총 {history.data.total}건 · 최근 등록 순</p>
          <ul>
            {history.data.items.map((item) => (
              <li key={item.id}>
                {kinds[item.kind] ?? item.kind} ·{" "}
                {results[item.result] ?? item.result} ·{" "}
                {new Date(item.finishedAt).toLocaleString("ko-KR")} · 기준{" "}
                {item.revisionNo}차 (
                {item.currentPolicy ? "현재 기준" : "이전 기준"})<br />
                <small>실행 번호 {item.runId}</small>
              </li>
            ))}
          </ul>
          {history.data.total === 0 && <p>등록된 실행 기록이 없습니다.</p>}
          <button
            disabled={offset === 0 || busy}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            이전 기록 페이지
          </button>
          <button
            disabled={offset + 20 >= history.data.total || busy}
            onClick={() => setOffset(offset + 20)}
          >
            다음 기록 페이지
          </button>
        </>
      )}
    </section>
  );
}
