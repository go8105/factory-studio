"""급여 (DSN-30 F21~F28, Q4·Q5).

월급제. 한 달 급여 = 기본급 + 고정 수당 + 근태 수당(통상시급 × 배율 × 시간) + 상여 − 공제(과세 지급 × 비율).
입력은 **그 달의 확정 근태 마감**이다. 확정하면 불변이고, 재계산은 새 버전이 된다.
퇴직금 추계와 ERP에 넘기는 부서·항목별 합계는 저장하지 않고 조회로 계산한다.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope

MODULE = "hr"
# 금액 계산 방식: 지급은 계산 방식마다, 공제는 모두 RATE(과세 지급 × 퍼센트)
ATTENDANCE_KINDS = {
    "OVERTIME": "overtime_minutes",
    "NIGHT": "night_minutes",
    "HOLIDAY": "holiday_minutes",
}

ITEM = master.Master(
    module=MODULE,
    table="hr.pay_item",
    columns=(
        "code",
        "name",
        "item_kind",
        "calc_kind",
        "rate",
        "is_taxable",
        "display_order",
        "is_active",
    ),
    sort={"code": "code", "name": "name", "displayOrder": "display_order"},
    default_sort="item_kind ASC, display_order ASC, code ASC",
    unique=("code",),
    filters={"itemKind": "item_kind", "isActive": "is_active"},
    references=(
        master.Reference("hr.pay_base_item", "pay_item_id", "급여 기준 수당"),
        master.Reference("hr.bonus_rule", "pay_item_id", "상여 규칙"),
        master.Reference("hr.payslip_line", "pay_item_id", "급여명세"),
    ),
    not_found="급여 항목을 찾을 수 없습니다.",
    duplicate_field="code",
    duplicate_message="이미 있는 급여 항목 코드입니다.",
    referenced_message="급여 기준이나 명세서가 쓰는 항목은 삭제할 수 없습니다.",
)
BASE = master.Master(
    module=MODULE,
    table="hr.pay_base",
    columns=("employee_id", "effective_from", "base_salary", "ordinary_hours"),
    sort={"effectiveFrom": "effective_from"},
    default_sort="effective_from DESC, employee_id ASC",
    unique=("employee_id", "effective_from"),
    filters={"employeeId": "employee_id", "effectiveFrom": "effective_from"},
    references=(master.Reference("hr.pay_base_item", "pay_base_id", "고정 수당"),),
    not_found="급여 기준을 찾을 수 없습니다.",
    duplicate_field="effectiveFrom",
    duplicate_message="그 사원의 해당 적용 월 기준이 이미 있습니다.",
    referenced_message="고정 수당을 먼저 지우세요.",
)
BASE_ITEM = master.Master(
    module=MODULE,
    table="hr.pay_base_item",
    columns=("pay_base_id", "pay_item_id", "amount"),
    sort={},
    default_sort="pay_item_id ASC",
    unique=("pay_base_id", "pay_item_id"),
    filters={"payBaseId": "pay_base_id"},
    not_found="고정 수당을 찾을 수 없습니다.",
    duplicate_field="payItemId",
    duplicate_message="그 항목은 이미 들어 있습니다.",
)
BONUS = master.Master(
    module=MODULE,
    table="hr.bonus_rule",
    columns=("payable_mm", "rate_percent", "pay_item_id", "is_active"),
    sort={"payableMm": "payable_mm"},
    default_sort="payable_mm ASC",
    filters={"isActive": "is_active"},
    not_found="상여 규칙을 찾을 수 없습니다.",
    duplicate_field="payableMm",
    duplicate_message="그 달에 쓰는 상여 규칙이 이미 있습니다.",
)
RUN = master.Master(
    module=MODULE,
    table="hr.payroll_run",
    columns=(
        "pay_month",
        "attendance_close_id",
        "pay_date",
        "version",
        "status",
        "confirmed_at",
    ),
    sort={"payMonth": "pay_month"},
    default_sort="pay_month DESC, version DESC",
    filters={"month": "pay_month", "status": "status"},
    not_found="급여 실행을 찾을 수 없습니다.",
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


def _won(value: Decimal) -> Decimal:
    """원 단위로 반올림한다. numeric(18,0)이라 소수가 들어가면 저장되지 않는다."""
    return value.quantize(Decimal(1), rounding=ROUND_HALF_UP)


# ── 급여 항목 ────────────────────────────────────────────────────────────────


def items(context: AuthContext, **kwargs):
    return master.listing(ITEM, context, **kwargs)


def create_item(context: AuthContext, values: dict[str, Any], key: str):
    values["rate"] = values.get("rate") or None  # 빈 칸은 '배수·비율 없음'이다
    _check_item(values)
    return master.create(ITEM, context, values, key)


def update_item(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    if "rate" in values:
        values["rate"] = values["rate"] or None

    def check(_connection, _scoped, merged, _current, _row_id):
        _check_item(merged)

    return master.update(ITEM, context, row_id, values, key, check=check)


def delete_item(context: AuthContext, row_id: int, key: str):
    master.delete(ITEM, context, row_id, key)


def _check_item(values: dict[str, Any]) -> None:
    """DB CHECK와 같은 규칙을 먼저 보고 사람이 읽을 수 있는 메시지로 돌려준다."""
    calc = values.get("calc_kind")
    kind = values.get("item_kind")
    if (kind == "DEDUCTION") != (calc == "RATE"):
        raise _invalid(
            "calc_kind", "공제는 비율(RATE)로만, 지급은 비율이 아닌 방식으로 만듭니다."
        )
    needs_rate = calc in ("OVERTIME", "NIGHT", "HOLIDAY", "RATE")
    if needs_rate and not values.get("rate"):
        raise _invalid("rate", "연장·야간·휴일은 배수를, 공제는 퍼센트를 적습니다.")
    if not needs_rate and values.get("rate"):
        raise _invalid("rate", "이 계산 방식은 배수·비율을 쓰지 않습니다.")


# ── 사원 급여 기준 ───────────────────────────────────────────────────────────


def bases(context: AuthContext, employee_id: int | None, offset: int, limit: int):
    """사원 이름과 고정 수당 합계를 함께 보여준다."""
    where = "b.workspace_id=:w AND b.generation_id=:g"
    params: dict[str, Any] = {"offset": offset, "limit": limit}
    if employee_id is not None:
        where += " AND b.employee_id=:employee"
        params["employee"] = employee_id
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params.update(_scope(scoped))
        total = connection.execute(
            text(f"SELECT count(*) FROM hr.pay_base b WHERE {where}"), params
        ).scalar_one()
        rows = (
            connection.execute(
                text(
                    f"""
                SELECT b.id, b.employee_id, e.employee_code, e.name employee_name,
                       b.effective_from, b.base_salary, b.ordinary_hours,
                       coalesce((SELECT sum(i.amount) FROM hr.pay_base_item i
                                  WHERE i.workspace_id=b.workspace_id AND i.generation_id=b.generation_id
                                    AND i.pay_base_id=b.id),0) fixed_total
                FROM hr.pay_base b
                JOIN hr.employee e ON e.workspace_id=b.workspace_id AND e.generation_id=b.generation_id AND e.id=b.employee_id
                WHERE {where}
                ORDER BY b.effective_from DESC, e.employee_code
                OFFSET :offset LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
    return [master.present(row) for row in rows], total


