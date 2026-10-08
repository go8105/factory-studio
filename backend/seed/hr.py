"""HR 합성 시드 (W1c, DSN-30).

기준일 T를 중심으로:
  **지난달** — 근태 전체 + 마감 확정 + 급여 확정. 급여대장·인건비 분석·내 정보가 바로 보인다.
  **이번달** — 기준일까지 근태 + 마감본 작성 중. 사용자가 마감 확정 → 계산 → 확정을 직접 해 본다.

금액 계산은 제품과 같은 함수(`fs.hr.payroll.slip_lines`)를 쓴다 — 시드와 제품이 갈라지지 않게.
사람 이름·사업자 정보는 모두 합성이다.
"""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from seed.common import at, month_shift, month_text

if TYPE_CHECKING:  # pragma: no cover - 순환 참조를 피한다
    from seed.generate import SeedWriter

# 부서·직위·직책·근무 형태 — 코드는 모든 솔루션이 가져다 쓰는 원천이다(DSN-30 Q1).
DEPARTMENTS = [
    ("ADM", "경영지원팀", None, 1),
    ("PROD", "생산팀", None, 2),
    ("QC", "품질팀", None, 3),
    ("ENG", "설비팀", None, 4),
]
GRADES = [
    ("G1", "사원", 1),
    ("G2", "주임", 2),
    ("G3", "대리", 3),
    ("G4", "과장", 4),
    ("G5", "부장", 5),
]
DUTIES = [("HEAD", "팀장", 1, True), ("LEAD", "파트장", 2, False)]
WORK_PATTERNS = [
    ("DAY", "주간 일근", "DAY", "09:00:00", 480, 60, False),
    ("NIGHT", "야간 교대", "TWO_SHIFT", "22:00:00", 480, 60, False),
]
# (코드, 이름, 부서, 직위, 직책, 근무 형태, 입사 개월 전, 기본급)
EMPLOYEES = [
    ("E001", "강민수", "ADM", "G5", "HEAD", "DAY", 96, "5200000"),
    ("E002", "서지우", "ADM", "G3", None, "DAY", 44, "3400000"),
    ("E003", "한도윤", "PROD", "G5", "HEAD", "DAY", 84, "5000000"),
    ("E004", "오세림", "PROD", "G4", "LEAD", "DAY", 60, "4100000"),
    ("E005", "임하준", "PROD", "G2", None, "NIGHT", 30, "2900000"),
    ("E006", "배소윤", "PROD", "G1", None, "NIGHT", 14, "2510000"),
    ("E007", "노은찬", "QC", "G4", "HEAD", "DAY", 72, "4300000"),
    ("E008", "문가영", "QC", "G2", None, "DAY", 26, "2950000"),
    ("E009", "조태현", "ENG", "G4", "HEAD", "DAY", 68, "4400000"),
    ("E010", "유나경", "ENG", "G3", None, "DAY", 38, "3300000"),
]
# 급여 항목 — 공제는 비율(RATE)로만 만든다(DB CHECK).
PAY_ITEMS = [
    ("BASE", "기본급", "EARNING", "BASE", None, True, 1),
    ("MEAL", "식대", "EARNING", "FIXED", None, False, 2),
    ("DUTY_PAY", "직책수당", "EARNING", "FIXED", None, True, 3),
    ("OT", "연장근로수당", "EARNING", "OVERTIME", "1.5", True, 4),
    ("NIGHT_PAY", "야간근로수당", "EARNING", "NIGHT", "0.5", True, 5),
    ("HOLIDAY_PAY", "휴일근로수당", "EARNING", "HOLIDAY", "1.5", True, 6),
    ("BONUS", "정기상여", "EARNING", "BONUS", None, True, 7),
    ("PENSION", "국민연금", "DEDUCTION", "RATE", "4.5", True, 1),
    ("HEALTH", "건강보험", "DEDUCTION", "RATE", "3.55", True, 2),
    ("EMPLOY", "고용보험", "DEDUCTION", "RATE", "0.9", True, 3),
    ("TAX", "소득세", "DEDUCTION", "RATE", "3.3", True, 4),
]
MEAL_PAY = "200000"
DUTY_PAY = {"HEAD": "300000", "LEAD": "150000"}
ORDINARY_HOURS = 209
# 공휴일 — 날짜가 고정인 것만 둔다(설·추석은 음력이라 해마다 달라 넣지 않는다).
FIXED_HOLIDAYS = [
    ((1, 1), "신정"),
    ((3, 1), "삼일절"),
    ((5, 5), "어린이날"),
    ((6, 6), "현충일"),
    ((8, 15), "광복절"),
    ((10, 3), "개천절"),
    ((10, 9), "한글날"),
    ((12, 25), "성탄절"),
]
# 자격·교육 — (사원, 구분, 이름, 발급처, 취득 개월 전, 유효 개월, 만료 D-day)
QUALIFICATIONS = [
    ("E004", "CERT", "지게차운전기능사", "한국산업인력공단", 40, None, 18),
    ("E005", "CERT", "위험물산업기사", "한국산업인력공단", 24, None, 400),
    ("E007", "CERT", "품질경영기사", "한국산업인력공단", 50, None, None),
    ("E009", "CERT", "전기기능사", "한국산업인력공단", 60, None, -40),
    ("E003", "TRAINING", "관리감독자 안전보건교육", "안전보건공단", 4, None, None),
    ("E006", "TRAINING", "신규 채용자 안전교육", "사내", 13, None, None),
    ("E008", "TRAINING", "측정기 취급 교육", "사내", 8, None, None),
]
ANNUAL_DAYS = {"G1": "11.0", "G2": "15.0", "G3": "15.0", "G4": "17.0", "G5": "20.0"}
# 휴가 — (사원, 종류, 시작 D-day, 일수, 상태)
LEAVES = [
    ("E002", "ANNUAL", -24, "2", "APPROVED"),
    ("E004", "ANNUAL", -16, "1", "APPROVED"),
    ("E008", "HALF_AM", -11, "0.5", "APPROVED"),
    ("E010", "ANNUAL", -6, "1", "APPROVED"),
    ("E006", "ANNUAL", 6, "2", "REQUESTED"),
    ("E005", "SICK", 3, "1", "REQUESTED"),
    ("E002", "ANNUAL", -3, "1", "REJECTED"),
]
# 예외 근태 — (사원, D-day, 상태, 연장 분)
ATTENDANCE_EXCEPTIONS = [
    ("E004", -38, "LATE", 0),
    ("E006", -31, "ABSENT", 0),
    ("E003", -27, "NORMAL", 120),
    ("E004", -20, "NORMAL", 90),
    ("E010", -13, "EARLY", 0),
    ("E008", -9, "NORMAL", 60),
    ("E003", -5, "NORMAL", 150),
]


