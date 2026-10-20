import json

import pytest
from fs.gw.journal_routes import ROUTES, build

SCOPE = {"workspaceId": "10", "generationId": "20", "policyDigest": "a" * 64}
OPS = [
    "company-setup",
    "binding.None.request",
    "binding.12.accept",
    "binding.12.cancel",
    "binding.12.suspend",
    "binding.12.resume",
    "roles.12",
]


def inputs():
    records = [
        {
            "digest": f"{i:064x}",
            "payload": {
                "workspaceId": 10,
                "generationId": 20,
                "coverage": "gw.company.intent.v2",
                "operation": op,
                "snapshot": "private",
            },
        }
        for i, op in enumerate(OPS, 1)
    ]
    return records, {r["digest"]: "AUDIT_CONFIRMED" for r in records}


def run(records, dispositions):
    return build(
        records,
        dispositions,
        scope=SCOPE,
        code_revision="abcdef0",
        db_revision="gw_readiness",
        head="f" * 64,
    )


def test_all_observed_does_not_certify_execution_revision_or_revocation():
    result = run(*inputs())
    assert result["result"] == "PARTIAL" and len(result["routes"]) == len(ROUTES)
    assert all(r["state"] == "COMMIT_OBSERVED" for r in result["routes"])
    for field in (
        "executionRevisionVerified",
        "completenessConfirmed",
        "revocationsReapplied",
        "releaseAuthorized",
    ):
        assert result[field] is False
    assert "private" not in json.dumps(result) and "binding.12" not in json.dumps(
        result
    )
    assert all(
        r["storageFailureRollback"] == r["restoredAccessDenial"] == "UNVERIFIED"
        for r in result["routes"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "company",
        "generation",
        "boolean",
        "legacy",
        "malformed",
        "unknown",
        "abort",
        "unknown-state",
        "late-failure",
    ],
)
def test_another_scope_operation_or_old_success_cannot_fill_route(change):
    records, states = inputs()
    record = records[4]
    if change == "company":
        record["payload"]["workspaceId"] = 11
    elif change == "generation":
        record["payload"]["generationId"] = 21
    elif change == "boolean":
        record["payload"]["workspaceId"] = True
    elif change == "legacy":
        record["payload"]["coverage"] = "gw.company_identity.intent.v1"
    elif change == "malformed":
        record["payload"]["operation"] = "binding.012.suspend"
    elif change == "unknown":
        record["payload"]["operation"] = "binding.12.arbitrary"
    elif change == "abort":
        states[record["digest"]] = "ABORT_CONFIRMED"
    elif change == "unknown-state":
        states[record["digest"]] = "UNKNOWN"
    else:
        extra = {**record, "digest": "e" * 64}
        records.append(extra)
        states[extra["digest"]] = "COMMITTED_WITHOUT_AUDIT"
    result = run(records, states)
    assert result["result"] == "BLOCKED"
    route = next(r for r in result["routes"] if r["route"] == "BINDING_SUSPEND")
    assert route["state"] != "COMMIT_OBSERVED"


def test_empty_routes_remain_missing():
    assert all(r["state"] == "MISSING" for r in run([], {})["routes"])
