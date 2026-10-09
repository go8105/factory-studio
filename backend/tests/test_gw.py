"""FS-030b approval invariants through authenticated APIs, real PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from fs.erp.interface import approval_source_digest

P = "/api/v1/gw"


def call(client, session, method, path, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else P + path,
        json=body,
        headers={
            "X-CSRF-Token": session["csrfToken"],
            "Idempotency-Key": key or str(uuid4()),
        },
    )


def ok(r, status=200):
    assert r.status_code == status, r.text
    return r.json()["data"]


def why(r, name):
    assert r.status_code == 409, r.text
    assert r.json()["error"]["details"]["reason"] == name, r.text


@pytest.fixture
def gw(guest_space):
    c, s, e = guest_space
    people = [
        ok(
            call(
                c, s, "POST", "/people", {"code": code, "name": code, "jobRole": role}
            ),
            201,
        )
        for code, role in [
            ("STAFF", "STAFF"),
            ("TEAM", "MANAGER"),
            ("BOSS", "EXECUTIVE"),
            ("BOARD", "BOARD_ADMIN"),
        ]
    ]
    route = ok(
        call(
            c,
            s,
            "POST",
            "/routes",
            {
                "code": "TEAM-BOSS",
                "name": "팀장 임원",
                "steps": [{"personId": p["id"]} for p in people[1:3]],
            },
        ),
        201,
    )
    return c, s, e, people, route


def new(gw, **overrides):
    c, s, _e, pp, r = gw
    values = {
        "actingPersonId": pp[0]["id"],
        "title": "합성 기안",
        "body": "구매 검토",
        "routeId": r["id"],
        "kind": "GENERAL",
        **overrides,
    }
    return ok(call(c, s, "POST", "/documents", values), 201)


def act(gw, d, action, who=0, **extra):
    c, s, _e, pp, _r = gw
    return call(
        c,
        s,
        "POST",
        f"/documents/{d['id']}/{action}",
        {"actingPersonId": pp[who]["id"], "expectedVersion": d["version"], **extra},
    )


def test_sequential_approval_and_frozen_snapshot(gw):
    c, s, _e, pp, _r = gw
    d = new(gw)
    d = ok(act(gw, d, "submit"))
    why(act(gw, d, "approve", 2), "NOT_CURRENT_STEP")
    why(
        call(
            c,
            s,
            "PATCH",
            f"/documents/{d['id']}",
            {
                "actingPersonId": pp[0]["id"],
                "expectedVersion": d["version"],
                "title": "변조",
                "body": "변조",
            },
        ),
        "IMMUTABLE_DOCUMENT",
    )
    ok(
        call(
            c,
            s,
            "PATCH",
            "/people/" + pp[1]["id"],
            {
                "expectedVersion": 1,
                "name": "새 팀장",
                "jobRole": "MANAGER",
                "isActive": True,
            },
        )
    )
    d = ok(act(gw, d, "approve", 1))
    assert d["steps"][0]["personName"] == "TEAM"
    why(act(gw, d, "withdraw", reason="회수 요청"), "WITHDRAW_NOT_ALLOWED")
    d = ok(act(gw, d, "approve", 2))
    assert d["status"] == "APPROVED"
    assert len(d["events"]) == 4
    assert all("actorKey" not in ev for ev in d["events"])
    why(act(gw, d, "resubmit"), "IMMUTABLE_DOCUMENT")


def test_reject_resubmit_preserves_previous(gw):
    c, _s, _e, _pp, _r = gw
    d = ok(act(gw, new(gw), "submit"))
    assert act(gw, d, "reject", 1, reason=" ").status_code == 400
    d = ok(act(gw, d, "reject", 1, reason="보완 필요"))
    assert d["steps"][1]["status"] == "SKIPPED"
    n = ok(act(gw, d, "resubmit"))
    assert n["previousDocumentId"] == d["id"]
    assert n["roundNo"] == 2
    why(act(gw, d, "resubmit"), "SUCCESSOR_EXISTS")
    old = ok(c.get(P + "/documents/" + d["id"]))
    assert old["version"] == d["version"]
    assert old["status"] == "REJECTED"
    assert n["events"][0]["eventType"] == "RESUBMISSION_CREATED"


def test_idempotent_approval_and_changed_request(gw):
    c, s, _e, pp, _r = gw
    d = ok(act(gw, new(gw), "submit"))
    body = {"actingPersonId": pp[1]["id"], "expectedVersion": d["version"]}
    path = f"/documents/{d['id']}/approve"
    a = call(c, s, "POST", path, body, "same")
    b = call(c, s, "POST", path, body, "same")
    assert a.status_code == b.status_code == 200
    assert a.json() == b.json()
    assert (
        call(c, s, "POST", path, {**body, "reason": "다른 본문"}, "same").status_code
        == 422
    )
    why(act(gw, d, "approve", 1), "VERSION_CONFLICT")


def test_concurrent_approve_and_withdraw(gw):
    c, s, _e, pp, _r = gw
    d = ok(act(gw, new(gw), "submit"))

    def run(action, who):
        with TestClient(c.app, base_url=str(c.base_url)) as client:
            client.cookies.update(c.cookies)
            return call(
                client,
                s,
                "POST",
                f"/documents/{d['id']}/{action}",
                {
                    "actingPersonId": pp[who]["id"],
                    "expectedVersion": d["version"],
                    "reason": "경합 검사",
                },
            )

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run, "approve", 1), pool.submit(run, "withdraw", 0)]
        results = [f.result() for f in futures]
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (
        len(
            [
                e
                for e in ok(c.get(P + "/documents/" + d["id"]))["events"]
                if e["eventType"] != "SKIPPED"
            ]
        )
        == 3
    )


def test_route_validation_and_self_approval(gw):
    c, s, _e, pp, r = gw
    for ids in [[], [pp[1]["id"]] * 2, [p["id"] for p in pp]]:
        res = call(
            c,
            s,
            "POST",
            "/routes",
            {"code": "BAD", "name": "실패", "steps": [{"personId": i} for i in ids]},
        )
        assert res.status_code == 400, res.text
    res = call(
        c,
        s,
        "POST",
        "/documents",
        {
            "actingPersonId": pp[1]["id"],
            "routeId": r["id"],
            "title": "자기",
            "body": "결재",
            "kind": "GENERAL",
        },
    )
    assert res.status_code == 400


def test_person_use_and_last_admin(gw):
    c, s, _e, pp, _r = gw
    d = new(gw)

    def disable(p):
        return call(
            c,
            s,
            "PATCH",
            "/people/" + p["id"],
            {
                "expectedVersion": p["version"],
                "name": p["name"],
                "jobRole": p["jobRole"],
                "isActive": False,
            },
        )

    why(disable(pp[0]), "PERSON_IN_USE")
    why(disable(pp[3]), "LAST_BOARD_ADMIN")
    d = ok(act(gw, d, "submit"))
    why(disable(pp[1]), "PERSON_IN_USE")


def test_post_lifecycle_plain_text_and_author(gw):
    c, s, _e, pp, _r = gw
    body = {
        "actingPersonId": pp[0]["id"],
        "boardKind": "NOTICE",
        "title": "공지",
        "body": "<script>alert(1)</script>",
    }
    why(call(c, s, "POST", "/posts", body), "WRONG_ACTOR")
    p = ok(call(c, s, "POST", "/posts", {**body, "actingPersonId": pp[3]["id"]}), 201)

    def postact(p, a, **extra):
        return call(
            c,
            s,
            "POST",
            f"/posts/{p['id']}/{a}",
            {"actingPersonId": pp[3]["id"], "expectedVersion": p["version"], **extra},
        )

    p = ok(postact(p, "publish"))
    why(
        call(
            c,
            s,
            "PATCH",
            "/posts/" + p["id"],
            {
                "actingPersonId": pp[3]["id"],
                "expectedVersion": p["version"],
                "title": "변조",
                "body": "변조",
            },
        ),
        "IMMUTABLE_DOCUMENT",
    )
    n = ok(postact(p, "correct"))
    assert n["previousPostId"] == p["id"]
    assert n["body"] == body["body"]
    why(postact(p, "correct"), "SUCCESSOR_EXISTS")
    assert postact(p, "withdraw", reason=" ").status_code == 400
    p = ok(postact(p, "withdraw", reason="게시 철회"))
    assert p["status"] == "WITHDRAWN"
    assert p["body"] == body["body"]


def test_erp_changed_refresh_duplicate_and_disabled(gw):
    c, s, e, _pp, _r = gw
    candidates = ok(c.get(P + "/sources"))["rows"]
    assert candidates
    no = candidates[0]["documentNo"]
    d = new(gw, kind="ERP_PURCHASE", sourceNo=no)
    other = new(gw, kind="ERP_PURCHASE", sourceNo=no)
    with e.begin() as conn:
        conn.execute(
            text(
                "UPDATE erp.purchase_invoice SET total_amount=total_amount+1,supply_amount=supply_amount+1 WHERE workspace_id=:w AND generation_id=:g AND invoice_no=:no"
            ),
            {"w": s["workspaceId"], "g": s["generationId"], "no": no},
        )
    why(act(gw, d, "submit"), "SOURCE_CHANGED")
    d = ok(act(gw, d, "refresh-source"))
    d = ok(act(gw, d, "submit"))
    other = ok(act(gw, other, "refresh-source"))
    why(act(gw, other, "submit"), "ACTIVE_APPROVAL_EXISTS")
    ok(call(c, s, "PATCH", "/api/v1/core/workspace/modules/erp", {"enabled": False}))
    why(act(gw, other, "submit"), "SOURCE_MODULE_DISABLED")
    assert (
        ok(c.get(P + "/documents/" + d["id"]))["sourceComparison"]["availability"]
        == "DISABLED"
    )
    d = ok(act(gw, d, "approve", 1))
    assert d["status"] == "IN_REVIEW"
    assert ok(act(gw, new(gw), "submit"))["status"] == "IN_REVIEW"


def test_auth_extra_fields_precision_and_pagination(gw):
    c, s, _e, pp, _r = gw
    assert (
        c.post(
            P + "/people", json={"code": "NO", "name": "No", "jobRole": "STAFF"}
        ).status_code
        == 403
    )
    res = call(
        c,
        s,
        "POST",
        "/people",
        {"code": "NO", "name": "No", "jobRole": "STAFF", "actorKey": "forged"},
    )
    assert res.status_code == 400
    assert c.get(P + "/documents?limit=101").status_code == 400
    assert c.get(P + "/documents?sort=body;drop").status_code == 400
    d = new(gw, amount="1234567890123456.78", currency="KRW")
    assert d["amount"] == "1234567890123456.78"
    assert ok(c.get(P + "/documents?box=drafts&personId=" + pp[0]["id"]))["total"] == 1
    assert c.get(P + "/documents?box=drafts").status_code == 400


def test_other_workspace_and_old_generation_ids(gw):
    c, s, _e, pp, r = gw
    d = new(gw)
    with TestClient(c.app, base_url=str(c.base_url)) as other:
        other_s = ok(
            other.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "격리-" + uuid4().hex[:8]},
                headers={"Idempotency-Key": str(uuid4())},
            ),
            201,
        )
        assert other.get(P + "/documents/" + d["id"]).status_code == 404
        assert (
            call(
                other,
                other_s,
                "POST",
                "/documents",
                {
                    "actingPersonId": pp[0]["id"],
                    "title": "침범",
                    "body": "차단",
                    "routeId": r["id"],
                    "kind": "GENERAL",
                },
            ).status_code
            == 404
        )
    ok(call(c, s, "POST", "/api/v1/core/workspace/generations", {}), 201)
    assert c.get(P + "/documents/" + d["id"]).status_code == 404


def test_digest_excludes_display():
    a = {
        "schemaVersion": 1,
        "documentNo": "PI",
        "totalAmount": "10.00",
        "display": {"invoiceDate": "2026-01-01"},
    }
    b = {**a, "display": {"invoiceDate": "2026-02-01"}}
    assert approval_source_digest(a) == approval_source_digest(b)
    assert approval_source_digest(a) != approval_source_digest(
        {**b, "totalAmount": "11.00"}
    )


def test_badge_latest_submission_and_no_erp_writes(gw):
    c, s, e, _pp, _r = gw
    no = ok(c.get(P + "/sources"))["rows"][0]["documentNo"]
    with e.connect() as cn:
        invoice_id = cn.execute(
            text(
                "SELECT id FROM erp.purchase_invoice WHERE workspace_id=:w AND generation_id=:g AND invoice_no=:no"
            ),
            {"w": s["workspaceId"], "g": s["generationId"], "no": no},
        ).scalar_one()
        before = cn.execute(
            text(
                "SELECT row_to_json(p)::text FROM erp.purchase_invoice p WHERE id=:id"
            ),
            {"id": invoice_id},
        ).scalar_one()
    path = f"/api/v1/erp/purchase-invoices/{invoice_id}/gw-approval"
    assert ok(c.get(path))["approval"] is None
    d = new(gw, kind="ERP_PURCHASE", sourceNo=no)
    assert ok(c.get(path))["approval"] is None
    d = ok(act(gw, d, "submit"))
    assert ok(c.get(path))["approval"]["id"] == d["id"]
    d = ok(act(gw, d, "approve", 1))
    d = ok(act(gw, d, "approve", 2))
    assert ok(c.get(path))["approval"]["status"] == "APPROVED"
    n = ok(act(gw, new(gw, kind="ERP_PURCHASE", sourceNo=no), "submit"))
    assert ok(c.get(path))["approval"]["id"] == n["id"]
    with e.connect() as cn:
        assert (
            cn.execute(
                text(
                    "SELECT row_to_json(p)::text FROM erp.purchase_invoice p WHERE id=:id"
                ),
                {"id": invoice_id},
            ).scalar_one()
            == before
        )
    ok(call(c, s, "PATCH", "/api/v1/core/workspace/modules/gw", {"enabled": False}))
    assert ok(c.get(path)) == {"enabled": False, "approval": None}


@pytest.mark.parametrize(
    "actions,actors",
    [(["approve", "approve"], [1, 1]), (["approve", "reject"], [1, 1])],
)
def test_concurrent_decisions_one_event(gw, actions, actors):
    c, s, _e, pp, _r = gw
    d = ok(act(gw, new(gw), "submit"))

    def run(a, i):
        with TestClient(c.app, base_url=str(c.base_url)) as client:
            client.cookies.update(c.cookies)
            return call(
                client,
                s,
                "POST",
                f"/documents/{d['id']}/{a}",
                {
                    "actingPersonId": pp[i]["id"],
                    "expectedVersion": d["version"],
                    "reason": "동시 검토",
                },
            )

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run, a, i) for a, i in zip(actions, actors)]
        assert sorted(f.result().status_code for f in futures) == [200, 409]
    assert (
        len(
            [
                e
                for e in ok(c.get(P + "/documents/" + d["id"]))["events"]
                if e["eventType"] != "SKIPPED"
            ]
        )
        == 3
    )


def test_same_source_concurrent_submission(gw):
    c, s, _e, pp, _r = gw
    no = ok(c.get(P + "/sources"))["rows"][0]["documentNo"]
    dd = [new(gw, kind="ERP_PURCHASE", sourceNo=no) for _ in range(2)]

    def run(d):
        with TestClient(c.app, base_url=str(c.base_url)) as client:
            client.cookies.update(c.cookies)
            return call(
                client,
                s,
                "POST",
                f"/documents/{d['id']}/submit",
                {"actingPersonId": pp[0]["id"], "expectedVersion": d["version"]},
            )

    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(run, d) for d in dd]
        responses = [f.result() for f in futures]
    assert sorted(r.status_code for r in responses) == [200, 409]
    why(next(r for r in responses if r.status_code == 409), "ACTIVE_APPROVAL_EXISTS")


@pytest.mark.parametrize("count", [1, 3])
def test_one_and_three_step_routes(gw, count):
    c, s, _e, pp, _r = gw
    route = ok(
        call(
            c,
            s,
            "POST",
            "/routes",
            {
                "code": "STEPS",
                "name": "단계",
                "steps": [{"personId": p["id"]} for p in pp[1 : count + 1]],
            },
        ),
        201,
    )
    d = ok(act(gw, new(gw, routeId=route["id"]), "submit"))
    for i in range(1, count + 1):
        d = ok(act(gw, d, "approve", i))
    assert d["status"] == "APPROVED"


def test_template_change_does_not_change_draft_steps(gw):
    c, s, _e, pp, r = gw
    d = new(gw)
    ok(
        call(
            c,
            s,
            "PATCH",
            "/routes/" + r["id"],
            {
                "expectedVersion": 1,
                "name": "변경",
                "isActive": True,
                "steps": [{"personId": pp[2]["id"]}],
            },
        )
    )
    d = ok(act(gw, d, "submit"))
    assert len(d["steps"]) == 2
    n = new(gw)
    assert len(n["steps"]) == 1


def test_erp_status_changed_cancelled_missing(gw):
    c, s, e, _pp, _r = gw
    no = next(
        v["documentNo"]
        for v in ok(c.get(P + "/sources"))["rows"]
        if v["status"] == "draft"
    )
    d = new(gw, kind="ERP_PURCHASE", sourceNo=no)
    d = ok(act(gw, d, "submit"))
    with e.begin() as cn:
        cn.execute(
            text(
                "UPDATE erp.purchase_invoice SET status='cancelled',cancelled_at=clock_timestamp(),cancel_reason='합성 취소' WHERE workspace_id=:w AND generation_id=:g AND invoice_no=:no"
            ),
            {"w": s["workspaceId"], "g": s["generationId"], "no": no},
        )
    detail = ok(c.get(P + "/documents/" + d["id"]))
    assert detail["sourceComparison"]["currentStatus"] == "cancelled"
    assert detail["sourceComparison"]["statusChanged"] is True
    d = ok(act(gw, d, "reject", 1, reason="원문 취소"))
    n = ok(act(gw, d, "resubmit"))
    why(act(gw, n, "submit"), "SOURCE_CANCELLED")
    with e.begin() as cn:
        cn.execute(
            text(
                "UPDATE erp.purchase_invoice SET invoice_no='RENAMED' WHERE workspace_id=:w AND generation_id=:g AND invoice_no=:no"
            ),
            {"w": s["workspaceId"], "g": s["generationId"], "no": no},
        )
    assert (
        ok(c.get(P + "/documents/" + d["id"]))["sourceComparison"]["availability"]
        == "MISSING"
    )
    why(act(gw, n, "submit"), "SOURCE_MISSING")


def test_erp_amount_injection_and_audit(gw):
    c, s, e, pp, r = gw
    no = ok(c.get(P + "/sources"))["rows"][0]["documentNo"]
    res = call(
        c,
        s,
        "POST",
        "/documents",
        {
            "actingPersonId": pp[0]["id"],
            "routeId": r["id"],
            "title": "변조",
            "body": "금액",
            "kind": "ERP_PURCHASE",
            "sourceNo": no,
            "amount": "1.00",
            "currency": "KRW",
        },
    )
    assert res.status_code == 400
    d = ok(act(gw, new(gw), "submit"))
    with e.connect() as cn:
        records = (
            cn.execute(
                text(
                    "SELECT summary FROM core.audit_event WHERE workspace_id=:w AND action LIKE 'gw.%'"
                ),
                {"w": s["workspaceId"]},
            )
            .scalars()
            .all()
        )
        assert records and all("body" not in x for x in records)
        event = cn.execute(
            text(
                "SELECT actor_key,actor_kind FROM gw.approval_event WHERE document_id=:id ORDER BY event_seq DESC LIMIT 1"
            ),
            {"id": int(d["id"])},
        ).one()
        assert event.actor_kind == "GUEST" and event.actor_key
