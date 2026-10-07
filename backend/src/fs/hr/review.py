"""자격·교육과 인사 평가 (DSN-30 F06·F31, Q6).

자격은 만료 30일 전부터 경고만 한다 — 자격이 없다고 다른 일을 막지 않는다.
평가는 연도별 평가 기간 안에서 목표 작성 → 제출 → 평가자(기본 부서장) 등급·의견 → 확정이다.
확정하면 불변이고, 평가 기간을 닫으면 더 만들거나 고칠 수 없다.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

MODULE = "hr"
EXPIRY_WARNING_DAYS = 30

QUALIFICATION = master.Master(
    module=MODULE,
    table="hr.qualification",
    columns=(
        "employee_id",
        "qual_kind",
        "name",
        "issuer",
        "acquired_on",
        "expires_on",
    ),
    sort={"acquiredOn": "acquired_on", "expiresOn": "expires_on"},
    default_sort="acquired_on DESC, id DESC",
    filters={"employeeId": "employee_id", "qualKind": "qual_kind"},
    not_found="자격·교육을 찾을 수 없습니다.",
)
CYCLE = master.Master(
    module=MODULE,
    table="hr.review_cycle",
    columns=("cycle_year", "name", "status"),
    sort={"cycleYear": "cycle_year"},
    default_sort="cycle_year DESC",
    unique=("cycle_year",),
    references=(master.Reference("hr.review", "cycle_id", "평가"),),
    not_found="평가 기간을 찾을 수 없습니다.",
    duplicate_field="cycleYear",
    duplicate_message="그 해 평가 기간이 이미 있습니다.",
    referenced_message="평가가 들어 있어 삭제할 수 없습니다.",
)
REVIEW = master.Master(
    module=MODULE,
    table="hr.review",
    columns=(
        "cycle_id",
        "employee_id",
        "goals",
        "self_comment",
        "reviewer_code",
        "grade",
        "reviewer_comment",
        "status",
        "confirmed_at",
    ),
    sort={},
    default_sort="employee_id ASC",
    unique=("cycle_id", "employee_id"),
    filters={"cycleId": "cycle_id", "employeeId": "employee_id", "status": "status"},
    not_found="평가를 찾을 수 없습니다.",
    duplicate_field="employeeId",
    duplicate_message="그 사원의 평가가 이미 있습니다.",
)


def _scope(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def _invalid(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {master.camel(field): message}},
    )


# ── 자격·교육 ────────────────────────────────────────────────────────────────


def qualifications(context: AuthContext, expiring: bool, **kwargs):
    """만료 임박(30일 이내)만 보려면 expiring. 이미 지난 것도 함께 보여준다."""
    rows, total = master.listing(QUALIFICATION, context, **kwargs)
    today = business_today()
    marked = [
        {
            **row,
            "expiryState": expiry_state(row["expiresOn"], today.isoformat()),
        }
        for row in rows
    ]
    if not expiring:
        return marked, total
    near = [row for row in marked if row["expiryState"] in ("EXPIRING", "EXPIRED")]
    return near, len(near)


def expiry_state(expires_on: str | None, today: str) -> str:
    if expires_on is None:
        return "NONE"
    if expires_on < today:
        return "EXPIRED"
    from datetime import date as _date

    left = (_date.fromisoformat(expires_on) - _date.fromisoformat(today)).days
    return "EXPIRING" if left <= EXPIRY_WARNING_DAYS else "VALID"


def create_qualification(context: AuthContext, values: dict[str, Any], key: str):
    def check(connection, scoped, merged, _current, _row_id):
        found = connection.execute(
            text(
                "SELECT 1 FROM hr.employee WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": merged["employee_id"]},
        ).first()
        if found is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")

    return master.create(QUALIFICATION, context, values, key, check=check)


def update_qualification(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(QUALIFICATION, context, row_id, values, key)


def delete_qualification(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(QUALIFICATION, context, row_id, key)


# ── 평가 기간 ────────────────────────────────────────────────────────────────


def cycles(context: AuthContext, **kwargs):
    return master.listing(CYCLE, context, **kwargs)


def create_cycle(context: AuthContext, values: dict[str, Any], key: str):
    return master.create(CYCLE, context, {**values, "status": "OPEN"}, key)


def close_cycle(context: AuthContext, row_id: int, key: str):
    """닫으면 그 해 평가를 더 만들거나 고칠 수 없다. 확정하지 않은 평가는 그대로 남는다."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, CYCLE, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", CYCLE.not_found)
        if row["status"] == "CLOSED":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 닫은 평가 기간입니다.",
                {"reason": "ALREADY_CLOSED"},
            )
        return (
            master.store(connection, CYCLE, scoped, {"status": "CLOSED"}, row_id),
            CYCLE.entity,
            row_id,
        )

    return action(MODULE, context, "hr.review_cycle.close", key, {"id": row_id}, run)


