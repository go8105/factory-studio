// H-01 인사 현황 — 인원·입퇴사·근태·연차·자격 만료·평가 진행 (DSN-30 F41, UI-02 D 패턴).
import { useEffect, useState, type ReactNode } from "react";
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

const BASE = "/api/v1/hr";
export const QUAL_KINDS: Record<string, string> = {
  CERT: "자격",
  TRAINING: "교육",
};
type Overview = {
  month: string;
  headcount: {
    departmentCode: string;
    departmentName: string;
    active: number;
    onLeave: number;
    retired: number;
  }[];
  moves: { hires: number; leavers: number };
  attendance: {
    overtimeHours: string;
    nightHours: string;
    holidayHours: string;
    absentDays: number;
  };
  leave: { grantedDays: string; usedDays: string; usageRate: string | null };
  expiring: {
    employeeCode: string;
    employeeName: string;
    qualKind: string;
    qualName: string;
    expiresOn: string;
    expired: boolean;
  }[];
  reviews: {
    cycleYear: string;
    cycleStatus: string;
    total: number;
    confirmed: number;
  }[];
};

function Tile({
  label,
  value,
  unit,
  note,
  badge,
}: {
  label: string;
  value: string;
  unit?: string;
  note: string;
  badge?: ReactNode;
}) {
  return (
    <section className="stat-tile" aria-label={label}>
      <p>{label}</p>
      <strong>
        {value} {unit && <span>{unit}</span>}
      </strong>
      {badge}
      <small>{note}</small>
    </section>
  );
}
const hours = (value: string) => Number(value).toFixed(1);

export function Overview() {
  const { fail } = useSession();
  const [month, setMonth] = useState(thisMonth());
  const [data, setData] = useState<Overview>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Overview>(`${BASE}/overview?month=${month}`, {
      signal: controller.signal,
    })
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
  const total = (data?.headcount ?? []).reduce(
    (sum, row) => ({
      active: sum.active + row.active,
      onLeave: sum.onLeave + row.onLeave,
      retired: sum.retired + row.retired,
    }),
    { active: 0, onLeave: 0, retired: 0 },
  );
  return (
    <div className="page-fill">
      <PageTitle
        id="H-01"
        title="인사 현황"
        subtitle="인원·근태·연차·자격을 한눈에 봅니다"
        help="hr/h-01"
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
          <div className="kpi-grid">
            <Tile
              label="재직 인원"
              value={String(total.active)}
              unit="명"
              note={`휴직 ${total.onLeave} · 퇴직 ${total.retired}`}
            />
            <Tile
              label={`${month} 입·퇴사`}
              value={`${data.moves.hires} / ${data.moves.leavers}`}
              unit="명"
              note="입사 / 퇴사"
            />
            <Tile
              label="연장 근로"
              value={hours(data.attendance.overtimeHours)}
              unit="시간"
              note={`야간 ${hours(data.attendance.nightHours)} · 휴일 ${hours(data.attendance.holidayHours)}시간`}
              badge={
                data.attendance.absentDays > 0 ? (
                  <Badge tone="warning">
                    결근 {data.attendance.absentDays}일
                  </Badge>
                ) : undefined
              }
            />
            <Tile
              label={`${month.slice(0, 4)}년 연차 사용률`}
              value={data.leave.usageRate ?? "—"}
              unit={data.leave.usageRate ? "%" : undefined}
              note={
                data.leave.usageRate
                  ? `발생 ${data.leave.grantedDays} · 사용 ${data.leave.usedDays}일`
                  : "연차 발생을 아직 등록하지 않았습니다"
              }
            />
          </div>
          <div className="dashboard-grid">
            <figure>
              <figcaption>부서별 인원</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>부서</th>
                    <th>재직</th>
                    <th>휴직</th>
                    <th>퇴직</th>
                  </tr>
                </thead>
                <tbody>
                  {data.headcount.map((row) => (
                    <tr key={row.departmentCode}>
                      <td>{row.departmentName}</td>
                      <td>{row.active}</td>
                      <td>{row.onLeave}</td>
                      <td>{row.retired}</td>
                    </tr>
                  ))}
                  {!data.headcount.length && (
                    <tr>
                      <td colSpan={4}>부서가 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>자격·교육 만료 임박 (30일)</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>사원</th>
                    <th>구분</th>
                    <th>이름</th>
                    <th>만료일</th>
                  </tr>
                </thead>
                <tbody>
                  {data.expiring.map((row) => (
                    <tr key={`${row.employeeCode}-${row.qualName}`}>
                      <td>{row.employeeName}</td>
                      <td>{QUAL_KINDS[row.qualKind] ?? row.qualKind}</td>
                      <td>{row.qualName}</td>
                      <td>
                        <Badge tone={row.expired ? "issue" : "warning"}>
                          {row.expiresOn}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {!data.expiring.length && (
                    <tr>
                      <td colSpan={4}>곧 만료되는 자격·교육이 없습니다.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </figure>
            <figure>
              <figcaption>평가 진행</figcaption>
              <table>
                <thead>
                  <tr>
                    <th>연도</th>
                    <th>상태</th>
                    <th>확정 / 전체</th>
                  </tr>
                </thead>
                <tbody>
                  {data.reviews.map((row) => (
                    <tr key={row.cycleYear}>
                      <td>{row.cycleYear}</td>
                      <td>
                        <Badge
                          tone={row.cycleStatus === "OPEN" ? "normal" : "issue"}
                        >
                          {row.cycleStatus === "OPEN" ? "진행 중" : "닫힘"}
                        </Badge>
                      </td>
                      <td>
                        {row.confirmed} / {row.total}
                      </td>
                    </tr>
                  ))}
                  {!data.reviews.length && (
                    <tr>
                      <td colSpan={3}>
                        <Link to="/hr/reviews">
                          평가 기간을 만들면 여기 보입니다 →
                        </Link>
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
