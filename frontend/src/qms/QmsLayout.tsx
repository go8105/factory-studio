// QMS 솔루션 레이아웃: 공통 SolutionLayout에 메뉴만 넘긴다 (FS-023 화면 설계 1장, UI-01)
import { SolutionLayout } from "../shared/SolutionLayout";
import { qmsScreens } from "../shared/menuCatalog";
export { qmsScreens } from "../shared/menuCatalog";

export function QmsLayout() {
  return (
    <SolutionLayout
      name="QMS"
      title="QMS 품질관리"
      base="/qms"
      screens={qmsScreens}
    />
  );
}
