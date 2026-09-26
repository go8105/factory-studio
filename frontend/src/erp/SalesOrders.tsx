// E-04 수주 — 직접 등록 또는 견적 전환, 명세별 출하 진행률 (FS-019b)
import { useState, type FormEvent } from "react";
import {
  Badge,
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
  customers,
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

type OrderLine = {
  id: number;
  lineNo: number;
  itemId: number;
  orderQty: string;
  unit: string;
  unitPrice: string;
  amount: string;
  instructedQty: string;
  shippedQty: string;
};
export type Order = {
  id: number;
  orderNo: string;
  partnerId: number;
  orderedOn: string;
  dueOn: string;
  status: "open" | "shipping" | "closed" | "cancelled";
  quotationId: number | null;
  quoteNo: string | null;
  quoteRevisionNo: number | null;
  shipmentOrderCount: number;
  totalAmount: string;
  lines: OrderLine[];
};
export type DraftLine = {
  itemId: number;
  qty: string;
  unitPrice: string;
  discountRate?: string;
};

const STATUS: Record<
  Order["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  open: ["접수", "warning"],
  shipping: ["출하 중", "normal"],
  closed: ["완료", "normal"],
  cancelled: ["취소", "issue"],
};
const today = () => new Date().toLocaleDateString("sv-SE");
const editable = (o: Order) => o.status === "open" && !o.shipmentOrderCount;

/** 품목·수량·단가 라인 편집 표. 단가를 비우면 서버가 거래처 단가를 넣는다. */
export function LineEditor({
  lines,
  items,
  onChange,
  caption,
  discount = false,
}: {
  lines: DraftLine[];
  items: Item[];
  onChange: (lines: DraftLine[]) => void;
  caption: string;
  discount?: boolean;
}) {
  const rows = lines.map((l, i) => ({ id: i, ...l }));
  const set = (index: number, patch: Partial<DraftLine>) =>
    onChange(lines.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  const columns: Column<(typeof rows)[number]>[] = [
    {
      key: "itemId",
      label: "품목",
      render: (r) => (
        <select
          aria-label={`${r.id + 1}번째 품목`}
          value={r.itemId}
          onChange={(e) => set(r.id, { itemId: Number(e.target.value) })}
        >
          {items.map((i) => (
            <option key={i.id} value={i.id}>
              {i.itemCode} {i.name} ({i.baseUnit})
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "qty",
      label: "수량",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 수량`}
          inputMode="decimal"
          value={r.qty}
          onChange={(e) => set(r.id, { qty: e.target.value })}
        />
      ),
    },
    {
      key: "unitPrice",
      label: "단가",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 단가`}
          inputMode="decimal"
          placeholder="비우면 거래처 단가"
          value={r.unitPrice}
          onChange={(e) => set(r.id, { unitPrice: e.target.value })}
        />
      ),
    },
    ...(discount
      ? [
          {
            key: "discountRate" as const,
            label: "할인율(%)",
            render: (r: (typeof rows)[number]) => (
              <input
                aria-label={`${r.id + 1}번째 할인율`}
                inputMode="decimal"
                value={r.discountRate ?? "0"}
                onChange={(e) => set(r.id, { discountRate: e.target.value })}
              />
            ),
          },
        ]
      : []),
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-label={`${r.id + 1}번째 라인 빼기`}
          onClick={() => onChange(lines.filter((_, i) => i !== r.id))}
        >
          빼기
        </button>
      ),
    },
  ];
  return (
    <>
      <DataTable
        rows={rows}
        columns={columns}
        caption={caption}
        offset={0}
        total={rows.length}
        limit={rows.length || 1}
        onPage={() => undefined}
        empty={<p className="muted">라인이 없습니다.</p>}
      />
      <div className="form-actions">
        <button
          type="button"
          className="secondary"
          disabled={items.length === 0}
          onClick={() =>
            onChange([
              ...lines,
              { itemId: items[0].id, qty: "", unitPrice: "" },
            ])
          }
        >
          라인 추가
        </button>
      </div>
    </>
  );
}

const orderLines = (lines: DraftLine[]) =>
  lines.map((l) => ({
    itemId: l.itemId,
    orderQty: l.qty.trim(),
    unitPrice: l.unitPrice.trim() || null,
  }));

export function SalesOrders() {
  const { data, error, reload } = useLists<[Order[], Partner[], Item[]]>([
    "/sales-orders",
    PARTNERS,
    ITEMS,
  ]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [edit, setEdit] = useState<{ dueOn: string; lines: DraftLine[] }>();
  const blank = { orderNo: "", partnerId: 0, orderedOn: today(), dueOn: "" };
  const [create, setCreate] = useState(blank);
  const [createLines, setCreateLines] = useState<DraftLine[]>([]);

  if (moduleOff(error)) return <ModuleOff />;
  const [orders, partners, allItems] = data ?? [undefined, [], []];
  const items = allItems.filter((i) => i.isActive);
  const buyers = customers(partners);
  const name = labels(partners, allItems);
  const errors = fieldErrors(saveError);
  const selected = orders?.find((o) => o.id === selectedId);

  function select(id: number | undefined) {
    setSelectedId(id);
    setEdit(undefined);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Order>("/sales-orders", "POST", {
      ...create,
      orderNo: create.orderNo.trim().toUpperCase(),
      partnerId: create.partnerId || buyers[0]?.id,
      lines: orderLines(createLines),
    });
    if (created) {
      setCreate(blank);
      setCreateLines([]);
      select(created.id);
    }
  }

  async function saveEdit() {
    if (!selected || !edit || pending) return;
    const saved = await send(`/sales-orders/${selected.id}`, "PATCH", {
      dueOn: edit.dueOn,
      lines: orderLines(edit.lines),
    });
    if (saved) setEdit(undefined);
  }

  const columns: Column<Order>[] = [
    { key: "orderNo", label: "수주번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => select(r.id)}
          >
            명세 {r.lines.length}
          </button>
          {editable(r) && (
            <button
              type="button"
              className="link-button"
              onClick={() => void send(`/sales-orders/${r.id}/cancel`, "POST")}
            >
              취소
            </button>
          )}
        </span>
      ),
    },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "orderedOn", label: "수주일" },
    { key: "dueOn", label: "납기일" },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={STATUS[r.status][1]}>{STATUS[r.status][0]}</Badge>
      ),
    },
    {
      key: "totalAmount",
      label: "공급가액",
      render: (r) => won(r.totalAmount),
    },
    {
      key: "quoteNo",
      label: "근거 견적",
      render: (r) =>
        r.quoteNo ? `${r.quoteNo} (${r.quoteRevisionNo}차)` : "직접 등록",
    },
  ];
  const lineColumns: Column<OrderLine>[] = [
    { key: "lineNo", label: "행" },
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "orderQty",
      label: "수주",
      render: (r) => `${qty(r.orderQty)} ${r.unit}`,
    },
    { key: "unitPrice", label: "단가", render: (r) => won(r.unitPrice) },
    { key: "amount", label: "금액", render: (r) => won(r.amount) },
    {
      key: "instructedQty",
      label: "출하지시",
      render: (r) => qty(r.instructedQty),
    },
    {
      key: "shippedQty",
      label: "출하 진행",
      render: (r) =>
        `${qty(r.orderQty)}개 중 ${qty(r.shippedQty)}개 출하 (${Math.floor(
          (Number(r.shippedQty) / Number(r.orderQty)) * 100,
        )}%)`,
    },
  ];

  return (
    <>
      <PageTitle
        id="E-04"
        title="수주"
        subtitle="수주를 등록하고 명세별 출하 진행률을 봅니다"
        help="erp/e-04"
      />
      <p className="muted">
        견적 없이 직접 등록하는 수주도 정상 경로입니다. 견적에서 만들려면 E-02
        견적의 &quot;수주 전환&quot;을 쓰세요. 납기일은 납품 기일이지 결제
        만기가 아닙니다. 출하지시가 생기면 수주 내용을 바꿀 수 없습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!orders ? (
        !error && <Loading />
      ) : (
        <>
          <DataTable
            rows={orders}
            columns={columns}
            caption="수주 목록"
            offset={0}
            total={orders.length}
            limit={orders.length || 1}
            onPage={() => undefined}
            empty={
              <EmptyState
                reason="등록된 수주가 없습니다. 아래 폼에서 첫 수주를 등록하세요."
                to="#sales-order-form"
                action="수주 등록"
              />
            }
          />

          <RevealAnchor when={selected} />

          {selected && (
            <section className="panel" aria-label="수주 명세">
              <h2>
                {selected.orderNo} 명세{" "}
                <Badge tone={STATUS[selected.status][1]}>
                  {STATUS[selected.status][0]}
                </Badge>
              </h2>
              {edit ? (
                <>
                  <Field
                    label="납기일"
                    type="date"
                    value={edit.dueOn}
                    error={errors.dueOn}
                    onChange={(e) =>
                      setEdit({ ...edit, dueOn: e.target.value })
                    }
                  />
                  <LineEditor
                    lines={edit.lines}
                    items={items}
                    caption={`${selected.orderNo} 명세 편집`}
                    onChange={(lines) => setEdit({ ...edit, lines })}
                  />
                  {errors.lines && <p className="notice">{errors.lines}</p>}
                  <div className="form-actions">
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setEdit(undefined)}
                    >
                      편집 취소
                    </button>
                    <button
                      type="button"
                      disabled={pending}
                      onClick={() => void saveEdit()}
                    >
                      저장
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <DataTable
                    rows={selected.lines}
                    columns={lineColumns}
                    caption={`${selected.orderNo} 수주 명세`}
                    offset={0}
                    total={selected.lines.length}
                    limit={selected.lines.length || 1}
                    onPage={() => undefined}
                  />
                  {editable(selected) ? (
                    <div className="form-actions">
                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          setEdit({
                            dueOn: selected.dueOn,
                            lines: selected.lines.map((l) => ({
                              itemId: l.itemId,
                              qty: String(Number(l.orderQty)),
                              unitPrice: String(Number(l.unitPrice)),
                            })),
                          })
                        }
                      >
                        명세 편집
                      </button>
                    </div>
                  ) : (
                    <p className="muted">
                      출하지시가 있거나 종결된 수주라 내용을 바꿀 수 없습니다.
                    </p>
                  )}
                </>
              )}
            </section>
          )}

          <form
            id="sales-order-form"
            className="panel"
            aria-label="수주 등록"
            onSubmit={(e) => void submitCreate(e)}
          >
            <h2>새 수주</h2>
            <div className="master-grid">
              <Field
                label="수주번호"
                value={create.orderNo}
                required
                maxLength={40}
                placeholder="예: SO-0101"
                error={errors.orderNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    orderNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="order-partner">거래처</label>
                <select
                  id="order-partner"
                  value={create.partnerId || buyers[0]?.id || ""}
                  onChange={(e) =>
                    setCreate({ ...create, partnerId: Number(e.target.value) })
                  }
                >
                  {buyers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.partnerCode} {p.partnerName}
                    </option>
                  ))}
                </select>
                {errors.partnerId && <small>{errors.partnerId}</small>}
              </div>
              <Field
                label="수주일"
                type="date"
                value={create.orderedOn}
                required
                error={errors.orderedOn}
                onChange={(e) =>
                  setCreate({ ...create, orderedOn: e.target.value })
                }
              />
              <Field
                label="납기일"
                type="date"
                value={create.dueOn}
                required
                error={errors.dueOn}
                onChange={(e) =>
                  setCreate({ ...create, dueOn: e.target.value })
                }
              />
            </div>
            <LineEditor
              lines={createLines}
              items={items}
              caption="새 수주 명세"
              onChange={setCreateLines}
            />
            {errors.lines && <p className="notice">{errors.lines}</p>}
            <div className="form-actions">
              <button
                type="submit"
                disabled={pending || createLines.length === 0}
              >
                수주 등록
              </button>
            </div>
          </form>
        </>
      )}
    </>
  );
}
