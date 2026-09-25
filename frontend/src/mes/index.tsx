// MES 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { MesLayout } from "./MesLayout";
import { Sites } from "./Sites";
import { Equipments } from "./Equipments";
import { Items } from "./Items";
import { Processes } from "./Processes";

export default function MesRoutes() {
  return (
    <Routes>
      <Route element={<MesLayout />}>
        {/* 대시보드(M-01)가 생기기 전까지는 첫 기준정보 화면으로 들어간다. */}
        <Route index element={<Navigate to="sites" replace />} />
        <Route path="sites" element={<Sites />} />
        <Route path="equipments" element={<Equipments />} />
        <Route path="items" element={<Items />} />
        <Route path="processes" element={<Processes />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
