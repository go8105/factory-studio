"""회사 사용자 관리. 자격증명은 응답/이력/영수증에 저장하지 않는다."""

import hashlib
import hmac
import json
from dataclasses import replace

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from fs.common.clock import real_today
from fs.common.config import get_settings
from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.security import hash_password
from fs.core.company import companies, lock_accounts, require_session, resolve_company
from fs.core.service import create_member_account
from fs.hr.work import event, principal, scope


def platform_admin(c, ctx):
    return ctx.actor_kind == "MEMBER" and bool(
        c.execute(
            text(
                """SELECT 1 FROM core.app_user u JOIN core.user_role ur ON ur.user_id=u.id JOIN core.role r ON r.id=ur.role_id WHERE u.id=:u AND u.status='active' AND u.disabled_at IS NULL AND r.role_key='ADMIN'"""
            ),
            {"u": ctx.user_id},
        ).first()
    )


def management_scope(c, ctx, company_id):
    if platform_admin(c, ctx):
        row = c.execute(
            text(
                """SELECT w.active_generation_id FROM core.company co JOIN core.workspace w ON w.id=co.workspace_id WHERE co.workspace_id=:w AND co.status='ACTIVE' AND w.workspace_kind='COMPANY'"""
            ),
            {"w": company_id},
        ).first()
        if row is None:
            raise ApiError(404, "NOT_FOUND", "회사를 찾을 수 없습니다.")
        return replace(ctx, workspace_id=company_id, generation_id=row[0])
    sc, _ = resolve_company(c, ctx, company_id)
    principal(c, sc, True)
    return sc


def managed_companies(ctx):
    with read() as c:
        if platform_admin(c, ctx):
            return [
                dict(r)
                for r in c.execute(
                    text(
                        "SELECT workspace_id AS id,name FROM core.company WHERE status='ACTIVE' ORDER BY workspace_id"
                    )
                ).mappings()
            ]
        available = companies(c, ctx)
        result = []
        for co in available:
            sc, _ = resolve_company(c, ctx, co["id"])
            if principal(c, sc)["role"] == "ADMIN":
                result.append({"id": co["id"], "name": co["name"]})
        return result


def capabilities(ctx):
    with read() as c:
        allowed = platform_admin(c, ctx)
        return {"isPlatformAdmin": allowed, "canCreateCompany": allowed}


