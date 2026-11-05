// Q-01 품질 대시보드 — KPI 4개 + 주요 차트·보조 영역(UI-02 D 패턴, F-01 기준).
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  ModuleOff,
  moduleOff,
  QMS,
  time,
  type Hold,
  type Inspection,
} from "./common";

type DashboardData = {
  month: string;
  inspected: number;
  passRate: string | null;
  activeHolds: number;
  pendingLots: number | null;
  daily: { date: string; inspected: number; failed: number }[];
  topDefects: { code: string; name: string; count: number }[];
  recentFails: Inspection[];
  holds: Hold[];
  incomingPending: number | null;
  openNcrs: number;
  openCapas: number;
  openClaims: number;
  gaugesDue: number;
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

/** 일자별 검사 수(막대)와 불합격 수(진한 부분). 값은 막대 아래 표로도 읽을 수 있다. */
function DailyBars({ daily }: { daily: DashboardData["daily"] }) {
  if (!daily.length)
    return (
      <figure className="reading-chart" aria-label="일자별 검사">
        <figcaption>일자별 검사 · 불합격</figcaption>
        <p className="muted">이 달에 확정한 검사가 없습니다.</p>
      </figure>
    );
  const W = 720;
  const H = 170;
  const pad = { l: 36, r: 12, t: 12, b: 22 };
  const max = Math.max(...daily.map((d) => d.inspected), 1);
  const slot = (W - pad.l - pad.r) / daily.length;
  const bar = Math.min(28, slot * 0.6);
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  return (
    <figure className="reading-chart" aria-label="일자별 검사">
      <figcaption>일자별 검사 · 불합격 (건)</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="일자별 검사 수와 불합격 수 막대 그래프"
      >
        <line className="axis" x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} />
        <text className="tick" x={pad.l - 6} y={y(max) + 4} textAnchor="end">
          {max}
        </text>
        <text className="tick" x={pad.l - 6} y={y(0)} textAnchor="end">
          0
        </text>
        {daily.map((d, i) => {
          const x = pad.l + slot * i + (slot - bar) / 2;
          return (
            <g key={d.date}>
              <title>{`${d.date} · 검사 ${d.inspected} · 불합격 ${d.failed}`}</title>
              <rect
                x={x}
                y={y(d.inspected)}
                width={bar}
                height={y(0) - y(d.inspected)}
                fill="var(--accent-soft)"
              />
              <rect
                x={x}
                y={y(d.failed)}
                width={bar}
                height={y(0) - y(d.failed)}
                fill="var(--danger-fg)"
              />
              <text
                className="tick"
                x={x + bar / 2}
                y={H - 6}
                textAnchor="middle"
              >
                {d.date.slice(8)}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="chart-tooltip">
        옅은 막대 = 검사 수 · 진한 막대 = 불합격 수. 막대 위에 커서를 올리면
        날짜별 값을 볼 수 있습니다.
      </p>
    </figure>
  );
}

/** F71 미결 업무. 숫자만 보여 주고 끝내지 않고 처리할 화면으로 바로 보낸다. */
function OpenWork({ data }: { data: DashboardData }) {
  const rows: { to: string; label: string; value: string; warn: boolean }[] = [
    {
      to: "/qms/pending",
      label: "수입 검사 대기",
      // WMS를 꺼 두면 0건이 아니라 읽을 수 없는 것이다.
      value:
        data.incomingPending === null
          ? "조회 불가"
          : `${data.incomingPending}건`,
      warn: (data.incomingPending ?? 0) > 0,
    },
    {
      to: "/qms/ncrs",
      label: "미결 부적합",
      value: `${data.openNcrs}건`,
      warn: data.openNcrs > 0,
    },
    {
      to: "/qms/capas",
      label: "미결 시정·예방 조치",
      value: `${data.openCapas}건`,
      warn: data.openCapas > 0,
    },
    {
      to: "/qms/claims",
      label: "열린 클레임",
      value: `${data.openClaims}건`,
      warn: data.openClaims > 0,
    },
    {
      to: "/qms/gauges",
      label: "교정 도래 계측기",
      value: `${data.gaugesDue}대`,
      warn: data.gaugesDue > 0,
    },
  ];
  return (
    <section className="panel" aria-label="미결 업무">
      <h2>미결 업무</h2>
      <ul className="rank-list">
        {rows.map((row) => (
          <li key={row.to}>
            <Link className="text-link" to={row.to}>
              {row.label}
            </Link>
            <span>
              {row.warn ? <Badge tone="issue">{row.value}</Badge> : row.value}
            </span>
          </li>
        ))}
      </ul>
    </section>
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
    api<DashboardData>(`${QMS}/dashboard${month ? `?month=${month}` : ""}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month, reload]);
  if (moduleOff(error)) return <ModuleOff />;

  return (
    <>
      <PageTitle
        id="Q-01"
        title="품질 개요"
        subtitle="이번 달 검사·합격률과 보류 중인 LOT"
        help="qms/q-01"
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
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="검사"
              value={String(data.inspected)}
              unit="건"
              note="이 달 확정 검사"
            />
            <Tile
              label="합격률"
              value={data.passRate ?? "계산 불가"}
              unit={data.passRate === null ? undefined : "%"}
              note={
                data.passRate === null
                  ? "확정 검사가 없어 계산하지 않습니다"
                  : "합격 ÷ 확정 검사"
              }
            />
            <Tile
              label="활성 보류"
              value={String(data.activeHolds)}
              unit="LOT"
              note="보류 중(패킹을 막지 않음)"
              badge={
                data.activeHolds > 0 && <Badge tone="issue">처분 필요</Badge>
              }
            />
            <Tile
              label="검사 대기"
              value={
                data.pendingLots === null
                  ? "조회 불가"
                  : String(data.pendingLots)
              }
              unit={data.pendingLots === null ? undefined : "LOT"}
              note={
                data.pendingLots === null
                  ? "MES를 꺼서 대기 LOT을 읽지 않습니다"
                  : "MES 완료 LOT 중 미검사"
              }
            />
          </div>
          <div className="dashboard-grid has-lead">
            <DailyBars daily={data.daily} />
            <OpenWork data={data} />
            <section className="panel" aria-label="불량 유형 상위">
              <h2>불량 유형 상위 5 · {data.month}</h2>
              {data.topDefects.length ? (
                <ol className="rank-list">
                  {data.topDefects.map((d) => (
                    <li key={d.code}>
                      <span>
                        {d.code} {d.name}
                      </span>
                      <span>{d.count}건</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="muted">이 달 불합격 항목이 없습니다.</p>
              )}
              <Link className="text-link" to="/qms/metrics">
                품질 지표 →
              </Link>
            </section>
            <section className="panel" aria-label="활성 보류 LOT">
              <h2>활성 보류 LOT · {data.holds.length}건</h2>
              {data.holds.length ? (
                <ul className="rank-list">
                  {data.holds.slice(0, 5).map((h) => (
                    <li key={h.id}>
                      <span>
                        {h.lotNo} · {h.itemCode}
                      </span>
                      <span>{time(h.heldAt)}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">보류 중인 LOT이 없습니다.</p>
              )}
              <Link className="text-link" to="/qms/holds">
                품질 보류 →
              </Link>
            </section>
            <section className="panel" aria-label="최근 불합격 검사">
              <h2>최근 불합격 검사</h2>
              {data.recentFails.length ? (
                <ul className="rank-list">
                  {data.recentFails.map((i) => (
                    <li key={i.id}>
                      <span>
                        {i.inspectionNo} · {i.lotNo}
                      </span>
                      <span>{i.inspectedOn}</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">불합격 검사가 없습니다.</p>
              )}
              <Link className="text-link" to="/qms/inspections">
                검사 →
              </Link>
            </section>
          </div>
        </>
      )}
    </>
  );
}
