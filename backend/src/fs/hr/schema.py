"""HR 요청 본문 (DSN-30 모듈 설계). 범위 키·내부 id는 클라이언트가 보내지 않는다."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

CODE = r"^[A-Z0-9][A-Z0-9_-]{0,29}$"
TitleKind = Literal["GRADE", "DUTY"]
PatternKind = Literal["DAY", "TWO_SHIFT", "THREE_SHIFT"]
AppointmentKind = Literal[
    "HIRE", "TRANSFER", "PROMOTION", "DUTY", "LEAVE", "RETURN", "RETIRE"
]


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")


class DepartmentCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = Field(None, alias="parentId")
    display_order: int = Field(1, alias="displayOrder", ge=1)
    is_active: bool = Field(True, alias="isActive")


class DepartmentUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    parent_id: int | None = Field(None, alias="parentId")
    display_order: int | None = Field(None, alias="displayOrder", ge=1)
    is_active: bool | None = Field(None, alias="isActive")


class TitleCreate(ApiModel):
    title_kind: TitleKind = Field(alias="titleKind")
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=60)
    rank_order: int = Field(alias="rankOrder", ge=1)
    is_head: bool = Field(False, alias="isHead")


class TitleUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    rank_order: int | None = Field(None, alias="rankOrder", ge=1)
    is_head: bool | None = Field(None, alias="isHead")


class WorkPatternCreate(ApiModel):
    code: str = Field(pattern=CODE)
    name: str = Field(min_length=1, max_length=60)
    pattern_kind: PatternKind = Field(alias="patternKind")
    start_time: time = Field(alias="startTime")
    scheduled_minutes: int = Field(alias="scheduledMinutes", ge=1, le=720)
    break_minutes: int = Field(60, alias="breakMinutes", ge=0, le=480)
    works_weekend: bool = Field(False, alias="worksWeekend")


class WorkPatternUpdate(ApiModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    pattern_kind: PatternKind | None = Field(None, alias="patternKind")
    start_time: time | None = Field(None, alias="startTime")
    scheduled_minutes: int | None = Field(None, alias="scheduledMinutes", ge=1, le=720)
    break_minutes: int | None = Field(None, alias="breakMinutes", ge=0, le=480)
    works_weekend: bool | None = Field(None, alias="worksWeekend")


class EmployeeCreate(ApiModel):
    """사원 등록. 최초 소속은 입사(HIRE) 발령으로 함께 확정한다."""

    employee_code: str = Field(alias="employeeCode", pattern=CODE)
    name: str = Field(min_length=1, max_length=60)
    hire_date: date = Field(alias="hireDate")
    department_id: int = Field(alias="departmentId")
    grade_id: int = Field(alias="gradeId")
    duty_id: int | None = Field(None, alias="dutyId")
    work_pattern_id: int = Field(alias="workPatternId")


class EmployeeUpdate(ApiModel):
    """부서·직위·직책·재직 상태는 바꾸지 않는다 — 발령으로만 바뀐다(DSN-30 F03)."""

    name: str | None = Field(None, min_length=1, max_length=60)
    work_pattern_id: int | None = Field(None, alias="workPatternId")


class AppointmentCreate(ApiModel):
    employee_id: int = Field(alias="employeeId")
    kind: AppointmentKind
    effective_date: date = Field(alias="effectiveDate")
    department_id: int | None = Field(None, alias="departmentId")
    grade_id: int | None = Field(None, alias="gradeId")
    duty_id: int | None = Field(None, alias="dutyId")
    reason: str | None = Field(None, min_length=2, max_length=200)


MONTH = r"^[0-9]{4}-(0[1-9]|1[0-2])$"
YEAR = r"^[0-9]{4}$"
DAYS = r"^\d{1,3}(\.[05])?$"  # numeric(4,1), 반일은 .5
AttendanceStatus = Literal[
    "NORMAL", "LATE", "EARLY", "ABSENT", "LEAVE", "HALF_LEAVE", "OFF"
]
LeaveKind = Literal["ANNUAL", "HALF_AM", "HALF_PM", "SICK", "SPECIAL"]


class MonthBody(ApiModel):
    month: str = Field(pattern=MONTH)


class AttendanceUpdate(ApiModel):
    """예외만 고친다. 날짜·사원은 바꾸지 않는다(자동 생성이 만든 행)."""

    status: AttendanceStatus | None = None
    clock_in: datetime | None = Field(None, alias="clockIn")
    clock_out: datetime | None = Field(None, alias="clockOut")
    overtime_minutes: int | None = Field(None, alias="overtimeMinutes", ge=0, le=960)
    night_minutes: int | None = Field(None, alias="nightMinutes", ge=0, le=960)
    holiday_minutes: int | None = Field(None, alias="holidayMinutes", ge=0, le=960)
    note: str | None = Field(None, max_length=200)


class LeaveBalanceCreate(ApiModel):
    employee_id: int = Field(alias="employeeId")
    leave_year: str = Field(alias="leaveYear", pattern=YEAR)
    granted_days: str = Field(alias="grantedDays", pattern=DAYS)


class LeaveBalanceUpdate(ApiModel):
    granted_days: str = Field(alias="grantedDays", pattern=DAYS)


class LeaveRequestCreate(ApiModel):
    employee_id: int = Field(alias="employeeId")
    leave_kind: LeaveKind = Field(alias="leaveKind")
    from_date: date = Field(alias="fromDate")
    to_date: date = Field(alias="toDate")
    days: str = Field(pattern=DAYS)
    reason: str | None = Field(None, min_length=2, max_length=200)


class LeaveDecision(ApiModel):
    approver_code: str = Field(alias="approverCode", pattern=CODE)
    reason: str | None = Field(None, min_length=2, max_length=200)
