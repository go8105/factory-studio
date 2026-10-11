import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Projects } from "./Projects";
import { NotFound } from "../shared/components";
import "./Flow.css";
function HomeRedirect() {
  const { search } = useLocation();
  return <Navigate replace to={`boards${search}`} />;
}
export default function WorkOsRoutes() {
  return (
    <div className="flow-shell">
      <Routes>
        <Route index element={<HomeRedirect />} />
        <Route path="boards" element={<Projects />} />
        <Route path="my-tasks" element={<Projects myTasks />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </div>
  );
}