def _settled(seed_date: date, day_of_month: int) -> int:
    """마감·급여를 확정한 날(이번달 N일)까지의 D-day. 기준일을 넘지 않는다."""
    return min(day_of_month - seed_date.day, 0)


def _holidays(year: int) -> list[tuple[date, str]]:
    return [(date(year, m, d), name) for (m, d), name in FIXED_HOLIDAYS]


def _month_days(month: str, last: date | None = None) -> list[date]:
    year, number = int(month[:4]), int(month[5:7])
    days = [
        date(year, number, day) for day in range(1, monthrange(year, number)[1] + 1)
    ]
    return [day for day in days if last is None or day <= last]


def seed_hr(writer: SeedWriter) -> None:
    """HR 한 벌. 다른 솔루션과 같은 기준일 T를 쓴다."""
    from fs.hr.payroll import slip_lines

    seed_date = writer.seed_date
    prev_month = month_text(seed_date, -1)
    this_month = month_text(seed_date, 0)

    writer.add(
        "core.holiday",
        [
            {"holiday_on": day, "name": name, "kind": "PUBLIC"}
            for year in (seed_date.year - 1, seed_date.year)
            for day, name in _holidays(year)
        ],
    )
    holiday_days = {
        day
        for year in (seed_date.year - 1, seed_date.year)
        for day, _ in _holidays(year)
    }

    departments = writer.add(
        "hr.department",
        [
            {
                "code": code,
                "name": name,
                "parent_id": parent,
                "display_order": order,
                "is_active": True,
            }
            for code, name, parent, order in DEPARTMENTS
        ],
        "code",
    )
    titles = writer.add(
        "hr.title",
        [
            {
                "title_kind": "GRADE",
                "code": code,
                "name": name,
                "rank_order": order,
                "is_head": False,
            }
            for code, name, order in GRADES
        ]
        + [
            {
                "title_kind": "DUTY",
                "code": code,
                "name": name,
                "rank_order": order,
                "is_head": head,
            }
            for code, name, order, head in DUTIES
        ],
        "code",
    )
    patterns = writer.add(
        "hr.work_pattern",
        [
            {
                "code": code,
                "name": name,
                "pattern_kind": kind,
                "start_time": start,
                "scheduled_minutes": minutes,
                "break_minutes": rest,
                "works_weekend": weekend,
                "is_active": True,
            }
            for code, name, kind, start, minutes, rest, weekend in WORK_PATTERNS
        ],
        "code",
    )

    hire_dates = {
        code: month_shift(seed_date.replace(day=2), -months)
        for code, _n, _d, _g, _t, _p, months, _s in EMPLOYEES
    }
    employees = writer.add(
        "hr.employee",
        [
            {
                "employee_code": code,
                "name": name,
                "hire_date": hire_dates[code],
                "status": "ACTIVE",
                "department_id": departments[dept],
                "grade_id": titles[grade],
                "duty_id": titles[duty] if duty else None,
                "work_pattern_id": patterns[pattern],
                "retire_date": None,
                "retire_reason": None,
            }
            for code, name, dept, grade, duty, pattern, _m, _s in EMPLOYEES
        ],
        "employee_code",
    )
    # 입사 발령은 사원마다 확정 1건 — 현재 부서·직위는 확정 발령의 결과다(F03).
    writer.add(
        "hr.appointment",
        [
            {
                "appointment_no": f"AP-{hire_dates[code]:%Y%m%d}-{index + 1:03d}",
                "employee_id": employees[code],
                "kind": "HIRE",
                "effective_date": hire_dates[code],
                "department_id": departments[dept],
                "grade_id": titles[grade],
                "duty_id": titles[duty] if duty else None,
                "reason": "입사",
                "status": "confirmed",
                # 발령일은 실제 입사일이지만, 이 공간에 기록을 넣은 시각은 공간을 만든 때다.
                "confirmed_at": at(seed_date, -91, 9),
            }
            for index, (code, _n, dept, grade, duty, _p, _m, _s) in enumerate(EMPLOYEES)
        ],
    )

    writer.add(
        "hr.qualification",
        [
            {
                "employee_id": employees[code],
                "qual_kind": kind,
                "name": name,
                "issuer": issuer,
                "acquired_on": month_shift(seed_date, -months),
                "expires_on": seed_date + timedelta(days=expires)
                if expires is not None
                else None,
            }
            for code, kind, name, issuer, months, _v, expires in QUALIFICATIONS
        ],
    )

    year = f"{seed_date.year:04d}"
    writer.add(
        "hr.leave_balance",
        [
            {
                "employee_id": employees[code],
                "leave_year": year,
                "granted_days": Decimal(ANNUAL_DAYS[grade]),
            }
            for code, _n, _d, grade, _t, _p, _m, _s in EMPLOYEES
        ],
    )
    heads = {
        dept: code
        for code, _n, dept, _g, duty, _p, _m, _s in EMPLOYEES
        if duty == "HEAD"
    }
    department_of = {code: dept for code, _n, dept, _g, _t, _p, _m, _s in EMPLOYEES}
    leave_days: dict[tuple[str, date], str] = {}
    leave_rows = []
    for index, (code, kind, offset, days, status) in enumerate(LEAVES):
        start = seed_date + timedelta(days=offset)
        span = int(float(days)) or 1
        end = start + timedelta(days=span - 1)
        decided = status != "REQUESTED"
        leave_rows.append(
            {
                "request_no": f"LV-{start:%Y%m%d}-{index + 1:03d}",
                "employee_id": employees[code],
                "leave_kind": kind,
                "from_date": start,
                "to_date": end,
                "days": Decimal(days),
                "reason": "개인 사정" if kind == "ANNUAL" else None,
                "status": status,
                "approver_code": heads[department_of[code]] if decided else None,
                "decided_at": at(seed_date, offset - 1, 17) if decided else None,
            }
        )
        if status == "APPROVED":
            for step in range(span):
                leave_days[(code, start + timedelta(days=step))] = (
                    "HALF_LEAVE" if kind in ("HALF_AM", "HALF_PM") else "LEAVE"
                )
    writer.add("hr.leave_request", leave_rows)

    # ── 근태: 지난달 전체 + 이번달 기준일까지 ────────────────────────────────
    exceptions = {
        (code, seed_date + timedelta(days=offset)): (status, overtime)
        for code, offset, status, overtime in ATTENDANCE_EXCEPTIONS
    }
    pattern_of = {code: pattern for code, _n, _d, _g, _t, pattern, _m, _s in EMPLOYEES}
    rows = []
    for month, last in ((prev_month, None), (this_month, seed_date)):
        for day in _month_days(month, last):
            for code, _n, _d, _g, _t, pattern, _m, _s in EMPLOYEES:
                if day < hire_dates[code]:
                    continue
                rows.append(
                    _attendance_row(
                        employees[code],
                        day,
                        night=pattern_of[code] == "NIGHT",
                        holiday=day in holiday_days,
                        leave=leave_days.get((code, day)),
                        exception=exceptions.get((code, day)),
                    )
                )
    writer.add("hr.attendance", rows)

    closes = writer.add(
        "hr.attendance_close",
        [
            {
                "close_month": prev_month,
                "version": 1,
                "status": "confirmed",
                "confirmed_at": at(seed_date, _settled(seed_date, 2), 10),
            },
            # 이번달은 작성 중 — 사용자가 확정하고 급여를 계산해 본다.
            {
                "close_month": this_month,
                "version": 1,
                "status": "draft",
                "confirmed_at": None,
            },
        ],
        "close_month",
    )

    _payroll(writer, employees, prev_month, closes[prev_month], slip_lines)


