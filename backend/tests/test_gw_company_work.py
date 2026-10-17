"""03: 회사 준비 API와 비공개 업무 서비스의 실제 PostgreSQL 결과 검증."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from fs.common.errors import ApiError
from fs.gw import company_work as work
from sqlalchemy import text
from test_gw_company import context
from test_hr_work import company_env  # noqa: F401


def api(client, co, path, body=None, *, method="POST", key=None):
    return client.request(
        method,
        "/api/v1/gw/" + path,
        params={"companyId": co["companyId"]},
        json=body,
        headers={"X-CSRF-Token": client.csrf, "Idempotency-Key": key or str(uuid4())},
    )


def ok(response):
    assert response.status_code == 200, response.text
    return response.json()["data"]


def initialize(env):
    _, co, admin, _ = env
    data = ok(
        api(
            admin,
            co,
            "company-setup",
            {"employeeCode": "HUGH-001", "reason": "합성 회사 최초 설정"},
        )
    )
    return int(data["personId"])


def import_staff(env):
    engine, co, admin, staff = env
    preview = ok(api(admin, co, "company-hr-preview", method="GET"))
    ok(
        api(
            admin,
            co,
            "company-hr-import",
            {
                "previewDigest": preview["digest"],
                "employeeCodes": ["HUGH-002"],
                "reason": "합성 직원 명시적 가져오기",
            },
        )
    )
    with engine.connect() as c:
        person = c.execute(
            text(
                "SELECT id FROM gw.person WHERE workspace_id=:w AND hr_employee_code='HUGH-002'"
            ),
            {"w": co["companyId"]},
        ).scalar_one()
    return person, context(engine, staff).user_id


def connect_staff(env):
    _, co, admin, staff = env
    p, user = import_staff(env)
    binding = ok(
        api(
            admin,
            co,
            "identity-bindings",
            {
                "personId": str(p),
                "userId": str(user),
                "reason": "합성 직원 본인 연결 요청",
            },
        )
    )
    assert binding["state"] == "PENDING"
    ok(
        api(
            staff,
            co,
            "me/binding/accept",
            {"bindingId": binding["id"], "expectedVersion": 1},
        )
    )
    return p, binding["id"]


def call_work(env, client, kind, id, operation, values, key=None):
    engine, co, _, _ = env
    return work.mutate(
        context(engine, client),
        co["companyId"],
        kind,
        id,
        operation,
        values,
        key or str(uuid4()),
    )


def read_work(env, client, kind, id=None, **kw):
    engine, co, _, _ = env
    return work.read(context(engine, client), co["companyId"], kind, id, **kw)


def route(env, person):
    return call_work(
        env,
        env[2],
        "routes",
        None,
        "create",
        {
            "code": "CO-ROUTE",
            "name": "합성 결재선",
            "steps": [{"person_id": person, "seq": 1, "participant_role": "APPROVER"}],
        },
    )


def document(env, person):
    r = route(env, person)
    return call_work(
        env,
        env[2],
        "documents",
        None,
        "create",
        {
            "route_id": int(r["id"]),
            "kind": "GENERAL",
            "title": "비공개 합성 기안",
            "body": "검색에서 숨길 합성 원문",
        },
    )


def test_setup_atomic_owner_hr_and_idempotency(company_env):
    engine, co, admin, staff = company_env
    body = {"employeeCode": "HUGH-001", "reason": "합성 최초 설정"}
    assert api(staff, co, "company-setup", body).status_code == 403
    assert (
        api(
            admin, co, "company-setup", {**body, "employeeCode": "HUGH-002"}
        ).status_code
        == 400
    )
    key = str(uuid4())
    first = ok(api(admin, co, "company-setup", body, key=key))
    assert ok(api(admin, co, "company-setup", body, key=key)) == first
    assert api(admin, co, "company-setup", body).status_code == 409
    me = ok(api(admin, co, "me", method="GET"))
    assert me["bindingStatus"] == "ACTIVE" and me["businessReady"] is False
    assert len(me["roles"]) == 5 and "AUDITOR" not in me["roles"]
    with engine.connect() as c:
        assert (
            c.execute(
                text(
                    "SELECT count(*) FROM gw.person_identity_binding WHERE workspace_id=:w"
                ),
                {"w": co["companyId"]},
            ).scalar_one()
            == 1
        )
        assert (
            c.execute(
                text("SELECT count(*) FROM gw.role_grant WHERE workspace_id=:w"),
                {"w": co["companyId"]},
            ).scalar_one()
            == 5
        )


def test_binding_self_consent_cancel_recreate_and_replay(company_env):
    _, co, admin, staff = company_env
    initialize(company_env)
    p, user = import_staff(company_env)
    body = {"personId": str(p), "userId": str(user), "reason": "합성 연결 요청"}
    b = ok(api(admin, co, "identity-bindings", body))
    assert (
        api(
            admin, co, "me/binding/accept", {"bindingId": b["id"], "expectedVersion": 1}
        ).status_code
        == 403
    )
    assert (
        ok(api(staff, co, "me/binding", method="GET"))["hrEmployeeCode"] == "HUGH-002"
    )
    assert api(staff, co, "identity-bindings", method="GET").status_code == 403
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{b['id']}/cancel",
            {"expectedVersion": 1, "reason": "미수락 요청 취소"},
        )
    )
    assert (
        api(
            staff, co, "me/binding/accept", {"bindingId": b["id"], "expectedVersion": 2}
        ).status_code
        == 403
    )
    b = ok(api(admin, co, "identity-bindings", body))
    key = str(uuid4())
    accept = {"bindingId": b["id"], "expectedVersion": 1}
    first = ok(api(staff, co, "me/binding/accept", accept, key=key))
    assert ok(api(staff, co, "me/binding/accept", accept, key=key)) == first
    assert api(admin, co, "identity-bindings", body).status_code == 409
    suspended = ok(
        api(
            admin,
            co,
            f"identity-bindings/{b['id']}/suspend",
            {"expectedVersion": 2, "reason": "합성 연결 정지"},
        )
    )
    assert api(staff, co, "me/binding/accept", accept, key=key).status_code == 403
    assert suspended["state"] == "SUSPENDED"
    assert (
        api(
            admin,
            co,
            f"identity-bindings/{b['id']}/cancel",
            {"expectedVersion": 3, "reason": "잘못된 연결 취소"},
        ).status_code
        == 409
    )
    resumed = ok(
        api(
            admin,
            co,
            f"identity-bindings/{b['id']}/resume",
            {"expectedVersion": 3, "reason": "동일 계정 복귀"},
        )
    )
    assert resumed["state"] == "ACTIVE" and resumed["userId"] == str(user)


def test_roles_last_security_admin_cas_and_revoked_receipt(company_env):
    _, co, admin, staff = company_env
    own = initialize(company_env)
    target, _ = connect_staff(company_env)
    roles = ok(api(admin, co, f"people/{own}/roles", method="GET"))
    assert (
        api(
            admin,
            co,
            f"people/{own}/roles",
            {
                "expectedVersion": roles["version"],
                "roles": [],
                "reason": "마지막 권한 제거",
            },
            method="PATCH",
        ).status_code
        == 409
    )
    mine = ok(api(admin, co, "me/binding", method="GET"))
    assert (
        api(
            admin,
            co,
            f"identity-bindings/{mine['id']}/suspend",
            {"expectedVersion": mine["version"], "reason": "마지막 관리자 정지"},
        ).status_code
        == 409
    )
    current = ok(api(admin, co, f"people/{target}/roles", method="GET"))
    grant = {
        "expectedVersion": current["version"],
        "roles": ["SECURITY_ADMIN"],
        "reason": "합성 관리자 추가",
    }
    ok(api(admin, co, f"people/{target}/roles", grant, method="PATCH"))
    assert (
        api(admin, co, f"people/{target}/roles", grant, method="PATCH").status_code
        == 409
    )
    key = str(uuid4())
    remove = {
        "expectedVersion": roles["version"],
        "roles": [],
        "reason": "합성 역할 회수",
    }
    ok(api(admin, co, f"people/{own}/roles", remove, method="PATCH", key=key))
    assert (
        api(
            admin, co, f"people/{own}/roles", remove, method="PATCH", key=key
        ).status_code
        == 403
    )
    assert api(admin, co, "security-events", method="GET").status_code == 403
    assert ok(api(staff, co, "identity-bindings", method="GET"))["total"] == 2
    events = ok(api(staff, co, "security-events", method="GET"))
    assert events["total"] >= 5 and all("summary" not in r for r in events["items"])


def test_document_draft_private_submit_approve_identity(company_env):
    _, _, admin, staff = company_env
    initialize(company_env)
    target, _ = connect_staff(company_env)
    doc = document(company_env, target)
    assert doc["authMode"] == "IDENTITY"
    with pytest.raises(ApiError) as e:
        read_work(company_env, staff, "documents", int(doc["id"]))
    assert e.value.status_code == 404
    assert read_work(company_env, staff, "documents", search="합성")["total"] == 0
    submitted = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    assert read_work(company_env, staff, "documents")["total"] == 1
    viewed = read_work(company_env, staff, "documents", int(doc["id"]))
    assert len(viewed["actionSteps"]) == 1
    saved = call_work(
        company_env,
        staff,
        "documents",
        int(doc["id"]),
        "approve",
        {"expected_version": submitted["version"]},
    )
    assert saved["status"] == "APPROVED"
    assert saved["events"][-1]["actingPersonId"] == str(target)
    assert saved["events"][-1]["actorKind"] == "MEMBER"


def test_post_explicit_role_no_board_admin_escalation(company_env):
    engine, co, admin, staff = company_env
    initialize(company_env)
    target, _ = connect_staff(company_env)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person SET job_role='BOARD_ADMIN' WHERE workspace_id=:w AND id=:p"
            ),
            {"w": co["companyId"], "p": target},
        )
    with pytest.raises(ApiError) as e:
        call_work(
            company_env,
            staff,
            "posts",
            None,
            "create",
            {"board_kind": "NOTICE", "title": "권한 없는 공지", "body": "합성"},
        )
    assert e.value.status_code == 403
    doc = call_work(
        company_env,
        admin,
        "posts",
        None,
        "create",
        {"board_kind": "NOTICE", "title": "합성 공지", "body": "합성 공지 본문"},
    )
    assert read_work(company_env, staff, "posts")["total"] == 0
    call_work(
        company_env,
        admin,
        "posts",
        int(doc["id"]),
        "publish",
        {"expected_version": doc["version"]},
    )
    assert read_work(company_env, staff, "posts")["total"] == 1
    with pytest.raises(ApiError):
        call_work(
            company_env,
            staff,
            "posts",
            int(doc["id"]),
            "edit",
            {"expected_version": 2, "title": "가로채기", "body": "합성"},
        )


def test_strict_csrf_company_and_actor_inputs(company_env):
    _, co, admin, _ = company_env
    assert (
        admin.post(
            "/api/v1/gw/company-setup",
            params={"companyId": co["companyId"]},
            json={"employeeCode": "HUGH-001", "reason": "합성"},
        ).status_code
        == 403
    )
    assert (
        api(
            admin,
            co,
            "company-setup",
            {"employeeCode": "HUGH-001", "reason": "합성", "actingPersonId": "1"},
        ).status_code
        == 400
    )
    assert (
        admin.get(
            "/api/v1/gw/company-setup",
            params={"companyId": co["companyId"], "personId": "1"},
        ).status_code
        == 400
    )
    assert (
        api(
            admin, co, "company-setup", {"employeeCode": "HUGH-001", "reason": "  "}
        ).status_code
        == 400
    )


@pytest.fixture
def third(company_env):
    from fastapi.testclient import TestClient
    from fs.main import create_app
    from test_hr_users import manage

    _, co, admin, _ = company_env
    secret = "Synthetic-third-" + str(uuid4())
    result = manage(
        admin,
        co,
        body={
            "loginId": "company-third",
            "password": secret,
            "name": "세번째 합성 직원",
            "employeeCode": "HUGH-003",
            "annualDays": 15,
            "role": "STAFF",
        },
    )
    assert result.status_code == 200, result.text
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/core/sessions",
            json={"loginId": "company-third", "password": secret},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert response.status_code == 201, response.text
        client.csrf = response.json()["data"]["csrfToken"]
        yield client


def connect_third(env, client):
    engine, co, admin, _ = env
    preview = ok(api(admin, co, "company-hr-preview", method="GET"))
    ok(
        api(
            admin,
            co,
            "company-hr-import",
            {
                "previewDigest": preview["digest"],
                "employeeCodes": ["HUGH-003"],
                "reason": "합성 직원 명시적 가져오기",
            },
        )
    )
    with engine.connect() as c:
        person = c.execute(
            text(
                "SELECT id FROM gw.person WHERE workspace_id=:w AND hr_employee_code='HUGH-003'"
            ),
            {"w": co["companyId"]},
        ).scalar_one()
    b = ok(
        api(
            admin,
            co,
            "identity-bindings",
            {
                "personId": str(person),
                "userId": str(context(engine, client).user_id),
                "reason": "세번째 합성 직원 연결",
            },
        )
    )
    ok(
        api(
            client,
            co,
            "me/binding/accept",
            {"bindingId": b["id"], "expectedVersion": 1},
        )
    )
    return person, b["id"]


def test_reader_is_read_only_revoke_and_no_admin_private_bypass(company_env, third):
    _, co, admin, staff = company_env
    own = initialize(company_env)
    target, _ = connect_staff(company_env)
    reader, _ = connect_third(company_env, third)
    # 보안 관리자도 다른 직원의 초안은 열 수 없다.
    r = route(company_env, own)
    private = call_work(
        company_env,
        staff,
        "documents",
        None,
        "create",
        {
            "route_id": int(r["id"]),
            "kind": "GENERAL",
            "title": "직원만 보는 초안",
            "body": "검색 숨김",
        },
    )
    with pytest.raises(ApiError) as e:
        read_work(company_env, admin, "documents", int(private["id"]))
    assert e.value.status_code == 404
    assert read_work(company_env, admin, "documents", search="검색 숨김")["total"] == 0
    # 같은 회사라도 제삼자는 명시적 권한을 받기 전에는 접근할 수 없다.
    doc = call_work(
        company_env,
        staff,
        "documents",
        int(private["id"]),
        "submit",
        {"expected_version": private["version"]},
    )
    with pytest.raises(ApiError):
        read_work(company_env, third, "documents", int(doc["id"]))
    grant = ok(
        api(
            staff,
            co,
            f"documents/{doc['id']}/readers",
            {
                "personId": str(reader),
                "expectedVersion": doc["version"],
                "reason": "합성 열람 권한",
            },
        )
    )
    assert (
        read_work(company_env, third, "documents", int(doc["id"]))["actionSteps"] == []
    )
    with pytest.raises(ApiError) as e:
        call_work(
            company_env,
            third,
            "documents",
            int(doc["id"]),
            "approve",
            {"expected_version": grant["version"]},
        )
    assert e.value.status_code == 409
    assert (
        api(admin, co, f"documents/{doc['id']}/readers", method="GET").status_code
        == 404
    )
    ok(
        api(
            staff,
            co,
            f"documents/{doc['id']}/readers/{reader}",
            {
                "isActive": False,
                "expectedVersion": grant["version"],
                "reason": "합성 열람 권한 회수",
            },
            method="PATCH",
        )
    )
    with pytest.raises(ApiError):
        read_work(company_env, third, "documents", int(doc["id"]))
    assert read_work(company_env, third, "documents", search="검색 숨김")["total"] == 0
    assert target != own


def test_reassignment_preserves_original_step_and_removes_old_reader(
    company_env, third
):
    engine, co, admin, staff = company_env
    initialize(company_env)
    original, binding = connect_staff(company_env)
    replacement, _ = connect_third(company_env, third)
    doc = document(company_env, original)
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    step = doc["steps"][0]
    reassign = {
        "expectedVersion": doc["version"],
        "stepId": step["id"],
        "personId": str(replacement),
        "reason": "합성 비활성 담당 재배정",
    }
    assert (
        api(admin, co, f"documents/{doc['id']}/reassign-step", reassign).status_code
        == 409
    )
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding}/suspend",
            {"expectedVersion": 2, "reason": "합성 담당자 정지"},
        )
    )
    blocked = ok(api(admin, co, "blocked-assignments", method="GET"))
    assert blocked["total"] == 1
    assert not {"title", "body", "amount"} & blocked["items"][0].keys()
    assert blocked["items"][0]["documentVersion"] == doc["version"]
    new = ok(api(admin, co, f"documents/{doc['id']}/reassign-step", reassign))
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding}/resume",
            {"expectedVersion": 3, "reason": "합성 담당자 복귀"},
        )
    )
    with pytest.raises(ApiError) as e:
        read_work(company_env, staff, "documents", int(doc["id"]))
    assert e.value.status_code == 404
    assert read_work(company_env, staff, "documents")["total"] == 0
    saved = call_work(
        company_env,
        third,
        "documents",
        int(doc["id"]),
        "approve",
        {"expected_version": new["version"]},
    )
    assert saved["status"] == "APPROVED"
    assert saved["steps"][0]["originalPersonId"] == str(original)
    assert saved["steps"][0]["personId"] == str(replacement)
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT person_id FROM gw.approval_step WHERE id=:id"),
                {"id": int(step["id"])},
            ).scalar_one()
            == original
        )
    assert ok(api(admin, co, "blocked-assignments", method="GET"))["total"] == 0


def test_suspension_blocks_success_receipt_and_reassignment_self(company_env, third):
    _, co, admin, _ = company_env
    own = initialize(company_env)
    original, binding = connect_staff(company_env)
    _, third_binding = connect_third(company_env, third)
    key = str(uuid4())
    values = {
        "board_kind": "FREE",
        "title": "합성 개인 게시",
        "body": "권한 회수 후 재노출 방지",
    }
    created = call_work(company_env, third, "posts", None, "create", values, key)
    assert (
        call_work(company_env, third, "posts", None, "create", values, key) == created
    )
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{third_binding}/suspend",
            {"expectedVersion": 2, "reason": "합성 재시도 차단"},
        )
    )
    with pytest.raises(ApiError) as e:
        call_work(company_env, third, "posts", None, "create", values, key)
    assert e.value.status_code == 403
    doc = document(company_env, original)
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding}/suspend",
            {"expectedVersion": 2, "reason": "합성 재배정 준비"},
        )
    )
    assert (
        api(
            admin,
            co,
            f"documents/{doc['id']}/reassign-step",
            {
                "expectedVersion": doc["version"],
                "stepId": doc["steps"][0]["id"],
                "personId": str(own),
                "reason": "본인 재배정 거부",
            },
        ).status_code
        == 400
    )


def test_delegated_current_access_expires_and_actual_actor_preserved(
    company_env, third
):
    from datetime import UTC, datetime, timedelta

    from fs.gw import company
    from fs.gw import service as gw

    engine, co, admin, staff = company_env
    initialize(company_env)
    original, _ = connect_staff(company_env)
    delegate, _ = connect_third(company_env, third)
    doc = document(company_env, original)
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    current = datetime.now(UTC)
    with company.transaction(context(engine, admin), co["companyId"], write=True) as (
        c,
        ctx,
        _,
    ):
        grant = gw.insert(
            c,
            ctx,
            "delegation",
            {
                "delegator_person_id": original,
                "delegate_person_id": delegate,
                "starts_at": current - timedelta(hours=1),
                "ends_at": current + timedelta(hours=1),
                "reason": "합성 위임",
            },
        )
    assert read_work(company_env, third, "documents")["total"] == 1
    assert (
        len(read_work(company_env, third, "documents", int(doc["id"]))["actionSteps"])
        == 1
    )
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.delegation SET revoked_at=clock_timestamp() WHERE id=:id"),
            {"id": grant},
        )
    assert read_work(company_env, third, "documents")["total"] == 0
    with pytest.raises(ApiError) as e:
        read_work(company_env, third, "documents", int(doc["id"]))
    assert e.value.status_code == 404
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.delegation SET revoked_at=NULL WHERE id=:id"), {"id": grant}
        )
    saved = call_work(
        company_env,
        third,
        "documents",
        int(doc["id"]),
        "approve",
        {"expected_version": doc["version"]},
    )
    event = next(e for e in saved["events"] if e["eventType"] == "APPROVED")
    assert event["actingPersonId"] == str(delegate)
    assert event["onBehalfOfPersonId"] == str(original)
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.delegation SET revoked_at=clock_timestamp() WHERE id=:id"),
            {"id": grant},
        )
    # 실제 처리자의 이력 접근은 위임 회수 후에도 보존된다.
    assert read_work(company_env, third, "documents")["total"] == 1
    assert staff is not None


def test_successor_draft_hidden_and_company_source_closed(company_env):
    _, _, admin, staff = company_env
    initialize(company_env)
    target, _ = connect_staff(company_env)
    doc = document(company_env, target)
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    rejected = call_work(
        company_env,
        staff,
        "documents",
        int(doc["id"]),
        "reject",
        {"expected_version": doc["version"], "reason": "합성 반려"},
    )
    new = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "resubmit",
        {"expected_version": rejected["version"]},
    )
    assert new["status"] == "DRAFT"
    assert (
        read_work(company_env, staff, "documents", int(doc["id"]))["successor"] is None
    )
    with pytest.raises(ApiError) as e:
        read_work(company_env, staff, "documents", int(new["id"]))
    assert e.value.status_code == 404
    with pytest.raises(ApiError) as e:
        call_work(
            company_env,
            admin,
            "documents",
            None,
            "create",
            {
                "kind": "ERP_PURCHASE",
                "route_id": int(doc["routeId"]),
                "title": "차단",
                "body": "합성",
            },
        )
    assert e.value.status_code == 400


def test_concurrent_last_admin_removals_serialize(company_env):
    from concurrent.futures import ThreadPoolExecutor

    _, co, admin, staff = company_env
    own = initialize(company_env)
    target, _ = connect_staff(company_env)
    own_roles = ok(api(admin, co, f"people/{own}/roles", method="GET"))
    target_roles = ok(api(admin, co, f"people/{target}/roles", method="GET"))
    grant = ok(
        api(
            admin,
            co,
            f"people/{target}/roles",
            {
                "expectedVersion": target_roles["version"],
                "roles": ["SECURITY_ADMIN"],
                "reason": "합성 보안 관리자 추가",
            },
            method="PATCH",
        )
    )

    def remove(client, person, version):
        return api(
            client,
            co,
            f"people/{person}/roles",
            {
                "expectedVersion": version,
                "roles": [],
                "reason": "동시 마지막 권한 제거",
            },
            method="PATCH",
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(remove, admin, own, own_roles["version"]),
            pool.submit(remove, staff, target, grant["version"]),
        ]
        assert sorted(f.result(timeout=20) for f in futures) == [200, 409]


def test_org_post_current_membership_and_author_access(company_env):
    engine, co, admin, staff = company_env
    own = initialize(company_env)
    target, _ = connect_staff(company_env)
    with engine.begin() as c:
        org = c.execute(
            text("SELECT organization_unit_id FROM gw.person WHERE id=:id"), {"id": own}
        ).scalar_one()
        # 다른 직접 소속이면 공지의 내용·검색·건수 모두 감춘다.
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=NULL WHERE id=:id"),
            {"id": target},
        )
    post = call_work(
        company_env,
        admin,
        "posts",
        None,
        "create",
        {
            "board_kind": "NOTICE",
            "visibility": "ORG",
            "audience_org_id": org,
            "title": "조직 공지",
            "body": "조직 합성 내용",
        },
    )
    post = call_work(
        company_env,
        admin,
        "posts",
        int(post["id"]),
        "publish",
        {"expected_version": post["version"]},
    )
    assert read_work(company_env, staff, "posts", search="조직 합성")["total"] == 0
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:id"),
            {"id": target, "org": org},
        )
    assert read_work(company_env, staff, "posts")["total"] == 1
    with engine.begin() as c:
        c.execute(
            text("UPDATE gw.person SET organization_unit_id=NULL WHERE id=:id"),
            {"id": own},
        )
    assert (
        read_work(company_env, admin, "posts", int(post["id"]))["title"] == "조직 공지"
    )
    withdrawn = call_work(
        company_env,
        admin,
        "posts",
        int(post["id"]),
        "withdraw",
        {"expected_version": post["version"], "reason": "합성 공지 철회"},
    )
    assert withdrawn["status"] == "WITHDRAWN"
    assert read_work(company_env, staff, "posts")["total"] == 0
    assert co["companyId"] > 0


def test_setup_concurrent_retry_and_binding_validation(company_env):
    from concurrent.futures import ThreadPoolExecutor

    from fs.gw import company_identity as identities

    engine, co, admin, staff = company_env
    ctx = context(engine, admin)
    key = str(uuid4())
    values = {"employee_code": "HUGH-001", "reason": "동시 합성 최초 설정"}
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(identities.setup, ctx, co["companyId"], values, key)
            for _ in range(2)
        ]
        assert futures[0].result(timeout=20) == futures[1].result(timeout=20)
    with pytest.raises(ApiError) as e:
        identities.setup(ctx, co["companyId"], {**values, "reason": "본문 변경"}, key)
    assert e.value.status_code == 422
    target, user = import_staff(company_env)
    own = int(ok(api(admin, co, "me", method="GET"))["person"]["id"])
    assert (
        api(
            admin,
            co,
            "identity-bindings",
            {
                "personId": str(own),
                "userId": str(user),
                "reason": "다른 사번 계정 거부",
            },
        ).status_code
        == 400
    )
    assert (
        api(
            admin,
            co,
            "identity-bindings",
            {
                "personId": str(target + 100000),
                "userId": str(user),
                "reason": "범위 없는 직원 거부",
            },
        ).status_code
        == 404
    )
    binding = ok(
        api(
            admin,
            co,
            "identity-bindings",
            {"personId": str(target), "userId": str(user), "reason": "합성 확인 요청"},
        )
    )
    assert (
        api(
            staff,
            co,
            "me/binding/accept",
            {"bindingId": binding["id"], "expectedVersion": 2},
        ).status_code
        == 409
    )
    assert (
        api(
            admin,
            co,
            f"people/{target}/roles",
            {
                "expectedVersion": 1,
                "roles": ["SECURITY_ADMIN"],
                "reason": "미수락 역할 부여 거부",
            },
            method="PATCH",
        ).status_code
        == 400
    )
    assert (
        api(
            admin,
            co,
            f"people/{own}/roles",
            {
                "expectedVersion": 1,
                "roles": ["BOARD_ADMIN"],
                "reason": "알 수 없는 권한 거부",
            },
            method="PATCH",
        ).status_code
        == 400
    )


def test_waiting_read_rechecks_reader_revocation_after_lock(company_env, third):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from time import monotonic, sleep

    from fs.gw import company

    engine, co, admin, staff = company_env
    initialize(company_env)
    target, _ = connect_staff(company_env)
    reader, _ = connect_third(company_env, third)
    doc = document(company_env, target)
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/readers",
            {
                "personId": str(reader),
                "expectedVersion": doc["version"],
                "reason": "합성 대기 전 열람",
            },
        )
    )
    third_ctx = context(engine, third)
    admin_ctx = context(engine, admin)
    started = Event()

    def pending():
        started.set()
        try:
            work.read(third_ctx, co["companyId"], "documents", int(doc["id"]))
        except ApiError as error:
            return error.status_code
        return 200

    with ThreadPoolExecutor(max_workers=1) as pool:
        with company.transaction(admin_ctx, co["companyId"], write=True) as (c, ctx, _):
            future = pool.submit(pending)
            assert started.wait(timeout=10)
            deadline = monotonic() + 10
            while True:
                with engine.connect() as probe:
                    waiting = probe.execute(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE locktype='advisory' AND classid=16 AND objid=:company AND objsubid=2 AND NOT granted)"
                        ),
                        {"company": co["companyId"]},
                    ).scalar_one()
                if waiting:
                    break
                assert monotonic() < deadline, (
                    "조회가 회사 잠금에서 대기하지 않았습니다."
                )
                sleep(0.01)
            c.execute(
                text(
                    "UPDATE gw.document_reader SET is_active=false WHERE workspace_id=:w AND generation_id=:g AND document_id=:doc AND person_id=:person"
                ),
                {
                    "w": ctx.workspace_id,
                    "g": ctx.generation_id,
                    "doc": int(doc["id"]),
                    "person": reader,
                },
            )
        assert future.result(timeout=20) == 404
    assert staff is not None


def test_company_parallel_consent_reference_and_authority(company_env, third):
    from zoneinfo import ZoneInfo

    from fs.gw import company
    from fs.gw import service as gw

    engine, co, admin, staff = company_env
    initialize(company_env)
    approver, _ = connect_staff(company_env)
    other, _ = connect_third(company_env, third)
    for role in ("CONSENT", "REFERENCE"):
        route = call_work(
            company_env,
            admin,
            "routes",
            None,
            "create",
            {
                "code": "CO-" + role,
                "name": "합성 병렬 " + role,
                "steps": [
                    {"person_id": approver, "seq": 1, "participant_role": "APPROVER"},
                    {"person_id": other, "seq": 1, "participant_role": role},
                ],
            },
        )
        draft = call_work(
            company_env,
            admin,
            "documents",
            None,
            "create",
            {
                "route_id": int(route["id"]),
                "kind": "GENERAL",
                "title": "합성 병렬 " + role,
                "body": "합성 본문",
            },
        )
        doc = call_work(
            company_env,
            admin,
            "documents",
            int(draft["id"]),
            "submit",
            {"expected_version": draft["version"]},
        )
        # 참조는 먼저 확인하며, 합의는 승인 뒤에도 대기 상태를 유지한다.
        first_client, first_action = (
            (third, "reference") if role == "REFERENCE" else (staff, "approve")
        )
        second_client, second_action = (
            (staff, "approve") if role == "REFERENCE" else (third, "consent")
        )
        decided = call_work(
            company_env,
            first_client,
            "documents",
            int(doc["id"]),
            first_action,
            {"expected_version": doc["version"], "reason": "합성 참여 처리"},
        )
        assert decided["status"] == "IN_REVIEW"
        saved = call_work(
            company_env,
            second_client,
            "documents",
            int(doc["id"]),
            second_action,
            {"expected_version": decided["version"]},
        )
        assert saved["status"] == "APPROVED"
        assert {
            e["actingPersonId"]
            for e in saved["events"]
            if e["eventType"] in {"APPROVED", "CONSENTED"}
        } == {str(approver), str(other)}
    route = call_work(
        company_env,
        admin,
        "routes",
        None,
        "create",
        {
            "code": "CO-AUTHORITY",
            "name": "합성 전결",
            "steps": [
                {"person_id": approver, "seq": 1, "participant_role": "APPROVER"},
                {"person_id": other, "seq": 2, "participant_role": "APPROVER"},
            ],
        },
    )
    with company.transaction(context(engine, admin), co["companyId"], write=True) as (
        c,
        ctx,
        _,
    ):
        gw.insert(
            c,
            ctx,
            "authority_rule",
            {
                "code": "CO-LIMIT",
                "document_kind": "GENERAL",
                "currency": "KRW",
                "amount_from": 0,
                "amount_to": 1000,
                "final_seq": 1,
                "effective_from": gw.now(c)
                .astimezone(ZoneInfo("Asia/Seoul"))
                .strftime("%Y-%m"),
            },
        )
    draft = call_work(
        company_env,
        admin,
        "documents",
        None,
        "create",
        {
            "route_id": int(route["id"]),
            "kind": "GENERAL",
            "title": "합성 전결 검증",
            "body": "가정 금액",
            "amount": "100",
            "currency": "KRW",
        },
    )
    doc = call_work(
        company_env,
        admin,
        "documents",
        int(draft["id"]),
        "submit",
        {"expected_version": draft["version"]},
    )
    assert doc["steps"][1]["status"] == "SKIPPED"
    assert doc["authorityRuleId"] is not None
    with pytest.raises(ApiError) as e:
        read_work(company_env, third, "documents", int(doc["id"]))
    assert e.value.status_code == 404
    saved = call_work(
        company_env,
        staff,
        "documents",
        int(doc["id"]),
        "approve",
        {"expected_version": doc["version"]},
    )
    assert saved["status"] == "APPROVED"
