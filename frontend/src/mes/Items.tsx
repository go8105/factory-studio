// M-12 품목 — MES 전용 품목과 단위 환산(마스터-디테일) (FS-020a)
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
  useDiscardGuard,
  type Column,
} from "../shared/components";
import {
  changed,
  fieldErrors,
  MesOrder,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
} from "./common";

type Conversion = {
  id: number;
  itemId: number;
  fromUnit: string;
  toUnit: string;
  factor: string;
};
export type Item = {
  id: number;
  itemCode: string;
  name: string;
  baseUnit: string;
  itemType: "finished" | "semi_finished" | "raw" | "auxiliary";
  isActive: boolean;
  // F12 상세 · F13 관리 · F17 포장 (모두 선택)
  spec: string | null;
  drawingNo: string | null;
  revision: string | null;
  itemGroup: string | null;
  material: string | null;
  color: string | null;
  unitWeightKg: string | null;
  customerPartNo: string | null;
  lotTracked: boolean;
  shelfLifeDays: number | null;
  inspectionRequired: boolean;
  defaultWarehouseCode: string | null;
  barcodeEnabled: boolean;
  boxQty: string | null;
  boxesPerPallet: number | null;
  conversions: Conversion[];
};
type ItemDraft = Omit<Item, "id" | "conversions">;
type ConvDraft = { fromUnit: string; factor: string };

type Panel =
  { type: "item"; row: Item | null } | { type: "conv"; row: Conversion | null };

const UNITS = ["EA", "BOX", "KG", "M", "L", "SET"];
// 상세 탭의 글자 칸: [키, 라벨, 최대 길이]
const TEXTS = {
  detail: [
    ["spec", "규격", 100],
    ["drawingNo", "도면 번호", 40],
    ["revision", "리비전", 10],
    ["itemGroup", "품목 그룹", 40],
    ["material", "재질", 60],
    ["color", "색상", 30],
    ["unitWeightKg", "단위 중량(kg)", 13],
    ["customerPartNo", "고객 품번", 40],
  ],
} as const satisfies {
  detail: readonly (readonly [keyof ItemDraft, string, number])[];
};
const TYPES = {
  finished: "완제품",
  semi_finished: "반제품",
  raw: "원자재",
  auxiliary: "부자재",
};

const EMPTY_ITEM: ItemDraft = {
  itemCode: "",
  name: "",
  baseUnit: "EA",
  itemType: "finished",
  isActive: true,
  spec: null,
  drawingNo: null,
  revision: null,
  itemGroup: null,
  material: null,
  color: null,
  unitWeightKg: null,
  customerPartNo: null,
  lotTracked: true,
  shelfLifeDays: null,
  inspectionRequired: false,
  defaultWarehouseCode: null,
  barcodeEnabled: true,
  boxQty: null,
  boxesPerPallet: null,
};

const EMPTY_CONV: ConvDraft = {
  fromUnit: "BOX",
  factor: "",
};

