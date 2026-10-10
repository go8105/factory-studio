from uuid import uuid4

from fastapi.testclient import TestClient
from fs.main import create_app
from sqlalchemy import text

pytest_plugins = ["test_hr_work"]

ROOT = "/api/v1/flow"


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
    mine = staff.get(
        ROOT + "/my-tasks", params={"companyId": company["companyId"]}
    ).json()["data"]
    assert len(mine) == 1
    assert mine[0]["assignees"][0]["display_name"]
    assert mine[0]["assignees"][0]["active"]

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


def test_company_policy_group_reorder_and_comment_audit(company_env):
    engine, company, admin, staff = company_env
    bid = board(admin, company)
    data = get(admin, company, bid)
    first, second = data["groups"]
    assert (
        post(
            admin,
            company,
            "group-update",
            {
                "boardId": bid,
                "id": second["id"],
                "version": second["version"],
                "name": second["name"],
                "color": second["color"],
                "position": 0,
            },
        ).status_code
        == 200
    )
    assert get(admin, company, bid)["groups"][0]["id"] == second["id"]
    assert post(staff, company, "settings", {"allowCreate": False}).status_code == 403
    assert post(admin, company, "settings", {"allowCreate": False}).status_code == 200
    assert (
        post(staff, company, "board-create", {"name": "제한 보드"}).status_code == 403
    )
    tid = task(admin, company, bid, first["id"])
    comment = post(
        admin,
        company,
        "comment-create",
        {"boardId": bid, "taskId": tid, "body": "변경 전 합성 댓글"},
    ).json()["data"]["id"]
    assert (
        post(
            admin,
            company,
            "comment-update",
            {
                "boardId": bid,
                "taskId": tid,
                "id": comment,
                "version": 1,
                "body": "변경 후 합성 댓글",
            },
        ).status_code
        == 200
    )
    with engine.connect() as c:
        event = c.execute(
            text(
                "SELECT details FROM flow.work_task_event WHERE workspace_id=:w AND action='comment-update'"
            ),
            {"w": company["companyId"]},
        ).scalar_one()
        assert event["before"]["body"] == "변경 전 합성 댓글"


def test_parent_archive_restores_only_its_batch_and_concurrent_edit(company_env):
    from concurrent.futures import ThreadPoolExecutor

    _, company, admin, _ = company_env
    bid = board(admin, company)
    gid = get(admin, company, bid)["groups"][0]["id"]
    parent = task(admin, company, bid, gid)
    first = task(admin, company, bid, gid, parentId=parent)
    second = task(admin, company, bid, gid, parentId=parent)

    def current(tid):
        return next(t for t in get(admin, company, bid)["tasks"] if t["id"] == tid)

    b = update(current(first))
    b["archived"] = True
    assert post(admin, company, "task-update", b).status_code == 200
    b = update(current(parent))
    b["archived"] = True
    assert post(admin, company, "task-update", b).status_code == 200
    b = update(current(parent))
    b["archived"] = False
    assert post(admin, company, "task-update", b).status_code == 200
    assert current(first)["archived_at"] is not None
    assert current(second)["archived_at"] is None
    b = update(current(second))
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                lambda _: post(admin, company, "task-update", b).status_code, range(2)
            )
        )
    assert sorted(responses) == [200, 409]


def test_parent_pagination_preserves_children_and_server_filters(company_env):
    _, company, admin, _ = company_env
    bid = board(admin, company)
    gid = get(admin, company, bid)["groups"][0]["id"]
    first = task(admin, company, bid, gid, title="검색 부모")
    child = task(
        admin, company, bid, gid, title="완료 하위", parentId=first, status="DONE"
    )
    second = task(admin, company, bid, gid, title="두 번째 업무")

    def page(**extra):
        r = admin.get(
            ROOT, params={"companyId": company["companyId"], "boardId": bid, **extra}
        )
        assert r.status_code == 200, r.text
        return r.json()["data"]

    one = page(limit=1)
    assert {t["id"] for t in one["tasks"]} == {first, child}
    assert one["nextOffset"] == 1
    two = page(limit=1, offset=1)
    assert [t["id"] for t in two["tasks"]] == [second]
    assert two["nextOffset"] is None
    found = page(search="완료 하위", status="DONE")
    assert {t["id"] for t in found["tasks"]} == {first, child}
    assert found["tasks"][0]["progress"] == 100
    assert page(search="%")["tasks"] == []


def test_flow_alias_receipt_and_independent_module(company_env):
    engine, company, admin, _ = company_env
    key = str(uuid4())
    body = {"name": "이전 링크 재시도 보드", "template": "PROJECT"}
    first = post(admin, company, "board-create", body, key)
    assert first.status_code == 200
    replay = admin.post(
        "/api/v1/gw/projects/board-create",
        params={"companyId": company["companyId"]},
        json=body,
        headers={"X-CSRF-Token": admin.csrf, "Idempotency-Key": key},
    )
    assert replay.json() == first.json()
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false WHERE workspace_id=:w AND module_key='gw'"
            ),
            {"w": company["companyId"]},
        )
    assert get(admin, company)["boards"][0]["id"] == first.json()["data"]["id"]
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false WHERE workspace_id=:w AND module_key='flow'"
            ),
            {"w": company["companyId"]},
        )
    assert (
        admin.get(ROOT, params={"companyId": company["companyId"]}).status_code == 409
    )


def test_flow_migration_roundtrip_preserves_records_and_favorites(
    company_env, monkeypatch
):
    from alembic import command
    from alembic.config import Config

    engine, company, admin, _ = company_env
    bid = board(admin, company)
    gid = get(admin, company, bid)["groups"][0]["id"]
    tid = task(admin, company, bid, gid)
    assert (
        post(
            admin,
            company,
            "comment-create",
            {"boardId": bid, "taskId": tid, "body": "합성 보존 댓글"},
        ).status_code
        == 200
    )
    tables = (
        "work_board",
        "work_board_member",
        "work_group",
        "work_task",
        "work_task_assignee",
        "work_task_comment",
        "work_task_event",
        "work_board_favorite",
        "work_view_preference",
        "work_project_settings",
    )

    def snapshot(schema):
        with engine.connect() as c:
            return [
                c.execute(
                    text(
                        f"SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY id),'[]'::jsonb) FROM {schema}.{name} t"
                    )
                ).scalar_one()
                for name in tables
            ]

    before = snapshot("flow")
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace SET menu_preferences=CAST(:prefs AS jsonb) WHERE id=:w"
            ),
            {
                "w": company["companyId"],
                "prefs": '{"menuIds":["flow:boards","gw:pending","flow:my-tasks"],"sidebarMode":"favorites"}',
            },
        )
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    cfg = Config("backend/alembic.ini")
    command.downgrade(cfg, "gw_projects")
    assert snapshot("gw") == before
    with engine.connect() as c:
        assert c.execute(
            text("SELECT menu_preferences->'menuIds' FROM core.workspace WHERE id=:w"),
            {"w": company["companyId"]},
        ).scalar_one() == ["gw:projects", "gw:pending", "gw:my-tasks"]
    command.upgrade(cfg, "head")
    assert snapshot("flow") == before
    with engine.connect() as c:
        assert c.execute(
            text("SELECT menu_preferences->'menuIds' FROM core.workspace WHERE id=:w"),
            {"w": company["companyId"]},
        ).scalar_one() == ["flow:boards", "gw:pending", "flow:my-tasks"]
    assert get(admin, company, bid)["board"]["id"] == bid
