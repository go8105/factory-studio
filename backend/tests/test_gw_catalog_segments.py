"""Large-history chunks never become an intermediate operational success."""

# ruff: noqa: F401,F811
import json
import os
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidSignature
from test_gw_catalog_recovery import interrupt, recover
from test_gw_catalog_store import cli_env, invoke, setup
from test_gw_catalog_transfer import outgoing, receiver
from test_gw_catalog_transfer import receive as small_receive

from fs.gw import catalog_segments as segments
from fs.gw import catalog_store as store
from fs.gw import catalog_transfer as transfer
from fs.gw.evidence_trust import EvidenceTrust
from fs.gw.operating_contract import canonical


def package(parts, base=0, sha="ABSENT", **changes):
    path = parts[0].parent / ("package-" + uuid4().hex)
    path.mkdir(mode=0o700)
    kw = parts[1]
    args = {
        "context": kw["context"],
        "public_keys": kw["public_keys"],
        "now": kw["now"],
        "base_revision": base,
        "base_digest": sha,
    }
    args.update(changes)
    report = segments.export(parts[0], path, **args)
    return path, (path / "manifest.json").read_bytes(), report


def receive(parts, path, packet, report, *, number=None, previous=None, **changes):
    folder, raw, anchor = packet
    kw = parts[1]
    args = {
        "context": kw["context"],
        "public_keys": kw["public_keys"],
        "now": kw["now"],
        "expected_manifest_digest": anchor["manifestDigest"],
        "expected_catalog_id": anchor["catalogId"],
        "expected_pin_digest": (previous or {}).get("pinDigest", "ABSENT"),
        "initialize": previous is None,
        "resume": previous is not None,
        "part_number": number,
        "part_raw": (folder / f"part-{number:05d}.bin").read_bytes()
        if number
        else None,
    }
    args.update(changes)
    return segments.receive(path, raw, **args)


def finish(parts, dest, packet, report=None, **changes):
    report = receive(parts, dest, packet, None, previous=report, **changes)
    changes = {k: v for k, v in changes.items() if k not in {"resume", "initialize"}}
    while report["state"] != "COMPLETE":
        report = receive(
            parts,
            dest,
            packet,
            None,
            number=report["nextPart"],
            previous=report,
            **changes,
        )
    return report


def blocked(parts, dest):
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=parts[1]["public_keys"],
            workspace_id=parts[2]["workspace_id"],
            now=parts[1]["now"],
        )


def test_more_than_256_revisions_activates_only_final_fail_and_lost_response(setup):
    last = invoke(setup)
    for _ in range(256):
        last = invoke(setup, last, operation="refresh")
    last = invoke(setup, last, head_path=setup[0] / "missing")
    with pytest.raises(ValueError):
        outgoing(setup)
    packet = package(setup)
    assert packet[2]["parts"] == 258
    dest = receiver(setup)
    progress = receive(setup, dest, packet, None)
    assert progress["state"] == "RECEIVING" and "result" not in progress
    for number in range(1, 259):
        progress = receive(setup, dest, packet, None, previous=progress, number=number)
        if number < 258:
            assert not (dest / store.PIN).exists()
            blocked(setup, dest)
    assert (
        progress["state"] == "COMPLETE"
        and progress["result"] == "FAIL"
        and progress["revision"] == 258
        and not progress["ready"]
    )
    assert not (dest / store.PENDING).exists()
    replay = receive(setup, dest, packet, None, previous=progress)
    assert replay == progress
    assert len(list(dest.glob("catalog-*.json"))) == 258


def test_more_than_8mib_unknown_originals_preserved_without_inferred_success(
    setup, monkeypatch
):
    interrupt(setup, monkeypatch, size=0)
    for revision in range(3, 8):
        raw = bytes([revision]) * store.MAX_BYTES
        file = setup[0] / store.filename(revision, store.digest(raw))
        file.write_bytes(raw)
        file.chmod(0o600)
    recovered = recover(setup)
    with pytest.raises(ValueError):
        outgoing(setup)
    packet = package(setup)
    assert (
        sum(p.stat().st_size for p in packet[0].glob("part-*.bin"))
        > transfer.MAX_TRANSFER
    )
    dest = receiver(setup)
    report = finish(setup, dest, packet)
    assert (
        report["result"] == "PARTIAL"
        and report["catalogDigest"] == recovered["catalogDigest"]
        and not report["ready"]
    )
    assert all(
        (dest / p.name).read_bytes() == p.read_bytes()
        for p in setup[0].glob("catalog-*.json")
    )