def delete_cycle(context: AuthContext, row_id: int, key: str) -> None:
    master.delete(CYCLE, context, row_id, key)


# ── 평가 ─────────────────────────────────────────────────────────────────────


def reviews(context: AuthContext, **kwargs):
    """사원 이름과 평가 기간을 함께 — 목록만 보고도 누구의 몇 년 평가인지 알 수 있게."""
    rows, total = master.listing(REVIEW, context, **kwargs)
    if not rows:
        return rows, total
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        names = {
            row["id"]: (row["employee_code"], row["name"])
            for row in connection.execute(
                text(
                    "SELECT id, employee_code, name FROM hr.employee "
                    "WHERE workspace_id=:w AND generation_id=:g"
                ),
                _scope(scoped),
            ).mappings()
        }
        years = {
            row["id"]: row["cycle_year"]
            for row in connection.execute(
                text(
                    "SELECT id, cycle_year FROM hr.review_cycle "
                    "WHERE workspace_id=:w AND generation_id=:g"
                ),
                _scope(scoped),
            ).mappings()
        }
    return [
        {
            **row,
            "employeeCode": names.get(row["employeeId"], ("—", "—"))[0],
            "employeeName": names.get(row["employeeId"], ("—", "—"))[1],
            "cycleYear": years.get(row["cycleId"], "—"),
        }
        for row in rows
    ], total


def _open_cycle(connection: Connection, scoped: AuthContext, cycle_id: int) -> None:
    status = connection.execute(
        text(
            "SELECT status FROM hr.review_cycle "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_scope(scoped), "id": cycle_id},
    ).scalar()
    if status is None:
        raise _invalid("cycle_id", "현재 공간의 평가 기간을 선택하세요.")
    if status != "OPEN":
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            "닫힌 평가 기간은 더 고칠 수 없습니다.",
            {"reason": "CYCLE_CLOSED"},
        )


def _default_reviewer(
    connection: Connection, scoped: AuthContext, employee_id: int
) -> str:
    """평가자를 안 적으면 그 사원 부서의 부서장(is_head 직책)이 된다."""
    code = connection.execute(
        text(
            """
        SELECT head.employee_code FROM hr.employee e
        JOIN hr.employee head ON head.workspace_id=e.workspace_id AND head.generation_id=e.generation_id
                             AND head.department_id=e.department_id AND head.status='ACTIVE'
        JOIN hr.title t ON t.workspace_id=head.workspace_id AND t.generation_id=head.generation_id
                       AND t.id=head.duty_id AND t.is_head
        WHERE e.workspace_id=:w AND e.generation_id=:g AND e.id=:id AND head.id<>e.id
        ORDER BY head.employee_code LIMIT 1
            """
        ),
        {**_scope(scoped), "id": employee_id},
    ).scalar()
    if code is None:
        raise _invalid(
            "reviewer_code", "그 사원 부서에 부서장이 없습니다. 평가자를 직접 고르세요."
        )
    return code


