"""GW-b 결재 정책 v2. 상신 고정·병렬/합의·전결·처리 시점 위임 검사."""

from __future__ import annotations

from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import text

from fs.common import master
from fs.common.engine import action, read
from fs.common.scope import read_scope
from fs.gw import service as gw

AUTHORITY = master.Master(
    module="gw",
    table="gw.authority_rule",
    columns=(
        "code",
        "document_kind",
        "currency",
        "amount_from",
        "amount_to",
        "final_seq",
        "effective_from",
        "effective_to",
        "is_active",
        "version",
    ),
    sort={"code": "code"},
    default_sort="code ASC",
    unique=("code",),
    references=(
        master.Reference("gw.approval_document", "authority_rule_id", "결재 문서"),
    ),
    duplicate_field="code",
    duplicate_message="이미 사용 중인 전결 코드입니다.",
)


def participants(c, ctx, entries, drafter=None, legacy=False):
    normalized = [
        {
            **s,
            "seq": s.get("seq") or i + 1,
            "participant_role": s.get("participant_role", "APPROVER"),
        }
        for i, s in enumerate(entries)
    ]
    ids = [s["person_id"] for s in normalized]
    stages = sorted({s["seq"] for s in normalized})
    if not 1 <= len(ids) <= 30 or len(ids) != len(set(ids)) or drafter in ids:
        raise gw.invalid(
            "steps", "기안자를 제외한 서로 다른 담당자 1~30명을 지정하세요."
        )
    if stages != list(range(1, len(stages) + 1)) or len(stages) > 3:
        raise gw.invalid("steps", "단계를 1부터 3까지 연속으로 지정하세요.")
    for seq in stages:
        if not any(
            s["seq"] == seq and s["participant_role"] == "APPROVER" for s in normalized
        ):
            raise gw.invalid("steps", "각 단계에 결재 담당자가 한 명 이상 필요합니다.")
    if legacy and (
        len(ids) > 3
        or any(
            s["seq"] != i + 1 or s["participant_role"] != "APPROVER"
            for i, s in enumerate(normalized)
        )
    ):
        raise gw.invalid(
            "steps", "기존 결재 정책의 문서는 순차 결재선만 사용할 수 있습니다."
        )
    return [
        {
            **gw.actor(c, ctx, s["person_id"]),
            "seq": s["seq"],
            "participant_role": s["participant_role"],
        }
        for s in sorted(normalized, key=lambda s: s["seq"])
    ]


def organization(c, ctx, person):
    if person.get("organization_unit_id") is None:
        return {"organization_code": None, "organization_name": None}
    org = gw.one(c, ctx, "organization_unit", person["organization_unit_id"])
    return {"organization_code": org["code"], "organization_name": org["name"]}


def authority(c, ctx, row, t):
    if row["policy_version"] != 2 or row["amount"] is None:
        return None
    month = t.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m")
    found = gw.rows(
        c,
        f"SELECT * FROM gw.authority_rule WHERE {gw.S} AND is_active AND document_kind=:kind AND currency=:currency AND amount_from<=:amount AND (amount_to IS NULL OR amount_to>:amount) AND effective_from<=:month AND (effective_to IS NULL OR effective_to>=:month)",
        gw.params(
            ctx,
            kind=row["kind"],
            currency=row["currency"],
            amount=row["amount"],
            month=month,
        ),
    )
    if len(found) > 1:
        raise gw.conflict("AUTHORITY_AMBIGUOUS")
    return found[0] if found else None


