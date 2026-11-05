"""Actual read-only PostgreSQL selection/CLI/ingestion with synthetic signed claims."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.security.service import database_now
from fs.gw.acceptance_sources import sign_current
from fs.gw.operating_contract import canonical
from fs.gw.readiness import SOURCE_FIELD
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_gw_company_work import api
from test_gw_evidence import prepare
from test_hr_work import company_env


def configured(env, monkeypatch):
    backup, _ = prepare(env, monkeypatch)
    engine, co, admin, _ = env
    source_key, key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    public = {
        "source": source_key.public_key().public_bytes_raw(),
        "collector": key.public_key().public_bytes_raw(),
    }
    monkeypatch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps({k: base64.b64encode(v).decode() for k, v in public.items()}),
    )
    with engine.connect() as c:
        now = database_now(c) - timedelta(seconds=2)
    backup.update(
        signerKeyId="source",
        startedAt=(now - timedelta(minutes=2)).isoformat(),
        finishedAt=(now - timedelta(minutes=1)).isoformat(),
    )
    backup["metrics"].update(
        snapshotStartedAt=backup["startedAt"], storageConfirmedAt=backup["finishedAt"]
    )
    restore = backup | {
        "runId": str(uuid4()),
        "kind": "RESTORE",
        "result": "PARTIAL",
        "startedAt": backup["finishedAt"],
        "finishedAt": now.isoformat(),
        "metrics": {
            "rowHashesMatch": True,
            "revocationsReapplied": False,
            "failedCheckCount": 1,
        },
    }

    def signed(payload):
        return {
            "envelope": payload,
            "signature": base64.b64encode(source_key.sign(canonical(payload))).decode(),
        }

    for source in [backup, restore]:
        assert api(admin, co, "operating-evidence", signed(source)).status_code == 200
    args = {
        "company_id": co["companyId"],
        "code_revision": "abcdef012345",
        "public_keys": public,
        "signer": key,
        "signer_id": "collector",
    }
    return args, restore, signed


@pytest.mark.parametrize(
    "change",
    ["none", "fail", "partial", "new-pass", "legacy", "tamper", "policy", "version"],
)
def test_latest_current_db_sources_and_http_revalidation(
    company_env, monkeypatch, change
):
    args, restore, signed = configured(company_env, monkeypatch)
    engine, co, admin, _ = company_env
    proof = sign_current(engine, **args)
    diag = proof["envelope"]["metrics"]["acceptanceDiagnostics"]
    assert diag["scope"] == "CURRENT_REGISTERED_SOURCES" and diag["version"] == 2
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    state = api(admin, co, "operations", method="GET").json()["data"]
    assert state["evidenceChecks"][2]["state"] == "PARTIAL" and not state["ready"]
    assert state["launchGate"]["unverifiedCount"] == 4
    if change == "none":
        return
    if change in {"fail", "partial", "new-pass"}:
        newer = restore | {
            "runId": str(uuid4()),
            "result": "FAIL" if change == "fail" else "PARTIAL",
        }
        if change == "new-pass":
            newer.update(
                result="PASS",
                metrics={
                    "rowHashesMatch": True,
                    "foreignKeysValid": True,
                    "sessionsInvalidated": True,
                    "revocationsReapplied": True,
                    "twoAccountChecks": True,
                    "lossWindowSeconds": 60,
                    "elapsedSeconds": 120,
                },
            )
        assert api(admin, co, "operating-evidence", signed(newer)).status_code == 200
    elif change == "policy":
        policy = state["policy"] | {"reason": "합성 새 현재 기준", "rpoMinutes": 90}
        assert (
            api(
                admin,
                co,
                "operating-policies",
                {"expectedVersion": 1, "policy": policy},
            ).status_code
            == 200
        )
    else:
        with engine.begin() as c:
            row = (
                c.execute(
                    text(
                        "SELECT id,metrics FROM gw.operating_evidence WHERE workspace_id=:w AND kind='RESTORE'"
                    ),
                    {"w": co["companyId"]},
                )
                .mappings()
                .one()
            )
            metrics = row["metrics"]
            if change == "legacy":
                metrics.pop(SOURCE_FIELD)
            elif change == "tamper":
                metrics[SOURCE_FIELD]["manifestDigest"] = "e" * 64
            elif change == "version":
                c.execute(
                    text(
                        "UPDATE gw.operating_evidence SET code_revision='fffffff' WHERE id=:i"
                    ),
                    {"i": row["id"]},
                )
            if change in {"legacy", "tamper"}:
                c.execute(
                    text(
                        "UPDATE gw.operating_evidence SET metrics=cast(:m AS jsonb) WHERE id=:i"
                    ),
                    {"m": json.dumps(metrics), "i": row["id"]},
                )
    current = api(admin, co, "operations", method="GET").json()["data"]
    assert current["evidenceChecks"][2]["state"] == (
        "STALE" if change == "policy" else "INVALID"
    )
    assert not current["ready"]
    if change in {"partial", "new-pass"}:
        newproof = sign_current(engine, **args)
        assert (
            newproof["envelope"]["metrics"]["acceptanceDiagnostics"]["restore"]["runId"]
            == newer["runId"]
        )
    else:
        with pytest.raises(ApiError):
            sign_current(engine, **args)


def test_actual_cli_readonly_export_and_write_rejection(
    company_env, monkeypatch, tmp_path
):
    args, _, _ = configured(company_env, monkeypatch)
    engine, co, admin, _ = company_env
    tmp_path.chmod(0o700)
    keyfile = tmp_path / "key"
    keyfile.write_bytes(args["signer"].private_bytes_raw())
    keyfile.chmod(0o600)
    env = os.environ.copy()
    env.update(
        FS_GW_PREFLIGHT_DATABASE_URL=env["TEST_DATABASE_URL"],
        FS_GW_RUNNER_KEY_FILE=str(keyfile),
        FS_GW_RUNNER_KEY_ID="collector",
    )
    output = tmp_path / "proof"
    cmd = [
        sys.executable,
        str(Path(__file__).parents[2] / "tools/gw_acceptance_collect.py"),
        "--current-company-id",
        str(co["companyId"]),
        "--signed-reconciliation",
        "--output",
        str(output),
    ]
    with engine.connect() as c:
        before = c.scalar(text("SELECT count(*) FROM gw.operating_evidence"))
    result = subprocess.run(
        cmd, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {"result": "PARTIAL", "ready": False}
    proof = json.loads(output.read_bytes())
    assert output.stat().st_mode & 0o777 == 0o600
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM gw.operating_evidence")) == before
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    original = output.read_bytes()
    assert (
        subprocess.run(
            cmd, env=env, capture_output=True, timeout=30, check=False
        ).returncode
        == 1
    )
    assert output.read_bytes() == original

    def write_during_read(conn, cursor, statement, parameters, ctx, many):
        if "SELECT DISTINCT ON (kind)" in statement:
            conn.execute(text("UPDATE gw.operating_settings SET version=version+1"))

    event.listen(engine, "before_cursor_execute", write_during_read)
    try:
        with pytest.raises(DBAPIError):
            sign_current(engine, **args)
    finally:
        event.remove(engine, "before_cursor_execute", write_during_read)


def test_new_failure_committed_during_read_snapshot_is_rejected_at_registration(
    company_env, monkeypatch
):
    args, restore, signed = configured(company_env, monkeypatch)
    engine, co, admin, _ = company_env
    earlier = sign_current(engine, **args)
    assert api(admin, co, "operating-evidence", earlier).status_code == 200
    inserted = False

    def concurrent_failure(conn, cursor, statement, parameters, ctx, many):
        nonlocal inserted
        if "SELECT DISTINCT ON (kind)" in statement and not inserted:
            inserted = True
            failed = restore | {"runId": str(uuid4()), "result": "FAIL"}
            assert (
                api(admin, co, "operating-evidence", signed(failed)).status_code == 200
            )

    event.listen(engine, "before_cursor_execute", concurrent_failure)
    try:
        snapshot_proof = sign_current(engine, **args)
    finally:
        event.remove(engine, "before_cursor_execute", concurrent_failure)
    assert inserted
    assert (
        snapshot_proof["envelope"]["metrics"]["acceptanceDiagnostics"]["restore"][
            "runId"
        ]
        == restore["runId"]
    )
    # Snapshot consistency cannot authorize use after a newer registration commits.
    assert api(admin, co, "operating-evidence", snapshot_proof).status_code == 400
    current = api(admin, co, "operations", method="GET").json()["data"]
    assert current["evidenceChecks"][2]["state"] == "INVALID"
    assert current["ready"] is False
    with pytest.raises(ApiError):
        sign_current(engine, **args)
