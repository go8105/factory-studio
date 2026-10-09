// HR 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (DSN-30 5장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { hrScreens } from "../shared/menuCatalog";
export { hrScreens } from "../shared/menuCatalog";

const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function HrLayout() {
  return (
    <SolutionLayout
      name="HR"
      title="HR 인사·급여"
      base="/hr"
      screens={hrScreens}
      others={others}
    />
  );
}
