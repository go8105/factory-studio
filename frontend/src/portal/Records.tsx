// P-07 운영 기록
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  ErrorNotice,
  Loading,
  NotFound,
  PageTitle,
  type Column,
} from "../shared/components";
type RecordRow = {
  id: number;
  action?: string;
  entityKind?: string;
  actorKind?: string;
  createdAt?: string;
  jobKind?: string;
  status?: string;
  scopeKind?: string;
  startedAt?: string;
  finishedAt?: string;
};
const auditColumns: Column<RecordRow>[] = [
  { key: "id", label: "번호" },
  { key: "action", label: "동작" },
  { key: "entityKind", label: "대상" },
  { key: "actorKind", label: "주체" },
  { key: "createdAt", label: "기록 시각" },
];
const jobColumns: Column<RecordRow>[] = [
  { key: "id", label: "번호" },
  { key: "jobKind", label: "작업" },
  { key: "status", label: "상태" },
  { key: "scopeKind", label: "범위" },
  { key: "startedAt", label: "시작" },
  { key: "finishedAt", label: "종료" },
];
export function Records() {
  const { fail } = useSession();
  const [kind, setKind] = useState("audit-events");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<RecordRow[]>();
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<unknown>();
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setData(undefined);
    setError(undefined);
    api<RecordRow[]>(`/admin/${kind}?offset=${offset}&limit=20`, {
      signal: controller.signal,
    })
      .then((r) => {
        if (controller.signal.aborted) return;
        setData(r.data);
        setTotal(r.page?.total ?? 0);
      })
      .catch((e) => {
        if (!controller.signal.aborted) {
          setError(e);
          if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
        }
      });
    return () => controller.abort();
  }, [kind, offset, retry]);
  if (error instanceof ApiError && [403, 404].includes(error.status))
    return <NotFound />;

  const tabs = (
    <div className="tabs" role="group" aria-label="기록 종류">
      {[
        ["audit-events", "감사 로그"],
        ["job-runs", "작업 실행 내역"],
      ].map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={kind === key}
          onClick={() => {
            setKind(key);
            setOffset(0);
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );

  return (
    <div className="page-fill">
      <PageTitle
        id="P-07"
        title="운영 기록"
        subtitle="작업 실행 내역과 감사 로그 · 읽기 전용"
      />
      <ErrorNotice error={error} retry={() => setRetry(retry + 1)} />
      {!data ? (
        <>
          {tabs}
          {!error && <Loading delay={300} />}
        </>
      ) : (
        <DataTable
          leading={tabs}
          rows={data}
          columns={kind === "audit-events" ? auditColumns : jobColumns}
          caption={kind === "audit-events" ? "감사 로그" : "작업 실행 내역"}
          offset={offset}
          total={total}
          limit={20}
          onPage={setOffset}
        />
      )}
    </div>
  );
}
