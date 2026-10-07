"""인사 현황·인건비 분석·본인 조회 (DSN-30 F41~F44).

모두 **조회 계산**이다. 인원·인건비·연차 사용률은 저장하지 않는다(DSN-30 4장).
인건비는 **확정 급여**만 센다 — 작성 중인 계산은 숫자에 넣지 않는다.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.hr.review import EXPIRY_WARNING_DAYS

MODULE = "hr"


def _scope(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def _month_range(month: str) -> tuple[date, date]:
    year, number = int(month[:4]), int(month[5:7])
    return date(year, number, 1), date(year, number, monthrange(year, number)[1])


def _headcount(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]]:
    return [
        {
            "departmentCode": row["code"],
            "departmentName": row["name"],
            "active": row["active"],
            "onLeave": row["on_leave"],
            "retired": row["retired"],
        }
        for row in connection.execute(
            text(
                """
            SELECT d.code, d.name,
                   count(e.id) FILTER (WHERE e.status='ACTIVE') active,
                   count(e.id) FILTER (WHERE e.status='LEAVE') on_leave,
                   count(e.id) FILTER (WHERE e.status='RETIRED') retired
            FROM hr.department d
            LEFT JOIN hr.employee e ON e.workspace_id=d.workspace_id AND e.generation_id=d.generation_id
                                   AND e.department_id=d.id
            WHERE d.workspace_id=:w AND d.generation_id=:g
            GROUP BY d.code, d.name, d.display_order
            ORDER BY d.display_order, d.code
                """
            ),
            _scope(scoped),
        ).mappings()
    ]


def _moves(connection: Connection, scoped: AuthContext, month: str) -> dict[str, int]:
    first, last = _month_range(month)
    row = (
        connection.execute(
            text(
                "SELECT count(*) FILTER (WHERE hire_date BETWEEN :first AND :last) hires, "
                "count(*) FILTER (WHERE retire_date BETWEEN :first AND :last) leavers "
                "FROM hr.employee WHERE workspace_id=:w AND generation_id=:g"
            ),
            {**_scope(scoped), "first": first, "last": last},
        )
        .mappings()
        .one()
    )
    return {"hires": row["hires"], "leavers": row["leavers"]}


def _labor_cost(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]]:
    """확정 급여 1건의 부서별 지급·공제·실지급. 확정본이 없으면 빈 목록이다."""
    return [
        {
            "departmentCode": row["department_code"],
            "employees": row["employees"],
            "grossPay": str(row["gross_pay"]),
            "deductionTotal": str(row["deduction_total"]),
            "netPay": str(row["net_pay"]),
        }
        for row in connection.execute(
            text(
                """
            SELECT s.department_code, count(*) employees,
                   sum(s.gross_pay) gross_pay, sum(s.deduction_total) deduction_total,
                   sum(s.net_pay) net_pay
            FROM hr.payslip s
            JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id
                                 AND r.id=s.run_id AND r.status='confirmed' AND r.pay_month=:month
            WHERE s.workspace_id=:w AND s.generation_id=:g
            GROUP BY s.department_code
            ORDER BY s.department_code
                """
            ),
            {**_scope(scoped), "month": month},
        ).mappings()
    ]


def _attendance(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[str, Any]:
    first, last = _month_range(month)
    row = (
        connection.execute(
            text(
                "SELECT coalesce(sum(overtime_minutes),0) overtime, "
                "coalesce(sum(night_minutes),0) night, coalesce(sum(holiday_minutes),0) holiday, "
                "count(*) FILTER (WHERE status='ABSENT') absent_days "
                "FROM hr.attendance WHERE workspace_id=:w AND generation_id=:g "
                "AND work_date BETWEEN :first AND :last"
            ),
            {**_scope(scoped), "first": first, "last": last},
        )
        .mappings()
        .one()
    )
    return {
        "overtimeHours": str(Decimal(row["overtime"]) / 60),
        "nightHours": str(Decimal(row["night"]) / 60),
        "holidayHours": str(Decimal(row["holiday"]) / 60),
        "absentDays": row["absent_days"],
    }


def _leave_usage(
    connection: Connection, scoped: AuthContext, year: str
) -> dict[str, Any]:
    """연차 사용률 = 승인 사용 ÷ 발생. 발생이 없으면 비율을 만들지 않는다."""
    row = (
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
            {**_scope(scoped), "year": year},
        )
        .mappings()
        .one()
    )
    granted, used = Decimal(row["granted"]), Decimal(row["used"])
    return {
        "grantedDays": str(granted),
        "usedDays": str(used),
        "usageRate": str(round(used / granted * 100, 1)) if granted else None,
    }


def _expiring(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]]:
    today = business_today()
    return [
        {
            "employeeCode": row["employee_code"],
            "employeeName": row["name"],
            "qualKind": row["qual_kind"],
            "qualName": row["qual_name"],
            "expiresOn": row["expires_on"].isoformat(),
            "expired": row["expires_on"] < today,
        }
        for row in connection.execute(
            text(
                """
            SELECT e.employee_code, e.name, q.qual_kind, q.name qual_name, q.expires_on
            FROM hr.qualification q
            JOIN hr.employee e ON e.workspace_id=q.workspace_id AND e.generation_id=q.generation_id AND e.id=q.employee_id
            WHERE q.workspace_id=:w AND q.generation_id=:g
              AND q.expires_on IS NOT NULL AND q.expires_on <= :limit
            ORDER BY q.expires_on
                """
            ),
            {
                **_scope(scoped),
                "limit": date.fromordinal(today.toordinal() + EXPIRY_WARNING_DAYS),
            },
        ).mappings()
    ]


def overview(context: AuthContext, month: str) -> dict[str, Any]:
    """H-01 인사 현황: 인원·입퇴사·자격 만료 임박·평가 진행."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        reviews = connection.execute(
            text(
                "SELECT c.cycle_year, c.status cycle_status, "
                "count(r.id) total, "
                "count(r.id) FILTER (WHERE r.status='confirmed') confirmed "
                "FROM hr.review_cycle c "
                "LEFT JOIN hr.review r ON r.workspace_id=c.workspace_id AND r.generation_id=c.generation_id "
                "                     AND r.cycle_id=c.id "
                "WHERE c.workspace_id=:w AND c.generation_id=:g "
                "GROUP BY c.cycle_year, c.status ORDER BY c.cycle_year DESC LIMIT 3"
            ),
            _scope(scoped),
        ).mappings()
        return {
            "month": month,
            "headcount": _headcount(connection, scoped),
            "moves": _moves(connection, scoped, month),
            "attendance": _attendance(connection, scoped, month),
            "leave": _leave_usage(connection, scoped, month[:4]),
            "expiring": _expiring(connection, scoped),
            "reviews": [
                {
                    "cycleYear": row["cycle_year"],
                    "cycleStatus": row["cycle_status"],
                    "total": row["total"],
                    "confirmed": row["confirmed"],
                }
                for row in reviews
            ],
        }


