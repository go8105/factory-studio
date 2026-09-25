// M-02 생산계획 — 월 계획과 품목·주차별 라인, 작업지시 배정 현황 (FS-020c)
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
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
import { fieldErrors, ModuleOff, moduleOff, useLists, useSend } from "./common";

export type PlanLine = {
  id: number;
  productionPlanId: number;
  itemId: number;
  targetWeek: string;
  planQty: string;
  unit: string;
  allocatedQty: string;
  remainingQty: string;
};
export type Plan = {
  id: number;
  planCode: string;
  targetMonth: string;
  salesPlanCode: string | null;
  status: "draft" | "confirmed";
  lines: PlanLine[];
};
type Item = { id: number; itemCode: string; name: string; baseUnit: string };
type DraftLine = { itemId: number; targetWeek: string; planQty: string };

const qty = (value: string) => Number(value).toLocaleString();

export function Plans() {
  const { data, error, reload } = useLists<[Plan[], Item[]]>([
    "/production-plans",
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
  const [create, setCreate] = useState({
    planCode: "",
    targetMonth: "",
    salesPlanCode: "",
  });

  if (moduleOff(error)) return <ModuleOff />;
  const [plans, items] = data ?? [undefined, []];
  const selected = plans?.find((p) => p.id === selectedId);
  const original = (selected?.lines ?? []).map(
    ({ itemId, targetWeek, planQty }) => ({
      itemId,
      targetWeek,
      planQty: String(Number(planQty)),
    }),
  );
  const draft = lines ?? original;
  const errors = fieldErrors(saveError);
  const itemLabel = (id: number) => {
    const i = items.find((x) => x.id === id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };

  function select(id: number | undefined) {
    setSelectedId(id);
    setLines(undefined);
    setError(undefined);
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const created = await send<Plan>("/production-plans", "POST", {
      planCode: create.planCode.trim().toUpperCase(),
      targetMonth: create.targetMonth,
      salesPlanCode: create.salesPlanCode.trim() || null,
    });
    if (created) {
      setCreate({ planCode: "", targetMonth: "", salesPlanCode: "" });
      select(created.id);
    }
  }

  async function saveLines() {
    if (!selected || pending) return;
    const saved = await send(`/production-plans/${selected.id}/lines`, "PUT", {
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
                  void send(`/production-plans/${r.id}/confirm`, "POST")
                }
              >
                확정
              </button>
              {deleteButtons(`plan:${r.id}`, `/production-plans/${r.id}`)}
            </>
          )}
        </span>
      ),
    },
    { key: "targetMonth", label: "대상 월" },
    {
      key: "status",
      label: "상태",
      render: (r) =>
        r.status === "confirmed" ? (
          <Badge>확정</Badge>
        ) : (
          <Badge tone="warning">초안</Badge>
        ),
    },
    {
      key: "salesPlanCode",
      label: "판매계획 코드",
      render: (r) => r.salesPlanCode ?? "-",
    },
  ];

  const editable = selected?.status === "draft";
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
      key: "targetWeek",
      label: "주차",
      render: (r) => (
        <input
          aria-label={`${r.id + 1}번째 주차`}
          placeholder="2026-W41"
          value={r.targetWeek}
          onChange={(e) => setLine(r.id, { targetWeek: e.target.value })}
        />
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
    { key: "targetWeek", label: "주차" },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        Number(r.remainingQty) > 0 ? (
          <Link className="link-button" to={`/mes/work-orders?line=${r.id}`}>
            지시 만들기
          </Link>
        ) : (
          "-"
        ),
    },
    { key: "itemId", label: "품목", render: (r) => itemLabel(r.itemId) },
    {
      key: "planQty",
      label: "계획",
      render: (r) => `${qty(r.planQty)} ${r.unit}`,
    },
    {
      key: "allocatedQty",
      label: "지시 배정",
      render: (r) => qty(r.allocatedQty),
    },
    { key: "remainingQty", label: "잔여", render: (r) => qty(r.remainingQty) },
  ];
  const dirty =
    lines !== undefined && JSON.stringify(lines) !== JSON.stringify(original);

  return (
    <>
      <PageTitle
        id="M-02"
        title="생산계획"
        subtitle="월 생산계획을 품목·주차별로 세우고 작업지시 배정 현황을 봅니다"
        help="mes/m-02"
      />
      <p className="muted">
        ERP와 독립이므로 판매계획 코드는 직접 입력합니다(선택). 실제 운영에서는
        인터페이스로 연계합니다. 확정한 계획의 라인에서만 작업지시를 만들 수
        있고, 확정 후에는 계획을 바꿀 수 없습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!plans ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={plans}
                columns={columns}
                caption="생산계획 목록"
                offset={0}
                total={plans.length}
                limit={plans.length || 1}
                onPage={() => undefined}
                empty={
                  <EmptyState
                    reason="등록된 생산계획이 없습니다. 우측 폼에서 첫 계획을 만드세요."
                    to="#plan-form"
                    action="계획 만들기"
                  />
                }
              />
            </section>
            <form
              id="plan-form"
              className="panel"
              aria-label="생산계획 만들기"
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 생산계획</h2>
              <Field
                label="계획 코드"
                value={create.planCode}
                required
                maxLength={40}
                pattern="[A-Z][A-Z0-9_\-]{1,39}"
                title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                placeholder="예: PP-2026-10"
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
              <Field
                label="판매계획 코드 (선택)"
                value={create.salesPlanCode}
                maxLength={40}
                placeholder="예: SP-2026-10"
                error={errors.salesPlanCode}
                onChange={(e) =>
                  setCreate({ ...create, salesPlanCode: e.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  만들기
                </button>
              </div>
            </form>
          </div>

          {selected ? (
            <section className="panel" aria-label="계획 라인">
              <h2>
                {selected.planCode} 라인{" "}
                {selected.status === "confirmed" ? (
                  <Badge>확정</Badge>
                ) : (
                  <Badge tone="warning">초안</Badge>
                )}
              </h2>
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
                        { itemId: items[0].id, targetWeek: "", planQty: "" },
                      ])
                    }
                  >
                    라인 추가
                  </button>
                  <button
                    type="button"
                    disabled={pending || !dirty}
                    onClick={() => void saveLines()}
                  >
                    라인 저장
                  </button>
                </div>
              )}
            </section>
          ) : (
            <p className="muted">
              목록에서 &quot;라인&quot;을 누르면 품목·주차별 계획과 지시 배정
              현황을 볼 수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
