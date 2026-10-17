"""회사 전결/위임. 업무 관리 역할과 실제 결재 당사자를 분리한다."""

from sqlalchemy import text

from fs.gw import company, policy
from fs.gw import company_identity as identities
from fs.gw import company_work as work
from fs.gw import service as s


def read(context, company_id, kind, *, offset=0, limit=50):
    with company.transaction(context, company_id) as (c, ctx, _):
        p, roles = company.principal(c, ctx)
        params = s.params(ctx, person=p["id"], offset=offset, limit=limit)
        if kind == "authority-rules":
            where = (
                s.S
                + " AND document_kind='GENERAL'"
                + ("" if "POLICY_ADMIN" in roles else " AND is_active")
            )
            rows = s.rows(
                c,
                f"SELECT * FROM gw.authority_rule WHERE {where} ORDER BY id DESC LIMIT :limit OFFSET :offset",
                params,
            )
            total = c.execute(
                text(f"SELECT count(*) FROM gw.authority_rule WHERE {where}"), params
            ).scalar_one()
        else:
            where = "d.workspace_id=:w AND d.generation_id=:g AND (d.delegator_person_id=:person OR d.delegate_person_id=:person)"
            rows = s.rows(
                c,
                f"SELECT d.*,p.name AS delegator_name,q.name AS delegate_name FROM gw.delegation d JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(d.workspace_id,d.generation_id,d.delegator_person_id) JOIN gw.person q ON (q.workspace_id,q.generation_id,q.id)=(d.workspace_id,d.generation_id,d.delegate_person_id) WHERE {where} ORDER BY d.id DESC LIMIT :limit OFFSET :offset",
                params,
            )
            total = c.execute(
                text(f"SELECT count(*) FROM gw.delegation d WHERE {where}"), params
            ).scalar_one()
        return {"rows": s.wire(rows), "total": total, "offset": offset, "limit": limit}


def mutate(context, company_id, kind, id, operation, values, key):
    def authorize(c, ctx, identity):
        if kind == "authority-rules":
            company.principal(c, ctx, "POLICY_ADMIN")
            if id and s.one(c, ctx, "authority_rule", id)["document_kind"] != "GENERAL":
                work.not_found()
        elif (
            id
            and s.one(c, ctx, "delegation", id)["delegator_person_id"] != identity["id"]
        ):
            work.not_found()

    def run(c, ctx, identity):
        if kind == "authority-rules":
            if values.get("document_kind", "GENERAL") != "GENERAL":
                raise s.invalid("documentKind", "회사에서는 일반 기안만 선택하세요.")
            if id:
                s.check_version(s.one(c, ctx, "authority_rule", id, True), values)
            result = policy.rule_mutation(c, ctx, id, operation, values)
        else:
            if not id:
                identities.require_active(c, ctx, values["delegate_person_id"])
                if values.get("document_kind") not in {None, "GENERAL"}:
                    raise s.invalid(
                        "documentKind", "회사에서는 일반 기안만 위임할 수 있습니다."
                    )
                p = s.one(c, ctx, "person", identity["id"])
                docs = s.rows(
                    c,
                    f"SELECT * FROM gw.approval_document WHERE {s.S} AND status='IN_REVIEW' AND kind='GENERAL'",
                    s.params(ctx),
                )
                if not any(
                    any(
                        x["delegation"] is None
                        for x in policy.eligible(c, ctx, d, p, company_mode=True)
                    )
                    for d in docs
                ):
                    raise s.invalid(
                        "delegatePersonId",
                        "현재 본인에게 배정된 미처리 결재 단계가 필요합니다.",
                    )
            result = policy.delegation_mutation(
                c, ctx, id, {**values, "acting_person_id": identity["id"]}
            )
        identities.bump(c, ctx)
        return result

    return company.action(
        context,
        company_id,
        f"company.{kind}.{id}.{operation}",
        key,
        values,
        run,
        authorize=authorize,
    )
