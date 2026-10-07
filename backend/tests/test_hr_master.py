"""W1b-1 HR 기준정보: 부서·직위/직책·근무 형태·사원·발령.

핵심 규칙(DSN-30): 사원의 부서·직위·직책·재직 상태는 **확정 발령으로만** 바뀐다.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

SEEDS = ()  # HR 시드는 아직 없다(W1c). 빈 공간에서 만든다.
H = "/api/v1/hr"


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


def _post(client, created, path: str, body: dict, key: str | None = None):
    return client.post(f"{H}{path}", json=body, headers=_headers(created, key))


def _base(client, created) -> dict[str, int]:
    """부서·직위·직책·근무 형태 한 벌."""
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
    duty = _ok(
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
    return {
        "department": department["id"],
        "grade": grade["id"],
        "duty": duty["id"],
        "pattern": pattern["id"],
    }


def _employee(client, created, ids, code: str = "E001") -> dict:
    return _ok(
        _post(
            client,
            created,
            "/employees",
            {
                "employeeCode": code,
                "name": "홍길동",
                "hireDate": "2026-03-02",
                "departmentId": ids["department"],
                "gradeId": ids["grade"],
                "workPatternId": ids["pattern"],
            },
        ),
        201,
    )


def test_masters_are_created_and_listed(hr):
    client, created = hr
    ids = _base(client, created)
    assert ids
    rows = _ok(client.get(f"{H}/departments"))
    assert [r["code"] for r in rows] == ["PROD"]
    titles = _ok(client.get(f"{H}/titles", params={"titleKind": "DUTY"}))
    assert [t["code"] for t in titles] == ["HEAD"]


def test_duplicate_department_code_is_field_error(hr):
    client, created = hr
    _base(client, created)
    response = _post(
        client, created, "/departments", {"code": "PROD", "name": "다른 이름"}
    )
    assert response.status_code == 400
    assert "code" in response.json()["error"]["details"]["fields"]


def test_department_cycle_is_rejected(hr):
    client, created = hr
    parent = _ok(
        _post(client, created, "/departments", {"code": "HQ", "name": "본사"}), 201
    )
    child = _ok(
        _post(
            client,
            created,
            "/departments",
            {"code": "SUB", "name": "지사", "parentId": parent["id"]},
        ),
        201,
    )
    response = client.patch(
        f"{H}/departments/{parent['id']}",
        json={"parentId": child["id"]},
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert "parentId" in response.json()["error"]["details"]["fields"]


def test_head_flag_only_on_duty(hr):
    client, created = hr
    response = _post(
        client,
        created,
        "/titles",
        {
            "titleKind": "GRADE",
            "code": "G9",
            "name": "부장",
            "rankOrder": 9,
            "isHead": True,
        },
    )
    assert response.status_code == 400
    assert "isHead" in response.json()["error"]["details"]["fields"]


def test_employee_create_also_confirms_hire_appointment(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    assert employee["status"] == "ACTIVE"
    card = _ok(client.get(f"{H}/employees/{employee['id']}"))
    assert [(a["kind"], a["status"]) for a in card["appointments"]] == [
        ("HIRE", "confirmed")
    ]
    assert card["appointments"][0]["appointmentNo"].startswith("AP-20260302-")


def test_employee_update_cannot_move_department(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    response = client.patch(
        f"{H}/employees/{employee['id']}",
        json={"departmentId": ids["department"]},
        headers=_headers(created),
    )
    assert response.status_code == 400  # 본문에 없는 칸 — 발령으로만 바꾼다


def test_appointment_moves_employee_only_after_confirm(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    other = _ok(
        _post(client, created, "/departments", {"code": "QC", "name": "품질부"}), 201
    )
    appointment = _ok(
        _post(
            client,
            created,
            "/appointments",
            {
                "employeeId": employee["id"],
                "kind": "TRANSFER",
                "effectiveDate": "2026-07-01",
                "departmentId": other["id"],
                "reason": "품질부 이동",
            },
        ),
        201,
    )
    assert appointment["status"] == "draft"
    assert (
        _ok(client.get(f"{H}/employees/{employee['id']}"))["departmentId"]
        == ids["department"]
    )

    confirmed = _ok(
        client.post(
            f"{H}/appointments/{appointment['id']}/confirm", headers=_headers(created)
        )
    )
    assert confirmed["status"] == "confirmed" and confirmed["confirmedAt"]
    assert (
        _ok(client.get(f"{H}/employees/{employee['id']}"))["departmentId"]
        == other["id"]
    )


def test_confirmed_appointment_is_immutable(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    card = _ok(client.get(f"{H}/employees/{employee['id']}"))
    hire_id = card["appointments"][0]["id"]
    again = client.post(
        f"{H}/appointments/{hire_id}/confirm", headers=_headers(created)
    )
    assert again.status_code == 409
    removed = client.delete(f"{H}/appointments/{hire_id}", headers=_headers(created))
    assert removed.status_code == 409


def test_retire_appointment_sets_status_and_date(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    appointment = _ok(
        _post(
            client,
            created,
            "/appointments",
            {
                "employeeId": employee["id"],
                "kind": "RETIRE",
                "effectiveDate": "2026-09-30",
                "reason": "개인 사정",
            },
        ),
        201,
    )
    _ok(
        client.post(
            f"{H}/appointments/{appointment['id']}/confirm", headers=_headers(created)
        )
    )
    card = _ok(client.get(f"{H}/employees/{employee['id']}"))
    assert (card["status"], card["retireDate"]) == ("RETIRED", "2026-09-30")
    blocked = _post(
        client,
        created,
        "/appointments",
        {"employeeId": employee["id"], "kind": "RETURN", "effectiveDate": "2026-10-01"},
    )
    assert blocked.status_code == 409


def test_transfer_requires_department(hr):
    client, created = hr
    ids = _base(client, created)
    employee = _employee(client, created, ids)
    response = _post(
        client,
        created,
        "/appointments",
        {
            "employeeId": employee["id"],
            "kind": "TRANSFER",
            "effectiveDate": "2026-07-01",
        },
    )
    assert response.status_code == 400
    assert "departmentId" in response.json()["error"]["details"]["fields"]


def test_referenced_department_cannot_be_deleted(hr):
    client, created = hr
    ids = _base(client, created)
    _employee(client, created, ids)
    response = client.delete(
        f"{H}/departments/{ids['department']}", headers=_headers(created)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "REFERENCED_BY_OTHERS"


def test_interface_provides_people_and_departments(hr):
    client, created = hr
    ids = _base(client, created)
    _employee(client, created, ids)
    from fs.common.db import get_engine
    from fs.hr import interface

    with get_engine().connect() as connection:
        from fs.common.auth import AuthContext

        scoped = AuthContext(
            actor_kind="GUEST",
            actor_key="test",
            workspace_id=created["workspaceId"],
            generation_id=created["generationId"],
            user_id=None,
            roles=frozenset(),
            token="g_test",
        )
        people = interface.employees(connection, scoped)
        departments = interface.departments(connection, scoped)
    assert [p["employeeCode"] for p in people] == ["E001"]
    assert people[0]["departmentCode"] == "PROD" and people[0]["gradeName"] == "과장"
    assert [d["code"] for d in departments] == ["PROD", "QC"] or [
        d["code"] for d in departments
    ] == ["PROD"]
