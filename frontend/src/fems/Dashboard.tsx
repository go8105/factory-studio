// F-01 대시보드 — 이번 달 얼마나 썼고 목표 대비 어떤가 (FS-018f)
// 1차에너지(TOE)는 PRIMARY, 배출량은 EMISSION 계수로 서버가 따로 계산한다.
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import type { SummaryRow } from "./Allocations";
import { formatAt } from "./Readings";
type Converted = {
  sourceCode: string;
  name: string;
  status: "CALCULATED" | "NOT_APPLICABLE" | "FACTOR_MISSING" | "UNIT_MISMATCH";
  consumption: { quantity: string; unit: string };
  toe: string | null;
};
export type DashboardData = {
  period: { month: string; from: string; to: string } | null;
  openAlarms?: {
    id: number;
    ruleCode: string;
    ruleName: string;
    alarmKind: string;
    status: string;
  }[];
  openAlarmCount?: number;
  peak?: string | null;
  generation?: {
    sourceCode: string;
    name: string;
    quantity: string;
    unit: string;
  }[];
  primaryEnergy: {
    total: string;
    unit: string;
    complete: boolean;
    sources: Converted[];
  };
  target: {
    status: "SET" | "UNSET";
    target: string | null;
    actual: string;
    unit: string;
    achievementRate: string | null;
  };
  charge: { total: string; currency: string; complete: boolean };
  emission: { total: string; unit: string; complete: boolean };
  daily: { date: string; toe: string }[];
  topEquipment: SummaryRow[];
  quality: {
    issues: number;
    recent: {
      observedAt: string;
      timezone: string;
      channelName: string;
      quality: string;
    }[];
  };
};
const num = (value: string, digits = 2) =>
  Number(value).toLocaleString("ko-KR", { maximumFractionDigits: digits });
