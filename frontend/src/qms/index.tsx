// QMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { QmsLayout } from "./QmsLayout";
import { Dashboard } from "./Dashboard";
import { Pending } from "./Pending";
import { Inspections } from "./Inspections";
import { Holds } from "./Holds";
import { Specs } from "./Specs";
import { DefectTypes } from "./DefectTypes";
import { Gauges } from "./Gauges";
import { ChangeNotices } from "./ChangeNotices";
import { Ncrs } from "./Ncrs";
import { Capas } from "./Capas";
import { Claims } from "./Claims";
import { Suppliers } from "./Suppliers";

export default function QmsRoutes() {
  return (
    <Routes>
      <Route element={<QmsLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="pending" element={<Pending />} />
        <Route path="inspections" element={<Inspections />} />
        <Route path="holds" element={<Holds />} />
        <Route path="specs" element={<Specs />} />
        <Route path="defect-types" element={<DefectTypes />} />
        <Route path="gauges" element={<Gauges />} />
        <Route path="change-notices" element={<ChangeNotices />} />
        <Route path="ncrs" element={<Ncrs />} />
        <Route path="capas" element={<Capas />} />
        <Route path="claims" element={<Claims />} />
        <Route path="suppliers" element={<Suppliers />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
