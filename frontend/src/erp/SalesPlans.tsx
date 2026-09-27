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
  type Column,
  useDiscardGuard,
} from "../shared/components";
import {
  fieldErrors,
  ITEMS,
  labels,
  ModuleOff,
  moduleOff,
  qty,
  useLists,
  useSend,
  type Item,
} from "./common";

type PlanLine = {
  id: number;
  salesPlanId: number;
  itemId: number;
  planQty: string;
  unit: string;
};
type Plan = {
  id: number;
  planCode: string;
  targetMonth: string;
  status: "draft" | "confirmed";
  confirmedAt: string | null;
  lines: PlanLine[];
};
type DraftLine = { itemId: number; planQty: string };

const status = (s: Plan["status"]) =>
  s === "confirmed" ? <Badge>확정</Badge> : <Badge tone="warning">초안</Badge>;

export function SalesPlans() {
  const { data, error, reload } = useLists<[Plan[], Item[]]>([
    "/sales-plans",
    ITEMS,
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
  const [panelOpen, setPanelOpen] = useState(false);
  const [create, setCreate] = useState({ planCode: "", targetMonth: "" });

  const [plans, allItems] = data ?? [undefined, []];
  const items = allItems.filter((i) => i.isActive);
  const name = labels([], allItems);
  const selected = plans?.find((p) => p.id === selectedId);
  const original = (selected?.lines ?? []).map(({ itemId, planQty }) => ({
    itemId,
    planQty: String(Number(planQty)),
  }));
  const draft = lines ?? original;
  const errors = fieldErrors(saveError);
  const lineDirty =
    lines !== undefined && JSON.stringify(lines) !== JSON.stringify(original);
  const createDirty =
    panelOpen && (create.planCode !== "" || create.targetMonth !== "");
  const dirty = lineDirty || createDirty;
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;

  function openCreate() {
    setError(undefined);
    setCreate({ planCode: "", targetMonth: "" });
    setPanelOpen(true);
  }

  function closeCreate() {
    setPanelOpen(false);
    setCreate({ planCode: "", targetMonth: "" });
    setError(undefined);
  }

  function select(id: number | undefined) {
    guard.guard(() => {
      setSelectedId(id);
      setLines(undefined);
      setError(undefined);
    });
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Plan>("/sales-plans", "POST", {
      planCode: create.planCode.trim().toUpperCase(),
      targetMonth: create.targetMonth,
    });
    if (created) {
      setCreate({ planCode: "", targetMonth: "" });
      setPanelOpen(false);
      setSelectedId(created.id);
      setLines(undefined);
      setError(undefined);
    }
  }

  async function saveLines() {
    if (!selected || pending) return;
    const saved = await send(`/sales-plans/${selected.id}/lines`, "PUT", {
      lines: draft.map((l) => ({ ...l, planQty: l.planQty.trim() })),
    });
    if (saved) setLines(undefined);
  }

  const setLine = (index: number, patch: Partial<DraftLine>) =>
    setLines(draft.map((l, i) => (i === index ? { ...l, ...patch } : l)));

  const columns: Column<Plan>[] = [
    { key: "planCode", label: "계획 코드" },
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
            라인 {r.lines.length}
          </button>
          {r.status === "draft" && (
            <>
              <button
                type="button"
                className="link-button"
                onClick={() =>
                  void send(`/sales-plans/${r.id}/confirm`, "POST")
                }
              >
                확정
              </button>
              {deleteButtons(`plan:${r.id}`, `/sales-plans/${r.id}`)}
            </>
          )}
        </span>
      ),
    },
    { key: "targetMonth", label: "대상 월" },
    { key: "status", label: "상태", render: (r) => status(r.status) },
    {
      key: "confirmedAt",
      label: "확정 시각",
      render: (r) =>
        r.confirmedAt ? new Date(r.confirmedAt).toLocaleString() : "-",
    },
  ];
  const draftRows = draft.map((l, i) => ({ id: i, ...l }));
  const draftColumns: Column<(typeof draftRows)[number]>[] = [
    {
      key: "itemId",
      label: "품목",
      render: (r) => (
        <select
          aria-label={`${r.id + 1}번째 품목`}
          value={r.itemId}
          onChange={(e) => setLine(r.id, { itemId: Number(e.target.value) })}
        >
          {items.map((i) => (
            <option key={i.id} value={i.id}>
              {i.itemCode} {i.name} ({i.baseUnit})
            </option>
          ))}
        </select>
      ),
    },
    {
      key: "planQty",
      label: "계획 수량",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 수량`}
          inputMode="decimal"
          value={r.planQty}
          onChange={(e) => setLine(r.id, { planQty: e.target.value })}
        />
      ),
    },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-label={`${r.id + 1}번째 라인 빼기`}
          onClick={() => setLines(draft.filter((_, i) => i !== r.id))}
        >
          빼기
        </button>
      ),
    },
  ];
  const lineColumns: Column<PlanLine>[] = [
    { key: "itemId", label: "품목", render: (r) => name.item(r.itemId) },
    {
      key: "planQty",
      label: "계획 수량",
      render: (r) => `${qty(r.planQty)} ${r.unit}`,
    },
  ];
  const editable = selected?.status === "draft";

  return (
    <div className="page-fill">
      <PageTitle
        id="E-03"
        title="판매계획"
        subtitle="월별 품목 판매계획을 세우고 확정합니다"
        help="erp/e-03"
        actions={
          <button
            type="button"
            aria-pressed={panelOpen}
            onClick={() =>
              guard.guard(() => (panelOpen ? closeCreate() : openCreate()))
            }
          >
            판매계획 만들기
          </button>
        }
      />
      <p className="muted">
        MES 생산계획은 이 계획을 코드(예: SP-2026-10)로만 적어 둡니다. 독립
        솔루션이라 ERP에서는 이 계획이 MES에서 쓰이는지 알 수 없습니다. 확정한
        계획은 바꿀 수 없으니 변경은 새 계획으로 만드세요.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!plans ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <DataTable
                rows={plans}
                columns={columns}
                caption="판매계획 목록"
                offset={0}
                total={plans.length}
                limit={plans.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 판매계획이 없습니다. 패널을 열어 첫 계획을 만드세요."
                    action="판매계획 만들기"
                    onAction={() => guard.guard(openCreate)}
                  />
                }
              />
            </div>

            {selected ? (
              <section className="section-block" aria-label="계획 라인">
                <div className="section-heading">
                  <h2>
                    {selected.planCode} 라인 {status(selected.status)}
                  </h2>
                </div>
                {editable ? (
                  <DataTable
                    rows={draftRows}
                    columns={draftColumns}
                    caption={`${selected.planCode} 계획 라인`}
                    offset={0}
                    total={draftRows.length}
                    limit={draftRows.length || 1}
                    onPage={() => undefined}
                    empty={
                      <p className="muted">
                        라인이 없습니다. 라인이 없는 계획은 확정할 수 없습니다.
                      </p>
                    }
                  />
                ) : (
                  <DataTable
                    rows={selected.lines}
                    columns={lineColumns}
                    caption={`${selected.planCode} 계획 라인`}
                    offset={0}
                    total={selected.lines.length}
                    limit={selected.lines.length || 1}
                    onPage={() => undefined}
                    empty={<p className="muted">라인이 없습니다.</p>}
                  />
                )}
                {errors.lines && <p className="notice">{errors.lines}</p>}
                {editable && (
                  <div className="form-actions">
                    <button
                      type="button"
                      className="secondary"
                      disabled={items.length === 0}
                      onClick={() =>
                        setLines([
                          ...draft,
                          { itemId: items[0].id, planQty: "" },
                        ])
                      }
                    >
                      라인 추가
                    </button>
                    <button
                      type="button"
                      disabled={pending || !lineDirty}
                      onClick={() => void saveLines()}
                    >
                      라인 저장
                    </button>
                  </div>
                )}
              </section>
            ) : (
              <p className="muted">
                목록에서 &quot;라인&quot;을 누르면 품목별 계획 수량을 볼 수
                있습니다.
              </p>
            )}
          </section>

          {panelOpen && (
            <FormPanel
              title="판매계획 만들기"
              guard={guard}
              onClose={() => guard.guard(closeCreate)}
              onSubmit={(e) => void submitCreate(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    만들기
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closeCreate)}
                  >
                    취소
                  </button>
                </>
              }
            >
              <Field
                label="계획 코드"
                value={create.planCode}
                required
                maxLength={40}
                placeholder="예: SP-2026-10"
                error={errors.planCode}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    planCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <Field
                label="대상 월"
                type="month"
                value={create.targetMonth}
                required
                error={errors.targetMonth}
                onChange={(e) =>
                  setCreate({ ...create, targetMonth: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
