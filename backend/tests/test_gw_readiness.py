"""Readiness diagnostics do not hide newer failures or infer whole readiness."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from fs.gw.operating_contract import OperatingPolicy
from fs.gw.readiness import assess


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
    args = {
        "policy": policy,
        "policy_id": 1,
        "code_revision": "abcdef012345",
        "db_revision": "gw_readiness",
        "signer_ids": {"runner"},
        "now": now,
    }
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
        ("metrics", {}, "INVALID"),
    ],
)
def test_changed_or_incomplete_evidence_cannot_pass(field, value, state):
    row, args = fixture()
    row[field] = value
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
    assert assess([failed, row], **args)[0]["state"] == "FAILED"
    acceptance = row | {"kind": "ACCEPTANCE"}
    assert assess([acceptance], **args)[2]["state"] == "INVALID"
    args["policy"] = None
    assert all(c["state"] == "POLICY_REQUIRED" for c in assess([row], **args))
