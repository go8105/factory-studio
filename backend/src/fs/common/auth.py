from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Header
from sqlalchemy import Connection, text

from fs.common.config import get_settings
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.security import csrf_matches, token_hash


@dataclass(frozen=True)
class AuthContext:
    actor_kind: str
    actor_key: str
    workspace_id: int
    generation_id: int
    user_id: int | None
    roles: frozenset[str]
    token: str


def _resolve_guest(connection: Connection, token: str) -> AuthContext:
    row = (
        connection.execute(
            text(
                """
            SELECT id, active_generation_id, guest_actor_key::text actor_key, expires_at
            FROM core.workspace
            WHERE workspace_kind='GUEST' AND guest_session_key=:token_hash
            """
            ),
            {"token_hash": token_hash(token)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise ApiError(401, "SESSION_EXPIRED", "세션이 없거나 종료되었습니다.")
    if row["expires_at"] <= datetime.now(UTC):
        raise ApiError(410, "WORKSPACE_EXPIRED", "게스트 공간이 만료되었습니다.")
    return AuthContext(
        actor_kind="GUEST",
        actor_key=row["actor_key"],
        workspace_id=row["id"],
        generation_id=row["active_generation_id"],
        user_id=None,
        roles=frozenset({"GUEST"}),
        token=token,
    )


def _resolve_member(
    connection: Connection, token: str, *, allow_recovery=False
) -> AuthContext:
    row = (
        connection.execute(
            text(
                """
            SELECT s.id session_id, u.id user_id, w.id workspace_id,
                   w.active_generation_id, s.expires_at, s.assurance,
                   array_remove(array_agg(r.role_key), NULL) roles
            FROM core.auth_session s
            JOIN core.app_user u ON u.id=s.user_id
            JOIN core.workspace w ON w.owner_user_id=u.id AND w.workspace_kind='MEMBER'
            LEFT JOIN core.user_role ur ON ur.user_id=u.id
            LEFT JOIN core.role r ON r.id=ur.role_id
            WHERE s.token_hash=:token_hash AND s.revoked_at IS NULL
              AND u.status='active' AND u.disabled_at IS NULL
              AND s.security_version=u.security_version
              AND (s.absolute_expires_at IS NULL OR s.absolute_expires_at>clock_timestamp())
            GROUP BY s.id,u.id,w.id,w.active_generation_id,s.expires_at
            """
            ),
            {"token_hash": token_hash(token)},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["expires_at"] <= datetime.now(UTC):
        raise ApiError(401, "SESSION_EXPIRED", "세션이 없거나 만료되었습니다.")
    if row["assurance"] == "RECOVERY_LIMITED" and not allow_recovery:
        raise ApiError(
            403, "RECOVERY_ONLY", "인증 앱을 다시 등록한 뒤 로그인해 주세요."
        )
    connection.execute(
        text(
            "UPDATE core.auth_session SET expires_at=LEAST(:expires,coalesce(absolute_expires_at,:expires)) WHERE id=:id"
        ),
        {
            "expires": datetime.now(UTC)
            + timedelta(minutes=get_settings().session_idle_minutes),
            "id": row["session_id"],
        },
    )
    return AuthContext(
        actor_kind="MEMBER",
        actor_key=str(row["user_id"]),
        workspace_id=row["workspace_id"],
        generation_id=row["active_generation_id"],
        user_id=row["user_id"],
        roles=frozenset(row["roles"]),
        token=token,
    )


def resolve_auth(
    fs_session: Annotated[str | None, Cookie(alias="fs_session")] = None,
) -> AuthContext:
    if not fs_session or len(fs_session) < 4 or fs_session[1] != "_":
        raise ApiError(401, "SESSION_EXPIRED", "세션이 필요합니다.")
    with get_engine().begin() as connection:
        return resolve_token(connection, fs_session)


def resolve_token(
    connection: Connection, token: str, *, allow_recovery=False
) -> AuthContext:
    if token.startswith("g_"):
        return _resolve_guest(connection, token)
    if token.startswith("m_"):
        return _resolve_member(connection, token, allow_recovery=allow_recovery)
    raise ApiError(401, "SESSION_EXPIRED", "알 수 없는 세션 종류입니다.")


def require_csrf(
    context: AuthContext,
    x_csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if not x_csrf_token:
        raise ApiError(403, "FORBIDDEN", "CSRF 토큰이 필요합니다.")
    if context.actor_kind == "GUEST":
        valid = csrf_matches(get_settings().session_secret, context.token, x_csrf_token)
    else:
        with get_engine().connect() as connection:
            stored = connection.execute(
                text(
                    "SELECT csrf_token_hash FROM core.auth_session WHERE token_hash=:token_hash AND revoked_at IS NULL"
                ),
                {"token_hash": token_hash(context.token)},
            ).scalar_one_or_none()
        valid = stored is not None and stored == token_hash(x_csrf_token)
    if not valid:
        raise ApiError(403, "FORBIDDEN", "CSRF 토큰이 일치하지 않습니다.")
