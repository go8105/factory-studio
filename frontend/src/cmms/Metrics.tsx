// C-07 보전 지표 — MTBF·MTTR·PM 준수율과 고장 파레토 (UI-02 D 패턴, FS-029 D51).
// 저장하지 않고 조회할 때 계산한다. 작업지시를 고치면 지표도 따라 바뀐다.
import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
  EmptyState,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { moduleOff, useGet } from "./hooks";
import {
  CAUSE_LABEL,
  hours,
  type AssetMetric,
  type Cause,
  type Metrics as Data,
  type ParetoRow,
} from "./common";

const monthsAgo = (n: number) =>
  new Date(Date.now() - n * 30 * 86_400_000).toISOString().slice(0, 10);

export function Metrics() {
  const [from, setFrom] = useState(monthsAgo(3));
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ from: monthsAgo(3), to: "" });
  const { data, error, reload } = useGet<Data>(
    `/metrics?from=${applied.from}${applied.to ? `&to=${applied.to}` : ""}`,
  );
  if (moduleOff(error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const assetColumns: Column<AssetMetric>[] = [
    {
      key: "assetCode",
      label: "설비",
      render: (r) => `${r.assetCode} ${r.assetName}`,
    },
    { key: "failures", label: "고장" },
    { key: "downtime", label: "정지 시간", render: (r) => hours(r.downtime) },
    { key: "mttr", label: "MTTR", render: (r) => hours(r.mttr) },
  ];
  const paretoColumns: Column<ParetoRow>[] = [
    {
      key: "kind",
      label: "구분",
      render: (r) => (r.kind === "CAUSE" ? "원인" : "증상"),
    },
    {
      key: "name",
      label: "이름",
      render: (r) =>
        r.kind === "CAUSE" ? (CAUSE_LABEL[r.name as Cause] ?? r.name) : r.name,
    },
    { key: "count", label: "건수" },
  ];
  return (
    <>
      <PageTitle
        id="C-07"
        title="보전 지표"
        subtitle="MTBF·MTTR·PM 준수율과 고장이 몰린 곳"
        help="cmms/c-07"
      />
      <ErrorNotice error={error} retry={() => reload()} />
      <form
        className="filter-bar"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          setApplied({ from, to });
        }}
      >
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
      </form>
      {!data ? (
        !error && <Loading />
      ) : (
        <>
          <div className="kpi-grid">
            <section className="stat-tile" aria-label="MTBF">
              <p>MTBF</p>
              <strong>{hours(data.mtbf)}</strong>
              <small>
                {data.failures === 0
                  ? "이 기간에 고장이 없습니다"
                  : "(기간 − 정지) ÷ 고장 건수"}
              </small>
            </section>
            <section className="stat-tile" aria-label="MTTR">
              <p>MTTR</p>
              <strong>{hours(data.mttr)}</strong>
              <small>
                고장 {data.failures}건 · 정지 {hours(data.downtime)}
              </small>
            </section>
            <section className="stat-tile" aria-label="PM 준수율">
              <p>PM 준수율</p>
              <strong>{data.pmRate == null ? "—" : `${data.pmRate}%`}</strong>
              <small>
                {data.pmTotal === 0
                  ? "이 기간에 예정된 PM이 없습니다"
                  : `${data.pmKept}/${data.pmTotal}건 예정일 안에 완료`}
              </small>
            </section>
            <section className="stat-tile" aria-label="기간">
              <p>기간</p>
              <strong>{hours(data.periodHours)}</strong>
              <small>
                {data.from} ~ {data.to}
              </small>
            </section>
          </div>
          {data.failures === 0 ? (
            <p role="note" className="muted">
              이 기간에 완료된 고장 작업지시가 없어 MTBF·MTTR을 계산하지
              않았습니다. 0이 아니라 <strong>고장이 없는 것</strong>입니다.
            </p>
          ) : (
            <>
              <section>
                <h3>설비별</h3>
                <DataTable
                  rows={data.byAsset}
                  columns={assetColumns}
                  caption="설비별 고장"
                  offset={0}
                  total={data.byAsset.length}
                  limit={data.byAsset.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="고장이 없습니다."
                      to="/cmms/work-orders"
                      action="작업지시"
                    />
                  }
                />
              </section>
              <section>
                <h3>고장 파레토</h3>
                <p className="muted">
                  무엇이 자주 멈추는지 원인·증상별로 셉니다. 코드를 적어 두지
                  않은 작업지시는 세지 않습니다.
                </p>
                <DataTable
                  rows={data.pareto}
                  columns={paretoColumns}
                  caption="고장 파레토"
                  offset={0}
                  total={data.pareto.length}
                  limit={data.pareto.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason="원인·증상 코드를 적은 작업지시가 없습니다."
                      to="/cmms/failure-codes"
                      action="고장 코드"
                    />
                  }
                />
              </section>
            </>
          )}
          {data.pmTotal > 0 && data.pmKept < data.pmTotal && (
            <p role="note" className="muted">
              <Badge tone="warning">유예 없음</Badge> 예정일 당일까지 완료해야
              준수로 셉니다. 하루라도 넘기면 준수가 아닙니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
