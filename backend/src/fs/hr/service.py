"""HR 업무 규칙과 트랜잭션 경계 (DSN-30).

기준정보(부서·직위/직책·근무 형태)는 공통 엔진(fs.common.master)이 맡는다.
사원과 발령만 여기서 다룬다 — **현재 부서·직위·직책·재직 상태는 확정 발령으로만 바뀐다**(F03).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

MODULE = "hr"

DEPARTMENT = master.Master(
    module=MODULE,
    table="hr.department",
    columns=("code", "name", "parent_id", "display_order", "is_active"),
    sort={"code": "code", "name": "name", "displayOrder": "display_order"},
    default_sort="display_order ASC, code ASC",
    unique=("code",),
    filters={"active": "is_active"},
    references=(
        master.Reference("hr.department", "parent_id", "하위 부서"),
        master.Reference("hr.employee", "department_id", "사원"),
        master.Reference("hr.appointment", "department_id", "발령"),
    ),
    not_found="부서를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 부서 코드입니다.",
    referenced_message=(
        "하위 부서나 사원이 참조 중이라 삭제할 수 없습니다. "
        "사용 안 함으로 바꾸면 새 입력에서 제외됩니다."
    ),
)
TITLE = master.Master(
    module=MODULE,
    table="hr.title",
    columns=("title_kind", "code", "name", "rank_order", "is_head"),
    sort={"code": "code", "name": "name", "rankOrder": "rank_order"},
    default_sort="title_kind ASC, rank_order ASC",
    unique=("title_kind", "code"),
    filters={"titleKind": "title_kind"},
    references=(
        master.Reference("hr.employee", "grade_id", "사원 직위"),
        master.Reference("hr.employee", "duty_id", "사원 직책"),
        master.Reference("hr.appointment", "grade_id", "발령 직위"),
        master.Reference("hr.appointment", "duty_id", "발령 직책"),
    ),
    not_found="직위·직책을 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="같은 구분에 이미 있는 코드입니다.",
    referenced_message="사원이나 발령이 참조 중이라 삭제할 수 없습니다.",
)
WORK_PATTERN = master.Master(
    module=MODULE,
    table="hr.work_pattern",
    columns=(
        "code",
        "name",
        "pattern_kind",
        "start_time",
        "scheduled_minutes",
        "break_minutes",
        "works_weekend",
    ),
    sort={"code": "code", "name": "name"},
    default_sort="code ASC",
    unique=("code",),
    references=(master.Reference("hr.employee", "work_pattern_id", "사원"),),
    not_found="근무 형태를 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 사용 중인 근무 형태 코드입니다.",
    referenced_message="사원이 쓰고 있어 삭제할 수 없습니다.",
)
EMPLOYEE = master.Master(
    module=MODULE,
    table="hr.employee",
    columns=(
        "employee_code",
        "name",
        "hire_date",
        "status",
        "department_id",
        "grade_id",
        "duty_id",
        "work_pattern_id",
        "retire_date",
        "retire_reason",
    ),
    sort={"employeeCode": "employee_code", "name": "name", "hireDate": "hire_date"},
    default_sort="employee_code ASC",
    unique=("employee_code",),
    filters={"status": "status", "departmentId": "department_id"},
    references=(master.Reference("hr.appointment", "employee_id", "발령"),),
    not_found="사원을 찾을 수 없습니다.",
    duplicate_field="employeeCode",
    duplicate_message="이미 사용 중인 사원 코드입니다.",
    referenced_message="발령 이력이 있어 삭제할 수 없습니다. 퇴직 발령으로 처리하세요.",
)
APPOINTMENT = master.Master(
    module=MODULE,
    table="hr.appointment",
    columns=(
        "appointment_no",
        "employee_id",
        "kind",
        "effective_date",
        "department_id",
        "grade_id",
        "duty_id",
        "reason",
        "status",
        "confirmed_at",
    ),
    sort={
        "appointmentNo": "appointment_no",
        "effectiveDate": "effective_date",
    },
    default_sort="effective_date DESC, id DESC",
    unique=("appointment_no",),
    filters={"employeeId": "employee_id", "status": "status"},
    not_found="발령을 찾을 수 없습니다.",
)
# 발령 종류별로 반드시 채워야 하는 칸 (schema.json CHECK와 같은 규칙)
REQUIRED = {
    "HIRE": ("department_id", "grade_id"),
    "TRANSFER": ("department_id",),
    "PROMOTION": ("grade_id",),
    "DUTY": (),
    "LEAVE": (),
    "RETURN": (),
    "RETIRE": (),
}
LABELS = {
    "department_id": "부서",
    "grade_id": "직위",
    "duty_id": "직책",
}


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {master.camel(field): message}},
    )


def _exists(
    connection: Connection, scoped: AuthContext, table: str, row_id: int
) -> bool:
    return (
        connection.execute(
            text(
                f"SELECT 1 FROM {table} WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
        ).first()
        is not None
    )


def _check_title(
    connection: Connection, scoped: AuthContext, row_id: int, kind: str, field: str
) -> None:
    row = (
        connection.execute(
            text(
                "SELECT title_kind FROM hr.title WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise _invalid(field, "현재 공간의 대상을 선택하세요.")
    if row["title_kind"] != kind:
        raise _invalid(
            field, "직위는 GRADE, 직책은 DUTY로 등록된 것만 고를 수 있습니다."
        )


def _next_no(connection: Connection, scoped: AuthContext, on: date) -> str:
    """AP-YYYYMMDD-NNN. 같은 날짜 안에서 이어 붙인다."""
    prefix = f"AP-{on:%Y%m%d}-"
    last = connection.execute(
        text(
            "SELECT max(appointment_no) FROM hr.appointment "
            "WHERE workspace_id=:w AND generation_id=:g AND appointment_no LIKE :prefix"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "prefix": prefix + "%"},
    ).scalar()
    return f"{prefix}{(int(last[-3:]) if last else 0) + 1:03d}"


# ── 부서·직위/직책·근무 형태: 공통 엔진 ─────────────────────────────────────────


def _department_parent(
    connection: Connection,
    scoped: AuthContext,
    merged: dict[str, Any],
    current: dict[str, Any] | None,
    row_id: int | None,
) -> None:
    parent_id = merged.get("parent_id")
    if parent_id is None:
        return
    if parent_id == row_id:
        raise _invalid("parent_id", "자기 자신을 상위 부서로 둘 수 없습니다.")
    if not _exists(connection, scoped, "hr.department", parent_id):
        raise _invalid("parent_id", "현재 공간의 부서를 선택하세요.")
    # 순환(A → B → A)은 DB가 막지 못한다. 상위로 거슬러 올라가며 자신을 만나면 거부한다.
    seen, cursor = {row_id}, parent_id
    while cursor is not None:
        if cursor in seen:
            raise _invalid("parent_id", "상위 부서가 서로를 가리킬 수 없습니다.")
        seen.add(cursor)
        cursor = connection.execute(
            text(
                "SELECT parent_id FROM hr.department WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": cursor},
        ).scalar()


def _title_head(
    connection: Connection,
    scoped: AuthContext,
    merged: dict[str, Any],
    current: dict[str, Any] | None,
    row_id: int | None,
) -> None:
    if merged.get("is_head") and merged.get("title_kind") != "DUTY":
        raise _invalid("is_head", "부서장은 직책(DUTY)에만 지정할 수 있습니다.")


def departments(context: AuthContext, **kwargs):
    return master.listing(DEPARTMENT, context, **kwargs)


def create_department(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(DEPARTMENT, context, values, key, check=_department_parent)


def update_department(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(
        DEPARTMENT, context, row_id, values, key, check=_department_parent
    )


def delete_department(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(DEPARTMENT, context, row_id, key)


def titles(context: AuthContext, **kwargs):
    return master.listing(TITLE, context, **kwargs)


def create_title(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(TITLE, context, values, key, check=_title_head)


def update_title(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return master.update(TITLE, context, row_id, values, key, check=_title_head)


def delete_title(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(TITLE, context, row_id, key)


def work_patterns(context: AuthContext, **kwargs):
    return master.listing(WORK_PATTERN, context, **kwargs)


def create_work_pattern(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(WORK_PATTERN, context, values, key)


def update_work_pattern(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(WORK_PATTERN, context, row_id, values, key)


def delete_work_pattern(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(WORK_PATTERN, context, row_id, key)


# ── 사원 ────────────────────────────────────────────────────────────────────


def employees(context: AuthContext, **kwargs):
    return master.listing(EMPLOYEE, context, **kwargs)


def employee(context: AuthContext, row_id: int):
    """인사카드: 사원 + 발령 이력."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        row = master.fetch(connection, EMPLOYEE, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", EMPLOYEE.not_found)
        history = (
            connection.execute(
                text(
                    f"SELECT {APPOINTMENT.selection} FROM hr.appointment "
                    "WHERE workspace_id=:w AND generation_id=:g AND employee_id=:id "
                    "ORDER BY effective_date DESC, id DESC"
                ),
                {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
            )
            .mappings()
            .all()
        )
    return {
        **master.present(row),
        "appointments": [master.present(x) for x in history],
    }


def create_employee(context: AuthContext, values: dict[str, Any], key: str):
    """사원 등록 + 입사(HIRE) 발령 확정을 한 트랜잭션에서."""

    def run(connection: Connection, scoped: AuthContext):
        for field, table in (
            ("department_id", "hr.department"),
            ("work_pattern_id", "hr.work_pattern"),
        ):
            if not _exists(connection, scoped, table, values[field]):
                raise _invalid(field, "현재 공간의 대상을 선택하세요.")
        _check_title(connection, scoped, values["grade_id"], "GRADE", "grade_id")
        if values.get("duty_id") is not None:
            _check_title(connection, scoped, values["duty_id"], "DUTY", "duty_id")
        master.reject_duplicate(connection, EMPLOYEE, scoped, values, None)
        created = master.store(
            connection, EMPLOYEE, scoped, {**values, "status": "ACTIVE"}, None
        )
        # 확정 시각은 DB 시계로 남긴다(FS-030 D68).
        connection.execute(
            text(
                """
            INSERT INTO hr.appointment
              (workspace_id,generation_id,appointment_no,employee_id,kind,effective_date,
               department_id,grade_id,duty_id,reason,status,confirmed_at)
            VALUES (:w,:g,:no,:employee,'HIRE',:on,:department,:grade,:duty,
                    '사원 등록','confirmed',clock_timestamp())
                """
            ),
            {
                "w": scoped.workspace_id,
                "g": scoped.generation_id,
                "no": _next_no(connection, scoped, values["hire_date"]),
                "employee": created["id"],
                "on": values["hire_date"],
                "department": values["department_id"],
                "grade": values["grade_id"],
                "duty": values.get("duty_id"),
            },
        )
        return created, EMPLOYEE.entity, created["id"]

    return action(MODULE, context, "hr.employee.create", key, values, run, 201)


def update_employee(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    def check(connection, scoped, merged, current, _row_id):
        if "work_pattern_id" in values and not _exists(
            connection, scoped, "hr.work_pattern", values["work_pattern_id"]
        ):
            raise _invalid("work_pattern_id", "현재 공간의 대상을 선택하세요.")

    return master.update(EMPLOYEE, context, row_id, values, key, check=check)


def delete_employee(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(EMPLOYEE, context, row_id, key)


# ── 발령 ────────────────────────────────────────────────────────────────────


def appointments(context: AuthContext, **kwargs):
    return master.listing(APPOINTMENT, context, **kwargs)


def create_appointment(context: AuthContext, values: dict[str, Any], key: str):
    """작성(draft) 상태로 만든다. 확정은 별도 요청."""

    def run(connection: Connection, scoped: AuthContext):
        current = master.fetch(connection, EMPLOYEE, scoped, values["employee_id"])
        if current is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")
        kind = values["kind"]
        for field in REQUIRED[kind]:
            if values.get(field) is None:
                raise _invalid(field, f"{LABELS[field]}를 선택하세요.")
        if values.get("department_id") is not None and not _exists(
            connection, scoped, "hr.department", values["department_id"]
        ):
            raise _invalid("department_id", "현재 공간의 부서를 선택하세요.")
        if values.get("grade_id") is not None:
            _check_title(connection, scoped, values["grade_id"], "GRADE", "grade_id")
        if values.get("duty_id") is not None:
            _check_title(connection, scoped, values["duty_id"], "DUTY", "duty_id")
        if kind == "RETIRE" and values["effective_date"] < current["hire_date"]:
            raise _invalid("effective_date", "퇴직일은 입사일 이후여야 합니다.")
        if current["status"] == "RETIRED":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "퇴직한 사원에게는 발령을 낼 수 없습니다.",
                {"reason": "EMPLOYEE_RETIRED"},
            )
        created = master.store(
            connection,
            APPOINTMENT,
            scoped,
            {
                **values,
                "appointment_no": _next_no(
                    connection, scoped, values["effective_date"]
                ),
                "status": "draft",
            },
            None,
        )
        return created, APPOINTMENT.entity, created["id"]

    return action(MODULE, context, "hr.appointment.create", key, values, run, 201)


def confirm_appointment(context: AuthContext, row_id: int, key: str):
    """확정하면 사원의 현재값을 갱신하고, 이후 발령은 바뀌지 않는다(F03)."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, APPOINTMENT, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", APPOINTMENT.not_found)
        if row["status"] != "draft":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 확정한 발령입니다.",
                {"reason": "ALREADY_CONFIRMED"},
            )
        changes: dict[str, Any] = {}
        for field in ("department_id", "grade_id", "duty_id"):
            if row[field] is not None:
                changes[field] = row[field]
        if row["kind"] == "LEAVE":
            changes["status"] = "LEAVE"
        elif row["kind"] == "RETURN":
            changes["status"] = "ACTIVE"
        elif row["kind"] == "RETIRE":
            changes |= {
                "status": "RETIRED",
                "retire_date": row["effective_date"],
                "retire_reason": row["reason"] or "발령",
            }
        else:
            changes["status"] = "ACTIVE"
        assignments = ",".join(f"{name}=:{name}" for name in changes)
        connection.execute(
            text(
                f"UPDATE hr.employee SET {assignments} "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {
                "w": scoped.workspace_id,
                "g": scoped.generation_id,
                "id": row["employee_id"],
                **changes,
            },
        )
        confirmed = (
            connection.execute(
                text(
                    f"UPDATE hr.appointment SET status='confirmed', confirmed_at=clock_timestamp() "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {APPOINTMENT.selection}"
                ),
                {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
            )
            .mappings()
            .one()
        )
        return master.present(confirmed), APPOINTMENT.entity, row_id

    return action(MODULE, context, "hr.appointment.confirm", key, {"id": row_id}, run)


def delete_appointment(context: AuthContext, row_id: int, key: str) -> None:
    """작성 중인 발령만 지운다. 확정분은 이력이라 남긴다."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, APPOINTMENT, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", APPOINTMENT.not_found)
        if row["status"] != "draft":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "확정한 발령은 지울 수 없습니다. 반대 발령으로 바로잡으세요.",
                {"reason": "ALREADY_CONFIRMED"},
            )
        connection.execute(
            text(
                "DELETE FROM hr.appointment WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "id": row_id},
        )
        return {}, APPOINTMENT.entity, row_id

    action(MODULE, context, "hr.appointment.delete", key, {"id": row_id}, run, 204)