def _attendance_row(
    employee_id: int,
    day: date,
    *,
    night: bool,
    holiday: bool,
    leave: str | None,
    exception: tuple[str, int] | None,
) -> dict[str, Any]:
    """하루치 한 줄. 제품의 자동 생성과 같은 규칙이다(주말·공휴일은 쉼)."""
    off = day.weekday() >= 5
    day_kind = "HOLIDAY" if holiday else "OFFDAY" if off else "WORKDAY"
    if leave and day_kind == "WORKDAY":
        status, overtime, source = leave, 0, "MANUAL"
    elif day_kind != "WORKDAY":
        status, overtime, source = "OFF", 0, "AUTO"
    elif exception:
        status, overtime, source = exception[0], exception[1], "MANUAL"
    else:
        status, overtime, source = "NORMAL", 0, "AUTO"
    worked = status in ("NORMAL", "LATE", "EARLY")
    return {
        "employee_id": employee_id,
        "work_date": day,
        "day_kind": day_kind,
        "status": status,
        "clock_in": None,
        "clock_out": None,
        "overtime_minutes": overtime,
        # 야간 교대는 22:00~06:00이 통째로 야간 구간이다.
        "night_minutes": 480 if worked and night else 0,
        "holiday_minutes": 0,
        "source": source,
        "note": None,
    }


