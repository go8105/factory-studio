"""An externally confirmed latest hash, every original and retained revocation fence recovery."""

# ruff: noqa: F401,F811
import json
import os
import subprocess
import sys
from copy import deepcopy
from uuid import uuid4

import pytest
from test_gw_catalog_store import setup
from test_gw_catalog_trust_store import environment, expanded, initialize

from fs.gw import catalog_store as store
from fs.gw import catalog_trust_store as floor
from fs.gw import catalog_trust_transfer as transfer
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical


def folder(parent, name):
    path = parent / name
    path.mkdir(mode=0o700)
    return path


def prepared(parts, patch):
    origin, sha, keys = initialize(parts, patch)
    first = floor.inspect(origin)
    keys = expanded(keys)
    _, sha = floor.commit(origin, keys, expected_digest=sha)
    head, sha = floor.revoke(
        origin, workspace_id="10", key_id="catalog", expected_digest=sha
    )
    anchor = transfer._anchor(head, sha)
    package = folder(origin.parent, "package")
    result = transfer.export(origin, package, anchor=anchor)
    return origin, package, anchor, result["manifestDigest"], keys, first


def receive(values, dest, **changes):
    origin, package, anchor, manifest, *_ = values
    return transfer.receive(
        package,
        dest,
        anchor=anchor,
        expected_manifest_digest=manifest,
        **({"origin": origin} | changes),
    )


@pytest.mark.parametrize(
    "damage",
    [
        "new-host",
        "none",
        "middle-missing",
        "last-missing",
        "empty",
        "truncated",
        "changed",
        "head-missing",
        "head-truncated",
        "pending-truncated",
    ],
)
def test_reconstructs_exact_latest_originals_preserves_revocation_and_damaged_source(
    setup, monkeypatch, damage
):
    values = prepared(setup, monkeypatch)
    origin, package, anchor, _manifest, keys, *_ = values
    latest = origin / transfer.filename(anchor.revision, anchor.digest)
    if damage == "middle-missing":
        min(origin.glob("trust-*.json")).unlink()
    elif damage == "last-missing":
        latest.unlink()
    elif damage == "empty":
        latest.write_bytes(b"")
    elif damage == "truncated":
        latest.write_bytes(latest.read_bytes()[:8])
    elif damage == "changed":
        latest.write_bytes(b"x" * latest.stat().st_size)
    elif damage == "head-missing":
        (origin / floor.HEAD).unlink()
    elif damage == "head-truncated":
        (origin / floor.HEAD).write_bytes(b'{"vers')
    elif damage == "pending-truncated":
        (origin / floor.PENDING).write_bytes(b'{"vers')
        (origin / floor.PENDING).chmod(0o600)
    originals = {p.name: p.read_bytes() for p in origin.iterdir()}
    dest = folder(origin.parent, "recovered")
    args = {"origin": None, "new_host": True} if damage == "new-host" else {}
    report = receive(values, dest, **args)
    assert report["state"] == "COMPLETE" and report["ready"] is False
    head, sha = floor.inspect(dest)
    assert sha == anchor.digest and head.authorities[0].state == "REVOKED"
    assert originals == {p.name: p.read_bytes() for p in origin.iterdir()}
    assert not (dest / transfer.RECEIVING).exists()
    for part in json.loads((package / transfer.MANIFEST).read_bytes())["files"]:
        name = transfer.filename(part["revision"], part["digest"])
        assert (package / name).read_bytes() == (dest / name).read_bytes()
    monkeypatch.setenv(floor.ENV, str(dest))
    environment(
        monkeypatch, keys
    )  # Old valid ACTIVE settings cannot undo restored REVOKED.
    with pytest.raises(ValueError):
        from_environment()
    with pytest.raises(ValueError):
        floor.commit(dest, keys, expected_digest=sha)
    assert receive(values, dest, resume=True, **args) == report
    assert (
        transfer.export(dest, folder(origin.parent, "again"), anchor=anchor)["digest"]
        == sha
    )


