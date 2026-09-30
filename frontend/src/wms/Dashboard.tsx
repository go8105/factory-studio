// W-01 재고 대시보드 — KPI 4개 + 품목별 현재고·원천별 미반영·월 입출고(UI-02 D 패턴, F-01 기준).
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import { Badge, ErrorNotice, Loading, PageTitle } from "../shared/components";
import {
  KIND_LABEL,
  ModuleOff,
  moduleOff,
  num,
  WMS,
  type Purpose,
  type SourceKind,
} from "./common";

type DashboardData = {
  month: string;
  rawItems: number;
  fgLots: number;
  negativeCount: number;
  pendingSources: number | null;
  pendingByKind: Record<SourceKind, number | null>;
  items: {
    itemCode: string;
    itemName: string;
    itemClass: Purpose;
    unit: string;
    onHand: string;
    available: string;
    reservedQty: string;
    quarantinedOnHand: string;
    reservationShortage: string;
    negative: boolean;
  }[];
  flows: {
    itemCode: string;
    inbound: string;
    outbound: string;
    unit: string;
  }[];
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
    api<DashboardData>(`${WMS}/dashboard${month ? `?month=${month}` : ""}`, {
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
        id="W-01"
        title="재고 개요"
        subtitle="품목별 현재고와 아직 반영하지 않은 MES·ERP 기록"
        help="wms/w-01"
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
              label="원자재 품목"
              value={String(data.rawItems)}
              unit="품목"
              note="재고가 있는 원자재"
            />
            <Tile
              label="완제품 LOT"
              value={String(data.fgLots)}
              unit="LOT"
              note="재고가 남은 완제품 LOT"
            />
            <Tile
              label="음수 재고"
              value={String(data.negativeCount)}
              unit="건"
              note="품목·위치·LOT 기준(D15: 막지 않고 표시)"
              badge={
                data.negativeCount > 0 && (
                  <Link to="/wms/stock?negativeOnly=1">
                    <Badge tone="issue">확인 필요</Badge>
                  </Link>
                )
              }
            />
            <Tile
              label="미반영 원천"
              value={
                data.pendingSources === null
                  ? "조회 불가"
                  : String(data.pendingSources)
              }
              unit={data.pendingSources === null ? undefined : "건"}
              note={
                data.pendingSources === null
                  ? "MES·ERP를 모두 꺼서 읽지 않습니다"
                  : "MES·ERP 확정 기록 중 원장에 없는 것"
              }
            />
          </div>
          <div className="dashboard-grid has-lead">
            <section className="panel" aria-label="품목별 현재고">
              <h2>품목별 현재고 · 예약 가능</h2>
              {data.items.length ? (
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th scope="col">품목</th>
                        <th scope="col" className="num">
                          현재고
                        </th>
                        <th scope="col" className="num">
                          예약 가능
                        </th>
                        <th scope="col">단위</th>
                        <th scope="col">상태</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.items.map((i) => (
                        <tr key={i.itemCode}>
                          <td>
                            {i.itemCode} {i.itemName}
                          </td>
                          <td className="num">{num(i.onHand)}</td>
                          <td className="num">{num(i.available)}</td>
                          <td>{i.unit}</td>
                          <td>
                            {i.negative && <Badge tone="issue">음수</Badge>}
                            {Number(i.reservationShortage) > 0 && (
                              <Badge tone="issue">예약 부족</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="muted">
                  아직 재고가 없습니다. 원천 반영이나 기초재고 전표로
                  시작하세요.
                </p>
              )}
              <Link className="text-link" to="/wms/stock">
                재고 현황 →
              </Link>
            </section>
            <section className="panel" aria-label="원천별 미반영">
              <h2>원천별 미반영</h2>
              <ul className="rank-list">
                {(Object.keys(KIND_LABEL) as SourceKind[]).map((k) => (
                  <li key={k}>
                    <span>{KIND_LABEL[k]}</span>
                    <span>
                      {data.pendingByKind[k] === null
                        ? "꺼짐"
                        : `${data.pendingByKind[k]}건`}
                    </span>
                  </li>
                ))}
              </ul>
              <Link className="text-link" to="/wms/sources">
                원천 반영 →
              </Link>
            </section>
            <section className="panel" aria-label="월 입출고">
              <h2>월 입출고 · {data.month}</h2>
              {data.flows.length ? (
                <ul className="rank-list">
                  {data.flows.map((f) => (
                    <li key={f.itemCode}>
                      <span>{f.itemCode}</span>
                      <span>
                        입고 {num(f.inbound)} · 출고 {num(f.outbound)} {f.unit}
                      </span>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">이 달 확정 전표가 없습니다.</p>
              )}
              <Link className="text-link" to="/wms/moves">
                재고 원장 →
              </Link>
            </section>
          </div>
        </>
      )}
    </>
  );
}
