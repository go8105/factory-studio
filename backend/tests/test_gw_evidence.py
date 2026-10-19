"""Signed evidence scope, immutable failures, current policy and authorization."""

# ruff: noqa: F401,F811
import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text
from test_gw_company import context
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env

from fs.gw.operating_contract import OperatingPolicy, canonical


def prepare(env, monkeypatch):
    engine, co, admin, _staff = env
    person = initialize(env)
    connect_staff(env)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET assurance='MFA',verified_at=clock_timestamp() WHERE user_id=:u AND revoked_at IS NULL"
            ),
            {"u": context(engine, admin).user_id},
        )
    policy = OperatingPolicy(
        responsiblePersonId=str(person), reason="합성 실행 증거 기준"
    )
    assert (
        api(
            admin,
            co,
            "operating-policies",
            {"expectedVersion": 0, "policy": policy.model_dump(by_alias=True)},
        ).status_code
        == 200
    )
    private = Ed25519PrivateKey.generate()
    import json

    monkeypatch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps(
            {
                "runner": base64.b64encode(
                    private.public_key().public_bytes_raw()
                ).decode()
            }
        ),
    )
    monkeypatch.setenv("FS_CODE_REVISION", "abcdef012345")
    with engine.connect() as c:
        head = c.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    with engine.connect() as c:
        generation = c.execute(
            text(
                "SELECT generation_id FROM gw.operating_settings WHERE workspace_id=:w"
            ),
            {"w": co["companyId"]},
        ).scalar_one()
    now = datetime.now(UTC) - timedelta(seconds=5)
    body = {
        "version": 1,
        "runId": str(uuid4()),
        "workspaceId": str(co["companyId"]),
        "generationId": str(generation),
        "policyDigest": policy.digest(),
        "kind": "BACKUP",
        "startedAt": (now - timedelta(seconds=10)).isoformat(),
        "finishedAt": now.isoformat(),
        "codeRevision": "abcdef012345",
        "dbRevision": head,
        "manifestDigest": "a" * 64,
        "result": "PASS",
        "signerKeyId": "runner",
        "metrics": {
            "snapshotStartedAt": (now - timedelta(seconds=9)).isoformat(),
            "storageConfirmedAt": now.isoformat(),
            "artifactDigest": "b" * 64,
        },
    }

    def signed(data):
        return {
            "envelope": data,
            "signature": base64.b64encode(private.sign(canonical(data))).decode(),
        }

    return body, signed


def test_signed_evidence_records_failures_and_rejects_replay_or_forgery(
    company_env, monkeypatch
):
    body, signed = prepare(company_env, monkeypatch)
    _engine, co, admin, _staff = company_env
    key = str(uuid4())
    first = api(admin, co, "operating-evidence", signed(body), key=key)
    assert first.status_code == 200, first.text
    assert (
        api(admin, co, "operating-evidence", signed(body), key=key).json()
        == first.json()
    )
    assert api(admin, co, "operating-evidence", signed(body)).status_code == 409
    assert api(_staff, co, "operating-evidence", signed(body)).status_code == 403
    assert api(_staff, co, "operating-evidence", method="GET").status_code == 403
    state = api(admin, co, "operations", method="GET").json()["data"]
    assert state["evidenceChecks"][0]["state"] == "RECORDED_PASS"
    assert state["evidenceChecks"][0]["signatureVerified"]
    assert state["evidenceChecks"][1]["state"] == "MISSING"
    assert not state["ready"]

    tampered = signed(body)
    tampered["envelope"] = body | {"runId": str(uuid4())}
    assert api(admin, co, "operating-evidence", tampered).status_code == 400
    assert (
        api(
            admin,
            co,
            "operating-evidence",
            signed(body | {"runId": str(uuid4()), "workspaceId": "999999"}),
        ).status_code
        == 400
    )
    assert (
        api(
            admin,
            co,
            "operating-evidence",
            signed(
                body
                | {
                    "runId": str(uuid4()),
                    "result": "FAIL",
                    "metrics": {"failedCheckCount": 2},
                }
            ),
        ).status_code
        == 200
    )
    state = api(admin, co, "operations", method="GET").json()["data"]
    assert state["evidenceChecks"][0]["state"] == "FAILED"
    assert not state["evidenceIntegrityReverified"] and not state["ready"]
    history = api(admin, co, "operating-evidence", method="GET").json()["data"]
    assert history["total"] == 2
    assert [r["result"] for r in history["items"]] == ["FAIL", "PASS"]
    assert all(r["currentPolicy"] for r in history["items"])
    assert api(admin, co, "operations", method="GET").json()["data"]["ready"] is False


