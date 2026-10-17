"""회사 GW의 읽기 전용 준비 상태. 설정/업무 쓰기는 후속 단계다."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from fs.common.auth import AuthContext, resolve_auth
from fs.common.errors import ApiError
from fs.gw import company

router = APIRouter()
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
