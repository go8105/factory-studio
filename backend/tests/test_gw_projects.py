from uuid import uuid4

from fastapi.testclient import TestClient
from fs.main import create_app
from sqlalchemy import text

pytest_plugins = ["test_hr_work"]

ROOT = "/api/v1/gw/projects"


def get(client, company, bid=None):
    r = client.get(
        ROOT,
        params={"companyId": company["companyId"], **({"boardId": bid} if bid else {})},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]


def post(client, company, op, body, key=None):
    return client.post(
        ROOT + "/" + op,
        params={"companyId": company["companyId"]},
        json=body,
        headers={"X-CSRF-Token": client.csrf, "Idempotency-Key": key or str(uuid4())},
    )


def board(admin, company):
    r = post(
        admin, company, "board-create", {"name": "합성 프로젝트", "template": "PROJECT"}
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def task(admin, company, bid, gid, **extra):
    r = post(
        admin,
        company,
        "task-create",
        {"boardId": bid, "groupId": gid, "title": "합성 업무", **extra},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


def update(t, **extra):
    return dict(
        boardId=t["board_id"],
        id=t["id"],
        version=t["version"],
        groupId=t["group_id"],
        parentId=t["parent_id"],
        title=t["title"],
        description=t["description"],
        status=t["status"],
        priority=t["priority"],
        startsOn=t["starts_on"],
        endsOn=t["ends_on"],
        progress=t["progress"],
        position=t["position"],
        archived=bool(t["archived_at"]),
        assignees=[a["user_id"] for a in t["assignees"]],
        **extra,
    )


def test_board_permissions_revocation_and_receipt(company_env):
    engine, company, admin, staff = company_env
    bid = board(admin, company)
    data = get(staff, company, bid)
    assert data["role"] == "VIEWER"
    gid = data["groups"][0]["id"]
    uid = data["userId"]
    body = {"boardId": bid, "groupId": gid, "title": "합成 직원 업무"}
    assert post(staff, company, "task-create", body).status_code == 403
    assert (
        post(
            admin, company, "member", {"boardId": bid, "userId": uid, "role": "EDITOR"}
        ).status_code
        == 200
    )
    key = str(uuid4())
    r = post(staff, company, "task-create", body, key)
    assert r.status_code == 200, r.text
    assert post(staff, company, "task-create", body, key).json() == r.json()
    assert len(get(admin, company, bid)["tasks"]) == 1
    post(admin, company, "member", {"boardId": bid, "userId": uid, "role": "VIEWER"})
    assert post(staff, company, "task-create", body, key).status_code == 403
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.company_member SET is_active=false WHERE workspace_id=:w AND user_id=:u"
            ),
            {"w": company["companyId"], "u": uid},
        )
    assert (
        staff.get(
            ROOT, params={"companyId": company["companyId"], "boardId": bid}
        ).status_code
        == 403
    )
    assert (
        staff.get(ROOT, params={"companyId": company["companyId"] + 1000}).status_code
        == 403
    )


