"""Configured catalog snapshots never replace latest failure with an older success."""

import base64
import hashlib
import json
from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.checkpoint_catalog import DOMAIN, ENV, observe, require_history
from fs.gw.evidence_trust import load
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.restore_recheck import sign, verify
from test_gw_checkpoint_head import prepared_head
from test_gw_source_checkpoint import observation


def add_authority(keys, workspace_id, authority):
    public = {k: base64.b64encode(v).decode() for k, v in keys.items()}
    public["catalog"] = base64.b64encode(
        authority.public_key().public_bytes_raw()
    ).decode()
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
            k: {"workspaceIds": [str(workspace_id)], "purposes": uses[k]}
            for k in public
        },
    }
    return load(json.dumps(public), json.dumps(scopes), mode="COMPANY")


def publish(folder, envelope, key, patch):
    document = {
        "envelope": deepcopy(envelope),
        "signature": base64.b64encode(key.sign(DOMAIN + canonical(envelope))).decode(),
    }
    path = folder / (str(uuid4()) + ".json")
    raw = canonical(document) + b"\n"
    path.write_bytes(raw)
    path.chmod(0o600)
    config = {
        "version": 1,
        "provider": "SIGNED_SNAPSHOT_FILE",
        "catalogId": envelope["catalogId"],
        "file": str(path),
        "digest": hashlib.sha256(raw).hexdigest(),
    }
    patch.setenv(ENV, json.dumps(config))
    return document, config


def prepared(tmp_path, patch):
    docs, obs, collector, key, checkpoint, head, ctx = prepared_head()
    authority = Ed25519PrivateKey.generate()
    ctx["public_keys"] = add_authority(
        ctx["public_keys"], ctx["workspace_id"], authority
    )
    folder = tmp_path / "catalog"
    folder.mkdir(mode=0o700)
    envelope = {
        "version": 1,
        "kind": "CHECKPOINT_CATALOG",
        "catalogId": str(uuid4()),
        "revision": 1,
        "publishedAt": ctx["now"].isoformat(),
        "signerKeyId": "catalog",
        "records": [
            {
                "sequence": 1,
                "workspaceId": str(ctx["workspace_id"]),
                "generationId": str(ctx["generation_id"]),
                "policyDigest": ctx["policy"].digest(),
                "codeRevision": ctx["code_revision"],
                "dbRevision": ctx["db_revision"],
                "recordedAt": ctx["now"].isoformat(),
                "result": "PASS",
                "head": deepcopy(head),
            }
        ],
    }
    publish(folder, envelope, authority, patch)
    return docs, obs, collector, key, checkpoint, head, ctx, authority, folder, envelope


def recheck(parts):
    docs, obs, _collector, key, _checkpoint, head, ctx, *_ = parts
    catalog = observe(head, observed_at=ctx["now"].isoformat(), **ctx)
    return sign(
        docs["RESTORE"],
        measurement=obs,
        source_observation=observation(obs, ctx),
        checkpoint_head=head,
        catalog_observation=catalog,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )


def test_catalog_current_recheck_roundtrip_is_partial_and_excludes_other_company(
    tmp_path, monkeypatch
):
    parts = prepared(tmp_path, monkeypatch)
    (
        docs,
        _obs,
        collector,
        _key,
        _checkpoint,
        _head,
        ctx,
        authority,
        folder,
        envelope,
    ) = parts
    envelope["records"].append(
        envelope["records"][0] | {"sequence": 9, "workspaceId": "999", "head": None}
    )
    publish(folder, envelope, authority, monkeypatch)
    document = recheck(parts)
    parsed = verify(document, docs["RESTORE"], **ctx)
    assert parsed.version == 4 and parsed.result == "PARTIAL"
    assert parsed.catalog_observation.latest_sequence == 1
    assert not parsed.catalog_observation.external_independence_verified
    assert '"workspaceId":"999"' not in canonical(document).decode()
    acceptance = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        **ctx,
    )
    assert (
        verify_evidence(acceptance["envelope"], acceptance["signature"], **ctx).result
        == "PARTIAL"
    )
    assert parsed.model_dump(by_alias=True) == document["envelope"]


