"""HR 읽기 전용 제공 (DSN-90 2장). 다른 솔루션은 이 함수들로만 HR 값을 읽는다.

사람과 부서의 원천은 HR이다(D81). 받는 쪽은 코드를 스냅샷으로 보관하고 FK를 두지 않는다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available


def _scope(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """HR 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "hr")


def employees(
    connection: Connection, scoped: AuthContext, status: str | None = "ACTIVE"
) -> list[dict[str, Any]] | None:
    """사원 코드·이름·부서·직위·재직 상태. 각 솔루션이 'HR에서 가져오기'로 쓴다."""
    if not enabled(connection, scoped):
        return None
    where = "" if status is None else " AND e.status=:status"
    rows = connection.execute(
        text(
            f"""
        SELECT e.employee_code, e.name, e.status, e.hire_date,
               d.code department_code, d.name department_name,
               g.name grade_name, t.name duty_name, t.is_head
        FROM hr.employee e
        JOIN hr.department d ON d.workspace_id=e.workspace_id AND d.generation_id=e.generation_id AND d.id=e.department_id
        JOIN hr.title g ON g.workspace_id=e.workspace_id AND g.generation_id=e.generation_id AND g.id=e.grade_id
        LEFT JOIN hr.title t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.duty_id
        WHERE e.workspace_id=:w AND e.generation_id=:g{where}
        ORDER BY e.employee_code
            """
        ),
        {**_scope(scoped), "status": status},
    ).mappings()
    return [
        {
            "employeeCode": r["employee_code"],
            "name": r["name"],
            "status": r["status"],
            "hireDate": r["hire_date"].isoformat(),
            "departmentCode": r["department_code"],
            "departmentName": r["department_name"],
            "gradeName": r["grade_name"],
            "dutyName": r["duty_name"],
            "isHead": bool(r["is_head"]),
        }
        for r in rows
    ]


def departments(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """부서 코드·이름·상위·부서장 사원 코드. 부서 코드의 원천이다(DSN-30 Q1)."""
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            """
        SELECT d.code, d.name, d.is_active, p.code parent_code,
               (SELECT e.employee_code FROM hr.employee e
                  JOIN hr.title t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id
                                 AND t.id=e.duty_id AND t.is_head
                 WHERE e.workspace_id=d.workspace_id AND e.generation_id=d.generation_id
                   AND e.department_id=d.id AND e.status='ACTIVE'
                 ORDER BY e.employee_code LIMIT 1) head_employee_code
        FROM hr.department d
        LEFT JOIN hr.department p ON p.workspace_id=d.workspace_id AND p.generation_id=d.generation_id AND p.id=d.parent_id
        WHERE d.workspace_id=:w AND d.generation_id=:g
        ORDER BY d.display_order, d.code
            """
        ),
        _scope(scoped),
    ).mappings()
    return [
        {
            "code": r["code"],
            "name": r["name"],
            "parentCode": r["parent_code"],
            "isActive": r["is_active"],
            "headEmployeeCode": r["head_employee_code"],
        }
        for r in rows
    ]


