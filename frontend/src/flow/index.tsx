import {
  Navigate,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { Projects } from "./Projects";
import { NotFound } from "../shared/components";
import { MenuIcon } from "../shared/MenuIcon";
import "./Flow.css";
function HomeRedirect() {
  const { search } = useLocation();
  return <Navigate replace to={`boards${search}`} />;
}
export default function WorkOsRoutes() {
  return (
    <div className="flow-shell">
      <header className="flow-header">
        <NavLink to="/work-os" className="flow-brand">
          <MenuIcon kind="grid" />
          <span>
            Factory Flow<small>Work OS · 프로젝트 관리·협업</small>
          </span>
        </NavLink>
        <nav aria-label="Factory Flow">
          <NavLink to="/work-os/boards">프로젝트 보드</NavLink>
          <NavLink to="/work-os/my-tasks">내 업무</NavLink>
          <NavLink to="/home">전체 솔루션</NavLink>
          <NavLink to="/workspace">내 공간</NavLink>
        </nav>
      </header>
      <Routes>
        <Route index element={<HomeRedirect />} />
        <Route path="boards" element={<Projects />} />
        <Route path="my-tasks" element={<Projects myTasks />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}
