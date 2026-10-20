import json

import pytest
from fs.core.backup import BackupError
from fs.gw.journal_coverage import DISPOSITIONS, FAMILIES, build


def records():
    return [
        {
            "digest": str(i) * 64,
            "payload": {"coverage": family, "userId": 999, "snapshot": "private"},
        }
        for i, family in enumerate(FAMILIES, 1)
    ]


def test_all_observed_families_settled_cannot_prove_full_coverage():
    items = records()
    result = build(items, {item["digest"]: "AUDIT_CONFIRMED" for item in items})
    assert result["result"] == "PARTIAL"
    assert all(item["state"] == "SETTLED" for item in result["families"])
    assert not result["completenessConfirmed"]
    assert not result["revocationsReapplied"] and not result["releaseAuthorized"]
    assert len(result["remainingChecks"]) == 5
    assert "private" not in json.dumps(result) and "999" not in json.dumps(result)


@pytest.mark.parametrize("state", sorted(DISPOSITIONS))
def test_each_transaction_disposition_preserved(state):
    items = records()
    result = build(items, {item["digest"]: state for item in items})
    settled = state in {"AUDIT_CONFIRMED", "ABORT_CONFIRMED"}
    assert result["result"] == ("PARTIAL" if settled else "BLOCKED")
    for family in result["families"]:
        assert family["transactionDispositionCounts"][state] == 1


@pytest.mark.parametrize(
    "family", ["gw.company_identity.intent.v1", "new.family", None, []]
)
def test_unsupported_and_legacy_families_never_fill_missing_groups(family):
    item = {"digest": "a" * 64, "payload": {"coverage": family}}
    result = build([item], {item["digest"]: "AUDIT_CONFIRMED"})
    assert result["unsupportedRecords"] == 1 and result["result"] == "BLOCKED"
    assert all(group["state"] == "MISSING" for group in result["families"])


def test_empty_is_missing_not_success():
    result = build([], {})
    assert result["result"] == "BLOCKED"
    assert all(group["state"] == "MISSING" for group in result["families"])


@pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "override"])
def test_reject_inconsistent_or_manual_classification(change):
    items = records()
    dispositions = {item["digest"]: "AUDIT_CONFIRMED" for item in items}
    if change == "missing":
        dispositions.pop(items[0]["digest"])
    elif change == "extra":
        dispositions["f" * 64] = "UNKNOWN"
    elif change == "duplicate":
        items.append(items[0])
    else:
        dispositions[items[0]["digest"]] = "APPROVED"
    with pytest.raises(BackupError):
        build(items, dispositions)
