import hashlib

import pytest
from fs.gw.acceptance_artifact import inspect_copy
from test_gw_acceptance_collection import fixture, signed


@pytest.mark.parametrize(
    "change",
    ["match", "tamper", "partial", "stale", "signature", "symlink", "public", "empty"],
)
def test_staged_copy_requires_current_proof_and_actual_private_bytes(tmp_path, change):
    key, payloads, context = fixture()
    content = b"synthetic encrypted artifact"
    payloads["BACKUP"]["metrics"]["artifactDigest"] = hashlib.sha256(
        content
    ).hexdigest()
    if change == "partial":
        payloads["BACKUP"]["result"] = "PARTIAL"
    if change == "stale":
        context["code_revision"] = "fffffff"
    document = signed(payloads, key)["BACKUP"]
    if change == "signature":
        document["envelope"]["manifestDigest"] = "f" * 64
    path = tmp_path / "copy"
    path.write_bytes(b"" if change == "empty" else content)
    path.chmod(0o644 if change == "public" else 0o600)
    if change == "tamper":
        path.write_bytes(b"changed bytes")
    if change == "symlink":
        link = tmp_path / "link"
        link.symlink_to(path)
        path = link
    if change in {"match", "tamper"}:
        result = inspect_copy(path, document, **context)
        assert result["state"] == ("MATCH" if change == "match" else "MISMATCH")
        assert result["bytesRead"] == path.stat().st_size
        assert result["storageIndependenceConfirmed"] is False
        assert result["decryptionConfirmed"] is False
        assert str(path) not in str(result)
    else:
        from fs.common.errors import ApiError

        with pytest.raises((ValueError, OSError, ApiError)):
            inspect_copy(path, document, **context)


def test_cli_storage_mismatch_blocks_otherwise_matching_pair(
    tmp_path, monkeypatch, capsys
):
    import base64
    import importlib.util
    import json
    import sys
    from pathlib import Path

    from test_gw_operating_contract import NOW

    spec = importlib.util.spec_from_file_location(
        "copy_cli",
        Path(__file__).resolve().parents[2] / "tools/gw_acceptance_collect.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    key, payloads, ctx = fixture()
    documents = signed(payloads, key)
    tmp_path.chmod(0o700)
    context = {
        "workspaceId": 10,
        "generationId": 20,
        "policy": ctx["policy"].model_dump(by_alias=True),
        "codeRevision": ctx["code_revision"],
        "dbRevision": ctx["db_revision"],
    }
    for name, value in (
        ("context", context),
        ("backup", documents["BACKUP"]),
        ("restore", documents["RESTORE"]),
    ):
        target = tmp_path / name
        target.write_text(json.dumps(value))
        target.chmod(0o600)
    copy = tmp_path / "copy"
    copy.write_bytes(b"wrong artifact")
    copy.chmod(0o600)

    class Clock:
        @staticmethod
        def now(_tz):
            return NOW

    monkeypatch.setattr(cli, "datetime", Clock)
    monkeypatch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps(
            {"runner-1": base64.b64encode(key.public_key().public_bytes_raw()).decode()}
        ),
    )
    output = tmp_path / "result"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "collect",
            "--context",
            str(tmp_path / "context"),
            "--backup",
            str(tmp_path / "backup"),
            "--restore",
            str(tmp_path / "restore"),
            "--storage-copy",
            str(copy),
            "--output",
            str(output),
        ],
    )
    assert cli.main() == 2
    report = json.loads(output.read_text())
    assert report["backupRestorePairVerified"] is True
    assert report["result"] == "BLOCKED"
    assert report["ready"] is False
    assert len(report["remainingConditions"]) == 4
    assert output.stat().st_mode & 0o777 == 0o600
    assert str(copy) not in output.read_text()
    assert "BLOCKED" in capsys.readouterr().out
