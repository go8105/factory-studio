// M-12 품목 — MES 전용 품목과 단위 환산(마스터-디테일) (FS-020a)
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
  conversions: Conversion[];
};
type ItemDraft = Omit<Item, "id" | "conversions">;

const UNITS = ["EA", "BOX", "KG", "M", "L", "SET"];
const TYPES = {
  finished: "완제품",
  semi_finished: "반제품",
  raw: "원자재",
  auxiliary: "부자재",
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
  const [editing, setEditing] = useState<Item | null>(null);
  const [draft, setDraft] = useState<ItemDraft>();
  const [selectedId, setSelectedId] = useState<number>();
  const [editingConv, setEditingConv] = useState<Conversion | null>(null);
  const [conv, setConv] = useState({ fromUnit: "BOX", factor: "" });

  if (moduleOff(error)) return <ModuleOff />;
  const items = data?.[0];
  const selected = items?.find((i) => i.id === selectedId);
  const d: ItemDraft = draft ?? {
    itemCode: "",
    name: "",
    baseUnit: "EA",
    itemType: "finished",
    isActive: true,
  };
  const errors = fieldErrors(saveError);

  function edit(row: Item | null) {
    setEditing(row);
    setDraft(
      row
        ? {
            itemCode: row.itemCode,
            name: row.name,
            baseUnit: row.baseUnit,
            itemType: row.itemType,
            isActive: row.isActive,
          }
        : undefined,
    );
    setError(undefined);
  }
  function editConv(row: Conversion | null) {
    setEditingConv(row);
    setConv(
      row
        ? { fromUnit: row.fromUnit, factor: row.factor }
        : { fromUnit: "BOX", factor: "" },
    );
    setError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const clean = {
      ...d,
      itemCode: d.itemCode.trim().toUpperCase(),
      name: d.name.trim(),
    };
    const body = editing ? changed(clean, editing) : clean;
    if (editing && !Object.keys(body).length) return;
    const saved = await send<Item>(
      editing ? `/items/${editing.id}` : "/items",
      editing ? "PATCH" : "POST",
      body,
    );
    if (saved) {
      edit(null);
      if (!editing) setSelectedId(saved.id);
    }
  }

  async function submitConv(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const clean = {
      fromUnit: conv.fromUnit.trim().toUpperCase(),
      factor: conv.factor.trim(),
    };
    const body = editingConv ? changed(clean, editingConv) : clean;
    if (editingConv && !Object.keys(body).length) return;
    const path = `/items/${selected.id}/conversions`;
    const ok = await send(
      editingConv ? `${path}/${editingConv.id}` : path,
      editingConv ? "PATCH" : "POST",
      body,
    );
    if (ok) editConv(null);
  }

  const columns: Column<Item>[] = [
    { key: "itemCode", label: "코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => {
              setSelectedId(r.id);
              editConv(null);
            }}
          >
            환산 {r.conversions.length}
          </button>
          <button type="button" className="link-button" onClick={() => edit(r)}>
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
            onClick={() => editConv(r)}
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
    <>
      <PageTitle
        id="M-12"
        title="품목"
        subtitle="생산하는 제품과 투입하는 자재, 단위 환산을 관리합니다"
        help="mes/m-12"
      />
      <MesOrder />
      <p className="notice" role="note">
        이 품목은 MES 전용입니다. ERP 품목과 코드가 같아도 별개 데이터입니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!items ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
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
                    reason="등록된 품목이 없습니다. 우측 폼에서 첫 품목을 등록하세요."
                    to="#item-form"
                    action="품목 등록"
                  />
                }
              />
            </section>
            <form
              id="item-form"
              className="panel"
              aria-label={editing ? "품목 수정" : "품목 등록"}
              onSubmit={(e) => void submit(e)}
            >
              <h2>{editing ? `${editing.itemCode} 수정` : "품목 등록"}</h2>
              <Field
                label="품목 코드"
                value={d.itemCode}
                required
                maxLength={40}
                pattern="[A-Z][A-Z0-9_\-]{1,39}"
                title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                error={errors.itemCode}
                onChange={(e) =>
                  setDraft({ ...d, itemCode: e.target.value.toUpperCase() })
                }
              />
              <Field
                label="품목명"
                value={d.name}
                required
                maxLength={100}
                error={errors.name}
                onChange={(e) => setDraft({ ...d, name: e.target.value })}
              />
              <div className="field">
                <label htmlFor="item-type">유형</label>
                <select
                  id="item-type"
                  value={d.itemType}
                  onChange={(e) =>
                    setDraft({
                      ...d,
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
                  value={d.baseUnit}
                  onChange={(e) => setDraft({ ...d, baseUnit: e.target.value })}
                >
                  {UNITS.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
              {editing && (
                <p className="muted">
                  단위 환산이나 작업지시가 있으면 기준 단위를 바꿀 수 없습니다.
                </p>
              )}
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={d.isActive}
                  onChange={(e) =>
                    setDraft({ ...d, isActive: e.target.checked })
                  }
                />
                사용
              </label>
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  {editing ? "저장" : "등록"}
                </button>
                {editing && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => edit(null)}
                  >
                    취소
                  </button>
                )}
              </div>
            </form>
          </div>

          {selected ? (
            <div className="master-grid">
              <section>
                <h2>
                  {selected.itemCode} {selected.name} 단위 환산
                </h2>
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
                      to="#conversion-form"
                      action="환산 등록"
                    />
                  }
                />
              </section>
              <form
                id="conversion-form"
                className="panel"
                aria-label={editingConv ? "환산 수정" : "환산 등록"}
                onSubmit={(e) => void submitConv(e)}
              >
                <h2>{editingConv ? "환산 수정" : "환산 등록"}</h2>
                <Field
                  label="환산 전 단위"
                  value={conv.fromUnit}
                  required
                  maxLength={10}
                  error={errors.fromUnit}
                  onChange={(e) =>
                    setConv({ ...conv, fromUnit: e.target.value.toUpperCase() })
                  }
                />
                <Field
                  label={`환산 계수 (1 ${conv.fromUnit || "단위"} = ? ${selected.baseUnit})`}
                  value={conv.factor}
                  required
                  inputMode="decimal"
                  title="0보다 큰 수, 소수 6자리까지"
                  error={errors.factor}
                  onChange={(e) => setConv({ ...conv, factor: e.target.value })}
                />
                <div className="form-actions">
                  <button type="submit" disabled={pending}>
                    {editingConv ? "저장" : "등록"}
                  </button>
                  {editingConv && (
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => editConv(null)}
                    >
                      취소
                    </button>
                  )}
                </div>
              </form>
            </div>
          ) : (
            <p className="muted">
              품목 목록에서 &quot;환산&quot;을 누르면 그 품목의 단위 환산을
              관리할 수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
