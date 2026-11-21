// 머리글 + 명세 + 작성/확정/취소가 같은 모양인 문서 화면(E-20·E-22·E-23·E-24) 한 틀.
// 화면마다 다른 것은 입력 칸·명세 칸·단추뿐이라 설정으로 받는다.
import { useState, type FormEvent, type ReactNode } from "react";
import {
  Badge,
  DataTable,
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
  ModuleOff,
  moduleOff,
  PARTNERS,
  useLists,
  useSend,
  type Item,
  type Partner,
} from "./common";

export type DocLine = {
  id: number;
  lineNo: number;
  itemId: number;
  itemCode: string;
  itemName: string;
  quantity: string;
  unit: string;
};
export type Doc = {
  id: number;
  status: "draft" | "confirmed" | "ordered" | "closed" | "cancelled";
  cancelReason: string | null;
  lines: DocLine[];
  [key: string]: unknown;
};
export type DraftLine = { itemId: number; quantity: string };
/** 입력 칸이 고르는 목록 한 줄(코드·이름을 가진 기준정보). */
export type Row = { id: number; code?: string; name?: string } & Record<
  string,
  unknown
>;

export const STATUS: Record<string, { label: string; tone: string }> = {
  draft: { label: "작성 중", tone: "normal" },
  confirmed: { label: "확정", tone: "normal" },
  ordered: { label: "발주 완료", tone: "normal" },
  closed: { label: "종결", tone: "normal" },
  cancelled: { label: "취소", tone: "warning" },
};

export function StatusBadge({ status }: { status: string }) {
  const state = STATUS[status] ?? { label: status, tone: "normal" };
  return <Badge tone={state.tone as never}>{state.label}</Badge>;
}

