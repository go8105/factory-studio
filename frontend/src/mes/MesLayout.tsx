// MES 솔루션 레이아웃: 좌측 사이드바 + 포털 공통 헤더 (FS-008a 포털 §6-5)
import { useLayoutEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const mesScreens = [
  {
    path: "production-plans",
    id: "M-02",
    label: "생산계획",
    group: "생산계획",
  },
  { path: "work-orders", id: "M-03", label: "작업지시", group: "생산계획" },
  { path: "lots", id: "M-04", label: "LOT 현황", group: "생산실행" },
  { path: "executions", id: "M-05", label: "공정 실행", group: "생산실행" },
  {
    path: "material-issues",
    id: "M-06",
    label: "자재 투입",
    group: "생산실행",
  },
  { path: "results", id: "M-07", label: "실적 확정", group: "생산실행" },
  { path: "packing", id: "M-08", label: "패킹", group: "포장·입고" },
  { path: "receipts", id: "M-09", label: "완제품 입고", group: "포장·입고" },
  { path: "sites", id: "M-10", label: "사업장·공간", group: "기준정보" },
  { path: "equipments", id: "M-11", label: "설비", group: "기준정보" },
  { path: "items", id: "M-12", label: "품목", group: "기준정보" },
  { path: "processes", id: "M-13", label: "공정", group: "기준정보" },
  { path: "routes", id: "M-14", label: "공정 경로", group: "기준정보" },
  { path: "boms", id: "M-15", label: "BOM", group: "기준정보" },
];
export function MesLayout() {
  const location = useLocation();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const currentScreen = mesScreens.find(
    (s) =>
      location.pathname === `/mes/${s.path}` ||
      location.pathname.startsWith(`/mes/${s.path}/`),
  );

  // 접는 메뉴는 좁은 화면에서만 닫는다. 넓은 화면은 summary가 숨겨져(styles.css 801px 이상)
  // 다시 열 방법이 없으므로 절대 닫지 않는다. 기준 800px은 styles.css의 미디어 쿼리와 같다.
  // matchMedia가 없는 환경은 넓은 화면으로 본다(닫지 않는 쪽이 안전하다).
  const collapsible = () =>
    window.matchMedia?.("(max-width: 800px)").matches ?? false;
  const closeMenu = () => {
    if (detailsRef.current && collapsible()) detailsRef.current.open = false;
  };
  // 좁은 화면은 닫힌 상태로 시작한다. 그리기 전에 실행해 펼쳐진 메뉴가 깜빡이지 않는다.
  useLayoutEffect(closeMenu, []);

  const summaryTitle = currentScreen
    ? `MES 메뉴 · ${currentScreen.id} ${currentScreen.label}`
    : "MES 메뉴";

  return (
    <div className="solution-layout">
      <aside className="solution-sidebar" aria-label="MES 메뉴">
        <details ref={detailsRef} open className="solution-sidebar-details">
          <summary>{summaryTitle}</summary>
          <p className="eyebrow">MES 생산관리</p>
          <nav>
            {[...new Set(mesScreens.map((s) => s.group))].map((group) => (
              <section key={group}>
                <h2>{group}</h2>
                {mesScreens
                  .filter((s) => s.group === group)
                  .map((s) => (
                    <NavLink
                      key={s.path}
                      to={`/mes/${s.path}`}
                      onClick={closeMenu}
                    >
                      <span>{s.id}</span> {s.label}
                    </NavLink>
                  ))}
              </section>
            ))}
            <section>
              <h2>다른 앱</h2>
              <NavLink to="/fems" onClick={closeMenu}>
                FEMS 에너지관리
              </NavLink>
              <NavLink to="/erp" onClick={closeMenu}>
                ERP 경영관리
              </NavLink>
              <NavLink to="/home" onClick={closeMenu}>
                포털 홈
              </NavLink>
            </section>
          </nav>
        </details>
      </aside>
      <div className="solution-content">
        <Outlet />
      </div>
    </div>
  );
}
