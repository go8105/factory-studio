"""Encrypted chain integrity, concurrent writers, and actual transaction rollback."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import create_engine, text

from fs.common.errors import ApiError
from fs.core.backup import BackupError
from fs.core.security.journal import ZERO, append, canonical, verify
from fs.gw import company_identity, security_journal


@pytest.fixture
def journal(tmp_path, monkeypatch):
    directory = tmp_path / "journal"
    directory.mkdir(mode=0o700)
    key_file = tmp_path / "key"
    key_file.write_bytes(b"j" * 32)
    key_file.chmod(0o600)
    monkeypatch.setenv("FS_GW_IDENTITY_JOURNAL_DIR", str(directory))
    monkeypatch.setenv("FS_GW_IDENTITY_JOURNAL_KEY_FILE", str(key_file))
    return directory, key_file.read_bytes()


def payload():
    return {
        "coverage": "gw.company_identity.intent.v1",
        "snapshot": "synthetic-private",
    }


def test_encryption_tampering_missing_and_pinned_tail(journal):
    directory, key = journal
    append(directory, key, payload())
    head = append(directory, key, payload())
    state = verify(directory, key, head)
    assert state["records"] == 2
    assert not state["completenessConfirmed"] and not state["commitsConfirmed"]
    first = directory / "0000000001.json"
    second = directory / "0000000002.json"
    assert b"synthetic-private" not in first.read_bytes()
    assert first.stat().st_mode & 0o777 == 0o600
    original = first.read_bytes()
    first.unlink()
    with pytest.raises(BackupError):
        verify(directory, key, head)
    first.write_bytes(original)
    first.chmod(0o600)
    first.write_bytes(original.replace(b'"version":1', b'"version":2'))
    with pytest.raises(BackupError):
        append(directory, key, payload())
    first.write_bytes(original)
    second.unlink()
    with pytest.raises(BackupError):
        verify(directory, key, head)
    # A locally valid shortened chain cannot detect rollback without the external pin.
    assert verify(directory, key)["records"] == 1
    with pytest.raises(BackupError):
        verify(directory, b"x" * 32)


def test_concurrent_writers_and_partial_file(journal):
    directory, key = journal
    with ThreadPoolExecutor(max_workers=8) as pool:
        heads = list(pool.map(lambda _: append(directory, key, payload()), range(20)))
    assert len(set(heads)) == 20
    assert verify(directory, key)["records"] == 20
    broken = directory / "0000000021.json"
    broken.write_bytes(b"partial")
    broken.chmod(0o600)
    with pytest.raises(BackupError):
        append(directory, key, payload())


def test_permissions_symlink_and_empty_pin(journal, tmp_path):
    directory, key = journal
    assert verify(directory, key, ZERO)["records"] == 0
    directory.chmod(0o755)
    with pytest.raises(BackupError):
        append(directory, key, payload())
    directory.chmod(0o700)
    link = directory / "0000000001.json"
    link.symlink_to(tmp_path / "elsewhere")
    with pytest.raises((BackupError, FileNotFoundError)):
        verify(directory, key)


def test_identity_transaction_rolls_back_on_storage_failure(journal, monkeypatch):
    directory, key = journal
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.exec_driver_sql("ATTACH DATABASE ':memory:' AS gw")
        c.exec_driver_sql(
            "CREATE TABLE gw.person (id INTEGER, workspace_id INTEGER, generation_id INTEGER, is_active BOOLEAN, organization_unit_id INTEGER)"
        )
        c.exec_driver_sql(
            "CREATE TABLE gw.person_identity_binding (id INTEGER, workspace_id INTEGER, generation_id INTEGER, person_id INTEGER, user_id INTEGER, state TEXT)"
        )
        c.exec_driver_sql(
            "CREATE TABLE gw.role_grant (id INTEGER, workspace_id INTEGER, generation_id INTEGER, person_id INTEGER, role_key TEXT, is_active BOOLEAN)"
        )
        c.exec_driver_sql("INSERT INTO gw.person VALUES (1,10,20,1,1),(2,99,20,1,1)")
    ctx = SimpleNamespace(workspace_id=10, generation_id=20)

    @contextmanager
    def transaction(*args, **kwargs):
        with engine.begin() as c:
            yield c, ctx, None

    monkeypatch.setattr(company_identity.company, "transaction", transaction)
    for name in ("require_recent_auth", "bump", "audit", "save_receipt"):
        monkeypatch.setattr(company_identity, name, lambda *args: None)
    monkeypatch.setattr(company_identity, "find_receipt", lambda *args: None)
    monkeypatch.setattr(security_journal, "confirmation", lambda *args: None)

    def run(c, ctx):
        c.execute(text("UPDATE gw.person SET is_active=0 WHERE id=1"))
        return {"id": 1}, "person", 1

    def execute():
        return company_identity.execute(
            ctx, 10, "person.disable", "key", {}, lambda *a: None, run
        )

    directory.chmod(0o755)
    with pytest.raises(ApiError) as error:
        execute()
    assert error.value.code == "SECURITY_JOURNAL_UNAVAILABLE"
    with engine.connect() as c:
        assert c.scalar(text("SELECT is_active FROM gw.person WHERE id=1")) == 1
    directory.chmod(0o700)
    assert execute() == {"id": "1"}
    assert verify(directory, key)["records"] == 1
    envelope = json.loads((directory / "0000000001.json").read_bytes())
    stored = json.loads(
        AESGCM(key).decrypt(
            bytes.fromhex(envelope["nonce"]),
            bytes.fromhex(envelope["ciphertext"]),
            canonical(envelope["header"]),
        )
    )
    assert [p["id"] for p in stored["snapshot"]["person"]] == [1]
    # Existing receipt returns before journal creation, after authorization.
    monkeypatch.setattr(company_identity, "find_receipt", lambda *args: {"id": 1})
    assert execute() == {"id": 1}
    assert verify(directory, key)["records"] == 1

    @contextmanager
    def failed_commit(*args, **kwargs):
        with engine.begin() as c:
            yield c, ctx, None
            raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(company_identity.company, "transaction", failed_commit)
    monkeypatch.setattr(company_identity, "find_receipt", lambda *args: None)

    def activate(c, ctx):
        c.execute(text("UPDATE gw.person SET is_active=1 WHERE id=1"))
        return {"id": 1}, "person", 1

    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        company_identity.execute(
            ctx, 10, "person.activate", "new", {}, lambda *a: None, activate
        )
    with engine.connect() as c:
        assert c.scalar(text("SELECT is_active FROM gw.person WHERE id=1")) == 0
    assert verify(directory, key)["records"] == 2
    assert not verify(directory, key)["commitsConfirmed"]
    engine.dispose()


def test_optional_and_incomplete_configuration(journal, monkeypatch):
    monkeypatch.delenv("FS_GW_IDENTITY_JOURNAL_DIR")
    with pytest.raises(ApiError):
        security_journal.record(None, None, "test")
    monkeypatch.delenv("FS_GW_IDENTITY_JOURNAL_KEY_FILE")
    assert security_journal.record(None, None, "test") is None


def test_cli_checks_independent_pin_without_revealing_payload(journal):
    directory, key = journal
    head = append(directory, key, payload())
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "backend/src")}
    args = [
        sys.executable,
        str(root / "tools/gw_identity_journal.py"),
        "--expected-head",
    ]
    result = subprocess.run(
        [*args, head], env=env, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["records"] == 1
    assert "synthetic-private" not in result.stdout
    failed = subprocess.run(
        [*args, ZERO], env=env, capture_output=True, text=True, check=False
    )
    assert failed.returncode == 1 and not failed.stdout
    assert "Traceback" not in failed.stderr


def test_database_confirmation_is_scoped_and_legacy_is_unknown():
    records = [
        {
            "digest": "a" * 64,
            "payload": {
                "coverage": "gw.company.intent.v2",
                "workspaceId": 10,
                "generationId": 20,
                "operation": "synthetic",
                "snapshot": {},
            },
        }
    ]

    def connection(workspace=10, summary=None):
        rows = [{"workspace_id": workspace, "entity_key": "a" * 64, "summary": summary}]
        return SimpleNamespace(
            execute=lambda *a: SimpleNamespace(mappings=lambda: rows)
        )

    exact = {"generationId": "20", "operation": "synthetic"}
    assert security_journal.confirm_records(connection(summary=exact), records)[
        "commitsConfirmed"
    ]
    for c in (
        connection(workspace=99, summary=exact),
        connection(),
        connection(summary=[]),
        connection(summary={"generationId": "21", "operation": "synthetic"}),
    ):
        assert not security_journal.confirm_records(c, records)["commitsConfirmed"]
    legacy = [{"digest": "a" * 64, "payload": payload()}]
    result = security_journal.confirm_records(connection(summary=exact), legacy)
    assert result["legacyRecords"] == 1 and result["unconfirmedRecords"] == 1
    assert not result["commitsConfirmed"] and not result["completenessConfirmed"]
    assert not security_journal.confirm_records(None, [])["commitsConfirmed"]
