// E-11 매입 전표 — 원재료 매입 직접 등록, 확정 시 매입채무 생성, 취소(지급 소명 0행) (FS-019f)
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
import { JournalPanel } from "./Journal";

type Line = {
  id: number;
  lineNo: number;
  itemId: number;
  quantity: string;
  unit: string;
  unitPrice: string;
  supplyAmount: string;
  taxAmount: string;
  totalAmount: string;
};
type Invoice = {
  id: number;
  invoiceNo: string;
  partnerId: number;
  invoiceDate: string;
  dueDate: string | null;
  supplyAmount: string;
  taxAmount: string;
  totalAmount: string;
  status: "draft" | "confirmed" | "cancelled";
  cancelReason: string | null;
  appliedAmount: string;
  lines: Line[];
  cancelBlockedReason: "ALREADY_CANCELLED" | "PAYMENT_APPLIED" | null;
};
type DraftLine = {
  itemId: number;
  quantity: string;
  unit: string;
  unitPrice: string;
};
type RawItem = Item & { itemType: string };

const STATUS: Record<
  Invoice["status"],
  [string, "normal" | "warning" | "issue"]
> = {
  draft: ["작성", "warning"],
  confirmed: ["확정", "normal"],
  cancelled: ["취소", "issue"],
};
// 막힌 이유를 버튼 툴팁에 쓴다. 문구는 서버 409 메시지와 같다.
const BLOCKED = {
  ALREADY_CANCELLED: "이미 취소된 매입입니다.",
  PAYMENT_APPLIED:
    "지급 소명이 있어 취소할 수 없습니다. 소명을 먼저 취소하세요.",
};
const today = () => new Date().toLocaleDateString("sv-SE");

