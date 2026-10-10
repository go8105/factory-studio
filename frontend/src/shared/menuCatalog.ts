import catalog from "../../../backend/src/fs/core/menu_catalog.json";

export type Screen = { path: string; id: string; label: string; group: string };
export type Menu = Screen & {
  key: string;
  module: string;
  solution: string;
  to: string;
};
export const menuSolutions = catalog.solutions;
export const menuCatalog: Menu[] = menuSolutions.flatMap((solution) =>
  solution.screens.map((screen) => ({
    ...screen,
    key: `${solution.key}:${screen.path}`,
    module: solution.key,
    solution: solution.name,
    to: `${solution.key === "flow" ? "/work-os" : "/" + solution.key}/${screen.path}`,
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
export const hrScreens = screens("hr");

export const flowScreens = screens("flow");
