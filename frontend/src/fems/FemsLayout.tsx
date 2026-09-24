// FEMS 솔루션 레이아웃: 좌측 사이드바 + 포털 공통 헤더 (FS-008a 포털 §6-5)
import { NavLink, Outlet } from "react-router-dom";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const femsScreens = [
  { path: "readings", id: "F-02", label: "계측 조회", group: "에너지 현황" },
  { path: "equipments", id: "F-10", label: "설비", group: "기준정보" },
  { path: "energy-sources", id: "F-11", label: "에너지원", group: "기준정보" },
];
export function FemsLayout() {
  return (
    <div className="solution-layout">
      <aside className="solution-sidebar" aria-label="FEMS 메뉴">
        <p className="eyebrow">FEMS 에너지관리</p>
        <nav>
          {[...new Set(femsScreens.map((s) => s.group))].map((group) => (
            <section key={group}>
              <h2>{group}</h2>
              {femsScreens
                .filter((s) => s.group === group)
                .map((s) => (
                  <NavLink key={s.path} to={`/fems/${s.path}`}>
                    <span>{s.id}</span> {s.label}
                  </NavLink>
                ))}
            </section>
          ))}
          <section>
            <h2>다른 앱</h2>
            <NavLink to="/help/mes/m-01">MES 업무 안내</NavLink>
            <NavLink to="/help/erp/e-01">ERP 업무 안내</NavLink>
            <NavLink to="/home">포털 홈</NavLink>
          </section>
        </nav>
      </aside>
      <div className="solution-content">
        <Outlet />
      </div>
    </div>
  );
}
