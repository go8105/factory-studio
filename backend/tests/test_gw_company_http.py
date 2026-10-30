"""04 회사 GW HTTP 라우트·협업·권한 회수 검증. 합성 계정/격리 DB 전용."""

# ruff: noqa: F811
import re
from uuid import uuid4

import pytest
from test_gw_company_work import (
    api,
    connect_staff,
    connect_third,
    initialize,
    third,  # noqa: F401
)
from test_hr_work import company_env  # noqa: F401

from fs.gw import company
from fs.gw.router import router


def ok(response):
    assert response.status_code in {200, 201}, response.text
    return response.json()["data"]


@pytest.fixture(autouse=True)
def ready(monkeypatch):
    monkeypatch.setattr(company, "BUSINESS_READY", True)


def setup(env):
    own = initialize(env)
    target, _ = connect_staff(env)
    return own, target


def create_doc(env):
    _, co, admin, _ = env
    own, target = setup(env)
    route = ok(
        api(
            admin,
            co,
            "routes",
            {
                "code": "HTTP-ROUTE",
                "name": "회사 결재선",
                "steps": [
                    {"personId": str(target), "seq": 1, "participantRole": "APPROVER"}
                ],
            },
        )
    )
    doc = ok(
        api(
            admin,
            co,
            "documents",
            {
                "routeId": route["id"],
                "kind": "GENERAL",
                "title": "회사 HTTP 기안",
                "body": "비공개 본문",
            },
        )
    )
    return own, target, doc


def test_company_document_api_has_no_actor_selector(company_env):
    _, co, admin, staff = company_env
    _, _, doc = create_doc(company_env)
    assert doc["availableActions"] == ["edit", "select-route", "submit"]
    assert api(staff, co, "documents/" + doc["id"], method="GET").status_code == 404
    page = ok(api(staff, co, "documents", method="GET"))
    assert page["total"] == 0 and page["rows"] == []
    submitted = ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )
    page = staff.get(
        "/api/v1/gw/documents", params={"companyId": co["companyId"], "box": "pending"}
    )
    assert ok(page)["total"] == 1
    saved = ok(
        api(
            staff,
            co,
            f"documents/{doc['id']}/approve",
            {"expectedVersion": submitted["version"]},
        )
    )
    assert saved["status"] == "APPROVED"
    assert ok(api(staff, co, "notifications", method="GET"))
    for body in [
        {"expectedVersion": submitted["version"], "actingPersonId": saved["drafterId"]},
        {
            "expectedVersion": submitted["version"],
            "acting_person_id": saved["drafterId"],
        },
    ]:
        assert api(staff, co, f"documents/{doc['id']}/approve", body).status_code == 400


def test_all_63_routes_authenticate_company_before_business(company_env):
    _, co, _, staff = company_env
    for route in router.routes:
        path = re.sub(r"\{kind\}", "PURCHASE_INVOICE", route.path)
        path = re.sub(r"\{[^}]+\}", "1", path)
        for method in route.methods:
            result = staff.request(
                method,
                "/api/v1/gw" + path,
                params={"companyId": co["companyId"]},
                json={} if method != "GET" else None,
            )
            assert result.status_code in {400, 403, 409}, (method, path, result.text)
            assert result.headers["Cache-Control"] == "no-store"


def test_comments_notifications_follow_current_parent_acl(company_env):
    _, co, admin, staff = company_env
    _, _, doc = create_doc(company_env)
    doc = ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )
    comment = ok(
        api(
            staff,
            co,
            "comments",
            {"targetKind": "DOCUMENT", "targetId": doc["id"], "body": "회사 합성 댓글"},
        )
    )
    assert comment["authorName"]
    assert (
        api(
            admin,
            co,
            "comments/" + comment["id"],
            {"expectedVersion": comment["version"], "body": "타인 댓글 수정"},
            method="PATCH",
        ).status_code
        == 404
    )
    assert (
        api(
            admin,
            co,
            "comments/" + comment["id"] + "/delete",
            {"expectedVersion": comment["version"]},
        ).status_code
        == 404
    )
    assert len(ok(api(admin, co, "notifications", method="GET"))) == 1


