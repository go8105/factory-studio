// H-15 내 정보 — 본인 근태·잔여 연차·확정 명세서·평가 (DSN-30 F44, Q7).
// EIP 사람 연결(my_employee_code)이 아직 없어서 사원 코드를 **화면에서 고른다**. EIP가 생기면 그쪽이 준다.
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
import { moduleOff, useApiLists } from "../shared/hooks";
import { thisMonth } from "./Attendance";
import type { Employee } from "./Employees";
import { STATUS } from "./Employees";
import { won } from "./PayStandards";

const BASE = "/api/v1/hr";
type Me = {
  employee: {
    employeeCode: string;
    name: string;
    status: string;
    hireDate: string;
    departmentCode: string;
    departmentName: string;
    gradeName: string;
    dutyName: string | null;
  };
  month: string;
  attendance: {
    workedDays: number;
    absentDays: number;
    leaveDays: number;
    overtimeMinutes: number;
    nightMinutes: number;
  };
  leave: {
    year: string;
    grantedDays: string;
    usedDays: string;
    remainingDays: string;
  };
  payslips: {
    id: number;
    payMonth: string;
    payDate: string;
    grossPay: string;
    deductionTotal: string;
    netPay: string;
  }[];
  reviews: {
    id: number;
    cycleYear: string;
    status: string;
    grade: string | null;
    reviewerCode: string;
    reviewerComment: string | null;
  }[];
};
const REVIEW_STATE: Record<string, string> = {
  draft: "작성 중",
  submitted: "제출",
  confirmed: "확정",
};
const hours = (minutes: number) => (minutes / 60).toFixed(1);

export function Me() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [code, setCode] = useState("");
  const [data, setData] = useState<Me>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const lookups = useApiLists<[Employee[]]>(BASE, ["/employees?limit=200"]);
  const [employees = []] = lookups.data ?? [];

  useEffect(() => {
    if (!code && employees.length) setCode(employees[0].employeeCode);
  }, [employees]);

  useEffect(() => {
    if (!code) return setData(undefined);
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Me>(
      `${BASE}/me?employeeCode=${encodeURIComponent(code)}&month=${month}`,
      {
        signal: controller.signal,
      },
    )
      .then((reply) => !controller.signal.aborted && setData(reply.data))
      .catch((caught) => {
        if (controller.signal.aborted) return;
        setError(caught);
        if (caught instanceof ApiError && [401, 410].includes(caught.status))
          fail(caught);
      });
    return () => controller.abort();
  }, [code, month, reload]);

  if (moduleOff(error) || moduleOff(lookups.error))
    return (
      <EmptyState
        reason="HR을 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  return (
    <div className="page-fill">
      <PageTitle
        id="H-15"
        title="내 정보"
        subtitle="본인 근태·잔여 연차·확정 급여명세서·평가만 봅니다"
        help="hr/h-15"
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
      <ErrorNotice error={lookups.error} />
      <div className="filter-bar">
        <label htmlFor="me-code">사원</label>
        <select
          id="me-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        >
          {employees.map((employee) => (
            <option key={employee.id} value={employee.employeeCode}>
              {employee.employeeCode} {employee.name}
            </option>
          ))}
        </select>
        <small>
          로그인 사용자와 사원을 잇는 EIP 기능은 아직 없어서 여기서 고릅니다.
        </small>
      </div>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!employees.length && !lookups.error ? (
        <EmptyState
          reason="사원이 없습니다. 사원을 등록해야 본인 정보를 볼 수 있습니다."
          to="/hr/employees"
          action="사원 등록으로"
        />
      ) : !data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <dl className="detail-grid">
            <dt>사원</dt>
            <dd>
              {data.employee.employeeCode} {data.employee.name} ·{" "}
              {data.employee.departmentName} · {data.employee.gradeName}
              {data.employee.dutyName && ` · ${data.employee.dutyName}`}
            </dd>
            <dt>입사일</dt>
            <dd>
              {data.employee.hireDate}{" "}
              <Badge
                tone={data.employee.status === "ACTIVE" ? "normal" : "warning"}
              >
                {STATUS[data.employee.status] ?? data.employee.status}
              </Badge>
            </dd>
            <dt>{data.leave.year}년 연차</dt>
            <dd>
              잔여 <b>{data.leave.remainingDays}일</b> (발생{" "}
              {data.leave.grantedDays} · 사용 {data.leave.usedDays})
            </dd>
          </dl>
          <div className="dashboard-grid">
            <figure>
              <figcaption>{month} 내 근태</figcaption>
              <table>
                <tbody>
                  <tr>
                    <th scope="row">근무</th>
                    <td>{data.attendance.workedDays}일</td>
                  </tr>
                  <tr>
                    <th scope="row">휴가</th>
                    <td>{data.attendance.leaveDays}일</td>
                  </tr>
                  <tr>
                    <th scope="row">결근</th>
                    <td>{data.attendance.absentDays}일</td>
                  </tr>
                  <tr>
                    <th scope="row">연장</th>
                    <td>{hours(data.attendance.overtimeMinutes)}시간</td>
                  </tr>
                  <tr>
                    <th scope="row">야간</th>
                    <td>{hours(data.attendance.nightMinutes)}시간</td>
                  </tr>
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>내 급여명세서 (확정분)</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>급여 월</th>
                    <th>지급일</th>
                    <th>실지급액</th>
                  </tr>
                </thead>
                <tbody>
                  {data.payslips.map((slip) => (
                    <tr key={slip.id}>
                      <td>{slip.payMonth}</td>
                      <td>{slip.payDate}</td>
                      <td>{won(slip.netPay)}</td>
                    </tr>
                  ))}
                  {!data.payslips.length && (
                    <tr>
                      <td colSpan={3}>
                        확정한 급여가 없습니다.{" "}
                        <Link to="/hr/payroll">급여 계산 →</Link>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>내 평가</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>연도</th>
                    <th>상태</th>
                    <th>등급</th>
                    <th>평가자</th>
                  </tr>
                </thead>
                <tbody>
                  {data.reviews.map((review) => (
                    <tr key={review.id}>
                      <td>{review.cycleYear}</td>
                      <td>{REVIEW_STATE[review.status] ?? review.status}</td>
                      <td>{review.grade ?? "—"}</td>
                      <td>{review.reviewerCode}</td>
                    </tr>
                  ))}
                  {!data.reviews.length && (
                    <tr>
                      <td colSpan={4}>
                        평가가 없습니다.{" "}
                        <Link to="/hr/reviews">인사 평가 →</Link>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
          </div>
        </>
      )}
    </div>
  );
}
