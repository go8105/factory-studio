// E-02 견적 — 작성·확정·제출·수락/거절, 개정 이력, 수주 전환 (FS-019b)
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
import { LineEditor, type DraftLine } from "./SalesOrders";

type Status =
  "draft" | "confirmed" | "sent" | "accepted" | "rejected" | "cancelled";
type QuoteLine = {
  id: number;
  lineNo: number;
  itemId: number;
  quoteQty: string;
  unit: string;
  unitPrice: string;
  discountRate: string;
  amount: string;
  masterPrice: string | null;
  priceSource: "partner_price" | "manual";
};
type History = {
  id: number;
  status: Status;
  changedAt: string;
  reason: string | null;
};
type Quote = {
  id: number;
  quoteNo: string;
  revisionNo: number;
  revisionCount: number;
  isLatest: boolean;
  partnerId: number;
  quotedOn: string;
  validUntil: string | null;
  status: Status;
  remark: string | null;
  salesOrderId: number | null;
  totalAmount: string;
  lines: QuoteLine[];
  history: History[];
};

const STATUS: Record<Status, [string, "normal" | "warning" | "issue"]> = {
  draft: ["작성", "warning"],
  confirmed: ["확정", "normal"],
  sent: ["제출", "normal"],
  accepted: ["수락", "normal"],
  rejected: ["거절", "issue"],
  cancelled: ["취소", "issue"],
};
const badge = (s: Status) => <Badge tone={STATUS[s][1]}>{STATUS[s][0]}</Badge>;
const today = () => new Date().toLocaleDateString("sv-SE");

function Lines({
  quote,
  item,
}: {
  quote: Quote;
  item: (id: number) => string;
}) {
  const columns: Column<QuoteLine>[] = [
    { key: "lineNo", label: "행" },
    { key: "itemId", label: "품목", render: (r) => item(r.itemId) },
    {
      key: "quoteQty",
      label: "수량",
      render: (r) => `${qty(r.quoteQty)} ${r.unit}`,
    },
    { key: "unitPrice", label: "단가", render: (r) => won(r.unitPrice) },
    {
      key: "priceSource",
      label: "단가 출처",
      render: (r) =>
        r.priceSource === "partner_price" ? (
          <Badge>거래처 단가 적용</Badge>
        ) : (
          <Badge tone="warning">
            수동 입력
            {r.masterPrice ? ` (단가표 ${won(r.masterPrice)})` : ""}
          </Badge>
        ),
    },
    {
      key: "discountRate",
      label: "할인율",
      render: (r) => `${Number(r.discountRate)}%`,
    },
    { key: "amount", label: "금액", render: (r) => won(r.amount) },
  ];
  return (
    <DataTable
      rows={quote.lines}
      columns={columns}
      caption={`${quote.quoteNo} ${quote.revisionNo}차 명세`}
      offset={0}
      total={quote.lines.length}
      limit={quote.lines.length || 1}
      onPage={() => undefined}
      empty={<p className="muted">라인이 없습니다.</p>}
    />
  );
}

/** 같은 견적번호의 모든 개정본. 이전 개정본은 읽기 전용으로 연다. */
function Revisions({ id, item }: { id: number; item: (id: number) => string }) {
  const { data, error, reload } = useLists<[Quote[]]>([
    `/quotations/${id}/revisions`,
  ]);
  const [open, setOpen] = useState<number>();
  if (!data)
    return error ? <ErrorNotice error={error} retry={reload} /> : <Loading />;
  const [revisions] = data;
  const shown = revisions.find((r) => r.id === open);
  const columns: Column<Quote>[] = [
    { key: "revisionNo", label: "개정", render: (r) => `${r.revisionNo}차` },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={r.id === open}
          onClick={() => setOpen(r.id)}
        >
          열기
        </button>
      ),
    },
    { key: "quotedOn", label: "견적일" },
    { key: "status", label: "상태", render: (r) => badge(r.status) },
    {
      key: "totalAmount",
      label: "공급가액",
      render: (r) => won(r.totalAmount),
    },
    {
      key: "isLatest",
      label: "구분",
      render: (r) => (r.isLatest ? "최신" : "이전"),
    },
  ];
  return (
    <>
      <DataTable
        rows={revisions}
        columns={columns}
        caption="개정 이력"
        offset={0}
        total={revisions.length}
        limit={revisions.length || 1}
        onPage={() => undefined}
      />
      {shown && (
        <>
          <p className="muted">
            {shown.revisionNo}차{" "}
            {shown.isLatest ? "(최신)" : "(이전 개정본 · 읽기 전용)"}
          </p>
          <Lines quote={shown} item={item} />
        </>
      )}
    </>
  );
}

