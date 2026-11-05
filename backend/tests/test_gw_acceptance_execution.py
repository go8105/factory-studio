"""Exercise the adapter with signed originals, never a report's own PASS claim."""

import base64
from copy import deepcopy

import pytest
from fs.common.errors import ApiError
from fs.gw.acceptance_contract import attach
from fs.gw.acceptance_execution import execute
from fs.gw.launch_gate import build
from fs.gw.operating_contract import canonical
from fs.gw.readiness import SOURCE_FIELD
from test_gw_acceptance_collection import registered_fixture
from test_gw_launch_gate import inputs


def test_twelve_conditions_share_closed_boundary_and_never_support_pass():
    gate = build(**inputs())
    contract = gate["acceptanceContract"]
    assert contract["result"] == "PARTIAL"
    assert not any(
        contract[k]
        for k in ("passSupported", "liveCompanyAcceptance", "releaseAuthorized")
    )
    live = [
        c for c in gate["checks"] if c["verification"]["mode"] == "LIVE_ENVIRONMENT"
    ]
    assert len(live) == 4 and all(c["state"] == "UNVERIFIED" for c in live)
    assert all(
        c["verification"]["automaticScope"] and c["verification"]["remainingScope"]
        for c in gate["checks"]
    )
    with pytest.raises(ValueError):
        attach(gate["checks"][:-1])


def test_adapter_calls_original_verifiers_and_does_not_promote_pair_to_acceptance():
    _, rows, ctx = registered_fixture()
    pair, checks = execute(rows, connection=None, policy_id=1, **ctx)
    assert pair["result"] == "PARTIAL" and not pair["ready"]
    assert [c["state"] for c in checks] == ["RECORDED_PASS", "RECORDED_PASS", "MISSING"]


@pytest.mark.parametrize(
    "change,expected",
    [
        ("fail", "FAILED"),
        ("partial", "PARTIAL"),
        ("legacy", "LEGACY_UNVERIFIED"),
        ("tamper", "INVALID"),
        ("policy", "STALE"),
        ("version", "STALE"),
        ("revoked", "INVALID"),
    ],
)
@pytest.mark.parametrize("reverse", [False, True])
def test_current_adapter_never_uses_old_success(change, expected, reverse):
    key, rows, ctx = registered_fixture()
    newer = deepcopy(rows[1])
    newer["id"] += 100
    if change in {"fail", "partial"}:
        data = newer["metrics"][SOURCE_FIELD]
        data["result"] = newer["result"] = "FAIL" if change == "fail" else "PARTIAL"
        newer["signature"] = base64.b64encode(key.sign(canonical(data))).decode()
    elif change == "legacy":
        newer["metrics"] = {}
    elif change == "tamper":
        newer["manifest_digest"] = "f" * 64
    elif change == "policy":
        newer["policy_revision_id"] += 1
    elif change == "version":
        newer["code_revision"] = "f" * 40
    else:
        ctx["public_keys"] = {}
    candidates = [*rows, newer]
    if reverse:
        candidates.reverse()
    pair, checks = execute(candidates, connection=None, policy_id=1, **ctx)
    assert next(c for c in checks if c["kind"] == "RESTORE")["state"] == expected
    assert pair["result"] == "BLOCKED" and not pair["backupRestorePairVerified"]


@pytest.mark.parametrize("field", ["workspace_id", "generation_id"])
def test_foreign_scope_is_rejected_before_any_source_can_be_used(field):
    _, rows, ctx = registered_fixture()
    rows[0][field] += 1
    with pytest.raises(ApiError):
        execute(rows, connection=None, policy_id=1, **ctx)


def test_no_policy_is_explicit_and_does_not_claim_any_verified_original():
    _, rows, ctx = registered_fixture()
    ctx["policy"] = None
    pair, checks = execute(rows, connection=None, policy_id=None, **ctx)
    assert pair["reason"] == "POLICY_REQUIRED"
    assert all(
        c["state"] == "POLICY_REQUIRED" and not c["signatureVerified"] for c in checks
    )


def test_live_completion_flags_cannot_be_attached_as_valid_execution():
    gate = build(**inputs())
    next(c for c in gate["checks"] if c["code"] == "EXTERNAL_STORAGE")["state"] = (
        "CONFIRMED"
    )
    with pytest.raises(ValueError, match="live acceptance"):
        attach(gate["checks"])
