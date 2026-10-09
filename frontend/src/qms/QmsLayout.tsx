// QMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-023 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { qmsScreens } from "../shared/menuCatalog";
export { qmsScreens } from "../shared/menuCatalog";

const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function QmsLayout() {
  return (
    <SolutionLayout
      name="QMS"
      title="QMS 품질관리"
      base="/qms"
      screens={qmsScreens}
      others={others}
    />
  );
}
