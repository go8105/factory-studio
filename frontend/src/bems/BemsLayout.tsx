// BEMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-025 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { bemsScreens } from "../shared/menuCatalog";
export { bemsScreens } from "../shared/menuCatalog";

export function BemsLayout() {
  return (
    <SolutionLayout
      name="BEMS"
      title="BEMS 건물관리"
      base="/bems"
      screens={bemsScreens}
    />
  );
}
