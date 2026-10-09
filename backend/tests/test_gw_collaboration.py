"""GW-d uses real scoped PostgreSQL transactions, not mocked business storage."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from tests.test_gw import P, call, ok
from tests.test_gw_policy import act, draft
from tests.test_gw_policy import space as space_fixture

SEEDS = ()
EMPTY_MODULES = ("gw",)


@pytest.fixture(name="space")
def collaboration_space(guest_space):
    return space_fixture.__wrapped__(guest_space)


def post(z, visibility="WORKSPACE", org=None):
    c, s, _e, pp = z
    pp[0] = ok(
        call(
            c,
            s,
            "PATCH",
            "/people/" + pp[0]["id"],
            {
                "expectedVersion": pp[0]["version"],
                "name": pp[0]["name"],
                "jobRole": "BOARD_ADMIN",
                "isActive": True,
            },
        )
    )
    p = ok(
        call(
            c,
            s,
            "POST",
            "/posts",
            {
                "actingPersonId": pp[0]["id"],
                "boardKind": "NOTICE",
                "title": "합성 공지",
                "body": "원문",
                "visibility": visibility,
                "audienceOrgId": org,
            },
        ),
        201,
    )
    return ok(
        call(
            c,
            s,
            "POST",
            f"/posts/{p['id']}/publish",
            {"actingPersonId": pp[0]["id"], "expectedVersion": p["version"]},
        )
    )


def inbox(z, i):
    c, _s, _e, pp = z
    return ok(c.get(P + "/notifications", params={"personId": pp[i]["id"]}))


def calendar(z, **kw):
    c, s, _e, pp = z
    return call(
        c,
        s,
        "POST",
        "/calendar",
        {
            "actingPersonId": pp[0]["id"],
            "title": "회의",
            "scope": "PERSONAL",
            "startsAt": "2026-10-10T09:00:00+09:00",
            "endsAt": "2026-10-10T10:00:00+09:00",
            "attendeeIds": [pp[1]["id"]],
            **kw,
        },
    )


def channel(z, **kw):
    c, s, _e, pp = z
    return ok(
        call(
            c,
            s,
            "POST",
            "/channels",
            {
                "actingPersonId": pp[0]["id"],
                "name": "합성 대화",
                "channelKind": "DIRECT",
                "memberIds": [pp[1]["id"]],
                **kw,
            },
        ),
        201,
    )


def test_comment_history_delete_and_original_unchanged(space):
    c, s, _e, pp = space
    p = post(space)
    v = {
        "actingPersonId": pp[1]["id"],
        "targetKind": "POST",
        "targetId": p["id"],
        "body": "첫 의견",
    }
    key = str(uuid4())
    a = ok(call(c, s, "POST", "/comments", v, key), 201)
    assert ok(call(c, s, "POST", "/comments", v, key), 201)["id"] == a["id"]
    assert (
        call(
            c,
            s,
            "PATCH",
            "/comments/" + a["id"],
            {"actingPersonId": pp[2]["id"], "expectedVersion": 1, "body": "침범"},
        ).status_code
        == 409
    )
    a = ok(
        call(
            c,
            s,
            "PATCH",
            "/comments/" + a["id"],
            {"actingPersonId": pp[1]["id"], "expectedVersion": 1, "body": "수정 의견"},
        )
    )
    found = ok(
        c.get(
            P + "/comments",
            params={"personId": pp[0]["id"], "targetKind": "POST", "targetId": p["id"]},
        )
    )
    assert found[0]["revisions"][0]["body"] == "첫 의견"
    assert ok(c.get(P + "/posts/" + p["id"]))["version"] == p["version"]
    a = ok(
        call(
            c,
            s,
            "POST",
            f"/comments/{a['id']}/delete",
            {"actingPersonId": pp[1]["id"], "expectedVersion": a["version"]},
        )
    )
    assert a["body"] == "" and a["status"] == "DELETED"
    assert len([n for n in inbox(space, 0) if n["kind"] == "COMMENT"]) == 1
    with _e.connect() as conn:
        assert (
            conn.execute(
                text("SELECT body FROM gw.comment WHERE id=:id"), {"id": int(a["id"])}
            ).scalar_one()
            == "수정 의견"
        )


def test_document_comment_does_not_change_approval(space):
    c, s, _e, pp = space
    d = ok(act(space, draft(space), "submit"))
    assert ok(
        call(
            c,
            s,
            "POST",
            "/comments",
            {
                "actingPersonId": pp[1]["id"],
                "targetKind": "DOCUMENT",
                "targetId": d["id"],
                "body": "승인 범위와 별개",
            },
        ),
        201,
    )
    after = ok(c.get(P + "/documents/" + d["id"]))
    assert after["version"] == d["version"] and after["status"] == "IN_REVIEW"


def test_notification_stage_once_read_owner_and_close(space):
    c, s, _e, pp = space
    d = ok(act(space, draft(space), "submit"))
    assert [n["kind"] for n in inbox(space, 1)] == ["APPROVAL_ARRIVED"]
    assert inbox(space, 2) == []
    n = inbox(space, 1)[0]
    assert (
        call(
            c,
            s,
            "POST",
            f"/notifications/{n['id']}/read",
            {"actingPersonId": pp[2]["id"]},
        ).status_code
        == 409
    )
    first = ok(
        call(
            c,
            s,
            "POST",
            f"/notifications/{n['id']}/read",
            {"actingPersonId": pp[1]["id"]},
        )
    )
    second = ok(
        call(
            c,
            s,
            "POST",
            f"/notifications/{n['id']}/read",
            {"actingPersonId": pp[1]["id"]},
        )
    )
    assert first["readAt"] == second["readAt"]
    key = str(uuid4())
    d = ok(act(space, d, "approve", 1, key=key))
    assert len(inbox(space, 2)) == 1
    d = ok(act(space, d, "approve", 2))
    assert inbox(space, 0)[0]["kind"] == "APPROVAL_DONE"


@pytest.mark.parametrize(
    "action,who,expected", [("reject", 1, "REJECTED"), ("withdraw", 0, "WITHDRAWN")]
)
def test_reject_withdraw_notifications(space, action, who, expected):
    d = ok(act(space, draft(space), "submit"))
    ok(act(space, d, action, who, reason="합성 사유"))
    assert inbox(space, 0)[0]["kind"] == expected


def test_calendar_visibility_response_edit_and_cancel(space):
    c, s, _e, pp = space
    event = ok(calendar(space), 201)
    assert (
        c.get(
            P + f"/calendar/{event['id']}", params={"personId": pp[2]["id"]}
        ).status_code
        == 404
    )
    response = ok(
        call(
            c,
            s,
            "POST",
            f"/calendar/{event['id']}/respond",
            {
                "actingPersonId": pp[1]["id"],
                "expectedVersion": event["version"],
                "response": "ACCEPTED",
            },
        )
    )
    assert response["attendees"][0]["response"] == "ACCEPTED"
    assert (
        call(
            c,
            s,
            "POST",
            f"/calendar/{event['id']}/cancel",
            {"actingPersonId": pp[1]["id"], "expectedVersion": 1},
        ).status_code
        == 409
    )
    event = ok(
        call(
            c,
            s,
            "POST",
            f"/calendar/{event['id']}/cancel",
            {"actingPersonId": pp[0]["id"], "expectedVersion": 1},
        )
    )
    assert event["status"] == "CANCELLED"
    assert (
        call(
            c,
            s,
            "POST",
            f"/calendar/{event['id']}/respond",
            {
                "actingPersonId": pp[1]["id"],
                "expectedVersion": 2,
                "response": "DECLINED",
            },
        ).status_code
        == 409
    )
    assert len(inbox(space, 1)) == 2


@pytest.mark.parametrize(
    "extra",
    [
        {"endsAt": "2026-10-10T08:00:00+09:00"},
        {"scope": "DEPARTMENT"},
        {"allDay": True},
        {"attendeeIds": ["9223372036854775807"]},
    ],
)
def test_calendar_invalid_rollback(space, extra):
    r = calendar(space, **extra)
    assert r.status_code in (400, 404), r.text
    assert inbox(space, 1) == []


def test_calendar_overlap_boundary(space):
    c, _s, _e, pp = space
    ok(calendar(space), 201)
    q = {
        "personId": pp[1]["id"],
        "startsAt": "2026-10-10T10:00:00+09:00",
        "endsAt": "2026-10-11T00:00:00+09:00",
    }
    assert ok(c.get(P + "/calendar", params=q)) == []
    q["startsAt"] = "2026-10-10T09:30:00+09:00"
    assert len(ok(c.get(P + "/calendar", params=q))) == 1


def test_chat_dedup_cursor_leave_and_nonmember(space):
    c, s, _e, pp = space
    ch = channel(space)
    path = f"/channels/{ch['id']}/messages"
    assert c.get(P + path, params={"personId": pp[2]["id"]}).status_code == 404
    v = {"actingPersonId": pp[0]["id"], "body": "합성 메시지", "clientKey": "retry-one"}
    m = ok(call(c, s, "POST", path, v))
    assert m["seq"] == 1
    assert ok(call(c, s, "POST", path, v))["id"] == m["id"]
    assert call(c, s, "POST", path, {**v, "body": "다른 내용"}).status_code == 400
    ok(
        call(
            c,
            s,
            "POST",
            f"/channels/{ch['id']}/read",
            {"actingPersonId": pp[1]["id"], "seq": 1},
        )
    )
    assert (
        call(
            c,
            s,
            "POST",
            f"/channels/{ch['id']}/read",
            {"actingPersonId": pp[1]["id"], "seq": 2},
        ).status_code
        == 400
    )
    ok(
        call(
            c, s, "POST", f"/channels/{ch['id']}/leave", {"actingPersonId": pp[1]["id"]}
        )
    )
    assert c.get(P + path, params={"personId": pp[1]["id"]}).status_code == 404
    assert (
        call(
            c,
            s,
            "POST",
            path,
            {**v, "actingPersonId": pp[1]["id"], "clientKey": "left"},
        ).status_code
        == 404
    )
    assert ok(c.get(P + "/channels", params={"personId": pp[1]["id"]})) == []


def test_chat_concurrent_sequence_and_duplicate(space):
    c, s, _e, pp = space
    ch = channel(space)
    path = f"/channels/{ch['id']}/messages"

    def send(i):
        with TestClient(c.app, base_url="https://testserver") as other:
            other.cookies.update(c.cookies)
            return ok(
                call(
                    other,
                    s,
                    "POST",
                    path,
                    {
                        "actingPersonId": pp[i % 2]["id"],
                        "body": f"내용 {i}",
                        "clientKey": f"key-{i}",
                    },
                )
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        messages = list(pool.map(send, range(8)))
    assert sorted(m["seq"] for m in messages) == list(range(1, 9))
    assert len(ok(c.get(P + path, params={"personId": pp[0]["id"]}))["messages"]) == 8


def test_collaboration_csrf_and_other_workspace(space):
    c, _s, _e, pp = space
    channel(space)
    assert (
        c.post(
            P + "/channels",
            json={
                "actingPersonId": pp[0]["id"],
                "name": "비허용",
                "channelKind": "DIRECT",
                "memberIds": [pp[1]["id"]],
            },
        ).status_code
        == 403
    )
    assert (
        c.get(
            P + "/channels/9223372036854775807/messages",
            params={"personId": pp[0]["id"]},
        ).status_code
        == 404
    )


def organizations(z):
    _c, s, e, pp = z
    with e.begin() as conn:
        ids = []
        for code in ("ORG-A", "ORG-B"):
            ids.append(
                conn.execute(
                    text(
                        "INSERT INTO gw.organization_unit(workspace_id,generation_id,code,name) VALUES(:w,:g,:code,:code) RETURNING id"
                    ),
                    {"w": s["workspaceId"], "g": s["generationId"], "code": code},
                ).scalar_one()
            )
        for i in range(3):
            conn.execute(
                text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:id"),
                {"id": int(pp[i]["id"]), "org": ids[0] if i < 2 else ids[1]},
            )
    return ids


def test_department_notice_visibility_notifications_and_provider(space):
    from fs.gw import interface

    c, s, e, pp = space
    orgs = organizations(space)
    p = post(space, "ORG", orgs[0])
    assert c.get(P + "/posts/" + p["id"]).status_code == 404
    assert (
        ok(c.get(P + "/posts/" + p["id"], params={"personId": pp[1]["id"]}))["id"]
        == p["id"]
    )
    assert (
        c.get(P + "/posts/" + p["id"], params={"personId": pp[2]["id"]}).status_code
        == 404
    )
    assert inbox(space, 2) == [] and inbox(space, 1)[0]["kind"] == "NOTICE"
    assert (
        call(
            c,
            s,
            "POST",
            "/comments",
            {
                "actingPersonId": pp[2]["id"],
                "targetKind": "POST",
                "targetId": p["id"],
                "body": "볼 수 없음",
            },
        ).status_code
        == 404
    )
    with e.begin() as conn:
        conn.execute(
            text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:id"),
            {"id": int(pp[1]["id"]), "org": orgs[1]},
        )
    assert inbox(space, 1) == []
    with e.connect() as conn:
        from types import SimpleNamespace

        scoped = SimpleNamespace(
            workspace_id=s["workspaceId"], generation_id=s["generationId"]
        )
        assert interface.published_notices(conn, scoped) == []
        assert interface.lookup(conn, scoped, p["postNo"]) is None


def test_department_calendar_and_edit_keeps_scope_snapshot(space):
    c, s, e, pp = space
    orgs = organizations(space)
    event = ok(calendar(space, scope="DEPARTMENT", attendeeIds=[]), 201)
    assert ok(c.get(P + f"/calendar/{event['id']}", params={"personId": pp[1]["id"]}))[
        "organizationUnitId"
    ] == str(orgs[0])
    assert (
        c.get(
            P + f"/calendar/{event['id']}", params={"personId": pp[2]["id"]}
        ).status_code
        == 404
    )
    with e.begin() as conn:
        conn.execute(
            text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:id"),
            {"id": int(pp[0]["id"]), "org": orgs[1]},
        )
    edited = ok(
        call(
            c,
            s,
            "PATCH",
            f"/calendar/{event['id']}",
            {
                "actingPersonId": pp[0]["id"],
                "expectedVersion": 1,
                "title": "변경",
                "scope": "DEPARTMENT",
                "startsAt": "2026-10-10T09:00:00+09:00",
                "endsAt": "2026-10-10T11:00:00+09:00",
                "attendeeIds": [],
            },
        )
    )
    assert edited["organizationUnitId"] == str(orgs[0])


def test_real_other_space_cannot_read_or_write(space):
    c, _s, _e, _pp = space
    ch = channel(space)
    with TestClient(c.app, base_url="https://testserver") as other:
        session = ok(
            other.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "다른 합성 공간"},
                headers={"Idempotency-Key": str(uuid4())},
            ),
            201,
        )
        person = ok(
            call(
                other,
                session,
                "POST",
                "/people",
                {"code": "OTHER", "name": "다른사람", "jobRole": "STAFF"},
            ),
            201,
        )
        path = f"/channels/{ch['id']}/messages"
        assert other.get(P + path, params={"personId": person["id"]}).status_code == 404
        assert (
            call(
                other,
                session,
                "POST",
                path,
                {"actingPersonId": person["id"], "body": "침범", "clientKey": "other"},
            ).status_code
            == 404
        )


def test_chat_same_client_key_concurrent_dedup(space):
    c, s, _e, pp = space
    ch = channel(space)
    path = f"/channels/{ch['id']}/messages"

    def send(_i):
        with TestClient(c.app, base_url="https://testserver") as other:
            other.cookies.update(c.cookies)
            return ok(
                call(
                    other,
                    s,
                    "POST",
                    path,
                    {
                        "actingPersonId": pp[0]["id"],
                        "body": "같은 내용",
                        "clientKey": "shared",
                    },
                )
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        messages = list(pool.map(send, range(2)))
    assert messages[0]["id"] == messages[1]["id"]
    assert len(ok(c.get(P + path, params={"personId": pp[0]["id"]}))["messages"]) == 1


def test_notification_failure_rolls_back_submission(space, monkeypatch):
    from fs.gw import collaboration

    c, _s, _e, _pp = space
    d = draft(space)

    def fail(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(collaboration, "notify", fail)
    with pytest.raises(RuntimeError, match="synthetic failure"):
        act(space, d, "submit")
    current = ok(c.get(P + "/documents/" + d["id"]))
    assert current["status"] == "DRAFT" and current["version"] == d["version"]
    assert not any(e["eventType"] == "SUBMITTED" for e in current["events"])


def test_common_providers_pending_month_and_disabled(space):
    from types import SimpleNamespace

    from fs.gw import interface

    _c, s, e, pp = space
    d = ok(act(space, draft(space), "submit"))
    with e.begin() as conn:
        conn.execute(
            text("UPDATE gw.person SET hr_employee_code=:code WHERE id=:id"),
            {"id": int(pp[1]["id"]), "code": "HR-ONE"},
        )
    ctx = SimpleNamespace(
        workspace_id=s["workspaceId"], generation_id=s["generationId"]
    )
    with e.connect() as conn:
        assert interface.pending_tasks(conn, ctx, "HR-ONE")[0]["count"] == 1
        assert interface.pending_tasks(conn, ctx, "UNKNOWN") == []
        assert interface.lookup(conn, ctx, d["documentNo"])["caption"] == d["title"]
        from datetime import datetime
        from zoneinfo import ZoneInfo

        month = (
            datetime.fromisoformat(d["submittedAt"])
            .astimezone(ZoneInfo("Asia/Seoul"))
            .strftime("%Y-%m")
        )
        assert interface.monthly_summary(conn, ctx, month)["metrics"]["submitted"] == 1
    with e.begin() as conn:
        conn.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false WHERE workspace_id=:w AND module_key='gw'"
            ),
            {"w": s["workspaceId"]},
        )
    with e.connect() as conn:
        assert interface.published_notices(conn, ctx) is None
        assert interface.pending_tasks(conn, ctx, "HR-ONE") is None
        assert interface.monthly_summary(conn, ctx, month) is None
        assert interface.lookup(conn, ctx, d["documentNo"]) is None


def test_inactive_department_does_not_prevent_notice_withdrawal(space):
    c, s, e, pp = space
    orgs = organizations(space)
    p = post(space, "ORG", orgs[0])
    with e.begin() as conn:
        conn.execute(
            text("UPDATE gw.organization_unit SET is_active=false WHERE id=:id"),
            {"id": orgs[0]},
        )
    withdrawn = ok(
        call(
            c,
            s,
            "POST",
            f"/posts/{p['id']}/withdraw",
            {
                "actingPersonId": pp[0]["id"],
                "expectedVersion": p["version"],
                "reason": "부서 공지 철회",
            },
        )
    )
    assert withdrawn["status"] == "WITHDRAWN"


def test_left_member_cannot_replay_cached_message_but_leave_retries(space):
    c, s, _e, pp = space
    ch = channel(space)
    path = f"/channels/{ch['id']}"
    key = str(uuid4())
    body = {
        "actingPersonId": pp[1]["id"],
        "body": "나가기 전 내용",
        "clientKey": "prior",
    }
    ok(call(c, s, "POST", path + "/messages", body, key))
    leave_key = str(uuid4())
    leave = {"actingPersonId": pp[1]["id"]}
    ok(call(c, s, "POST", path + "/leave", leave, leave_key))
    assert ok(call(c, s, "POST", path + "/leave", leave, leave_key))["left"]
    assert call(c, s, "POST", path + "/messages", body, key).status_code == 404


def test_hidden_notice_notification_cannot_replay_cached_read(space):
    c, s, e, pp = space
    orgs = organizations(space)
    post(space, "ORG", orgs[0])
    n = inbox(space, 1)[0]
    key = str(uuid4())
    body = {"actingPersonId": pp[1]["id"]}
    path = f"/notifications/{n['id']}/read"
    ok(call(c, s, "POST", path, body, key))
    with e.begin() as conn:
        conn.execute(
            text("UPDATE gw.person SET organization_unit_id=:org WHERE id=:id"),
            {"id": int(pp[1]["id"]), "org": orgs[1]},
        )
    assert call(c, s, "POST", path, body, key).status_code == 404
