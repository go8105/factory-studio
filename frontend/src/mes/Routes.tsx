// M-14 공정 경로 — 품목별 공정 순서의 버전 관리(초안 → 게시 → 폐기) (FS-020b)
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

export type Step = {
  id: number;
  processId: number;
  sequenceNo: number;
  standardCycleSec?: string | null;
  setupMinutes?: number | null;
  isSubcontract: boolean;
  subcontractorCode?: string | null;
};
export type Route = {
  id: number;
  itemId: number;
  routeCode: string;
  version: number;
  status: VersionStatus;
  publishedAt: string | null;
  steps: Step[];
};
type StepDraft = {
  processId: number;
  standardCycleSec?: string | null;
  setupMinutes?: number | null;
  isSubcontract: boolean;
  subcontractorCode?: string | null;
};
type StepForm = {
  processId: number;
  standardCycleSec: string;
  setupMinutes: string;
  isSubcontract: boolean;
  subcontractorCode: string;
};
type Named = { id: number; name: string };
type Item = Named & { itemCode: string };
type Process = Named & { processCode: string; isActive: boolean };

export function Routes() {
  const { data, error, reload } = useLists<[Route[], Item[], Process[]]>([
    "/routes",
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
    | { kind: "steps"; routeId: number }
    | { kind: "step"; routeId: number; stepIndex: number | null }
    | null
  >(null);

  const [create, setCreate] = useState({ itemId: 0, routeCode: "" });
  const [initialCreate, setInitialCreate] = useState({
    itemId: 0,
    routeCode: "",
  });
  const [steps, setSteps] = useState<StepDraft[]>();
  const [stepForm, setStepForm] = useState<StepForm>({
    processId: 0,
    standardCycleSec: "",
    setupMinutes: "",
    isSubcontract: false,
    subcontractorCode: "",
  });
  const [initialStepForm, setInitialStepForm] = useState<StepForm>({
    processId: 0,
    standardCycleSec: "",
    setupMinutes: "",
    isSubcontract: false,
    subcontractorCode: "",
  });

  if (moduleOff(error)) return <ModuleOff />;
  const [routes, items, processes] = data ?? [undefined, [], []];

  const selectedId = panel && "routeId" in panel ? panel.routeId : undefined;
  const selected = routes?.find((r) => r.id === selectedId);
  const draftSteps: StepDraft[] =
    steps ??
    selected?.steps.map((s) => ({
      processId: s.processId,
      standardCycleSec: s.standardCycleSec ?? null,
      setupMinutes: s.setupMinutes ?? null,
      isSubcontract: Boolean(s.isSubcontract),
      subcontractorCode: s.subcontractorCode ?? null,
    })) ??
    [];
  const errors = fieldErrors(saveError);

  function toPayloadStep(s: StepDraft) {
    const cycle = s.standardCycleSec?.trim() || null;
    const setupStr =
      s.setupMinutes !== undefined && s.setupMinutes !== null
        ? String(s.setupMinutes).trim()
        : "";
    const setup =
      setupStr !== "" && !Number.isNaN(Number(setupStr)) ? Number(setupStr) : null;
    const isSub = Boolean(s.isSubcontract);
    const subCode =
      isSub && s.subcontractorCode?.trim() ? s.subcontractorCode.trim() : null;
    return {
      processId: s.processId,
      standardCycleSec: cycle,
      setupMinutes: setup,
      isSubcontract: isSub,
      subcontractorCode: subCode,
    };
  }

  const itemLabel = (id: number) => {
    const item = items.find((i) => i.id === id);
    return item ? `${item.itemCode} ${item.name}` : String(id);
  };
  const processLabel = (id: number) => {
    const p = processes.find((x) => x.id === id);
    return p ? `${p.processCode} ${p.name}` : String(id);
  };

  const dirty =
    (panel?.kind === "create" &&
      JSON.stringify(create) !== JSON.stringify(initialCreate)) ||
    (panel?.kind === "step" &&
      JSON.stringify(stepForm) !== JSON.stringify(initialStepForm));
  const guard = useDiscardGuard(dirty);

  function openCreate() {
    const initial = { itemId: items[0]?.id ?? 0, routeCode: "" };
    setCreate(initial);
    setInitialCreate(initial);
    setPanel({ kind: "create" });
    setError(undefined);
  }

  function openSteps(routeId: number) {
    setPanel({ kind: "steps", routeId });
    setSteps(undefined);
    setError(undefined);
  }

  function openStepForm(routeId: number, stepIndex: number | null) {
    const target =
      stepIndex !== null && draftSteps[stepIndex]
        ? draftSteps[stepIndex]
        : undefined;
    const initial: StepForm = {
      processId: target?.processId ?? processes[0]?.id ?? 0,
      standardCycleSec: target?.standardCycleSec ?? "",
      setupMinutes:
        target?.setupMinutes != null ? String(target.setupMinutes) : "",
      isSubcontract: target?.isSubcontract ?? false,
      subcontractorCode: target?.subcontractorCode ?? "",
    };
    setStepForm(initial);
    setInitialStepForm(initial);
    setPanel({ kind: "step", routeId, stepIndex });
    setError(undefined);
  }

  function closePanel() {
    setPanel(null);
    setSteps(undefined);
    setError(undefined);
  }

  async function revise(row: Route) {
    const created = await send<Route>(`/routes/${row.id}/revise`, "POST");
    if (created) openSteps(created.id);
  }

  async function publish(row: Route) {
    await send<Route>(`/routes/${row.id}/publish`, "POST");
  }

  async function submitCreate(event: FormEvent) {
    event.preventDefault();
    if (pending) return;
    const body = {
      itemId: create.itemId || items[0]?.id,
      routeCode: create.routeCode.trim().toUpperCase(),
    };
    const created = await send<Route>("/routes", "POST", body);
    if (created) {
      openSteps(created.id);
    }
  }

  function move(index: number, delta: number) {
    const next = [...draftSteps];
    const [taken] = next.splice(index, 1);
    next.splice(index + delta, 0, taken);
    setSteps(next);
  }

  function removeStep(index: number) {
    setSteps(draftSteps.filter((_, i) => i !== index));
  }

  async function saveSteps() {
    if (!selected || pending) return;
    const saved = await send<Route>(`/routes/${selected.id}/steps`, "PUT", {
      steps: draftSteps.map(toPayloadStep),
    });
    if (saved) setSteps(undefined);
  }

  async function submitStep(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const newStep: StepDraft = {
      processId: stepForm.processId || processes[0]?.id || 0,
      standardCycleSec: stepForm.standardCycleSec.trim() || null,
      setupMinutes:
        stepForm.setupMinutes.trim() !== "" &&
        !Number.isNaN(Number(stepForm.setupMinutes))
          ? Number(stepForm.setupMinutes)
          : null,
      isSubcontract: stepForm.isSubcontract,
      subcontractorCode:
        stepForm.isSubcontract && stepForm.subcontractorCode.trim()
          ? stepForm.subcontractorCode.trim()
          : null,
    };
    let nextSteps: StepDraft[];
    if (panel?.kind === "step" && panel.stepIndex !== null) {
      nextSteps = draftSteps.map((s, idx) =>
        idx === panel.stepIndex ? newStep : s,
      );
    } else {
      nextSteps = [...draftSteps, newStep];
    }
    const saved = await send<Route>(`/routes/${selected.id}/steps`, "PUT", {
      steps: nextSteps.map(toPayloadStep),
    });
    if (saved) {
      openSteps(selected.id);
    }
  }

  const columns: Column<Route>[] = [
    { key: "routeCode", label: "경로 코드" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <span className="row-actions">
          <button
            type="button"
            className="link-button"
            aria-pressed={r.id === selectedId}
            onClick={() => guard.guard(() => openSteps(r.id))}
          >
            공정 {r.steps.length}
          </button>
          {versionButtons(
            r,
            "/routes",
            send,
            deleteButtons,
            () => void revise(r),
          )}
        </span>
      ),
    },
    { key: "version", label: "버전", render: (r) => `v${r.version}` },
    {
      key: "status",
      label: "상태",
      render: (r) => <StatusBadge status={r.status} />,
    },
    { key: "itemId", label: "품목", render: (r) => itemLabel(r.itemId) },
  ];

  type StepRow = {
    id: number;
    pid: number;
    label: string;
    standardCycleSec: string | null;
    setupMinutes: number | null;
    isSubcontract: boolean;
    subcontractorCode: string | null;
    step: StepDraft;
  };

  const editable = selected?.status === "draft";
  const stepColumns: Column<StepRow>[] = [
    { key: "id", label: "순서", render: (r) => String(r.id + 1) },
    {
      key: "pid",
      label: "관리",
      render: (r) =>
        editable ? (
          <span className="row-actions">
            <button
              type="button"
              className="link-button"
              onClick={() => openStepForm(selected!.id, r.id)}
            >
              수정
            </button>
            <button
              type="button"
              className="link-button"
              disabled={r.id === 0}
              aria-label={`${r.id + 1}번째 공정 위로`}
              onClick={() => move(r.id, -1)}
            >
              위로
            </button>
            <button
              type="button"
              className="link-button"
              disabled={r.id === draftSteps.length - 1}
              aria-label={`${r.id + 1}번째 공정 아래로`}
              onClick={() => move(r.id, 1)}
            >
              아래로
            </button>
            <button
              type="button"
              className="link-button"
              aria-label={`${r.id + 1}번째 공정 빼기`}
              onClick={() => removeStep(r.id)}
            >
              빼기
            </button>
          </span>
        ) : (
          "-"
        ),
    },
    { key: "label", label: "공정" },
    {
      key: "standardCycleSec",
      label: "표준 CT (초)",
      render: (r) =>
        r.step.standardCycleSec ? `${r.step.standardCycleSec}초` : "-",
    },
    {
      key: "setupMinutes",
      label: "준비 (분)",
      render: (r) =>
        r.step.setupMinutes != null ? `${r.step.setupMinutes}분` : "-",
    },
    {
      key: "isSubcontract",
      label: "구분",
      render: (r) =>
        r.step.isSubcontract ? (
          <span>
            외주{r.step.subcontractorCode ? ` (${r.step.subcontractorCode})` : ""}
          </span>
        ) : (
          "사내"
        ),
    },
  ];

  const dirtySteps =
    steps !== undefined &&
    JSON.stringify(steps.map(toPayloadStep)) !==
      JSON.stringify(
        (selected?.steps ?? []).map((s) => toPayloadStep(s)),
      );

  const formError = Object.keys(errors).length ? undefined : saveError;

  return (
    <div className="page-fill">
      <PageTitle
        id="M-14"
        title="공정 경로"
        subtitle="품목을 만드는 공정 순서를 버전으로 관리합니다"
        help="mes/m-14"
        actions={
          <button type="button" onClick={() => guard.guard(openCreate)}>
            새 공정 경로
          </button>
        }
      />
      <MesOrder />
      <p className="muted">
        게시된 경로만 작업지시에서 고를 수 있습니다. 게시·폐기된 버전은 바꿀 수
        없고, 바꾸려면 개정해서 새 버전(초안)으로 편집합니다.
      </p>
      {!panel && <ErrorNotice error={formError} />}
      <ErrorNotice error={error} retry={reload} />
      {!routes ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <DataTable
              rows={routes}
              columns={columns}
              caption="공정 경로 목록"
              offset={0}
              total={routes.length}
              limit={routes.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="등록된 공정 경로가 없습니다. 첫 공정 경로를 등록하세요."
                  action="새 공정 경로"
                  onAction={() => guard.guard(openCreate)}
                />
              }
            />
          </section>

          {panel?.kind === "create" && (
            <FormPanel
              key="route-create"
              title="새 공정 경로"
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
                <label htmlFor="route-item">품목</label>
                <select
                  id="route-item"
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
                label="경로 코드"
                value={create.routeCode}
                required
                maxLength={40}
                pattern="[A-Z][A-Z0-9_\-]{1,39}"
                title="영문 대문자로 시작하는 2~40자 (대문자·숫자·_·-)"
                placeholder="예: RT-C400"
                error={errors.routeCode}
                onChange={(e) =>
                  setCreate({
                    ...create,
                    routeCode: e.target.value.toUpperCase(),
                  })
                }
              />
              <p className="muted">
                v1 초안으로 만들어집니다. 이미 있는 경로는 목록에서 개정하세요.
              </p>
            </FormPanel>
          )}

          {panel?.kind === "steps" && selected && (
            <DetailPanel
              wide
              key={`steps-${selected.id}`}
              title={`${selected.routeCode} v${selected.version} 공정 순서`}
              onClose={closePanel}
              actions={
                editable ? (
                  <>
                    <button
                      type="button"
                      disabled={processes.length === 0}
                      onClick={() => openStepForm(selected.id, null)}
                    >
                      공정 추가
                    </button>
                    <button
                      type="button"
                      disabled={pending || !dirtySteps}
                      onClick={() => void saveSteps()}
                    >
                      순서 저장
                    </button>
                    {draftSteps.length > 0 && !dirtySteps && (
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
                상태: <StatusBadge status={selected.status} /> · 대상 품목:{" "}
                {itemLabel(selected.itemId)}
                {!editable &&
                  (selected.status === "published"
                    ? " · 게시된 버전은 바꿀 수 없습니다. 바꾸려면 목록에서 개정하세요."
                    : " · 폐기된 버전은 바꿀 수 없습니다.")}
              </p>
              <DataTable
                rows={draftSteps.map((step, index) => ({
                  id: index,
                  pid: step.processId,
                  label: processLabel(step.processId),
                  standardCycleSec: step.standardCycleSec ?? null,
                  setupMinutes: step.setupMinutes ?? null,
                  isSubcontract: Boolean(step.isSubcontract),
                  subcontractorCode: step.subcontractorCode ?? null,
                  step,
                }))}
                columns={stepColumns}
                caption={`${selected.routeCode} v${selected.version} 공정 순서`}
                offset={0}
                total={draftSteps.length}
                limit={draftSteps.length || 1}
                onPage={() => undefined}
                empty={
                  editable ? (
                    <EmptyState
                      reason="공정이 없습니다. 공정이 없는 경로는 게시할 수 없습니다."
                      action="공정 추가"
                      onAction={() => openStepForm(selected.id, null)}
                    />
                  ) : (
                    <p className="muted">
                      공정이 없습니다. 공정이 없는 경로는 게시할 수 없습니다.
                    </p>
                  )
                }
              />
              {errors.steps && <p className="notice">{errors.steps}</p>}
            </DetailPanel>
          )}

          {panel?.kind === "step" && selected && (
            <FormPanel
              key={`step-${panel.stepIndex ?? "new"}`}
              title={
                panel.stepIndex !== null
                  ? `${selected.routeCode} · ${panel.stepIndex + 1}번째 공정 수정`
                  : `${selected.routeCode} 공정 추가`
              }
              guard={guard}
              onClose={() => openSteps(selected.id)}
              onSubmit={(e) => void submitStep(e)}
              actions={
                <>
                  <button type="submit" disabled={pending}>
                    {panel.stepIndex !== null ? "저장" : "추가"}
                  </button>
                  <button
                    type="button"
                    className="secondary"
                    onClick={() => guard.guard(() => openSteps(selected.id))}
                  >
                    공정 목록으로
                  </button>
                </>
              }
            >
              <ErrorNotice error={formError} />
              <div className="field">
                <label htmlFor="step-process">공정</label>
                <select
                  id="step-process"
                  value={stepForm.processId || processes[0]?.id || ""}
                  onChange={(e) =>
                    setStepForm({
                      ...stepForm,
                      processId: Number(e.target.value),
                    })
                  }
                >
                  {processes.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.processCode} {p.name}
                      {!p.isActive && " (사용 안 함)"}
                    </option>
                  ))}
                </select>
                {errors.processId && <small>{errors.processId}</small>}
              </div>
              <Field
                label="표준 사이클 타임 (초)"
                type="text"
                inputMode="decimal"
                value={stepForm.standardCycleSec}
                placeholder="예: 45.50 (소수 2자리 이내)"
                error={errors.standardCycleSec}
                onChange={(e) =>
                  setStepForm({
                    ...stepForm,
                    standardCycleSec: e.target.value,
                  })
                }
              />
              <Field
                label="준비 시간 (분)"
                type="number"
                min={0}
                value={stepForm.setupMinutes}
                placeholder="예: 15"
                error={errors.setupMinutes}
                onChange={(e) =>
                  setStepForm({
                    ...stepForm,
                    setupMinutes: e.target.value,
                  })
                }
              />
              <div className="field">
                <label className="inline-check" htmlFor="step-is-subcontract">
                  <input
                    id="step-is-subcontract"
                    type="checkbox"
                    checked={stepForm.isSubcontract}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setStepForm({
                        ...stepForm,
                        isSubcontract: checked,
                        subcontractorCode: checked
                          ? stepForm.subcontractorCode
                          : "",
                      });
                    }}
                  />
                  외주 공정
                </label>
              </div>
              {stepForm.isSubcontract && (
                <Field
                  label="외주처 코드"
                  value={stepForm.subcontractorCode}
                  maxLength={40}
                  placeholder="예: SC-VEND01"
                  error={errors.subcontractorCode}
                  onChange={(e) =>
                    setStepForm({
                      ...stepForm,
                      subcontractorCode: e.target.value,
                    })
                  }
                />
              )}
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
