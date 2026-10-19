// W-18 재고 수불부 · W-19 재고 분석 · W-20 위치 점유 (DSN-13 F52·F54·F55·F37).
// 셋 다 표를 새로 두지 않고 원장과 마스터를 조회할 때 집계한다. 읽기 전용 화면이다.
import { useSearchParams } from "react-router-dom";
import {
  Badge,
  DataTable,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  num,
  useLists,
  type AnalysisRow,
  type LedgerRow,
  type OccupancyRow,
  type Warehouse,
} from "./common";

function WarehouseFilter({
  warehouses,
  value,
  onChange,
}: {
  warehouses: Warehouse[];
  value: string;
  onChange: (next: string) => void;
}) {
  return (
    <label>
      창고
      <select
        aria-label="창고 필터"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">전체 창고</option>
        {warehouses.map((w) => (
          <option key={w.id} value={w.id}>
            {w.code} · {w.name}
          </option>
        ))}
      </select>
    </label>
  );
}

/** W-18 재고 수불부 — 기간 기초·입고·출고·기말 (F52). ERP 원가 계산의 입력이다. */
export function Ledger() {
  const [params, setParams] = useSearchParams();
  const month = params.get("month") ?? "";
  const warehouse = params.get("warehouseId") ?? "";
  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next);
  };

  const query = new URLSearchParams();
  if (month) query.set("month", month);
  if (warehouse) query.set("warehouseId", warehouse);

  const { data } = useLists<
    [Warehouse[], { month: string; rows: LedgerRow[] }]
  >(["/warehouses", `/ledger?${query.toString()}`]);
  if (!data) return <Loading />;
  const warehouses = data[0] ?? [];
  const report = data[1];
  const rows = report?.rows ?? [];

  const columns: Column<LedgerRow>[] = [
    {
      key: "warehouseCode",
      label: "창고",
      render: (r) => `${r.warehouseCode} · ${r.warehouseName}`,
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => (
        <span>
          {r.itemCode} <span className="muted">· {r.itemName}</span>
        </span>
      ),
    },
    { key: "opening", label: "기초", render: (r) => num(r.opening) },
    { key: "inbound", label: "입고", render: (r) => num(r.inbound) },
    { key: "outbound", label: "출고", render: (r) => num(r.outbound) },
    {
      key: "closing",
      label: "기말",
      render: (r) => (
        <strong>
          {num(r.closing)} {r.baseUnit}
        </strong>
      ),
    },
  ];

  return (
    <div className="wms-ledger">
      <PageTitle
        id="W-18"
        title="W-18 재고 수불부"
        subtitle="한 달의 기초·입고·출고·기말을 품목과 창고별로 봅니다. ERP 원가 계산이 이 값을 씁니다."
      />
      <div
        className="filter-bar"
        style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}
      >
        <label>
          월
          <input
            aria-label="조회 월"
            type="month"
            value={month || report?.month.slice(0, 7) || ""}
            onChange={(e) => setParam("month", e.target.value)}
          />
        </label>
        <WarehouseFilter
          warehouses={warehouses}
          value={warehouse}
          onChange={(v) => setParam("warehouseId", v)}
        />
      </div>
      <DataTable
        caption={`${report?.month ?? ""} 재고 수불부`}
        rows={rows}
        columns={columns}
        offset={0}
        limit={rows.length || 1}
        total={rows.length}
        onPage={() => undefined}
      />
    </div>
  );
}

