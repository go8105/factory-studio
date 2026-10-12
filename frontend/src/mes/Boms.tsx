import { Fragment, useState, type FormEvent } from "react";
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
import { ApiError } from "../shared/api";
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

type Substitute = {
  id: number;
  bomLineId: number;
  substituteItemId: number;
  priority: number;
  ratio: string;
};
type Line = {
  id: number;
  lineNo: number;
  materialItemId: number;
  qtyPerUnit: string;
  unit: string;
  lossRate: string;
  issueProcessId: number | null;
  substitutes?: Substitute[];
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
type Process = {
  id: number;
  processCode: string;
  name: string;
};
type DraftLine = Omit<Line, "id" | "lineNo" | "substitutes">;

const toDraft = (lines: Line[]): DraftLine[] =>
  lines.map(
    ({ materialItemId, qtyPerUnit, unit, lossRate, issueProcessId }) => ({
      materialItemId,
      qtyPerUnit: String(Number(qtyPerUnit)),
      unit,
      lossRate: String(Number(lossRate)),
      issueProcessId: issueProcessId ?? null,
    }),
  );

export function Boms() {
  const { data, error, reload } = useLists<[Bom[], Item[], Process[]]>([
    "/boms",
    "/items",
    "/processes",
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

  const [linesState, setLinesState] = useState<Line[] | undefined>();
  const [expandedLineIds, setExpandedLineIds] = useState<Set<number>>(
    new Set(),
  );
  const [subDrafts, setSubDrafts] = useState<
    Record<
      number,
      { substituteItemId: number; priority: number; ratio: string }
    >
  >({});

  const [lineDraft, setLineDraft] = useState<DraftLine>({
    materialItemId: 0,
    qtyPerUnit: "1",
    unit: "",
    lossRate: "0",
    issueProcessId: null,
  });
  const [initialLineDraft, setInitialLineDraft] = useState<DraftLine>({
    materialItemId: 0,
    qtyPerUnit: "1",
    unit: "",
    lossRate: "0",
    issueProcessId: null,
  });

  if (moduleOff(error)) return <ModuleOff />;
  const [boms, items, processes] = data ?? [undefined, [], []];

  const selectedId = panel && "bomId" in panel ? panel.bomId : undefined;
  const selected = boms?.find((b) => b.id === selectedId);
  const draftLines = linesState ?? selected?.lines ?? [];
  const editable = selected?.status === "draft";
  const dirtyLines =
    linesState !== undefined &&
    JSON.stringify(toDraft(linesState)) !==
      JSON.stringify(toDraft(selected?.lines ?? []));

  const errors = fieldErrors(saveError);
  const referencedError =
    saveError instanceof ApiError &&
    saveError.error.code === "REFERENCED_BY_OTHERS" &&
    saveError.error.details?.lineId
      ? {
          lineId: Number(saveError.error.details.lineId),
          message: saveError.error.message,
        }
      : null;

  const item = (id: number) => items.find((i) => i.id === id);
  const itemLabel = (id: number) => {
    const i = item(id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };
  const processLabel = (id: number | null | undefined) => {
    if (id == null) return "공정 지정 안 함";
    const p = processes.find((proc) => proc.id === id);
    return p ? `${p.processCode} ${p.name}` : String(id);
  };
  const units = (id: number) => {
    const i = item(id);
    return i ? [i.baseUnit, ...i.conversions.map((c) => c.fromUnit)] : [];
  };
  const materials = items.filter((i) => i.id !== selected?.itemId);

  const availableSubstitutes = (line: Line) => {
    const existingSubIds = new Set(
      (line.substitutes ?? []).map((s) => s.substituteItemId),
    );
    return items.filter(
      (i) =>
        i.id !== selected?.itemId &&
        i.id !== line.materialItemId &&
        !existingSubIds.has(i.id),
    );
  };

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
    setLinesState(undefined);
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
        issueProcessId: target.issueProcessId ?? null,
      };
    } else {
      const defaultMaterial = targetMaterials[0];
      initial = {
        materialItemId: defaultMaterial?.id ?? 0,
        qtyPerUnit: "1",
        unit: defaultMaterial?.baseUnit ?? "",
        lossRate: "0",
        issueProcessId: null,
      };
    }
    setLineDraft(initial);
    setInitialLineDraft(initial);
    setPanel({ kind: "line", bomId, lineIndex });
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
    setLinesState(undefined);
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

  function move(index: number, delta: number) {
    const next = [...draftLines];
    const [taken] = next.splice(index, 1);
    next.splice(index + delta, 0, taken);
    setLinesState(next);
  }

  async function saveLinesOrder() {
    if (!selected || pending) return;
    const saved = await send<Bom>(`/boms/${selected.id}/lines`, "PUT", {
      lines: toDraft(draftLines),
    });
    if (saved) {
      setLinesState(undefined);
    }
  }

  async function submitLine(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const currentLines = toDraft(draftLines);
    const updatedLine: DraftLine = {
      ...lineDraft,
      qtyPerUnit: lineDraft.qtyPerUnit.trim(),
      lossRate: lineDraft.lossRate.trim() || "0",
      issueProcessId: lineDraft.issueProcessId ?? null,
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
      setLinesState(undefined);
      openLines(selected.id);
    }
  }

  async function removeLine(index: number) {
    if (!selected || pending) return;
    const currentLines = toDraft(draftLines);
    const nextLines = currentLines.filter((_, i) => i !== index);
    const saved = await send<Bom>(`/boms/${selected.id}/lines`, "PUT", {
      lines: nextLines,
    });
    if (saved) {
      setLinesState(undefined);
    }
  }

  function toggleExpand(lineId: number) {
    setExpandedLineIds((prev) => {
      const next = new Set(prev);
      if (next.has(lineId)) next.delete(lineId);
      else next.add(lineId);
      return next;
    });
  }

  async function addSubstitute(event: FormEvent, lineId: number) {
    event.preventDefault();
    if (pending || !selected) return;
    const targetLine = selected.lines.find((l) => l.id === lineId);
    if (!targetLine) return;
    const avail = availableSubstitutes(targetLine);
    const draft = subDrafts[lineId] ?? {
      substituteItemId: avail[0]?.id ?? 0,
      priority: (targetLine.substitutes?.length ?? 0) + 1,
      ratio: "1",
    };
    const subItemId = draft.substituteItemId || avail[0]?.id;
    if (!subItemId) return;
    const nextSubstitutes = [
      ...(targetLine.substitutes ?? []).map((s) => ({
        substituteItemId: s.substituteItemId,
        priority: s.priority,
        ratio: String(s.ratio),
      })),
      {
        substituteItemId: subItemId,
        priority: Number(draft.priority) || 1,
        ratio: String(draft.ratio || "1").trim(),
      },
    ];
    const saved = await send<Substitute[]>(
      `/boms/${selected.id}/lines/${lineId}/substitutes`,
      "PUT",
      { substitutes: nextSubstitutes },
    );
    if (saved) {
      setSubDrafts((prev) => {
        const next = { ...prev };
        delete next[lineId];
        return next;
      });
    }
  }

  async function removeSubstitute(lineId: number, subIndex: number) {
    if (pending || !selected) return;
    const targetLine = selected.lines.find((l) => l.id === lineId);
    if (!targetLine || !targetLine.substitutes) return;
    const nextSubstitutes = targetLine.substitutes
      .filter((_, idx) => idx !== subIndex)
      .map((s) => ({
        substituteItemId: s.substituteItemId,
        priority: s.priority,
        ratio: String(s.ratio),
      }));
    await send<Substitute[]>(
      `/boms/${selected.id}/lines/${lineId}/substitutes`,
      "PUT",
      { substitutes: nextSubstitutes },
    );
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
                    {dirtyLines && (
                      <button
                        type="button"
                        disabled={pending}
                        onClick={() => void saveLinesOrder()}
                      >
                        순서 저장
                      </button>
                    )}
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
                        disabled={pending || dirtyLines}
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
              <section className="data-table fill">
                <div className="table-toolbar">
                  <div className="table-toolbar-lead">
                    <p>
                      총 <strong>{draftLines.length}</strong>개 구성 자재
                      {dirtyLines &&
                        " · 순서가 변경되었습니다. '순서 저장'을 누르세요."}
                    </p>
                  </div>
                </div>
                {draftLines.length ? (
                  <div className="table-scroll">
                    <table>
                      <caption>{`${selected.bomCode} 구성 자재`}</caption>
                      <thead>
                        <tr>
                          {editable && (
                            <th scope="col" style={{ width: "4rem" }}>
                              순서
                            </th>
                          )}
                          <th scope="col">자재</th>
                          <th scope="col" className="num">
                            소요량(1개당)
                          </th>
                          <th scope="col">단위</th>
                          <th scope="col" className="num">
                            손실률(%)
                          </th>
                          <th scope="col">투입 공정</th>
                          <th scope="col">대체 자재</th>
                          <th scope="col">관리</th>
                        </tr>
                      </thead>
                      <tbody>
                        {draftLines.map((line, index) => {
                          const subCount = line.substitutes?.length ?? 0;
                          const isExpanded = expandedLineIds.has(line.id);
                          const hasRefError =
                            referencedError?.lineId === line.id;
                          const currentSubDraft = subDrafts[line.id] ?? {
                            substituteItemId:
                              availableSubstitutes(line)[0]?.id ?? 0,
                            priority: subCount + 1,
                            ratio: "1",
                          };
                          const availSubs = availableSubstitutes(line);

                          return (
                            <Fragment key={line.id || `line-${index}`}>
                              <tr>
                                {editable && (
                                  <td>
                                    <span className="row-actions">
                                      <button
                                        type="button"
                                        className="link-button"
                                        disabled={index === 0}
                                        aria-label={`${index + 1}번째 자재 위로`}
                                        onClick={() => move(index, -1)}
                                      >
                                        ↑
                                      </button>
                                      <button
                                        type="button"
                                        className="link-button"
                                        disabled={
                                          index === draftLines.length - 1
                                        }
                                        aria-label={`${index + 1}번째 자재 아래로`}
                                        onClick={() => move(index, 1)}
                                      >
                                        ↓
                                      </button>
                                    </span>
                                  </td>
                                )}
                                <td>{itemLabel(line.materialItemId)}</td>
                                <td className="num">{line.qtyPerUnit}</td>
                                <td>{line.unit}</td>
                                <td className="num">{line.lossRate}</td>
                                <td>{processLabel(line.issueProcessId)}</td>
                                <td>
                                  <button
                                    type="button"
                                    className="link-button"
                                    aria-expanded={isExpanded}
                                    onClick={() => toggleExpand(line.id)}
                                  >
                                    대체 자재{" "}
                                    {subCount > 0 ? `(${subCount})` : "설정"}{" "}
                                    {isExpanded ? "▲" : "▼"}
                                  </button>
                                </td>
                                <td>
                                  {editable ? (
                                    <span className="row-actions">
                                      <button
                                        type="button"
                                        className="link-button"
                                        onClick={() =>
                                          openLineForm(selected.id, index)
                                        }
                                      >
                                        수정
                                      </button>
                                      <button
                                        type="button"
                                        className="link-button"
                                        aria-label={`${index + 1}번째 자재 빼기`}
                                        onClick={() => void removeLine(index)}
                                      >
                                        빼기
                                      </button>
                                      {hasRefError && (
                                        <span
                                          className="notice error-inline"
                                          style={{
                                            display: "inline-block",
                                            marginLeft: "6px",
                                            color: "var(--issue, #c0392b)",
                                            fontWeight: 600,
                                            fontSize: "var(--fs-xs, 0.75rem)",
                                          }}
                                        >
                                          {referencedError.message}
                                        </span>
                                      )}
                                    </span>
                                  ) : (
                                    "-"
                                  )}
                                </td>
                              </tr>
                              {isExpanded && (
                                <tr className="substitutes-row">
                                  <td
                                    colSpan={editable ? 8 : 7}
                                    style={{
                                      background: "var(--surface-2, #f9f9f8)",
                                      padding: "12px 16px",
                                    }}
                                  >
                                    <div className="substitutes-container">
                                      <div
                                        style={{
                                          display: "flex",
                                          justifyContent: "space-between",
                                          alignItems: "center",
                                          marginBottom: "8px",
                                        }}
                                      >
                                        <strong>
                                          {itemLabel(line.materialItemId)} 대체
                                          자재
                                        </strong>
                                        <span
                                          className="muted"
                                          style={{
                                            fontSize: "var(--fs-xs)",
                                          }}
                                        >
                                          우선순위 순으로 적용됩니다
                                        </span>
                                      </div>
                                      {subCount === 0 ? (
                                        <p
                                          className="muted"
                                          style={{
                                            margin: "4px 0 12px",
                                          }}
                                        >
                                          등록된 대체 자재가 없습니다.
                                        </p>
                                      ) : (
                                        <table
                                          style={{
                                            width: "100%",
                                            marginBottom: "12px",
                                            background: "var(--surface)",
                                          }}
                                        >
                                          <thead>
                                            <tr>
                                              <th style={{ width: "5rem" }}>
                                                우선순위
                                              </th>
                                              <th>대체 품목</th>
                                              <th style={{ width: "8rem" }}>
                                                대체 비율
                                              </th>
                                              {editable && (
                                                <th style={{ width: "4rem" }}>
                                                  관리
                                                </th>
                                              )}
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {line.substitutes!.map(
                                              (sub, sIdx) => (
                                                <tr key={sub.id || sIdx}>
                                                  <td>{sub.priority}순위</td>
                                                  <td>
                                                    {itemLabel(
                                                      sub.substituteItemId,
                                                    )}
                                                  </td>
                                                  <td>{sub.ratio}</td>
                                                  {editable && (
                                                    <td>
                                                      <button
                                                        type="button"
                                                        className="link-button"
                                                        onClick={() =>
                                                          void removeSubstitute(
                                                            line.id,
                                                            sIdx,
                                                          )
                                                        }
                                                      >
                                                        삭제
                                                      </button>
                                                    </td>
                                                  )}
                                                </tr>
                                              ),
                                            )}
                                          </tbody>
                                        </table>
                                      )}
                                      {editable && (
                                        <form
                                          onSubmit={(e) =>
                                            void addSubstitute(e, line.id)
                                          }
                                          style={{
                                            display: "flex",
                                            flexWrap: "wrap",
                                            gap: "8px",
                                            alignItems: "flex-end",
                                          }}
                                        >
                                          <div
                                            style={{
                                              minWidth: "140px",
                                              flex: 1,
                                            }}
                                          >
                                            <label
                                              htmlFor={`sub-item-${line.id}`}
                                              style={{
                                                display: "block",
                                                fontSize: "var(--fs-xs)",
                                                marginBottom: "4px",
                                              }}
                                            >
                                              대체 품목
                                            </label>
                                            <select
                                              id={`sub-item-${line.id}`}
                                              value={
                                                currentSubDraft.substituteItemId ||
                                                availSubs[0]?.id ||
                                                ""
                                              }
                                              disabled={availSubs.length === 0}
                                              onChange={(e) => {
                                                const val = Number(
                                                  e.target.value,
                                                );
                                                setSubDrafts((prev) => ({
                                                  ...prev,
                                                  [line.id]: {
                                                    ...currentSubDraft,
                                                    substituteItemId: val,
                                                  },
                                                }));
                                              }}
                                            >
                                              {availSubs.length === 0 ? (
                                                <option value="">
                                                  추가 가능한 대체 품목 없음
                                                </option>
                                              ) : (
                                                availSubs.map((m) => (
                                                  <option
                                                    key={m.id}
                                                    value={m.id}
                                                  >
                                                    {m.itemCode} {m.name}
                                                  </option>
                                                ))
                                              )}
                                            </select>
                                          </div>
                                          <div style={{ width: "5rem" }}>
                                            <label
                                              htmlFor={`sub-prio-${line.id}`}
                                              style={{
                                                display: "block",
                                                fontSize: "var(--fs-xs)",
                                                marginBottom: "4px",
                                              }}
                                            >
                                              우선순위
                                            </label>
                                            <input
                                              id={`sub-prio-${line.id}`}
                                              type="number"
                                              min={1}
                                              value={currentSubDraft.priority}
                                              onChange={(e) => {
                                                const val = Number(
                                                  e.target.value,
                                                );
                                                setSubDrafts((prev) => ({
                                                  ...prev,
                                                  [line.id]: {
                                                    ...currentSubDraft,
                                                    priority: val,
                                                  },
                                                }));
                                              }}
                                            />
                                          </div>
                                          <div style={{ width: "6rem" }}>
                                            <label
                                              htmlFor={`sub-ratio-${line.id}`}
                                              style={{
                                                display: "block",
                                                fontSize: "var(--fs-xs)",
                                                marginBottom: "4px",
                                              }}
                                            >
                                              비율
                                            </label>
                                            <input
                                              id={`sub-ratio-${line.id}`}
                                              type="text"
                                              placeholder="1.0"
                                              value={currentSubDraft.ratio}
                                              onChange={(e) => {
                                                const val = e.target.value;
                                                setSubDrafts((prev) => ({
                                                  ...prev,
                                                  [line.id]: {
                                                    ...currentSubDraft,
                                                    ratio: val,
                                                  },
                                                }));
                                              }}
                                            />
                                          </div>
                                          <button
                                            type="submit"
                                            className="secondary"
                                            disabled={
                                              pending || availSubs.length === 0
                                            }
                                          >
                                            대체 자재 추가
                                          </button>
                                        </form>
                                      )}
                                    </div>
                                  </td>
                                </tr>
                              )}
                            </Fragment>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ padding: "var(--s4)" }}>
                    {editable && materials.length > 0 ? (
                      <EmptyState
                        reason="자재가 없습니다. 자재가 없는 BOM은 게시할 수 없습니다."
                        action="자재 추가"
                        onAction={() => openLineForm(selected.id, null)}
                      />
                    ) : (
                      <p className="muted">
                        자재가 없습니다. 자재가 없는 BOM은 게시할 수 없습니다.
                      </p>
                    )}
                  </div>
                )}
              </section>
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
              <div className="field">
                <label htmlFor="bom-line-process">투입 공정 (선택)</label>
                <select
                  id="bom-line-process"
                  value={lineDraft.issueProcessId ?? ""}
                  onChange={(e) =>
                    setLineDraft({
                      ...lineDraft,
                      issueProcessId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">(공정 지정 안 함)</option>
                  {processes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.processCode} {p.name}
                    </option>
                  ))}
                </select>
              </div>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