def eligible(c, ctx, row, person, ss=None, t=None):
    if (
        row["status"] != "IN_REVIEW"
        or person["id"] == row["drafter_id"]
        or not person["is_active"]
    ):
        return []
    ss = ss if ss is not None else gw.steps(c, ctx, row["id"])
    t = t if t is not None else gw.now(c)
    found = []
    for step in ss:
        if step["seq"] != row["current_step"] or step["status"] != "WAITING":
            continue
        # 기존 v1은 원 담당자의 순차 처리를 유지한다.
        assigned = gw.one(c, ctx, "person", step["person_id"])
        if not assigned["is_active"]:
            continue
        delegation = None
        if step["person_id"] != person["id"]:
            if row["policy_version"] != 2 or any(
                s["person_id"] == person["id"] for s in ss
            ):
                continue
            grants = gw.rows(
                c,
                f"SELECT * FROM gw.delegation WHERE {gw.S} AND delegator_person_id=:owner AND delegate_person_id=:person AND revoked_at IS NULL AND starts_at<=:t AND ends_at>:t AND (document_kind IS NULL OR document_kind=:kind) AND (max_amount IS NULL OR (CAST(:currency AS varchar)='KRW' AND CAST(:amount AS numeric) IS NOT NULL AND max_amount>=:amount))",
                gw.params(
                    ctx,
                    owner=step["person_id"],
                    person=person["id"],
                    t=t,
                    kind=row["kind"],
                    currency=row["currency"],
                    amount=row["amount"],
                ),
            )
            if len(grants) != 1:
                continue
            if c.execute(
                text(
                    f"SELECT 1 FROM gw.delegation WHERE {gw.S} AND revoked_at IS NULL AND starts_at<=:t AND ends_at>:t AND (delegator_person_id=:person OR delegate_person_id=:owner)"
                ),
                gw.params(ctx, person=person["id"], owner=step["person_id"], t=t),
            ).first():
                continue
            delegation = grants[0]
        found.append({"step": step, "delegation": delegation})
    return found


def decision(c, ctx, row, person, action_name, values):
    ss = gw.steps(c, ctx, row["id"])
    t = gw.now(c)
    candidates = eligible(c, ctx, row, person, ss, t)
    expected_role = (
        "APPROVER"
        if action_name in {"approve", "reject"}
        else "REFERENCE"
        if action_name == "reference"
        else "CONSENT"
    )
    candidates = [
        x for x in candidates if x["step"]["participant_role"] == expected_role
    ]
    if values.get("step_id") is not None:
        candidates = [x for x in candidates if x["step"]["id"] == values["step_id"]]
    if not candidates:
        raise gw.conflict("NOT_CURRENT_STEP")
    if len(candidates) > 1:
        raise gw.conflict("ASSIGNMENT_REQUIRED")
    assignment = candidates[0]
    step = assignment["step"]
    grant = assignment["delegation"]
    role = step["participant_role"]
    rejecting = action_name in {"reject", "oppose"}
    allowed = {
        "APPROVER": {"approve", "reject"},
        "CONSENT": {"consent", "oppose"},
        "REFERENCE": {"reference"},
    }
    if action_name not in allowed[role]:
        raise gw.invalid("action", "참여 구분에 맞는 처리만 할 수 있습니다.")
    r = gw.reason(values, rejecting or role == "REFERENCE")
    evt = (
        "OPPOSED"
        if role == "CONSENT" and rejecting
        else "REJECTED"
        if rejecting
        else "APPROVED"
        if role == "APPROVER"
        else "CONSENTED"
    )
    c.execute(
        text(
            f"UPDATE gw.approval_step SET status=:status,decided_at=:t,decision_reason=:reason WHERE {gw.S} AND id=:id"
        ),
        gw.params(
            ctx,
            id=step["id"],
            status="REJECTED" if rejecting else "APPROVED",
            t=t,
            reason=r,
        ),
    )
    skipped = []
    if rejecting:
        changes = {"status": "REJECTED", "closed_at": t, "current_step": None}
        skipped = skip(c, ctx, row["id"])
    elif role == "REFERENCE":
        changes = {}
    else:
        remaining = c.execute(
            text(
                f"SELECT 1 FROM gw.approval_step WHERE {gw.S} AND document_id=:doc AND seq=:seq AND participant_role<>'REFERENCE' AND status='WAITING'"
            ),
            gw.params(ctx, doc=row["id"], seq=step["seq"]),
        ).first()
        if remaining:
            changes = {}
        else:
            skipped = skip(c, ctx, row["id"], step["seq"])
            nxt = c.execute(
                text(
                    f"SELECT min(seq) FROM gw.approval_step WHERE {gw.S} AND document_id=:doc AND seq>:seq AND participant_role<>'REFERENCE' AND status='WAITING'"
                ),
                gw.params(ctx, doc=row["id"], seq=step["seq"]),
            ).scalar_one()
            changes = (
                {"current_step": nxt}
                if nxt
                else {"status": "APPROVED", "closed_at": t, "current_step": None}
            )
    return (
        changes,
        evt,
        r,
        step["seq"],
        grant,
        {
            "stepId": str(step["id"]),
            "participantRole": role,
            "delegationId": str(grant["id"]) if grant else None,
            "originalPersonName": step["person_name"],
        },
        skipped,
    )


