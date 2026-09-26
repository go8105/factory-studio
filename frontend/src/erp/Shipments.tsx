// E-06 출하 — 출하지시를 한 번에 출하 확정, 같은 순간 매출 인식 (FS-019c)
import { useState, type FormEvent } from "react";
import {
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  Loading,
  PageTitle,
  type Column,
  RevealAnchor,
} from "../shared/components";
import {
  fieldErrors,
  ITEMS,
  labels,
  ModuleOff,
  moduleOff,
  PARTNERS,
  qty,
  useLists,
  useSend,
  won,
  type Item,
  type Partner,
} from "./common";
import type { ShipOrder } from "./ShipmentOrders";

type ShipmentLine = {
  id: number;
  shipmentOrderLineId: number;
  packingNo: string | null;
  shippedQty: string;
  itemId: number;
  shippedUom: string;
};
type Shipment = {
  id: number;
  shipmentNo: string;
  shipmentOrderId: number;
  shipOrderNo: string;
  orderNo: string;
  partnerId: number;
  shippedAt: string;
  salesRecordId: number | null;
  supplyAmount: string | null;
  taxAmount: string | null;
  totalAmount: string | null;
  lines: ShipmentLine[];
};

export function Shipments() {
  const { data, error, reload } = useLists<
    [Shipment[], ShipOrder[], Partner[], Item[]]
  >(["/shipments", "/shipment-orders", PARTNERS, ITEMS]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [create, setCreate] = useState({ shipmentNo: "", shipmentOrderId: 0 });
  const [packing, setPacking] = useState<Record<number, string>>({});

  if (moduleOff(error)) return <ModuleOff />;
  const [shipments, shipOrders, partners, items] = data ?? [
    undefined,
    [],
    [],
    [],
  ];
  const name = labels(partners, items);
  const errors = fieldErrors(saveError);
  const selected = shipments?.find((s) => s.id === selectedId);
  const open = shipOrders.filter((s) => s.status === "open");
  const target = open.find((s) => s.id === create.shipmentOrderId);

  function select(id: number | undefined) {
    setSelectedId(id);
    setError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || !target) return;
    const created = await send<Shipment>("/shipments", "POST", {
      shipmentNo: create.shipmentNo.trim().toUpperCase(),
      shipmentOrderId: target.id,
      lines: target.lines.map((l) => ({
        shipmentOrderLineId: l.id,
        packingNo: (packing[l.id] ?? "").trim() || null,
      })),
    });
    if (created) {
      setCreate({ shipmentNo: "", shipmentOrderId: 0 });
      setPacking({});
      select(created.id);
    }
  }

  const columns: Column<Shipment>[] = [
    { key: "shipmentNo", label: "출하번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={r.id === selectedId}
          onClick={() => select(r.id)}
        >
          명세 {r.lines.length}
        </button>
      ),
    },
    { key: "shipOrderNo", label: "출하지시" },
    { key: "orderNo", label: "수주" },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    {
      key: "shippedAt",
      label: "출하 시각",
      render: (r) => new Date(r.shippedAt).toLocaleString(),
    },
    {
      key: "totalAmount",
      label: "매출(합계)",
      render: (r) => (r.totalAmount ? won(r.totalAmount) : "-"),
    },
  ];
  const lineColumns: Column<ShipmentLine>[] = [
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "shippedQty",
      label: "출하 수량",
      render: (r) => `${qty(r.shippedQty)} ${r.shippedUom}`,
    },
    {
      key: "packingNo",
      label: "패킹번호",
      render: (r) => r.packingNo ?? "-",
    },
  ];
  const draftColumns: Column<ShipOrder["lines"][number]>[] = [
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "orderQty",
      label: "출하 수량",
      render: (r) => `${qty(r.orderQty)} ${r.unit}`,
    },
    {
      key: "id",
      label: "패킹번호 (선택)",
      render: (r) => (
        <input
          aria-label={`${r.lineNo}행 패킹번호`}
          maxLength={40}
          placeholder="예: PL-0101"
          value={packing[r.id] ?? ""}
          onChange={(e) => setPacking({ ...packing, [r.id]: e.target.value })}
        />
      ),
    },
  ];

  return (
    <>
      <PageTitle
        id="E-06"
        title="출하"
        subtitle="출하지시를 출하 확정하고, 같은 순간 매출을 인식합니다"
        help="erp/e-06"
      />
      <p className="muted">
        MES와 독립이므로 패킹번호는 직접 입력합니다(선택). 실제 운영에서는
        인터페이스로 연계합니다. 오타를 막을 수 없고, ERP 안에서 이미 출하한
        번호만 거부합니다. 품목·수량만으로도 출하가 성립하며, 확정하면 매출과
        매출채권이 함께 생깁니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!shipments ? (
        !error && <Loading />
      ) : (
        <>
          <DataTable
            rows={shipments}
            columns={columns}
            caption="출하 목록"
            offset={0}
            total={shipments.length}
            limit={shipments.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="출하 이력이 없습니다. 아래 폼에서 미출하 지시를 출하하세요."
                to="#shipment-form"
                action="출하 확정"
              />
            }
          />

          <RevealAnchor when={selected} />

          {selected && (
            <section className="panel" aria-label="출하 명세">
              <h2>{selected.shipmentNo} 명세</h2>
              <p className="muted">
                매출: 공급가액 {won(selected.supplyAmount ?? "0")} · 세액{" "}
                {won(selected.taxAmount ?? "0")} · 합계{" "}
                {won(selected.totalAmount ?? "0")}
              </p>
              <DataTable
                rows={selected.lines}
                columns={lineColumns}
                caption={`${selected.shipmentNo} 출하 명세`}
                offset={0}
                total={selected.lines.length}
                limit={selected.lines.length || 1}
                onPage={() => undefined}
              />
            </section>
          )}

          <form
            id="shipment-form"
            className="panel"
            aria-label="출하 확정"
            onSubmit={(e) => void submit(e)}
          >
            <h2>출하 확정</h2>
            <div className="master-grid">
              <Field
                label="출하번호"
                value={create.shipmentNo}
                required
                maxLength={40}
                placeholder="예: SH-0101"
                error={errors.shipmentNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    shipmentNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="shipment-order">출하지시</label>
                <select
                  id="shipment-order"
                  value={create.shipmentOrderId || ""}
                  onChange={(e) => {
                    setCreate({
                      ...create,
                      shipmentOrderId: Number(e.target.value),
                    });
                    setPacking({});
                  }}
                >
                  <option value="">미출하 지시 선택</option>
                  {open.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.shipOrderNo} · {s.orderNo} ·{" "}
                      {name.partner(s.partnerId)}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {target && (
              <DataTable
                rows={target.lines}
                columns={draftColumns}
                caption={`${target.shipOrderNo} 출하 명세`}
                offset={0}
                total={target.lines.length}
                limit={target.lines.length || 1}
                onPage={() => undefined}
              />
            )}
            {errors.lines && <p className="notice">{errors.lines}</p>}
            <div className="form-actions">
              <button type="submit" disabled={pending || !target}>
                출하 확정
              </button>
            </div>
          </form>
        </>
      )}
    </>
  );
}
