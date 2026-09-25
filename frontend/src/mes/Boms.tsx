// M-15 BOM — 품목 1개를 만드는 데 드는 자재(1단계 전개)의 버전 관리 (FS-020b)
import { useState, type FormEvent } from "react";
import {
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
  MesOrder,
  ModuleOff,
  moduleOff,
  StatusBadge,
  useLists,
  useSend,
  versionButtons,
  type VersionStatus,
} from "./common";

type Line = {
  id: number;
  lineNo: number;
  materialItemId: number;
  qtyPerUnit: string;
  unit: string;
  lossRate: string;
};
export type Bom = {
  id: number;
  bomCode: string;
  itemId: number;
  versionNo: number;
  status: VersionStatus;
  lines: Line[];
};
type Item = {
  id: number;
  itemCode: string;
  name: string;
  baseUnit: string;
  itemType: string;
  conversions: { fromUnit: string }[];
};
type DraftLine = Omit<Line, "id" | "lineNo">;

const toDraft = (lines: Line[]): DraftLine[] =>
  lines.map(({ materialItemId, qtyPerUnit, unit, lossRate }) => ({
    materialItemId,
    qtyPerUnit: String(Number(qtyPerUnit)),
    unit,
    lossRate: String(Number(lossRate)),
  }));

export function Boms() {
  const { data, error, reload } = useLists<[Bom[], Item[]]>([
    "/boms",
    "/items",
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
  const [create, setCreate] = useState({ itemId: 0, bomCode: "" });
  const [revising, setRevising] = useState<{ id: number; bomCode: string }>();

  if (moduleOff(error)) return <ModuleOff />;
  const [boms, items] = data ?? [undefined, []];
  const selected = boms?.find((b) => b.id === selectedId);
  const draft = lines ?? toDraft(selected?.lines ?? []);
  const errors = fieldErrors(saveError);
  const item = (id: number) => items.find((i) => i.id === id);
  const itemLabel = (id: number) => {
    const i = item(id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };
  const units = (id: number) => {
    const i = item(id);
    return i ? [i.baseUnit, ...i.conversions.map((c) => c.fromUnit)] : [];
  };
  const materials = items.filter((i) => i.id !== selected?.itemId);

  function select(id: number | undefined) {
    setSelectedId(id);
    setLines(undefined);
    setRevising(undefined);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Bom>("/boms", "POST", {
      itemId: create.itemId || items[0]?.id,
      bomCode: create.bomCode.trim().toUpperCase(),
    });
    if (created) {
      setCreate({ itemId: 0, bomCode: "" });
      select(created.id);
    }
  }

  async function submitRevise(event: FormEvent) {
    event.preventDefault();
    if (pending || !revising) return;
    const created = await send<Bom>(`/boms/${revising.id}/revise`, "POST", {
      bomCode: revising.bomCode.trim().toUpperCase(),
    });
    if (created) select(created.id);
  }

  function setLine(index: number, patch: Partial<DraftLine>) {
    setLines(draft.map((l, i) => (i === index ? { ...l, ...patch } : l)));
  }

  async function saveLines() {
    if (!selected || pending) return;
    const saved = await send(`/boms/${selected.id}/lines`, "PUT", {
      lines: draft.map((l) => ({
        ...l,
        qtyPerUnit: l.qtyPerUnit.trim(),
        lossRate: l.lossRate.trim() || "0",
      })),
    });
    if (saved) setLines(undefined);
  }

  const columns: Column<Bom>[] = [
    { key: "bomCode", label: "BOM 코드" },
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
            자재 {r.lines.length}
          </button>
          {versionButtons(r, "/boms", send, deleteButtons, () => {
            select(r.id);
            setRevising({
              id: r.id,
              bomCode: `${r.bomCode.replace(/-V\d+$/, "")}-V${r.versionNo + 1}`,
            });
          })}
        </span>
      ),
    },
    { key: "versionNo", label: "버전", render: (r) => `v${r.versionNo}` },
    {
      key: "status",
      label: "상태",
      render: (r) => <StatusBadge status={r.status} />,
    },
    { key: "itemId", label: "만들 품목", render: (r) => itemLabel(r.itemId) },
  ];

  const editable = selected?.status === "draft";
  const lineRows = draft.map((l, index) => ({ id: index, ...l }));
  const lineColumns: Column<(typeof lineRows)[number]>[] = [
    {
      key: "materialItemId",
      label: "자재",
      render: (r) =>
        editable ? (
          <select
            aria-label={`${r.id + 1}번째 자재`}
            value={r.materialItemId}
            onChange={(e) => {
              const id = Number(e.target.value);
              setLine(r.id, {
                materialItemId: id,
                unit: item(id)?.baseUnit ?? "",
              });
            }}
          >
            {materials.map((m) => (
              <option key={m.id} value={m.id}>
                {m.itemCode} {m.name}
              </option>
            ))}
          </select>
        ) : (
          itemLabel(r.materialItemId)
        ),
    },
    {
      key: "qtyPerUnit",
      label: "소요량(1개당)",
      render: (r) =>
        editable ? (
          <input
            aria-label={`${r.id + 1}번째 소요량`}
            inputMode="decimal"
            value={r.qtyPerUnit}
            onChange={(e) => setLine(r.id, { qtyPerUnit: e.target.value })}
          />
        ) : (
          r.qtyPerUnit
        ),
    },
    {
      key: "unit",
      label: "단위",
      render: (r) =>
        editable ? (
          <select
            aria-label={`${r.id + 1}번째 단위`}
            value={r.unit}
            onChange={(e) => setLine(r.id, { unit: e.target.value })}
          >
            {units(r.materialItemId).map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
        ) : (
          r.unit
        ),
    },
    {
      key: "lossRate",
      label: "손실률(%)",
      render: (r) =>
        editable ? (
          <input
            aria-label={`${r.id + 1}번째 손실률`}
            inputMode="decimal"
            value={r.lossRate}
            onChange={(e) => setLine(r.id, { lossRate: e.target.value })}
          />
        ) : (
          r.lossRate
        ),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        editable ? (
          <button
            type="button"
            className="link-button"
            aria-label={`${r.id + 1}번째 자재 빼기`}
            onClick={() => setLines(draft.filter((_, i) => i !== r.id))}
          >
            빼기
          </button>
        ) : (
          "-"
        ),
    },
  ];
  const dirty =
    lines !== undefined &&
    JSON.stringify(lines) !== JSON.stringify(toDraft(selected?.lines ?? []));

  return (
    <>
      <PageTitle
        id="M-15"
        title="BOM"
        subtitle="품목 1개를 만드는 데 드는 자재와 수량을 버전으로 관리합니다"
        help="mes/m-15"
      />
      <MesOrder />
      <p className="muted">
        1단계 전개만 다룹니다. 게시된 BOM만 작업지시에 적용되고, 게시·폐기된
        버전은 바꿀 수 없어 개정해서 새 버전(새 BOM 코드)으로 편집합니다. 자재
        투입은 기록만 하고 재고를 차감하지 않습니다(재고는 WMS 소유).
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!boms ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={boms}
                columns={columns}
                caption="BOM 목록"
                offset={0}
                total={boms.length}
                limit={boms.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 BOM이 없습니다. 우측 폼에서 첫 BOM을 만드세요."
                    to="#bom-form"
                    action="BOM 만들기"
                  />
                }
              />
            </section>
            {revising ? (
              <form
                className="panel"
                aria-label="BOM 개정"
                onSubmit={(e) => void submitRevise(e)}
              >
                <h2>개정</h2>
                <p className="muted">
                  현재 구성을 복사해 다음 버전 초안을 만듭니다. BOM 코드는
                  버전마다 달라야 합니다.
                </p>
                <Field
                  label="새 BOM 코드"
                  value={revising.bomCode}
                  required
                  maxLength={40}
                  error={errors.bomCode}
                  onChange={(e) =>
                    setRevising({
                      ...revising,
                      bomCode: e.target.value.toUpperCase(),
                    })
                  }
                />
                <div className="form-actions">
                  <button type="submit" disabled={pending}>
                    개정
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setRevising(undefined)}
                  >
                    취소
                  </button>
                </div>
              </form>
            ) : (
              <form
                id="bom-form"
                className="panel"
                aria-label="BOM 만들기"
                onSubmit={(e) => void submitCreate(e)}
              >
                <h2>새 BOM</h2>
                <div className="field">
                  <label htmlFor="bom-item">만들 품목</label>
                  <select
                    id="bom-item"
                    value={create.itemId || items[0]?.id || ""}
                    onChange={(e) =>
                      setCreate({ ...create, itemId: Number(e.target.value) })
                    }
                  >
                    {items.map((i) => (
                      <option key={i.id} value={i.id}>
                        {i.itemCode} {i.name}
                      </option>
                    ))}
                  </select>
                  {errors.itemId && <small>{errors.itemId}</small>}
                </div>
                <Field
                  label="BOM 코드"
                  value={create.bomCode}
                  required
                  maxLength={40}
                  pattern="[A-Z][A-Z0-9_\-]{1,39}"
                  title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                  placeholder="예: BOM-C400"
                  error={errors.bomCode}
                  onChange={(e) =>
                    setCreate({
                      ...create,
                      bomCode: e.target.value.toUpperCase(),
                    })
                  }
                />
                <div className="form-actions">
                  <button type="submit" disabled={pending}>
                    만들기
                  </button>
                </div>
              </form>
            )}
          </div>

          {selected ? (
            <section className="panel" aria-label="구성 자재">
              <h2>
                {selected.bomCode} v{selected.versionNo} 구성 자재{" "}
                <StatusBadge status={selected.status} />
              </h2>
              <p className="muted">
                만들 품목: {itemLabel(selected.itemId)}
                {!editable &&
                  " · 게시·폐기된 버전은 바꿀 수 없습니다. 바꾸려면 개정하세요."}
              </p>
              <DataTable
                rows={lineRows}
                columns={lineColumns}
                caption={`${selected.bomCode} 구성 자재`}
                offset={0}
                total={lineRows.length}
                limit={lineRows.length || 1}
                onPage={() => undefined}
                empty={
                  <p className="muted">
                    자재가 없습니다. 자재가 없는 BOM은 게시할 수 없습니다.
                  </p>
                }
              />
              {errors.lines && <p className="notice">{errors.lines}</p>}
              {editable && (
                <div className="form-actions">
                  <button
                    type="button"
                    className="secondary"
                    disabled={materials.length === 0}
                    onClick={() =>
                      setLines([
                        ...draft,
                        {
                          materialItemId: materials[0].id,
                          qtyPerUnit: "1",
                          unit: materials[0].baseUnit,
                          lossRate: "0",
                        },
                      ])
                    }
                  >
                    자재 추가
                  </button>
                  <button
                    type="button"
                    disabled={pending || !dirty}
                    onClick={() => void saveLines()}
                  >
                    구성 저장
                  </button>
                </div>
              )}
            </section>
          ) : (
            <p className="muted">
              목록에서 &quot;자재&quot;를 누르면 그 버전의 구성을 보고, 초안이면
              편집할 수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
