"""Actual existing restore rechecks and current source ingestion; no live acceptance."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.core.security.journal import verify as chain_verify
from fs.gw.acceptance_sources import sign_current
from fs.gw.evidence_trust import from_environment
from fs.gw.journal_observation import observe
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_hr_work import company_env
from test_security_journal import journal


def add_keys(env, patch, config, folder):
    co = env[1]
    public = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
    scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
    generated = {}
    for name, purpose in [
        ("rechecker", "RESTORE_RECHECK"),
        ("collector", "ACCEPTANCE_RECONCILIATION"),
        ("observer", "JOURNAL_OBSERVATION"),
    ]:
        key = Ed25519PrivateKey.generate()
        generated[name] = key
        public[name] = base64.b64encode(key.public_key().public_bytes_raw()).decode()
        scopes["keys"][name] = {
            "workspaceIds": [str(co["companyId"])],
            "purposes": [purpose],
        }
    patch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
    patch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
    keyfile = folder / "rechecker-key"
    keyfile.write_bytes(generated["rechecker"].private_bytes_raw())
    keyfile.chmod(0o600)
    patch.setenv("FS_GW_RUNNER_KEY_FILE", str(keyfile))
    patch.setenv("FS_GW_RUNNER_KEY_ID", "rechecker")
    return generated, config | {
        "public": from_environment(),
        "signer": generated["rechecker"],
        "signerId": "rechecker",
    }


@pytest.mark.parametrize("combined_journal", [False, True])
def test_real_target_current_recheck_partial_fail_unavailable_and_latest_guards(
    company_env, backup_env, monkeypatch, journal, combined_journal
):
    engine, co, admin, _ = company_env
    module, config, folders, _ = backup_env
    if combined_journal:
        monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "true")
        monkeypatch.setenv(
            "FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"]
        )
    else:
        monkeypatch.delenv("FS_GW_IDENTITY_JOURNAL_DIR")
        monkeypatch.delenv("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
    args = restored(company_env, backup_env)
    result = module.restore(**args)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    target_url = make_url(os.environ["TEST_DATABASE_URL"]).set(
        database=result["database"]
    )
    target = create_engine(target_url)
    try:
        keys, recheck_config = add_keys(
            company_env, monkeypatch, config, folders["reports"]
        )
        original = json.loads(args["evidence"].read_bytes())
        backup = json.loads((folders["backups"] / "backup.json").read_bytes())
        assert api(admin, co, "operating-evidence", backup).status_code == 200
        assert api(admin, co, "operating-evidence", original).status_code == 200

        def journal_observation():
            if not combined_journal:
                return None
            monkeypatch.setenv(
                "FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"]
            )
            return observe(
                engine,
                company_id=co["companyId"],
                code_revision=config["codeRevision"],
                public_keys=from_environment(),
                signer=keys["observer"],
                signer_id="observer",
            )

        def collect(document):
            return sign_current(
                engine,
                company_id=co["companyId"],
                code_revision=config["codeRevision"],
                public_keys=from_environment(),
                signer=keys["collector"],
                signer_id="collector",
                restore_recheck=document,
                journal_observation=journal_observation(),
            )

        def inspect():
            if combined_journal:
                monkeypatch.setenv(
                    "FS_GW_JOURNAL_EXPECTED_HEAD", chain_verify(*journal)["head"]
                )
            data = api(admin, co, "operations", method="GET").json()["data"]
            assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
            return data["evidenceChecks"][2]

        def check(name):
            output = folders["reports"] / name
            summary = module.recheck_restore(
                url=target_url.render_as_string(hide_password=False),
                artifact=args["artifact"],
                checkpoint_file=args["checkpoint_file"],
                head=args["head"],
                expected_checkpoint_digest=args["expected_checkpoint_digest"],
                restore_document=original,
                output=output,
                config=recheck_config,
            )
            assert output.stat().st_mode & 0o777 == 0o600
            return json.loads(output.read_bytes()), summary

        fresh, summary = check("fresh.json")
        assert summary == {"result": "PARTIAL", "ready": False, "targetMeasured": True}
        assert fresh["envelope"]["stateMatchesExecution"]
        # Bounded future skew must not permit replay before DB registration catches up.
        from fs.gw.operating_contract import canonical

        clock = (
            datetime.fromisoformat(fresh["envelope"]["checkedAt"])
            + timedelta(seconds=20)
        ).isoformat()
        fresh["envelope"]["checkedAt"] = clock
        fresh["envelope"]["measurement"]["observedAt"] = clock
        fresh["signature"] = base64.b64encode(
            keys["rechecker"].sign(canonical(fresh["envelope"]))
        ).decode()
        recheck_path = folders["reports"] / "collector-recheck.json"
        recheck_path.write_text(json.dumps(fresh))
        recheck_path.chmod(0o600)
        collector_key = folders["reports"] / "collector-key"
        collector_key.write_bytes(keys["collector"].private_bytes_raw())
        collector_key.chmod(0o600)
        env = os.environ.copy()
        env.update(
            FS_GW_PREFLIGHT_DATABASE_URL=os.environ["TEST_DATABASE_URL"],
            FS_GW_RUNNER_KEY_FILE=str(collector_key),
            FS_GW_RUNNER_KEY_ID="collector",
            FS_CODE_REVISION=config["codeRevision"],
        )
        acceptance_path = folders["reports"] / "acceptance-cli.json"
        command = [
            sys.executable,
            str(Path(__file__).parents[2] / "tools/gw_acceptance_collect.py"),
            "--current-company-id",
            str(co["companyId"]),
            "--signed-reconciliation",
            "--restore-recheck",
            str(recheck_path),
            "--output",
            str(acceptance_path),
        ]
        if combined_journal:
            journal_path = folders["reports"] / "collector-journal.json"
            journal_path.write_text(json.dumps(journal_observation()))
            journal_path.chmod(0o600)
            env["FS_GW_JOURNAL_EXPECTED_HEAD"] = os.environ[
                "FS_GW_JOURNAL_EXPECTED_HEAD"
            ]
            command += ["--journal-observation", str(journal_path)]
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        assert process.returncode == 0  # Successful limited collection remains PARTIAL.
        assert acceptance_path.stat().st_mode & 0o777 == 0o600
        acceptance = json.loads(acceptance_path.read_bytes())
        assert (
            acceptance["envelope"]["metrics"]["acceptanceDiagnostics"]["version"] == 4
        )
        assert api(admin, co, "operating-evidence", acceptance).status_code == 200
        assert inspect()["state"] == "PARTIAL"
        assert inspect()["restoreRecheck"]["targetMeasured"]
        assert api(admin, co, "operating-evidence", fresh).status_code == 400
        with pytest.raises(ApiError):
            collect(fresh)
        with pytest.raises(ApiError):
            sign_current(
                engine,
                company_id=co["companyId"],
                code_revision=config["codeRevision"],
                public_keys=from_environment(),
                signer=keys["collector"],
                signer_id="collector",
            )
        with target.begin() as c:
            c.execute(text("UPDATE core.auth_session SET revoked_at=NULL"))
        failed, _ = check("failed.json")
        assert failed["envelope"]["result"] == "BLOCKED"
        assert failed["envelope"]["measurement"]["unrevokedSessions"] > 0
        failed_acceptance = collect(failed)
        assert failed_acceptance["envelope"]["result"] == "FAIL"
        assert (
            api(admin, co, "operating-evidence", failed_acceptance).status_code == 200
        )
        assert inspect()["state"] == "FAILED"
        assert not inspect()["restoreRecheck"]["stateMatchesExecution"]
        # Connection refusal is signed as unavailable, with no fabricated counts or reopening.
        with cleanup.connect() as c:
            c.execute(
                text(f'ALTER DATABASE "{result["database"]}" ALLOW_CONNECTIONS false')
            )
        # Unavailable targets cannot provide a DB clock. A fresh runner clock must
        # actually pass the last registration; do not relax anti-replay ordering.
        with engine.connect() as c:
            latest = c.scalar(
                text(
                    "SELECT max(recorded_at) FROM gw.operating_evidence WHERE kind='ACCEPTANCE'"
                )
            )
        delay = (latest - datetime.now(UTC)).total_seconds()
        assert delay < 30
        if delay >= 0:
            time.sleep(delay + 0.01)
        unavailable, _ = check("unavailable.json")
        assert unavailable["envelope"]["measurement"] is None
        assert not unavailable["envelope"]["targetMeasured"]
        assert (
            api(admin, co, "operating-evidence", collect(unavailable)).status_code
            == 200
        )
        assert (
            inspect()["state"] == "FAILED"
            and not inspect()["restoreRecheck"]["targetMeasured"]
        )
        with cleanup.connect() as c:
            assert not c.scalar(
                text("SELECT datallowconn FROM pg_database WHERE datname=:n"),
                {"n": result["database"]},
            )
        # A later failed source must invalidate the saved recheck, never fall back.
        failed_backup = json.loads(json.dumps(backup))
        failed_backup["envelope"].update(runId=str(uuid4()), result="FAIL")
        failed_backup["envelope"]["metrics"]["failedCheckCount"] = 1
        failed_backup["signature"] = base64.b64encode(
            config["signer"].sign(canonical(failed_backup["envelope"]))
        ).decode()
        assert api(admin, co, "operating-evidence", failed_backup).status_code == 200
        assert inspect()["state"] == "INVALID"
        assert "restoreRecheck" not in inspect()
        with pytest.raises(ApiError):
            collect(unavailable)
        with pytest.raises(BackupError):
            module.recheck_restore(
                url=os.environ["TEST_DATABASE_URL"],
                artifact=args["artifact"],
                checkpoint_file=args["checkpoint_file"],
                head=args["head"],
                expected_checkpoint_digest=args["expected_checkpoint_digest"],
                restore_document=original,
                output=folders["reports"] / "wrong-source.json",
                config=recheck_config,
            )
    finally:
        target.dispose()
        with cleanup.connect() as c:
            c.execute(text(f'DROP DATABASE "{result["database"]}" WITH (FORCE)'))
        cleanup.dispose()


def test_real_recheck_cli_private_output_no_source_fallback_and_wrong_physical_target(
    company_env, backup_env, monkeypatch
):
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    result = module.restore(**args)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    other = "fs_gw_restore_" + uuid4().hex + "_test"
    other_created = False
    try:
        _, _ = add_keys(company_env, monkeypatch, config, folders["reports"])
        target_url = make_url(os.environ["TEST_DATABASE_URL"]).set(
            database=result["database"]
        )
        env = os.environ.copy()
        env["FS_GW_RECHECK_DATABASE_URL"] = target_url.render_as_string(
            hide_password=False
        )
        output = folders["reports"] / "cli.json"
        command = [
            sys.executable,
            str(Path(__file__).parents[2] / "tools/gw_backup.py"),
            "recheck-restore",
            "--backup",
            str(args["artifact"]),
            "--checkpoint",
            str(args["checkpoint_file"]),
            "--head",
            str(args["head"]),
            "--expected-checkpoint-digest",
            args["expected_checkpoint_digest"],
            "--restore-evidence",
            str(args["evidence"]),
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=30, check=False
        )
        assert (
            completed.returncode == 0
            and json.loads(completed.stdout)["result"] == "PARTIAL"
        )
        original = output.read_bytes()
        assert (
            subprocess.run(
                command, env=env, capture_output=True, timeout=30, check=False
            ).returncode
            == 1
        )
        assert output.read_bytes() == original
        missing = env.copy()
        missing.pop("FS_GW_RECHECK_DATABASE_URL")
        command[-1] = str(folders["reports"] / "no-fallback.json")
        assert (
            subprocess.run(
                command, env=missing, capture_output=True, timeout=30, check=False
            ).returncode
            == 1
        )
        assert not Path(command[-1]).exists()
        with cleanup.connect() as c:
            c.execute(text(f'CREATE DATABASE "{other}"'))
        other_created = True
        env["FS_GW_RECHECK_DATABASE_URL"] = target_url.set(
            database=other
        ).render_as_string(hide_password=False)
        command[-1] = str(folders["reports"] / "wrong-target.json")
        assert (
            subprocess.run(
                command, env=env, capture_output=True, timeout=30, check=False
            ).returncode
            == 1
        )
        assert not Path(command[-1]).exists()
        with cleanup.connect() as c:
            c.execute(
                text(f'ALTER DATABASE "{result["database"]}" ALLOW_CONNECTIONS false')
            )
        env["FS_GW_RECHECK_DATABASE_URL"] = target_url.render_as_string(
            hide_password=False
        )
        command[-1] = str(folders["reports"] / "blocked.json")
        completed = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=30, check=False
        )
        assert (
            completed.returncode == 2
            and not json.loads(completed.stdout)["targetMeasured"]
        )
    finally:
        with cleanup.connect() as c:
            if other_created:
                c.execute(text(f'DROP DATABASE "{other}" WITH (FORCE)'))
            c.execute(text(f'DROP DATABASE "{result["database"]}" WITH (FORCE)'))
        cleanup.dispose()
