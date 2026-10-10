"""회사 소속의 읽기 전용 계약. 기존 개인/게스트 인증 공간과 분리한다."""

from dataclasses import replace

from sqlalchemy import text

from fs.common.errors import ApiError


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
