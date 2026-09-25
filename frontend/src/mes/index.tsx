// MES 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { MesLayout } from "./MesLayout";
import { Sites } from "./Sites";
import { Equipments } from "./Equipments";
import { Items } from "./Items";
import { Processes } from "./Processes";
import { Routes as RouteVersions } from "./Routes";
import { Boms } from "./Boms";
import { Plans } from "./Plans";
import { Orders } from "./Orders";
import { Lots } from "./Lots";
import { Executions } from "./Executions";
import { Materials } from "./Materials";
import { Results } from "./Results";

export default function MesRoutes() {
  return (
    <Routes>
      <Route element={<MesLayout />}>
        {/* 대시보드(M-01)가 생기기 전까지는 생산계획으로 들어간다. */}
        <Route index element={<Navigate to="production-plans" replace />} />
        <Route path="production-plans" element={<Plans />} />
        <Route path="work-orders" element={<Orders />} />
        <Route path="lots" element={<Lots />} />
        <Route path="executions" element={<Executions />} />
        <Route path="material-issues" element={<Materials />} />
        <Route path="results" element={<Results />} />
        <Route path="sites" element={<Sites />} />
        <Route path="equipments" element={<Equipments />} />
        <Route path="items" element={<Items />} />
        <Route path="processes" element={<Processes />} />
        <Route path="routes" element={<RouteVersions />} />
        <Route path="boms" element={<Boms />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
