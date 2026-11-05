"""Preserved-prefix rollover keeps ciphertext identities and old backup anchors."""

# ruff: noqa:F811
import json

import pytest
from fs.core.backup import BackupError
from fs.core.security import journal as chain
from fs.core.security import journal_bundle as bundles
from fs.gw import backup_journal as bridge
from test_journal_bundle import payload
from test_security_journal import journal  # noqa: F401


def test_rollover_resets_active_capacity_and_keeps_backup_prefix(
    journal, tmp_path, monkeypatch
):
    source, key = journal
    monkeypatch.setattr(chain, "MAX_RECORDS", 2)
    monkeypatch.setattr(bundles, "MAX_RECORDS", 2)
    monkeypatch.setattr(chain, "MAX_TOTAL_RECORDS", 6)
    monkeypatch.setattr(bundles, "MAX_TOTAL_RECORDS", 6)
    monkeypatch.setattr(bridge, "confirmed_digests", lambda *a: set())
    first = chain.append(source, key, payload())
    baseline = bridge.anchor(
        None, chain.verified_records(source, key, first, metadata_only=True)
    )
    second = chain.append(source, key, payload())
    with pytest.raises(BackupError):
        chain.append(source, key, payload())
    successor = tmp_path / "next"
    bundles.export(source, key, second, successor, rollover=True)
    assert chain.verify(successor, key, second) == chain.verify(source, key, second)
    assert (successor / ".history/0000000001.json").read_bytes() == (
        source / "0000000001.json"
    ).read_bytes()
    chain.append(successor, key, payload())
    fourth = chain.append(successor, key, payload())
    observed = chain.verified_records(successor, key, fourth, metadata_only=True)
    plan = bridge.plan(None, baseline, observed)
    assert plan["candidates"] == 4 and plan["baseHead"] == first
    monkeypatch.setenv("FS_GW_JOURNAL_EXPECTED_HEAD", fourth)
    bridge.validate_restore(baseline, plan)
    assert chain.verify(source, key, second)["records"] == 2
    offline = tmp_path / "offline"
    bundles.export(successor, key, fourth, offline)
    assert bundles.inspect(offline, key, fourth)["records"] == 4
    with pytest.raises(BackupError):
        chain.append(successor, key, payload())
    newer = tmp_path / "next2"
    bundles.export(successor, key, fourth, newer, rollover=True)
    chain.append(newer, key, payload())
    sixth = chain.append(newer, key, payload())
    assert chain.verify(newer, key, sixth)["records"] == 6
    with pytest.raises(BackupError):
        bundles.export(newer, key, sixth, tmp_path / "over-limit", rollover=True)
    with pytest.raises(BackupError):
        chain.append(newer, key, payload())


@pytest.mark.parametrize("damage", ["history", "manifest", "head", "gap", "link"])
def test_preserved_prefix_damage_blocks_read_and_write(journal, tmp_path, damage):
    source, key = journal
    head = chain.append(source, key, payload())
    successor = tmp_path / "next"
    bundles.export(source, key, head, successor, rollover=True)
    if damage == "history":
        (successor / ".history/0000000001.json").unlink()
    elif damage == "manifest":
        (successor / ".history.json").unlink()
    elif damage == "head":
        p = successor / ".history.json"
        value = json.loads(p.read_text())
        value["head"] = "f" * 64
        p.write_text(json.dumps(value))
    elif damage == "gap":
        (successor / "0000000003.json").write_text("{}")
        (successor / "0000000003.json").chmod(0o600)
    else:
        original = successor / ".history/0000000001.json"
        original.unlink()
        original.symlink_to(source / "0000000001.json")
    with pytest.raises((BackupError, OSError)):
        chain.verify(successor, key, head)
    with pytest.raises((BackupError, OSError)):
        chain.append(successor, key, payload())


def test_incomplete_rollover_blocks_append_and_does_not_change_source(
    journal, tmp_path, monkeypatch
):
    source, key = journal
    head = chain.append(source, key, payload())
    real_write = bundles.write

    def failed_write(path, data):
        if path.name == ".history.json":
            raise OSError("synthetic failure")
        real_write(path, data)

    monkeypatch.setattr(bundles, "write", failed_write)
    target = tmp_path / "next"
    with pytest.raises(OSError):
        bundles.export(source, key, head, target, rollover=True)
    with pytest.raises(BackupError):
        chain.append(target, key, payload())
    assert chain.verify(source, key, head)["records"] == 1
    with pytest.raises(BackupError):
        bundles.export(source, key, chain.ZERO, tmp_path / "stale", rollover=True)


def test_cli_switch_check_rejects_original_advancing(journal, tmp_path):
    import os
    import subprocess
    import sys
    from pathlib import Path

    source, key = journal
    head = chain.append(source, key, payload())
    target = tmp_path / "next"
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root / "backend/src")}
    command = [sys.executable, str(root / "tools/gw_journal_bundle.py")]
    options = ["--expected-head", head, "--bundle", str(target)]
    for action in ["rollover", "check-switch"]:
        result = subprocess.run(
            command + [action] + options,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        value = json.loads(result.stdout)
        assert value["successorPrepared"] and not value["sourceRotated"]
        assert not value["releaseAuthorized"]
    chain.append(source, key, payload())
    stale = subprocess.run(
        command + ["check-switch"] + options,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert stale.returncode == 1 and not stale.stdout
    assert chain.verify(target, key, head)["records"] == 1