@pytest.mark.parametrize(
    "mode,reason",
    [
        ("fail", "LATEST_FAIL"),
        ("partial", "LATEST_PARTIAL"),
        ("missing", "ORIGINAL_MISSING"),
        ("different", "HEAD_MISMATCH"),
        ("old-code", "CONTEXT_MISMATCH"),
        ("old-db", "CONTEXT_MISMATCH"),
        ("old-policy", "CONTEXT_MISMATCH"),
        ("scope", "SCOPE_MISSING"),
    ],
)
def test_latest_record_is_selected_across_results_originals_and_old_context(
    tmp_path, monkeypatch, mode, reason
):
    parts = prepared(tmp_path, monkeypatch)
    docs, _obs, collector, _key, checkpoint, _head, ctx, authority, folder, envelope = (
        parts
    )
    newer = deepcopy(envelope["records"][0])
    newer["sequence"] = 2
    if mode == "fail":
        newer["result"] = "FAIL"
    elif mode == "partial":
        newer["result"] = "PARTIAL"
    elif mode == "missing":
        newer["head"] = None
    elif mode == "different":
        newer["head"]["payload"]["runId"] = str(uuid4())
    elif mode == "old-code":
        newer["codeRevision"] = "f" * 8
    elif mode == "old-db":
        newer["dbRevision"] = "old_revision"
    elif mode == "old-policy":
        newer["policyDigest"] = "f" * 64
        newer["head"]["payload"]["scope"]["policyDigest"] = "f" * 64
    if newer["head"] is not None:
        newer["head"]["signature"] = base64.b64encode(
            checkpoint.sign(
                b"FS-OPERATOR-BUNDLE-v1\0" + canonical(newer["head"]["payload"])
            )
        ).decode()
    envelope.update(revision=2, records=[newer, envelope["records"][0]])
    if mode == "scope":
        envelope["records"] = []
    publish(folder, envelope, authority, monkeypatch)
    document = recheck(parts)
    parsed = verify(document, docs["RESTORE"], **ctx)
    assert parsed.result == "BLOCKED" and parsed.catalog_observation.reason == reason
    assert parsed.catalog_observation.latest_sequence == (
        None if mode == "scope" else 2
    )
    acceptance = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        **ctx,
    )
    assert acceptance["envelope"]["result"] == "FAIL"


@pytest.mark.parametrize(
    "change",
    [
        "pin",
        "signature",
        "purpose",
        "revoked",
        "missing",
        "mode",
        "folder-mode",
        "symlink",
        "old",
        "future",
        "duplicate-sequence",
        "extra",
        "duplicate-json",
        "empty-config",
        "relative",
        "wrong-id",
        "float-version",
        "reused-issuer",
    ],
)
def test_unreadable_tampered_or_untrusted_catalog_never_falls_back(
    tmp_path, monkeypatch, change
):
    parts = prepared(tmp_path, monkeypatch)
    (
        _docs,
        _obs,
        _collector,
        _key,
        _checkpoint,
        head,
        ctx,
        authority,
        folder,
        envelope,
    ) = parts
    if change == "old":
        envelope["publishedAt"] = (ctx["now"] - timedelta(minutes=16)).isoformat()
        envelope["records"][0]["recordedAt"] = envelope["publishedAt"]
        envelope["records"][0]["head"] = None
    elif change == "future":
        envelope["publishedAt"] = (ctx["now"] + timedelta(seconds=31)).isoformat()
    elif change == "duplicate-sequence":
        envelope["records"] *= 2
    elif change == "extra":
        envelope["independent"] = True
    elif change == "float-version":
        envelope["version"] = 1.0
    elif change == "purpose":
        envelope["signerKeyId"] = "rechecker"
    document, config = publish(folder, envelope, authority, monkeypatch)
    path = Path(config["file"])
    if change == "pin":
        config["digest"] = "0" * 64
    elif change == "signature":
        document["signature"] = "AAAA"
        raw = canonical(document)
        path.write_bytes(raw)
        config["digest"] = hashlib.sha256(raw).hexdigest()
    elif change == "revoked":
        ctx["public_keys"] = add_authority(
            ctx["public_keys"], ctx["workspace_id"], Ed25519PrivateKey.generate()
        )
    elif change == "missing":
        path.unlink()
    elif change == "mode":
        path.chmod(0o644)
    elif change == "folder-mode":
        folder.chmod(0o755)
    elif change == "symlink":
        link = folder / "link"
        link.symlink_to(path)
        config["file"] = str(link)
    elif change == "duplicate-json":
        raw = canonical(document).replace(b'"version":1', b'"version":1,"version":1', 1)
        path.write_bytes(raw)
        config["digest"] = hashlib.sha256(raw).hexdigest()
    elif change == "relative":
        config["file"] = "catalog.json"
    elif change == "wrong-id":
        config["catalogId"] = str(uuid4())
    elif change == "reused-issuer":
        public = {
            k: base64.b64encode(v).decode() for k, v in ctx["public_keys"].items()
        }
        scopes = {
            "version": 1,
            "keys": {
                k: {
                    "workspaceIds": [str(ctx["workspace_id"])],
                    "purposes": ["CHECKPOINT_CATALOG", "RESTORE_RECHECK"]
                    if k == "catalog"
                    else ["BACKUP"],
                }
                for k in public
            },
        }
        with pytest.raises(ValueError):
            load(json.dumps(public), json.dumps(scopes), mode="COMPANY")
        return
    monkeypatch.setenv(ENV, "" if change == "empty-config" else json.dumps(config))
    with pytest.raises(ValueError, match="configured checkpoint catalog"):
        observe(head, observed_at=ctx["now"].isoformat(), **ctx)