export function PurchaseInvoices() {
  const { data, error, reload } = useLists<[Invoice[], Partner[], RawItem[]]>([
    "/purchase-invoices",
    PARTNERS,
    ITEMS,
  ]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [lines, setLines] = useState<DraftLine[]>();
  const [cancelId, setCancelId] = useState<number>();
  const [reason, setReason] = useState("");
  const [journalId, setJournalId] = useState<number>();
  const blank = {
    invoiceNo: "",
    partnerId: 0,
    invoiceDate: today(),
    dueDate: "",
  };
  const [create, setCreate] = useState(blank);

  if (moduleOff(error)) return <ModuleOff />;
  const [invoices, partners, allItems] = data ?? [undefined, [], []];
  const suppliers = partners.filter(
    (p) => p.partnerKind === "SUPPLIER" && p.isActive,
  );
  const raws = allItems.filter((i) => i.itemType === "raw" && i.isActive);
  const name = labels(partners, allItems);
  const errors = fieldErrors(saveError);
  const selected = invoices?.find((i) => i.id === selectedId);
  const cancelTarget = invoices?.find((i) => i.id === cancelId);
  const original: DraftLine[] = (selected?.lines ?? []).map((l) => ({
    itemId: l.itemId,
    quantity: String(Number(l.quantity)),
    unit: l.unit,
    unitPrice: String(Number(l.unitPrice)),
  }));
  const draft = lines ?? original;
  const dirty =
    lines !== undefined && JSON.stringify(lines) !== JSON.stringify(original);

  function select(id: number | undefined) {
    setSelectedId(id);
    setLines(undefined);
    setCancelId(undefined);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Invoice>("/purchase-invoices", "POST", {
      invoiceNo: create.invoiceNo.trim().toUpperCase(),
      partnerId: create.partnerId || suppliers[0]?.id,
      invoiceDate: create.invoiceDate,
      dueDate: create.dueDate || null,
    });
    if (created) {
      setCreate(blank);
      select(created.id);
    }
  }

  async function saveLines() {
    if (!selected || pending) return;
    const saved = await send(`/purchase-invoices/${selected.id}/lines`, "PUT", {
      lines: draft.map((l) => ({
        ...l,
        quantity: l.quantity.trim(),
        unit: l.unit.trim().toUpperCase(),
        unitPrice: l.unitPrice.trim(),
      })),
    });
    if (saved) setLines(undefined);
  }

  async function cancel() {
    if (!cancelTarget || pending) return;
    const saved = await send(
      `/purchase-invoices/${cancelTarget.id}/cancel`,
      "POST",
      { reason: reason.trim() },
    );
    if (saved) {
      setCancelId(undefined);
      setReason("");
    }
  }

  const setLine = (index: number, patch: Partial<DraftLine>) =>
    setLines(draft.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const columns: Column<Invoice>[] = [
    { key: "invoiceNo", label: "전표번호" },
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
          {r.status === "confirmed" && (
            <button
              type="button"
              className="link-button"
              aria-pressed={r.id === journalId}
              onClick={() => setJournalId(r.id)}
            >
              분개
            </button>
          )}
          {r.status === "draft" && (
            <button
              type="button"
              className="link-button"
              onClick={() =>
                void send(`/purchase-invoices/${r.id}/confirm`, "POST")
              }
            >
              확정
            </button>
          )}
          <button
            type="button"
            className="link-button"
            disabled={!!r.cancelBlockedReason}
            title={
              r.cancelBlockedReason
                ? BLOCKED[r.cancelBlockedReason]
                : "매입을 취소합니다"
            }
            onClick={() => {
              setCancelId(r.id);
              setError(undefined);
            }}
          >
            취소
          </button>
          {r.status === "draft" &&
            deleteButtons(`pi:${r.id}`, `/purchase-invoices/${r.id}`)}
        </span>
      ),
    },
    {
      key: "partnerId",
      label: "공급처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "invoiceDate", label: "매입일" },
    {
      key: "dueDate",
      label: "만기",
      render: (r) =>
        r.dueDate ?? (r.status === "draft" ? "확정 시 결제조건" : "미설정"),
    },
    {
      key: "supplyAmount",
      label: "공급가액",
      render: (r) => won(r.supplyAmount),
    },
    { key: "taxAmount", label: "세액", render: (r) => won(r.taxAmount) },
    { key: "totalAmount", label: "합계", render: (r) => won(r.totalAmount) },
    {
      key: "appliedAmount",
      label: "소명액",
      render: (r) => won(r.appliedAmount),
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <Badge tone={STATUS[r.status][1]}>
          {STATUS[r.status][0]}
          {r.cancelReason ? ` · ${r.cancelReason}` : ""}
        </Badge>
      ),
    },
  ];
  const lineColumns: Column<Line>[] = [
    { key: "lineNo", label: "행" },
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "quantity",
      label: "수량",
      render: (r) => `${qty(r.quantity)} ${r.unit}`,
    },
    { key: "unitPrice", label: "단가", render: (r) => won(r.unitPrice) },
    {
      key: "supplyAmount",
      label: "공급가액",
      render: (r) => won(r.supplyAmount),
    },
    { key: "taxAmount", label: "세액", render: (r) => won(r.taxAmount) },
  ];
  const draftRows = draft.map((l, i) => ({ id: i, ...l }));
  const draftColumns: Column<(typeof draftRows)[number]>[] = [
    {
      key: "itemId",
      label: "품목",
      render: (r) => (
        <select
          aria-label={`${r.id + 1}번째 품목`}
          value={r.itemId}
          onChange={(e) => {
            const item = raws.find((i) => i.id === Number(e.target.value));
            setLine(r.id, {
              itemId: Number(e.target.value),
              unit: item?.baseUnit ?? "",
            });
          }}
        >
          {raws.map((i) => (
            <option key={i.id} value={i.id}>
              {i.itemCode} {i.name} ({i.baseUnit})
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "quantity",
      label: "수량",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 수량`}
          inputMode="decimal"
          value={r.quantity}
          onChange={(e) => setLine(r.id, { quantity: e.target.value })}
        />
      ),
    },
    {
      key: "unit",
      label: "단위",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 단위`}
          maxLength={10}
          value={r.unit}
          onChange={(e) => setLine(r.id, { unit: e.target.value })}
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
          value={r.unitPrice}
          onChange={(e) => setLine(r.id, { unitPrice: e.target.value })}
        />
      ),
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-label={`${r.id + 1}번째 라인 빼기`}
          onClick={() => setLines(draft.filter((_, i) => i !== r.id))}
        >
          빼기
        </button>
      ),
    },
  ];

  return (
    <>
      <PageTitle
        id="E-11"
        title="매입 전표"
        subtitle="원재료 매입을 등록·확정하고, 확정하면 매입채무가 생깁니다"
        help="erp/e-11"
      />
      <p className="muted">
        구매발주·입고검수는 WMS 영역이라 1차 범위에서 뺐고, 매입 전표를 직접
        등록합니다. 원재료 품목만 받습니다. 금액·세액은 서버가 명세마다
        계산합니다. 확정하면 매입채무가 함께 생기고, 지급 소명이 없을 때만
        취소할 수 있습니다(세금계산서와는 무관).
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!invoices ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={invoices}
                columns={columns}
                caption="매입 전표 목록"
                offset={0}
                total={invoices.length}
                limit={invoices.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 매입 전표가 없습니다. 우측 폼에서 등록하세요."
                    to="#purchase-form"
                    action="매입 등록"
                  />
                }
              />
            </section>
            <form
              id="purchase-form"
              className="panel"
              aria-label="매입 전표 등록"
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 매입 전표</h2>
              <Field
                label="전표번호"
                value={create.invoiceNo}
                required
                maxLength={40}
                placeholder="예: PI-0101"
                error={errors.invoiceNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    invoiceNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="purchase-partner">공급처</label>
                <select
                  id="purchase-partner"
                  value={create.partnerId || suppliers[0]?.id || ""}
                  onChange={(e) =>
                    setCreate({ ...create, partnerId: Number(e.target.value) })
                  }
                >
                  {suppliers.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.partnerCode} {p.partnerName}
                    </option>
                  ))}
                </select>
                {errors.partnerId && <small>{errors.partnerId}</small>}
              </div>
              <Field
                label="매입일"
                type="date"
                value={create.invoiceDate}
                required
                error={errors.invoiceDate}
                onChange={(e) =>
                  setCreate({ ...create, invoiceDate: e.target.value })
                }
              />
              <Field
                label="만기 (비우면 결제조건)"
                type="date"
                value={create.dueDate}
                error={errors.dueDate}
                onChange={(e) =>
                  setCreate({ ...create, dueDate: e.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  등록
                </button>
              </div>
            </form>
          </div>

          {journalId && (
            <JournalPanel
              kind="PURCHASE"
              id={journalId}
              onClose={() => setJournalId(undefined)}
            />
          )}
          {cancelTarget && (
            <section className="panel" aria-label="매입 취소">
              <h2>{cancelTarget.invoiceNo} 취소</h2>
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
                  onClick={() => setCancelId(undefined)}
                >
                  닫기
                </button>
                <button
                  type="button"
                  disabled={pending || !reason.trim()}
                  onClick={() => void cancel()}
                >
                  매입 취소 확정
                </button>
              </div>
            </section>
          )}

          {selected && (
            <section className="panel" aria-label="매입 명세">
              <h2>
                {selected.invoiceNo} 명세{" "}
                <Badge tone={STATUS[selected.status][1]}>
                  {STATUS[selected.status][0]}
                </Badge>
              </h2>
              <p className="muted">
                공급가액 {won(selected.supplyAmount)} · 세액{" "}
                {won(selected.taxAmount)} · 합계 {won(selected.totalAmount)}
              </p>
              {selected.status === "draft" ? (
                <>
                  <DataTable
                    rows={draftRows}
                    columns={draftColumns}
                    caption={`${selected.invoiceNo} 명세 편집`}
                    offset={0}
                    total={draftRows.length}
                    limit={draftRows.length || 1}
                    onPage={() => undefined}
                    empty={
                      <p className="muted">
                        명세가 없습니다. 명세가 없는 매입은 확정할 수 없습니다.
                      </p>
                    }
                  />
                  {errors.lines && <p className="notice">{errors.lines}</p>}
                  <div className="form-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={raws.length === 0}
                      onClick={() =>
                        setLines([
                          ...draft,
                          {
                            itemId: raws[0].id,
                            quantity: "",
                            unit: raws[0].baseUnit,
                            unitPrice: "",
                          },
                        ])
                      }
                    >
                      라인 추가
                    </button>
                    <button
                      type="button"
                      disabled={pending || !dirty}
                      onClick={() => void saveLines()}
                    >
                      명세 저장
                    </button>
                  </div>
                </>
              ) : (
                <DataTable
                  rows={selected.lines}
                  columns={lineColumns}
                  caption={`${selected.invoiceNo} 매입 명세`}
                  offset={0}
                  total={selected.lines.length}
                  limit={selected.lines.length || 1}
                  onPage={() => undefined}
                />
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
