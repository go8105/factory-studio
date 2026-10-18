"""회사 GW 준비·연결 관리 API. 전체 업무 공개는 04 통합 후다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request
from pydantic import Field

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.core.company import members
from fs.gw import company, company_work, organization, schema
from fs.gw import company_identity as identities
from fs.gw.operating_contract import OperatingPolicy
from fs.hr.interface import work_identity


async def reject_actor(request: Request):
    if "personId" in request.query_params:
        raise ApiError(
            400, "VALIDATION_FAILED", "회사 GW의 처리자는 로그인 계정으로 결정합니다."
        )


router = APIRouter(dependencies=[Depends(reject_actor)])
Auth = Annotated[AuthContext, Depends(resolve_auth)]


@router.get("/companies")
def companies(context: Auth):
    return {"data": company.company_list(context)}


@router.get("/me")
def me(
    request: Request,
    context: Auth,
    company_id: Annotated[int, Query(alias="companyId", gt=0, le=2147483647)],
):
    if "personId" in request.query_params:
        raise ApiError(
            400, "VALIDATION_FAILED", "회사 GW에서 담당자를 선택할 수 없습니다."
        )
    return {"data": company.me(context, company_id)}


CompanyId = Annotated[int, Query(alias="companyId", gt=0, le=2147483647)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Csrf = Annotated[str | None, Header(alias="X-CSRF-Token")]
Reason = Annotated[schema.Text, Field(min_length=2, max_length=500)]


class Setup(schema.Model):
    employee_code: schema.Text = Field(alias="employeeCode", max_length=30)
    reason: Reason


class BindingRequest(schema.Model):
    person_id: schema.Id = Field(alias="personId")
    user_id: schema.Id = Field(alias="userId")
    reason: Reason


class BindingAccept(schema.Version):
    binding_id: schema.Id = Field(alias="bindingId")


class Change(schema.Version):
    reason: Reason


class CompanyHrImport(schema.HrImport):
    reason: Reason


class RoleChange(Change):
    roles: list[str] = Field(max_length=6)


def command(context, csrf, key, fn, *args):
    mutation_key(context, csrf, key)
    return {"data": fn(*args, key)}


@router.get("/company-setup")
def setup_preview(context: Auth, company_id: CompanyId):
    with company.transaction(context, company_id) as (c, ctx, _):
        identities.owner(c, ctx)
        return {"data": work_identity(c, ctx, ctx.user_id)}


@router.post("/company-setup")
def setup(
    context: Auth,
    company_id: CompanyId,
    payload: Setup,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context, csrf, key, identities.setup, context, company_id, payload.model_dump()
    )


@router.get("/identity-bindings")
def bindings(
    context: Auth,
    company_id: CompanyId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return {
        "data": identities.overview(context, company_id, offset=offset, limit=limit)
    }


@router.post("/identity-bindings")
def request_binding(
    context: Auth,
    company_id: CompanyId,
    payload: BindingRequest,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        identities.binding,
        context,
        company_id,
        None,
        "request",
        payload.model_dump(),
    )


@router.get("/me/binding")
def my_binding(context: Auth, company_id: CompanyId):
    return {"data": identities.my_binding(context, company_id)}


@router.post("/me/binding/accept")
def accept_binding(
    context: Auth,
    company_id: CompanyId,
    payload: BindingAccept,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        identities.binding,
        context,
        company_id,
        payload.binding_id,
        "accept",
        payload.model_dump(),
    )


@router.post("/identity-bindings/{id}/{operation}")
def change_binding(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    operation: Annotated[str, Path(pattern="^(cancel|suspend|resume)$")],
    payload: Change,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        identities.binding,
        context,
        company_id,
        id,
        operation,
        payload.model_dump(),
    )


@router.get("/people/{id}/roles")
def roles(context: Auth, company_id: CompanyId, id: schema.Id):
    return {"data": identities.role_list(context, company_id, id)}


@router.patch("/people/{id}/roles")
def change_roles(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    payload: RoleChange,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        identities.roles,
        context,
        company_id,
        id,
        payload.model_dump(),
    )


@router.get("/identity-candidates")
def candidates(
    context: Auth,
    company_id: CompanyId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str, Query(max_length=100)] = "",
):
    with company.transaction(context, company_id) as (c, ctx, _):
        company.principal(c, ctx, "ORG_ADMIN")
        data = [
            {"id": str(m["id"]), "name": m["name"]}
            for m in members(c, ctx)
            if m["active"] and search.casefold() in m["name"].casefold()
        ]
        return {"data": {"items": data[offset : offset + limit], "total": len(data)}}


@router.get("/company-hr-preview")
def hr_preview(context: Auth, company_id: CompanyId):
    with company.transaction(context, company_id) as (c, ctx, _):
        company.principal(c, ctx, "ORG_ADMIN")
        return {"data": organization.state(c, ctx)}


@router.post("/company-hr-import")
def hr_import(
    context: Auth,
    company_id: CompanyId,
    payload: CompanyHrImport,
    csrf: Csrf = None,
    key: Key = None,
):
    def run(c, ctx, _):
        result = organization.import_snapshot(c, ctx, payload.model_dump())
        identities.bump(c, ctx)
        identities.audit(
            c, ctx, "organization_unit", ctx.workspace_id, "import-hr", payload.reason
        )
        return result

    mutation_key(context, csrf, key)
    return {
        "data": company.action(
            context,
            company_id,
            "company-hr-import",
            key,
            payload.model_dump(),
            run,
            authorize=lambda c, ctx, p: company.principal(c, ctx, "ORG_ADMIN"),
        )
    }


class Reader(Change):
    person_id: schema.Id = Field(alias="personId")
    is_active: bool = Field(True, alias="isActive", strict=True)


class ReaderPatch(Change):
    is_active: bool = Field(alias="isActive", strict=True)


class Reassign(Change):
    step_id: schema.Id = Field(alias="stepId")
    person_id: schema.Id = Field(alias="personId")


@router.get("/documents/{id}/readers")
def readers(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return {
        "data": company_work.readers(
            context, company_id, id, offset=offset, limit=limit
        )
    }


@router.post("/documents/{id}/readers")
def grant_reader(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    payload: Reader,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        company_work.reader,
        context,
        company_id,
        id,
        payload.person_id,
        payload.model_dump(),
    )


@router.patch("/documents/{id}/readers/{person_id}")
def change_reader(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    person_id: schema.Id,
    payload: ReaderPatch,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        company_work.reader,
        context,
        company_id,
        id,
        person_id,
        payload.model_dump(),
    )


@router.get("/blocked-assignments")
def blocked(
    context: Auth,
    company_id: CompanyId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return {
        "data": company_work.blocked(context, company_id, offset=offset, limit=limit)
    }


@router.post("/documents/{id}/reassign-step")
def reassign(
    context: Auth,
    company_id: CompanyId,
    id: schema.Id,
    payload: Reassign,
    csrf: Csrf = None,
    key: Key = None,
):
    return command(
        context,
        csrf,
        key,
        company_work.reassign,
        context,
        company_id,
        id,
        payload.model_dump(),
    )


@router.get("/security-events")
def security_events(
    context: Auth,
    company_id: CompanyId,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return {
        "data": company_work.security_events(
            context, company_id, offset=offset, limit=limit
        )
    }


class OperatingPolicyApply(schema.Model):
    expected_version: int = Field(alias="expectedVersion", ge=0, strict=True)
    policy: OperatingPolicy


@router.get("/operations")
def operating_read(context: Auth, company_id: CompanyId):
    from fs.gw.operations import read

    return {"data": read(context, company_id)}


@router.post("/operating-policies")
def operating_apply(
    context: Auth,
    company_id: CompanyId,
    payload: OperatingPolicyApply,
    request: Request,
    csrf: Csrf = None,
    key: Key = None,
):
    from fs.core.security.router import require_origin
    from fs.gw.operations import apply_policy

    require_origin(request)
    body = {
        "expectedVersion": payload.expected_version,
        "policy": payload.policy.model_dump(by_alias=True),
    }
    return command(context, csrf, key, apply_policy, context, company_id, body)


class EmergencyKitRequest(schema.Model):
    reason: Reason


@router.post("/emergency-kit")
def emergency_kit(
    context: Auth,
    company_id: CompanyId,
    payload: EmergencyKitRequest,
    request: Request,
    csrf: Csrf = None,
    key: Key = None,
):
    from fs.core.security.router import require_origin
    from fs.gw.emergency import issue

    require_origin(request)
    mutation_key(context, csrf, key)
    return {"data": issue(context, company_id, payload.reason, key)}