export function Quotations() {
  const { data, error, reload } = useLists<[Quote[], Partner[], Item[]]>([
    "/quotations",
    PARTNERS,
    ITEMS,
  ]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [lines, setLines] = useState<DraftLine[]>();
  const [reason, setReason] = useState("");
  const [showRevisions, setShowRevisions] = useState(false);
  const blank = {
    quoteNo: "",
    partnerId: 0,
    quotedOn: today(),
    validUntil: "",
    remark: "",
  };
  const [create, setCreate] = useState(blank);
  const [convert, setConvert] = useState({
    orderNo: "",
    orderedOn: today(),
    dueOn: "",
  });

  if (moduleOff(error)) return <ModuleOff />;
  const [quotes, partners, allItems] = data ?? [undefined, [], []];
  const items = allItems.filter((i) => i.isActive);
  const buyers = customers(partners);
  const name = labels(partners, allItems);
  const errors = fieldErrors(saveError);
  const selected = quotes?.find((q) => q.id === selectedId);
  const original: DraftLine[] = (selected?.lines ?? []).map((l) => ({
    itemId: l.itemId,
    qty: String(Number(l.quoteQty)),
    unitPrice:
      l.priceSource === "partner_price" ? "" : String(Number(l.unitPrice)),
    discountRate: String(Number(l.discountRate)),
  }));
  const draft = lines ?? original;
  const dirty =
    lines !== undefined && JSON.stringify(lines) !== JSON.stringify(original);

  function select(id: number | undefined) {
    setSelectedId(id);
    setLines(undefined);
    setReason("");
    setShowRevisions(false);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Quote>("/quotations", "POST", {
      quoteNo: create.quoteNo.trim().toUpperCase(),
      partnerId: create.partnerId || buyers[0]?.id,
      quotedOn: create.quotedOn,
      validUntil: create.validUntil || null,
      remark: create.remark.trim() || null,
    });
    if (created) {
      setCreate(blank);
      select(created.id);
    }
  }

  async function saveLines() {
    if (!selected || pending) return;
    const saved = await send(`/quotations/${selected.id}/lines`, "PUT", {
      lines: draft.map((l) => ({
        itemId: l.itemId,
        quoteQty: l.qty.trim(),
        unitPrice: l.unitPrice.trim() || null,
        discountRate: (l.discountRate ?? "0").trim() || "0",
      })),
    });
    if (saved) setLines(undefined);
  }

  async function move(status: Status) {
    if (!selected || pending) return;
    const saved = await send(`/quotations/${selected.id}/status`, "POST", {
      status,
      reason: reason.trim() || null,
    });
    if (saved) setReason("");
  }

  async function revise() {
    if (!selected || pending) return;
    const created = await send<Quote>(
      `/quotations/${selected.id}/revise`,
      "POST",
    );
    if (created) select(created.id);
  }

  async function submitConvert(event: FormEvent) {
    event.preventDefault();
    if (!selected || pending) return;
    const order = await send(`/quotations/${selected.id}/convert`, "POST", {
      ...convert,
      orderNo: convert.orderNo.trim().toUpperCase(),
    });
    if (order) setConvert({ orderNo: "", orderedOn: today(), dueOn: "" });
  }

  const columns: Column<Quote>[] = [
    { key: "quoteNo", label: "견적번호" },
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
          열기
        </button>
      ),
    },
    {
      key: "revisionNo",
      label: "개정",
      render: (r) =>
        `${r.revisionNo}차${r.revisionCount > 1 ? ` (${r.revisionCount}건)` : ""}`,
    },
    {
      key: "partnerId",
      label: "거래처",
      render: (r) => name.partner(r.partnerId),
    },
    { key: "quotedOn", label: "견적일" },
    {
      key: "validUntil",
      label: "유효기한",
      render: (r) => r.validUntil ?? "-",
    },
    { key: "status", label: "상태", render: (r) => badge(r.status) },
    {
      key: "totalAmount",
      label: "공급가액",
      render: (r) => won(r.totalAmount),
    },
    {
      key: "salesOrderId",
      label: "수주",
      render: (r) => (r.salesOrderId ? "전환됨" : "-"),
    },
  ];

  const s = selected?.status;
  const canConvert =
    !!selected && !selected.salesOrderId && (s === "sent" || s === "accepted");
  return (
    <>
      <PageTitle
        id="E-02"
        title="견적"
        subtitle="견적을 작성·제출하고 개정 이력과 수주 전환을 관리합니다"
        help="erp/e-02"
      />
      <p className="muted">
        단가를 비우면 거래처별 단가(E-17)의 견적일 기준 단가를 가져와 견적에
        복사합니다. 확정한 견적은 고칠 수 없고 &quot;개정&quot;으로 새 차수를
        만듭니다. 이전 차수는 읽기 전용으로 남습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!quotes ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={quotes}
                columns={columns}
                caption="견적 목록 (최신 개정본)"
                offset={0}
                total={quotes.length}
                limit={quotes.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 견적이 없습니다. 우측 폼에서 첫 견적을 만드세요."
                    to="#quotation-form"
                    action="견적 만들기"
                  />
                }
              />
            </section>
            <form
              id="quotation-form"
              className="panel"
              aria-label="견적 만들기"
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 견적</h2>
              <Field
                label="견적번호"
                value={create.quoteNo}
                required
                maxLength={40}
                placeholder="예: Q-0101"
                error={errors.quoteNo}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    quoteNo: e.target.value.toUpperCase(),
                  })
                }
              />
              <div className="field">
                <label htmlFor="quote-partner">거래처</label>
                <select
                  id="quote-partner"
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
                label="견적일"
                type="date"
                value={create.quotedOn}
                required
                error={errors.quotedOn}
                onChange={(e) =>
                  setCreate({ ...create, quotedOn: e.target.value })
                }
              />
              <Field
                label="유효기한 (선택)"
                type="date"
                value={create.validUntil}
                error={errors.validUntil}
                onChange={(e) =>
                  setCreate({ ...create, validUntil: e.target.value })
                }
              />
              <Field
                label="비고 (선택)"
                value={create.remark}
                maxLength={1000}
                onChange={(e) =>
                  setCreate({ ...create, remark: e.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  만들기
                </button>
              </div>
            </form>
          </div>

          {selected ? (
            <section className="panel" aria-label="견적 상세">
              <h2>
                {selected.quoteNo} {selected.revisionNo}차{" "}
                {badge(selected.status)}
              </h2>
              <p className="muted">
                {name.partner(selected.partnerId)} · 견적일 {selected.quotedOn}{" "}
                · 공급가액 {won(selected.totalAmount)}
              </p>
              {s === "draft" ? (
                <>
                  <LineEditor
                    lines={draft}
                    items={items}
                    discount
                    caption={`${selected.quoteNo} 명세 편집`}
                    onChange={setLines}
                  />
                  {errors.lines && <p className="notice">{errors.lines}</p>}
                  <div className="form-actions">
                    <button
                      type="button"
                      disabled={pending || !dirty}
                      onClick={() => void saveLines()}
                    >
                      라인 저장
                    </button>
                  </div>
                  {selected.lines.length > 0 && (
                    <Lines quote={selected} item={name.item} />
                  )}
                </>
              ) : (
                <Lines quote={selected} item={name.item} />
              )}

              <div className="form-actions">
                {s === "draft" && (
                  <button
                    type="button"
                    disabled={pending || dirty}
                    onClick={() => void move("confirmed")}
                  >
                    확정
                  </button>
                )}
                {s === "confirmed" && (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => void move("sent")}
                  >
                    제출
                  </button>
                )}
                {s === "sent" && (
                  <button
                    type="button"
                    disabled={pending}
                    onClick={() => void move("accepted")}
                  >
                    수락
                  </button>
                )}
                {(s === "confirmed" || s === "sent" || s === "rejected") && (
                  <button
                    type="button"
                    className="secondary"
                    disabled={pending}
                    onClick={() => void revise()}
                  >
                    개정
                  </button>
                )}
              </div>
              {(s === "draft" || s === "confirmed" || s === "sent") && (
                <div className="form-actions">
                  <Field
                    label="거절·취소 사유"
                    value={reason}
                    maxLength={200}
                    error={errors.reason}
                    onChange={(e) => setReason(e.target.value)}
                  />
                  {s === "sent" && (
                    <button
                      type="button"
                      className="secondary"
                      disabled={pending || !reason.trim()}
                      onClick={() => void move("rejected")}
                    >
                      거절
                    </button>
                  )}
                  <button
                    type="button"
                    className="secondary"
                    disabled={pending || !reason.trim()}
                    onClick={() => void move("cancelled")}
                  >
                    견적 취소
                  </button>
                </div>
              )}

              {canConvert && (
                <form
                  aria-label="수주 전환"
                  onSubmit={(e) => void submitConvert(e)}
                >
                  <h3>수주 전환</h3>
                  <p className="muted">
                    할인율을 반영한 단가로 수주 명세를 만듭니다.
                  </p>
                  <div className="master-grid">
                    <Field
                      label="수주번호"
                      value={convert.orderNo}
                      required
                      maxLength={40}
                      error={errors.orderNo}
                      onChange={(e) =>
                        setConvert({
                          ...convert,
                          orderNo: e.target.value.toUpperCase(),
                        })
                      }
                    />
                    <Field
                      label="수주일"
                      type="date"
                      value={convert.orderedOn}
                      required
                      onChange={(e) =>
                        setConvert({ ...convert, orderedOn: e.target.value })
                      }
                    />
                    <Field
                      label="납기일"
                      type="date"
                      value={convert.dueOn}
                      required
                      error={errors.dueOn}
                      onChange={(e) =>
                        setConvert({ ...convert, dueOn: e.target.value })
                      }
                    />
                  </div>
                  <div className="form-actions">
                    <button type="submit" disabled={pending}>
                      수주로 전환
                    </button>
                  </div>
                </form>
              )}
              {selected.salesOrderId && (
                <p className="muted">
                  수주로 전환된 견적입니다. E-04 수주에서 확인하세요.
                </p>
              )}

              <h3>상태 이력</h3>
              <ol aria-label="상태 이력">
                {selected.history.map((h) => (
                  <li key={h.id}>
                    {new Date(h.changedAt).toLocaleString()} ·{" "}
                    {STATUS[h.status][0]}
                    {h.reason ? ` · ${h.reason}` : ""}
                  </li>
                ))}
              </ol>
              {selected.revisionCount > 1 &&
                (showRevisions ? (
                  <Revisions
                    key={selected.id}
                    id={selected.id}
                    item={name.item}
                  />
                ) : (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setShowRevisions(true)}
                  >
                    개정 이력 {selected.revisionCount}건 보기
                  </button>
                ))}
            </section>
          ) : (
            <p className="muted">
              목록에서 &quot;열기&quot;를 누르면 명세·상태 이력·개정 이력을 볼
              수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
