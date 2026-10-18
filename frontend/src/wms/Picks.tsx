// W-12 피킹 — 출고 예약 기반 피킹 지시 목록·동선(sequenceNo) 명세·LOT 대체 사유 및 도착 위치 선택 (DSN-13 F22·F23·F27).
// 명세는 위치 코드 순(sequenceNo ASC)으로 표시하며, 예약 LOT이 보류·만료·수량 부족으로 대체된 경우 사유(lotSubstitutions)를 안내한다.
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../shared/api";
import {
  Badge,
  DataTable,
  DetailPanel,
  Loading,
  PageTitle,
  type Column,
} from "../shared/components";
import {
  ModuleOff,
  moduleOff,
  num,
  PICK_STATUS_LABEL,
  PICK_SUBSTITUTION_REASON_LABEL,
  time,
  useLists,
  WMS,
  type Item,
  type Location,
  type PickOrder,
  type PickOrderStatus,
  type Warehouse,
} from "./common";
import { useWmsQuery, type Page, type Reservation } from "./operations";

const LIMIT = 50;

export function Picks() {
  const [params, setParams] = useSearchParams();
  const page = Number(params.get("page") ?? "1");
  const statusFilter = (params.get("status") as PickOrderStatus | null) ?? "";
  const warehouseFilter = params.get("warehouseId") ?? "";
  const reservationFilter = params.get("reservationId") ?? "";
  const itemCodeFilter = params.get("itemCode") ?? "";
  const openId = params.get("open") ?? "";

  const setParam = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page" && key !== "open") next.set("page", "1");
    setParams(next);
  };

  const {
    data: meta,
    error: metaError,
    reload: reloadMeta,
  } = useLists<[Warehouse[], Item[], { rows: Reservation[]; total: number }]>([
    "/warehouses",
    "/items",
    "/reservations?pageSize=100",
  ]);
  const warehouses = meta?.[0] ?? [];
  const items = meta?.[1] ?? [];
  const reservations = meta?.[2]?.rows ?? [];

  const query = new URLSearchParams({
    page: String(page),
    pageSize: String(LIMIT),
  });
  if (statusFilter) query.set("status", statusFilter);
  if (warehouseFilter) query.set("warehouseId", warehouseFilter);
  if (reservationFilter) query.set("reservationId", reservationFilter);
  if (itemCodeFilter) query.set("itemCode", itemCodeFilter);

  const {
    data: orderPage,
    error: listError,
    reload,
  } = useWmsQuery<Page<PickOrder>>(`/pick-orders?${query.toString()}`);

  const [selectedOrder, setSelectedOrder] = useState<PickOrder | null>(null);
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationsLoadedWhId, setLocationsLoadedWhId] = useState<number | null>(
    null,
  );
  const [toLocationId, setToLocationId] = useState<string>("");

  const orders = orderPage?.rows ?? [];
  const total = orderPage?.total ?? 0;

  useEffect(() => {
    if (!openId || !orderPage) return;
    const targetId = Number(openId);
    if (!Number.isFinite(targetId) || targetId <= 0) return;
    const found = orders.find((o) => o.id === targetId);
    if (found) {
      setSelectedOrder(found);
      return;
    }
    const controller = new AbortController();
    api<PickOrder>(`${WMS}/pick-orders/${targetId}`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (
          !controller.signal.aborted &&
          res.data &&
          Array.isArray(res.data.lines)
        ) {
          setSelectedOrder(res.data);
        }
      })
      .catch(() => {});
    return () => controller.abort();
  }, [openId, orderPage]);

  useEffect(() => {
    if (!selectedOrder || !selectedOrder.warehouseId) {
      setLocations([]);
      setLocationsLoadedWhId(null);
      setToLocationId("");
      return;
    }
    const whId = selectedOrder.warehouseId;
    const controller = new AbortController();
    api<Location[]>(`${WMS}/warehouses/${whId}/locations`, {
      signal: controller.signal,
    })
      .then((res) => {
        if (!controller.signal.aborted) {
          const rows = Array.isArray(res.data) ? res.data : [];
          setLocations(rows);
          setLocationsLoadedWhId(whId);
          const fromIds = new Set(
            (selectedOrder.lines ?? []).map((l) => l.locationId),
          );
          const shipping = rows.filter(
            (l) =>
              l.isActive && l.locationType === "SHIPPING" && !fromIds.has(l.id),
          );
          setToLocationId(shipping.length > 0 ? String(shipping[0].id) : "");
        }
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setLocations([]);
          setLocationsLoadedWhId(whId);
          setToLocationId("");
        }
      });
    return () => controller.abort();
  }, [selectedOrder?.id, selectedOrder?.warehouseId]);

  const openOrder = (order: PickOrder) => {
    setSelectedOrder(order);
    setParam("open", String(order.id));
  };

  const closeOrder = () => {
    setSelectedOrder(null);
    setParam("open", "");
  };

  if (moduleOff(metaError ?? listError)) return <ModuleOff />;
  if (!meta || !orderPage) return <Loading />;

  const fromLocationIds = new Set(
    (selectedOrder?.lines ?? []).map((l) => l.locationId),
  );
  const shippingLocations = locations.filter(
    (l) =>
      l.isActive && l.locationType === "SHIPPING" && !fromLocationIds.has(l.id),
  );
  const normalLocations = locations.filter(
    (l) =>
      l.isActive && l.locationType === "NORMAL" && !fromLocationIds.has(l.id),
  );
  const candidateLocations = [...shippingLocations, ...normalLocations];
  const isLocationsReady =
    selectedOrder?.warehouseId != null &&
    locationsLoadedWhId === selectedOrder.warehouseId;

  const sortedLines = selectedOrder
    ? [...(selectedOrder.lines ?? [])].sort(
        (a, b) => a.sequenceNo - b.sequenceNo || a.lineNo - b.lineNo,
      )
    : [];

  const columns: Column<PickOrder>[] = [
    {
      key: "pickNo",
      label: "지시 번호",
      render: (r) => <strong>{r.pickNo}</strong>,
    },
    {
      key: "reservationNo",
      label: "예약 번호",
      render: (r) => (
        <span>
          {r.reservationNo}
          {r.lotSubstitutions.length > 0 && (
            <>
              {" "}
              <Badge tone="warning">
                LOT 대체 {r.lotSubstitutions.length}건
              </Badge>
            </>
          )}
        </span>
      ),
    },
    {
      key: "warehouseName",
      label: "창고",
      render: (r) =>
        r.warehouseCode ? `${r.warehouseCode} · ${r.warehouseName}` : "-",
    },
    {
      key: "status",
      label: "상태",
      render: (r) => {
        const tone =
          r.status === "PICKED"
            ? "normal"
            : r.status === "OPEN"
              ? "warning"
              : "issue";
        return <Badge tone={tone}>{PICK_STATUS_LABEL[r.status]}</Badge>;
      },
    },
    {
      key: "lineCount",
      label: "명세 건수",
      render: (r) => `${r.lineCount}건 (${num(r.totalQty)})`,
    },
    {
      key: "createdAt",
      label: "생성 일시",
      render: (r) => time(r.createdAt),
    },
    {
      key: "id",
      label: "작업",
      render: (r) => (
        <button
          type="button"
          className="link-button"
          onClick={() => openOrder(r)}
        >
          상세
        </button>
      ),
    },
  ];

  return (
    <div className="wms-picks">
      <PageTitle
        id="W-12"
        title="W-12 피킹"
        subtitle="출고 예약 기반 피킹 지시 목록과 위치 코드 순서(동선) 피킹 명세·LOT 대체 사유를 확인합니다."
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
            <option value="PICKED">피킹 완료</option>
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
          예약
          <select
            aria-label="예약 필터"
            value={reservationFilter}
            onChange={(e) => setParam("reservationId", e.target.value)}
          >
            <option value="">전체 예약</option>
            {reservations.map((res) => (
              <option key={res.id} value={res.id}>
                {res.reservationNo}
                {res.shipmentOrderRef ? ` (${res.shipmentOrderRef})` : ""}
              </option>
            ))}
          </select>
        </label>

        <label>
          품목
          <select
            aria-label="품목 필터"
            value={itemCodeFilter}
            onChange={(e) => setParam("itemCode", e.target.value)}
          >
            <option value="">전체 품목</option>
            {items.map((it) => (
              <option key={it.id} value={it.itemCode}>
                {it.itemCode} · {it.name}
              </option>
            ))}
          </select>
        </label>

        <button
          type="button"
          className="secondary"
          onClick={() => {
            reloadMeta();
            reload();
          }}
        >
          새로고침
        </button>
      </div>

      <DataTable
        caption="피킹 지시 목록"
        rows={orders}
        columns={columns}
        offset={(page - 1) * LIMIT}
        limit={LIMIT}
        total={total}
        onPage={(offset) =>
          setParam("page", String(Math.floor(offset / LIMIT) + 1))
        }
      />

      {selectedOrder && (
        <DetailPanel wide title={selectedOrder.pickNo} onClose={closeOrder}>
          <div
            className="detail-grid"
            style={{ display: "grid", gap: "0.75rem" }}
          >
            <div>
              <strong>상태: </strong>
              <Badge
                tone={
                  selectedOrder.status === "PICKED"
                    ? "normal"
                    : selectedOrder.status === "OPEN"
                      ? "warning"
                      : "issue"
                }
              >
                {PICK_STATUS_LABEL[selectedOrder.status]}
              </Badge>
            </div>
            <div>
              <strong>출고 예약: </strong>
              <Link
                className="link-button"
                to={`/wms/reservations?open=${selectedOrder.reservationId}`}
              >
                {selectedOrder.reservationNo}
              </Link>
              {selectedOrder.shipmentOrderRef && (
                <span className="muted">
                  {" "}
                  · 참고 출하지시 {selectedOrder.shipmentOrderRef}
                </span>
              )}
            </div>
            <div>
              <strong>창고: </strong>
              {selectedOrder.warehouseCode
                ? `${selectedOrder.warehouseCode} · ${selectedOrder.warehouseName}`
                : "-"}
            </div>
            <div>
              <strong>명세 건수 / 총 지시 수량: </strong>
              {selectedOrder.lineCount}건 / {num(selectedOrder.totalQty)}
              {selectedOrder.totalPickedQty != null &&
                ` (피킹 확정 ${num(selectedOrder.totalPickedQty)})`}
            </div>
            <div>
              <strong>생성 일시: </strong>
              {time(selectedOrder.createdAt)}
            </div>
            {selectedOrder.pickedAt && (
              <div>
                <strong>피킹 일시: </strong>
                {time(selectedOrder.pickedAt)}
              </div>
            )}
            {selectedOrder.cancelReason && (
              <div>
                <strong>취소 사유: </strong>
                {selectedOrder.cancelReason}
              </div>
            )}
            {selectedOrder.stockDocumentId && (
              <div>
                <strong>재고 전표: </strong>
                <Link
                  className="link-button"
                  to={`/wms/documents?open=${selectedOrder.stockDocumentId}`}
                >
                  {selectedOrder.stockDocumentNo ??
                    `전표 #${selectedOrder.stockDocumentId}`}{" "}
                  보기
                </Link>
              </div>
            )}

            {selectedOrder.lotSubstitutions.length > 0 && (
              <section
                className="notice"
                role="note"
                aria-label="예약 LOT 대체 배정 안내"
              >
                <strong>
                  예약 LOT 대체 배정 안내 (
                  {selectedOrder.lotSubstitutions.length}
                  건)
                </strong>
                <ul style={{ marginTop: "0.35rem", marginBottom: 0 }}>
                  {selectedOrder.lotSubstitutions.map((sub) => (
                    <li key={`${sub.lineNo}-${sub.requestedLotNo}`}>
                      <Badge tone="warning">
                        {PICK_SUBSTITUTION_REASON_LABEL[sub.reason] ??
                          sub.reasonLabel}
                      </Badge>{" "}
                      <strong>{sub.itemCode}</strong> · 예약 LOT{" "}
                      <code>{sub.requestedLotNo}</code> (
                      {sub.requestedLocationCode}, 요청 {num(sub.requestedQty)}
                      {Number(sub.keptQty) > 0
                        ? `, 유지 ${num(sub.keptQty)}`
                        : ""}
                      ) → 대체 배정:{" "}
                      {sub.allocatedLots
                        .map(
                          (al) =>
                            `${al.lotNo ?? "미지정"} (${al.locationCode} · ${num(al.qty)})`,
                        )
                        .join(", ")}
                      <small>{sub.message}</small>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            <section style={{ marginTop: "0.25rem" }}>
              <h3 style={{ marginBottom: "0.5rem" }}>
                피킹 동선 명세 (위치 코드 순)
              </h3>
              <div className="table-scroll">
                <table aria-label="피킹 동선 명세">
                  <thead>
                    <tr>
                      <th>동선</th>
                      <th>위치(칸)</th>
                      <th>품목</th>
                      <th>LOT · 유효기간</th>
                      <th className="num">지시 수량</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sortedLines.map((line) => (
                      <tr key={line.id}>
                        <td>
                          <strong>#{line.sequenceNo}</strong>
                        </td>
                        <td>
                          <strong>{line.locationCode}</strong>{" "}
                          <span className="muted">{line.locationName}</span>
                        </td>
                        <td>
                          {line.itemCode}{" "}
                          <span className="muted">· {line.itemName}</span>
                        </td>
                        <td>
                          {line.lotNo ?? <span className="muted">비추적</span>}
                          {line.expiryDate && (
                            <span className="muted">
                              {" "}
                              (만료 {line.expiryDate})
                            </span>
                          )}
                        </td>
                        <td className="num">
                          {num(line.qty)} {line.baseUnit}
                          {line.pickedQty != null && (
                            <span className="muted">
                              {" "}
                              / 확정 {num(line.pickedQty)}
                            </span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>

            {selectedOrder.status === "OPEN" && (
              <section
                style={{
                  marginTop: "0.5rem",
                  paddingTop: "0.75rem",
                  borderTop: "1px solid var(--border)",
                  display: "grid",
                  gap: "0.5rem",
                }}
              >
                {isLocationsReady && shippingLocations.length === 0 && (
                  <p className="notice" role="note">
                    출고장 칸이 없어 보관 칸으로 이동합니다. W-06에서 출고장을
                    만들 수 있습니다.
                  </p>
                )}
                <div className="field" style={{ marginBottom: 0 }}>
                  <label htmlFor="pick-to-location">도착 위치 선택</label>
                  <select
                    id="pick-to-location"
                    aria-label="도착 위치 선택"
                    value={toLocationId}
                    onChange={(e) => setToLocationId(e.target.value)}
                  >
                    <option value="">위치를 선택하세요</option>
                    {candidateLocations.map((loc) => (
                      <option key={loc.id} value={loc.id}>
                        {loc.code} {loc.name}
                        {loc.locationType === "SHIPPING"
                          ? " [출고장]"
                          : " [보관]"}
                      </option>
                    ))}
                  </select>
                </div>
              </section>
            )}
          </div>
        </DetailPanel>
      )}
    </div>
  );
}
