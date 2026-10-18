"""Retention metadata, original ACL, calendar months and holds across policies."""

# ruff: noqa: F401,F811
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from sqlalchemy import text
from test_gw_company import context
from test_gw_company_work import api, call_work, document, ok
from test_gw_evidence import prepare
from test_hr_work import company_env


def fixture(env, monkeypatch):
    prepare(env, monkeypatch)
    engine, co, admin, staff = env
    with engine.connect() as c:
        target = c.execute(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": context(engine, staff).user_id},
        ).scalar_one()
        org = c.execute(
            text("SELECT organization_unit_id FROM gw.person WHERE id=:id"),
            {"id": target},
        ).scalar_one()
    doc = document(env, target)
    submitted = call_work(
        env,
        admin,
        "documents",
        int(doc["id"]),
        "submit",
        {"expected_version": doc["version"]},
    )
    call_work(
        env,
        staff,
        "documents",
        int(doc["id"]),
        "approve",
        {"expected_version": submitted["version"]},
    )
    grant = ok(api(admin, co, f"people/{target}/roles", method="GET"))
    ok(
        api(
            admin,
            co,
            f"people/{target}/roles",
            {
                "expectedVersion": grant["version"],
                "roles": grant["roles"] + ["BOARD_PUBLISHER"],
                "reason": "합성 부서 공지 작성",
            },
            method="PATCH",
        )
    )
    post = call_work(
        env,
        staff,
        "posts",
        None,
        "create",
        {
            "board_kind": "NOTICE",
            "visibility": "ORG",
            "audience_org_id": org,
            "title": "숨겨진 합성 게시 제목",
            "body": "비공개 본문은 보관 관리자에게 공개하지 않음",
        },
    )
    post = call_work(
        env,
        staff,
        "posts",
        int(post["id"]),
        "publish",
        {"expected_version": post["version"]},
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.approval_document SET closed_at='2024-01-31 12:00:00+09' WHERE id=:id"
            ),
            {"id": int(doc["id"])},
        )
        c.execute(
            text(
                "UPDATE gw.board_post SET published_at='2024-01-31 12:00:00+09' WHERE id=:id"
            ),
            {"id": int(post["id"])},
        )
    policy = ok(api(admin, co, "operations", method="GET"))["policy"] | {
        "documentReviewMonths": 1,
        "reason": "합성 달력 기한 검토",
    }
    ok(api(admin, co, "operating-policies", {"expectedVersion": 1, "policy": policy}))
    return doc, post


def refresh(env, version=2):
    return api(
        env[2],
        env[1],
        "retention-reviews/refresh",
        {"expectedVersion": version, "reason": "합성 기한 대상 검토"},
    )


def entries(env):
    return ok(api(env[2], env[1], "retention-reviews", method="GET"))


def change(env, row, state, *, key=None):
    return api(
        env[2],
        env[1],
        f"retention-reviews/{row['id']}/transition",
        {
            "expectedVersion": row["version"],
            "state": state,
            "reason": "합성 보관 검토 변경",
        },
        key=key,
    )


def test_refresh_calendar_metadata_and_source_acl(company_env, monkeypatch):
    _doc, post = fixture(company_env, monkeypatch)
    engine, co, admin, staff = company_env
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person SET organization_unit_id=NULL WHERE workspace_id=:w AND id=(SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE')"
            ),
            {"w": co["companyId"], "u": context(engine, admin).user_id},
        )
    assert ok(refresh(company_env)) == {"added": 2, "hasMore": False}
    assert ok(refresh(company_env))["added"] == 0
    data = entries(company_env)
    assert data["total"] == 2 and all(r["dueOn"] == "2024-02-29" for r in data["items"])
    row = next(r for r in data["items"] if r["kind"] == "posts")
    assert row["sourceId"] == post["id"] and row["canReadSource"] is False
    assert (
        "title" not in str(data)
        and "숨겨진" not in str(data)
        and "비공개 본문" not in str(data)
    )
    assert (
        api(
            admin, co, f"retention-reviews/{row['id']}/source", method="GET"
        ).status_code
        == 404
    )
    assert change(company_env, row, "ARCHIVE_PREPARED").status_code == 404
    assert change(company_env, row, "HELD").status_code == 200
    assert api(staff, co, "retention-reviews", method="GET").status_code == 403
    assert (
        api(
            staff,
            co,
            "retention-reviews/refresh",
            {"expectedVersion": 2, "reason": "권한 없는 갱신"},
        ).status_code
        == 403
    )
    assert (
        admin.get(
            "/api/v1/gw/retention-reviews",
            params={"companyId": co["companyId"], "sourceId": "not-an-id"},
        ).status_code
        == 400
    )
    assert (
        api(admin, co, "retention-reviews/999999999/source", method="GET").status_code
        == 404
    )
    with engine.connect() as c:
        staff_person = c.execute(
            text(
                "SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE'"
            ),
            {"w": co["companyId"], "u": context(engine, staff).user_id},
        ).scalar_one()
    grant = ok(api(admin, co, f"people/{staff_person}/roles", method="GET"))
    ok(
        api(
            admin,
            co,
            f"people/{staff_person}/roles",
            {
                "expectedVersion": grant["version"],
                "roles": grant["roles"] + ["AUDITOR"],
                "reason": "합성 보관 감사 조회",
            },
            method="PATCH",
        )
    )
    assert ok(api(staff, co, "retention-reviews", method="GET"))["total"] == 2
    assert api(staff, co, "retention-events", method="GET").status_code == 200
    assert (
        api(
            staff,
            co,
            f"retention-reviews/{row['id']}/transition",
            {"expectedVersion": 2, "state": "DUE", "reason": "감사 역할 쓰기 거부"},
        ).status_code
        == 403
    )
    selected = admin.get(
        "/api/v1/gw/retention-reviews",
        params={
            "companyId": co["companyId"],
            "sourceId": post["id"],
            "state": "HELD",
            "limit": 1,
        },
    ).json()["data"]
    assert selected["total"] == 1 and selected["items"][0]["id"] == row["id"]
    with engine.connect() as c:
        assert (
            c.execute(
                text("SELECT body FROM gw.board_post WHERE id=:id"),
                {"id": int(post["id"])},
            ).scalar_one()
            == "비공개 본문은 보관 관리자에게 공개하지 않음"
        )


