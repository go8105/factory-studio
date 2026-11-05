"""Pinned offline transfer retains failures, validates every revision and resumes safely."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from fs.gw import catalog_store as store
from fs.gw import catalog_transfer as transfer
from fs.gw.checkpoint_catalog import DOMAIN, read
from fs.gw.operating_contract import canonical
from test_gw_catalog_store import cli_env, invoke, setup


def outgoing(parts, base=0, sha="ABSENT", now=None):
    folder, kw, *_ = parts
    return transfer.export(
        folder,
        context=kw["context"],
        public_keys=kw["public_keys"],
        now=now or kw["now"],
        base_revision=base,
        base_digest=sha,
    )


def receiver(parts):
    path = parts[0].parent / "receiver"
    path.mkdir(mode=0o700)
    return path


def receive(parts, path, raw, report, previous=None, **changes):
    kw = parts[1]
    args = {
        "context": kw["context"],
        "public_keys": kw["public_keys"],
        "now": kw["now"],
        "expected_transfer_digest": report["transferDigest"],
        "expected_catalog_id": report["catalogId"],
        "expected_pin_digest": previous["pinDigest"] if previous else "ABSENT",
        "initialize": previous is None,
    }
    args.update(changes)
    return transfer.install(path, raw, **args)


def reseal(parts, raw, change):
    bundle = json.loads(raw)
    change(bundle)
    for snapshot in bundle["snapshots"]:
        document = json.loads(base64.b64decode(snapshot["content"]))
        document["signature"] = base64.b64encode(
            parts[1]["signer"].sign(DOMAIN + canonical(document["envelope"]))
        ).decode()
        data = canonical(document) + b"\n"
        snapshot.update(
            content=base64.b64encode(data).decode(), digest=store.digest(data)
        )
    data = canonical(bundle) + b"\n"
    return data, {
        "catalogId": bundle["catalogId"],
        "transferDigest": store.digest(data),
    }


def change_envelope(bundle, index, change):
    snapshot = bundle["snapshots"][index]
    document = json.loads(base64.b64decode(snapshot["content"]))
    change(document["envelope"])
    snapshot["content"] = base64.b64encode(canonical(document)).decode()


def test_initial_copy_then_missed_revisions_preserve_failures_and_refresh(
    setup, monkeypatch
):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    accepted = receive(setup, dest, raw, report)
    assert (
        accepted["catalogDigest"] == first["catalogDigest"]
        and accepted["ready"] is False
    )
    assert accepted["pinDigest"] != first["pinDigest"]  # Paths are receiver-owned.
    failed = invoke(setup, first, head_path=setup[0] / "missing")
    refreshed = invoke(setup, failed, operation="refresh")
    batch, final = outgoing(setup, 1, first["catalogDigest"])
    installed = receive(setup, dest, batch, final, accepted)
    assert (
        installed["revision"] == 3
        and installed["sequence"] == 2
        and installed["result"] == "FAIL"
    )
    assert installed["catalogDigest"] == refreshed["catalogDigest"]
    assert len(list(dest.glob("catalog-*.json"))) == 3
    assert any(
        json.loads(p.read_bytes())["envelope"]["records"][0]["result"] == "FAIL"
        for p in dest.glob("catalog-*.json")
    )
    monkeypatch.setenv(store.PIN_ENV, str(dest / store.PIN))
    assert (
        read(
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=setup[2]["now"],
        )[0]
        .records[0]
        .result
        == "FAIL"
    )
    with pytest.raises(ValueError):
        store.publish(
            dest,
            **(
                setup[1]
                | {
                    "expected_pin_digest": installed["pinDigest"],
                    "initialize": False,
                    "operation": "refresh",
                }
            ),
        )
    with pytest.raises(ValueError):
        receive(
            setup, setup[0], raw, report, first
        )  # Publisher store cannot become receiver.


@pytest.mark.parametrize(
    "problem",
    [
        "wrong_hash",
        "wrong_id",
        "wrong_scope",
        "missing",
        "order",
        "event_gap",
        "same_sequence_change",
        "old_success",
        "signature",
        "stale",
        "old_base",
        "extra_field",
    ],
)
def test_invalid_transfer_fences_receiver_and_never_installs_older_success(
    setup, problem
):
    first = invoke(setup)
    failed = invoke(setup, first, head_path=setup[0] / "absent")
    invoke(setup, failed, operation="refresh")
    raw, report = outgoing(setup)
    dest = receiver(setup)
    changes = {}
    if problem == "wrong_hash":
        changes["expected_transfer_digest"] = "0" * 64
    elif problem == "wrong_id":
        from uuid import uuid4

        changes["expected_catalog_id"] = str(uuid4())
    elif problem == "wrong_scope":
        changes["context"] = setup[1]["context"].model_copy(
            update={"generation_id": 999}
        )
    elif problem == "signature":
        bundle = json.loads(raw)
        doc = json.loads(base64.b64decode(bundle["snapshots"][-1]["content"]))
        doc["signature"] = base64.b64encode(b"z" * 64).decode()
        data = canonical(doc) + b"\n"
        bundle["snapshots"][-1].update(
            content=base64.b64encode(data).decode(), digest=store.digest(data)
        )
        raw = canonical(bundle)
        report["transferDigest"] = store.digest(raw)
    elif problem == "stale":
        changes["now"] = setup[1]["now"] + timedelta(minutes=16)
    else:

        def alter(bundle):
            if problem == "missing":
                bundle["snapshots"].pop(1)
            elif problem == "order":
                bundle["snapshots"].reverse()
            elif problem == "old_base":
                bundle.update(baseRevision=1, baseDigest=first["catalogDigest"])
            elif problem == "extra_field":
                bundle["adminApproved"] = True
            else:

                def change(env):
                    record = env["records"][0]
                    if problem == "event_gap":
                        record["sequence"] += 5
                    elif problem == "same_sequence_change":
                        record["result"] = "PARTIAL"
                    elif problem == "old_success":
                        original = json.loads(
                            base64.b64decode(bundle["snapshots"][0]["content"])
                        )["envelope"]["records"][0]
                        record.update(result="PASS", head=original["head"], sequence=3)

                change_envelope(bundle, -1, change)

        raw, report = reseal(setup, raw, alter)
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        receive(setup, dest, raw, report, **changes)
    assert not list(dest.glob("catalog-*.json")) and (dest / store.PENDING).exists()


@pytest.mark.parametrize(
    "cut",
    [
        "identity_temp",
        "snapshot_temp",
        "identity_link",
        "snapshot_link",
        "replace",
        "after_replace",
        "clear_pending",
    ],
)
def test_interrupted_receive_same_bundle_resumes_without_private_key_or_overwrite(
    setup, monkeypatch, cut
):
    invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    original_write, original_link, original_replace = (
        store.write_new,
        os.link,
        os.replace,
    )
    original_unlink, original_sync = os.unlink, os.fsync
    count = 0
    replaced = False

    def broken_write(root, name, data):
        nonlocal count
        if name.startswith(".pin-"):
            count += 1
            if (cut == "identity_temp" and count == 1) or (
                cut == "snapshot_temp" and count == 2
            ):
                original_write(root, name, data[:8])
                raise OSError("interrupted temp write")
        return original_write(root, name, data)

    def broken_link(src, dst, **kw):
        value = original_link(src, dst, **kw)
        if (cut == "identity_link" and dst == store.RECEIVER) or (
            cut == "snapshot_link" and dst.startswith("catalog-")
        ):
            raise OSError("interrupted after atomic link")
        return value

    def broken_replace(*args, **kw):
        nonlocal replaced
        if cut == "replace":
            raise OSError("interrupted replace")
        value = original_replace(*args, **kw)
        replaced = True
        return value

    def broken_sync(fd):
        if cut == "after_replace" and replaced:
            raise OSError("interrupted directory sync")
        return original_sync(fd)

    def broken_unlink(name, **kw):
        if cut == "clear_pending" and name == store.PENDING:
            raise OSError("interrupted pending removal")
        return original_unlink(name, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(store, "write_new", broken_write)
        patch.setattr(os, "link", broken_link)
        patch.setattr(os, "replace", broken_replace)
        patch.setattr(os, "fsync", broken_sync)
        patch.setattr(os, "unlink", broken_unlink)
        with pytest.raises(OSError):
            receive(setup, dest, raw, report)
    assert (dest / store.PENDING).exists()
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=setup[2]["now"],
        )
    with pytest.raises(ValueError):
        receive(setup, dest, raw, report)
    pin = (
        store.digest((dest / store.PIN).read_bytes())
        if (dest / store.PIN).exists()
        else "ABSENT"
    )
    recovered = receive(
        setup, dest, raw, report, initialize=False, resume=True, expected_pin_digest=pin
    )
    assert recovered["result"] == "PASS" and recovered["ready"] is False
    assert not (dest / store.PENDING).exists()
    completed = receive(setup, dest, raw, report, recovered, resume=True)
    assert completed == recovered
    assert len(list(dest.glob("catalog-*.json"))) == 1


def test_pending_different_bundle_and_stale_pin_rejected(setup, monkeypatch):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    with monkeypatch.context() as patch:
        patch.setattr(
            os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("interrupted"))
        )
        with pytest.raises(OSError):
            receive(setup, dest, raw, report)
    invoke(setup, first, operation="refresh")
    newer, new_report = outgoing(setup)
    with pytest.raises(ValueError):
        receive(setup, dest, newer, new_report, initialize=False, resume=True)
    result = receive(setup, dest, raw, report, initialize=False, resume=True)
    with pytest.raises(ValueError):
        receive(setup, dest, newer, new_report, result, expected_pin_digest="0" * 64)
    assert store.digest((dest / store.PIN).read_bytes()) == result["pinDigest"]


def test_missing_or_corrupt_publisher_archive_never_skipped(setup):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    oldest = next(
        p
        for p in setup[0].glob("catalog-*.json")
        if json.loads(p.read_bytes())["envelope"]["revision"] == 1
    )
    oldest.write_bytes(b"damaged")
    with pytest.raises(ValueError):
        outgoing(setup)
    oldest.unlink()  # Synthetic missing archive; not a recovery instruction.
    with pytest.raises(KeyError):
        outgoing(setup)


def test_old_context_latest_is_retained_and_reported_unmatched(setup):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    changed = setup[1]["context"].model_copy(update={"code_revision": "a" * 40})
    result = receive(setup, dest, raw, report, context=changed)
    assert (
        result["catalogDigest"] == first["catalogDigest"]
        and result["contextMatches"] is False
    )


def test_two_real_receiver_cli_processes_and_no_signing_key_required(setup):
    first = invoke(setup)
    now = datetime.now(UTC)
    invoke(setup, first, operation="refresh", now=now)
    raw, report = outgoing(setup, now=now)
    dest = receiver(setup)
    env, publishing = cli_env(setup)
    del env["FS_GW_CATALOG_KEY_FILE"]
    del env["FS_GW_CATALOG_KEY_ID"]
    bundle = dest.parent / "transfer.json"
    bundle.write_bytes(raw)
    bundle.chmod(0o600)
    command = [
        sys.executable,
        "tools/gw_checkpoint_transfer.py",
        "install",
        "--directory",
        str(dest),
        "--context",
        publishing[6],
        "--transfer",
        str(bundle),
        "--expected-transfer-digest",
        report["transferDigest"],
        "--expected-catalog-id",
        report["catalogId"],
        "--expected-pin-digest",
        "ABSENT",
        "--initialize",
    ]
    processes = [
        subprocess.Popen(
            command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for _ in range(2)
    ]
    outcomes = [(p.communicate(timeout=30), p.returncode) for p in processes]
    assert sorted(code for _, code in outcomes) == [0, 1]
    assert all(not output[1] for output, _ in outcomes)
    assert len(list(dest.glob("catalog-*.json"))) == 2


def test_confirmed_new_anchor_with_tampered_bytes_fences_old_pin_and_same_original_resumes(
    setup,
):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    installed = receive(setup, dest, raw, report)
    invoke(setup, first, operation="refresh")
    newer, anchor = outgoing(setup, 1, first["catalogDigest"])
    before = (dest / store.PIN).read_bytes()
    with pytest.raises(ValueError):
        receive(setup, dest, newer + b"tamper", anchor, installed)
    assert (
        dest / store.PIN
    ).read_bytes() == before  # Retained as evidence, unusable while fenced.
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=setup[2]["now"],
        )
    resumed = receive(setup, dest, newer, anchor, installed, resume=True)
    assert resumed["revision"] == 2 and resumed["result"] == "PASS"


@pytest.mark.parametrize(
    "problem",
    [
        "too_many",
        "oversize",
        "duplicate_json",
        "recursive",
        "bool_version",
        "key_revoked",
    ],
)
def test_transfer_bounds_and_current_authority_fail_closed(setup, problem):
    invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    changes = {}
    if problem == "too_many":
        bundle = json.loads(raw)
        bundle["snapshots"] *= transfer.MAX_SNAPSHOTS + 1
        raw = canonical(bundle)
    elif problem == "oversize":
        raw = b"x" * (transfer.MAX_TRANSFER + 1)
    elif problem == "duplicate_json":
        raw = raw.replace(b'"version":1', b'"version":1,"version":1', 1)
    elif problem == "recursive":
        raw = b"[" * 2000 + b"]" * 2000
    elif problem == "bool_version":
        bundle = json.loads(raw)
        bundle["version"] = True
        raw = canonical(bundle)
    else:
        from fs.gw.evidence_trust import EvidenceTrust

        changes["public_keys"] = EvidenceTrust({}, {})
    report["transferDigest"] = store.digest(raw)
    with pytest.raises((ValueError, KeyError, RecursionError)):
        receive(setup, dest, raw, report, **changes)
    assert (dest / store.PENDING).exists() and not (dest / store.PIN).exists()


def test_export_refuses_interrupted_source_and_bounded_batch(setup, monkeypatch):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    with monkeypatch.context() as patch:
        patch.setattr(transfer, "MAX_SNAPSHOTS", 1)
        with pytest.raises(ValueError):
            outgoing(setup)
    pending = setup[0] / store.PENDING
    pending.write_bytes(b"{}")
    pending.chmod(0o600)
    with pytest.raises(ValueError):
        outgoing(setup)


def test_cli_missing_input_fences_receiver_and_wrong_expected_pin_does_not(setup):
    first = invoke(setup)
    invoke(setup, first, operation="refresh", now=datetime.now(UTC))
    _raw, report = outgoing(setup, now=datetime.now(UTC))
    env, publishing = cli_env(setup)
    dest = receiver(setup)
    command = [
        sys.executable,
        "tools/gw_checkpoint_transfer.py",
        "install",
        "--directory",
        str(dest),
        "--context",
        publishing[6],
        "--transfer",
        str(dest.parent / "missing-transfer.json"),
        "--expected-transfer-digest",
        report["transferDigest"],
        "--expected-catalog-id",
        report["catalogId"],
        "--expected-pin-digest",
        "0" * 64,
        "--initialize",
    ]
    denied = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert (
        denied.returncode == 1
        and not denied.stderr
        and not (dest / store.PENDING).exists()
    )
    command[-2] = "ABSENT"
    blocked = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert (
        blocked.returncode == 1
        and not blocked.stderr
        and (dest / store.PENDING).exists()
    )


def test_receiver_symlink_and_existing_altered_snapshot_cannot_be_overwritten(
    setup, monkeypatch
):
    invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    with monkeypatch.context() as patch:
        patch.setattr(
            os, "replace", lambda *a, **k: (_ for _ in ()).throw(OSError("interrupted"))
        )
        with pytest.raises(OSError):
            receive(setup, dest, raw, report)
    snapshot = next(dest.glob("catalog-*.json"))
    snapshot.write_bytes(b"altered")
    with pytest.raises(ValueError):
        receive(setup, dest, raw, report, initialize=False, resume=True)
    assert snapshot.read_bytes() == b"altered" and (dest / store.PENDING).exists()


def test_complete_history_can_advance_past_failure_only_with_new_capture(setup):
    first = invoke(setup)
    fail = invoke(setup, first, head_path=setup[0] / "absent")
    now = setup[1]["now"]
    setup[4](now + timedelta(seconds=1))
    fresh = invoke(setup, fail, now=now + timedelta(seconds=2))
    raw, report = outgoing(setup, now=now + timedelta(seconds=2))
    dest = receiver(setup)
    result = receive(setup, dest, raw, report, now=now + timedelta(seconds=2))
    assert (
        result["result"] == "PASS" and result["catalogDigest"] == fresh["catalogDigest"]
    )
    assert len(list(dest.glob("catalog-*.json"))) == 3


def test_same_revision_fork_cannot_be_claimed_as_completed_retry(setup):
    invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    result = receive(setup, dest, raw, report)

    def alter(bundle):
        change_envelope(
            bundle, 0, lambda env: env["records"][0].update(result="FAIL", head=None)
        )

    fork, anchor = reseal(setup, raw, alter)
    with pytest.raises(ValueError):
        receive(setup, dest, fork, anchor, result, resume=True)
    assert (
        len(list(dest.glob("catalog-*.json"))) == 1
        and not (dest / store.PENDING).exists()
    )
    assert store.digest((dest / store.PIN).read_bytes()) == result["pinDigest"]


def test_changed_base_archive_cannot_replace_retained_receiver_history(setup):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    result = receive(setup, dest, raw, report)
    invoke(setup, first, operation="refresh")
    batch, _ = outgoing(setup, 1, first["catalogDigest"])

    def alter(bundle):
        for index in range(2):
            change_envelope(
                bundle,
                index,
                lambda env: env["records"][0].update(result="FAIL", head=None),
            )

    fork, anchor = reseal(setup, batch, alter)
    document = json.loads(fork)
    document["baseDigest"] = document["snapshots"][0]["digest"]
    fork = canonical(document)
    anchor["transferDigest"] = store.digest(fork)
    with pytest.raises(ValueError):
        receive(setup, dest, fork, anchor, result)
    assert (
        len(list(dest.glob("catalog-*.json"))) == 1 and (dest / store.PENDING).exists()
    )


def test_expired_pending_same_original_can_finish_history_but_never_become_current_success(
    setup,
):
    first = invoke(setup)
    raw, report = outgoing(setup)
    dest = receiver(setup)
    with pytest.raises(ValueError):
        receive(setup, dest, raw + b"damaged", report)
    later = setup[1]["now"] + timedelta(minutes=16)
    history = receive(
        setup, dest, raw, report, initialize=False, resume=True, now=later
    )
    assert history["targetFresh"] is False and history["ready"] is False
    assert not (dest / store.PENDING).exists()
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=later,
        )
    invoke(setup, first, operation="refresh", now=later)
    fresh_raw, anchor = outgoing(setup, 1, first["catalogDigest"], now=later)
    current = receive(setup, dest, fresh_raw, anchor, history, now=later)
    assert current["targetFresh"] is True and current["revision"] == 2


def test_real_cli_expired_pending_pass_returns_two_and_remains_unusable(setup):
    old_time = datetime.now(UTC) - timedelta(minutes=16)
    setup[4](old_time - timedelta(seconds=1))
    invoke(setup, now=old_time)
    raw, report = outgoing(setup, now=old_time)
    env, publishing = cli_env(setup)
    env.pop("FS_GW_CATALOG_KEY_FILE")
    env.pop("FS_GW_CATALOG_KEY_ID")
    dest = receiver(setup)
    packet = dest.parent / "expired-transfer.json"
    packet.write_bytes(raw)
    packet.chmod(0o600)
    command = [
        sys.executable,
        "tools/gw_checkpoint_transfer.py",
        "install",
        "--directory",
        str(dest),
        "--context",
        publishing[6],
        "--transfer",
        str(packet),
        "--expected-transfer-digest",
        report["transferDigest"],
        "--expected-catalog-id",
        report["catalogId"],
        "--expected-pin-digest",
        "ABSENT",
        "--initialize",
    ]
    blocked = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert blocked.returncode == 1 and (dest / store.PENDING).exists()
    command[-1] = "--resume"
    historical = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert historical.returncode == 2 and not historical.stderr
    outcome = json.loads(historical.stdout)
    assert (
        outcome["result"] == "PASS"
        and outcome["targetFresh"] is False
        and outcome["ready"] is False
    )
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=datetime.now(UTC),
        )
