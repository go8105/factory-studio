"""Private filesystem publishing, CAS races and interruption fail closed."""

import base64
import json
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_gw_checkpoint_catalog import add_authority
from test_gw_checkpoint_head import CONTEXT, prepared_head

from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import ENV, read
from fs.gw.operating_contract import canonical


@pytest.fixture
def setup(tmp_path, monkeypatch):
    _, _, _, _, checkpoint_key, head, ctx = prepared_head()
    authority = Ed25519PrivateKey.generate()
    ctx["public_keys"] = add_authority(
        ctx["public_keys"], ctx["workspace_id"], authority
    )
    tmp_path.chmod(0o700)
    folder = tmp_path / "store"
    folder.mkdir(mode=0o700)
    cipher = tmp_path / "checkpoint.enc"
    cipher.write_bytes(b"FSBACK01" + b"x" * 128)
    cipher.chmod(0o600)
    head["payload"]["checkpointDigest"] = store.digest(cipher.read_bytes())

    def save_head(when=None):
        if when is not None:
            head["payload"]["capturedAt"] = when.isoformat()
        head["signature"] = base64.b64encode(
            checkpoint_key.sign(CONTEXT + canonical(head["payload"]))
        ).decode()
        path = tmp_path / "head.json"
        path.write_bytes(canonical(head))
        path.chmod(0o600)
        return path

    context = store.PublishContext(
        workspaceId=ctx["workspace_id"],
        generationId=ctx["generation_id"],
        policy=ctx["policy"],
        codeRevision=ctx["code_revision"],
        dbRevision=ctx["db_revision"],
    )
    kwargs = {
        "context": context,
        "public_keys": ctx["public_keys"],
        "signer": authority,
        "signer_id": "catalog",
        "now": ctx["now"],
        "expected_pin_digest": "ABSENT",
        "head_path": save_head(),
        "checkpoint_path": cipher,
        "initialize": True,
    }
    monkeypatch.delenv(ENV, raising=False)
    monkeypatch.setenv(store.PIN_ENV, str(folder / store.PIN))
    return folder, kwargs, ctx, head, save_head


def invoke(parts, previous=None, **changes):
    folder, kwargs, *_ = parts
    args = dict(kwargs)
    if previous:
        args.update(expected_pin_digest=previous["pinDigest"], initialize=False)
    args.update(changes)
    return store.publish(folder, **args)


def observed(parts, now=None):
    _, _, ctx, *_ = parts
    return read(
        public_keys=ctx["public_keys"],
        workspace_id=ctx["workspace_id"],
        now=now or ctx["now"],
    )


def test_publish_refresh_keep_original_bytes_and_scope(setup):
    first = invoke(setup)
    assert first["result"] == "PASS" and first["ready"] is False
    folder, kwargs, *_ = setup
    files = {p.name: p.read_bytes() for p in folder.glob("catalog-*.json")}
    catalog, sha = observed(setup)
    assert sha == first["catalogDigest"] and catalog.records[0].sequence == 1
    second = invoke(
        setup, first, operation="refresh", now=kwargs["now"] + timedelta(minutes=16)
    )
    assert second["revision"] == 2 and second["sequence"] == 1
    refreshed, _ = observed(setup, kwargs["now"] + timedelta(minutes=16))
    assert refreshed.records == catalog.records
    assert all((folder / name).read_bytes() == raw for name, raw in files.items())
    with pytest.raises(ValueError):
        invoke(
            setup,
            second,
            context=kwargs["context"].model_copy(update={"generation_id": 999}),
        )


