"""Planned catalog retirement is exact history authority, never current/revoked authority."""

# ruff: noqa: F401,F811
import base64
import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_gw_catalog_recovery import interrupt, recover
from test_gw_catalog_segments import finish, package
from test_gw_catalog_store import cli_env, invoke, setup
from test_gw_catalog_transfer import outgoing, receive, receiver

from fs.gw import catalog_key_handover as handover
from fs.gw import catalog_store as store
from fs.gw.checkpoint_catalog import DOMAIN, CatalogConfig, verify_document
from fs.gw.evidence_trust import EvidenceTrust, authorize, from_environment
from fs.gw.operating_contract import canonical


def add_successor(parts):
    key = Ed25519PrivateKey.generate()
    trust = parts[1]["public_keys"]
    scopes = dict(trust.scopes) | {
        "next-catalog": (
            frozenset([str(parts[2]["workspace_id"])]),
            frozenset(["CHECKPOINT_CATALOG"]),
        )
    }
    trust = EvidenceTrust(
        dict(trust) | {"next-catalog": key.public_key().public_bytes_raw()}, scopes
    )
    parts[1]["public_keys"] = parts[2]["public_keys"] = trust
    return key, trust


def issue(parts, previous, successor, **changes):
    kw = parts[1]
    args = {
        "context": kw["context"],
        "public_keys": kw["public_keys"],
        "retiring_signer": kw["signer"],
        "retiring_id": "catalog",
        "successor_signer": successor,
        "successor_id": "next-catalog",
        "now": kw["now"],
        "expected_pin_digest": previous["pinDigest"],
    }
    args.update(changes)
    raw, report = handover.issue(parts[0], **args)
    path = parts[0].parent / "handover.json"
    path.write_bytes(raw)
    path.chmod(0o600)
    return path, raw, report


def configuration(parts, receipt, *, state="RETIRED"):
    return {
        "version": 1,
        "keys": [
            {
                "version": 1,
                "workspaceId": str(parts[2]["workspace_id"]),
                "keyId": "catalog",
                "publicKey": base64.b64encode(
                    parts[1]["signer"].public_key().public_bytes_raw()
                ).decode(),
                "state": state,
                "approvals": [
                    {
                        "version": 1,
                        "file": str(receipt[0]),
                        "digest": receipt[2]["handoverDigest"],
                    }
                ]
                if state == "RETIRED"
                else [],
            }
        ],
    }


def retired(parts, full, receipt, *, state="RETIRED", keep_active=False, config=None):
    active = (
        full
        if keep_active
        else EvidenceTrust(
            {k: v for k, v in full.items() if k != "catalog"},
            {k: v for k, v in full.scopes.items() if k != "catalog"},
        )
    )
    return handover.bind(
        active, json.dumps(config or configuration(parts, receipt, state=state))
    )


def source(parts, patch, kind):
    if kind == "PARTIAL":
        interrupt(parts, patch, size=8)
        return recover(parts)
    first = invoke(parts)
    return (
        invoke(parts, first, head_path=parts[0] / "absent") if kind == "FAIL" else first
    )


@pytest.mark.parametrize("kind", ["PASS", "FAIL", "PARTIAL"])
@pytest.mark.parametrize("transport", ["single", "segments"])
@pytest.mark.parametrize("existing_receiver", [False, True])
def test_exact_retirement_history_advances_receiver_but_never_changes_latest_result(
    setup, monkeypatch, kind, transport, existing_receiver
):
    first = source(setup, monkeypatch, kind)
    dest = receiver(setup)
    old = receive(setup, dest, *outgoing(setup)) if existing_receiver else None
    successor, full = add_successor(setup)
    receipt = issue(setup, first, successor)
    before = {p.name: p.read_bytes() for p in setup[0].glob("catalog-*.json")}
    current = invoke(
        setup, first, operation="refresh", signer=successor, signer_id="next-catalog"
    )
    keys = retired(setup, full, receipt)
    setup[1]["public_keys"] = setup[2]["public_keys"] = keys
    if old:
        with pytest.raises(ValueError):
            store.managed_read(
                dest / store.PIN,
                public_keys=keys,
                workspace_id=setup[2]["workspace_id"],
                now=setup[1]["now"],
            )
    base, sha = (first["revision"], first["catalogDigest"]) if old else (0, "ABSENT")
    if transport == "single":
        raw, anchor = outgoing(setup, base, sha)
        copied = receive(setup, dest, raw, anchor, old)
    else:
        packet = package(setup, base, sha)
        copied = finish(setup, dest, packet, old, **({"resume": False} if old else {}))
    assert (
        copied["result"] == kind
        and copied["revision"] == current["revision"]
        and not copied["ready"]
    )
    assert all(
        (setup[0] / name).read_bytes() == data and (dest / name).read_bytes() == data
        for name, data in before.items()
        if int(store.NAME.fullmatch(name)[1]) >= base
    )
    observed, _ = store.managed_read(
        dest / store.PIN,
        public_keys=keys,
        workspace_id=setup[2]["workspace_id"],
        now=setup[1]["now"],
    )
    assert (
        observed.signer_key_id == "next-catalog" and observed.records[0].result == kind
    )
    with pytest.raises(ValueError):
        invoke(
            setup, current, operation="refresh"
        )  # Retired private key is never current authority.
    revoked = retired(setup, full, receipt, state="REVOKED", keep_active=True)
    if kind == "PARTIAL":
        # Active outer signature cannot resurrect a revoked original recovery proof.
        with pytest.raises(ValueError):
            store.managed_read(
                dest / store.PIN,
                public_keys=revoked,
                workspace_id=setup[2]["workspace_id"],
                now=setup[1]["now"],
            )
    with pytest.raises(ValueError):
        handover.key(
            revoked,
            "catalog",
            str(setup[2]["workspace_id"]),
            digest=first["catalogDigest"],
            catalog_id=first["catalogId"],
            generation_id=str(setup[2]["generation_id"]),
            claimed_at=setup[1]["now"].isoformat(),
        )


