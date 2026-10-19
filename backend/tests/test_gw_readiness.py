"""Readiness diagnostics do not hide newer failures or infer whole readiness."""

import base64
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fs.gw.operating_contract import EvidenceEnvelope, OperatingPolicy, canonical
from fs.gw.readiness import SOURCE_FIELD, assess


def sign(row, args):
    payload = {
        "version": 1,
        "runId": str(row["run_id"]),
        "workspaceId": str(row["workspace_id"]),
        "generationId": str(row["generation_id"]),
        "policyDigest": args["policy"].digest(),
        "kind": row["kind"],
        "startedAt": row["started_at"].isoformat(),
        "finishedAt": row["finished_at"].isoformat(),
        "codeRevision": row["code_revision"],
        "dbRevision": row["db_revision"],
        "manifestDigest": row["manifest_digest"],
        "result": row["result"],
        "signerKeyId": row["signer_key_id"],
        "metrics": {k: v for k, v in row["metrics"].items() if k != SOURCE_FIELD},
    }
    row["signature"] = base64.b64encode(
        row["_signer"].sign(canonical(payload))
    ).decode()
    row["metrics"] = {
        **EvidenceEnvelope.model_validate(payload).metrics.model_dump(by_alias=True),
        SOURCE_FIELD: payload,
    }


def fixture():
    now = datetime.now(UTC)
    policy = OperatingPolicy(responsiblePersonId="1", reason="합성 준비 점검")
    row = {
        "kind": "BACKUP",
        "policy_revision_id": 1,
        "workspace_id": 1,
        "generation_id": 2,
        "run_id": uuid4(),
        "code_revision": "abcdef012345",
        "db_revision": "gw_readiness",
        "signer_key_id": "runner",
        "started_at": now - timedelta(seconds=20),
        "finished_at": now - timedelta(seconds=1),
        "manifest_digest": "a" * 64,
        "result": "PASS",
        "metrics": {
            "snapshotStartedAt": (now - timedelta(seconds=19)).isoformat(),
            "storageConfirmedAt": (now - timedelta(seconds=2)).isoformat(),
            "artifactDigest": "b" * 64,
        },
    }
    private = Ed25519PrivateKey.generate()
    row["_signer"] = private
    args = {
        "policy": policy,
        "policy_id": 1,
        "code_revision": "abcdef012345",
        "db_revision": "gw_readiness",
        "public_keys": {"runner": private.public_key().public_bytes_raw()},
        "now": now,
    }
    sign(row, args)
    return row, args


def test_current_backup_is_only_registered_pass_and_other_proofs_missing():
    row, args = fixture()
    checks = assess([row], **args)
    assert [c["state"] for c in checks] == ["RECORDED_PASS", "MISSING", "MISSING"]
    assert "별도" in checks[0]["detail"]
    assert not any("ready" in c for c in checks)


@pytest.mark.parametrize(
    "field,value,state",
    [
        ("policy_revision_id", 2, "STALE"),
        ("code_revision", "1234567", "STALE"),
        ("db_revision", "other", "STALE"),
        ("signer_key_id", "revoked", "INVALID"),
        ("result", "FAIL", "FAILED"),
        ("result", "PARTIAL", "PARTIAL"),
        ("metrics", {}, "LEGACY_UNVERIFIED"),
    ],
)
def test_changed_or_incomplete_evidence_cannot_pass(field, value, state):
    row, args = fixture()
    row[field] = value
    if field == "result":
        sign(row, args)
    assert assess([row], **args)[0]["state"] == state


def test_stale_backup_future_and_expired_proofs():
    row, args = fixture()
    args["now"] += timedelta(hours=2)
    assert assess([row], **args)[0]["state"] == "STALE"
    args["now"] -= timedelta(hours=3)
    assert assess([row], **args)[0]["state"] == "STALE"
    args["now"] += timedelta(days=40)
    assert assess([row], **args)[0]["state"] == "STALE"


def test_latest_failure_does_not_fall_back_to_older_pass_and_acceptance_cannot_pass():
    row, args = fixture()
    failed = row | {"result": "FAIL"}
    sign(failed, args)
    assert assess([failed, row], **args)[0]["state"] == "FAILED"
    acceptance = row | {"kind": "ACCEPTANCE"}
    assert assess([acceptance], **args)[2]["state"] == "INVALID"
    args["policy"] = None
    assert all(c["state"] == "POLICY_REQUIRED" for c in assess([row], **args))


@pytest.mark.parametrize(
    "tamper", ["signature", "source", "metrics", "scope", "run", "key"]
)
def test_source_signature_and_database_fields_are_bound(tamper):
    import copy

    row, args = fixture()
    # Copy JSON only: cryptographic private key objects are not serializable.
    row["metrics"] = copy.deepcopy(row["metrics"])
    if tamper == "signature":
        row["signature"] = "AAAA"
    elif tamper == "source":
        row["metrics"][SOURCE_FIELD]["manifestDigest"] = "f" * 64
    elif tamper == "metrics":
        row["metrics"]["artifactDigest"] = "f" * 64
    elif tamper == "scope":
        row["workspace_id"] = 99
    elif tamper == "run":
        row["run_id"] = uuid4()
    else:
        args["public_keys"] = {
            "runner": Ed25519PrivateKey.generate().public_key().public_bytes_raw()
        }
    check = assess([row], **args)[0]
    assert check["state"] == "INVALID" and not check["signatureVerified"]


def test_missing_source_is_not_reconstructed_and_offset_round_trip_is_valid():
    row, args = fixture()
    assert assess([row], **args)[0]["signatureVerified"]
    # Same instant in DB after timestamptz normalization must still match.
    from datetime import timezone

    row["started_at"] = row["started_at"].astimezone(timezone(timedelta(hours=9)))
    assert assess([row], **args)[0]["signatureVerified"]
    row["metrics"].pop(SOURCE_FIELD)
    check = assess([row], **args)[0]
    assert check["state"] == "LEGACY_UNVERIFIED" and not check["signatureVerified"]


def test_verified_signatures_can_still_have_partial_results():
    row, args = fixture()
    rows = [row]
    for kind in ("RESTORE", "ACCEPTANCE"):
        item = row | {"kind": kind, "result": "PARTIAL", "run_id": uuid4()}
        sign(item, args)
        rows.append(item)
    checks = assess(rows, **args)
    assert all(c["signatureVerified"] for c in checks)
    assert [c["state"] for c in checks] == ["RECORDED_PASS", "PARTIAL", "PARTIAL"]
