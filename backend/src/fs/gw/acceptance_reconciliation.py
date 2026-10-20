"""Signed, limited source reconciliation. No live acceptance or release authority."""

import base64
import hashlib
from uuid import uuid4

from fs.gw.operating_contract import (
    AcceptanceDiagnostics,
    backup_is_current,
    canonical,
    evidence_error,
    timestamp,
    verify_evidence,
)


def reconcile(documents, **context):
    """Read original signatures, never unsigned synthetic reports or caller flags."""
    sources = {}
    references = {}
    for kind in ("BACKUP", "RESTORE"):
        document = documents.get(kind)
        if not isinstance(document, dict) or set(document) != {"envelope", "signature"}:
            raise evidence_error()
        data = verify_evidence(document["envelope"], document["signature"], **context)
        if (
            data.kind != kind
            or data.result not in {"PASS", "PARTIAL"}
            or timestamp(data.finished_at) > context["now"]
        ):
            raise evidence_error()
        sources[kind] = data
        references[kind.lower()] = {
            "runId": data.run_id,
            "sourceDigest": hashlib.sha256(canonical(document)).hexdigest(),
        }
    backup, restore = sources["BACKUP"], sources["RESTORE"]
    if (
        not backup_is_current(backup, context["policy"], context["now"])
        or backup.run_id == restore.run_id
        or backup.manifest_digest != restore.manifest_digest
        or timestamp(backup.finished_at) > timestamp(restore.started_at)
    ):
        raise evidence_error()
    return AcceptanceDiagnostics.model_validate(
        {
            "version": 1,
            "scope": "BACKUP_RESTORE_RECONCILIATION",
            **references,
            "externalStorage": "UNVERIFIED",
            "journalCoverage": "UNVERIFIED",
            "liveCompany": "UNVERIFIED",
            "finalRelease": "UNVERIFIED",
        }
    )


def sign_reconciliation(documents, *, signer, signer_id, **context):
    diagnostics = reconcile(documents, **context).model_dump(by_alias=True)
    payload = {
        "version": 1,
        "runId": str(uuid4()),
        "workspaceId": str(context["workspace_id"]),
        "generationId": str(context["generation_id"]),
        "policyDigest": context["policy"].digest(),
        "kind": "ACCEPTANCE",
        "startedAt": context["now"].isoformat(),
        "finishedAt": context["now"].isoformat(),
        "codeRevision": context["code_revision"],
        "dbRevision": context["db_revision"],
        "manifestDigest": hashlib.sha256(canonical(diagnostics)).hexdigest(),
        "result": "PARTIAL",
        "signerKeyId": signer_id,
        "metrics": {"acceptanceDiagnostics": diagnostics},
    }
    signature = base64.b64encode(signer.sign(canonical(payload))).decode()
    verify_evidence(payload, signature, **context)
    return {"envelope": payload, "signature": signature}


def verify_registered_sources(data, rows, *, policy_id, **context):
    """Called under the same company/settings lock as registration and readiness.

    Resolve each latest row first; no backwards search after failure, partial,
    missing original, or replaced policy/version. A PARTIAL restore can support
    only this limited PARTIAL reconciliation, never a restore PASS.
    """
    from fs.gw.readiness import SOURCE_FIELD, evaluate

    documents = {}
    for kind in ("BACKUP", "RESTORE"):
        candidates = [r for r in rows if r["kind"] == kind]
        if not candidates:
            raise evidence_error()
        row = max(candidates, key=lambda r: (r["recorded_at"], r["id"]))
        if (
            row["workspace_id"] != context["workspace_id"]
            or row["generation_id"] != context["generation_id"]
            or row["finished_at"] > timestamp(data.started_at)
        ):
            raise evidence_error()
        state, _, verified = evaluate(
            row,
            context["policy"],
            policy_id,
            context["code_revision"],
            context["db_revision"],
            context["public_keys"],
            context["now"],
        )
        if not verified or state not in {"RECORDED_PASS", "PARTIAL"}:
            raise evidence_error()
        documents[kind] = {
            "envelope": row["metrics"][SOURCE_FIELD],
            "signature": row["signature"],
        }
    expected = reconcile(documents, **context)
    if data.metrics.acceptance_diagnostics != expected:
        raise evidence_error()
