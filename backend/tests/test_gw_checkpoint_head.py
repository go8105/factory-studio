"""Signed capture times bind a specific checkpoint, never prove an external latest list."""

import base64
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.evidence_trust import load
from fs.gw.operating_contract import canonical, timestamp, verify_evidence
from fs.gw.restore_recheck import parse_envelope, sign, verify
from test_gw_restore_recheck import prepared
from test_gw_source_checkpoint import observation

CONTEXT = b"FS-OPERATOR-BUNDLE-v1\0"


@pytest.mark.parametrize("version", [[], {}, True, 3.0, "3", None])
def test_malformed_version_is_validation_error(version):
    with pytest.raises(ValueError):
        parse_envelope({"version": version})


@pytest.mark.parametrize("with_source", [False, True])
def test_existing_versions_keep_identical_signed_payloads(with_source):
    docs, obs, _collector, key, ctx = prepared()
    document = sign(
        docs["RESTORE"],
        measurement=obs,
        source_observation=observation(obs, ctx) if with_source else None,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )
    original = deepcopy(document)
    parsed = verify(document, docs["RESTORE"], **ctx)
    assert parsed.version == (2 if with_source else 1)
    assert canonical(parsed.model_dump(by_alias=True)) == canonical(
        original["envelope"]
    )
    assert document == original


def prepared_head():
    docs, obs, collector, rechecker, ctx = prepared()
    checkpoint = Ed25519PrivateKey.generate()
    public = {k: base64.b64encode(v).decode() for k, v in ctx["public_keys"].items()}
    public["checkpoint"] = base64.b64encode(
        checkpoint.public_key().public_bytes_raw()
    ).decode()
    uses = {
        "runner-1": ["BACKUP", "RESTORE"],
        "collector": ["ACCEPTANCE_RECONCILIATION"],
        "rechecker": ["RESTORE_RECHECK"],
        "checkpoint": ["CHECKPOINT"],
    }
    scopes = {
        "version": 1,
        "keys": {
            k: {"workspaceIds": [str(ctx["workspace_id"])], "purposes": v}
            for k, v in uses.items()
        },
    }
    ctx["public_keys"] = load(json.dumps(public), json.dumps(scopes), mode="COMPANY")
    payload = {
        "version": 1,
        "kind": "CHECKPOINT_HEAD",
        "scope": {
            "workspaceId": str(ctx["workspace_id"]),
            "generationId": str(ctx["generation_id"]),
            "policyDigest": ctx["policy"].digest(),
        },
        "backupRunId": obs["backupRunId"],
        "runId": obs["checkpointRunId"],
        "checkpointDigest": obs["checkpointDigest"],
        "capturedAt": docs["RESTORE"]["envelope"]["startedAt"],
    }
    head = {
        "payload": payload,
        "signature": base64.b64encode(
            checkpoint.sign(CONTEXT + canonical(payload))
        ).decode(),
        "signerKeyId": "checkpoint",
    }
    return docs, obs, collector, rechecker, checkpoint, head, ctx


def checked_head():
    docs, obs, collector, key, checkpoint, head, ctx = prepared_head()
    document = sign(
        docs["RESTORE"],
        measurement=obs,
        source_observation=observation(obs, ctx),
        checkpoint_head=head,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )
    return document, docs, collector, key, checkpoint, ctx


def test_head_signature_binds_capture_without_changing_old_restore_bytes():
    doc, docs, collector, _key, _checkpoint, ctx = checked_head()
    before = canonical(docs["RESTORE"])
    data = verify(doc, docs["RESTORE"], **ctx)
    assert data.version == 3 and data.result == "PARTIAL"
    assert (
        data.checkpoint_head.payload.checkpoint_digest
        == data.measurement.checkpoint_digest
    )
    result = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=doc,
        **ctx,
    )
    accepted = verify_evidence(result["envelope"], result["signature"], **ctx)
    assert (
        accepted.result == "PARTIAL"
        and accepted.metrics.acceptance_diagnostics.final_release == "UNVERIFIED"
    )
    assert canonical(docs["RESTORE"]) == before
    assert data.model_dump(by_alias=True) == doc["envelope"]


