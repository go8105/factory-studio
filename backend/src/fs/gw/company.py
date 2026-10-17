"""GW-COMPANY-02: 회사 인증 기반. 업무 공개는 ACL/협업 구현 후 별도로 연다."""

from contextlib import contextmanager
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from fs.common.auth import AuthContext, resolve_auth
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import WORKSPACE_LOCK_NAMESPACE, read_scope, seed_ready
from fs.core.company import (
    companies,
    lock_accounts,
    members,
    require_session,
    resolve_company,
)
from fs.hr.interface import work_identity

BUSINESS_READY = False

S = "workspace_id=:w AND generation_id=:g"
ROLES = frozenset(
    {
        "ORG_ADMIN",
        "ROUTE_ADMIN",
        "POLICY_ADMIN",
        "BOARD_PUBLISHER",
        "SECURITY_ADMIN",
        "AUDITOR",
    }
)


@contextmanager
def transaction(context, company_id, *, write=False):
    """Company lock -> account lock -> session row; recheck in READ COMMITTED."""
    if context.actor_kind != "MEMBER":
        raise ApiError(
            403, "MEMBER_REQUIRED", "회사 GW는 로그인 회원만 사용할 수 있습니다."
        )
    with get_engine().execution_options(isolation_level="READ COMMITTED").begin() as c:
        lock = "pg_advisory_xact_lock" if write else "pg_advisory_xact_lock_shared"
        c.execute(
            text(f"SELECT {lock}(:namespace,:workspace)"),
            {"namespace": WORKSPACE_LOCK_NAMESPACE, "workspace": company_id},
        )
        lock_accounts(c)
        require_session(c, context)
        scoped, company = resolve_company(c, context, company_id)
        scoped = read_scope(c, scoped, "gw")
        yield c, scoped, company


def identity(c, scoped):
    row = (
        c.execute(
            text(f"""SELECT b.id AS binding_id,b.state,p.id,p.code,p.name,p.is_active,p.organization_unit_id,p.job_role,p.version
      FROM gw.person_identity_binding b JOIN gw.person p
      ON (p.workspace_id,p.generation_id,p.id)=(b.workspace_id,b.generation_id,b.person_id)
      WHERE b.{S.replace(" AND ", " AND b.")} AND b.user_id=:u AND b.state<>'CANCELLED'"""),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "u": scoped.user_id},
        )
        .mappings()
        .one_or_none()
    )
    return dict(row) if row else None


def principal(c, scoped, role=None):
    person = identity(c, scoped)
    if not person or person["state"] != "ACTIVE" or not person["is_active"]:
        raise ApiError(403, "GW_IDENTITY_REQUIRED", "활성 GW 직원 연결이 필요합니다.")
    roles = frozenset(
        c.execute(
            text(
                f"SELECT role_key FROM gw.role_grant WHERE {S} AND person_id=:p AND is_active"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "p": person["id"]},
        ).scalars()
    )
    if role is not None and role not in roles:
        raise ApiError(403, "GW_ROLE_REQUIRED", "이 작업의 GW 권한이 필요합니다.")
    return person, roles


def action(context, company_id, operation, key, body, fn, *, authorize):
    """회사 명령 기반: 현재 주체/객체 권한을 성공 영수증보다 먼저 검사한다.

    공개 쓰기 API는 후속 단계에서 CSRF·입력 검증 후 이 함수를 사용한다.
    authorize는 객체 ACL까지 검사해야 하며 생략할 수 없다.
    """
    with transaction(context, company_id, write=True) as (c, scoped, _):
        person, _ = principal(c, scoped)
        authorize(c, scoped, person)
        digest = request_digest(body)
        cached = find_receipt(c, scoped, operation, key, digest)
        if cached is not None:
            return cached
        result, entity, entity_id = fn(c, scoped, person)
        save_receipt(c, scoped, operation, key, digest, entity, entity_id, result)
        return result


def company_list(context):
    with get_engine().begin() as c:
        lock_accounts(c)
        require_session(c, context)
        return companies(c, context)


def me(context, company_id):
    with transaction(context, company_id) as (c, scoped, company):
        p = {"w": scoped.workspace_id, "g": scoped.generation_id}
        settings = (
            c.execute(
                text(f"SELECT authz_version FROM gw.collaboration_settings WHERE {S}"),
                p,
            )
            .mappings()
            .one_or_none()
        )
        bound = identity(c, scoped)
        active = bound and bound["state"] == "ACTIVE" and bound["is_active"]
        roles = sorted(principal(c, scoped)[1]) if active else []
        owner = any(
            m["id"] == scoped.user_id and m["role"] == "OWNER"
            for m in members(c, scoped)
        )
        return {
            "company": company,
            "mode": "COMPANY",
            "person": {
                "id": str(bound["id"]),
                "code": bound["code"],
                "name": bound["name"],
                "jobRole": bound["job_role"],
                "isActive": bound["is_active"],
                "version": bound["version"],
                "organizationUnitId": str(bound["organization_unit_id"])
                if bound["organization_unit_id"]
                else None,
            }
            if bound
            else None,
            "bindingStatus": bound["state"] if bound else "UNBOUND",
            "roles": roles,
            "authzVersion": settings["authz_version"] if settings else 0,
            "setupRequired": settings is None,
            "companyOwner": owner,
            "hrIdentityAvailable": work_identity(c, scoped, scoped.user_id) is not None,
            "capabilities": ["GENERAL", "COLLABORATION"]
            if BUSINESS_READY and active and settings
            else [],
            "businessReady": bool(BUSINESS_READY and active and settings),
        }


_personal_seed = seed_ready("gw")


async def entry(
    request: Request,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    company_id: Annotated[
        int | None, Query(alias="companyId", gt=0, le=2147483647)
    ] = None,
):
    if company_id is None:
        await run_in_threadpool(_personal_seed, context)
        return
    body = None
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        try:
            body = await request.json()
        except ValueError:
            pass

    def check():
        with transaction(context, company_id):
            if "personId" in request.query_params:
                raise ApiError(
                    400, "VALIDATION_FAILED", "회사 GW에서 담당자를 선택할 수 없습니다."
                )
            if isinstance(body, dict) and (
                {"actingPersonId", "acting_person_id"} & body.keys()
            ):
                raise ApiError(
                    400,
                    "VALIDATION_FAILED",
                    "회사 GW의 처리자는 로그인 계정으로 결정합니다.",
                )
            raise ApiError(
                409,
                "GW_COMPANY_NOT_READY",
                "회사 GW의 업무 권한 연결을 준비 중입니다. 개인 체험은 계속 사용할 수 있습니다.",
            )

    await run_in_threadpool(check)
