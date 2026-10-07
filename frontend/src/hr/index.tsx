// HR 라우트 묶음. App에서 lazy로 불러 포털 첫 번들에서 분리한다.
import { Navigate, Route, Routes } from "react-router-dom";
import { NotFound } from "../shared/components";
import { Appointments } from "./Appointments";
import { Attendance } from "./Attendance";
import { AttendanceCloses } from "./AttendanceCloses";
import { Departments } from "./Departments";
import { Employees } from "./Employees";
import { HrLayout } from "./HrLayout";
import { Leaves } from "./Leaves";
import { Titles } from "./Titles";
import { WorkPatterns } from "./WorkPatterns";

export default function HrRoutes() {
  return (
    <Routes>
      <Route element={<HrLayout />}>
        <Route index element={<Navigate to="employees" replace />} />
        <Route path="departments" element={<Departments />} />
        <Route path="titles" element={<Titles />} />
        <Route path="work-patterns" element={<WorkPatterns />} />
        <Route path="employees" element={<Employees />} />
        <Route path="appointments" element={<Appointments />} />
        <Route path="attendance" element={<Attendance />} />
        <Route path="attendance-closes" element={<AttendanceCloses />} />
        <Route path="leaves" element={<Leaves />} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  );
}
