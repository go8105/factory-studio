// FEMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { FemsLayout } from "./FemsLayout";
import { EnergySources } from "./EnergySources";
import { Readings } from "./Readings";
import { Dashboard } from "./Dashboard";
import { Allocations } from "./Allocations";
import { Emissions } from "./Emissions";
import { Targets } from "./Targets";
import { Equipments } from "./Equipments";
import { Tariffs } from "./Tariffs";
export default function FemsRoutes() {
  return (
    <Routes>
      <Route element={<FemsLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="equipments" element={<Equipments />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="readings" element={<Readings />} />
        <Route path="allocations" element={<Allocations />} />
        <Route path="emissions" element={<Emissions />} />
        <Route path="targets" element={<Targets />} />
        <Route path="energy-sources" element={<EnergySources />} />
        <Route path="tariffs" element={<Tariffs />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
