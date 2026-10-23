// C-10 보전 비용 — 부품 + 인건비 + 외주 (UI-02 L 패턴 조회 전용, DSN-21 Q5·F43).
// 저장하지 않는다. 완료한 작업지시에서 볼 때마다 계산한다.
import { useState, type FormEvent } from "react";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { moduleOff, useGet } from "./hooks";
import { money, type CostData, type CostRow } from "./common";

const monthsAgo = (n: number) =>
  new Date(Date.now() - n * 30 * 86_400_000).toISOString().slice(0, 10);

export function Cost() {
  const [from, setFrom] = useState(monthsAgo(6));
  const [to, setTo] = useState("");
  const [applied, setApplied] = useState({ from: monthsAgo(6), to: "" });
  const [by, setBy] = useState<"asset" | "month">("asset");
  const { data, error, reload } = useGet<CostData>(
    `/cost?from=${applied.from}${applied.to ? `&to=${applied.to}` : ""}`,
  );
  if (moduleOff(error))
    return (
      <EmptyState
        reason="CMMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
        to="/workspace"
        action="내 공간으로"
      />
    );
  const columns: Column<CostRow>[] = [
    { key: "group", label: by === "asset" ? "설비" : "월" },
    {
      key: "orderCount",
      label: "작업지시",
      render: (r) =>
        `${r.orderCount}건 (고장 ${r.bmCount} · 예방 ${r.pmCount})`,
    },
    { key: "partCost", label: "부품비", render: (r) => money(r.partCost) },
    { key: "laborCost", label: "인건비", render: (r) => money(r.laborCost) },
    {
      key: "externalCost",
      label: "외주비",
      render: (r) => money(r.externalCost),
    },
    { key: "totalCost", label: "합계", render: (r) => money(r.totalCost) },
  ];
  const rows = data ? (by === "asset" ? data.byAsset : data.byMonth) : [];
  return (
    <div className="page-fill">
      <PageTitle
        id="C-10"
        title="보전 비용"
        subtitle="완료한 작업지시의 부품·인건비·외주비"
        help="cmms/c-10"
      />
      <ErrorNotice error={error} retry={() => reload()} />
      <p role="note" className="muted">
        <strong>저장하지 않습니다.</strong> 볼 때마다 완료한 작업지시에서
        계산합니다. 부품비는 쓸 때의 단가, 인건비는 작업 기록 분 ÷ 60 × 정비원
        시간당 인건비입니다. 외주비의 회계 처리는 ERP에서 직접 매입으로 따로
        합니다.
      </p>
      <form
        className="filter-bar"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          setApplied({ from, to });
        }}
      >
        <label>
          기준
          <select
            value={by}
            onChange={(e) => setBy(e.target.value as "asset" | "month")}
          >
            <option value="asset">설비별</option>
            <option value="month">월별</option>
          </select>
        </label>
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
            <section className="stat-tile" aria-label="합계">
              <p>합계</p>
              <strong>{money(data.totalCost)}</strong>
              <small>완료 {data.orderCount}건</small>
            </section>
            <section className="stat-tile" aria-label="부품비">
              <p>부품비</p>
              <strong>{money(data.partCost)}</strong>
              <small>수량 × 쓸 때의 단가</small>
            </section>
            <section className="stat-tile" aria-label="인건비">
              <p>인건비</p>
              <strong>{money(data.laborCost)}</strong>
              <small>작업 분 ÷ 60 × 시간당</small>
            </section>
            <section className="stat-tile" aria-label="외주비">
              <p>외주비</p>
              <strong>{money(data.externalCost)}</strong>
              <small>회계는 ERP 직접 매입</small>
            </section>
          </div>
          <DataTable
            rows={rows}
            columns={columns}
            caption={by === "asset" ? "설비별 비용" : "월별 비용"}
            offset={0}
            total={rows.length}
            limit={rows.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="이 기간에 완료한 작업지시가 없습니다. 진행 중인 것은 아직 얼마가 들지 몰라 세지 않습니다."
                to="/cmms/work-orders"
                action="작업지시"
              />
            }
          />
        </>
      )}
    </div>
  );
}
