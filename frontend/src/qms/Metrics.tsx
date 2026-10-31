// Q-13 품질 지표 — 발생처별 불량률·PPM, 불량 유형 파레토, 월 추이(UI-02 D 패턴, F72).
// 저장하는 값이 아니라 그때그때 센 값이다. PPM은 불량 '개수'가 있는 곳에서만 낸다.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import { ModuleOff, moduleOff, num, QMS } from "./common";

type KindMetric = {
  lots: number;
  failedLots: number;
  failRate: string | null;
  ppm: string | null;
};
type ParetoRow = { code: string; name: string; count: number };
type ProcessParetoRow = { code: string; name: string; qty: string };
type TrendRow = {
  month: string;
  inspected: number;
  failed: number;
  ppm: string | null;
};
type Metrics = {
  month: string;
  months: string[];
  incoming: KindMetric;
  outgoing: KindMetric;
  customer: { claims: number; qty: string };
  process: {
    records: number;
    inputQty: string;
    defectQty: string;
    ppm: string | null;
  } | null;
  pareto: ParetoRow[];
  processPareto: ProcessParetoRow[] | null;
  trend: TrendRow[];
};

const dash = (v: string | null, unit = "") =>
  v === null
    ? "—"
    : `${Number(v).toLocaleString("ko-KR", {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
      })}${unit}`;

