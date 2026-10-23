"""Actual current-source comparisons after a real dump and isolated restore."""

# ruff: noqa: F401,F811
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_gw_restore_recheck_db import add_keys
from test_hr_work import company_env

from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.gw.acceptance_sources import sign_current
from fs.gw.evidence_trust import from_environment


def test_actual_source_changes_cannot_hide_behind_unchanged_closed_restore(
    company_env, backup_env, monkeypatch
):
    engine, co, admin, _staff = company_env
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    restored_result = module.restore(**args)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    target_url = (
        make_url(os.environ["TEST_DATABASE_URL"])
        .set(database=restored_result["database"])
        .render_as_string(hide_password=False)
    )
    try:
        keys, checked_config = add_keys(
            company_env, monkeypatch, config, folders["reports"]
        )
        original = json.loads(args["evidence"].read_bytes())
        backup = json.loads((folders["backups"] / "backup.json").read_bytes())
        assert api(admin, co, "operating-evidence", backup).status_code == 200
        assert api(admin, co, "operating-evidence", original).status_code == 200

        def check(name, source_url=os.environ["TEST_DATABASE_URL"]):
            output = folders["reports"] / name
            result = module.recheck_restore(
                url=target_url,
                source_url=source_url,
                artifact=args["artifact"],
                checkpoint_file=args["checkpoint_file"],
                head=args["head"],
                expected_checkpoint_digest=args["expected_checkpoint_digest"],
                restore_document=original,
                output=output,
                config=checked_config,
            )
            assert output.stat().st_mode & 0o777 == 0o600
            return json.loads(output.read_bytes()), result

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

        def state():
            data = api(admin, co, "operations", method="GET").json()["data"]
            assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
            return data["evidenceChecks"][2]

        document, result = check("current-match.json")
        assert result["result"] == "PARTIAL"
        source = document["envelope"]["sourceObservation"]
        assert source["reason"] == "MATCH" and not any(source["changedGroups"].values())
        assert (
            api(admin, co, "operating-evidence", collect(document)).status_code == 200
        )
        assert state()["state"] == "PARTIAL"
        assert state()["restoreRecheck"]["sourceObservation"]["reason"] == "MATCH"
        # Older target-only rechecks cannot omit the already registered source check.
        target_only, _ = check("target-only.json", source_url=None)
        with pytest.raises(ApiError):
            collect(target_only)
        # Server registration still enforces this when an issuing client skips its precheck.
        with monkeypatch.context() as unchecked_client:
            unchecked_client.setattr(
                "fs.gw.acceptance_sources.require_new_observation", lambda *a, **k: None
            )
            downgraded = collect(target_only)
        assert api(admin, co, "operating-evidence", downgraded).status_code == 400
        # Attempt an actual UPDATE inside the new source adapter's read transaction.
        with tempfile.TemporaryDirectory(dir=folders["reports"]) as directory:
            temp = Path(directory)
            (temp / "checkpoint").mkdir(mode=0o700)
            manifest = module.unpack(args["artifact"], temp, config, kind="BACKUP")
            changes = module.unpack(
                args["checkpoint_file"], temp / "checkpoint", config, kind="CHECKPOINT"
            )
            with engine.connect() as c:
                baseline = c.scalar(
                    text("SELECT sum(security_version) FROM core.app_user")
                )

            def attempt_write(conn, cursor, statement, parameters, context, many):
                if statement == "SELECT transaction_timestamp()":
                    conn.execute(
                        text(
                            "UPDATE core.app_user SET security_version=security_version+1"
                        )
                    )

            event.listen(engine, "before_cursor_execute", attempt_write)
            try:
                with monkeypatch.context() as use_owned_engine:
                    use_owned_engine.setattr(
                        module, "create_engine", lambda *a, **k: engine
                    )
                    denied = module.observe_current_source(
                        url=os.environ["TEST_DATABASE_URL"],
                        manifest=manifest,
                        changes=changes,
                    )
                assert not denied["sourceMeasured"] and denied["changedGroups"] is None
            finally:
                event.remove(engine, "before_cursor_execute", attempt_write)
            with engine.connect() as c:
                assert (
                    c.scalar(text("SELECT sum(security_version) FROM core.app_user"))
                    == baseline
                )
        # Check each capture family without changing the restored target.
        updates = [
            (
                "UPDATE core.app_user SET security_version=security_version+1 WHERE login_id='hugh-staff'",
                "core",
            ),
            (
                "UPDATE gw.person SET is_active=NOT is_active WHERE workspace_id=:w AND id IN (SELECT person_id FROM gw.person_identity_binding WHERE workspace_id=:w AND user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff'))",
                "gw",
            ),
            (
                "UPDATE hr.work_account SET is_active=NOT is_active WHERE user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')",
                "hr",
            ),
        ]
        for index, (statement, group) in enumerate(updates):
            with engine.begin() as c:
                changed = c.execute(text(statement), {"w": co["companyId"]}).rowcount
                assert changed > 0
            document, result = check(f"changed-{index}.json")
            assert result["result"] == "BLOCKED"
            assert document["envelope"]["measurement"]["result"] == "PARTIAL"
            source = document["envelope"]["sourceObservation"]
            assert source["sourceMeasured"] and source["changedGroups"][group] > 0
            assert source["currentStateDigest"] != source["checkpointStateDigest"]
            acceptance = collect(document)
            assert acceptance["envelope"]["result"] == "FAIL"
            assert api(admin, co, "operating-evidence", acceptance).status_code == 200
            assert state()["state"] == "FAILED"
            assert state()["restoreRecheck"]["sourceObservation"]["reason"] == "CHANGED"
        # Wrong physical source must fail before capturing account/permission rows.
        with pytest.raises(BackupError):
            check("wrong-source.json", target_url)
        assert not (folders["reports"] / "wrong-source.json").exists()
        # A new checkpoint is not an authorization to reuse an older restore.
        new_checkpoint, new_head = (
            folders["checkpoints"] / "new.fsbackup",
            folders["checkpoints"] / "new-head.json",
        )
        captured = module.checkpoint(
            url=os.environ["TEST_DATABASE_URL"],
            artifact=args["artifact"],
            output=new_checkpoint,
            head=new_head,
            config=config,
        )
        with pytest.raises(BackupError):
            module.recheck_restore(
                url=target_url,
                source_url=os.environ["TEST_DATABASE_URL"],
                artifact=args["artifact"],
                checkpoint_file=new_checkpoint,
                head=new_head,
                expected_checkpoint_digest=captured["checkpointDigest"],
                restore_document=original,
                output=folders["reports"] / "wrong-checkpoint.json",
                config=checked_config,
            )
        # No DATABASE_URL fallback when the explicitly requested source URL is absent.
        env = os.environ.copy()
        env["FS_GW_RECHECK_DATABASE_URL"] = target_url
        env.pop("FS_GW_SOURCE_CHECKPOINT_DATABASE_URL", None)
        output = folders["reports"] / "missing-source.json"
        command = [
            sys.executable,
            str(Path(__file__).parents[2] / "tools/gw_backup.py"),
            "recheck-restore",
            "--check-current-source",
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
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, check=False, timeout=60
        )
        assert process.returncode == 1 and not output.exists()
        # Connection refusal records unknown source measurements; target is still measured.
        missing_url = (
            make_url(os.environ["TEST_DATABASE_URL"])
            .set(database="gw_missing_source_45_test")
            .render_as_string(hide_password=False)
        )
        env["FS_GW_SOURCE_CHECKPOINT_DATABASE_URL"] = missing_url
        process = subprocess.run(
            command, env=env, capture_output=True, text=True, check=False, timeout=60
        )
        assert process.returncode == 2 and output.stat().st_mode & 0o777 == 0o600
        unavailable = json.loads(output.read_bytes())
        source = unavailable["envelope"]["sourceObservation"]
        assert not source["sourceMeasured"] and source["changedGroups"] is None
        assert source["currentStateDigest"] is None and source["contextMatches"] is None
        assert unavailable["envelope"]["measurement"]["result"] == "PARTIAL"
        assert (
            api(admin, co, "operating-evidence", collect(unavailable)).status_code
            == 200
        )
        assert state()["state"] == "FAILED"
        assert not state()["restoreRecheck"]["sourceObservation"]["sourceMeasured"]
    finally:
        with cleanup.connect() as c:
            c.execute(
                text(f'DROP DATABASE "{restored_result["database"]}" WITH (FORCE)')
            )
        cleanup.dispose()
