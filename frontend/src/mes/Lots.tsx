// M-04 LOT 현황 — LOT 목록과 한 화면 추적 이력(공정·설비·실적·투입 자재) (FS-020d)
import { useEffect, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  EmptyState,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import { MES, ModuleOff, moduleOff, useLists, type Equipment } from "./common";

export type Step = {
  routeStepId: number;
  sequenceNo: number;
  processId: number;
  executionId: number | null;
  equipmentId: number | null;
  executionStatus: "running" | "completed" | null;
  startedAt: string | null;
  endedAt: string | null;
  inputQty: string | null;
  goodQty: string | null;
  defectQty: string | null;
  defectReason: string | null;
  materialIssues?: {
    id: number;
    materialItemId: number;
    issuedQty: string;
    unit: string;
  }[];
};
export type Lot = {
  id: number;
  lotNo: string;
  status: "ready" | "in_progress" | "completed";
  completionReason: "normal" | "all_defective" | null;
  workOrderId: number;
  orderNo: string;
  itemId: number;
  planQty: string;
  orderStatus: string;
  routeCode: string;
  routeVersion: number;
  unit: string;
  stepCount: number;
  completedSteps: number;
  finalGoodQty: string | null;
  running: Step | null;
  nextStep: (Step & { inputQty: string }) | null;
  steps?: Step[];
  // QMS 조회(FS-023 D9·D10). QMS를 끄면 null.
  qualityHold?: boolean | null;
  qualityResult?: "PASS" | "FAIL" | null;
};
type Named = { id: number; name: string };
type Item = Named & { itemCode: string };
type Process = Named & { processCode: string };

const num = (v: string | null) =>
  v === null ? "-" : Number(v).toLocaleString();

export function LotStatus({ lot }: { lot: Lot }) {
  if (lot.status === "completed")
    return lot.completionReason === "all_defective" ? (
      <Badge tone="issue">전량 불량 종결</Badge>
    ) : (
      <Badge>완료</Badge>
    );
  return lot.status === "ready" ? (
    <Badge tone="warning">대기</Badge>
  ) : (
    <Badge>진행</Badge>
  );
}

export function Lots() {
  const { fail } = useSession();
  const { data, error, reload } = useLists<
    [Lot[], Item[], Process[], Equipment[]]
  >(["/lots", "/items", "/processes", "/equipments"]);
  const [selectedId, setSelectedId] = useState<number>();
  const [detail, setDetail] = useState<Lot>();
  const [detailError, setDetailError] = useState<unknown>();
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    setDetail(undefined);
    setDetailError(undefined);
    api<Lot>(`${MES}/lots/${selectedId}`, { signal: controller.signal })
      .then((r) => setDetail(r.data))
      .catch((e) => {
        if (controller.signal.aborted) return;
        setDetailError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      });
    return () => controller.abort();
  }, [selectedId]);

  if (moduleOff(error)) return <ModuleOff />;
  const [lots, items, processes, equipments] = data ?? [undefined, [], [], []];
  const itemLabel = (id: number) => {
    const i = items.find((x) => x.id === id);
    return i ? `${i.itemCode} ${i.name}` : String(id);
  };
  const processName = (id: number) =>
    processes.find((p) => p.id === id)?.name ?? String(id);
  const equipmentCode = (id: number | null) =>
    id === null
      ? "-"
      : (equipments.find((e) => e.id === id)?.equipmentCode ?? String(id));

  const shown = (lots ?? []).filter(
    (l) => !statusFilter || l.status === statusFilter,
  );
  const columns: Column<Lot>[] = [
    { key: "lotNo", label: "LOT" },
    {
      key: "id",
      label: "관리",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          aria-pressed={r.id === selectedId}
          onClick={() => setSelectedId(r.id)}
        >
          이력
        </button>
      ),
    },
    {
      key: "status",
      label: "상태",
      render: (r) => (
        <>
          <LotStatus lot={r} />{" "}
          {r.qualityHold && <Badge tone="issue">QMS 보류</Badge>}
        </>
      ),
    },
    { key: "orderNo", label: "지시" },
    { key: "itemId", label: "품목", render: (r) => itemLabel(r.itemId) },
    {
      key: "completedSteps",
      label: "진행",
      render: (r) => `${r.completedSteps}/${r.stepCount}`,
    },
    {
      key: "finalGoodQty",
      label: "최종 양품",
      render: (r) => num(r.finalGoodQty),
    },
  ];

  // 전량 불량으로 끝난 LOT의 남은 단계는 '투입 없음으로 미실행'이다(FS-006).
  const stepState = (lot: Lot, s: Step) =>
    s.executionStatus === "completed"
      ? "완료"
      : s.executionStatus === "running"
        ? "진행 중"
        : lot.completionReason === "all_defective"
          ? "투입 없음으로 미실행"
          : "대기";
  const stepColumns: Column<Step & { id: number }>[] = [
    { key: "sequenceNo", label: "순서" },
    {
      key: "processId",
      label: "공정",
      render: (r) => processName(r.processId),
    },
    {
      key: "executionStatus",
      label: "상태",
      render: (r) => stepState(detail!, r),
    },
    {
      key: "equipmentId",
      label: "설비",
      render: (r) => equipmentCode(r.equipmentId),
    },
    {
      key: "inputQty",
      label: "투입",
      render: (r) => num(r.executionStatus === "completed" ? r.inputQty : null),
    },
    { key: "goodQty", label: "양품", render: (r) => num(r.goodQty) },
    { key: "defectQty", label: "불량", render: (r) => num(r.defectQty) },
    {
      key: "defectReason",
      label: "불량 사유",
      render: (r) => r.defectReason ?? "-",
    },
    {
      key: "materialIssues",
      label: "투입 자재",
      render: (r) =>
        r.materialIssues?.length
          ? r.materialIssues
              .map(
                (m) =>
                  `${items.find((i) => i.id === m.materialItemId)?.itemCode ?? m.materialItemId} ${num(m.issuedQty)} ${m.unit}`,
              )
              .join(", ")
          : "-",
    },
  ];

  // 읽기 전용 상세 기준 화면(UI-03): 목록 + "이력"으로 여는 넓은 상세 패널(폼 없음).
  return (
    <div className="page-fill">
      <PageTitle
        id="M-04"
        title="LOT 현황"
        subtitle="LOT마다 거친 공정·설비·실적·투입 자재를 한 화면에서 추적합니다"
        help="mes/m-04"
      />
      <p className="muted" role="note">
        한 작업지시는 한 LOT으로 생산합니다(분할 생산 없음).
      </p>
      <ErrorNotice error={error} retry={reload} />
      {!lots ? (
        !error && <Loading />
      ) : (
        <div className="split-view fill">
          <section className="fill">
            <div className="filter-bar">
              <label>
                상태
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  <option value="">전체</option>
                  <option value="ready">대기</option>
                  <option value="in_progress">진행</option>
                  <option value="completed">완료</option>
                </select>
              </label>
            </div>
            <DataTable
              rows={shown}
              columns={columns}
              caption="LOT 목록"
              offset={0}
              total={shown.length}
              limit={shown.length || 1}
              onPage={() => undefined}
              empty={
                <EmptyState
                  reason="LOT이 없습니다. 작업지시를 발행하면 LOT이 만들어집니다."
                  to="/mes/work-orders"
                  action="작업지시 화면으로"
                />
              }
            />
          </section>
          {selectedId && (
            <DetailPanel
              wide
              key={selectedId}
              title={detail ? `${detail.lotNo} 이력` : "LOT 이력"}
              onClose={() => setSelectedId(undefined)}
            >
              {detailError ? (
                <ErrorNotice error={detailError} />
              ) : !detail ? (
                <Loading />
              ) : (
                <>
                  <p>
                    <LotStatus lot={detail} />
                  </p>
                  <p className="muted">
                    지시 {detail.orderNo} · {itemLabel(detail.itemId)} · 계획{" "}
                    {num(detail.planQty)} {detail.unit} · 경로{" "}
                    {detail.routeCode} v{detail.routeVersion}
                    {detail.finalGoodQty !== null &&
                      ` · 최종 양품 ${num(detail.finalGoodQty)}`}
                    {detail.qualityHold !== null &&
                      detail.qualityHold !== undefined &&
                      ` · 품질 판정 ${
                        detail.qualityResult === "PASS"
                          ? "합격"
                          : detail.qualityResult === "FAIL"
                            ? "불합격"
                            : "미검사"
                      }${detail.qualityHold ? " (QMS 보류 중)" : ""}`}
                  </p>
                  <DataTable
                    rows={(detail.steps ?? []).map((s) => ({
                      ...s,
                      id: s.routeStepId,
                    }))}
                    columns={stepColumns}
                    caption={`${detail.lotNo} 공정 이력`}
                    offset={0}
                    total={detail.steps?.length ?? 0}
                    limit={detail.steps?.length || 1}
                    onPage={() => undefined}
                    empty={<p className="muted">경로에 공정이 없습니다.</p>}
                  />
                </>
              )}
            </DetailPanel>
          )}
        </div>
      )}
    </div>
  );
}
