"""회사 GW 기반을 격리 PostgreSQL에서 검증한다. 업무 공개/전체 ACL 검증은 후속이다."""

# ruff: noqa: F811
import importlib.util
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fs.common.auth import resolve_token
from fs.common.errors import ApiError
from fs.core.company import lock_accounts
from fs.gw import company
from fs.gw.router import router
from fs.hr.interface import work_identity
from fs.hr.work_setup import create_company
from fs.main import create_app
from seed.copy import COMPANY_GW_TABLES, _seeded_tables, copy_module_seed
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from test_hr_work import company_env  # noqa: F401


def context(engine, client):
    with engine.begin() as c:
        return resolve_token(c, client.cookies.get("fs_session"))


def bound(engine, co, client, state="ACTIVE"):
    ctx = context(engine, client)
    with engine.begin() as c:
        scoped, _ = company.resolve_company(c, ctx, co["companyId"])
        p = {"w": scoped.workspace_id, "g": scoped.generation_id, "u": ctx.user_id}
        person = c.execute(
            text("""INSERT INTO gw.person(workspace_id,generation_id,code,name,job_role)
          VALUES (:w,:g,'GW-STAFF','합성 직원','STAFF') RETURNING id"""),
            p,
        ).scalar_one()
        p["person"] = person
        c.execute(
            text("""INSERT INTO gw.person_identity_binding(workspace_id,generation_id,person_id,user_id,state,requested_by_user_id,activated_at)
          VALUES (:w,:g,:person,:u,CAST(:state AS varchar),:u,CASE WHEN CAST(:state AS varchar)='ACTIVE' THEN clock_timestamp() END)"""),
            {**p, "state": state},
        )
    return scoped, person


def test_unbound_company_status_is_read_only(company_env):
    engine, co, admin, staff = company_env
    for client, owner in [(admin, True), (staff, False)]:
        r = client.get("/api/v1/gw/me", params={"companyId": co["companyId"]})
        assert r.status_code == 200, r.text
        data = r.json()["data"]
        assert data["bindingStatus"] == "UNBOUND"
        assert data["setupRequired"] is True
        assert data["companyOwner"] is owner
        assert data["hrIdentityAvailable"] is True
        assert data["roles"] == data["capabilities"] == []
        assert data["businessReady"] is False
    with engine.connect() as c:
        assert all(
            c.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
            for table in COMPANY_GW_TABLES
        )


def test_company_scope_no_admin_bypass_and_no_guest_access(company_env):
    engine, co, admin, staff = company_env
    with engine.begin() as c:
        other = create_company(
            c,
            {
                "companyName": "다른 합성 회사",
                "loginId": "other-company-admin",
                "name": "다른 관리자",
                "password": "Synthetic-" + str(uuid4()),
                "employeeCode": "OTHER-01",
                "workStart": "09:00",
                "dailyMinutes": 480,
                "breakMinutes": 60,
                "annualDays": 15,
            },
        )
    for client in (staff, admin):
        assert (
            client.get(
                "/api/v1/gw/me", params={"companyId": other["companyId"]}
            ).status_code
            == 403
        )
        listing = client.get("/api/v1/gw/companies").json()["data"]
        assert [x["id"] for x in listing] == [co["companyId"]]
    with TestClient(create_app()) as guest:
        assert guest.get("/api/v1/gw/companies").status_code == 401
        assert (
            guest.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "합성 회사 경계"},
                headers={"Idempotency-Key": str(uuid4())},
            ).status_code
            == 201
        )
        assert guest.get("/api/v1/gw/companies").status_code == 403
        assert (
            guest.get(
                "/api/v1/gw/me", params={"companyId": co["companyId"]}
            ).status_code
            == 403
        )


def test_all_63_business_endpoints_fail_closed_without_seeding(
    company_env, monkeypatch
):
    monkeypatch.setattr(company, "BUSINESS_READY", False)
    engine, co, _, staff = company_env
    count = 0
    for route in router.routes:
        path = re.sub(r"\{kind\}", "PURCHASE_INVOICE", route.path)
        path = re.sub(r"\{[^}]+\}", "1", path)
        for method in route.methods:
            r = staff.request(
                method,
                "/api/v1/gw" + path,
                params={"companyId": co["companyId"]},
                json={} if method != "GET" else None,
            )
            assert r.status_code == 409, (method, path, r.text)
            assert r.json()["error"]["code"] == "GW_COMPANY_NOT_READY"
            assert r.headers["Cache-Control"] == "no-store"
            count += 1
    assert count == 63
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT count(*) FROM gw.person WHERE workspace_id=:w"),
                {"w": co["companyId"]},
            ).scalar_one()
            == 0
        )


