// W-11 적치 — 입고 완료 물품의 적치 작업 목록·실시간 추천 위치·적치 완료 및 취소 (DSN-13 F14).
// 추천 위치는 목록 조회 시 현재 재고·위치 용량·혼적 규칙에 따라 실시간 산출된다.
// 적치 완료 시 추천 위치를 기본 선택하되 사용자가 변경할 수 있으며, 확정 시 PUTAWAY 재고 전표가 생성된다.
import { useEffect, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useSession } from "../app/session";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  ErrorNotice,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  fieldErrors,
  num,
  PUTAWAY_STATUS_LABEL,
  time,
  useLists,
  WMS,
  type Item,
  type Location,
  type PutawayStatus,
  type PutawayTask,
  type Warehouse,
} from "./common";

const LIMIT = 50;

export function Putaways() {
  const { session } = useSession();
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const statusFilter = (params.get("status") as PutawayStatus | null) ?? "";
  const warehouseFilter = params.get("warehouseId") ?? "";
  const itemFilter = params.get("itemId") ?? "";

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.set("page", "1");
    setParams(next);
  };

  const { data: meta } = useLists<[Warehouse[], Item[]]>([
    "/warehouses",
    "/items",
  ]);
  const warehouses = meta?.[0] ?? [];
  const items = meta?.[1] ?? [];

  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(LIMIT),
  });
  if (statusFilter) query.set("status", statusFilter);
  if (warehouseFilter) query.set("warehouseId", warehouseFilter);
  if (itemFilter) query.set("itemId", itemFilter);

  const { data: taskEnvelope, reload } = useLists<
    [{ rows: PutawayTask[]; total: number; page: number; pageSize: number }]
  >([`/putaway-tasks?${query.toString()}`]);

  const [selectedTask, setSelectedTask] = useState<PutawayTask | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [toLocationId, setToLocationId] = useState<string>("");
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<unknown>();

  const openTask = (task: PutawayTask) => {
    setSelectedTask(task);
    setActionError(undefined);
    setToLocationId(
      task.suggestedLocationId ? String(task.suggestedLocationId) : "",
    );
  };

  useEffect(() => {
    if (!selectedTask || selectedTask.status !== "OPEN") {
      setLocations([]);
      return;
    }
    const controller = new AbortController();
    api<Location[]>(`${WMS}/warehouses/${selectedTask.warehouseId}/locations`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (!controller.signal.aborted) {
          setLocations(res.data ?? []);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setLocations([]);
        }
      });
    return () => controller.abort();
  }, [selectedTask?.id, selectedTask?.warehouseId, selectedTask?.status]);

  if (!meta || !taskEnvelope) return <Loading />;

  const taskData = taskEnvelope[0];
  const tasks = taskData?.rows ?? [];
  const total = taskData?.total ?? 0;

  const candidateLocations = (() => {
    if (!selectedTask) return [];
    const normals = locations.filter(
      (l) =>
        l.isActive &&
        l.locationType === "NORMAL" &&
        l.id !== selectedTask.fromLocationId,
    );
    if (
      selectedTask.suggestedLocationId &&
      selectedTask.suggestedLocationCode &&
      !normals.some((l) => l.id === selectedTask.suggestedLocationId)
    ) {
      normals.unshift({
        id: selectedTask.suggestedLocationId,
        warehouseId: selectedTask.warehouseId,
        warehouseCode: selectedTask.warehouseCode,
        code: selectedTask.suggestedLocationCode,
        name: selectedTask.suggestedLocationName ?? "",
        isDefault: false,
        isActive: true,
        moveCount: 0,
        locationType: "NORMAL",
      });
    }
    return normals;
  })();

  const errors = fieldErrors(actionError);

  async function handleComplete(e: FormEvent) {
    e.preventDefault();
    if (!selectedTask || !toLocationId) return;
    setPending(true);
    setActionError(undefined);
    try {
      const res = await api<PutawayTask>(
        `${WMS}/putaway-tasks/${selectedTask.id}/complete`,
        {
          method: "POST",
          csrf: session?.csrfToken,
          key: crypto.randomUUID(),
          body: { toLocationId: Number(toLocationId) },
        },
      );
      setSelectedTask(res.data);
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setPending(false);
    }
  }

  async function handleCancel() {
    if (!selectedTask) return;
    setPending(true);
    setActionError(undefined);
    try {
      const res = await api<PutawayTask>(
        `${WMS}/putaway-tasks/${selectedTask.id}/cancel`,
        {
          method: "POST",
          csrf: session?.csrfToken,
          key: crypto.randomUUID(),
          body: {},
        },
      );
      setSelectedTask(res.data);
      reload();
    } catch (err) {
      setActionError(err);
    } finally {
      setPending(false);
    }
  }

  const columns: Column<PutawayTask>[] = [
    {
      key: "taskNo",
      label: "작업 번호",
      render: (r) => <strong>{r.taskNo}</strong>,
    },
    {
      key: "status",
      label: "상태",
      render: (r) => {
        const tone =
          r.status === "DONE"
            ? "normal"
            : r.status === "OPEN"
              ? "warning"
              : "issue";
        return <Badge tone={tone}>{PUTAWAY_STATUS_LABEL[r.status]}</Badge>;
      },
    },
    {
      key: "warehouseName",
      label: "창고",
      render: (r) => `${r.warehouseCode} · ${r.warehouseName}`,
    },
    {
      key: "itemCode",
      label: "품목",
      render: (r) => (
        <span>
          {r.itemCode} <span className="muted">· {r.itemName}</span>
        </span>
      ),
    },
    {
      key: "lotNo",
      label: "LOT",
      render: (r) => r.lotNo ?? <span className="muted">-</span>,
    },
    {
      key: "qty",
      label: "수량",
      render: (r) => `${num(r.qty)} ${r.baseUnit}`,
    },
    {
      key: "fromLocationCode",
      label: "출발 위치",
      render: (r) => `${r.fromLocationCode} ${r.fromLocationName}`,
    },
    {
      key: "suggestedLocationCode",
      label: "추천 위치",
      render: (r) =>
        r.suggestedLocationCode ? (
          <span style={{ fontWeight: 500 }}>
            {r.suggestedLocationCode} {r.suggestedLocationName}
          </span>
        ) : (
          <span className="muted">추천 없음</span>
        ),
    },
    {
      key: "toLocationCode",
      label: "적치 위치",
      render: (r) =>
        r.toLocationCode ? (
          `${r.toLocationCode} ${r.toLocationName}`
        ) : (
          <span className="muted">-</span>
        ),
    },
    {
      key: "createdAt",
      label: "등록 일시",
      render: (r) => time(r.createdAt),
    },
    {
      key: "id",
      label: "작업",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => openTask(r)}
        >
          상세
        </button>
      ),
    },
  ];

  return (
    <div className="wms-putaways">
      <PageTitle
        id="W-11"
        title="W-11 적치"
        subtitle="입고 완료된 물품의 적치 작업 목록과 실시간 추천 위치를 확인하고 적치를 완료합니다."
      />

      <div
        className="filter-bar"
        style={{
          display: "flex",
          gap: "0.5rem",
          flexWrap: "wrap",
          marginBottom: "1rem",
        }}
      >
        <label>
          상태
          <select
            aria-label="상태 필터"
            value={statusFilter}
            onChange={(e) => setParam("status", e.target.value)}
          >
            <option value="">전체 상태</option>
            <option value="OPEN">대기</option>
            <option value="DONE">완료</option>
            <option value="CANCELLED">취소</option>
          </select>
        </label>

        <label>
          창고
          <select
            aria-label="창고 필터"
            value={warehouseFilter}
            onChange={(e) => setParam("warehouseId", e.target.value)}
          >
            <option value="">전체 창고</option>
            {warehouses.map((w) => (
              <option key={w.id} value={w.id}>
                {w.code} · {w.name}
              </option>
            ))}
          </select>
        </label>

        <label>
          품목
          <select
            aria-label="품목 필터"
            value={itemFilter}
            onChange={(e) => setParam("itemId", e.target.value)}
          >
            <option value="">전체 품목</option>
            {items.map((it) => (
              <option key={it.id} value={it.id}>
                {it.itemCode} · {it.name}
              </option>
            ))}
          </select>
        </label>

        <button type="button" className="secondary-button" onClick={reload}>
          새로고침
        </button>
      </div>

      <DataTable
        caption="적치 작업 목록"
        rows={tasks}
        columns={columns}
        offset={(page - 1) * LIMIT}
        limit={LIMIT}
        total={total}
        onPage={(offset) =>
          setParam("page", String(Math.floor(offset / LIMIT) + 1))
        }
      />

      {selectedTask && (
        <DetailPanel
          title={selectedTask.taskNo}
          onClose={() => setSelectedTask(null)}
        >
          <div
            className="detail-grid"
            style={{ display: "grid", gap: "0.75rem" }}
          >
            <ErrorNotice error={actionError} />
            <div>
              <strong>상태: </strong>
              <Badge
                tone={
                  selectedTask.status === "DONE"
                    ? "normal"
                    : selectedTask.status === "OPEN"
                      ? "warning"
                      : "issue"
                }
              >
                {PUTAWAY_STATUS_LABEL[selectedTask.status]}
              </Badge>
            </div>
            <div>
              <strong>창고: </strong>
              {selectedTask.warehouseCode} · {selectedTask.warehouseName}
            </div>
            <div>
              <strong>품목: </strong>
              {selectedTask.itemCode} · {selectedTask.itemName}
            </div>
            <div>
              <strong>LOT 번호: </strong>
              {selectedTask.lotNo ?? "-"}
            </div>
            <div>
              <strong>적치 수량: </strong>
              {num(selectedTask.qty)} {selectedTask.baseUnit}
            </div>
            <div>
              <strong>출발 위치: </strong>
              {selectedTask.fromLocationCode} {selectedTask.fromLocationName}
            </div>
            <div>
              <strong>추천 위치: </strong>
              {selectedTask.suggestedLocationCode ? (
                `${selectedTask.suggestedLocationCode} ${selectedTask.suggestedLocationName}`
              ) : (
                <span className="muted">추천 없음 (수동 선택 필요)</span>
              )}
            </div>
            <div>
              <strong>적치 위치: </strong>
              {selectedTask.toLocationCode ? (
                `${selectedTask.toLocationCode} ${selectedTask.toLocationName}`
              ) : (
                <span className="muted">-</span>
              )}
            </div>
            <div>
              <strong>등록 일시: </strong>
              {time(selectedTask.createdAt)}
            </div>
            {selectedTask.doneAt && (
              <div>
                <strong>완료 일시: </strong>
                {time(selectedTask.doneAt)}
              </div>
            )}
            {selectedTask.stockDocumentId && (
              <div>
                <strong>재고 전표: </strong>
                <Link
                  className="link-button"
                  to={`/wms/documents?open=${selectedTask.stockDocumentId}`}
                >
                  전표 #{selectedTask.stockDocumentId} 보기
                </Link>
              </div>
            )}

            {selectedTask.status === "OPEN" && (
              <form
                onSubmit={handleComplete}
                style={{
                  marginTop: "0.75rem",
                  paddingTop: "0.75rem",
                  borderTop: "1px solid #e5e7eb",
                  display: "grid",
                  gap: "0.75rem",
                }}
              >
                <div className="field">
                  <label htmlFor="putaway-to-location">적치 위치 선택</label>
                  <select
                    id="putaway-to-location"
                    aria-label="적치 위치 선택"
                    value={toLocationId}
                    onChange={(e) => setToLocationId(e.target.value)}
                    required
                  >
                    <option value="">위치를 선택하세요</option>
                    {candidateLocations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.code} {loc.name}
                        {loc.id === selectedTask.suggestedLocationId
                          ? " (추천)"
                          : ""}
                      </option>
                    ))}
                  </select>
                  {errors.toLocationId && <small>{errors.toLocationId}</small>}
                </div>
                <div
                  className="button-row"
                  style={{ display: "flex", gap: "0.5rem" }}
                >
                  <button type="submit" disabled={pending || !toLocationId}>
                    적치 완료
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    disabled={pending}
                    onClick={handleCancel}
                  >
                    적치 취소
                  </button>
                </div>
              </form>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
