"""HR 읽기 전용 제공 (DSN-90 2장). 다른 솔루션은 이 함수들로만 HR 값을 읽는다.

사람과 부서의 원천은 HR이다(D81). 받는 쪽은 코드를 스냅샷으로 보관하고 FK를 두지 않는다.
"""

from __future__ import annotations

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
