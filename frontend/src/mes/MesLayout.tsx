// MES 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-008a 포털 §6-5, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const mesScreens: Screen[] = [
  { path: "dashboard", id: "M-01", label: "대시보드", group: "생산 현황" },
  {
    path: "production-plans",
    id: "M-02",
    label: "생산계획",
    group: "생산계획",
  },
  { path: "work-orders", id: "M-03", label: "작업지시", group: "생산계획" },
  { path: "lots", id: "M-04", label: "LOT 현황", group: "생산실행" },
  { path: "executions", id: "M-05", label: "공정 실행", group: "생산실행" },
  {
    path: "material-issues",
    id: "M-06",
    label: "자재 투입",
    group: "생산실행",
  },
  { path: "results", id: "M-07", label: "실적 확정", group: "생산실행" },
  { path: "packing", id: "M-08", label: "패킹", group: "포장·입고" },
  { path: "receipts", id: "M-09", label: "완제품 입고", group: "포장·입고" },
  { path: "sites", id: "M-10", label: "사업장·공간", group: "기준정보" },
  { path: "equipments", id: "M-11", label: "설비", group: "기준정보" },
  { path: "items", id: "M-12", label: "품목", group: "기준정보" },
  { path: "processes", id: "M-13", label: "공정", group: "기준정보" },
  { path: "routes", id: "M-14", label: "공정 경로", group: "기준정보" },
  { path: "boms", id: "M-15", label: "BOM", group: "기준정보" },
];
const others = [
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/home", label: "포털 홈" },
];
export function MesLayout() {
  return (
    <SolutionLayout
      name="MES"
      title="MES 생산관리"
      base="/mes"
      screens={mesScreens}
      others={others}
    />
  );
}
