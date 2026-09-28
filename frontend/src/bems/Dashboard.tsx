// B-01 건물 대시보드 — KPI 4개 + 최근 7일 분해 + 활성 경보 + 구역 카드(UI-02 D 패턴, F-01 기준).
import { type ReactNode } from "react";
import { Link } from "react-router-dom";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  AdvanceControl,
  ModuleOff,
  moduleOff,
  num,
  ruleText,
  SEVERITY_LABEL,
  ShareBars,
  SOURCE_LABEL,
  STATE_LABEL,
  STATUS_LABEL,
  time,
  useGet,
  type Alarm,
  type BreakdownRow,
  type Metric,
  type Setpoints,
  type State,
  type Zone,
} from "./common";

type DashboardData = {
  yesterday: string;
  week: BreakdownRow[] | null;
  zones: (Zone & {
    environment: Partial<Record<Metric, string>>;
    setpoints: Setpoints;
    hvac: {
      code: string;
      state: State;
      controlSource: "SCHEDULE" | "MANUAL";
    }[];
  })[];
  alarms: Alarm[];
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

const pct = (part: string, whole: string) =>
  Number(whole) ? num((Number(part) / Number(whole)) * 100) : "—";

export function Dashboard() {
  const { data, error, reload } = useGet<DashboardData>("/dashboard");
  if (moduleOff(error)) return <ModuleOff />;
  const day = data?.week?.find((r) => r.period === data.yesterday);
  const raised = data?.alarms.filter((a) => a.status === "raised").length ?? 0;
  const off = data && data.week === null;

  return (
    <>
      <PageTitle
        id="B-01"
        title="건물 개요"
        subtitle="사업장 전력 중 공용(조명·공조·사무동) 몫과 구역 환경·공조 운전"
        help="bems/b-01"
        actions={<AdvanceControl onDone={() => reload()} />}
      />
      <ErrorNotice error={error} retry={() => reload()} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="어제 사업장 전력"
              value={off ? "계산 불가" : num(day?.site, 0)}
              unit={off ? undefined : "kWh"}
              note={
                off ? "FEMS 꺼짐" : `${data.yesterday} · FEMS 최상위 계측기`
              }
            />
            <Tile
              label="공용 비율"
              value={off || !day ? "—" : pct(day.common, day.site)}
              unit={off || !day ? undefined : "%"}
              note={off ? "FEMS 꺼짐 · 계산 불가" : "공용 계측 ÷ 사업장 전력"}
            />
            <Tile
              label="활성 경보"
              value={String(data.alarms.length)}
              unit="건"
              note={`확인 대기 ${raised}`}
              badge={
                raised > 0 && (
                  <Link to="/bems/alarms">
                    <Badge tone="issue">확인 필요</Badge>
                  </Link>
                )
              }
            />
            <Tile
              label="미계측 잔여"
              value={off || !day ? "—" : pct(day.residual, day.site)}
              unit={off || !day ? undefined : "%"}
              note={off ? "FEMS 꺼짐 · 계산 불가" : "사업장 − 제조 − 공용"}
              badge={
                data.week?.some((r) => r.mismatch) && (
                  <Link to="/bems/breakdown">
                    <Badge tone="issue">불일치</Badge>
                  </Link>
                )
              }
            />
          </div>
          <div className="dashboard-grid has-lead">
            <section className="panel" aria-label="최근 7일 분해">
              {data.week ? (
                <ShareBars rows={data.week} caption="최근 7일 분해" />
              ) : (
                <p className="muted">
                  FEMS를 사용하지 않도록 설정해 분해를 계산하지 않습니다.
                </p>
              )}
              <Link className="text-link" to="/bems/breakdown">
                에너지 분해 →
              </Link>
            </section>
            <section className="panel" aria-label="활성 경보">
              <h2>활성 경보</h2>
              {data.alarms.length ? (
                <ul className="rank-list">
                  {data.alarms.map((a) => (
                    <li key={a.id}>
                      <span>
                        {a.zoneName} {ruleText(a)}
                      </span>
                      <span>
                        <Badge
                          tone={a.severity === "CRITICAL" ? "issue" : "warning"}
                        >
                          {SEVERITY_LABEL[a.severity]}
                        </Badge>{" "}
                        {STATUS_LABEL[a.status]} · {time(a.raisedAt)}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">발생 중인 경보가 없습니다.</p>
              )}
              <Link className="text-link" to="/bems/alarms">
                경보 →
              </Link>
            </section>
          </div>
          <div className="bems-zones">
            {data.zones.map((z) => (
              <section
                key={z.id}
                className="panel"
                aria-label={`${z.name} 현황`}
              >
                <h2>{z.name}</h2>
                <p>
                  {num(z.environment.TEMP)}℃ · 습도{" "}
                  {num(z.environment.HUMIDITY)}% · CO₂{" "}
                  {num(z.environment.CO2, 0)} ppm
                </p>
                <p className="muted">
                  냉방 {num(z.setpoints.COOL_TEMP)}℃ · 난방{" "}
                  {num(z.setpoints.HEAT_TEMP)}℃ · CO₂ 상한{" "}
                  {num(z.setpoints.CO2_MAX, 0)} ppm
                </p>
                {z.hvac.map((h) => (
                  <p key={h.code}>
                    {h.code} {STATE_LABEL[h.state]}(
                    {SOURCE_LABEL[h.controlSource]})
                  </p>
                ))}
              </section>
            ))}
          </div>
        </>
      )}
    </>
  );
}
