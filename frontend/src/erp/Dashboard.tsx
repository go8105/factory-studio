// E-01 ERP 대시보드 — 당월 매출·미수금·미지급·수주잔, 매출 추이, 미수 상위, 계획 대비 실적, 처리 대기 (FS-019h)
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  ERP,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  qty,
  useLists,
  won,
  type Partner,
} from "./common";

type DashboardData = {
  month: string;
  salesSupply: string;
  salesTotal: string;
  salesCount: number;
  receivableBalance: string;
  payableBalance: string;
  orderBacklog: string;
  monthlySales: { month: string; supplyAmount: string }[];
  topReceivables: { partnerId: number; balance: string }[];
  receivableByDue: { overdue: string; notDue: string; unset: string };
  planVsActual: {
    itemId: number;
    itemCode: string;
    name: string;
    planQty: string;
    actualQty: string;
  }[];
  pending: { uninvoicedSales: number; unappliedReceipts: number };
};

function Tile({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note: string;
}) {
  return (
    <section className="stat-tile" aria-label={label}>
      <p>{label}</p>
      <strong>{value}</strong>
      <small>{note}</small>
    </section>
  );
}

export function Dashboard() {
  const { fail } = useSession();
  const lists = useLists<[Partner[]]>([PARTNERS]);
  const [month, setMonth] = useState("");
  const [data, setData] = useState<DashboardData>();
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    api<DashboardData>(`${ERP}/dashboard${month ? `?month=${month}` : ""}`, {
      signal: controller.signal,
    })
      .then((r) => setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [month]);

  if (moduleOff(error) || moduleOff(lists.error)) return <ModuleOff />;
  const name = labels(lists.data?.[0] ?? [], []);
  const peak = Math.max(
    1,
    ...(data?.monthlySales ?? []).map((m) => Number(m.supplyAmount)),
  );

  return (
    <>
      <PageTitle
        id="E-01"
        title="경영 개요"
        subtitle="이번 달 매출과 미수금을 한눈에 봅니다"
        help="erp/e-01"
      />
      <div className="filter-bar">
        <label>
          조회 월
          <input
            type="month"
            value={month || data?.month || ""}
            onChange={(e) => e.target.value && setMonth(e.target.value)}
          />
        </label>
      </div>
      <ErrorNotice error={error} />
      {!data ? (
        !error && <Loading />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="당월 매출"
              value={won(data.salesSupply)}
              note={`공급가액 · ${data.salesCount}건 · 합계 ${won(data.salesTotal)}`}
            />
            <Tile
              label="미수금"
              value={won(data.receivableBalance)}
              note="채권 원금 − 소명액(월과 무관)"
            />
            <Tile
              label="미지급"
              value={won(data.payableBalance)}
              note="채무 원금 − 소명액(월과 무관)"
            />
            <Tile
              label="수주잔"
              value={won(data.orderBacklog)}
              note="(수주 − 출하) × 단가"
            />
          </div>
          <div className="dashboard-grid">
            <section className="panel" aria-label="월별 매출 추이">
              <h2>월별 매출 추이</h2>
              <ol className="rank-list">
                {data.monthlySales.map((m) => (
                  <li key={m.month}>
                    <span>{m.month}</span>
                    <meter
                      min={0}
                      max={peak}
                      value={Number(m.supplyAmount)}
                      aria-label={`${m.month} 매출`}
                    />
                    <strong>{won(m.supplyAmount)}</strong>
                  </li>
                ))}
              </ol>
              <Link className="text-link" to="/erp/sales-records">
                매출 보기
              </Link>
            </section>
            <section className="panel" aria-label="거래처별 미수금 상위">
              <h2>거래처별 미수금 상위 5</h2>
              {data.topReceivables.length === 0 ? (
                <p className="muted">남은 미수금이 없습니다.</p>
              ) : (
                <ol className="rank-list">
                  {data.topReceivables.map((t) => (
                    <li key={t.partnerId}>
                      <span>{name.partner(t.partnerId)}</span>
                      <strong>{won(t.balance)}</strong>
                    </li>
                  ))}
                </ol>
              )}
              <p className="muted">
                만기별: 연체 {won(data.receivableByDue.overdue)} · 미도래{" "}
                {won(data.receivableByDue.notDue)} · 만기 미설정{" "}
                {won(data.receivableByDue.unset)}(결제조건 없는 거래처, 연체로
                보지 않음)
              </p>
              <Link className="text-link" to="/erp/receivables">
                매출채권 현황
              </Link>
            </section>
            <section className="panel" aria-label="판매계획 대비 실적">
              <h2>판매계획 대비 실적</h2>
              {data.planVsActual.length === 0 ? (
                <p className="muted">이달 확정된 판매계획이 없습니다.</p>
              ) : (
                <ul className="rank-list">
                  {data.planVsActual.map((p) => (
                    <li key={p.itemId}>
                      <span>
                        {p.itemCode} {p.name}
                      </span>
                      <strong>
                        {qty(p.actualQty)} / {qty(p.planQty)}
                      </strong>
                    </li>
                  ))}
                </ul>
              )}
              <p className="muted">실적 = 이달 인식된 매출의 출하 수량</p>
              <Link className="text-link" to="/erp/sales-plans">
                판매계획
              </Link>
            </section>
            <section className="panel" aria-label="처리 대기">
              <h2>처리 대기</h2>
              <ul className="rank-list">
                <li>
                  <Link to="/erp/tax-invoices">세금계산서 미발급 매출</Link>
                  <strong>{data.pending.uninvoicedSales}건</strong>
                </li>
                <li>
                  <Link to="/erp/receipts">미소명 잔여가 있는 수금</Link>
                  <strong>{data.pending.unappliedReceipts}건</strong>
                </li>
              </ul>
            </section>
          </div>
        </>
      )}
    </>
  );
}
