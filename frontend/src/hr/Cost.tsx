// H-14 인건비·근태 분석 — 확정 급여의 부서·항목별 인건비와 그 달 근태·연차 (DSN-30 F42·F43).
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { ApiError, api } from "../shared/api";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import { moduleOff } from "../shared/hooks";
import { thisMonth } from "./Attendance";
import { won } from "./PayStandards";

const BASE = "/api/v1/hr";
type Cost = {
  month: string;
  confirmed: boolean;
  departments: {
    departmentCode: string;
    employees: number;
    grossPay: string;
    deductionTotal: string;
    netPay: string;
  }[];
  items: {
    itemCode: string;
    itemName: string;
    itemKind: string;
    amount: string;
  }[];
  attendance: {
    overtimeHours: string;
    nightHours: string;
    holidayHours: string;
    absentDays: number;
  };
  leave: { grantedDays: string; usedDays: string; usageRate: string | null };
};
const hours = (value: string) => Number(value).toFixed(1);

export function Cost() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState<Cost>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Cost>(`${BASE}/cost?month=${month}`, { signal: controller.signal })
      .then((reply) => !controller.signal.aborted && setData(reply.data))
      .catch((caught) => {
        if (controller.signal.aborted) return;
        setError(caught);
        if (caught instanceof ApiError && [401, 410].includes(caught.status))
          fail(caught);
      });
    return () => controller.abort();
  }, [month, reload]);

  if (moduleOff(error))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const total = (data?.departments ?? []).reduce(
    (sum, row) => ({
      employees: sum.employees + row.employees,
      gross: sum.gross + Number(row.grossPay),
      net: sum.net + Number(row.netPay),
    }),
    { employees: 0, gross: 0, net: 0 },
  );
  return (
    <div className="page-fill">
      <PageTitle
        id="H-14"
        title="인건비·근태 분석"
        subtitle="인건비는 확정한 급여만 셉니다"
        help="hr/h-14"
        actions={
          <label>
            조회 월
            <input
              type="month"
              value={month}
              onChange={(event) =>
                event.target.value && setMonth(event.target.value)
              }
            />
          </label>
        }
      />
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <div className="filter-bar">
            {data.confirmed ? (
              <Badge>
                확정 급여 {total.employees}명 · 지급 {won(total.gross)} · 실지급{" "}
                {won(total.net)}
              </Badge>
            ) : (
              <Badge tone="warning">
                {month} 확정 급여가 없습니다 —{" "}
                <Link to="/hr/payroll">급여 계산에서 확정하세요</Link>
              </Badge>
            )}
          </div>
          <div className="dashboard-grid">
            <figure>
              <figcaption>부서별 인건비</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>부서</th>
                    <th>인원</th>
                    <th>지급</th>
                    <th>공제</th>
                    <th>실지급</th>
                  </tr>
                </thead>
                <tbody>
                  {data.departments.map((row) => (
                    <tr key={row.departmentCode}>
                      <td>{row.departmentCode}</td>
                      <td>{row.employees}</td>
                      <td>{won(row.grossPay)}</td>
                      <td>{won(row.deductionTotal)}</td>
                      <td>{won(row.netPay)}</td>
                    </tr>
                  ))}
                  {!data.departments.length && (
                    <tr>
                      <td colSpan={5}>확정한 급여가 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>항목별 인건비</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>항목</th>
                    <th>구분</th>
                    <th>금액</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((row) => (
                    <tr key={row.itemCode}>
                      <td>{row.itemName}</td>
                      <td>{row.itemKind === "EARNING" ? "지급" : "공제"}</td>
                      <td>{won(row.amount)}</td>
                    </tr>
                  ))}
                  {!data.items.length && (
                    <tr>
                      <td colSpan={3}>확정한 급여가 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>근태·연차</figcaption>
              <table>
                <tbody>
                  <tr>
                    <th scope="row">연장 근로</th>
                    <td>{hours(data.attendance.overtimeHours)}시간</td>
                  </tr>
                  <tr>
                    <th scope="row">야간 근로</th>
                    <td>{hours(data.attendance.nightHours)}시간</td>
                  </tr>
                  <tr>
                    <th scope="row">휴일 근로</th>
                    <td>{hours(data.attendance.holidayHours)}시간</td>
                  </tr>
                  <tr>
                    <th scope="row">결근</th>
                    <td>{data.attendance.absentDays}일</td>
                  </tr>
                  <tr>
                    <th scope="row">{month.slice(0, 4)}년 연차 사용률</th>
                    <td>
                      {data.leave.usageRate
                        ? `${data.leave.usageRate}% (발생 ${data.leave.grantedDays} · 사용 ${data.leave.usedDays}일)`
                        : "연차 발생을 아직 등록하지 않았습니다"}
                    </td>
                  </tr>
                </tbody>
              </table>
            </figure>
          </div>
        </>
      )}
    </div>
  );
}
