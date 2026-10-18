"""회사 GW 직원 연결·명시 역할. 회사/계정 잠금 안에서만 권한을 판정한다."""

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.core.company import members, require_recent_auth
from fs.gw import company, organization, security_journal
from fs.gw import service as gw
from fs.hr.interface import work_identity


def denied():
    raise ApiError(403, "GW_ROLE_REQUIRED", "이 작업의 GW 권한이 필요합니다.")


def bump(c, ctx):
    c.execute(
        text(
            f"UPDATE gw.collaboration_settings SET authz_version=authz_version+1 WHERE {gw.S}"
        ),
        gw.params(ctx),
    )


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
            "reason": reason,
            **{
                k: v
                for k, v in (result or {}).items()
                if k in {"state", "roles", "person_id", "user_id", "version"}
            },
        },
    )


def active_people(c, ctx):
    users = {m["id"] for m in members(c, ctx) if m["active"]}
    return {
        r["person_id"]
        for r in gw.rows(
            c,
            f"SELECT b.person_id,b.user_id FROM gw.person_identity_binding b JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id) WHERE b.{gw.S.replace(' AND ', ' AND b.')} AND b.state='ACTIVE' AND p.is_active",
            gw.params(ctx),
        )
        if r["user_id"] in users
    }


def require_active(c, ctx, person_id):
    if person_id not in active_people(c, ctx):
        raise gw.invalid("personId", "같은 회사의 활성 연결 직원을 선택하세요.")


def last_admin(c, ctx, person_id):
    admins = {
        r["person_id"]
        for r in gw.rows(
            c,
            f"SELECT person_id FROM gw.role_grant WHERE {gw.S} AND role_key='SECURITY_ADMIN' AND is_active",
            gw.params(ctx),
        )
    }
    if person_id in admins and not ((admins & active_people(c, ctx)) - {person_id}):
        raise ApiError(
            409, "LAST_SECURITY_ADMIN", "마지막 활성 보안 관리자는 유지해야 합니다."
        )


def owner(c, ctx):
    if not any(
        m["id"] == ctx.user_id and m["role"] == "OWNER" and m["active"]
        for m in members(c, ctx)
    ):
        denied()


def execute(context, company_id, operation, key, values, authorize, run):
    """미연결 본인의 동의/최초 설정도 현재 권한을 receipt 앞에서 검사한다."""
    with company.transaction(context, company_id, write=True) as (c, ctx, _):
        authorize(c, ctx)
        require_recent_auth(c, ctx)
        digest = request_digest(values)
        saved = find_receipt(c, ctx, operation, key, digest)
        if saved is not None:
            return saved
        result, table, id = run(c, ctx)
        bump(c, ctx)
        audit(
            c, ctx, table, id, operation, values.get("reason", "본인 연결 동의"), result
        )
        result = gw.wire(result)
        save_receipt(c, ctx, operation, key, digest, "gw." + table, id, result)
        security_journal.record(c, ctx, operation)
        return result


