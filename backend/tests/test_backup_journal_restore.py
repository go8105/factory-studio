"""Actual PG dump/restore: revoked-then-resumed and unconfirmed history stay denied."""

# ruff: noqa:F811
import json
import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env  # noqa: F401
from test_gw_company import context
from test_gw_company_work import api, ok
from test_hr_users import manage
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401

from fs.core.backup import BackupError
from fs.core.security.journal import ZERO, append, verify
from fs.core.security.recording import record_user


def test_actual_history_bound_restore_restricts_without_changing_source(
    company_env, backup_env, journal, monkeypatch
):
    engine, co, admin, staff = company_env
    module, config, folders, _ = backup_env
    directory, key = journal
    admin_id = context(engine, admin).user_id
    staff_id = context(engine, staff).user_id
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
        module.backup(
            url=source,
            company_id=co["companyId"],
            output=artifact,
            evidence=folders["backups"] / "history.json",
            config=config,
        )
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
        with engine.connect() as c:
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
    finally:
        target.dispose()
        cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as c:
            c.execute(text(f'DROP DATABASE "{restored["database"]}" WITH (FORCE)'))
        cleanup.dispose()
