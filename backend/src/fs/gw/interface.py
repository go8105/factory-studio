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


def published_notices(connection, scoped, limit=10):
    """EIP has no selected simulation person: expose workspace notices only."""
    if not enabled(connection, scoped):
        return None
    if not 1 <= limit <= 100:
        raise ApiError(400, "VALIDATION_FAILED", "조회 수는 1~100입니다.")
    from fs.gw import service

    return service.wire(
        service.rows(
            connection,
            """SELECT id,post_no,title,body,author_name,published_at FROM gw.board_post
        WHERE workspace_id=:w AND generation_id=:g AND board_kind='NOTICE' AND status='PUBLISHED' AND visibility='WORKSPACE'
        ORDER BY published_at DESC,id DESC LIMIT :limit""",
            service.params(scoped, limit=limit),
        )
    )


def monthly_summary(connection, scoped, month):
    if not enabled(connection, scoped):
        return None
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from fs.gw import service

    try:
        start = datetime.strptime(month, "%Y-%m").replace(tzinfo=ZoneInfo("Asia/Seoul"))
        if start.strftime("%Y-%m") != month:
            raise ValueError()
        end = (
            start.replace(year=start.year + 1, month=1)
            if start.month == 12
            else start.replace(month=start.month + 1)
        )
    except ValueError as e:
        raise ApiError(400, "VALIDATION_FAILED", "월은 YYYY-MM입니다.") from e
    row = service.rows(
        connection,
        """SELECT count(*) submitted,count(*) FILTER(WHERE status='APPROVED') approved,
        count(*) FILTER(WHERE status='REJECTED') rejected,count(*) FILTER(WHERE status='IN_REVIEW') in_review
        FROM gw.approval_document WHERE workspace_id=:w AND generation_id=:g AND submitted_at>=:start AND submitted_at<:end""",
        service.params(scoped, start=start, end=end),
    )[0]
    return {"month": month, "metrics": service.wire(row)}


def pending_tasks(connection, scoped, hr_employee_code):
    if not enabled(connection, scoped):
        return None
    from fs.gw import service

    person = service.rows(
        connection,
        f"SELECT id FROM gw.person WHERE {service.S} AND hr_employee_code=:code AND is_active",
        service.params(scoped, code=hr_employee_code),
    )
    if not person:
        return []
    count = service.listing(
        connection,
        scoped,
        "documents",
        {"box": "pending", "person_id": person[0]["id"]},
    )["total"]
    return (
        [
            {
                "kind": "APPROVAL",
                "label": "결재 대기",
                "count": count,
                "path": "/gw/pending",
            }
        ]
        if count
        else []
    )


def lookup(connection, scoped, code):
    if not enabled(connection, scoped):
        return None
    from fs.gw import service

    for table, column, kind, label, path, extra in [
        (
            "approval_document",
            "document_no",
            "document",
            "결재 문서",
            "/gw/documents",
            "",
        ),
        (
            "board_post",
            "post_no",
            "post",
            "게시글",
            "/gw/board",
            "AND visibility='WORKSPACE' AND status='PUBLISHED'",
        ),
    ]:
        rows = service.rows(
            connection,
            f"SELECT id,title FROM gw.{table} WHERE {service.S} AND {column}=:code {extra}",
            service.params(scoped, code=code),
        )
        if rows:
            return {
                "kind": kind,
                "label": label,
                "code": code,
                "caption": rows[0]["title"],
                "path": path + "?open=" + str(rows[0]["id"]),
            }
    return None