@pytest.mark.parametrize(
    "problem",
    [
        "manifest_hash",
        "duplicate",
        "order",
        "extra",
        "scope",
        "version",
        "base",
        "missing_manifest",
        "part_hash",
        "missing_part",
        "wrong_number",
        "signature",
        "revoked",
        "future",
        "stale",
        "fork",
    ],
)
def test_invalid_or_incomplete_plan_never_activates_old_success(setup, problem):
    first = invoke(setup)
    raw, anchor = outgoing(setup)
    dest = receiver(setup)
    old = small_receive(setup, dest, raw, anchor)
    invoke(setup, first, head_path=setup[0] / "missing")
    folder, manifest, report = package(setup, 1, first["catalogDigest"])
    value = json.loads(manifest)
    changes = {"initialize": False, "resume": False, "previous": old}
    if problem == "manifest_hash":
        report["manifestDigest"] = "0" * 64
    elif problem == "missing_manifest":
        manifest = b""
    elif problem == "duplicate":
        value["parts"].append(value["parts"][0])
    elif problem == "order":
        value["parts"].reverse()
    elif problem == "extra":
        value["adminApproved"] = True
    elif problem == "scope":
        value["workspaceId"] = "999"
    elif problem == "version":
        value["version"] = True
    elif problem == "base":
        value["baseDigest"] = "f" * 64
    elif problem == "part_hash":
        changes.update(number=1, part_raw=b"damaged")
    elif problem == "missing_part":
        changes.update(number=1, part_raw=None)
    elif problem == "wrong_number":
        changes.update(number=2)
    elif problem == "revoked":
        changes.update(public_keys=EvidenceTrust({}, {}))
    elif problem in {"stale", "future"}:
        changes["number"] = 1
        changes["now"] = setup[1]["now"] + timedelta(
            minutes=16 if problem == "stale" else -1
        )
    elif problem == "fork":
        value["parts"][-1]["digest"] = value["parts"][-1]["actualDigest"] = "f" * 64
    elif problem == "signature":
        data = json.loads((folder / "part-00001.bin").read_bytes())
        data["signature"] = "eA=="
        damaged = canonical(data)
        (folder / "part-00001.bin").write_bytes(damaged)
        value["targetDigest"] = store.digest(damaged)
        value["parts"][0].update(
            digest=store.digest(damaged),
            actualDigest=store.digest(damaged),
            size=len(damaged),
        )
    if problem not in {"manifest_hash", "missing_manifest"}:
        manifest = canonical(value)
        report["manifestDigest"] = store.digest(manifest)
    packet = folder, manifest, report
    original_pin = (dest / store.PIN).read_bytes()
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        result = receive(setup, dest, packet, None, **changes)
        while result["state"] != "COMPLETE":
            result = receive(
                setup,
                dest,
                packet,
                None,
                previous=result,
                number=result["nextPart"],
                **{k: v for k, v in changes.items() if k in {"now", "public_keys"}},
            )
    assert (dest / store.PIN).read_bytes() == original_pin
    # Revoked current keys prevent base verification BEFORE mutation; all other cases fence.
    if problem != "revoked":
        assert (dest / store.PENDING).exists()
    blocked(setup, dest) if problem != "revoked" else None


@pytest.mark.parametrize(
    "cut",
    [
        "manifest",
        "identity",
        "snapshot",
        "link",
        "replace",
        "after_replace",
        "pending_clear",
    ],
)
def test_restart_reconstructs_progress_from_exact_originals_and_final_cas(
    setup, monkeypatch, cut
):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    packet = package(setup)
    dest = receiver(setup)
    link, replace, unlink = os.link, os.replace, os.unlink

    def broken_put(root, name, raw):
        if (
            (cut == "manifest" and name.startswith(".catalog-plan-"))
            or (cut == "identity" and name == store.RECEIVER)
            or (cut == "snapshot" and name.startswith("catalog-"))
        ):
            raise OSError("injected before publication")
        result = transfer.put_snapshot_original(root, name, raw)
        return result

    def broken_link(src, dst, **kw):
        result = link(src, dst, **kw)
        if cut == "link" and dst.startswith("catalog-"):
            raise OSError("injected after link")
        return result

    def broken_replace(*a, **kw):
        if cut == "replace":
            raise OSError("injected before replace")
        result = replace(*a, **kw)
        if cut == "after_replace":
            raise OSError("injected after replace")
        return result

    def broken_unlink(name, **kw):
        if cut == "pending_clear" and name == store.PENDING:
            raise OSError("injected before clear")
        return unlink(name, **kw)

    with monkeypatch.context() as patch:
        patch.setattr(
            transfer, "put_snapshot_original", transfer.put_snapshot, raising=False
        )
        patch.setattr(transfer, "put_snapshot", broken_put)
        patch.setattr(os, "link", broken_link)
        patch.setattr(os, "replace", broken_replace)
        patch.setattr(os, "unlink", broken_unlink)
        with pytest.raises(OSError):
            finish(setup, dest, packet)
    assert (dest / store.PENDING).exists()
    blocked(setup, dest)
    pin = (
        store.digest((dest / store.PIN).read_bytes())
        if (dest / store.PIN).exists()
        else "ABSENT"
    )
    if cut in {"replace", "after_replace", "pending_clear"}:
        before = {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in dest.iterdir()
        }
        waiting = receive(
            setup, dest, packet, None, previous={"pinDigest": pin}, status=True
        )
        assert waiting["state"] == "AWAITING_FINALIZE" and "result" not in waiting
        assert waiting["sourceResult"] == "PASS" and waiting["ready"] is False
        assert before == {
            p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in dest.iterdir()
        }
    report = finish(setup, dest, packet, {"pinDigest": pin})
    assert report["state"] == "COMPLETE" and report["revision"] == 2
    assert len(list(dest.glob("catalog-*.json"))) == 2


