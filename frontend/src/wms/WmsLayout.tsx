// WMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-024 화면 설계 1장, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
export const wmsScreens: Screen[] = [
  { path: "dashboard", id: "W-01", label: "대시보드", group: "재고" },
  { path: "stock", id: "W-02", label: "재고 현황", group: "재고" },
  { path: "sources", id: "W-03", label: "원천 반영", group: "입출고" },
  { path: "inbounds", id: "W-08", label: "입고 예정·검수", group: "입출고" },
  { path: "reservations", id: "W-09", label: "출고 예약", group: "입출고" },
  { path: "documents", id: "W-04", label: "재고 전표", group: "입출고" },
  { path: "moves", id: "W-05", label: "재고 원장", group: "입출고" },
  { path: "warehouses", id: "W-06", label: "창고·위치", group: "기준정보" },
  { path: "items", id: "W-07", label: "품목·단위", group: "기준정보" },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function WmsLayout() {
  return (
    <SolutionLayout
      name="WMS"
      title="WMS 창고관리"
      base="/wms"
      screens={wmsScreens}
      others={others}
    />
  );
}
