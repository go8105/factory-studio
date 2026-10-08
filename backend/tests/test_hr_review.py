"""W1b-4 HR 자격·평가·현황·본인과 EIP 공통 제공 함수.

핵심 규칙(DSN-30 F06·F31·F41~F44): 자격은 만료 30일 전부터 경고만 한다.
평가는 작성 → 제출 → 평가자 확정이고, 평가 기간을 닫으면 더 고칠 수 없다.
현황·인건비·본인 조회는 모두 저장하지 않는 조회 계산이며, 인건비는 **확정 급여**만 센다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

SEEDS = ()
EMPTY_MODULES = ("hr",)  # 빈 공간에서 규칙만 본다 — HR 시드는 W1c에서 따로 검증한다
H = "/api/v1/hr"


@pytest.fixture
def hr(guest_space):
    client, created, engine = guest_space
    return client, created, engine


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
    """생산부에 사원 2명 — E001 일반, E100 부서장."""
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
    head = _ok(
        _post(
            client,
            created,
            "/titles",
            {
                "titleKind": "DUTY",
                "code": "HEAD",
                "name": "부서장",
                "rankOrder": 1,
                "isHead": True,
            },
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
    common = {
        "departmentId": department["id"],
        "gradeId": grade["id"],
        "workPatternId": pattern["id"],
        "hireDate": "2026-03-02",
    }
    worker = _ok(
        _post(
            client,
            created,
            "/employees",
            {**common, "employeeCode": "E001", "name": "홍길동"},
        ),
        201,
    )
    boss = _ok(
        _post(
            client,
            created,
            "/employees",
            {**common, "employeeCode": "E100", "name": "김부장", "dutyId": head["id"]},
        ),
        201,
    )
    return {"worker": worker, "boss": boss}


def _cycle(client, created):
    return _ok(
        _post(
            client,
            created,
            "/review-cycles",
            {"cycleYear": "2026", "name": "2026년 평가"},
        ),
        201,
    )


def test_qualification_warns_before_it_expires(hr):
    client, created, _ = hr
    ids = _org(client, created)
    worker = ids["worker"]["id"]

    def add(name, expires):
        return _ok(
            _post(
                client,
                created,
                "/qualifications",
                {
                    "employeeId": worker,
                    "qualKind": "CERT",
                    "name": name,
                    "acquiredOn": "2025-01-02",
                    "expiresOn": expires,
                },
            ),
            201,
        )

    add("지게차운전", "2026-10-20")  # FS_TODAY=2026-09-24 → 26일 남음
    add("산업안전기사", "2027-06-30")
    add("위험물취급", "2026-09-01")
    forever = _ok(
        _post(
            client,
            created,
            "/qualifications",
            {
                "employeeId": worker,
                "qualKind": "TRAINING",
                "name": "신입 교육",
                "acquiredOn": "2026-03-02",
            },
        ),
        201,
    )
    assert forever["expiresOn"] is None

    states = {
        row["name"]: row["expiryState"]
        for row in _ok(client.get(f"{H}/qualifications", params={"limit": 50}))
    }
    assert states == {
        "지게차운전": "EXPIRING",
        "산업안전기사": "VALID",
        "위험물취급": "EXPIRED",
        "신입 교육": "NONE",
    }
    near = _ok(client.get(f"{H}/qualifications", params={"expiring": True}))
    assert {row["name"] for row in near} == {"지게차운전", "위험물취급"}

    # 인사카드(H-05)에도 함께 나온다.
    card = _ok(client.get(f"{H}/employees/{worker}"))
    assert len(card["qualifications"]) == 4
    assert card["qualifications"][0]["expiryState"] in (
        "NONE",
        "VALID",
        "EXPIRING",
        "EXPIRED",
    )


def test_review_runs_from_self_to_reviewer(hr):
    client, created, _ = hr
    ids = _org(client, created)
    cycle = _cycle(client, created)
    made = _ok(
        _post(
            client,
            created,
            "/reviews",
            {
                "cycleId": cycle["id"],
                "employeeId": ids["worker"]["id"],
                "goals": "불량률 1% 아래로 낮추기",
            },
        ),
        201,
    )
    # 평가자를 안 적으면 그 부서 부서장이 된다.
    assert (made["reviewerCode"], made["status"]) == ("E100", "draft")

    _ok(
        client.patch(
            f"{H}/reviews/{made['id']}",
            json={"selfComment": "목표를 넘겼습니다"},
            headers=_headers(created),
        )
    )
    # 제출 전에는 평가자가 확정할 수 없다.
    early = client.post(
        f"{H}/reviews/{made['id']}/confirm",
        json={"reviewerCode": "E100", "grade": "A"},
        headers=_headers(created),
    )
    assert early.status_code == 409
    assert early.json()["error"]["details"]["reason"] == "WRONG_STATUS"

    _ok(_post(client, created, f"/reviews/{made['id']}/submit"))
    # 제출 후에는 본인이 못 고친다.
    assert (
        client.patch(
            f"{H}/reviews/{made['id']}",
            json={"selfComment": "다시 씁니다"},
            headers=_headers(created),
        ).status_code
        == 409
    )
    # 지정된 평가자만 확정한다.
    wrong = client.post(
        f"{H}/reviews/{made['id']}/confirm",
        json={"reviewerCode": "E001", "grade": "A"},
        headers=_headers(created),
    )
    assert wrong.status_code == 400

    confirmed = _ok(
        client.post(
            f"{H}/reviews/{made['id']}/confirm",
            json={
                "reviewerCode": "E100",
                "grade": "A",
                "reviewerComment": "잘했습니다",
            },
            headers=_headers(created),
        )
    )
    assert (confirmed["status"], confirmed["grade"]) == ("confirmed", "A")
    assert confirmed["confirmedAt"]
    rows = _ok(client.get(f"{H}/reviews", params={"cycleId": cycle["id"]}))
    assert rows[0]["employeeCode"] == "E001" and rows[0]["cycleYear"] == "2026"


def test_closed_cycle_stops_new_and_changed_reviews(hr):
    client, created, _ = hr
    ids = _org(client, created)
    cycle = _cycle(client, created)
    made = _ok(
        _post(
            client,
            created,
            "/reviews",
            {
                "cycleId": cycle["id"],
                "employeeId": ids["worker"]["id"],
                "goals": "목표를 적습니다",
            },
        ),
        201,
    )
    closed = _ok(_post(client, created, f"/review-cycles/{cycle['id']}/close"))
    assert closed["status"] == "CLOSED"
    assert (
        _post(client, created, f"/review-cycles/{cycle['id']}/close").status_code == 409
    )
    blocked = client.patch(
        f"{H}/reviews/{made['id']}",
        json={"selfComment": "늦게 씁니다"},
        headers=_headers(created),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["reason"] == "CYCLE_CLOSED"
    again = _post(
        client,
        created,
        "/reviews",
        {
            "cycleId": cycle["id"],
            "employeeId": ids["boss"]["id"],
            "goals": "부서장 목표",
        },
    )
    assert again.status_code == 409


def test_one_review_per_employee_in_a_cycle(hr):
    client, created, _ = hr
    ids = _org(client, created)
    cycle = _cycle(client, created)
    body = {
        "cycleId": cycle["id"],
        "employeeId": ids["worker"]["id"],
        "goals": "같은 사람 두 번",
    }
    _ok(_post(client, created, "/reviews", body), 201)
    assert _post(client, created, "/reviews", body).status_code == 400


def test_overview_counts_people_and_warns_about_qualifications(hr):
    client, created, _ = hr
    ids = _org(client, created)
    _ok(
        _post(
            client,
            created,
            "/qualifications",
            {
                "employeeId": ids["worker"]["id"],
                "qualKind": "CERT",
                "name": "지게차운전",
                "acquiredOn": "2025-01-02",
                "expiresOn": "2026-10-20",
            },
        ),
        201,
    )
    overview = _ok(client.get(f"{H}/overview", params={"month": "2026-03"}))
    assert overview["headcount"][0]["departmentCode"] == "PROD"
    assert overview["headcount"][0]["active"] == 2
    assert overview["moves"] == {"hires": 2, "leavers": 0}  # 둘 다 2026-03 입사
    assert [row["qualName"] for row in overview["expiring"]] == ["지게차운전"]
    assert overview["leave"]["usageRate"] is None  # 발생이 없으면 비율을 만들지 않는다


def test_cost_counts_confirmed_payroll_only(hr):
    client, created, _ = hr
    ids = _org(client, created)
    _ok(
        _post(
            client,
            created,
            "/pay-items",
            {
                "code": "BASE",
                "name": "기본급",
                "itemKind": "EARNING",
                "calcKind": "BASE",
            },
        ),
        201,
    )
    _ok(
        _post(
            client,
            created,
            "/pay-bases",
            {
                "employeeId": ids["worker"]["id"],
                "effectiveFrom": "2026-01",
                "baseSalary": "2000000",
            },
        ),
        201,
    )
    _ok(_post(client, created, "/attendance/generate", {"month": "2026-03"}), 201)
    opened = _ok(
        _post(client, created, "/attendance-closes", {"month": "2026-03"}), 201
    )
    _ok(_post(client, created, f"/attendance-closes/{opened['id']}/confirm"))
    run = _ok(
        _post(
            client,
            created,
            "/payroll-runs",
            {"month": "2026-03", "payDate": "2026-04-10"},
        ),
        201,
    )
    draft = _ok(client.get(f"{H}/cost", params={"month": "2026-03"}))
    assert draft["confirmed"] is False and draft["departments"] == []

    _ok(_post(client, created, f"/payroll-runs/{run['id']}/confirm"))
    confirmed = _ok(client.get(f"{H}/cost", params={"month": "2026-03"}))
    assert confirmed["confirmed"] is True
    assert confirmed["departments"][0]["grossPay"] == "2000000"
    assert [item["itemCode"] for item in confirmed["items"]] == ["BASE"]


def test_me_shows_only_that_person(hr):
    client, created, _ = hr
    ids = _org(client, created)
    worker = ids["worker"]["id"]
    _ok(
        _post(
            client,
            created,
            "/leave-balances",
            {"employeeId": worker, "leaveYear": "2026", "grantedDays": "15"},
        ),
        201,
    )
    _ok(_post(client, created, "/attendance/generate", {"month": "2026-03"}), 201)
    cycle = _cycle(client, created)
    _ok(
        _post(
            client,
            created,
            "/reviews",
            {"cycleId": cycle["id"], "employeeId": worker, "goals": "내 목표"},
        ),
        201,
    )
    mine = _ok(
        client.get(f"{H}/me", params={"employeeCode": "E001", "month": "2026-03"})
    )
    assert mine["employee"]["name"] == "홍길동"
    assert mine["employee"]["departmentCode"] == "PROD"
    assert mine["attendance"]["workedDays"] > 0
    assert mine["leave"]["remainingDays"] == "15.0"
    assert mine["payslips"] == []  # 확정 급여가 없다
    assert [r["cycleYear"] for r in mine["reviews"]] == ["2026"]
    assert (
        client.get(
            f"{H}/me", params={"employeeCode": "E999", "month": "2026-03"}
        ).status_code
        == 404
    )


def test_eip_providers_answer_summary_tasks_and_lookup(guest_space):
    client, created, engine = guest_space
    ids = _org(client, created)
    worker, boss = ids["worker"], ids["boss"]
    _ok(
        _post(
            client,
            created,
            "/leave-balances",
            {"employeeId": worker["id"], "leaveYear": "2026", "grantedDays": "15"},
        ),
        201,
    )
    request = _ok(
        _post(
            client,
            created,
            "/leave-requests",
            {
                "employeeId": worker["id"],
                "leaveKind": "ANNUAL",
                "fromDate": "2026-03-10",
                "toDate": "2026-03-10",
                "days": "1",
            },
        ),
        201,
    )
    cycle = _cycle(client, created)
    mine = _ok(
        _post(
            client,
            created,
            "/reviews",
            {"cycleId": cycle["id"], "employeeId": worker["id"], "goals": "내 목표"},
        ),
        201,
    )
    _ok(_post(client, created, f"/reviews/{mine['id']}/submit"))

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
        summary = interface.monthly_summary(connection, scoped, "2026-03")
        head_tasks = interface.pending_tasks(connection, scoped, "E100")
        own_tasks = interface.pending_tasks(connection, scoped, "E001")
        stranger = interface.pending_tasks(connection, scoped, "E999")
        found = interface.lookup(connection, scoped, request["requestNo"])
        person = interface.lookup(connection, scoped, "E001")
        missing = interface.lookup(connection, scoped, "NOPE")

    assert summary["metrics"]["headcount"] == 2
    assert summary["metrics"]["hires"] == 2
    assert summary["metrics"]["laborCost"] == "0"  # 확정 급여가 없다
    assert summary["metrics"]["leaveUsageRate"] == "0.0"
    # 부서장은 휴가 승인과 평가 확정을, 본인은 아무것도 기다리지 않는다.
    assert {task["kind"] for task in head_tasks} == {
        "LEAVE_APPROVAL",
        "REVIEW_DECISION",
    }
    assert own_tasks == []
    assert stranger == []
    assert found["kind"] == "leaveRequest" and found["path"] == "/hr/leaves"
    assert person["kind"] == "employee" and person["caption"] == "홍길동"
    assert missing is None
    assert boss["employeeCode"] == "E100"