def test_hold_survives_policy_change_and_global_release(company_env, monkeypatch):
    fixture(company_env, monkeypatch)
    _engine, co, admin, _staff = company_env
    ok(refresh(company_env))
    old = next(r for r in entries(company_env)["items"] if r["kind"] == "documents")
    ok(change(company_env, old, "HELD"))
    policy = ok(api(admin, co, "operations", method="GET"))["policy"] | {
        "reason": "합성 새로운 보관 기준",
        "documentReviewMonths": 2,
    }
    ok(api(admin, co, "operating-policies", {"expectedVersion": 2, "policy": policy}))
    ok(refresh(company_env, 3))
    current = next(
        r
        for r in entries(company_env)["items"]
        if r["kind"] == "documents" and r["currentPolicy"]
    )
    assert current["effectiveHold"] is True
    assert change(company_env, current, "ARCHIVE_PREPARED").status_code == 409
    old = next(r for r in entries(company_env)["items"] if r["id"] == old["id"])
    ok(change(company_env, old, "DUE"))
    ok(
        api(
            admin,
            co,
            "retention-company-hold",
            {"expectedVersion": 3, "hold": True, "reason": "합성 회사 조사 보존"},
        )
    )
    assert change(company_env, current, "ARCHIVE_PREPARED").status_code == 409
    assert (
        api(
            admin,
            co,
            "retention-company-hold",
            {"expectedVersion": 3, "hold": False, "reason": "오래된 해제 요청"},
        ).status_code
        == 409
    )
    ok(
        api(
            admin,
            co,
            "retention-company-hold",
            {"expectedVersion": 4, "hold": False, "reason": "합성 보존 종료 검토"},
        )
    )
    ok(change(company_env, current, "ARCHIVE_PREPARED"))
    assert change(company_env, old, "ARCHIVE_PREPARED").status_code == 409
    assert (
        api(
            admin,
            co,
            f"retention-reviews/{current['id']}/transition",
            {
                "expectedVersion": 2,
                "state": "ARCHIVED",
                "reason": "검증 없이 보관 완료",
            },
        ).status_code
        == 400
    )
    assert ok(api(admin, co, "operations", method="GET"))["ready"] is False
    logs = ok(api(admin, co, "retention-events", method="GET"))["items"]
    changes = [r for r in logs if r["action"] == "retention.company_hold.changed"]
    assert [r["hold"] for r in changes] == [False, True]
    assert changes[0]["reason"] == "합성 보존 종료 검토"
    assert any(r["from"] == "HELD" and r["to"] == "DUE" for r in logs)


def test_current_acl_and_fresh_auth_before_receipt_and_row_cas(
    company_env, monkeypatch
):
    fixture(company_env, monkeypatch)
    engine, co, admin, _staff = company_env
    ok(refresh(company_env))
    row = next(r for r in entries(company_env)["items"] if r["kind"] == "posts")
    key = str(uuid4())
    ok(change(company_env, row, "ARCHIVE_PREPARED", key=key))
    assert change(company_env, row, "ARCHIVE_PREPARED", key=key).status_code == 200
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person SET organization_unit_id=NULL WHERE workspace_id=:w AND id=(SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=:u AND state='ACTIVE')"
            ),
            {"w": co["companyId"], "u": context(engine, admin).user_id},
        )
    assert change(company_env, row, "ARCHIVE_PREPARED", key=key).status_code == 404
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp()-interval '6 minutes' WHERE user_id=:u"
            ),
            {"u": context(engine, admin).user_id},
        )
    assert refresh(company_env).status_code == 403
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp() WHERE user_id=:u"
            ),
            {"u": context(engine, admin).user_id},
        )
    row = next(r for r in entries(company_env)["items"] if r["kind"] == "documents")
    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(
            pool.map(
                lambda state: change(company_env, row, state).status_code,
                ["HELD", "ARCHIVE_PREPARED"],
            )
        )
    assert sorted(result) == [200, 409]


def test_due_refresh_is_bounded_and_does_not_duplicate_existing_rows(
    company_env, monkeypatch
):
    from sqlalchemy import inspect

    _doc, post = fixture(company_env, monkeypatch)
    engine, _co, _admin, _staff = company_env
    with engine.begin() as c:
        columns = [
            item["name"]
            for item in inspect(c).get_columns("board_post", schema="gw")
            if item["name"] != "id"
        ]
        select = [
            "n AS serial"
            if col == "serial"
            else "'SYN-BATCH-'||n AS post_no"
            if col == "post_no"
            else "p." + col
            for col in columns
        ]
        c.execute(
            text(
                f"INSERT INTO gw.board_post({','.join(columns)}) SELECT {','.join(select)} FROM gw.board_post p CROSS JOIN generate_series(10000,10200) n WHERE p.id=:id"
            ),
            {"id": int(post["id"])},
        )
    assert ok(refresh(company_env)) == {"added": 200, "hasMore": True}
    assert ok(refresh(company_env)) == {"added": 3, "hasMore": False}
    assert ok(refresh(company_env))["added"] == 0
    assert entries(company_env)["total"] == 203
