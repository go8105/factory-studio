// H-11 급여 계산 — 마감 선택 → 계산 → 검토 → 확정 (DSN-30 F23·F24).
// 확정하면 그 달 급여는 불변이다. 다시 계산하면 새 버전이 되고 이전 확정본은 지난 버전이 된다.
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
import { won } from "./PayStandards";

const BASE = "/api/v1/hr";
export type PayrollRun = {
  id: number;
  payMonth: string;
  attendanceCloseId: number;
  payDate: string;
  version: number;
  status: string;
  confirmedAt: string | null;
};
export type Payslip = {
  id: number;
  employeeId: number;
  employeeCode: string;
  employeeName: string;
  departmentCode: string;
  gradeName: string;
  grossPay: string;
  deductionTotal: string;
  netPay: string;
};
export const RUN_STATE: Record<
  string,
  { label: string; tone: "normal" | "warning" | "issue" }
> = {
  draft: { label: "작성 중", tone: "warning" },
  confirmed: { label: "확정", tone: "normal" },
  superseded: { label: "이전 버전", tone: "issue" },
};
/** 지급일 기본값: 다음 달 10일. 계산할 때 바꿀 수 있다. */
function defaultPayDate(month: string) {
  const [year, number] = month.split("-").map(Number);
  const next =
    number === 12
      ? `${year + 1}-01`
      : `${year}-${String(number + 1).padStart(2, "0")}`;
  return `${next}-10`;
}

export function Payroll() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [payDate, setPayDate] = useState(defaultPayDate(thisMonth()));
  const [runs, setRuns] = useState<PayrollRun[]>();
  const [slips, setSlips] = useState<Payslip[]>();
  const [picked, setPicked] = useState<number>();
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
    api<PayrollRun[]>(`${BASE}/payroll-runs?month=${month}&limit=20`, {
      signal: controller.signal,
    })
      .then((reply) => {
        setRuns(reply.data);
        // 가장 최근 버전을 자동으로 펼친다 — 계산 직후 바로 검토한다.
        setPicked(reply.data[0]?.id);
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [month, reload]);

  useEffect(() => {
    if (!picked) return setSlips(undefined);
    const controller = new AbortController();
    api<Payslip[]>(`${BASE}/payslips?runId=${picked}&limit=200`, {
      signal: controller.signal,
    })
      .then((reply) => setSlips(reply.data))
      .catch(() => controller.signal.aborted || setSlips([]));
    return () => controller.abort();
  }, [picked, reload]);

  async function calculate() {
    setDone("");
    const made = await send<PayrollRun & { employees: number }>(
      "/payroll-runs",
      "POST",
      { month, payDate },
    );
    if (made)
      setDone(
        `${month} 급여 ${made.version}차를 계산했습니다(사원 ${made.employees}명). 검토 후 확정하세요.`,
      );
  }

  async function confirm(run: PayrollRun) {
    setDone("");
    const ok = await send(`/payroll-runs/${run.id}/confirm`, "POST");
    if (ok)
      setDone(`${run.payMonth} 급여를 확정했습니다. 이제 고칠 수 없습니다.`);
  }

  if (moduleOff(loadError))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const current = runs?.find((run) => run.id === picked);
  const total = (slips ?? []).reduce(
    (sum, slip) => ({
      gross: sum.gross + Number(slip.grossPay),
      deduction: sum.deduction + Number(slip.deductionTotal),
      net: sum.net + Number(slip.netPay),
    }),
    { gross: 0, deduction: 0, net: 0 },
  );
  const runColumns: Column<PayrollRun>[] = [
    { key: "payMonth", label: "급여 월" },
    { key: "version", label: "버전" },
    { key: "payDate", label: "지급일" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={RUN_STATE[r.status]?.tone ?? "normal"}>
          {RUN_STATE[r.status]?.label ?? r.status}
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
      render: (r) => (
        <span className="row-actions">
          <button className="link-button" onClick={() => setPicked(r.id)}>
            검토
          </button>
          {r.status === "draft" && (
            <button disabled={pending} onClick={() => void confirm(r)}>
              확정
            </button>
          )}
        </span>
      ),
    },
  ];
  const slipColumns: Column<Payslip>[] = [
    { key: "departmentCode", label: "부서" },
    { key: "employeeCode", label: "사원 코드" },
    { key: "employeeName", label: "이름" },
    { key: "gradeName", label: "직위" },
    { key: "grossPay", label: "지급 합계", render: (r) => won(r.grossPay) },
    {
      key: "deductionTotal",
      label: "공제 합계",
      render: (r) => won(r.deductionTotal),
    },
    { key: "netPay", label: "실지급액", render: (r) => won(r.netPay) },
  ];
  return (
    <div className="page-fill">
      <PageTitle
        id="H-11"
        title="급여 계산"
        subtitle="그 달 근태를 마감해야 계산할 수 있습니다"
        help="hr/h-11"
        actions={
          <button
            type="button"
            disabled={pending}
            onClick={() => void calculate()}
          >
            {month} 급여 계산
          </button>
        }
      />
      {done && <p role="status">{done}</p>}
      <ErrorNotice error={saveError} />
      <div className="filter-bar">
        <label htmlFor="payroll-month">급여 월</label>
        <input
          id="payroll-month"
          type="month"
          value={month}
          onChange={(event) => {
            setMonth(event.target.value);
            setPayDate(defaultPayDate(event.target.value));
          }}
        />
        <label htmlFor="payroll-pay-date">지급일</label>
        <input
          id="payroll-pay-date"
          type="date"
          value={payDate}
          onChange={(event) => setPayDate(event.target.value)}
        />
      </div>
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      {!runs ? (
        !loadError && <Loading />
      ) : (
        <DataTable
          rows={runs}
          columns={runColumns}
          caption={`${month} 급여 실행`}
          offset={0}
          total={runs.length}
          limit={runs.length || 1}
          onPage={() => {}}
          empty={
            <EmptyState
              reason={`${month} 급여를 아직 계산하지 않았습니다.`}
              action={`${month} 급여 계산`}
              onAction={() => void calculate()}
            />
          }
        />
      )}
      {current && slips && (
        <>
          <p role="status">
            {current.payMonth} {current.version}차 ·{" "}
            {RUN_STATE[current.status]?.label} · 사원 {slips.length}명 · 지급{" "}
            {won(total.gross)} · 공제 {won(total.deduction)} · 실지급{" "}
            {won(total.net)}
          </p>
          <DataTable
            rows={slips}
            columns={slipColumns}
            caption="사원별 계산 결과"
            offset={0}
            total={slips.length}
            limit={slips.length || 1}
            onPage={() => {}}
            empty={
              <EmptyState
                reason="계산된 명세서가 없습니다."
                action="다시 계산"
                onAction={() => void calculate()}
              />
            }
          />
        </>
      )}
    </div>
  );
}