def test_chat_leave_denies_message_receipt_replay(company_env):
    _, co, admin, staff = company_env
    _, target = setup(company_env)
    channel = ok(
        api(
            admin,
            co,
            "channels",
            {
                "name": "회사 합성 채팅",
                "channelKind": "DIRECT",
                "memberIds": [str(target)],
            },
        )
    )
    body = {"body": "회수할 합성 메시지", "clientKey": str(uuid4())}
    key = str(uuid4())
    message = ok(api(staff, co, f"channels/{channel['id']}/messages", body, key=key))
    assert message["seq"] == 1
    assert (
        ok(api(admin, co, f"channels/{channel['id']}/messages", method="GET"))[
            "messages"
        ][0]["body"]
        == body["body"]
    )
    ok(api(staff, co, f"channels/{channel['id']}/leave", {}))
    assert (
        api(staff, co, f"channels/{channel['id']}/messages", body, key=key).status_code
        == 404
    )
    assert (
        api(staff, co, f"channels/{channel['id']}/messages", method="GET").status_code
        == 404
    )


def test_calendar_owner_attendee_and_current_scope(company_env):
    _, co, admin, staff = company_env
    _, target = setup(company_env)
    event = ok(
        api(
            admin,
            co,
            "calendar",
            {
                "title": "회사 일정",
                "scope": "PERSONAL",
                "startsAt": "2026-10-19T09:00:00+09:00",
                "endsAt": "2026-10-19T10:00:00+09:00",
                "attendeeIds": [str(target)],
            },
        )
    )
    # Calendar edit replaces the event; omitted optional fields use schema defaults.
    event = ok(
        api(
            admin,
            co,
            f"calendar/{event['id']}",
            {
                "title": "회사 일정 수정",
                "scope": "PERSONAL",
                "startsAt": "2026-10-19T09:00:00+09:00",
                "endsAt": "2026-10-19T10:00:00+09:00",
                "attendeeIds": [str(target)],
                "expectedVersion": event["version"],
            },
            method="PATCH",
        )
    )
    assert event["allDay"] is False and event["location"] is None
    assert (
        api(
            staff,
            co,
            f"calendar/{event['id']}/cancel",
            {"expectedVersion": event["version"]},
        ).status_code
        == 404
    )
    assert (
        api(
            admin,
            co,
            f"calendar/{event['id']}/respond",
            {"expectedVersion": event["version"], "response": "ACCEPTED"},
        ).status_code
        == 404
    )
    saved = ok(
        api(
            staff,
            co,
            f"calendar/{event['id']}/respond",
            {"expectedVersion": event["version"], "response": "ACCEPTED"},
        )
    )
    assert saved["attendees"][0]["response"] == "ACCEPTED"


def test_all_63_routes_deny_other_company_and_actor_fields(company_env):
    from fs.hr.work_setup import create_company

    engine, co, admin, staff = company_env
    setup(company_env)
    with engine.begin() as c:
        other = create_company(
            c,
            {
                "companyName": "다른 HTTP 합성 회사",
                "loginId": "http-other-owner",
                "name": "다른 합성 소유자",
                "password": "Synthetic-" + str(uuid4()),
                "employeeCode": "HTTP-OTHER",
                "workStart": "09:00",
                "dailyMinutes": 480,
                "breakMinutes": 60,
                "annualDays": 15,
            },
        )
    count = 0
    for route in router.routes:
        path = re.sub(r"\{kind\}", "PURCHASE_INVOICE", route.path)
        path = re.sub(r"\{[^}]+\}", "1", path)
        for method in route.methods:
            for client in (admin, staff):
                denied = client.request(
                    method,
                    "/api/v1/gw" + path,
                    params={"companyId": other["companyId"]},
                    json={} if method != "GET" else None,
                )
                assert denied.status_code == 403, (method, path, denied.text)
                forged = client.request(
                    method,
                    "/api/v1/gw" + path,
                    params={
                        "companyId": co["companyId"],
                        **({"personId": "1"} if method == "GET" else {}),
                    },
                    json={"actingPersonId": "1"} if method != "GET" else None,
                )
                assert forged.status_code == 400, (method, path, forged.text)
            count += 1
    assert count == 63


