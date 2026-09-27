// W-02 재고 현황 — 확정 원장 합계를 창고·위치·품목·LOT별로 보여 준다(UI-02 L 패턴, F-02 기준).
// 완제품은 품목 합계 줄에 가용 = 현재고 − ERP 미출하 지시(D17)를 둔다. 음수는 막지 않고 표시한다(D15).
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  ModuleOff,
  moduleOff,
  num,
  StockBadges,
  useLists,
  WMS,
  type Item,
  type StockRow,
  type StockTotal,
  type Warehouse,
} from "./common";

type Filters = {
  warehouseId: string;
  itemCode: string;
  lotNo: string;
  negativeOnly: boolean;
  unassignedOnly: boolean;
};

export function Stock() {
  const { fail } = useSession();
  const [params] = useSearchParams();
  const initial: Filters = {
    warehouseId: "",
    itemCode: params.get("itemCode") ?? "",
    lotNo: params.get("lotNo") ?? "",
    negativeOnly: params.get("negativeOnly") === "1",
    unassignedOnly: false,
  };
  const [draft, setDraft] = useState<Filters>(initial);
  const [applied, setApplied] = useState<Filters>(initial);
  const lists = useLists<[Warehouse[], Item[]]>(["/warehouses", "/items"]);
  const [data, setData] = useState<{
    rows: StockRow[];
    totals: StockTotal[];
  }>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const query = new URLSearchParams();
    if (applied.warehouseId) query.set("warehouseId", applied.warehouseId);
    if (applied.itemCode) query.set("itemCode", applied.itemCode);
    if (applied.lotNo) query.set("lotNo", applied.lotNo.trim());
    if (applied.negativeOnly) query.set("negativeOnly", "true");
    if (applied.unassignedOnly) query.set("unassignedOnly", "true");
    setError(undefined);
    setData(undefined);
    api<{ rows: StockRow[]; totals: StockTotal[] }>(`${WMS}/stock?${query}`, {
      signal: controller.signal,
    })
      .then((r) => !controller.signal.aborted && setData(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [applied, reload]);
  if (moduleOff(error) || moduleOff(lists.error)) return <ModuleOff />;
  const [warehouses, items] = lists.data ?? [[], []];

  const columns: Column<StockRow & { id: number }>[] = [
    { key: "warehouseCode", label: "창고" },
    { key: "locationCode", label: "위치" },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => `${r.itemCode} ${r.itemName}`,
    },
    {
      key: "lotNo",
      label: "LOT",
      render: (r) => (r.itemClass === "RAW" ? "—" : (r.lotNo ?? "(미지정)")),
    },
    { key: "onHand", label: "현재고", render: (r) => num(r.onHand) },
    { key: "unit", label: "단위" },
    {
      key: "negative",
      label: "상태",
      render: (r) => <StockBadges row={r} />,
    },
    {
      key: "id",
      label: "원장",
      render: (r) => (
        <Link
          className="link-button"
          to={`/wms/moves?itemCode=${r.itemCode}${r.lotNo ? `&lotNo=${r.lotNo}` : ""}`}
        >
          원장
        </Link>
      ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="W-02"
        title="재고 현황"
        subtitle="확정 전표의 이동 합계입니다. 수량을 직접 고치지 않고 전표로만 바꿉니다"
        help="wms/w-02"
      />
      <form
        className="filter-bar"
        onSubmit={(e) => {
          e.preventDefault();
          setApplied(draft);
        }}
      >
        <label>
          창고
          <select
            value={draft.warehouseId}
            onChange={(e) =>
              setDraft({ ...draft, warehouseId: e.target.value })
            }
          >
            <option value="">전체</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} {w.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          품목
          <select
            value={draft.itemCode}
            onChange={(e) => setDraft({ ...draft, itemCode: e.target.value })}
          >
            <option value="">전체</option>
            {items.map((i) => (
              <option key={i.id} value={i.itemCode}>
                {i.itemCode} {i.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          LOT 번호
          <input
            value={draft.lotNo}
            maxLength={50}
            onChange={(e) => setDraft({ ...draft, lotNo: e.target.value })}
          />
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={draft.negativeOnly}
            onChange={(e) =>
              setDraft({ ...draft, negativeOnly: e.target.checked })
            }
          />
          음수만
        </label>
        <label className="inline-check">
          <input
            type="checkbox"
            checked={draft.unassignedOnly}
            onChange={(e) =>
              setDraft({ ...draft, unassignedOnly: e.target.checked })
            }
          />
          LOT 미지정만
        </label>
        <button type="submit">조회</button>
      </form>
      <ErrorNotice
        error={error ?? lists.error}
        retry={() => setReload((n) => n + 1)}
      />
      {!data ? (
        !error && <Loading delay={300} />
      ) : (
        <>
          <DataTable
            rows={data.rows.map((r, i) => ({ ...r, id: i + 1 }))}
            columns={columns}
            caption="재고 현황"
            offset={0}
            total={data.rows.length}
            limit={data.rows.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="조건에 맞는 재고가 없습니다. MES·ERP 기록을 반영하거나 기초재고 전표를 확정하세요."
                to="/wms/sources"
                action="원천 반영으로"
              />
            }
          />
          {data.totals.length > 0 && (
            <section className="panel" aria-label="완제품 품목 합계">
              <h2>완제품 품목 합계 · 가용</h2>
              <ul className="rank-list">
                {data.totals.map((t) => (
                  <li key={t.itemCode}>
                    <span>{t.itemCode} 합계</span>
                    <span>
                      현재고 {num(t.onHand)} ·{" "}
                      {t.available === null
                        ? "가용 계산 불가(ERP 꺼짐)"
                        : `미출하 지시 ${num(t.openShipmentQty!)} · 가용 ${num(t.available)}`}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