@pytest.mark.parametrize(
    "damage",
    [
        "wrong-manifest",
        "wrong-ledger",
        "wrong-revision",
        "wrong-anchor",
        "missing",
        "extra",
        "tamper",
        "duplicate-json",
        "bool-version",
        "manifest-size",
        "path-injection",
        "reorder",
        "file-size",
        "transition",
    ],
)
def test_confirmed_anchor_and_every_package_byte_are_required_before_activation(
    setup, monkeypatch, damage
):
    values = prepared(setup, monkeypatch)
    origin, package, anchor, digest, *_ = values
    value = json.loads((package / transfer.MANIFEST).read_bytes())
    if damage == "wrong-manifest":
        digest = "0" * 64
    elif damage == "wrong-ledger":
        anchor = anchor.model_copy(update={"ledger_id": str(uuid4())})
    elif damage == "wrong-revision":
        anchor = anchor.model_copy(update={"revision": 2})
    elif damage == "wrong-anchor":
        anchor = anchor.model_copy(update={"digest": "0" * 64})
    elif damage == "missing":
        min(package.glob("trust-*.json")).unlink()
    elif damage == "extra":
        p = package / "extra.json"
        p.write_bytes(b"x")
        p.chmod(0o600)
    elif damage == "tamper":
        p = min(package.glob("trust-*.json"))
        p.write_bytes(p.read_bytes() + b" ")
    elif damage == "duplicate-json":
        (package / transfer.MANIFEST).write_bytes(b'{"version":1,"version":1}')
        digest = store.digest((package / transfer.MANIFEST).read_bytes())
    elif damage == "manifest-size":
        (package / transfer.MANIFEST).write_bytes(b"x" * (transfer.MAX_MANIFEST + 1))
    else:
        if damage == "bool-version":
            value["version"] = True
        elif damage == "path-injection":
            value["files"][0]["file"] = "../../outside"
        elif damage == "reorder":
            value["files"].reverse()
        elif damage == "file-size":
            value["files"][0]["size"] += 1
        else:
            # A consistently re-hashed chain still cannot undo REVOKED -> ACTIVE.
            previous = "ABSENT"
            for part in value["files"]:
                old = package / transfer.filename(part["revision"], part["digest"])
                record = json.loads(old.read_bytes())
                record["previousDigest"] = previous
                record["authorities"][0]["state"] = (
                    "REVOKED" if part["revision"] == 1 else "ACTIVE"
                )
                raw = canonical(record)
                sha = store.digest(raw)
                old.unlink()
                new = package / transfer.filename(part["revision"], sha)
                new.write_bytes(raw)
                new.chmod(0o600)
                part.update(digest=sha, size=len(raw))
                previous = sha
            value["anchor"]["digest"] = previous
            anchor = anchor.model_copy(update={"digest": previous})
        raw = canonical(value)
        (package / transfer.MANIFEST).write_bytes(raw)
        digest = store.digest(raw)
    dest = folder(origin.parent, "failed-recovery")
    # New-host mode isolates package validation from conflicting retained local claims.
    with pytest.raises((ValueError, OSError)):
        transfer.receive(
            package, dest, anchor=anchor, expected_manifest_digest=digest, new_host=True
        )
    assert (dest / transfer.RECEIVING).exists()
    assert not (dest / floor.HEAD).exists()
    with pytest.raises((ValueError, OSError)):
        floor.inspect(dest)
    with pytest.raises((ValueError, OSError)):
        floor.resume(dest, expected_digest=anchor.digest)


@pytest.mark.parametrize(
    "claim",
    [
        "newer-record",
        "fork-name",
        "newer-head",
        "other-ledger",
        "newer-pending",
        "future-version",
        "unknown-file",
        "duplicate-revision",
    ],
)
def test_retained_newer_or_conflicting_claims_are_never_replaced_by_old_backup(
    setup, monkeypatch, claim
):
    values = prepared(setup, monkeypatch)
    origin, _package, anchor, *_ = values
    if claim in {"newer-record", "fork-name", "duplicate-revision"}:
        revision = anchor.revision + 1 if claim == "newer-record" else 1
        if claim == "fork-name":
            min(origin.glob("trust-*.json")).unlink()
        p = origin / transfer.filename(revision, "f" * 64)
        p.write_bytes(b"unfinished")
    elif claim == "unknown-file":
        p = origin / "unknown"
        p.write_bytes(b"x")
    else:
        p = origin / (floor.PENDING if claim == "newer-pending" else floor.HEAD)
        value = anchor.model_dump(by_alias=True)
        if claim in {"newer-head", "newer-pending"}:
            value["revision"] += 1
        elif claim == "other-ledger":
            value["ledgerId"] = str(uuid4())
        else:
            value["version"] = 2
        p.write_bytes(canonical(value))
    p.chmod(0o600)
    before = {p.name: p.read_bytes() for p in origin.iterdir()}
    with pytest.raises(ValueError):
        receive(values, folder(origin.parent, "rejected"))
    assert before == {p.name: p.read_bytes() for p in origin.iterdir()}