def payroll_runs(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[str, Any] | None:
    """확정 급여의 **부서·항목별 합계**. ERP F94 급여 전표가 읽는다(DSN-90 흐름 4).

    개인 금액은 넘기지 않는다. 확정본이 없으면 None이 아니라 빈 합계를 돌려준다.
    """
    if not enabled(connection, scoped):
        return None
    run = (
        connection.execute(
            text(
                "SELECT id, pay_month, pay_date, version, confirmed_at FROM hr.payroll_run "
                "WHERE workspace_id=:w AND generation_id=:g AND pay_month=:month AND status='confirmed'"
            ),
            {**_scope(scoped), "month": month},
        )
        .mappings()
        .one_or_none()
    )
    if run is None:
        return {"month": month, "confirmed": False, "lines": []}
    rows = connection.execute(
        text(
            """
        SELECT s.department_code, l.item_code, p.name item_name, p.item_kind,
               sum(l.amount) amount, count(DISTINCT s.id) employees
        FROM hr.payslip s
        JOIN hr.payslip_line l ON l.workspace_id=s.workspace_id AND l.generation_id=s.generation_id AND l.payslip_id=s.id
        JOIN hr.pay_item p ON p.workspace_id=l.workspace_id AND p.generation_id=l.generation_id AND p.id=l.pay_item_id
        WHERE s.workspace_id=:w AND s.generation_id=:g AND s.run_id=:run
        GROUP BY s.department_code, l.item_code, p.name, p.item_kind, p.display_order
        ORDER BY s.department_code, p.item_kind, p.display_order, l.item_code
            """
        ),
        {**_scope(scoped), "run": run["id"]},
    ).mappings()
    return {
        "month": run["pay_month"],
        "confirmed": True,
        "runId": run["id"],
        "version": run["version"],
        "payDate": run["pay_date"].isoformat(),
        "confirmedAt": run["confirmed_at"].isoformat(),
        "lines": [
            {
                "departmentCode": r["department_code"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "itemKind": r["item_kind"],
                "amount": str(r["amount"]),
                "employees": r["employees"],
            }
            for r in rows
        ],
    }


def monthly_summary(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[str, Any] | None:
    """지표 키 → 값 (DSN-90 2-1 공통). 인건비는 **확정 급여**만 센다."""
    if not enabled(connection, scoped):
        return None
    people = (
        connection.execute(
            text(
                "SELECT count(*) FILTER (WHERE status='ACTIVE') headcount, "
                "count(*) FILTER (WHERE to_char(hire_date,'YYYY-MM')=:month) hires, "
                "count(*) FILTER (WHERE to_char(retire_date,'YYYY-MM')=:month) leavers "
                "FROM hr.employee WHERE workspace_id=:w AND generation_id=:g"
            ),
            {**_scope(scoped), "month": month},
        )
        .mappings()
        .one()
    )
    cost = connection.execute(
        text(
            "SELECT coalesce(sum(s.gross_pay),0) gross FROM hr.payslip s "
            "JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id "
            "                     AND r.id=s.run_id AND r.status='confirmed' AND r.pay_month=:month "
            "WHERE s.workspace_id=:w AND s.generation_id=:g"
        ),
        {**_scope(scoped), "month": month},
    ).scalar_one()
    overtime = connection.execute(
        text(
            "SELECT coalesce(sum(overtime_minutes),0) FROM hr.attendance "
            "WHERE workspace_id=:w AND generation_id=:g AND to_char(work_date,'YYYY-MM')=:month"
        ),
        {**_scope(scoped), "month": month},
    ).scalar_one()
    leave = (
        connection.execute(
            text(
                """
        SELECT coalesce(sum(b.granted_days),0) granted,
               coalesce(sum((SELECT sum(r.days) FROM hr.leave_request r
                              WHERE r.workspace_id=b.workspace_id AND r.generation_id=b.generation_id
                                AND r.employee_id=b.employee_id AND r.status='APPROVED'
                                AND r.leave_kind IN ('ANNUAL','HALF_AM','HALF_PM')
                                AND to_char(r.from_date,'YYYY')=b.leave_year)),0) used
        FROM hr.leave_balance b
        WHERE b.workspace_id=:w AND b.generation_id=:g AND b.leave_year=:year
            """
            ),
            {**_scope(scoped), "year": month[:4]},
        )
        .mappings()
        .one()
    )
    granted, used = Decimal(leave["granted"]), Decimal(leave["used"])
    return {
        "month": month,
        "metrics": {
            "headcount": people["headcount"],
            "hires": people["hires"],
            "leavers": people["leavers"],
            "laborCost": str(cost),
            "overtimeHours": str(Decimal(overtime) / 60),
            "leaveUsageRate": str(round(used / granted * 100, 1)) if granted else None,
        },
    }


def pending_tasks(
    connection: Connection, scoped: AuthContext, hr_employee_code: str
) -> list[dict[str, Any]] | None:
    """그 사람이 기다리고 있는 일 (DSN-90 흐름 6). 사원이 아니면 빈 목록이다."""
    if not enabled(connection, scoped):
        return None
    employee = (
        connection.execute(
            text(
                "SELECT e.id, e.department_id, coalesce(t.is_head,false) is_head "
                "FROM hr.employee e "
                "LEFT JOIN hr.title t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id "
                "                    AND t.id=e.duty_id "
                "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.employee_code=:code"
            ),
            {**_scope(scoped), "code": hr_employee_code},
        )
        .mappings()
        .one_or_none()
    )
    if employee is None:
        return []
    tasks: list[dict[str, Any]] = []
    if employee["is_head"]:
        waiting = connection.execute(
            text(
                "SELECT count(*) FROM hr.leave_request r "
                "JOIN hr.employee e ON e.workspace_id=r.workspace_id AND e.generation_id=r.generation_id "
                "                  AND e.id=r.employee_id AND e.department_id=:department "
                "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.status='REQUESTED' "
                "AND r.employee_id<>:id"
            ),
            {
                **_scope(scoped),
                "department": employee["department_id"],
                "id": employee["id"],
            },
        ).scalar_one()
        if waiting:
            tasks.append(
                {
                    "kind": "LEAVE_APPROVAL",
                    "label": "휴가 승인 대기",
                    "count": waiting,
                    "path": "/hr/leaves",
                }
            )
    reviewing = connection.execute(
        text(
            "SELECT count(*) FROM hr.review "
            "WHERE workspace_id=:w AND generation_id=:g AND reviewer_code=:code AND status='submitted'"
        ),
        {**_scope(scoped), "code": hr_employee_code},
    ).scalar_one()
    if reviewing:
        tasks.append(
            {
                "kind": "REVIEW_DECISION",
                "label": "평가 확정 대기",
                "count": reviewing,
                "path": "/hr/reviews",
            }
        )
    mine = connection.execute(
        text(
            "SELECT count(*) FROM hr.review "
            "WHERE workspace_id=:w AND generation_id=:g AND employee_id=:id AND status='draft'"
        ),
        {**_scope(scoped), "id": employee["id"]},
    ).scalar_one()
    if mine:
        tasks.append(
            {
                "kind": "REVIEW_SELF",
                "label": "자기 평가 작성",
                "count": mine,
                "path": "/hr/me",
            }
        )
    return tasks


def lookup(
    connection: Connection, scoped: AuthContext, code: str
) -> dict[str, Any] | None:
    """번호 하나로 HR 안의 대상을 찾는다 (DSN-90 2-1). 없으면 None."""
    if not enabled(connection, scoped):
        return None
    targets = (
        ("employee", "사원", "/hr/employees", "hr.employee", "employee_code", "name"),
        (
            "appointment",
            "발령",
            "/hr/appointments",
            "hr.appointment",
            "appointment_no",
            "kind",
        ),
        (
            "leaveRequest",
            "휴가 신청",
            "/hr/leaves",
            "hr.leave_request",
            "request_no",
            "status",
        ),
    )
    for kind, label, path, table, column, caption in targets:
        row = (
            connection.execute(
                text(
                    f"SELECT id, {column} code, {caption} caption FROM {table} "
                    f"WHERE workspace_id=:w AND generation_id=:g AND {column}=:code"
                ),
                {**_scope(scoped), "code": code},
            )
            .mappings()
            .one_or_none()
        )
        if row is not None:
            return {
                "kind": kind,
                "label": label,
                "code": row["code"],
                "caption": str(row["caption"]),
                "path": path,
            }
    return None
