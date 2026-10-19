// WMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { WmsLayout } from "./WmsLayout";
import { Dashboard } from "./Dashboard";
import { Stock } from "./Stock";
import { Sources } from "./Sources";
import { Documents } from "./Documents";
import { Moves } from "./Moves";
import { Warehouses } from "./Warehouses";
import { Inbounds } from "./Inbounds";
import { Reservations } from "./Reservations";
import { Items } from "./Items";
import { Lots } from "./Lots";
import { Counts } from "./Counts";
import { Labels } from "./Labels";
import { Issues } from "./Issues";
import { Putaways } from "./Putaways";
import { Picks } from "./Picks";

export default function WmsRoutes() {
  return (
    <Routes>
      <Route element={<WmsLayout />}>
        <Route index element={<Navigate to="dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="stock" element={<Stock />} />
        <Route path="sources" element={<Sources />} />
        <Route path="documents" element={<Documents />} />
        <Route path="moves" element={<Moves />} />
        <Route path="warehouses" element={<Warehouses />} />
        <Route path="inbounds" element={<Inbounds />} />
        <Route path="labels" element={<Labels />} />
        <Route path="counts" element={<Counts />} />
        <Route path="issues" element={<Issues />} />
        <Route path="putaways" element={<Putaways />} />
        <Route path="reservations" element={<Reservations />} />
        <Route path="picks" element={<Picks />} />
        <Route path="items" element={<Items />} />
        <Route path="lots" element={<Lots />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
