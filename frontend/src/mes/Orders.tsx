// M-03 작업지시 — 계획 라인에서 수량을 배정해 지시를 만들고 발행(LOT 생성)·취소한다 (FS-020c)
import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
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
import { fieldErrors, ModuleOff, moduleOff, useLists, useSend } from "./common";
import type { Plan } from "./Plans";

type OrderStatus =
  "draft" | "released" | "in_progress" | "completed" | "cancelled";
export type Order = {
  id: number;
  orderNo: string;
  itemId: number;
  routeVersionId: number;
  bomVersionId: number | null;
  productionPlanLineId: number;
  planQty: string;
  unit: string;
  planStartDate: string;
  planEndDate: string;
  status: OrderStatus;
  cancelReason: string | null;
  lotId: number | null;
  lotNo: string | null;
  lotStatus: string | null;
};
type Version = {
  id: number;
  itemId: number;
  status: string;
  routeCode?: string;
  version?: number;
  bomCode?: string;
  versionNo?: number;
};
type Item = { id: number; itemCode: string; name: string };
type Draft = {
  productionPlanLineId: number;
  routeVersionId: number;
  bomVersionId: number | null;
  planQty: string;
  planStartDate: string;
  planEndDate: string;
};

type Panel =
  { type: "order"; row: Order | null } | { type: "cancel"; row: Order };

const STATUS: Record<OrderStatus, [string, "normal" | "warning" | "issue"]> = {
  draft: ["등록", "warning"],
  released: ["발행", "normal"],
  in_progress: ["진행", "normal"],
  completed: ["완료", "normal"],
  cancelled: ["취소", "issue"],
};

