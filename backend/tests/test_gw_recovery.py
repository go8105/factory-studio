"""Historical failure boundaries never become current readiness evidence."""

from copy import deepcopy
from datetime import timedelta
from uuid import uuid4

import pytest
from test_gw_source_checkpoint import proof

from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.operating_contract import EvidenceEnvelope
from fs.gw.recovery import boundary, next_step


def fixture():
    recheck, docs, collector, _key, ctx = proof("changed")
    doc = sign_reconciliation(
        docs,
        signer=collector,
        signer_id="collector",
        database_observed_at=ctx["now"].isoformat(),
        restore_recheck=recheck,
        **ctx,
    )
    data = EvidenceEnvelope.model_validate(doc["envelope"])
    row = data.model_dump() | {
        "id": 1,
        "workspace_id": ctx["workspace_id"],
        "generation_id": ctx["generation_id"],
        "run_id": data.run_id,
        "recorded_at": ctx["now"],
        "started_at": ctx["now"],
        "finished_at": ctx["now"],
        "metrics": data.metrics.model_dump(by_alias=True)
        | {"_signedEnvelope": doc["envelope"]},
        "signature": doc["signature"],
    }
    return row, docs, ctx


@pytest.mark.parametrize(
    "change",
    [None, "missing", "tampered", "row", "signature", "revoked", "wrong-scope"],
)
def test_history_signature_and_row_match_or_fresh_backup_fallback(change):
    row, docs, ctx = fixture()
    if change == "missing":
        row["metrics"].pop("_signedEnvelope")
    elif change == "tampered":
        row["metrics"]["_signedEnvelope"]["codeRevision"] = "f" * 8
    elif change == "row":
        row["manifest_digest"] = "f" * 64
    elif change == "signature":
        row["signature"] = "AAAA"
    elif change == "revoked":
        ctx["public_keys"] = {}
    elif change == "wrong-scope":
        row["workspace_id"] += 1
    anchor = boundary(row, ctx["public_keys"])
    assert anchor["trustedOriginal"] == (change is None)
    assert anchor["runId"] == row["run_id"]
    backup = EvidenceEnvelope.model_validate(docs["BACKUP"]["envelope"])
    restore = EvidenceEnvelope.model_validate(docs["RESTORE"]["envelope"])
    assert next_step(anchor, backup, restore) == (
        "NEW_RESTORE_REQUIRED" if change is None else "NEW_BACKUP_REQUIRED"
    )


@pytest.mark.parametrize(
    "reuse",
    [
        "none",
        "run",
        "target",
        "checkpoint-run",
        "checkpoint-digest",
        "before",
        "missing-backup",
        "missing-restore",
        "backup-run",
        "backup-digest",
    ],
)
def test_new_partial_requires_other_checkpoint_and_physical_restore_after_failure(
    reuse,
):
    row, docs, ctx = fixture()
    anchor = boundary(row, ctx["public_keys"])
    backup = EvidenceEnvelope.model_validate(docs["BACKUP"]["envelope"])
    restore = EvidenceEnvelope.model_validate(docs["RESTORE"]["envelope"])
    # next_step examines candidates after the caller verifies their actual signatures.
    restore = restore.model_copy(
        deep=True,
        update={
            "run_id": str(uuid4()),
            "started_at": (ctx["now"] + timedelta(seconds=1)).isoformat(),
        },
    )
    observed = restore.metrics.restore_diagnostics.execution_observation
    original = deepcopy(observed)
    observed.target_identity = "d" * 64
    observed.checkpoint_run_id = str(uuid4())
    observed.checkpoint_digest = "e" * 64
    if reuse == "run":
        restore.run_id = anchor["previous"]["restoreRunId"]
    elif reuse == "target":
        observed.target_identity = original.target_identity
    elif reuse == "checkpoint-run":
        observed.checkpoint_run_id = original.checkpoint_run_id
    elif reuse == "checkpoint-digest":
        observed.checkpoint_digest = original.checkpoint_digest
    elif reuse == "before":
        restore.started_at = ctx["now"].isoformat()
    elif reuse == "backup-run":
        backup.run_id = str(uuid4())
    elif reuse == "backup-digest":
        backup.manifest_digest = "f" * 64
    elif reuse == "missing-backup":
        backup = None
    elif reuse == "missing-restore":
        restore = None
    assert next_step(anchor, backup, restore) == (
        "RECHECK_REQUIRED"
        if reuse == "none"
        else "NEW_BACKUP_REQUIRED"
        if reuse == "missing-backup"
        else "NEW_RESTORE_REQUIRED"
    )
