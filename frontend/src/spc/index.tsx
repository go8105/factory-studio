// SPC 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { SpcLayout } from "./SpcLayout";
import { Dashboard } from "./Dashboard";
import { Chart } from "./Chart";
import { Capability } from "./Capability";
import { Measure } from "./Measure";
import { Signals } from "./Signals";
import { Subgroups } from "./Subgroups";
import { Characteristics } from "./Characteristics";
import { Violations } from "./Violations";

export default function SpcRoutes() {
  return (
    <Routes>
      <Route element={<SpcLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="chart" element={<Chart />} />
        <Route path="capability" element={<Capability />} />
        <Route path="measure" element={<Measure />} />
        <Route path="signals" element={<Signals />} />
        <Route path="subgroups" element={<Subgroups />} />
        <Route path="characteristics" element={<Characteristics />} />
        <Route path="violations" element={<Violations />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