/** W-19 재고 분석 — 안전재고·최대재고 경고(F37)와 회전율·장기 체화(F54). */
export function Analysis() {
  const [params, setParams] = useSearchParams();
  const warehouse = params.get("warehouseId") ?? "";
  const query = warehouse ? `?warehouseId=${warehouse}` : "";

  const { data } = useLists<
    [Warehouse[], { staleDays: number; rows: AnalysisRow[] }]
  >(["/warehouses", `/analysis${query}`]);
  if (!data) return <Loading />;
  const warehouses = data[0] ?? [];
  const staleDays = data[1]?.staleDays ?? 90;
  const rows = data[1]?.rows ?? [];

  const columns: Column<AnalysisRow>[] = [
    {
      key: "itemCode",
      label: "품목",
      render: (r) => (
        <span>
          {r.itemCode} <span className="muted">· {r.itemName}</span>
        </span>
      ),
    },
    {
      key: "onHand",
      label: "현재고",
      render: (r) => `${num(r.onHand)} ${r.baseUnit}`,
    },
    {
      key: "safetyStock",
      label: "안전·최대",
      render: (r) =>
        r.safetyStock || r.maxStock ? (
          <span>
            {r.safetyStock ? num(r.safetyStock) : "-"} /{" "}
            {r.maxStock ? num(r.maxStock) : "-"}
          </span>
        ) : (
          <span className="muted">미설정</span>
        ),
    },
    {
      key: "belowSafety",
      label: "경고",
      render: (r) => (
        <>
          {r.belowSafety && <Badge tone="issue">안전재고 부족</Badge>}{" "}
          {r.aboveMax && <Badge tone="warning">최대재고 초과</Badge>}
          {!r.belowSafety && !r.aboveMax && <span className="muted">-</span>}
        </>
      ),
    },
    {
      key: "turnover",
      label: `회전율(${staleDays}일)`,
      render: (r) =>
        r.turnover === null ? <span className="muted">-</span> : r.turnover,
    },
    {
      key: "lastOutOn",
      label: "마지막 출고",
      render: (r) =>
        r.lastOutOn ? (
          <span>
            {r.lastOutOn}{" "}
            {r.stale && <Badge tone="warning">{r.staleDays}일 경과</Badge>}
          </span>
        ) : (
          <Badge tone="warning">출고 없음</Badge>
        ),
    },
    {
      key: "abcClass",
      label: "ABC",
      render: (r) => r.abcClass ?? <span className="muted">-</span>,
    },
  ];

  return (
    <div className="wms-analysis">
      <PageTitle
        id="W-19"
        title="W-19 재고 분석"
        subtitle={`안전재고 부족·최대재고 초과를 알리고, 마지막 출고 후 ${staleDays}일이 지난 품목을 장기 체화로 봅니다.`}
      />
      <div
        className="filter-bar"
        style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}
      >
        <WarehouseFilter
          warehouses={warehouses}
          value={warehouse}
          onChange={(v) => {
            const next = new URLSearchParams(params);
            if (v) next.set("warehouseId", v);
            else next.delete("warehouseId");
            setParams(next);
          }}
        />
      </div>
      <DataTable
        caption="재고 분석"
        rows={rows}
        columns={columns}
        offset={0}
        limit={rows.length || 1}
        total={rows.length}
        onPage={() => undefined}
      />
    </div>
  );
}

/** W-20 위치 점유 — 용량 대비 현재고 (F55). 용량이 없는 칸은 점유율을 내지 않는다. */
export function Occupancy() {
  const [params, setParams] = useSearchParams();
  const warehouse = params.get("warehouseId") ?? "";
  const query = warehouse ? `?warehouseId=${warehouse}` : "";

  const { data } = useLists<[Warehouse[], { rows: OccupancyRow[] }]>([
    "/warehouses",
    `/occupancy${query}`,
  ]);
  if (!data) return <Loading />;
  const warehouses = data[0] ?? [];
  const rows = data[1]?.rows ?? [];

  const columns: Column<OccupancyRow>[] = [
    {
      key: "locationCode",
      label: "위치",
      render: (r) => (
        <span>
          <strong>{r.locationCode}</strong>{" "}
          <span className="muted">{r.locationName}</span>
        </span>
      ),
    },
    {
      key: "warehouseCode",
      label: "창고",
      render: (r) => `${r.warehouseCode} · ${r.warehouseName}`,
    },
    { key: "onHand", label: "현재고", render: (r) => num(r.onHand) },
    {
      key: "capacityQty",
      label: "용량",
      render: (r) =>
        r.capacityQty ? (
          num(r.capacityQty)
        ) : (
          <span className="muted">제한 없음</span>
        ),
    },
    {
      key: "usagePercent",
      label: "점유율",
      render: (r) =>
        r.usagePercent === null ? (
          <span className="muted">-</span>
        ) : (
          <Badge tone={r.over ? "issue" : "normal"}>{r.usagePercent}%</Badge>
        ),
    },
    {
      key: "itemCount",
      label: "품목·LOT",
      render: (r) => `${r.itemCount} · ${r.lotCount}`,
    },
    {
      key: "mixItems",
      label: "혼적",
      render: (r) => (
        <span className="muted">
          품목 {r.mixItems ? "허용" : "금지"} · LOT{" "}
          {r.mixLots ? "허용" : "금지"}
        </span>
      ),
    },
  ];

  return (
    <div className="wms-occupancy">
      <PageTitle
        id="W-20"
        title="W-20 위치 점유"
        subtitle="칸마다 용량 대비 현재고와 혼적 규칙을 봅니다. 적치 추천이 이 값을 기준으로 칸을 고릅니다."
      />
      <div
        className="filter-bar"
        style={{ display: "flex", gap: "0.5rem", marginBottom: "1rem" }}
      >
        <WarehouseFilter
          warehouses={warehouses}
          value={warehouse}
          onChange={(v) => {
            const next = new URLSearchParams(params);
            if (v) next.set("warehouseId", v);
            else next.delete("warehouseId");
            setParams(next);
          }}
        />
      </div>
      <DataTable
        caption="위치 점유 현황"
        rows={rows}
        columns={columns}
        offset={0}
        limit={rows.length || 1}
        total={rows.length}
        onPage={() => undefined}
      />
    </div>
  );
}
