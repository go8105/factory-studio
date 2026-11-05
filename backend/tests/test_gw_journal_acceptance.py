"""Signed observations remain bounded partial diagnostics, never whole acceptance."""

import base64
import json
from copy import deepcopy
from datetime import timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import (
    sign_reconciliation,
    verify_registered_sources,
)
from fs.gw.evidence_trust import load
from fs.gw.operating_contract import (
    acceptance_context_digest,
    canonical,
    verify_evidence,
)
from pydantic import ValidationError
from test_gw_acceptance_collection import fixture as sources
from test_gw_acceptance_collection import signed
from test_gw_journal_observation import fixture as observation


def prepared():
    source_key, payloads, ctx = sources()
    observer, payload, _, _, _ = observation()
    collector = Ed25519PrivateKey.generate()
    keys = {"runner-1": source_key, "observer": observer, "collector": collector}
    scopes = {
        "version": 1,
        "keys": {
            name: {"workspaceIds": [str(ctx["workspace_id"])], "purposes": purposes}
            for name, purposes in [
                ("runner-1", ["BACKUP", "RESTORE"]),
                ("observer", ["JOURNAL_OBSERVATION"]),
                ("collector", ["ACCEPTANCE_RECONCILIATION"]),
            ]
        },
    }
    ctx["public_keys"] = load(
        json.dumps(
            {
                name: base64.b64encode(key.public_key().public_bytes_raw()).decode()
                for name, key in keys.items()
            }
        ),
        json.dumps(scopes),
        mode="COMPANY",
    )
    payload.update(
        workspaceId=str(ctx["workspace_id"]),
        generationId=str(ctx["generation_id"]),
        policyDigest=ctx["policy"].digest(),
        codeRevision=ctx["code_revision"],
        dbRevision=ctx["db_revision"],
        observedAt=ctx["now"].isoformat(),
        contextDigest=acceptance_context_digest(
            **{
                k: ctx[k]
                for k in (
                    "workspace_id",
                    "generation_id",
                    "policy",
                    "code_revision",
                    "db_revision",
                )
            }
        ),
    )
    return signed(payloads, source_key), collector, observer, payload, ctx


def build(documents, collector, observer, payload, ctx):
    document = {
        "envelope": payload,
        "signature": base64.b64encode(observer.sign(canonical(payload))).decode(),
    }
    return sign_reconciliation(
        documents,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        journal_observation=document,
        **ctx,
    )


@pytest.mark.parametrize("blocked", [False, True])
def test_nested_original_binds_signature_and_only_partial_or_fail(blocked):
    docs, collector, observer, payload, ctx = prepared()
    if blocked:
        payload["dispositions"]["AUDIT_CONFIRMED"] -= 1
        payload["dispositions"]["PENDING"] += 1
        payload["result"] = "BLOCKED"
    proof = build(docs, collector, observer, payload, ctx)
    data = verify_evidence(proof["envelope"], proof["signature"], **ctx)
    assert data.result == ("FAIL" if blocked else "PARTIAL")
    assert data.metrics.acceptance_diagnostics.version == 3
    for name in [
        "external_storage",
        "journal_coverage",
        "live_company",
        "final_release",
    ]:
        assert getattr(data.metrics.acceptance_diagnostics, name) == "UNVERIFIED"
    # Signature-only verification cannot replace the live connection check.
    with pytest.raises(ApiError):
        verify_registered_sources(data, [], policy_id=1, **ctx)


@pytest.mark.parametrize(
    "change",
    [
        "tamper",
        "wrong-purpose",
        "wrong-company",
        "wrong-generation",
        "wrong-policy",
        "wrong-context",
        "wrong-db",
        "expired",
        "future",
        "pass",
        "true-flag",
        "reuse-run",
        "extra",
        "standalone-file-mode",
        "integer-version",
    ],
)
def test_invalid_nested_observation_cannot_be_resigned_as_acceptance(change):
    docs, collector, observer, payload, ctx = prepared()
    if change == "wrong-purpose":
        payload["signerKeyId"] = "collector"
        observer = collector
    elif change.startswith("wrong-"):
        key, value = {
            "wrong-company": ("workspaceId", "999"),
            "wrong-generation": ("generationId", "999"),
            "wrong-policy": ("policyDigest", "f" * 64),
            "wrong-context": ("contextDigest", "f" * 64),
            "wrong-db": ("dbRevision", "old_head"),
        }[change]
        payload[key] = value
    elif change == "expired":
        payload["observedAt"] = (ctx["now"] - timedelta(minutes=16)).isoformat()
    elif change == "future":
        payload["observedAt"] = (ctx["now"] + timedelta(seconds=1)).isoformat()
    elif change == "pass":
        payload["result"] = "PASS"
    elif change == "true-flag":
        payload["ready"] = True
    elif change == "reuse-run":
        payload["runId"] = docs["BACKUP"]["envelope"]["runId"]
    elif change == "extra":
        payload["releaseApproval"] = True
    elif change == "integer-version":
        payload["version"] = True
    if change == "tamper":
        proof = build(docs, collector, observer, payload, ctx)
        envelope = deepcopy(proof["envelope"])
        envelope["metrics"]["acceptanceDiagnostics"]["journalObservation"][
            "signature"
        ] = base64.b64encode(b"x" * 64).decode()
        signature = base64.b64encode(collector.sign(canonical(envelope))).decode()
        with pytest.raises(ApiError):
            verify_evidence(envelope, signature, **ctx)
        return
    if change == "standalone-file-mode":
        with pytest.raises(ApiError):
            sign_reconciliation(
                docs,
                signer=collector,
                signer_id="collector",
                journal_observation={"envelope": payload, "signature": ""},
                **ctx,
            )
        return
    with pytest.raises((ApiError, ValidationError)):
        build(docs, collector, observer, payload, ctx)
