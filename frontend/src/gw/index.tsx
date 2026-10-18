import { Operations } from "./Operations";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { NotFound } from "../shared/components";
import { GwLayout } from "./GwLayout";
import { Dashboard } from "./Dashboard";
import { Documents } from "./Documents";
import { Board } from "./Board";
import { Masters } from "./Masters";
import { Authority } from "./Authority";
import { Delegations } from "./Delegations";
import { People, Organization } from "./Organization";
import { Calendar, Notifications, Chat } from "./Collaboration";
import "./gw.css";
import { LegacyFlowRedirect } from "../flow/LegacyFlowRedirect";
function DefaultGw() {
  const location = useLocation();
  return <Navigate to={"dashboard" + location.search} replace />;
}
export default function GwRoutes() {
  return (
    <Routes>
      <Route element={<GwLayout />}>
        <Route index element={<DefaultGw />} />
        <Route path="projects" element={<LegacyFlowRedirect page="boards" />} />
        <Route
          path="my-tasks"
          element={<LegacyFlowRedirect page="my-tasks" />}
        />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="operations" element={<Operations />} />
        <Route path="drafts" element={<Documents box="drafts" />} />
        <Route path="pending" element={<Documents box="pending" />} />
        <Route path="documents" element={<Documents box="archive" />} />
        <Route path="board" element={<Board />} />
        <Route path="routes" element={<Masters kind="routes" />} />
        <Route path="authority-rules" element={<Authority />} />
        <Route path="delegations" element={<Delegations />} />
        <Route path="people" element={<People />} />
        <Route path="organization" element={<Organization />} />
        <Route path="calendar" element={<Calendar />} />
        <Route path="notifications" element={<Notifications />} />
        <Route path="chat" element={<Chat />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