@pytest.mark.parametrize(
    "problem",
    [
        "live",
        "new_backdated",
        "same_revision_fork",
        "other_company",
        "other_generation",
        "other_catalog",
        "unapproved_later",
        "removed_approval",
        "revoked",
    ],
)
def test_retired_signature_cannot_authorize_new_or_current_or_different_bytes(
    setup, problem
):
    first = invoke(setup)
    successor, full = add_successor(setup)
    receipt = issue(setup, first, successor)
    original = (
        setup[0] / store.filename(first["revision"], first["catalogDigest"])
    ).read_bytes()
    raw = original
    if problem in {
        "new_backdated",
        "same_revision_fork",
        "other_company",
        "other_generation",
        "other_catalog",
    }:
        value = json.loads(raw)
        env = value["envelope"]
        if problem == "new_backdated":
            env["revision"] += 10
            env["publishedAt"] = (setup[1]["now"] - timedelta(seconds=1)).isoformat()
        elif problem == "same_revision_fork":
            env["records"][0].update(result="FAIL", head=None)
        elif problem == "other_company":
            env["records"][0].update(workspaceId="999", result="FAIL", head=None)
        elif problem == "other_generation":
            env["records"][0].update(generationId="999", result="FAIL", head=None)
        else:
            from uuid import uuid4

            env["catalogId"] = str(uuid4())
        value["signature"] = base64.b64encode(
            setup[1]["signer"].sign(DOMAIN + canonical(env))
        ).decode()
        raw = canonical(value)
    keys = retired(
        setup,
        full,
        receipt,
        keep_active=True,
        state="REVOKED" if problem == "revoked" else "RETIRED",
    )
    if problem == "removed_approval":
        keys = EvidenceTrust(
            {k: v for k, v in full.items() if k != "catalog"},
            {k: v for k, v in full.scopes.items() if k != "catalog"},
        )
    if problem == "unapproved_later":
        later = invoke(setup, first, operation="refresh")
        raw = (
            setup[0] / store.filename(later["revision"], later["catalogDigest"])
        ).read_bytes()
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=json.loads(raw)["envelope"]["catalogId"],
        file="/unused",
        digest=store.digest(raw),
    )
    with pytest.raises((ValueError, KeyError)):
        verify_document(
            raw,
            config,
            public_keys=keys,
            workspace_id=setup[2]["workspace_id"],
            historical=problem != "live",
        )
    with pytest.raises(ValueError):
        authorize(keys, "catalog", "CHECKPOINT_CATALOG", str(setup[2]["workspace_id"]))


