"""회사 소속의 읽기 전용 계약. 기존 개인/게스트 인증 공간과 분리한다."""

from dataclasses import replace

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.security import token_hash


def lock_accounts(connection, *, exclusive=False):
    """회사 공간 잠금 다음에 획득한다. 전역 계정 관리와 회사 업무를 직렬화한다."""
    fn = "pg_advisory_xact_lock" if exclusive else "pg_advisory_xact_lock_shared"
    connection.execute(
        text(f"SELECT {fn}(hashtextextended('fs.company.user-management',0))")
    )


def require_session(connection, context):
    """업무 TX 안에서 현재 계정·세션을 재검증하고 로그아웃과 직렬화한다."""
    if context.actor_kind != "MEMBER" or context.user_id is None:
        raise ApiError(
            403, "MEMBER_REQUIRED", "회사 업무는 로그인 회원만 사용할 수 있습니다."
        )
    valid = connection.execute(
        text("""SELECT s.id,s.assurance FROM core.auth_session s JOIN core.app_user u ON u.id=s.user_id
        WHERE s.token_hash=:token AND s.user_id=:user AND s.revoked_at IS NULL
          AND s.expires_at>clock_timestamp() AND u.status='active' AND u.disabled_at IS NULL
          AND s.security_version=u.security_version
          AND (s.absolute_expires_at IS NULL OR s.absolute_expires_at>clock_timestamp())
        FOR SHARE OF s"""),
        {"token": token_hash(context.token), "user": context.user_id},
    ).first()
    if valid is None:
        raise ApiError(401, "SESSION_EXPIRED", "세션이 없거나 만료되었습니다.")
    from fs.core.security.config import security_settings

    if valid[1] == "RECOVERY_LIMITED":
        raise ApiError(403, "RECOVERY_ONLY", "인증 앱을 다시 등록해 주세요.")
    if security_settings().mode == "COMPANY" and valid[1] != "MFA":
        raise ApiError(
            403, "MFA_REQUIRED", "내 계정 보안에서 인증 앱을 등록한 뒤 로그인해 주세요."
        )


def companies(connection, context):
    if context.actor_kind != "MEMBER":
        raise ApiError(
            403,
            "MEMBER_REQUIRED",
            "실제 근무는 회원만 사용할 수 있습니다. 근무 체험을 이용하세요.",
        )
    return [
        dict(r)
        for r in connection.execute(
            text("""
      SELECT c.workspace_id AS id,c.name,c.is_example AS "isExample",c.timezone
      FROM core.company c JOIN core.company_member m ON m.workspace_id=c.workspace_id
      JOIN core.app_user u ON u.id=m.user_id
      WHERE m.user_id=:u AND m.is_active AND c.status='ACTIVE'
        AND u.status='active' AND u.disabled_at IS NULL ORDER BY c.workspace_id
    """),
            {"u": context.user_id},
        ).mappings()
    ]


def resolve_company(connection, context, company_id):
    allowed = companies(connection, context)
    company = next((c for c in allowed if c["id"] == company_id), None)
    if company is None:
        raise ApiError(
            403, "COMPANY_ACCESS_DENIED", "이 회사의 활성 구성원이 아닙니다."
        )
    row = connection.execute(
        text("""SELECT active_generation_id FROM core.workspace
        WHERE id=:w AND workspace_kind='COMPANY' """),
        {"w": company_id},
    ).first()
    if row is None:
        raise ApiError(403, "COMPANY_ACCESS_DENIED", "회사 공간을 확인할 수 없습니다.")
    return replace(context, workspace_id=company_id, generation_id=row[0]), company


def members(connection, context):
    """회사 구성원의 공개 식별자/이름/소유자 여부. 업무 솔루션용 읽기 계약."""
    scoped, _ = resolve_company(connection, context, context.workspace_id)
    return [
        dict(r)
        for r in connection.execute(
            text("""
      SELECT u.id,u.display_name AS name,m.role,m.is_active AND u.status='active'
        AND u.disabled_at IS NULL AS active
      FROM core.company_member m JOIN core.app_user u ON u.id=m.user_id
      WHERE m.workspace_id=:w ORDER BY u.display_name,u.id
    """),
            {"w": scoped.workspace_id},
        ).mappings()
    ]
