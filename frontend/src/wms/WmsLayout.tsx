// WMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-024 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { wmsScreens } from "../shared/menuCatalog";
export { wmsScreens } from "../shared/menuCatalog";

export function WmsLayout() {
  return (
    <SolutionLayout
      name="WMS"
      title="WMS 창고관리"
      base="/wms"
      screens={wmsScreens}
    />
  );
}
