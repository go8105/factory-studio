// SPC 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-028 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { spcScreens } from "../shared/menuCatalog";
export { spcScreens } from "../shared/menuCatalog";

const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function SpcLayout() {
  return (
    <SolutionLayout
      name="SPC"
      title="SPC 공정관리"
      base="/spc"
      screens={spcScreens}
      others={others}
    />
  );
}
