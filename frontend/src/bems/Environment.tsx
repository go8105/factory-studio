// B-03 환경 모니터링 — 구역 탭 · 온도/CO₂/습도 선 그래프 + 설정값 점선 + 값 표 (UI-02 D 패턴).
import { useState } from "react";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  LineChart,
  METRICS,
  METRIC_LABEL,
  ModuleOff,
  moduleOff,
  num,
  time,
  UNIT,
  useGet,
  useLists,
  type Clock,
  type Metric,
  type Setpoints,
  type Zone,
} from "./common";

type Reading = {
  periodStart: string;
  metric: Metric;
  value: string;
  quality: string;
  source: string;
};
type Data = { zoneId: number; readings: Reading[]; setpoints: Setpoints };
type Row = { id: number; at: string } & Partial<Record<Metric, string>>;
const RANGES = [
  [24, "최근 24시간"],
  [48, "최근 48시간"],
  [168, "최근 7일"],
  [336, "최근 14일"],
] as const;

const day = (d: Date) =>
  d.toLocaleDateString("sv-SE", { timeZone: "Asia/Seoul" });

export function Environment() {
  const zones = useLists<[Zone[]]>(["/zones"]);
  const clock = useGet<Clock>("/simulation/clock");
  const [zoneId, setZoneId] = useState<number>();
  const [hours, setHours] = useState(48);
  const [table, setTable] = useState(false);
  const active = zones.data?.[0].filter((z) => z.isActive) ?? [];
  const zone = zoneId ?? active[0]?.id;
  // 조회 끝 = 시뮬레이션 마지막 관측 구간(다음 구간 − 1시간)의 날짜.
  const end = clock.data
    ? new Date(Date.parse(clock.data.next) - 3_600_000)
    : null;
  const path =
    zone && end
      ? `/environment?zoneId=${zone}&from=${day(new Date(end.getTime() - hours * 3_600_000))}&to=${day(end)}`
      : null;
  const { data, error, reload } = useGet<Data>(path);
  if (moduleOff(zones.error) || moduleOff(error)) return <ModuleOff />;
  const since = end ? end.getTime() - (hours - 1) * 3_600_000 : 0;
  const readings = (data && data.zoneId === zone ? data.readings : []).filter(
    (r) => Date.parse(r.periodStart) >= since,
  );
  const series = (m: Metric) => ({
    label: METRIC_LABEL[m],
    points: readings
      .filter((r) => r.metric === m)
      .map((r) => ({
        at: r.periodStart,
        value: Number(r.value),
        simulated: r.source === "SIMULATION",
      })),
  });
  const byHour = new Map<string, Row>();
  for (const r of readings) {
    const row = byHour.get(r.periodStart) ?? {
      id: byHour.size,
      at: r.periodStart,
    };
    row[r.metric] = r.value;
    byHour.set(r.periodStart, row);
  }
  const rows = [...byHour.values()].reverse();
  // 센서가 없는 지표는 칸도 그래프도 만들지 않는다 — 구역마다 둔 지표가 다르다.
  const measured = new Set(readings.map((r) => r.metric));
  const shown = METRICS.filter((m) => measured.has(m));
  const columns: Column<Row>[] = [
    { key: "at", label: "시각", render: (r) => time(r.at) },
    ...shown.map((m) => ({
      key: m,
      label: `${METRIC_LABEL[m]} ${UNIT[m]}`,
      render: (r: Row) => num(r[m]),
    })),
  ];
  const sp = data?.setpoints;

  return (
    <>
      <PageTitle
        id="B-03"
        title="환경 모니터링"
        subtitle="구역별 1시간 관측(온도·습도·CO₂·미세먼지·조도·재실)과 공조 설정값"
        help="bems/b-03"
        actions={
          <label>
            기간
            <select
              value={hours}
              onChange={(e) => setHours(Number(e.target.value))}
            >
              {RANGES.map(([h, label]) => (
                <option key={h} value={h}>
                  {label}
                </option>
              ))}
            </select>
          </label>
        }
      />
      <ErrorNotice error={zones.error ?? clock.error ?? error} retry={reload} />
      {!zones.data ? (
        !zones.error && <Loading />
      ) : !active.length ? (
        <EmptyState
          reason="구역이 없습니다. 구역과 환경 센서를 먼저 등록하세요."
          to="/bems/zones"
          action="구역·계측으로"
        />
      ) : (
        <>
          <div className="tabs" role="tablist">
            {active.map((z) => (
              <button
                key={z.id}
                type="button"
                aria-pressed={zone === z.id}
                className={zone === z.id ? "active" : ""}
                onClick={() => setZoneId(z.id)}
              >
                {z.name}
              </button>
            ))}
          </div>
          {!data || data.zoneId !== zone ? (
            !error && <Loading delay={300} />
          ) : (
            <>
              <LineChart
                caption="실내 온도"
                unit="℃"
                series={series("TEMP")}
                references={
                  sp
                    ? [
                        { label: "냉방 설정", value: Number(sp.COOL_TEMP) },
                        { label: "난방 설정", value: Number(sp.HEAT_TEMP) },
                      ]
                    : []
                }
              />
              <LineChart
                caption="CO₂"
                unit="ppm"
                series={series("CO2")}
                references={
                  sp ? [{ label: "CO₂ 상한", value: Number(sp.CO2_MAX) }] : []
                }
              />
              <LineChart caption="습도" unit="%" series={series("HUMIDITY")} />
              {(["PM25", "LUX", "OCCUPANCY"] as Metric[])
                .filter((m) => measured.has(m))
                .map((m) => (
                  <LineChart
                    key={m}
                    caption={METRIC_LABEL[m]}
                    unit={UNIT[m]}
                    series={series(m)}
                  />
                ))}
              <button
                type="button"
                className="secondary"
                aria-expanded={table}
                onClick={() => setTable(!table)}
              >
                {table ? "값 표 닫기" : "값 표 보기"}
              </button>
              {table && (
                <DataTable
                  rows={rows}
                  columns={columns}
                  caption="환경 관측 값"
                  offset={0}
                  total={rows.length}
                  limit={rows.length || 1}
                  onPage={() => undefined}
                />
              )}
            </>
          )}
        </>
      )}
    </>
  );
}
