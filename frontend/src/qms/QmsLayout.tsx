// QMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-023 화면 설계 1장, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
export const qmsScreens: Screen[] = [
  { path: "dashboard", id: "Q-01", label: "대시보드", group: "품질 현황" },
  { path: "pending", id: "Q-03", label: "검사 대기", group: "검사" },
  { path: "inspections", id: "Q-04", label: "검사", group: "검사" },
  { path: "holds", id: "Q-05", label: "품질 보류", group: "검사" },
  { path: "specs", id: "Q-02", label: "검사 기준", group: "기준정보" },
  { path: "defect-types", id: "Q-06", label: "불량 유형", group: "기준정보" },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
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
