// ERP 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-008a 포털 §6-5, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { erpScreens } from "../shared/menuCatalog";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export { erpScreens } from "../shared/menuCatalog";

export function ErpLayout() {
  return (
    <SolutionLayout
      name="ERP"
      title="ERP 경영관리"
      base="/erp"
      screens={erpScreens}
    />
  );
}