def register_company(ctx, key, body):
    from fs.hr.work_setup import create_company

    safe = {k: v for k, v in body.items() if k != "password"}
    safe["credentialFingerprint"] = hmac.new(
        get_settings().session_secret.encode(),
        json.dumps(body, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()

    def authorize(c, scoped):
        from fs.core.company import require_recent_auth

        lock_accounts(c, exclusive=True)
        require_session(c, ctx)
        if not platform_admin(c, scoped):
            raise ApiError(403, "FORBIDDEN", "총 관리자만 회사를 등록할 수 있습니다.")
        require_recent_auth(c, scoped)

    def run(c, scoped):
        try:
            result = create_company(c, body)
        except (IntegrityError, ValueError) as exc:
            raise ApiError(
                409, "DUPLICATE_ACCOUNT", "이미 사용 중인 아이디 또는 사원 코드입니다."
            ) from exc
        from fs.hr.security_journal import record

        generation = c.execute(
            text("SELECT active_generation_id FROM core.workspace WHERE id=:w"),
            {"w": result["companyId"]},
        ).scalar_one()
        record(
            c,
            replace(scoped, workspace_id=result["companyId"], generation_id=generation),
            result["userId"],
            "hr.users.company-create",
        )
        return result, "core.company", result["companyId"]

    return action(
        "core", ctx, "hr.users.company-create", key, safe, run, authorize=authorize
    )


def listing(ctx, company_id):
    with read() as c:
        sc = management_scope(c, ctx, company_id)
        return [
            dict(r)
            for r in c.execute(
                text("""SELECT u.id AS "userId",u.login_id AS "loginId",e.employee_code AS "employeeCode",e.name,(u.id=:actor) AS "isSelf",a.work_role AS role,(u.status='active' AND u.disabled_at IS NULL AND a.is_active AND m.is_active) AS active
        FROM hr.work_account a JOIN hr.employee e ON (e.workspace_id,e.generation_id,e.id)=(a.workspace_id,a.generation_id,a.employee_id)
        JOIN core.company_member m ON m.workspace_id=a.workspace_id AND m.user_id=a.user_id JOIN core.app_user u ON u.id=a.user_id
        WHERE a.workspace_id=:w AND a.generation_id=:g ORDER BY e.employee_code,u.id"""),
                {**scope(sc), "actor": ctx.user_id},
            ).mappings()
        ]


def mutate(ctx, company_id, operation, key, body):
    with read() as c:
        sc = management_scope(c, ctx, company_id)
    safe = {k: v for k, v in body.items() if k != "password"}
    if "password" in body:
        safe["credentialFingerprint"] = hmac.new(
            get_settings().session_secret.encode(),
            json.dumps(body, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()

    def authorize(c, scoped):
        from fs.core.company import require_recent_auth

        # Recheck after the company lock and before replaying any receipt.
        lock_accounts(c, exclusive=True)
        require_session(c, ctx)
        management_scope(c, ctx, scoped.workspace_id)
        require_recent_auth(c, scoped)

    def run(c, scoped):
        # 계정 ID/비밀번호는 회사 밖에서도 유일하므로 다른 회사의 동시 쓰기도 직렬화한다.
        c.execute(
            text(
                "SELECT pg_advisory_xact_lock(hashtextextended('fs.company.user-management',0))"
            )
        )
        params = scope(scoped)
        if operation == "create":
            user = create_member_account(
                c, body["loginId"], body["name"], body["password"], real_today()
            )
            base = (
                c.execute(
                    text(
                        "SELECT department_id,grade_id,work_pattern_id FROM hr.employee WHERE workspace_id=:w AND generation_id=:g ORDER BY id LIMIT 1"
                    ),
                    params,
                )
                .mappings()
                .first()
            )
            if base is None:
                raise ApiError(
                    409, "PRECONDITION_NOT_MET", "회사 사원 기준을 먼저 구성하세요."
                )
            employee = c.execute(
                text(
                    """INSERT INTO hr.employee(workspace_id,generation_id,employee_code,name,hire_date,department_id,grade_id,work_pattern_id) VALUES (:w,:g,:code,:name,:day,:department_id,:grade_id,:work_pattern_id) RETURNING id"""
                ),
                {
                    **params,
                    **dict(base),
                    "code": body["employeeCode"],
                    "name": body["name"],
                    "day": real_today(),
                },
            ).scalar_one()
            uid = user["userId"]
            c.execute(
                text(
                    "INSERT INTO core.company_member(workspace_id,user_id,role) VALUES (:w,:u,'MEMBER')"
                ),
                {**params, "u": uid},
            )
            c.execute(
                text(
                    "INSERT INTO hr.work_account(workspace_id,generation_id,user_id,employee_id,work_role) VALUES (:w,:g,:u,:e,:role)"
                ),
                {**params, "u": uid, "e": employee, "role": body["role"]},
            )
            c.execute(
                text(
                    "INSERT INTO hr.leave_balance(workspace_id,generation_id,employee_id,leave_year,granted_days) VALUES (:w,:g,:e,:year,:days)"
                ),
                {
                    **params,
                    "e": employee,
                    "year": str(real_today().year),
                    "days": body["annualDays"],
                },
            )
        else:
            uid = body["userId"]
            target = (
                c.execute(
                    text(
                        "SELECT a.employee_id,a.work_role,a.is_active,u.status FROM hr.work_account a JOIN core.app_user u ON u.id=a.user_id WHERE a.workspace_id=:w AND a.generation_id=:g AND a.user_id=:u FOR UPDATE OF a,u"
                    ),
                    {**params, "u": uid},
                )
                .mappings()
                .first()
            )
            if target is None:
                raise ApiError(404, "NOT_FOUND", "이 회사의 사용자가 아닙니다.")
            if uid == ctx.user_id:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "현재 로그인한 관리자 계정은 이 화면에서 변경할 수 없습니다.",
                )
            privileged = c.execute(
                text(
                    "SELECT 1 FROM core.user_role ur JOIN core.role r ON r.id=ur.role_id WHERE ur.user_id=:u AND r.role_key='ADMIN'"
                ),
                {"u": uid},
            ).first()
            if privileged and not platform_admin(c, ctx):
                raise ApiError(
                    403, "FORBIDDEN", "전체 관리자 계정은 변경할 수 없습니다."
                )
            if (
                c.execute(
                    text("SELECT count(*) FROM core.company_member WHERE user_id=:u"),
                    {"u": uid},
                ).scalar()
                != 1
            ):
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "여러 회사에 연결된 계정은 별도 관리가 필요합니다.",
                )
            if (
                target["work_role"] == "ADMIN"
                and target["is_active"]
                and target["status"] == "active"
                and (
                    operation == "disable"
                    or (operation == "role" and body["role"] == "STAFF")
                )
            ):
                count = c.execute(
                    text(
                        """SELECT count(*) FROM hr.work_account a JOIN core.app_user u ON u.id=a.user_id JOIN core.company_member m ON m.workspace_id=a.workspace_id AND m.user_id=a.user_id WHERE a.workspace_id=:w AND a.generation_id=:g AND a.work_role='ADMIN' AND a.is_active AND m.is_active AND u.status='active' AND u.disabled_at IS NULL"""
                    ),
                    params,
                ).scalar()
                if count <= 1:
                    raise ApiError(
                        409,
                        "PRECONDITION_NOT_MET",
                        "마지막 회사 관리자는 사용 중지하거나 직원으로 변경할 수 없습니다.",
                    )
            employee = target["employee_id"]
            if operation == "password":
                c.execute(
                    text(
                        "UPDATE core.app_user SET password_hash=:hash,status='active',disabled_at=NULL,security_version=security_version+1 WHERE id=:u"
                    ),
                    {"hash": hash_password(body["password"]), "u": uid},
                )
                c.execute(
                    text(
                        "UPDATE hr.work_account SET is_active=true WHERE workspace_id=:w AND generation_id=:g AND user_id=:u"
                    ),
                    {**params, "u": uid},
                )
                c.execute(
                    text(
                        "UPDATE core.company_member SET is_active=true WHERE workspace_id=:w AND user_id=:u"
                    ),
                    {**params, "u": uid},
                )
            elif operation == "disable":
                c.execute(
                    text(
                        "UPDATE core.app_user SET status='disabled',disabled_at=now() WHERE id=:u"
                    ),
                    {"u": uid},
                )
                c.execute(
                    text(
                        "UPDATE hr.work_account SET is_active=false WHERE workspace_id=:w AND generation_id=:g AND user_id=:u"
                    ),
                    {**params, "u": uid},
                )
                c.execute(
                    text(
                        "UPDATE core.company_member SET is_active=false WHERE workspace_id=:w AND user_id=:u"
                    ),
                    {**params, "u": uid},
                )
            elif operation == "role":
                c.execute(
                    text(
                        "UPDATE hr.work_account SET work_role=:role WHERE workspace_id=:w AND generation_id=:g AND user_id=:u"
                    ),
                    {**params, "u": uid, "role": body["role"]},
                )
            elif operation == "login-id":
                c.execute(
                    text("UPDATE core.app_user SET login_id=:login WHERE id=:u"),
                    {"login": body["loginId"], "u": uid},
                )
            else:
                raise ApiError(400, "VALIDATION_FAILED", "지원하지 않는 변경입니다.")
            c.execute(
                text(
                    "UPDATE core.auth_session SET revoked_at=now() WHERE user_id=:u AND revoked_at IS NULL"
                ),
                {"u": uid},
            )
        result = {"userId": uid}
        audit = {k: v for k, v in safe.items() if k != "credentialFingerprint"}
        event(c, scoped, employee, "user-" + operation, uid, audit)
        from fs.hr.security_journal import record

        record(c, scoped, uid, "hr.users." + operation)
        return result, "hr.work_account", uid

    try:
        return action(
            "hr", sc, "hr.users." + operation, key, safe, run, authorize=authorize
        )
    except IntegrityError, ValueError:
        raise ApiError(
            409, "USER_CONFLICT", "이미 사용 중인 아이디 또는 사원 코드입니다."
        ) from None