@pytest.mark.parametrize(
    "problem",
    [
        "hash",
        "missing",
        "signature",
        "scope",
        "future",
        "old",
        "symlink",
        "permissions",
        "nested_json",
    ],
)
def test_invalid_input_appends_fail_never_old_success(setup, problem):
    first = invoke(setup)
    folder, kwargs, ctx, head, save = setup
    if problem == "hash":
        Path(kwargs["checkpoint_path"]).write_bytes(b"FSBACK01" + b"z" * 128)
    elif problem == "nested_json":
        Path(kwargs["head_path"]).write_bytes(b"[" * 2000 + b"]" * 2000)
    elif problem == "missing":
        kwargs["head_path"] = folder / "absent"
    elif problem == "signature":
        head["signature"] = base64.b64encode(b"z" * 64).decode()
        Path(kwargs["head_path"]).write_bytes(canonical(head))
    elif problem == "scope":
        head["payload"]["scope"]["generationId"] = "999"
        save()
    elif problem == "future":
        save(ctx["now"] + timedelta(seconds=31))
    elif problem == "old":
        save(ctx["now"] - timedelta(days=2))
    elif problem == "symlink":
        link = Path(kwargs["checkpoint_path"]).with_name("link.enc")
        link.symlink_to(kwargs["checkpoint_path"])
        kwargs["checkpoint_path"] = link
    else:
        Path(kwargs["checkpoint_path"]).chmod(0o644)
    failed = invoke(setup, first)
    assert failed["result"] == "FAIL" and failed["sequence"] == 2
    cat, _ = observed(setup)
    assert cat.records[0].result == "FAIL" and cat.records[0].head is None
    refreshed = invoke(setup, failed, operation="refresh")
    assert refreshed["result"] == "FAIL" and refreshed["sequence"] == 2
    assert len(list(folder.glob("catalog-*.json"))) == 3


def test_failed_source_requires_new_capture_and_refresh_cannot_upgrade_context(setup):
    first = invoke(setup)
    folder, kwargs, ctx, _, save = setup
    bad = invoke(setup, first, head_path=folder / "absent")
    retry = invoke(setup, bad)
    assert retry["result"] == "FAIL"
    save(ctx["now"] + timedelta(seconds=1))
    repaired = invoke(setup, retry, now=ctx["now"] + timedelta(seconds=2))
    assert repaired["result"] == "PASS" and repaired["sequence"] == 4
    before, _ = observed(setup, ctx["now"] + timedelta(seconds=2))
    newer_context = kwargs["context"].model_copy(update={"code_revision": "a" * 40})
    invoke(
        setup,
        repaired,
        operation="refresh",
        context=newer_context,
        now=ctx["now"] + timedelta(seconds=3),
    )
    after, _ = observed(setup, ctx["now"] + timedelta(seconds=3))
    assert after.records == before.records


@pytest.mark.parametrize("cut", ["snapshot", "pin", "replace", "directory_sync"])
def test_interruption_blocks_read_then_recovery_appends_partial(
    setup, monkeypatch, cut
):
    first = invoke(setup)
    folder, kwargs, ctx, *_ = setup
    old_files = {p.name: p.read_bytes() for p in folder.glob("catalog-*.json")}
    original_write = store.write_new
    original_replace = store.os.replace
    original_sync = store.os.fsync
    replaced = False

    def broken_write(root, name, raw):
        if (cut == "snapshot" and name.startswith("catalog-")) or (
            cut == "pin" and name.startswith(".pin-")
        ):
            raise OSError("injected interruption")
        return original_write(root, name, raw)

    def broken_replace(*args, **kw):
        nonlocal replaced
        if cut == "replace":
            raise OSError("injected interruption")
        value = original_replace(*args, **kw)
        replaced = True
        return value

    def broken_sync(fd):
        if cut == "directory_sync" and replaced:
            raise OSError("injected interruption")
        return original_sync(fd)

    with monkeypatch.context() as patch:
        patch.setattr(store, "write_new", broken_write)
        patch.setattr(store.os, "replace", broken_replace)
        patch.setattr(store.os, "fsync", broken_sync)
        with pytest.raises(OSError):
            invoke(setup, first)
    with pytest.raises(ValueError):
        observed(setup)
    with pytest.raises(ValueError):
        invoke(setup, first, operation="refresh")
    pin = store.digest((folder / store.PIN).read_bytes())
    recovered = invoke(
        setup, expected_pin_digest=pin, initialize=False, operation="recover-pending"
    )
    assert (
        recovered["result"] == "PARTIAL"
        and recovered["revision"] >= 3
        and recovered["sequence"] >= 3
    )
    assert not (folder / store.PENDING).exists()
    catalog, _ = observed(setup)
    assert catalog.records[0].head is None
    assert all((folder / name).read_bytes() == raw for name, raw in old_files.items())
    assert (
        invoke(setup, recovered)["result"] == "FAIL"
    )  # old HEAD cannot repair interruption
    assert ctx["now"] == kwargs["now"]


