"""GW-scoped recovery orchestration at the core login cookie path."""

from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from fs.common.config import get_settings
from fs.core.security.router import require_challenge, require_origin
from fs.gw import emergency

router = APIRouter()


class EmergencyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    grant_token: str = Field(alias="grantToken", pattern=r"^[A-Za-z0-9_-]{43}$")


@router.post("/emergency", status_code=201)
def redeem(
    payload: EmergencyInput,
    request: Request,
    response: Response,
    challenge: Annotated[str | None, Cookie(alias="fs_auth_challenge")] = None,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_challenge(challenge, csrf)
    value, error = emergency.redeem(challenge, payload.grant_token)
    if error:
        raise error
    response.set_cookie(
        get_settings().session_cookie,
        value["token"],
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie("fs_auth_challenge", path="/api/v1/core/security/login")
    return {"data": {"recoveryOnly": True, "csrfToken": value["csrfToken"]}}
