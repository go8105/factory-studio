import base64
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from fs.common.errors import ApiError
from fs.gw.operating_contract import (
    OperatingPolicy,
    backup_is_current,
    canonical,
    verify_evidence,
)

NOW = datetime(2026, 10, 18, 4, 0, tzinfo=UTC)


def policy(**changes):
    return OperatingPolicy.model_validate(
        {"responsiblePersonId": "1", "reason": "합성 운영 기준"} | changes
    )


def envelope():
    return {
        "version": 1,
        "runId": str(uuid4()),
        "workspaceId": "10",
        "generationId": "20",
        "policyDigest": policy().digest(),
        "kind": "BACKUP",
        "startedAt": (NOW - timedelta(minutes=30)).isoformat(),
        "finishedAt": NOW.isoformat(),
        "codeRevision": "c4184e1",
        "dbRevision": "gw_readiness",
        "manifestDigest": "a" * 64,
        "result": "PASS",
        "signerKeyId": "runner-1",
        "metrics": {
            "snapshotStartedAt": (NOW - timedelta(minutes=29)).isoformat(),
            "storageConfirmedAt": NOW.isoformat(),
            "artifactDigest": "b" * 64,
        },
    }


def verify(payload, *, signing_key=None, signature=None, **changes):
    key = signing_key or Ed25519PrivateKey.generate()
    encoded = signature or base64.b64encode(key.sign(canonical(payload))).decode()
    kwargs = {
        "public_keys": {"runner-1": key.public_key().public_bytes_raw()},
        "workspace_id": 10,
        "generation_id": 20,
        "policy": policy(),
        "db_revision": "gw_readiness",
        "code_revision": "c4184e1",
        "now": NOW,
    } | changes
    return verify_evidence(payload, encoded, **kwargs)


@pytest.mark.parametrize(
    "changes",
    [
        {"rpoMinutes": 30},
        {"expectedPeople": True},
        {"expectedPeople": "10"},
        {"reason": "  "},
        {"backupKeepDays": 1},
        {"actorId": "999"},
    ],
)
def test_policy_rejects_invalid_or_actor_override(changes):
    with pytest.raises(ValidationError):
        policy(**changes)


def test_policy_digest_stable_but_changes_with_effective_policy():
    assert policy().digest() == policy().digest()
    assert policy().digest() != policy(rpoMinutes=90).digest()


def test_signed_backup_is_current_from_snapshot_not_completion():
    data = verify(envelope())
    assert backup_is_current(data, policy(), NOW)
    stale = envelope()
    stale["startedAt"] = (NOW - timedelta(hours=2)).isoformat()
    stale["metrics"]["snapshotStartedAt"] = (NOW - timedelta(hours=2)).isoformat()
    assert not backup_is_current(verify(stale), policy(), NOW)


@pytest.mark.parametrize(
    "changes",
    [
        {"workspace_id": 99},
        {"generation_id": 99},
        {"policy": policy(rpoMinutes=90)},
        {"db_revision": "old_head"},
        {"code_revision": "fffffff"},
        {"now": NOW + timedelta(days=31)},
    ],
)
def test_signed_but_wrong_current_context_rejected(changes):
    with pytest.raises(ApiError):
        verify(envelope(), **changes)


def test_signature_tampering_unknown_keys_and_plaintext_override_rejected():
    p = envelope()
    key = Ed25519PrivateKey.generate()
    signature = base64.b64encode(key.sign(canonical(p))).decode()
    changed = deepcopy(p)
    changed["metrics"]["artifactDigest"] = "c" * 64
    with pytest.raises(ApiError):
        verify(changed, signing_key=key, signature=signature)
    for changes in (
        {"signerKeyId": "unknown"},
        {"metrics": {"password": "must-never-be-stored"}},
        {"startedAt": NOW.replace(tzinfo=None).isoformat()},
        {"finishedAt": (NOW + timedelta(minutes=1)).isoformat()},
    ):
        with pytest.raises(ApiError):
            verify(p | changes)


