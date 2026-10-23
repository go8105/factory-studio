"""Real dump/restore observation, changed-target rejection and signed failure."""

# ruff: noqa: F401,F811
import json
import os
import tempfile
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_hr_work import company_env

from fs.core.backup import BackupError


def restored(env, backup_env):
    engine, co, _admin, _staff = env
    module, config, folders, _ = backup_env
    url = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "database.fsbackup"
    backup = folders["backups"] / "backup.json"
    module.backup(
        url=url,
        company_id=co["companyId"],
        output=artifact,
        evidence=backup,
        config=config,
    )
    # Checkpoint source records deny these two grants after the backup.
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE gw.person_identity_binding SET state='SUSPENDED',closed_at=clock_timestamp() WHERE workspace_id=:w AND user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')"
            ),
            {"w": co["companyId"]},
        )
        c.execute(
            text(
                "UPDATE hr.work_account SET is_active=false WHERE user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')"
            )
        )
    checkpoint = folders["checkpoints"] / "latest.fsbackup"
    head = folders["checkpoints"] / "head.json"
    captured = module.checkpoint(
        url=url, artifact=artifact, output=checkpoint, head=head, config=config
    )
    admin_url = (
        make_url(url).set(database="postgres").render_as_string(hide_password=False)
    )
    args = {
        "admin_url": admin_url,
        "artifact": artifact,
        "checkpoint_file": checkpoint,
        "head": head,
        "expected_checkpoint_digest": captured["checkpointDigest"],
        "report": folders["reports"] / "result.json",
        "evidence": folders["reports"] / "restore.json",
        "config": config,
    }
    return args


def test_actual_target_rechecks_are_readonly_and_detect_reenabled_permissions(
    company_env, backup_env
):
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    result = module.restore(**args)
    target_url = make_url(os.environ["TEST_DATABASE_URL"]).set(
        database=result["database"]
    )
    target = create_engine(target_url)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    try:
        with tempfile.TemporaryDirectory(dir=folders["reports"]) as directory:
            base = Path(directory)
            (base / "backup").mkdir(mode=0o700)
            (base / "checkpoint").mkdir(mode=0o700)
            manifest = module.unpack(
                args["artifact"], base / "backup", config, kind="BACKUP"
            )
            changes = module.unpack(
                args["checkpoint_file"], base / "checkpoint", config, kind="CHECKPOINT"
            )

            def measure():
                with target.connect() as c, c.begin():
                    return module.observe_restoration(
                        c,
                        manifest=manifest,
                        changes=changes,
                        checkpoint_digest=args["expected_checkpoint_digest"],
                    )

            assert measure()["result"] == "PARTIAL"
            checks = [
                (
                    "UPDATE core.auth_session SET revoked_at=NULL",
                    "UPDATE core.auth_session SET revoked_at=clock_timestamp()",
                    "unrevokedSessions",
                ),
                (
                    "UPDATE gw.person_identity_binding SET state='ACTIVE',closed_at=NULL WHERE state='SUSPENDED'",
                    "UPDATE gw.person_identity_binding SET state='SUSPENDED',closed_at=clock_timestamp() WHERE user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')",
                    "gwViolations",
                ),
                (
                    "UPDATE hr.work_account SET is_active=true WHERE user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')",
                    "UPDATE hr.work_account SET is_active=false WHERE user_id=(SELECT id FROM core.app_user WHERE login_id='hugh-staff')",
                    "hrViolations",
                ),
            ]
            for mutation, undo, field in checks:
                with target.begin() as c:
                    assert c.execute(text(mutation)).rowcount > 0
                observed = measure()
                assert observed["result"] == "BLOCKED" and observed[field] > 0
                with target.begin() as c:
                    c.execute(text(undo))
                assert measure()["result"] == "PARTIAL"
            with target.begin() as c:
                role = {
                    "u": c.scalar(text("SELECT min(id) FROM core.app_user")),
                    "r": c.scalar(
                        text(
                            "INSERT INTO core.role(role_key,description) VALUES('SYNTHETIC_OBSERVATION','synthetic restore check') RETURNING id"
                        )
                    ),
                }
                c.execute(
                    text("INSERT INTO core.user_role(user_id,role_id) VALUES(:u,:r)"),
                    dict(role),
                )
            assert measure()["coreViolations"] > 0
            with target.begin() as c:
                c.execute(
                    text("DELETE FROM core.user_role WHERE user_id=:u AND role_id=:r"),
                    dict(role),
                )
                c.execute(text("DELETE FROM core.role WHERE id=:r"), dict(role))
            for clause, undo, field in [
                ("GRANT CONNECT ON", "REVOKE CONNECT ON", "publicConnectRevoked"),
            ]:
                with cleanup.connect() as c:
                    c.execute(
                        text(f'{clause} DATABASE "{result["database"]}" TO PUBLIC')
                    )
                observed = measure()
                assert observed["result"] == "BLOCKED" and not observed[field]
                with cleanup.connect() as c:
                    c.execute(
                        text(f'{undo} DATABASE "{result["database"]}" FROM PUBLIC')
                    )
            with cleanup.connect() as c:
                c.execute(
                    text(f'ALTER DATABASE "{result["database"]}" CONNECTION LIMIT 1')
                )
            assert not measure()["connectionLimitZero"]
            with cleanup.connect() as c:
                c.execute(
                    text(f'ALTER DATABASE "{result["database"]}" CONNECTION LIMIT 0')
                )
            assert measure()["result"] == "PARTIAL"

            def attempt_write(conn, cursor, statement, parameters, ctx, many):
                if statement == "SELECT transaction_timestamp()":
                    conn.execute(text("UPDATE core.auth_session SET revoked_at=NULL"))

            event.listen(target, "before_cursor_execute", attempt_write)
            try:
                with pytest.raises(DBAPIError):
                    measure()
            finally:
                event.remove(target, "before_cursor_execute", attempt_write)
    finally:
        target.dispose()
        with cleanup.connect() as c:
            c.execute(text(f'DROP DATABASE "{result["database"]}" WITH (FORCE)'))
        cleanup.dispose()