@pytest.mark.parametrize(
    "change",
    [
        "workspace",
        "generation",
        "policy",
        "backup",
        "checkpoint",
        "digest",
        "late",
        "old",
        "float",
        "extra",
        "tamper",
        "purpose",
        "revoked",
        "source-omitted",
        "head-omitted",
        "unknown-head",
    ],
)
def test_signed_head_must_match_current_scope_original_and_clock(change):
    doc, docs, _collector, key, checkpoint, ctx = checked_head()
    payload = doc["envelope"]["checkpointHead"]["payload"]
    if change in {"workspace", "generation", "policy"}:
        payload["scope"][
            {
                "workspace": "workspaceId",
                "generation": "generationId",
                "policy": "policyDigest",
            }[change]
        ] = "f" * 64 if change == "policy" else "999"
    elif change in {"backup", "checkpoint"}:
        payload["backupRunId" if change == "backup" else "runId"] = str(uuid4())
    elif change == "digest":
        payload["checkpointDigest"] = "0" * 64
    elif change in {"late", "old"}:
        start = timestamp(docs["RESTORE"]["envelope"]["startedAt"])
        payload["capturedAt"] = (
            start + timedelta(seconds=31)
            if change == "late"
            else start - timedelta(minutes=ctx["policy"].rpo_minutes, seconds=31)
        ).isoformat()
    elif change == "float":
        payload["version"] = 1.0
    elif change == "extra":
        payload["latestIndependentlyVerified"] = True
    elif change == "source-omitted":
        doc["envelope"].pop("sourceObservation")
    elif change == "head-omitted":
        doc["envelope"].pop("checkpointHead")
    elif change == "unknown-head":
        doc["envelope"]["checkpointHead"]["url"] = "private.invalid"
    elif change == "purpose":
        doc["envelope"]["checkpointHead"]["signerKeyId"] = "rechecker"
    elif change == "revoked":
        ctx["public_keys"] = load(
            json.dumps(
                {
                    k: base64.b64encode(v).decode()
                    for k, v in ctx["public_keys"].items()
                    if k != "checkpoint"
                }
            ),
            json.dumps(
                {
                    "version": 1,
                    "keys": {
                        k: {
                            "workspaceIds": [str(ctx["workspace_id"])],
                            "purposes": ["ACCEPTANCE_RECONCILIATION"]
                            if k == "collector"
                            else ["RESTORE_RECHECK"]
                            if k == "rechecker"
                            else ["BACKUP", "RESTORE"],
                        }
                        for k in ctx["public_keys"]
                        if k != "checkpoint"
                    },
                }
            ),
            mode="COMPANY",
        )
    if "checkpointHead" in doc["envelope"]:
        doc["envelope"]["checkpointHead"]["signature"] = base64.b64encode(
            checkpoint.sign(CONTEXT + canonical(payload))
        ).decode()
    if change == "tamper":
        payload["capturedAt"] = (ctx["now"] - timedelta(seconds=1)).isoformat()
    doc["signature"] = base64.b64encode(key.sign(canonical(doc["envelope"]))).decode()
    with pytest.raises((ValueError, KeyError)):
        verify(doc, docs["RESTORE"], **ctx)


@pytest.mark.parametrize("seconds", [-30, 30])
def test_capture_time_allows_only_declared_restore_clock_tolerance(seconds):
    docs, obs, _collector, key, checkpoint, head, ctx = prepared_head()
    head["payload"]["capturedAt"] = (
        timestamp(docs["RESTORE"]["envelope"]["startedAt"]) + timedelta(seconds=seconds)
    ).isoformat()
    head["signature"] = base64.b64encode(
        checkpoint.sign(CONTEXT + canonical(head["payload"]))
    ).decode()
    result = sign(
        docs["RESTORE"],
        measurement=obs,
        source_observation=observation(obs, ctx),
        checkpoint_head=head,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )
    assert verify(result, docs["RESTORE"], **ctx).result == "PARTIAL"