def base_detail(context: AuthContext, row_id: int):
    """고정 수당 줄까지 함께 — H-10 상세 패널."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        row = master.fetch(connection, BASE, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", BASE.not_found)
        lines = (
            connection.execute(
                text(
                    """
                SELECT i.id, i.pay_item_id, p.code item_code, p.name item_name, i.amount
                FROM hr.pay_base_item i
                JOIN hr.pay_item p ON p.workspace_id=i.workspace_id AND p.generation_id=i.generation_id AND p.id=i.pay_item_id
                WHERE i.workspace_id=:w AND i.generation_id=:g AND i.pay_base_id=:base
                ORDER BY p.display_order, p.code
                    """
                ),
                {**_scope(scoped), "base": row_id},
            )
            .mappings()
            .all()
        )
    return {
        **master.present(row),
        "items": [master.present(line) for line in lines],
    }


def create_base(context: AuthContext, values: dict[str, Any], key: str):
    def check(connection, scoped, merged, _current, _row_id):
        found = connection.execute(
            text(
                "SELECT 1 FROM hr.employee WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": merged["employee_id"]},
        ).first()
        if found is None:
            raise _invalid("employee_id", "현재 공간의 사원을 선택하세요.")

    return master.create(BASE, context, values, key, check=check)


def update_base(context: AuthContext, row_id: int, values: dict[str, Any], key: str):
    return master.update(BASE, context, row_id, values, key)


def delete_base(context: AuthContext, row_id: int, key: str):
    master.delete(BASE, context, row_id, key)


def add_base_item(context: AuthContext, base_id: int, values: dict[str, Any], key: str):
    """고정 수당 한 줄. FIXED 방식 항목만 넣을 수 있다."""

    def run(connection: Connection, scoped: AuthContext):
        if master.fetch(connection, BASE, scoped, base_id) is None:
            raise ApiError(404, "NOT_FOUND", BASE.not_found)
        calc = connection.execute(
            text(
                "SELECT calc_kind FROM hr.pay_item "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": values["pay_item_id"]},
        ).scalar()
        if calc is None:
            raise _invalid("pay_item_id", "현재 공간의 급여 항목을 선택하세요.")
        if calc != "FIXED":
            raise _invalid("pay_item_id", "고정 수당(FIXED) 항목만 넣을 수 있습니다.")
        merged = {**values, "pay_base_id": base_id}
        master.reject_duplicate(connection, BASE_ITEM, scoped, merged, None)
        created = master.store(connection, BASE_ITEM, scoped, merged, None)
        return created, BASE_ITEM.entity, created["id"]

    return action(
        MODULE,
        context,
        "hr.pay_base_item.create",
        key,
        {"base": base_id, **values},
        run,
        201,
    )


def update_base_item(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(BASE_ITEM, context, row_id, values, key)


def delete_base_item(context: AuthContext, row_id: int, key: str):
    master.delete(BASE_ITEM, context, row_id, key)


# ── 상여 규칙 ────────────────────────────────────────────────────────────────


def bonus_rules(context: AuthContext, **kwargs):
    return master.listing(BONUS, context, **kwargs)


def create_bonus_rule(context: AuthContext, values: dict[str, Any], key: str):
    def check(connection, scoped, merged, _current, _row_id):
        calc = connection.execute(
            text(
                "SELECT calc_kind FROM hr.pay_item "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_scope(scoped), "id": merged["pay_item_id"]},
        ).scalar()
        if calc != "BONUS":
            raise _invalid("pay_item_id", "상여(BONUS) 항목을 선택하세요.")

    return master.create(BONUS, context, values, key, check=check)


def update_bonus_rule(
    context: AuthContext, row_id: int, values: dict[str, Any], key: str
):
    return master.update(BONUS, context, row_id, values, key)


def delete_bonus_rule(context: AuthContext, row_id: int, key: str):
    master.delete(BONUS, context, row_id, key)


# ── 급여 계산 ────────────────────────────────────────────────────────────────


def runs(context: AuthContext, **kwargs):
    return master.listing(RUN, context, **kwargs)


def _month_range(month: str) -> tuple[date, date]:
    year, number = int(month[:4]), int(month[5:7])
    return date(year, number, 1), date(year, number, monthrange(year, number)[1])


def _confirmed_close(connection: Connection, scoped: AuthContext, month: str) -> int:
    close_id = connection.execute(
        text(
            "SELECT id FROM hr.attendance_close WHERE workspace_id=:w AND generation_id=:g "
            "AND close_month=:month AND status='confirmed'"
        ),
        {**_scope(scoped), "month": month},
    ).scalar()
    if close_id is None:
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            f"{month} 근태를 먼저 마감해야 급여를 계산할 수 있습니다.",
            {"reason": "ATTENDANCE_NOT_CLOSED", "month": month},
        )
    return close_id


def _active_items(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]]:
    return [
        dict(row)
        for row in connection.execute(
            text(
                "SELECT id, code, name, item_kind, calc_kind, rate, is_taxable, display_order "
                "FROM hr.pay_item WHERE workspace_id=:w AND generation_id=:g AND is_active "
                "ORDER BY display_order, code"
            ),
            _scope(scoped),
        ).mappings()
    ]


def _targets(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]]:
    """재직 사원 중 그 달에 적용되는 급여 기준이 있는 사람. 기준은 가장 최근 적용 월 하나."""
    first, last = _month_range(month)
    return [
        dict(row)
        for row in connection.execute(
            text(
                """
            SELECT DISTINCT ON (e.id)
                   e.id employee_id, e.employee_code, e.name employee_name,
                   d.code department_code, g.name grade_name,
                   b.id pay_base_id, b.base_salary, b.ordinary_hours,
                   coalesce(a.overtime_minutes,0) overtime_minutes,
                   coalesce(a.night_minutes,0) night_minutes,
                   coalesce(a.holiday_minutes,0) holiday_minutes
            FROM hr.employee e
            JOIN hr.department d ON d.workspace_id=e.workspace_id AND d.generation_id=e.generation_id AND d.id=e.department_id
            JOIN hr.title g ON g.workspace_id=e.workspace_id AND g.generation_id=e.generation_id AND g.id=e.grade_id
            JOIN hr.pay_base b ON b.workspace_id=e.workspace_id AND b.generation_id=e.generation_id
                              AND b.employee_id=e.id AND b.effective_from<=:month
            LEFT JOIN (SELECT employee_id,
                              sum(overtime_minutes) overtime_minutes,
                              sum(night_minutes) night_minutes,
                              sum(holiday_minutes) holiday_minutes
                         FROM hr.attendance
                        WHERE workspace_id=:w AND generation_id=:g AND work_date BETWEEN :first AND :last
                        GROUP BY employee_id) a ON a.employee_id=e.id
            WHERE e.workspace_id=:w AND e.generation_id=:g AND e.status='ACTIVE'
            ORDER BY e.id, b.effective_from DESC
                """
            ),
            {**_scope(scoped), "month": month, "first": first, "last": last},
        ).mappings()
    ]


def _fixed_amounts(
    connection: Connection, scoped: AuthContext, base_ids: list[int]
) -> dict[tuple[int, int], Decimal]:
    if not base_ids:
        return {}
    return {
        (row["pay_base_id"], row["pay_item_id"]): row["amount"]
        for row in connection.execute(
            text(
                "SELECT pay_base_id, pay_item_id, amount FROM hr.pay_base_item "
                "WHERE workspace_id=:w AND generation_id=:g AND pay_base_id=ANY(:bases)"
            ),
            {**_scope(scoped), "bases": base_ids},
        ).mappings()
    }


def _bonus_percent(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[int, Decimal]:
    """그 달(MM)에 쓰는 상여 규칙: 급여 항목 id → 지급률."""
    return {
        row["pay_item_id"]: row["rate_percent"]
        for row in connection.execute(
            text(
                "SELECT pay_item_id, rate_percent FROM hr.bonus_rule "
                "WHERE workspace_id=:w AND generation_id=:g AND payable_mm=:mm AND is_active"
            ),
            {**_scope(scoped), "mm": month[5:7]},
        ).mappings()
    }


def slip_lines(
    person: dict[str, Any],
    items_: list[dict[str, Any]],
    fixed: dict[tuple[int, int], Decimal],
    bonus: dict[int, Decimal],
) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
    """한 사람의 명세 줄과 지급·공제 합계. 공제는 과세 지급 합계에만 건다."""
    base_salary = Decimal(person["base_salary"])
    hourly = base_salary / Decimal(person["ordinary_hours"])
    lines: list[dict[str, Any]] = []
    gross = taxable = Decimal(0)
    for item in items_:
        calc = item["calc_kind"]
        if item["item_kind"] != "EARNING":
            continue
        basis: Decimal | None = None
        if calc == "BASE":
            amount = base_salary
        elif calc == "FIXED":
            amount = fixed.get((person["pay_base_id"], item["id"]), Decimal(0))
        elif calc in ATTENDANCE_KINDS:
            hours = Decimal(person[ATTENDANCE_KINDS[calc]]) / Decimal(60)
            basis = hours.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            amount = _won(hourly * Decimal(item["rate"]) * hours)
        elif calc == "BONUS":
            percent = bonus.get(item["id"])
            if percent is None:
                continue
            basis = percent
            amount = _won(base_salary * percent / Decimal(100))
        else:  # pragma: no cover - CHECK가 막는 조합
            continue
        # 기본급은 0이어도 남긴다. 그 사람에게 설정하지 않은 고정 수당은 줄을 만들지 않는다.
        if amount == 0 and calc != "BASE":
            continue
        gross += amount
        if item["is_taxable"]:
            taxable += amount
        lines.append(
            {
                "pay_item_id": item["id"],
                "item_code": item["code"],
                "amount": amount,
                "basis_quantity": basis,
            }
        )
    deduction = Decimal(0)
    for item in items_:
        if item["item_kind"] != "DEDUCTION":
            continue
        amount = _won(taxable * Decimal(item["rate"]) / Decimal(100))
        if amount == 0:
            continue
        deduction += amount
        lines.append(
            {
                "pay_item_id": item["id"],
                "item_code": item["code"],
                "amount": amount,
                "basis_quantity": Decimal(item["rate"]),
            }
        )
    return lines, gross, deduction


def calculate(context: AuthContext, month: str, pay_date: date, key: str):
    """그 달의 확정 근태 마감으로 급여를 계산한다. 작성 중인 실행이 있으면 다시 계산한다."""

    def run(connection: Connection, scoped: AuthContext):
        close_id = _confirmed_close(connection, scoped, month)
        items_ = _active_items(connection, scoped)
        if not any(item["calc_kind"] == "BASE" for item in items_):
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "기본급(BASE) 급여 항목을 먼저 만드세요.",
                {"reason": "NO_BASE_ITEM"},
            )
        people = _targets(connection, scoped, month)
        if not people:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "그 달에 적용되는 급여 기준이 있는 재직 사원이 없습니다.",
                {"reason": "NO_PAY_BASE"},
            )
        version = _replace_draft(connection, scoped, month)
        fixed = _fixed_amounts(
            connection, scoped, [person["pay_base_id"] for person in people]
        )
        bonus = _bonus_percent(connection, scoped, month)
        created = master.store(
            connection,
            RUN,
            scoped,
            {
                "pay_month": month,
                "attendance_close_id": close_id,
                "pay_date": pay_date,
                "version": version,
                "status": "draft",
                "confirmed_at": None,
            },
            None,
        )
        for person in people:
            lines, gross, deduction = slip_lines(person, items_, fixed, bonus)
            slip_id = connection.execute(
                text(
                    """
                INSERT INTO hr.payslip (workspace_id,generation_id,run_id,employee_id,
                    department_code,grade_name,gross_pay,deduction_total,net_pay)
                VALUES (:w,:g,:run,:employee,:department,:grade,:gross,:deduction,:net)
                RETURNING id
                    """
                ),
                {
                    **_scope(scoped),
                    "run": created["id"],
                    "employee": person["employee_id"],
                    "department": person["department_code"],
                    "grade": person["grade_name"],
                    "gross": gross,
                    "deduction": deduction,
                    "net": gross - deduction,
                },
            ).scalar_one()
            for line in lines:
                connection.execute(
                    text(
                        """
                    INSERT INTO hr.payslip_line (workspace_id,generation_id,payslip_id,
                        pay_item_id,item_code,amount,basis_quantity)
                    VALUES (:w,:g,:slip,:item,:code,:amount,:basis)
                        """
                    ),
                    {
                        **_scope(scoped),
                        "slip": slip_id,
                        "item": line["pay_item_id"],
                        "code": line["item_code"],
                        "amount": line["amount"],
                        "basis": line["basis_quantity"],
                    },
                )
        result = {**created, "employees": len(people)}
        return result, RUN.entity, created["id"]

    return action(
        MODULE,
        context,
        "hr.payroll_run.calculate",
        key,
        {"month": month, "payDate": pay_date.isoformat()},
        run,
        201,
    )


def _replace_draft(connection: Connection, scoped: AuthContext, month: str) -> int:
    """작성 중인 실행은 지우고 그 번호를 다시 쓴다. 확정본이 있으면 다음 번호가 된다."""
    draft = (
        connection.execute(
            text(
                "SELECT id, version FROM hr.payroll_run WHERE workspace_id=:w AND generation_id=:g "
                "AND pay_month=:month AND status='draft'"
            ),
            {**_scope(scoped), "month": month},
        )
        .mappings()
        .one_or_none()
    )
    if draft is not None:
        connection.execute(
            text(
                "DELETE FROM hr.payslip_line WHERE workspace_id=:w AND generation_id=:g "
                "AND payslip_id IN (SELECT id FROM hr.payslip "
                "WHERE workspace_id=:w AND generation_id=:g AND run_id=:run)"
            ),
            {**_scope(scoped), "run": draft["id"]},
        )
        connection.execute(
            text(
                "DELETE FROM hr.payslip WHERE workspace_id=:w AND generation_id=:g AND run_id=:run"
            ),
            {**_scope(scoped), "run": draft["id"]},
        )
        connection.execute(
            text(
                "DELETE FROM hr.payroll_run WHERE workspace_id=:w AND generation_id=:g AND id=:run"
            ),
            {**_scope(scoped), "run": draft["id"]},
        )
        return draft["version"]
    latest = connection.execute(
        text(
            "SELECT max(version) FROM hr.payroll_run "
            "WHERE workspace_id=:w AND generation_id=:g AND pay_month=:month"
        ),
        {**_scope(scoped), "month": month},
    ).scalar()
    return (latest or 0) + 1


def confirm_run(context: AuthContext, row_id: int, key: str):
    """확정하면 그 급여는 불변이다. 이전 확정본은 superseded가 되고 ERP는 최신 확정본만 읽는다."""

    def run(connection: Connection, scoped: AuthContext):
        row = master.fetch(connection, RUN, scoped, row_id)
        if row is None:
            raise ApiError(404, "NOT_FOUND", RUN.not_found)
        if row["status"] != "draft":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 확정했거나 지난 급여 실행입니다.",
                {"reason": "ALREADY_CONFIRMED"},
            )
        connection.execute(
            text(
                "UPDATE hr.payroll_run SET status='superseded' WHERE workspace_id=:w "
                "AND generation_id=:g AND pay_month=:month AND status='confirmed'"
            ),
            {**_scope(scoped), "month": row["pay_month"]},
        )
        confirmed = (
            connection.execute(
                text(
                    f"UPDATE hr.payroll_run SET status='confirmed', confirmed_at=clock_timestamp() "
                    f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {RUN.selection}"
                ),
                {**_scope(scoped), "id": row_id},
            )
            .mappings()
            .one()
        )
        return master.present(confirmed), RUN.entity, row_id

    return action(MODULE, context, "hr.payroll_run.confirm", key, {"id": row_id}, run)


# ── 급여대장·명세서 ──────────────────────────────────────────────────────────


def payslips(context: AuthContext, run_id: int, offset: int, limit: int):
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if master.fetch(connection, RUN, scoped, run_id) is None:
            raise ApiError(404, "NOT_FOUND", RUN.not_found)
        params = {**_scope(scoped), "run": run_id, "offset": offset, "limit": limit}
        total = connection.execute(
            text(
                "SELECT count(*) FROM hr.payslip "
                "WHERE workspace_id=:w AND generation_id=:g AND run_id=:run"
            ),
            params,
        ).scalar_one()
        rows = (
            connection.execute(
                text(
                    """
                SELECT s.id, s.employee_id, e.employee_code, e.name employee_name,
                       s.department_code, s.grade_name, s.gross_pay, s.deduction_total, s.net_pay
                FROM hr.payslip s
                JOIN hr.employee e ON e.workspace_id=s.workspace_id AND e.generation_id=s.generation_id AND e.id=s.employee_id
                WHERE s.workspace_id=:w AND s.generation_id=:g AND s.run_id=:run
                ORDER BY s.department_code, e.employee_code
                OFFSET :offset LIMIT :limit
                    """
                ),
                params,
            )
            .mappings()
            .all()
        )
    return [master.present(row) for row in rows], total


def payslip_detail(context: AuthContext, slip_id: int):
    """명세서 한 장 — 항목별 줄과 급여 월. 인쇄 화면이 쓴다."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        row = (
            connection.execute(
                text(
                    """
                SELECT s.id, s.run_id, r.pay_month, r.pay_date, r.status, r.version,
                       s.employee_id, e.employee_code, e.name employee_name,
                       s.department_code, s.grade_name, s.gross_pay, s.deduction_total, s.net_pay
                FROM hr.payslip s
                JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id AND r.id=s.run_id
                JOIN hr.employee e ON e.workspace_id=s.workspace_id AND e.generation_id=s.generation_id AND e.id=s.employee_id
                WHERE s.workspace_id=:w AND s.generation_id=:g AND s.id=:id
                    """
                ),
                {**_scope(scoped), "id": slip_id},
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise ApiError(404, "NOT_FOUND", "급여명세서를 찾을 수 없습니다.")
        lines = (
            connection.execute(
                text(
                    """
                SELECT l.id, l.item_code, p.name item_name, p.item_kind, p.calc_kind,
                       l.amount, l.basis_quantity
                FROM hr.payslip_line l
                JOIN hr.pay_item p ON p.workspace_id=l.workspace_id AND p.generation_id=l.generation_id AND p.id=l.pay_item_id
                WHERE l.workspace_id=:w AND l.generation_id=:g AND l.payslip_id=:slip
                ORDER BY p.item_kind, p.display_order, l.item_code
                    """
                ),
                {**_scope(scoped), "slip": slip_id},
            )
            .mappings()
            .all()
        )
    return {**master.present(row), "lines": [master.present(line) for line in lines]}


def severance(context: AuthContext, employee_id: int):
    """퇴직금 추계 = 최근 3개월 평균 임금(1일) × 30일 × 근속 연수. 저장하지 않는다(F28)."""
    with read() as connection:
        scoped = read_scope(connection, context, MODULE)
        employee = (
            connection.execute(
                text(
                    "SELECT id, employee_code, name, hire_date, retire_date FROM hr.employee "
                    "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
                ),
                {**_scope(scoped), "id": employee_id},
            )
            .mappings()
            .one_or_none()
        )
        if employee is None:
            raise ApiError(404, "NOT_FOUND", "사원을 찾을 수 없습니다.")
        months = (
            connection.execute(
                text(
                    """
                SELECT r.pay_month, s.gross_pay
                FROM hr.payslip s
                JOIN hr.payroll_run r ON r.workspace_id=s.workspace_id AND r.generation_id=s.generation_id
                                     AND r.id=s.run_id AND r.status='confirmed'
                WHERE s.workspace_id=:w AND s.generation_id=:g AND s.employee_id=:id
                ORDER BY r.pay_month DESC LIMIT 3
                    """
                ),
                {**_scope(scoped), "id": employee_id},
            )
            .mappings()
            .all()
        )
        last_day = employee["retire_date"] or business_today()
    days = sum(
        monthrange(int(m["pay_month"][:4]), int(m["pay_month"][5:7]))[1] for m in months
    )
    total = sum((m["gross_pay"] for m in months), Decimal(0))
    daily = _won(total / days) if days else Decimal(0)
    years = Decimal((last_day - employee["hire_date"]).days) / Decimal(365)
    return {
        "employeeId": employee["id"],
        "employeeCode": employee["employee_code"],
        "employeeName": employee["name"],
        "months": [m["pay_month"] for m in months],
        "averageDailyWage": str(daily),
        "serviceYears": str(years.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)),
        "estimate": str(_won(daily * 30 * years)),
    }
