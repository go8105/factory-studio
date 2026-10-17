// MES·ERP·FEMS 공통 솔루션 레이아웃: 좌측 사이드바(넓은 화면 접기, 좁은 화면 서랍) + 본문 (UI-01)
import { useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useFavorites } from "./favorites";
import { MenuIcon } from "./MenuIcon";
import { ErrorNotice } from "./components";
import { menuByKey, type Menu, type Screen } from "./menuCatalog";

export type { Screen } from "./menuCatalog";

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
  beforeContent,
  content,
  linkQuery,
}: {
  name: string;
  title: string;
  base: string;
  screens: Screen[];
  others: { to: string; label: string }[];
  beforeContent?: ReactNode;
  content?: ReactNode;
  linkQuery?: string;
}) {
  const location = useLocation();
  const favorites = useFavorites();
  const favoriteMode = favorites.data?.sidebarMode === "favorites";
  const moduleKey = base.slice(1);
  const selected = favorites.data?.menuIds ?? [];
  const visibleScreens: Menu[] = favoriteMode
    ? selected.flatMap((key) => {
        const menu = menuByKey.get(key);
        return menu ? [menu] : [];
      })
    : screens.map((screen) => menuByKey.get(`${moduleKey}:${screen.path}`)!);
  function menuRow(screen: Menu) {
    const key = screen.key;
    const pinned = selected.includes(key);
    return (
      <div className="sidebar-menu-row" key={screen.key}>
        <NavLink
          to={
            linkQuery && screen.to.startsWith(base + "/")
              ? screen.to + "?" + linkQuery
              : screen.to
          }
          onClick={closeMenu}
          title={`${screen.solution} · ${screen.label}`}
          aria-label={`${screen.id} ${screen.label} · ${screen.solution}`}
        >
          <span className="sidebar-menu-icon">
            <MenuIcon menu={screen} />
          </span>
          <span className="sidebar-menu-label">
            <span>{screen.id}</span> {screen.label}
            {favoriteMode && <small>{screen.solution}</small>}
          </span>
        </NavLink>
        {favorites.data && (
          <button
            className="favorite-icon-button"
            aria-label={`${screen.solution} ${screen.label} 즐겨찾기 ${pinned ? "해제" : "등록"}`}
            aria-pressed={pinned}
            disabled={
              favorites.pending || favorites.loading || favorites.uncertain
            }
            onClick={() =>
              void favorites.save(
                pinned
                  ? selected.filter((id) => id !== key)
                  : [...selected, key],
                favorites.data!.sidebarMode,
              )
            }
          >
            <MenuIcon kind="star" />
          </button>
        )}
      </div>
    );
  }
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
              {!!(favorites.data || favorites.loading || favorites.error) && (
                <>
                  <div
                    className="sidebar-menu-mode"
                    aria-label="사이드바 메뉴 표시"
                  >
                    <button
                      aria-label="즐겨찾기만 보기"
                      aria-pressed={favoriteMode}
                      disabled={
                        !favorites.data ||
                        favorites.pending ||
                        favorites.loading ||
                        favorites.uncertain
                      }
                      onClick={() => void favorites.save(selected, "favorites")}
                    >
                      즐겨찾기
                    </button>
                    <button
                      aria-label="전체 메뉴 보기"
                      aria-pressed={!favoriteMode}
                      disabled={
                        !favorites.data ||
                        favorites.pending ||
                        favorites.loading ||
                        favorites.uncertain
                      }
                      onClick={() => void favorites.save(selected, "all")}
                    >
                      전체 메뉴
                    </button>
                  </div>
                  <ErrorNotice
                    error={favorites.error}
                    retry={
                      favorites.pending
                        ? undefined
                        : () => void favorites.reload()
                    }
                  />
                </>
              )}
              {favoriteMode ? (
                <section>
                  <h2>즐겨찾기</h2>
                  {visibleScreens.map(menuRow)}
                  {visibleScreens.length === 0 && (
                    <p className="sidebar-favorite-empty">
                      등록된 즐겨찾기 메뉴가 없습니다. 전체 메뉴에서 선택하거나
                      내 공간에서 추가하세요.
                    </p>
                  )}
                  <NavLink
                    to={`/workspace?menus=${moduleKey}`}
                    title="메뉴 추가·순서 편집"
                    onClick={closeMenu}
                  >
                    메뉴 추가·순서 편집
                  </NavLink>
                </section>
              ) : (
                [...new Set(visibleScreens.map((s) => s.group))].map(
                  (group) => (
                    <section key={group}>
                      <h2>{group}</h2>
                      {visibleScreens
                        .filter((s) => s.group === group)
                        .map(menuRow)}
                    </section>
                  ),
                )
              )}
              <section>
                <h2>{favoriteMode ? "내 공간" : "다른 앱"}</h2>
                {!favoriteMode &&
                  others.map((o) => (
                    <NavLink key={o.to} to={o.to} onClick={closeMenu}>
                      {o.label}
                    </NavLink>
                  ))}
                {favoriteMode && (
                  <NavLink to="/home" title="앱 런처" onClick={closeMenu}>
                    앱 런처
                  </NavLink>
                )}
                {!favoriteMode && (
                  <NavLink
                    to={`/workspace?menus=${moduleKey}`}
                    title="메뉴 추가·순서 편집"
                    onClick={closeMenu}
                  >
                    즐겨찾기 구성
                  </NavLink>
                )}
                {/* 업무 화면에는 바닥글이 없으므로 공통 안내를 여기에 둔다(UI-02). */}
                <NavLink
                  to="/help/common"
                  title="공통 이용 안내"
                  onClick={closeMenu}
                >
                  공통 이용 안내
                </NavLink>
              </section>
            </nav>
          </div>
        </details>
      </aside>
      <div className="solution-content">
        {beforeContent}
        {content ?? <Outlet />}
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
