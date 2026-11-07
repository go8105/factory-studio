import catalog from "../../../backend/src/fs/core/menu_catalog.json";

export type Screen = { path: string; id: string; label: string; group: string };
export type Menu = Screen & {
  key: string;
  module: string;
  solution: string;
  to: string;
};
export const menuSolutions = catalog.solutions;

// flow만 폴더·카탈로그 키(flow)와 URL(/work-os)이 다르다.
export const solutionPath = (key: string) =>
  key === "flow" ? "/work-os" : "/" + key;

// 사이드바 "다른 앱"과 헤더 전환기에 쓰는 표시 이름.
// 카탈로그 title에서 만들지 않는다 — spc는 "통계적 공정관리"로 사이드바에 길고
// hr은 급여를 포함하며 flow에는 title이 없다. 화면에 쓰는 이름은 여기 한 곳에서 정한다.
const DISPLAY: Record<string, string> = {
  gw: "GW 그룹웨어",
  mes: "MES 생산관리",
  erp: "ERP 경영관리",
  wms: "WMS 창고관리",
  fems: "FEMS 에너지관리",
  qms: "QMS 품질관리",
  bems: "BEMS 건물관리",
  spc: "SPC 공정관리",
  cmms: "CMMS 설비보전",
  hr: "HR 인사·급여",
  flow: "Factory Flow",
};
export const solutionLabel = (key: string): string =>
  DISPLAY[key] ?? menuSolutions.find((s) => s.key === key)?.name ?? key;

// 현재 솔루션을 뺀 나머지 전부. 모듈마다 손으로 적던 목록을 대신한다.
export const otherSolutions = (current: string) =>
  menuSolutions
    .filter((s) => s.key !== current)
    .map((s) => ({ to: solutionPath(s.key), label: solutionLabel(s.key) }));

export const solutionFromPath = (pathname: string): string | undefined =>
  menuSolutions.find(
    (s) =>
      pathname === solutionPath(s.key) ||
      pathname.startsWith(solutionPath(s.key) + "/"),
  )?.key;

export const menuCatalog: Menu[] = menuSolutions.flatMap((solution) =>
  solution.screens.map((screen) => ({
    ...screen,
    key: `${solution.key}:${screen.path}`,
    module: solution.key,
    solution: solution.name,
    to: `${solutionPath(solution.key)}/${screen.path}`,
  })),
);
export const menuByKey = new Map(menuCatalog.map((menu) => [menu.key, menu]));
export const defaultMenuIds = catalog.defaultMenuIds;
const screens = (key: string): Screen[] =>
  menuSolutions.find((s) => s.key === key)!.screens;
export const gwScreens = screens("gw");
export const mesScreens = screens("mes");
export const erpScreens = screens("erp");
export const wmsScreens = screens("wms");
export const femsScreens = screens("fems");
export const qmsScreens = screens("qms");
export const bemsScreens = screens("bems");
export const spcScreens = screens("spc");
export const cmmsScreens = screens("cmms");
export const hrScreens = screens("hr");

export const flowScreens = screens("flow");