@pytest.mark.parametrize(
    "cut",
    [
        "record-before",
        "record-partial",
        "record-after",
        "receipt-before",
        "receipt-partial",
        "head-before",
        "head-partial",
        "head-after",
        "clear-fence",
        "after-clear",
    ],
)
def test_interruption_never_activates_previous_state_and_resumes_only_exact_complete_files(
    setup, monkeypatch, cut
):
    values = prepared(setup, monkeypatch)
    origin, _package, anchor, *_ = values
    dest = folder(origin.parent, "interrupted")
    write = store.write_new
    activate = floor._activate
    unlink = os.unlink

    def broken_write(root, name, raw):
        is_record = bool(floor.NAME.fullmatch(name))
        selected = (
            (is_record and cut.startswith("record-"))
            or (name == transfer.RECEIPT and cut.startswith("receipt-"))
            or (name == floor.PENDING and cut == "head-partial")
        )
        if selected:
            if cut.endswith("partial"):
                write(root, name, raw[:8])
            elif cut.endswith("after"):
                write(root, name, raw)
            raise OSError("injected")
        return write(root, name, raw)

    def broken_activate(*args):
        if cut == "head-before":
            raise OSError("injected")
        activate(*args)
        if cut == "head-after":
            raise OSError("injected")

    def broken_unlink(name, **kw):
        if name == transfer.RECEIVING and cut == "clear-fence":
            raise OSError("injected")
        unlink(name, **kw)
        if name == transfer.RECEIVING and cut == "after-clear":
            raise OSError("injected")

    with monkeypatch.context() as fault:
        fault.setattr(store, "write_new", broken_write)
        fault.setattr(floor, "_activate", broken_activate)
        fault.setattr(os, "unlink", broken_unlink)
        with pytest.raises(OSError):
            receive(values, dest)
    if cut != "after-clear":
        with pytest.raises((ValueError, OSError)):
            floor.inspect(dest)
    if cut.endswith("partial"):
        before = {p.name: p.read_bytes() for p in dest.iterdir()}
        with pytest.raises((ValueError, OSError)):
            receive(values, dest, resume=True)
        assert before == {p.name: p.read_bytes() for p in dest.iterdir()}
        assert (
            receive(values, folder(origin.parent, "replacement"))["digest"]
            == anchor.digest
        )
    else:
        assert receive(values, dest, resume=True)["digest"] == anchor.digest
        assert floor.inspect(dest)[1] == anchor.digest


def test_real_cli_requires_pins_and_explicit_new_host_and_never_installs_environment(
    setup, monkeypatch
):
    origin, package, anchor, manifest, *_ = prepared(setup, monkeypatch)
    dest = folder(origin.parent, "cli-recovered")
    command = [
        sys.executable,
        "tools/gw_catalog_trust_transfer.py",
        "receive",
        "--directory",
        str(package),
        "--output",
        str(dest),
        "--expected-ledger-id",
        anchor.ledger_id,
        "--expected-revision",
        str(anchor.revision),
        "--expected-digest",
        anchor.digest,
        "--expected-manifest-digest",
        manifest,
    ]
    process = subprocess.run(command, capture_output=True, timeout=30, check=False)
    assert process.returncode == 1 and not process.stderr
    command += ["--new-host"]
    process = subprocess.run(command, capture_output=True, timeout=30, check=False)
    assert process.returncode == 0 and not process.stderr
    assert json.loads(process.stdout)["ready"] is False
    assert os.environ[floor.ENV] == str(origin)
    assert floor.inspect(dest)[1] == anchor.digest


@pytest.mark.parametrize(
    "change",
    ["manifest", "origin", "origin-bytes", "target-newer-head", "target-other-head"],
)
def test_pending_recovery_is_bound_to_same_plan_origin_and_current_claims(
    setup, monkeypatch, change
):
    values = prepared(setup, monkeypatch)
    origin, package, anchor, _digest, *_ = values
    dest = folder(origin.parent, "pending")
    original = transfer._manifest
    with monkeypatch.context() as fault:
        fault.setattr(
            transfer,
            "_manifest",
            lambda *args: (_ for _ in ()).throw(OSError("injected")),
        )
        with pytest.raises(OSError):
            receive(values, dest)
    assert transfer._manifest is original
    overrides = {"resume": True}
    if change == "manifest":
        overrides["expected_manifest_digest"] = "f" * 64
    elif change == "origin":
        overrides.update(origin=None, new_host=True)
    elif change == "origin-bytes":
        p = max(origin.glob("trust-*.json"))
        p.write_bytes(p.read_bytes()[:8])
    else:
        value = anchor.model_dump(by_alias=True)
        if change == "target-newer-head":
            value["revision"] += 1
        else:
            value["ledgerId"] = str(uuid4())
        p = dest / floor.HEAD
        p.write_bytes(canonical(value))
        p.chmod(0o600)
    before = {p.name: p.read_bytes() for p in dest.iterdir()}
    if change == "manifest":
        with pytest.raises(ValueError):
            transfer.receive(package, dest, anchor=anchor, origin=origin, **overrides)
    else:
        with pytest.raises(ValueError):
            receive(values, dest, **overrides)
    assert before == {p.name: p.read_bytes() for p in dest.iterdir()}


