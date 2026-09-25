// M-07 실적 확정 — 실행 중 공정의 양품·불량을 확정하고, 확정된 실적을 조회한다 (FS-020e)
import { useState } from "react";
import {
  Badge,
  DataTable,
  ErrorNotice,
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
import { ResultForm } from "./ResultForm";

type Running = {
  id: number;
  lotId: number;
  lotNo: string;
  sequenceNo: number;
  processId: number;
  equipmentId: number;
  unit: string;
};
type Result = {
  id: number;
  lotNo: string;
  completionReason: string | null;
  sequenceNo: number;
  processId: number;
  equipmentId: number;
  inputQty: string;
  goodQty: string;
  defectQty: string;
  unit: string;
  defectReason: string | null;
  confirmedAt: string;
};
type Process = { id: number; name: string };

const num = (v: string) => Number(v).toLocaleString();

export function Results() {
  const { data, error, reload } = useLists<
    [Running[], Result[], Lot[], Process[], Equipment[]]
  >(["/executions", "/results", "/lots", "/processes", "/equipments"]);
  const { send, pending, error: saveError } = useSend(reload);
  const [confirmingId, setConfirmingId] = useState<number>();
  const [defectsOnly, setDefectsOnly] = useState(false);

  if (moduleOff(error)) return <ModuleOff />;
  const [running, results, lots, processes, equipments] = data ?? [
    undefined,
    [],
    [],
    [],
    [],
  ];
  const errors = fieldErrors(saveError);
  const processName = (id: number) =>
    processes.find((p) => p.id === id)?.name ?? String(id);
  const equipmentCode = (id: number) =>
    equipments.find((e) => e.id === id)?.equipmentCode ?? String(id);
  const confirming = running?.find((r) => r.id === confirmingId);
  const confirmingLot =
    confirming && lots.find((l) => l.id === confirming.lotId);
  const shown = results.filter((r) => !defectsOnly || Number(r.defectQty) > 0);

  const runningColumns: Column<Running>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => setConfirmingId(r.id)}
        >
          실적 확정
        </button>
      ),
    },
    {
      key: "processId",
      label: "공정",
      render: (r) => `${r.sequenceNo}. ${processName(r.processId)}`,
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) => equipmentCode(r.equipmentId),
    },
  ];
  const resultColumns: Column<Result>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "processId",
      label: "공정",
      render: (r) => `${r.sequenceNo}. ${processName(r.processId)}`,
    },
    { key: "inputQty", label: "투입", render: (r) => num(r.inputQty) },
    { key: "goodQty", label: "양품", render: (r) => num(r.goodQty) },
    {
      key: "defectQty",
      label: "불량",
      render: (r) =>
        Number(r.goodQty) === 0 ? (
          <Badge tone="issue">전량 불량 {num(r.defectQty)}</Badge>
        ) : (
          num(r.defectQty)
        ),
    },
    {
      key: "defectReason",
      label: "불량률·사유",
      render: (r) =>
        Number(r.defectQty) > 0
          ? `${((Number(r.defectQty) / Number(r.inputQty)) * 100).toFixed(1)}% · ${r.defectReason}`
          : "-",
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) => equipmentCode(r.equipmentId),
    },
    {
      key: "confirmedAt",
      label: "확정",
      render: (r) => new Date(r.confirmedAt).toLocaleDateString("ko-KR"),
    },
  ];

  return (
    <>
      <PageTitle
        id="M-07"
        title="실적 확정"
        subtitle="공정의 투입·양품·불량을 확정합니다. 확정하면 공정이 끝납니다"
        help="mes/m-07"
      />
      <p className="notice" role="note">
        품질 검사는 QMS 영역으로 범위에서 제외했습니다. 양품·불량은 작업자가
        직접 판정하며, 확정한 실적은 고치지 않습니다.
      </p>
      <ErrorNotice error={Object.keys(errors).length ? undefined : saveError} />
      <ErrorNotice error={error} retry={reload} />
      {!running ? (
        !error && <Loading />
      ) : (
        <>
          <div className="master-grid">
            <section>
              <DataTable
                rows={running}
                columns={runningColumns}
                caption="확정을 기다리는 공정"
                offset={0}
                total={running.length}
                limit={running.length || 1}
                onPage={() => undefined}
                empty={<p className="muted">실행 중인 공정이 없습니다.</p>}
              />
            </section>
            {confirming ? (
              <ResultForm
                key={confirming.id}
                executionId={confirming.id}
                title={`${confirming.lotNo} · ${processName(confirming.processId)} 실적`}
                inputQty={confirmingLot?.running?.inputQty ?? null}
                unit={confirming.unit}
                sequenceNo={confirming.sequenceNo}
                send={send}
                pending={pending}
                errors={errors}
                onClose={() => setConfirmingId(undefined)}
              />
            ) : (
              <p className="muted">
                확정할 공정의 &quot;실적 확정&quot;을 누르세요.
              </p>
            )}
          </div>
          <section>
            <h2>확정된 실적</h2>
            <label className="inline-check">
              <input
                type="checkbox"
                checked={defectsOnly}
                onChange={(e) => setDefectsOnly(e.target.checked)}
              />
              불량이 있는 실적만
            </label>
            <DataTable
              rows={shown}
              columns={resultColumns}
              caption="확정된 실적"
              offset={0}
              total={shown.length}
              limit={shown.length || 1}
              onPage={() => undefined}
              empty={<p className="muted">확정된 실적이 없습니다.</p>}
            />
          </section>
        </>
      )}
    </>
  );
}
