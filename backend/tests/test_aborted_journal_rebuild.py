"""False restrictions are replaced by a fresh closed restore, never in-place grants."""

# ruff: noqa:F811
import json
import os

from fs.core.security.journal import verify
from fs.core.security.recording import record_user
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env  # noqa: F401
from test_gw_company import context
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401


def test_pending_then_aborted_rebuild_keeps_previous_target_closed(
    company_env, backup_env, journal, monkeypatch
):
    engine, co, _, staff = company_env
    module, config, folders, _ = backup_env
    uid = context(engine, staff).user_id
    directory, key = journal
    monkeypatch.setenv("FS_GW_JOURNAL_TX_PROOF", "true")
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", verify(directory, key)["head"])
    source = os.environ["TEST_DATABASE_URL"]
    admin_url = (
        make_url(source).set(database="postgres").render_as_string(hide_password=False)
    )
    artifact = folders["backups"] / "rebuild.fsbackup"
    module.backup(
        url=source,
        company_id=co["companyId"],
        output=artifact,
        evidence=folders["backups"] / "rebuild-evidence.json",
        config=config,
    )
    targets = []

    def restore(name):
        checkpoint = folders["checkpoints"] / f"{name}.fsbackup"
        head = folders["checkpoints"] / f"{name}-head.json"
        captured = module.checkpoint(
            url=source, artifact=artifact, output=checkpoint, head=head, config=config
        )
        report = folders["reports"] / f"{name}.json"
        restored = module.restore(
            admin_url=admin_url,
            artifact=artifact,
            checkpoint_file=checkpoint,
            head=head,
            expected_checkpoint_digest=captured["checkpointDigest"],
            report=report,
            evidence=folders["reports"] / f"{name}-evidence.json",
            config=config,
        )
        targets.append(restored["database"])
        return restored["database"], json.loads(report.read_text())

    def state(name):
        target = create_engine(make_url(source).set(database=name))
        try:
            with target.connect() as c:
                return (
                    c.scalar(
                        text("SELECT status FROM core.app_user WHERE id=:u"), {"u": uid}
                    ),
                    c.scalar(
                        text(
                            "SELECT datconnlimit FROM pg_database WHERE datname=current_database()"
                        )
                    ),
                )
        finally:
            target.dispose()

    try:
        with engine.connect() as pending:
            tx = pending.begin()
            try:
                pending.execute(
                    text(
                        "UPDATE core.app_user SET security_version=security_version+1 WHERE id=:u"
                    ),
                    {"u": uid},
                )
                record_user(pending, uid, "synthetic.unfinished-revocation")
                monkeypatch.setenv(
                    "FS_GW_JOURNAL_EXPECTED_HEAD", verify(directory, key)["head"]
                )
                old_name, old_report = restore("pending")
                assert old_report["journalUnconfirmedIntents"] == 1
                assert old_report["journalAbortedIntents"] == 0
                assert state(old_name) == ("disabled", 0)
            finally:
                tx.rollback()
        new_name, new_report = restore("after-abort")
        assert new_name != old_name
        assert new_report["journalAbortedIntents"] == 1
        assert (
            new_report["journalCandidateIntents"]
            == new_report["journalDisabledAccounts"]
            == 0
        )
        assert state(new_name) == ("active", 0)
        assert state(old_name) == ("disabled", 0)
        assert new_report["result"] == "PARTIAL" and new_report["closed"]
        assert (
            not new_report["checkpointCompletenessConfirmed"]
            and not new_report["revocationsReapplied"]
        )
        with engine.connect() as c:
            assert (
                c.scalar(
                    text("SELECT status FROM core.app_user WHERE id=:u"), {"u": uid}
                )
                == "active"
            )
    finally:
        cleanup = create_engine(admin_url, isolation_level="AUTOCOMMIT")
        with cleanup.connect() as c:
            for name in targets:
                c.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        cleanup.dispose()