def test_evidence_current_policy_keys_and_fresh_auth_before_receipt(
    company_env, monkeypatch
):
    body, signed = prepare(company_env, monkeypatch)
    engine, co, admin, _staff = company_env
    key = str(uuid4())
    assert (
        api(admin, co, "operating-evidence", signed(body), key=key).status_code == 200
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp()-interval '6 minutes' WHERE user_id=:u"
            ),
            {"u": context(engine, admin).user_id},
        )
    assert (
        api(admin, co, "operating-evidence", signed(body), key=key).status_code == 403
    )
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET verified_at=clock_timestamp() WHERE user_id=:u"
            ),
            {"u": context(engine, admin).user_id},
        )
    person = OperatingPolicy.model_validate(
        {
            "responsiblePersonId": api(admin, co, "operations", method="GET").json()[
                "data"
            ]["policy"]["responsiblePersonId"],
            "reason": "합성 새로운 기준",
            "rpoMinutes": 90,
        }
    )
    assert (
        api(
            admin,
            co,
            "operating-policies",
            {"expectedVersion": 1, "policy": person.model_dump(by_alias=True)},
        ).status_code
        == 200
    )
    assert (
        api(
            admin, co, "operating-evidence", signed(body | {"runId": str(uuid4())})
        ).status_code
        == 400
    )
    assert (
        api(admin, co, "operating-evidence", method="GET").json()["data"]["items"][0][
            "currentPolicy"
        ]
        is False
    )
    monkeypatch.delenv("FS_GW_EVIDENCE_PUBLIC_KEYS")
    assert (
        api(
            admin, co, "operating-evidence", signed(body | {"runId": str(uuid4())})
        ).status_code
        == 503
    )


def test_retained_original_and_row_tamper_are_rechecked(company_env, monkeypatch):
    import json

    from fs.gw.readiness import SOURCE_FIELD

    body, signed = prepare(company_env, monkeypatch)
    engine, co, admin, _staff = company_env
    assert api(admin, co, "operating-evidence", signed(body)).status_code == 200
    with engine.connect() as c:
        stored = c.execute(
            text("SELECT metrics FROM gw.operating_evidence WHERE workspace_id=:w"),
            {"w": co["companyId"]},
        ).scalar_one()
    assert stored[SOURCE_FIELD] == body
    original = json.loads(json.dumps(stored))
    for mode in ("source", "normalized", "legacy"):
        changed = json.loads(json.dumps(original))
        if mode == "source":
            changed[SOURCE_FIELD]["manifestDigest"] = "f" * 64
        elif mode == "normalized":
            changed["artifactDigest"] = "f" * 64
        else:
            changed.pop(SOURCE_FIELD)
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE gw.operating_evidence SET metrics=cast(:m AS jsonb) WHERE workspace_id=:w"
                ),
                {"w": co["companyId"], "m": json.dumps(changed)},
            )
        state = api(admin, co, "operations", method="GET").json()["data"]
        assert state["evidenceChecks"][0]["state"] == (
            "LEGACY_UNVERIFIED" if mode == "legacy" else "INVALID"
        )
        assert (
            not state["evidenceChecks"][0]["signatureVerified"] and not state["ready"]
        )
