# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""HR API (/api/v1/hr, DSN-30). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.hr import service
from fs.hr.schema import (
    AppointmentCreate,
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeCreate,
    EmployeeUpdate,
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
