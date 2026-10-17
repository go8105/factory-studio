"""FS-030 TX-G1..6. Workspace lock serializes transitions, numbering and master edits.
Cross-solution reads use ERP's provider only. Submitted content and events never update.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fs.common.engine import action as run_action
from fs.common.engine import read as read_transaction
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp import interface as erp

S = "workspace_id=:w AND generation_id=:g"
TABLES = {
    "people": "person",
    "routes": "approval_route",
    "documents": "approval_document",
    "posts": "board_post",
}


def params(ctx, **kw):
    return {"w": ctx.workspace_id, "g": ctx.generation_id, **kw}


def invalid(field, message):
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def conflict(reason, **details):
    messages = {
        "VERSION_CONFLICT": "다른 작업으로 변경되었습니다. 서버 상태를 다시 확인하세요.",
        "WRONG_ACTOR": "작성 담당자 역할로 전환하세요.",
        "NOT_CURRENT_STEP": "현재 결재 단계의 담당자만 처리할 수 있습니다.",
        "PERSON_INACTIVE": "비활성 담당자는 처리할 수 없습니다.",
        "PERSON_IN_USE": "초안 또는 진행 결재에서 사용 중인 담당자입니다.",
        "LAST_BOARD_ADMIN": "마지막 활성 게시판 운영 담당자는 유지해야 합니다.",
        "IMMUTABLE_DOCUMENT": "현재 상태에서는 이 작업을 할 수 없습니다.",
        "SOURCE_CHANGED": "원문이 바뀌었습니다. 원문을 갱신하고 다시 검토하세요.",
        "SOURCE_MODULE_DISABLED": "ERP가 꺼져 있거나 아직 열지 않아 원문을 조회할 수 없습니다. ERP를 한 번 열면 조회됩니다.",
        "SOURCE_MISSING": "원문이 없습니다.",
        "SOURCE_CANCELLED": "취소된 원문은 상신할 수 없습니다.",
        "ACTIVE_APPROVAL_EXISTS": "동일 원천의 결재가 진행 중입니다.",
        "WITHDRAW_NOT_ALLOWED": "첫 승인 이후에는 회수할 수 없습니다.",
        "SUCCESSOR_EXISTS": "이미 후속 문서가 있습니다.",
        "ROUTE_INACTIVE": "비활성 결재선은 선택할 수 없습니다.",
        "DUPLICATE_CODE": "이미 사용 중인 코드입니다.",
        "AUTHORITY_OVERLAP": "같은 유형·통화의 전결 금액과 기간이 겹칩니다.",
        "AUTHORITY_AMBIGUOUS": "적용할 전결 규칙이 여러 개입니다. 규칙을 확인하세요.",
        "AUTHORITY_IN_USE": "상신 문서에서 사용한 규칙은 내용 수정·삭제가 불가합니다. 비활성화 후 새 규칙을 등록하세요.",
        "DELEGATION_OVERLAP_OR_CHAIN": "위임 기간이 겹치거나 연쇄 위임이 됩니다.",
        "DELEGATION_REVOKED": "이미 회수한 위임입니다.",
        "ASSIGNMENT_REQUIRED": "대리 처리할 담당 단계를 선택하세요.",
        "SOURCE_NOT_IMPLEMENTED": "해당 솔루션의 원천 조회 기능이 아직 구현되지 않았습니다.",
    }
    return ApiError(
        409,
        "PRECONDITION_NOT_MET",
        messages.get(reason, "현재 상태를 다시 확인해 주세요."),
        {"reason": reason, **details},
    )


def rows(c, sql, p):
    return [dict(r) for r in c.execute(text(sql), p).mappings()]


def one(c, ctx, table, id, lock=False):
    result = rows(
        c,
        f"SELECT * FROM gw.{table} WHERE {S} AND id=:id"
        + (" FOR UPDATE" if lock else ""),
        params(ctx, id=id),
    )
    if not result:
        raise ApiError(404, "NOT_FOUND", "현재 공간에서 대상을 찾을 수 없습니다.")
    return result[0]


def wire(value, key=""):
    if isinstance(value, dict):
        return {
            k.split("_")[0] + "".join(p.title() for p in k.split("_")[1:]): wire(v, k)
            for k, v in value.items()
            if k not in {"workspace_id", "generation_id", "actor_key"}
        }
    if isinstance(value, list):
        return [wire(v) for v in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if value is not None and (
        key == "id" or key.endswith("_id") or key in {"serial", "submission_order"}
    ):
        return str(value)
    return value


def insert(c, ctx, table, values):
    values = {
        "workspace_id": ctx.workspace_id,
        "generation_id": ctx.generation_id,
        **values,
    }
    expressions = [
        f"CAST(:{k} AS jsonb)" if k in {"source_snapshot", "details"} else ":" + k
        for k in values
    ]
    data = {
        k: json.dumps(v, ensure_ascii=False)
        if k in {"source_snapshot", "details"} and v is not None
        else v
        for k, v in values.items()
    }
    return c.execute(
        text(
            f"INSERT INTO gw.{table} ({','.join(values)}) VALUES ({','.join(expressions)}) RETURNING id"
        ),
        data,
    ).scalar_one()


def update(c, ctx, table, id, values):
    assignments = [
        f"{k}=CAST(:{k} AS jsonb)"
        if k in {"source_snapshot", "details"}
        else f"{k}=:{k}"
        for k in values
    ]
    data = {
        k: json.dumps(v, ensure_ascii=False)
        if k in {"source_snapshot", "details"} and v is not None
        else v
        for k, v in values.items()
    }
    c.execute(
        text(
            f"UPDATE gw.{table} SET {','.join([*assignments, 'version=version+1'])} WHERE {S} AND id=:id"
        ),
        params(ctx, id=id, **data),
    )


def now(c):
    return c.execute(text("SELECT clock_timestamp()")).scalar_one()


def number(c, ctx, table, column="serial"):
    return c.execute(
        text(f"SELECT coalesce(max({column}),0)+1 FROM gw.{table} WHERE {S}"),
        params(ctx),
    ).scalar_one()


def check_version(row, values):
    if row["version"] != values["expected_version"]:
        raise conflict(
            "VERSION_CONFLICT", version=row["version"], status=row.get("status")
        )


def actor(c, ctx, id):
    p = one(c, ctx, "person", id)
    if not p["is_active"]:
        raise conflict("PERSON_INACTIVE")
    return p


def identity(p, prefix):
    return {
        prefix + "_id": p["id"],
        prefix + "_code": p["code"],
        prefix + "_name": p["name"],
        prefix + "_job_role": p["job_role"],
    }


def authored(row, p, field="drafter_id"):
    if row[field] != p["id"]:
        raise conflict("WRONG_ACTOR")


def draft(row):
    if row["status"] != "DRAFT":
        raise conflict(
            "IMMUTABLE_DOCUMENT", status=row["status"], version=row["version"]
        )


def reason(values, required=False):
    r = (values.get("reason") or "").strip() or None
    if required and (not r or len(r) < 2):
        raise invalid("reason", "사유를 2~500자로 입력하세요.")
    return r


def event(c, ctx, table, row, p, kind, r=None, step=None, on_behalf=None, details=None):
    isdoc = table == "approval_document"
    et = "approval_event" if isdoc else "board_event"
    fk = "document_id" if isdoc else "post_id"
    seq = c.execute(
        text(
            f"SELECT coalesce(max(event_seq),0)+1 FROM gw.{et} WHERE {S} AND {fk}=:id"
        ),
        params(ctx, id=row["id"]),
    ).scalar_one()
    values = {
        fk: row["id"],
        "event_seq": seq,
        "event_type": kind,
        "acting_person_id": p["id"],
        "person_code": p["code"],
        "person_name": p["name"],
        "person_job_role": p["job_role"],
        "actor_kind": ctx.actor_kind,
        "actor_key": ctx.actor_key,
        "reason": r,
        ("document_version" if isdoc else "post_version"): row["version"],
    }
    if isdoc:
        values.update(step_seq=step, on_behalf_of_person_id=on_behalf, details=details)
    insert(c, ctx, et, values)


SOURCE_KINDS = {
    "ERP_PURCHASE": "PURCHASE_INVOICE",
    "ERP_PO": "PURCHASE_ORDER",
    "ERP_EXPENSE": "EXPENSE_CLAIM",
    "PLM_ECO": "ECO",
}


def provider(c, ctx, kind, no=None, **query):
    # 제공된 계약만 연결한다. 신규 ERP 유형은 제공 측 선언을 기다린다.
    if kind == "ECO":
        try:
            from fs.plm import interface as plm
        except ModuleNotFoundError as e:
            if e.name not in {"fs.plm", "fs.plm.interface"}:
                raise
            return {"availability": "UNIMPLEMENTED"}
        if not hasattr(plm, "eco_for_approval"):
            return {"availability": "UNIMPLEMENTED"}
        if no is None:
            return {
                "availability": "AVAILABLE",
                "value": {"rows": [], "total": 0, "manualEntry": True},
            }
        result = plm.eco_for_approval(c, ctx, no)
    else:
        supported = getattr(erp, "APPROVAL_KINDS", ("PURCHASE_INVOICE",))
        if kind not in supported:
            return {"availability": "UNIMPLEMENTED"}
        result = (
            erp.approval_document(c, ctx, kind, no)
            if no is not None
            else erp.approval_documents(c, ctx, kind, **query)
        )
    return {
        "availability": "DISABLED" if result is None else "AVAILABLE",
        "value": result,
    }


def source(c, ctx, no, kind="PURCHASE_INVOICE"):
    result = provider(c, ctx, kind, no)
    if result["availability"] == "UNIMPLEMENTED":
        raise conflict("SOURCE_NOT_IMPLEMENTED")
    s = result["value"]
    if s is None:
        raise conflict("SOURCE_MODULE_DISABLED")
    if not s["found"]:
        raise conflict("SOURCE_MISSING")
    if s["status"] in {"cancelled", "CANCELLED", "withdrawn", "WITHDRAWN"}:
        raise conflict("SOURCE_CANCELLED")
    return {
        "source_kind": kind,
        "source_no": no,
        "source_snapshot": s["snapshot"],
        "source_digest": s["digest"],
        "source_status": s["status"],
        "amount": s["snapshot"].get("totalAmount"),
        "currency": s["snapshot"].get("currency"),
    }


def comparison(c, ctx, row):
    if row["kind"] == "GENERAL":
        return None
    result = provider(c, ctx, row["source_kind"], row["source_no"])
    s = result.get("value")
    present = s is not None and s["found"]
    return {
        "availability": result["availability"]
        if not s
        else ("AVAILABLE" if present else "MISSING"),
        "contentChanged": s["digest"] != row["source_digest"] if present else None,
        "statusChanged": s["status"] != row["source_status"] if present else None,
        "currentStatus": s["status"] if present else None,
    }


def steps(c, ctx, id, *, company_mode=False):
    result = rows(
        c,
        f"SELECT * FROM gw.approval_step WHERE {S} AND document_id=:id ORDER BY seq,id",
        params(ctx, id=id),
    )
    if company_mode:
        assignments = rows(
            c,
            f"SELECT DISTINCT ON (step_id) step_id,person_id FROM gw.step_assignment WHERE {S} AND document_id=:id ORDER BY step_id,assignment_seq DESC",
            params(ctx, id=id),
        )
        by_step = {a["step_id"]: a["person_id"] for a in assignments}
        for step in result:
            step["original_person_id"] = step["person_id"]
            step["person_id"] = by_step.get(step["id"], step["person_id"])
    return result


def route_people(c, ctx, id, drafter=None, legacy=False):
    from fs.gw import policy

    route = one(c, ctx, "approval_route", id)
    if not route["is_active"]:
        raise conflict("ROUTE_INACTIVE")
    rr = rows(
        c,
        f"SELECT * FROM gw.route_step WHERE {S} AND route_id=:id ORDER BY seq,id",
        params(ctx, id=id),
    )
    return route, policy.participants(c, ctx, rr, drafter, legacy)


def write_steps(c, ctx, id, pp):
    from fs.gw import policy

    c.execute(
        text(f"DELETE FROM gw.approval_step WHERE {S} AND document_id=:id"),
        params(ctx, id=id),
    )
    for p in pp:
        insert(
            c,
            ctx,
            "approval_step",
            {
                "document_id": id,
                "seq": p["seq"],
                "participant_role": p["participant_role"],
                **identity(p, "person"),
                **policy.organization(c, ctx, p),
            },
        )


def successor(c, ctx, table, id):
    col = "previous_document_id" if table == "approval_document" else "previous_post_id"
    found = rows(
        c,
        f"SELECT id,{'document_no' if table == 'approval_document' else 'post_no'} FROM gw.{table} WHERE {S} AND {col}=:id",
        params(ctx, id=id),
    )
    return found[0] if found else None


def detail(c, ctx, kind, id, person=None):
    table = TABLES[kind]
    row = one(c, ctx, table, id)
    if kind == "posts":
        from fs.gw.collaboration import missing, post_visible

        if not post_visible(row, one(c, ctx, "person", person) if person else None):
            missing()
    if kind == "routes":
        row["steps"] = rows(
            c,
            "SELECT r.seq,r.person_id,r.participant_role,p.name,p.job_role,p.is_active FROM gw.route_step r JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(r.workspace_id,r.generation_id,r.person_id) WHERE r.workspace_id=:w AND r.generation_id=:g AND r.route_id=:id ORDER BY r.seq,r.id",
            params(ctx, id=id),
        )
    if kind in {"documents", "posts"}:
        doc = kind == "documents"
        et = "approval_event" if doc else "board_event"
        fk = "document_id" if doc else "post_id"
        row["events"] = rows(
            c,
            f"SELECT * FROM gw.{et} WHERE {S} AND {fk}=:id ORDER BY event_seq",
            params(ctx, id=id),
        )
        row["successor"] = successor(c, ctx, table, id)
        row["available_actions"] = []
        if doc:
            row["steps"] = steps(c, ctx, id)
            row["source_comparison"] = comparison(c, ctx, row)
            submission = next(
                (e for e in row["events"] if e["event_type"] == "SUBMITTED"), None
            )
            row["authority_snapshot"] = (
                (submission.get("details") or {}).get("authorityRule")
                if submission
                else None
            )
            row["action_steps"] = []
        if person is not None:
            p = one(c, ctx, "person", person)
            if p["is_active"]:
                owns = row["drafter_id" if doc else "author_id"] == p["id"]
                if doc:
                    if owns and row["status"] == "DRAFT":
                        row["available_actions"] = [
                            "edit",
                            "select-route",
                            "submit",
                        ] + (["refresh-source"] if row["kind"] != "GENERAL" else [])
                    if (
                        owns
                        and row["status"] == "IN_REVIEW"
                        and not any(
                            s["status"] == "APPROVED"
                            and s["participant_role"] != "REFERENCE"
                            for s in row["steps"]
                        )
                    ):
                        row["available_actions"] = ["withdraw"]
                    if (
                        owns
                        and row["status"] in {"REJECTED", "WITHDRAWN"}
                        and not row["successor"]
                    ):
                        row["available_actions"] = ["resubmit"]
                    from fs.gw import policy

                    eligible = policy.eligible(c, ctx, row, p, row["steps"])
                    row["action_steps"] = [
                        {
                            "step_id": x["step"]["id"],
                            "person_name": x["step"]["person_name"],
                            "participant_role": x["step"]["participant_role"],
                            "delegation_id": x["delegation"]["id"]
                            if x["delegation"]
                            else None,
                        }
                        for x in eligible
                    ]
                    for x in eligible:
                        row["available_actions"].extend(
                            {
                                "APPROVER": ["approve", "reject"],
                                "CONSENT": ["consent", "oppose"],
                                "REFERENCE": ["reference"],
                            }[x["step"]["participant_role"]]
                        )
                    row["available_actions"] = list(
                        dict.fromkeys(row["available_actions"])
                    )
                elif owns and (
                    row["board_kind"] == "FREE" or p["job_role"] == "BOARD_ADMIN"
                ):
                    row["available_actions"] = (
                        ["edit", "publish"]
                        if row["status"] == "DRAFT"
                        else (
                            (["withdraw"] if row["status"] == "PUBLISHED" else [])
                            + (["correct"] if not row["successor"] else [])
                        )
                    )
    return wire(row)


def read(context, kind, id=None, **q):
    with read_transaction() as c:
        ctx = read_scope(c, context, "gw")
        person = q.get("person_id")
        if person is not None:
            one(c, ctx, "person", person)
        if kind == "sources":
            source_kind = q.get("source_kind", "PURCHASE_INVOICE")
            result = provider(
                c,
                ctx,
                source_kind,
                id,
                search=q.get("search", ""),
                offset=q.get("offset", 0),
                limit=q.get("limit", 50),
            )
            value = result.get("value")
            if id is not None and value is not None and not value["found"]:
                raise ApiError(404, "NOT_FOUND", "원문이 없습니다.")
            return {
                "enabled": value is not None,
                "availability": result["availability"],
                **(value or {"rows": [], "total": 0}),
            }
        if kind == "dashboard":
            return dashboard(c, ctx, person)
        if id is not None:
            return detail(c, ctx, kind, id, person)
        return listing(c, ctx, kind, q)


def listing(c, ctx, kind, q):
    table = TABLES[kind]
    where = S
    p = params(
        ctx,
        search=q.get("search", ""),
        offset=q.get("offset", 0),
        limit=q.get("limit", 50),
    )
    person = q.get("person_id")
    search_columns = (
        ["name", "code", "coalesce(hr_employee_code,'')"]
        if kind == "people"
        else ["name", "code"]
        if kind == "routes"
        else ["title", "document_no" if kind == "documents" else "post_no"]
    )
    where += (
        " AND ("
        + " OR ".join(
            f"strpos(lower({column}),lower(:search))>0" for column in search_columns
        )
        + ")"
    )
    q = {**q, "kind": q.get("document_kind")}
    for name in ["status", "kind", "board_kind"]:
        if q.get(name):
            where += f" AND {name}=:{name}"
            p[name] = q[name]
    if kind == "documents":
        box = q.get("box", "all")
        if box in {"drafts", "pending"} and person is None:
            raise invalid("personId", "담당자를 선택하세요.")
        if box == "drafts":
            where += " AND drafter_id=:person"
            p["person"] = person
        if box == "archive":
            where += " AND status IN ('APPROVED','REJECTED','WITHDRAWN')"
        if box == "pending":
            where += " AND status='IN_REVIEW' AND EXISTS (SELECT 1 FROM gw.approval_step s WHERE (s.workspace_id,s.generation_id,s.document_id)=(approval_document.workspace_id,approval_document.generation_id,approval_document.id) AND s.seq=approval_document.current_step AND s.status='WAITING' AND (s.person_id=:person OR EXISTS (SELECT 1 FROM gw.delegation d WHERE (d.workspace_id,d.generation_id,d.delegator_person_id)=(s.workspace_id,s.generation_id,s.person_id) AND d.delegate_person_id=:person AND d.revoked_at IS NULL)))"
            p["person"] = person
    if kind == "posts":
        p["viewer"] = person
        where += " AND (visibility='WORKSPACE' OR author_id=:viewer OR audience_org_id=(SELECT organization_unit_id FROM gw.person WHERE workspace_id=:w AND generation_id=:g AND id=:viewer AND is_active))"
    if kind == "posts" and q.get("mine"):
        if person is None:
            raise invalid("personId", "담당자를 선택하세요.")
        where += " AND author_id=:person"
        p["person"] = person
    sort = q.get("sort", "serial")
    if kind in {"people", "routes"}:
        sort = "code"
    if kind == "documents" and q.get("box") == "pending":
        from fs.gw import policy

        person_row = one(c, ctx, "person", person)
        candidates = rows(
            c, f"SELECT * FROM gw.{table} WHERE {where} ORDER BY {sort} DESC,id DESC", p
        )
        t = now(c)
        found = [r for r in candidates if policy.eligible(c, ctx, r, person_row, t=t)]
        return {
            "rows": wire(found[p["offset"] : p["offset"] + p["limit"]]),
            "total": len(found),
            "offset": p["offset"],
            "limit": p["limit"],
        }
    found = rows(
        c,
        f"SELECT * FROM gw.{table} WHERE {where} ORDER BY {sort} DESC,id DESC OFFSET :offset LIMIT :limit",
        p,
    )
    if kind == "people":
        from fs.gw.organization import enrich_people

        found = enrich_people(c, ctx, found)
    if kind == "routes":
        found = [detail(c, ctx, kind, r["id"]) for r in found]
    total = c.execute(
        text(f"SELECT count(*) FROM gw.{table} WHERE {where}"), p
    ).scalar_one()
    return {
        "rows": wire(found),
        "total": total,
        "offset": p["offset"],
        "limit": p["limit"],
    }


def dashboard(c, ctx, person):
    if person is None:
        return {"needsPerson": True}
    actor(c, ctx, person)
    counts = {
        s: c.execute(
            text(
                f"SELECT count(*) FROM gw.approval_document WHERE {S} AND drafter_id=:person AND status=:status"
            ),
            params(ctx, person=person, status=s),
        ).scalar_one()
        for s in ["DRAFT", "IN_REVIEW", "APPROVED", "REJECTED", "WITHDRAWN"]
    }
    return {
        "needsPerson": False,
        "drafts": counts["DRAFT"],
        "inReview": counts["IN_REVIEW"],
        "closed": sum(counts[s] for s in ["APPROVED", "REJECTED", "WITHDRAWN"]),
        "pending": listing(
            c, ctx, "documents", {"box": "pending", "person_id": person, "limit": 5}
        )["total"],
        "recentDocuments": listing(c, ctx, "documents", {"box": "archive", "limit": 5})[
            "rows"
        ],
        "recentPosts": listing(
            c, ctx, "posts", {"status": "PUBLISHED", "limit": 5, "person_id": person}
        )["rows"],
    }


def audit(
    c, ctx, kind, entity, action, result, table=None, summary=None, entity_kind=None
):
    c.execute(
        text(
            "INSERT INTO core.audit_event(workspace_id,actor_user_id,action,entity_kind,entity_key,summary,actor_kind,actor_key,scope_kind,created_at) VALUES(:w,:user,:action,:entity,:id,CAST(:summary AS jsonb),:ak,:actor,'WORKSPACE',clock_timestamp())"
        ),
        {
            "w": ctx.workspace_id,
            "user": ctx.user_id,
            "action": f"gw.{kind}.{action}",
            "entity": entity_kind or "gw." + (table or TABLES[kind]),
            "id": str(entity),
            "summary": json.dumps(
                summary
                if summary is not None
                else {"version": result.get("version"), "status": result.get("status")}
            ),
            "ak": ctx.actor_kind,
            "actor": ctx.actor_key,
        },
    )


def mutate(context, kind, id, action, values, key):
    def run(c, ctx):
        before = (
            one(c, ctx, TABLES[kind], id)
            if id and kind in {"documents", "posts"}
            else None
        )
        entity = (
            master(c, ctx, kind, id, values)
            if kind in {"people", "routes"}
            else document(c, ctx, id, action, values)
            if kind == "documents"
            else post(c, ctx, id, action, values)
        )
        if kind in {"documents", "posts"}:
            from fs.gw.collaboration import business_notifications

            business_notifications(
                c, ctx, kind, before, one(c, ctx, TABLES[kind], entity)
            )
        result = detail(c, ctx, kind, entity, values.get("acting_person_id"))
        audit(c, ctx, kind, entity, action, result)
        return result, "gw." + TABLES[kind], entity

    try:
        return run_action(
            "gw",
            context,
            f"gw.{kind}.{id or 'new'}.{action}",
            key,
            values,
            run,
            201 if id is None else 200,
        )
    except IntegrityError as e:
        if getattr(e.orig, "sqlstate", None) == "23505":
            raise conflict(
                "DUPLICATE_CODE"
                if kind in {"people", "routes"}
                else "ACTIVE_APPROVAL_EXISTS"
            ) from e
        raise


def master(c, ctx, kind, id, v):
    table = TABLES[kind]
    row = one(c, ctx, table, id, True) if id else None
    if row:
        check_version(row, v)
    if kind == "people":
        if row and (
            not v["is_active"]
            or (row["job_role"] == "BOARD_ADMIN" and v["job_role"] != "BOARD_ADMIN")
        ):
            if (
                row["is_active"]
                and row["job_role"] == "BOARD_ADMIN"
                and c.execute(
                    text(
                        f"SELECT count(*) FROM gw.person WHERE {S} AND is_active AND job_role='BOARD_ADMIN'"
                    ),
                    params(ctx),
                ).scalar_one()
                <= 1
            ):
                raise conflict("LAST_BOARD_ADMIN")
            used = c.execute(
                text(
                    f"""SELECT count(*) FROM gw.board_post WHERE {S} AND author_id=:id AND status='DRAFT' AND (:inactive OR board_kind='NOTICE')"""
                ),
                params(ctx, id=id, inactive=not v["is_active"]),
            ).scalar_one()
            if not v["is_active"]:
                used += c.execute(
                    text(
                        f"""SELECT count(*) FROM gw.approval_document d WHERE {S} AND ((drafter_id=:id AND status IN ('DRAFT','IN_REVIEW')) OR (status='IN_REVIEW' AND EXISTS (SELECT 1 FROM gw.approval_step a WHERE (a.workspace_id,a.generation_id,a.document_id)=(d.workspace_id,d.generation_id,d.id) AND a.person_id=:id AND a.status='WAITING')))"""
                    ),
                    params(ctx, id=id),
                ).scalar_one()
            if used:
                raise conflict("PERSON_IN_USE", count=used)
        if row and row["hr_employee_code"] and v["name"] != row["name"]:
            raise invalid(
                "name", "HR 연결 담당자의 이름은 HR에서 가져오기로 갱신하세요."
            )
        data = {k: v[k] for k in ["name", "job_role"]}
        if row:
            data["is_active"] = v["is_active"]
    else:
        from fs.gw import policy

        pp = policy.participants(c, ctx, v["steps"])
        data = {"name": v["name"]}
        if row:
            data["is_active"] = v["is_active"]
    if row:
        update(c, ctx, table, id, data)
    else:
        id = insert(c, ctx, table, {"code": v["code"], **data})
    if kind == "routes":
        c.execute(
            text(f"DELETE FROM gw.route_step WHERE {S} AND route_id=:id"),
            params(ctx, id=id),
        )
        for p in pp:
            insert(
                c,
                ctx,
                "route_step",
                {
                    "route_id": id,
                    "seq": p["seq"],
                    "person_id": p["id"],
                    "participant_role": p["participant_role"],
                },
            )
    return id


def document(c, ctx, id, action, v, *, company_mode=False):
    p = actor(c, ctx, v["acting_person_id"])
    table = "approval_document"
    if id is None:
        route, pp = route_people(c, ctx, v["route_id"], p["id"])
        serial = number(c, ctx, table)
        data = {
            "serial": serial,
            "document_no": f"GW-{serial:06d}",
            "kind": v["kind"],
            "policy_version": 2,
            "title": v["title"],
            "body": v["body"],
            **identity(p, "drafter"),
            "route_id": route["id"],
            "route_code": route["code"],
            "route_name": route["name"],
        }
        if v["kind"] != "GENERAL":
            if not v.get("source_no"):
                raise invalid("sourceNo", "결재 원문을 선택하세요.")
            if v.get("amount") is not None or v.get("currency") is not None:
                raise invalid("amount", "금액은 서버 원문을 사용합니다.")
            data.update(source(c, ctx, v["source_no"], SOURCE_KINDS[v["kind"]]))
        else:
            if v.get("source_no") is not None:
                raise invalid("sourceNo", "일반 기안은 원천을 지정할 수 없습니다.")
            data.update(money(v))
        id = insert(c, ctx, table, data)
        write_steps(c, ctx, id, pp)
        event(c, ctx, table, one(c, ctx, table, id), p, "CREATED")
        return id
    row = one(c, ctx, table, id, True)
    check_version(row, v)
    if action not in {"approve", "reject", "consent", "oppose", "reference"}:
        authored(row, p)
    changes = {}
    evt = ""
    r = None
    step = None
    on_behalf = None
    event_details = None
    skipped = []
    if action in {"edit", "select-route", "refresh-source", "submit"}:
        draft(row)
        if action == "edit":
            changes = {"title": v["title"], "body": v["body"]}
            if row["kind"] == "GENERAL":
                changes.update(money(v))
            elif "amount" in v or "currency" in v:
                raise invalid("amount", "원문 금액은 바꿀 수 없습니다.")
            evt = "DRAFT_SAVED"
        if action == "select-route":
            route, pp = route_people(
                c, ctx, v["route_id"], p["id"], legacy=row["policy_version"] == 1
            )
            write_steps(c, ctx, id, pp)
            changes = {
                "route_id": route["id"],
                "route_code": route["code"],
                "route_name": route["name"],
            }
            evt = "ROUTE_SELECTED"
        if action == "refresh-source":
            if row["kind"] == "GENERAL":
                raise invalid("kind", "외부 원문 기안만 원문을 갱신할 수 있습니다.")
            changes = source(c, ctx, row["source_no"], row["source_kind"])
            evt = "SOURCE_REFRESHED"
        if action == "submit":
            route = one(c, ctx, "approval_route", row["route_id"])
            if not route["is_active"]:
                raise conflict("ROUTE_INACTIVE")
            from fs.gw import policy

            ss = steps(c, ctx, id, company_mode=company_mode)
            pp = policy.participants(
                c, ctx, ss, p["id"], legacy=row["policy_version"] == 1
            )
            if row["kind"] != "GENERAL":
                current = source(c, ctx, row["source_no"], row["source_kind"])
                if (
                    current["source_digest"] != row["source_digest"]
                    or current["source_status"] != row["source_status"]
                ):
                    raise conflict("SOURCE_CHANGED")
                if c.execute(
                    text(
                        f"SELECT 1 FROM gw.approval_document WHERE {S} AND source_kind=:kind AND source_no=:no AND status='IN_REVIEW'"
                    ),
                    params(ctx, kind=row["source_kind"], no=row["source_no"]),
                ).first():
                    raise conflict("ACTIVE_APPROVAL_EXISTS")
            write_steps(c, ctx, id, pp)
            changes = {
                "status": "IN_REVIEW",
                "current_step": 1,
                "submission_order": number(c, ctx, table, "submission_order"),
                "submitted_at": now(c),
                **identity(p, "drafter"),
            }
            t = changes["submitted_at"]
            org = policy.organization(c, ctx, p)
            changes.update(
                drafter_org_code=org["organization_code"],
                drafter_org_name=org["organization_name"],
            )
            rule = policy.authority(c, ctx, row, t)
            changes["authority_rule_id"] = rule["id"] if rule else None
            event_details = {
                "policyVersion": row["policy_version"],
                "authorityRule": wire(rule) if rule else None,
                "appliedMonth": t.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m"),
            }
            if rule:
                for seq in sorted(
                    {s["seq"] for s in pp if s["seq"] > rule["final_seq"]}
                ):
                    skipped.extend(policy.skip(c, ctx, id, seq))
            evt = "SUBMITTED"
    elif action in {"approve", "reject", "consent", "oppose", "reference", "withdraw"}:
        from fs.gw import policy

        if row["status"] != "IN_REVIEW":
            raise conflict("IMMUTABLE_DOCUMENT", status=row["status"])
        if action == "withdraw":
            if any(
                s["status"] == "APPROVED" and s["participant_role"] != "REFERENCE"
                for s in steps(c, ctx, id, company_mode=company_mode)
            ):
                raise conflict("WITHDRAW_NOT_ALLOWED")
            r = reason(v, True)
            changes = {"status": "WITHDRAWN", "closed_at": now(c), "current_step": None}
            evt = "WITHDRAWN"
            skipped = policy.skip(c, ctx, id)
        else:
            changes, evt, r, step, grant, event_details, skipped = policy.decision(
                c, ctx, row, p, action, v, company_mode=company_mode
            )
            on_behalf = (
                event_details
                and next(
                    s["person_id"]
                    for s in steps(c, ctx, id, company_mode=company_mode)
                    if str(s["id"]) == event_details["stepId"]
                )
                if grant
                else None
            )
    elif action == "resubmit":
        if row["status"] not in {"REJECTED", "WITHDRAWN"}:
            raise conflict("IMMUTABLE_DOCUMENT")
        follow = successor(c, ctx, table, id)
        if follow:
            raise conflict("SUCCESSOR_EXISTS", successor=wire(follow))
        serial = number(c, ctx, table)
        data = {
            k: row[k]
            for k in [
                "kind",
                "title",
                "body",
                "drafter_id",
                "drafter_code",
                "drafter_name",
                "drafter_job_role",
                "route_id",
                "route_code",
                "route_name",
                "source_kind",
                "source_no",
                "source_snapshot",
                "source_digest",
                "source_status",
                "amount",
                "currency",
                "policy_version",
            ]
        }
        data.update(
            serial=serial,
            document_no=f"GW-{serial:06d}",
            previous_document_id=id,
            round_no=row["round_no"] + 1,
        )
        new = insert(c, ctx, table, data)
        if company_mode:
            from fs.gw import policy

            pp = policy.participants(
                c, ctx, steps(c, ctx, id, company_mode=True), p["id"]
            )
            write_steps(c, ctx, new, pp)
        else:
            for s in steps(c, ctx, id, company_mode=company_mode):
                insert(
                    c,
                    ctx,
                    "approval_step",
                    {
                        "document_id": new,
                        **{
                            k: s[k]
                            for k in [
                                "seq",
                                "person_id",
                                "person_code",
                                "person_name",
                                "person_job_role",
                                "participant_role",
                                "organization_code",
                                "organization_name",
                            ]
                        },
                    },
                )
        event(c, ctx, table, one(c, ctx, table, new), p, "RESUBMISSION_CREATED")
        return new
    else:
        raise ApiError(404, "NOT_FOUND", "지원하지 않는 작업입니다.")
    update(c, ctx, table, id, changes)
    saved = one(c, ctx, table, id)
    event(c, ctx, table, saved, p, evt, r, step, on_behalf, event_details)
    if saved["policy_version"] == 2:
        for skipped_step in skipped:
            event(
                c,
                ctx,
                table,
                saved,
                p,
                "SKIPPED",
                step=skipped_step["seq"],
                details={
                    "stepId": str(skipped_step["id"]),
                    "personName": skipped_step["person_name"],
                    "participantRole": skipped_step["participant_role"],
                    "cause": evt,
                },
            )
    return id


def money(v):
    amount = v.get("amount")
    currency = v.get("currency")
    if (amount is None) != (currency is None):
        raise invalid("amount", "금액과 통화를 함께 입력하거나 비워 주세요.")
    return {"amount": amount, "currency": currency}


def post(c, ctx, id, action, v, *, notice_allowed=None):
    p = actor(c, ctx, v["acting_person_id"])
    table = "board_post"
    row = one(c, ctx, table, id, True) if id else None
    if row:
        check_version(row, v)
        authored(row, p, "author_id")
    board = row["board_kind"] if row else v["board_kind"]
    if board == "NOTICE" and (
        (p["job_role"] != "BOARD_ADMIN")
        if notice_allowed is None
        else not notice_allowed
    ):
        raise conflict("WRONG_ACTOR")
    r = None
    visibility = v.get("visibility", row["visibility"] if row else "WORKSPACE")
    org = v.get("audience_org_id", row["audience_org_id"] if row else None)
    if visibility == "ORG":
        if (
            board != "NOTICE"
            or not org
            or (
                action in {"create", "edit", "publish"}
                and not one(c, ctx, "organization_unit", org)["is_active"]
            )
        ):
            raise invalid("audienceOrgId", "부서 공지는 활성 조직을 선택하세요.")
    elif org is not None:
        raise invalid("audienceOrgId", "전체 공개 글은 부서를 지정할 수 없습니다.")
    if row is None:
        serial = number(c, ctx, table)
        id = insert(
            c,
            ctx,
            table,
            {
                "serial": serial,
                "post_no": f"GB-{serial:06d}",
                "board_kind": board,
                "visibility": visibility,
                "audience_org_id": org,
                **identity(p, "author"),
                "title": v["title"],
                "body": v["body"],
            },
        )
        evt = "CREATED"
    elif action in {"edit", "publish"}:
        draft(row)
        values = (
            {
                "title": v["title"],
                "body": v["body"],
                "visibility": visibility,
                "audience_org_id": org,
            }
            if action == "edit"
            else {
                "status": "PUBLISHED",
                "published_at": now(c),
                **identity(p, "author"),
            }
        )
        update(c, ctx, table, id, values)
        evt = "DRAFT_SAVED" if action == "edit" else "PUBLISHED"
    elif action == "withdraw":
        if row["status"] != "PUBLISHED":
            raise conflict("IMMUTABLE_DOCUMENT")
        r = reason(v, True)
        update(
            c,
            ctx,
            table,
            id,
            {"status": "WITHDRAWN", "withdrawn_at": now(c), "withdraw_reason": r},
        )
        evt = "WITHDRAWN"
    elif action == "correct":
        if row["status"] == "DRAFT":
            raise conflict("IMMUTABLE_DOCUMENT")
        follow = successor(c, ctx, table, id)
        if follow:
            raise conflict("SUCCESSOR_EXISTS", successor=wire(follow))
        serial = number(c, ctx, table)
        id = insert(
            c,
            ctx,
            table,
            {
                "serial": serial,
                "post_no": f"GB-{serial:06d}",
                "previous_post_id": id,
                "board_kind": board,
                "visibility": visibility,
                "audience_org_id": org,
                **identity(p, "author"),
                "title": row["title"],
                "body": row["body"],
            },
        )
        evt = "CORRECTION_CREATED"
    else:
        raise ApiError(404, "NOT_FOUND", "지원하지 않는 작업입니다.")
    event(c, ctx, table, one(c, ctx, table, id), p, evt, r)
    return id
