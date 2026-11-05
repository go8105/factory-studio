"""Actual PG dump/restore: revoked-then-resumed and unconfirmed history stay denied."""

# ruff: noqa:F811
import json
import os

import pytest
from fs.common.auth import _resolve_member
from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.core.security.crypto import opaque_token
from fs.core.security.journal import ZERO, append, verify
from fs.core.security.journal_bundle import export
from fs.core.security.journal_witness import publish
from fs.core.security.recording import record_user
from fs.core.security.service import verify_login
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env  # noqa: F401
from test_gw_company import context
from test_gw_company_work import api, ok
from test_hr_users import manage
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401


@pytest.mark.parametrize("rollover", [False, True])
def test_actual_history_bound_restore_restricts_without_changing_source(
    company_env, backup_env, journal, monkeypatch, rollover
):
    engine, co, admin, staff = company_env
    module, config, folders, _ = backup_env
    directory, key = journal
    if rollover:
        copies = directory.parent / "delivery-copies"
        receipts = directory.parent / "delivery-witness"
        for folder in (copies, receipts):
            folder.mkdir(mode=0o700)
        witness_key = directory.parent / "delivery-key"
        witness_key.write_bytes(b"w" * 32)
        witness_key.chmod(0o600)
        monkeypatch.setenv("FS_GW_JOURNAL_WITNESS_DIR", str(receipts))
        monkeypatch.setenv("FS_GW_JOURNAL_WITNESS_KEY_FILE", str(witness_key))
    admin_context = context(engine, admin)
    staff_context = context(engine, staff)
    admin_id = admin_context.user_id
    staff_id = staff_context.user_id
    pending_token, pending_hash = opaque_token()
    # Synthetic unfinished login request belongs to the pre-backup fixture.
    with engine.begin() as c:
        pending_id = c.execute(
            text("""INSERT INTO core.authentication_challenge
            (user_id,purpose,token_hash,state,security_version,attempt_count,expires_at,created_at)
            SELECT id,'LOGIN_MFA',:t,'PENDING',security_version,0,
                clock_timestamp()+interval '5 minutes',clock_timestamp()
            FROM core.app_user WHERE id=:u RETURNING id"""),
            {"u": admin_id, "t": pending_hash},
        ).scalar_one()
    with engine.begin() as c:
        record_user(c, admin_id, "synthetic.baseline")
    # File survives an absent/rolled-back DB confirmation before the backup snapshot.
    append(
        directory,
        key,
        {
            "coverage": "core.security.intent.v1",
            "userId": staff_id,
            "operation": "synthetic.unconfirmed",
            "snapshot": {},
        },
    )
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", verify(directory, key)["head"])
    source = os.environ["TEST_DATABASE_URL"]
    artifact = folders["backups"] / "history.fsbackup"
    with engine.begin() as pending:
        record_user(pending, staff_id, "synthetic.pending.before-snapshot")
        monkeypatch.setenv(
            "FS_GW_JOURNAL_EXPECTED_HEAD", verify(directory, key)["head"]
        )
        if rollover:
            publish(
                directory,
                key,
                verify(directory, key)["head"],
                copies,
                receipts,
                b"w" * 32,
            )
            monkeypatch.delenv("FS_GW_JOURNAL_EXPECTED_HEAD")
        module.backup(
            url=source,
            company_id=co["companyId"],
            output=artifact,
            evidence=folders["backups"] / "history.json",
            config=config,
        )
    if rollover:
        successor = directory.parent / "successor"
        export(directory, key, verify(directory, key)["head"], successor, rollover=True)
        monkeypatch.setenv("FS_GW_IDENTITY_JOURNAL_DIR", str(successor))
        directory = successor
    binding = ok(api(staff, co, "me/binding", method="GET"))
    suspended = ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding['id']}/suspend",
            {"expectedVersion": binding["version"], "reason": "합성 변경 회수"},
        )
    )
    resumed = ok(
        api(
            admin,
            co,
            f"identity-bindings/{binding['id']}/resume",
            {"expectedVersion": suspended["version"], "reason": "합성 재연결"},
        )
    )
    assert resumed["state"] == "ACTIVE"
    for role in ("ADMIN", "STAFF"):
        assert (
            manage(admin, co, "/role", {"userId": staff_id, "role": role}).status_code
            == 200
        )
    latest_pin = verify(directory, key)["head"]
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", latest_pin)
    if rollover:
        publish(directory, key, latest_pin, copies, receipts, b"w" * 32)
        monkeypatch.delenv("FS_GW_JOURNAL_EXPECTED_HEAD")
    changes = folders["checkpoints"] / "history.fsbackup"
    head = folders["checkpoints"] / "history-head.json"
    captured = module.checkpoint(
        url=source, artifact=artifact, output=changes, head=head, config=config
    )
    admin_url = (
        make_url(source).set(database="postgres").render_as_string(hide_password=False)
    )
    args = {
        "admin_url": admin_url,
        "artifact": artifact,
        "checkpoint_file": changes,
        "head": head,
        "expected_checkpoint_digest": captured["checkpointDigest"],
        "config": config,
    }
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", ZERO)
    with pytest.raises(BackupError):
        module.restore(
            **args,
            report=folders["reports"] / "stale.json",
            evidence=folders["reports"] / "stale-evidence.json",
        )
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", latest_pin)
    restored = module.restore(
        **args,
        report=folders["reports"] / "history.json",
        evidence=folders["reports"] / "history-evidence.json",
    )
    target_url = make_url(source).set(database=restored["database"])
    target = create_engine(target_url)
    try:
        restored.update(json.loads((folders["reports"] / "history.json").read_text()))
        assert restored["result"] == "PARTIAL" and restored["closed"]
        assert restored["journalRestrictionsApplied"]
        assert restored["journalUnconfirmedIntents"] == 1
        assert restored["journalCandidateIntents"] == 6
        assert restored["journalDisabledAccounts"] == 1
        assert restored["journalQuarantinedScopes"] == 1
        proof = json.loads((folders["reports"] / "history-evidence.json").read_text())
        diagnostic = proof["envelope"]["metrics"]["restoreDiagnostics"]
        assert diagnostic["journalUnconfirmedIntents"] == 1
        assert diagnostic["journalCandidateIntents"] == 6
        assert diagnostic["journalQuarantinedScopes"] == 1
        assert diagnostic["databaseClosed"] is True
        assert (
            not restored["checkpointCompletenessConfirmed"]
            and not restored["revocationsReapplied"]
        )
        with target.connect() as c:
            assert (
                c.scalar(
                    text("SELECT status FROM core.app_user WHERE id=:u"),
                    {"u": staff_id},
                )
                == "disabled"
            )
            assert (
                c.scalar(
                    text("SELECT status FROM core.app_user WHERE id=:u"),
                    {"u": admin_id},
                )
                == "active"
            )
            assert (
                c.scalar(
                    text("SELECT is_active FROM hr.work_account WHERE user_id=:u"),
                    {"u": staff_id},
                )
                is False
            )
            assert c.scalar(
                text(
                    "SELECT company_hold FROM gw.operating_settings WHERE workspace_id=:w"
                ),
                {"w": co["companyId"]},
            )
            assert (
                c.scalar(
                    text(
                        "SELECT count(*) FROM gw.person_identity_binding WHERE workspace_id=:w AND state='ACTIVE'"
                    ),
                    {"w": co["companyId"]},
                )
                == 0
            )
            assert (
                c.scalar(
                    text(
                        "SELECT datconnlimit FROM pg_database WHERE datname=current_database()"
                    )
                )
                == 0
            )
        # Use the product authentication resolvers against the closed target.
        # The test owner is a superuser; employee DB connections stay disabled.
        for old_context in (admin_context, staff_context):
            with pytest.raises(ApiError) as error, target.begin() as c:
                _resolve_member(c, old_context.token)
            assert error.value.status_code == 401
        with target.begin() as c:
            assert (
                c.scalar(
                    text(
                        "SELECT state FROM core.authentication_challenge WHERE id=:id"
                    ),
                    {"id": pending_id},
                )
                == "EXPIRED"
            )
            _, denied = verify_login(c, pending_token, "000000")
            assert denied.status_code == 401
            assert (
                c.scalar(
                    text(
                        "SELECT count(*) FROM core.auth_session WHERE revoked_at IS NULL"
                    )
                )
                == 0
            )
            assert (
                c.scalar(
                    text(
                        "SELECT datconnlimit FROM pg_database WHERE datname=current_database()"
                    )
                )
                == 0
            )
        with engine.connect() as c:
            assert (
                c.scalar(
                    text(
                        "SELECT state FROM core.authentication_challenge WHERE id=:id"
                    ),
                    {"id": pending_id},
                )
                == "PENDING"
            )
            assert _resolve_member(c, admin_context.token).user_id == admin_id
            # HR role changes already revoke the staff session in the source.
            with pytest.raises(ApiError) as source_denied:
                _resolve_member(c, staff_context.token)
            assert source_denied.value.status_code == 401
            assert (
                c.scalar(
                    text("SELECT status FROM core.app_user WHERE id=:u"),
                    {"u": staff_id},
                )
                == "active"
            )
            assert (
                c.scalar(
                    text("SELECT state FROM gw.person_identity_binding WHERE id=:id"),
                    {"id": int(binding["id"])},
                )
                == "ACTIVE"
            )
            assert (
                c.scalar(
                    text("SELECT work_role FROM hr.work_account WHERE user_id=:u"),
                    {"u": staff_id},
                )
                == "STAFF"
            )
        assert api(admin, co, "operations", method="GET").status_code == 200
    finally:
        target.dispose()
        cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as c:
            c.execute(text(f'DROP DATABASE "{restored["database"]}" WITH (FORCE)'))
        cleanup.dispose()