def test_interrupted_initial_publish_keeps_identity_and_cannot_reinitialize(
    setup, monkeypatch
):
    folder, *_ = setup
    original = store.write_new
    with monkeypatch.context() as patch:

        def broken(root, name, raw):
            if name.startswith("catalog-"):
                raise OSError("injected")
            return original(root, name, raw)

        patch.setattr(store, "write_new", broken)
        with pytest.raises(OSError):
            invoke(setup)
    intended = json.loads((folder / store.PENDING).read_bytes())["catalogId"]
    with pytest.raises(ValueError):
        invoke(setup)
    recovered = invoke(setup, operation="recover-pending", initialize=False)
    assert recovered["catalogId"] == intended and recovered["result"] == "PARTIAL"


def test_old_pin_cas_wrong_key_and_unscoped_authority_do_not_advance(setup):
    first = invoke(setup)
    folder, kwargs, *_ = setup
    for changes, error in [
        ({}, ValueError),
        ({"signer": Ed25519PrivateKey.generate()}, InvalidSignature),
        ({"public_keys": dict(kwargs["public_keys"])}, ValueError),
    ]:
        with pytest.raises(error):
            invoke(setup, **changes)
    assert len(list(folder.glob("catalog-*.json"))) == 1
    assert not (folder / store.PENDING).exists()
    assert store.digest((folder / store.PIN).read_bytes()) == first["pinDigest"]


def test_rollback_orphan_corrupt_pin_and_ambiguous_configuration_block(
    setup, monkeypatch
):
    first = invoke(setup)
    folder, *_ = setup
    old_pin = (folder / store.PIN).read_bytes()
    invoke(setup, first)
    (folder / store.PIN).write_bytes(old_pin)
    with pytest.raises(ValueError):
        observed(setup)
    monkeypatch.setenv(ENV, "{}")
    with pytest.raises(ValueError):
        observed(setup)
    monkeypatch.delenv(ENV)
    (folder / store.PIN).write_bytes(b"{}")
    with pytest.raises(ValueError):
        observed(setup)


@pytest.mark.parametrize("object_name", [store.PIN, store.PENDING, store.LOCK])
def test_control_file_symlink_rejected(setup, object_name):
    folder, *_ = setup
    target = folder.parent / "foreign"
    target.write_bytes(b"{}")
    target.chmod(0o600)
    (folder / object_name).symlink_to(target)
    with pytest.raises((ValueError, OSError)):
        invoke(setup)
    assert target.read_bytes() == b"{}"