def test_configured_catalog_rejects_old_format_and_changed_catalog_after_observation(
    tmp_path, monkeypatch
):
    parts = prepared(tmp_path, monkeypatch)
    docs, obs, _collector, key, _checkpoint, head, ctx, authority, folder, envelope = (
        parts
    )
    with pytest.raises(ValueError):
        sign(
            docs["RESTORE"],
            measurement=obs,
            source_observation=observation(obs, ctx),
            checkpoint_head=head,
            checked_at=ctx["now"].isoformat(),
            signer=key,
            signer_id="rechecker",
            **ctx,
        )
    document = recheck(parts)
    envelope["revision"] = 2
    envelope["records"][0]["result"] = "FAIL"
    publish(folder, envelope, authority, monkeypatch)
    with pytest.raises(ValueError, match="current checkpoint catalog differs"):
        verify(document, docs["RESTORE"], **ctx)
    monkeypatch.delenv(ENV)
    with pytest.raises(ValueError):
        verify(document, docs["RESTORE"], **ctx)


@pytest.mark.parametrize(
    "change",
    [
        "revision",
        "sequence",
        "identity",
        "equivocation",
        "rewritten-head",
        "missing-history",
        "capture-rollback",
        "capture-equivocation",
        "downgrade",
        "none",
    ],
)
def test_registered_history_blocks_rollback_reset_or_equivocation_even_without_original(
    tmp_path, monkeypatch, change
):
    parts = prepared(tmp_path, monkeypatch)
    current = observe(parts[5], observed_at=parts[6]["now"].isoformat(), **parts[6])
    old = deepcopy(current)
    if change == "revision":
        old["catalogRevision"] += 1
    elif change == "sequence":
        old["latestSequence"] += 1
    elif change == "identity":
        old["catalogId"] = str(uuid4())
    elif change == "equivocation":
        old["catalogDigest"] = "f" * 64
    elif change == "rewritten-head":
        old["latestHeadDigest"] = "f" * 64
    elif change == "capture-rollback":
        old["latestCapturedAt"] = (parts[6]["now"] + timedelta(seconds=1)).isoformat()
    elif change == "capture-equivocation":
        old["latestSequence"] = 1
        current["latestSequence"] = 2
        current["catalogRevision"] = 2
        old["latestHeadDigest"] = "f" * 64
    elif change == "missing-history":
        old = None

    class Connection:
        def execute(self, *a, **k):
            return self

        def mappings(self):
            return self

        def all(self):
            return [{"observation": old}]

    data = SimpleNamespace(
        result="PARTIAL",
        metrics=SimpleNamespace(
            acceptance_diagnostics=SimpleNamespace(
                restore_recheck=SimpleNamespace(
                    envelope={"catalogObservation": current}
                )
                if change != "downgrade"
                else None
            )
        ),
    )
    if change == "none":
        require_history(Connection(), data, workspace_id=1, generation_id=1)
    else:
        with pytest.raises((ApiError, ValueError)):
            require_history(Connection(), data, workspace_id=1, generation_id=1)


