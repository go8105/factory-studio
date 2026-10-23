// CMMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { CmmsLayout } from "./CmmsLayout";
import { Assets } from "./Assets";
import { FailureCodes } from "./FailureCodes";
import { Cost } from "./Cost";
import { Metrics } from "./Metrics";
import { Overview } from "./Overview";
import { PmPlans } from "./PmPlans";
import { Signals } from "./Signals";
import { SpareParts } from "./SpareParts";
import { Technicians } from "./Technicians";
import { WorkOrders } from "./WorkOrders";

export default function CmmsRoutes() {
  return (
    <Routes>
      <Route element={<CmmsLayout />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="overview" element={<Overview />} />
        <Route path="signals" element={<Signals />} />
        <Route path="work-orders" element={<WorkOrders />} />
        <Route path="pm-plans" element={<PmPlans />} />
        <Route path="assets" element={<Assets />} />
        <Route path="spare-parts" element={<SpareParts />} />
        <Route path="metrics" element={<Metrics />} />
        <Route path="cost" element={<Cost />} />
        <Route path="technicians" element={<Technicians />} />
        <Route path="failure-codes" element={<FailureCodes />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
