"""Counterexamples for restrictive credential/permission checkpoint comparisons."""

from copy import deepcopy

import pytest
from fs.core.security.backup import restriction_violations
from fs.hr.backup import restriction_violations as hr_violations


def state():
    return {
        "users": [
            {
                "id": 1,
                "status": "active",
                "disabled": False,
                "security_version": 1,
                "identity": "identity-digest",
                "credential": "credential-digest",
            }
        ],
        "roles": [{"user_id": 1, "role_id": 1}],
        "workspaces": [
            {
                "id": 2,
                "owner_user_id": 1,
                "active_generation_id": 3,
                "workspace_kind": "COMPANY",
            }
        ],
        "companies": [{"workspace_id": 2, "status": "ACTIVE"}],
        "members": [
            {
                "id": 4,
                "workspace_id": 2,
                "user_id": 1,
                "role": "OWNER",
                "is_active": True,
            }
        ],
        "factors": [
            {
                "id": 5,
                "user_id": 1,
                "state": "ACTIVE",
                "version": 1,
                "last_used_step": 7,
                "secret": "secret-fingerprint",
            }
        ],
        "codes": [
            {"id": 6, "user_id": 1, "factor_id": 5, "used": False, "revoked": False}
        ],
        "sso": [{"id": 7, "user_id": 1, "state": "ACTIVE", "version": 1}],
        "throttles": [
            {
                "bucket_hash": "bucket",
                "window": "2026-10-23 00:00:00+00:00",
                "fail_count": 5,
                "locked": "2026-10-23 00:10:00+00:00",
            }
        ],
    }


@pytest.mark.parametrize(
    "change",
    [
        "credential",
        "identity",
        "security-version",
        "new-role",
        "company-role",
        "company-stopped",
        "workspace-generation",
        "factor-secret",
        "factor-version",
        "otp-step",
        "pending-factor",
        "recovery-used",
        "sso-version",
        "throttle-count",
        "throttle-lock",
        "journal-user",
    ],
)
def test_effective_permission_or_replay_counter_drift_is_not_a_success(change):
    original = state()
    checkpoint = deepcopy(original)
    current = deepcopy(original)
    if change in {"credential", "identity"}:
        current["users"][0][change] = "different-fingerprint"
    elif change == "security-version":
        current["users"][0]["security_version"] = 2
    elif change == "new-role":
        current["roles"].append({"user_id": 1, "role_id": 999})
    elif change == "company-role":
        current["members"][0]["role"] = "MANAGER"
    elif change == "company-stopped":
        checkpoint["companies"][0]["status"] = "SUSPENDED"
    elif change == "workspace-generation":
        current["workspaces"][0]["active_generation_id"] = 999
    elif change == "factor-secret":
        current["factors"][0]["secret"] = "different-fingerprint"
    elif change == "factor-version":
        current["factors"][0]["version"] = 2
    elif change == "otp-step":
        current["factors"][0]["last_used_step"] = 6
    elif change == "pending-factor":
        current["factors"][0]["state"] = "PENDING"
    elif change == "recovery-used":
        checkpoint["codes"][0]["used"] = True
    elif change == "sso-version":
        current["sso"][0]["version"] = 2
    elif change == "throttle-count":
        current["throttles"][0]["fail_count"] = 4
    elif change == "throttle-lock":
        current["throttles"][0]["locked"] = None
    core, journal = restriction_violations(
        current, original, checkpoint, [1] if change == "journal-user" else []
    )
    assert core + journal > 0


def test_stricter_denial_is_valid_and_neither_input_snapshot_is_mutated():
    original = state()
    checkpoint = deepcopy(original)
    current = deepcopy(original)
    assert restriction_violations(current, original, checkpoint, []) == (0, 0)
    current["users"][0].update(status="disabled", disabled=True, security_version=2)
    current["roles"] = []
    current["members"][0]["is_active"] = False
    current["factors"][0]["state"] = "REVOKED"
    current["codes"][0]["revoked"] = True
    current["sso"][0]["state"] = "REVOKED"
    current["throttles"][0]["fail_count"] = 6
    assert restriction_violations(current, original, checkpoint, [1]) == (0, 0)
    assert original == checkpoint == state()


@pytest.mark.parametrize(
    "change", ["old-denied", "latest-denied", "identity", "journal", "new-grant"]
)
def test_hr_grants_must_be_allowed_by_both_captured_states(change):
    original = [
        {
            "id": 1,
            "workspace_id": 2,
            "generation_id": 3,
            "user_id": 4,
            "employee_id": 5,
            "work_role": "STAFF",
            "is_active": True,
        }
    ]
    checkpoint = deepcopy(original)
    current = deepcopy(original)
    if change == "old-denied":
        original[0]["is_active"] = False
    elif change == "latest-denied":
        checkpoint[0]["is_active"] = False
    elif change == "identity":
        current[0]["employee_id"] = 999
    elif change == "new-grant":
        current[0]["id"] = 999
    assert (
        hr_violations(
            current, original, checkpoint, {4} if change == "journal" else set()
        )
        == 1
    )
    current[0]["is_active"] = False
    assert hr_violations(current, original, checkpoint, {4}) == 0