@pytest.mark.parametrize("target_mode", ["clear", "blocked", "unavailable"])
@pytest.mark.parametrize("source_blocked", [False, True])
@pytest.mark.parametrize("catalog_blocked", [False, True])
def test_any_blocked_or_unavailable_observation_keeps_acceptance_failed(
    tmp_path, monkeypatch, target_mode, source_blocked, catalog_blocked
):
    parts = prepared(tmp_path, monkeypatch)
    docs, obs, collector, key, _checkpoint, head, ctx, authority, folder, envelope = (
        parts
    )
    if catalog_blocked:
        envelope["records"][0]["result"] = "FAIL"
        publish(folder, envelope, authority, monkeypatch)
    source = observation(obs, ctx, "changed" if source_blocked else "match")
    measurement = deepcopy(obs)
    if target_mode == "blocked":
        measurement.update(coreViolations=1, result="BLOCKED", stateDigest="0" * 64)
    elif target_mode == "unavailable":
        measurement = None
    catalog = observe(head, observed_at=ctx["now"].isoformat(), **ctx)
    document = sign(
        docs["RESTORE"],
        measurement=measurement,
        source_observation=source,
        checkpoint_head=head,
        catalog_observation=catalog,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )
    expected = (
        "PARTIAL"
        if target_mode == "clear" and not source_blocked and not catalog_blocked
        else "BLOCKED"
    )
    assert verify(document, docs["RESTORE"], **ctx).result == expected
    result = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        **ctx,
    )
    assert result["envelope"]["result"] == (
        "PARTIAL" if expected == "PARTIAL" else "FAIL"
    )


@pytest.mark.parametrize(
    "reason",
    [
        "LATEST_FAIL",
        "LATEST_PARTIAL",
        "ORIGINAL_MISSING",
        "SCOPE_MISSING",
        "CONTEXT_MISMATCH",
        "HEAD_MISMATCH",
    ],
)
@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_any_registered_catalog_failure_requires_capture_strictly_after_registration(
    tmp_path, monkeypatch, reason, offset
):
    from fs.gw.operating_contract import timestamp

    parts = prepared(tmp_path, monkeypatch)
    current = observe(parts[5], observed_at=parts[6]["now"].isoformat(), **parts[6])
    current.update(catalogRevision=2, latestSequence=2)
    old = deepcopy(current)
    old.update(
        catalogRevision=1,
        latestSequence=1,
        reason=reason,
        result="BLOCKED",
        latestRecordResult="FAIL"
        if reason == "LATEST_FAIL"
        else "PARTIAL"
        if reason == "LATEST_PARTIAL"
        else "PASS",
    )
    captured = timestamp(current["latestCapturedAt"])
    if reason in {"SCOPE_MISSING", "ORIGINAL_MISSING", "LATEST_FAIL", "LATEST_PARTIAL"}:
        old.update(latestHeadDigest=None, latestCapturedAt=None)
    else:
        old.update(
            latestHeadDigest="f" * 64,
            latestCapturedAt=(captured - timedelta(seconds=2)).isoformat(),
        )
    if reason == "SCOPE_MISSING":
        old.update(latestSequence=None, latestRecordResult=None)

    class Connection:
        def execute(self, *a, **k):
            return self

        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "observation": old,
                    "result": "FAIL",
                    "recorded_at": captured + timedelta(seconds=offset),
                }
            ]

    data = SimpleNamespace(
        result="PARTIAL",
        metrics=SimpleNamespace(
            acceptance_diagnostics=SimpleNamespace(
                restore_recheck=SimpleNamespace(
                    envelope={"catalogObservation": current}
                )
            )
        ),
    )
    if offset < 0:
        require_history(Connection(), data, workspace_id=1, generation_id=1)
    else:
        with pytest.raises(ApiError) as rejected:
            require_history(Connection(), data, workspace_id=1, generation_id=1)
        assert rejected.value.code == "OPERATING_RECOVERY_REQUIRED"
