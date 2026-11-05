"""Execution-time restore checks are bounded observations, never live acceptance."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from fs.common.errors import ApiError
from fs.gw.acceptance_reconciliation import sign_reconciliation
from test_gw_acceptance_collection import fixture as source_fixture
from test_gw_acceptance_collection import signed
from test_gw_operating_contract import NOW, envelope, verify


def observation():
    return {
        "version": 1,
        "scope": "RESTORED_CHECKPOINT_RESTRICTIONS",
        "observedAt": NOW.isoformat(),
        "clockToleranceSeconds": 30,
        "backupRunId": str(uuid4()),
        "checkpointRunId": str(uuid4()),
        "backupManifestDigest": "a" * 64,
        "checkpointDigest": "b" * 64,
        "checkpointManifestDigest": "c" * 64,
        "sourceIdentity": "d" * 64,
        "targetIdentity": "e" * 64,
        "stateDigest": "f" * 64,
        "connectionLimitZero": True,
        "publicConnectRevoked": True,
        "dbRevisionMatches": True,
        "unrevokedSessions": 0,
        "pendingChallenges": 0,
        "coreViolations": 0,
        "gwViolations": 0,
        "hrViolations": 0,
        "journalUserViolations": 0,
        "result": "PARTIAL",
        "revocationsComplete": False,
        "liveCompanyAcceptance": False,
        "releaseAuthorized": False,
        "currentTargetStateVerified": False,
    }


def payload():
    return envelope() | {
        "kind": "RESTORE",
        "result": "PARTIAL",
        "metrics": {
            "sessionsInvalidated": True,
            "revocationsReapplied": False,
            "twoAccountChecks": False,
            "failedCheckCount": 1,
            "restoreDiagnostics": {
                "version": 2,
                "databaseClosed": True,
                "dbRevisionMatches": True,
                "checkpointRestrictionsApplied": True,
                "checkpointCompletenessConfirmed": False,
                "journalCandidateIntents": 0,
                "journalUnconfirmedIntents": 0,
                "journalQuarantinedScopes": 0,
                "executionObservation": observation(),
            },
        },
    }


def test_new_and_old_contracts_keep_partial_and_observe_only_execution_time():
    p = payload()
    data = verify(p)
    assert data.metrics.restore_diagnostics.version == 2
    assert not data.metrics.restore_diagnostics.execution_observation.current_target_state_verified
    old = deepcopy(p)
    old["metrics"]["restoreDiagnostics"].pop("executionObservation")
    old["metrics"]["restoreDiagnostics"]["version"] = 1
    assert verify(old).result == "PARTIAL"


@pytest.mark.parametrize(
    "change",
    [
        "pass",
        "completion",
        "live",
        "release",
        "current-target",
        "integer-flag",
        "float-version",
        "no-timezone",
        "future",
        "before-start",
        "manifest",
        "same-database",
        "run-reuse",
        "negative-count",
        "bool-count",
        "string-count",
        "unknown-field",
        "positive-core",
        "positive-gw",
        "positive-hr",
        "positive-journal",
        "pending",
        "session",
        "public-connect",
        "connection-limit",
        "db-head",
        "session-metric",
        "revocations",
        "two-accounts",
        "completeness",
    ],
)
def test_invalid_or_promoted_observation_cannot_be_resigned(change):
    p = payload()
    diag = p["metrics"]["restoreDiagnostics"]
    obs = diag["executionObservation"]
    if change == "pass":
        p["result"] = "PASS"
    elif change in {"completion", "live", "release", "current-target", "integer-flag"}:
        key = {
            "completion": "revocationsComplete",
            "live": "liveCompanyAcceptance",
            "release": "releaseAuthorized",
            "current-target": "currentTargetStateVerified",
            "integer-flag": "releaseAuthorized",
        }[change]
        obs[key] = 0 if change == "integer-flag" else True
    elif change == "float-version":
        obs["version"] = 1.0
    elif change == "no-timezone":
        obs["observedAt"] = NOW.replace(tzinfo=None).isoformat()
    elif change == "future":
        obs["observedAt"] = (NOW + timedelta(seconds=31)).isoformat()
    elif change == "before-start":
        obs["observedAt"] = (NOW - timedelta(hours=1)).isoformat()
    elif change == "manifest":
        obs["backupManifestDigest"] = "f" * 64
    elif change == "same-database":
        obs["targetIdentity"] = obs["sourceIdentity"]
    elif change == "run-reuse":
        obs["backupRunId"] = p["runId"]
    elif change in {"negative-count", "bool-count", "string-count"}:
        obs["coreViolations"] = {
            "negative-count": -1,
            "bool-count": False,
            "string-count": "0",
        }[change]
    elif change == "unknown-field":
        obs["password"] = "never"
    elif change.startswith("positive-"):
        obs[
            {
                "positive-core": "coreViolations",
                "positive-gw": "gwViolations",
                "positive-hr": "hrViolations",
                "positive-journal": "journalUserViolations",
            }[change]
        ] = 1
    elif change == "pending":
        obs["pendingChallenges"] = 1
    elif change == "session":
        obs["unrevokedSessions"] = 1
    elif change == "public-connect":
        obs["publicConnectRevoked"] = False
    elif change == "connection-limit":
        obs["connectionLimitZero"] = False
    elif change == "db-head":
        obs["dbRevisionMatches"] = False
    elif change == "session-metric":
        p["metrics"]["sessionsInvalidated"] = False
    elif change == "revocations":
        p["metrics"]["revocationsReapplied"] = True
    elif change == "two-accounts":
        p["metrics"]["twoAccountChecks"] = True
    else:
        diag["checkpointCompletenessConfirmed"] = True
    with pytest.raises(ApiError):
        verify(p)


def test_tampered_observation_and_wrong_backup_run_are_rejected_by_reconciliation():
    key, payloads, ctx = source_fixture()
    restore = payloads["RESTORE"]
    restore.update(result="PARTIAL", metrics=payload()["metrics"])
    obs = restore["metrics"]["restoreDiagnostics"]["executionObservation"]
    obs.update(
        observedAt=restore["finishedAt"],
        backupManifestDigest=restore["manifestDigest"],
        backupRunId=payloads["BACKUP"]["runId"],
    )
    docs = signed(payloads, key)
    proof = sign_reconciliation(docs, signer=key, signer_id="runner-1", **ctx)
    assert proof["envelope"]["result"] == "PARTIAL"
    docs["RESTORE"]["envelope"]["metrics"]["restoreDiagnostics"][
        "executionObservation"
    ]["stateDigest"] = "0" * 64
    with pytest.raises(ApiError):
        sign_reconciliation(docs, signer=key, signer_id="runner-1", **ctx)
    obs["backupRunId"] = str(uuid4())
    docs = signed(payloads, key)
    with pytest.raises(ApiError):
        sign_reconciliation(docs, signer=key, signer_id="runner-1", **ctx)


def test_clock_tolerance_is_explicit_bounded_and_blocked_observation_stays_failed():
    p = payload()
    obs = p["metrics"]["restoreDiagnostics"]["executionObservation"]
    obs["observedAt"] = (NOW + timedelta(seconds=30)).isoformat()
    assert verify(p).result == "PARTIAL"
    obs["clockToleranceSeconds"] = 31
    with pytest.raises(ApiError):
        verify(p)
    obs["clockToleranceSeconds"] = 30
    obs["pendingChallenges"] = 1
    obs["result"] = "BLOCKED"
    p["result"] = "FAIL"
    assert verify(p).result == "FAIL"
