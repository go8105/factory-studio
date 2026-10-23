"""Select and sign current registered originals in one read-only DB snapshot."""

from sqlalchemy import text

from fs.gw.acceptance_preflight import read_transaction, snapshot, validate_request
from fs.gw.acceptance_reconciliation import (
    require_new_observation,
    sign_reconciliation,
    verify_registered_sources,
)
from fs.gw.operating_contract import (
    OperatingPolicy,
    evidence_error,
    timestamp,
    verify_evidence,
)
from fs.gw.readiness import SOURCE_FIELD, evaluate


def sign_current(
    engine,
    *,
    company_id,
    code_revision,
    public_keys,
    signer,
    signer_id,
    admin_login="admin",
    journal_observation=None,
    restore_recheck=None,
):
    validate_request(
        company_id=company_id, code_revision=code_revision, admin_login=admin_login
    )
    with read_transaction(engine) as c:
        current, preflight = snapshot(
            c,
            company_id=company_id,
            code_revision=code_revision,
            admin_login=admin_login.strip().lower(),
        )
        context = {
            "workspace_id": current["workspaceId"],
            "generation_id": current["generationId"],
            "policy": OperatingPolicy.model_validate(current["policy"]),
            "code_revision": current["codeRevision"],
            "db_revision": current["dbRevision"],
            "public_keys": public_keys,
            "now": timestamp(preflight["observedAt"]),
        }
        params = {"w": company_id, "g": current["generationId"]}
        policy_id = c.execute(
            text(
                "SELECT current_policy_revision_id FROM gw.operating_settings WHERE workspace_id=:w AND generation_id=:g"
            ),
            params,
        ).scalar_one()
        # Select latest across ALL results, policies and versions. No success filter/fallback.
        rows = (
            c.execute(
                text("""SELECT DISTINCT ON (kind) * FROM gw.operating_evidence
            WHERE workspace_id=:w AND generation_id=:g AND kind IN ('BACKUP','RESTORE')
            ORDER BY kind,recorded_at DESC,id DESC"""),
                params,
            )
            .mappings()
            .all()
        )
        documents = {}
        for row in rows:
            state, _, verified = evaluate(
                row,
                context["policy"],
                policy_id,
                code_revision,
                current["dbRevision"],
                public_keys,
                context["now"],
            )
            if not verified or state not in {"RECORDED_PASS", "PARTIAL"}:
                raise evidence_error()
            documents[row["kind"]] = {
                "envelope": row["metrics"][SOURCE_FIELD],
                "signature": row["signature"],
            }
        document = sign_reconciliation(
            documents,
            signer=signer,
            signer_id=signer_id,
            database_observed_at=preflight["observedAt"],
            journal_observation=journal_observation,
            restore_recheck=restore_recheck,
            **context,
        )
        data = verify_evidence(document["envelope"], document["signature"], **context)
        require_new_observation(
            c, data, workspace_id=company_id, generation_id=current["generationId"]
        )
        verify_registered_sources(
            data, rows, policy_id=policy_id, connection=c, **context
        )
        return document