@pytest.mark.parametrize(
    "problem",
    [
        "pin",
        "retiring_signature",
        "successor_signature",
        "role_swap",
        "scope",
        "public",
        "issuer_scope",
        "issuer_removed",
        "issuer_revoked",
        "alias",
        "id_reused",
        "duplicate",
        "version",
        "extra",
        "revoked_with_grant",
        "retired_without_grant",
        "invalid_public",
        "relative",
        "duplicate_json",
        "recursive",
        "symlink",
        "public_file",
        "overlap",
        "future",
    ],
)
def test_lifecycle_and_dual_signature_configuration_rejects_ambiguous_or_changed_authority(
    setup, problem
):
    first = invoke(setup)
    successor, full = add_successor(setup)
    receipt = issue(setup, first, successor)
    config = configuration(setup, receipt)
    record = config["keys"][0]
    if problem in {"retiring_signature", "successor_signature", "role_swap", "future"}:
        value = json.loads(receipt[1])
        if problem == "role_swap":
            value["retiringSignature"], value["successorSignature"] = (
                value["successorSignature"],
                value["retiringSignature"],
            )
        elif problem == "future":
            value["envelope"]["issuedAt"] = (
                datetime.now(UTC) + timedelta(minutes=1)
            ).isoformat()
        else:
            value[
                "retiringSignature"
                if problem == "retiring_signature"
                else "successorSignature"
            ] = base64.b64encode(b"x" * 64).decode()
        data = canonical(value)
        receipt[0].write_bytes(data)
        record["approvals"][0]["digest"] = store.digest(data)
    elif problem == "pin":
        record["approvals"][0]["digest"] = "f" * 64
    elif problem == "scope":
        record["workspaceId"] = "999"
    elif problem == "public":
        record["publicKey"] = base64.b64encode(
            Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        ).decode()
    elif problem == "issuer_scope":
        full = EvidenceTrust(
            full,
            dict(full.scopes)
            | {"next-catalog": (frozenset(["999"]), frozenset(["CHECKPOINT_CATALOG"]))},
        )
    elif problem == "issuer_removed":
        full = EvidenceTrust(
            {k: v for k, v in full.items() if k != "next-catalog"},
            {k: v for k, v in full.scopes.items() if k != "next-catalog"},
        )
    elif problem == "issuer_revoked":
        config["keys"].append(
            record
            | {
                "keyId": "next-catalog",
                "publicKey": base64.b64encode(full["next-catalog"]).decode(),
                "state": "REVOKED",
                "approvals": [],
            }
        )
    elif problem == "alias":
        full = EvidenceTrust(
            dict(full) | {"alias": full["catalog"]},
            dict(full.scopes) | {"alias": full.scopes["catalog"]},
        )
    elif problem == "id_reused":
        full = EvidenceTrust(
            dict(full) | {"catalog": full["next-catalog"]}, full.scopes
        )
    elif problem == "duplicate":
        config["keys"].append(deepcopy(record))
    elif problem == "version":
        config["version"] = True
    elif problem == "extra":
        record["acceptancePass"] = True
    elif problem == "revoked_with_grant":
        record["state"] = "REVOKED"
    elif problem == "retired_without_grant":
        record["approvals"] = []
    elif problem == "invalid_public":
        record["publicKey"] = "not-base64"
    elif problem == "relative":
        record["approvals"][0]["file"] = "relative/handover.json"
    elif problem == "symlink":
        other = receipt[0].with_name("original-handover.json")
        receipt[0].rename(other)
        receipt[0].symlink_to(other)
    elif problem == "public_file":
        receipt[0].chmod(0o644)
    elif problem == "overlap":
        record["approvals"] *= 2
    raw = json.dumps(config)
    if problem == "duplicate_json":
        raw = raw.replace('"version": 1', '"version":1,"version":1', 1)
    elif problem == "recursive":
        raw = "[" * 2000 + "]" * 2000
    with pytest.raises(
        (ValueError, KeyError, OSError, InvalidSignature, RecursionError)
    ):
        handover.bind(full, raw)


def test_recovery_inner_signature_needs_exact_approval_and_retired_outer_never_live(
    setup, monkeypatch
):
    current = source(setup, monkeypatch, "PARTIAL")
    successor, full = add_successor(setup)
    receipt = issue(setup, current, successor)
    latest = invoke(
        setup, current, operation="refresh", signer=successor, signer_id="next-catalog"
    )
    keys = retired(setup, full, receipt)
    path = setup[0] / store.filename(latest["revision"], latest["catalogDigest"])
    value = json.loads(path.read_bytes())
    proof = value["envelope"]["recoveryProof"]
    proof["envelope"]["recoveredAt"] = (
        setup[1]["now"] - timedelta(seconds=1)
    ).isoformat()
    from fs.gw.catalog_recovery import DOMAIN as recovery_domain

    proof["signature"] = base64.b64encode(
        setup[1]["signer"].sign(recovery_domain + canonical(proof["envelope"]))
    ).decode()
    value["signature"] = base64.b64encode(
        successor.sign(DOMAIN + canonical(value["envelope"]))
    ).decode()
    raw = canonical(value)
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=latest["catalogId"],
        file="/unused",
        digest=store.digest(raw),
    )
    with pytest.raises(ValueError):
        verify_document(
            raw, config, public_keys=keys, workspace_id=setup[2]["workspace_id"]
        )


