"""Owned PostgreSQL and real encrypted company records, not whole-route acceptance."""

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
from fs.core.backup import BackupError
from fs.core.security.journal import verify as chain_verify
from fs.gw import company
from fs.gw.evidence_trust import from_environment
from fs.gw.journal_observation import observe, verify_current
from fs.gw.security_journal import record
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_gw_acceptance_sources_db import configured
from test_gw_company import context
from test_gw_company_work import api
from test_hr_work import company_env
from test_security_journal import journal


def prepared(env, patch, journal):
    patch.setenv("FS_GW_JOURNAL_TX_PROOF", "true")
    args, _, _ = configured(env, patch)
    observer = Ed25519PrivateKey.generate()
    public = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
    public["observer"] = base64.b64encode(
        observer.public_key().public_bytes_raw()
    ).decode()
    patch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
    co = env[1]
    scopes = {
        "version": 1,
        "keys": {
            "source": {
                "workspaceIds": [str(co["companyId"])],
                "purposes": ["BACKUP", "RESTORE", "CHECKPOINT"],
            },
            "collector": {
                "workspaceIds": [str(co["companyId"])],
                "purposes": ["ACCEPTANCE_RECONCILIATION"],
            },
            "observer": {
                "workspaceIds": [str(co["companyId"])],
                "purposes": ["JOURNAL_OBSERVATION"],
            },
        },
    }
    patch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
    head = chain_verify(*journal)["head"]
    patch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", head)
    return args | {
        "public_keys": from_environment(),
        "signer": observer,
        "signer_id": "observer",
    }


def test_real_scoped_audit_and_abort_observation_never_registers_as_acceptance(
    company_env, monkeypatch, journal
):
    args = prepared(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    doc = observe(engine, **args)
    assert doc["envelope"]["result"] == "PARTIAL"
    assert doc["envelope"]["dispositions"]["AUDIT_CONFIRMED"] >= 4
    # An actual rolled-back transaction leaves an intent but no committed confirmation.
    ctx = context(engine, admin)
    with pytest.raises(RuntimeError), engine.begin() as c:
        scoped, _ = company.resolve_company(c, ctx, co["companyId"])
        record(c, scoped, "synthetic.abort")
        raise RuntimeError("synthetic abort")
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"])
    newdoc = observe(engine, **args)
    assert newdoc["envelope"]["result"] == "PARTIAL"
    assert newdoc["envelope"]["dispositions"]["ABORT_CONFIRMED"] == 1
    checked = verify_current(
        engine,
        newdoc,
        **{k: v for k, v in args.items() if k not in {"signer", "signer_id"}},
    )
    assert not checked.ready and not checked.completeness_confirmed
    with pytest.raises(ValueError):
        verify_current(
            engine,
            doc,
            **{k: v for k, v in args.items() if k not in {"signer", "signer_id"}},
        )
    assert api(admin, co, "operating-evidence", newdoc).status_code == 400
    assert (
        api(admin, co, "operations", method="GET").json()["data"]["launchGate"][
            "unverifiedCount"
        ]
        == 4
    )


@pytest.mark.parametrize(
    "change",
    [
        "policy",
        "audit-removed",
        "committed-no-audit",
        "pending",
        "legacy-proof",
        "chain-advanced",
        "stale-pin",
        "tamper",
    ],
)
def test_current_source_is_required_without_past_observation_fallback(
    company_env, monkeypatch, journal, change
):
    args = prepared(company_env, monkeypatch, journal)
    engine, co, admin, _ = company_env
    doc = observe(engine, **args)
    ctx = context(engine, admin)
    held = None
    try:
        if change == "policy":
            policy = api(admin, co, "operations", method="GET").json()["data"][
                "policy"
            ] | {"reason": "합성 새 기준", "rpoMinutes": 90}
            assert (
                api(
                    admin,
                    co,
                    "operating-policies",
                    {"expectedVersion": 1, "policy": policy},
                ).status_code
                == 200
            )
        elif change == "audit-removed":
            with engine.begin() as c:
                c.execute(
                    text(
                        "DELETE FROM core.audit_event WHERE entity_kind='gw.security_journal'"
                    )
                )
        elif change in {
            "committed-no-audit",
            "pending",
            "legacy-proof",
            "chain-advanced",
            "stale-pin",
        }:
            if change == "legacy-proof":
                monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "false")
            held = engine.connect()
            tx = held.begin()
            scoped, _ = company.resolve_company(held, ctx, co["companyId"])
            record(held, scoped, "synthetic.observation-change")
            if change == "committed-no-audit":
                held.execute(
                    text(
                        "DELETE FROM core.audit_event WHERE entity_key=(SELECT entity_key FROM core.audit_event WHERE entity_kind='gw.security_journal' ORDER BY id DESC LIMIT 1)"
                    )
                )
            if change != "pending":
                tx.commit()
                held.close()
                held = None
            if change != "stale-pin":
                monkeypatch.setenv(
                    "FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"]
                )
        else:
            path = next(Path(journal[0]).glob("0000000001.json"))
            raw = path.read_bytes()
            path.write_bytes(raw.replace(b'"version":1', b'"version":2'))
        with pytest.raises((ValueError, BackupError)):
            verify_current(
                engine,
                doc,
                **{k: v for k, v in args.items() if k not in {"signer", "signer_id"}},
            )
        if change in {"audit-removed", "committed-no-audit", "pending", "legacy-proof"}:
            current = observe(engine, **args)["envelope"]
            assert current["result"] == "BLOCKED"
            if change == "pending":
                assert current["dispositions"]["PENDING"] >= 1
            if change == "legacy-proof":
                assert current["missingTransactionProofs"] >= 1
    finally:
        if held is not None:
            held.rollback()
            held.close()


