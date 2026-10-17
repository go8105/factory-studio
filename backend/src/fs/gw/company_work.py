"""회사 결재·게시 ACL. 04의 전체 라우트/화면 통합 전에는 업무 API를 공개하지 않는다."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.gw import company, policy
from fs.gw import company_identity as identities
from fs.gw import service as gw


def not_found():
    raise ApiError(404, "NOT_FOUND", "열람 가능한 대상을 찾을 수 없습니다.")


def acl(kind, alias="d"):
    """WHERE에 먼저 적용한다. count/search/page에 비공개 원문이 섞이지 않는다."""
    same = (
        f"x.workspace_id={alias}.workspace_id AND x.generation_id={alias}.generation_id"
    )
    if kind == "posts":
        return f"({alias}.author_id=:person OR ({alias}.status='PUBLISHED' AND ({alias}.visibility='WORKSPACE' OR {alias}.audience_org_id=:org)))"
    effective = "COALESCE((SELECT a.person_id FROM gw.step_assignment a WHERE a.workspace_id=x.workspace_id AND a.generation_id=x.generation_id AND a.step_id=x.id ORDER BY a.assignment_seq DESC LIMIT 1),x.person_id)"
    other = "COALESCE((SELECT a.person_id FROM gw.step_assignment a WHERE a.workspace_id=z.workspace_id AND a.generation_id=z.generation_id AND a.step_id=z.id ORDER BY a.assignment_seq DESC LIMIT 1),z.person_id)"
    return f"""({alias}.kind='GENERAL' AND ({alias}.drafter_id=:person OR
      ({alias}.status<>'DRAFT' AND (
       EXISTS(SELECT 1 FROM gw.document_reader x WHERE {same} AND x.document_id={alias}.id AND x.person_id=:person AND x.is_active)
       OR EXISTS(SELECT 1 FROM gw.approval_step x WHERE {same} AND x.document_id={alias}.id AND x.status<>'SKIPPED' AND {effective}=:person)
       OR EXISTS(SELECT 1 FROM gw.approval_event x WHERE {same} AND x.document_id={alias}.id AND x.acting_person_id=:person AND x.event_type IN ('APPROVED','REJECTED','CONSENTED','OPPOSED'))
       OR ({alias}.status='IN_REVIEW' AND EXISTS(
         SELECT 1 FROM gw.approval_step x JOIN gw.delegation grant_row ON
           grant_row.workspace_id=x.workspace_id AND grant_row.generation_id=x.generation_id
           AND grant_row.delegator_person_id={effective}
         WHERE {same} AND x.document_id={alias}.id AND x.status='WAITING' AND x.seq={alias}.current_step
           AND {effective}=ANY(CAST(:active AS bigint[]))
           AND grant_row.delegate_person_id=:person AND grant_row.revoked_at IS NULL
           AND grant_row.starts_at<=clock_timestamp() AND grant_row.ends_at>clock_timestamp()
           AND (grant_row.document_kind IS NULL OR grant_row.document_kind={alias}.kind)
           AND (grant_row.max_amount IS NULL OR ({alias}.currency='KRW' AND grant_row.max_amount>={alias}.amount))
           AND NOT EXISTS(SELECT 1 FROM gw.approval_step z WHERE z.workspace_id=x.workspace_id AND z.generation_id=x.generation_id AND z.document_id=x.document_id AND {other}=:person)
           AND NOT EXISTS(SELECT 1 FROM gw.delegation z WHERE z.workspace_id=x.workspace_id AND z.generation_id=x.generation_id AND z.revoked_at IS NULL AND z.starts_at<=clock_timestamp() AND z.ends_at>clock_timestamp() AND (z.delegator_person_id=:person OR z.delegate_person_id={effective}))
       ))
      ))))"""


def person(c, ctx, id):
    return gw.one(c, ctx, "person", id)


def visible(c, ctx, kind, id, p):
    table = gw.TABLES[kind]
    return (
        c.execute(
            text(
                f"SELECT 1 FROM gw.{table} d WHERE d.workspace_id=:w AND d.generation_id=:g AND d.id=:id AND {acl(kind)}"
            ),
            gw.params(
                ctx,
                id=id,
                person=p["id"],
                org=p["organization_unit_id"],
                active=sorted(identities.active_people(c, ctx)),
            ),
        ).first()
        is not None
    )


def require_visible(c, ctx, kind, id, p):
    if not visible(c, ctx, kind, id, p):
        not_found()


def detail(c, ctx, kind, id, p):
    require_visible(c, ctx, kind, id, p)
    row = gw.one(c, ctx, gw.TABLES[kind], id)
    previous = "previous_document_id" if kind == "documents" else "previous_post_id"
    if row[previous] and not visible(c, ctx, kind, row[previous], p):
        row[previous] = None
    successor = gw.successor(c, ctx, gw.TABLES[kind], id)
    row["successor"] = (
        successor if successor and visible(c, ctx, kind, successor["id"], p) else None
    )
    row["events"] = gw.rows(
        c,
        f"SELECT * FROM gw.{'approval_event' if kind == 'documents' else 'board_event'} WHERE {gw.S} AND {'document_id' if kind == 'documents' else 'post_id'}=:id ORDER BY event_seq",
        gw.params(ctx, id=id),
    )
    if kind == "documents":
        row["steps"] = gw.steps(c, ctx, id, company_mode=True)
        row["action_steps"] = [
            {
                "step_id": x["step"]["id"],
                "participant_role": x["step"]["participant_role"],
            }
            for x in policy.eligible(c, ctx, row, p, company_mode=True)
        ]
    return gw.wire(row)


def read(context, company_id, kind, id=None, *, offset=0, limit=50, search=""):
    if (
        kind not in {"documents", "posts"}
        or offset < 0
        or not 1 <= limit <= 100
        or len(search) > 100
    ):
        raise gw.invalid("query", "목록 조건을 확인하세요.")
    with company.transaction(context, company_id) as (c, ctx, _):
        principal, _ = company.principal(c, ctx)
        p = person(c, ctx, principal["id"])
        if id is not None:
            return detail(c, ctx, kind, id, p)
        where = f"d.workspace_id=:w AND d.generation_id=:g AND {acl(kind)} AND (strpos(lower(d.title),lower(:search))>0 OR strpos(lower(d.body),lower(:search))>0)"
        params = gw.params(
            ctx,
            person=p["id"],
            active=sorted(identities.active_people(c, ctx)),
            org=p["organization_unit_id"],
            search=search,
            offset=offset,
            limit=limit,
        )
        total = c.execute(
            text(f"SELECT count(*) FROM gw.{gw.TABLES[kind]} d WHERE {where}"), params
        ).scalar_one()
        data = gw.rows(
            c,
            f"SELECT d.id,d.title,d.status,d.version FROM gw.{gw.TABLES[kind]} d WHERE {where} ORDER BY d.id DESC LIMIT :limit OFFSET :offset",
            params,
        )
        return {"items": gw.wire(data), "total": total}


def mutate(context, company_id, kind, id, operation, values, key):
    if kind not in {"documents", "posts", "routes"}:
        not_found()
    if {"acting_person_id", "actingPersonId"} & values.keys():
        raise gw.invalid("actingPersonId", "처리자는 로그인 계정으로 결정합니다.")

    def authorize(c, ctx, principal):
        p = person(c, ctx, principal["id"])
        if kind == "routes":
            company.principal(c, ctx, "ROUTE_ADMIN")
        elif id is not None:
            require_visible(c, ctx, kind, id, p)
            if operation not in {"approve", "reject", "consent", "oppose", "reference"}:
                row = gw.one(c, ctx, gw.TABLES[kind], id)
                if row["drafter_id" if kind == "documents" else "author_id"] != p["id"]:
                    not_found()
        if kind == "posts":
            board = (
                gw.one(c, ctx, "board_post", id)["board_kind"]
                if id
                else values["board_kind"]
            )
            if board == "NOTICE":
                company.principal(c, ctx, "BOARD_PUBLISHER")

    def run(c, ctx, principal):
        p = person(c, ctx, principal["id"])
        v = {**values, "acting_person_id": p["id"]}
        if kind == "routes":
            for step in v["steps"]:
                identities.require_active(
                    c, ctx, step["person_id"] if "person_id" in step else step["id"]
                )
            saved = gw.master(c, ctx, kind, id, v)
            return (
                gw.wire(gw.one(c, ctx, "approval_route", saved)),
                "gw.approval_route",
                saved,
            )
        if kind == "documents":
            if (
                v.get("kind", "GENERAL") != "GENERAL"
                or v.get("source_no") is not None
                or operation == "refresh-source"
            ):
                raise gw.invalid("kind", "회사에서는 일반 기안만 사용할 수 있습니다.")
            if id and gw.one(c, ctx, "approval_document", id)["kind"] != "GENERAL":
                not_found()
            if operation in {"create", "select-route", "submit"}:
                if operation == "submit":
                    participants = gw.steps(c, ctx, id, company_mode=True)
                else:
                    _, participants = gw.route_people(c, ctx, v["route_id"], p["id"])
                for step in participants:
                    identities.require_active(
                        c, ctx, step["person_id"] if "person_id" in step else step["id"]
                    )
            saved = gw.document(c, ctx, id, operation, v, company_mode=True)
            if operation in {"create", "resubmit"}:
                c.execute(
                    text(
                        f"UPDATE gw.approval_document SET auth_mode='IDENTITY' WHERE {gw.S} AND id=:id"
                    ),
                    gw.params(ctx, id=saved),
                )
        else:
            current = gw.one(c, ctx, "board_post", id) if id else {}
            if (
                operation in {"create", "edit", "publish", "correct"}
                and v.get("visibility", current.get("visibility")) == "ORG"
                and v.get("audience_org_id", current.get("audience_org_id"))
                != p["organization_unit_id"]
            ):
                raise gw.invalid("audienceOrgId", "본인 소속 조직만 선택하세요.")
            saved = gw.post(
                c,
                ctx,
                id,
                operation,
                v,
                notice_allowed="BOARD_PUBLISHER" in company.principal(c, ctx)[1],
            )
        result = detail(c, ctx, kind, saved, p)
        gw.audit(c, ctx, kind, saved, operation, result)
        return result, "gw." + gw.TABLES[kind], saved

    return company.action(
        context,
        company_id,
        f"company.{kind}.{id}.{operation}",
        key,
        values,
        run,
        authorize=authorize,
    )


def reader(context, company_id, document_id, person_id, values, key):
    def authorize(c, ctx, principal):
        row = gw.one(c, ctx, "approval_document", document_id)
        if row["kind"] != "GENERAL" or row["drafter_id"] != principal["id"]:
            not_found()

    def run(c, ctx, principal):
        doc = gw.one(c, ctx, "approval_document", document_id, True)
        gw.check_version(doc, values)
        if doc["status"] == "DRAFT":
            raise gw.conflict("IMMUTABLE_DOCUMENT")
        if values["is_active"]:
            identities.require_active(c, ctx, person_id)
        rows = gw.rows(
            c,
            f"SELECT * FROM gw.document_reader WHERE {gw.S} AND document_id=:doc AND person_id=:person",
            gw.params(ctx, doc=document_id, person=person_id),
        )
        changes = {
            "is_active": values["is_active"],
            "granted_by_user_id": ctx.user_id,
            "reason": values["reason"],
        }
        if rows:
            gw.update(c, ctx, "document_reader", rows[0]["id"], changes)
        elif values["is_active"]:
            gw.insert(
                c,
                ctx,
                "document_reader",
                {"document_id": document_id, "person_id": person_id, **changes},
            )
        else:
            not_found()
        gw.update(c, ctx, "approval_document", document_id, {})
        gw.event(
            c,
            ctx,
            "approval_document",
            gw.one(c, ctx, "approval_document", document_id),
            person(c, ctx, principal["id"]),
            "READER_GRANTED" if values["is_active"] else "READER_REVOKED",
            values["reason"],
            details={"personId": str(person_id)},
        )
        identities.bump(c, ctx)
        identities.audit(
            c, ctx, "approval_document", document_id, "reader", values["reason"]
        )
        return (
            {
                "document_id": document_id,
                "person_id": person_id,
                "is_active": values["is_active"],
                "version": doc["version"] + 1,
            },
            "gw.approval_document",
            document_id,
        )

    return company.action(
        context,
        company_id,
        f"reader.{document_id}.{person_id}",
        key,
        values,
        run,
        authorize=authorize,
    )


def reassign(context, company_id, document_id, values, key):
    def authorize(c, ctx, principal):
        company.principal(c, ctx, "SECURITY_ADMIN")
        row = gw.one(c, ctx, "approval_document", document_id)
        if row["kind"] != "GENERAL":
            not_found()

    def run(c, ctx, principal):
        doc = gw.one(c, ctx, "approval_document", document_id, True)
        gw.check_version(doc, values)
        steps = gw.steps(c, ctx, document_id, company_mode=True)
        step = next((s for s in steps if s["id"] == values["step_id"]), None)
        active = identities.active_people(c, ctx)
        target = values["person_id"]
        if (
            doc["status"] != "IN_REVIEW"
            or not step
            or step["status"] != "WAITING"
            or step["person_id"] in active
        ):
            raise ApiError(
                409,
                "GW_STEP_NOT_BLOCKED",
                "비활성 담당자의 미처리 단계만 재배정할 수 있습니다.",
            )
        identities.require_active(c, ctx, target)
        if target in {principal["id"], doc["drafter_id"]} or any(
            s["person_id"] == target for s in steps
        ):
            raise gw.invalid("personId", "본인·기안자·이미 배정된 직원을 제외하세요.")
        seq = c.execute(
            text(
                f"SELECT coalesce(max(assignment_seq),0)+1 FROM gw.step_assignment WHERE {gw.S} AND step_id=:id"
            ),
            gw.params(ctx, id=step["id"]),
        ).scalar_one()
        gw.insert(
            c,
            ctx,
            "step_assignment",
            {
                "document_id": document_id,
                "step_id": step["id"],
                "person_id": target,
                "assignment_seq": seq,
                "reason": values["reason"],
                "assigned_by_user_id": ctx.user_id,
            },
        )
        gw.update(c, ctx, "approval_document", document_id, {})
        gw.event(
            c,
            ctx,
            "approval_document",
            gw.one(c, ctx, "approval_document", document_id),
            person(c, ctx, principal["id"]),
            "STEP_REASSIGNED",
            values["reason"],
            step=step["seq"],
            details={"stepId": str(step["id"]), "personId": str(target)},
        )
        identities.bump(c, ctx)
        identities.audit(
            c,
            ctx,
            "approval_document",
            document_id,
            "step-reassigned",
            values["reason"],
        )
        return (
            {
                "document_id": document_id,
                "step_id": step["id"],
                "person_id": target,
                "version": doc["version"] + 1,
            },
            "gw.approval_document",
            document_id,
        )

    return company.action(
        context,
        company_id,
        f"reassign.{document_id}",
        key,
        values,
        run,
        authorize=authorize,
    )


def readers(context, company_id, document_id, *, offset=0, limit=50):
    with company.transaction(context, company_id) as (c, ctx, _):
        principal, _ = company.principal(c, ctx)
        row = gw.one(c, ctx, "approval_document", document_id)
        if row["kind"] != "GENERAL" or row["drafter_id"] != principal["id"]:
            not_found()
        where = f"{gw.S} AND document_id=:doc"
        p = gw.params(ctx, doc=document_id, offset=offset, limit=limit)
        rows = gw.rows(
            c,
            f"SELECT person_id,is_active,version FROM gw.document_reader WHERE {where} ORDER BY id LIMIT :limit OFFSET :offset",
            p,
        )
        return {
            "items": gw.wire(rows),
            "total": c.execute(
                text(f"SELECT count(*) FROM gw.document_reader WHERE {where}"), p
            ).scalar_one(),
        }


def blocked(context, company_id, *, offset=0, limit=50):
    with company.transaction(context, company_id) as (c, ctx, _):
        company.principal(c, ctx, "SECURITY_ADMIN")
        active = identities.active_people(c, ctx)
        # 담당 정보 외의 원문·제목·금액은 관리 응답에 포함하지 않는다.
        rows = gw.rows(
            c,
            "SELECT s.document_id,d.version AS document_version,s.id AS step_id,s.seq,s.participant_role,coalesce((SELECT a.person_id FROM gw.step_assignment a WHERE a.workspace_id=s.workspace_id AND a.generation_id=s.generation_id AND a.step_id=s.id ORDER BY a.assignment_seq DESC LIMIT 1),s.person_id) AS person_id FROM gw.approval_step s JOIN gw.approval_document d ON (d.workspace_id,d.generation_id,d.id)=(s.workspace_id,s.generation_id,s.document_id) WHERE s.workspace_id=:w AND s.generation_id=:g AND s.status='WAITING' AND d.status='IN_REVIEW' AND d.kind='GENERAL' ORDER BY s.document_id,s.seq,s.id",
            gw.params(ctx),
        )
        data = [r for r in rows if r["person_id"] not in active]
        return {"items": gw.wire(data[offset : offset + limit]), "total": len(data)}


def security_events(context, company_id, *, offset=0, limit=50):
    with company.transaction(context, company_id) as (c, ctx, _):
        _, roles = company.principal(c, ctx)
        if not roles & {"SECURITY_ADMIN", "AUDITOR"}:
            identities.denied()
        p = {"w": ctx.workspace_id, "offset": offset, "limit": limit}
        rows = gw.rows(
            c,
            "SELECT id,actor_user_id,action,entity_kind,entity_key,created_at FROM core.audit_event WHERE workspace_id=:w AND action LIKE 'gw.security.%' ORDER BY id DESC LIMIT :limit OFFSET :offset",
            p,
        )
        total = c.execute(
            text(
                "SELECT count(*) FROM core.audit_event WHERE workspace_id=:w AND action LIKE 'gw.security.%'"
            ),
            p,
        ).scalar_one()
        return {"items": gw.wire(rows), "total": total}