def test_intermediate_status_is_read_only_replay_exact_and_changed_original_finally_blocks(
    setup,
):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    packet = package(setup)
    dest = receiver(setup)
    report = receive(setup, dest, packet, None, number=1)
    before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in dest.iterdir()}
    status = receive(setup, dest, packet, None, previous=report, status=True)
    assert (
        status["nextPart"] == 2
        and status["state"] == "RECEIVING"
        and "result" not in status
    )
    assert before == {
        p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in dest.iterdir()
    }
    assert receive(setup, dest, packet, None, previous=report, number=1) == report
    snapshot = next(dest.glob("catalog-*.json"))
    data = snapshot.read_bytes()
    snapshot.write_bytes(
        data[:-1] + b"x"
    )  # Same-size corruption cannot be trusted as completion.
    with pytest.raises((ValueError, InvalidSignature)):
        receive(setup, dest, packet, None, previous=report, number=2)
    blocked(setup, dest)


def test_expired_pending_can_finish_history_but_not_current_read_and_new_manifest_advances(
    setup,
):
    first = invoke(setup)
    packet = package(setup)
    dest = receiver(setup)
    report = receive(setup, dest, packet, None)
    later = setup[1]["now"] + timedelta(minutes=16)
    final = receive(setup, dest, packet, None, previous=report, number=1, now=later)
    assert (
        final["state"] == "COMPLETE"
        and final["targetFresh"] is False
        and not final["ready"]
    )
    with pytest.raises(ValueError):
        store.managed_read(
            dest / store.PIN,
            public_keys=setup[1]["public_keys"],
            workspace_id=setup[2]["workspace_id"],
            now=later,
        )
    invoke(setup, first, operation="refresh", now=later)
    newer = package(setup, 1, first["catalogDigest"], now=later)
    current = finish(setup, dest, newer, final, resume=False, now=later)
    assert current["targetFresh"] and current["revision"] == 2


def test_wrong_plan_pin_or_role_cannot_reset_pending_progress(setup):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    packet = package(setup)
    dest = receiver(setup)
    report = receive(setup, dest, packet, None, number=1)
    before = {p.name: p.read_bytes() for p in dest.iterdir()}
    for changes in (
        {"expected_pin_digest": "f" * 64},
        {"expected_manifest_digest": "f" * 64},
        {"resume": False},
        {"initialize": True},
        {"context": setup[1]["context"].model_copy(update={"generation_id": 99})},
    ):
        with pytest.raises(ValueError):
            receive(setup, dest, packet, None, previous=report, **changes)
        assert before == {p.name: p.read_bytes() for p in dest.iterdir()}
    with pytest.raises(ValueError):
        receive(setup, setup[0], packet, None, previous=first)
    final = finish(setup, dest, packet, report)
    assert final["revision"] == 2
    # Unrecognized manifest cannot be introduced as a completed retry without a fence.
    value = json.loads(packet[1])
    changed = canonical(value)  # Different exact bytes, same valid semantic content.
    forged = packet[0], changed, packet[2] | {"manifestDigest": store.digest(changed)}
    with pytest.raises(ValueError):
        receive(setup, dest, forged, None, previous=final)


def test_current_key_revocation_after_staging_revalidates_all_before_activation(setup):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    packet = package(setup)
    dest = receiver(setup)
    report = receive(setup, dest, packet, None, number=1)
    with pytest.raises(ValueError):
        receive(
            setup,
            dest,
            packet,
            None,
            previous=report,
            number=2,
            public_keys=EvidenceTrust({}, {}),
        )
    blocked(setup, dest)
    assert (dest / store.PENDING).exists() and not (dest / store.PIN).exists()


