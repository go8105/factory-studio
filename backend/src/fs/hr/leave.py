"""연차와 휴가 (DSN-30 F13, Q3).

연도별 발생 일수만 저장하고 **잔여는 조회로 계산한다**(발생 − 승인 사용).
신청 → 부서장(직책 is_head) 승인 → 그 날짜의 근태가 LEAVE가 된다. 잔여를 넘는 신청은 거부한다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.hr.attendance import closed_months

MODULE = "hr"
# 잔여에서 깎는 휴가 (병가·특별휴가는 연차와 별개)
ANNUAL = ("ANNUAL", "HALF_AM", "HALF_PM")

BALANCE = master.Master(
    module=MODULE,
    table="hr.leave_balance",
    columns=("employee_id", "leave_year", "granted_days"),
    sort={"leaveYear": "leave_year"},
    default_sort="leave_year DESC, employee_id ASC",
    unique=("employee_id", "leave_year"),
    filters={"year": "leave_year", "employeeId": "employee_id"},
    not_found="연차 발생 기록을 찾을 수 없습니다.",
    duplicate_field="leaveYear",
    duplicate_message="그 사원의 해당 연도 발생 기록이 이미 있습니다.",
)
REQUEST = master.Master(
    module=MODULE,
    table="hr.leave_request",
    columns=(
        "request_no",
        "employee_id",
        "leave_kind",
        "from_date",
        "to_date",
        "days",
        "reason",
        "status",
        "approver_code",
        "decided_at",
    ),
    sort={"requestNo": "request_no", "fromDate": "from_date"},
    default_sort="from_date DESC, id DESC",
    unique=("request_no",),
    filters={"status": "status", "employeeId": "employee_id"},
    not_found="휴가 신청을 찾을 수 없습니다.",
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


def _used(
    connection: Connection, scoped: AuthContext, employee_id: int, year: str
) -> Decimal:
    return connection.execute(
        text(
            "SELECT coalesce(sum(days),0) FROM hr.leave_request "
            "WHERE workspace_id=:w AND generation_id=:g AND employee_id=:employee "
            "AND status='APPROVED' AND leave_kind=ANY(:kinds) "
            "AND to_char(from_date,'YYYY')=:year"
        ),
        {
            **_scope(scoped),
            "employee": employee_id,
            "year": year,
            "kinds": list(ANNUAL),
        },
    ).scalar_one()


def _next_no(connection: Connection, scoped: AuthContext, on: date) -> str:
    prefix = f"LV-{on:%Y%m%d}-"
    last = connection.execute(
        text(
            "SELECT max(request_no) FROM hr.leave_request "
            "WHERE workspace_id=:w AND generation_id=:g AND request_no LIKE :prefix"
        ),
        {**_scope(scoped), "prefix": prefix + "%"},
    ).scalar()
    return f"{prefix}{(int(last[-3:]) if last else 0) + 1:03d}"


# ── 연차 발생·잔여 ───────────────────────────────────────────────────────────


def balances(context: AuthContext, year: str | None, offset: int, limit: int):
    """발생·사용·잔여를 함께 돌려준다. 잔여는 저장하지 않는다."""
    where = "b.workspace_id=:w AND b.generation_id=:g"
    params: dict[str, Any] = {"offset": offset, "limit": limit, "kinds": list(ANNUAL)}
    if year:
        where += " AND b.leave_year=:year"
        params["year"] = year
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params.update(_scope(scoped))
        total = connection.execute(
            text(f"SELECT count(*) FROM hr.leave_balance b WHERE {where}"), params
        ).scalar_one()
        rows = (
            connection.execute(
                text(
                    f"""
                SELECT b.id, b.employee_id, e.employee_code, e.name employee_name,
                       b.leave_year, b.granted_days,
                       coalesce((SELECT sum(r.days) FROM hr.leave_request r
                                  WHERE r.workspace_id=b.workspace_id AND r.generation_id=b.generation_id
                                    AND r.employee_id=b.employee_id AND r.status='APPROVED'
                                    AND r.leave_kind=ANY(:kinds)
                                    AND to_char(r.from_date,'YYYY')=b.leave_year),0) used_days
                FROM hr.leave_balance b
                JOIN hr.employee e ON e.workspace_id=b.workspace_id AND e.generation_id=b.generation_id AND e.id=b.employee_id
                WHERE {where}
                ORDER BY b.leave_year DESC, e.employee_code
                OFFSET :offset LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
    return [
        {
            **master.present(row),
            "remainingDays": str(row["granted_days"] - row["used_days"]),
        }
        for row in rows
    ], total


