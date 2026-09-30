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
import { lazy, Suspense, useRef, useState } from "react";
import "./HomeShell.css";
import { SessionProvider, useSession } from "./session";
import { api } from "../shared/api";
import { ErrorNotice, Loading, NotFound } from "../shared/components";
import { Entry } from "../portal/Entry";
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
const VisionLab = lazy(() => import("../factory/VisionLab"));
const Factory = lazy(() => import("../factory/Factory"));
function Layout() {
  const { session, setSession, busy, navigationBlocked, fail } = useSession();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>();
  const [leaving, setLeaving] = useState(false);
  const { pathname } = useLocation();
  // 업무 화면(솔루션)은 사이드바·본문이 헤더 아래 높이를 모두 쓴다. 바닥글은 포털 화면에만 둔다.
  const work = /^\/(fems|mes|erp|qms|wms|bems)(\/|$)/.test(pathname);
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
          <span className="brand-tagline">제조 현장의 올인원 시스템</span>
        </Link>
        <nav aria-label="주 메뉴">
          {session && (
            <>
              <NavLink to="/home">앱 런처</NavLink>
              <NavLink to="/factory">3D 공장</NavLink>
              <NavLink to="/flow">전체 흐름</NavLink>
              <NavLink to="/workspace">내 공간</NavLink>
            </>
          )}
          <NavLink to="/help">도움말</NavLink>
          {session?.roles.includes("ADMIN") && (
            <NavLink to="/records">운영 기록</NavLink>
          )}
          {session ? (
            <button
              className="link-button"
              disabled={busy || navigationBlocked || leaving}
              onClick={() => void logout()}
            >
              나가기
            </button>
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
          <Route element={<Private />}>
            <Route path="/home" element={<Home />} />
            <Route path="/factory" element={<Factory />} />
            <Route path="/factory/vision-lab" element={<VisionLab />} />
            <Route path="/flow" element={<FlowMap />} />
            <Route path="/cards/:card?" element={<Cards />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/records" element={<Admin />} />
            <Route path="/fems/*" element={<FemsRoutes />} />
            <Route path="/mes/*" element={<MesRoutes />} />
            <Route path="/erp/*" element={<ErpRoutes />} />
            <Route path="/qms/*" element={<QmsRoutes />} />
            <Route path="/wms/*" element={<WmsRoutes />} />
            <Route path="/bems/*" element={<BemsRoutes />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </div>
  );
}

export function App() {
  return (
    <SessionProvider>
      <PortalRoutes />
    </SessionProvider>
  );
}
