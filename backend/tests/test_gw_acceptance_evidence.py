"""Real HTTP/DB ingestion tests with synthetic signed claims, not actual recovery."""

# ruff: noqa: F401,F811
import hashlib
import json
from datetime import timedelta
from uuid import uuid4

import pytest
from fs.core.security.service import database_now
from fs.gw.acceptance_reconciliation import reconcile
from fs.gw.operating_contract import OperatingPolicy, canonical
from fs.gw.readiness import SOURCE_FIELD
from sqlalchemy import text
from test_gw_company_work import api
from test_gw_evidence import prepare
from test_hr_work import company_env


@pytest.mark.parametrize(
    "change", ["failure", "partial", "new-pass", "legacy", "tamper"]
)
def test_signed_reconciliation_registration_and_latest_source_invalidation(
    company_env, monkeypatch, change
):
    backup, signed = prepare(company_env, monkeypatch)
    engine, co, admin, staff = company_env
    with engine.connect() as c:
        clock = database_now(c) - timedelta(seconds=1)
    backup["startedAt"] = (clock - timedelta(minutes=2)).isoformat()
    backup["finishedAt"] = (clock - timedelta(minutes=1)).isoformat()
    backup["metrics"]["snapshotStartedAt"] = backup["startedAt"]
    backup["metrics"]["storageConfirmedAt"] = backup["finishedAt"]
    restore = backup | {
        "runId": str(uuid4()),
        "kind": "RESTORE",
        "result": "PARTIAL",
        "startedAt": backup["finishedAt"],
        "finishedAt": (clock - timedelta(seconds=10)).isoformat(),
        "metrics": {
            "rowHashesMatch": True,
            "revocationsReapplied": False,
            "failedCheckCount": 1,
        },
    }
    docs = {"BACKUP": signed(backup), "RESTORE": signed(restore)}
    from fs.gw.operating_evidence import verifier_config

    with engine.connect() as c:
        keys, code, revision = verifier_config(c)
    policy = OperatingPolicy.model_validate(
        api(admin, co, "operations", method="GET").json()["data"]["policy"]
    )
    diagnostic = reconcile(
        docs,
        public_keys=keys,
        workspace_id=int(backup["workspaceId"]),
        generation_id=int(backup["generationId"]),
        policy=policy,
        code_revision=code,
        db_revision=revision,
        now=clock,
    ).model_dump(by_alias=True)
    acceptance = backup | {
        "runId": str(uuid4()),
        "kind": "ACCEPTANCE",
        "result": "PARTIAL",
        "startedAt": clock.isoformat(),
        "finishedAt": clock.isoformat(),
        "manifestDigest": hashlib.sha256(canonical(diagnostic)).hexdigest(),
        "metrics": {"acceptanceDiagnostics": diagnostic},
    }
    # Original files must also be the latest registered sources; signature alone is insufficient.
    assert api(admin, co, "operating-evidence", signed(acceptance)).status_code == 400
    for doc in docs.values():
        assert api(admin, co, "operating-evidence", doc).status_code == 200
    assert api(staff, co, "operating-evidence", signed(acceptance)).status_code == 403
    key = str(uuid4())
    accepted = api(admin, co, "operating-evidence", signed(acceptance), key=key)
    assert accepted.status_code == 200, accepted.text
    assert (
        api(admin, co, "operating-evidence", signed(acceptance), key=key).json()
        == accepted.json()
    )
    state = api(admin, co, "operations", method="GET").json()["data"]
    assert state["evidenceChecks"][2]["state"] == "PARTIAL"
    assert state["evidenceChecks"][2]["signatureVerified"]
    assert "최신 백업" in state["evidenceChecks"][2]["detail"]
    assert not state["ready"] and state["launchGate"]["unverifiedCount"] == 4
    assert (
        state["backupRestoreCollection"]["result"] == "BLOCKED"
    )  # PARTIAL restore remains PARTIAL.
    assert (
        "evidenceChecks"
        not in api(staff, co, "operations", method="GET").json()["data"]
    )
    assert (
        api(
            admin,
            co,
            "operating-evidence",
            signed(acceptance | {"runId": str(uuid4()), "result": "PASS"}),
        ).status_code
        == 400
    )
    if change in {"failure", "partial", "new-pass"}:
        newer = restore | {
            "runId": str(uuid4()),
            "result": "FAIL" if change == "failure" else "PARTIAL",
        }
        if change == "new-pass":
            newer["result"] = "PASS"
            newer["metrics"] = {
                "rowHashesMatch": True,
                "foreignKeysValid": True,
                "sessionsInvalidated": True,
                "revocationsReapplied": True,
                "twoAccountChecks": True,
                "lossWindowSeconds": 60,
                "elapsedSeconds": 50,
            }
        assert api(admin, co, "operating-evidence", signed(newer)).status_code == 200
    else:
        with engine.begin() as c:
            stored = c.execute(
                text(
                    "SELECT metrics FROM gw.operating_evidence WHERE workspace_id=:w AND kind='RESTORE'"
                ),
                {"w": co["companyId"]},
            ).scalar_one()
            if change == "legacy":
                stored.pop(SOURCE_FIELD)
            else:
                stored[SOURCE_FIELD]["manifestDigest"] = "f" * 64
            c.execute(
                text(
                    "UPDATE gw.operating_evidence SET metrics=cast(:m AS jsonb) WHERE workspace_id=:w AND kind='RESTORE'"
                ),
                {"w": co["companyId"], "m": json.dumps(stored)},
            )
    state = api(admin, co, "operations", method="GET").json()["data"]
    assert state["evidenceChecks"][2]["state"] == "INVALID"
    assert not state["evidenceChecks"][2]["signatureVerified"]
    assert not state["ready"] and state["launchGate"]["unverifiedCount"] == 4
    before = api(admin, co, "operating-evidence", method="GET").json()["data"]["total"]
    assert (
        api(
            admin,
            co,
            "operating-evidence",
            signed(acceptance | {"runId": str(uuid4())}),
        ).status_code
        == 400
    )
    assert (
        api(admin, co, "operating-evidence", method="GET").json()["data"]["total"]
        == before
    )
