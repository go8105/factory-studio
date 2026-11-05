"""Actual encrypted export, offline verification and incomplete-copy rejection."""

# ruff: noqa:F811
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fs.core.backup import BackupError
from fs.core.security.journal import ZERO, append, verify
from fs.core.security.journal_bundle import export, inspect
from test_security_journal import journal  # noqa: F401


def payload():
    return {
        "coverage": "core.security.intent.v1",
        "operation": "synthetic",
        "userId": 1,
        "snapshot": {"private": "synthetic-secret"},
    }


def test_export_is_pinned_and_source_continues_without_changing_bundle(
    journal, tmp_path
):
    source, key = journal
    head = append(source, key, payload())
    target = tmp_path / "bundle"
    export(source, key, head, target)
    assert inspect(target, key, head)["records"] == 1
    assert (target / "records/0000000001.json").read_bytes() == (
        source / "0000000001.json"
    ).read_bytes()
    assert "synthetic-secret" not in (target / "manifest.json").read_text()
    newer = append(source, key, payload())
    assert verify(source, key, newer)["records"] == 2
    assert inspect(target, key, head)["records"] == 1
    with pytest.raises(BackupError):
        inspect(target, key, newer)
    with pytest.raises(FileExistsError):
        export(source, key, newer, target)
    with pytest.raises(BackupError):
        export(source, key, head, tmp_path / "stale")
    assert not (tmp_path / "stale").exists()
    assert inspect(target, key, head)["records"] == 1


@pytest.mark.parametrize("damage", ["missing", "tamper", "manifest", "extra", "key"])
def test_copied_bundle_rejects_damage(journal, tmp_path, damage):
    source, key = journal
    head = append(source, key, payload())
    target = tmp_path / "bundle"
    export(source, key, head, target)
    record = target / "records/0000000001.json"
    if damage == "missing":
        record.unlink()
    elif damage == "tamper":
        record.write_bytes(b"{}")
    elif damage == "manifest":
        (target / "manifest.json").write_text("{}")
    elif damage == "extra":
        (target / "unknown").touch()
    else:
        key = b"x" * 32
    with pytest.raises(BackupError):
        inspect(target, key, head)


def test_partial_copy_cannot_be_verified_or_overwritten(journal, tmp_path, monkeypatch):
    from fs.core.security import journal_bundle

    source, key = journal
    head = append(source, key, payload())
    target = tmp_path / "bundle"
    real_write = journal_bundle.write

    def fail_manifest(path, data):
        if path.name == "manifest.json":
            raise OSError("synthetic failure")
        real_write(path, data)

    monkeypatch.setattr(journal_bundle, "write", fail_manifest)
    with pytest.raises(OSError):
        export(source, key, head, target)
    with pytest.raises(BackupError):
        inspect(target, key, head)
    with pytest.raises(FileExistsError):
        export(source, key, head, target)
    assert verify(source, key, head)["records"] == 1


def test_rejects_inside_source_and_public_parent(journal, tmp_path):
    source, key = journal
    with pytest.raises(BackupError):
        export(source, key, ZERO, source / "bundle")
    public = tmp_path / "public"
    public.mkdir(mode=0o755)
    with pytest.raises(BackupError):
        export(source, key, ZERO, public / "bundle")


def test_cli_offline_verification_does_not_need_database(journal, tmp_path):
    source, key = journal
    head = append(source, key, payload())
    root = Path(__file__).resolve().parents[2]
    target = tmp_path / "bundle"
    env = {**os.environ, "PYTHONPATH": str(root / "backend/src")}
    env.pop("DATABASE_URL", None)
    for action in ["export", "verify"]:
        result = subprocess.run(
            [
                sys.executable,
                str(root / "tools/gw_journal_bundle.py"),
                action,
                "--expected-head",
                head,
                "--bundle",
                str(target),
            ],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0
        report = json.loads(result.stdout)
        assert report["bundleVerified"] and not report["sourceRotated"]
        assert (
            not report["externalDurabilityConfirmed"]
            and not report["releaseAuthorized"]
        )
        assert not report["completenessConfirmed"]


def test_empty_snapshot_is_not_coverage_confirmation(journal, tmp_path):
    source, key = journal
    target = tmp_path / "empty"
    export(source, key, ZERO, target)
    state = inspect(target, key, ZERO)
    assert state["records"] == 0 and not state["completenessConfirmed"]
    assert (target.stat().st_mode & 0o777) == 0o700
    assert ((target / "manifest.json").stat().st_mode & 0o777) == 0o600


def test_export_and_append_share_lock(journal, tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from fs.core.security import journal_bundle

    source, key = journal
    head = append(source, key, payload())
    target = tmp_path / "bundle"
    copying, resume = Event(), Event()
    real_write = journal_bundle.write

    def paused_write(path, data):
        if path.name == "0000000001.json":
            copying.set()
            assert resume.wait(5)
        real_write(path, data)

    monkeypatch.setattr(journal_bundle, "write", paused_write)
    with ThreadPoolExecutor(max_workers=2) as pool:
        exported = pool.submit(export, source, key, head, target)
        try:
            assert copying.wait(5)
            appended = pool.submit(append, source, key, payload())
        finally:
            resume.set()
        assert exported.result()["records"] == 1
        new_head = appended.result()
    assert inspect(target, key, head)["records"] == 1
    assert verify(source, key, new_head)["records"] == 2