def create_review(context: AuthContext, values: dict[str, Any], key: str):
    def run(connection: Connection, scoped: AuthContext):
        _open_cycle(connection, scoped, values["cycle_id"])
        employee = connection.execute(
            text(
                "SELECT status FROM hr.employee "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": values["employee_id"]},
        ).scalar()
        if employee is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")
        reviewer = values.get("reviewer_code") or _default_reviewer(
            connection, scoped, values["employee_id"]
        )
        merged = {
            **values,
            "reviewer_code": reviewer,
            "self_comment": None,
            "grade": None,
            "reviewer_comment": None,
            "status": "draft",
            "confirmed_at": None,
        }
        master.reject_duplicate(connection, REVIEW, scoped, merged, None)
        created = master.store(connection, REVIEW, scoped, merged, None)
        return created, REVIEW.entity, created["id"]

    return action(MODULE, context, "hr.review.create", key, values, run, 201)


def _editable(connection: Connection, scoped: AuthContext, row_id: int, *allowed: str):
    row = master.fetch(connection, REVIEW, scoped, row_id)
    if row is None:
        raise ApiError(404, "NOT_FOUND", REVIEW.not_found)
    _open_cycle(connection, scoped, row["cycle_id"])
    if row["status"] not in allowed:
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            "지금 상태에서는 할 수 없습니다.",
            {"reason": "WRONG_STATUS", "status": row["status"]},
        )
    return row


def save_self(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    """본인 목표·자기 평가. 제출하기 전까지만 고친다."""

    def run(connection: Connection, scoped: AuthContext):
        _editable(connection, scoped, row_id, "draft")
        return (
            master.store(connection, REVIEW, scoped, values, row_id),
            REVIEW.entity,
            row_id,
        )

    return action(MODULE, context, "hr.review.self", key, {"id": row_id, **values}, run)


def submit_review(context: AuthContext, row_id: int, key: str):
    """제출하면 본인은 더 고칠 수 없고 평가자 차례가 된다."""

    def run(connection: Connection, scoped: AuthContext):
        _editable(connection, scoped, row_id, "draft")
        return (
            master.store(connection, REVIEW, scoped, {"status": "submitted"}, row_id),
            REVIEW.entity,
            row_id,
        )

    return action(MODULE, context, "hr.review.submit", key, {"id": row_id}, run)


def confirm_review(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    """평가자가 등급·의견을 적고 확정한다. 확정 후에는 바뀌지 않는다."""

    def run(connection: Connection, scoped: AuthContext):
        row = _editable(connection, scoped, row_id, "submitted")
        if values["reviewer_code"] != row["reviewer_code"]:
            raise _invalid(
                "reviewer_code", f"이 평가의 평가자는 {row['reviewer_code']}입니다."
            )
        confirmed = (
            connection.execute(
                text(
                    f"UPDATE hr.review SET grade=:grade, reviewer_comment=:comment, "
                    f"status='confirmed', confirmed_at=clock_timestamp() "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id "
                    f"RETURNING {REVIEW.selection}"
                ),
                {
                    **_scope(scoped),
                    "id": row_id,
                    "grade": values["grade"],
                    "comment": values.get("reviewer_comment"),
                },
            )
            .mappings()
            .one()
        )
        return master.present(confirmed), REVIEW.entity, row_id

    return action(
        MODULE, context, "hr.review.confirm", key, {"id": row_id, **values}, run
    )


def delete_review(context: AuthContext, row_id: int, key: str) -> None:
    def run(connection: Connection, scoped: AuthContext):
        _editable(connection, scoped, row_id, "draft", "submitted")
        connection.execute(
            text(
                "DELETE FROM hr.review WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": row_id},
        )
        return None, REVIEW.entity, row_id

    action(MODULE, context, "hr.review.delete", key, {"id": row_id}, run, 204)