def create_balance(context: AuthContext, values: dict[str, Any], key: str):
    def check(connection, scoped, merged, current, _row_id):
        found = connection.execute(
            text(
                "SELECT 1 FROM hr.employee WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": merged["employee_id"]},
        ).first()
        if found is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")

    return master.create(BALANCE, context, values, key, check=check)


def update_balance(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return master.update(BALANCE, context, row_id, values, key)


# ── 휴가 신청·승인 ───────────────────────────────────────────────────────────


def requests(context: AuthContext, **kwargs):
    return master.listing(REQUEST, context, **kwargs)


def create_request(context: AuthContext, values: dict[str, Any], key: str):
    def run(connection: Connection, scoped: AuthContext):
        employee = (
            connection.execute(
                text(
                    "SELECT id, status FROM hr.employee "
                    "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
                ),
                {**_scope(scoped), "id": values["employee_id"]},
            )
            .mappings()
            .one_or_none()
        )
        if employee is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")
        if employee["status"] != "ACTIVE":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "재직 중인 사원만 휴가를 신청할 수 있습니다.",
                {"reason": "EMPLOYEE_NOT_ACTIVE"},
            )
        year = f"{values['from_date']:%Y}"
        if values["leave_kind"] in ANNUAL:
            granted = connection.execute(
                text(
                    "SELECT granted_days FROM hr.leave_balance "
                    "WHERE workspace_id=:w AND generation_id=:g AND employee_id=:employee AND leave_year=:year"
                ),
                {**_scope(scoped), "employee": employee["id"], "year": year},
            ).scalar()
            if granted is None:
                raise _invalid(
                    "leave_kind", f"{year}년 연차 발생이 등록되지 않았습니다."
                )
            remaining = granted - _used(connection, scoped, employee["id"], year)
            if Decimal(str(values["days"])) > remaining:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    f"잔여 연차({remaining}일)를 넘습니다.",
                    {"reason": "NOT_ENOUGH_LEAVE", "remainingDays": str(remaining)},
                )
        created = master.store(
            connection,
            REQUEST,
            scoped,
            {
                **values,
                "request_no": _next_no(connection, scoped, values["from_date"]),
                "status": "REQUESTED",
                "approver_code": None,
                "decided_at": None,
            },
            None,
        )
        return created, REQUEST.entity, created["id"]

    return action(MODULE, context, "hr.leave_request.create", key, values, run, 201)


