// FEMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-008a 포털 §6-5, UI-01)
import { SolutionLayout, type Screen } from "../shared/SolutionLayout";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const femsScreens: Screen[] = [
  { path: "dashboard", id: "F-01", label: "대시보드", group: "에너지 현황" },
  { path: "readings", id: "F-02", label: "계측 조회", group: "에너지 현황" },
  {
    path: "allocations",
    id: "F-03",
    label: "설비별 배분",
    group: "에너지 현황",
  },
  { path: "emissions", id: "F-04", label: "배출량 현황", group: "에너지 현황" },
  {
    path: "production",
    id: "F-05",
    label: "생산량 등록",
    group: "원단위·목표",
  },
  { path: "intensity", id: "F-06", label: "원단위 분석", group: "원단위·목표" },
  {
    path: "targets",
    id: "F-07",
    label: "목표 대비 실적",
    group: "원단위·목표",
  },
  { path: "billing", id: "F-08", label: "요금 산정", group: "요금" },
  { path: "sites", id: "F-09", label: "사업장·공간", group: "기준정보" },
  { path: "equipments", id: "F-10", label: "설비", group: "기준정보" },
  { path: "energy-sources", id: "F-11", label: "에너지원", group: "기준정보" },
  { path: "meters", id: "F-12", label: "계측기·채널", group: "기준정보" },
  {
    path: "energy-factors",
    id: "F-13",
    label: "환산·배출계수",
    group: "기준정보",
  },
  { path: "tariffs", id: "F-14", label: "요금제", group: "기준정보" },
];
const others = [
  { to: "/mes", label: "MES 생산관리" },
  { to: "/qms", label: "QMS 품질관리" },
  { to: "/wms", label: "WMS 창고관리" },
  { to: "/bems", label: "BEMS 건물관리" },
  { to: "/erp", label: "ERP 경영관리" },
  { to: "/spc", label: "SPC 공정관리" },
  { to: "/gw", label: "GW 그룹웨어" },
  { to: "/home", label: "포털 홈" },
];
export function FemsLayout() {
  return (
    <SolutionLayout
      name="FEMS"
      title="FEMS 에너지관리"
      base="/fems"
      screens={femsScreens}
      others={others}
    />
  );
}
