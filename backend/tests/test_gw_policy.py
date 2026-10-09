"""GW-b v2 API policies, scoped real PostgreSQL, boundary and concurrency checks."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from tests.test_gw import P, call, ok, why

SEEDS = ()
EMPTY_MODULES = ("gw",)


@pytest.fixture
def space(guest_space):
    c, s, e = guest_space
    pp = [
        ok(
            call(
                c,
                s,
                "POST",
                "/people",
                {"code": f"P{i}", "name": f"합성 담당자 {i}", "jobRole": "STAFF"},
            ),
            201,
        )
        for i in range(8)
    ]
    return c, s, e, pp


def route(z, entries=None):
    c, s, _e, p = z
    return ok(
        call(
            c,
            s,
            "POST",
            "/routes",
            {
                "code": "R" + uuid4().hex[:12].upper(),
                "name": "검토 결재선",
                "steps": entries
                or [
                    {"personId": p[1]["id"], "seq": 1},
                    {"personId": p[2]["id"], "seq": 2},
                ],
            },
        ),
        201,
    )


def draft(z, r=None, **extra):
    c, s, _e, p = z
    return ok(
        call(
            c,
            s,
            "POST",
            "/documents",
            {
                "actingPersonId": p[0]["id"],
                "kind": "GENERAL",
                "title": "합성 검토",
                "body": "테스트 기안",
                "routeId": (r or route(z))["id"],
                **extra,
            },
        ),
        201,
    )


def act(z, d, a, i=0, key=None, **extra):
    c, s, _e, p = z
    return call(
        c,
        s,
        "POST",
        f"/documents/{d['id']}/{a}",
        {"actingPersonId": p[i]["id"], "expectedVersion": d["version"], **extra},
        key,
    )


def rule(z, **extra):
    c, s, _e, _p = z
    return call(
        c,
        s,
        "POST",
        "/authority-rules",
        {
            "code": "A" + uuid4().hex[:12].upper(),
            "documentKind": "GENERAL",
            "finalSeq": 1,
            "effectiveFrom": datetime.now(ZoneInfo("Asia/Seoul")).strftime("%Y-%m"),
            **extra,
        },
    )


def grant(z, owner=1, delegate=6, **extra):
    c, s, _e, p = z
    t = datetime.now(UTC)
    return call(
        c,
        s,
        "POST",
        "/delegations",
        {
            "actingPersonId": p[owner]["id"],
            "delegatePersonId": p[delegate]["id"],
            "startsAt": (t - timedelta(days=1)).isoformat(),
            "endsAt": (t + timedelta(days=1)).isoformat(),
            "reason": "휴가 검토",
            "documentKind": None,
            "maxAmount": None,
            **extra,
        },
    )


def detail(z, d, i=0):
    return ok(z[0].get(f"{P}/documents/{d['id']}?personId={z[3][i]['id']}"))


def test_parallel_consent_reference_progress_and_frozen_route(space):
    z = space
    p = z[3]
    r = route(
        z,
        [
            {"personId": p[i]["id"], "seq": 1, "participantRole": role}
            for i, role in [
                (1, "APPROVER"),
                (2, "APPROVER"),
                (3, "CONSENT"),
                (4, "REFERENCE"),
            ]
        ]
        + [{"personId": p[5]["id"], "seq": 2}],
    )
    d = ok(act(z, draft(z, r), "submit"))
    assert d["policyVersion"] == 2
    why(act(z, d, "approve", 0), "NOT_CURRENT_STEP")
    d = ok(act(z, d, "reference", 4, reason="참고 검토"))
    assert d["currentStep"] == 1
    d = ok(act(z, d, "approve", 1))
    assert d["currentStep"] == 1
    d = ok(act(z, d, "approve", 2))
    assert d["currentStep"] == 1
    d = ok(act(z, d, "consent", 3))
    assert d["currentStep"] == 2
    assert [e["eventType"] for e in d["events"]][-3:] == [
        "APPROVED",
        "APPROVED",
        "CONSENTED",
    ]
    d = ok(act(z, d, "approve", 5))
    assert d["status"] == "APPROVED"
    assert len([s for s in d["steps"] if s["participantRole"] == "APPROVER"]) == 3


def test_reference_not_required_and_opposition_terminal(space):
    z = space
    p = z[3]
    r = route(
        z,
        [
            {"personId": p[1]["id"], "seq": 1},
            {"personId": p[3]["id"], "seq": 1, "participantRole": "REFERENCE"},
        ],
    )
    d = ok(act(z, draft(z, r), "submit"))
    d = ok(act(z, d, "approve", 1))
    assert d["status"] == "APPROVED"
    assert d["steps"][1]["status"] == "SKIPPED"
    r = route(
        z,
        [
            {"personId": p[1]["id"], "seq": 1},
            {"personId": p[3]["id"], "seq": 1, "participantRole": "CONSENT"},
            {"personId": p[2]["id"], "seq": 2},
        ],
    )
    d = ok(act(z, draft(z, r), "submit"))
    d = ok(act(z, d, "oppose", 3, reason="예산 재검토"))
    assert d["status"] == "REJECTED"
    assert d["events"][2]["eventType"] == "OPPOSED"


@pytest.mark.parametrize(
    "entries",
    [
        [(1, 2, "APPROVER")],
        [(1, 1, "CONSENT")],
        [(1, 1, "APPROVER"), (1, 2, "APPROVER")],
    ],
)
def test_invalid_route_stages_roles_duplicates(space, entries):
    z = space
    p = z[3]
    r = call(
        z[0],
        z[1],
        "POST",
        "/routes",
        {
            "code": "BAD",
            "name": "잘못된 결재선",
            "steps": [
                {"personId": p[i]["id"], "seq": seq, "participantRole": role}
                for i, seq, role in entries
            ],
        },
    )
    assert r.status_code == 400, r.text


@pytest.mark.parametrize(
    "amount,expected", [("0", True), ("999.99", True), ("1000", False)]
)
def test_authority_half_open_amount_freeze_and_unused_stages(space, amount, expected):
    z = space
    a = ok(rule(z, amountFrom="0", amountTo="1000"), 201)
    d = ok(act(z, draft(z, amount=amount, currency="KRW"), "submit"))
    assert (d["authorityRuleId"] is not None) == expected
    if expected:
        assert d["authoritySnapshot"]["code"] == a["code"]
        assert d["steps"][1]["status"] == "SKIPPED"
        why(
            call(
                z[0],
                z[1],
                "PATCH",
                f"/authority-rules/{a['id']}",
                {"expectedVersion": a["version"], "finalSeq": 2},
            ),
            "AUTHORITY_IN_USE",
        )
        ok(
            call(
                z[0],
                z[1],
                "PATCH",
                f"/authority-rules/{a['id']}",
                {"expectedVersion": a["version"], "isActive": False},
            )
        )
        assert detail(z, d)["authoritySnapshot"]["finalSeq"] == 1
        why(
            call(z[0], z[1], "DELETE", f"/authority-rules/{a['id']}"),
            "AUTHORITY_IN_USE",
        )
        d = ok(act(z, d, "approve", 1))
        assert d["status"] == "APPROVED"
    else:
        assert d["steps"][1]["status"] == "WAITING"


def test_authority_overlap_adjacent_currency_and_period(space):
    z = space
    ok(rule(z, amountFrom="0", amountTo="100", effectiveTo="2098-12"), 201)
    why(rule(z, amountFrom="99", amountTo="200"), "AUTHORITY_OVERLAP")
    ok(rule(z, amountFrom="100", amountTo="200", effectiveTo="2098-12"), 201)
    ok(rule(z, currency="USD", amountTo="100", effectiveTo="2098-12"), 201)
    ok(rule(z, effectiveFrom="2099-01", effectiveTo="2099-02", amountTo="100"), 201)
    d = ok(act(z, draft(z), "submit"))
    assert d["authorityRuleId"] is None


def test_legacy_policy_ignores_new_rules_and_delegation(space):
    z = space
    ok(rule(z), 201)
    ok(grant(z), 201)
    d = draft(z)
    with z[2].begin() as c:
        c.execute(
            text(
                "UPDATE gw.approval_document SET policy_version=1 WHERE id=:id AND workspace_id=:w AND generation_id=:g"
            ),
            {"id": int(d["id"]), "w": z[1]["workspaceId"], "g": z[1]["generationId"]},
        )
    d = ok(act(z, d, "submit"))
    assert d["authorityRuleId"] is None
    assert d["policyVersion"] == 1
    why(act(z, d, "approve", 6), "NOT_CURRENT_STEP")
    d = ok(act(z, d, "approve", 1))
    d = ok(act(z, d, "approve", 2))
    assert d["status"] == "APPROVED"


def test_delegation_original_actual_actor_and_pending_box(space):
    z = space
    g = ok(grant(z, maxAmount="100", documentKind="GENERAL"), 201)
    d = ok(act(z, draft(z, amount="100", currency="KRW"), "submit"))
    rows = ok(z[0].get(f"{P}/documents?box=pending&personId={z[3][6]['id']}"))["rows"]
    assert [r["id"] for r in rows] == [d["id"]]
    assert "approve" in detail(z, d, 6)["availableActions"]
    d = ok(act(z, d, "approve", 6))
    ev = d["events"][-1]
    assert ev["personId"] == z[3][6]["id"]
    assert ev["onBehalfOfPersonId"] == z[3][1]["id"]
    assert ev["details"]["delegationId"] == g["id"]
    assert d["steps"][0]["personId"] == z[3][1]["id"]


@pytest.mark.parametrize(
    "amount,currency,kind",
    [
        ("101", "KRW", "GENERAL"),
        (None, None, "GENERAL"),
        ("100", "USD", "GENERAL"),
        ("100", "KRW", "ERP_PURCHASE"),
    ],
)
def test_delegation_limit_currency_kind(space, amount, currency, kind):
    z = space
    ok(grant(z, maxAmount="100", documentKind=kind), 201)
    d = ok(act(z, draft(z, amount=amount, currency=currency), "submit"))
    why(act(z, d, "approve", 6), "NOT_CURRENT_STEP")


def test_expired_future_revoked_chain_and_self_delegation(space):
    z = space
    t = datetime.now(UTC)
    assert grant(z, delegate=1).status_code == 400
    g = ok(
        grant(
            z,
            startsAt=(t - timedelta(days=2)).isoformat(),
            endsAt=(t - timedelta(days=1)).isoformat(),
        ),
        201,
    )
    d = ok(act(z, draft(z), "submit"))
    why(act(z, d, "approve", 6), "NOT_CURRENT_STEP")
    g = ok(
        grant(
            z,
            startsAt=(t + timedelta(days=1)).isoformat(),
            endsAt=(t + timedelta(days=2)).isoformat(),
        ),
        201,
    )
    why(act(z, d, "approve", 6), "NOT_CURRENT_STEP")
    g = ok(grant(z), 201)
    why(grant(z, owner=6, delegate=7), "DELEGATION_OVERLAP_OR_CHAIN")
    why(
        call(
            z[0],
            z[1],
            "POST",
            f"/delegations/{g['id']}/revoke",
            {"actingPersonId": z[3][6]["id"], "expectedVersion": g["version"]},
        ),
        "WRONG_ACTOR",
    )
    ok(
        call(
            z[0],
            z[1],
            "POST",
            f"/delegations/{g['id']}/revoke",
            {"actingPersonId": z[3][1]["id"], "expectedVersion": g["version"]},
        )
    )
    why(act(z, d, "approve", 6), "NOT_CURRENT_STEP")


def test_delegate_drafter_and_other_participant_forbidden(space):
    z = space
    ok(grant(z, delegate=0), 201)
    d = ok(act(z, draft(z), "submit"))
    why(act(z, d, "approve", 0), "NOT_CURRENT_STEP")
    ok(grant(z, owner=2, delegate=1), 201)
    d = ok(act(z, d, "approve", 1))
    why(act(z, d, "approve", 1), "NOT_CURRENT_STEP")


def test_multiple_assignments_require_step_and_idempotent_replay(space):
    z = space
    p = z[3]
    ok(grant(z), 201)
    ok(grant(z, owner=2), 201)
    r = route(z, [{"personId": p[i]["id"], "seq": 1} for i in (1, 2)])
    d = ok(act(z, draft(z, r), "submit"))
    why(act(z, d, "approve", 6), "ASSIGNMENT_REQUIRED")
    key = str(uuid4())
    r = act(z, d, "approve", 6, key, stepId=d["steps"][0]["id"])
    first = ok(r)
    again = ok(act(z, d, "approve", 6, key, stepId=d["steps"][0]["id"]))
    assert again == first
    d = ok(act(z, first, "approve", 6))
    assert d["status"] == "APPROVED"
    assert len([e for e in d["events"] if e["eventType"] == "APPROVED"]) == 2


def test_resubmit_recalculates_authority_without_rewriting_history(space):
    z = space
    a = ok(rule(z), 201)
    d = ok(act(z, draft(z, amount="10", currency="KRW"), "submit"))
    d = ok(act(z, d, "reject", 1, reason="재검토 필요"))
    original = detail(z, d)
    ok(
        call(
            z[0],
            z[1],
            "PATCH",
            f"/authority-rules/{a['id']}",
            {"expectedVersion": a["version"], "isActive": False},
        )
    )
    n = ok(act(z, d, "resubmit"))
    n = ok(act(z, n, "submit"))
    assert n["authorityRuleId"] is None
    assert n["steps"][1]["status"] == "WAITING"
    old = detail(z, d)
    assert old["authoritySnapshot"] == original["authoritySnapshot"]
    assert old["steps"] == original["steps"]


def test_unimplemented_source_contract_is_explicit(space):
    z = space
    for kind in ("PURCHASE_ORDER", "EXPENSE_CLAIM", "ECO"):
        data = ok(z[0].get(f"{P}/sources?kind={kind}"))
        assert data["availability"] == "UNIMPLEMENTED"
        assert data["enabled"] is False


def test_concurrent_parallel_decisions_version_retry(space):
    z = space
    p = z[3]
    r = route(z, [{"personId": p[i]["id"], "seq": 1} for i in (1, 2)])
    d = ok(act(z, draft(z, r), "submit"))

    def run(i):
        with TestClient(z[0].app, base_url=str(z[0].base_url)) as c:
            c.cookies.update(z[0].cookies)
            return call(
                c,
                z[1],
                "POST",
                f"/documents/{d['id']}/approve",
                {"actingPersonId": p[i]["id"], "expectedVersion": d["version"]},
            )

    with ThreadPoolExecutor(2) as pool:
        result = list(pool.map(run, (1, 2)))
    assert sorted(r.status_code for r in result) == [200, 409]
    now = detail(z, d)
    remaining = next(s for s in now["steps"] if s["status"] == "WAITING")
    i = next(i for i, p in enumerate(p) if p["id"] == remaining["personId"])
    now = ok(act(z, now, "approve", i))
    assert now["status"] == "APPROVED"
