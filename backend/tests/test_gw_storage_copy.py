"""Real AES-GCM/tar/signature/dump checks; no PostgreSQL or external store."""

import hashlib
import os
from pathlib import Path

import pytest
from fs.core.backup import BackupError, encrypt
from fs.gw.operating_contract import canonical
from test_gw_acceptance_collection import fixture, signed
from test_gw_backup import runner


@pytest.mark.parametrize(
    "change",
    ["none", "wrong-key", "manifest", "dump", "signature", "artifact", "existing"],
)
def test_offline_copy_authentication_and_private_cleanup(tmp_path, change, monkeypatch):
    module = runner()
    signer, payloads, context = fixture()
    config = {
        "key": os.urandom(32),
        "keyId": "test",
        "signer": signer,
        "signerId": "runner-1",
        "public": context["public_keys"],
    }
    tmp_path.chmod(0o700)
    dump = tmp_path / "synthetic.dump"
    dump.write_bytes(b"synthetic dump bytes")
    dump.chmod(0o600)
    manifest = {
        "version": 1,
        "kind": "BACKUP",
        "runId": payloads["BACKUP"]["runId"],
        "encryptionKeyId": "test",
        "dumpDigest": hashlib.sha256(dump.read_bytes()).hexdigest(),
    }
    payloads["BACKUP"]["manifestDigest"] = hashlib.sha256(
        canonical(manifest)
    ).hexdigest()
    if change == "manifest":
        manifest["runId"] = payloads["RESTORE"]["runId"]
    if change == "dump":
        dump.write_bytes(b"changed dump")
    archive = tmp_path / "synthetic.tar"
    module.pack(archive, manifest, config, dump=dump)
    artifact = tmp_path / "copy.enc"
    encrypt(archive, artifact, config["key"])
    payloads["BACKUP"]["metrics"]["artifactDigest"] = hashlib.sha256(
        artifact.read_bytes()
    ).hexdigest()
    document = signed(payloads, signer)["BACKUP"]
    if change == "signature":
        document["envelope"]["manifestDigest"] = "f" * 64
    if change == "artifact":
        artifact.write_bytes(b"changed ciphertext")
    if change == "wrong-key":
        config["key"] = os.urandom(32)
    output = tmp_path / "report.json"
    if change == "existing":
        output.write_bytes(b"keep")
    original = artifact.read_bytes()
    if change == "none":
        assert module.verify_storage_copy(
            artifact=artifact,
            document=document,
            context=context,
            output=output,
            config=config,
        ) == {"result": "PARTIAL", "ready": False}
        import json

        report = json.loads(output.read_bytes())
        assert report["storageCopy"]["decryptionConfirmed"] is True
        assert report["manifestSignatureVerified"] is True
        assert report["dumpDigestVerified"] is True
        assert report["databaseRestoreConfirmed"] is False
        assert report["storageCopy"]["storageIndependenceConfirmed"] is False
        assert output.stat().st_mode & 0o777 == 0o600
        assert str(tmp_path) not in output.read_text()
        # The public CLI must work without any DB URL, security mode or signing key.
        import base64
        import sys

        from test_gw_operating_contract import NOW

        key_file = tmp_path / "key"
        key_file.write_bytes(config["key"])
        key_file.chmod(0o600)
        for name in (
            "DATABASE_URL",
            "FS_GW_RESTORE_ADMIN_URL",
            "FS_GW_RUNNER_KEY_FILE",
            "FS_SECURITY_MODE",
        ):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.setenv("FS_GW_BACKUP_KEY_FILE", str(key_file))
        monkeypatch.setenv("FS_GW_BACKUP_KEY_ID", "test")
        monkeypatch.setenv(
            "FS_GW_EVIDENCE_PUBLIC_KEYS",
            json.dumps(
                {"runner-1": base64.b64encode(config["public"]["runner-1"]).decode()}
            ),
        )
        current = {
            "workspaceId": 10,
            "generationId": 20,
            "policy": context["policy"].model_dump(by_alias=True),
            "codeRevision": context["code_revision"],
            "dbRevision": context["db_revision"],
        }
        for name, data in (("context.json", current), ("proof.json", document)):
            path = tmp_path / name
            path.write_text(json.dumps(data))
            path.chmod(0o600)

        class Clock:
            @staticmethod
            def now(_tz):
                return NOW

        monkeypatch.setattr(module, "datetime", Clock)
        monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "tools"))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "gw_backup",
                "verify-copy",
                "--backup",
                str(artifact),
                "--backup-evidence",
                str(tmp_path / "proof.json"),
                "--context",
                str(tmp_path / "context.json"),
                "--report",
                str(tmp_path / "cli-report.json"),
            ],
        )
        module.main()
        assert json.loads((tmp_path / "cli-report.json").read_text())["ready"] is False

    else:
        from fs.common.errors import ApiError

        with pytest.raises((BackupError, ApiError)):
            module.verify_storage_copy(
                artifact=artifact,
                document=document,
                context=context,
                output=output,
                config=config,
            )
        assert (
            output.read_bytes() == b"keep"
            if change == "existing"
            else not output.exists()
        )
    assert artifact.read_bytes() == original
    assert not list(Path(tmp_path).glob(".fs-storage-copy-*"))
