// HR 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { Appointments } from "./Appointments";
import { Attendance } from "./Attendance";
import { AttendanceCloses } from "./AttendanceCloses";
import { Departments } from "./Departments";
import { Employees } from "./Employees";
import { HrLayout } from "./HrLayout";
import { Cost } from "./Cost";
import { Leaves } from "./Leaves";
import { Me } from "./Me";
import { Overview } from "./Overview";
import { Payroll } from "./Payroll";
import { Payslips } from "./Payslips";
import { Reviews } from "./Reviews";
import { PayStandards } from "./PayStandards";
import { Titles } from "./Titles";
import { Work } from "./Work";
import { WorkPatterns } from "./WorkPatterns";

export default function HrRoutes() {
  return (
    <Routes>
      <Route element={<HrLayout />}>
        <Route index element={<Navigate to="overview" replace />} />
        <Route path="work" element={<Work />} />
        <Route path="work-demo" element={<Work demo />} />
        <Route path="overview" element={<Overview />} />
        <Route path="departments" element={<Departments />} />
        <Route path="titles" element={<Titles />} />
        <Route path="work-patterns" element={<WorkPatterns />} />
        <Route path="employees" element={<Employees />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="attendance-closes" element={<AttendanceCloses />} />
        <Route path="leaves" element={<Leaves />} />
        <Route path="pay-standards" element={<PayStandards />} />
        <Route path="payroll" element={<Payroll />} />
        <Route path="payslips" element={<Payslips />} />
        <Route path="reviews" element={<Reviews />} />
        <Route path="cost" element={<Cost />} />
        <Route path="me" element={<Me />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