def test_company_policy_role_and_delegation_http(company_env):
    _, co, admin, staff = company_env
    _, target, doc = create_doc(company_env)
    rule = {
        "code": "HTTP-LIMIT",
        "documentKind": "GENERAL",
        "currency": "KRW",
        "amountFrom": "0",
        "amountTo": "1000",
        "finalSeq": 1,
        "effectiveFrom": "2026-01",
    }
    assert api(staff, co, "authority-rules", rule).status_code == 403
    saved = ok(api(admin, co, "authority-rules", rule))
    changed = ok(
        api(
            admin,
            co,
            "authority-rules/" + saved["id"],
            {"expectedVersion": saved["version"], "isActive": False},
            method="PATCH",
        )
    )
    assert changed["isActive"] is False
    assert (
        api(
            admin,
            co,
            "authority-rules/" + saved["id"],
            {"expectedVersion": saved["version"]},
            method="DELETE",
        ).status_code
        == 409
    )
    assert (
        api(
            admin,
            co,
            "authority-rules/" + saved["id"],
            {"expectedVersion": changed["version"]},
            method="DELETE",
        ).status_code
        == 204
    )
    assert (
        api(
            admin, co, "authority-rules", {**rule, "documentKind": "ERP_PURCHASE"}
        ).status_code
        == 400
    )
    assert (
        api(
            staff,
            co,
            "delegations",
            {
                "delegatePersonId": doc["drafterId"],
                "startsAt": "2026-10-01T00:00:00+09:00",
                "endsAt": "2026-12-01T00:00:00+09:00",
                "reason": "미배정 위임 거부",
            },
        ).status_code
        == 400
    )
    ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )
    grant = ok(
        api(
            staff,
            co,
            "delegations",
            {
                "delegatePersonId": doc["drafterId"],
                "startsAt": "2026-10-01T00:00:00+09:00",
                "endsAt": "2026-12-01T00:00:00+09:00",
                "reason": "합성 본인 결재 위임",
            },
        )
    )
    assert grant["delegatorPersonId"] == str(target)
    assert (
        api(
            admin,
            co,
            f"delegations/{grant['id']}/revoke",
            {"expectedVersion": grant["version"]},
        ).status_code
        == 404
    )
    ok(
        api(
            staff,
            co,
            f"delegations/{grant['id']}/revoke",
            {"expectedVersion": grant["version"]},
        )
    )


def test_company_people_aliases_sources_and_query_bounds(company_env):
    _, co, admin, staff = company_env
    own, target = setup(company_env)
    for endpoint in ("people", "people-master"):
        assert (
            api(
                staff,
                co,
                endpoint,
                {"code": "FAKE", "name": "가짜 직원", "jobRole": "BOARD_ADMIN"},
            ).status_code
            == 403
        )
        assert (
            api(
                admin,
                co,
                endpoint,
                {"code": "FAKE", "name": "가짜 직원", "jobRole": "BOARD_ADMIN"},
            ).status_code
            == 400
        )
        assert (
            api(
                staff,
                co,
                f"{endpoint}/{own}",
                {
                    "expectedVersion": 1,
                    "isActive": False,
                    "reason": "무권한 직원 변경 거부",
                },
                method="PATCH",
            ).status_code
            == 403
        )
    assert ok(api(staff, co, f"people/{target}", method="GET"))["id"] == str(target)
    assert api(admin, co, "sources", method="GET").status_code == 400
    for params in (
        {"limit": "101"},
        {"offset": "-1"},
        {"search": "x" * 101},
        {"personId": str(target)},
        {"workspaceId": "1"},
    ):
        assert (
            admin.get(
                "/api/v1/gw/people-options",
                params={"companyId": co["companyId"], **params},
            ).status_code
            == 400
        )
    reply = admin.get(
        "/api/v1/gw/people-options",
        params={"companyId": co["companyId"], "limit": 1, "search": ""},
    )
    assert len(ok(reply)) == 1 and reply.json()["page"]["total"] == 2
    assert api(staff, co, "channels", []).status_code == 400


