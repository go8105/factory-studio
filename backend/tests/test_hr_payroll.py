"""W1b-3 HR 급여: 항목·기준·계산·확정·명세서.

핵심 규칙(DSN-30 Q4·Q5): 입력은 그 달의 **확정 근태 마감**. 지급 = 기본급 + 고정 수당 +
근태 수당(통상시급 × 배율 × 시간) + 상여, 공제 = 과세 지급 × 퍼센트. 확정 후 불변, 재계산은 새 버전.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

SEEDS = ()
EMPTY_MODULES = ("hr",)  # 빈 공간에서 규칙만 본다 — HR 시드는 W1c에서 따로 검증한다
H = "/api/v1/hr"
MONTH = "2026-03"


@pytest.fixture
def hr(guest_space):
    client, created, _engine = guest_space
    return client, created


def _headers(created, key: str | None = None) -> dict[str, str]:
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": key or str(uuid4()),
    }


def _ok(response, status: int = 200):
    assert response.status_code == status, response.text
    return response.json().get("data") if response.content else None


def _post(client, created, path: str, body: dict | None = None):
    return client.post(f"{H}{path}", json=body, headers=_headers(created))


def _org(client, created) -> dict:
    """부서·직위·근무 형태·사원 1명 + 2026-03 근태(연장 120분·야간 60분)."""
    department = _ok(
        _post(client, created, "/departments", {"code": "PROD", "name": "생산부"}), 201
    )
    grade = _ok(
        _post(
            client,
            created,
            "/titles",
            {"titleKind": "GRADE", "code": "G3", "name": "과장", "rankOrder": 3},
        ),
        201,
    )
    pattern = _ok(
        _post(
            client,
            created,
            "/work-patterns",
            {
                "code": "DAY",
                "name": "일근",
                "patternKind": "DAY",
                "startTime": "09:00:00",
                "scheduledMinutes": 480,
            },
        ),
        201,
    )
    employee = _ok(
        _post(
            client,
            created,
            "/employees",
            {
                "employeeCode": "E001",
                "name": "홍길동",
                "hireDate": "2025-03-02",
                "departmentId": department["id"],
                "gradeId": grade["id"],
                "workPatternId": pattern["id"],
            },
        ),
        201,
    )
    _ok(_post(client, created, "/attendance/generate", {"month": MONTH}), 201)
    rows = _ok(client.get(f"{H}/attendance", params={"month": MONTH, "limit": 200}))
    workdays = [row for row in rows if row["dayKind"] == "WORKDAY"]
    _ok(
        client.patch(
            f"{H}/attendance/{workdays[0]['id']}",
            json={"overtimeMinutes": 120},
            headers=_headers(created),
        )
    )
    _ok(
        client.patch(
            f"{H}/attendance/{workdays[1]['id']}",
            json={"nightMinutes": 60},
            headers=_headers(created),
        )
    )
    return {"employee": employee, "department": department}


def _items(client, created) -> dict:
    """기본급·식대(고정)·연장 1.5배·야간 0.5배·상여·국민연금 4.5%."""

    def make(**body):
        return _ok(_post(client, created, "/pay-items", body), 201)

    return {
        "base": make(
            code="BASE",
            name="기본급",
            itemKind="EARNING",
            calcKind="BASE",
            displayOrder=1,
        ),
        "meal": make(
            code="MEAL",
            name="식대",
            itemKind="EARNING",
            calcKind="FIXED",
            isTaxable=False,
            displayOrder=2,
        ),
        "overtime": make(
            code="OT",
            name="연장수당",
            itemKind="EARNING",
            calcKind="OVERTIME",
            rate="1.5",
            displayOrder=3,
        ),
        "night": make(
            code="NIGHT",
            name="야간수당",
            itemKind="EARNING",
            calcKind="NIGHT",
            rate="0.5",
            displayOrder=4,
        ),
        "bonus": make(
            code="BONUS",
            name="정기상여",
            itemKind="EARNING",
            calcKind="BONUS",
            displayOrder=5,
        ),
        "pension": make(
            code="PENSION",
            name="국민연금",
            itemKind="DEDUCTION",
            calcKind="RATE",
            rate="4.5",
            displayOrder=1,
        ),
    }


def _base(client, created, ids, items, meal: str = "200000") -> dict:
    """통상시급이 딱 떨어지게 기본급 2,090,000 / 209시간 = 10,000원."""
    base = _ok(
        _post(
            client,
            created,
            "/pay-bases",
            {
                "employeeId": ids["employee"]["id"],
                "effectiveFrom": "2026-01",
                "baseSalary": "2090000",
                "ordinaryHours": 209,
            },
        ),
        201,
    )
    _ok(
        _post(
            client,
            created,
            f"/pay-bases/{base['id']}/items",
            {"payItemId": items["meal"]["id"], "amount": meal},
        ),
        201,
    )
    return base


def _close(client, created, month: str = MONTH) -> None:
    opened = _ok(_post(client, created, "/attendance-closes", {"month": month}), 201)
    _ok(_post(client, created, f"/attendance-closes/{opened['id']}/confirm"))


def _calculate(client, created, month: str = MONTH):
    return _post(
        client, created, "/payroll-runs", {"month": month, "payDate": "2026-04-10"}
    )


def test_pay_item_rules_match_the_database_check(hr):
    client, created = hr
    wrong_kind = _post(
        client,
        created,
        "/pay-items",
        {"code": "TAX", "name": "소득세", "itemKind": "DEDUCTION", "calcKind": "FIXED"},
    )
    assert wrong_kind.status_code == 400
    assert "calcKind" in wrong_kind.json()["error"]["details"]["fields"]
    missing_rate = _post(
        client,
        created,
        "/pay-items",
        {
            "code": "OT",
            "name": "연장수당",
            "itemKind": "EARNING",
            "calcKind": "OVERTIME",
        },
    )
    assert missing_rate.status_code == 400
    assert "rate" in missing_rate.json()["error"]["details"]["fields"]
    extra_rate = _post(
        client,
        created,
        "/pay-items",
        {
            "code": "BASE",
            "name": "기본급",
            "itemKind": "EARNING",
            "calcKind": "BASE",
            "rate": "1.5",
        },
    )
    assert extra_rate.status_code == 400


def test_only_fixed_items_go_into_a_pay_base(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    base = _ok(
        _post(
            client,
            created,
            "/pay-bases",
            {
                "employeeId": ids["employee"]["id"],
                "effectiveFrom": "2026-01",
                "baseSalary": "2090000",
            },
        ),
        201,
    )
    wrong = _post(
        client,
        created,
        f"/pay-bases/{base['id']}/items",
        {"payItemId": items["overtime"]["id"], "amount": "100000"},
    )
    assert wrong.status_code == 400
    _ok(
        _post(
            client,
            created,
            f"/pay-bases/{base['id']}/items",
            {"payItemId": items["meal"]["id"], "amount": "200000"},
        ),
        201,
    )
    again = _post(
        client,
        created,
        f"/pay-bases/{base['id']}/items",
        {"payItemId": items["meal"]["id"], "amount": "300000"},
    )
    assert again.status_code == 400  # 같은 항목은 한 번만
    detail = _ok(client.get(f"{H}/pay-bases/{base['id']}"))
    assert [line["itemCode"] for line in detail["items"]] == ["MEAL"]


def test_calculation_needs_a_confirmed_attendance_close(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    _base(client, created, ids, items)
    not_closed = _calculate(client, created)
    assert not_closed.status_code == 409
    assert not_closed.json()["error"]["details"]["reason"] == "ATTENDANCE_NOT_CLOSED"


def test_calculated_amounts_follow_the_design_formula(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    _base(client, created, ids, items)
    _close(client, created)
    run = _ok(_calculate(client, created), 201)
    assert (run["status"], run["version"], run["employees"]) == ("draft", 1, 1)

    slips = _ok(client.get(f"{H}/payslips", params={"runId": run["id"]}))
    assert len(slips) == 1 and slips[0]["departmentCode"] == "PROD"
    detail = _ok(client.get(f"{H}/payslips/{slips[0]['id']}"))
    amounts = {line["itemCode"]: line["amount"] for line in detail["lines"]}
    # 통상시급 10,000 · 연장 2시간 × 1.5 = 30,000 · 야간 1시간 × 0.5 = 5,000
    assert amounts["BASE"] == "2090000"
    assert amounts["MEAL"] == "200000"
    assert amounts["OT"] == "30000"
    assert amounts["NIGHT"] == "5000"
    assert "BONUS" not in amounts  # 3월 상여 규칙이 없다
    # 과세 지급 = 2,090,000 + 30,000 + 5,000 = 2,125,000 (식대는 비과세) → 4.5% = 95,625
    assert amounts["PENSION"] == "95625"
    assert detail["grossPay"] == "2325000"
    assert detail["deductionTotal"] == "95625"
    assert detail["netPay"] == "2229375"
    basis = {line["itemCode"]: line["basisQuantity"] for line in detail["lines"]}
    assert (basis["OT"], basis["NIGHT"]) == ("2.00", "1.00")


def test_bonus_only_applies_in_its_month(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    _base(client, created, ids, items)
    _ok(
        _post(
            client,
            created,
            "/bonus-rules",
            {
                "payableMm": "03",
                "ratePercent": "100",
                "payItemId": items["bonus"]["id"],
            },
        ),
        201,
    )
    not_bonus = _post(
        client,
        created,
        "/bonus-rules",
        {"payableMm": "06", "ratePercent": "50", "payItemId": items["base"]["id"]},
    )
    assert not_bonus.status_code == 400  # 상여 항목이 아니다
    _close(client, created)
    run = _ok(_calculate(client, created), 201)
    slips = _ok(client.get(f"{H}/payslips", params={"runId": run["id"]}))
    detail = _ok(client.get(f"{H}/payslips/{slips[0]['id']}"))
    amounts = {line["itemCode"]: line["amount"] for line in detail["lines"]}
    assert amounts["BONUS"] == "2090000"  # 기본급 × 100%


def test_recalculation_replaces_the_draft_and_confirmation_makes_a_new_version(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    base = _base(client, created, ids, items)
    _close(client, created)
    first = _ok(_calculate(client, created), 201)

    # 작성 중일 때 다시 계산하면 같은 버전을 덮어쓴다.
    _ok(
        client.patch(
            f"{H}/pay-bases/{base['id']}",
            json={"baseSalary": "3000000"},
            headers=_headers(created),
        )
    )
    again = _ok(_calculate(client, created), 201)
    assert again["version"] == 1 and again["id"] != first["id"]
    runs = _ok(client.get(f"{H}/payroll-runs", params={"month": MONTH}))
    assert len(runs) == 1
    slips = _ok(client.get(f"{H}/payslips", params={"runId": again["id"]}))
    assert (
        slips[0]["grossPay"] == "3250239"
    )  # 통상시급이 올라 연장·야간도 다시 계산된다

    confirmed = _ok(_post(client, created, f"/payroll-runs/{again['id']}/confirm"))
    assert confirmed["status"] == "confirmed" and confirmed["confirmedAt"]
    assert (
        _post(client, created, f"/payroll-runs/{again['id']}/confirm").status_code
        == 409
    )

    # 확정 후 재계산은 새 버전이 되고, 확정하면 이전 확정본은 superseded가 된다.
    third = _ok(_calculate(client, created), 201)
    assert third["version"] == 2
    _ok(_post(client, created, f"/payroll-runs/{third['id']}/confirm"))
    runs = _ok(client.get(f"{H}/payroll-runs", params={"month": MONTH}))
    assert sorted((r["version"], r["status"]) for r in runs) == [
        (1, "superseded"),
        (2, "confirmed"),
    ]


def test_erp_reads_department_and_item_totals_only(guest_space):
    client, created, engine = guest_space
    ids = _org(client, created)
    items = _items(client, created)
    _base(client, created, ids, items)
    _close(client, created)
    run = _ok(_calculate(client, created), 201)

    from fs.common.auth import AuthContext
    from fs.hr import interface

    scoped = AuthContext(
        "GUEST",
        "test",
        created["workspaceId"],
        created["generationId"],
        None,
        frozenset({"GUEST"}),
        "synthetic",
    )
    with engine.begin() as connection:
        before = interface.payroll_runs(connection, scoped, MONTH)
        assert before == {"month": MONTH, "confirmed": False, "lines": []}
    _ok(_post(client, created, f"/payroll-runs/{run['id']}/confirm"))
    with engine.begin() as connection:
        after = interface.payroll_runs(connection, scoped, MONTH)
    assert after["confirmed"] is True and after["version"] == 1
    assert {line["itemCode"] for line in after["lines"]} == {
        "BASE",
        "MEAL",
        "OT",
        "NIGHT",
        "PENSION",
    }
    assert all(line["departmentCode"] == "PROD" for line in after["lines"])
    # 개인 금액·사원 코드는 넘기지 않는다.
    assert all("employeeCode" not in line for line in after["lines"])


def test_severance_estimate_is_computed_not_stored(hr):
    client, created = hr
    ids = _org(client, created)
    items = _items(client, created)
    _base(client, created, ids, items)
    _close(client, created)
    run = _ok(_calculate(client, created), 201)
    _ok(_post(client, created, f"/payroll-runs/{run['id']}/confirm"))
    estimate = _ok(
        client.get(f"{H}/severance", params={"employeeId": ids["employee"]["id"]})
    )
    assert estimate["months"] == [MONTH]
    # 2,325,000 / 31일 = 75,000원, 2025-03-02 입사
    assert estimate["averageDailyWage"] == "75000"
    assert float(estimate["serviceYears"]) >= 1
    assert int(estimate["estimate"]) > 0