def test_restore_pass_requires_every_measurement_and_target():
    p = envelope() | {
        "kind": "RESTORE",
        "startedAt": (NOW - timedelta(seconds=120)).isoformat(),
        "metrics": {
            "rowHashesMatch": True,
            "foreignKeysValid": True,
            "sessionsInvalidated": True,
            "revocationsReapplied": True,
            "twoAccountChecks": True,
            "lossWindowSeconds": 60,
            "elapsedSeconds": 120,
        },
    }
    assert verify(p).kind == "RESTORE"
    for field, bad in [
        ("rowHashesMatch", False),
        ("foreignKeysValid", False),
        ("sessionsInvalidated", False),
        ("revocationsReapplied", False),
        ("twoAccountChecks", False),
        ("lossWindowSeconds", 3601),
        ("elapsedSeconds", 14401),
        ("elapsedSeconds", 1),
        ("failedCheckCount", 1),
    ]:
        q = deepcopy(p)
        q["metrics"][field] = bad
        with pytest.raises(ApiError):
            verify(q)
    q = deepcopy(p)
    del q["metrics"]["lossWindowSeconds"]
    with pytest.raises(ApiError):
        verify(q)
    failed = deepcopy(p)
    failed["result"] = "FAIL"
    failed["metrics"]["rowHashesMatch"] = False
    assert verify(failed).result == "FAIL"


def diagnostic():
    return {
        "version": 1,
        "databaseClosed": True,
        "dbRevisionMatches": True,
        "checkpointRestrictionsApplied": True,
        "checkpointCompletenessConfirmed": False,
        "journalCandidateIntents": 2,
        "journalUnconfirmedIntents": 1,
        "journalQuarantinedScopes": 1,
    }


def test_signed_partial_restore_carries_measurements_without_pass_promotion():
    data = envelope() | {
        "kind": "RESTORE",
        "result": "PARTIAL",
        "metrics": {"restoreDiagnostics": diagnostic()},
    }
    result = verify(data)
    assert result.result == "PARTIAL"
    assert result.metrics.restore_diagnostics.journal_unconfirmed_intents == 1
    with pytest.raises(ApiError):
        verify(data | {"kind": "BACKUP"})
    data["result"] = "PASS"
    with pytest.raises(ApiError):
        verify(data)


@pytest.mark.parametrize(
    "field,value",
    [
        ("journalUnconfirmedIntents", -1),
        ("journalUnconfirmedIntents", 3),
        ("journalCandidateIntents", "2"),
        ("databaseClosed", 1),
        ("database", "private-location"),
    ],
)
def test_restore_diagnostic_fields_are_closed_typed_and_consistent(field, value):
    data = envelope() | {
        "kind": "RESTORE",
        "result": "PARTIAL",
        "metrics": {"restoreDiagnostics": diagnostic() | {field: value}},
    }
    with pytest.raises(ApiError):
        verify(data)


def test_restore_pass_rejects_contradictory_diagnostics_even_with_valid_measurements():
    details = diagnostic() | {
        "checkpointCompletenessConfirmed": True,
        "journalUnconfirmedIntents": 0,
        "journalQuarantinedScopes": 0,
    }
    payload = envelope() | {
        "kind": "RESTORE",
        "startedAt": (NOW - timedelta(seconds=120)).isoformat(),
        "metrics": {
            "rowHashesMatch": True,
            "foreignKeysValid": True,
            "sessionsInvalidated": True,
            "revocationsReapplied": True,
            "twoAccountChecks": True,
            "lossWindowSeconds": 60,
            "elapsedSeconds": 120,
            "restoreDiagnostics": details,
        },
    }
    assert verify(payload).result == "PASS"
    for field, value in (
        ("databaseClosed", False),
        ("dbRevisionMatches", False),
        ("checkpointRestrictionsApplied", False),
        ("checkpointCompletenessConfirmed", False),
        ("journalUnconfirmedIntents", 1),
        ("journalQuarantinedScopes", 1),
    ):
        changed = deepcopy(payload)
        changed["metrics"]["restoreDiagnostics"][field] = value
        with pytest.raises(ApiError):
            verify(changed)
