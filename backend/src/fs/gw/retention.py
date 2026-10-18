"""Retention bookkeeping never deletes originals or grants source access."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.core.company import require_recent_auth
from fs.gw import company, company_work
from fs.gw import service as gw
from fs.gw.operations import settings

S = company.S


def audit(c, ctx, table, id, operation, reason, result=None):
    gw.audit(
        c,
        ctx,
        "security",
        id,
        operation,
        {},
        entity_kind="gw." + table,
        summary={
            "generationId": str(ctx.generation_id),
            "reason": reason,
            **(result or {}),
        },
    )


def params(ctx, **extra):
    return {"w": ctx.workspace_id, "g": ctx.generation_id, **extra}


def permission(c, ctx, *, write=False):
    person, roles = company.principal(c, ctx)
    if write:
        company.principal(c, ctx, "SECURITY_ADMIN")
        require_recent_auth(c, ctx, always=True)
    elif not roles.intersection({"SECURITY_ADMIN", "AUDITOR"}):
        raise ApiError(403, "FORBIDDEN", "보관 검토 기록을 확인할 권한이 없습니다.")
    return person


def required_settings(c, ctx):
    current = settings(c, ctx)
    if current is None or current["current_policy_revision_id"] is None:
        raise ApiError(
            409, "OPERATING_PREREQUISITE_REQUIRED", "운영 기준을 먼저 적용하세요."
        )
    return current


def review(c, ctx, id):
    row = (
        c.execute(
            text(f"SELECT * FROM gw.retention_review WHERE {S} AND id=:id FOR UPDATE"),
            params(ctx, id=id),
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        company_work.not_found()
    return row


def kind_and_id(row):
    return (
        ("documents", row["document_id"])
        if row["document_id"] is not None
        else ("posts", row["post_id"])
    )


def held(c, ctx, row):
    column = "document_id" if row["document_id"] is not None else "post_id"
    return c.execute(
        text(
            f"SELECT EXISTS(SELECT 1 FROM gw.retention_review WHERE {S} AND {column}=:source AND state='HELD')"
        ),
        params(ctx, source=row[column]),
    ).scalar_one()


def refresh(context, company_id, payload, key):
    def authorize(c, ctx, _):
        permission(c, ctx, write=True)

    def run(c, ctx, _):
        current = required_settings(c, ctx)
        if current["version"] != payload["expectedVersion"]:
            raise ApiError(
                409,
                "STATE_CHANGED",
                "운영 기준이 변경되었습니다. 현재 값을 다시 확인하세요.",
            )
        p = params(
            ctx, policy=current["current_policy_revision_id"], reason=payload["reason"]
        )
        # KST calendar months, not 30-day approximations; preserve past policy rows.
        rows = (
            c.execute(
                text(f"""WITH policy AS (SELECT document_review_months AS months FROM gw.operating_policy_revision WHERE {S} AND id=:policy),
        candidates AS (
          SELECT d.id AS source_id,'DOCUMENT' AS kind,((d.closed_at AT TIME ZONE 'Asia/Seoul')::date+make_interval(months=>p.months))::date AS due
          FROM gw.approval_document d CROSS JOIN policy p WHERE d.{S.replace(" AND ", " AND d.")} AND d.kind='GENERAL' AND d.status IN ('APPROVED','REJECTED','WITHDRAWN') AND d.closed_at IS NOT NULL
          UNION ALL
          SELECT d.id,'POST',((coalesce(d.withdrawn_at,d.published_at) AT TIME ZONE 'Asia/Seoul')::date+make_interval(months=>p.months))::date
          FROM gw.board_post d CROSS JOIN policy p WHERE d.{S.replace(" AND ", " AND d.")} AND d.status IN ('PUBLISHED','WITHDRAWN') AND d.published_at IS NOT NULL
        ) SELECT * FROM candidates x WHERE due <= (clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date
          AND NOT EXISTS(SELECT 1 FROM gw.retention_review r WHERE r.workspace_id=:w AND r.generation_id=:g AND r.policy_revision_id=:policy AND ((x.kind='DOCUMENT' AND r.document_id=x.source_id) OR (x.kind='POST' AND r.post_id=x.source_id)))
          ORDER BY due,kind,source_id LIMIT 201"""),
                p,
            )
            .mappings()
            .all()
        )
        ids = []
        for item in rows[:200]:
            id = c.execute(
                text("""INSERT INTO gw.retention_review(workspace_id,generation_id,document_id,post_id,policy_revision_id,review_due_on,state,reason,created_at)
                VALUES(:w,:g,:doc,:post,:policy,:due,'DUE',:reason,clock_timestamp()) RETURNING id"""),
                p
                | {
                    "doc": item["source_id"] if item["kind"] == "DOCUMENT" else None,
                    "post": item["source_id"] if item["kind"] == "POST" else None,
                    "due": item["due"],
                },
            ).scalar_one()
            ids.append(str(id))
        audit(
            c,
            ctx,
            "operating_settings",
            current["id"],
            "retention.refreshed",
            payload["reason"],
            {
                "added": len(ids),
                "policyRevisionId": str(current["current_policy_revision_id"]),
            },
        )
        return (
            {"added": len(ids), "hasMore": len(rows) > 200},
            "gw.operating_settings",
            current["id"],
        )

    return company.action(
        context,
        company_id,
        "gw.retention.refresh",
        key,
        payload,
        run,
        authorize=authorize,
    )


def company_hold(context, company_id, payload, key):
    def authorize(c, ctx, _):
        permission(c, ctx, write=True)

    def run(c, ctx, _):
        current = required_settings(c, ctx)
        if current["version"] != payload["expectedVersion"]:
            raise ApiError(
                409,
                "STATE_CHANGED",
                "운영 기준이 변경되었습니다. 현재 값을 다시 확인하세요.",
            )
        c.execute(
            text(
                f"UPDATE gw.operating_settings SET company_hold=:hold,hold_reason=:reason,version=version+1,updated_by_user_id=:u,updated_at=clock_timestamp() WHERE {S}"
            ),
            params(ctx, hold=payload["hold"], reason=payload["reason"], u=ctx.user_id),
        )
        audit(
            c,
            ctx,
            "operating_settings",
            current["id"],
            "retention.company_hold.changed",
            payload["reason"],
            {"hold": payload["hold"], "version": current["version"] + 1},
        )
        return (
            {"hold": payload["hold"], "version": current["version"] + 1},
            "gw.operating_settings",
            current["id"],
        )

    return company.action(
        context,
        company_id,
        "gw.retention.company_hold",
        key,
        payload,
        run,
        authorize=authorize,
    )


def transition(context, company_id, id, payload, key):
    def authorize(c, ctx, _):
        person = permission(c, ctx, write=True)
        row = review(c, ctx, id)
        if payload["state"] == "ARCHIVE_PREPARED":
            kind, source = kind_and_id(row)
            company_work.require_visible(c, ctx, kind, source, person)

    def run(c, ctx, _):
        row = review(c, ctx, id)
        current = required_settings(c, ctx)
        if row["version"] != payload["expectedVersion"]:
            raise ApiError(
                409, "STATE_CHANGED", "검토 상태가 변경되었습니다. 새로 확인하세요."
            )
        target = payload["state"]
        allowed = {
            "DUE": {"HELD", "ARCHIVE_PREPARED"},
            "HELD": {"DUE"},
            "ARCHIVE_PREPARED": {"DUE", "HELD"},
            "ARCHIVED": set(),
        }
        if target not in allowed[row["state"]]:
            raise ApiError(
                409, "STATE_CHANGED", "현재 상태에서 선택한 처리로 바꿀 수 없습니다."
            )
        if target == "ARCHIVE_PREPARED":
            if current["company_hold"] or held(c, ctx, row):
                raise ApiError(
                    409,
                    "RETENTION_HELD",
                    "회사 또는 개별 보류가 적용 중입니다. 해제 이력을 확인하세요.",
                )
            if row["policy_revision_id"] != current["current_policy_revision_id"]:
                raise ApiError(
                    409,
                    "STATE_CHANGED",
                    "이전 기준의 검토입니다. 현재 기준 대상을 갱신하세요.",
                )
        c.execute(
            text(
                f"UPDATE gw.retention_review SET state=:state,reason=:reason,version=version+1,reviewed_by_user_id=:u,reviewed_at=clock_timestamp() WHERE {S} AND id=:id"
            ),
            params(ctx, id=id, state=target, reason=payload["reason"], u=ctx.user_id),
        )
        audit(
            c,
            ctx,
            "retention_review",
            id,
            "retention.state.changed",
            payload["reason"],
            {"from": row["state"], "to": target, "version": row["version"] + 1},
        )
        return (
            {"id": str(id), "state": target, "version": row["version"] + 1},
            "gw.retention_review",
            id,
        )

    return company.action(
        context,
        company_id,
        f"gw.retention.transition.{id}",
        key,
        payload,
        run,
        authorize=authorize,
    )


def history(context, company_id, *, offset=0, limit=20, state=None, source_id=None):
    with company.transaction(context, company_id) as (c, ctx, _):
        person = permission(c, ctx)
        current = settings(c, ctx)
        where = "r." + S.replace(" AND ", " AND r.")
        p = params(ctx, offset=offset, limit=limit)
        if state:
            where += " AND r.state=:state"
            p["state"] = state
        if source_id:
            where += " AND (r.document_id=:source OR r.post_id=:source)"
            p["source"] = source_id
        rows = (
            c.execute(
                text(f"""SELECT r.*,p.revision_no FROM gw.retention_review r JOIN gw.operating_policy_revision p
          ON (p.workspace_id,p.generation_id,p.id)=(r.workspace_id,r.generation_id,r.policy_revision_id)
          WHERE {where} ORDER BY r.review_due_on,r.id LIMIT :limit OFFSET :offset"""),
                p,
            )
            .mappings()
            .all()
        )
        count = c.execute(
            text(f"SELECT count(*) FROM gw.retention_review r WHERE {where}"), p
        ).scalar_one()
        result = []
        for row in rows:
            kind, source = kind_and_id(row)
            visible = company_work.visible(c, ctx, kind, source, person)
            result.append(
                {
                    "id": str(row["id"]),
                    "kind": kind,
                    "sourceId": str(source),
                    "dueOn": row["review_due_on"].isoformat(),
                    "state": row["state"],
                    "version": row["version"],
                    "reason": row["reason"],
                    "revisionNo": row["revision_no"],
                    "currentPolicy": bool(
                        current
                        and row["policy_revision_id"]
                        == current["current_policy_revision_id"]
                    ),
                    "canReadSource": visible,
                    "effectiveHold": bool(current and current["company_hold"])
                    or held(c, ctx, row),
                }
            )
        return {
            "total": count,
            "items": result,
            "companyHold": bool(current and current["company_hold"]),
            "holdReason": current["hold_reason"] if current else None,
            "settingsVersion": current["version"] if current else 0,
        }


def source(context, company_id, id):
    with company.transaction(context, company_id) as (c, ctx, _):
        person = permission(c, ctx)
        row = review(c, ctx, id)
        kind, source_id = kind_and_id(row)
        company_work.require_visible(c, ctx, kind, source_id, person)
        return {"kind": kind, "sourceId": str(source_id)}


def events(context, company_id, *, offset=0, limit=20):
    with company.transaction(context, company_id) as (c, ctx, _):
        permission(c, ctx)
        p = params(ctx, offset=offset, limit=limit)
        where = "workspace_id=:w AND action IN ('gw.security.retention.refreshed','gw.security.retention.company_hold.changed','gw.security.retention.state.changed') AND summary->>'generationId'=cast(:g AS text)"
        rows = (
            c.execute(
                text(
                    f"SELECT id,action,entity_key,summary,created_at FROM core.audit_event WHERE {where} ORDER BY id DESC LIMIT :limit OFFSET :offset"
                ),
                p,
            )
            .mappings()
            .all()
        )
        count = c.execute(
            text(f"SELECT count(*) FROM core.audit_event WHERE {where}"), p
        ).scalar_one()
        return {
            "total": count,
            "items": [
                {
                    "id": str(r["id"]),
                    "action": r["action"].removeprefix("gw.security."),
                    "entityId": r["entity_key"],
                    "reason": r["summary"]["reason"],
                    "hold": r["summary"].get("hold"),
                    "from": r["summary"].get("from"),
                    "to": r["summary"].get("to"),
                    "at": r["created_at"].isoformat(),
                }
                for r in rows
            ],
        }