def test_notification_and_comment_receipt_hidden_after_read_revocation(
    company_env, third
):
    from sqlalchemy import text
    from test_gw_company import context

    engine, co, admin, _ = company_env
    _, _, doc = create_doc(company_env)
    person, _ = connect_third(company_env, third)
    doc = ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/submit",
            {"expectedVersion": doc["version"]},
        )
    )
    reader = ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/readers",
            {
                "personId": str(person),
                "expectedVersion": doc["version"],
                "reason": "합성 읽기 허용",
            },
        )
    )
    body = {
        "targetKind": "DOCUMENT",
        "targetId": doc["id"],
        "body": "회수 뒤 숨길 댓글",
    }
    key = str(uuid4())
    ok(api(third, co, "comments", body, key=key))
    with company.transaction(context(engine, admin), co["companyId"], write=True) as (
        c,
        ctx,
        _,
    ):
        notification = c.execute(
            text(
                "INSERT INTO gw.notification(workspace_id,generation_id,recipient_id,kind,ref_kind,ref_id,event_key,title) VALUES (:w,:g,:p,'COMMENT','DOCUMENT',:d,'TEST-READER','숨길 합성 알림') RETURNING id"
            ),
            {
                "w": ctx.workspace_id,
                "g": ctx.generation_id,
                "p": person,
                "d": int(doc["id"]),
            },
        ).scalar_one()
    assert len(ok(api(third, co, "notifications", method="GET"))) == 1
    ok(
        api(
            admin,
            co,
            f"documents/{doc['id']}/readers/{person}",
            {
                "expectedVersion": reader["version"],
                "isActive": False,
                "reason": "합성 읽기 회수",
            },
            method="PATCH",
        )
    )
    assert api(third, co, "comments", body, key=key).status_code == 404
    assert ok(api(third, co, "notifications", method="GET")) == []
    assert api(third, co, f"notifications/{notification}/read", {}).status_code == 404
    assert (
        third.get(
            "/api/v1/gw/comments",
            params={
                "companyId": co["companyId"],
                "targetKind": "DOCUMENT",
                "targetId": doc["id"],
            },
        ).status_code
        == 404
    )


def test_person_display_active_reason_and_version_are_company_scoped(company_env):
    _, co, admin, staff = company_env
    own, target = setup(company_env)
    path = f"people-master/{target}"
    assert (
        api(
            admin,
            co,
            path,
            {"expectedVersion": 1, "jobRole": "MANAGER"},
            method="PATCH",
        ).status_code
        == 400
    )
    saved = ok(
        api(
            admin,
            co,
            path,
            {"expectedVersion": 1, "jobRole": "MANAGER", "reason": "합성 표시 변경"},
            method="PATCH",
        )
    )
    assert saved["jobRole"] == "MANAGER"
    assert (
        api(
            staff,
            co,
            path,
            {
                "expectedVersion": saved["version"],
                "jobRole": "STAFF",
                "reason": "권한 없는 변경",
            },
            method="PATCH",
        ).status_code
        == 403
    )
    assert (
        api(
            admin,
            co,
            path,
            {"expectedVersion": 1, "isActive": False, "reason": "오래된 화면 변경"},
            method="PATCH",
        ).status_code
        == 409
    )
    inactive = ok(
        api(
            admin,
            co,
            path,
            {
                "expectedVersion": saved["version"],
                "isActive": False,
                "reason": "합성 직원 비활성",
            },
            method="PATCH",
        )
    )
    me = ok(api(staff, co, "me", method="GET"))
    assert me["person"]["isActive"] is False and me["businessReady"] is False
    assert api(staff, co, "documents", method="GET").status_code == 403
    restored = ok(
        api(
            admin,
            co,
            path,
            {
                "expectedVersion": inactive["version"],
                "isActive": True,
                "reason": "합성 직원 복귀",
            },
            method="PATCH",
        )
    )
    assert restored["isActive"] is True
    assert (
        api(
            admin,
            co,
            path,
            {
                "expectedVersion": restored["version"],
                "name": "변경 이름",
                "reason": "HR 이름 변경 시도",
            },
            method="PATCH",
        ).status_code
        == 400
    )
    assert (
        api(
            admin,
            co,
            f"people-master/{own}",
            {"expectedVersion": 1, "isActive": False, "reason": "마지막 관리자 비활성"},
            method="PATCH",
        ).status_code
        == 409
    )