def cost(context: AuthContext, month: str) -> dict[str, Any]:
    """H-14 인건비·근태 분석: 부서별 인건비(확정 급여)와 근태·연차."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        departments = _labor_cost(connection, scoped, month)
        items = [
            {
                "itemCode": row["item_code"],
                "itemName": row["item_name"],
                "itemKind": row["item_kind"],
                "amount": str(row["amount"]),
            }
            for row in connection.execute(
                text(
                    """
                SELECT l.item_code, p.name item_name, p.item_kind, sum(l.amount) amount
                FROM hr.payslip s
                JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id
                                     AND r.id=s.run_id AND r.status='confirmed' AND r.pay_month=:month
                JOIN hr.payslip_line l ON l.workspace_id=s.workspace_id AND l.generation_id=s.generation_id
                                      AND l.payslip_id=s.id
                JOIN hr.pay_item p ON p.workspace_id=l.workspace_id AND p.generation_id=l.generation_id
                                  AND p.id=l.pay_item_id
                WHERE s.workspace_id=:w AND s.generation_id=:g
                GROUP BY l.item_code, p.name, p.item_kind, p.display_order
                ORDER BY p.item_kind DESC, p.display_order, l.item_code
                    """
                ),
                {**_scope(scoped), "month": month},
            ).mappings()
        ]
        return {
            "month": month,
            "confirmed": bool(departments),
            "departments": departments,
            "items": items,
            "attendance": _attendance(connection, scoped, month),
            "leave": _leave_usage(connection, scoped, month[:4]),
        }


def me(context: AuthContext, employee_code: str, month: str) -> dict[str, Any]:
    """H-15 내 정보: 본인 근태·잔여 연차·확정 급여명세서·평가.

    EIP `my_employee_code(actor)`가 아직 없어서 **사원 코드를 받아** 그 사람 것만 돌려준다
    (DSN-30 Q7 — EIP 사람 연결이 생기면 코드는 화면이 아니라 EIP가 준다).
    """
    first, last = _month_range(month)
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        employee = (
            connection.execute(
                text(
                    """
                SELECT e.id, e.employee_code, e.name, e.status, e.hire_date,
                       d.code department_code, d.name department_name,
                       g.name grade_name, t.name duty_name
                FROM hr.employee e
                JOIN hr.department d ON d.workspace_id=e.workspace_id AND d.generation_id=e.generation_id AND d.id=e.department_id
                JOIN hr.title g ON g.workspace_id=e.workspace_id AND g.generation_id=e.generation_id AND g.id=e.grade_id
                LEFT JOIN hr.title t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.duty_id
                WHERE e.workspace_id=:w AND e.generation_id=:g AND e.employee_code=:code
                    """
                ),
                {**_scope(scoped), "code": employee_code},
            )
            .mappings()
            .one_or_none()
        )
        if employee is None:
            raise ApiError(
                404, "NOT_FOUND", f"사원 코드 {employee_code}를 찾을 수 없습니다."
            )
        params = {
            **_scope(scoped),
            "id": employee["id"],
            "first": first,
            "last": last,
            "year": month[:4],
        }
        attendance = (
            connection.execute(
                text(
                    "SELECT count(*) FILTER (WHERE status IN ('NORMAL','LATE','EARLY')) worked_days, "
                    "count(*) FILTER (WHERE status='ABSENT') absent_days, "
                    "count(*) FILTER (WHERE status IN ('LEAVE','HALF_LEAVE')) leave_days, "
                    "coalesce(sum(overtime_minutes),0) overtime_minutes, "
                    "coalesce(sum(night_minutes),0) night_minutes "
                    "FROM hr.attendance WHERE workspace_id=:w AND generation_id=:g "
                    "AND employee_id=:id AND work_date BETWEEN :first AND :last"
                ),
                params,
            )
            .mappings()
            .one()
        )
        balance = (
            connection.execute(
                text(
                    """
                SELECT b.granted_days,
                       coalesce((SELECT sum(r.days) FROM hr.leave_request r
                                  WHERE r.workspace_id=b.workspace_id AND r.generation_id=b.generation_id
                                    AND r.employee_id=b.employee_id AND r.status='APPROVED'
                                    AND r.leave_kind IN ('ANNUAL','HALF_AM','HALF_PM')
                                    AND to_char(r.from_date,'YYYY')=b.leave_year),0) used_days
                FROM hr.leave_balance b
                WHERE b.workspace_id=:w AND b.generation_id=:g AND b.employee_id=:id AND b.leave_year=:year
                    """
                ),
                params,
            )
            .mappings()
            .one_or_none()
        )
        payslips = [
            {
                "id": row["id"],
                "payMonth": row["pay_month"],
                "payDate": row["pay_date"].isoformat(),
                "grossPay": str(row["gross_pay"]),
                "deductionTotal": str(row["deduction_total"]),
                "netPay": str(row["net_pay"]),
            }
            for row in connection.execute(
                text(
                    "SELECT s.id, r.pay_month, r.pay_date, s.gross_pay, s.deduction_total, s.net_pay "
                    "FROM hr.payslip s "
                    "JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id "
                    "                     AND r.id=s.run_id AND r.status='confirmed' "
                    "WHERE s.workspace_id=:w AND s.generation_id=:g AND s.employee_id=:id "
                    "ORDER BY r.pay_month DESC LIMIT 12"
                ),
                params,
            ).mappings()
        ]
        reviews = [
            {
                "id": row["id"],
                "cycleYear": row["cycle_year"],
                "status": row["status"],
                "grade": row["grade"],
                "reviewerCode": row["reviewer_code"],
                "reviewerComment": row["reviewer_comment"],
            }
            for row in connection.execute(
                text(
                    "SELECT r.id, c.cycle_year, r.status, r.grade, r.reviewer_code, r.reviewer_comment "
                    "FROM hr.review r "
                    "JOIN hr.review_cycle c ON c.workspace_id=r.workspace_id AND c.generation_id=r.generation_id "
                    "                      AND c.id=r.cycle_id "
                    "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.employee_id=:id "
                    "ORDER BY c.cycle_year DESC"
                ),
                params,
            ).mappings()
        ]
    granted = Decimal(balance["granted_days"]) if balance else Decimal(0)
    used = Decimal(balance["used_days"]) if balance else Decimal(0)
    return {
        "employee": {
            "employeeCode": employee["employee_code"],
            "name": employee["name"],
            "status": employee["status"],
            "hireDate": employee["hire_date"].isoformat(),
            "departmentCode": employee["department_code"],
            "departmentName": employee["department_name"],
            "gradeName": employee["grade_name"],
            "dutyName": employee["duty_name"],
        },
        "month": month,
        "attendance": {
            "workedDays": attendance["worked_days"],
            "absentDays": attendance["absent_days"],
            "leaveDays": attendance["leave_days"],
            "overtimeMinutes": attendance["overtime_minutes"],
            "nightMinutes": attendance["night_minutes"],
        },
        "leave": {
            "year": month[:4],
            "grantedDays": str(granted),
            "usedDays": str(used),
            "remainingDays": str(granted - used),
        },
        "payslips": payslips,
        "reviews": reviews,
    }