const PARTIAL = "일부 계산 불가 · 합계에서 제외";
const QUALITY_LABEL: Record<string, string> = {
  invalid: "결측",
  estimated: "추정",
  reset: "리셋",
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
  unit: string;
  note: string;
  badge?: ReactNode;
}) {
  return (
    <section className="stat-tile" aria-label={label}>
      <p>{label}</p>
      <strong>
        {value} <span>{unit}</span>
      </strong>
      {badge}
      <small>{note}</small>
    </section>
  );
}
export function TargetTile({ target }: { target: DashboardData["target"] }) {
  if (target.status === "UNSET" || target.achievementRate === null)
    return (
      <Tile
        label="목표 대비"
        value="미설정"
        unit=""
        note="이 달의 사업장 TOE 목표가 없어 달성률을 계산하지 않습니다."
      />
    );
  const within = Number(target.achievementRate) <= 100;
  return (
    <Tile
      label="목표 대비"
      value={num(target.achievementRate, 1)}
      unit="%"
      badge={
        <Badge tone={within ? "normal" : "warning"}>
          {within ? "목표 이내" : "목표 초과"}
        </Badge>
      }
      note={`실적 ${num(target.actual, 3)} ÷ 목표 ${num(target.target ?? "0", 3)} TOE`}
    />
  );
}
// 에너지원별 구성: TOE 환산 후 비중. 용수는 환산 대상이 아니라 막대에서 뺀다.
// 주요 차트 옆 보조 영역이라 에너지원마다 이름·값 한 줄 + 막대 한 줄로 쌓는다.
export function Composition({ sources }: { sources: Converted[] }) {
  const calculated = sources.filter((s) => s.toe !== null);
  const total = calculated.reduce((sum, s) => sum + Number(s.toe), 0);
  return (
    <section className="panel" aria-label="에너지원별 구성">
      <h2>에너지원별 구성 · TOE 환산</h2>
      <ul className="share-list">
        {calculated.map((s) => {
          const share = total ? (Number(s.toe) / total) * 100 : 0;
          return (
            <li key={s.sourceCode}>
              <span>
                {s.name}{" "}
                <small>
                  {num(s.consumption.quantity)} {s.consumption.unit}
                </small>
              </span>
              <span>
                {num(s.toe!, 3)} TOE · {share.toFixed(1)}%
              </span>
              <span className="bar" aria-hidden="true">
                <span style={{ width: `${share}%` }} />
              </span>
            </li>
          );
        })}
      </ul>
      <p className="share-total">
        환산 합계 <strong>{num(String(total), 3)} TOE</strong>
      </p>
      {sources
        .filter((s) => s.toe === null)
        .map((s) => (
          <p key={s.sourceCode} className="muted">
            {s.name}:{" "}
            {s.status === "NOT_APPLICABLE"
              ? "환산 대상 아님"
              : "계수가 없거나 단위가 맞지 않아 계산 불가"}{" "}
            ({num(s.consumption.quantity)} {s.consumption.unit})
          </p>
        ))}
    </section>
  );
}
export function DailyChart({ daily }: { daily: DashboardData["daily"] }) {
  const [hover, setHover] = useState<number>();
  if (!daily.length) return null;
  // 3:2 격자의 주요 차트. 옆 구성 카드와 높이가 비슷하도록 가로로 긴 비율을 쓴다.
  const W = 720;
  const H = 170;
  const pad = { l: 48, r: 16, t: 12, b: 16 };
  const values = daily.map((d) => Number(d.toe));
  const max = Math.max(...values, 0.001);
  const x = (i: number) =>
    pad.l +
    (daily.length === 1 ? 0 : (i / (daily.length - 1)) * (W - pad.l - pad.r));
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  const d = values
    .map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join("");
  const point = hover === undefined ? undefined : daily[hover];
  return (
    <figure className="reading-chart" aria-label="일자별 추이">
      <figcaption>일자별 1차에너지 사용량 (TOE)</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="일자별 TOE 선 그래프"
        onMouseLeave={() => setHover(undefined)}
        onMouseMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - box.left) / box.width) * W;
          const i = Math.round(
            ((px - pad.l) / (W - pad.l - pad.r)) * (daily.length - 1),
          );
          setHover(Math.min(daily.length - 1, Math.max(0, i)));
        }}
      >
        <line className="axis" x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} />
        <line
          className="grid"
          x1={pad.l}
          x2={W - pad.r}
          y1={y(max)}
          y2={y(max)}
        />
        <text className="tick" x={pad.l - 8} y={y(0)} textAnchor="end">
          0
        </text>
        <text className="tick" x={pad.l - 8} y={y(max) + 4} textAnchor="end">
          {num(String(max), 2)}
        </text>
        <path className="series" d={d} />
        {point && (
          <g>
            <line
              className="crosshair"
              x1={x(hover!)}
              x2={x(hover!)}
              y1={pad.t}
              y2={H - pad.b}
            />
            <circle
              className="marker"
              cx={x(hover!)}
              cy={y(Number(point.toe))}
              r={4}
            />
          </g>
        )}
      </svg>
      <p className="chart-tooltip" aria-live="polite">
        {point
          ? `${point.date} · ${num(point.toe, 3)} TOE`
          : `${daily[0].date} ~ ${daily[daily.length - 1].date} · 그래프 위에 커서를 올리면 날짜별 값을 볼 수 있습니다.`}
      </p>
    </figure>
  );
}
export function Dashboard() {
  const { fail } = useSession();
  const [month, setMonth] = useState("");
  const [data, setData] = useState<DashboardData>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<DashboardData>(
      `/api/v1/fems/dashboard${month ? `?month=${month}` : ""}`,
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
        id="F-01"
        title="에너지 개요"
        subtitle={
          data?.period
            ? `${data.period.from} ~ ${data.period.to} · 조회 시 계산`
            : "이번 달 사용량과 목표 대비"
        }
        help="fems/f-01"
        actions={
          <label>
            조회 월
            <input
              type="month"
              // 처음에는 서버가 정한 달을 보여 준다. 같은 조회를 다시 보내지 않는다.
              value={month || data?.period?.month || ""}
              onChange={(e) => e.target.value && setMonth(e.target.value)}
            />
          </label>
        }
      />
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!data ? (
        !error && <Loading delay={300} />
      ) : !data.period ? (
        <EmptyState
          reason="계측값이 없어 개요를 만들 수 없습니다. 기준정보를 먼저 등록하세요."
          to="/fems/energy-sources"
          action="에너지원 등록"
        />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="총 소비"
              value={num(data.primaryEnergy.total, 3)}
              unit="TOE"
              note="1차에너지 환산 후 합산 · 용수 제외"
              badge={
                !data.primaryEnergy.complete && (
                  <Badge tone="warning">{PARTIAL}</Badge>
                )
              }
            />
            <TargetTile target={data.target} />
            <Tile
              label="예상 요금"
              value={num(data.charge.total, 0)}
              unit="원"
              note="기본요금 + 당월 누계 사용량 × 단가"
              badge={
                !data.charge.complete && (
                  <Badge tone="warning">요금제 없는 에너지원 제외</Badge>
                )
              }
            />
            <Tile
              label="배출량"
              value={num(data.emission.total, 3)}
              unit="tCO2eq"
              note="배출계수 적용 · 환산계수와 다른 계수"
              badge={
                !data.emission.complete && (
                  <Badge tone="warning">{PARTIAL}</Badge>
                )
              }
            />
          </div>
          {/* 주요 차트(일자별 추이) + 보조 영역 3:2. 읽는 순서는 화면 폭과 관계없이 같다. */}
          <div className="dashboard-grid has-lead">
            <DailyChart daily={data.daily} />
            <section className="panel" aria-label="에너지 경보">
              <h2>
                진행 중인 경보 {data.openAlarmCount ?? 0}건
                {!!data.openAlarmCount && (
                  <>
                    {" "}
                    <Badge tone="issue">확인 필요</Badge>
                  </>
                )}
              </h2>
              {data.openAlarms?.length ? (
                <ul className="rank-list">
                  {data.openAlarms.map((a) => (
                    <li key={a.id}>
                      <span>
                        {a.ruleCode} {a.ruleName}
                      </span>
                      <span>{a.status === "OPEN" ? "발생" : "확인"}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">진행 중인 경보가 없습니다.</p>
              )}
              {data.generation?.map((g) => (
                <p className="muted" key={g.sourceCode}>
                  {g.name} 발전{" "}
                  {Number(g.quantity).toLocaleString("ko-KR", {
                    maximumFractionDigits: 0,
                  })}{" "}
                  {g.unit} · 역송을 재지 않아 전부 자가소비로 봅니다
                </p>
              ))}
              <p className="muted">
                {/* 계측이 없는 달은 0이 아니라 낼 수 없는 값이다. */}이 달
                수요전력{" "}
                {data.peak
                  ? Number(data.peak).toLocaleString("ko-KR", {
                      maximumFractionDigits: 1,
                    })
                  : "—"}{" "}
                · 1시간 근사
              </p>
              <Link className="text-link" to="/fems/alarms">
                에너지 경보 →
              </Link>
            </section>
            <Composition sources={data.primaryEnergy.sources} />
            <section className="panel" aria-label="설비별 소비 상위 5">
              <h2>설비별 소비 상위 5 · kWh</h2>
              <ol className="rank-list">
                {data.topEquipment.map((q) => (
                  <li key={q.equipmentId}>
                    <span>
                      {q.equipmentCode} {q.equipmentName}
                    </span>
                    <span>{num(q.quantity, 1)} kWh</span>
                  </li>
                ))}
              </ol>
              <Link className="text-link" to="/fems/allocations">
                설비별 배분 보기 →
              </Link>
            </section>
            <section className="panel" aria-label="계측 품질 이상">
              <h2>계측 품질 이상 · {data.quality.issues}건</h2>
              {data.quality.recent.length ? (
                <ul className="rank-list">
                  {data.quality.recent.map((r) => (
                    <li key={`${r.channelName}-${r.observedAt}`}>
                      <span>{r.channelName}</span>
                      <span>
                        {formatAt(r.observedAt, r.timezone)}{" "}
                        <Badge tone="issue">
                          {QUALITY_LABEL[r.quality] ?? r.quality}
                        </Badge>
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">이 달에는 품질 이상 계측값이 없습니다.</p>
              )}
              <Link className="text-link" to="/fems/readings">
                계측 조회 →
              </Link>
            </section>
          </div>
        </>
      )}
    </>
  );
}
