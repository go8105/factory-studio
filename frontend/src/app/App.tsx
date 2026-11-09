import { AccountSecurity } from "../portal/AccountSecurity";
import {
  Link,
  NavLink,
  Navigate,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { lazy, Suspense, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  otherSolutions,
  solutionFromPath,
  solutionLabel,
} from "../shared/menuCatalog";
import "./HomeShell.css";
import { SessionProvider, useSession } from "./session";
import { api } from "../shared/api";
import { FavoritesProvider } from "../shared/favorites";
import { ErrorNotice, Loading, NotFound } from "../shared/components";
import { About } from "../portal/About";
import { Entry } from "../portal/Entry";
import { Holidays } from "../portal/Holidays";
import { Home } from "../portal/Home";
// Markdown 렌더러와 정적 콘텐츠는 첫 화면에 필요 없으므로 분리한다.
const content = () => import("../portal/ContentPages");
const FlowMap = lazy(() => content().then((m) => ({ default: m.FlowMap })));
const Cards = lazy(() => content().then((m) => ({ default: m.Cards })));
const Help = lazy(() => content().then((m) => ({ default: m.Help })));
import { Workspace } from "../portal/Workspace";
import { Records } from "../portal/Records";
const FemsRoutes = lazy(() => import("../fems"));
const MesRoutes = lazy(() => import("../mes"));
const ErpRoutes = lazy(() => import("../erp"));
const QmsRoutes = lazy(() => import("../qms"));
const WmsRoutes = lazy(() => import("../wms"));
const BemsRoutes = lazy(() => import("../bems"));
const SpcRoutes = lazy(() => import("../spc"));
const CmmsRoutes = lazy(() => import("../cmms"));
const HrRoutes = lazy(() => import("../hr"));
const WorkOsRoutes = lazy(() => import("../flow"));
const GwRoutes = lazy(() => import("../gw"));
const VisionLab = lazy(() => import("../factory/VisionLab"));
const Factory = lazy(() => import("../factory/Factory"));
const CadCam = lazy(() => import("../cad-cam/CadCam"));

// 헤더 드롭다운. 사이드바 서랍과 같이 <details>로 만든다(새 라이브러리 없음).
function HeaderMenu({
  summary,
  label,
  children,
}: {
  summary: string;
  label: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDetailsElement>(null);
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  const close = () => {
    if (ref.current) ref.current.open = false;
    setOpen(false);
  };
  // 이동하면 닫는다. 메뉴 안의 링크를 눌러 화면이 바뀌는 경우를 포함한다.
  useEffect(close, [pathname]);
  useEffect(() => {
    const outside = (e: MouseEvent) => {
      if (
        ref.current?.open &&
        e.target instanceof Node &&
        !ref.current.contains(e.target)
      )
        close();
    };
    document.addEventListener("click", outside);
    return () => document.removeEventListener("click", outside);
  }, []);
  return (
    <details
      className="header-menu"
      aria-label={label}
      ref={ref}
      // 닫혀 있으면 항목을 그리지 않는다. 접근성 트리와 화면의 링크 목록이 같아진다.
      onToggle={(e) => setOpen(e.currentTarget.open)}
      onKeyDown={(e) => {
        if (e.key === "Escape" && ref.current?.open) {
          close();
          ref.current.querySelector("summary")?.focus();
        }
      }}
    >
      <summary>{summary}</summary>
      {open && <div className="header-menu-list">{children}</div>}
    </details>
  );
}

function Layout() {
  const { session, setSession, busy, navigationBlocked, fail } = useSession();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>();
  const [leaving, setLeaving] = useState(false);
  const { pathname } = useLocation();
  // 업무 화면(솔루션)은 사이드바·본문이 헤더 아래 높이를 모두 쓴다. 바닥글은 포털 화면에만 둔다.
  const work =
    /^\/(fems|mes|erp|qms|wms|bems|spc|cmms|gw|hr|work-os|cad-cam)(\/|$)/.test(
      pathname,
    );
  const current = solutionFromPath(pathname);
  async function logout() {
    setLeaving(true);
    try {
      await api("/sessions/current", {
        method: "DELETE",
        csrf: session?.csrfToken,
      });
      setSession(null);
      navigate("/");
    } catch (e) {
      setError(e);
      fail(e);
    } finally {
      setLeaving(false);
    }
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        본문으로 건너뛰기
      </a>
      <header
        className={`site-header${pathname === "/home" ? " launcher-header" : ""}`}
        onClickCapture={(e) => {
          if (busy) e.preventDefault();
        }}
        aria-busy={busy}
      >
        <Link className="brand" to={session ? "/home" : "/"}>
          <img className="brand-mark" src="/logo.svg" alt="" />
          Factory Studio
          <span className="brand-tagline">독립 솔루션 제조 업무 플랫폼</span>
        </Link>
        <nav aria-label="주 메뉴">
          {/* 앱 전환기. 요약에 현재 솔루션 이름이 보여 어디에 있는지 헤더가 알려 준다.
              11개 솔루션과 CAD·CAM·3D 공장·전체 흐름이 모두 여기 한 곳에 있다. */}
          {session && (
            <HeaderMenu
              summary={current ? solutionLabel(current) : "앱 선택"}
              label="앱 전환"
            >
              <NavLink to="/home">앱 런처</NavLink>
              {otherSolutions(current ?? "").map((o) => (
                <NavLink key={o.to} to={o.to}>
                  {o.label}
                </NavLink>
              ))}
              <NavLink to="/cad-cam">CAD·CAM</NavLink>
              <NavLink to="/factory">3D 공장</NavLink>
              <NavLink to="/flow">전체 흐름</NavLink>
            </HeaderMenu>
          )}
          <NavLink to="/help">도움말</NavLink>
          {session ? (
            <HeaderMenu summary="계정" label="계정 메뉴">
              <NavLink to="/workspace">내 공간</NavLink>
              <NavLink to="/holidays">휴일 달력</NavLink>
              {session.actorKind === "MEMBER" && (
                <NavLink to="/account/security">내 계정 보안</NavLink>
              )}
              {session.roles.includes("ADMIN") && (
                <>
                  <NavLink to="/hr/users">사용자 관리</NavLink>
                  <NavLink to="/records">운영 기록</NavLink>
                </>
              )}
              <button
                className="link-button"
                disabled={busy || navigationBlocked || leaving}
                onClick={() => void logout()}
              >
                나가기
              </button>
            </HeaderMenu>
          ) : (
            <Link to="/">시작하기</Link>
          )}
        </nav>
      </header>
      {/* 업무 화면(솔루션·3D)은 사이드바·캔버스가 폭을 직접 쓴다. */}
      <main
        id="main"
        key={pathname}
        tabIndex={-1}
        className={work ? "wide" : undefined}
      >
        <ErrorNotice error={error} />
        <Suspense fallback={<Loading />}>
          <Outlet />
        </Suspense>
      </main>
      {!work && (
        <footer
          className={`site-footer${pathname === "/home" ? " launcher-footer" : ""}`}
        >
          <span>Factory Studio</span>
          <span>합성 데이터로 구성한 제조 업무 포트폴리오</span>
          <Link to="/help/common">공통 이용 안내</Link>
        </footer>
      )}
    </div>
  );
}
function Private() {
  return useSession().session ? <Outlet /> : <Navigate to="/" replace />;
}
function Admin() {
  return useSession().session?.roles.includes("ADMIN") ? (
    <Records />
  ) : (
    <NotFound />
  );
}
function PortalRoutes() {
  const location = useLocation();
  const { busy, navigationBlocked } = useSession();
  const visibleLocation = useRef(location);
  const blocked = busy || navigationBlocked;
  // 초기화가 끝날 때까지 뒤로가기·프로그램 이동도 현재 화면을 유지한다.
  if (!blocked) visibleLocation.current = location;
  return (
    <div
      onClickCapture={(event) => {
        if (
          blocked &&
          event.target instanceof Element &&
          event.target.closest("a")
        ) {
          event.preventDefault();
          event.stopPropagation();
        }
      }}
      onAuxClickCapture={(event) => {
        if (blocked) event.preventDefault();
      }}
    >
      <Routes location={visibleLocation.current}>
        <Route path="/" element={<Entry />} />
        <Route element={<Layout />}>
          <Route path="/help/*" element={<Help />} />
          <Route
            path="/account/recovery"
            element={<AccountSecurity recovery />}
          />
          <Route element={<Private />}>
            <Route path="/home" element={<Home />} />
            <Route path="/account/security" element={<AccountSecurity />} />
            <Route path="/cad-cam" element={<CadCam />} />
            <Route path="/factory" element={<Factory />} />
            <Route path="/factory/vision-lab" element={<VisionLab />} />
            <Route path="/flow" element={<FlowMap />} />
            <Route path="/cards/:card?" element={<Cards />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/holidays" element={<Holidays />} />
            <Route path="/records" element={<Admin />} />
            <Route path="/fems/*" element={<FemsRoutes />} />
            <Route path="/mes/*" element={<MesRoutes />} />
            <Route path="/erp/*" element={<ErpRoutes />} />
            <Route path="/qms/*" element={<QmsRoutes />} />
            <Route path="/wms/*" element={<WmsRoutes />} />
            <Route path="/bems/*" element={<BemsRoutes />} />
            <Route path="/spc/*" element={<SpcRoutes />} />
            <Route path="/cmms/*" element={<CmmsRoutes />} />
            <Route path="/hr/*" element={<HrRoutes />} />
            <Route path="/work-os/*" element={<WorkOsRoutes />} />
            <Route path="/gw/*" element={<GwRoutes />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </div>
  );
}

function SessionApp() {
  return (
    <SessionProvider>
      <FavoritesProvider>
        <PortalRoutes />
      </FavoritesProvider>
    </SessionProvider>
  );
}

// 공개 소개는 세션 확인/API 응답 없이 열리며 기존 인증 흐름은 그대로 둔다.
export function App() {
  return (
    <Routes>
      <Route path="/about" element={<About />} />
      <Route path="*" element={<SessionApp />} />
    </Routes>
  );
}
