// Q-02 검사 기준 — 버전 목록 → 항목 상세(DetailPanel wide) → 항목 폼(FormPanel, 닫으면 항목 상세로). UI-03 P 패턴(F-12).
// 게시한 기준은 불변이다. 바꾸려면 개정(새 초안). 품목은 MES 조회로 고르고, MES를 끄면 코드를 직접 입력한다.
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
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
  limitText,
  ModuleOff,
  moduleOff,
  QMS,
  AQLS,
  SPEC_KIND,
  SpecBadge,
  time,
  useSend,
  type Spec,
  type SpecItem,
  type SpecKind,
} from "./common";

type MesItem = { itemCode: string; name: string; baseUnit: string };
type Create = {
  itemCode: string;
  itemName: string;
  note: string;
  inspectionKind: SpecKind;
  aql: string;
};
type ItemDraft = {
  name: string;
  method: SpecItem["method"];
  lowerLimit: string;
  upperLimit: string;
  unit: string;
  isRequired: boolean;
};
const EMPTY_CREATE: Create = {
  itemCode: "",
  itemName: "",
  note: "",
  inspectionKind: "OUTGOING",
  aql: "",
};
const EMPTY_ITEM: ItemDraft = {
  name: "",
  method: "RANGE",
  lowerLimit: "",
  upperLimit: "",
  unit: "",
  isRequired: true,
};

function toPayload(item: SpecItem | ItemDraft) {
  const range = item.method === "RANGE";
  const blank = (v: string | null) =>
    v === null || String(v).trim() === "" ? null : String(v).trim();
  return {
    name: item.name.trim(),
    method: item.method,
    lowerLimit: range ? blank(item.lowerLimit) : null,
    upperLimit: range ? blank(item.upperLimit) : null,
    unit: range ? blank(item.unit) : null,
    isRequired: item.isRequired,
  };
}

