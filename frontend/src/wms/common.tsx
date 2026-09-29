// WMS 화면 공통 (FS-024): API 경로·타입·배지. 공통 훅(shared/hooks)에 WMS 접두사를 붙인다.
import { Badge, EmptyState } from "../shared/components";
import { useApiLists, useApiSend } from "../shared/hooks";
export { fieldErrors, moduleOff } from "../shared/hooks";

export const WMS = "/api/v1/wms";

export type Purpose = "RAW" | "FG";
export type Warehouse = {
  id: number;
  code: string;
  name: string;
  purpose: Purpose;
  isActive: boolean;
  locationCount: number;
};
export type Location = {
  id: number;
  warehouseId: number;
  warehouseCode: string;
  code: string;
  name: string;
  isDefault: boolean;
  isActive: boolean;
  moveCount: number;
};
export type Conversion = { id: number; fromUnit: string; factor: string };
export type Item = {
  id: number;
  itemCode: string;
  name: string;
  baseUnit: string;
  itemClass: Purpose;
  lotTracked: boolean;
  isActive: boolean;
  moveCount: number;
  conversions: Conversion[];
};
export type StockRow = {
  itemId: number;
  itemCode: string;
  itemName: string;
  itemClass: Purpose;
  unit: string;
  locationId: number;
  locationCode: string;
  warehouseId: number;
  warehouseCode: string;
  lotNo: string | null;
  onHand: string;
  negative: boolean;
  lotUnassigned: boolean;
};
export type StockTotal = {
  itemCode: string;
  onHand: string;
  openShipmentQty: string | null;
  available: string | null;
};
export type SourceKind =
  "MES_RECEIPT" | "MES_ISSUE" | "ERP_SHIPMENT" | "ERP_PURCHASE";
export type ManualType = "OPENING" | "ADJUSTMENT" | "TRANSFER";
export type DocumentType =
  SourceKind | ManualType | "REVERSAL" | "WMS_INSPECTION";
export type Move = {
  id: number;
  documentId: number;
  lineNo: number;
  itemId: number;
  itemCode: string;
  itemName: string;
  itemClass: Purpose;
  locationId: number;
  locationCode: string;
  warehouseCode: string;
  lotNo: string | null;
  qtyDelta: string;
  unit: string;
  sourceQty: string | null;
  sourceUnit: string | null;
  movedAt: string;
  documentNo?: string;
  documentType?: DocumentType;
  sourceRef?: string | null;
  running?: string;
};
export type StockDocument = {
  id: number;
  documentNo: string;
  documentType: DocumentType;
  status: "draft" | "posted";
  sourceKey: string | null;
  sourceRef: string | null;
  reversesDocumentId: number | null;
  reversesDocumentNo: string | null;
  reasonCode: Reason | null;
  documentOn: string;
  documentMonth: string;
  postedAt: string | null;
  note: string | null;
  lineCount: number;
  moves?: Move[];
  negative?: StockRow[];
};
export type Reason = "RETURN" | "SCRAP" | "COUNT" | "OTHER";
export type SourceState =
  | "pending"
  | "blocked"
  | "synced"
  | "cancel_pending"
  | "reversed"
  | "cancelled"
  | "inspection_pending"
  | "inspected"
  | "inspected_cancelled";
export type SourceLine = {
  itemCode: string;
  qty: string;
  unit: string;
  lotNo?: string;
  packingNo?: string | null;
};
export type Source = {
  sourceKey: string;
  sourceRef: string;
  occurredAt: string;
  cancelledAt?: string | null;
  lines: SourceLine[];
  state: SourceState;
  reason: { code: string; itemCode?: string; unit?: string } | null;
  documentId: number | null;
  documentNo: string | null;
};

export const KIND_LABEL: Record<SourceKind, string> = {
  MES_RECEIPT: "MES 완제품 입고",
  MES_ISSUE: "MES 자재 투입",
  ERP_SHIPMENT: "ERP 출하",
  ERP_PURCHASE: "ERP 매입",
};
export const TYPE_LABEL: Record<DocumentType, string> = {
  ...KIND_LABEL,
  OPENING: "기초재고",
  ADJUSTMENT: "조정",
  TRANSFER: "창고 간 이동",
  REVERSAL: "되돌림",
  WMS_INSPECTION: "입고 검수",
};
export const REASON_LABEL: Record<Reason, string> = {
  RETURN: "반품 입고",
  SCRAP: "폐기",
  COUNT: "실물 차이",
  OTHER: "기타",
};
export const PURPOSE_LABEL: Record<Purpose, string> = {
  RAW: "원자재",
  FG: "완제품",
};
export const BLOCK_LABEL: Record<string, string> = {
  ITEM_NOT_REGISTERED: "품목 미등록",
  UNIT_CONVERSION_MISSING: "단위 환산 없음",
  NO_WAREHOUSE: "반영 창고 없음",
  SOURCE_CANCELLED: "원천 취소됨",
  SOURCE_NOT_FOUND: "원천 없음",
  SOURCE_CLAIMED: "입고 검수에서 처리할 원천",
};

export const num = (v: string | number, digits = 3) =>
  Number(v).toLocaleString("ko-KR", { maximumFractionDigits: digits });
/** 부호를 붙인 증감(+1,940 / −60). */
export const signed = (v: string) =>
  Number(v) > 0 ? `+${num(v)}` : `−${num(Math.abs(Number(v)))}`;
export const time = (v: string) =>
  new Date(v).toLocaleString("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });

export function ModuleOff() {
  return (
    <EmptyState
      reason="WMS를 사용하지 않도록 설정했습니다. 내 공간에서 다시 켤 수 있습니다."
      to="/workspace"
      action="내 공간으로"
    />
  );
}

/** 재고 상태 배지 — 색만으로 구분하지 않고 문구를 쓴다(화면 설계 W-02). */
export function StockBadges({ row }: { row: StockRow }) {
  return (
    <>
      {row.negative && <Badge tone="issue">음수</Badge>}{" "}
      {row.lotUnassigned && <Badge tone="warning">LOT 미지정</Badge>}
    </>
  );
}

export const useLists = <T extends unknown[]>(paths: string[]) =>
  useApiLists<T>(WMS, paths);
export const useSend = (onDone: () => void) => useApiSend(WMS, onDone);
