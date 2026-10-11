"""회사 근무 전용 API. 개인 공간 시드 복사 의존성을 적용하지 않는다."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.hr import work

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
Csrf = Annotated[str | None, Header(alias="X-CSRF-Token")]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Company = Annotated[int, Query(alias="companyId", gt=0)]


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Request(Body):
    kind: Literal["ANNUAL", "HALF_AM", "HALF_PM", "HOURLY", "TRIP"]
    startsAt: AwareDatetime
    endsAt: AwareDatetime
    reason: str = Field(min_length=2, max_length=500)
    destination: str | None = Field(default=None, max_length=200)


class Id(Body):
    id: int = Field(gt=0)


class Correction(Id):
    clockIn: AwareDatetime
    clockOut: AwareDatetime | None = None
    reason: str = Field(min_length=2, max_length=500)


class Close(Body):
    month: str = Field(pattern=r"^[1-9]\d{3}-(0[1-9]|1[0-2])$")


@router.get("/companies")
def companies(context: Auth):
    return {"data": work.company_list(context)}


@router.get("/overview")
def overview(
    context: Auth,
    company_id: Company,
    month: str = Query(pattern=r"^[1-9]\d{3}-(0[1-9]|1[0-2])$"),
):
    return {"data": work.overview(context, company_id, month)}


@router.post("/clock/{operation}")
def clock(
    operation: Literal["clock-in", "clock-out"],
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return {
        "data": work.mutate(
            context, company_id, operation, mutation_key(context, csrf, key), {}
        )
    }


@router.post("/requests")
def request(
    body: Request,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return {
        "data": work.mutate(
            context,
            company_id,
            "request",
            mutation_key(context, csrf, key),
            body.model_dump(mode="json"),
        )
    }


@router.post("/requests/{operation}")
def decision(
    operation: Literal["approve", "reject", "cancel"],
    body: Id,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return {
        "data": work.mutate(
            context,
            company_id,
            operation,
            mutation_key(context, csrf, key),
            body.model_dump(mode="json"),
        )
    }


@router.post("/corrections")
def correction(
    body: Correction,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return {
        "data": work.mutate(
            context,
            company_id,
            "correct",
            mutation_key(context, csrf, key),
            body.model_dump(mode="json"),
        )
    }


@router.post("/close")
def close(
    body: Close, context: Auth, company_id: Company, csrf: Csrf = None, key: Key = None
):
    return {
        "data": work.mutate(
            context,
            company_id,
            "close",
            mutation_key(context, csrf, key),
            body.model_dump(mode="json"),
        )
    }


# 사용자 관리에서도 게스트·직원·다른 회사 요청은 서비스에서 차단한다.
from decimal import Decimal

from pydantic import SecretStr

from fs.hr import users

LoginId = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9._-]{2,39}$")]
Password = Annotated[SecretStr, Field(min_length=10, max_length=256)]


class CreateUser(Body):
    loginId: LoginId
    password: Password
    name: str = Field(min_length=2, max_length=100)
    employeeCode: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,29}$")
    role: Literal["ADMIN", "STAFF"] = "STAFF"
    annualDays: Decimal = Field(
        default=15, ge=0, le=366, max_digits=5, decimal_places=2
    )


class UserId(Body):
    userId: int = Field(gt=0)


class CreateCompany(CreateUser):
    companyName: str = Field(min_length=1, max_length=120)
    workStart: str = Field(
        default="09:00", pattern=r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"
    )
    dailyMinutes: int = Field(default=480, ge=60, le=960)
    breakMinutes: int = Field(default=60, ge=0, le=240)

    @field_validator("companyName")
    @classmethod
    def company_nonblank(cls, v):
        if not v.strip():
            raise ValueError("회사명을 입력하세요.")
        return v.strip()


@router.get("/management-capabilities")
def management_capabilities(context: Auth):
    return {"data": users.capabilities(context)}


@router.post("/companies")
def register_company(
    body: CreateCompany, context: Auth, csrf: Csrf = None, key: Key = None
):
    values = body.model_dump(mode="json")
    values["password"] = body.password.get_secret_value()
    return {
        "data": users.register_company(
            context, mutation_key(context, csrf, key), values
        )
    }


class UserPassword(UserId):
    password: Password


class UserLogin(UserId):
    loginId: LoginId


class UserRole(UserId):
    role: Literal["ADMIN", "STAFF"]


def user_action(context, company_id, operation, body, csrf, key):
    values = body.model_dump(mode="json")
    if hasattr(body, "password"):
        values["password"] = body.password.get_secret_value()
    return {
        "data": users.mutate(
            context, company_id, operation, mutation_key(context, csrf, key), values
        )
    }


@router.get("/managed-companies")
def managed_companies(context: Auth):
    return {"data": users.managed_companies(context)}


@router.get("/users")
def list_users(context: Auth, company_id: Company):
    return {"data": users.listing(context, company_id)}


@router.post("/users")
def create_user(
    body: CreateUser,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return user_action(context, company_id, "create", body, csrf, key)


@router.post("/users/password")
def user_password(
    body: UserPassword,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return user_action(context, company_id, "password", body, csrf, key)


@router.post("/users/login-id")
def user_login(
    body: UserLogin,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return user_action(context, company_id, "login-id", body, csrf, key)


@router.post("/users/role")
def user_role(
    body: UserRole,
    context: Auth,
    company_id: Company,
    csrf: Csrf = None,
    key: Key = None,
):
    return user_action(context, company_id, "role", body, csrf, key)


@router.post("/users/disable")
def user_disable(
    body: UserId, context: Auth, company_id: Company, csrf: Csrf = None, key: Key = None
):
    return user_action(context, company_id, "disable", body, csrf, key)