def skip(c, ctx, document_id, seq=None):
    return gw.rows(
        c,
        f"UPDATE gw.approval_step SET status='SKIPPED' WHERE {gw.S} AND document_id=:doc AND status='WAITING'"
        + (" AND seq=:seq" if seq is not None else "")
        + " RETURNING id,seq,person_name,participant_role",
        gw.params(ctx, doc=document_id, seq=seq),
    )


def rule_check(c, ctx, v, current=None, id=None):
    if current:
        gw.check_version(current, {"expected_version": v.pop("expected_version")})
    for field in AUTHORITY.columns:
        if (
            field not in {"amount_to", "effective_to", "version"}
            and v.get(field) is None
        ):
            raise gw.invalid(master.camel(field), "필수 항목을 비울 수 없습니다.")
    low = Decimal(v["amount_from"])
    high = Decimal(v["amount_to"]) if v.get("amount_to") is not None else None
    v["amount_from"] = low
    v["amount_to"] = high
    if high is not None and high <= low:
        raise gw.invalid(
            "amountTo", "상한은 하한보다 커야 합니다. 상한은 포함하지 않습니다."
        )
    if v.get("effective_to") is not None and v["effective_to"] < v["effective_from"]:
        raise gw.invalid("effectiveTo", "종료 월은 시작 월 이후여야 합니다.")
    if (
        current
        and c.execute(
            text(
                f"SELECT 1 FROM gw.approval_document WHERE {gw.S} AND authority_rule_id=:id"
            ),
            gw.params(ctx, id=id),
        ).first()
        and any(
            v[k] != current[k]
            for k in AUTHORITY.columns
            if k not in {"is_active", "version"}
        )
    ):
        raise gw.conflict("AUTHORITY_IN_USE")
    if (
        v["is_active"]
        and c.execute(
            text(
                f"SELECT 1 FROM gw.authority_rule WHERE {gw.S} AND id IS DISTINCT FROM CAST(:id AS bigint) AND is_active AND document_kind=:kind AND currency=:currency AND (CAST(:high AS numeric) IS NULL OR amount_from<:high) AND (amount_to IS NULL OR amount_to>:low) AND (CAST(:end AS varchar) IS NULL OR effective_from<=:end) AND (effective_to IS NULL OR effective_to>=:start)"
            ),
            gw.params(
                ctx,
                id=id,
                kind=v["document_kind"],
                currency=v["currency"],
                high=high,
                low=low,
                start=v["effective_from"],
                end=v.get("effective_to"),
            ),
        ).first()
    ):
        raise gw.conflict("AUTHORITY_OVERLAP")


def rules_write(context, id, operation, values, key):
    def run(c, ctx):
        current = master.fetch(c, AUTHORITY, ctx, id) if id else None
        if id and current is None:
            raise gw.ApiError(404, "NOT_FOUND", "전결 규칙을 찾을 수 없습니다.")
        if operation == "delete":
            if master.references(c, AUTHORITY, ctx, id):
                raise gw.conflict("AUTHORITY_IN_USE")
            c.execute(
                text(f"DELETE FROM gw.authority_rule WHERE {gw.S} AND id=:id"),
                gw.params(ctx, id=id),
            )
            gw.audit(
                c, ctx, "authority-rules", id, operation, current, "authority_rule"
            )
            return {}, "gw.authority_rule", id
        data = {**(current or {}), **values}
        rule_check(c, ctx, data, current, id)
        stored = {k: data[k] for k in AUTHORITY.columns if k != "version"}
        stored["amount_from"] = Decimal(stored["amount_from"])
        stored["amount_to"] = (
            Decimal(stored["amount_to"]) if stored["amount_to"] is not None else None
        )
        stored["version"] = current["version"] + 1 if current else 1
        master.reject_duplicate(c, AUTHORITY, ctx, stored, id)
        result = master.store(c, AUTHORITY, ctx, stored, id)
        gw.audit(
            c, ctx, "authority-rules", result["id"], operation, result, "authority_rule"
        )
        return result, "gw.authority_rule", result["id"]

    return action(
        "gw",
        context,
        f"gw.authority-rules.{id or 'new'}.{operation}",
        key,
        values,
        run,
        201 if id is None else 200,
    )