@pytest.mark.parametrize(
    "problem",
    ["base", "missing", "tamper", "pending", "limit", "destination", "symlink"],
)
def test_export_fails_without_publishing_manifest_on_incomplete_or_oversized_source(
    setup, monkeypatch, problem
):
    first = invoke(setup)
    invoke(setup, first, operation="refresh")
    changes = {}
    if problem == "base":
        changes.update(base_revision=1, base_digest="f" * 64)
    elif problem in {"missing", "tamper"}:
        path = setup[0] / store.filename(1, first["catalogDigest"])
        path.unlink() if problem == "missing" else path.write_bytes(b"damaged")
    elif problem == "pending":
        file = setup[0] / store.PENDING
        file.write_bytes(b"{}")
        file.chmod(0o600)
    elif problem == "limit":
        monkeypatch.setattr(segments, "MAX_PARTS", 1)
    elif problem == "destination":
        changes["output"] = setup[0]
    elif problem == "symlink":
        file = setup[0] / store.filename(1, first["catalogDigest"])
        original = file.parent.parent / "old-catalog.json"
        file.rename(original)
        file.symlink_to(original)
    folder = setup[0].parent / "failed-package"
    folder.mkdir(mode=0o700)
    args = {
        "context": setup[1]["context"],
        "public_keys": setup[1]["public_keys"],
        "now": setup[1]["now"],
        "base_revision": 0,
        "base_digest": "ABSENT",
        "output": folder,
    }
    args.update(changes)
    with pytest.raises((ValueError, OSError, KeyError)):
        segments.export(setup[0], **args)
    assert not (folder / "manifest.json").exists()


def test_two_real_cli_processes_resume_only_one_final_activation_without_private_keys(
    setup,
):
    first = invoke(setup)
    invoke(setup, first, operation="refresh", now=datetime.now(UTC))
    packet = package(setup, now=datetime.now(UTC))
    env, publishing = cli_env(setup)
    env.pop("FS_GW_CATALOG_KEY_FILE")
    env.pop("FS_GW_CATALOG_KEY_ID")
    dest = receiver(setup)
    command = [
        sys.executable,
        "tools/gw_checkpoint_segments.py",
        "receive",
        "--directory",
        str(dest),
        "--context",
        publishing[6],
        "--manifest",
        str(packet[0] / "manifest.json"),
        "--expected-manifest-digest",
        packet[2]["manifestDigest"],
        "--expected-catalog-id",
        packet[2]["catalogId"],
        "--expected-pin-digest",
        "ABSENT",
        "--initialize",
    ]
    start = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert start.returncode == 2 and not start.stderr
    assert json.loads(start.stdout)["state"] == "RECEIVING"
    command[-1] = "--resume"
    command += ["--part-number", "1", "--part-file", str(packet[0] / "part-00001.bin")]
    staged = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert staged.returncode == 2 and not staged.stderr
    command[-3] = "2"
    command[-1] = str(packet[0] / "part-00002.bin")
    processes = [
        subprocess.Popen(
            command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for _ in range(2)
    ]
    outcomes = [(p.communicate(timeout=30), p.returncode) for p in processes]
    assert sorted(code for _, code in outcomes) == [0, 1]
    assert all(not output[1] for output, _ in outcomes)
    assert (
        len(list(dest.glob("catalog-*.json"))) == 2
        and not (dest / store.PENDING).exists()
    )


def test_cli_missing_manifest_fences_after_operator_anchor_but_not_wrong_cas(setup):
    first = invoke(setup)
    packet = package(setup)
    env, publishing = cli_env(setup)
    dest = receiver(setup)
    command = [
        sys.executable,
        "tools/gw_checkpoint_segments.py",
        "receive",
        "--directory",
        str(dest),
        "--context",
        publishing[6],
        "--manifest",
        str(packet[0] / "missing.json"),
        "--expected-manifest-digest",
        packet[2]["manifestDigest"],
        "--expected-catalog-id",
        first["catalogId"],
        "--expected-pin-digest",
        "f" * 64,
        "--initialize",
    ]
    wrong = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert wrong.returncode == 1 and not (dest / store.PENDING).exists()
    command[-2] = "ABSENT"
    missing = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert (
        missing.returncode == 1
        and not missing.stderr
        and (dest / store.PENDING).exists()
    )


@pytest.mark.parametrize("problem", ["duplicate_json", "recursive", "oversize"])
def test_malformed_manifest_bound_to_confirmed_anchor_still_fences_receiver(
    setup, problem
):
    invoke(setup)
    folder, raw, anchor = package(setup)
    if problem == "duplicate_json":
        raw = raw.replace(b'"version":1', b'"version":1,"version":1', 1)
    elif problem == "recursive":
        raw = b"[" * 2000 + b"]" * 2000
    else:
        raw = b"x" * (segments.MAX_PLAN + 1)
    packet = folder, raw, anchor | {"manifestDigest": store.digest(raw)}
    dest = receiver(setup)
    with pytest.raises((ValueError, RecursionError)):
        receive(setup, dest, packet, None)
    assert (dest / store.PENDING).exists() and not (dest / store.PIN).exists()
    blocked(setup, dest)
