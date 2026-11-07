// SPC 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-028 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { spcScreens } from "../shared/menuCatalog";
export { spcScreens } from "../shared/menuCatalog";

export function SpcLayout() {
  return (
    <SolutionLayout
      name="SPC"
      title="SPC 공정관리"
      base="/spc"
      screens={spcScreens}
    />
  );
}
