// CMMS 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { CmmsLayout } from "./CmmsLayout";
import { Assets } from "./Assets";
import { FailureCodes } from "./FailureCodes";
import { Signals } from "./Signals";
import { Technicians } from "./Technicians";
import { WorkOrders } from "./WorkOrders";

export default function CmmsRoutes() {
  return (
    <Routes>
      <Route element={<CmmsLayout />}>
        <Route index element={<Navigate to="work-orders" replace />} />
        <Route path="signals" element={<Signals />} />
        <Route path="work-orders" element={<WorkOrders />} />
        <Route path="assets" element={<Assets />} />
        <Route path="technicians" element={<Technicians />} />
        <Route path="failure-codes" element={<FailureCodes />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