def cli_env(parts):
    folder, kwargs, ctx, *_ = parts
    public = kwargs["public_keys"]
    uses = {
        "runner-1": ["BACKUP", "RESTORE"],
        "checkpoint": ["CHECKPOINT"],
        "collector": ["ACCEPTANCE_RECONCILIATION"],
        "rechecker": ["RESTORE_RECHECK"],
        "catalog": ["CHECKPOINT_CATALOG"],
    }
    scopes = {
        "version": 1,
        "keys": {
            k: {"workspaceIds": [str(ctx["workspace_id"])], "purposes": uses[k]}
            for k in public
        },
    }
    key = folder.parent / "authority.key"
    key.write_bytes(kwargs["signer"].private_bytes_raw())
    key.chmod(0o600)
    context = folder.parent / "context.json"
    context.write_bytes(canonical(kwargs["context"].model_dump(by_alias=True)))
    context.chmod(0o600)
    env = os.environ | {
        "FS_GW_EVIDENCE_PUBLIC_KEYS": json.dumps(
            {k: base64.b64encode(v).decode() for k, v in public.items()}
        ),
        "FS_GW_EVIDENCE_KEY_SCOPES": json.dumps(scopes),
        "FS_SECURITY_MODE": "COMPANY",
        "FS_GW_CATALOG_KEY_FILE": str(key),
        "FS_GW_CATALOG_KEY_ID": "catalog",
    }
    from gw_catalog_trust_helpers import approve_subprocess

    from fs.gw.catalog_trust_store import ENV as TRUST_ENV

    trust_directory = folder.parent / "trust"
    trust_directory.mkdir(mode=0o700, exist_ok=True)
    env[TRUST_ENV] = str(trust_directory)
    approve_subprocess(env)
    command = [
        sys.executable,
        "tools/gw_checkpoint_catalog.py",
        "publish",
        "--directory",
        str(folder),
        "--context",
        str(context),
        "--head",
        str(kwargs["head_path"]),
        "--checkpoint",
        str(kwargs["checkpoint_path"]),
    ]
    return env, command