def test_actor_forgery_and_invalid_company_never_fall_back(company_env, monkeypatch):
    monkeypatch.setattr(company, "BUSINESS_READY", False)
    _, co, _, staff = company_env
    for params, body in [
        ({"personId": "1"}, None),
        ({}, {"actingPersonId": 1}),
        ({}, {"acting_person_id": 1}),
    ]:
        r = staff.request(
            "GET" if body is None else "POST",
            "/api/v1/gw/documents",
            params={"companyId": co["companyId"], **params},
            json=body,
        )
        assert r.status_code == 400, r.text
    for value in ["", "invalid", "0", "-1", "2147483648"]:
        assert (
            staff.get("/api/v1/gw/dashboard", params={"companyId": value}).status_code
            == 400
        )


def test_role_and_identity_are_separate_from_hr_admin(company_env):
    engine, co, admin, _ = company_env
    scoped, person = bound(engine, co, admin)
    with company.transaction(context(engine, admin), co["companyId"]) as (c, sc, _):
        assert principal_roles(c, sc) == set()
        assert work_identity(c, sc, scoped.user_id)["employeeCode"] == "HUGH-001"
        with pytest.raises(ApiError) as caught:
            company.principal(c, sc, "SECURITY_ADMIN")
        assert caught.value.status_code == 403
    with engine.begin() as c:
        c.execute(
            text("""INSERT INTO gw.role_grant(workspace_id,generation_id,person_id,role_key,changed_by_user_id,reason)
         VALUES (:w,:g,:p,'SECURITY_ADMIN',:u,'합성 권한 검사')"""),
            {
                "w": scoped.workspace_id,
                "g": scoped.generation_id,
                "p": person,
                "u": scoped.user_id,
            },
        )
    data = admin.get("/api/v1/gw/me", params={"companyId": co["companyId"]}).json()[
        "data"
    ]
    assert data["roles"] == ["SECURITY_ADMIN"]
    assert data["businessReady"] is False


def principal_roles(c, sc):
    return set(company.principal(c, sc)[1])


def test_binding_state_and_unique_active_identity(company_env):
    engine, co, _, staff = company_env
    scoped, person = bound(engine, co, staff, "PENDING")
    p = {
        "w": scoped.workspace_id,
        "g": scoped.generation_id,
        "u": scoped.user_id,
        "p": person,
    }
    with engine.begin() as c:
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text("""INSERT INTO gw.person_identity_binding(workspace_id,generation_id,person_id,user_id,state,requested_by_user_id)
             VALUES (:w,:g,:p,:u,'PENDING',:u)"""),
                p,
            )
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text(
                    "UPDATE gw.person_identity_binding SET state='ACTIVE' WHERE workspace_id=:w"
                ),
                p,
            )
        c.execute(
            text(
                "UPDATE gw.person_identity_binding SET state='CANCELLED',closed_at=clock_timestamp() WHERE workspace_id=:w"
            ),
            p,
        )
        c.execute(
            text("""INSERT INTO gw.person_identity_binding(workspace_id,generation_id,person_id,user_id,state,requested_by_user_id)
             VALUES (:w,:g,:p,:u,'PENDING',:u)"""),
            p,
        )
    with (
        company.transaction(context(engine, staff), co["companyId"]) as (c, sc, _),
        pytest.raises(ApiError),
    ):
        company.principal(c, sc)


def test_revoked_session_is_rechecked_after_context_resolution(company_env):
    engine, co, _, staff = company_env
    stale = context(engine, staff)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u"
            ),
            {"u": stale.user_id},
        )
    with pytest.raises(ApiError) as caught, company.transaction(stale, co["companyId"]):
        pass
    assert caught.value.status_code == 401


def test_account_revoke_while_waiting_does_not_reuse_old_snapshot(
    company_env, monkeypatch
):
    engine, co, _, staff = company_env
    stale = context(engine, staff)
    started = Event()

    def waiting_lock(c, *, exclusive=False):
        started.set()
        lock_accounts(c, exclusive=exclusive)

    monkeypatch.setattr(company, "lock_accounts", waiting_lock)

    def blocked_read():
        try:
            with company.transaction(stale, co["companyId"]):
                return 200
        except ApiError as e:
            return e.status_code

    with ThreadPoolExecutor(1) as pool:
        with engine.begin() as c:
            lock_accounts(c, exclusive=True)
            future = pool.submit(blocked_read)
            assert started.wait(3)
            c.execute(
                text(
                    "UPDATE core.app_user SET status='disabled',disabled_at=clock_timestamp() WHERE id=:u"
                ),
                {"u": stale.user_id},
            )
        assert future.result(timeout=10) == 401


def test_company_copy_and_reset_guard(company_env):
    engine, co, _, staff = company_env
    from datetime import date

    from fs.core.service import reset_generation

    with engine.begin() as c:
        with pytest.raises(RuntimeError):
            copy_module_seed(c, co["companyId"], "gw")
        with pytest.raises(ApiError):
            reset_generation(
                c,
                replace(context(engine, staff), workspace_id=co["companyId"]),
                date(2026, 10, 17),
                "synthetic-reset",
            )