export function DocumentScreen<T extends Doc>({
  id,
  title,
  path,
  note,
  columns,
  blank,
  form,
  lineItems,
  extraActions,
  detail,
  extraPaths = [],
}: {
  id: string;
  title: string;
  path: string;
  note: string;
  columns: (name: ReturnType<typeof labelsOf>) => Column<T>[];
  blank: Record<string, unknown>;
  form: (
    draft: Record<string, unknown>,
    set: (patch: Record<string, unknown>) => void,
    lists: { partners: Partner[]; items: Item[]; extras: Row[][] },
    errors: Record<string, string>,
  ) => ReactNode;
  /** 명세에 고를 수 있는 품목. 비우면 모든 사용 중 품목. */
  lineItems?: (items: Item[]) => Item[];
  extraActions?: (doc: T, send: Sender, extras: Row[][]) => ReactNode;
  detail?: (doc: T) => ReactNode;
  /** 입력 칸이 고를 목록(부서·프로젝트·요청 등). form의 넷째 인자로 들어온다. */
  extraPaths?: string[];
}) {
  const { data, error, reload } = useLists<unknown[][]>([
    path,
    PARTNERS,
    ITEMS,
    ...extraPaths,
  ]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);
  const [selectedId, setSelectedId] = useState<number>();
  const [creating, setCreating] = useState(false);
  const [draft, setDraft] = useState(blank);
  const [lines, setLines] = useState<DraftLine[]>([]);
  const [cancelReason, setCancelReason] = useState("");

  const [docs, partners, allItems, ...extras] = (data ?? [
    undefined,
    [],
    [],
  ]) as [T[] | undefined, Partner[], Item[], ...Row[][]];
  const items = (lineItems ? lineItems(allItems) : allItems).filter(
    (i) => i.isActive,
  );
  const errors = fieldErrors(saveError);
  const selected = docs?.find((d) => d.id === selectedId);
  const dirty = creating || lines.length > 0;
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;

  async function create(event: FormEvent) {
    event.preventDefault();
    const made = await send<{ id: number }>(path, "POST", draft);
    if (made?.id) {
      setCreating(false);
      setDraft(blank);
      setSelectedId(made.id);
    }
  }

  async function saveLines(doc: T) {
    const body = { lines: lines.filter((l) => l.itemId && l.quantity) };
    if (await send(`${path}/${doc.id}/lines`, "PUT", body)) setLines([]);
  }

  const name = labelsOf(partners, allItems);
  return (
    <div className="page-fill">
      <PageTitle
        id={id}
        title={title}
        help={`erp/${id.toLowerCase()}`}
        actions={
          <button
            type="button"
            aria-pressed={creating}
            onClick={() => guard.guard(() => setCreating((v) => !v))}
          >
            {title} 등록
          </button>
        }
      />
      <p className="muted" role="note">
        {note}
      </p>
      <ErrorNotice error={error} retry={reload} />
      <ErrorNotice error={saveError} />
      {!docs ? (
        <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={docs}
              columns={[
                ...columns(name),
                {
                  key: "status",
                  label: "상태",
                  render: (d) => <StatusBadge status={d.status} />,
                },
                {
                  key: "id",
                  label: "관리",
                  render: (d) => (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setSelectedId(d.id)}
                    >
                      열기
                    </button>
                  ),
                },
              ]}
              caption={title}
              offset={0}
              total={docs.length}
              limit={docs.length || 1}
              onPage={() => undefined}
              empty="등록된 문서가 없습니다."
            />
            {selected && (
              <section className="section-block">
                <div className="section-heading">
                  <h2>명세</h2>
                  <StatusBadge status={selected.status} />
                </div>
                {detail?.(selected)}
                <DataTable
                  rows={selected.lines}
                  columns={[
                    { key: "lineNo", label: "순서", render: (l) => l.lineNo },
                    {
                      key: "itemCode",
                      label: "품목",
                      render: (l) => `${l.itemCode} ${l.itemName}`,
                    },
                    {
                      key: "quantity",
                      label: "수량",
                      render: (l) =>
                        `${Number(l.quantity).toLocaleString()} ${l.unit}`,
                    },
                  ]}
                  caption="명세"
                  offset={0}
                  total={selected.lines.length}
                  limit={selected.lines.length || 1}
                  onPage={() => undefined}
                  empty="명세가 없습니다."
                />
                {selected.status === "draft" && (
                  <div className="section-block">
                    <h3>명세 편집</h3>
                    {lines.map((line, index) => (
                      <div className="field-row" key={index}>
                        <select
                          aria-label={`${index + 1}번째 품목`}
                          value={line.itemId || ""}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? { ...l, itemId: Number(e.target.value) }
                                  : l,
                              ),
                            )
                          }
                        >
                          <option value="">품목 선택</option>
                          {items.map((i) => (
                            <option key={i.id} value={i.id}>
                              {i.itemCode} {i.name}
                            </option>
                          ))}
                        </select>
                        <Field
                          label={`${index + 1}번째 수량`}
                          value={line.quantity}
                          onChange={(e) =>
                            setLines(
                              lines.map((l, i) =>
                                i === index
                                  ? { ...l, quantity: e.target.value }
                                  : l,
                              ),
                            )
                          }
                        />
                        <button
                          type="button"
                          className="link-button"
                          onClick={() =>
                            setLines(lines.filter((_, i) => i !== index))
                          }
                        >
                          줄 삭제
                        </button>
                      </div>
                    ))}
                    {errors.lines && <small role="alert">{errors.lines}</small>}
                    <button
                      type="button"
                      onClick={() =>
                        setLines([...lines, { itemId: 0, quantity: "" }])
                      }
                    >
                      줄 추가
                    </button>
                    <button
                      type="button"
                      disabled={pending || !lines.length}
                      onClick={() => void saveLines(selected)}
                    >
                      명세 저장
                    </button>
                  </div>
                )}
                <div className="row-actions">
                  {selected.status === "draft" && (
                    <>
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() =>
                          void send(`${path}/${selected.id}/confirm`, "POST")
                        }
                      >
                        확정
                      </button>
                      {deleteButtons(
                        String(selected.id),
                        `${path}/${selected.id}`,
                      )}
                    </>
                  )}
                  {extraActions?.(selected, send, extras)}
                  {selected.status !== "cancelled" && (
                    <>
                      <Field
                        label="취소 사유"
                        value={cancelReason}
                        onChange={(e) => setCancelReason(e.target.value)}
                      />
                      <button
                        type="button"
                        className="secondary"
                        disabled={pending || cancelReason.trim().length < 1}
                        onClick={() =>
                          void send(`${path}/${selected.id}/cancel`, "POST", {
                            reason: cancelReason,
                          })
                        }
                      >
                        취소
                      </button>
                    </>
                  )}
                  {selected.cancelReason && (
                    <p role="note">취소 사유: {selected.cancelReason}</p>
                  )}
                </div>
              </section>
            )}
          </section>
          {creating && (
            <FormPanel
              title={`${title} 등록`}
              guard={guard}
              onClose={() => setCreating(false)}
              onSubmit={(e) => void create(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    등록
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setCreating(false))}
                  >
                    닫기
                  </button>
                </>
              }
            >
              <ErrorNotice error={saveError} />
              <fieldset className="field" disabled={pending}>
                {form(
                  draft,
                  (patch) => {
                    setDraft({ ...draft, ...patch });
                    setError(undefined);
                  },
                  { partners, items: allItems, extras },
                  errors,
                )}
              </fieldset>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}

export type Sender = ReturnType<typeof useSend>["send"];

export function labelsOf(partners: Partner[], items: Item[]) {
  return {
    partner: (id: number) => {
      const p = partners.find((x) => x.id === id);
      return p ? `${p.partnerCode} ${p.partnerName}` : String(id);
    },
    item: (id: number) => {
      const i = items.find((x) => x.id === id);
      return i ? `${i.itemCode} ${i.name}` : String(id);
    },
  };
}
