"""Read-only GW provider. Does not call ERP (no recursive cross reads)."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.scope import module_available


def enabled(connection, scoped):
    return module_available(connection, scoped.workspace_id, "gw")


def approvals(connection, scoped, document_refs):
    if not enabled(connection, scoped):
        return None
    if len(document_refs) > 100 or any(
        k not in {"PURCHASE_INVOICE", "PURCHASE_ORDER", "EXPENSE_CLAIM", "ECO"}
        for k, n in document_refs
    ):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "조회 대상을 확인해 주세요.",
            {"fields": {"documentRefs": "지원 종류의 원문을 100개 이하로 지정하세요."}},
        )
    mixed = len({kind for kind, no in document_refs}) > 1

    def ref_key(kind, no):
        return f"{kind}:{no}" if mixed else no

    result = {ref_key(kind, no): None for kind, no in document_refs}
    requested = set(document_refs)
    if not result:
        return result
    rows = connection.execute(
        text("""SELECT DISTINCT ON (source_kind,source_no) id,document_no,status,submission_order,source_digest,source_status,source_no,source_kind
      FROM gw.approval_document WHERE workspace_id=:w AND generation_id=:g
      AND source_kind=ANY(:kinds) AND status<>'DRAFT' AND source_no=ANY(:nos)
      ORDER BY source_kind,source_no,(status='IN_REVIEW') DESC,submission_order DESC,id DESC"""),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "nos": [no for kind, no in document_refs],
            "kinds": list({kind for kind, no in document_refs}),
        },
    ).mappings()
    for r in rows:
        if (r["source_kind"], r["source_no"]) not in requested:
            continue
        result[ref_key(r["source_kind"], r["source_no"])] = {
            "id": str(r["id"]),
            "documentNo": r["document_no"],
            "status": r["status"],
            "submissionOrder": str(r["submission_order"]),
            "sourceDigest": r["source_digest"],
            "sourceStatus": r["source_status"],
        }
    return result
