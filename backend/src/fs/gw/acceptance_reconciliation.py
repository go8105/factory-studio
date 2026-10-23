"""Signed, limited source reconciliation. No live acceptance or release authority."""

import base64
import hashlib
from uuid import uuid4

from fs.gw.operating_contract import (
    AcceptanceDiagnostics,
    JournalAcceptanceDiagnostics,
    RegisteredAcceptanceDiagnostics,
    acceptance_context_digest,
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


def registered_diagnostics(diagnostics, *, observed_at, **context):
    if timestamp(observed_at) > context["now"]:
        raise evidence_error()
    return RegisteredAcceptanceDiagnostics.model_validate(
        diagnostics.model_dump(by_alias=True)
        | {
            "version": 2,
            "scope": "CURRENT_REGISTERED_SOURCES",
            "observedAt": observed_at,
            "contextDigest": acceptance_context_digest(
                **{
                    k: context[k]
                    for k in (
                        "workspace_id",
                        "generation_id",
                        "policy",
                        "code_revision",
                        "db_revision",
                    )
                }
            ),
        }
    )


def sign_reconciliation(
    documents,
    *,
    signer,
    signer_id,
    database_observed_at=None,
    journal_observation=None,
    **context,
):
    diagnostics = reconcile(documents, **context)
    if database_observed_at is not None:
        if timestamp(database_observed_at) != context["now"]:
            raise evidence_error()
        diagnostics = registered_diagnostics(
            diagnostics, observed_at=database_observed_at, **context
        )
    if journal_observation is not None:
        if database_observed_at is None:
            raise evidence_error()
        diagnostics = JournalAcceptanceDiagnostics.model_validate(
            diagnostics.model_dump(by_alias=True)
            | {
                "version": 3,
                "scope": "CURRENT_REGISTERED_SOURCES_AND_JOURNAL",
                "journalObservation": journal_observation,
            }
        )
    diagnostics = diagnostics.model_dump(by_alias=True)
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
        "result": "FAIL"
        if journal_observation is not None
        and journal_observation["envelope"]["result"] == "BLOCKED"
        else "PARTIAL",
        "signerKeyId": signer_id,
        "metrics": {"acceptanceDiagnostics": diagnostics},
    }
    signature = base64.b64encode(signer.sign(canonical(payload))).decode()
    verify_evidence(payload, signature, **context)
    return {"envelope": payload, "signature": signature}


def verify_registered_sources(data, rows, *, policy_id, connection=None, **context):
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
    diagnostic = data.metrics.acceptance_diagnostics
    if isinstance(diagnostic, RegisteredAcceptanceDiagnostics):
        observed = timestamp(diagnostic.observed_at)
        if observed != timestamp(data.started_at) or any(
            row["recorded_at"] > observed
            for row in rows
            if row["kind"] in {"BACKUP", "RESTORE"}
        ):
            raise evidence_error()
        expected = registered_diagnostics(
            expected, observed_at=diagnostic.observed_at, **context
        )
    if isinstance(diagnostic, JournalAcceptanceDiagnostics):
        from cryptography.exceptions import InvalidSignature

        from fs.core.backup import BackupError
        from fs.gw.journal_observation import verify_registered

        if connection is None:
            raise evidence_error()
        document = diagnostic.journal_observation.model_dump()
        try:
            verify_registered(connection, document, **context)
        except BackupError, OSError, ValueError, TypeError, KeyError, InvalidSignature:
            raise evidence_error() from None
        expected = JournalAcceptanceDiagnostics.model_validate(
            expected.model_dump(by_alias=True)
            | {
                "version": 3,
                "scope": "CURRENT_REGISTERED_SOURCES_AND_JOURNAL",
                "journalObservation": document,
            }
        )
    if diagnostic != expected:
        raise evidence_error()


def require_new_observation(connection, data, *, workspace_id, generation_id):
    """A new collection must observe after the latest registered acceptance run.

    Select across all results/policies/versions, including missing originals. This
    is registration order, not a claim about unregistered operator files.
    """
    from sqlalchemy import text

    if data.kind != "ACCEPTANCE":
        return
    diagnostic = data.metrics.acceptance_diagnostics
    history = (
        connection.execute(
            text("""SELECT max(recorded_at) AS recorded_at,
        coalesce(bool_or(metrics->'acceptanceDiagnostics'->>'version'='3'),false) AS journal_required
        FROM gw.operating_evidence
        WHERE workspace_id=:w AND generation_id=:g AND kind='ACCEPTANCE'
        """),
            {"w": workspace_id, "g": generation_id},
        )
        .mappings()
        .one()
    )
    if not isinstance(diagnostic, JournalAcceptanceDiagnostics):
        if history["journal_required"]:
            raise evidence_error()
        return
    latest = history["recorded_at"]
    if (
        latest is not None
        and timestamp(diagnostic.journal_observation.envelope["observedAt"]) <= latest
    ):
        raise evidence_error()
