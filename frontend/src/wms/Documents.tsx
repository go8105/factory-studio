// W-04 재고 전표 — 목록 + 넓은 행 편집 패널(UI-03 W 패턴, E-04 기준).
// 기초·조정·이동은 초안 → 확정. 원천 반영·되돌림 전표는 읽기만 한다. 확정 전표는 바꾸지 않는다(정정은 조정).
// 이동은 한 줄 = 보낼 위치·받을 위치 한 쌍이며 서버가 −/+ 두 줄로 저장한다(합 0).
import { useEffect, useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Field,
  FormPanel,
  Loading,
  PageTitle,
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  ModuleOff,
  moduleOff,
  num,
  REASON_LABEL,
  signed,
  TYPE_LABEL,
  useLists,
  useSend,
  WMS,
  type DocumentType,
  type Item,
  type Location,
  type ManualType,
  type Reason,
  type StockDocument,
  type Warehouse,
} from "./common";

type Line = {
  itemId: string;
  locationId: string;
  fromLocationId: string;
  toLocationId: string;
  lotNo: string;
  qty: string;
};
type Draft = {
  type: ManualType;
  documentOn: string;
  reasonCode: Reason | "";
  note: string;
  lines: Line[];
};
const EMPTY_LINE: Line = {
  itemId: "",
  locationId: "",
  fromLocationId: "",
  toLocationId: "",
  lotNo: "",
  qty: "",
};
const MANUAL: ManualType[] = ["OPENING", "ADJUSTMENT", "TRANSFER"];

function draftOf(doc: StockDocument): Draft {
  const moves = doc.moves ?? [];
  const lines: Line[] =
    doc.documentType === "TRANSFER"
      ? moves
          .filter((_, i) => i % 2 === 0)
          .map((out, i) => ({
            ...EMPTY_LINE,
            itemId: String(out.itemId),
            lotNo: out.lotNo ?? "",
            fromLocationId: String(out.locationId),
            toLocationId: String(moves[i * 2 + 1]?.locationId ?? ""),
            qty: String(Math.abs(Number(out.qtyDelta))),
          }))
      : moves.map((m) => ({
          ...EMPTY_LINE,
          itemId: String(m.itemId),
          locationId: String(m.locationId),
          lotNo: m.lotNo ?? "",
          qty: String(Number(m.qtyDelta)),
        }));
  return {
    type: doc.documentType as ManualType,
    documentOn: doc.documentOn,
    reasonCode: doc.reasonCode ?? "",
    note: doc.note ?? "",
    lines,
  };
}

function body(draft: Draft) {
  return {
    documentOn: draft.documentOn || null,
    reasonCode: draft.type === "ADJUSTMENT" ? draft.reasonCode || null : null,
    note: draft.note.trim() || null,
    lines: draft.lines.map((l) => ({
      itemId: Number(l.itemId),
      lotNo: l.lotNo.trim() || null,
      qty: l.qty.trim(),
      ...(draft.type === "TRANSFER"
        ? {
            fromLocationId: Number(l.fromLocationId) || null,
            toLocationId: Number(l.toLocationId) || null,
          }
        : { locationId: Number(l.locationId) || null }),
    })),
  };
}