@pytest.mark.parametrize(
    "problem",
    [
        "cas",
        "missing_history",
        "same_key",
        "wrong_private",
        "retired",
        "clock",
        "stale",
    ],
)
def test_issue_requires_both_active_keys_and_exact_healthy_current_history(
    setup, problem
):
    first = invoke(setup)
    successor, full = add_successor(setup)
    changes = {}
    if problem == "cas":
        changes["expected_pin_digest"] = "f" * 64
    elif problem == "missing_history":
        next_item = invoke(setup, first, operation="refresh")
        (setup[0] / store.filename(first["revision"], first["catalogDigest"])).unlink()
        first = next_item
    elif problem == "same_key":
        changes.update(successor_signer=setup[1]["signer"], successor_id="catalog")
    elif problem == "wrong_private":
        changes["successor_signer"] = Ed25519PrivateKey.generate()
    elif problem == "retired":
        receipt = issue(setup, first, successor)
        changes["public_keys"] = retired(setup, full, receipt, keep_active=True)
    elif problem == "clock":
        changes["now"] = setup[1]["now"] - timedelta(seconds=1)
    else:
        changes["now"] = setup[1]["now"] + timedelta(minutes=16)
    before = {p.name: p.read_bytes() for p in setup[0].iterdir()}
    with pytest.raises((ValueError, KeyError, InvalidSignature)):
        issue(setup, first, successor, **changes)
    assert before == {p.name: p.read_bytes() for p in setup[0].iterdir()}


def test_real_issue_cli_and_public_only_inspection_reload_pinned_lifecycle(
    setup, monkeypatch
):
    first = invoke(setup)
    first = invoke(setup, first, operation="refresh", now=datetime.now(UTC))
    env, publishing = cli_env(setup)
    successor, full = add_successor(setup)
    public = {k: base64.b64encode(v).decode() for k, v in full.items()}
    scopes = json.loads(env["FS_GW_EVIDENCE_KEY_SCOPES"])
    scopes["keys"]["next-catalog"] = {
        "workspaceIds": [str(setup[2]["workspace_id"])],
        "purposes": ["CHECKPOINT_CATALOG"],
    }
    env["FS_GW_EVIDENCE_PUBLIC_KEYS"] = json.dumps(public)
    env["FS_GW_EVIDENCE_KEY_SCOPES"] = json.dumps(scopes)
    private = setup[0].parent / "next.key"
    private.write_bytes(successor.private_bytes_raw())
    private.chmod(0o600)
    env.update(
        FS_GW_CATALOG_SUCCESSOR_KEY_FILE=str(private),
        FS_GW_CATALOG_SUCCESSOR_KEY_ID="next-catalog",
    )
    output = setup[0].parent / "cli-handover.json"
    command = [
        sys.executable,
        "tools/gw_catalog_key_handover.py",
        "issue",
        "--context",
        publishing[6],
        "--directory",
        str(setup[0]),
        "--retiring-key-id",
        "catalog",
        "--expected-pin-digest",
        first["pinDigest"],
        "--output",
        str(output),
    ]
    before = {p.name: p.read_bytes() for p in setup[0].iterdir()}
    result = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert (
        result.returncode == 0
        and not result.stderr
        and output.stat().st_mode & 0o777 == 0o600
    )
    report = json.loads(result.stdout)
    assert (
        report["handoverDigest"] == store.digest(output.read_bytes())
        and not report["ready"]
    )
    assert before == {p.name: p.read_bytes() for p in setup[0].iterdir()}
    receipt = output, output.read_bytes(), report
    config = configuration(setup, receipt)
    public.pop("catalog")
    scopes["keys"].pop("catalog")
    env.update(
        FS_GW_EVIDENCE_PUBLIC_KEYS=json.dumps(public),
        FS_GW_EVIDENCE_KEY_SCOPES=json.dumps(scopes),
    )
    env[handover.ENV] = json.dumps(config)
    for name in [
        "FS_GW_CATALOG_KEY_FILE",
        "FS_GW_CATALOG_KEY_ID",
        "FS_GW_CATALOG_SUCCESSOR_KEY_FILE",
        "FS_GW_CATALOG_SUCCESSOR_KEY_ID",
    ]:
        env.pop(name)
    command = [
        sys.executable,
        "tools/gw_catalog_key_handover.py",
        "inspect",
        "--context",
        publishing[6],
        "--retiring-key-id",
        "catalog",
    ]
    result = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert result.returncode == 2 and not result.stderr
    assert json.loads(result.stdout) == {
        "keyId": "catalog",
        "state": "RETIRED",
        "approvedDocuments": 2,
        "ready": False,
    }
    for name in [
        "FS_GW_EVIDENCE_PUBLIC_KEYS",
        "FS_GW_EVIDENCE_KEY_SCOPES",
        handover.ENV,
    ]:
        monkeypatch.setenv(name, env[name])
    assert from_environment().catalog_lifecycle is not None
    output.write_bytes(output.read_bytes() + b"tampered")
    with pytest.raises(ValueError):
        from_environment()
    result = subprocess.run(
        command, env=env, capture_output=True, timeout=30, check=False
    )
    assert (
        result.returncode == 1 and not result.stderr
    )  # Safe diagnostic, no private values/trace.


