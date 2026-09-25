// M-14 공정 경로 — 품목별 공정 순서의 버전 관리(초안 → 게시 → 폐기) (FS-020b)
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

type Step = { id: number; processId: number; sequenceNo: number };
export type Route = {
  id: number;
  itemId: number;
  routeCode: string;
  version: number;
  status: VersionStatus;
  publishedAt: string | null;
  steps: Step[];
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
  const [selectedId, setSelectedId] = useState<number>();
  const [steps, setSteps] = useState<number[]>();
  const [adding, setAdding] = useState<number>();
  const [create, setCreate] = useState({ itemId: 0, routeCode: "" });

  if (moduleOff(error)) return <ModuleOff />;
  const [routes, items, processes] = data ?? [undefined, [], []];
  const selected = routes?.find((r) => r.id === selectedId);
  const draftSteps = steps ?? selected?.steps.map((s) => s.processId) ?? [];
  const errors = fieldErrors(saveError);
  const itemLabel = (id: number) => {
    const item = items.find((i) => i.id === id);
    return item ? `${item.itemCode} ${item.name}` : String(id);
  };
  const processLabel = (id: number) => {
    const p = processes.find((x) => x.id === id);
    return p ? `${p.processCode} ${p.name}` : String(id);
  };

  function select(id: number | undefined) {
    setSelectedId(id);
    setSteps(undefined);
    setError(undefined);
  }

  async function revise(row: Route) {
    const created = await send<Route>(`/routes/${row.id}/revise`, "POST");
    if (created) select(created.id);
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
      setCreate({ itemId: 0, routeCode: "" });
      select(created.id);
    }
  }

  function move(index: number, delta: number) {
    const next = [...draftSteps];
    const [taken] = next.splice(index, 1);
    next.splice(index + delta, 0, taken);
    setSteps(next);
  }

  async function saveSteps() {
    if (!selected || pending) return;
    const saved = await send(`/routes/${selected.id}/steps`, "PUT", {
      processIds: draftSteps,
    });
    if (saved) setSteps(undefined);
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
            onClick={() => select(r.id)}
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

  const editable = selected?.status === "draft";
  const stepColumns: Column<{ id: number; pid: number; label: string }>[] = [
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
              onClick={() => setSteps(draftSteps.filter((_, i) => i !== r.id))}
            >
              빼기
            </button>
          </span>
        ) : (
          "-"
        ),
    },
    { key: "label", label: "공정" },
  ];
  const dirty =
    steps !== undefined &&
    JSON.stringify(steps) !==
      JSON.stringify(selected?.steps.map((s) => s.processId));

  return (
    <>
      <PageTitle
        id="M-14"
        title="공정 경로"
        subtitle="품목을 만드는 공정 순서를 버전으로 관리합니다"
        help="mes/m-14"
      />
      <MesOrder />
      <p className="muted">
        게시된 경로만 작업지시에서 고를 수 있습니다. 게시·폐기된 버전은 바꿀 수
        없고, 바꾸려면 개정해서 새 버전(초안)으로 편집합니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!routes ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
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
                    reason="등록된 공정 경로가 없습니다. 우측 폼에서 첫 경로를 만드세요."
                    to="#route-form"
                    action="경로 만들기"
                  />
                }
              />
            </section>
            <form
              id="route-form"
              className="panel"
              aria-label="공정 경로 만들기"
              onSubmit={(e) => void submitCreate(e)}
            >
              <h2>새 공정 경로</h2>
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
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  만들기
                </button>
              </div>
            </form>
          </div>

          {selected ? (
            <section className="panel" aria-label="공정 순서">
              <h2>
                {selected.routeCode} v{selected.version} 공정 순서{" "}
                <StatusBadge status={selected.status} />
              </h2>
              {!editable && (
                <p className="muted">
                  {selected.status === "published" ? "게시" : "폐기"}된 버전은
                  바꿀 수 없습니다. 바꾸려면 목록에서 개정하세요.
                </p>
              )}
              <DataTable
                rows={draftSteps.map((pid, index) => ({
                  id: index,
                  pid,
                  label: processLabel(pid),
                }))}
                columns={stepColumns}
                caption={`${selected.routeCode} v${selected.version} 공정 순서`}
                offset={0}
                total={draftSteps.length}
                limit={draftSteps.length || 1}
                onPage={() => undefined}
                empty={
                  <p className="muted">
                    공정이 없습니다. 공정이 없는 경로는 게시할 수 없습니다.
                  </p>
                }
              />
              {errors.steps && <p className="notice">{errors.steps}</p>}
              {editable && (
                <div className="field">
                  <label htmlFor="route-add">추가할 공정</label>
                  <select
                    id="route-add"
                    value={adding ?? processes[0]?.id ?? ""}
                    onChange={(e) => setAdding(Number(e.target.value))}
                  >
                    {processes.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.processCode} {p.name}
                        {!p.isActive && " (사용 안 함)"}
                      </option>
                    ))}
                  </select>
                </div>
              )}
              {editable && (
                <div className="form-actions">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      setSteps([...draftSteps, adding ?? processes[0].id])
                    }
                  >
                    공정 추가
                  </button>
                  <button
                    type="button"
                    disabled={pending || !dirty}
                    onClick={() => void saveSteps()}
                  >
                    순서 저장
                  </button>
                </div>
              )}
            </section>
          ) : (
            <p className="muted">
              목록에서 &quot;공정&quot;을 누르면 그 버전의 공정 순서를 보고,
              초안이면 편집할 수 있습니다.
            </p>
          )}
        </>
      )}
    </>
  );
}