def delegation_write(context, id, values, key):
    def run(c, ctx):
        person = gw.actor(c, ctx, values["acting_person_id"])
        if id:
            current = gw.one(c, ctx, "delegation", id, True)
            gw.check_version(current, values)
            if current["delegator_person_id"] != person["id"]:
                raise gw.conflict("WRONG_ACTOR")
            if current["revoked_at"] is not None:
                raise gw.conflict("DELEGATION_REVOKED")
            gw.update(c, ctx, "delegation", id, {"revoked_at": gw.now(c)})
        else:
            delegate = gw.actor(c, ctx, values["delegate_person_id"])
            if delegate["id"] == person["id"]:
                raise gw.invalid("delegatePersonId", "자신에게 위임할 수 없습니다.")
            start, end = values["starts_at"], values["ends_at"]
            if end <= start:
                raise gw.invalid("endsAt", "종료 시각은 시작 시각보다 늦어야 합니다.")
            if c.execute(
                text(
                    f"SELECT 1 FROM gw.delegation WHERE {gw.S} AND revoked_at IS NULL AND starts_at<:end AND ends_at>:start AND (delegator_person_id=:delegate OR delegate_person_id=:owner OR delegator_person_id=:owner)"
                ),
                gw.params(
                    ctx,
                    owner=person["id"],
                    delegate=delegate["id"],
                    start=start,
                    end=end,
                ),
            ).first():
                raise gw.conflict("DELEGATION_OVERLAP_OR_CHAIN")
            if (
                values.get("max_amount") is not None
                and Decimal(values["max_amount"]) <= 0
            ):
                raise gw.invalid("maxAmount", "한도는 0보다 커야 합니다.")
            r = gw.reason(values, True)
            id_created = gw.insert(
                c,
                ctx,
                "delegation",
                {
                    "delegator_person_id": person["id"],
                    "delegate_person_id": delegate["id"],
                    "starts_at": start,
                    "ends_at": end,
                    "document_kind": values.get("document_kind"),
                    "max_amount": values.get("max_amount"),
                    "reason": r,
                },
            )
            result = gw.wire(gw.one(c, ctx, "delegation", id_created))
            gw.audit(c, ctx, "delegations", id_created, "create", result, "delegation")
            return result, "gw.delegation", id_created
        result = gw.wire(gw.one(c, ctx, "delegation", id))
        gw.audit(c, ctx, "delegations", id, "revoke", result, "delegation")
        return result, "gw.delegation", id

    return action(
        "gw",
        context,
        f"gw.delegations.{id or 'new'}",
        key,
        values,
        run,
        201 if id is None else 200,
    )


def delegations(context, offset, limit):
    with read() as c:
        ctx = read_scope(c, context, "gw")
        rr = gw.rows(
            c,
            "SELECT d.*,p.name AS delegator_name,q.name AS delegate_name FROM gw.delegation d JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(d.workspace_id,d.generation_id,d.delegator_person_id) JOIN gw.person q ON (q.workspace_id,q.generation_id,q.id)=(d.workspace_id,d.generation_id,d.delegate_person_id) WHERE d.workspace_id=:w AND d.generation_id=:g ORDER BY d.id DESC OFFSET :offset LIMIT :limit",
            gw.params(ctx, offset=offset, limit=limit),
        )
        total = c.execute(
            text(f"SELECT count(*) FROM gw.delegation WHERE {gw.S}"), gw.params(ctx)
        ).scalar_one()
        return {"rows": gw.wire(rr), "total": total, "offset": offset, "limit": limit}
