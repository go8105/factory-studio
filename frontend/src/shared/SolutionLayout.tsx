// MES·ERP·FEMS 공통 솔루션 레이아웃: 좌측 사이드바(넓은 화면 접기, 좁은 화면 서랍) + 본문 (UI-01)
import { useLayoutEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";

export type Screen = { path: string; id: string; label: string; group: string };

const STORAGE_KEY = "fs.sidebar.collapsed";
function readCollapsed() {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

export function SolutionLayout({
  name,
  title,
  base,
  screens,
  others,
}: {
  name: string;
  title: string;
  base: string;
  screens: Screen[];
  others: { to: string; label: string }[];
}) {
  const location = useLocation();
  const detailsRef = useRef<HTMLDetailsElement>(null);
  const summaryRef = useRef<HTMLElement>(null);
  const [collapsed, setCollapsed] = useState(readCollapsed);
  const currentScreen = screens.find(
    (s) =>
      location.pathname === `${base}/${s.path}` ||
      location.pathname.startsWith(`${base}/${s.path}/`),
  );

  // 서랍은 좁은 화면에서만 닫는다. 넓은 화면은 summary가 숨겨져(styles.css 801px 이상)
  // 다시 열 방법이 없으므로 절대 닫지 않는다. 기준 800px은 styles.css의 미디어 쿼리와 같다.
  // matchMedia가 없는 환경은 넓은 화면으로 본다(닫지 않는 쪽이 안전하다).
  const collapsible = () =>
    window.matchMedia?.("(max-width: 800px)").matches ?? false;
  const closeMenu = () => {
    if (detailsRef.current && collapsible()) detailsRef.current.open = false;
  };
  // 좁은 화면은 닫힌 상태로 시작한다. 그리기 전에 실행해 펼쳐진 메뉴가 깜빡이지 않는다.
  useLayoutEffect(closeMenu, []);

  function toggleCollapsed() {
    const next = !collapsed;
    setCollapsed(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next ? "1" : "0");
    } catch {
      // 저장하지 못해도 현재 화면에서는 접힌다.
    }
  }

  const summaryTitle = currentScreen
    ? `${name} 메뉴 · ${currentScreen.id} ${currentScreen.label}`
    : `${name} 메뉴`;

  return (
    <div className={`solution-layout${collapsed ? " collapsed" : ""}`}>
      <aside className="solution-sidebar" aria-label={`${name} 메뉴`}>
        <div className="sidebar-head">
          <p className="eyebrow">{title}</p>
          <button
            type="button"
            className="sidebar-toggle"
            aria-expanded={!collapsed}
            aria-label={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
            title={collapsed ? "메뉴 펼치기" : "메뉴 접기"}
            onClick={toggleCollapsed}
          >
            <SidebarIcon />
          </button>
        </div>
        <details
          ref={detailsRef}
          open
          className="solution-sidebar-details"
          // 서랍 바깥(흐린 배경)을 누르면 닫는다. 배경은 details의 ::after다.
          onClick={(e) => {
            if (e.target === e.currentTarget) closeMenu();
          }}
          onKeyDown={(e) => {
            if (e.key === "Escape" && detailsRef.current?.open) {
              closeMenu();
              summaryRef.current?.focus();
            }
          }}
          onToggle={(e) => {
            if (e.currentTarget.open && collapsible())
              e.currentTarget.querySelector<HTMLElement>("nav a")?.focus();
          }}
        >
          <summary ref={summaryRef}>{summaryTitle}</summary>
          <div className="drawer">
            <div className="drawer-head">
              <p className="eyebrow">{title}</p>
              <button
                type="button"
                className="sidebar-toggle"
                aria-label="메뉴 닫기"
                onClick={() => {
                  closeMenu();
                  summaryRef.current?.focus();
                }}
              >
                ✕
              </button>
            </div>
            <nav>
              {[...new Set(screens.map((s) => s.group))].map((group) => (
                <section key={group}>
                  <h2>{group}</h2>
                  {screens
                    .filter((s) => s.group === group)
                    .map((s) => (
                      <NavLink
                        key={s.path}
                        to={`${base}/${s.path}`}
                        onClick={closeMenu}
                      >
                        <span>{s.id}</span> {s.label}
                      </NavLink>
                    ))}
                </section>
              ))}
              <section>
                <h2>다른 앱</h2>
                {others.map((o) => (
                  <NavLink key={o.to} to={o.to} onClick={closeMenu}>
                    {o.label}
                  </NavLink>
                ))}
              </section>
            </nav>
          </div>
        </details>
      </aside>
      <div className="solution-content">
        <Outlet />
      </div>
    </div>
  );
}

function SidebarIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      aria-hidden="true"
    >
      <rect x="1.5" y="2.5" width="13" height="11" rx="2" />
      <path d="M6 2.5v11" />
    </svg>
  );
}