def test_environment_converts_approval_io_signature_and_recursive_failures_to_safe_configuration_error(
    setup, monkeypatch
):
    first = invoke(setup)
    env, _ = cli_env(setup)
    successor, full = add_successor(setup)
    receipt = issue(setup, first, successor)
    env["FS_GW_EVIDENCE_PUBLIC_KEYS"] = json.dumps(
        {k: base64.b64encode(v).decode() for k, v in full.items()}
    )
    scopes = json.loads(env["FS_GW_EVIDENCE_KEY_SCOPES"])
    scopes["keys"]["next-catalog"] = {
        "workspaceIds": [str(setup[2]["workspace_id"])],
        "purposes": ["CHECKPOINT_CATALOG"],
    }
    env["FS_GW_EVIDENCE_KEY_SCOPES"] = json.dumps(scopes)
    for name in ["FS_GW_EVIDENCE_PUBLIC_KEYS", "FS_GW_EVIDENCE_KEY_SCOPES"]:
        monkeypatch.setenv(name, env[name])
    config = configuration(setup, receipt)
    config["keys"][0]["approvals"][0]["file"] = str(
        receipt[0].with_name("missing.json")
    )
    monkeypatch.setenv(handover.ENV, json.dumps(config))
    with pytest.raises(ValueError, match="lifecycle trust unavailable"):
        from_environment()
    value = json.loads(receipt[1])
    value["retiringSignature"] = base64.b64encode(b"x" * 64).decode()
    raw = canonical(value)
    receipt[0].write_bytes(raw)
    config = configuration(setup, receipt)
    config["keys"][0]["approvals"][0]["digest"] = store.digest(raw)
    monkeypatch.setenv(handover.ENV, json.dumps(config))
    with pytest.raises(ValueError, match="lifecycle trust unavailable"):
        from_environment()
    monkeypatch.setenv(handover.ENV, "[" * 2000 + "]" * 2000)
    with pytest.raises(ValueError, match="lifecycle trust unavailable"):
        from_environment()


@pytest.mark.parametrize("claim", ["sequence", "record", "revision"])
def test_even_dual_signed_capture_metadata_must_match_the_exact_original(setup, claim):
    first = invoke(setup)
    successor, full = add_successor(setup)
    path, raw, report = issue(setup, first, successor)
    value = json.loads(raw)
    envelope = value["envelope"]
    if claim == "sequence":
        envelope["capturedSequence"] += 1
    elif claim == "record":
        envelope["capturedRecordDigest"] = "f" * 64
    else:
        envelope["capturedRevision"] += 1
        envelope["snapshots"][-1]["revision"] += 1
    message = handover.DOMAIN + canonical(envelope)
    value["retiringSignature"] = base64.b64encode(
        setup[1]["signer"].sign(b"RETIRING\0" + message)
    ).decode()
    value["successorSignature"] = base64.b64encode(
        successor.sign(b"SUCCESSOR\0" + message)
    ).decode()
    raw = canonical(value)
    path.write_bytes(raw)
    report["handoverDigest"] = store.digest(raw)
    keys = retired(setup, full, (path, raw, report))
    data = (
        setup[0] / store.filename(first["revision"], first["catalogDigest"])
    ).read_bytes()
    config = CatalogConfig(
        version=1,
        provider="SIGNED_SNAPSHOT_FILE",
        catalogId=first["catalogId"],
        file="/unused",
        digest=first["catalogDigest"],
    )
    with pytest.raises(ValueError, match="capture metadata"):
        verify_document(
            data,
            config,
            public_keys=keys,
            workspace_id=setup[2]["workspace_id"],
            historical=True,
        )
