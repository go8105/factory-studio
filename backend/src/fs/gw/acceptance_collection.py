"""Read-only collection of existing runner proofs; never a release approval."""

import hashlib

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
            and timestamp(backup.finished_at) <= timestamp(restore.started_at)
        )
    return {
        "version": 1,
        "kind": "ACCEPTANCE_COLLECTION",
        "result": "PARTIAL" if paired else "BLOCKED",
        "ready": False,
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
