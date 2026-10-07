// H-08 근태 마감 — 월 합계를 확인하고 마감한다. 확정하면 그 달은 잠긴다(DSN-30 F14·F15).
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { ApiError, api } from "../shared/api";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { moduleOff, useApiSend } from "../shared/hooks";
import { thisMonth } from "./Attendance";

const BASE = "/api/v1/hr";
const LIMIT = 20;
type Close = {
  id: number;
  closeMonth: string;
  version: number;
  status: string;
  confirmedAt: string | null;
};
type Summary = {
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  workedDays: number;
  absentDays: number;
  leaveDays: number;
  overtimeMinutes: number;
  nightMinutes: number;
  holidayMinutes: number;
};
const STATE: Record<
  string,
  { label: string; tone: "normal" | "warning" | "issue" }
> = {
  draft: { label: "작성 중", tone: "warning" },
  confirmed: { label: "확정", tone: "normal" },
  superseded: { label: "이전 버전", tone: "issue" },
};

export function AttendanceCloses() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [rows, setRows] = useState<Close[]>();
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const [summary, setSummary] = useState<Summary[]>();
  const [reload, setReload] = useState(0);
  const [loadError, setLoadError] = useState<unknown>();
  const [done, setDone] = useState("");
  const {
    send,
    pending,
    error: saveError,
  } = useApiSend(BASE, () => setReload((n) => n + 1));

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    Promise.all([
      api<Close[]>(
        `${BASE}/attendance-closes?offset=${offset}&limit=${LIMIT}`,
        {
          signal: controller.signal,
        },
      ),
      api<Summary[]>(`${BASE}/attendance/summary?month=${month}`, {
        signal: controller.signal,
      }),
    ])
      .then(([closes, months]) => {
        setRows(closes.data);
        setTotal(closes.page?.total ?? 0);
        setSummary(months.data);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [month, offset, reload]);

  async function openClose() {
    setDone("");
    const made = await send<Close>("/attendance-closes", "POST", { month });
    if (made)
      setDone(
        `${month} 마감 ${made.version}차를 열었습니다. 확정해야 그 달이 잠깁니다.`,
      );
  }

  async function confirm(row: Close) {
    setDone("");
    const ok = await send(`/attendance-closes/${row.id}/confirm`, "POST");
    if (ok) setDone(`${row.closeMonth} 근태를 마감했습니다.`);
  }

  if (moduleOff(loadError))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const hours = (value: number) =>
    value ? `${(value / 60).toFixed(1)}시간` : "—";
  const summaryColumns: Column<Summary & { id: number }>[] = [
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    { key: "workedDays", label: "근무" },
    { key: "absentDays", label: "결근" },
    { key: "leaveDays", label: "휴가" },
    {
      key: "overtimeMinutes",
      label: "연장",
      render: (r) => hours(r.overtimeMinutes),
    },
    {
      key: "nightMinutes",
      label: "야간",
      render: (r) => hours(r.nightMinutes),
    },
    {
      key: "holidayMinutes",
      label: "휴일",
      render: (r) => hours(r.holidayMinutes),
    },
  ];
  const closeColumns: Column<Close>[] = [
    { key: "closeMonth", label: "마감 월" },
    { key: "version", label: "버전" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={STATE[r.status]?.tone ?? "normal"}>
          {STATE[r.status]?.label ?? r.status}
        </Badge>
      ),
    },
    {
      key: "confirmedAt",
      label: "확정 시각",
      render: (r) => r.confirmedAt ?? "—",
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        r.status === "draft" ? (
          <button disabled={pending} onClick={() => void confirm(r)}>
            마감 확정
          </button>
        ) : (
          <span>—</span>
        ),
    },
  ];
  const summaryRows = (summary ?? []).map((row) => ({
    ...row,
    id: row.employeeId,
  }));
  return (
    <div className="page-fill">
      <PageTitle
        id="H-08"
        title="근태 마감"
        subtitle="확정하면 그 달의 근태는 고칠 수 없습니다"
        help="hr/h-08"
        actions={
          <button
            type="button"
            disabled={pending}
            onClick={() => void openClose()}
          >
            {month} 마감 열기
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={saveError} />
      <div className="filter-bar">
        <label htmlFor="close-month">조회 월</label>
        <input
          id="close-month"
          type="month"
          value={month}
          onChange={(event) => setMonth(event.target.value)}
        />
      </div>
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      {!summary ? (
        !loadError && <Loading />
      ) : (
        <DataTable
          rows={summaryRows}
          columns={summaryColumns}
          caption={`${month} 사원별 근태 합계`}
          offset={0}
          total={summaryRows.length}
          limit={summaryRows.length || 1}
          onPage={() => {}}
          empty={
            <EmptyState
              reason={`${month} 근태가 없습니다. 근태 화면에서 먼저 만드세요.`}
              to="/hr/attendance"
              action="근태 화면으로"
            />
          }
        />
      )}
      {rows && (
        <DataTable
          rows={rows}
          columns={closeColumns}
          caption="마감 이력"
          offset={offset}
          total={total}
          limit={LIMIT}
          onPage={setOffset}
          empty={
            <EmptyState
              reason="마감한 달이 없습니다. 월을 고르고 마감을 열어 보세요."
              action={`${month} 마감 열기`}
              onAction={() => void openClose()}
            />
          }
        />
      )}
    </div>
  );
}
