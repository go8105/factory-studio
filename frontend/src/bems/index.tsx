// BEMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { BemsLayout } from "./BemsLayout";
import { Dashboard } from "./Dashboard";
import { Breakdown } from "./Breakdown";
import { Environment } from "./Environment";
import { Hvac } from "./Hvac";
import { Schedules } from "./Schedules";
import { Alarms } from "./Alarms";
import { Lighting } from "./Lighting";
import { Comfort } from "./Comfort";
import { Peak } from "./Peak";
import { Energy } from "./Energy";
import { Costs } from "./Costs";
import { Reviews } from "./Reviews";
import { Zones } from "./Zones";

export default function BemsRoutes() {
  return (
    <Routes>
      <Route element={<BemsLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="breakdown" element={<Breakdown />} />
        <Route path="environment" element={<Environment />} />
        <Route path="hvac" element={<Hvac />} />
        <Route path="schedules" element={<Schedules />} />
        <Route path="lighting" element={<Lighting />} />
        <Route path="peak" element={<Peak />} />
        <Route path="alarms" element={<Alarms />} />
        <Route path="comfort" element={<Comfort />} />
        <Route path="energy" element={<Energy />} />
        <Route path="costs" element={<Costs />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="zones" element={<Zones />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
