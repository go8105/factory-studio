// SPC 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-028 화면 설계 1장, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
export const spcScreens: Screen[] = [
  { path: "dashboard", id: "S-01", label: "대시보드", group: "공정 현황" },
  { path: "chart", id: "S-02", label: "관리도", group: "공정 현황" },
  { path: "capability", id: "S-03", label: "공정능력", group: "공정 현황" },
  { path: "measure", id: "S-04", label: "측정 입력", group: "측정·이상" },
  { path: "signals", id: "S-05", label: "이상·조치", group: "측정·이상" },
  { path: "subgroups", id: "S-06", label: "부분군 기록", group: "측정·이상" },
  {
    path: "characteristics",
    id: "S-07",
    label: "관리 특성·한계",
    group: "기준정보",
  },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
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
