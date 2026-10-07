// H-12 급여대장·명세서 — 실행 한 건의 대장과 사원별 명세서(인쇄) (DSN-30 F25·F28).
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { ApiError, api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { moduleOff } from "../shared/hooks";
import { RUN_STATE, type PayrollRun, type Payslip } from "./Payroll";
import { won } from "./PayStandards";

const BASE = "/api/v1/hr";
type SlipLine = {
  id: number;
  itemCode: string;
  itemName: string;
  itemKind: string;
  calcKind: string;
  amount: string;
  basisQuantity: string | null;
};
type SlipDetail = Payslip & {
  payMonth: string;
  payDate: string;
  status: string;
  version: number;
  lines: SlipLine[];
};
type Severance = {
  employeeCode: string;
  employeeName: string;
  months: string[];
  averageDailyWage: string;
  serviceYears: string;
  estimate: string;
};

export function Payslips() {
  const { fail } = useSession();
  const [runs, setRuns] = useState<PayrollRun[]>();
  const [runId, setRunId] = useState("");
  const [rows, setRows] = useState<Payslip[]>();
  const [picked, setPicked] = useState<SlipDetail>();
  const [severance, setSeverance] = useState<Severance>();
  const [loadError, setLoadError] = useState<unknown>();
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoadError(undefined);
    api<PayrollRun[]>(`${BASE}/payroll-runs?limit=50`, {
      signal: controller.signal,
    })
      .then((reply) => {
        setRuns(reply.data);
        setRunId((current) => current || String(reply.data[0]?.id ?? ""));
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
        if (error instanceof ApiError && [401, 410].includes(error.status))
          fail(error);
      });
    return () => controller.abort();
  }, [reload]);

  useEffect(() => {
    if (!runId) return setRows(undefined);
    const controller = new AbortController();
    api<Payslip[]>(`${BASE}/payslips?runId=${runId}&limit=200`, {
      signal: controller.signal,
    })
      .then((reply) => setRows(reply.data))
      .catch((error) => {
        if (controller.signal.aborted) return;
        setLoadError(error);
      });
    return () => controller.abort();
  }, [runId]);

  async function open(slip: Payslip) {
    setSeverance(undefined);
    const [detail, estimate] = await Promise.all([
      api<SlipDetail>(`${BASE}/payslips/${slip.id}`),
      api<Severance>(`${BASE}/severance?employeeId=${slip.employeeId}`),
    ]);
    setPicked(detail.data);
    setSeverance(estimate.data);
  }

  if (moduleOff(loadError))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const run = runs?.find((item) => String(item.id) === runId);
  const columns: Column<Payslip>[] = [
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
    {
      key: "id",
      label: "명세서",
      render: (r) => (
        <button className="link-button" onClick={() => void open(r)}>
          열기
        </button>
      ),
    },
  ];
  const earnings = (picked?.lines ?? []).filter(
    (l) => l.itemKind === "EARNING",
  );
  const deductions = (picked?.lines ?? []).filter(
    (l) => l.itemKind === "DEDUCTION",
  );
  return (
    <div className="page-fill">
      <PageTitle
        id="H-12"
        title="급여대장·명세서"
        subtitle="실행 한 건의 사원별 지급·공제와 명세서를 봅니다"
        help="hr/h-12"
        actions={
          picked && (
            <button type="button" onClick={() => window.print()}>
              명세서 인쇄
            </button>
          )
        }
      />
      <ErrorNotice error={loadError} retry={() => setReload((n) => n + 1)} />
      <div className="filter-bar">
        <label htmlFor="payslip-run">급여 실행</label>
        <select
          id="payslip-run"
          value={runId}
          onChange={(event) => {
            setPicked(undefined);
            setRunId(event.target.value);
          }}
        >
          {(runs ?? []).map((item) => (
            <option key={item.id} value={String(item.id)}>
              {item.payMonth} {item.version}차 ·{" "}
              {RUN_STATE[item.status]?.label ?? item.status}
            </option>
          ))}
        </select>
        {run && (
          <Badge tone={RUN_STATE[run.status]?.tone ?? "normal"}>
            지급일 {run.payDate}
          </Badge>
        )}
      </div>
      <div className="split-view fill">
        <section className="fill">
          {!runs ? (
            !loadError && <Loading />
          ) : !runs.length ? (
            <EmptyState
              reason="급여를 아직 계산하지 않았습니다."
              to="/hr/payroll"
              action="급여 계산으로"
            />
          ) : !rows ? (
            <Loading />
          ) : (
            <DataTable
              rows={rows}
              columns={columns}
              caption="급여대장"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => {}}
              empty={
                <EmptyState
                  reason="명세서가 없습니다."
                  to="/hr/payroll"
                  action="급여 계산으로"
                />
              }
            />
          )}
        </section>
        {picked && (
          <DetailPanel
            wide
            title={`${picked.employeeName} ${picked.payMonth} 급여명세서`}
            onClose={() => setPicked(undefined)}
          >
            <dl className="detail-grid">
              <dt>사원</dt>
              <dd>
                {picked.employeeCode} · {picked.departmentCode} ·{" "}
                {picked.gradeName}
              </dd>
              <dt>지급일</dt>
              <dd>
                {picked.payDate} ({picked.version}차 ·{" "}
                {RUN_STATE[picked.status]?.label ?? picked.status})
              </dd>
            </dl>
            <table>
              <caption>지급</caption>
              <thead>
                <tr>
                  <th>항목</th>
                  <th>근거</th>
                  <th>금액</th>
                </tr>
              </thead>
              <tbody>
                {earnings.map((line) => (
                  <tr key={line.id}>
                    <td>{line.itemName}</td>
                    <td>{basisText(line)}</td>
                    <td>{won(line.amount)}</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">지급 합계</th>
                  <td />
                  <td>{won(picked.grossPay)}</td>
                </tr>
              </tbody>
            </table>
            <table>
              <caption>공제</caption>
              <thead>
                <tr>
                  <th>항목</th>
                  <th>비율</th>
                  <th>금액</th>
                </tr>
              </thead>
              <tbody>
                {deductions.map((line) => (
                  <tr key={line.id}>
                    <td>{line.itemName}</td>
                    <td>
                      {line.basisQuantity ? `${line.basisQuantity}%` : "—"}
                    </td>
                    <td>{won(line.amount)}</td>
                  </tr>
                ))}
                <tr>
                  <th scope="row">공제 합계</th>
                  <td />
                  <td>{won(picked.deductionTotal)}</td>
                </tr>
                <tr>
                  <th scope="row">실지급액</th>
                  <td />
                  <td>
                    <b>{won(picked.netPay)}</b>
                  </td>
                </tr>
              </tbody>
            </table>
            {severance && (
              <dl className="detail-grid">
                <dt>퇴직금 추계</dt>
                <dd>
                  {won(severance.estimate)}원 — 최근 {severance.months.length}
                  개월 평균 임금 {won(severance.averageDailyWage)}원 × 30일 ×
                  근속 {severance.serviceYears}년 (저장하지 않는 조회
                  계산입니다)
                </dd>
              </dl>
            )}
          </DetailPanel>
        )}
      </div>
    </div>
  );
}

/** 연장·야간·휴일은 시간, 상여는 지급률이 근거다. */
function basisText(line: SlipLine) {
  if (line.basisQuantity === null) return "—";
  return line.calcKind === "BONUS"
    ? `${line.basisQuantity}%`
    : `${line.basisQuantity}시간`;
}
