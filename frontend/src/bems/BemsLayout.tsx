// BEMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-025 화면 설계 1장, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
export const bemsScreens: Screen[] = [
  { path: "dashboard", id: "B-01", label: "대시보드", group: "건물 현황" },
  { path: "breakdown", id: "B-02", label: "에너지 분해", group: "건물 현황" },
  {
    path: "environment",
    id: "B-03",
    label: "환경 모니터링",
    group: "건물 현황",
  },
  { path: "hvac", id: "B-04", label: "공조 운전", group: "운전·경보" },
  { path: "schedules", id: "B-05", label: "운전 스케줄", group: "운전·경보" },
  { path: "alarms", id: "B-06", label: "경보", group: "운전·경보" },
  { path: "zones", id: "B-07", label: "구역·계측", group: "기준정보" },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/fems", label: "FEMS 에너지관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function BemsLayout() {
  return (
    <SolutionLayout
      name="BEMS"
      title="BEMS 건물관리"
      base="/bems"
      screens={bemsScreens}
      others={others}
    />
  );
}
