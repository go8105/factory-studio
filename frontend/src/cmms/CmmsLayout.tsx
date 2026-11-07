// CMMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-029 화면 설계, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { cmmsScreens } from "../shared/menuCatalog";
export { cmmsScreens } from "../shared/menuCatalog";

export function CmmsLayout() {
  return (
    <SolutionLayout
      name="CMMS"
      title="CMMS 설비보전"
      base="/cmms"
      screens={cmmsScreens}
    />
  );
}