def _decide(
    context: AuthContext, row_id: int, approve: bool, values: dict[str, Any], key: str
):
    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, REQUEST, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", REQUEST.not_found)
        if row["status"] != "REQUESTED":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 처리한 신청입니다.",
                {"reason": "ALREADY_DECIDED", "status": row["status"]},
            )
        approver = (
            connection.execute(
                text(
                    """
                SELECT e.id FROM hr.employee e
                JOIN hr.title t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id
                               AND t.id=e.duty_id AND t.is_head
                WHERE e.workspace_id=:w AND e.generation_id=:g AND e.employee_code=:code AND e.status='ACTIVE'
                    """
                ),
                {**_scope(scoped), "code": values["approver_code"]},
            )
            .scalars()
            .first()
        )
        if approver is None:
            raise _invalid(
                "approver_code", "부서장 직책을 가진 재직 사원만 승인할 수 있습니다."
            )
        if approver == row["employee_id"]:
            raise _invalid("approver_code", "본인 신청은 스스로 승인할 수 없습니다.")
        if approve:
            # 잔여를 다시 본다 — 신청 뒤 다른 신청이 먼저 승인됐을 수 있다.
            year = f"{row['from_date']:%Y}"
            if row["leave_kind"] in ANNUAL:
                granted = connection.execute(
                    text(
                        "SELECT granted_days FROM hr.leave_balance "
                        "WHERE workspace_id=:w AND generation_id=:g AND employee_id=:employee AND leave_year=:year "
                        "FOR UPDATE"
                    ),
                    {**_scope(scoped), "employee": row["employee_id"], "year": year},
                ).scalar()
                remaining = (granted or 0) - _used(
                    connection, scoped, row["employee_id"], year
                )
                if row["days"] > remaining:
                    raise ApiError(
                        409,
                        "PRECONDITION_NOT_MET",
                        f"잔여 연차({remaining}일)를 넘어 승인할 수 없습니다.",
                        {"reason": "NOT_ENOUGH_LEAVE", "remainingDays": str(remaining)},
                    )
        decided = (
            connection.execute(
                text(
                    f"UPDATE hr.leave_request SET status=:status, approver_code=:approver, "
                    f"decided_at=clock_timestamp(), reason=coalesce(:reason, reason) "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {REQUEST.selection}"
                ),
                {
                    **_scope(scoped),
                    "id": row_id,
                    "status": "APPROVED" if approve else "REJECTED",
                    "approver": values["approver_code"],
                    "reason": values.get("reason"),
                },
            )
            .mappings()
            .one()
        )
        presented = master.present(decided)
        applied = 0
        if approve:
            # 마감하지 않은 달의 근태만 LEAVE로 바꾼다.
            closed = closed_months(connection, scoped)
            months = {
                f"{row['from_date']:%Y-%m}",
                f"{row['to_date']:%Y-%m}",
            }
            if not months & closed:
                applied = connection.execute(
                    text(
                        """
                    UPDATE hr.attendance SET status=:status, clock_in=NULL, clock_out=NULL,
                           night_minutes=0, source='MANUAL',
                           note=coalesce(note, '') || :note
                    WHERE workspace_id=:w AND generation_id=:g AND employee_id=:employee
                      AND work_date BETWEEN :from_date AND :to_date AND day_kind='WORKDAY'
                        """
                    ),
                    {
                        **_scope(scoped),
                        "employee": row["employee_id"],
                        "from_date": row["from_date"],
                        "to_date": row["to_date"],
                        "status": "HALF_LEAVE"
                        if row["leave_kind"].startswith("HALF")
                        else "LEAVE",
                        "note": f"휴가 {presented['requestNo']}",
                    },
                ).rowcount
        return {**presented, "attendanceUpdated": applied}, REQUEST.entity, row_id

    return action(
        MODULE,
        context,
        f"hr.leave_request.{'approve' if approve else 'reject'}",
        key,
        {"id": row_id, **values},
        run,
    )


def approve_request(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return _decide(context, row_id, True, values, key)


def reject_request(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return _decide(context, row_id, False, values, key)


def cancel_request(context: AuthContext, row_id: int, key: str):
    """신청 중인 것만 취소한다. 처리한 신청은 이력으로 남긴다."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, REQUEST, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", REQUEST.not_found)
        if row["status"] != "REQUESTED":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "처리한 신청은 취소할 수 없습니다.",
                {"reason": "ALREADY_DECIDED", "status": row["status"]},
            )
        cancelled = (
            connection.execute(
                text(
                    f"UPDATE hr.leave_request SET status='CANCELLED' "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {REQUEST.selection}"
                ),
                {**_scope(scoped), "id": row_id},
            )
            .mappings()
            .one()
        )
        return master.present(cancelled), REQUEST.entity, row_id

    return action(MODULE, context, "hr.leave_request.cancel", key, {"id": row_id}, run)
