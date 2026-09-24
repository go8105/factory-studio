from __future__ import annotations

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Cookie, Depends, Header, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth, resolve_token
from fs.common.config import get_settings
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest
from fs.common.page import Page
from fs.common.security import guest_csrf_token, member_csrf_token
from fs.core.schema import LoginRequest, ModuleUpdate
from fs.core.service import (
    create_guest,
    current_session,
    list_admin_records,
    list_modules,
    login_member,
    logout,
    reset_generation,
    update_module,
    workspace_info,
)

router = APIRouter()


def _set_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=get_settings().session_cookie,
        value=token,
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )


@router.post("/guest-sessions", status_code=201)
def guest_session(
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    fs_session: Annotated[str | None, Cookie(alias="fs_session")] = None,
) -> dict[str, object]:
    if not idempotency_key or len(idempotency_key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    if fs_session:
        with get_engine().begin() as connection:
            context = resolve_token(connection, fs_session)
            if context.actor_kind != "GUEST":
                raise ApiError(
                    409, "PRECONDITION_NOT_MET", "회원 세션이 이미 활성 상태입니다."
                )
            cached = find_receipt(
                connection,
                context,
                "guest.session.create",
                idempotency_key,
                request_digest({}),
            )
            if cached is None:
                raise ApiError(
                    422, "IDEMPOTENCY_CONFLICT", "현재 세션의 생성 키가 아닙니다."
                )
            cached["csrfToken"] = guest_csrf_token(
                get_settings().session_secret, fs_session
            )
        return {"data": cached}
    target_date = datetime.now(ZoneInfo("Asia/Seoul")).date()
    with get_engine().begin() as connection:
        data, token = create_guest(connection, target_date, idempotency_key)
    _set_cookie(response, token)
    return {"data": data}


@router.post("/sessions", status_code=201)
def member_session(
    payload: LoginRequest,
    response: Response,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    fs_session: Annotated[str | None, Cookie(alias="fs_session")] = None,
) -> dict[str, object]:
    if not idempotency_key or len(idempotency_key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    digest = request_digest(
        {"loginId": payload.login_id.strip().lower(), "password": payload.password}
    )
    if fs_session:
        with get_engine().begin() as connection:
            context = resolve_token(connection, fs_session)
            if context.actor_kind != "MEMBER":
                raise ApiError(
                    409, "PRECONDITION_NOT_MET", "게스트 세션이 이미 활성 상태입니다."
                )
            cached = find_receipt(
                connection,
                context,
                "member.session.create",
                idempotency_key,
                digest,
            )
            if cached is None:
                raise ApiError(
                    422, "IDEMPOTENCY_CONFLICT", "현재 세션의 로그인 키가 아닙니다."
                )
            cached["csrfToken"] = member_csrf_token(
                get_settings().session_secret, fs_session
            )
        return {"data": cached}
    with get_engine().begin() as connection:
        data, token = login_member(
            connection, payload.login_id, payload.password, idempotency_key
        )
    _set_cookie(response, token)
    return {"data": data}


@router.get("/sessions/current")
def get_current_session(
    context: Annotated[AuthContext, Depends(resolve_auth)],
) -> dict[str, object]:
    with get_engine().connect() as connection:
        data = current_session(connection, context)
    secret = get_settings().session_secret
    data["csrfToken"] = (
        guest_csrf_token(secret, context.token)
        if context.actor_kind == "GUEST"
        else member_csrf_token(secret, context.token)
    )
    return {"data": data}


@router.delete("/sessions/current", status_code=204)
def delete_current_session(
    response: Response,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    require_csrf(context, x_csrf_token)
    with get_engine().begin() as connection:
        logout(connection, context)
    response.delete_cookie(get_settings().session_cookie, path="/")


@router.get("/workspace")
def get_workspace(
    context: Annotated[AuthContext, Depends(resolve_auth)],
) -> dict[str, object]:
    with get_engine().connect() as connection:
        return {"data": workspace_info(connection, context)}


@router.get("/workspace/modules")
def get_modules(
    context: Annotated[AuthContext, Depends(resolve_auth)],
) -> dict[str, object]:
    with get_engine().connect() as connection:
        return {"data": list_modules(connection, context)}


@router.patch("/workspace/modules/{module_key}")
def patch_module(
    module_key: str,
    payload: ModuleUpdate,
    context: Annotated[AuthContext, Depends(resolve_auth)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> dict[str, object]:
    require_csrf(context, x_csrf_token)
    if not idempotency_key or len(idempotency_key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    with get_engine().begin() as connection:
        data = update_module(
            connection, context, module_key, payload.enabled, idempotency_key
        )
    return {"data": data}


@router.post("/workspace/generations", status_code=201)
def post_generation(
    context: Annotated[AuthContext, Depends(resolve_auth)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> dict[str, object]:
    require_csrf(context, x_csrf_token)
    if not idempotency_key or len(idempotency_key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    target_date = datetime.now(ZoneInfo("Asia/Seoul")).date()
    with get_engine().begin() as connection:
        data = reset_generation(connection, context, target_date, idempotency_key)
    return {"data": data}


@router.get("/admin/job-runs")
def get_admin_job_runs(
    context: Annotated[AuthContext, Depends(resolve_auth)],
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    with get_engine().connect() as connection:
        data, total = list_admin_records(
            connection, context, "job-runs", page.offset, page.limit
        )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/admin/audit-events")
def get_admin_audit_events(
    context: Annotated[AuthContext, Depends(resolve_auth)],
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    with get_engine().connect() as connection:
        data, total = list_admin_records(
            connection, context, "audit-events", page.offset, page.limit
        )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }
