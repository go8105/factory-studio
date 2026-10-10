import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from fs.common.db import reset_engine
from fs.hr import work
from fs.hr.work_setup import create_example_company
from fs.main import create_app
from seed.generate import create_template


@pytest.fixture
def company_env(clean_database, monkeypatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", os.environ["TEST_DATABASE_URL"])
    monkeypatch.setenv(
        "SESSION_SECRET", "test-company-session-secret-with-32-characters"
    )
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setattr(work, "now", lambda: datetime(2026, 10, 12, 0, 0, tzinfo=UTC))
    reset_engine()
    password = "Test-only-" + str(uuid4())
    with engine.begin() as c:
        create_template(c, date(2026, 9, 24))
        company = create_example_company(c, password, password)
    clients = []
    for login in ["hugh-admin", "hugh-staff"]:
        client = TestClient(create_app())
        clients.append(client)
        response = client.post(
            "/api/v1/core/sessions",
            json={"loginId": login, "password": password},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
        client.csrf = response.json()["data"]["csrfToken"]
    yield engine, company, clients[0], clients[1]
    for client in clients:
        client.close()
    reset_engine()


def call(client, company, path, body=None, key=None):
    return client.post(
        "/api/v1/hr/work/" + path,
        params={"companyId": company["companyId"]},
        json=body,
        headers={"X-CSRF-Token": client.csrf, "Idempotency-Key": key or str(uuid4())},
    )


def overview(client, company):
    r = client.get(
        "/api/v1/hr/work/overview",
        params={"companyId": company["companyId"], "month": "2026-10"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def request(
    client, company, kind="HOURLY", start="09:00", end="10:00", day="2026-10-13"
):
    return call(
        client,
        company,
        "requests",
        {
            "kind": kind,
            "startsAt": day + "T" + start + ":00+09:00",
            "endsAt": day + "T" + end + ":00+09:00",
            "reason": "예제 신청",
            "destination": "예제 출장지" if kind == "TRIP" else None,
        },
    )


def test_company_scope_and_guest_denial(company_env):
    _, company, admin, staff = company_env
    assert len(admin.get("/api/v1/hr/work/companies").json()["data"]) == 1
    assert overview(staff, company)["person"]["role"] == "STAFF"
    assert (
        staff.get(
            "/api/v1/hr/work/overview",
            params={"companyId": company["companyId"] + 100, "month": "2026-10"},
        ).status_code
        == 403
    )
    with TestClient(create_app()) as guest:
        assert (
            guest.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "근무 체험"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 201
        )
        assert guest.get("/api/v1/hr/work/companies").status_code == 403
    assert (
        call(
            staff,
            company,
            "clock/clock-in",
            {"employeeId": overview(admin, company)["person"]["id"]},
        ).status_code
        == 200
    )  # 본문 사원 ID로 본인을 바꿀 수 없다
    assert (
        overview(staff, company)["activeSession"]["employee_id"]
        == overview(staff, company)["person"]["id"]
    )


def test_clock_idempotency_and_employee_visibility(company_env, monkeypatch):
    _, company, admin, staff = company_env
    key = str(uuid4())
    first = call(staff, company, "clock/clock-in", key=key)
    assert first.status_code == 200, first.text
    assert call(staff, company, "clock/clock-in", key=key).json() == first.json()
    assert call(staff, company, "clock/clock-in").status_code == 409
    monkeypatch.setattr(work, "now", lambda: datetime(2026, 10, 12, 9, tzinfo=UTC))
    assert call(staff, company, "clock/clock-out").status_code == 200
    assert call(staff, company, "clock/clock-out").status_code == 409
    assert len(overview(staff, company)["sessions"]) == 1
    assert call(admin, company, "clock/clock-in").status_code == 200
    assert len(overview(admin, company)["sessions"]) == 2
    assert len(overview(staff, company)["sessions"]) == 1


def test_hourly_approval_and_trip_no_deduction(company_env):
    _, company, admin, staff = company_env
    made = request(staff, company)
    assert made.status_code == 200, made.text
    assert made.json()["data"]["minutes"] == 60
    id = made.json()["data"]["id"]
    assert call(staff, company, "requests/approve", {"id": id}).status_code == 403
    key = str(uuid4())
    approved = call(admin, company, "requests/approve", {"id": id}, key)
    assert approved.status_code == 200, approved.text
    assert (
        call(admin, company, "requests/approve", {"id": id}, key).json()
        == approved.json()
    )
    assert overview(staff, company)["remainingMinutes"] == 7140
    assert call(admin, company, "requests/approve", {"id": id}).status_code == 409
    trip = request(staff, company, "TRIP", day="2026-10-14").json()["data"]["id"]
    assert call(admin, company, "requests/approve", {"id": trip}).status_code == 200
    assert overview(staff, company)["remainingMinutes"] == 7140


def test_hourly_break_overlap_fraction_and_half_preserve_clock(company_env):
    _, company, admin, staff = company_env
    assert request(staff, company, start="09:00", end="09:30").status_code == 400
    assert (
        request(staff, company, start="11:00", end="13:00").json()["data"]["minutes"]
        == 60
    )
    assert request(staff, company, start="11:00", end="12:00").status_code == 400
    assert request(staff, company, start="08:00", end="09:00").status_code == 400
    assert call(staff, company, "clock/clock-in").status_code == 200
    half = request(staff, company, "HALF_PM", "14:00", "18:00", day="2026-10-12")
    assert half.json()["data"]["minutes"] == 240
    assert (
        call(
            admin, company, "requests/approve", {"id": half.json()["data"]["id"]}
        ).status_code
        == 200
    )
    assert overview(staff, company)["activeSession"]["clock_in"] is not None


def test_revoked_membership_blocks_receipt_replay(company_env):
    engine, company, _, staff = company_env
    key = str(uuid4())
    assert call(staff, company, "clock/clock-in", key=key).status_code == 200
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.company_member SET is_active=false WHERE workspace_id=:w AND role='MEMBER'"
            ),
            {"w": company["companyId"]},
        )
    assert call(staff, company, "clock/clock-in", key=key).status_code == 403


def test_cancel_and_admin_correction_events(company_env):
    _, company, admin, staff = company_env
    request_id = request(staff, company).json()["data"]["id"]
    assert (
        call(staff, company, "requests/cancel", {"id": request_id}).status_code == 200
    )
    r = call(staff, company, "clock/clock-in").json()["data"]["id"]
    body = {
        "id": r,
        "clockIn": "2026-10-12T08:59:00+09:00",
        "clockOut": None,
        "reason": "출근 버튼 누락 정정",
    }
    assert call(staff, company, "corrections", body).status_code == 403
    assert call(admin, company, "corrections", body).status_code == 200
    assert any(e["action"] == "correct" for e in overview(admin, company)["events"])


def test_concurrent_clock_in_single_session(company_env):
    _, company, _, staff = company_env
    with ThreadPoolExecutor(2) as pool:
        statuses = list(
            pool.map(
                lambda _: call(staff, company, "clock/clock-in").status_code, range(2)
            )
        )
    assert sorted(statuses) == [200, 409]
    assert len(overview(staff, company)["sessions"]) == 1


def test_approved_cancel_returns_balance_once(company_env):
    _,company,admin,staff=company_env
    id=request(staff,company).json()['data']['id']
    assert call(admin,company,'requests/approve',{'id':id}).status_code==200
    assert call(staff,company,'requests/cancel',{'id':id}).json()['data']['status']=='CANCEL_REQUESTED'
    assert overview(staff,company)['remainingMinutes']==7140
    key=str(uuid4())
    assert call(admin,company,'requests/approve',{'id':id},key).json()['data']['status']=='CANCELLED'
    assert call(admin,company,'requests/approve',{'id':id},key).status_code==200
    assert overview(staff,company)['remainingMinutes']==7200


def test_closed_month_and_invalid_timestamp(company_env,monkeypatch):
    _,company,admin,staff=company_env
    monkeypatch.setattr(work,'now',lambda:datetime(2026,9,10,0,0,tzinfo=UTC))
    assert call(staff,company,'clock/clock-in').status_code==200
    assert call(admin,company,'close',{'month':'2026-09'}).status_code==400
    monkeypatch.setattr(work,'now',lambda:datetime(2026,10,12,0,0,tzinfo=UTC))
    assert call(admin,company,'close',{'month':'2026-09'}).status_code==400
    assert call(staff,company,'clock/clock-out').status_code==200
    assert call(admin,company,'close',{'month':'2026-09'}).status_code==200
    assert request(staff,company,day='2026-09-14').status_code==409
    assert call(staff,company,'requests',{'kind':'HOURLY','startsAt':'invalid','endsAt':'invalid','reason':'예제 시각'}).status_code==400
    assert request(staff,company,day='2027-01-04').status_code==400