def test_two_real_cli_processes_same_cas_exactly_one_wins(setup):
    # The fixture clock is synthetic; refresh does not need a current source HEAD.
    first = invoke(setup)
    env, command = cli_env(setup)
    command[2] = "refresh"
    command = command[:7] + ["--expected-pin-digest", first["pinDigest"]]
    processes = [
        subprocess.Popen(
            command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        for _ in range(2)
    ]
    outcomes = [(p.communicate(timeout=30), p.returncode) for p in processes]
    assert sorted(code for _, code in outcomes) == [0, 1]
    folder, *_ = setup
    assert len(list(folder.glob("catalog-*.json"))) == 2
    assert not (folder / store.PENDING).exists()
    winner = next(json.loads(output[0]) for output, code in outcomes if code == 0)
    assert (
        winner["revision"] == 2 and winner["sequence"] == 1 and winner["ready"] is False
    )


def test_killed_source_validation_leaves_pending_before_any_new_success(
    setup, monkeypatch
):
    first = invoke(setup)
    folder, *_ = setup
    with monkeypatch.context() as patch:

        def killed(*args, **kwargs):
            raise SystemExit(137)

        patch.setattr(store, "load_private", killed)
        with pytest.raises(SystemExit):
            invoke(setup, first)
    assert (folder / store.PENDING).exists()
    assert len(list(folder.glob("catalog-*.json"))) == 1
    with pytest.raises(ValueError):
        observed(setup)


def test_partial_snapshot_is_preserved_by_recovery(setup, monkeypatch):
    first = invoke(setup)
    folder, *_ = setup
    original = store.write_new
    with monkeypatch.context() as patch:

        def partial(root, name, raw):
            if name.startswith("catalog-"):
                original(root, name, raw[:8])
                raise OSError("partial write")
            return original(root, name, raw)

        patch.setattr(store, "write_new", partial)
        with pytest.raises(OSError):
            invoke(setup, first)
    truncated = next(p for p in folder.glob("catalog-*.json") if p.stat().st_size == 8)
    recovered = invoke(setup, first, operation="recover-pending")
    assert recovered["result"] == "PARTIAL" and recovered["revision"] == 3
    assert truncated.read_bytes() == b'{"envelo'
    assert observed(setup)[0].records[0].result == "PARTIAL"


@pytest.mark.parametrize(
    "problem",
    ["directory", "pin", "snapshot", "hardlink", "empty_env", "duplicate_json"],
)
def test_managed_reader_rejects_private_file_and_configuration_violations(
    setup, monkeypatch, problem
):
    invoke(setup)
    folder, *_ = setup
    if problem == "directory":
        folder.chmod(0o755)
    elif problem == "pin":
        (folder / store.PIN).chmod(0o644)
    elif problem == "snapshot":
        next(folder.glob("catalog-*.json")).chmod(0o644)
    elif problem == "hardlink":
        os.link(folder / store.PIN, folder.parent / "another-pin")
    elif problem == "empty_env":
        monkeypatch.setenv(store.PIN_ENV, "")
    else:
        (folder / store.PIN).write_bytes(b'{"version":1,"version":1}')
    with pytest.raises(ValueError):
        observed(setup)


def test_freshness_not_reset_by_read_and_history_not_deleted(setup):
    first = invoke(setup)
    folder, kwargs, *_ = setup
    with pytest.raises(ValueError):
        observed(setup, kwargs["now"] + timedelta(minutes=15, seconds=1))
    invoke(setup, first, operation="refresh", now=kwargs["now"] + timedelta(minutes=16))
    assert len(list(folder.glob("catalog-*.json"))) == 2
    assert observed(setup, kwargs["now"] + timedelta(minutes=16))[0].revision == 2


def test_pin_replacement_during_reader_never_pairs_old_catalog_with_new_digest(
    setup, monkeypatch
):
    first = invoke(setup)
    original = store.read_fd
    count = 0
    with monkeypatch.context() as patch:

        def raced(root, name, limit=store.MAX_BYTES):
            nonlocal count
            if name == store.PIN:
                count += 1
                if count == 3:
                    # A cooperative writer completes between the reader's two checks.
                    patch.setattr(store, "read_fd", original)
                    invoke(setup, first, operation="refresh")
            return original(root, name, limit)

        patch.setattr(store, "read_fd", raced)
        with pytest.raises(ValueError):
            observed(setup)
    assert observed(setup)[0].revision == 2


def test_initialization_flag_and_source_capture_regression_rejected(setup):
    first = invoke(setup)
    _, _, ctx, _, save = setup
    with pytest.raises(ValueError):
        invoke(setup, first, initialize=True)
    save(ctx["now"] - timedelta(minutes=30))
    assert invoke(setup, first)["result"] == "FAIL"


def test_catalog_authority_revocation_blocks_managed_read_without_old_fallback(setup):
    invoke(setup)
    folder, kwargs, ctx, *_ = setup
    from fs.gw.evidence_trust import EvidenceTrust

    revoked = EvidenceTrust(
        {k: v for k, v in kwargs["public_keys"].items() if k != "catalog"}, {}
    )
    with pytest.raises(ValueError):
        read(public_keys=revoked, workspace_id=ctx["workspace_id"], now=ctx["now"])
    assert len(list(folder.glob("catalog-*.json"))) == 1


def test_cli_status_without_private_key_reports_orphan_as_blocked(setup):
    invoke(setup)
    folder, *_ = setup
    env, command = cli_env(setup)
    del env["FS_GW_CATALOG_KEY_FILE"]
    command[2] = "status"
    command = command[:7]
    healthy = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert healthy.returncode == 0 and json.loads(healthy.stdout)["ready"] is False
    (
        folder / store.PIN
    ).unlink()  # Test corruption only: never a production recovery step.
    blocked = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert blocked.returncode == 2
    assert json.loads(blocked.stdout)["highestStoredRevision"] == 1


def test_recursive_context_cli_is_safe_error_without_trace_or_private_output(setup):
    env, command = cli_env(setup)
    command[2] = "status"
    command = command[:7]
    Path(command[6]).write_bytes(b"[" * 2000 + b"]" * 2000)
    blocked = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert blocked.returncode == 1 and not blocked.stderr
    assert b"Traceback" not in blocked.stdout and b"[" * 20 not in blocked.stdout
