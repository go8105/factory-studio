"""Actual backups/restores plus configured catalog rechecks and current API guards."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
import time
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.gw.acceptance_sources import sign_current
from fs.gw.checkpoint_catalog import ENV
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical, timestamp
from gw_catalog_trust_helpers import approve_environment
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_checkpoint_catalog import publish
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_gw_restore_recheck_db import add_keys
from test_hr_work import company_env


def test_real_catalog_current_fail_missing_rollback_fresh_restore_and_cli(
    company_env, backup_env, monkeypatch
):
    engine, co, admin, _ = company_env
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    targets = []
    counter = 0
    try:

        def restore(current):
            nonlocal counter
            counter += 1
            current = current | {
                "report": folders["reports"] / f"report-{counter}.json",
                "evidence": folders["reports"] / f"restore-{counter}.json",
            }
            result = module.restore(**current)
            targets.append(result["database"])
            document = json.loads(current["evidence"].read_bytes())
            assert api(admin, co, "operating-evidence", document).status_code == 200
            with engine.connect() as c:
                clock = c.scalar(text("SELECT clock_timestamp()"))
            delay = (
                timestamp(document["envelope"]["finishedAt"]) - clock
            ).total_seconds()
            assert delay < 30
            if delay >= 0:
                time.sleep(delay + 0.02)
            return result["database"], document, current["evidence"]

        backup = json.loads((folders["backups"] / "backup.json").read_bytes())
        assert api(admin, co, "operating-evidence", backup).status_code == 200
        database, original, original_path = restore(args)
        keys, checked_config = add_keys(
            company_env, monkeypatch, config, folders["reports"]
        )
        authority = Ed25519PrivateKey.generate()
        public = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
        public["catalog"] = base64.b64encode(
            authority.public_key().public_bytes_raw()
        ).decode()
        scopes["keys"]["catalog"] = {
            "workspaceIds": [str(co["companyId"])],
            "purposes": ["CHECKPOINT_CATALOG"],
        }
        monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
        monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
        approve_environment(monkeypatch, folders["reports"] / "trust")
        checked_config["public"] = from_environment()
        catalog_folder = folders["reports"] / "catalog"
        catalog_folder.mkdir(mode=0o700)
        head = json.loads(args["head"].read_bytes())
        p = head["payload"]
        catalog = {
            "version": 1,
            "kind": "CHECKPOINT_CATALOG",
            "catalogId": str(uuid4()),
            "revision": 1,
            "publishedAt": datetime.now(UTC).isoformat(),
            "signerKeyId": "catalog",
            "records": [],
        }

        def update(sequence, result="PASS", current_head=head, code=None):
            catalog["revision"] = sequence
            catalog["publishedAt"] = datetime.now(UTC).isoformat()
            catalog["records"].append(
                {
                    "sequence": sequence,
                    "workspaceId": str(co["companyId"]),
                    "generationId": p["scope"]["generationId"],
                    "policyDigest": p["scope"]["policyDigest"],
                    "codeRevision": code or config["codeRevision"],
                    "dbRevision": original["envelope"]["dbRevision"],
                    "recordedAt": datetime.now(UTC).isoformat(),
                    "result": result,
                    "head": current_head,
                }
            )
            return publish(catalog_folder, catalog, authority, monkeypatch)

        update(1)
        initial_catalog = deepcopy(catalog)

        def check(name):
            output = folders["reports"] / name
            module.recheck_restore(
                url=make_url(os.environ["TEST_DATABASE_URL"])
                .set(database=database)
                .render_as_string(hide_password=False),
                source_url=os.environ["TEST_DATABASE_URL"],
                artifact=args["artifact"],
                checkpoint_file=args["checkpoint_file"],
                head=args["head"],
                expected_checkpoint_digest=args["expected_checkpoint_digest"],
                restore_document=original,
                output=output,
                config=checked_config,
                check_catalog=True,
            )
            return json.loads(output.read_bytes())

        def collect(document):
            return sign_current(
                engine,
                company_id=co["companyId"],
                code_revision=config["codeRevision"],
                public_keys=from_environment(),
                signer=keys["collector"],
                signer_id="collector",
                restore_recheck=document,
            )

        def status():
            data = api(admin, co, "operations", method="GET").json()["data"]
            assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
            return data["evidenceChecks"][2]

        first = check("first-catalog.json")
        assert first["envelope"]["version"] == 4
        accepted = collect(first)
        assert accepted["envelope"]["result"] == "PARTIAL"
        assert api(admin, co, "operating-evidence", accepted).status_code == 200
        assert status()["restoreRecheck"]["catalogObservation"]["reason"] == "MATCH"
        assert not status()["restoreRecheck"]["catalogObservation"][
            "externalIndependenceVerified"
        ]
        assert api(admin, co, "operating-evidence", first).status_code == 400
        failures = []
        for seq, result, selected, code, reason in [
            (2, "FAIL", None, None, "LATEST_FAIL"),
            (3, "PARTIAL", head, None, "LATEST_PARTIAL"),
            (4, "PASS", None, None, "ORIGINAL_MISSING"),
            (5, "PASS", head, "f" * 8, "CONTEXT_MISMATCH"),
        ]:
            update(seq, result, selected, code)
            assert status()["state"] == "INVALID"
            assert "restoreRecheck" not in status()
            with pytest.raises((ApiError, ValueError)):
                collect(first)
            current = check(f"failed-{seq}.json")
            assert current["envelope"]["result"] == "BLOCKED"
            assert current["envelope"]["catalogObservation"]["reason"] == reason
            failed = collect(current)
            assert failed["envelope"]["result"] == "FAIL"
            assert api(admin, co, "operating-evidence", failed).status_code == 200
            assert status()["state"] == "FAILED"
            failures.append(failed["envelope"]["runId"])
        # A higher catalog number pointing at the same old success is insufficient.
        update(6)
        selected = check("replayed-success.json")
        assert selected["envelope"]["result"] == "PARTIAL"
        with pytest.raises(ApiError) as rejected:
            collect(selected)
        assert rejected.value.code == "OPERATING_RECOVERY_REQUIRED"
        with monkeypatch.context() as bypass:
            bypass.setattr(
                "fs.gw.checkpoint_catalog.require_history", lambda *a, **k: None
            )
            unsafe = collect(selected)
        assert api(admin, co, "operating-evidence", unsafe).status_code == 400
        # Rolling back the configured pin/file also cannot roll back retained floors.
        publish(catalog_folder, initial_catalog, authority, monkeypatch)
        rollback = check("rolled-back-catalog.json")
        with pytest.raises(ApiError):
            collect(rollback)
        assert status()["state"] == "INVALID"
        # A fresh actual checkpoint and a new closed restore repair the known failure.
        new_checkpoint, new_head = (
            folders["checkpoints"] / "recovered.fsbackup",
            folders["checkpoints"] / "recovered-head.json",
        )
        captured = module.checkpoint(
            url=os.environ["TEST_DATABASE_URL"],
            artifact=args["artifact"],
            output=new_checkpoint,
            head=new_head,
            config=config,
        )
        args = args | {
            "checkpoint_file": new_checkpoint,
            "head": new_head,
            "expected_checkpoint_digest": captured["checkpointDigest"],
        }
        database, original, original_path = restore(args)
        update(7, current_head=json.loads(new_head.read_bytes()))
        fresh = check("fresh-catalog.json")
        recovered = collect(fresh)
        assert api(admin, co, "operating-evidence", recovered).status_code == 200
        assert status()["state"] == "PARTIAL"
        with engine.connect() as c:
            assert c.scalar(
                text(
                    "SELECT count(*) FROM gw.operating_evidence WHERE kind='ACCEPTANCE' AND result='FAIL'"
                )
            ) == len(failures)
        # Configuration removal cannot downgrade a company which already adopted v4.
        downgrade = check("downgrade-source.json")
        downgrade["envelope"].update(
            version=3, scope="CURRENT_SOURCE_RESTORE_AND_SIGNED_CHECKPOINT_HEAD"
        )
        downgrade["envelope"].pop("catalogObservation")
        downgrade["signature"] = base64.b64encode(
            keys["rechecker"].sign(canonical(downgrade["envelope"]))
        ).decode()
        with monkeypatch.context() as missing:
            missing.delenv(ENV)
            assert status()["state"] == "INVALID"
            with pytest.raises(ApiError):
                collect(downgrade)
            with monkeypatch.context() as bypass:
                bypass.setattr(
                    "fs.gw.checkpoint_catalog.require_history", lambda *a, **k: None
                )
                unsafe = collect(downgrade)
            assert api(admin, co, "operating-evidence", unsafe).status_code == 400
        # Recheck CLI reads only its configured snapshot and writes a new private file.
        env = os.environ.copy()
        env.update(
            FS_GW_RECHECK_DATABASE_URL=make_url(os.environ["TEST_DATABASE_URL"])
            .set(database=database)
            .render_as_string(hide_password=False),
            FS_GW_SOURCE_CHECKPOINT_DATABASE_URL=os.environ["TEST_DATABASE_URL"],
        )
        output = folders["reports"] / "catalog-cli.json"
        command = [
            sys.executable,
            str(Path(__file__).parents[2] / "tools/gw_backup.py"),
            "recheck-restore",
            "--check-current-source",
            "--check-checkpoint-catalog",
            "--backup",
            str(args["artifact"]),
            "--checkpoint",
            str(args["checkpoint_file"]),
            "--head",
            str(args["head"]),
            "--expected-checkpoint-digest",
            args["expected_checkpoint_digest"],
            "--restore-evidence",
            str(original_path),
            "--output",
            str(output),
        ]
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        assert process.returncode == 0 and output.stat().st_mode & 0o777 == 0o600
        assert json.loads(output.read_bytes())["envelope"]["version"] == 4
        collector_key = folders["reports"] / "catalog-collector-key"
        collector_key.write_bytes(keys["collector"].private_bytes_raw())
        collector_key.chmod(0o600)
        collector_env = env | {
            "FS_GW_RUNNER_KEY_FILE": str(collector_key),
            "FS_GW_RUNNER_KEY_ID": "collector",
            "FS_GW_PREFLIGHT_DATABASE_URL": os.environ["TEST_DATABASE_URL"],
        }
        acceptance_file = folders["reports"] / "catalog-acceptance-cli.json"
        collect_command = [
            sys.executable,
            str(Path(__file__).parents[2] / "tools/gw_acceptance_collect.py"),
            "--current-company-id",
            str(co["companyId"]),
            "--signed-reconciliation",
            "--restore-recheck",
            str(output),
            "--output",
            str(acceptance_file),
        ]
        process = subprocess.run(
            collect_command,
            env=collector_env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert (
            process.returncode == 0 and acceptance_file.stat().st_mode & 0o777 == 0o600
        )
        assert (
            json.loads(acceptance_file.read_bytes())["envelope"]["result"] == "PARTIAL"
        )
        absent = folders["reports"] / "missing-catalog-cli.json"
        command[-1] = str(absent)
        env.pop(ENV)
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        assert process.returncode == 1 and not absent.exists()
        update(8, result="FAIL", current_head=None)
        env[ENV] = os.environ[ENV]
        collector_env[ENV] = os.environ[ENV]
        blocked_file = folders["reports"] / "catalog-blocked-cli.json"
        command[-1] = str(blocked_file)
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, timeout=60, check=False
        )
        assert process.returncode == 2 and blocked_file.stat().st_mode & 0o777 == 0o600
        collect_command[-3] = str(blocked_file)
        collect_command[-1] = str(
            folders["reports"] / "catalog-failed-acceptance-cli.json"
        )
        process = subprocess.run(
            collect_command,
            env=collector_env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert process.returncode == 2
        failed_cli = json.loads(Path(collect_command[-1]).read_bytes())
        assert failed_cli["envelope"]["result"] == "FAIL"
        assert status()["state"] == "INVALID"  # CLI never auto-registers.
        assert api(admin, co, "operating-evidence", failed_cli).status_code == 200
        assert status()["state"] == "FAILED"
        # Deleting a catalog authority without a durable retirement/revocation is a configuration error.
        with monkeypatch.context() as revoked:
            revoked.setenv(
                "FS_GW_EVIDENCE_PUBLIC_KEYS",
                json.dumps({k: v for k, v in public.items() if k != "catalog"}),
            )
            revoked.setenv(
                "FS_GW_EVIDENCE_KEY_SCOPES",
                json.dumps(
                    {
                        "version": 1,
                        "keys": {
                            k: v for k, v in scopes["keys"].items() if k != "catalog"
                        },
                    }
                ),
            )
            assert status()["state"] == "CONFIG_REQUIRED"
            assert "restoreRecheck" not in status()
        assert (
            status()["state"] == "FAILED"
        )  # Exact retained current failure, never old success.
    finally:
        with cleanup.connect() as c:
            for name in targets:
                c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        cleanup.dispose()
