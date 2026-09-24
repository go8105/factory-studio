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
import { useState } from "react";
import { SessionProvider, useSession } from "./session";
import { api } from "../shared/api";
import { ErrorNotice, NotFound } from "../shared/components";
import { Entry } from "../portal/Entry";
import { Home } from "../portal/Home";
import { FlowMap, Cards, Help } from "../portal/ContentPages";
import { Workspace } from "../portal/Workspace";
import { Records } from "../portal/Records";
function Layout() {
  const { session, setSession, busy, fail } = useSession();
  const navigate = useNavigate();
  const [error, setError] = useState<unknown>();
  const [leaving, setLeaving] = useState(false);
  const { pathname } = useLocation();
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
    <>
      <a className="skip-link" href="#main">
        본문으로 건너뛰기
      </a>
      <header
        className="site-header"
        onClickCapture={(e) => {
          if (busy) e.preventDefault();
        }}
        aria-busy={busy}
      >
        <Link className="brand" to={session ? "/home" : "/"}>
          Factory Studio<span>제조 현장의 세 시스템</span>
        </Link>
        <nav aria-label="주 메뉴">
          {session && (
            <>
              <NavLink to="/home">앱 런처</NavLink>
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
              disabled={busy || leaving}
              onClick={() => void logout()}
            >
              나가기
            </button>
          ) : (
            <Link to="/">시작하기</Link>
          )}
        </nav>
      </header>
      <main id="main" key={pathname} tabIndex={-1}>
        <ErrorNotice error={error} />
        <Outlet />
      </main>
      <footer className="site-footer">
        <span>Factory Studio</span>
        <span>합성 데이터로 구성한 제조 업무 포트폴리오</span>
        <Link to="/help/common">공통 이용 안내</Link>
      </footer>
    </>
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
export function App() {
  return (
    <SessionProvider>
      <Routes>
        <Route path="/" element={<Entry />} />
        <Route element={<Layout />}>
          <Route path="/help/*" element={<Help />} />
          <Route element={<Private />}>
            <Route path="/home" element={<Home />} />
            <Route path="/flow" element={<FlowMap />} />
            <Route path="/cards/:card?" element={<Cards />} />
            <Route path="/workspace" element={<Workspace />} />
            <Route path="/records" element={<Admin />} />
          </Route>
          <Route path="*" element={<NotFound />} />
        </Route>
      </Routes>
    </SessionProvider>
  );
}
