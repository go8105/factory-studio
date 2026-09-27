// M-15 BOM — 품목 1개를 만드는 데 드는 자재(1단계 전개)의 버전 관리 (FS-020b)
import { useState, type FormEvent } from "react";
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

  const [panel, setPanel] = useState<
    | { kind: "create" }
    | { kind: "revise"; row: Bom }
    | { kind: "lines"; bomId: number }
    | { kind: "line"; bomId: number; lineIndex: number | null }
    | null
  >(null);

  const [create, setCreate] = useState({ itemId: 0, bomCode: "" });
  const [initialCreate, setInitialCreate] = useState({
    itemId: 0,
    bomCode: "",
  });
  const [revise, setRevise] = useState({ id: 0, bomCode: "" });
  const [initialRevise, setInitialRevise] = useState({ id: 0, bomCode: "" });

  const [lineDraft, setLineDraft] = useState<DraftLine>({
    materialItemId: 0,
    qtyPerUnit: "1",
    unit: "",
    lossRate: "0",
  });
  const [initialLineDraft, setInitialLineDraft] = useState<DraftLine>({
    materialItemId: 0,
    qtyPerUnit: "1",
    unit: "",
    lossRate: "0",
  });

  if (moduleOff(error)) return <ModuleOff />;
  const [boms, items] = data ?? [undefined, []];

  const selectedId = panel && "bomId" in panel ? panel.bomId : undefined;
  const selected = boms?.find((b) => b.id === selectedId);
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

  const dirty =
    (panel?.kind === "create" &&
      JSON.stringify(create) !== JSON.stringify(initialCreate)) ||
    (panel?.kind === "revise" &&
      JSON.stringify(revise) !== JSON.stringify(initialRevise)) ||
    (panel?.kind === "line" &&
      JSON.stringify(lineDraft) !== JSON.stringify(initialLineDraft));
  const guard = useDiscardGuard(dirty);

  function openCreate() {
    const initial = { itemId: items[0]?.id ?? 0, bomCode: "" };
    setCreate(initial);
    setInitialCreate(initial);
    setPanel({ kind: "create" });
    setError(undefined);
  }

  function openRevise(row: Bom) {
    const defaultCode = `${row.bomCode.replace(/-V\d+$/, "")}-V${row.versionNo + 1}`;
    const initial = { id: row.id, bomCode: defaultCode };
    setRevise(initial);
    setInitialRevise(initial);
    setPanel({ kind: "revise", row });
    setError(undefined);
  }

  function openLines(bomId: number) {
    setPanel({ kind: "lines", bomId });
    setError(undefined);
  }

  function openLineForm(bomId: number, lineIndex: number | null) {
    const targetBom = boms?.find((b) => b.id === bomId);
    const targetMaterials = items.filter((i) => i.id !== targetBom?.itemId);
    let initial: DraftLine;
    if (lineIndex !== null && targetBom && targetBom.lines[lineIndex]) {
      const target = targetBom.lines[lineIndex];
      initial = {
        materialItemId: target.materialItemId,
        qtyPerUnit: String(Number(target.qtyPerUnit)),
        unit: target.unit,
        lossRate: String(Number(target.lossRate)),
      };
    } else {
      const defaultMaterial = targetMaterials[0];
      initial = {
        materialItemId: defaultMaterial?.id ?? 0,
        qtyPerUnit: "1",
        unit: defaultMaterial?.baseUnit ?? "",
        lossRate: "0",
      };
    }
    setLineDraft(initial);
    setInitialLineDraft(initial);
    setPanel({ kind: "line", bomId, lineIndex });
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
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
      openLines(created.id);
    }
  }

  async function submitRevise(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.kind !== "revise") return;
    const created = await send<Bom>(`/boms/${revise.id}/revise`, "POST", {
      bomCode: revise.bomCode.trim().toUpperCase(),
    });
    if (created) {
      openLines(created.id);
    }
  }

  async function publish(row: Bom) {
    await send<Bom>(`/boms/${row.id}/publish`, "POST");
  }

  async function submitLine(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const currentLines = toDraft(selected.lines);
    const updatedLine: DraftLine = {
      ...lineDraft,
      qtyPerUnit: lineDraft.qtyPerUnit.trim(),
      lossRate: lineDraft.lossRate.trim() || "0",
    };
    let nextLines: DraftLine[];
    if (panel?.kind === "line" && panel.lineIndex !== null) {
      nextLines = currentLines.map((l, idx) =>
        idx === panel.lineIndex ? updatedLine : l,
      );
    } else {
      nextLines = [...currentLines, updatedLine];
    }
    const saved = await send<Bom>(`/boms/${selected.id}/lines`, "PUT", {
      lines: nextLines,
    });
    if (saved) {
      openLines(selected.id);
    }
  }

  async function removeLine(index: number) {
    if (!selected || pending) return;
    const currentLines = toDraft(selected.lines);
    const nextLines = currentLines.filter((_, i) => i !== index);
    await send<Bom>(`/boms/${selected.id}/lines`, "PUT", {
      lines: nextLines,
    });
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
            onClick={() => guard.guard(() => openLines(r.id))}
          >
            자재 {r.lines.length}
          </button>
          {versionButtons(r, "/boms", send, deleteButtons, () => openRevise(r))}
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
  const lineRows = (selected?.lines ?? []).map((l, index) => ({
    ...l,
    index,
  }));
  const lineColumns: Column<(typeof lineRows)[number]>[] = [
    {
      key: "materialItemId",
      label: "자재",
      render: (r) => itemLabel(r.materialItemId),
    },
    {
      key: "qtyPerUnit",
      label: "소요량(1개당)",
      render: (r) => r.qtyPerUnit,
    },
    {
      key: "unit",
      label: "단위",
      render: (r) => r.unit,
    },
    {
      key: "lossRate",
      label: "손실률(%)",
      render: (r) => r.lossRate,
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        editable ? (
          <span className="row-actions">
            <button
              type="button"
              className="link-button"
              onClick={() => openLineForm(selected!.id, r.index)}
            >
              수정
            </button>
            <button
              type="button"
              className="link-button"
              aria-label={`${r.index + 1}번째 자재 빼기`}
              onClick={() => void removeLine(r.index)}
            >
              빼기
            </button>
          </span>
        ) : (
          "-"
        ),
    },
  ];

  const formError = Object.keys(errors).length ? undefined : saveError;

  return (
    <div className="page-fill">
      <PageTitle
        id="M-15"
        title="BOM"
        subtitle="품목 1개를 만드는 데 드는 자재와 수량을 버전으로 관리합니다"
        help="mes/m-15"
        actions={
          <button type="button" onClick={() => guard.guard(openCreate)}>
            새 BOM
          </button>
        }
      />
      <MesOrder />
      <p className="muted">
        1단계 전개만 다룹니다. 게시된 BOM만 작업지시에 적용되고, 게시·폐기된
        버전은 바꿀 수 없어 개정해서 새 버전(새 BOM 코드)으로 편집합니다. 자재
        투입은 기록만 하고 재고를 차감하지 않습니다(재고는 WMS 소유).
      </p>
      {!panel && <ErrorNotice error={formError} />}
      <ErrorNotice error={error} retry={reload} />
      {!boms ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
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
                  reason="등록된 BOM이 없습니다. 첫 BOM을 만드세요."
                  action="새 BOM"
                  onAction={() => guard.guard(openCreate)}
                />
              }
            />
          </section>

          {panel?.kind === "create" && (
            <FormPanel
              key="bom-create"
              title="새 BOM"
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitCreate(e)}
              actions={
                <>
                  <button type="submit" disabled={pending}>
                    만들기
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
              <ErrorNotice error={formError} />
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
            </FormPanel>
          )}

          {panel?.kind === "revise" && (
            <FormPanel
              key="bom-revise"
              title="BOM 개정"
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitRevise(e)}
              actions={
                <>
                  <button type="submit" disabled={pending}>
                    개정
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
              <ErrorNotice error={formError} />
              <p className="muted">
                현재 구성을 복사해 다음 버전 초안을 만듭니다. BOM 코드는
                버전마다 달라야 합니다.
              </p>
              <Field
                label="새 BOM 코드"
                value={revise.bomCode}
                required
                maxLength={40}
                error={errors.bomCode}
                onChange={(e) =>
                  setRevise({
                    ...revise,
                    bomCode: e.target.value.toUpperCase(),
                  })
                }
              />
            </FormPanel>
          )}

          {panel?.kind === "lines" && selected && (
            <DetailPanel
              wide
              key={`lines-${selected.id}`}
              title={`${selected.bomCode} v${selected.versionNo} 구성 자재`}
              onClose={closePanel}
              actions={
                editable ? (
                  <>
                    <button
                      type="button"
                      disabled={materials.length === 0}
                      onClick={() => openLineForm(selected.id, null)}
                    >
                      자재 추가
                    </button>
                    {selected.lines.length > 0 && (
                      <button
                        type="button"
                        className="secondary"
                        disabled={pending}
                        onClick={() => void publish(selected)}
                      >
                        게시
                      </button>
                    )}
                  </>
                ) : undefined
              }
            >
              <ErrorNotice error={formError} />
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
                  editable && materials.length > 0 ? (
                    <EmptyState
                      reason="자재가 없습니다. 자재가 없는 BOM은 게시할 수 없습니다."
                      action="자재 추가"
                      onAction={() => openLineForm(selected.id, null)}
                    />
                  ) : (
                    <p className="muted">
                      자재가 없습니다. 자재가 없는 BOM은 게시할 수 없습니다.
                    </p>
                  )
                }
              />
              {errors.lines && <p className="notice">{errors.lines}</p>}
            </DetailPanel>
          )}

          {panel?.kind === "line" && selected && (
            <FormPanel
              key={`line-${panel.lineIndex ?? "new"}`}
              title={
                panel.lineIndex !== null
                  ? `${selected.bomCode} · ${panel.lineIndex + 1}번째 자재 수정`
                  : `${selected.bomCode} 자재 추가`
              }
              guard={guard}
              onClose={() => openLines(selected.id)}
              onSubmit={(e) => void submitLine(e)}
              actions={
                <>
                  <button type="submit" disabled={pending}>
                    {panel.lineIndex !== null ? "저장" : "추가"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => openLines(selected.id))}
                  >
                    자재 목록으로
                  </button>
                </>
              }
            >
              <ErrorNotice error={formError} />
              {errors.lines && <p className="notice">{errors.lines}</p>}
              <div className="field">
                <label htmlFor="bom-line-material">자재</label>
                <select
                  id="bom-line-material"
                  value={lineDraft.materialItemId || materials[0]?.id || ""}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setLineDraft({
                      ...lineDraft,
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
              </div>
              <Field
                label="소요량(1개당)"
                value={lineDraft.qtyPerUnit}
                required
                inputMode="decimal"
                onChange={(e) =>
                  setLineDraft({ ...lineDraft, qtyPerUnit: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="bom-line-unit">단위</label>
                <select
                  id="bom-line-unit"
                  value={lineDraft.unit}
                  onChange={(e) =>
                    setLineDraft({ ...lineDraft, unit: e.target.value })
                  }
                >
                  {units(lineDraft.materialItemId).map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
              <Field
                label="손실률(%)"
                value={lineDraft.lossRate}
                inputMode="decimal"
                onChange={(e) =>
                  setLineDraft({ ...lineDraft, lossRate: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
