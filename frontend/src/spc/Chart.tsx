// S-02 관리도 — X̄·R 관리도 + 값 표 (UI-02 D 패턴). SPC 시연 화면.
// 규격선(LSL·USL)은 그리지 않는다 — 관리 한계와 헷갈리지 않게 규격은 S-03에서 본다.
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  CharacteristicSelect,
  chartKeys,
  CHART_LABEL,
  ControlChart,
  ModuleOff,
  moduleOff,
  num,
  RULE_LABEL,
  STATUS_LABEL,
  time,
  useCharacteristic,
  useGet,
  type Characteristic,
  type ChartData,
  type Point,
} from "./common";

const monthAgo = () =>
  new Date(Date.now() - 60 * 86_400_000).toISOString().slice(0, 10);

export function Chart() {
  const list = useGet<Characteristic[]>("/characteristics");
  const { current, select, query } = useCharacteristic(list.data);
  const [from, setFrom] = useState(monthAgo);
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ from: monthAgo(), to: "" });
  const chart = useGet<ChartData>(
    current
      ? `/characteristics/${current.id}/chart?from=${applied.from}${applied.to ? `&to=${applied.to}` : ""}`
      : null,
  );
  const navigate = useNavigate();
  if (moduleOff(list.error) || moduleOff(chart.error)) return <ModuleOff />;
  const data = chart.data;
  const openSignal = (p: Point) => {
    const s = p.signals.find((x) => x.status !== "void");
    if (s) navigate(`/spc/signals?c=${current?.id}&signal=${s.id}`);
  };
  const latest = data?.limits[data.limits.length - 1];
  const digits = (data?.characteristic.decimals ?? 3) + 1;
  const [position, dispersion] = chartKeys(
    data?.characteristic ?? { chartType: "XBAR_R" },
  );
  const columns: Column<Point>[] = [
    {
      key: "measuredAt",
      label: "측정 시각",
      render: (p) => time(p.measuredAt),
    },
    { key: "lotNo", label: "LOT" },
    { key: "equipmentCode", label: "설비" },
    {
      key: "xbar",
      label: CHART_LABEL[position],
      render: (p) => num(p.xbar, digits),
    },
    {
      key: "r",
      label: CHART_LABEL[dispersion],
      render: (p) => num(p.r, digits),
    },
    {
      key: "limitVersion",
      label: "한계",
      render: (p) => (p.limitVersion ? `v${p.limitVersion}` : "미게시"),
    },
    {
      key: "signals",
      label: "판정",
      render: (p) =>
        p.status === "void" ? (
          <Badge>무효</Badge>
        ) : p.signals.length ? (
          p.signals.map((s) => (
            <Link
              key={s.id}
              to={`/spc/signals?c=${current?.id}&signal=${s.id}`}
            >
              <Badge tone={s.status === "open" ? "issue" : "normal"}>
                {s.chart === dispersion ? `${CHART_LABEL[dispersion]} ` : ""}
                {RULE_LABEL[s.rule]} · {STATUS_LABEL[s.status]}
              </Badge>
            </Link>
          ))
        ) : (
          <span className="muted">—</span>
        ),
    },
  ];
  return (
    <div>
      <PageTitle
        id="S-02"
        title="관리도"
        subtitle="부분군 평균(X̄)과 범위(R)가 관리 한계 안에서 움직이는지 봅니다"
        help="spc/s-02"
        actions={
          latest && (
            <span className="muted">
              한계 v{latest.version} · 게시 {time(latest.publishedAt)}
            </span>
          )
        }
      />
      <ErrorNotice
        error={list.error ?? chart.error}
        retry={() => {
          list.reload();
          chart.reload();
        }}
      />
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
            <Link to={`/spc/capability${query}`}>공정능력 →</Link>
          </form>
          {!data ? (
            !chart.error && <Loading />
          ) : (
            <>
              {!data.limits.length && (
                <p className="muted" role="note">
                  한계를 아직 게시하지 않아 점만 표시합니다.{" "}
                  <Link to={`/spc/characteristics?c=${data.characteristic.id}`}>
                    한계 게시 →
                  </Link>
                </p>
              )}
              <ControlChart kind={position} data={data} onSignal={openSignal} />
              <ControlChart
                kind={dispersion}
                data={data}
                onSignal={openSignal}
                height={130}
              />
              <section>
                <DataTable
                  rows={[...data.points].reverse()}
                  columns={columns}
                  caption="부분군 값"
                  offset={0}
                  total={data.points.length}
                  limit={data.points.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="이 기간에 부분군이 없습니다."
                      to={`/spc/measure${query}`}
                      action="측정 입력"
                    />
                  }
                />
              </section>
            </>
          )}
        </>
      )}
    </div>
  );
}
