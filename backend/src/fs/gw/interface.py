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
        k != "PURCHASE_INVOICE" for k, n in document_refs
    ):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "조회 대상을 확인해 주세요.",
            {"fields": {"documentRefs": "매입 전표를 100개 이하로 지정하세요."}},
        )
    result = {no: None for kind, no in document_refs}
    if not result:
        return result
    rows = connection.execute(
        text("""SELECT DISTINCT ON (source_no) id,document_no,status,submission_order,source_digest,source_status,source_no
      FROM gw.approval_document WHERE workspace_id=:w AND generation_id=:g
      AND source_kind='PURCHASE_INVOICE' AND status<>'DRAFT' AND source_no=ANY(:nos)
      ORDER BY source_no,(status='IN_REVIEW') DESC,submission_order DESC,id DESC"""),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "nos": list(result)},
    ).mappings()
    for r in rows:
        result[r["source_no"]] = {
            "id": str(r["id"]),
            "documentNo": r["document_no"],
            "status": r["status"],
            "submissionOrder": str(r["submission_order"]),
            "sourceDigest": r["source_digest"],
            "sourceStatus": r["source_status"],
        }
    return result
