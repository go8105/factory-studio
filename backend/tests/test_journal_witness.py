"""Authenticated receipt delivery, stale/rollback/branch rejection, no grants."""

# ruff: noqa:F811
import json
from datetime import UTC, datetime, timedelta

import pytest
from test_journal_bundle import payload
from test_security_journal import journal  # noqa: F401

from fs.core.backup import BackupError
from fs.core.security import journal_witness as witness
from fs.core.security.journal import append, verify
from fs.core.security.journal_bundle import export
from fs.gw import backup_journal


@pytest.fixture
def delivery(journal, tmp_path, monkeypatch):
    source, key = journal
    bundles, receipts = tmp_path / "copies", tmp_path / "witness"
    for p in (bundles, receipts):
        p.mkdir(mode=0o700)
    witness_key = b"w" * 32
    key_file = tmp_path / "witness-key"
    key_file.write_bytes(witness_key)
    key_file.chmod(0o600)
    monkeypatch.setenv("FS_GW_JOURNAL_WITNESS_DIR", str(receipts))
    monkeypatch.setenv("FS_GW_JOURNAL_WITNESS_KEY_FILE", str(key_file))
    monkeypatch.delenv("FS_GW_JOURNAL_EXPECTED_HEAD", raising=False)
    return source, key, bundles, receipts, witness_key


def test_delivery_drives_backup_pin_and_rejects_stale_or_regressed_receipts(
    delivery, monkeypatch
):
    source, key, bundles, receipts, wkey = delivery
    first = append(source, key, payload())
    result = witness.publish(source, key, first, bundles, receipts, wkey)
    assert result["sequence"] == 1 and not result["externalDurabilityConfirmed"]
    assert witness.expected_head() == first
    assert backup_journal.source_records()[0]["head"] == first
    second = append(source, key, payload())
    with pytest.raises(BackupError):
        backup_journal.source_records()
    witness.publish(source, key, None, bundles, receipts, wkey)
    assert witness.latest(receipts, wkey)["head"] == second
    assert backup_journal.source_records()[0]["records"] == 2
    with pytest.raises(BackupError):
        witness.latest(receipts, wkey, now=datetime.now(UTC) + timedelta(hours=1))
    with pytest.raises(BackupError):
        witness.latest(receipts, wkey, now=datetime.now(UTC) - timedelta(hours=1))
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", first)
    with pytest.raises(BackupError):
        witness.expected_head()
    monkeypatch.delenv("FS_GW_JOURNAL_EXPECTED_HEAD")
    monkeypatch.setenv("FS_GW_JOURNAL_WITNESS_MIN_SEQUENCE", "2")
    (receipts / "0000000002.json").unlink()
    with pytest.raises(BackupError):
        witness.expected_head()


def test_publish_continues_after_rollover_but_rejects_branch(delivery, tmp_path):
    source, key, bundles, receipts, wkey = delivery
    first = append(source, key, payload())
    witness.publish(source, key, first, bundles, receipts, wkey)
    successor = tmp_path / "successor"
    export(source, key, first, successor, rollover=True)
    second = append(successor, key, payload())
    witness.publish(successor, key, second, bundles, receipts, wkey)
    assert witness.latest(receipts, wkey)["records"] == 2
    branch = append(source, key, payload())
    with pytest.raises(BackupError):
        witness.publish(source, key, branch, bundles, receipts, wkey)
    assert witness.latest(receipts, wkey)["sequence"] == 2


@pytest.mark.parametrize("failure", ["copy", "receipt"])
def test_failed_delivery_does_not_advance_confirmed_head(
    delivery, monkeypatch, failure
):
    source, key, bundles, receipts, wkey = delivery
    first = append(source, key, payload())
    witness.publish(source, key, first, bundles, receipts, wkey)
    second = append(source, key, payload())

    def fail(*args, **kwargs):
        raise OSError("synthetic failure")

    monkeypatch.setattr(witness, "inspect" if failure == "copy" else "write", fail)
    with pytest.raises(OSError):
        witness.publish(source, key, second, bundles, receipts, wkey)
    assert witness.latest(receipts, wkey)["head"] == first
    assert verify(source, key, second)["records"] == 2


@pytest.mark.parametrize("damage", ["mac", "gap", "key"])
def test_receipt_store_authentication(delivery, damage):
    source, key, bundles, receipts, wkey = delivery
    head = append(source, key, payload())
    witness.publish(source, key, head, bundles, receipts, wkey)
    p = receipts / "0000000001.json"
    if damage == "mac":
        value = json.loads(p.read_text())
        value["payload"]["head"] = "f" * 64
        p.write_text(json.dumps(value))
    elif damage == "gap":
        p.rename(receipts / "0000000002.json")
    else:
        wkey = b"x" * 32
    with pytest.raises(BackupError):
        witness.latest(receipts, wkey)


def test_configuration_and_path_separation(delivery, monkeypatch):
    source, key, bundles, receipts, wkey = delivery
    head = append(source, key, payload())
    with pytest.raises(BackupError):
        witness.publish(source, key, head, bundles, receipts, key)
    with pytest.raises(BackupError):
        witness.publish(source, key, head, source, receipts, wkey)
    monkeypatch.delenv("FS_GW_JOURNAL_WITNESS_KEY_FILE")
    with pytest.raises(BackupError):
        witness.expected_head()


def test_actual_cli_publish_and_check_without_database(delivery):
    import os
    import subprocess
    import sys
    from pathlib import Path

    source, key, bundles, receipts, wkey = delivery
    head = append(source, key, payload())
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "backend/src")}
    env.pop("DATABASE_URL", None)
    base = [sys.executable, str(root / "tools/gw_journal_delivery.py")]
    for args in [
        ["publish", "--expected-head", head, "--bundles", str(bundles)],
        ["check"],
    ]:
        result = subprocess.run(
            base + args, env=env, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0
        value = json.loads(result.stdout)
        assert value["head"] == head and value["sequence"] == 1
        assert (
            not value["externalDurabilityConfirmed"] and not value["releaseAuthorized"]
        )
    assert witness.latest(receipts, wkey)["head"] == head


def test_automatic_advance_requires_bootstrap_pin(delivery):
    source, key, bundles, receipts, wkey = delivery
    append(source, key, payload())
    with pytest.raises(BackupError):
        witness.publish(source, key, None, bundles, receipts, wkey)
    assert not list(bundles.iterdir())