def setup(context, company_id, values, key):
    def authorize(c, ctx):
        owner(c, ctx)
        if not work_identity(c, ctx, ctx.user_id):
            raise ApiError(
                409, "HR_IDENTITY_REQUIRED", "본인 HR 직원 연결을 먼저 확인하세요."
            )
        current = company.identity(c, ctx)
        settings = gw.rows(
            c, f"SELECT * FROM gw.collaboration_settings WHERE {gw.S}", gw.params(ctx)
        )
        if settings and (
            settings[0]["initialized_by_user_id"] != ctx.user_id
            or not current
            or current["state"] != "ACTIVE"
            or not current["is_active"]
        ):
            denied()

    def run(c, ctx):
        if any(
            c.execute(
                text(f"SELECT 1 FROM gw.{t} WHERE {gw.S} LIMIT 1"), gw.params(ctx)
            ).first()
            for t in (
                "collaboration_settings",
                "person",
                "organization_unit",
                "approval_document",
                "approval_route",
                "board_post",
            )
        ):
            raise ApiError(
                409,
                "GW_ALREADY_INITIALIZED",
                "빈 회사 GW에서만 최초 설정할 수 있습니다.",
            )
        hr = work_identity(c, ctx, ctx.user_id)
        if hr["employeeCode"] != values["employee_code"]:
            raise gw.invalid("employeeCode", "본인의 HR 사번을 확인하세요.")
        source = organization.state(c, ctx)
        organization.import_snapshot(
            c,
            ctx,
            {
                "preview_digest": source["digest"],
                "employee_codes": [hr["employeeCode"]],
            },
        )
        person = gw.rows(
            c,
            f"SELECT * FROM gw.person WHERE {gw.S} AND hr_employee_code=:code",
            gw.params(ctx, code=hr["employeeCode"]),
        )[0]
        id = gw.insert(
            c,
            ctx,
            "collaboration_settings",
            {"initialized_by_user_id": ctx.user_id, "initialized_at": gw.now(c)},
        )
        gw.insert(
            c,
            ctx,
            "person_identity_binding",
            {
                "person_id": person["id"],
                "user_id": ctx.user_id,
                "state": "ACTIVE",
                "requested_by_user_id": ctx.user_id,
                "activated_at": gw.now(c),
                "reason": values["reason"],
            },
        )
        for role in sorted(company.ROLES - {"AUDITOR"}):
            gw.insert(
                c,
                ctx,
                "role_grant",
                {
                    "person_id": person["id"],
                    "role_key": role,
                    "changed_by_user_id": ctx.user_id,
                    "reason": values["reason"],
                },
            )
        return (
            {"person_id": person["id"], "roles": sorted(company.ROLES - {"AUDITOR"})},
            "collaboration_settings",
            id,
        )

    return execute(context, company_id, "company-setup", key, values, authorize, run)


def binding(context, company_id, id, operation, values, key):
    def authorize(c, ctx):
        if operation == "accept":
            row = gw.one(c, ctx, "person_identity_binding", id)
            if row["user_id"] != ctx.user_id or row["state"] not in {
                "PENDING",
                "ACTIVE",
            }:
                denied()
            person = gw.one(c, ctx, "person", row["person_id"])
            hr = work_identity(c, ctx, ctx.user_id)
            if (
                not person["is_active"]
                or not hr
                or hr["employeeCode"] != person["hr_employee_code"]
            ):
                denied()
        else:
            company.principal(
                c,
                ctx,
                "ORG_ADMIN" if operation in {"request", "cancel"} else "SECURITY_ADMIN",
            )

    def run(c, ctx):
        if operation == "request":
            person = gw.one(c, ctx, "person", values["person_id"])
            member = next(
                (
                    m
                    for m in members(c, ctx)
                    if m["id"] == values["user_id"] and m["active"]
                ),
                None,
            )
            hr = work_identity(c, ctx, values["user_id"]) if member else None
            if (
                not person["is_active"]
                or not hr
                or hr["employeeCode"] != person["hr_employee_code"]
            ):
                raise gw.invalid(
                    "userId", "동일 사번의 활성 회사 계정과 GW 직원을 확인하세요."
                )
            if c.execute(
                text(
                    f"SELECT 1 FROM gw.person_identity_binding WHERE {gw.S} AND state<>'CANCELLED' AND (person_id=:person OR user_id=:user)"
                ),
                gw.params(ctx, person=person["id"], user=values["user_id"]),
            ).first():
                raise ApiError(
                    409,
                    "GW_BINDING_EXISTS",
                    "이미 연결되었거나 확인 중인 계정 또는 직원입니다.",
                )
            bid = gw.insert(
                c,
                ctx,
                "person_identity_binding",
                {
                    "person_id": person["id"],
                    "user_id": values["user_id"],
                    "state": "PENDING",
                    "requested_by_user_id": ctx.user_id,
                    "reason": values["reason"],
                },
            )
        else:
            bid = id
            row = gw.one(c, ctx, "person_identity_binding", bid, True)
            gw.check_version(row, values)
            before, after = {
                "accept": ("PENDING", "ACTIVE"),
                "cancel": ("PENDING", "CANCELLED"),
                "suspend": ("ACTIVE", "SUSPENDED"),
                "resume": ("SUSPENDED", "ACTIVE"),
            }[operation]
            if row["state"] != before:
                raise ApiError(
                    409, "GW_BINDING_STATE", "현재 연결 상태에서는 처리할 수 없습니다."
                )
            if operation == "suspend":
                last_admin(c, ctx, row["person_id"])
            if operation == "resume" and (
                not any(
                    m["id"] == row["user_id"] and m["active"] for m in members(c, ctx)
                )
                or not gw.one(c, ctx, "person", row["person_id"])["is_active"]
            ):
                raise ApiError(
                    409,
                    "GW_IDENTITY_INACTIVE",
                    "계정과 GW 직원 활성 상태를 확인하세요.",
                )
            changes = {
                "state": after,
                "reason": values.get("reason", "본인 연결 동의"),
                "closed_at": gw.now(c) if after in {"CANCELLED", "SUSPENDED"} else None,
            }
            if operation == "accept":
                changes["activated_at"] = gw.now(c)
            gw.update(c, ctx, "person_identity_binding", bid, changes)
        return (
            gw.one(c, ctx, "person_identity_binding", bid),
            "person_identity_binding",
            bid,
        )

    return execute(
        context, company_id, f"binding.{id}.{operation}", key, values, authorize, run
    )