export function Orders() {
  const [params] = useSearchParams();
  const { data, error, reload } = useLists<
    [Order[], Plan[], Version[], Version[], Item[]]
  >(["/work-orders", "/production-plans", "/routes", "/boms", "/items"]);
  const { send, pending, error: saveError, setError } = useSend(reload);

  const preset = Number(params.get("line")) || undefined;
  const [panel, setPanel] = useState<Panel | null>(() =>
    preset ? { type: "order", row: null } : null,
  );
  const [draft, setDraft] = useState<Draft>();
  const [initial, setInitial] = useState<Draft>();
  const [cancelReason, setCancelReason] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const orderDirty =
    panel?.type === "order" &&
    Boolean(
      initial && draft
        ? (Object.keys(draft) as (keyof Draft)[]).some(
            (k) => draft[k] !== initial[k],
          )
        : draft?.planQty.trim() || draft?.planStartDate || draft?.planEndDate,
    );
  const cancelDirty = panel?.type === "cancel" && Boolean(cancelReason.trim());
  const guard = useDiscardGuard(orderDirty || cancelDirty);

  if (moduleOff(error)) return <ModuleOff />;
  const [orders, plans, routes, boms, items] = data ?? [
    undefined,
    [],
    [],
    [],
    [],
  ];
  const editing = panel?.type === "order" ? panel.row : null;
  const lines = plans
    .filter((p) => p.status === "confirmed")
    .flatMap((p) => p.lines.map((l) => ({ ...l, planCode: p.planCode })));
  const openLines = lines.filter(
    (l) => Number(l.remainingQty) > 0 || l.id === editing?.productionPlanLineId,
  );
  const item = (id: number) => items.find((i) => i.id === id);
  const itemCode = (id: number) => item(id)?.itemCode ?? String(id);
  const lineLabel = (id: number) => {
    const l = lines.find((x) => x.id === id);
    return l
      ? `${l.planCode} · ${itemCode(l.itemId)} · ${l.targetWeek} · 잔여 ${Number(l.remainingQty).toLocaleString()}`
      : String(id);
  };
  const routeLabel = (id: number) => {
    const r = routes.find((x) => x.id === id);
    return r ? `${r.routeCode} v${r.version}` : String(id);
  };
  const bomLabel = (id: number | null) => {
    if (id === null) return "없음";
    const b = boms.find((x) => x.id === id);
    return b ? `${b.bomCode} v${b.versionNo}` : String(id);
  };

  const defaultLine =
    openLines.find((l) => l.id === preset) ?? openLines[0] ?? undefined;
  const blank = (lineId?: number): Draft => {
    const line = lines.find((l) => l.id === lineId);
    const itemId = line?.itemId;
    return {
      productionPlanLineId: lineId ?? 0,
      routeVersionId:
        routes.find((r) => r.itemId === itemId && r.status === "published")
          ?.id ?? 0,
      bomVersionId:
        boms.find((b) => b.itemId === itemId && b.status === "published")?.id ??
        null,
      planQty: line ? String(Number(line.remainingQty)) : "",
      planStartDate: "",
      planEndDate: "",
    };
  };
  const d = draft ?? blank(defaultLine?.id);
  const lineItem = lines.find((l) => l.id === d.productionPlanLineId)?.itemId;
  const errors = fieldErrors(saveError);

  function openOrderPanel(row: Order | null) {
    const values: Draft = row
      ? {
          productionPlanLineId: row.productionPlanLineId,
          routeVersionId: row.routeVersionId,
          bomVersionId: row.bomVersionId,
          planQty: String(Number(row.planQty)),
          planStartDate: row.planStartDate,
          planEndDate: row.planEndDate,
        }
      : blank(defaultLine?.id);
    setPanel({ type: "order", row });
    setDraft(values);
    setInitial(values);
    setError(undefined);
  }

  function openCancelPanel(row: Order) {
    setPanel({ type: "cancel", row });
    setCancelReason("");
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
    setCancelReason("");
    setError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "order") return;
    const body = editing
      ? Object.fromEntries(
          Object.entries({
            routeVersionId: d.routeVersionId,
            bomVersionId: d.bomVersionId,
            planQty: d.planQty.trim(),
            planStartDate: d.planStartDate,
            planEndDate: d.planEndDate,
          }).filter(([k, v]) => {
            const before =
              k === "planQty"
                ? String(Number(editing.planQty))
                : editing[k as keyof Order];
            return before !== v;
          }),
        )
      : { ...d, planQty: d.planQty.trim() };
    if (editing && !Object.keys(body).length) return;
    const ok = await send(
      editing ? `/work-orders/${editing.id}` : "/work-orders",
      editing ? "PATCH" : "POST",
      body,
    );
    if (ok) closePanel();
  }

  async function submitCancel(event: FormEvent) {
    event.preventDefault();
    if (pending || panel?.type !== "cancel") return;
    const ok = await send(`/work-orders/${panel.row.id}/cancel`, "POST", {
      cancelReason,
    });
    if (ok) closePanel();
  }

  const shown = (orders ?? []).filter(
    (o) => !statusFilter || o.status === statusFilter,
  );
  const columns: Column<Order>[] = [
    { key: "orderNo", label: "지시 번호" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          {r.status === "draft" && (
            <>
              <button
                type="button"
                className="link-button"
                onClick={() =>
                  void send(`/work-orders/${r.id}/release`, "POST")
                }
              >
                발행
              </button>
              <button
                type="button"
                className="link-button"
                aria-pressed={panel?.type === "order" && editing?.id === r.id}
                onClick={() => guard.guard(() => openOrderPanel(r))}
              >
                수정
              </button>
              <button
                type="button"
                className="link-button"
                aria-pressed={panel?.type === "cancel" && panel.row.id === r.id}
                onClick={() => guard.guard(() => openCancelPanel(r))}
              >
                취소
              </button>
            </>
          )}
          {r.status === "released" && r.lotId === null && (
            <button
              type="button"
              className="link-button"
              onClick={() => void send(`/work-orders/${r.id}/lot`, "POST")}
            >
              LOT 생성
            </button>
          )}
          {!["draft"].includes(r.status) &&
            !(r.status === "released" && r.lotId === null) &&
            "-"}
        </span>
      ),
    },
    {
      key: "status",
      label: "상태",
      render: (r) => {
        const [label, tone] = STATUS[r.status];
        return <Badge tone={tone}>{label}</Badge>;
      },
    },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    {
      key: "planQty",
      label: "수량",
      render: (r) => `${Number(r.planQty).toLocaleString()} ${r.unit}`,
    },
    { key: "lotNo", label: "LOT", render: (r) => r.lotNo ?? "-" },
    {
      key: "routeVersionId",
      label: "경로",
      render: (r) => routeLabel(r.routeVersionId),
    },
    {
      key: "bomVersionId",
      label: "BOM",
      render: (r) => bomLabel(r.bomVersionId),
    },
    {
      key: "planStartDate",
      label: "계획 기간",
      render: (r) => `${r.planStartDate} ~ ${r.planEndDate}`,
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="M-03"
        title="작업지시"
        subtitle="확정 계획의 수량을 배정해 지시를 만들고 발행합니다"
        help="mes/m-03"
        actions={
          openLines.length > 0 ? (
            <button
              type="button"
              aria-pressed={panel?.type === "order" && !editing}
              onClick={() => guard.guard(() => openOrderPanel(null))}
            >
              작업지시 등록
            </button>
          ) : undefined
        }
      />
      <p className="muted" role="note">
        배정 합계는 계획 수량을 넘을 수 없습니다. 게시된 경로·BOM만 고를 수
        있고(BOM은 선택), 발행하면 LOT이 만들어지며 그 뒤에는 바꾸거나 취소할 수
        없습니다. 한 지시는 한 LOT으로 생산합니다.
      </p>
      {!panel && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!orders ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="filter-bar">
              <label htmlFor="order-status">상태:</label>
              <select
                id="order-status"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
              >
                <option value="">전체</option>
                {Object.entries(STATUS).map(([k, [label]]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <DataTable
              rows={shown}
              columns={columns}
              caption="작업지시 목록"
              offset={0}
              total={shown.length}
              limit={shown.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="조건에 맞는 작업지시가 없습니다."
                  to="/mes/production-plans"
                  action="생산계획 보기"
                />
              }
            />
          </section>
          {panel?.type === "cancel" && (
            <FormPanel
              title={`${panel.row.orderNo} 취소`}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submitCancel(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    취소 확정
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(closePanel)}
                  >
                    닫기
                  </button>
                </>
              }
            >
              <p className="muted" role="note">
                취소하면 배정 수량이 계획 잔여로 돌아갑니다. 사유는 필수입니다.
              </p>
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <Field
                label="취소 사유"
                value={cancelReason}
                required
                maxLength={300}
                error={errors.cancelReason}
                onChange={(e) => setCancelReason(e.target.value)}
              />
            </FormPanel>
          )}
          {panel?.type === "order" && (
            <FormPanel
              key={editing?.id ?? "new-order"}
              title={editing ? `${editing.orderNo} 수정` : "작업지시 등록"}
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    {editing ? "저장" : "등록"}
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
              <div className="field">
                <label htmlFor="order-line">계획 라인</label>
                <select
                  id="order-line"
                  value={d.productionPlanLineId}
                  disabled={!!editing}
                  onChange={(e) => setDraft(blank(Number(e.target.value)))}
                >
                  {openLines.map((l) => (
                    <option key={l.id} value={l.id}>
                      {lineLabel(l.id)}
                    </option>
                  ))}
                </select>
                {errors.productionPlanLineId && (
                  <small>{errors.productionPlanLineId}</small>
                )}
              </div>
              <div className="field">
                <label htmlFor="order-route">공정 경로 (게시된 버전)</label>
                <select
                  id="order-route"
                  value={d.routeVersionId}
                  onChange={(e) =>
                    setDraft({ ...d, routeVersionId: Number(e.target.value) })
                  }
                >
                  {routes
                    .filter(
                      (r) => r.itemId === lineItem && r.status === "published",
                    )
                    .map((r) => (
                      <option key={r.id} value={r.id}>
                        {routeLabel(r.id)}
                      </option>
                    ))}
                </select>
                {errors.routeVersionId && (
                  <small>{errors.routeVersionId}</small>
                )}
              </div>
              <div className="field">
                <label htmlFor="order-bom">BOM (선택)</label>
                <select
                  id="order-bom"
                  value={d.bomVersionId ?? ""}
                  onChange={(e) =>
                    setDraft({
                      ...d,
                      bomVersionId: e.target.value
                        ? Number(e.target.value)
                        : null,
                    })
                  }
                >
                  <option value="">
                    BOM 없음 (자재 투입 기준 소요량 없음)
                  </option>
                  {boms
                    .filter(
                      (b) => b.itemId === lineItem && b.status === "published",
                    )
                    .map((b) => (
                      <option key={b.id} value={b.id}>
                        {bomLabel(b.id)}
                      </option>
                    ))}
                </select>
                {errors.bomVersionId && <small>{errors.bomVersionId}</small>}
              </div>
              <Field
                label="지시 수량"
                value={d.planQty}
                required
                inputMode="decimal"
                error={errors.planQty}
                onChange={(e) => setDraft({ ...d, planQty: e.target.value })}
              />
              <Field
                label="계획 시작일"
                type="date"
                value={d.planStartDate}
                required
                error={errors.planStartDate}
                onChange={(e) =>
                  setDraft({ ...d, planStartDate: e.target.value })
                }
              />
              <Field
                label="계획 종료일"
                type="date"
                value={d.planEndDate}
                required
                error={errors.planEndDate}
                onChange={(e) =>
                  setDraft({ ...d, planEndDate: e.target.value })
                }
              />
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