def test_cli_sign_verify_private_outputs_and_database_readonly(
    company_env, monkeypatch, journal, tmp_path
):
    args = prepared(company_env, monkeypatch, journal)
    engine, co, _admin, _ = company_env
    tmp_path.chmod(0o700)
    keyfile = tmp_path / "signer"
    keyfile.write_bytes(args["signer"].private_bytes_raw())
    keyfile.chmod(0o600)
    env = os.environ.copy()
    env.update(
        FS_GW_PREFLIGHT_DATABASE_URL=env["TEST_DATABASE_URL"],
        FS_GW_RUNNER_KEY_FILE=str(keyfile),
        FS_GW_RUNNER_KEY_ID="observer",
    )
    output = tmp_path / "observation"
    command = [
        sys.executable,
        str(Path(__file__).parents[2] / "tools/gw_identity_journal.py"),
        "--expected-head",
        env["FS_GW_JOURNAL_EXPECTED_HEAD"],
        "--company-id",
        str(co["companyId"]),
    ]
    created = subprocess.run(
        [*command, "--signed-observation", str(output)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert created.returncode == 0
    assert set(json.loads(created.stdout)) == {"result", "ready", "scopeRecords"}
    assert output.stat().st_mode & 0o777 == 0o600
    original = output.read_bytes()
    assert (
        subprocess.run(
            [*command, "--signed-observation", str(output)],
            env=env,
            capture_output=True,
            check=False,
            timeout=30,
        ).returncode
        == 1
    )
    assert output.read_bytes() == original
    env.pop("FS_GW_RUNNER_KEY_FILE")
    env.pop("FS_GW_RUNNER_KEY_ID")
    assert (
        subprocess.run(
            [*command, "--verify-observation", str(output)],
            env=env,
            capture_output=True,
            check=False,
            timeout=30,
        ).returncode
        == 0
    )

    def write_during_read(conn, cursor, statement, parameters, ctx, many):
        if statement == "SELECT transaction_timestamp()":
            conn.execute(text("UPDATE gw.operating_settings SET version=version+1"))

    event.listen(engine, "before_cursor_execute", write_during_read)
    try:
        with pytest.raises(DBAPIError):
            observe(engine, **args)
    finally:
        event.remove(engine, "before_cursor_execute", write_during_read)


def test_other_company_and_generation_are_excluded_but_new_global_head_is_required(
    company_env, monkeypatch, journal
):
    from fs.core.security.journal import append
    from fs.core.security.transaction_proof import capture

    args = prepared(company_env, monkeypatch, journal)
    engine, co, _admin, _staff = company_env
    original = observe(engine, **args)
    generation = int(original["envelope"]["generationId"])
    with engine.begin() as c:
        for workspace, gen in [
            (co["companyId"] + 100000, generation),
            (co["companyId"], generation + 100000),
        ]:
            append(
                *journal,
                {
                    "coverage": "gw.company.intent.v2",
                    "workspaceId": workspace,
                    "generationId": gen,
                    "operation": "synthetic.other-scope-private-operation",
                    "snapshot": {},
                    **capture(c),
                },
            )
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"])
    latest = observe(engine, **args)
    assert latest["envelope"]["result"] == "PARTIAL"
    assert latest["envelope"]["scopeRecords"] == original["envelope"]["scopeRecords"]
    assert latest["envelope"]["dispositions"] == original["envelope"]["dispositions"]
    assert latest["envelope"]["sourceHead"] != original["envelope"]["sourceHead"]
    assert "other-scope-private-operation" not in json.dumps(latest)
    with pytest.raises(ValueError):
        verify_current(
            engine,
            original,
            **{k: v for k, v in args.items() if k not in {"signer", "signer_id"}},
        )


def test_head_change_during_measurement_cannot_publish_an_observation(
    company_env, monkeypatch, journal
):
    from fs.core.security.journal import append

    args = prepared(company_env, monkeypatch, journal)
    engine = company_env[0]
    changed = False

    def change_head(conn, cursor, statement, parameters, ctx, many):
        nonlocal changed
        if statement == "SELECT transaction_timestamp()" and not changed:
            changed = True
            append(
                *journal,
                {
                    "coverage": "gw.company_identity.intent.v1",
                    "snapshot": "synthetic concurrent record",
                },
            )
            monkeypatch.setenv(
                "FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"]
            )

    event.listen(engine, "before_cursor_execute", change_head)
    try:
        with pytest.raises(BackupError, match="관측 도중"):
            observe(engine, **args)
    finally:
        event.remove(engine, "before_cursor_execute", change_head)
    assert changed
