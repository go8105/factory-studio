"""Company-scoped observed identity operations, not full route acceptance."""

import re

from fs.core.backup import BackupError
from fs.core.security.transaction_proof import summary
from fs.gw.journal_coverage import build as validate_records

ROUTES = {
    "COMPANY_SETUP": r"company-setup",
    "BINDING_REQUEST": r"binding\.None\.request",
    "BINDING_ACCEPT": r"binding\.[1-9][0-9]{0,18}\.accept",
    "BINDING_CANCEL": r"binding\.[1-9][0-9]{0,18}\.cancel",
    "BINDING_SUSPEND": r"binding\.[1-9][0-9]{0,18}\.suspend",
    "BINDING_RESUME": r"binding\.[1-9][0-9]{0,18}\.resume",
    "ROLE_CHANGE": r"roles\.[1-9][0-9]{0,18}",
}


def build(records, dispositions, *, scope, code_revision, db_revision, head):
    validate_records(records, dispositions)
    if (
        not re.fullmatch(r"[0-9a-f]{7,64}", code_revision)
        or not re.fullmatch(r"[A-Za-z0-9_]{1,100}", db_revision)
        or not re.fullmatch(r"[0-9a-f]{64}", head)
        or any(
            not re.fullmatch(r"[1-9][0-9]{0,18}", scope[k])
            for k in ("workspaceId", "generationId")
        )
        or not re.fullmatch(r"[0-9a-f]{64}", scope["policyDigest"])
    ):
        raise BackupError("현재 경로 진단 기준을 확인하세요.")
    groups = {route: {} for route in ROUTES}
    excluded = unsupported = 0
    for record in records:
        payload = record["payload"]
        if (
            type(payload.get("workspaceId")) is not int
            or type(payload.get("generationId")) is not int
            or str(payload["workspaceId"]) != scope["workspaceId"]
            or str(payload["generationId"]) != scope["generationId"]
        ):
            excluded += 1
            continue
        if payload.get("coverage") != "gw.company.intent.v2":
            unsupported += 1
            continue
        operation = payload.get("operation")
        route = next(
            (
                key
                for key, pattern in ROUTES.items()
                if isinstance(operation, str) and re.fullmatch(pattern, operation)
            ),
            None,
        )
        if route is None:
            unsupported += 1
            continue
        groups[route][record["digest"]] = dispositions[record["digest"]]
    checks = []
    for route, values in groups.items():
        counts = summary(values)["transactionDispositionCounts"]
        unresolved = len(values) - counts["AUDIT_CONFIRMED"] - counts["ABORT_CONFIRMED"]
        checks.append(
            {
                "route": route,
                "records": len(values),
                "state": "UNSETTLED"
                if unresolved
                else (
                    "COMMIT_OBSERVED"
                    if counts["AUDIT_CONFIRMED"]
                    else ("ABORT_ONLY" if values else "MISSING")
                ),
                "transactionDispositionCounts": counts,
                "storageFailureRollback": "UNVERIFIED",
                "restoredAccessDenial": "UNVERIFIED",
            }
        )
    return {
        "version": 1,
        "catalogVersion": "GW_IDENTITY_ROUTES_V1",
        "kind": "OBSERVED_IDENTITY_ROUTES",
        "workspaceId": scope["workspaceId"],
        "generationId": scope["generationId"],
        "assessmentPolicyDigest": scope["policyDigest"],
        "assessmentCodeRevision": code_revision,
        "assessmentDbRevision": db_revision,
        "head": head,
        "records": len(records),
        "excludedScopeRecords": excluded,
        "unsupportedScopeRecords": unsupported,
        "routes": checks,
        "result": "BLOCKED"
        if unsupported or any(c["state"] != "COMMIT_OBSERVED" for c in checks)
        else "PARTIAL",
        "executionRevisionVerified": False,
        "completenessConfirmed": False,
        "revocationsReapplied": False,
        "releaseAuthorized": False,
    }
