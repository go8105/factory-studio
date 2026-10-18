import { useEffect, useRef, useState } from "react";
import { useSession } from "../app/session";
import { api, ApiError, MutationKeys } from "../shared/api";
import { ErrorNotice } from "../shared/components";
import { WMS, type StockQuantities } from "./common";

export type Page<T> = {
  rows: T[];
  total: number;
  page: number;
  pageSize: number;
};
export type InboundLine = {
  id: number;
  itemId: number;
  lotNo: string | null;
  expectedQty: string;
  normalLocationId: number;
  quarantineLocationId: number | null;
  acceptedQty: string | null;
  quarantinedQty: string | null;
  shortageQty: string | null;
  reason: string | null;
};
export type NoticeKind = "PURCHASE" | "PO" | "SALES_RETURN" | "SUBCONTRACT";
export type Inbound = {
  id: number;
  noticeNo: string;
  noticeKind: NoticeKind;
  businessKey: string;
  warehouseId: number;
  expectedOn: string;
  vehicleNo: string | null;
  partnerRef: string | null;
  status: "PLANNED" | "ARRIVED" | "INSPECTED" | "CANCELLED";
  version: number;
  arrivedAt: string | null;
  inspectedAt: string | null;
  reason: string | null;
  stockDocumentId: number | null;
  lines: InboundLine[];
  sourceClaim: { sourceKey: string; status: string } | null;
  sourceState: string;
};
export type Reservation = {
  id: number;
  reservationNo: string;
  businessKey: string;
  status: "ACTIVE" | "RELEASED" | "CONSUMED";
  version: number;
  shipmentOrderRef: string | null;
  shipmentSourceKey: string | null;
  stockDocumentId: number | null;
  reason: string | null;
  shortage?: string;
  pickOrderId?: number | null;
  pickOrderNo?: string | null;
  pickOrderStatus?: "OPEN" | "PICKED" | "CANCELLED" | null;
  lines: (StockQuantities & {
    id: number;
    itemId: number;
    locationId: number;
    lotNo: string | null;
    quantity: string;
    onHand: string;
  })[];
  shipmentOrderState: string;
  shipmentOrderComparison: {
    state: string;
    lines: {
      itemCode: string;
      unit: string;
      reservedQty: string;
      orderQty: string;
    }[];
  };
};
export type Shipment = {
  sourceKey: string;
  shipmentNo: string;
  shipmentOrderNo: string;
  lines: {
    itemCode: string;
    qty: string;
    unit: string;
    packingNo: string | null;
  }[];
};
export type ReservationSources = {
  enabled: boolean;
  orders: { shipmentOrderNo: string; status: string }[];
  shipments: Shipment[];
};
export const states: Record<string, string> = {
  PLANNED: "예정",
  ARRIVED: "도착 · 검수 대기",
  INSPECTED: "검수 완료",
  CANCELLED: "취소",
  ACTIVE: "활성",
  RELEASED: "해제",
  CONSUMED: "소진",
};
export const noticeKinds: Record<NoticeKind, string> = {
  PURCHASE: "매입",
  PO: "발주",
  SALES_RETURN: "판매 반품",
  SUBCONTRACT: "외주",
};
export const comparison: Record<string, string> = {
  match: "수량 일치",
  mismatch: "수량 불일치",
  unlinked: "직접 참고 없음",
  unavailable: "ERP 꺼짐",
  missing: "원천 없음",
  conversion_missing: "단위 환산 없음",
  conversion_invalid: "환산 수량 오류",
};

// Decimal milli-units: never derive a persisted shortage from binary float subtraction.
export function milli(value: string): bigint | null {
  if (!/^\d+(\.\d{1,3})?$/.test(value)) return null;
  const [whole, part = ""] = value.split(".");
  return BigInt(whole) * 1000n + BigInt(part.padEnd(3, "0"));
}
export function remainder(expected: string, accepted: string, held: string) {
  const [e, a, h] = [expected, accepted, held].map(milli);
  if (e === null || a === null || h === null || e < a + h) return null;
  const n = e - a - h;
  return `${n / 1000n}.${String(n % 1000n).padStart(3, "0")}`;
}
export function useWmsQuery<T>(path: string | null) {
  const { fail } = useSession();
  const [value, setValue] = useState<{ path: string; data: T }>();
  const [error, setError] = useState<unknown>();
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError(undefined);
    if (path)
      void api<T>(WMS + path, { signal: controller.signal })
        .then((r) => {
          if (!controller.signal.aborted) setValue({ path, data: r.data });
        })
        .catch((e) => {
          if (!controller.signal.aborted) {
            setError(e);
            if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
          }
        });
    return () => controller.abort();
  }, [path, tick]);
  return {
    data: value?.path === path ? value.data : undefined,
    error,
    reload: () => setTick((n) => n + 1),
    accept: (data: T) => {
      if (path) setValue({ path, data });
    },
  };
}
export function useWmsCommand() {
  const { session, fail } = useSession();
  const keys = useRef(new MutationKeys());
  const lock = useRef(false);
  const alive = useRef(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  async function send<T>(path: string, body: unknown, method = "POST") {
    if (lock.current) return;
    lock.current = true;
    setPending(true);
    setError(undefined);
    const operation = `${method} ${path} ${JSON.stringify(body)}`;
    try {
      const r = await api<T>(WMS + path, {
        method,
        body,
        csrf: session?.csrfToken,
        key: keys.current.get(operation),
      });
      keys.current.complete(operation);
      return alive.current ? r.data : undefined;
    } catch (e) {
      if (e instanceof ApiError && e.status > 0 && e.status < 500)
        keys.current.complete(operation);
      if (alive.current) {
        setError(e);
        if (e instanceof ApiError && [401, 410].includes(e.status)) fail(e);
      }
    } finally {
      lock.current = false;
      if (alive.current) setPending(false);
    }
  }
  return { send, pending, error, clear: () => setError(undefined) };
}
export function OperationError({
  error,
  retry,
}: {
  error: unknown;
  retry?: () => void;
}) {
  const fields =
    error instanceof ApiError
      ? (error.error.details?.fields as Record<string, string> | undefined)
      : undefined;
  return (
    <>
      <ErrorNotice error={error} retry={retry} />
      {fields && (
        <ul role="alert">
          {Object.entries(fields).map(([k, v]) => (
            <li key={k}>
              {k}: {v}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
