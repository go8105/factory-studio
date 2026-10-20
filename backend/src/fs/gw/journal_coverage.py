"""Observed recording-family coverage, never all-route or revocation acceptance."""

from fs.core.backup import BackupError
from fs.core.security.transaction_proof import summary

FAMILIES = (
    "core.security.intent.v1",
    "hr.users.intent.v1",
    "gw.company.intent.v2",
)
DISPOSITIONS = {
    "AUDIT_CONFIRMED",
    "ABORT_CONFIRMED",
    "PENDING",
    "SOURCE_MISMATCH",
    "COMMITTED_WITHOUT_AUDIT",
    "UNKNOWN",
}


def build(records, dispositions):
    digests = [record["digest"] for record in records]
    if (
        len(set(digests)) != len(digests)
        or set(digests) != set(dispositions)
        or any(value not in DISPOSITIONS for value in dispositions.values())
    ):
        raise BackupError("수집 계열과 거래 판정 범위가 다릅니다.")
    groups = {family: {} for family in FAMILIES}
    unsupported = 0
    for record in records:
        family = record["payload"].get("coverage")
        if not isinstance(family, str) or family not in groups:
            unsupported += 1
            continue
        groups[family][record["digest"]] = dispositions[record["digest"]]
    checks = []
    for family, values in groups.items():
        counts = summary(values)
        checks.append(
            {
                "family": family,
                "records": len(values),
                "state": "MISSING"
                if not values
                else ("SETTLED" if counts["allTransactionsSettled"] else "UNSETTLED"),
                "transactionDispositionCounts": counts["transactionDispositionCounts"],
            }
        )
    return {
        "version": 1,
        "kind": "OBSERVED_JOURNAL_FAMILIES",
        "result": "BLOCKED"
        if unsupported or any(check["state"] != "SETTLED" for check in checks)
        else "PARTIAL",
        "records": len(records),
        "unsupportedRecords": unsupported,
        "families": checks,
        "completenessConfirmed": False,
        "revocationsReapplied": False,
        "releaseAuthorized": False,
        "remainingChecks": [
            "ROUTE_EXECUTION_AND_ROLLBACK",
            "INDEPENDENT_LATEST_HEAD",
            "RESTORED_ACCESS_DENIAL",
            "SOURCE_UNCHANGED",
            "OPERATOR_BOUNDARIES",
        ],
    }