def test_failed_post_replay_observation_freezes_target_and_retains_signed_fail(
    company_env, backup_env, monkeypatch
):
    module, _config, _folders, _ = backup_env
    args = restored(company_env, backup_env)
    replay = module.core_checkpoint.replay

    def broken_replay(c, checkpoint):
        result = replay(c, checkpoint)
        c.execute(text("UPDATE core.auth_session SET revoked_at=NULL"))
        return result  # Recheck must catch stale success flags from a replay adapter.

    monkeypatch.setattr(module.core_checkpoint, "replay", broken_replay)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    try:
        with pytest.raises(BackupError):
            module.restore(**args)
        report = json.loads(args["report"].read_text())
        assert report["result"] == "FAIL" and report["connectionsDisabled"]
        proof = json.loads(args["evidence"].read_text())
        assert proof["envelope"]["result"] == "FAIL"
        assert (
            proof["envelope"]["metrics"]["restoreDiagnostics"]["executionObservation"][
                "unrevokedSessions"
            ]
            > 0
        )
        _engine, co, admin, _ = company_env
        assert api(admin, co, "operating-evidence", proof).status_code == 200
        state = api(admin, co, "operations", method="GET").json()["data"]
        assert state["evidenceChecks"][1]["state"] == "FAILED" and not state["ready"]
        with cleanup.connect() as c:
            assert not c.scalar(
                text("SELECT datallowconn FROM pg_database WHERE datname=:name"),
                {"name": report["database"]},
            )
    finally:
        if args["report"].exists():
            report = json.loads(args["report"].read_text())
            with cleanup.connect() as c:
                c.execute(text(f'DROP DATABASE "{report["database"]}" WITH (FORCE)'))
        cleanup.dispose()
