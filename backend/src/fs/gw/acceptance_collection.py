"""Read-only collection of existing runner proofs; never a release approval."""

import hashlib
from datetime import timedelta

from fs.common.errors import ApiError
from fs.gw.operating_contract import (
    backup_is_current,
    canonical,
    timestamp,
    verify_evidence,
)


def collect(documents, **context):
    """Require exactly one current backup and its later restore, not arbitrary PASS flags.

    The trusted context must come from the operator, never from proof contents.
    Even a matching pair cannot establish external storage or company acceptance.
    """
    checks = []
    verified = {}
    restore_measurements = None
    for kind in ("BACKUP", "RESTORE"):
        document = documents.get(kind)
        state = "MISSING"
        source_digest = None
        if document is not None:
            try:
                if set(document) != {"envelope", "signature"}:
                    raise ValueError()
                data = verify_evidence(
                    document["envelope"], document["signature"], **context
                )
                if data.kind != kind or timestamp(data.finished_at) > context["now"]:
                    raise ValueError()
                source_digest = hashlib.sha256(canonical(document)).hexdigest()
                state = data.result
                if kind == "RESTORE" and state in {"PASS", "PARTIAL"}:
                    restore_measurements = {
                        name: data.metrics.model_dump(by_alias=True)[name]
                        for name in (
                            "rowHashesMatch",
                            "foreignKeysValid",
                            "sessionsInvalidated",
                            "revocationsReapplied",
                            "twoAccountChecks",
                            "lossWindowSeconds",
                            "elapsedSeconds",
                            "restoreDiagnostics",
                        )
                    }
                if (
                    kind == "BACKUP"
                    and state == "PASS"
                    and not backup_is_current(data, context["policy"], context["now"])
                ):
                    state = "STALE"
                if state == "PASS":
                    verified[kind] = data
            except ApiError, ValueError, TypeError, KeyError:
                state = "INVALID"
        checks.append({"kind": kind, "state": state, "sourceDigest": source_digest})
    paired = False
    if len(verified) == 2:
        backup, restore = verified["BACKUP"], verified["RESTORE"]
        paired = (
            backup.run_id != restore.run_id
            and backup.manifest_digest == restore.manifest_digest
            and timestamp(backup.finished_at)
            <= timestamp(restore.started_at) + timedelta(seconds=30)
        )
    return {
        "version": 1,
        "kind": "ACCEPTANCE_COLLECTION",
        "result": "PARTIAL" if paired else "BLOCKED",
        "ready": False,
        "restoreMeasurements": restore_measurements,
        "workspaceId": str(context["workspace_id"]),
        "generationId": str(context["generation_id"]),
        "policyDigest": context["policy"].digest(),
        "codeRevision": context["code_revision"],
        "dbRevision": context["db_revision"],
        "collectedAt": context["now"].isoformat(),
        "checks": checks,
        "backupRestorePairVerified": paired,
        "remainingConditions": [
            "EXTERNAL_STORAGE",
            "JOURNAL_COVERAGE",
            "LIVE_COMPANY",
            "FINAL_RELEASE",
        ],
    }


def collect_registered(rows, *, policy_id, **context):
    """Bind latest registrations to retained signatures before collecting their pair.

    Caller reads rows and current policy under the company transaction. Never
    search backwards for an older success after a later failure or invalid row.
    """
    from fs.gw.readiness import SOURCE_FIELD, evaluate

    documents = {}
    registrations = []
    for kind in ("BACKUP", "RESTORE"):
        candidates = [row for row in rows if row["kind"] == kind]
        row = (
            max(candidates, key=lambda r: (r["recorded_at"], r["id"]))
            if candidates
            else None
        )
        state = "MISSING"
        if row is not None:
            state, _detail, _verified = evaluate(
                row,
                context["policy"],
                policy_id,
                context["code_revision"],
                context["db_revision"],
                context["public_keys"],
                context["now"],
            )
            if (
                row["workspace_id"] != context["workspace_id"]
                or row["generation_id"] != context["generation_id"]
            ):
                state = "INVALID"
            if state in {"RECORDED_PASS", "PARTIAL"}:
                documents[kind] = {
                    "envelope": row["metrics"][SOURCE_FIELD],
                    "signature": row["signature"],
                }
        registrations.append({"kind": kind, "state": state})
    report = collect(documents, **context)
    report["source"] = "LATEST_REGISTRATIONS"
    report["registrations"] = registrations
    return report
