"""기존 GW 조회/담당자 별칭의 회사 범위 구현."""

from sqlalchemy import text

from fs.gw import company, organization
from fs.gw import company_identity as identities
from fs.gw import company_work as work
from fs.gw import service as s


def read(context, company_id, kind, id=None, **q):
    if kind in {"documents", "posts"}:
        return work.read(context, company_id, kind, id, **q)
    with company.transaction(context, company_id) as (c, ctx, _):
        identity, roles = company.principal(c, ctx)
        p = s.one(c, ctx, "person", identity["id"])
        if kind == "sources":
            raise s.invalid("kind", "회사에서는 외부 원천을 사용할 수 없습니다.")
        if kind == "hr-preview":
            if "ORG_ADMIN" in roles:
                return organization.state(c, ctx)
            units, _ = organization.local(c, ctx)
            return {
                "available": False,
                "digest": None,
                "departments": None,
                "employees": None,
                "organizations": s.wire(units),
                "people": [],
            }
        if kind == "dashboard":
            base = (
                f"d.workspace_id=:w AND d.generation_id=:g AND {work.acl('documents')}"
            )
            params = s.params(
                ctx,
                person=p["id"],
                org=p["organization_unit_id"],
                active=sorted(identities.active_people(c, ctx)),
            )
            docs = s.rows(
                c,
                f"SELECT d.* FROM gw.approval_document d WHERE {base} ORDER BY d.id DESC",
                params,
            )
            posts = s.rows(
                c,
                f"SELECT d.* FROM gw.board_post d WHERE d.workspace_id=:w AND d.generation_id=:g AND {work.acl('posts')} AND d.status='PUBLISHED' ORDER BY d.id DESC LIMIT 5",
                params,
            )
            own = [d for d in docs if d["drafter_id"] == p["id"]]
            return s.wire(
                {
                    "needs_person": False,
                    "drafts": sum(d["status"] == "DRAFT" for d in own),
                    "in_review": sum(d["status"] == "IN_REVIEW" for d in own),
                    "closed": sum(
                        d["status"] in {"APPROVED", "REJECTED", "WITHDRAWN"}
                        for d in own
                    ),
                    "pending": sum(
                        bool(work.policy.eligible(c, ctx, d, p, company_mode=True))
                        for d in docs
                    ),
                    "recent_documents": [
                        d
                        for d in docs
                        if d["status"] in {"APPROVED", "REJECTED", "WITHDRAWN"}
                    ][:5],
                    "recent_posts": posts,
                }
            )
        if kind == "people-options":
            kind = "people"
            options = True
        else:
            options = False
        if kind not in {"people", "routes"}:
            work.not_found()
        active = identities.active_people(c, ctx)
        if id:
            if (
                kind == "people"
                and id not in active
                and "ORG_ADMIN" not in roles
                and "SECURITY_ADMIN" not in roles
            ):
                work.not_found()
            return s.detail(c, ctx, kind, id)
        if kind == "routes":
            return s.listing(c, ctx, kind, q)
        where = (
            s.S
            + " AND (strpos(lower(name),lower(:search))>0 OR strpos(lower(code),lower(:search))>0)"
        )
        params = s.params(
            ctx,
            search=q.get("search", ""),
            offset=q.get("offset", 0),
            limit=q.get("limit", 50),
            active=sorted(active),
        )
        if options or not roles & {"ORG_ADMIN", "SECURITY_ADMIN"}:
            where += " AND id=ANY(CAST(:active AS bigint[]))"
        rows = organization.enrich_people(
            c,
            ctx,
            s.rows(
                c,
                f"SELECT * FROM gw.person WHERE {where} ORDER BY code,id LIMIT :limit OFFSET :offset",
                params,
            ),
        )
        total = c.execute(
            text(f"SELECT count(*) FROM gw.person WHERE {where}"), params
        ).scalar_one()
        return {
            "rows": s.wire(rows),
            "total": total,
            "offset": params["offset"],
            "limit": params["limit"],
        }


def mutate_person(context, company_id, id, values, key):
    def authorize(c, ctx, identity):
        company.principal(c, ctx, "ORG_ADMIN")
        if id is None:
            raise s.invalid("person", "회사 직원은 HR에서 명시적으로 가져오세요.")
        s.one(c, ctx, "person", id)

    def run(c, ctx, identity):
        row = s.one(c, ctx, "person", id, True)
        s.check_version(row, values)
        if values.get("name", row["name"]) != row["name"]:
            raise s.invalid("name", "직원 이름은 HR 가져오기로 갱신하세요.")
        changes = {k: values[k] for k in ("job_role", "is_active") if k in values}
        if changes.get("is_active") is False:
            identities.last_admin(c, ctx, id)
        s.update(c, ctx, "person", id, changes)
        identities.bump(c, ctx)
        identities.audit(
            c,
            ctx,
            "person",
            id,
            "person-edit",
            values.get("reason", "GW 직원 상태 변경"),
        )
        return s.wire(s.one(c, ctx, "person", id)), "gw.person", id

    return company.action(
        context,
        company_id,
        f"company.people.{id}.edit",
        key,
        values,
        run,
        authorize=authorize,
    )
