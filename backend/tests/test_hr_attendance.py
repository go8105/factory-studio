"""W1b-2 HR 근태·마감·휴가.

핵심 규칙(DSN-30): 근태는 근무 형태·휴일로 자동 생성하고 예외만 고친다. 마감하면 그 달은 잠긴다.
휴가는 부서장이 승인하고, 잔여를 넘으면 거부하며, 승인하면 그 날짜의 근태가 LEAVE가 된다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text

SEEDS = ()
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


def _post(client, created, path: str, body: dict | None = None, key: str | None = None):
    return client.post(f"{H}{path}", json=body, headers=_headers(created, key))


def _setup(client, created) -> dict:
    """부서·직위·부서장 직책·근무 형태 + 사원 2명(1명은 부서장)."""
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
        "hireDate": "2026-01-02",
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
    return {"worker": worker, "boss": boss, "department": department["id"]}


def _holiday(engine, created, on: str, name: str) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO core.holiday (workspace_id,generation_id,holiday_on,name,kind) "
                "VALUES (:w,:g,:on,:name,'PUBLIC')"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "on": on,
                "name": name,
            },
        )


def test_generate_fills_the_month_once(hr):
    client, created, _ = hr
    _setup(client, created)
    first = _ok(
        _post(client, created, "/attendance/generate", {"month": "2026-03"}), 201
    )
    assert first["employees"] == 2 and first["created"] == 62  # 31일 × 2명
    again = _ok(
        _post(client, created, "/attendance/generate", {"month": "2026-03"}), 201
    )
    assert again["created"] == 0  # 이미 있는 날은 건드리지 않는다
    body = client.get(
        f"{H}/attendance", params={"month": "2026-03", "limit": 200}
    ).json()
    assert body["page"]["total"] == 62 and body["closed"] is False
    kinds = {row["workDate"]: row["dayKind"] for row in body["data"]}
    assert kinds["2026-03-02"] == "WORKDAY"  # 월요일
    assert kinds["2026-03-07"] == "OFFDAY"  # 토요일


def test_holiday_calendar_marks_the_day_off(hr):
    client, created, engine = hr
    _setup(client, created)
    _holiday(engine, created, "2026-03-02", "임시공휴일")
    _ok(_post(client, created, "/attendance/generate", {"month": "2026-03"}), 201)
    rows = _ok(client.get(f"{H}/attendance", params={"month": "2026-03", "limit": 200}))
    day = next(r for r in rows if r["workDate"] == "2026-03-02")
    assert (day["dayKind"], day["status"]) == ("HOLIDAY", "OFF")


def test_exception_edit_marks_manual_and_summary_counts_it(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    _ok(_post(client, created, "/attendance/generate", {"month": "2026-03"}), 201)
    rows = _ok(
        client.get(
            f"{H}/attendance",
            params={
                "month": "2026-03",
                "limit": 200,
                "employeeId": ids["worker"]["id"],
            },
        )
    )
    workday = next(r for r in rows if r["dayKind"] == "WORKDAY")
    updated = _ok(
        client.patch(
            f"{H}/attendance/{workday['id']}",
            json={"status": "LATE", "overtimeMinutes": 90, "note": "지각·연장"},
            headers=_headers(created),
        )
    )
    assert (updated["status"], updated["source"]) == ("LATE", "MANUAL")
    summary = _ok(client.get(f"{H}/attendance/summary", params={"month": "2026-03"}))
    mine = next(s for s in summary if s["employeeCode"] == "E001")
    assert mine["overtimeMinutes"] == 90 and mine["workedDays"] >= 1


def test_close_locks_the_month_and_reclose_makes_a_new_version(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    _ok(_post(client, created, "/attendance/generate", {"month": "2026-03"}), 201)
    rows = _ok(client.get(f"{H}/attendance", params={"month": "2026-03", "limit": 200}))
    workday = next(r for r in rows if r["dayKind"] == "WORKDAY")

    close = _ok(_post(client, created, "/attendance-closes", {"month": "2026-03"}), 201)
    assert (close["version"], close["status"]) == (1, "draft")
    confirmed = _ok(_post(client, created, f"/attendance-closes/{close['id']}/confirm"))
    assert confirmed["status"] == "confirmed" and confirmed["confirmedAt"]

    blocked = client.patch(
        f"{H}/attendance/{workday['id']}",
        json={"status": "ABSENT"},
        headers=_headers(created),
    )
    assert blocked.status_code == 409
    assert blocked.json()["error"]["details"]["reason"] == "MONTH_CLOSED"
    assert (
        _post(client, created, "/attendance/generate", {"month": "2026-03"}).status_code
        == 409
    )

    second = _ok(
        _post(client, created, "/attendance-closes", {"month": "2026-03"}), 201
    )
    assert second["version"] == 2
    _ok(
        client.patch(
            f"{H}/attendance/{workday['id']}",
            json={"status": "ABSENT"},
            headers=_headers(created),
        )
    )
    _ok(_post(client, created, f"/attendance-closes/{second['id']}/confirm"))
    closes = _ok(client.get(f"{H}/attendance-closes", params={"month": "2026-03"}))
    assert sorted((c["version"], c["status"]) for c in closes) == [
        (1, "superseded"),
        (2, "confirmed"),
    ]
    assert ids  # 설정이 쓰였음을 표시


def test_leave_needs_balance_and_cannot_exceed_remaining(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    worker = ids["worker"]["id"]
    no_balance = _post(
        client,
        created,
        "/leave-requests",
        {
            "employeeId": worker,
            "leaveKind": "ANNUAL",
            "fromDate": "2026-03-02",
            "toDate": "2026-03-02",
            "days": "1",
        },
    )
    assert no_balance.status_code == 400
    _ok(
        _post(
            client,
            created,
            "/leave-balances",
            {"employeeId": worker, "leaveYear": "2026", "grantedDays": "1.5"},
        ),
        201,
    )
    too_much = _post(
        client,
        created,
        "/leave-requests",
        {
            "employeeId": worker,
            "leaveKind": "ANNUAL",
            "fromDate": "2026-03-02",
            "toDate": "2026-03-03",
            "days": "2",
        },
    )
    assert too_much.status_code == 409
    assert too_much.json()["error"]["details"]["reason"] == "NOT_ENOUGH_LEAVE"


def test_approved_leave_turns_attendance_into_leave_and_uses_balance(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    worker, boss = ids["worker"]["id"], ids["boss"]
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
    request = _ok(
        _post(
            client,
            created,
            "/leave-requests",
            {
                "employeeId": worker,
                "leaveKind": "ANNUAL",
                "fromDate": "2026-03-02",
                "toDate": "2026-03-03",
                "days": "2",
                "reason": "개인 사정",
            },
        ),
        201,
    )
    assert request["requestNo"].startswith("LV-20260302-")
    mine = client.post(
        f"{H}/leave-requests/{request['id']}/approve",
        json={"approverCode": "E001"},
        headers=_headers(created),
    )
    assert mine.status_code == 400  # 부서장이 아니다

    approved = _ok(
        client.post(
            f"{H}/leave-requests/{request['id']}/approve",
            json={"approverCode": boss["employeeCode"]},
            headers=_headers(created),
        )
    )
    assert approved["status"] == "APPROVED" and approved["attendanceUpdated"] == 2
    rows = _ok(
        client.get(
            f"{H}/attendance",
            params={"month": "2026-03", "limit": 200, "employeeId": worker},
        )
    )
    assert [
        r["status"] for r in rows if r["workDate"] in ("2026-03-02", "2026-03-03")
    ] == [
        "LEAVE",
        "LEAVE",
    ]
    balance = _ok(client.get(f"{H}/leave-balances", params={"year": "2026"}))
    mine_balance = next(b for b in balance if b["employeeCode"] == "E001")
    assert (mine_balance["usedDays"], mine_balance["remainingDays"]) == ("2.0", "13.0")


def test_decided_request_cannot_be_decided_again(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    worker, boss = ids["worker"]["id"], ids["boss"]
    _ok(
        _post(
            client,
            created,
            "/leave-balances",
            {"employeeId": worker, "leaveYear": "2026", "grantedDays": "5"},
        ),
        201,
    )
    request = _ok(
        _post(
            client,
            created,
            "/leave-requests",
            {
                "employeeId": worker,
                "leaveKind": "HALF_AM",
                "fromDate": "2026-03-04",
                "toDate": "2026-03-04",
                "days": "0.5",
            },
        ),
        201,
    )
    _ok(
        client.post(
            f"{H}/leave-requests/{request['id']}/reject",
            json={"approverCode": boss["employeeCode"], "reason": "일정 조정 필요"},
            headers=_headers(created),
        )
    )
    again = client.post(
        f"{H}/leave-requests/{request['id']}/approve",
        json={"approverCode": boss["employeeCode"]},
        headers=_headers(created),
    )
    assert again.status_code == 409
    cancelled = client.post(
        f"{H}/leave-requests/{request['id']}/cancel", headers=_headers(created)
    )
    assert cancelled.status_code == 409


def test_requested_leave_can_be_cancelled(hr):
    client, created, _ = hr
    ids = _setup(client, created)
    worker = ids["worker"]["id"]
    _ok(
        _post(
            client,
            created,
            "/leave-balances",
            {"employeeId": worker, "leaveYear": "2026", "grantedDays": "5"},
        ),
        201,
    )
    request = _ok(
        _post(
            client,
            created,
            "/leave-requests",
            {
                "employeeId": worker,
                "leaveKind": "ANNUAL",
                "fromDate": "2026-03-05",
                "toDate": "2026-03-05",
                "days": "1",
            },
        ),
        201,
    )
    cancelled = _ok(
        client.post(
            f"{H}/leave-requests/{request['id']}/cancel", headers=_headers(created)
        )
    )
    assert cancelled["status"] == "CANCELLED"
    balance = _ok(client.get(f"{H}/leave-balances", params={"year": "2026"}))
    mine = next(b for b in balance if b["employeeCode"] == "E001")
    assert mine["remainingDays"] == "5.0"  # 취소하면 잔여가 돌아온다