def test_security_tables_never_enter_template_copy(company_env):
    engine, co, _, staff = company_env
    scoped, _ = bound(engine, co, staff)
    with engine.connect() as c:
        copied = _seeded_tables(c, scoped.workspace_id, scoped.generation_id, ("gw",))
        assert not (copied & COMPANY_GW_TABLES)
        assert "gw.person" in copied


def test_receipt_replay_checks_current_identity_before_returning_body(company_env):
    engine, co, _, staff = company_env
    scoped, person = bound(engine, co, staff)
    ctx = context(engine, staff)
    seen = []

    def run(c, sc, p):
        seen.append(p["id"])
        return {"body": "synthetic private result"}, "gw.person", person

    def allow(c, sc, p):
        assert p["id"] == person

    for _ in range(2):
        assert (
            company.action(
                ctx,
                co["companyId"],
                "test.company.receipt",
                "synthetic-key",
                {},
                run,
                authorize=allow,
            )["body"]
            == "synthetic private result"
        )
    assert seen == [person]
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person_identity_binding SET state='SUSPENDED',closed_at=clock_timestamp() WHERE workspace_id=:w"
            ),
            {"w": scoped.workspace_id},
        )
    with pytest.raises(ApiError) as caught:
        company.action(
            ctx,
            co["companyId"],
            "test.company.receipt",
            "synthetic-key",
            {},
            run,
            authorize=allow,
        )
    assert caught.value.status_code == 403


def test_security_fk_role_and_step_document_constraints(company_env):
    engine, co, _, staff = company_env
    scoped, person = bound(engine, co, staff)
    p = {
        "w": scoped.workspace_id,
        "g": scoped.generation_id,
        "u": scoped.user_id,
        "p": person,
    }
    with engine.begin() as c:
        foreign = c.execute(
            text("SELECT id FROM gw.person WHERE workspace_id<>:w LIMIT 1"), p
        ).scalar_one()
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text("""INSERT INTO gw.role_grant(workspace_id,generation_id,person_id,role_key,changed_by_user_id,reason)
             VALUES (:w,:g,:p,'SECURITY_ADMIN',:u,'복합 범위 검사')"""),
                {**p, "p": foreign},
            )
        with pytest.raises(IntegrityError), c.begin_nested():
            c.execute(
                text("""INSERT INTO gw.role_grant(workspace_id,generation_id,person_id,role_key,changed_by_user_id,reason)
             VALUES (:w,:g,:p,'PLATFORM_ADMIN',:u,'잘못된 권한 검사')"""),
                p,
            )
        route = c.execute(
            text(
                "INSERT INTO gw.approval_route(workspace_id,generation_id,code,name) VALUES (:w,:g,'TEST','합성 결재선') RETURNING id"
            ),
            p,
        ).scalar_one()
        docs = []
        for n in (1, 2):
            docs.append(
                c.execute(
                    text("""INSERT INTO gw.approval_document(workspace_id,generation_id,serial,document_no,kind,title,body,drafter_id,drafter_code,drafter_name,drafter_job_role,route_id,route_code,route_name)
            VALUES (:w,:g,:n,:no,'GENERAL','합성 제목','합성 내용',:p,'GW-STAFF','합성 직원','STAFF',:route,'TEST','합성 결재선') RETURNING id"""),
                    {**p, "n": n, "no": f"TEST-{n}", "route": route},
                ).scalar_one()
            )
        step = c.execute(
            text("""INSERT INTO gw.approval_step(workspace_id,generation_id,document_id,seq,person_id,person_code,person_name,person_job_role)
         VALUES (:w,:g,:doc,1,:p,'GW-STAFF','합성 직원','STAFF') RETURNING id"""),
            {**p, "doc": docs[0]},
        ).scalar_one()
        for doc, valid in [(docs[0], True), (docs[1], False)]:
            sql = text("""INSERT INTO gw.step_assignment(workspace_id,generation_id,document_id,step_id,person_id,assignment_seq,reason,assigned_by_user_id)
             VALUES (:w,:g,:doc,:step,:p,1,'합성 단계 범위 검사',:u)""")
            values = {**p, "doc": doc, "step": step}
            if valid:
                c.execute(sql, values)
            else:
                with pytest.raises(IntegrityError), c.begin_nested():
                    c.execute(sql, values)


def test_downgrade_refuses_existing_company_security_history(company_env, monkeypatch):
    engine, co, _, staff = company_env
    bound(engine, co, staff)
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20261017_gw_company_identity.py"
    )
    spec = importlib.util.spec_from_file_location("test_gw_company_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as c:
        monkeypatch.setattr(migration.op, "get_bind", lambda: c)
        with pytest.raises(RuntimeError, match="downgrade"):
            migration.downgrade()
        assert (
            c.execute(
                text("SELECT count(*) FROM gw.person_identity_binding")
            ).scalar_one()
            == 1
        )
