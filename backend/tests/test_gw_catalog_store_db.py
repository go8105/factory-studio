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
from gw_catalog_trust_helpers import approve_environment
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_gw_backup import backup_env
from test_gw_company_work import api
from test_gw_restore_observation_db import restored
from test_gw_restore_recheck_db import add_keys
from test_hr_work import company_env

from fs.gw import catalog_store as store
from fs.gw.acceptance_sources import sign_current
from fs.gw.catalog_store import PIN_ENV
from fs.gw.checkpoint_catalog import ENV, read
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical, timestamp


@pytest.mark.parametrize(
    "receiver_mode", [False, True, "recovery", "segments", "handover", "chain"]
)
def test_actual_checkpoint_cli_atomic_pin_fail_and_current_api(
    company_env, backup_env, monkeypatch, receiver_mode
):
    engine, co, admin, _ = company_env
    module, config, folders, _ = backup_env
    args = restored(company_env, backup_env)
    target = module.restore(**args)
    targets = [target["database"]]
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
        approve_environment(monkeypatch, folders["reports"] / "trust")
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

        def deliver_segments(exit_code, *, tamper, resume):
            nonlocal installed, deliveries
            deliveries += 1
            package = folders["reports"] / f"segments-{deliveries}"
            package.mkdir(mode=0o700)
            exported = subprocess.run(
                [
                    sys.executable,
                    "tools/gw_checkpoint_segments.py",
                    "export",
                    "--directory",
                    str(folder),
                    "--context",
                    str(context),
                    "--from-revision",
                    str(installed["revision"] if installed else 0),
                    "--from-catalog-digest",
                    installed["catalogDigest"] if installed else "ABSENT",
                    "--output-directory",
                    str(package),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert exported.returncode == 0 and not exported.stderr
            anchor = json.loads(exported.stdout)
            manifest = package / "manifest.json"
            if tamper:
                manifest.write_bytes(manifest.read_bytes() + b"tampered")
            receiving_env = os.environ.copy()
            receiving_env.pop("FS_GW_CATALOG_KEY_FILE", None)
            receiving_env.pop("FS_GW_CATALOG_KEY_ID", None)
            command = [
                sys.executable,
                "tools/gw_checkpoint_segments.py",
                "receive",
                "--directory",
                str(receiver),
                "--context",
                str(context),
                "--manifest",
                str(manifest),
                "--expected-manifest-digest",
                anchor["manifestDigest"],
                "--expected-catalog-id",
                anchor["catalogId"],
                "--expected-pin-digest",
                installed["pinDigest"] if installed else "ABSENT",
            ]
            result = subprocess.run(
                command
                + (
                    ["--resume"]
                    if resume
                    else ["--initialize"]
                    if installed is None
                    else []
                ),
                env=receiving_env,
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert not result.stderr
            if exit_code == 1:
                assert result.returncode == 1
                return
            assert result.returncode == 2
            report = json.loads(result.stdout)
            while report["state"] != "COMPLETE":
                assert report["state"] == "RECEIVING" and "result" not in report
                with pytest.raises(ValueError):
                    store.managed_read(
                        receiver / store.PIN,
                        public_keys=from_environment(),
                        workspace_id=co["companyId"],
                        now=datetime.now(UTC),
                    )
                assert not api(admin, co, "operations", method="GET").json()["data"][
                    "ready"
                ]
                number = report["nextPart"]
                result = subprocess.run(
                    command
                    + [
                        "--resume",
                        "--part-number",
                        str(number),
                        "--part-file",
                        str(package / f"part-{number:05d}.bin"),
                    ],
                    env=receiving_env,
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                assert not result.stderr and result.returncode in {0, 2}
                report = json.loads(result.stdout)
            assert result.returncode == exit_code and not report["ready"]
            installed = report

        def deliver(exit_code=0, *, tamper=False, resume=False):
            nonlocal installed, deliveries
            if receiver_mode in {"segments", "handover", "chain"}:
                return deliver_segments(exit_code, tamper=tamper, resume=resume)
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
        if receiver_mode in {"recovery", "segments", "handover", "chain"}:
            original_write = store.write_new
            with monkeypatch.context() as patch:

                def interrupted(root, name, data):
                    if name.startswith("catalog-"):
                        original_write(root, name, data[:8])
                        raise OSError("owned publisher interruption")
                    return original_write(root, name, data)

                patch.setattr(store, "write_new", interrupted)
                with pytest.raises(OSError):
                    store.publish(
                        folder,
                        context=store.PublishContext.model_validate(
                            json.loads(context.read_bytes())
                        ),
                        public_keys=from_environment(),
                        signer=authority,
                        signer_id="catalog",
                        now=datetime.now(UTC),
                        expected_pin_digest=first["pinDigest"],
                        head_path=args["head"],
                        checkpoint_path=args["checkpoint_file"],
                    )
            first = cli("recover-pending", first["pinDigest"], exit_code=2)
            assert first["result"] == "PARTIAL"
            deliver(exit_code=2)
            assert status()["state"] == "INVALID"
            unknown = collect(recheck("recovery-unknown.json"))
            assert unknown["envelope"]["result"] == "FAIL"
            assert api(admin, co, "operating-evidence", unknown).status_code == 200
            if receiver_mode in {"handover", "chain"}:
                from fs.gw import catalog_key_handover as handover

                successor = Ed25519PrivateKey.generate()
                successor_file = folders["reports"] / "successor.key"
                successor_file.write_bytes(successor.private_bytes_raw())
                successor_file.chmod(0o600)
                public["next-catalog"] = base64.b64encode(
                    successor.public_key().public_bytes_raw()
                ).decode()
                scopes["keys"]["next-catalog"] = {
                    "workspaceIds": [str(co["companyId"])],
                    "purposes": ["CHECKPOINT_CATALOG"],
                }
                monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
                monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
                monkeypatch.setenv(
                    "FS_GW_CATALOG_SUCCESSOR_KEY_FILE", str(successor_file)
                )
                monkeypatch.setenv("FS_GW_CATALOG_SUCCESSOR_KEY_ID", "next-catalog")
                approve_environment(monkeypatch)
                receipt = folders["reports"] / "catalog-handover.json"
                issued = subprocess.run(
                    [
                        sys.executable,
                        "tools/gw_catalog_key_handover.py",
                        "issue",
                        "--directory",
                        str(folder),
                        "--context",
                        str(context),
                        "--retiring-key-id",
                        "catalog",
                        "--expected-pin-digest",
                        first["pinDigest"],
                        "--output",
                        str(receipt),
                    ],
                    capture_output=True,
                    timeout=30,
                    check=False,
                )
                assert issued.returncode == 0 and not issued.stderr
                approved = json.loads(issued.stdout)
                assert approved["recoveryProofs"] == 1 and not approved["ready"]
                monkeypatch.setenv("FS_GW_CATALOG_KEY_FILE", str(successor_file))
                monkeypatch.setenv("FS_GW_CATALOG_KEY_ID", "next-catalog")
                first = cli("refresh", first["pinDigest"], exit_code=2)
                lifecycle = {
                    "version": 1,
                    "keys": [
                        {
                            "version": 1,
                            "workspaceId": str(co["companyId"]),
                            "keyId": "catalog",
                            "publicKey": public.pop("catalog"),
                            "state": "RETIRED",
                            "approvals": [
                                {
                                    "version": 1,
                                    "file": str(receipt),
                                    "digest": approved["handoverDigest"],
                                }
                            ],
                        }
                    ],
                }
                scopes["keys"].pop("catalog")
                monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
                monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
                monkeypatch.setenv(handover.ENV, json.dumps(lifecycle))
                approve_environment(monkeypatch)
                checked["public"] = from_environment()
                assert status()["state"] == "INVALID"
                retained_handover = receipt.read_bytes()
                receipt.write_bytes(retained_handover + b"tampered")
                assert status()["state"] == "CONFIG_REQUIRED"
                receipt.write_bytes(
                    retained_handover
                )  # Exact original under the same configured digest.
                checked["public"] = from_environment()
                deliver(exit_code=2)
                shifted = collect(recheck("retired-inner-current.json"))
                assert shifted["envelope"]["result"] == "FAIL"
                assert api(admin, co, "operating-evidence", shifted).status_code == 200
                if receiver_mode == "chain":
                    # The first private key is now unavailable; extension reads only B/C private keys.
                    key.unlink()
                    final_key = Ed25519PrivateKey.generate()
                    final_file = folders["reports"] / "final-catalog.key"
                    final_file.write_bytes(final_key.private_bytes_raw())
                    final_file.chmod(0o600)
                    public["final-catalog"] = base64.b64encode(
                        final_key.public_key().public_bytes_raw()
                    ).decode()
                    scopes["keys"]["final-catalog"] = {
                        "workspaceIds": [str(co["companyId"])],
                        "purposes": ["CHECKPOINT_CATALOG"],
                    }
                    monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
                    monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
                    monkeypatch.setenv(
                        "FS_GW_CATALOG_SUCCESSOR_KEY_FILE", str(final_file)
                    )
                    monkeypatch.setenv(
                        "FS_GW_CATALOG_SUCCESSOR_KEY_ID", "final-catalog"
                    )
                    approve_environment(monkeypatch)
                    own_file = folders["reports"] / "next-catalog-handover.json"
                    issue_args = [
                        sys.executable,
                        "tools/gw_catalog_key_handover.py",
                        "issue",
                        "--directory",
                        str(folder),
                        "--context",
                        str(context),
                        "--retiring-key-id",
                        "next-catalog",
                        "--expected-pin-digest",
                        first["pinDigest"],
                        "--output",
                        str(own_file),
                    ]
                    issued_next = subprocess.run(
                        issue_args, capture_output=True, timeout=30, check=False
                    )
                    assert issued_next.returncode == 0 and not issued_next.stderr
                    own = json.loads(issued_next.stdout)
                    continued_file = folders["reports"] / "continued-catalog.json"
                    extend_args = issue_args.copy()
                    extend_args[2] = "extend"
                    extend_args[-1] = str(continued_file)
                    extend_args += [
                        "--predecessor-key-id",
                        "catalog",
                        "--parent-file",
                        str(receipt),
                        "--expected-parent-digest",
                        approved["handoverDigest"],
                        "--retiring-handover-file",
                        str(own_file),
                        "--expected-retiring-handover-digest",
                        own["handoverDigest"],
                    ]
                    extended = subprocess.run(
                        extend_args, capture_output=True, timeout=30, check=False
                    )
                    assert extended.returncode == 0 and not extended.stderr
                    continuation = json.loads(extended.stdout)
                    assert continuation["edges"] == 2 and not continuation["ready"]
                    monkeypatch.setenv("FS_GW_CATALOG_KEY_FILE", str(final_file))
                    monkeypatch.setenv("FS_GW_CATALOG_KEY_ID", "final-catalog")
                    first = cli("refresh", first["pinDigest"], exit_code=2)
                    lifecycle["keys"][0]["approvals"] = [
                        {
                            "version": 1,
                            "file": str(continued_file),
                            "digest": continuation["handoverDigest"],
                        }
                    ]
                    lifecycle["keys"].append(
                        {
                            "version": 1,
                            "workspaceId": str(co["companyId"]),
                            "keyId": "next-catalog",
                            "publicKey": public.pop("next-catalog"),
                            "state": "RETIRED",
                            "approvals": [
                                {
                                    "version": 1,
                                    "file": str(own_file),
                                    "digest": own["handoverDigest"],
                                }
                            ],
                        }
                    )
                    scopes["keys"].pop("next-catalog")
                    monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public))
                    monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
                    monkeypatch.setenv(handover.ENV, json.dumps(lifecycle))
                    successor_file.unlink()
                    approve_environment(monkeypatch)
                    checked["public"] = from_environment()
                    retained_continuation = continued_file.read_bytes()
                    continued_file.write_bytes(retained_continuation + b"tampered")
                    assert status()["state"] == "CONFIG_REQUIRED"
                    continued_file.write_bytes(retained_continuation)
                    checked["public"] = from_environment()
                    assert status()["state"] == "INVALID"
                    deliver(exit_code=2)
                    repeated = collect(recheck("continued-inner-current.json"))
                    assert repeated["envelope"]["result"] == "FAIL"
                    assert (
                        api(admin, co, "operating-evidence", repeated).status_code
                        == 200
                    )
            # Wait only for the existing bounded runner/DB clock difference, never relax production ordering.
            catalog_path = folder / store.filename(
                first["revision"], first["catalogDigest"]
            )
            recovered_at = timestamp(
                json.loads(catalog_path.read_bytes())["envelope"]["publishedAt"]
            )
            with engine.connect() as c:
                delay = (
                    recovered_at - c.scalar(text("SELECT clock_timestamp()"))
                ).total_seconds()
            assert delay < 30
            if delay >= 0:
                time.sleep(delay + 0.02)
            new_checkpoint = folders["checkpoints"] / "after-recovery.fsbackup"
            new_head = folders["checkpoints"] / "after-recovery-head.json"
            captured = module.checkpoint(
                url=os.environ["TEST_DATABASE_URL"],
                artifact=args["artifact"],
                output=new_checkpoint,
                head=new_head,
                config=config,
            )
            first = cli(
                "publish",
                first["pinDigest"],
                ("--head", str(new_head), "--checkpoint", str(new_checkpoint)),
            )
            args = args | {
                "checkpoint_file": new_checkpoint,
                "head": new_head,
                "expected_checkpoint_digest": captured["checkpointDigest"],
                "report": folders["reports"] / "after-recovery-restore-report.json",
                "evidence": folders["reports"] / "after-recovery-restore.json",
            }
            target = module.restore(**args)
            targets.append(target["database"])
            original = json.loads(args["evidence"].read_bytes())
            assert original["envelope"]["result"] == "PARTIAL"
            assert api(admin, co, "operating-evidence", original).status_code == 200
            deliver()
            renewed = collect(recheck("after-recovery-current.json"))
            assert renewed["envelope"]["result"] == "PARTIAL"
            assert api(admin, co, "operating-evidence", renewed).status_code == 200
            with engine.connect() as c:
                assert (
                    c.scalar(
                        text(
                            "SELECT count(*) FROM gw.operating_evidence WHERE kind='ACCEPTANCE' AND result='FAIL'"
                        )
                    )
                    >= 1
                )
                delay = (
                    timestamp(renewed["envelope"]["finishedAt"])
                    - c.scalar(text("SELECT clock_timestamp()"))
                ).total_seconds()
            assert delay < 30
            if delay >= 0:
                time.sleep(delay + 0.02)
            assert status()["state"] == "PARTIAL"
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
        assert (
            failed["result"] == "FAIL" and failed["sequence"] == first["sequence"] + 1
        )
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
        assert (
            refreshed["result"] == "FAIL"
            and refreshed["sequence"] == failed["sequence"]
        )
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
        if receiver_mode == "handover":
            # Current revocation overrides older dual-signed approvals, without resetting history.
            lifecycle["keys"][0].update(state="REVOKED", approvals=[])
            monkeypatch.setenv(handover.ENV, json.dumps(lifecycle))
            approve_environment(monkeypatch)
            checked["public"] = from_environment()
            with pytest.raises(ValueError):
                from fs.gw.catalog_transfer import export as export_history

                export_history(
                    folder,
                    context=store.PublishContext.model_validate(
                        json.loads(context.read_bytes())
                    ),
                    public_keys=from_environment(),
                    now=datetime.now(UTC),
                    base_revision=0,
                    base_digest="ABSENT",
                )
            current_catalog, _ = read(
                public_keys=from_environment(),
                workspace_id=co["companyId"],
                now=datetime.now(UTC),
            )
            assert (
                current_catalog.records[0].result == "FAIL"
                and current_catalog.signer_key_id == "next-catalog"
            )
            assert not api(admin, co, "operations", method="GET").json()["data"][
                "ready"
            ]
        elif receiver_mode == "chain":
            from fs.gw import catalog_trust_store as floor

            trust_path = os.environ[floor.ENV]
            monkeypatch.delenv(floor.ENV)
            assert status()["state"] == "CONFIG_REQUIRED"
            monkeypatch.setenv(floor.ENV, trust_path)
            assert status()["state"] == "INVALID"  # Latest actual FAIL remains.
            # Persist revocation before live ENV edits; earlier valid settings immediately fail.
            _, previous_floor = floor.inspect(trust_path)
            revoked = subprocess.run(
                [
                    sys.executable,
                    "tools/gw_catalog_trust.py",
                    "revoke",
                    "--expected-digest",
                    previous_floor,
                    "--workspace-id",
                    str(co["companyId"]),
                    "--key-id",
                    "next-catalog",
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert revoked.returncode == 0 and not revoked.stderr
            assert not json.loads(revoked.stdout)["ready"]
            with pytest.raises(ValueError):
                from_environment()
            assert status()["state"] == "CONFIG_REQUIRED"
            # Even the former correctly signed/valid RETIRED configuration cannot undo it.
            rollback = subprocess.run(
                [
                    sys.executable,
                    "tools/gw_catalog_trust.py",
                    "advance",
                    "--expected-digest",
                    json.loads(revoked.stdout)["digest"],
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            assert rollback.returncode == 1 and not rollback.stderr
            lifecycle["keys"][1].update(state="REVOKED", approvals=[])
            monkeypatch.setenv(handover.ENV, json.dumps(lifecycle))
            with pytest.raises(ValueError):
                from_environment()
            assert status()["state"] == "CONFIG_REQUIRED"
    finally:
        with cleanup.connect() as connection:
            for database in targets:
                connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        cleanup.dispose()
