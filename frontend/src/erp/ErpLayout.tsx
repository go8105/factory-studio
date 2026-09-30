// ERP 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-008a 포털 §6-5, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const erpScreens: Screen[] = [
  { path: "dashboard", id: "E-01", label: "대시보드", group: "개요" },
  { path: "quotations", id: "E-02", label: "견적", group: "영업" },
  { path: "sales-plans", id: "E-03", label: "판매계획", group: "영업" },
  { path: "sales-orders", id: "E-04", label: "수주", group: "영업" },
  {
    path: "shipment-orders",
    id: "E-05",
    label: "출하지시",
    group: "출하·매출",
  },
  { path: "shipments", id: "E-06", label: "출하", group: "출하·매출" },
  { path: "sales-records", id: "E-07", label: "매출", group: "출하·매출" },
  {
    path: "tax-invoices",
    id: "E-08",
    label: "세금계산서",
    group: "출하·매출",
  },
  {
    path: "receivables",
    id: "E-09",
    label: "매출채권 현황",
    group: "채권·수금",
  },
  {
    path: "receipts",
    id: "E-10",
    label: "수금 등록·소명",
    group: "채권·수금",
  },
  {
    path: "purchase-invoices",
    id: "E-11",
    label: "매입 전표",
    group: "매입·채무",
  },
  { path: "payables", id: "E-12", label: "매입채무 현황", group: "매입·채무" },
  {
    path: "payments",
    id: "E-13",
    label: "지급 등록·소명",
    group: "매입·채무",
  },
  {
    path: "journal-preview",
    id: "E-14",
    label: "분개 미리보기",
    group: "회계",
  },
  { path: "partners", id: "E-15", label: "거래처", group: "기준정보" },
  { path: "items", id: "E-16", label: "품목", group: "기준정보" },
  {
    path: "partner-prices",
    id: "E-17",
    label: "거래처별 단가",
    group: "기준정보",
  },
  {
    path: "accounts",
    id: "E-18",
    label: "계정과목·분개규칙",
    group: "기준정보",
  },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/home", label: "포털 홈" },
];
export function ErpLayout() {
  return (
    <SolutionLayout
      name="ERP"
      title="ERP 경영관리"
      base="/erp"
      screens={erpScreens}
      others={others}
    />
  );
}