def roles(context, company_id, person_id, values, key):
    def authorize(c, ctx):
        company.principal(c, ctx, "SECURITY_ADMIN")
        gw.one(c, ctx, "person", person_id)

    def run(c, ctx):
        p = gw.one(c, ctx, "person", person_id, True)
        gw.check_version(p, values)
        desired = set(values["roles"])
        if len(desired) != len(values["roles"]) or not desired <= company.ROLES:
            raise gw.invalid("roles", "중복 없이 GW 역할을 선택하세요.")
        if "SECURITY_ADMIN" not in desired:
            last_admin(c, ctx, person_id)
        if desired:
            require_active(c, ctx, person_id)
        current = {
            r["role_key"]: r
            for r in gw.rows(
                c,
                f"SELECT * FROM gw.role_grant WHERE {gw.S} AND person_id=:person",
                gw.params(ctx, person=person_id),
            )
        }
        for role in sorted(desired | current.keys()):
            v = {
                "is_active": role in desired,
                "changed_by_user_id": ctx.user_id,
                "reason": values["reason"],
            }
            if role in current:
                gw.update(c, ctx, "role_grant", current[role]["id"], v)
            else:
                gw.insert(
                    c,
                    ctx,
                    "role_grant",
                    {"person_id": person_id, "role_key": role, **v},
                )
        gw.update(c, ctx, "person", person_id, {})
        return (
            {
                "person_id": person_id,
                "version": p["version"] + 1,
                "roles": sorted(desired),
            },
            "person",
            person_id,
        )

    return execute(
        context, company_id, f"roles.{person_id}", key, values, authorize, run
    )


def overview(context, company_id, *, offset=0, limit=50):
    with company.transaction(context, company_id) as (c, ctx, _):
        _, roles = company.principal(c, ctx)
        if not roles & {"ORG_ADMIN", "SECURITY_ADMIN"}:
            denied()
        rows = gw.rows(
            c,
            f"SELECT * FROM gw.person_identity_binding WHERE {gw.S} ORDER BY id LIMIT :limit OFFSET :offset",
            gw.params(ctx, limit=limit, offset=offset),
        )
        return {
            "items": gw.wire(rows),
            "total": c.execute(
                text(f"SELECT count(*) FROM gw.person_identity_binding WHERE {gw.S}"),
                gw.params(ctx),
            ).scalar_one(),
        }


def my_binding(context, company_id):
    with company.transaction(context, company_id) as (c, ctx, _):
        rows = gw.rows(
            c,
            f"SELECT b.id,b.version,b.state,p.code,p.name,p.hr_employee_code,u.name AS organization_name FROM gw.person_identity_binding b JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id) LEFT JOIN gw.organization_unit u ON (u.workspace_id,u.generation_id,u.id)=(p.workspace_id,p.generation_id,p.organization_unit_id) WHERE b.{gw.S.replace(' AND ', ' AND b.')} AND b.user_id=:user AND b.state<>'CANCELLED'",
            gw.params(ctx, user=ctx.user_id),
        )
        return gw.wire(rows[0]) if rows else None


def role_list(context, company_id, person_id):
    with company.transaction(context, company_id) as (c, ctx, _):
        company.principal(c, ctx, "SECURITY_ADMIN")
        person = gw.one(c, ctx, "person", person_id)
        rows = gw.rows(
            c,
            f"SELECT role_key FROM gw.role_grant WHERE {gw.S} AND person_id=:person AND is_active ORDER BY role_key",
            gw.params(ctx, person=person_id),
        )
        return {
            "personId": str(person_id),
            "version": person["version"],
            "roles": [r["role_key"] for r in rows],
        }
