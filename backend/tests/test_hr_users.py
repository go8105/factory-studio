# ruff: noqa: F811
# Imported pytest fixture is deliberately shadowed by fixture parameters.
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import text
from test_hr_work import company_env  # noqa: F401

from fs.main import create_app


def manage(client, company, operation="", body=None, key=None):
    return client.post(
        "/api/v1/hr/work/users" + operation,
        params={"companyId": company["companyId"]},
        json=body,
        headers={"X-CSRF-Token": client.csrf, "Idempotency-Key": key or str(uuid4())},
    )


def users(client, company):
    return client.get(
        "/api/v1/hr/work/users", params={"companyId": company["companyId"]}
    )


def test_admin_creates_account_once_and_hides_credentials(company_env):
    engine, company, admin, staff = company_env
    secret = "Synthetic-new-" + str(uuid4())
    body = {
        "loginId": "new-staff",
        "password": secret,
        "name": "추가 직원",
        "employeeCode": "HUGH-003",
        "annualDays": 12,
        "role": "STAFF",
    }
    assert users(staff, company).status_code == 403
    assert staff.get("/api/v1/hr/work/managed-companies").json()["data"] == []
    key = str(uuid4())
    r = manage(admin, company, body=body, key=key)
    assert r.status_code == 200, r.text
    assert manage(admin, company, body=body, key=key).json() == r.json()
    listing = users(admin, company).json()["data"]
    assert len(listing) == 3
    assert secret not in str(listing)
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM core.app_user WHERE login_id='new-staff'")
            ).scalar()
            == 1
        )
        receipts = (
            c.execute(
                text(
                    "SELECT response_summary FROM core.request_receipt WHERE operation_key LIKE 'hr.users.%'"
                )
            )
            .scalars()
            .all()
        )
        events = (
            c.execute(
                text("SELECT summary FROM hr.work_event WHERE action LIKE 'user-%'")
            )
            .scalars()
            .all()
        )
        assert secret not in str(receipts) + str(events)
        assert "password" not in str(receipts) + str(events)
    with TestClient(create_app()) as new:
        login = new.post(
            "/api/v1/core/sessions",
            json={"loginId": "new-staff", "password": secret},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert login.status_code == 201, login.text
        overview = new.get(
            "/api/v1/hr/work/overview",
            params={"companyId": company["companyId"], "month": "2026-10"},
        )
        assert overview.json()["data"]["remainingMinutes"] == 12 * 480
        assert overview.json()["data"]["person"]["role"] == "STAFF"


def test_reset_renames_and_revokes_old_session(company_env):
    _, company, admin, staff = company_env
    uid = next(
        u["userId"]
        for u in users(admin, company).json()["data"]
        if u["loginId"] == "hugh-staff"
    )
    secret = "Synthetic-reset-" + str(uuid4())
    assert (
        manage(
            staff, company, "/password", {"userId": uid, "password": secret}
        ).status_code
        == 403
    )
    assert (
        manage(
            admin, company, "/password", {"userId": uid, "password": secret}
        ).status_code
        == 200
    )
    assert staff.get("/api/v1/hr/work/companies").status_code == 401
    assert (
        manage(
            admin, company, "/login-id", {"userId": uid, "loginId": "renamed-staff"}
        ).status_code
        == 200
    )
    with TestClient(create_app()) as login:
        assert (
            login.post(
                "/api/v1/core/sessions",
                json={"loginId": "renamed-staff", "password": secret},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 201
        )
    assert manage(admin, company, "/disable", {"userId": uid}).status_code == 200
    with TestClient(create_app()) as login:
        assert (
            login.post(
                "/api/v1/core/sessions",
                json={"loginId": "renamed-staff", "password": secret},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 401
        )


def test_scope_self_guard_and_password_validation(company_env):
    _, company, admin, _ = company_env
    own = next(
        u["userId"]
        for u in users(admin, company).json()["data"]
        if u["role"] == "ADMIN"
    )
    assert manage(admin, company, "/disable", {"userId": own}).status_code == 409
    assert (
        manage(
            admin,
            company,
            "/password",
            {"userId": own + 10000, "password": "Synthetic-no-target"},
        ).status_code
        == 404
    )
    secret = "tiny"
    r = manage(
        admin,
        company,
        body={
            "loginId": "invalid-user",
            "name": "예제",
            "employeeCode": "HUGH-004",
            "password": secret,
        },
    )
    assert r.status_code == 400
    assert secret not in r.text
    assert users(admin, {"companyId": company["companyId"] + 10000}).status_code == 403


def test_platform_admin_activates_prepared_users_without_membership(company_env):
    engine, company, _, _ = company_env
    from fs.common.clock import real_today
    from fs.core.service import create_member_account

    secret = "Synthetic-platform-" + str(uuid4())
    with engine.begin() as c:
        create_member_account(
            c, "platform-admin", "전체 관리자", secret, real_today(), admin=True
        )
        c.execute(
            text(
                "UPDATE core.app_user SET status='disabled',disabled_at=now() WHERE login_id IN ('hugh-admin','hugh-staff')"
            )
        )
    with TestClient(create_app()) as platform:
        r = platform.post(
            "/api/v1/core/sessions",
            json={"loginId": "platform-admin", "password": secret},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert r.status_code == 201
        platform.csrf = r.json()["data"]["csrfToken"]
        assert (
            platform.get("/api/v1/hr/work/managed-companies").json()["data"][0]["id"]
            == company["companyId"]
        )
        listing = users(platform, company).json()["data"]
        assert len(listing) == 2
        for u in listing:
            assert (
                manage(
                    platform,
                    company,
                    "/password",
                    {"userId": u["userId"], "password": secret},
                ).status_code
                == 200
            )
        assert all(u["active"] for u in users(platform, company).json()["data"])
        admin_id = next(u["userId"] for u in listing if u["role"] == "ADMIN")
        assert (
            manage(platform, company, "/disable", {"userId": admin_id}).status_code
            == 409
        )


def test_platform_company_creation_atomic_and_company_admin_not_global(company_env):
    engine, _company, admin, _staff = company_env
    from fs.common.clock import real_today
    from fs.core.service import create_member_account

    body = {
        "companyName": "합성 신규 회사",
        "loginId": "new-owner",
        "name": "신규 관리자",
        "employeeCode": "OWNER-001",
        "password": "Synthetic-" + str(uuid4()),
        "role": "ADMIN",
    }
    headers = {"X-CSRF-Token": admin.csrf, "Idempotency-Key": str(uuid4())}
    assert (
        admin.get("/api/v1/hr/work/management-capabilities").json()["data"][
            "isPlatformAdmin"
        ]
        is False
    )
    assert (
        admin.post("/api/v1/hr/work/companies", json=body, headers=headers).status_code
        == 403
    )
    secret = "Synthetic-global-" + str(uuid4())
    with engine.begin() as c:
        create_member_account(
            c, "global-manager", "총 관리자", secret, real_today(), admin=True
        )
    with TestClient(create_app()) as platform:
        login = platform.post(
            "/api/v1/core/sessions",
            json={"loginId": "global-manager", "password": secret},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert login.status_code == 201, login.text
        headers = {
            "X-CSRF-Token": login.json()["data"]["csrfToken"],
            "Idempotency-Key": str(uuid4()),
        }
        r = platform.post("/api/v1/hr/work/companies", json=body, headers=headers)
        assert r.status_code == 200, r.text
        assert (
            platform.post(
                "/api/v1/hr/work/companies", json=body, headers=headers
            ).json()
            == r.json()
        )
        co = r.json()["data"]["companyId"]
        listing = platform.get(
            "/api/v1/hr/work/users", params={"companyId": co}
        ).json()["data"]
        assert listing[0]["role"] == "ADMIN"
        assert body["password"] not in str(r.json())
        assert (
            platform.post(
                "/api/v1/hr/work/companies",
                json={**body, "companyName": "다른 회사"},
                headers={**headers, "Idempotency-Key": str(uuid4())},
            ).status_code
            == 409
        )
        with engine.connect() as c:
            assert (
                c.execute(
                    text("SELECT count(*) FROM core.company WHERE name='다른 회사'")
                ).scalar()
                == 0
            )
            assert not c.execute(
                text(
                    "SELECT 1 FROM core.user_role ur JOIN core.role r ON r.id=ur.role_id JOIN core.app_user u ON u.id=ur.user_id WHERE u.login_id='new-owner' AND r.role_key='ADMIN'"
                )
            ).first()
