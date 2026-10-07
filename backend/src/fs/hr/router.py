# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""HR API (/api/v1/hr, DSN-30). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.hr import attendance, leave, payroll, service
from fs.hr.schema import (
    AppointmentCreate,
    AttendanceUpdate,
    BonusRuleCreate,
    BonusRuleUpdate,
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeUpdate,
    LeaveBalanceCreate,
    LeaveBalanceUpdate,
    LeaveDecision,
    LeaveRequestCreate,
    MonthBody,
    PayBaseCreate,
    PayBaseItemBody,
    PayBaseUpdate,
    PayItemCreate,
    PayItemUpdate,
    PayrollRunCreate,
    TitleCreate,
    TitleUpdate,
    WorkPatternCreate,
    WorkPatternUpdate,
)

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]

# 공통 엔진: CSRF·멱등 키 확인
_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for name, value in values.items() if name not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _page(rows_total: tuple[list[dict[str, Any]], int], page: Page) -> dict[str, Any]:
    rows, total = rows_total
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


# ── 부서 ────────────────────────────────────────────────────────────────────


@router.get("/departments")
def list_departments(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.departments(
            context,
            filters={"active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/departments", status_code=201)
def post_department(
    payload: DepartmentCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.create_department(
            context, _values(payload, frozenset({"parent_id"})), key
        )
    }


@router.patch("/departments/{row_id}")
def patch_department(
    row_id: int,
    payload: DepartmentUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = _values(payload, frozenset({"parent_id"}))
    return {"data": service.update_department(context, row_id, values, key)}


@router.delete("/departments/{row_id}", status_code=204)
def delete_department(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    service.delete_department(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 직위·직책 ────────────────────────────────────────────────────────────────


@router.get("/titles")
def list_titles(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    title_kind: Annotated[str | None, Query(alias="titleKind")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.titles(
            context,
            filters={"titleKind": title_kind},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/titles", status_code=201)
def post_title(
    payload: TitleCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.create_title(context, _values(payload), key)}


@router.patch("/titles/{row_id}")
def patch_title(
    row_id: int,
    payload: TitleUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.update_title(context, row_id, _values(payload), key)}


@router.delete("/titles/{row_id}", status_code=204)
def delete_title(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    service.delete_title(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 근무 형태 ────────────────────────────────────────────────────────────────


@router.get("/work-patterns")
def list_work_patterns(
    context: Auth, offset: int = 0, limit: int = 50, sort: str | None = None
):
    page = Page(offset, limit).checked()
    return _page(
        service.work_patterns(context, sort=sort, offset=page.offset, limit=page.limit),
        page,
    )


@router.post("/work-patterns", status_code=201)
def post_work_pattern(
    payload: WorkPatternCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.create_work_pattern(context, _values(payload), key)}


@router.patch("/work-patterns/{row_id}")
def patch_work_pattern(
    row_id: int,
    payload: WorkPatternUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.update_work_pattern(context, row_id, _values(payload), key)}


@router.delete("/work-patterns/{row_id}", status_code=204)
def delete_work_pattern(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    service.delete_work_pattern(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 사원 ────────────────────────────────────────────────────────────────────


@router.get("/employees")
def list_employees(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    status: str | None = None,
    department_id: Annotated[int | None, Query(alias="departmentId")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.employees(
            context,
            filters={"status": status, "departmentId": department_id},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.get("/employees/{row_id}")
def get_employee(context: Auth, row_id: int):
    return {"data": service.employee(context, row_id)}


@router.post("/employees", status_code=201)
def post_employee(
    payload: EmployeeCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.create_employee(
            context, _values(payload, frozenset({"duty_id"})), key
        )
    }


@router.patch("/employees/{row_id}")
def patch_employee(
    row_id: int,
    payload: EmployeeUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.update_employee(context, row_id, _values(payload), key)}


@router.delete("/employees/{row_id}", status_code=204)
def delete_employee(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    service.delete_employee(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 발령 ────────────────────────────────────────────────────────────────────


@router.get("/appointments")
def list_appointments(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    status: str | None = None,
    employee_id: Annotated[int | None, Query(alias="employeeId")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.appointments(
            context,
            filters={"status": status, "employeeId": employee_id},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/appointments", status_code=201)
def post_appointment(
    payload: AppointmentCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = _values(
        payload, frozenset({"department_id", "grade_id", "duty_id", "reason"})
    )
    return {"data": service.create_appointment(context, values, key)}


@router.post("/appointments/{row_id}/confirm")
def confirm_appointment(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.confirm_appointment(context, row_id, key)}


@router.delete("/appointments/{row_id}", status_code=204)
def delete_appointment(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    service.delete_appointment(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 근태 ────────────────────────────────────────────────────────────────────


@router.get("/attendance")
def list_attendance(
    context: Auth,
    month: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")],
    offset: int = 0,
    limit: int = 100,
    employee_id: Annotated[int | None, Query(alias="employeeId")] = None,
):
    page = Page(offset, limit).checked()
    rows, total, closed = attendance.listing(
        context, month, employee_id, page.offset, page.limit
    )
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
        "closed": closed,
    }


@router.get("/attendance/summary")
def attendance_summary(
    context: Auth, month: Annotated[str, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]
):
    return {"data": attendance.summary(context, month)}


@router.post("/attendance/generate", status_code=201)
def generate_attendance(
    payload: MonthBody,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": attendance.generate(context, payload.month, key)}


@router.patch("/attendance/{row_id}")
def patch_attendance(
    row_id: int,
    payload: AttendanceUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = _values(payload, frozenset({"clock_in", "clock_out", "note"}))
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    return {"data": attendance.update(context, row_id, values, key)}


# ── 근태 마감 ────────────────────────────────────────────────────────────────


@router.get("/attendance-closes")
def list_closes(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    month: str | None = None,
    status: str | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        attendance.closes(
            context,
            filters={"month": month, "status": status},
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/attendance-closes", status_code=201)
def post_close(
    payload: MonthBody,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": attendance.open_close(context, payload.month, key)}


@router.post("/attendance-closes/{row_id}/confirm")
def confirm_close(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": attendance.confirm_close(context, row_id, key)}


# ── 연차·휴가 ────────────────────────────────────────────────────────────────


@router.get("/leave-balances")
def list_balances(
    context: Auth, offset: int = 0, limit: int = 50, year: str | None = None
):
    page = Page(offset, limit).checked()
    rows, total = leave.balances(context, year, page.offset, page.limit)
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.post("/leave-balances", status_code=201)
def post_balance(
    payload: LeaveBalanceCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": leave.create_balance(context, _values(payload), key)}


@router.patch("/leave-balances/{row_id}")
def patch_balance(
    row_id: int,
    payload: LeaveBalanceUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": leave.update_balance(context, row_id, _values(payload), key)}


@router.get("/leave-requests")
def list_requests(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    status: str | None = None,
    employee_id: Annotated[int | None, Query(alias="employeeId")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        leave.requests(
            context,
            filters={"status": status, "employeeId": employee_id},
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/leave-requests", status_code=201)
def post_request(
    payload: LeaveRequestCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": leave.create_request(
            context, _values(payload, frozenset({"reason"})), key
        )
    }


@router.post("/leave-requests/{row_id}/approve")
def approve_request(
    row_id: int,
    payload: LeaveDecision,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": leave.approve_request(
            context, row_id, _values(payload, frozenset({"reason"})), key
        )
    }


@router.post("/leave-requests/{row_id}/reject")
def reject_request(
    row_id: int,
    payload: LeaveDecision,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": leave.reject_request(
            context, row_id, _values(payload, frozenset({"reason"})), key
        )
    }


@router.post("/leave-requests/{row_id}/cancel")
def cancel_request(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": leave.cancel_request(context, row_id, key)}


# ── 급여 항목 ────────────────────────────────────────────────────────────────


@router.get("/pay-items")
def list_pay_items(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    item_kind: Annotated[str | None, Query(alias="itemKind")] = None,
    is_active: Annotated[bool | None, Query(alias="isActive")] = None,
):
    page = Page(offset, limit).checked()
    return _page(
        payroll.items(
            context,
            filters={"itemKind": item_kind, "isActive": is_active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/pay-items", status_code=201)
def post_pay_item(
    payload: PayItemCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": payroll.create_item(context, _values(payload, frozenset({"rate"})), key)
    }


@router.patch("/pay-items/{row_id}")
def patch_pay_item(
    row_id: int,
    payload: PayItemUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = _values(payload, frozenset({"rate"}))
    return {"data": payroll.update_item(context, row_id, values, key)}


@router.delete("/pay-items/{row_id}", status_code=204)
def delete_pay_item(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    payroll.delete_item(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 사원 급여 기준 ───────────────────────────────────────────────────────────


@router.get("/pay-bases")
def list_pay_bases(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    employee_id: Annotated[int | None, Query(alias="employeeId")] = None,
):
    page = Page(offset, limit).checked()
    return _page(payroll.bases(context, employee_id, page.offset, page.limit), page)


@router.get("/pay-bases/{row_id}")
def get_pay_base(row_id: int, context: Auth):
    return {"data": payroll.base_detail(context, row_id)}


@router.post("/pay-bases", status_code=201)
def post_pay_base(
    payload: PayBaseCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.create_base(context, _values(payload), key)}


@router.patch("/pay-bases/{row_id}")
def patch_pay_base(
    row_id: int,
    payload: PayBaseUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.update_base(context, row_id, _values(payload), key)}


@router.delete("/pay-bases/{row_id}", status_code=204)
def delete_pay_base(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    payroll.delete_base(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


@router.post("/pay-bases/{row_id}/items", status_code=201)
def post_pay_base_item(
    row_id: int,
    payload: PayBaseItemBody,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.add_base_item(context, row_id, _values(payload), key)}


@router.patch("/pay-base-items/{row_id}")
def patch_pay_base_item(
    row_id: int,
    payload: PayBaseItemBody,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = _values(payload)
    values.pop("pay_item_id", None)  # 항목은 바꾸지 않는다 — 지우고 다시 넣는다
    return {"data": payroll.update_base_item(context, row_id, values, key)}


@router.delete("/pay-base-items/{row_id}", status_code=204)
def delete_pay_base_item(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    payroll.delete_base_item(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 상여 규칙 ────────────────────────────────────────────────────────────────


@router.get("/bonus-rules")
def list_bonus_rules(context: Auth, offset: int = 0, limit: int = 50):
    page = Page(offset, limit).checked()
    return _page(
        payroll.bonus_rules(context, offset=page.offset, limit=page.limit), page
    )


@router.post("/bonus-rules", status_code=201)
def post_bonus_rule(
    payload: BonusRuleCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.create_bonus_rule(context, _values(payload), key)}


@router.patch("/bonus-rules/{row_id}")
def patch_bonus_rule(
    row_id: int,
    payload: BonusRuleUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.update_bonus_rule(context, row_id, _values(payload), key)}


@router.delete("/bonus-rules/{row_id}", status_code=204)
def delete_bonus_rule(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    payroll.delete_bonus_rule(
        context, row_id, _mutation(context, x_csrf_token, idempotency_key)
    )
    return Response(status_code=204)


# ── 급여 계산·확정 ───────────────────────────────────────────────────────────


@router.get("/payroll-runs")
def list_payroll_runs(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    month: str | None = None,
    status: str | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        payroll.runs(
            context,
            filters={"month": month, "status": status},
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/payroll-runs", status_code=201)
def post_payroll_run(
    payload: PayrollRunCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.calculate(context, payload.month, payload.pay_date, key)}


@router.post("/payroll-runs/{row_id}/confirm")
def confirm_payroll_run(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
):
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": payroll.confirm_run(context, row_id, key)}


# ── 급여대장·명세서 ──────────────────────────────────────────────────────────


@router.get("/payslips")
def list_payslips(
    context: Auth,
    run_id: Annotated[int, Query(alias="runId")],
    offset: int = 0,
    limit: int = 50,
):
    page = Page(offset, limit).checked()
    return _page(payroll.payslips(context, run_id, page.offset, page.limit), page)


@router.get("/payslips/{row_id}")
def get_payslip(row_id: int, context: Auth):
    return {"data": payroll.payslip_detail(context, row_id)}


@router.get("/severance")
def get_severance(
    context: Auth, employee_id: Annotated[int, Query(alias="employeeId")]
):
    return {"data": payroll.severance(context, employee_id)}
