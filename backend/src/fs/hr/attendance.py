"""근태와 월 마감 (DSN-30 F12·F14·F15, Q2).

근무 형태와 공통 휴일 달력으로 **한 달치를 자동으로 만들고**(AUTO), 지각·결근·연장 같은 예외만 고친다(MANUAL).
월 마감을 확정하면 그 달은 더 고칠 수 없다. 다시 마감하면 새 버전이 되고 이전 확정본은 superseded가 된다.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

MODULE = "hr"
NIGHT_FROM, NIGHT_TO = time(22, 0), time(6, 0)

ATTENDANCE = master.Master(
    module=MODULE,
    table="hr.attendance",
    columns=(
        "employee_id",
        "work_date",
        "day_kind",
        "status",
        "clock_in",
        "clock_out",
        "overtime_minutes",
        "night_minutes",
        "holiday_minutes",
        "source",
        "note",
    ),
    sort={"workDate": "work_date"},
    default_sort="work_date ASC, employee_id ASC",
    unique=("employee_id", "work_date"),
    not_found="근태를 찾을 수 없습니다.",
)
CLOSE = master.Master(
    module=MODULE,
    table="hr.attendance_close",
    columns=("close_month", "version", "status", "confirmed_at"),
    sort={"closeMonth": "close_month"},
    default_sort="close_month DESC, version DESC",
    filters={"month": "close_month", "status": "status"},
    not_found="근태 마감을 찾을 수 없습니다.",
)


def _scope(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def _month_range(month: str) -> tuple[date, date]:
    year, number = int(month[:4]), int(month[5:7])
    return date(year, number, 1), date(year, number, monthrange(year, number)[1])


def _night_minutes(start: time, minutes: int) -> int:
    """근무 구간과 22~06시가 겹치는 분. 교대 근무의 야간 수당 근거가 된다."""
    begin = datetime.combine(date(2000, 1, 1), start)
    night = 0
    for offset in range(minutes):
        moment = (begin + timedelta(minutes=offset)).time()
        if moment >= NIGHT_FROM or moment < NIGHT_TO:
            night += 1
    return night


def closed_months(connection: Connection, scoped: AuthContext) -> set[str]:
    return set(
        connection.execute(
            text(
                # 월마다 마지막 버전만 본다 — 다시 마감을 열면(draft) 그 달은 다시 열린다.
                "SELECT close_month FROM (SELECT DISTINCT ON (close_month) close_month, status "
                "FROM hr.attendance_close WHERE workspace_id=:w AND generation_id=:g "
                "ORDER BY close_month, version DESC) latest WHERE status='confirmed'"
            ),
            _scope(scoped),
        ).scalars()
    )


def _require_open(connection: Connection, scoped: AuthContext, month: str) -> None:
    if month in closed_months(connection, scoped):
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            f"{month} 근태는 마감했습니다. 다시 마감하면 새 버전으로 고칠 수 있습니다.",
            {"reason": "MONTH_CLOSED", "month": month},
        )


# ── 조회 ────────────────────────────────────────────────────────────────────


def listing(
    context: AuthContext, month: str, employee_id: int | None, offset: int, limit: int
):
    first, last = _month_range(month)
    where = "a.workspace_id=:w AND a.generation_id=:g AND a.work_date BETWEEN :first AND :last"
    params: dict[str, Any] = {**_scope(context), "first": first, "last": last}
    if employee_id is not None:
        where += " AND a.employee_id=:employee"
        params["employee"] = employee_id
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params.update(_scope(scoped))
        total = connection.execute(
            text(f"SELECT count(*) FROM hr.attendance a WHERE {where}"), params
        ).scalar_one()
        rows = (
            connection.execute(
                text(
                    f"SELECT a.id, a.employee_id, e.employee_code, e.name employee_name, "
                    f"a.work_date, a.day_kind, a.status, a.clock_in, a.clock_out, "
                    f"a.overtime_minutes, a.night_minutes, a.holiday_minutes, a.source, a.note "
                    f"FROM hr.attendance a JOIN hr.employee e "
                    f"  ON e.workspace_id=a.workspace_id AND e.generation_id=a.generation_id AND e.id=a.employee_id "
                    f"WHERE {where} ORDER BY a.work_date, e.employee_code "
                    f"OFFSET :offset LIMIT :limit"
                ),
                {**params, "offset": offset, "limit": limit},
            )
            .mappings()
            .all()
        )
        closed = month in closed_months(connection, scoped)
    return [master.present(row) for row in rows], total, closed


def summary(context: AuthContext, month: str):
    """사원별 월 합계 — 급여 계산(W1b-3)의 입력이 된다."""
    first, last = _month_range(month)
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = (
            connection.execute(
                text(
                    """
                SELECT e.id employee_id, e.employee_code, e.name employee_name,
                       count(*) FILTER (WHERE a.status IN ('NORMAL','LATE','EARLY')) worked_days,
                       count(*) FILTER (WHERE a.status='ABSENT') absent_days,
                       count(*) FILTER (WHERE a.status IN ('LEAVE','HALF_LEAVE')) leave_days,
                       coalesce(sum(a.overtime_minutes),0) overtime_minutes,
                       coalesce(sum(a.night_minutes),0) night_minutes,
                       coalesce(sum(a.holiday_minutes),0) holiday_minutes
                FROM hr.employee e
                LEFT JOIN hr.attendance a
                  ON a.workspace_id=e.workspace_id AND a.generation_id=e.generation_id
                 AND a.employee_id=e.id AND a.work_date BETWEEN :first AND :last
                WHERE e.workspace_id=:w AND e.generation_id=:g
                GROUP BY e.id, e.employee_code, e.name
                HAVING count(a.id) > 0
                ORDER BY e.employee_code
                    """
                ),
                {**_scope(scoped), "first": first, "last": last},
            )
            .mappings()
            .all()
        )
    return [master.present(row) for row in rows]


# ── 자동 생성·예외 수정 ──────────────────────────────────────────────────────


def generate(context: AuthContext, month: str, key: str):
    """그 달의 빠진 날만 채운다. 이미 있는 날(손으로 고친 것 포함)은 건드리지 않는다."""

    def run(connection: Connection, scoped: AuthContext):
        _require_open(connection, scoped, month)
        first, last = _month_range(month)
        employees = (
            connection.execute(
                text(
                    """
                SELECT e.id, e.hire_date, e.retire_date, p.start_time, p.scheduled_minutes,
                       p.break_minutes, p.works_weekend
                FROM hr.employee e
                JOIN hr.work_pattern p
                  ON p.workspace_id=e.workspace_id AND p.generation_id=e.generation_id AND p.id=e.work_pattern_id
                WHERE e.workspace_id=:w AND e.generation_id=:g AND e.hire_date <= :last
                  AND (e.retire_date IS NULL OR e.retire_date >= :first)
                ORDER BY e.id
                    """
                ),
                {**_scope(scoped), "first": first, "last": last},
            )
            .mappings()
            .all()
        )
        holidays = set(
            connection.execute(
                text(
                    "SELECT holiday_on FROM core.holiday "
                    "WHERE workspace_id=:w AND generation_id=:g AND holiday_on BETWEEN :first AND :last"
                ),
                {**_scope(scoped), "first": first, "last": last},
            ).scalars()
        )
        leaves = (
            connection.execute(
                text(
                    """
                SELECT employee_id, from_date, to_date, leave_kind FROM hr.leave_request
                WHERE workspace_id=:w AND generation_id=:g AND status='APPROVED'
                  AND from_date <= :last AND to_date >= :first
                    """
                ),
                {**_scope(scoped), "first": first, "last": last},
            )
            .mappings()
            .all()
        )
        existing = set(
            connection.execute(
                text(
                    "SELECT employee_id, work_date FROM hr.attendance "
                    "WHERE workspace_id=:w AND generation_id=:g AND work_date BETWEEN :first AND :last"
                ),
                {**_scope(scoped), "first": first, "last": last},
            )
        )
        rows = []
        for employee in employees:
            night = _night_minutes(
                employee["start_time"],
                employee["scheduled_minutes"] + employee["break_minutes"],
            )
            for day in range((last - first).days + 1):
                work_date = first + timedelta(days=day)
                if (employee["id"], work_date) in existing:
                    continue
                if work_date < employee["hire_date"]:
                    continue
                if employee["retire_date"] and work_date > employee["retire_date"]:
                    continue
                weekend = work_date.weekday() >= 5
                if work_date in holidays:
                    day_kind = "HOLIDAY"
                elif weekend and not employee["works_weekend"]:
                    day_kind = "OFFDAY"
                else:
                    day_kind = "WORKDAY"
                leave = next(
                    (
                        x
                        for x in leaves
                        if x["employee_id"] == employee["id"]
                        and x["from_date"] <= work_date <= x["to_date"]
                    ),
                    None,
                )
                if day_kind != "WORKDAY":
                    status, clock_in, clock_out = "OFF", None, None
                elif leave is not None:
                    status = (
                        "HALF_LEAVE"
                        if leave["leave_kind"].startswith("HALF")
                        else "LEAVE"
                    )
                    clock_in = clock_out = None
                else:
                    status = "NORMAL"
                    clock_in = datetime.combine(work_date, employee["start_time"])
                    clock_out = clock_in + timedelta(
                        minutes=employee["scheduled_minutes"]
                        + employee["break_minutes"]
                    )
                rows.append(
                    {
                        "employee_id": employee["id"],
                        "work_date": work_date,
                        "day_kind": day_kind,
                        "status": status,
                        "clock_in": clock_in,
                        "clock_out": clock_out,
                        "overtime_minutes": 0,
                        "night_minutes": night if status == "NORMAL" else 0,
                        "holiday_minutes": 0,
                        "source": "AUTO",
                        "note": None,
                    }
                )
        if rows:
            connection.execute(
                text(
                    """
                INSERT INTO hr.attendance
                  (workspace_id,generation_id,employee_id,work_date,day_kind,status,clock_in,clock_out,
                   overtime_minutes,night_minutes,holiday_minutes,source,note)
                VALUES (:w,:g,:employee_id,:work_date,:day_kind,:status,:clock_in,:clock_out,
                        :overtime_minutes,:night_minutes,:holiday_minutes,:source,:note)
                    """
                ),
                [{**_scope(scoped), **row} for row in rows],
            )
        result = {"month": month, "created": len(rows), "employees": len(employees)}
        return result, "attendance", len(rows)

    return action(
        MODULE, context, "hr.attendance.generate", key, {"month": month}, run, 201
    )


def update(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    """예외만 고친다. 고치면 출처가 MANUAL이 된다."""

    def check(connection, scoped, merged, current, _row_id):
        _require_open(connection, scoped, f"{current['work_date']:%Y-%m}")

    return master.update(
        ATTENDANCE, context, row_id, {**values, "source": "MANUAL"}, key, check=check
    )


# ── 월 마감 ─────────────────────────────────────────────────────────────────


def closes(context: AuthContext, **kwargs):
    return master.listing(CLOSE, context, **kwargs)


def open_close(context: AuthContext, month: str, key: str):
    """그 달의 마감본을 작성한다. 이미 확정한 달이면 다음 버전이 된다(재마감)."""

    def run(connection: Connection, scoped: AuthContext):
        latest = connection.execute(
            text(
                "SELECT max(version) FROM hr.attendance_close "
                "WHERE workspace_id=:w AND generation_id=:g AND close_month=:month"
            ),
            {**_scope(scoped), "month": month},
        ).scalar()
        draft = connection.execute(
            text(
                "SELECT id FROM hr.attendance_close "
                "WHERE workspace_id=:w AND generation_id=:g AND close_month=:month AND status='draft'"
            ),
            {**_scope(scoped), "month": month},
        ).scalar()
        if draft is not None:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 작성 중인 마감본이 있습니다.",
                {"reason": "DRAFT_EXISTS", "closeId": draft},
            )
        created = master.store(
            connection,
            CLOSE,
            scoped,
            {
                "close_month": month,
                "version": (latest or 0) + 1,
                "status": "draft",
                "confirmed_at": None,
            },
            None,
        )
        return created, CLOSE.entity, created["id"]

    return action(
        MODULE, context, "hr.attendance_close.open", key, {"month": month}, run, 201
    )


def confirm_close(context: AuthContext, row_id: int, key: str):
    """확정하면 그 달의 근태는 더 고칠 수 없다. 이전 확정본은 superseded가 된다."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, CLOSE, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", CLOSE.not_found)
        if row["status"] != "draft":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 확정했거나 지난 마감본입니다.",
                {"reason": "ALREADY_CONFIRMED"},
            )
        connection.execute(
            text(
                "UPDATE hr.attendance_close SET status='superseded' "
                "WHERE workspace_id=:w AND generation_id=:g AND close_month=:month AND status='confirmed'"
            ),
            {**_scope(scoped), "month": row["close_month"]},
        )
        confirmed = (
            connection.execute(
                text(
                    f"UPDATE hr.attendance_close SET status='confirmed', confirmed_at=clock_timestamp() "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {CLOSE.selection}"
                ),
                {**_scope(scoped), "id": row_id},
            )
            .mappings()
            .one()
        )
        return master.present(confirmed), CLOSE.entity, row_id

    return action(
        MODULE, context, "hr.attendance_close.confirm", key, {"id": row_id}, run
    )