def test_receipt_is_checked_on_every_read_and_old_completed_retry_cannot_hide_advance(
    setup, monkeypatch
):
    values = prepared(setup, monkeypatch)
    origin, _, anchor, *_ = values
    dest = folder(origin.parent, "receipt-check")
    receive(values, dest)
    original = (dest / transfer.RECEIPT).read_bytes()
    receipt = json.loads(original)
    receipt["anchor"]["digest"] = "f" * 64
    (dest / transfer.RECEIPT).write_bytes(canonical(receipt))
    with pytest.raises((OSError, ValueError)):
        floor.inspect(dest)
    (dest / transfer.RECEIPT).write_bytes(original)
    # Revocation of another recorded key is a new current state; old export cannot be retried as current.
    floor.revoke(dest, workspace_id="10", key_id="next", expected_digest=anchor.digest)
    with pytest.raises(ValueError):
        receive(values, dest, resume=True)
    assert floor.inspect(dest)[0].revision == anchor.revision + 1


@pytest.mark.parametrize(
    "issue",
    [
        "bad-pin",
        "not-empty",
        "nested",
        "source-partial",
        "file-symlink",
        "public-file",
        "write-cut",
    ],
)
def test_export_never_publishes_manifest_for_unconfirmed_or_incomplete_source(
    setup, monkeypatch, issue
):
    origin, _package, anchor, *_ = prepared(setup, monkeypatch)
    output = folder(origin.parent, "new-export")
    if issue == "bad-pin":
        anchor = anchor.model_copy(update={"digest": "f" * 64})
    elif issue == "not-empty":
        p = output / "keep"
        p.write_bytes(b"x")
        p.chmod(0o600)
    elif issue == "nested":
        output = folder(origin, "nested")
    elif issue == "source-partial":
        max(origin.glob("trust-*.json")).write_bytes(b"partial")
    elif issue == "file-symlink":
        p = max(origin.glob("trust-*.json"))
        old = origin.parent / "original"
        p.rename(old)
        p.symlink_to(old)
    elif issue == "public-file":
        max(origin.glob("trust-*.json")).chmod(0o644)
    else:
        original_write = store.write_new

        def cut(root, name, raw):
            if floor.NAME.fullmatch(name):
                original_write(root, name, raw[:8])
                raise OSError("injected")
            return original_write(root, name, raw)

        monkeypatch.setattr(store, "write_new", cut)
    with pytest.raises((OSError, ValueError)):
        transfer.export(origin, output, anchor=anchor)
    assert not (output / transfer.MANIFEST).exists()


def test_two_actual_receiver_processes_one_new_activation_and_public_only_export(
    setup, monkeypatch
):
    origin, _, anchor, *_ = prepared(setup, monkeypatch)
    package = folder(origin.parent, "cli-export")
    monkeypatch.delenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS"
    )  # No current grant config/private keys required.
    anchor_args = [
        "--expected-ledger-id",
        anchor.ledger_id,
        "--expected-revision",
        str(anchor.revision),
        "--expected-digest",
        anchor.digest,
    ]
    exported = subprocess.run(
        [
            sys.executable,
            "tools/gw_catalog_trust_transfer.py",
            "export",
            "--directory",
            str(origin),
            "--output",
            str(package),
            *anchor_args,
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert exported.returncode == 0 and not exported.stderr
    digest = json.loads(exported.stdout)["manifestDigest"]
    dest = folder(origin.parent, "raced")
    command = [
        sys.executable,
        "tools/gw_catalog_trust_transfer.py",
        "receive",
        "--directory",
        str(package),
        "--output",
        str(dest),
        *anchor_args,
        "--expected-manifest-digest",
        digest,
        "--existing-directory",
        str(origin),
    ]
    processes = [
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    outcomes = [(p.communicate(timeout=30), p.returncode) for p in processes]
    assert sorted(code for _, code in outcomes) == [0, 1]
    assert all(not streams[1] for streams, _ in outcomes)
    assert floor.inspect(dest)[1] == anchor.digest
