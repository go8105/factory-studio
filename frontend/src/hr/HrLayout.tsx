// HR 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (DSN-30 5장, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
export const hrScreens: Screen[] = [
  { path: "departments", id: "H-02", label: "부서", group: "조직·사원" },
  { path: "titles", id: "H-03", label: "직위·직책", group: "조직·사원" },
  { path: "work-patterns", id: "H-04", label: "근무 형태", group: "조직·사원" },
  { path: "employees", id: "H-05", label: "사원", group: "조직·사원" },
  { path: "appointments", id: "H-06", label: "발령", group: "조직·사원" },
  { path: "attendance", id: "H-07", label: "근태", group: "근태·휴가" },
  {
    path: "attendance-closes",
    id: "H-08",
    label: "근태 마감",
    group: "근태·휴가",
  },
  { path: "leaves", id: "H-09", label: "휴가", group: "근태·휴가" },
  { path: "pay-standards", id: "H-10", label: "급여 기준", group: "급여" },
  { path: "payroll", id: "H-11", label: "급여 계산", group: "급여" },
  { path: "payslips", id: "H-12", label: "급여대장·명세서", group: "급여" },
];
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
