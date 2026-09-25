// FEMS 솔루션 레이아웃: 좌측 사이드바 + 포털 공통 헤더 (FS-008a 포털 §6-5)
import { useLayoutEffect, useRef } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
// 구현된 화면만 메뉴에 둔다. 준비 중 항목을 나열하지 않는다(FS-008a 포털 §1).
export const femsScreens = [
  { path: "dashboard", id: "F-01", label: "대시보드", group: "에너지 현황" },
  { path: "readings", id: "F-02", label: "계측 조회", group: "에너지 현황" },
  {
    path: "allocations",
    id: "F-03",
    label: "설비별 배분",
    group: "에너지 현황",
  },
  { path: "emissions", id: "F-04", label: "배출량 현황", group: "에너지 현황" },
  {
    path: "production",
    id: "F-05",
    label: "생산량 등록",
    group: "원단위·목표",
  },
  { path: "intensity", id: "F-06", label: "원단위 분석", group: "원단위·목표" },
  {
    path: "targets",
    id: "F-07",
    label: "목표 대비 실적",
    group: "원단위·목표",
  },
  { path: "billing", id: "F-08", label: "요금 산정", group: "요금" },
  { path: "equipments", id: "F-10", label: "설비", group: "기준정보" },
  { path: "energy-sources", id: "F-11", label: "에너지원", group: "기준정보" },
  {
    path: "energy-factors",
    id: "F-13",
    label: "환산·배출계수",
    group: "기준정보",
  },
  { path: "tariffs", id: "F-14", label: "요금제", group: "기준정보" },
];
export function FemsLayout() {
  const location = useLocation();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const currentScreen = femsScreens.find(
    (s) =>
      location.pathname === `/fems/${s.path}` ||
      location.pathname.startsWith(`/fems/${s.path}/`),
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
    ? `FEMS 메뉴 · ${currentScreen.id} ${currentScreen.label}`
    : "FEMS 메뉴";

  return (
    <div className="solution-layout">
      <aside className="solution-sidebar" aria-label="FEMS 메뉴">
        <details ref={detailsRef} open className="solution-sidebar-details">
          <summary>{summaryTitle}</summary>
          <p className="eyebrow">FEMS 에너지관리</p>
          <nav>
            {[...new Set(femsScreens.map((s) => s.group))].map((group) => (
              <section key={group}>
                <h2>{group}</h2>
                {femsScreens
                  .filter((s) => s.group === group)
                  .map((s) => (
                    <NavLink
                      key={s.path}
                      to={`/fems/${s.path}`}
                      onClick={closeMenu}
                    >
                      <span>{s.id}</span> {s.label}
                    </NavLink>
                  ))}
              </section>
            ))}
            <section>
              <h2>다른 앱</h2>
              <NavLink to="/help/mes/m-01" onClick={closeMenu}>
                MES 업무 안내
              </NavLink>
              <NavLink to="/help/erp/e-01" onClick={closeMenu}>
                ERP 업무 안내
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
