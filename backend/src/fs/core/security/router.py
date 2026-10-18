"""Core security API. Expected failures leave the transaction before raising."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Header, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from fs.common.auth import AuthContext, require_csrf, resolve_auth, resolve_token
from fs.common.config import get_settings
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.security import member_csrf_token
from fs.core.security import service
from fs.core.security.config import security_settings
from fs.core.service import current_session

router = APIRouter()


class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=1, max_length=200)


class OTPInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str = Field(min_length=1, max_length=64)


class EnrollmentInput(OTPInput):
    factor_id: str = Field(alias="factorId", pattern=r"^[1-9][0-9]{0,18}$")


def require_origin(request):
    settings = security_settings()
    if settings.mode == "COMPANY" and request.url.scheme != "https":
        raise ApiError(
            503, "SECURITY_CONFIGURATION_UNAVAILABLE", "안전한 연결을 확인해 주세요."
        )
    origin = request.headers.get("origin")
    expected = settings.public_origin or str(request.base_url).rstrip("/")
    if (
        (origin is not None and origin != expected)
        or (settings.mode == "COMPANY" and origin != expected)
        or request.headers.get("sec-fetch-site") == "cross-site"
    ):
        raise ApiError(403, "FORBIDDEN", "현재 제품 화면에서 다시 시도하세요.")


def require_challenge(challenge, csrf):
    expected = member_csrf_token(
        get_settings().session_secret, "challenge:" + (challenge or "")
    )
    if not challenge or not csrf or not hmac.compare_digest(expected, csrf):
        raise ApiError(403, "FORBIDDEN", "로그인 화면에서 다시 시작하세요.")


def challenge_cookie(response, token):
    response.set_cookie(
        "fs_auth_challenge",
        token,
        max_age=300,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path="/api/v1/core/security/login",
    )
    response.headers["Cache-Control"] = "no-store"
    return {
        "mfaRequired": True,
        "challengeCsrfToken": member_csrf_token(
            get_settings().session_secret, "challenge:" + token
        ),
        "expiresInSeconds": 300,
    }


def finish(result):
    data, error = result
    if error:
        raise error
    return {"data": data}


@router.get("/me")
def me(context: Annotated[AuthContext, Depends(resolve_auth)]):
    with get_engine().begin() as c:
        result = service.security_summary(c, context)
    return finish(result)


@router.post("/enrollment/start")
def enrollment_start(
    payload: PasswordInput,
    request: Request,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.start_enrollment(c, context, payload.password)
    return finish(result)


@router.post("/enrollment/confirm")
def enrollment_confirm(
    payload: EnrollmentInput,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.confirm_enrollment(c, context, payload.factor_id, payload.code)
    if result[1] is None:
        response.delete_cookie(get_settings().session_cookie, path="/")
    return finish(result)


@router.post("/step-up")
def step_up(
    payload: OTPInput,
    request: Request,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.step_up(c, context, payload.code)
    return finish(result)


@router.post("/login/verify", status_code=201)
def verify_login(
    payload: OTPInput,
    request: Request,
    response: Response,
    challenge: Annotated[str | None, Cookie(alias="fs_auth_challenge")] = None,
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_challenge(challenge, csrf)
    with get_engine().begin() as c:
        result = service.verify_login(c, challenge, payload.code)
    if result[1]:
        raise result[1]
    value = result[0]
    if value["recoveryOnly"]:
        data = {"recoveryOnly": True}
    else:
        with get_engine().begin() as c:
            context = resolve_token(c, value["token"])
        with get_engine().connect() as c:
            data = current_session(c, context)
    data["csrfToken"] = value["csrfToken"]
    response.set_cookie(
        get_settings().session_cookie,
        value["token"],
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="lax",
        path="/",
    )
    response.delete_cookie("fs_auth_challenge", path="/api/v1/core/security/login")
    return {"data": data}


def recovery_context(
    fs_session: Annotated[str | None, Cookie(alias="fs_session")] = None,
):
    if not fs_session:
        raise service.failed()
    with get_engine().begin() as c:
        return resolve_token(c, fs_session, allow_recovery=True)


@router.post("/recovery/start")
def recovery_start(
    request: Request,
    context: Annotated[AuthContext, Depends(recovery_context)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.start_enrollment(c, context, "", recovery=True)
    return finish(result)


@router.post("/recovery/complete")
def recovery_complete(
    payload: EnrollmentInput,
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(recovery_context)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.confirm_enrollment(
            c, context, payload.factor_id, payload.code, recovery=True
        )
    if result[1] is None:
        response.delete_cookie(get_settings().session_cookie, path="/")
    return finish(result)


@router.get("/recovery/status")
def recovery_status(context: Annotated[AuthContext, Depends(recovery_context)]):
    with get_engine().begin() as c:
        row, error = service.session(c, context, allow_recovery=True)
    if error:
        raise error
    if row["assurance"] != "RECOVERY_LIMITED":
        raise service.failed()
    return {
        "data": {
            "recoveryOnly": True,
            "csrfToken": member_csrf_token(
                get_settings().session_secret, context.token
            ),
        }
    }


@router.post("/recovery/logout", status_code=204)
def recovery_logout(
    request: Request,
    response: Response,
    context: Annotated[AuthContext, Depends(recovery_context)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    from fs.common.security import token_hash

    with get_engine().begin() as c:
        c.execute(
            text(
                "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE user_id=:u AND token_hash=:t"
            ),
            {"u": context.user_id, "t": token_hash(context.token)},
        )
        service.audit(c, context.user_id, "security.recovery.logout")
    response.delete_cookie(get_settings().session_cookie, path="/")


@router.post("/recovery-codes/rotate")
def rotate_codes(
    request: Request,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.rotate_codes(c, context)
    return finish(result)


@router.get("/sessions")
def sessions(context: Annotated[AuthContext, Depends(resolve_auth)]):
    with get_engine().begin() as c:
        result = service.list_sessions(c, context)
    return finish(result)


@router.post("/sessions/revoke-others")
def revoke_others(
    request: Request,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    csrf: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    require_origin(request)
    require_csrf(context, csrf)
    with get_engine().begin() as c:
        result = service.revoke_other_sessions(c, context)
    return finish(result)
