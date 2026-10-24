"""Real recovery cycles preserve failures and require new closed restore targets."""

# ruff: noqa: F401,F811
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_gw_restore_recheck_db import add_keys
from test_hr_work import company_env

from fs.common.errors import ApiError
from fs.gw.acceptance_sources import sign_current
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import timestamp


@pytest.mark.parametrize("missing_original", [False, True])
def test_real_fail_new_checkpoint_closed_restore_and_partial_recovery(
    company_env, backup_env, monkeypatch, missing_original
):
    engine, co, admin, _staff = company_env
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    created = []
    counter = 0
    try:

        def restore(current):
            nonlocal counter
            counter += 1
            current = current | {
                "report": folders["reports"] / f"restore-report-{counter}.json",
                "evidence": folders["reports"] / f"restore-proof-{counter}.json",
            }
            result = module.restore(**current)
            created.append(result["database"])
            document = json.loads(current["evidence"].read_bytes())
            assert api(admin, co, "operating-evidence", document).status_code == 200
            # The runner and PG clocks can differ within the declared 30s skew.
            # Readiness intentionally rejects even a slightly future completion.
            # Observe after it actually passes; never relax the product rule.
            with engine.connect() as c:
                database_clock = c.scalar(text("SELECT clock_timestamp()"))
            delay = (
                timestamp(document["envelope"]["finishedAt"]) - database_clock
            ).total_seconds()
            assert delay < 30
            if delay >= 0:
                time.sleep(delay + 0.02)
            return result["database"], document

        backup = json.loads((folders["backups"] / "backup.json").read_bytes())
        assert api(admin, co, "operating-evidence", backup).status_code == 200
        database, original = restore(args)
        keys, recheck_config = add_keys(
            company_env, monkeypatch, config, folders["reports"]
        )
        # A different checkpoint captured BEFORE the failure is still too old.
        earlier_checkpoint = folders["checkpoints"] / "before-failure.fsbackup"
        earlier_head = folders["checkpoints"] / "before-failure-head.json"
        earlier = module.checkpoint(
            url=os.environ["TEST_DATABASE_URL"],
            artifact=args["artifact"],
            output=earlier_checkpoint,
            head=earlier_head,
            config=config,
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
            )

        def check(current, name, target, proof):
            output = folders["reports"] / name
            module.recheck_restore(
                url=make_url(os.environ["TEST_DATABASE_URL"])
                .set(database=target)
                .render_as_string(hide_password=False),
                source_url=os.environ["TEST_DATABASE_URL"],
                artifact=current["artifact"],
                checkpoint_file=current["checkpoint_file"],
                head=current["head"],
                expected_checkpoint_digest=current["expected_checkpoint_digest"],
                restore_document=proof,
                output=output,
                config=recheck_config,
            )
            return json.loads(output.read_bytes())

        def status():
            data = api(admin, co, "operations", method="GET").json()["data"]
            assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
            return data

        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE core.app_user SET security_version=security_version+1 WHERE login_id='hugh-staff'"
                )
            )
        failed = collect(check(args, "drift.json", database, original))
        assert failed["envelope"]["result"] == "FAIL"
        assert api(admin, co, "operating-evidence", failed).status_code == 200
        failed_run = failed["envelope"]["runId"]
        assert status()["recovery"]["state"] == "NEW_RESTORE_REQUIRED"
        if missing_original:
            with engine.begin() as c:
                c.execute(
                    text(
                        "UPDATE gw.operating_evidence SET metrics=metrics-'_signedEnvelope' WHERE run_id=cast(:run AS uuid)"
                    ),
                    {"run": failed_run},
                )
            assert status()["recovery"]["state"] == "NEW_BACKUP_REQUIRED"
            assert not status()["recovery"]["failureOriginalVerified"]
        # Reverting the changed source cannot erase the already registered failure.
        with engine.begin() as c:
            c.execute(
                text(
                    "UPDATE core.app_user SET security_version=security_version-1 WHERE login_id='hugh-staff'"
                )
            )
        reverted = check(args, "reverted.json", database, original)
        assert reverted["envelope"]["result"] == "PARTIAL"
        with pytest.raises(ApiError):
            collect(reverted)
        # Even an issuing client that skips the recovery precheck cannot register it.
        with monkeypatch.context() as unchecked:
            unchecked.setattr("fs.gw.recovery.require_recovery", lambda *a, **k: None)
            bypass = collect(reverted)
        rejected = api(admin, co, "operating-evidence", bypass)
        assert rejected.status_code == 400
        assert rejected.json()["error"]["code"] == "OPERATING_RECOVERY_REQUIRED"
        collector_file = folders["reports"] / "collector-key"
        collector_file.write_bytes(keys["collector"].private_bytes_raw())
        collector_file.chmod(0o600)
        env = os.environ.copy()
        env.update(
            FS_GW_RUNNER_KEY_FILE=str(collector_file),
            FS_GW_RUNNER_KEY_ID="collector",
            FS_GW_PREFLIGHT_DATABASE_URL=os.environ["TEST_DATABASE_URL"],
            FS_CODE_REVISION=config["codeRevision"],
        )
        output = folders["reports"] / "blocked-collection.json"
        process = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).parents[2] / "tools/gw_acceptance_collect.py"),
                "--current-company-id",
                str(co["companyId"]),
                "--signed-reconciliation",
                "--restore-recheck",
                str(folders["reports"] / "reverted.json"),
                "--output",
                str(output),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        assert process.returncode == 1 and not output.exists()
        assert ("새 백업" if missing_original else "새 격리 복원") in process.stdout
        # Another physical target with the old checkpoint also cannot hide the failure.
        database, original = restore(args)
        with pytest.raises(ApiError):
            collect(check(args, "same-checkpoint.json", database, original))
        assert status()["recovery"]["state"] in {
            "NEW_BACKUP_REQUIRED",
            "NEW_RESTORE_REQUIRED",
        }
        if not missing_original:
            stale_args = args | {
                "checkpoint_file": earlier_checkpoint,
                "head": earlier_head,
                "expected_checkpoint_digest": earlier["checkpointDigest"],
            }
            stale_database, stale_restore = restore(stale_args)
            stale = check(
                stale_args, "pre-failure-checkpoint.json", stale_database, stale_restore
            )
            assert stale["envelope"]["version"] == 3
            assert stale["envelope"]["result"] == "PARTIAL"
            with pytest.raises(ApiError) as rejected:
                collect(stale)
            assert rejected.value.code == "OPERATING_RECOVERY_REQUIRED"
            with monkeypatch.context() as unchecked:
                unchecked.setattr(
                    "fs.gw.recovery.require_recovery", lambda *a, **k: None
                )
                bypass = collect(stale)
            assert api(admin, co, "operating-evidence", bypass).status_code == 400
        # Missing historical originals need a fresh backup before a new checkpoint.
        if missing_original:
            artifact = folders["backups"] / "fresh.fsbackup"
            proof = folders["backups"] / "fresh.json"
            module.backup(
                url=os.environ["TEST_DATABASE_URL"],
                company_id=co["companyId"],
                output=artifact,
                evidence=proof,
                config=config,
            )
            assert (
                api(
                    admin, co, "operating-evidence", json.loads(proof.read_bytes())
                ).status_code
                == 200
            )
            args = args | {"artifact": artifact}
        new_checkpoint, new_head = (
            folders["checkpoints"] / "recovery.fsbackup",
            folders["checkpoints"] / "recovery-head.json",
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
        database, original = restore(args)
        pending = status()
        assert pending["recovery"]["state"] == "RECHECK_REQUIRED", {
            "state": pending["recovery"]["state"],
            "checks": [
                (check["kind"], check["state"], check["detail"])
                for check in pending["evidenceChecks"]
            ],
        }
        fresh = check(args, "recovered.json", database, original)
        accepted = collect(fresh)
        assert accepted["envelope"]["result"] == "PARTIAL"
        assert api(admin, co, "operating-evidence", accepted).status_code == 200
        current = status()
        assert current["evidenceChecks"][2]["state"] == "PARTIAL"
        assert current["recovery"]["state"] == "RECOVERY_PARTIAL"
        assert current["recovery"]["failedRunId"] == failed_run
        head = current["evidenceChecks"][2]["restoreRecheck"]["checkpointHead"]
        assert head["capturedAt"] == captured["capturedAt"]
        assert head["signatureVerified"] and not head["latestIndependentlyVerified"]
        # Strip the new proof and issue a fresh, correctly signed old contract.
        import base64

        from fs.gw.operating_contract import canonical

        downgrade = check(args, "downgrade-source.json", database, original)
        downgrade["envelope"].update(
            version=2, scope="CURRENT_SOURCE_AND_RESTORED_CHECKPOINT_RESTRICTIONS"
        )
        downgrade["envelope"].pop("checkpointHead")
        downgrade["signature"] = base64.b64encode(
            keys["rechecker"].sign(canonical(downgrade["envelope"]))
        ).decode()
        with pytest.raises(ApiError):
            collect(downgrade)
        with monkeypatch.context() as unchecked:
            unchecked.setattr(
                "fs.gw.acceptance_sources.require_new_observation",
                lambda *a, **k: None,
            )
            unchecked.setattr("fs.gw.recovery.require_recovery", lambda *a, **k: None)
            bypass = collect(downgrade)
        assert api(admin, co, "operating-evidence", bypass).status_code == 400
        # Revoking only CHECKPOINT use invalidates the nested HEAD, even while
        # its runner remains authorized for BACKUP/RESTORE.
        scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
        scopes["keys"][config["signerId"]]["purposes"].remove("CHECKPOINT")
        with monkeypatch.context() as revoked:
            revoked.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
            assert status()["evidenceChecks"][2]["state"] == "INVALID"
            assert "restoreRecheck" not in status()["evidenceChecks"][2]
        assert status()["evidenceChecks"][2]["state"] == "PARTIAL"
        with engine.connect() as c:
            assert (
                c.scalar(
                    text(
                        "SELECT count(*) FROM gw.operating_evidence WHERE run_id=cast(:run AS uuid) AND result='FAIL'"
                    ),
                    {"run": failed_run},
                )
                == 1
            )
        # A newer restore failure must be selected; never fall back to this partial cycle.
        failed_restore = json.loads(json.dumps(original))
        failed_restore["envelope"].update(runId=str(uuid4()), result="FAIL")
        failed_restore["envelope"]["metrics"]["sessionsInvalidated"] = False
        failed_restore["envelope"]["metrics"]["restoreDiagnostics"][
            "executionObservation"
        ].update(unrevokedSessions=1, result="BLOCKED")
        failed_restore["signature"] = base64.b64encode(
            config["signer"].sign(canonical(failed_restore["envelope"]))
        ).decode()
        assert api(admin, co, "operating-evidence", failed_restore).status_code == 200
        assert status()["recovery"]["state"] == "NEW_RESTORE_REQUIRED"
        assert status()["evidenceChecks"][2]["state"] == "INVALID"
    finally:
        with cleanup.connect() as c:
            for database in created:
                c.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        cleanup.dispose()
