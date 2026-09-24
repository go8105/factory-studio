// FEMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { FemsLayout } from "./FemsLayout";
import { EnergySources } from "./EnergySources";
import { Readings } from "./Readings";
import { Equipments } from "./Equipments";
export default function FemsRoutes() {
  return (
    <Routes>
      <Route element={<FemsLayout />}>
        <Route index element={<Navigate to="readings" replace />} />
        <Route path="equipments" element={<Equipments />} />
        <Route path="readings" element={<Readings />} />
        <Route path="energy-sources" element={<EnergySources />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