export function Items() {
  const { data, error, reload } = useLists<[Item[]]>(["/items"]);
  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(reload);

  const [panel, setPanel] = useState<Panel | null>(null);
  const [selectedId, setSelectedId] = useState<number>();
  const [itemDraft, setItemDraft] = useState<ItemDraft>(EMPTY_ITEM);
  const [itemInitial, setItemInitial] = useState<ItemDraft>(EMPTY_ITEM);
  const [convDraft, setConvDraft] = useState<ConvDraft>(EMPTY_CONV);
  const [convInitial, setConvInitial] = useState<ConvDraft>(EMPTY_CONV);

  const itemDirty =
    panel?.type === "item" &&
    (panel.row
      ? (Object.keys(itemDraft) as (keyof ItemDraft)[]).some(
          (k) => itemDraft[k] !== itemInitial[k],
        )
      : Boolean(itemDraft.itemCode.trim() || itemDraft.name.trim()));

  const convDirty =
    panel?.type === "conv" &&
    (panel.row
      ? convDraft.fromUnit !== convInitial.fromUnit ||
        convDraft.factor !== convInitial.factor
      : Boolean(convDraft.factor.trim()));

  const guard = useDiscardGuard(itemDirty || convDirty);

  if (moduleOff(error)) return <ModuleOff />;
  const items = data?.[0];
  const selected = items?.find((i) => i.id === selectedId);

  const errors = fieldErrors(saveError);

  function openItemPanel(row: Item | null) {
    // id·환산은 입력값이 아니다. 나머지 칸은 그대로 가져온다.
    const values: ItemDraft = row
      ? (Object.fromEntries(
          Object.keys(EMPTY_ITEM).map((key) => [
            key,
            row[key as keyof ItemDraft],
          ]),
        ) as ItemDraft)
      : EMPTY_ITEM;
    setPanel({ type: "item", row });
    setItemDraft(values);
    setItemInitial(values);
    setError(undefined);
  }

  function openConvPanel(row: Conversion | null) {
    const values: ConvDraft = row
      ? { fromUnit: row.fromUnit, factor: row.factor }
      : EMPTY_CONV;
    setPanel({ type: "conv", row });
    setConvDraft(values);
    setConvInitial(values);
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
    setError(undefined);
  }

  async function submitItem(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "item") return;
    const editing = panel.row;
    const clean = {
      ...itemDraft,
      itemCode: itemDraft.itemCode.trim().toUpperCase(),
      name: itemDraft.name.trim(),
    };
    const body = editing ? changed(clean, editing) : clean;
    if (editing && !Object.keys(body).length) return;
    const saved = await send<Item>(
      editing ? `/items/${editing.id}` : "/items",
      editing ? "PATCH" : "POST",
      body,
    );
    if (saved) {
      closePanel();
      if (!editing) setSelectedId(saved.id);
    }
  }

  async function submitConv(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "conv" || !selected) return;
    const editingConv = panel.row;
    const clean = {
      fromUnit: convDraft.fromUnit.trim().toUpperCase(),
      factor: convDraft.factor.trim(),
    };
    const body = editingConv ? changed(clean, editingConv) : clean;
    if (editingConv && !Object.keys(body).length) return;
    const path = `/items/${selected.id}/conversions`;
    const ok = await send(
      editingConv ? `${path}/${editingConv.id}` : path,
      editingConv ? "PATCH" : "POST",
      body,
    );
    if (ok) closePanel();
  }

  const columns: Column<Item>[] = [
    { key: "itemCode", label: "코드" },
    { key: "itemGroup", label: "품목 그룹", render: (r) => r.itemGroup ?? "—" },
    { key: "spec", label: "규격", render: (r) => r.spec ?? "—" },
    {
      key: "boxQty",
      label: "포장",
      render: (r) =>
        r.boxQty
          ? `박스 ${r.boxQty}${r.boxesPerPallet ? ` · 팔레트 ${r.boxesPerPallet}박스` : ""}`
          : "—",
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            // 환산 목록만 보여 준다. 등록은 목록 머리의 "환산 등록"으로 연다
            // (겹침 화면에서 자동으로 열린 패널이 방금 고른 목록을 가리지 않게).
            onClick={() =>
              guard.guard(() => {
                setSelectedId(r.id);
                if (panel?.type === "conv") closePanel();
              })
            }
          >
            환산 {r.conversions.length}
          </button>
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.type === "item" && panel.row?.id === r.id}
            onClick={() => guard.guard(() => openItemPanel(r))}
          >
            수정
          </button>
          {deleteButtons(`item:${r.id}`, `/items/${r.id}`)}
        </span>
      ),
    },
    { key: "name", label: "품목명" },
    { key: "itemType", label: "유형", render: (r) => TYPES[r.itemType] },
    { key: "baseUnit", label: "기준 단위" },
    {
      key: "isActive",
      label: "사용",
      render: (r) =>
        r.isActive ? "사용" : <Badge tone="warning">사용 안 함</Badge>,
    },
  ];

  const convColumns: Column<Conversion>[] = [
    {
      key: "fromUnit",
      label: "환산",
      render: (r) =>
        `1 ${r.fromUnit} = ${Number(r.factor).toLocaleString()} ${r.toUnit}`,
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={panel?.type === "conv" && panel.row?.id === r.id}
            onClick={() => guard.guard(() => openConvPanel(r))}
          >
            수정
          </button>
          {deleteButtons(
            `conv:${r.id}`,
            `/items/${r.itemId}/conversions/${r.id}`,
          )}
        </span>
      ),
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="M-12"
        title="품목"
        subtitle="생산하는 제품과 투입하는 자재, 단위 환산을 관리합니다"
        help="mes/m-12"
        actions={
          <button
            type="button"
            aria-pressed={panel?.type === "item" && !panel.row}
            onClick={() => guard.guard(() => openItemPanel(null))}
          >
            품목 등록
          </button>
        }
      />
      <MesOrder />
      <p className="notice" role="note">
        이 품목은 MES 전용입니다. ERP 품목과 코드가 같아도 별개 데이터입니다.
      </p>
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!items ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <DataTable
                rows={items}
                columns={columns}
                caption="품목 목록"
                offset={0}
                total={items.length}
                limit={items.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 품목이 없습니다. 첫 품목을 등록하세요."
                    action="품목 등록"
                    onAction={() => guard.guard(() => openItemPanel(null))}
                  />
                }
              />
            </div>
            {selected ? (
              <div className="section-block">
                <div className="section-heading">
                  <h2>
                    {selected.itemCode} {selected.name} 단위 환산
                  </h2>
                  <button
                    type="button"
                    className="secondary"
                    aria-pressed={panel?.type === "conv" && !panel.row}
                    onClick={() => guard.guard(() => openConvPanel(null))}
                  >
                    환산 등록
                  </button>
                </div>
                <DataTable
                  rows={selected.conversions}
                  columns={convColumns}
                  caption={`${selected.itemCode} 단위 환산 목록`}
                  offset={0}
                  total={selected.conversions.length}
                  limit={selected.conversions.length || 1}
                  onPage={() => undefined}
                  empty={
                    <EmptyState
                      reason={`단위 환산이 없습니다. 모든 수량은 기준 단위(${selected.baseUnit})로 다룹니다.`}
                      action="환산 등록"
                      onAction={() => guard.guard(() => openConvPanel(null))}
                    />
                  }
                />
              </div>
            ) : (
              <p className="muted" role="note">
                품목 목록에서 &quot;환산&quot;을 누르면 그 품목의 단위 환산을
                관리할 수 있습니다.
              </p>
            )}
          </section>
          {panel?.type === "item" && (
            <FormPanel
              key={panel.row?.id ?? "new-item"}
              title={panel.row ? `${panel.row.itemCode} 수정` : "품목 등록"}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitItem(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {panel.row ? "저장" : "등록"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closePanel)}
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
                value={itemDraft.itemCode}
                required
                maxLength={40}
                pattern="[A-Z][A-Z0-9_\-]{1,39}"
                title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                error={errors.itemCode}
                onChange={(e) =>
                  setItemDraft({
                    ...itemDraft,
                    itemCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label="품목명"
                value={itemDraft.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) =>
                  setItemDraft({ ...itemDraft, name: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="item-type">유형</label>
                <select
                  id="item-type"
                  value={itemDraft.itemType}
                  onChange={(e) =>
                    setItemDraft({
                      ...itemDraft,
                      itemType: e.target.value as Item["itemType"],
                    })
                  }
                >
                  {Object.entries(TYPES).map(([k, v]) => (
                    <option key={k} value={k}>
                      {v}
                    </option>
                  ))}
                </select>
              </div>
              <div className="field">
                <label htmlFor="item-unit">기준 단위</label>
                <select
                  id="item-unit"
                  value={itemDraft.baseUnit}
                  onChange={(e) =>
                    setItemDraft({ ...itemDraft, baseUnit: e.target.value })
                  }
                >
                  {UNITS.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
              {panel.row && (
                <p className="muted">
                  단위 환산이나 작업지시가 있으면 기준 단위를 바꿀 수 없습니다.
                </p>
              )}
              <details className="field-group">
                <summary>상세 (도면·재질·중량)</summary>
                {TEXTS.detail.map(([key, label, max]) => (
                  <Field
                    key={key}
                    label={label}
                    value={itemDraft[key] ?? ""}
                    maxLength={max}
                    error={errors[key]}
                    onChange={(e) =>
                      setItemDraft({
                        ...itemDraft,
                        [key]: e.target.value || null,
                      })
                    }
                  />
                ))}
              </details>
              <details className="field-group">
                <summary>관리 (LOT·유통기한·검사)</summary>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={itemDraft.lotTracked}
                    onChange={(e) =>
                      setItemDraft({
                        ...itemDraft,
                        lotTracked: e.target.checked,
                      })
                    }
                  />
                  LOT 추적
                </label>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={itemDraft.inspectionRequired}
                    onChange={(e) =>
                      setItemDraft({
                        ...itemDraft,
                        inspectionRequired: e.target.checked,
                      })
                    }
                  />
                  입고 검사 대상
                </label>
                <label className="inline-check">
                  <input
                    type="checkbox"
                    checked={itemDraft.barcodeEnabled}
                    onChange={(e) =>
                      setItemDraft({
                        ...itemDraft,
                        barcodeEnabled: e.target.checked,
                      })
                    }
                  />
                  바코드 사용
                </label>
                <Field
                  label="유통기한(일)"
                  type="number"
                  min={1}
                  max={36500}
                  value={itemDraft.shelfLifeDays ?? ""}
                  error={errors.shelfLifeDays}
                  onChange={(e) =>
                    setItemDraft({
                      ...itemDraft,
                      shelfLifeDays: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                />
                <Field
                  label="기본 창고 코드"
                  value={itemDraft.defaultWarehouseCode ?? ""}
                  maxLength={30}
                  error={errors.defaultWarehouseCode}
                  onChange={(e) =>
                    setItemDraft({
                      ...itemDraft,
                      defaultWarehouseCode: e.target.value || null,
                    })
                  }
                />
              </details>
              <details className="field-group">
                <summary>포장 (박스 입수·팔레트)</summary>
                <Field
                  label="박스 입수"
                  value={itemDraft.boxQty ?? ""}
                  maxLength={19}
                  error={errors.boxQty}
                  onChange={(e) =>
                    setItemDraft({
                      ...itemDraft,
                      boxQty: e.target.value || null,
                    })
                  }
                />
                <Field
                  label="팔레트당 박스 수"
                  type="number"
                  min={1}
                  max={9999}
                  value={itemDraft.boxesPerPallet ?? ""}
                  error={errors.boxesPerPallet}
                  onChange={(e) =>
                    setItemDraft({
                      ...itemDraft,
                      boxesPerPallet: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                />
                <p className="muted">
                  패킹은 박스 수량이 박스 입수 이하일 때만 닫습니다. 기준이
                  없으면 검사하지 않습니다.
                </p>
              </details>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={itemDraft.isActive}
                  onChange={(e) =>
                    setItemDraft({ ...itemDraft, isActive: e.target.checked })
                  }
                />
                사용
              </label>
            </FormPanel>
          )}
          {panel?.type === "conv" && selected && (
            <FormPanel
              key={panel.row?.id ?? "new-conv"}
              title={panel.row ? "환산 수정" : "환산 등록"}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitConv(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {panel.row ? "저장" : "등록"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closePanel)}
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
                label="환산 전 단위"
                value={convDraft.fromUnit}
                required
                maxLength={10}
                error={errors.fromUnit}
                onChange={(e) =>
                  setConvDraft({
                    ...convDraft,
                    fromUnit: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label={`환산 계수 (1 ${convDraft.fromUnit || "단위"} = ? ${selected.baseUnit})`}
                value={convDraft.factor}
                required
                inputMode="decimal"
                title="0보다 큰 수, 소수 6자리까지"
                error={errors.factor}
                onChange={(e) =>
                  setConvDraft({ ...convDraft, factor: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
