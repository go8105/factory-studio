"""회사 근무 전용 API. 개인 공간 시드 복사 의존성을 적용하지 않는다."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

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