def _payroll(
    writer: SeedWriter,
    employees: dict[str, int],
    month: str,
    close_id: int,
    slip_lines: Any,
) -> None:
    """지난달 급여를 제품과 같은 식으로 계산해 확정 1건으로 넣는다."""
    seed_date = writer.seed_date
    items = writer.add(
        "hr.pay_item",
        [
            {
                "code": code,
                "name": name,
                "item_kind": kind,
                "calc_kind": calc,
                "rate": Decimal(rate) if rate else None,
                "is_taxable": taxable,
                "display_order": order,
                "is_active": True,
            }
            for code, name, kind, calc, rate, taxable, order in PAY_ITEMS
        ],
        "code",
    )
    effective_from = month_text(seed_date, -12)
    base_of_id = writer.add(
        "hr.pay_base",
        [
            {
                "employee_id": employees[code],
                "effective_from": effective_from,
                "base_salary": Decimal(salary),
                "ordinary_hours": ORDINARY_HOURS,
            }
            for code, _n, _d, _g, _t, _p, _m, salary in EMPLOYEES
        ],
        "employee_id",
    )
    base_of = {code: base_of_id[employees[code]] for code, *_ in EMPLOYEES}
    writer.add(
        "hr.pay_base_item",
        [
            {
                "pay_base_id": base_of[code],
                "pay_item_id": items["MEAL"],
                "amount": Decimal(MEAL_PAY),
            }
            for code, _n, _d, _g, _t, _p, _m, _s in EMPLOYEES
        ]
        + [
            {
                "pay_base_id": base_of[code],
                "pay_item_id": items["DUTY_PAY"],
                "amount": Decimal(DUTY_PAY[duty]),
            }
            for code, _n, _d, _g, duty, _p, _m, _s in EMPLOYEES
            if duty
        ],
    )
    # 지난달에 정기 상여가 들어가도록 그 달을 지급 월로 둔다(기본급의 50%).
    writer.add(
        "hr.bonus_rule",
        [
            {
                "payable_mm": month[5:7],
                "rate_percent": Decimal("50.00"),
                "pay_item_id": items["BONUS"],
                "is_active": True,
            }
        ],
    )

    pay_date = month_shift(seed_date.replace(day=10), 0)
    run = writer.add(
        "hr.payroll_run",
        [
            {
                "pay_month": month,
                "attendance_close_id": close_id,
                "pay_date": pay_date,
                "version": 1,
                "status": "confirmed",
                "confirmed_at": at(seed_date, _settled(seed_date, 3), 11),
            }
        ],
        "pay_month",
    )[month]

    item_rows = [
        {
            "id": items[code],
            "code": code,
            "name": name,
            "item_kind": kind,
            "calc_kind": calc,
            "rate": Decimal(rate) if rate else None,
            "is_taxable": taxable,
            "display_order": order,
        }
        for code, name, kind, calc, rate, taxable, order in PAY_ITEMS
    ]
    fixed = {
        (base_of[code], items["MEAL"]): Decimal(MEAL_PAY)
        for code, _n, _d, _g, _t, _p, _m, _s in EMPLOYEES
    } | {
        (base_of[code], items["DUTY_PAY"]): Decimal(DUTY_PAY[duty])
        for code, _n, _d, _g, duty, _p, _m, _s in EMPLOYEES
        if duty
    }
    bonus = {items["BONUS"]: Decimal("50.00")}
    minutes = _month_minutes(writer, month)
    department_name = {code: dept for code, _n, dept, _g, _t, _p, _m, _s in EMPLOYEES}
    grade_name = {code: name for code, name, _o in GRADES}
    slips = []
    lines_by_code: dict[str, list[dict[str, Any]]] = {}
    for code, _n, _d, grade, _t, _p, _m, salary in EMPLOYEES:
        worked = minutes.get(employees[code], (0, 0, 0))
        person = {
            "pay_base_id": base_of[code],
            "base_salary": Decimal(salary),
            "ordinary_hours": ORDINARY_HOURS,
            "overtime_minutes": worked[0],
            "night_minutes": worked[1],
            "holiday_minutes": worked[2],
        }
        lines, gross, deduction = slip_lines(person, item_rows, fixed, bonus)
        lines_by_code[code] = lines
        slips.append(
            {
                "run_id": run,
                "employee_id": employees[code],
                "department_code": department_name[code],
                "grade_name": grade_name[grade],
                "gross_pay": gross,
                "deduction_total": deduction,
                "net_pay": gross - deduction,
            }
        )
    slip_ids = writer.add("hr.payslip", slips, "employee_id")
    writer.add(
        "hr.payslip_line",
        [
            {
                "payslip_id": slip_ids[employees[code]],
                "pay_item_id": line["pay_item_id"],
                "item_code": line["item_code"],
                "amount": line["amount"],
                "basis_quantity": line["basis_quantity"],
            }
            for code, lines in lines_by_code.items()
            for line in lines
        ],
    )


def _month_minutes(writer: SeedWriter, month: str) -> dict[int, tuple[int, int, int]]:
    first, last = _month_days(month)[0], _month_days(month)[-1]
    return {
        row["employee_id"]: (
            row["overtime_minutes"],
            row["night_minutes"],
            row["holiday_minutes"],
        )
        for row in writer.connection.execute(
            text(
                "SELECT employee_id, sum(overtime_minutes) overtime_minutes, "
                "sum(night_minutes) night_minutes, sum(holiday_minutes) holiday_minutes "
                "FROM hr.attendance WHERE workspace_id=:w AND generation_id=:g "
                "AND work_date BETWEEN :first AND :last GROUP BY employee_id"
            ),
            {
                "w": writer.workspace_id,
                "g": writer.generation_id,
                "first": first,
                "last": last,
            },
        ).mappings()
    }
