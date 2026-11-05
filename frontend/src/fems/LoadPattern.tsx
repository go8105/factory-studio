// F-16 부하 패턴·피크 — 시간대·요일 프로파일, 기저부하, 수요전력 (DSN-15 F25·F26)
// 저장하지 않고 조회할 때마다 센다. 수요전력은 1시간 계측의 최대값 근사다(Q2).
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";

type DayKind = "WEEKDAY" | "SATURDAY" | "HOLIDAY";
const DAY_KIND_LABEL: Record<DayKind, string> = {
  WEEKDAY: "평일",
  SATURDAY: "토요일",
  HOLIDAY: "휴일",
};
const DAY_KINDS: DayKind[] = ["WEEKDAY", "SATURDAY", "HOLIDAY"];
const HOURS = Array.from({ length: 24 }, (_, i) => i);

type Row = {
  dayKind: DayKind;
  hour: number;
  days: number;
  average: string;
  max: string;
};
type Pattern = {
  month: string | null;
  source: { id: number; sourceCode: string; name: string; unit: string } | null;
  sources?: { id: number; sourceCode: string; name: string }[];
  profile: Row[];
  peak: {
    value: string;
    date: string;
    hour: number;
    contractKw: string | null;
    contractRatio: string | null;
  } | null;
  baseLoad: { value: string; average: string; hours: string } | null;
  hasHolidayCalendar: boolean;
};

const num = (v: string, digits = 1) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });

/** 시간 × 요일 평균 히트맵. 색이 아니라 숫자와 막대 길이로 읽는다(저채도 기준). */
function Heatmap({ profile, unit }: { profile: Row[]; unit: string }) {
  const byKey = new Map(profile.map((r) => [`${r.dayKind}:${r.hour}`, r]));
  const peak = Math.max(...profile.map((r) => Number(r.average)), 0);
  if (!profile.length)
    return <p className="muted">이 달에 계측값이 없습니다.</p>;
  return (
    <div className="table-scroll">
      <table aria-label="시간대·요일 평균 사용량">
        <thead>
          <tr>
            <th scope="col">시</th>
            {DAY_KINDS.map((kind) => (
              <th key={kind} scope="col" className="num">
                {DAY_KIND_LABEL[kind]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {HOURS.map((hour) => (
            <tr key={hour}>
              <th scope="row">{String(hour).padStart(2, "0")}</th>
              {DAY_KINDS.map((kind) => {
                const row = byKey.get(`${kind}:${hour}`);
                if (!row)
                  return (
                    <td key={kind} className="num muted">
                      —
                    </td>
                  );
                const share = peak ? (Number(row.average) * 100) / peak : 0;
                return (
                  <td key={kind} className="num">
                    <span
                      className="bar-cell"
                      style={{ "--share": `${share}%` } as React.CSSProperties}
                    >
                      {num(row.average)}
                    </span>
                    <small className="muted"> {unit}</small>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function LoadPattern() {
  const { fail } = useSession();
  const [month, setMonth] = useState("");
  const [sourceId, setSourceId] = useState("");
  const [data, setData] = useState<Pattern>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    const query = new URLSearchParams(
      Object.entries({ month, energySourceId: sourceId }).filter(([, v]) => v),
    );
    api<Pattern>(`/api/v1/fems/load-pattern?${query}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month, sourceId, reload]);

  const unit = data?.source?.unit ?? "";
  return (
    <>
      <PageTitle
        id="F-16"
        title="부하 패턴·피크"
        subtitle="시간대·요일별 사용 모양과 수요전력 최대값"
        help="fems/f-16"
        actions={
          <label>
            조회 월
            <input
              type="month"
              value={month || data?.month || ""}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
        }
      />
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.source ? (
        <p className="muted">계측할 에너지원이 없습니다.</p>
      ) : (
        <>
          <div className="filter-bar">
            <label>
              에너지원
              <select
                value={sourceId || String(data.source.id)}
                onChange={(e) => setSourceId(e.target.value)}
              >
                {(data.sources ?? []).map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.sourceCode} {s.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="kpi-grid">
            <section className="stat-tile" aria-label="수요전력">
              <p>수요전력</p>
              <strong>
                {data.peak ? num(data.peak.value) : "—"}{" "}
                {data.peak && <span>{unit}</span>}
              </strong>
              <small>
                {data.peak
                  ? `${data.peak.date} ${String(data.peak.hour).padStart(2, "0")}시 · 1시간 근사`
                  : "이 달 계측값이 없습니다"}
              </small>
            </section>
            <section className="stat-tile" aria-label="계약전력 대비">
              <p>계약전력 대비</p>
              <strong>
                {data.peak?.contractRatio
                  ? `${num(data.peak.contractRatio)} %`
                  : "계산 불가"}
              </strong>
              <small>
                {/* 계약전력이 없으면 0%가 아니라 낼 수 없는 값이다. */}
                {data.peak?.contractKw
                  ? `계약전력 ${num(data.peak.contractKw)} kW`
                  : "적용 요금제에 계약전력이 없습니다"}
              </small>
            </section>
            <section className="stat-tile" aria-label="기저부하">
              <p>기저부하</p>
              <strong>
                {data.baseLoad ? num(data.baseLoad.value) : "—"}{" "}
                {data.baseLoad && <span>{unit}</span>}
              </strong>
              <small>
                {data.baseLoad
                  ? `${data.baseLoad.hours}시 최솟값 · 평균 ${num(data.baseLoad.average)}`
                  : "계측값이 없습니다"}
              </small>
            </section>
          </div>
          <p className="muted" role="note">
            <strong>수요전력은 1시간 계측의 최대값으로 근사합니다.</strong> 15분
            수요를 따로 재지 않으므로 실제 최대수요전력보다 낮게 나옵니다.
            {!data.hasHolidayCalendar && (
              <>
                {" "}
                휴일 달력이 비어 있어 <strong>일요일만 휴일</strong>로
                보았습니다.
              </>
            )}
          </p>
          <section className="panel" aria-label="시간대·요일 프로파일">
            <h2>
              시간대·요일 평균 · {data.month}{" "}
              {!data.hasHolidayCalendar && (
                <Badge tone="warning">휴일 달력 없음</Badge>
              )}
            </h2>
            <Heatmap profile={data.profile} unit={unit} />
          </section>
        </>
      )}
    </>
  );
}
