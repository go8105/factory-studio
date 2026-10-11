from uuid import uuid4

from test_gw_projects import board, get, post, task, update

pytest_plugins = ["test_hr_work"]


def test_free_columns_versions_scope_restore_and_group_copy(company_env):
    _, co, admin, staff = company_env
    bid = board(admin, co)
    initial = get(admin, co, bid)
    assert len(initial["columns"]) == 6
    gid = initial["groups"][0]["id"]
    tid = task(admin, co, bid, gid, status="REVIEW")
    body = {"boardId": bid, "name": "산출물", "kind": "TEXT"}
    assert post(staff, co, "column-create", body).status_code == 403
    key = str(uuid4())
    r = post(admin, co, "column-create", body, key)
    assert r.status_code == 200, r.text
    assert post(admin, co, "column-create", body, key).json() == r.json()
    col = next(
        x for x in get(admin, co, bid)["columns"] if x["id"] == r.json()["data"]["id"]
    )
    cellbody = {
        "boardId": bid,
        "taskId": tid,
        "taskVersion": 1,
        "columnId": col["id"],
        "columnVersion": 1,
        "version": 0,
        "value": "합성 보고서",
    }
    result = post(admin, co, "cell-update", cellbody)
    assert result.status_code == 200, result.text
    assert post(admin, co, "cell-update", cellbody).status_code == 409
    assert (
        post(
            admin, co, "cell-update", {**cellbody, "version": 1, "value": False}
        ).status_code
        == 422
    )
    other = board(admin, co)
    assert (
        post(admin, co, "cell-update", {**cellbody, "boardId": other}).status_code
        == 404
    )
    assert (
        post(
            admin, co, "cell-update", {**cellbody, "version": 1, "value": None}
        ).status_code
        == 200
    )
    assert (
        post(
            admin,
            co,
            "column-state",
            {"boardId": bid, "id": col["id"], "version": 1, "state": "delete"},
        ).status_code
        == 200
    )
    assert (
        post(
            admin, co, "cell-update", {**cellbody, "columnVersion": 2, "version": 2}
        ).status_code
        == 409
    )
    assert (
        post(
            admin,
            co,
            "column-state",
            {"boardId": bid, "id": col["id"], "version": 2, "state": "restore"},
        ).status_code
        == 200
    )
    assert get(admin, co, bid)["cells"][0]["value"] is None
    dup = post(admin, co, "group-duplicate", {"boardId": bid, "id": gid, "version": 1})
    assert dup.status_code == 200, dup.text
    copied = get(admin, co, bid)
    assert len(copied["tasks"]) == 2 and len(copied["cells"]) == 2
    assert (
        post(
            admin,
            co,
            "group-state",
            {"boardId": bid, "id": gid, "version": 1, "state": "delete"},
        ).status_code
        == 200
    )
    t = next(x for x in get(admin, co, bid)["tasks"] if x["id"] == tid)
    assert (
        post(admin, co, "task-update", {**update(t), "title": "차단 확인"}).status_code
        == 409
    )
    assert (
        post(
            admin,
            co,
            "group-state",
            {"boardId": bid, "id": gid, "version": 2, "state": "restore"},
        ).status_code
        == 200
    )
    assert (
        post(
            admin, co, "task-update", {**update(t), "title": "복구 후 수정"}
        ).status_code
        == 200
    )


def test_free_cell_date_number_status_validation(company_env):
    _, co, admin, _ = company_env
    bid = board(admin, co)
    gid = get(admin, co, bid)["groups"][0]["id"]
    tid = task(admin, co, bid, gid)
    for kind, good, bad in [
        ("NUMBER", 12, True),
        ("DATE", "2026-10-11", "2026-02-30"),
        ("STATUS", "검토", "없는상태"),
        ("CHECKBOX", False, "false"),
        (
            "TIMELINE",
            {"start": "2026-10-11", "end": "2026-10-12"},
            {"start": "2026-10-13", "end": "2026-10-12"},
        ),
    ]:
        r = post(
            admin,
            co,
            "column-create",
            {
                "boardId": bid,
                "name": kind,
                "kind": kind,
                "options": {"labels": ["검토", "완료"]} if kind == "STATUS" else {},
            },
        )
        assert r.status_code == 200, r.text
        body = {
            "boardId": bid,
            "taskId": tid,
            "taskVersion": 1,
            "columnId": r.json()["data"]["id"],
            "columnVersion": 1,
            "version": 0,
        }
        assert post(admin, co, "cell-update", {**body, "value": bad}).status_code == 422
        r = post(admin, co, "cell-update", {**body, "value": good})
        assert r.status_code == 200, r.text
