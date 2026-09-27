// W-07 품목·단위 — 목록 + 등록·수정 패널(UI-02 S 패턴, F-05 기준) + MES 품목 가져오기.
// WMS 품목은 WMS가 소유한다(FS-013 D1). 코드는 MES·ERP와 같게 두지만 연결되지 않는다. 완제품만 LOT을 추적한다(D16).
import { useState, type FormEvent } from "react";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
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
  PURPOSE_LABEL,
  useLists,
  useSend,
  WMS,
  type Item,
  type Purpose,
} from "./common";

type Draft = {
  itemCode: string;
  name: string;
  baseUnit: string;
  itemClass: Purpose;
  isActive: boolean;
};
type Candidate = {
  itemCode: string;
  name: string;
  baseUnit: string;
  itemClass: Purpose;
};
const EMPTY: Draft = {
  itemCode: "",
  name: "",
  baseUnit: "EA",
  itemClass: "RAW",
  isActive: true,
};

export function Items() {
  const { data, error, reload } = useLists<[Item[]]>(["/items"]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [panel, setPanel] = useState<
    { kind: "item"; id: number | null } | { kind: "import" } | null
  >(null);
  const [draft, setDraft] = useState<Draft>(EMPTY);
  const [initial, setInitial] = useState<Draft>(EMPTY);
  const [conversion, setConversion] = useState({ fromUnit: "", factor: "" });
  const [candidates, setCandidates] = useState<Candidate[]>();
  const [picked, setPicked] = useState<string[]>([]);
  const [importError, setImportError] = useState<unknown>();
  const guard = useDiscardGuard(
    panel?.kind === "item" && JSON.stringify(draft) !== JSON.stringify(initial),
  );
  if (moduleOff(error)) return <ModuleOff />;
  const rows = data?.[0];
  const errors = fieldErrors(saveError);
  const editing =
    panel?.kind === "item" && panel.id
      ? rows?.find((r) => r.id === panel.id)
      : undefined;
  const mesOff =
    importError instanceof ApiError &&
    importError.error.details?.reason === "SOURCE_MODULE_DISABLED";

  function open(row: Item | null) {
    const values = row
      ? {
          itemCode: row.itemCode,
          name: row.name,
          baseUnit: row.baseUnit,
          itemClass: row.itemClass,
          isActive: row.isActive,
        }
      : EMPTY;
    setPanel({ kind: "item", id: row?.id ?? null });
    setDraft(values);
    setInitial(values);
    setConversion({ fromUnit: "", factor: "" });
    setError(undefined);
  }
  async function openImport() {
    setPanel({ kind: "import" });
    setCandidates(undefined);
    setPicked([]);
    setImportError(undefined);
    try {
      const r = await api<Candidate[]>(`${WMS}/lookups/mes-items`);
      setCandidates(r.data);
      setPicked(r.data.map((c) => c.itemCode));
    } catch (e) {
      setImportError(e);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (panel?.kind === "import") {
      if (await send("/items/import", "POST", { itemCodes: picked }))
        setPanel(null);
      return;
    }
    const saved = editing
      ? await send(`/items/${editing.id}`, "PATCH", {
          name: draft.name,
          isActive: draft.isActive,
        })
      : await send("/items", "POST", {
          itemCode: draft.itemCode.trim().toUpperCase(),
          name: draft.name,
          baseUnit: draft.baseUnit.trim(),
          itemClass: draft.itemClass,
        });
    if (saved) setPanel(null);
  }

  const columns: Column<Item>[] = [
    { key: "itemCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={editing?.id === r.id}
          onClick={() => guard.guard(() => open(r))}
        >
          수정
        </button>
      ),
    },
    { key: "name", label: "이름" },
    {
      key: "itemClass",
      label: "분류",
      render: (r) => PURPOSE_LABEL[r.itemClass],
    },
    { key: "baseUnit", label: "기본 단위" },
    {
      key: "lotTracked",
      label: "LOT 추적",
      render: (r) => (r.lotTracked ? "추적" : "—"),
    },
    {
      key: "conversions",
      label: "환산",
      render: (r) =>
        r.conversions.length
          ? r.conversions
              .map((c) => `1 ${c.fromUnit} = ${num(c.factor, 6)} ${r.baseUnit}`)
              .join(" · ")
          : "—",
    },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? (
          <Badge>사용</Badge>
        ) : (
          <Badge tone="warning">사용 안 함</Badge>
        ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="W-07"
        title="품목·단위"
        subtitle="재고로 관리할 원자재·완제품과 단위 환산입니다"
        help="wms/w-07"
        actions={
          <>
            <button
              type="button"
              className="secondary"
              aria-pressed={panel?.kind === "import"}
              onClick={() => guard.guard(() => void openImport())}
            >
              MES 품목 가져오기
            </button>
            <button
              type="button"
              aria-pressed={panel?.kind === "item" && !panel.id}
              onClick={() => guard.guard(() => open(null))}
            >
              품목 등록
            </button>
          </>
        }
      />
      <p className="muted" role="note">
        품목 코드는 MES·ERP와 같게 두면 원천을 반영할 수 있습니다. 코드가 같을
        뿐 세 시스템의 품목은 연결되지 않습니다.
      </p>
      {!panel && <ErrorNotice error={saveError} />}
      <ErrorNotice error={error} retry={reload} />
      {!rows ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={rows}
              columns={columns}
              caption="품목 목록"
              offset={0}
              total={rows.length}
              limit={rows.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="품목이 없습니다. MES 품목을 가져오거나 직접 등록하세요."
                  action="MES 품목 가져오기"
                  onAction={() => void openImport()}
                />
              }
            />
          </section>
          {panel?.kind === "import" && (
            <FormPanel
              title="MES 품목 가져오기"
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button
                    type="submit"
                    disabled={pending || !picked.length}
                    aria-busy={pending}
                  >
                    {picked.length}개 가져오기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => setPanel(null)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <ErrorNotice error={saveError} />
              {mesOff ? (
                <p className="notice" role="note">
                  MES를 사용하지 않도록 설정했습니다. 품목을 직접 등록하세요.
                </p>
              ) : (
                <ErrorNotice error={importError} />
              )}
              {!candidates ? (
                !importError && <Loading />
              ) : candidates.length ? (
                <>
                  <p className="muted">
                    MES 원자재·완제품 중 WMS에 없는 품목입니다. 반제품은 공정
                    안에서만 쓰여 가져오지 않습니다.
                  </p>
                  {candidates.map((c) => (
                    <label key={c.itemCode} className="inline-check">
                      <input
                        type="checkbox"
                        checked={picked.includes(c.itemCode)}
                        onChange={(e) =>
                          setPicked(
                            e.target.checked
                              ? [...picked, c.itemCode]
                              : picked.filter((p) => p !== c.itemCode),
                          )
                        }
                      />
                      {c.itemCode} {c.name} · {PURPOSE_LABEL[c.itemClass]} ·{" "}
                      {c.baseUnit}
                    </label>
                  ))}
                </>
              ) : (
                <p className="muted">
                  가져올 품목이 없습니다. 모두 등록되어 있습니다.
                </p>
              )}
            </FormPanel>
          )}
          {panel?.kind === "item" && (
            <FormPanel
              key={panel.id ?? "new"}
              title={editing ? `${editing.itemCode} 수정` : "품목 등록"}
              guard={guard}
              onClose={() => setPanel(null)}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing ? "저장" : "등록"}
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
              <Field
                label="품목 코드"
                value={draft.itemCode}
                required
                disabled={!!editing}
                maxLength={40}
                error={errors.itemCode}
                onChange={(e) =>
                  setDraft({ ...draft, itemCode: e.target.value.toUpperCase() })
                }
              />
              <Field
                label="이름"
                value={draft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) => setDraft({ ...draft, name: e.target.value })}
              />
              <div className="field">
                <label htmlFor="wms-item-class">분류</label>
                <select
                  id="wms-item-class"
                  value={draft.itemClass}
                  disabled={!!editing}
                  onChange={(e) =>
                    setDraft({ ...draft, itemClass: e.target.value as Purpose })
                  }
                >
                  <option value="RAW">원자재 (품목 수량)</option>
                  <option value="FG">완제품 (LOT 추적)</option>
                </select>
              </div>
              <Field
                label="기본 단위"
                value={draft.baseUnit}
                required
                disabled={!!editing}
                maxLength={10}
                error={errors.baseUnit}
                onChange={(e) =>
                  setDraft({ ...draft, baseUnit: e.target.value })
                }
              />
              {editing && (
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={draft.isActive}
                    onChange={(e) =>
                      setDraft({ ...draft, isActive: e.target.checked })
                    }
                  />
                  사용
                </label>
              )}
              {editing && (
                <section className="section-block" aria-label="단위 환산">
                  <h3>단위 환산</h3>
                  {editing.conversions.length ? (
                    <ul className="rank-list">
                      {editing.conversions.map((c) => (
                        <li key={c.id}>
                          <span>
                            1 {c.fromUnit} = {num(c.factor, 6)}{" "}
                            {editing.baseUnit}
                          </span>
                          <button
                            type="button"
                            className="link-button"
                            disabled={pending}
                            onClick={() =>
                              void send(
                                `/items/${editing.id}/conversions/${c.id}`,
                                "DELETE",
                              )
                            }
                          >
                            삭제
                          </button>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="muted">환산이 없습니다.</p>
                  )}
                  <div className="field-row">
                    <Field
                      label="환산 단위"
                      value={conversion.fromUnit}
                      maxLength={10}
                      error={errors.fromUnit}
                      onChange={(e) =>
                        setConversion({
                          ...conversion,
                          fromUnit: e.target.value,
                        })
                      }
                    />
                    <Field
                      label={`계수 (${editing.baseUnit})`}
                      inputMode="decimal"
                      value={conversion.factor}
                      error={errors.factor}
                      onChange={(e) =>
                        setConversion({ ...conversion, factor: e.target.value })
                      }
                    />
                  </div>
                  <button
                    type="button"
                    className="secondary"
                    disabled={
                      pending || !conversion.fromUnit || !conversion.factor
                    }
                    onClick={() =>
                      void send(`/items/${editing.id}/conversions`, "POST", {
                        fromUnit: conversion.fromUnit.trim(),
                        factor: conversion.factor.trim(),
                      }).then(
                        (r) => r && setConversion({ fromUnit: "", factor: "" }),
                      )
                    }
                  >
                    환산 추가
                  </button>
                </section>
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
