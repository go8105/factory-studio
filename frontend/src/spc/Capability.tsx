// S-03 공정능력 — Cp·Cpk·히스토그램(LSL·USL 선) (UI-02 D 패턴). 값은 조회할 때 계산한다(D43).
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
} from "../shared/components";
import {
  CharacteristicSelect,
  JUDGEMENT_LABEL,
  JUDGEMENT_TONE,
  ModuleOff,
  moduleOff,
  num,
  spec,
  useCharacteristic,
  useGet,
  type Characteristic,
  type Judgement,
} from "./common";

type Bin = { from: string; to: string; count: number };
type CapabilityData = {
  characteristic: Characteristic;
  subgroupCount: number;
  minimum: number;
  openSignals: number;
  insufficient: boolean;
  mu?: string;
  sigma?: string;
  cp?: string | null;
  cpk?: string | null;
  judgement?: Judgement | null;
  histogram?: Bin[];
};

const monthAgo = () =>
  new Date(Date.now() - 60 * 86_400_000).toISOString().slice(0, 10);

function Histogram({ data }: { data: CapabilityData }) {
  const bins = data.histogram ?? [];
  const c = data.characteristic;
  const W = 720;
  const H = 180;
  const pad = { l: 36, r: 12, t: 16, b: 24 };
  const marks = [
    ["LSL", c.lsl],
    ["USL", c.usl],
    ["목표", c.target],
  ].filter((m): m is [string, string] => m[1] != null);
  const lo = Math.min(Number(bins[0].from), ...marks.map((m) => Number(m[1])));
  const hi = Math.max(
    Number(bins[bins.length - 1].to),
    ...marks.map((m) => Number(m[1])),
  );
  const span = hi - lo || 1;
  const x = (v: number) => pad.l + ((v - lo) / span) * (W - pad.l - pad.r);
  const max = Math.max(...bins.map((b) => b.count), 1);
  const h = (n: number) => (n / max) * (H - pad.t - pad.b);
  return (
    <figure className="reading-chart" aria-label="측정값 분포">
      <figcaption>측정값 분포 ({c.unit})</figcaption>
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="측정값 히스토그램과 규격선"
      >
        <line
          className="axis"
          x1={pad.l}
          x2={W - pad.r}
          y1={H - pad.b}
          y2={H - pad.b}
        />
        {bins.map((b) => (
          <g key={b.from}>
            <title>{`${num(b.from, c.decimals)}~${num(b.to, c.decimals)} · ${b.count}개`}</title>
            <rect
              className="spc-bar"
              x={x(Number(b.from)) + 1}
              y={H - pad.b - h(b.count)}
              width={Math.max(x(Number(b.to)) - x(Number(b.from)) - 2, 1)}
              height={h(b.count)}
            />
          </g>
        ))}
        {marks.map(([name, v]) => (
          <g key={name}>
            <line
              className={name === "목표" ? "spc-cl" : "spc-spec"}
              x1={x(Number(v))}
              x2={x(Number(v))}
              y1={pad.t}
              y2={H - pad.b}
            />
            <text
              className="tick"
              x={x(Number(v))}
              y={pad.t - 4}
              textAnchor="middle"
            >
              {name} {num(v, c.decimals)}
            </text>
          </g>
        ))}
      </svg>
    </figure>
  );
}

export function Capability() {
  const list = useGet<Characteristic[]>("/characteristics");
  const { current, select, query } = useCharacteristic(list.data);
  const [from, setFrom] = useState(monthAgo);
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ from: monthAgo(), to: "" });
  const cap = useGet<CapabilityData>(
    current
      ? `/characteristics/${current.id}/capability?from=${applied.from}${applied.to ? `&to=${applied.to}` : ""}`
      : null,
  );
  if (moduleOff(list.error) || moduleOff(cap.error)) return <ModuleOff />;
  const data = cap.data;
  return (
    <>
      <PageTitle
        id="S-03"
        title="공정능력"
        subtitle="규격 대비 공정의 폭(Cp)과 치우침까지 본 여유(Cpk)"
        help="spc/s-03"
      />
      <ErrorNotice error={list.error ?? cap.error} retry={() => cap.reload()} />
      {!list.data ? (
        !list.error && <Loading />
      ) : !list.data.length ? (
        <EmptyState
          reason="관리 특성이 없습니다."
          to="/spc/characteristics"
          action="관리 특성 등록"
        />
      ) : (
        <>
          <form
            className="filter-bar"
            onSubmit={(e) => {
              e.preventDefault();
              setApplied({ from, to });
            }}
          >
            <CharacteristicSelect
              list={list.data}
              value={current?.id}
              onChange={select}
            />
            <label>
              시작
              <input
                type="date"
                value={from}
                onChange={(e) => setFrom(e.target.value)}
              />
            </label>
            <label>
              종료
              <input
                type="date"
                value={to}
                onChange={(e) => setTo(e.target.value)}
              />
            </label>
            <button type="submit">조회</button>
            <Link to={`/spc/chart${query}`}>관리도 →</Link>
          </form>
          {!data ? (
            !cap.error && <Loading />
          ) : data.insufficient ? (
            <EmptyState
              reason={`유효 부분군이 ${data.minimum}개 이상이어야 계산합니다(현재 ${data.subgroupCount}개).`}
              to={`/spc/measure${query}`}
              action="측정 입력"
            />
          ) : (
            <>
              <p className="muted">규격 {spec(data.characteristic)}</p>
              <div className="kpi-grid">
                <section className="stat-tile" aria-label="Cp">
                  <p>Cp</p>
                  <strong>{data.cp == null ? "—" : num(data.cp, 2)}</strong>
                  <small>
                    {data.cp == null
                      ? "한쪽 규격 — 계산 안 함"
                      : "(USL − LSL) ÷ 6σ̂"}
                  </small>
                </section>
                <section className="stat-tile" aria-label="Cpk">
                  <p>Cpk</p>
                  <strong>{num(data.cpk, 2)}</strong>
                  {data.judgement && (
                    <Badge tone={JUDGEMENT_TONE[data.judgement]}>
                      {JUDGEMENT_LABEL[data.judgement]}
                    </Badge>
                  )}
                  <small>≥ 1.33 충분 · 1.00~1.33 주의 · 1.00 미만 부족</small>
                </section>
                <section className="stat-tile" aria-label="평균">
                  <p>평균 μ</p>
                  <strong>
                    {num(data.mu, data.characteristic.decimals + 1)}
                  </strong>
                  <small>X̄의 평균</small>
                </section>
                <section className="stat-tile" aria-label="표준편차 추정">
                  <p>σ̂ (R̄/d2)</p>
                  <strong>
                    {num(data.sigma, data.characteristic.decimals + 2)}
                  </strong>
                  <small>부분군 {data.subgroupCount}개</small>
                </section>
              </div>
              {data.openSignals > 0 && (
                <p role="note" className="spc-note">
                  이 기간에 미조치 이상이 {data.openSignals}건 있습니다. 관리
                  상태가 아니면 공정능력 해석에 주의하세요.{" "}
                  <Link to={`/spc/signals${query}`}>이상·조치 →</Link>
                </p>
              )}
              <Histogram data={data} />
              <details>
                <summary>계산식</summary>
                <p>
                  σ̂ = R̄ ÷ d2(n=5: 2.326) · Cp = (USL − LSL) ÷ 6σ̂ · Cpk = min(USL
                  − μ, μ − LSL) ÷ 3σ̂. 무효 부분군은 빠집니다.
                </p>
              </details>
            </>
          )}
        </>
      )}
    </>
  );
}