export function Documents() {
  const [params, setParams] = useSearchParams();
  const lists = useLists<[StockDocument[], Item[], Warehouse[]]>([
    "/documents",
    "/items",
    "/warehouses",
  ]);
  const { send, pending, error: saveError, setError } = useSend(lists.reload);
  const [locations, setLocations] = useState<Location[]>([]);
  const [filter, setFilter] = useState<{ type: string; status: string }>({
    type: "",
    status: "",
  });
  const [detail, setDetail] = useState<StockDocument | null>(null);
  const [editing, setEditing] = useState<{ id: number | null } | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [initial, setInitial] = useState<Draft | null>(null);
  const [notice, setNotice] = useState<string>();
  const guard = useDiscardGuard(
    !!editing && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  const [docs, items, warehouses] = lists.data ?? [[], [], []];

  useEffect(() => {
    if (!warehouses.length) return;
    void Promise.all(
      warehouses.map((w) =>
        api<Location[]>(`${WMS}/warehouses/${w.id}/locations`),
      ),
    ).then((r) => setLocations(r.flatMap((x) => x.data)));
  }, [warehouses.length]);
  const opened = params.get("open");
  useEffect(() => {
    if (opened) void openDetail(Number(opened));
  }, [opened]);
  if (moduleOff(lists.error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openDetail(id: number) {
    try {
      const r = await api<StockDocument>(`${WMS}/documents/${id}`);
      setEditing(null);
      setDetail(r.data);
      setError(undefined);
    } catch (e) {
      setError(e);
    }
  }
  function openNew(type: ManualType) {
    const values: Draft = {
      type,
      documentOn: "",
      reasonCode: "",
      note: "",
      lines: [{ ...EMPTY_LINE }],
    };
    setDetail(null);
    setEditing({ id: null });
    setDraft(values);
    setInitial(values);
    setNotice(undefined);
  }
  function openEdit(doc: StockDocument) {
    const values = draftOf(doc);
    setDetail(null);
    setEditing({ id: doc.id });
    setDraft(values);
    setInitial(values);
  }
  async function save(post: boolean) {
    if (!draft) return;
    const saved = editing?.id
      ? await send<StockDocument>(
          `/documents/${editing.id}`,
          "PATCH",
          body(draft),
        )
      : await send<StockDocument>("/documents", "POST", {
          documentType: draft.type,
          ...body(draft),
        });
    if (!saved) return;
    setInitial(draft);
    if (!post) {
      setEditing({ id: saved.id });
      setNotice(`${saved.documentNo} 임시 저장`);
      return;
    }
    const posted = await send<StockDocument>(
      `/documents/${saved.id}/post`,
      "POST",
    );
    if (!posted) {
      setEditing({ id: saved.id });
      return;
    }
    setEditing(null);
    setNotice(
      `${posted.documentNo} 확정` +
        (posted.negative?.length
          ? ` · 재고가 음수가 됩니다: ${posted.negative
              .map(
                (n) =>
                  `${n.itemCode} ${n.locationCode}${n.lotNo ? ` ${n.lotNo}` : ""} ${num(n.onHand)}`,
              )
              .join(", ")}`
          : ""),
    );
    setDetail(posted);
  }
  function submit(event: FormEvent) {
    event.preventDefault();
    void save(false);
  }

  const shown = docs.filter(
    (d) =>
      (!filter.type || d.documentType === filter.type) &&
      (!filter.status || d.status === filter.status),
  );
  const columns: Column<StockDocument>[] = [
    { key: "documentNo", label: "전표번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          {r.status === "draft" ? (
            <button
              type="button"
              className="link-button"
              aria-pressed={editing?.id === r.id}
              onClick={() =>
                guard.guard(
                  () =>
                    void api<StockDocument>(`${WMS}/documents/${r.id}`).then(
                      (x) => openEdit(x.data),
                    ),
                )
              }
            >
              편집
            </button>
          ) : (
            <button
              type="button"
              className="link-button"
              aria-pressed={detail?.id === r.id}
              onClick={() => guard.guard(() => void openDetail(r.id))}
            >
              상세
            </button>
          )}
        </span>
      ),
    },
    {
      key: "documentType",
      label: "유형",
      render: (r) =>
        TYPE_LABEL[r.documentType] +
        (r.reasonCode ? ` · ${REASON_LABEL[r.reasonCode]}` : ""),
    },
    { key: "sourceRef", label: "원천", render: (r) => r.sourceRef ?? "—" },
    { key: "lineCount", label: "줄" },
    {
      key: "status",
      label: "상태",
      render: (r) =>
        r.status === "posted" ? (
          <Badge>확정</Badge>
        ) : (
          <Badge tone="warning">작성 중</Badge>
        ),
    },
    { key: "documentOn", label: "업무일" },
  ];

  const itemOf = (id: string) => items.find((i) => String(i.id) === id);
  const locationOptions = (
    <>
      <option value="">선택</option>
      {locations
        .filter((l) => l.isActive)
        .map((l) => (
          <option key={l.id} value={l.id}>
            {l.warehouseCode} {l.code}
          </option>
        ))}
    </>
  );
  function setLine(index: number, patch: Partial<Line>) {
    if (!draft) return;
    setDraft({
      ...draft,
      lines: draft.lines.map((l, i) => (i === index ? { ...l, ...patch } : l)),
    });
  }

  return (
    <div className="page-fill">
      <PageTitle
        id="W-04"
        title="재고 전표"
        subtitle="기초재고·조정·창고 간 이동을 작성하고 확정합니다. 원천 반영 전표는 읽기만 합니다"
        help="wms/w-04"
        actions={
          <label>
            전표 만들기
            <select
              value=""
              aria-label="전표 만들기"
              onChange={(e) =>
                e.target.value &&
                guard.guard(() => openNew(e.target.value as ManualType))
              }
            >
              <option value="">유형 선택</option>
              {MANUAL.map((t) => (
                <option key={t} value={t}>
                  {TYPE_LABEL[t]}
                </option>
              ))}
            </select>
          </label>
        }
      />
      <div className="filter-bar">
        <label>
          유형
          <select
            value={filter.type}
            onChange={(e) => setFilter({ ...filter, type: e.target.value })}
          >
            <option value="">전체</option>
            {(Object.keys(TYPE_LABEL) as DocumentType[]).map((t) => (
              <option key={t} value={t}>
                {TYPE_LABEL[t]}
              </option>
            ))}
          </select>
        </label>
        <label>
          상태
          <select
            value={filter.status}
            onChange={(e) => setFilter({ ...filter, status: e.target.value })}
          >
            <option value="">전체</option>
            <option value="draft">작성 중</option>
            <option value="posted">확정</option>
          </select>
        </label>
      </div>
      {notice && (
        <p role="status" className="notice">
          {notice}
        </p>
      )}
      {!editing && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={lists.error} retry={lists.reload} />
      {!lists.data ? (
        !lists.error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={shown}
              columns={columns}
              caption="재고 전표 목록"
              offset={0}
              total={shown.length}
              limit={shown.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="전표가 없습니다. 원천을 반영하거나 기초재고 전표를 만드세요."
                  action="기초재고 만들기"
                  onAction={() => guard.guard(() => openNew("OPENING"))}
                />
              }
            />
          </section>
          {detail && !editing && (
            <DetailPanel
              wide
              title={`${detail.documentNo} ${TYPE_LABEL[detail.documentType]}`}
              onClose={() => {
                setDetail(null);
                setParams({});
              }}
            >
              <p className="muted">
                업무일 {detail.documentOn}
                {detail.sourceRef && ` · 원천 ${detail.sourceRef}`}
                {detail.reversesDocumentNo &&
                  ` · 되돌린 전표 ${detail.reversesDocumentNo}`}
                {detail.reasonCode &&
                  ` · 사유 ${REASON_LABEL[detail.reasonCode]}`}
                {detail.note && ` · ${detail.note}`}
              </p>
              <div className="table-scroll">
                <table>
                  <caption>이동 줄</caption>
                  <thead>
                    <tr>
                      <th scope="col">품목</th>
                      <th scope="col">위치</th>
                      <th scope="col">LOT</th>
                      <th scope="col" className="num">
                        증감
                      </th>
                      <th scope="col">원천 수량</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detail.moves?.map((m) => (
                      <tr key={m.id}>
                        <td>{m.itemCode}</td>
                        <td>
                          {m.warehouseCode} {m.locationCode}
                        </td>
                        <td>
                          {m.lotNo ?? (m.itemClass === "FG" ? "(미지정)" : "—")}
                        </td>
                        <td className="num">
                          {signed(m.qtyDelta)} {m.unit}
                        </td>
                        <td>
                          {m.sourceQty && m.sourceUnit !== m.unit
                            ? `${num(m.sourceQty)} ${m.sourceUnit}`
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="muted">
                확정한 전표는 바꿀 수 없습니다. 수량이 틀렸으면 조정 전표로
                바로잡으세요.
              </p>
            </DetailPanel>
          )}
          {editing && draft && (
            <FormPanel
              wide
              key={editing.id ?? "new"}
              title={`${TYPE_LABEL[draft.type]} 전표 ${editing.id ? "편집" : "작성"}`}
              guard={guard}
              onClose={() => setEditing(null)}
              onSubmit={submit}
              actions={
                <>
                  <button
                    type="submit"
                    className="secondary"
                    disabled={pending}
                  >
                    임시 저장
                  </button>
                  <button
                    type="button"
                    disabled={pending}
                    aria-busy={pending}
                    onClick={() => void save(true)}
                  >
                    확정
                  </button>
                  {editing.id && (
                    <button
                      type="button"
                      className="link-button"
                      disabled={pending}
                      onClick={() =>
                        void send(`/documents/${editing.id}`, "DELETE").then(
                          (r) => r && setEditing(null),
                        )
                      }
                    >
                      삭제
                    </button>
                  )}
                  <small className="muted">확정하면 수정할 수 없습니다</small>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field-row">
                <Field
                  label="업무일"
                  type="date"
                  value={draft.documentOn}
                  error={errors.documentOn}
                  onChange={(e) =>
                    setDraft({ ...draft, documentOn: e.target.value })
                  }
                />
                {draft.type === "ADJUSTMENT" && (
                  <label className="field">
                    조정 사유
                    <select
                      value={draft.reasonCode}
                      required
                      aria-invalid={!!errors.reasonCode}
                      onChange={(e) =>
                        setDraft({
                          ...draft,
                          reasonCode: e.target.value as Reason | "",
                        })
                      }
                    >
                      <option value="">선택</option>
                      {(Object.keys(REASON_LABEL) as Reason[]).map((r) => (
                        <option key={r} value={r}>
                          {REASON_LABEL[r]}
                        </option>
                      ))}
                    </select>
                    {errors.reasonCode && (
                      <small className="field-error">{errors.reasonCode}</small>
                    )}
                  </label>
                )}
              </div>
              <div className="table-scroll section-block">
                <table>
                  <caption>
                    {draft.type === "TRANSFER"
                      ? "이동 줄 (보낼 위치 → 받을 위치)"
                      : draft.type === "ADJUSTMENT"
                        ? "조정 줄 (증감 +/−)"
                        : "기초재고 줄"}
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">품목</th>
                      <th scope="col">LOT</th>
                      {draft.type === "TRANSFER" ? (
                        <>
                          <th scope="col">보낼 위치</th>
                          <th scope="col">받을 위치</th>
                        </>
                      ) : (
                        <th scope="col">위치</th>
                      )}
                      <th scope="col">
                        {draft.type === "ADJUSTMENT" ? "증감" : "수량"}
                      </th>
                      <th scope="col">관리</th>
                    </tr>
                  </thead>
                  <tbody>
                    {draft.lines.map((line, index) => {
                      const at = `lines.${index}`;
                      const item = itemOf(line.itemId);
                      const error = (f: string) => errors[`${at}.${f}`];
                      return (
                        <tr key={index}>
                          <td>
                            <select
                              aria-label={`${index + 1}번 줄 품목`}
                              value={line.itemId}
                              aria-invalid={!!error("itemId")}
                              onChange={(e) =>
                                setLine(index, {
                                  itemId: e.target.value,
                                  lotNo: "",
                                })
                              }
                            >
                              <option value="">선택</option>
                              {items
                                .filter((i) => i.isActive)
                                .map((i) => (
                                  <option key={i.id} value={i.id}>
                                    {i.itemCode} {i.name}
                                  </option>
                                ))}
                            </select>
                            {error("itemId") && (
                              <small className="field-error">
                                {error("itemId")}
                              </small>
                            )}
                          </td>
                          <td>
                            <input
                              aria-label={`${index + 1}번 줄 LOT`}
                              value={line.lotNo}
                              maxLength={50}
                              disabled={item?.itemClass === "RAW"}
                              placeholder={
                                item?.itemClass === "RAW" ? "—" : "LOT 번호"
                              }
                              aria-invalid={!!error("lotNo")}
                              onChange={(e) =>
                                setLine(index, { lotNo: e.target.value })
                              }
                            />
                            {error("lotNo") && (
                              <small className="field-error">
                                {error("lotNo")}
                              </small>
                            )}
                          </td>
                          {draft.type === "TRANSFER" ? (
                            <>
                              <td>
                                <select
                                  aria-label={`${index + 1}번 줄 보낼 위치`}
                                  value={line.fromLocationId}
                                  aria-invalid={!!error("fromLocationId")}
                                  onChange={(e) =>
                                    setLine(index, {
                                      fromLocationId: e.target.value,
                                    })
                                  }
                                >
                                  {locationOptions}
                                </select>
                                {error("fromLocationId") && (
                                  <small className="field-error">
                                    {error("fromLocationId")}
                                  </small>
                                )}
                              </td>
                              <td>
                                <select
                                  aria-label={`${index + 1}번 줄 받을 위치`}
                                  value={line.toLocationId}
                                  aria-invalid={!!error("toLocationId")}
                                  onChange={(e) =>
                                    setLine(index, {
                                      toLocationId: e.target.value,
                                    })
                                  }
                                >
                                  {locationOptions}
                                </select>
                                {error("toLocationId") && (
                                  <small className="field-error">
                                    {error("toLocationId")}
                                  </small>
                                )}
                              </td>
                            </>
                          ) : (
                            <td>
                              <select
                                aria-label={`${index + 1}번 줄 위치`}
                                value={line.locationId}
                                aria-invalid={!!error("locationId")}
                                onChange={(e) =>
                                  setLine(index, { locationId: e.target.value })
                                }
                              >
                                {locationOptions}
                              </select>
                              {error("locationId") && (
                                <small className="field-error">
                                  {error("locationId")}
                                </small>
                              )}
                            </td>
                          )}
                          <td>
                            <input
                              aria-label={`${index + 1}번 줄 수량`}
                              inputMode="decimal"
                              value={line.qty}
                              required
                              aria-invalid={!!error("qty")}
                              onChange={(e) =>
                                setLine(index, { qty: e.target.value })
                              }
                            />
                            {item && (
                              <small className="muted"> {item.baseUnit}</small>
                            )}
                            {error("qty") && (
                              <small className="field-error">
                                {error("qty")}
                              </small>
                            )}
                          </td>
                          <td>
                            <button
                              type="button"
                              className="link-button"
                              disabled={draft.lines.length === 1}
                              onClick={() =>
                                setDraft({
                                  ...draft,
                                  lines: draft.lines.filter(
                                    (_, i) => i !== index,
                                  ),
                                })
                              }
                            >
                              삭제
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() =>
                  setDraft({
                    ...draft,
                    lines: [...draft.lines, { ...EMPTY_LINE }],
                  })
                }
              >
                줄 추가
              </button>
              <Field
                label={
                  draft.reasonCode === "OTHER"
                    ? "메모 (기타 사유 필수)"
                    : "메모"
                }
                value={draft.note}
                maxLength={300}
                error={errors.note}
                onChange={(e) => setDraft({ ...draft, note: e.target.value })}
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
