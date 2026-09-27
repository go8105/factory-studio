// M-01 MES 대시보드 — 핵심 지표, 공정별 진행 파이프라인, 불량 사유, 계획 대비 실적, 처리 대기 (FS-020g)
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { ErrorNotice, Loading, PageTitle } from "../shared/components";
import { MES, ModuleOff, moduleOff, useLists } from "./common";

type DashboardData = {
  month: string;
  openOrders: number;
  producedQty: string;
  goodRate: string | null;
  receivedPallets: number;
  pipeline: { processId: number; running: number; waiting: number }[];
  defectReasons: { reason: string; defectQty: string }[];
  planVsActual: {
    itemId: number;
    planQty: string;
    allocatedQty: string;
    finalGoodQty: string;
  }[];
  pending: { unconfirmedResults: number; unpackedLots: number };
};
type Process = { id: number; processCode: string; name: string };
type Item = { id: number; itemCode: string; name: string };

const num = (v: string | number) => Number(v).toLocaleString();

function Tile({
  label,
  value,
  unit,
  note,
}: {
  label: string;
  value: string;
  unit?: string;
  note: string;
}) {
  return (
    <section className="stat-tile" aria-label={label}>
      <p>{label}</p>
      <strong>
        {value} {unit && <span>{unit}</span>}
      </strong>
      <small>{note}</small>
    </section>
  );
}

export function Dashboard() {
  const { fail } = useSession();
  const lists = useLists<[Process[], Item[]]>(["/processes", "/items"]);
  const [month, setMonth] = useState("");
  const [data, setData] = useState<DashboardData>();
  const [error, setError] = useState<unknown>();

  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    api<DashboardData>(`${MES}/dashboard${month ? `?month=${month}` : ""}`, {
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
  const [processes, items] = lists.data ?? [[], []];
  const processName = (id: number) =>
    processes.find((p) => p.id === id)?.name ?? String(id);
  const itemLabel = (id: number) => {
    const i = items.find((x) => x.id === id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };

  return (
    <>
      <PageTitle
        id="M-01"
        title="생산 개요"
        subtitle="이번 달 생산·품질과 공정별로 LOT이 어디에 있는지 봅니다"
        help="mes/m-01"
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
      <ErrorNotice error={error} />
      {!data ? (
        !error && <Loading />
      ) : (
        <>
          <div className="kpi-grid">
            <Tile
              label="진행 중 지시"
              value={num(data.openOrders)}
              unit="건"
              note="발행·진행 상태(월과 무관)"
            />
            <Tile
              label="당월 생산"
              value={num(data.producedQty)}
              unit="EA"
              note="마지막 공정 양품 · 공정별 양품은 합치지 않음"
            />
            <Tile
              label="양품률"
              value={data.goodRate === null ? "-" : data.goodRate}
              unit={data.goodRate === null ? undefined : "%"}
              note={
                data.goodRate === null
                  ? "이달 확정 실적 없음"
                  : "확정 실적 Σ양품 ÷ Σ산출(전 공정)"
              }
            />
            <Tile
              label="입고 완료"
              value={num(data.receivedPallets)}
              unit="PALLET"
              note="이달 완제품 입고"
            />
          </div>
          <div className="dashboard-grid">
            <section className="panel" aria-label="공정별 진행 현황">
              <h2>공정별 진행 현황</h2>
              <ol className="rank-list">
                {data.pipeline.map((p, index) => (
                  <li key={p.processId}>
                    <span>
                      {index + 1}. {processName(p.processId)}
                    </span>
                    <span>
                      실행 중 {p.running} · 대기 {p.waiting} LOT
                    </span>
                  </li>
                ))}
              </ol>
              <p className="muted">
                설비 가동률은 설비 상태(가동·정지·점검) 데이터가 없어 보여 주지
                않습니다.
              </p>
              <Link className="text-link" to="/mes/executions">
                공정 실행으로 →
              </Link>
            </section>
            <section className="panel" aria-label="불량 사유 상위">
              <h2>불량 사유 상위</h2>
              {data.defectReasons.length === 0 ? (
                <p className="muted">이달 불량이 없습니다.</p>
              ) : (
                <ol className="rank-list">
                  {data.defectReasons.map((r) => (
                    <li key={r.reason}>
                      <span>{r.reason}</span>
                      <span>{num(r.defectQty)} EA</span>
                    </li>
                  ))}
                </ol>
              )}
              <Link className="text-link" to="/mes/results">
                실적 보기 →
              </Link>
            </section>
            <section className="panel" aria-label="계획 대비 실적">
              <h2>계획 대비 실적 · {data.month}</h2>
              {data.planVsActual.length === 0 ? (
                <p className="muted">이달 확정된 생산계획이 없습니다.</p>
              ) : (
                <ul className="rank-list">
                  {data.planVsActual.map((r) => (
                    <li key={r.itemId}>
                      <span>{itemLabel(r.itemId)}</span>
                      <span>
                        계획 {num(r.planQty)} · 지시 {num(r.allocatedQty)} ·
                        양품 {num(r.finalGoodQty)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
              <Link className="text-link" to="/mes/production-plans">
                생산계획 보기 →
              </Link>
            </section>
            <section className="panel" aria-label="처리 대기">
              <h2>처리 대기</h2>
              <ul className="rank-list">
                <li>
                  <Link className="text-link" to="/mes/results">
                    미확정 실적
                  </Link>
                  <span>{data.pending.unconfirmedResults}건</span>
                </li>
                <li>
                  <Link className="text-link" to="/mes/packing">
                    미패킹 LOT
                  </Link>
                  <span>{data.pending.unpackedLots}건</span>
                </li>
              </ul>
            </section>
          </div>
        </>
      )}
    </>
  );
}
