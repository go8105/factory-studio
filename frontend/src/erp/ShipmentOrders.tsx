import { useState, type FormEvent } from "react";
import {
  Badge,
  DataTable,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  type Column,
  useDiscardGuard,
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
  type Item,
  type Partner,
} from "./common";
import type { Order } from "./SalesOrders";

type ShipOrderLine = {
  id: number;
  salesOrderLineId: number;
  orderQty: string;
  lineNo: number;
  itemId: number;
  unit: string;
};
export type ShipOrder = {
  id: number;
  shipOrderNo: string;
  salesOrderId: number;
  orderNo: string;
  partnerId: number;
  orderedOn: string;
  status: "open" | "shipped" | "cancelled";
  cancelReason: string | null;
  shipmentId: number | null;
  shipmentNo: string | null;
  lines: ShipOrderLine[];
};

export const SHIP_STATUS: Record<
  ShipOrder["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  open: ["미출하", "warning"],
  shipped: ["출하 완료", "normal"],
  cancelled: ["취소", "issue"],
};
const today = () => new Date().toLocaleDateString("sv-SE");

export function ShipmentOrders() {
  const { data, error, reload } = useLists<
    [ShipOrder[], Order[], Partner[], Item[]]
  >(["/shipment-orders", "/sales-orders", PARTNERS, ITEMS]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [reason, setReason] = useState("");
  const [panelOpen, setPanelOpen] = useState(false);
  const [create, setCreate] = useState({
    shipOrderNo: "",
    salesOrderId: 0,
    orderedOn: today(),
  });
  const [qtys, setQtys] = useState<Record<number, string>>({});

  const [shipOrders, orders, partners, items] = data ?? [undefined, [], [], []];
  const name = labels(partners, items);
  const errors = fieldErrors(saveError);
  const selected = shipOrders?.find((s) => s.id === selectedId);
  const shippable = orders.filter(
    (o) => o.status === "open" || o.status === "shipping",
  );
  const order = shippable.find((o) => o.id === create.salesOrderId);
  const remaining = (l: Order["lines"][number]) =>
    Number(l.orderQty) - Number(l.instructedQty);

  const dirty =
    panelOpen &&
    (create.shipOrderNo !== "" ||
      create.salesOrderId !== 0 ||
      Object.values(qtys).some((v) => v !== ""));
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;

  function openCreate() {
    setError(undefined);
    setCreate({ shipOrderNo: "", salesOrderId: 0, orderedOn: today() });
    setQtys({});
    setPanelOpen(true);
  }

  function closeCreate() {
    setPanelOpen(false);
    setCreate({ shipOrderNo: "", salesOrderId: 0, orderedOn: today() });
    setQtys({});
    setError(undefined);
  }

  function select(id: number | undefined) {
    guard.guard(() => {
      setSelectedId(id);
      setReason("");
      setError(undefined);
    });
  }

  function chooseOrder(id: number) {
    const picked = shippable.find((o) => o.id === id);
    setCreate({ ...create, salesOrderId: id });
    // 기본값은 남은 수량 전부. 남은 수량이 없는 명세는 비운다.
    setQtys(
      Object.fromEntries(
        (picked?.lines ?? []).map((l) => [
          l.id,
          remaining(l) > 0 ? String(remaining(l)) : "",
        ]),
      ),
    );
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending || !order) return;
    const created = await send<ShipOrder>("/shipment-orders", "POST", {
      shipOrderNo: create.shipOrderNo.trim().toUpperCase(),
      salesOrderId: order.id,
      orderedOn: create.orderedOn,
      lines: order.lines
        .filter((l) => (qtys[l.id] ?? "").trim())
        .map((l) => ({ salesOrderLineId: l.id, orderQty: qtys[l.id].trim() })),
    });
    if (created) {
      setCreate({ shipOrderNo: "", salesOrderId: 0, orderedOn: today() });
      setQtys({});
      setPanelOpen(false);
      select(created.id);
    }
  }

  async function cancel() {
    if (!selected || pending) return;
    const saved = await send(`/shipment-orders/${selected.id}/cancel`, "POST", {
      reason: reason.trim(),
    });
    if (saved) setReason("");
  }

  const columns: Column<ShipOrder>[] = [
    { key: "shipOrderNo", label: "출하지시번호" },
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
    { key: "orderNo", label: "수주번호" },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "orderedOn", label: "지시일" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={SHIP_STATUS[r.status][1]}>
          {SHIP_STATUS[r.status][0]}
        </Badge>
      ),
    },
    {
      key: "shipmentNo",
      label: "출하",
      render: (r) => r.shipmentNo ?? r.cancelReason ?? "-",
    },
  ];
  const lineColumns: Column<ShipOrderLine>[] = [
    { key: "lineNo", label: "수주 행" },
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "orderQty",
      label: "지시 수량",
      render: (r) => `${qty(r.orderQty)} ${r.unit}`,
    },
  ];
  const draftRows = (order?.lines ?? []).map((l) => ({
    ...l,
    remainingQty: String(remaining(l)),
  }));
  const draftColumns: Column<(typeof draftRows)[number]>[] = [
    { key: "lineNo", label: "행" },
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "orderQty",
      label: "수주",
      render: (r) => `${qty(r.orderQty)} ${r.unit}`,
    },
    {
      key: "remainingQty",
      label: "지시 가능",
      render: (r) => qty(r.remainingQty),
    },
    {
      key: "id",
      label: "이번 지시",
      render: (r) => (
        <input
          aria-label={`${r.lineNo}행 지시 수량`}
          inputMode="decimal"
          value={qtys[r.id] ?? ""}
          onChange={(e) => setQtys({ ...qtys, [r.id]: e.target.value })}
        />
      ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="E-05"
        title="출하지시"
        subtitle="수주 명세에서 출하할 수량을 배정합니다"
        help="erp/e-05"
        actions={
          <button
            type="button"
            aria-pressed={panelOpen}
            onClick={() =>
              guard.guard(() => (panelOpen ? closeCreate() : openCreate()))
            }
          >
            출하지시 만들기
          </button>
        }
      />
      <p className="muted">
        한 수주를 여러 지시로 나눌 수 있지만, 지시 합계는 수주 수량을 넘을 수
        없습니다. 지시는 E-06 출하에서 지시 수량 그대로 한 번에 출하합니다.
        수량을 바꾸려면 미출하 지시를 취소하고 다시 만드세요.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!shipOrders ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <DataTable
                rows={shipOrders}
                columns={columns}
                caption="출하지시 목록"
                offset={0}
                total={shipOrders.length}
                limit={shipOrders.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 출하지시가 없습니다. 패널을 열어 수주를 골라 지시하세요."
                    action="출하지시 만들기"
                    onAction={() => guard.guard(openCreate)}
                  />
                }
              />
            </div>

            {selected && (
              <section className="section-block" aria-label="출하지시 명세">
                <div className="section-heading">
                  <h2>
                    {selected.shipOrderNo} 명세{" "}
                    <Badge tone={SHIP_STATUS[selected.status][1]}>
                      {SHIP_STATUS[selected.status][0]}
                    </Badge>
                  </h2>
                </div>
                <DataTable
                  rows={selected.lines}
                  columns={lineColumns}
                  caption={`${selected.shipOrderNo} 지시 명세`}
                  offset={0}
                  total={selected.lines.length}
                  limit={selected.lines.length || 1}
                  onPage={() => undefined}
                />
                {selected.status === "open" && (
                  <div className="form-actions">
                    <Field
                      label="취소 사유"
                      value={reason}
                      maxLength={300}
                      error={errors.reason}
                      onChange={(e) => setReason(e.target.value)}
                    />
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending || !reason.trim()}
                      onClick={() => void cancel()}
                    >
                      지시 취소
                    </button>
                  </div>
                )}
              </section>
            )}
          </section>

          {panelOpen && (
            <FormPanel
              title="출하지시 만들기"
              guard={guard}
              onClose={() => guard.guard(closeCreate)}
              onSubmit={(e) => void submitCreate(e)}
              actions={
                <>
                  <button
                    type="submit"
                    disabled={pending || !order}
                    aria-busy={pending}
                  >
                    출하지시
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closeCreate)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <Field
                label="출하지시번호"
                value={create.shipOrderNo}
                required
                maxLength={40}
                placeholder="예: SH-O-0101"
                error={errors.shipOrderNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    shipOrderNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="ship-order-sales-order">수주</label>
                <select
                  id="ship-order-sales-order"
                  value={create.salesOrderId || ""}
                  onChange={(e) => chooseOrder(Number(e.target.value))}
                >
                  <option value="">수주 선택</option>
                  {shippable.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.orderNo} · {name.partner(o.partnerId)}
                    </option>
                  ))}
                </select>
              </div>
              <Field
                label="지시일"
                type="date"
                value={create.orderedOn}
                required
                error={errors.orderedOn}
                onChange={(e) =>
                  setCreate({ ...create, orderedOn: e.target.value })
                }
              />
              {order && (
                <DataTable
                  rows={draftRows}
                  columns={draftColumns}
                  caption={`${order.orderNo} 수주 명세`}
                  offset={0}
                  total={draftRows.length}
                  limit={draftRows.length || 1}
                  onPage={() => undefined}
                />
              )}
              {errors.lines && <p className="notice">{errors.lines}</p>}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
