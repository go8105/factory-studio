import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { GwLayout } from "./GwLayout";
import { Dashboard } from "./Dashboard";
import { Documents } from "./Documents";
import { Board } from "./Board";
import { Masters } from "./Masters";
import { Authority } from "./Authority";
import { Delegations } from "./Delegations";
import { People, Organization } from "./Organization";
import "./gw.css";
export default function GwRoutes() {
  return (
    <Routes>
      <Route element={<GwLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="drafts" element={<Documents box="drafts" />} />
        <Route path="pending" element={<Documents box="pending" />} />
        <Route path="documents" element={<Documents box="archive" />} />
        <Route path="board" element={<Board />} />
        <Route path="routes" element={<Masters kind="routes" />} />
        <Route path="authority-rules" element={<Authority />} />
        <Route path="delegations" element={<Delegations />} />
        <Route path="people" element={<People />} />
        <Route path="organization" element={<Organization />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
