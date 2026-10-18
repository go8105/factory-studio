"""GW administrator eligibility and workspace lock for core emergency recovery."""

from sqlalchemy import text

from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.scope import WORKSPACE_LOCK_NAMESPACE
from fs.common.security import token_hash
from fs.core.company import lock_accounts, require_recent_auth
from fs.core.security import emergency as credentials
from fs.gw import company


def lock_scope(c, company_id):
    c.execute(
        text("SELECT pg_advisory_xact_lock(:ns,:w)"),
        {"ns": WORKSPACE_LOCK_NAMESPACE, "w": int(company_id)},
    )
    # Exclusive account lock is the server-operator recovery boundary. No session
    # is required or created here; it serializes live grants/account revocation.
    lock_accounts(c, exclusive=True)


def eligible(c, *, user_id, company_id, generation_id, person_id):
    return (
        c.execute(
            text("""SELECT 1 FROM core.company co JOIN core.workspace w ON w.id=co.workspace_id
        JOIN core.company_member m ON m.workspace_id=w.id AND m.user_id=:u
        JOIN core.app_user u ON u.id=m.user_id
        JOIN gw.person_identity_binding b ON b.workspace_id=w.id AND b.generation_id=w.active_generation_id AND b.user_id=u.id
        JOIN gw.person p ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id)
        JOIN gw.role_grant r ON (r.workspace_id,r.generation_id,r.person_id)=(p.workspace_id,p.generation_id,p.id)
        WHERE co.workspace_id=:w AND co.status='ACTIVE' AND w.workspace_kind='COMPANY' AND w.active_generation_id=:g
        AND m.is_active AND u.status='active' AND u.disabled_at IS NULL AND b.state='ACTIVE' AND p.is_active AND p.id=:p
        AND r.role_key='SECURITY_ADMIN' AND r.is_active"""),
            {
                "u": int(user_id),
                "w": int(company_id),
                "g": int(generation_id),
                "p": int(person_id),
            },
        ).first()
        is not None
    )


def issue(context, company_id, reason, operation_key):
    with company.transaction(context, company_id, write=True) as (c, ctx, _):
        person, _roles = company.principal(c, ctx, "SECURITY_ADMIN")
        require_recent_auth(c, ctx, always=True)
        result = credentials.issue_kit(c, ctx, person["id"], reason, operation_key)
    data, error = result
    if error:
        raise error
    return data


def approve(c, kit, operator_uid, reason):
    lock_scope(c, kit.company_id)
    if not eligible(
        c,
        user_id=kit.user_id,
        company_id=kit.company_id,
        generation_id=kit.generation_id,
        person_id=kit.person_id,
    ):
        return None, ApiError(
            403,
            "EMERGENCY_RECOVERY_DENIED",
            "현재 회사의 활성 보안 관리자인지 확인하세요.",
        )
    return credentials.approve(c, kit, operator_uid, reason)


def redeem(login_token, grant_token):
    with get_engine().execution_options(isolation_level="READ COMMITTED").begin() as c:
        located = credentials.peek_grant(c, grant_token)
        if located is None or located.get("kind") != "EMERGENCY_GRANT":
            lock_accounts(c, exclusive=True)
            login = c.execute(
                text(
                    "SELECT id FROM core.authentication_challenge WHERE token_hash=:t AND purpose='LOGIN_MFA' FOR UPDATE"
                ),
                {"t": token_hash(login_token)},
            ).first()
            result = (
                credentials.fail_login(c, login[0])
                if login
                else (None, credentials.service.failed())
            )
        else:
            lock_scope(c, located["companyId"])
            if not eligible(
                c,
                user_id=located["userId"],
                company_id=located["companyId"],
                generation_id=located["generationId"],
                person_id=located["personId"],
            ):
                result = (
                    None,
                    ApiError(
                        403,
                        "EMERGENCY_RECOVERY_DENIED",
                        "현재 회사의 활성 보안 관리자 연결을 확인하세요.",
                    ),
                )
            else:
                result = credentials.redeem(c, login_token, grant_token)
    return result