export function Specs() {
  const { fail } = useSession();
  const [rows, setRows] = useState<Spec[]>();
  const [error, setError] = useState<unknown>();
  const [reload, setReload] = useState(0);
  const [panel, setPanel] = useState<
    | { kind: "create" }
    | { kind: "items"; id: number }
    | { kind: "item"; id: number; index: number | null }
    | null
  >(null);
  const [spec, setSpec] = useState<Spec>();
  const [mesItems, setMesItems] = useState<MesItem[] | null>();
  const [create, setCreate] = useState<Create>(EMPTY_CREATE);
  const [item, setItem] = useState<ItemDraft>(EMPTY_ITEM);
  const [itemInitial, setItemInitial] = useState<ItemDraft>(EMPTY_ITEM);
  const {
    send,
    pending,
    error: saveError,
    setError: setSaveError,
    deleteButtons,
  } = useSend(() => setReload((n) => n + 1));
  const dirty =
    (panel?.kind === "create" &&
      JSON.stringify(create) !== JSON.stringify(EMPTY_CREATE)) ||
    (panel?.kind === "item" &&
      JSON.stringify(item) !== JSON.stringify(itemInitial));
  const guard = useDiscardGuard(dirty);

  useEffect(() => {
    const controller = new AbortController();
    api<Spec[]>(`${QMS}/inspection-specs`, { signal: controller.signal })
      .then((r) => !controller.signal.aborted && setRows(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [reload]);

  if (moduleOff(error)) return <ModuleOff />;
  const errors = fieldErrors(saveError);

  async function openItems(id: number) {
    setSaveError(undefined);
    const r = await api<Spec>(`${QMS}/inspection-specs/${id}`);
    setSpec(r.data);
    setPanel({ kind: "items", id });
  }
  async function openCreate() {
    setCreate(EMPTY_CREATE);
    setSaveError(undefined);
    setPanel({ kind: "create" });
    try {
      const r = await api<MesItem[]>(`${QMS}/lookups/mes-items`);
      setMesItems(r.data);
    } catch {
      setMesItems(null); // MES 꺼짐 → 직접 입력
    }
  }
  function openItem(index: number | null) {
    const current = index === null ? null : spec!.items![index];
    const values: ItemDraft = current
      ? {
          name: current.name,
          method: current.method,
          lowerLimit:
            current.lowerLimit === null
              ? ""
              : String(Number(current.lowerLimit)),
          upperLimit:
            current.upperLimit === null
              ? ""
              : String(Number(current.upperLimit)),
          unit: current.unit ?? "",
          isRequired: current.isRequired,
        }
      : EMPTY_ITEM;
    setItem(values);
    setItemInitial(values);
    setSaveError(undefined);
    setPanel({ kind: "item", id: spec!.id, index });
  }
  async function saveItems(items: (SpecItem | ItemDraft)[]) {
    const saved = await send<Spec>(`/inspection-specs/${spec!.id}`, "PATCH", {
      items: items.map(toPayload),
    });
    if (saved) {
      setSpec(saved);
      setPanel({ kind: "items", id: saved.id });
    }
  }
  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    const saved = await send<Spec>("/inspection-specs", "POST", {
      itemCode: create.itemCode.trim().toUpperCase(),
      itemName: create.itemName.trim(),
      note: create.note.trim() || null,
      inspectionKind: create.inspectionKind,
      aql: create.aql || null,
    });
    if (saved) {
      setSpec(saved);
      setPanel({ kind: "items", id: saved.id });
    }
  }
  async function submitItem(event: FormEvent) {
    event.preventDefault();
    if (!spec || panel?.kind !== "item") return;
    const items = [...(spec.items ?? [])];
    if (panel.index === null) items.push(item as unknown as SpecItem);
    else items[panel.index] = item as unknown as SpecItem;
    await saveItems(items);
  }
  async function act(row: Spec, action: "publish" | "retire" | "revise") {
    const saved = await send<Spec>(
      `/inspection-specs/${row.id}/${action}`,
      "POST",
    );
    if (saved && action === "revise") void openItems(saved.id);
    else if (saved && spec?.id === row.id) setSpec(saved);
  }

  const columns: Column<Spec>[] = [
    {
      key: "itemCode",
      label: "품목",
      render: (r) => `${r.itemCode} ${r.itemName}`,
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={spec?.id === r.id && panel !== null}
            onClick={() => guard.guard(() => void openItems(r.id))}
          >
            항목 {r.itemCount}
          </button>
          {r.status === "draft" && (
            <button
              type="button"
              className="link-button"
              disabled={pending}
              onClick={() => void act(r, "publish")}
            >
              게시
            </button>
          )}
          {r.status !== "draft" && (
            <button
              type="button"
              className="link-button"
              disabled={pending}
              onClick={() => guard.guard(() => void act(r, "revise"))}
            >
              개정
            </button>
          )}
          {r.status === "published" && (
            <button
              type="button"
              className="link-button"
              disabled={pending}
              onClick={() => void act(r, "retire")}
            >
              폐기
            </button>
          )}
          {r.status === "draft" &&
            deleteButtons(`s:${r.id}`, `/inspection-specs/${r.id}`)}
        </span>
      ),
    },
    { key: "versionNo", label: "버전", render: (r) => `v${r.versionNo}` },
    {
      key: "status",
      label: "상태",
      render: (r) => <SpecBadge status={r.status} />,
    },
    { key: "inspectionCount", label: "검사" },
    {
      key: "publishedAt",
      label: "게시",
      render: (r) => (r.publishedAt ? time(r.publishedAt) : "—"),
    },
  ];

  const editable = spec?.status === "draft";
  return (
    <div className="page-fill">
      <PageTitle
        id="Q-02"
        title="검사 기준"
        subtitle="품목별 출하 전 검사 항목과 합격 한계를 버전으로 관리합니다"
        help="qms/q-02"
        actions={
          <button
            type="button"
            aria-pressed={panel?.kind === "create"}
            onClick={() => guard.guard(() => void openCreate())}
          >
            기준 만들기
          </button>
        }
      />
      <p className="muted" role="note">
        게시한 기준은 바꿀 수 없습니다. 바꾸려면 개정하세요. 검사는 만들 때의
        게시 기준을 그대로 씁니다.{" "}
        <strong>품목·검사 종류당 게시 기준이 1개</strong>
        이며, 새 버전을 게시하면 같은 종류의 이전 버전만 폐기됩니다. 반품·초품
        검사는 출하 기준을 씁니다.
      </p>
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={() => setReload((n) => n + 1)} />
      {!rows ? (
        !error && <Loading delay={300} />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="검사 기준 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="검사 기준이 없습니다. 품목별 기준을 게시해야 검사를 시작할 수 있습니다."
                  action="기준 만들기"
                  onAction={() => guard.guard(() => void openCreate())}
                />
              }
            />
          </section>

          {panel?.kind === "create" && (
            <FormPanel
              title="검사 기준 만들기"
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submitCreate(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => setPanel(null))}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              {mesItems ? (
                <div className="field">
                  <label htmlFor="spec-item">품목 (MES 조회)</label>
                  <select
                    id="spec-item"
                    value={create.itemCode}
                    required
                    aria-invalid={!!errors.itemCode}
                    onChange={(e) => {
                      const picked = mesItems.find(
                        (i) => i.itemCode === e.target.value,
                      );
                      setCreate({
                        ...create,
                        itemCode: e.target.value,
                        itemName: picked?.name ?? "",
                      });
                    }}
                  >
                    <option value="">선택</option>
                    {mesItems.map((i) => (
                      <option key={i.itemCode} value={i.itemCode}>
                        {i.itemCode} {i.name}
                      </option>
                    ))}
                  </select>
                  {errors.itemCode && <small>{errors.itemCode}</small>}
                </div>
              ) : (
                <>
                  {mesItems === null && (
                    <p className="muted" role="note">
                      MES를 사용하지 않아 품목을 직접 입력합니다.
                    </p>
                  )}
                  <div className="field-row">
                    <Field
                      label="품목 코드"
                      value={create.itemCode}
                      required
                      maxLength={40}
                      error={errors.itemCode}
                      onChange={(e) =>
                        setCreate({
                          ...create,
                          itemCode: e.target.value.toUpperCase(),
                        })
                      }
                    />
                    <Field
                      label="품목명"
                      value={create.itemName}
                      required
                      maxLength={100}
                      error={errors.itemName}
                      onChange={(e) =>
                        setCreate({ ...create, itemName: e.target.value })
                      }
                    />
                  </div>
                </>
              )}
              <div className="field">
                <label htmlFor="spec-kind">검사 종류</label>
                <select
                  id="spec-kind"
                  value={create.inspectionKind}
                  onChange={(e) =>
                    setCreate({
                      ...create,
                      inspectionKind: e.target.value as SpecKind,
                    })
                  }
                >
                  {(Object.keys(SPEC_KIND) as SpecKind[]).map((k) => (
                    <option key={k} value={k}>
                      {SPEC_KIND[k]}
                    </option>
                  ))}
                </select>
                <small>
                  품목·종류당 게시본 1개입니다.{" "}
                  <strong>반품·초품 검사는 출하 기준을 씁니다.</strong>
                </small>
              </div>
              <div className="field">
                <label htmlFor="spec-aql">AQL (선택)</label>
                <select
                  id="spec-aql"
                  value={create.aql}
                  onChange={(e) =>
                    setCreate({ ...create, aql: e.target.value })
                  }
                >
                  <option value="">없음 (시료 수 직접 입력)</option>
                  {AQLS.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
                <small>
                  AQL을 정하면 로트 크기에 맞는 시료 수와 합격 판정 개수를 표가
                  정합니다(KS Q ISO 2859-1, 일반 검사 수준 II).
                </small>
              </div>
              <Field
                label="메모"
                value={create.note}
                maxLength={300}
                onChange={(e) => setCreate({ ...create, note: e.target.value })}
              />
            </FormPanel>
          )}

          {panel?.kind === "items" && spec && (
            <DetailPanel
              wide
              key={`items-${spec.id}`}
              title={`${spec.itemCode} v${spec.versionNo} 검사 항목`}
              onClose={() => setPanel(null)}
              actions={
                editable && (
                  <button type="button" onClick={() => openItem(null)}>
                    항목 추가
                  </button>
                )
              }
            >
              <ErrorNotice error={saveError} />
              <p>
                <SpecBadge status={spec.status} /> {spec.itemName}
                {spec.note && ` · ${spec.note}`}
              </p>
              {!editable && (
                <p className="muted">
                  게시·폐기한 기준은 바꿀 수 없습니다. 바꾸려면 목록에서
                  개정하세요.
                </p>
              )}
              <DataTable
                rows={(spec.items ?? []).map((i, index) => ({
                  ...i,
                  id: index + 1,
                }))}
                columns={[
                  { key: "seq", label: "순서" },
                  {
                    key: "id",
                    label: "관리",
                    render: (r) =>
                      editable ? (
                        <span className="row-actions">
                          <button
                            type="button"
                            className="link-button"
                            onClick={() => openItem(r.id - 1)}
                          >
                            수정
                          </button>
                          <button
                            type="button"
                            className="link-button"
                            disabled={pending}
                            onClick={() =>
                              void saveItems(
                                (spec.items ?? []).filter(
                                  (_, i) => i !== r.id - 1,
                                ),
                              )
                            }
                          >
                            빼기
                          </button>
                        </span>
                      ) : (
                        "—"
                      ),
                  },
                  { key: "name", label: "항목" },
                  { key: "method", label: "기준", render: (r) => limitText(r) },
                  {
                    key: "isRequired",
                    label: "필수",
                    render: (r) => (r.isRequired ? "필수" : "선택"),
                  },
                ]}
                caption={`${spec.itemCode} v${spec.versionNo} 항목`}
                offset={0}
                total={spec.items?.length ?? 0}
                limit={spec.items?.length || 1}
                onPage={() => undefined}
                empty={
                  editable ? (
                    <EmptyState
                      reason="항목이 없습니다. 게시하려면 항목이 1개 이상 필요합니다."
                      action="항목 추가"
                      onAction={() => openItem(null)}
                    />
                  ) : (
                    <p className="muted">항목이 없습니다.</p>
                  )
                }
              />
            </DetailPanel>
          )}

          {panel?.kind === "item" && spec && (
            <FormPanel
              key={`item-${spec.id}-${panel.index ?? "new"}`}
              title={`${spec.itemCode} v${spec.versionNo} · ${panel.index === null ? "항목 추가" : "항목 수정"}`}
              guard={guard}
              onClose={() => setPanel({ kind: "items", id: spec.id })}
              onSubmit={(e) => void submitItem(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    저장
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      guard.guard(() =>
                        setPanel({ kind: "items", id: spec.id }),
                      )
                    }
                  >
                    항목 목록으로
                  </button>
                </>
              }
            >
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <Field
                label="항목명"
                value={item.name}
                required
                maxLength={100}
                onChange={(e) => setItem({ ...item, name: e.target.value })}
              />
              <div className="field">
                <label htmlFor="item-method">판정 방식</label>
                <select
                  id="item-method"
                  value={item.method}
                  onChange={(e) =>
                    setItem({
                      ...item,
                      method: e.target.value as ItemDraft["method"],
                    })
                  }
                >
                  <option value="RANGE">
                    수치 범위 (하한 ≤ 측정값 ≤ 상한)
                  </option>
                  <option value="PASS_FAIL">합·부 (작업자 판정)</option>
                </select>
              </div>
              {item.method === "RANGE" && (
                <>
                  <div className="field-row">
                    <Field
                      label="하한"
                      inputMode="decimal"
                      value={item.lowerLimit}
                      error={
                        Object.entries(errors).find(([k]) =>
                          k.endsWith(".lowerLimit"),
                        )?.[1]
                      }
                      onChange={(e) =>
                        setItem({ ...item, lowerLimit: e.target.value })
                      }
                    />
                    <Field
                      label="상한"
                      inputMode="decimal"
                      value={item.upperLimit}
                      error={
                        Object.entries(errors).find(([k]) =>
                          k.endsWith(".upperLimit"),
                        )?.[1]
                      }
                      onChange={(e) =>
                        setItem({ ...item, upperLimit: e.target.value })
                      }
                    />
                  </div>
                  <Field
                    label="단위"
                    value={item.unit}
                    maxLength={10}
                    error={
                      Object.entries(errors).find(([k]) =>
                        k.endsWith(".unit"),
                      )?.[1]
                    }
                    onChange={(e) => setItem({ ...item, unit: e.target.value })}
                  />
                  <p className="muted">
                    하한이나 상한 중 하나만 넣어도 됩니다(예: 절연 저항 ≥ 100).
                  </p>
                </>
              )}
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={item.isRequired}
                  onChange={(e) =>
                    setItem({ ...item, isRequired: e.target.checked })
                  }
                />
                필수 항목 (확정 전에 반드시 입력)
              </label>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
