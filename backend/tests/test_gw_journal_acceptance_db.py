"""Actual encrypted records, PostgreSQL, ingestion and CLI. No live acceptance."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.security.journal import append
from fs.core.security.journal import verify as chain_verify
from fs.gw import company
from fs.gw.acceptance_sources import sign_current
from fs.gw.evidence_trust import from_environment
from fs.gw.journal_observation import observe
from fs.gw.readiness import SOURCE_FIELD
from fs.gw.security_journal import record
from sqlalchemy import text
from test_gw_company import context
from test_gw_company_work import api
from test_gw_journal_observation_db import prepared
from test_hr_work import company_env
from test_security_journal import journal


def pin(patch, journal):
    patch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"])


def setup(env, patch, journal):
    observer_args = prepared(env, patch, journal)
    collector = Ed25519PrivateKey.generate()
    public = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
    public["collector"] = base64.b64encode(
        collector.public_key().public_bytes_raw()
    ).decode()
    patch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
    observer_args["public_keys"] = from_environment()
    collector_args = observer_args | {"signer": collector, "signer_id": "collector"}
    return observer_args, collector_args


def state(admin, co):
    response = api(admin, co, "operations", method="GET")
    assert response.status_code == 200
    data = response.json()["data"]
    assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
    return data["evidenceChecks"][2]


def test_register_partial_keep_original_and_only_confirmed_registration_tail(
    company_env, monkeypatch, journal
):
    observer, collector = setup(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    legacy = sign_current(engine, **collector)
    observation = observe(engine, **observer)
    proof = sign_current(engine, journal_observation=observation, **collector)
    assert proof["envelope"]["result"] == "PARTIAL"
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    # A separate head pin must follow the registration's own encrypted receipt.
    assert state(admin, co)["state"] == "INVALID"
    pin(monkeypatch, journal)
    current = state(admin, co)
    assert current["state"] == "PARTIAL" and current["signatureVerified"]
    assert (
        current["journalObservation"]["scopeRecords"]
        == observation["envelope"]["scopeRecords"]
    )
    assert api(admin, co, "operating-evidence", proof).status_code == 409
    assert api(admin, co, "operating-evidence", legacy).status_code == 400
    with pytest.raises(ApiError):
        sign_current(engine, **collector)
    with engine.connect() as c:
        row = c.execute(
            text(
                "SELECT metrics FROM gw.operating_evidence WHERE run_id=cast(:r AS uuid)"
            ),
            {"r": proof["envelope"]["runId"]},
        ).scalar_one()
        assert row[SOURCE_FIELD] == proof["envelope"]
        assert row["acceptanceDiagnostics"]["journalObservation"] == observation
    with pytest.raises(ApiError):
        sign_current(engine, journal_observation=observation, **collector)
    # Fresh observation after the latest registered run may be collected and registered.
    newer = observe(engine, **observer)
    fresh = sign_current(engine, journal_observation=newer, **collector)
    assert api(admin, co, "operating-evidence", fresh).status_code == 200
    pin(monkeypatch, journal)
    assert state(admin, co)["state"] == "PARTIAL"
    assert api(admin, co, "operating-evidence", observation).status_code == 400


def test_blocked_observation_persists_latest_failure_without_old_partial_fallback(
    company_env, monkeypatch, journal
):
    observer, collector = setup(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    old = observe(engine, **observer)
    earlier = sign_current(engine, journal_observation=old, **collector)
    assert api(admin, co, "operating-evidence", earlier).status_code == 200
    pin(monkeypatch, journal)
    with engine.begin() as c:
        scoped, _ = company.resolve_company(c, context(engine, admin), co["companyId"])
        record(c, scoped, "synthetic.no-audit")
        c.execute(
            text(
                "DELETE FROM core.audit_event WHERE entity_kind='gw.security_journal' AND entity_key=(SELECT entity_key FROM core.audit_event WHERE entity_kind='gw.security_journal' ORDER BY id DESC LIMIT 1)"
            )
        )
    pin(monkeypatch, journal)
    blocked = observe(engine, **observer)
    assert blocked["envelope"]["result"] == "BLOCKED"
    failed = sign_current(engine, journal_observation=blocked, **collector)
    assert failed["envelope"]["result"] == "FAIL"
    assert api(admin, co, "operating-evidence", failed).status_code == 200
    pin(monkeypatch, journal)
    latest = state(admin, co)
    assert latest["state"] == "FAILED" and latest["signatureVerified"]
    assert latest["journalObservation"]["unresolvedRecords"] == 1
    with pytest.raises(ApiError):
        sign_current(engine, journal_observation=old, **collector)
    # A later row without an original must block, rather than fall back to earlier partial.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.operating_evidence SET metrics=metrics-:field WHERE run_id=cast(:r AS uuid)"
            ),
            {"field": SOURCE_FIELD, "r": failed["envelope"]["runId"]},
        )
    latest = state(admin, co)
    assert latest["state"] == "LEGACY_UNVERIFIED" and not latest["signatureVerified"]
    assert "journalObservation" not in latest


@pytest.mark.parametrize(
    "change",
    [
        "business",
        "aborted-receipt",
        "pending-receipt",
        "core",
        "audit",
        "key-revoked",
        "tamper",
    ],
)
def test_changes_invalidate_registered_observation_and_old_collection(
    company_env, monkeypatch, journal, change
):
    observer, collector = setup(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    observation = observe(engine, **observer)
    proof = sign_current(engine, journal_observation=observation, **collector)
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    pin(monkeypatch, journal)
    assert state(admin, co)["state"] == "PARTIAL"
    held = None
    try:
        if change in {"business", "aborted-receipt", "pending-receipt"}:
            held = engine.connect()
            tx = held.begin()
            scoped, _ = company.resolve_company(
                held, context(engine, admin), co["companyId"]
            )
            record(
                held,
                scoped,
                "synthetic.business"
                if change == "business"
                else "gw.operating_evidence.record",
            )
            if change != "pending-receipt":
                tx.rollback() if change == "aborted-receipt" else tx.commit()
                held.close()
                held = None
        elif change == "core":
            append(
                *journal,
                {
                    "coverage": "gw.company_identity.intent.v1",
                    "snapshot": "synthetic unrelated change",
                },
            )
        elif change == "audit":
            with engine.begin() as c:
                c.execute(
                    text(
                        "DELETE FROM core.audit_event WHERE entity_kind='gw.security_journal'"
                    )
                )
        elif change == "key-revoked":
            scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
            scopes["keys"]["observer"]["workspaceIds"] = [str(co["companyId"] + 10000)]
            monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
            collector["public_keys"] = from_environment()
        else:
            with engine.begin() as c:
                c.execute(
                    text(
                        "UPDATE gw.operating_evidence SET metrics=jsonb_set(metrics, '{_signedEnvelope,metrics,acceptanceDiagnostics,journalObservation,envelope,sourceHead}', '\"ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff\"') WHERE kind='ACCEPTANCE'"
                    )
                )
        pin(monkeypatch, journal)
        current = state(admin, co)
        assert current["state"] == "INVALID" and not current["signatureVerified"]
        assert "journalObservation" not in current
        with pytest.raises(ApiError):
            sign_current(engine, journal_observation=observation, **collector)
    finally:
        if held is not None:
            held.rollback()
            held.close()


@pytest.mark.parametrize("blocked", [False, True])
def test_real_cli_collects_nested_original_and_private_output(
    company_env, monkeypatch, journal, tmp_path, blocked
):
    observer, collector = setup(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    if blocked:
        monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "false")
        with engine.begin() as c:
            scoped, _ = company.resolve_company(
                c, context(engine, admin), co["companyId"]
            )
            record(c, scoped, "synthetic.missing-proof")
        monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "true")
        pin(monkeypatch, journal)
    observation = observe(engine, **observer)
    tmp_path.chmod(0o700)
    source = tmp_path / "observation"
    source.write_text(json.dumps(observation))
    source.chmod(0o600)
    key = tmp_path / "collector-key"
    key.write_bytes(collector["signer"].private_bytes_raw())
    key.chmod(0o600)
    env = os.environ.copy()
    env.update(
        FS_GW_PREFLIGHT_DATABASE_URL=env["TEST_DATABASE_URL"],
        FS_GW_RUNNER_KEY_FILE=str(key),
        FS_GW_RUNNER_KEY_ID="collector",
    )
    output = tmp_path / "proof"
    command = [
        sys.executable,
        str(Path(__file__).parents[2] / "tools/gw_acceptance_collect.py"),
        "--current-company-id",
        str(co["companyId"]),
        "--signed-reconciliation",
        "--journal-observation",
        str(source),
        "--output",
        str(output),
    ]
    result = subprocess.run(
        command, env=env, capture_output=True, text=True, timeout=30, check=False
    )
    assert result.returncode == (2 if blocked else 0) and json.loads(result.stdout) == {
        "result": "FAIL" if blocked else "PARTIAL",
        "ready": False,
    }
    proof = json.loads(output.read_bytes())
    assert proof["envelope"]["metrics"]["acceptanceDiagnostics"]["version"] == 3
    assert output.stat().st_mode & 0o777 == 0o600
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    pin(monkeypatch, journal)
    assert state(admin, co)["state"] == ("FAILED" if blocked else "PARTIAL")
    original = output.read_bytes()
    assert (
        subprocess.run(
            command, env=env, capture_output=True, timeout=30, check=False
        ).returncode
        == 1
    )
    assert output.read_bytes() == original


def test_empty_observed_chain_is_retained_as_fail_not_promoted(
    company_env, monkeypatch, journal, tmp_path
):
    observer, collector = setup(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    empty = tmp_path / "empty-records"
    empty.mkdir(mode=0o700)
    monkeypatch.setenv("FS_GW_IDENTITY_JOURNAL_DIR", str(empty))
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", "0" * 64)
    observation = observe(engine, **observer)
    assert observation["envelope"]["result"] == "BLOCKED"
    assert observation["envelope"]["scopeRecords"] == 0
    proof = sign_current(engine, journal_observation=observation, **collector)
    assert proof["envelope"]["result"] == "FAIL"
    assert api(admin, co, "operating-evidence", proof).status_code == 200
    pin(monkeypatch, (empty, journal[1]))
    assert state(admin, co)["state"] == "FAILED"
