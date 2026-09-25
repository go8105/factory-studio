// M-05 공정 실행 — 다음 공정 시작(허용·비어 있는 설비)과 실행 중 공정의 실적 확정(완료) (FS-020d)
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
  routeStepId: number;
  sequenceNo: number;
  processId: number;
  equipmentId: number;
  startedAt: string;
  unit: string;
};
type Process = {
  id: number;
  processCode: string;
  name: string;
  equipmentIds: number[];
};
type Item = { id: number; itemCode: string; name: string };

const num = (v: string) => Number(v).toLocaleString();
const time = (v: string) =>
  new Date(v).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });

export function Executions() {
  const { data, error, reload } = useLists<
    [Lot[], Running[], Process[], Equipment[], Item[]]
  >(["/lots", "/executions", "/processes", "/equipments", "/items"]);
  const { send, pending, error: saveError, setError } = useSend(reload);
  const [starting, setStarting] = useState<{
    lotId: number;
    equipmentId: number;
  }>();
  const [confirming, setConfirming] = useState<{
    id: number;
    good: string;
    defect: string;
    reason: string;
  }>();

  if (moduleOff(error)) return <ModuleOff />;
  const [lots, running, processes, equipments, items] = data ?? [
    undefined,
    [],
    [],
    [],
    [],
  ];
  const errors = fieldErrors(saveError);
  const process = (id: number) => processes.find((p) => p.id === id);
  const equipment = (id: number) => equipments.find((e) => e.id === id);
  const busyLot = (equipmentId: number) =>
    running.find((r) => r.equipmentId === equipmentId)?.lotNo;
  const lot = (id: number) => lots?.find((l) => l.id === id);
  const itemCode = (id: number) =>
    items.find((i) => i.id === id)?.itemCode ?? id;

  const startable = (lots ?? []).filter(
    (l) =>
      l.nextStep &&
      !l.running &&
      ["released", "in_progress"].includes(l.orderStatus),
  );
  const startLot = starting && lot(starting.lotId);
  const startProcess =
    startLot?.nextStep && process(startLot.nextStep.processId);
  // 이 공정에 허용되고 사용 중(isActive)인 설비만 고른다. 다른 LOT이 쓰는 설비는 고를 수 없다(M-G07).
  const choices = (startProcess?.equipmentIds ?? [])
    .map(equipment)
    .filter((e): e is Equipment => !!e && e.isActive);

  const confirmRun = confirming && running.find((r) => r.id === confirming.id);
  const confirmLot = confirmRun && lot(confirmRun.lotId);
  const inputQty = confirmLot?.running?.inputQty ?? null;

  function openStart(l: Lot) {
    const allowed = (process(l.nextStep!.processId)?.equipmentIds ?? [])
      .map(equipment)
      .filter((e): e is Equipment => !!e && e.isActive);
    const free = allowed.find((e) => !busyLot(e.id)) ?? allowed[0];
    setStarting({ lotId: l.id, equipmentId: free?.id ?? 0 });
    setConfirming(undefined);
    setError(undefined);
  }

  async function submitStart(event: FormEvent) {
    event.preventDefault();
    if (pending || !startLot?.nextStep || !starting) return;
    const ok = await send(`/lots/${startLot.id}/executions`, "POST", {
      routeStepId: startLot.nextStep.routeStepId,
      equipmentId: starting.equipmentId,
    });
    if (ok) setStarting(undefined);
  }

  async function submitConfirm(event: FormEvent) {
    event.preventDefault();
    if (pending || !confirming) return;
    const ok = await send(`/executions/${confirming.id}/result`, "POST", {
      goodQty: confirming.good.trim(),
      defectQty: confirming.defect.trim() || "0",
      defectReason: confirming.reason.trim() || null,
    });
    if (ok) setConfirming(undefined);
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
          onClick={() => {
            setConfirming({ id: r.id, good: "", defect: "0", reason: "" });
            setStarting(undefined);
            setError(undefined);
          }}
        >
          실적 확정
        </button>
      ),
    },
    {
      key: "processId",
      label: "공정",
      render: (r) =>
        `${r.sequenceNo}. ${process(r.processId)?.name ?? r.processId}`,
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) => equipment(r.equipmentId)?.equipmentCode ?? r.equipmentId,
    },
    { key: "startedAt", label: "시작", render: (r) => time(r.startedAt) },
  ];
  const startColumns: Column<Lot>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => openStart(r)}
        >
          시작
        </button>
      ),
    },
    {
      key: "nextStep",
      label: "다음 공정",
      render: (r) =>
        `${r.nextStep!.sequenceNo}/${r.stepCount} ${process(r.nextStep!.processId)?.name ?? ""}`,
    },
    { key: "itemId", label: "품목", render: (r) => itemCode(r.itemId) },
    {
      key: "planQty",
      label: "투입 예정",
      render: (r) => `${num(r.nextStep!.inputQty)} ${r.unit}`,
    },
  ];

  return (
    <>
      <PageTitle
        id="M-05"
        title="공정 실행"
        subtitle="경로 순서대로 공정을 시작하고, 끝나면 실적을 확정합니다"
        help="mes/m-05"
      />
      <p className="muted">
        공정은 경로 순서대로만 시작하며, 설비는 그 공정에 허용된 사용 중 설비만
        고릅니다. 한 설비에서는 한 번에 한 공정만 실행합니다. 시작·종료 시각은
        서버가 기록하고, FEMS 설비별 에너지와는 설비·시간으로만 대응합니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!lots ? (
        !error && <Loading />
      ) : (
        <div className="master-grid">
          <section>
            <h2>실행 중</h2>
            <DataTable
              rows={running}
              columns={runningColumns}
              caption="실행 중인 공정"
              offset={0}
              total={running.length}
              limit={running.length || 1}
              onPage={() => undefined}
              empty={<p className="muted">실행 중인 공정이 없습니다.</p>}
            />
            <h2>시작할 수 있는 LOT</h2>
            <DataTable
              rows={startable}
              columns={startColumns}
              caption="시작할 수 있는 LOT"
              offset={0}
              total={startable.length}
              limit={startable.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="다음 공정을 시작할 LOT이 없습니다. 작업지시를 발행하면 LOT이 생깁니다."
                  to="/mes/work-orders"
                  action="작업지시 화면으로"
                />
              }
            />
          </section>
          {startLot?.nextStep && starting ? (
            <form
              className="panel"
              aria-label="공정 시작"
              onSubmit={(e) => void submitStart(e)}
            >
              <h2>
                {startLot.lotNo} · {startLot.nextStep.sequenceNo}번째{" "}
                {startProcess?.name} 시작
              </h2>
              <p className="muted">
                투입 {num(startLot.nextStep.inputQty)} {startLot.unit}
                {startLot.nextStep.sequenceNo === 1
                  ? " (지시 수량)"
                  : " (직전 공정 양품)"}
              </p>
              {choices.length === 0 ? (
                <p className="notice">
                  이 공정에 허용된 사용 중 설비가 없습니다. 공정·설비 화면에서
                  허용 설비를 확인하세요.
                </p>
              ) : (
                <div className="field">
                  <label htmlFor="start-equipment">설비</label>
                  <select
                    id="start-equipment"
                    value={starting.equipmentId}
                    onChange={(e) =>
                      setStarting({
                        ...starting,
                        equipmentId: Number(e.target.value),
                      })
                    }
                  >
                    {choices.map((e) => (
                      <option
                        key={e.id}
                        value={e.id}
                        disabled={!!busyLot(e.id)}
                      >
                        {e.equipmentCode} {e.name}
                        {busyLot(e.id) ? ` (사용 중: ${busyLot(e.id)})` : ""}
                      </option>
                    ))}
                  </select>
                  {errors.equipmentId && <small>{errors.equipmentId}</small>}
                </div>
              )}
              <div className="form-actions">
                <button
                  type="submit"
                  disabled={
                    pending ||
                    !choices.some(
                      (e) => e.id === starting.equipmentId && !busyLot(e.id),
                    )
                  }
                >
                  시작
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setStarting(undefined)}
                >
                  닫기
                </button>
              </div>
            </form>
          ) : confirmRun && confirming ? (
            <form
              className="panel"
              aria-label="실적 확정"
              onSubmit={(e) => void submitConfirm(e)}
            >
              <h2>
                {confirmRun.lotNo} · {process(confirmRun.processId)?.name} 실적
              </h2>
              <p className="muted">
                {inputQty !== null &&
                  `투입 ${num(inputQty)} ${confirmRun.unit}${confirmRun.sequenceNo === 1 ? " (지시 수량)" : " (직전 공정 양품)"}. `}
                양품 + 불량 = 투입이어야 하고, 확정 후에는 고칠 수 없습니다.
                품질 검사는 QMS 영역으로 범위에서 제외했으므로 작업자가 직접
                판정합니다.
              </p>
              <Field
                label="양품"
                value={confirming.good}
                required
                inputMode="decimal"
                error={errors.goodQty}
                onChange={(e) =>
                  setConfirming({ ...confirming, good: e.target.value })
                }
              />
              <Field
                label="불량"
                value={confirming.defect}
                inputMode="decimal"
                error={errors.defectQty}
                onChange={(e) =>
                  setConfirming({ ...confirming, defect: e.target.value })
                }
              />
              <Field
                label="불량 사유"
                value={confirming.reason}
                maxLength={300}
                required={Number(confirming.defect) > 0}
                error={errors.defectReason}
                onChange={(e) =>
                  setConfirming({ ...confirming, reason: e.target.value })
                }
              />
              <div className="form-actions">
                <button type="submit" disabled={pending}>
                  확정
                </button>
                <button
                  type="button"
                  className="link-button"
                  onClick={() => setConfirming(undefined)}
                >
                  닫기
                </button>
              </div>
            </form>
          ) : (
            <p className="muted">
              시작할 LOT의 &quot;시작&quot; 또는 실행 중 공정의 &quot;실적
              확정&quot;을 누르세요.
            </p>
          )}
        </div>
      )}
    </>
  );
}
