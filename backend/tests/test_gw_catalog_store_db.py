"""Real encrypted checkpoint -> publisher CLI -> managed reader -> existing API."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_gw_restore_recheck_db import add_keys
from test_hr_work import company_env

from fs.gw.acceptance_sources import sign_current
from fs.gw.catalog_store import PIN_ENV
from fs.gw.checkpoint_catalog import ENV, read
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical, timestamp


@pytest.mark.parametrize("receiver_mode", [False, True])
def test_actual_checkpoint_cli_atomic_pin_fail_and_current_api(
    company_env, backup_env, monkeypatch, receiver_mode
):
    engine, co, admin, _ = company_env
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    target = module.restore(**args)
    cleanup = create_engine(args["admin_url"], isolation_level="AUTOCOMMIT")
    try:
        backup = json.loads((folders["backups"] / "backup.json").read_bytes())
        original = json.loads(args["evidence"].read_bytes())
        assert original["envelope"]["result"] == "PARTIAL"
        assert api(admin, co, "operating-evidence", backup).status_code == 200
        assert api(admin, co, "operating-evidence", original).status_code == 200
        keys, checked = add_keys(company_env, monkeypatch, config, folders["reports"])
        authority = Ed25519PrivateKey.generate()
        public = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
        public["catalog"] = base64.b64encode(
            authority.public_key().public_bytes_raw()
        ).decode()
        scopes["keys"]["catalog"] = {
            "workspaceIds": [str(co["companyId"])],
            "purposes": ["CHECKPOINT_CATALOG"],
        }
        monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
        monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
        checked["public"] = from_environment()
        folder = folders["reports"] / "published"
        folder.mkdir(mode=0o700)
        key = folders["reports"] / "catalog.key"
        key.write_bytes(authority.private_bytes_raw())
        key.chmod(0o600)
        monkeypatch.setenv("FS_GW_CATALOG_KEY_FILE", str(key))
        monkeypatch.setenv("FS_GW_CATALOG_KEY_ID", "catalog")
        context = folders["reports"] / "catalog-context.json"
        scope = json.loads(args["head"].read_bytes())["payload"]["scope"]
        context.write_bytes(
            canonical(
                {
                    "workspaceId": int(scope["workspaceId"]),
                    "generationId": int(scope["generationId"]),
                    "policy": api(admin, co, "operations", method="GET").json()["data"][
                        "policy"
                    ],
                    "codeRevision": config["codeRevision"],
                    "dbRevision": original["envelope"]["dbRevision"],
                }
            )
        )
        context.chmod(0o600)
        monkeypatch.delenv(ENV, raising=False)
        monkeypatch.setenv(PIN_ENV, str(folder / "current-pin.json"))

        def cli(operation, expected=None, extra=(), exit_code=0):
            command = [
                sys.executable,
                "tools/gw_checkpoint_catalog.py",
                operation,
                "--directory",
                str(folder),
                "--context",
                str(context),
            ]
            if expected:
                command += ["--expected-pin-digest", expected]
            result = subprocess.run(
                command + list(extra), capture_output=True, timeout=30, check=False
            )
            assert (
                result.returncode == exit_code
            )  # Never expose private subprocess output on failure.
            return json.loads(result.stdout) if exit_code != 1 else None

        source = (
            "--head",
            str(args["head"]),
            "--checkpoint",
            str(args["checkpoint_file"]),
        )
        first = cli("publish", "ABSENT", source + ("--initialize",))
        assert first["result"] == "PASS" and first["ready"] is False
        assert cli("status")["pinDigest"] == first["pinDigest"]
        receiver = folders["reports"] / "receiver"
        receiver.mkdir(mode=0o700)
        installed = None
        deliveries = 0

        def deliver(exit_code=0, *, tamper=False, resume=False):
            nonlocal installed, deliveries
            deliveries += 1
            batch = folders["reports"] / f"transfer-{deliveries}.json"
            base = installed["revision"] if installed else 0
            base_digest = installed["catalogDigest"] if installed else "ABSENT"
            exported = subprocess.run(
                [
                    sys.executable,
                    "tools/gw_checkpoint_transfer.py",
                    "export",
                    "--directory",
                    str(folder),
                    "--context",
                    str(context),
                    "--from-revision",
                    str(base),
                    "--from-catalog-digest",
                    base_digest,
                    "--output",
                    str(batch),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert exported.returncode == 0
            anchor = json.loads(exported.stdout)
            if tamper:
                batch.write_bytes(batch.read_bytes() + b"tampered")
            receiving_env = os.environ.copy()
            receiving_env.pop("FS_GW_CATALOG_KEY_FILE", None)
            receiving_env.pop("FS_GW_CATALOG_KEY_ID", None)
            command = [
                sys.executable,
                "tools/gw_checkpoint_transfer.py",
                "install",
                "--directory",
                str(receiver),
                "--context",
                str(context),
                "--transfer",
                str(batch),
                "--expected-transfer-digest",
                anchor["transferDigest"],
                "--expected-catalog-id",
                first["catalogId"],
                "--expected-pin-digest",
                installed["pinDigest"] if installed else "ABSENT",
            ]
            if installed is None:
                command += ["--initialize"]
            if resume:
                command += ["--resume"]
            result = subprocess.run(
                command, env=receiving_env, capture_output=True, timeout=30, check=False
            )
            assert result.returncode == exit_code and not result.stderr
            if exit_code == 1:
                return
            installed = json.loads(result.stdout)
            assert installed["ready"] is False

        if receiver_mode:
            deliver()
            monkeypatch.setenv(PIN_ENV, str(receiver / "current-pin.json"))
        original_snapshots = {
            p.name: p.read_bytes() for p in folder.glob("catalog-*.json")
        }

        def recheck(name):
            output = folders["reports"] / name
            module.recheck_restore(
                url=make_url(os.environ["TEST_DATABASE_URL"])
                .set(database=target["database"])
                .render_as_string(hide_password=False),
                source_url=os.environ["TEST_DATABASE_URL"],
                artifact=args["artifact"],
                checkpoint_file=args["checkpoint_file"],
                head=args["head"],
                expected_checkpoint_digest=args["expected_checkpoint_digest"],
                restore_document=original,
                output=output,
                config=checked,
                check_catalog=True,
            )
            return json.loads(output.read_bytes())

        def collect(document):
            return sign_current(
                engine,
                company_id=co["companyId"],
                code_revision=config["codeRevision"],
                public_keys=from_environment(),
                signer=keys["collector"],
                signer_id="collector",
                restore_recheck=document,
            )

        def status():
            data = api(admin, co, "operations", method="GET").json()["data"]
            assert not data["ready"] and data["launchGate"]["unverifiedCount"] == 4
            return data["evidenceChecks"][2]

        proof = collect(recheck("published-match.json"))
        assert proof["envelope"]["result"] == "PARTIAL"
        assert api(admin, co, "operating-evidence", proof).status_code == 200
        with engine.connect() as connection:
            delay = (
                timestamp(proof["envelope"]["finishedAt"])
                - connection.scalar(text("SELECT clock_timestamp()"))
            ).total_seconds()
        assert delay < 30
        if delay >= 0:
            time.sleep(delay + 0.02)
        assert status()["restoreRecheck"]["catalogObservation"]["reason"] == "MATCH"
        failed = cli(
            "publish",
            first["pinDigest"],
            (
                "--head",
                str(folder / "missing.json"),
                "--checkpoint",
                str(args["checkpoint_file"]),
            ),
            exit_code=2,
        )
        assert failed["result"] == "FAIL" and failed["sequence"] == 2
        refreshed = cli("refresh", failed["pinDigest"], exit_code=2)
        if receiver_mode:
            deliver(exit_code=1, tamper=True)
            assert status()["state"] == "INVALID"
            deliver(
                exit_code=2, resume=True
            )  # Same original bytes include missed FAIL and refresh.
        assert status()["state"] == "INVALID"
        rejected = collect(recheck("published-failure.json"))
        assert rejected["envelope"]["result"] == "FAIL"
        assert api(admin, co, "operating-evidence", rejected).status_code == 200
        refreshed = cli("refresh", refreshed["pinDigest"], exit_code=2)
        if receiver_mode:
            deliver(exit_code=2)
        assert refreshed["result"] == "FAIL" and refreshed["sequence"] == 2
        cli("refresh", first["pinDigest"], exit_code=1)
        catalog, sha = read(
            public_keys=from_environment(),
            workspace_id=co["companyId"],
            now=datetime.now(UTC),
        )
        assert sha == refreshed["catalogDigest"] and catalog.records[0].result == "FAIL"
        assert all(
            (folder / name).read_bytes() == raw
            for name, raw in original_snapshots.items()
        )
    finally:
        with cleanup.connect() as connection:
            connection.execute(
                text(f'DROP DATABASE "{target["database"]}" WITH (FORCE)')
            )
        cleanup.dispose()
