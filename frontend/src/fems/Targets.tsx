// F-07 목표 대비 실적 — 범위(사업장·설비)별 섹션, 합산하지 않는다 (FS-018g)
// 좁은 화면에서도 달성률·상태가 먼저 보이도록 대상 다음에 둔다.
import { useEffect, useState, type ReactNode } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
type Status = "WITHIN" | "EXCEEDED" | "UNSET" | "NOT_CALCULABLE";
type Row = {
  unit: string;
  actual: string | null;
  target: string | null;
  achievementRate: string | null;
  status: Status;
};
export type SiteRow = Row & { energySourceCode: string | null; name: string };
export type EquipmentRow = Row & {
  equipmentId: number;
  equipmentCode: string;
  equipmentName: string;
  estimatedDays: number;
};
export type TargetData = {
  period: {
    month: string;
    from: string;
    to: string;
    monthToDate: boolean;
  } | null;
  site: SiteRow[];
  equipment: EquipmentRow[];
};
export const STATUS: Record<Status, [string, "normal" | "warning" | "issue"]> =
  {
    WITHIN: ["목표 이내", "normal"],
    EXCEEDED: ["목표 초과", "warning"],
    UNSET: ["미설정", "normal"],
    NOT_CALCULABLE: ["계산 불가", "issue"],
  };
const num = (value: string | null, digits = 1) =>
  value === null
    ? "—"
    : Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
export function TargetTable({
  caption,
  rows,
}: {
  caption: string;
  rows: { key: string; label: ReactNode; row: Row }[];
}) {
  return (
    <div className="table-scroll">
      <table className="emission-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">대상</th>
            <th scope="col" className="num">
              달성률
            </th>
            <th scope="col">상태</th>
            <th scope="col" className="num">
              목표
            </th>
            <th scope="col" className="num">
              실적
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ key, label, row }) => (
            <tr key={key}>
              <th scope="row">{label}</th>
              <td className="num">
                {row.achievementRate === null
                  ? "—"
                  : `${num(row.achievementRate)}%`}
              </td>
              <td>
                <Badge tone={STATUS[row.status][1]}>
                  {STATUS[row.status][0]}
                </Badge>
              </td>
              <td className="num">
                {num(row.target)} {row.target !== null && row.unit}
              </td>
              <td className="num">
                {num(row.actual)} {row.actual !== null && row.unit}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
export function Targets() {
  const { fail } = useSession();
  const [month, setMonth] = useState("");
  const [data, setData] = useState<TargetData>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<TargetData>(
      `/api/v1/fems/targets/performance${month ? `?month=${month}` : ""}`,
      { signal: controller.signal },
    )
      .then((r) => setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month, reload]);
  if (
    error instanceof ApiError &&
    error.error.details?.reason === "MODULE_DISABLED"
  )
    return (
      <EmptyState
        reason="FEMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  return (
    <>
      <PageTitle
        id="F-07"
        title="목표 대비 실적"
        subtitle="범위가 다른 목표는 섹션을 나누고 합산하지 않습니다"
        help="fems/f-07"
      />
      <div className="filter-bar">
        <label>
          조회 월
          <input
            type="month"
            // 처음에는 서버가 정한 달을 보여 준다. 같은 조회를 다시 보내지 않는다.
            value={month || data?.period?.month || ""}
            onChange={(e) => e.target.value && setMonth(e.target.value)}
          />
        </label>
      </div>
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.period ? (
        <EmptyState
          reason="계측값이 없어 실적을 계산할 수 없습니다."
          to="/fems/readings"
          action="계측값 보기"
        />
      ) : (
        <>
          <p className="muted" role="note">
            {data.period.monthToDate
              ? `당월 누계 기준 (${data.period.from} ~ ${data.period.to}). 목표도 같은 기간 기준으로 정했습니다.`
              : `${data.period.from} ~ ${data.period.to} 월 전체 기준.`}{" "}
            달성률 = 실적 ÷ 목표 × 100, 100% 이하면 목표 이내입니다.
          </p>
          <section className="panel" aria-label="사업장 목표">
            <h2>사업장 목표</h2>
            <TargetTable
              caption="에너지원별 목표와 1차에너지 환산 총량 목표"
              rows={data.site.map((r) => ({
                key: r.energySourceCode ?? "TOE",
                label: r.name,
                row: r,
              }))}
            />
          </section>
          <section className="panel" aria-label="설비 목표">
            <h2>설비 목표 · 전력</h2>
            <TargetTable
              caption="설비별 배분 결과(현재 결과) 기준"
              rows={data.equipment.map((r) => ({
                key: String(r.equipmentId),
                label: (
                  <>
                    {r.equipmentCode} {r.equipmentName}
                    {r.estimatedDays > 0 && (
                      <>
                        {" "}
                        <Badge tone="warning">추정 {r.estimatedDays}일</Badge>
                      </>
                    )}
                  </>
                ),
                row: r,
              }))}
            />
          </section>
        </>
      )}
    </>
  );
}
