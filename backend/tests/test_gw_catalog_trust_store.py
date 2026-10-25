"""Retained trust history fences old configuration, revocation, forks and interrupted writes."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
from copy import deepcopy

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_gw_catalog_key_chain import Rotations
from test_gw_catalog_store import setup

from fs.gw import catalog_key_handover as handover
from fs.gw import catalog_store as store
from fs.gw import catalog_trust_store as floor
from fs.gw.evidence_trust import EvidenceTrust, from_environment
from fs.gw.operating_contract import canonical


def environment(patch, keys, config=None):
    patch.setenv("FS_SECURITY_MODE", "COMPANY")
    patch.setenv(
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        json.dumps({k: base64.b64encode(v).decode() for k, v in keys.items()}),
    )
    patch.setenv(
        "FS_GW_EVIDENCE_KEY_SCOPES",
        json.dumps(
            {
                "version": 1,
                "keys": {
                    k: {"workspaceIds": sorted(companies), "purposes": sorted(uses)}
                    for k, (companies, uses) in keys.scopes.items()
                },
            }
        ),
    )
    if config and config["keys"]:
        patch.setenv(handover.ENV, json.dumps(config))
    else:
        patch.delenv(handover.ENV, raising=False)


def initialize(parts, patch):
    path = parts[0].parent / "durable-trust"
    path.mkdir(mode=0o700)
    patch.setenv(floor.ENV, str(path))
    keys = parts[1]["public_keys"]
    environment(patch, keys)
    head, sha = floor.commit(path, keys, expected_digest="ABSENT", initialize=True)
    assert head.revision == 1
    return path, sha, keys


def expanded(keys):
    new = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    return EvidenceTrust(
        dict(keys) | {"next": new},
        dict(keys.scopes)
        | {"next": (frozenset(["10"]), frozenset(["CHECKPOINT_CATALOG"]))},
    )


def test_three_rotations_cannot_restore_old_settings_or_old_approval(
    setup, monkeypatch
):
    rotations = Rotations(setup, monkeypatch)
    path, sha, _ = initialize(setup, monkeypatch)
    old_keys, old_config = None, None
    for successor in ["B", "C", "D"]:
        rotations.prepare(successor)
        keys = rotations.keys()
        _, sha = floor.commit(path, keys, expected_digest=sha)
        environment(monkeypatch, keys, rotations.config)
        assert from_environment().scoped
        if old_keys is None:
            old_keys, old_config = keys, deepcopy(rotations.config)
        keys = rotations.commit()
        _, sha = floor.commit(path, keys, expected_digest=sha)
        environment(monkeypatch, keys, rotations.config)
        assert from_environment().catalog_lifecycle is not None
    environment(monkeypatch, old_keys, old_config)
    with pytest.raises(ValueError, match="trust unavailable"):
        from_environment()
    with pytest.raises(ValueError):
        floor.commit(path, old_keys, expected_digest=sha)
    # Current B revocation is durable even though A's current chain now becomes invalid.
    _, revoked_sha = floor.revoke(
        path, workspace_id="10", key_id="B", expected_digest=sha
    )
    environment(monkeypatch, keys, rotations.config)
    with pytest.raises(ValueError):
        from_environment()
    with pytest.raises(ValueError, match="revocation cannot"):
        floor.commit(path, keys, expected_digest=revoked_sha)
    assert floor.inspect(path)[1] == revoked_sha


@pytest.mark.parametrize(
    "change",
    [
        "remove-path",
        "empty-store",
        "remove-lifecycle",
        "reactivate",
        "alias",
        "reuse-id",
        "other-purpose",
    ],
)
def test_recorded_revocation_is_not_restored_by_configuration_changes(
    setup, monkeypatch, change
):
    path, sha, keys = initialize(setup, monkeypatch)
    _, sha = floor.revoke(
        path, workspace_id="10", key_id="catalog", expected_digest=sha
    )
    public = base64.b64encode(keys["catalog"]).decode()
    config = {
        "version": 1,
        "keys": [
            {
                "version": 1,
                "workspaceId": "10",
                "keyId": "catalog",
                "publicKey": public,
                "state": "REVOKED",
                "approvals": [],
            }
        ],
    }
    current = handover.bind(keys, json.dumps(config))
    environment(monkeypatch, current, config)
    assert (
        from_environment().catalog_lifecycle.records["10", "catalog"].state == "REVOKED"
    )
    if change == "remove-path":
        monkeypatch.delenv(floor.ENV)
    elif change == "empty-store":
        empty = path.parent / "empty-trust"
        empty.mkdir(mode=0o700)
        monkeypatch.setenv(floor.ENV, str(empty))
    elif change in {"remove-lifecycle", "reactivate"}:
        monkeypatch.delenv(handover.ENV)
    else:
        public_keys = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        scopes = json.loads(os.environ["FS_GW_EVIDENCE_KEY_SCOPES"])
        if change == "alias":
            public_keys["alias"] = public_keys.pop("catalog")
            scopes["keys"]["alias"] = scopes["keys"].pop("catalog")
        elif change == "reuse-id":
            public_keys["catalog"] = base64.b64encode(
                Ed25519PrivateKey.generate().public_key().public_bytes_raw()
            ).decode()
        else:
            scopes["keys"]["catalog"]["purposes"] = ["BACKUP"]
        monkeypatch.setenv("FS_GW_EVIDENCE_PUBLIC_KEYS", json.dumps(public_keys))
        monkeypatch.setenv("FS_GW_EVIDENCE_KEY_SCOPES", json.dumps(scopes))
        if change != "other-purpose":
            monkeypatch.delenv(handover.ENV)
    with pytest.raises(ValueError, match="trust unavailable"):
        from_environment()
    assert floor.inspect(path)[1] == sha


@pytest.mark.parametrize(
    "damage",
    [
        "head-missing",
        "head-rollback",
        "tail-missing",
        "middle-missing",
        "changed",
        "symlink",
        "hardlink",
        "permissions",
        "directory",
        "unexpected",
        "duplicate-json",
        "boolean-version",
    ],
)
def test_retained_head_and_all_originals_are_required(setup, monkeypatch, damage):
    path, sha, keys = initialize(setup, monkeypatch)
    old_head = (path / floor.HEAD).read_bytes()
    next_keys = expanded(keys)
    floor.commit(path, next_keys, expected_digest=sha)
    files = sorted(path.glob("trust-*.json"))
    if damage == "head-missing":
        (path / floor.HEAD).unlink()
    elif damage == "head-rollback":
        (path / floor.HEAD).write_bytes(old_head)
    elif damage == "tail-missing":
        files[-1].unlink()
    elif damage == "middle-missing":
        files[0].unlink()
    elif damage == "changed":
        files[0].write_bytes(files[0].read_bytes() + b" ")
    elif damage == "symlink":
        original = path.parent / "original"
        files[-1].rename(original)
        files[-1].symlink_to(original)
    elif damage == "hardlink":
        os.link(files[-1], path.parent / "linked")
    elif damage == "permissions":
        files[-1].chmod(0o644)
    elif damage == "directory":
        path.chmod(0o755)
    elif damage == "unexpected":
        (path / "unknown").write_bytes(b"x")
    elif damage == "duplicate-json":
        files[-1].write_bytes(b'{"version":1,"version":1}')
    else:
        value = json.loads(files[-1].read_bytes())
        value["version"] = True
        files[-1].write_bytes(canonical(value))
    with pytest.raises((OSError, ValueError)):
        floor.check(next_keys, path)
    with pytest.raises((OSError, ValueError)):
        floor.commit(path, next_keys, expected_digest="ABSENT", initialize=True)


@pytest.mark.parametrize(
    "cut",
    [
        "record-partial",
        "record-complete",
        "head-partial",
        "head-complete",
        "replace",
        "after-replace",
    ],
)
def test_interrupted_append_never_reads_previous_success_and_exact_resume(
    setup, monkeypatch, cut
):
    path, sha, keys = initialize(setup, monkeypatch)
    new = expanded(keys)
    write = store.write_new
    activate = floor._activate
    replace = os.replace

    def broken_write(root, name, raw):
        if cut == "record-partial" and name.startswith("trust-"):
            write(root, name, raw[:9])
            raise OSError("injected")
        if cut == "record-complete" and name.startswith("trust-"):
            write(root, name, raw)
            raise OSError("injected")
        if cut == "head-partial" and name == floor.PENDING:
            write(root, name, raw[:9])
            raise OSError("injected")
        if cut == "head-complete" and name == floor.PENDING:
            write(root, name, raw)
            raise OSError("injected")
        return write(root, name, raw)

    def broken_replace(*args, **kw):
        if cut == "replace":
            raise OSError("injected")
        return replace(*args, **kw)

    def broken_activate(*args):
        activate(*args)
        if cut == "after-replace":
            raise OSError("injected")

    with monkeypatch.context() as fault:
        fault.setattr(store, "write_new", broken_write)
        fault.setattr(os, "replace", broken_replace)
        fault.setattr(floor, "_activate", broken_activate)
        with pytest.raises(OSError):
            floor.commit(path, new, expected_digest=sha)
    with pytest.raises((OSError, ValueError)):
        floor.check(keys, path)
    if cut in {"record-partial", "head-partial"}:
        with pytest.raises((OSError, ValueError)):
            floor.resume(
                path,
                expected_digest=max(path.glob("trust-*.json")).stem.split("-")[-1],
            )
    else:
        target = max(path.glob("trust-*.json")).stem.split("-")[-1]
        with pytest.raises(ValueError):
            floor.resume(path, expected_digest=sha)
        head, result = floor.resume(path, expected_digest=target)
        assert result == target and head.revision == 2
        assert floor.check(new, path) is new
        assert not (path / floor.PENDING).exists()


def test_two_cli_processes_cannot_commit_same_cas_twice(setup, monkeypatch):
    path, sha, keys = initialize(setup, monkeypatch)
    environment(monkeypatch, expanded(keys))
    command = [
        sys.executable,
        "tools/gw_catalog_trust.py",
        "advance",
        "--expected-digest",
        sha,
    ]
    processes = [
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for _ in range(2)
    ]
    outcomes = [(p.communicate(timeout=30), p.returncode) for p in processes]
    assert sorted(code for _, code in outcomes) == [0, 1]
    assert all(not streams[1] for streams, _ in outcomes)
    assert floor.inspect(path)[0].revision == 2
    # Revocation needs no private keys or valid live chain/settings.
    monkeypatch.delenv("FS_GW_EVIDENCE_PUBLIC_KEYS")
    current = floor.inspect(path)[1]
    command = [
        sys.executable,
        "tools/gw_catalog_trust.py",
        "revoke",
        "--expected-digest",
        current,
        "--workspace-id",
        "10",
        "--key-id",
        "catalog",
    ]
    result = subprocess.run(command, capture_output=True, timeout=30, check=False)
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout)["revokedKeys"] == 1
    assert not json.loads(result.stdout)["ready"]


@pytest.mark.parametrize(
    "change", ["reactivate", "remove", "rekey", "alias", "rollback", "fork", "new-root"]
)
def test_transition_rejects_even_well_formed_retirement_regressions(change):
    before = [
        floor.Authority(
            version=1,
            workspaceId="10",
            keyId="a",
            publicDigest="a" * 64,
            state="RETIRED",
            approvals=[["b" * 64, "c" * 64]],
        )
    ]
    after = deepcopy(before)
    if change == "reactivate":
        after[0] = after[0].model_copy(update={"state": "ACTIVE", "approvals": []})
    elif change == "remove":
        after = []
    elif change == "rekey":
        after[0] = after[0].model_copy(update={"public_digest": "f" * 64})
    elif change == "alias":
        after[0] = after[0].model_copy(update={"key_id": "alias"})
    elif change == "rollback":
        after[0] = after[0].model_copy(update={"approvals": [["b" * 64]]})
    elif change == "fork":
        after[0] = after[0].model_copy(update={"approvals": [["b" * 64, "d" * 64]]})
    else:
        after[0] = after[0].model_copy(update={"approvals": [["e" * 64, "f" * 64]]})
    with pytest.raises(ValueError):
        floor.transition(before, after)


@pytest.mark.parametrize("partial", [False, True])
def test_bootstrap_interruption_never_reinitializes_existing_originals(
    setup, monkeypatch, partial
):
    path = setup[0].parent / "bootstrap"
    path.mkdir(mode=0o700)
    keys = setup[1]["public_keys"]
    write = store.write_new

    def interrupted(root, name, raw):
        if name.startswith("trust-"):
            write(root, name, raw[:8] if partial else raw)
            raise OSError("injected")
        return write(root, name, raw)

    with monkeypatch.context() as patch:
        patch.setattr(store, "write_new", interrupted)
        with pytest.raises(OSError):
            floor.commit(path, keys, expected_digest="ABSENT", initialize=True)
    originals = {p.name: p.read_bytes() for p in path.glob("trust-*.json")}
    with pytest.raises((OSError, ValueError)):
        floor.commit(path, keys, expected_digest="ABSENT", initialize=True)
    target = max(path.glob("trust-*.json")).stem.split("-")[-1]
    if partial:
        with pytest.raises(ValueError):
            floor.resume(path, expected_digest=target)
    else:
        floor.resume(path, expected_digest=target)
        assert floor.check(keys, path) is keys
    assert originals == {p.name: p.read_bytes() for p in path.glob("trust-*.json")}


def test_revocation_resume_does_not_require_current_environment_or_private_keys(
    setup, monkeypatch
):
    path, sha, keys = initialize(setup, monkeypatch)
    write = store.write_new

    def interrupted(root, name, raw):
        write(root, name, raw)
        if name.startswith("trust-"):
            raise OSError("injected")

    with monkeypatch.context() as patch:
        patch.setattr(store, "write_new", interrupted)
        with pytest.raises(OSError):
            floor.revoke(path, workspace_id="10", key_id="catalog", expected_digest=sha)
    target = max(path.glob("trust-*.json")).stem.split("-")[-1]
    monkeypatch.delenv("FS_GW_EVIDENCE_PUBLIC_KEYS")
    result = subprocess.run(
        [
            sys.executable,
            "tools/gw_catalog_trust.py",
            "resume",
            "--expected-digest",
            target,
        ],
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0 and not result.stderr
    assert json.loads(result.stdout)["revokedKeys"] == 1
    with pytest.raises(ValueError):
        floor.check(keys, path)
    # Repeating a committed revocation is idempotent, not a release or new approval.
    assert (
        floor.revoke(path, workspace_id="10", key_id="catalog", expected_digest=target)[
            1
        ]
        == target
    )


def test_wrong_cas_unknown_key_and_size_limit_preserve_all_committed_bytes(
    setup, monkeypatch
):
    path, sha, keys = initialize(setup, monkeypatch)
    before = {p.name: p.read_bytes() for p in path.iterdir()}
    with pytest.raises(ValueError):
        floor.revoke(path, workspace_id="11", key_id="catalog", expected_digest=sha)
    with pytest.raises(ValueError):
        floor.commit(path, expanded(keys), expected_digest="0" * 64)
    with monkeypatch.context() as patch:
        patch.setattr(
            floor, "MAX_BYTES", max(p.stat().st_size for p in path.glob("trust-*.json"))
        )
        with pytest.raises(ValueError, match="size limit"):
            floor.commit(path, expanded(keys), expected_digest=sha)
    assert before == {p.name: p.read_bytes() for p in path.iterdir()}
    assert floor.check(keys, path) is keys


@pytest.mark.parametrize("damage", ["changed-bytes", "missing"])
def test_resume_requires_exact_retained_predecessor_head(setup, monkeypatch, damage):
    path, sha, keys = initialize(setup, monkeypatch)
    with monkeypatch.context() as patch:
        patch.setattr(
            floor, "_activate", lambda *args: (_ for _ in ()).throw(OSError("injected"))
        )
        with pytest.raises(OSError):
            floor.commit(path, expanded(keys), expected_digest=sha)
    if damage == "changed-bytes":
        head = path / floor.HEAD
        head.write_bytes(head.read_bytes() + b" ")
    else:
        (path / floor.HEAD).unlink()
    originals = {p.name: p.read_bytes() for p in path.iterdir()}
    target = max(path.glob("trust-*.json")).stem.split("-")[-1]
    with pytest.raises(ValueError):
        floor.resume(path, expected_digest=target)
    assert originals == {p.name: p.read_bytes() for p in path.iterdir()}


def test_revocation_retains_explicit_company_scope_without_expanding_other_authority(
    setup, monkeypatch
):
    path, sha, keys = initialize(setup, monkeypatch)
    scopes = dict(keys.scopes) | {
        "catalog": (frozenset(["10", "11"]), frozenset(["CHECKPOINT_CATALOG"]))
    }
    keys = EvidenceTrust(keys, scopes)
    _, sha = floor.commit(path, keys, expected_digest=sha)
    floor.revoke(path, workspace_id="10", key_id="catalog", expected_digest=sha)
    config = {
        "version": 1,
        "keys": [
            {
                "version": 1,
                "workspaceId": "10",
                "keyId": "catalog",
                "publicKey": base64.b64encode(keys["catalog"]).decode(),
                "state": "REVOKED",
                "approvals": [],
            }
        ],
    }
    keys = handover.bind(keys, json.dumps(config))
    environment(monkeypatch, keys, config)
    current = from_environment()
    with pytest.raises(ValueError):
        current.authorize("catalog", "CHECKPOINT_CATALOG", "10")
    current.authorize("catalog", "CHECKPOINT_CATALOG", "11")
    with pytest.raises(ValueError):
        current.authorize("catalog", "BACKUP", "11")
