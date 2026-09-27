// M-06 자재 투입 — 실행 중 공정에 자재 투입을 기록한다. BOM 기준 소요량을 제안하고 재고는 차감하지 않는다 (FS-020e)
import { useEffect, useState, type FormEvent } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  DataTable,
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
  MES,
  ModuleOff,
  moduleOff,
  useLists,
  useSend,
  type Equipment,
} from "./common";
import type { Lot } from "./Lots";

type Running = {
  id: number;
  lotId: number;
  lotNo: string;
  sequenceNo: number;
  processId: number;
  equipmentId: number;
};
type Item = {
  id: number;
  itemCode: string;
  name: string;
  baseUnit: string;
  conversions: { fromUnit: string }[];
};
type Process = { id: number; name: string };
type Requirement = {
  materialItemId: number;
  unit: string;
  qtyPerUnit: string;
  lossRate: string;
  requiredQty: string;
  issuedQty: string;
  suggestedQty: string;
};
type Issue = {
  id: number;
  materialItemId: number;
  materialLotNo: string | null;
  issuedQty: string;
  unit: string;
  issuedAt: string;
};

const num = (v: string) => Number(v).toLocaleString();

export function Materials() {
  const { fail } = useSession();
  const { data, error, reload } = useLists<
    [Running[], Item[], Process[], Equipment[], Lot[]]
  >(["/executions", "/items", "/processes", "/equipments", "/lots"]);
  const [selectedId, setSelectedId] = useState<number>();
  const [tick, setTick] = useState(0);
  const [detail, setDetail] = useState<{
    req: Requirement[];
    issues: Issue[];
  }>();
  const [detailError, setDetailError] = useState<unknown>();
  const [form, setForm] = useState({
    materialItemId: 0,
    materialLotId: "",
    issuedQty: "",
    unit: "",
  });
  const [panelOpen, setPanelOpen] = useState(false);

  const {
    send,
    pending,
    error: saveError,
    setError,
    deleteButtons,
  } = useSend(() => setTick((n) => n + 1));

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    const signal = controller.signal;
    setDetailError(undefined);
    Promise.all([
      api<Requirement[]>(`${MES}/executions/${selectedId}/bom-requirement`, {
        signal,
      }),
      api<Issue[]>(`${MES}/executions/${selectedId}/material-issues`, {
        signal,
      }),
    ])
      .then(([r, i]) => setDetail({ req: r.data, issues: i.data }))
      .catch((e) => {
        if (signal.aborted) return;
        setDetailError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [selectedId, tick]);

  const dirty = panelOpen && Boolean(form.issuedQty.trim());
  const guard = useDiscardGuard(dirty);

  if (moduleOff(error)) return <ModuleOff />;
  const [running, items, processes, equipments, lots] = data ?? [
    undefined,
    [],
    [],
    [],
    [],
  ];
  const errors = fieldErrors(saveError);
  const item = (id: number) => items.find((i) => i.id === id);
  const itemLabel = (id: number) => {
    const i = item(id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };
  const selected = running?.find((r) => r.id === selectedId);
  const selectedLot = selected && lots.find((l) => l.id === selected.lotId);
  const units = (id: number) => {
    const i = item(id);
    return i ? [i.baseUnit, ...i.conversions.map((c) => c.fromUnit)] : [];
  };
  const materialLots = lots.filter(
    (l) => l.itemId === form.materialItemId && l.status === "completed",
  );

  function select(id: number) {
    setSelectedId(id);
    setDetail(undefined);
    setError(undefined);
    const first = items[0];
    setForm({
      materialItemId: first?.id ?? 0,
      materialLotId: "",
      issuedQty: "",
      unit: first?.baseUnit ?? "",
    });
    setPanelOpen(true);
  }

  function fillSuggestion(r: Requirement) {
    setForm({
      materialItemId: r.materialItemId,
      materialLotId: "",
      issuedQty: String(Number(r.suggestedQty)),
      unit: r.unit,
    });
    setPanelOpen(true);
    setError(undefined);
  }

  function closePanel() {
    setPanelOpen(false);
    setError(undefined);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (pending || !selected) return;
    const ok = await send(
      `/executions/${selected.id}/material-issues`,
      "POST",
      {
        materialItemId: form.materialItemId,
        materialLotId: form.materialLotId ? Number(form.materialLotId) : null,
        issuedQty: form.issuedQty.trim(),
        unit: form.unit,
      },
    );
    if (ok) setForm({ ...form, materialLotId: "", issuedQty: "" });
  }

  const runningColumns: Column<Running>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={r.id === selectedId}
          onClick={() => guard.guard(() => select(r.id))}
        >
          투입
        </button>
      ),
    },
    {
      key: "processId",
      label: "공정",
      render: (r) =>
        `${r.sequenceNo}. ${processes.find((p) => p.id === r.processId)?.name ?? ""}`,
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) =>
        equipments.find((e) => e.id === r.equipmentId)?.equipmentCode ??
        r.equipmentId,
    },
  ];

  const reqColumns: Column<Requirement & { id: number }>[] = [
    {
      key: "materialItemId",
      label: "자재",
      render: (r) => itemLabel(r.materialItemId),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        Number(r.suggestedQty) > 0 ? (
          <button
            type="button"
            className="link-button"
            onClick={() => fillSuggestion(r)}
          >
            제안량 채우기
          </button>
        ) : (
          "투입 완료"
        ),
    },
    {
      key: "requiredQty",
      label: "기준 소요",
      render: (r) => `${num(r.requiredQty)} ${r.unit}`,
    },
    {
      key: "lossRate",
      label: "손실률",
      render: (r) => `${Number(r.lossRate)}%`,
    },
    {
      key: "issuedQty",
      label: "LOT 누적 투입",
      render: (r) => num(r.issuedQty),
    },
    { key: "suggestedQty", label: "제안", render: (r) => num(r.suggestedQty) },
  ];

  const issueColumns: Column<Issue>[] = [
    {
      key: "materialItemId",
      label: "자재",
      render: (r) => itemLabel(r.materialItemId),
    },
    {
      key: "id",
      label: "관리",
      render: (r) =>
        deleteButtons(
          `issue:${r.id}`,
          `/executions/${selectedId}/material-issues/${r.id}`,
        ),
    },
    {
      key: "issuedQty",
      label: "투입",
      render: (r) => `${num(r.issuedQty)} ${r.unit}`,
    },
    {
      key: "materialLotNo",
      label: "자재 LOT",
      render: (r) => r.materialLotNo ?? "지정 안 함",
    },
  ];

  return (
    <div className="page-fill">
      <PageTitle
        id="M-06"
        title="자재 투입"
        subtitle="실행 중인 공정에 들어간 자재를 기록합니다"
        help="mes/m-06"
      />
      <p className="notice" role="note">
        투입 기록만 남기며 MES는 재고를 차감하지 않습니다. 재고 차감은 공정
        실행이 완료된 뒤 WMS가 이 기록을 반영할 때 합니다(WMS 원천 반영).
      </p>
      {!panelOpen && (
        <ErrorNotice
          error={Object.keys(errors).length ? undefined : saveError}
        />
      )}
      <ErrorNotice error={error} retry={reload} />
      {!running ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="section-block">
              <DataTable
                rows={running}
                columns={runningColumns}
                caption="실행 중인 공정"
                offset={0}
                total={running.length}
                limit={running.length || 1}
                onPage={() => undefined}
                empty={
                  <p className="muted">
                    실행 중인 공정이 없습니다. 투입은 실적을 확정하기 전
                    공정에만 기록합니다.
                  </p>
                }
              />
            </div>
            {selected && (
              <div className="section-block">
                <div className="section-heading">
                  <h2>
                    {selected.lotNo} ·{" "}
                    {processes.find((p) => p.id === selected.processId)?.name}{" "}
                    투입 상세
                  </h2>
                  {!panelOpen && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setPanelOpen(true)}
                    >
                      투입 기록 열기
                    </button>
                  )}
                </div>
                {selectedLot && (
                  <p className="muted" role="note">
                    LOT 계획 {num(selectedLot.planQty)} {selectedLot.unit} 기준
                  </p>
                )}
                {detailError ? (
                  <ErrorNotice error={detailError} />
                ) : !detail ? (
                  <Loading />
                ) : (
                  <>
                    <DataTable
                      rows={detail.issues}
                      columns={issueColumns}
                      caption="이 공정의 투입 기록"
                      offset={0}
                      total={detail.issues.length}
                      limit={detail.issues.length || 1}
                      onPage={() => undefined}
                      empty={
                        <p className="muted">아직 투입 기록이 없습니다.</p>
                      }
                    />
                  </>
                )}
              </div>
            )}
            {!selected && (
              <p className="muted" role="note">
                실행 중 공정의 &quot;투입&quot;을 누르세요.
              </p>
            )}
          </section>
          {panelOpen && selected && (
            <FormPanel
              title="자재 투입 등록"
              guard={guard}
              onClose={closePanel}
              onSubmit={(e) => void submit(e)}
              actions={
                <>
                  <button type="submit" disabled={pending} aria-busy={pending}>
                    투입 기록
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
              <p className="muted">{selected.lotNo} 자재 투입</p>
              {/* 제안량 채우기는 입력과 같은 패널에 둔다. 겹침 화면에서 목록 쪽 버튼은 패널에 가려진다. */}
              {detail &&
                (detail.req.length === 0 ? (
                  <p className="notice">
                    BOM 없이 발행된 지시라 기준 소요량이 없습니다. 투입량을 직접
                    입력하세요.
                  </p>
                ) : (
                  <div className="section-block">
                    <DataTable
                      rows={detail.req.map((r) => ({
                        ...r,
                        id: r.materialItemId,
                      }))}
                      columns={reqColumns}
                      caption="BOM 기준 소요량"
                      offset={0}
                      total={detail.req.length}
                      limit={detail.req.length}
                      onPage={() => undefined}
                      empty={null}
                    />
                  </div>
                ))}
              <ErrorNotice
                error={Object.keys(errors).length ? undefined : saveError}
              />
              <div className="field">
                <label htmlFor="issue-item">자재</label>
                <select
                  id="issue-item"
                  value={form.materialItemId}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setForm({
                      ...form,
                      materialItemId: id,
                      materialLotId: "",
                      unit: item(id)?.baseUnit ?? "",
                    });
                  }}
                >
                  {items.map((i) => (
                    <option key={i.id} value={i.id}>
                      {i.itemCode} {i.name}
                    </option>
                  ))}
                </select>
                {errors.materialItemId && (
                  <small>{errors.materialItemId}</small>
                )}
              </div>
              <Field
                label="투입 수량"
                value={form.issuedQty}
                required
                inputMode="decimal"
                error={errors.issuedQty}
                onChange={(e) =>
                  setForm({ ...form, issuedQty: e.target.value })
                }
              />
              <div className="field">
                <label htmlFor="issue-unit">단위</label>
                <select
                  id="issue-unit"
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                >
                  {units(form.materialItemId).map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
                {errors.unit && <small>{errors.unit}</small>}
              </div>
              <div className="field">
                <label htmlFor="issue-lot">자재 LOT (선택)</label>
                <select
                  id="issue-lot"
                  value={form.materialLotId}
                  onChange={(e) =>
                    setForm({ ...form, materialLotId: e.target.value })
                  }
                >
                  <option value="">지정 안 함 (품목 단위 투입)</option>
                  {materialLots.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.lotNo}
                    </option>
                  ))}
                </select>
                {errors.materialLotId && <small>{errors.materialLotId}</small>}
              </div>
              <p className="muted">
                LOT을 지정하지 않은 같은 자재는 한 공정에 한 번만 기록합니다.
                바꾸려면 기존 기록을 지우고 다시 입력하세요.
              </p>
            </FormPanel>
          )}
        </div>
      )}
    </div>
  );
}
