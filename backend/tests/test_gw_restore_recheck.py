"""Fresh signatures cannot promote, replace, or outlive exact restore originals."""

import base64
import json
from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from test_gw_acceptance_collection import fixture as sources
from test_gw_acceptance_collection import signed
from test_gw_restore_observation import payload as restore_payload

from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.evidence_trust import load
from fs.gw.operating_contract import canonical, verify_evidence
from fs.gw.restore_recheck import sign, verify


def prepared():
    source_key, payloads, ctx = sources()
    collector, rechecker = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    restore = payloads["RESTORE"]
    restore.update(result="PARTIAL", metrics=restore_payload()["metrics"])
    obs = restore["metrics"]["restoreDiagnostics"]["executionObservation"]
    obs.update(
        backupRunId=payloads["BACKUP"]["runId"],
        backupManifestDigest=restore["manifestDigest"],
        observedAt=restore["finishedAt"],
    )
    keys = {"runner-1": source_key, "collector": collector, "rechecker": rechecker}
    uses = {
        "runner-1": ["BACKUP", "RESTORE"],
        "collector": ["ACCEPTANCE_RECONCILIATION"],
        "rechecker": ["RESTORE_RECHECK"],
    }
    public = json.dumps(
        {
            k: base64.b64encode(v.public_key().public_bytes_raw()).decode()
            for k, v in keys.items()
        }
    )
    scopes = {
        "version": 1,
        "keys": {
            k: {"workspaceIds": [str(ctx["workspace_id"])], "purposes": uses[k]}
            for k in keys
        },
    }
    ctx["public_keys"] = load(public, json.dumps(scopes), mode="COMPANY")
    return signed(payloads, source_key), deepcopy(obs), collector, rechecker, ctx


def recheck(documents, measurement, key, ctx):
    return sign(
        documents["RESTORE"],
        measurement=measurement,
        checked_at=ctx["now"].isoformat(),
        signer=key,
        signer_id="rechecker",
        **ctx,
    )


@pytest.mark.parametrize("mode", ["unchanged", "stronger", "blocked", "unavailable"])
def test_recheck_snapshot_partial_or_fail_never_releases(mode):
    docs, obs, collector, key, ctx = prepared()
    if mode == "stronger":
        obs["stateDigest"] = "0" * 64
    if mode == "blocked":
        obs.update(unrevokedSessions=1, result="BLOCKED", stateDigest="1" * 64)
    if mode == "unavailable":
        obs = None
    document = recheck(docs, obs, key, ctx)
    checked = verify(document, docs["RESTORE"], **ctx)
    assert checked.result == (
        "BLOCKED" if mode in {"blocked", "unavailable"} else "PARTIAL"
    )
    assert checked.target_measured == (mode != "unavailable")
    assert checked.state_matches_execution == (
        None if mode == "unavailable" else mode == "unchanged"
    )
    proof = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=document,
        **ctx,
    )
    data = verify_evidence(proof["envelope"], proof["signature"], **ctx)
    assert data.metrics.acceptance_diagnostics.version == 4
    assert data.result == ("FAIL" if checked.result == "BLOCKED" else "PARTIAL")
    assert data.metrics.acceptance_diagnostics.journal_coverage == "UNVERIFIED"


@pytest.mark.parametrize(
    "change",
    [
        "pass",
        "ready",
        "integer-flag",
        "version-float",
        "old",
        "future",
        "other-company",
        "other-policy",
        "other-version",
        "scope-purpose",
        "source",
        "target",
        "checkpoint",
        "digest-claim",
        "fake-unavailable",
        "extra",
        "reuse-run",
        "tamper",
        "wrong-restore",
    ],
)
def test_old_wrong_scope_or_fabricated_recheck_never_passes(change):
    docs, obs, _collector, key, ctx = prepared()
    document = recheck(docs, obs, key, ctx)
    p = document["envelope"]
    if change == "pass":
        p["result"] = "PASS"
    elif change == "ready":
        p["ready"] = True
    elif change == "integer-flag":
        p["ready"] = 0
    elif change == "version-float":
        p["version"] = 1.0
    elif change == "old":
        ctx["now"] += timedelta(minutes=16)
    elif change == "future":
        p["checkedAt"] = (ctx["now"] + timedelta(seconds=31)).isoformat()
    elif change == "other-company":
        p["workspaceId"] = "999"
    elif change == "other-policy":
        p["policyDigest"] = "f" * 64
    elif change == "other-version":
        p["codeRevision"] = "abcdef9"
    elif change == "scope-purpose":
        p["signerKeyId"] = "collector"
    elif change == "source":
        p["restore"]["sourceDigest"] = "f" * 64
    elif change == "target":
        p["targetIdentity"] = "f" * 64
    elif change == "checkpoint":
        p["measurement"]["checkpointDigest"] = "f" * 64
    elif change == "digest-claim":
        p["stateMatchesExecution"] = False
    elif change == "fake-unavailable":
        p["measurement"] = None
    elif change == "extra":
        p["operatorApproved"] = True
    elif change == "reuse-run":
        p["runId"] = p["restore"]["runId"]
    elif change == "wrong-restore":
        docs["RESTORE"]["envelope"]["runId"] = str(uuid4())
    if change != "tamper":
        document["signature"] = base64.b64encode(key.sign(canonical(p))).decode()
    else:
        p["targetIdentity"] = "0" * 64
    with pytest.raises((ValueError, ApiError)):
        verify(document, docs["RESTORE"], **ctx)
