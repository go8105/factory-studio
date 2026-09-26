// 채권·수금(E-09·E-10)과 채무·지급(E-12·E-13)은 같은 화면 규칙이다. API 필드 이름만 달라
// 여기서 공통 모양으로 바꿔 화면 두 벌이 같은 컴포넌트를 쓴다.
type Raw = Record<string, unknown>;

export type OpenItem = {
  id: number;
  partnerId: number;
  amount: string;
  appliedAmount: string;
  balance: string;
  status: "OPEN" | "PARTIAL" | "CLOSED";
  dueDate: string | null;
  date: string;
  doc: string;
  applications: Application[];
};
export type Application = {
  id: number;
  moneyId: number;
  itemId: number;
  amount: string;
  appliedAt: string;
  moneyNo: string;
  doc: string;
};
export type Money = {
  id: number;
  no: string;
  partnerId: number;
  on: string;
  amount: string;
  status: "draft" | "confirmed";
  appliedAmount: string;
  unappliedAmount: string;
  applications: Application[];
};

export type Side = {
  openPath: string;
  moneyPath: string;
  itemKey: string; // receivableId / payableId
  moneyKey: string; // receiptId / paymentId
  noKey: string; // receiptNo / paymentNo
  onKey: string; // receivedOn / paidOn
  docKey: string; // shipmentNo / invoiceNo
  dateKey: string; // recognizedAt / invoiceDate
  partnerKind: "CUSTOMER" | "SUPPLIER";
  item: string; // 채권 / 채무
  money: string; // 수금 / 지급
  source: string; // 매출 / 매입
  doc: string; // 표 머리글
  sourcePath: string; // 원천 화면
};

export const RECEIVABLE: Side = {
  openPath: "/receivables",
  moneyPath: "/receipts",
  itemKey: "receivableId",
  moneyKey: "receiptId",
  noKey: "receiptNo",
  onKey: "receivedOn",
  docKey: "shipmentNo",
  dateKey: "recognizedAt",
  partnerKind: "CUSTOMER",
  item: "채권",
  money: "수금",
  source: "매출",
  doc: "매출(출하번호)",
  sourcePath: "/erp/shipments",
};
export const PAYABLE: Side = {
  openPath: "/payables",
  moneyPath: "/payments",
  itemKey: "payableId",
  moneyKey: "paymentId",
  noKey: "paymentNo",
  onKey: "paidOn",
  docKey: "invoiceNo",
  dateKey: "invoiceDate",
  partnerKind: "SUPPLIER",
  item: "채무",
  money: "지급",
  source: "매입",
  doc: "매입(전표번호)",
  sourcePath: "/erp/purchase-invoices",
};

const application = (side: Side) => (a: Raw) =>
  ({
    ...a,
    moneyId: a[side.moneyKey],
    itemId: a[side.itemKey],
    moneyNo: a[side.noKey],
    doc: a[side.docKey],
  }) as Application;

export const toOpen = (side: Side) => (r: Raw) =>
  ({
    ...r,
    date: r[side.dateKey],
    doc: r[side.docKey],
    applications: (r.applications as Raw[]).map(application(side)),
  }) as OpenItem;

export const toMoney = (side: Side) => (r: Raw) =>
  ({
    ...r,
    no: r[side.noKey],
    on: r[side.onKey],
    applications: (r.applications as Raw[]).map(application(side)),
  }) as Money;
