// HR 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (DSN-30 5장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { hrScreens } from "../shared/menuCatalog";
export { hrScreens } from "../shared/menuCatalog";

export function HrLayout() {
  return (
    <SolutionLayout
      name="HR"
      title="HR 인사·급여"
      base="/hr"
      screens={hrScreens}
    />
  );
}
