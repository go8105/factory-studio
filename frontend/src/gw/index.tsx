import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { GwLayout } from "./GwLayout";
import { Dashboard } from "./Dashboard";
import { Documents } from "./Documents";
import { Board } from "./Board";
import { Masters } from "./Masters";
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
        <Route path="people" element={<Masters kind="people" />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
