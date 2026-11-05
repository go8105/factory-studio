"""Only current scoped observations; signatures never promote whole acceptance."""

import base64
import json
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.gw.evidence_trust import load
from fs.gw.journal_observation import JournalObservation, verify
from fs.gw.operating_contract import canonical
from pydantic import ValidationError

NOW = datetime(2026, 10, 23, 3, 0, tzinfo=UTC)


def fixture():
    key = Ed25519PrivateKey.generate()
    payload = {
        "version": 1,
        "kind": "JOURNAL_OBSERVATION",
        "scope": "GW_COMPANY_JOURNAL_SCOPE_V1",
        "runId": str(uuid4()),
        "workspaceId": "10",
        "generationId": "20",
        "policyDigest": "a" * 64,
        "contextDigest": "b" * 64,
        "codeRevision": "abc1234",
        "dbRevision": "test_head",
        "sourceIdentity": "c" * 64,
        "observedAt": NOW.isoformat(),
        "sourceHead": "d" * 64,
        "scopeRecordsDigest": "e" * 64,
        "scopeRecords": 2,
        "missingTransactionProofs": 0,
        "dispositions": {
            "AUDIT_CONFIRMED": 1,
            "ABORT_CONFIRMED": 1,
            "PENDING": 0,
            "SOURCE_MISMATCH": 0,
            "COMMITTED_WITHOUT_AUDIT": 0,
            "UNKNOWN": 0,
        },
        "result": "PARTIAL",
        "signerKeyId": "observer",
        **{
            k: False
            for k in (
                "ready",
                "completenessConfirmed",
                "revocationsReapplied",
                "liveCompanyAcceptance",
                "releaseAuthorized",
                "executionRevisionVerified",
                "independentStorageConfirmed",
            )
        },
    }
    public = json.dumps(
        {"observer": base64.b64encode(key.public_key().public_bytes_raw()).decode()}
    )
    scopes = {
        "version": 1,
        "keys": {
            "observer": {"workspaceIds": ["10"], "purposes": ["JOURNAL_OBSERVATION"]}
        },
    }
    trust = load(public, json.dumps(scopes), mode="COMPANY")
    return key, payload, trust, public, scopes


@pytest.mark.parametrize(
    "change",
    [
        "none",
        "pass",
        "ready",
        "integer-flag",
        "bool-version",
        "float-version",
        "count",
        "bool-count",
        "negative-count",
        "unknown-count",
        "missing-count",
        "missing-proof",
        "pending",
        "source-mismatch",
        "committed-no-audit",
        "unknown",
        "future",
        "expired",
        "no-timezone",
        "bad-run",
        "other-company",
        "other-version",
        "wrong-key-use",
        "unscoped",
        "extra",
        "tampered",
        "bad-signature",
    ],
)
def test_signature_scope_freshness_and_bounded_measurements(change):
    key, payload, trust, public, scopes = fixture()
    current = NOW
    if change == "pass":
        payload["result"] = "PASS"
    elif change == "ready":
        payload["ready"] = True
    elif change == "integer-flag":
        payload["ready"] = 0
    elif change == "bool-version":
        payload["version"] = True
    elif change == "float-version":
        payload["version"] = 1.0
    elif change == "count":
        payload["scopeRecords"] = 3
    elif change == "bool-count":
        payload["scopeRecords"] = True
    elif change == "negative-count":
        payload["dispositions"]["PENDING"] = -1
    elif change == "unknown-count":
        payload["dispositions"]["OTHER"] = 0
    elif change == "missing-count":
        payload["dispositions"].pop("UNKNOWN")
    elif change == "missing-proof":
        payload["missingTransactionProofs"] = 1
    elif change in {"pending", "source-mismatch", "committed-no-audit", "unknown"}:
        name = {
            "pending": "PENDING",
            "source-mismatch": "SOURCE_MISMATCH",
            "committed-no-audit": "COMMITTED_WITHOUT_AUDIT",
            "unknown": "UNKNOWN",
        }[change]
        payload["dispositions"]["ABORT_CONFIRMED"] = 0
        payload["dispositions"][name] = 1
    elif change == "future":
        current -= timedelta(seconds=1)
    elif change == "expired":
        current += timedelta(minutes=15, seconds=1)
    elif change == "no-timezone":
        payload["observedAt"] = "2026-10-23T03:00:00"
    elif change == "bad-run":
        payload["runId"] = "invalid"
    elif change == "other-company":
        scopes["keys"]["observer"]["workspaceIds"] = ["11"]
        trust = load(public, json.dumps(scopes))
    elif change == "other-version":
        payload["codeRevision"] = "fffffff"
    elif change == "wrong-key-use":
        scopes["keys"]["observer"]["purposes"] = ["BACKUP"]
        trust = load(public, json.dumps(scopes))
    elif change == "unscoped":
        trust = load(public)
    elif change == "extra":
        payload["dbUrl"] = "must not be copied"
    signature = base64.b64encode(key.sign(canonical(payload))).decode()
    if change == "tampered":
        payload["sourceHead"] = "f" * 64
    elif change == "bad-signature":
        signature = base64.b64encode(b"x" * 64).decode()
    document = {"envelope": payload, "signature": signature}
    if change == "none":
        data = verify(
            document,
            public_keys=trust,
            company_id=10,
            code_revision="abc1234",
            now=current,
        )
        assert data.result == "PARTIAL" and data.ready is False
    else:
        from fs.core.backup import BackupError

        with pytest.raises((ValueError, InvalidSignature, BackupError)):
            verify(
                document,
                public_keys=trust,
                company_id=10,
                code_revision="abc1234",
                now=current,
            )


def test_unresolved_and_empty_observations_can_only_be_blocked():
    _, payload, _, _, _ = fixture()
    payload["dispositions"]["AUDIT_CONFIRMED"] = 0
    payload["dispositions"]["PENDING"] = 1
    payload["result"] = "BLOCKED"
    assert JournalObservation.model_validate(payload).result == "BLOCKED"
    empty = deepcopy(payload)
    empty.update(
        scopeRecords=0, dispositions={key: 0 for key in payload["dispositions"]}
    )
    assert JournalObservation.model_validate(empty).result == "BLOCKED"
    empty["result"] = "PARTIAL"
    with pytest.raises(ValidationError):
        JournalObservation.model_validate(empty)