def test_subtask_aggregation_dates_conflict_and_scope(company_env):
    _, company, admin, staff = company_env
    bid = board(admin, company)
    data = get(admin, company, bid)
    gid = data["groups"][0]["id"]
    uid = get(staff, company)["userId"]
    parent = task(admin, company, bid, gid)
    child = task(
        admin,
        company,
        bid,
        gid,
        parentId=parent,
        status="DONE",
        startsOn="2026-10-10",
        endsOn="2026-10-12",
        assignees=[uid],
    )
    second = task(
        admin, company, bid, gid, parentId=parent, status="WORKING", progress=40
    )
    data = get(admin, company, bid)
    p = next(t for t in data["tasks"] if t["id"] == parent)
    assert p["progress"] == 70
    assert p["status"] == "WORKING"
    assert p["starts_on"] == "2026-10-10"
    assert (
        post(
            admin,
            company,
            "task-create",
            {
                "boardId": bid,
                "groupId": gid,
                "title": "잘못된 하위 업무",
                "parentId": child,
            },
        ).status_code
        == 422
    )
    t = next(t for t in data["tasks"] if t["id"] == second)
    body = update(t)
    body["status"] = "DONE"
    assert post(admin, company, "task-update", body).status_code == 200
    assert post(admin, company, "task-update", body).status_code == 409
    p = next(t for t in get(admin, company, bid)["tasks"] if t["id"] == parent)
    assert p["status"] == "DONE"
    assert p["progress"] == 100
    assert (
        len(
            staff.get(
                ROOT + "/my-tasks", params={"companyId": company["companyId"]}
            ).json()["data"]
        )
        == 1
    )
    other = board(admin, company)
    assert (
        post(
            admin,
            company,
            "task-create",
            {"boardId": other, "groupId": gid, "title": "다른 보드"},
        ).status_code
        == 422
    )
    assert (
        post(
            admin,
            company,
            "task-create",
            {
                "boardId": bid,
                "groupId": gid,
                "title": "날짜",
                "startsOn": "2026-10-20",
                "endsOn": "2026-10-10",
            },
        ).status_code
        == 422
    )


def test_comments_favorites_preferences_owner_archive(company_env):
    _, company, admin, staff = company_env
    bid = board(admin, company)
    data = get(admin, company, bid)
    gid = data["groups"][0]["id"]
    tid = task(admin, company, bid, gid)
    uid = data["userId"]
    assert (
        post(
            admin, company, "member", {"boardId": bid, "userId": uid, "role": "VIEWER"}
        ).status_code
        == 409
    )
    assert (
        post(staff, company, "favorite", {"boardId": bid, "selected": True}).status_code
        == 200
    )
    assert bid in get(staff, company)["favorites"]
    assert (
        post(
            staff,
            company,
            "preference",
            {"boardId": bid, "settings": {"view": "kanban"}},
        ).status_code
        == 200
    )
    assert get(staff, company, bid)["preference"][0]["settings"]["view"] == "kanban"
    r = post(
        admin,
        company,
        "comment-create",
        {"boardId": bid, "taskId": tid, "body": "합성 댓글"},
    )
    assert r.status_code == 200, r.text
    rid = r.json()["data"]["id"]
    assert (
        post(
            staff,
            company,
            "comment-update",
            {
                "boardId": bid,
                "taskId": tid,
                "id": rid,
                "version": 1,
                "body": "타인 댓글",
                "deleted": True,
            },
        ).status_code
        == 403
    )
    assert (
        post(
            admin,
            company,
            "comment-update",
            {
                "boardId": bid,
                "taskId": tid,
                "id": rid,
                "version": 1,
                "body": "새 댓글",
                "deleted": False,
            },
        ).status_code
        == 200
    )
    assert (
        post(
            admin,
            company,
            "board-update",
            {"boardId": bid, "name": "보관 프로젝트", "version": 1, "archived": True},
        ).status_code
        == 200
    )
    assert (
        post(
            admin,
            company,
            "task-create",
            {"boardId": bid, "groupId": gid, "title": "보관쓰기"},
        ).status_code
        == 409
    )
    assert get(staff, company, bid)["board"]["archived_at"]


def test_guest_and_invalid_fields(company_env):
    _, company, admin, _ = company_env
    with TestClient(create_app()) as client:
        r = client.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "업무 체험"},
            headers={"Idempotency-Key": str(uuid4())},
        )
        assert r.status_code == 201
        assert client.get(ROOT + "/companies").status_code == 403
    assert (
        post(
            admin, company, "board-create", {"name": " ", "template": "PROJECT"}
        ).status_code
        == 400
    )
    assert (
        post(
            admin, company, "board-create", {"name": "보드", "actingPersonId": 1}
        ).status_code
        == 400
    )