/** 파레토. 건수 막대와 누적 비율을 한 표에서 읽는다. */
function Pareto({
  caption,
  rows,
  unit,
  empty,
}: {
  caption: string;
  rows: { code: string; name: string; value: number }[];
  unit: string;
  empty: string;
}) {
  const total = rows.reduce((sum, r) => sum + r.value, 0);
  let running = 0;
  return (
    <section className="panel" aria-label={caption}>
      <h2>{caption}</h2>
      {rows.length === 0 || total === 0 ? (
        <p className="muted">{empty}</p>
      ) : (
        <div className="table-scroll">
          <table aria-label={caption}>
            <thead>
              <tr>
                <th scope="col">불량</th>
                <th scope="col" className="num">
                  {unit}
                </th>
                <th scope="col" className="num">
                  비율
                </th>
                <th scope="col" className="num">
                  누적
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                running += row.value;
                return (
                  <tr key={`${row.code} ${row.name}`}>
                    <td>
                      {row.code === "—" ? row.name : `${row.code} ${row.name}`}
                    </td>
                    <td className="num">{num(row.value, 3)}</td>
                    <td className="num">
                      {((row.value * 100) / total).toFixed(1)}%
                    </td>
                    <td className="num">
                      {((running * 100) / total).toFixed(1)}%
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

/** 월별 불합격률 꺾은선. 값은 아래 표로도 읽을 수 있다. */
function TrendChart({ trend }: { trend: TrendRow[] }) {
  if (trend.length === 0)
    return (
      <figure className="reading-chart" aria-label="월 추이">
        <figcaption>월 추이</figcaption>
        <p className="muted">확정한 검사가 아직 없습니다.</p>
      </figure>
    );
  const W = 720;
  const H = 180;
  const pad = { l: 40, r: 12, t: 14, b: 26 };
  const rate = (r: TrendRow) =>
    r.inspected === 0 ? 0 : (r.failed * 100) / r.inspected;
  const max = Math.max(...trend.map(rate), 1);
  const x = (i: number) =>
    trend.length === 1
      ? (pad.l + W - pad.r) / 2
      : pad.l + (i * (W - pad.l - pad.r)) / (trend.length - 1);
  const y = (v: number) => H - pad.b - (v / max) * (H - pad.t - pad.b);
  return (
    <figure className="reading-chart" aria-label="월 추이">
      <figcaption>월별 불합격률 (%)</figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="월별 불합격률">
        <line className="axis" x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} />
        <text className="tick" x={pad.l - 6} y={y(max) + 4} textAnchor="end">
          {max.toFixed(0)}
        </text>
        <polyline
          className="series"
          fill="none"
          points={trend.map((r, i) => `${x(i)},${y(rate(r))}`).join(" ")}
        />
        {trend.map((r, i) => (
          <g key={r.month}>
            <circle className="marker" cx={x(i)} cy={y(rate(r))} r={3} />
            <text className="tick" x={x(i)} y={H - 8} textAnchor="middle">
              {r.month.slice(2)}
            </text>
          </g>
        ))}
      </svg>
      <div className="table-scroll">
        <table>
          <caption>월별 검사·불합격·PPM</caption>
          <thead>
            <tr>
              <th scope="col">월</th>
              <th scope="col" className="num">
                검사
              </th>
              <th scope="col" className="num">
                불합격
              </th>
              <th scope="col" className="num">
                불합격률
              </th>
              <th scope="col" className="num">
                PPM
              </th>
            </tr>
          </thead>
          <tbody>
            {trend.map((r) => (
              <tr key={r.month}>
                <td>{r.month}</td>
                <td className="num">{r.inspected}</td>
                <td className="num">{r.failed}</td>
                <td className="num">{rate(r).toFixed(1)}%</td>
                <td className="num">{dash(r.ppm)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </figure>
  );
}

export function Metrics() {
  const { fail } = useSession();
  const [month, setMonth] = useState("");
  const [data, setData] = useState<Metrics>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    setData(undefined);
    api<Metrics>(`${QMS}/metrics${month ? `?month=${month}` : ""}`, {
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
        id="Q-13"
        title="품질 지표"
        subtitle="발생처별 불량률·PPM과 불량 유형 파레토, 월 추이"
        help="qms/q-13"
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
          <p className="muted" role="note">
            저장한 값이 아니라 조회할 때마다 세는 값입니다.{" "}
            <strong>PPM은 불량 개수를 적는 검사에서만 냅니다</strong> — 수입
            검사의 시료 불량 개수와 MES 공정 실적의 불량 수량입니다. 출하 검사와
            고객 클레임에는 개수를 적는 칸이 없어 LOT 불합격률·건수까지만
            보입니다.
          </p>
          <div className="table-scroll section-block">
            <table>
              <caption>발생처별 · {data.month}</caption>
              <thead>
                <tr>
                  <th scope="col">발생처</th>
                  <th scope="col" className="num">
                    대상
                  </th>
                  <th scope="col" className="num">
                    불합격
                  </th>
                  <th scope="col" className="num">
                    불합격률
                  </th>
                  <th scope="col" className="num">
                    PPM
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>수입</td>
                  <td className="num">{data.incoming.lots} LOT</td>
                  <td className="num">{data.incoming.failedLots}</td>
                  <td className="num">{dash(data.incoming.failRate, "%")}</td>
                  <td className="num">{dash(data.incoming.ppm)}</td>
                </tr>
                <tr>
                  <td>공정 (MES)</td>
                  {data.process === null ? (
                    <td className="num" colSpan={4}>
                      MES를 꺼서 읽지 않습니다
                    </td>
                  ) : (
                    <>
                      <td className="num">{data.process.records} 실적</td>
                      <td className="num">{num(data.process.defectQty)}</td>
                      <td className="num">—</td>
                      <td className="num">{dash(data.process.ppm)}</td>
                    </>
                  )}
                </tr>
                <tr>
                  <td>출하</td>
                  <td className="num">{data.outgoing.lots} LOT</td>
                  <td className="num">{data.outgoing.failedLots}</td>
                  <td className="num">{dash(data.outgoing.failRate, "%")}</td>
                  <td className="num">—</td>
                </tr>
                <tr>
                  <td>고객</td>
                  <td className="num">{data.customer.claims} 건</td>
                  <td className="num">{num(data.customer.qty)}</td>
                  <td className="num">—</td>
                  <td className="num">—</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div className="dashboard-grid has-lead">
            <TrendChart trend={data.trend} />
            <Pareto
              caption={`검사 불량 유형 · ${data.month}`}
              unit="건"
              rows={data.pareto.map((r) => ({ ...r, value: r.count }))}
              empty="이 달 불합격 항목이 없습니다."
            />
            {data.processPareto === null ? (
              <section className="panel" aria-label="공정 불량">
                <h2>공정 불량 · {data.month}</h2>
                <p className="muted">MES를 꺼서 공정 불량을 읽지 않습니다.</p>
              </section>
            ) : (
              <Pareto
                caption={`공정 불량 · ${data.month}`}
                unit="수량"
                rows={data.processPareto.map((r) => ({
                  ...r,
                  value: Number(r.qty),
                }))}
                empty="이 달 공정 불량 실적이 없습니다."
              />
            )}
          </div>
          <p className="muted">
            <Link className="text-link" to="/qms/ncrs">
              부적합 보고 →
            </Link>{" "}
            <Link className="text-link" to="/qms/suppliers">
              공급처 품질 →
            </Link>
          </p>
        </>
      )}
    </>
  );
}
