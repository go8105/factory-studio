"""A complete local checklist cannot stand in for unconnected live evidence."""

import pytest

from fs.gw.launch_gate import build
from fs.gw.operating_contract import OperatingPolicy


def inputs():
    return {
        "policy": OperatingPolicy(responsiblePersonId="1", reason="합성 전환 조건"),
        "connected": 10,
        "enrolled": 10,
        "departments": 1,
        "responsible_active": True,
        "evidence": [
            {
                "kind": kind,
                "state": "RECORDED_PASS",
                "signatureVerified": True,
                "detail": "합성 검증 결과",
            }
            for kind in ("BACKUP", "RESTORE", "ACCEPTANCE")
        ],
    }


def test_all_local_checks_still_require_four_unconnected_evidence_boundaries():
    gate = build(**inputs())
    assert (
        gate["confirmedCount"] == 8
        and gate["blockedCount"] == 0
        and gate["unverifiedCount"] == 4
    )
    assert not gate["ready"]
    assert len({c["code"] for c in gate["checks"]}) == 12
    assert {c["code"] for c in gate["checks"] if c["state"] == "UNVERIFIED"} == {
        "EXTERNAL_STORAGE",
        "JOURNAL_COVERAGE",
        "LIVE_COMPANY",
        "FINAL_RELEASE",
    }


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("policy", None, "POLICY"),
        ("connected", 9, "PEOPLE"),
        ("enrolled", 9, "MFA"),
        ("connected", 0, "MFA"),
        ("departments", 0, "DEPARTMENTS"),
        ("responsible_active", False, "RESPONSIBLE"),
    ],
)
def test_live_conditions_fail_closed(field, value, code):
    args = inputs()
    args[field] = value
    gate = build(**args)
    assert next(c for c in gate["checks"] if c["code"] == code)["state"] == "BLOCKED"
    assert not gate["ready"]


@pytest.mark.parametrize(
    "state,verified",
    [
        ("PARTIAL", True),
        ("FAILED", True),
        ("STALE", True),
        ("RECORDED_PASS", False),
        ("RECORDED_PASS", "true"),
    ],
)
def test_only_current_signature_verified_pass_counts_as_registered_condition(
    state, verified
):
    args = inputs()
    args["evidence"][0].update(state=state, signatureVerified=verified)
    gate = build(**args)
    assert (
        next(c for c in gate["checks"] if c["code"] == "BACKUP")["state"] == "BLOCKED"
    )


def test_missing_and_duplicate_evidence_are_not_satisfied():
    args = inputs()
    args["evidence"] = []
    assert build(**args)["blockedCount"] == 3
    args = inputs()
    args["evidence"].append(args["evidence"][0])
    assert build(**args)["blockedCount"] == 1


def test_unverified_conditions_include_criteria_without_changing_gate_state():
    gate = build(**inputs())
    pending = [c for c in gate["checks"] if c["state"] == "UNVERIFIED"]
    assert all(c["requiredEvidence"] and c["acceptanceScope"] for c in pending)
    assert all(len(c["requiredEvidence"]) >= 3 for c in pending)
    live = next(c for c in pending if c["code"] == "LIVE_COMPANY")
    assert "10명" in live["requiredEvidence"][0]
    args = inputs()
    args["policy"] = args["policy"].model_copy(update={"expected_people": 3})
    smaller = next(c for c in build(**args)["checks"] if c["code"] == "LIVE_COMPANY")
    assert "3명" in smaller["requiredEvidence"][0]
    assert not gate["ready"] and gate["unverifiedCount"] == 4
