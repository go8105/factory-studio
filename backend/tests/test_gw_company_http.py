"""04 회사 GW HTTP 라우트·협업·권한 회수 검증. 합성 계정/격리 DB 전용."""

# ruff: noqa: F811
import re
from uuid import uuid4

import pytest
from fs.gw import company
from fs.gw.router import router
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env  # noqa: F401


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
