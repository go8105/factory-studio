"""업무 모듈의 범위 S 확정 (FS-006 TX-01·TX-05 순서).

세션에서 얻은 generation_id는 다른 트랜잭션에서 읽은 값이라 초기화와 경합할 수 있다.
업무 질의 직전에 같은 트랜잭션 안에서 활성 세대와 모듈 사용 여부를 다시 읽는다.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Connection, text

from fs.common.auth import AuthContext, resolve_auth
from fs.common.db import get_engine
from fs.common.errors import ApiError

# core.service._workspace_lock과 같은 키 공간. 초기화·모듈 설정과 직렬화된다.
WORKSPACE_LOCK_NAMESPACE = 16


def _scope(
    connection: Connection, context: AuthContext, module_key: str
) -> AuthContext:
    row = (
        connection.execute(
            text(
                """
            SELECT w.active_generation_id, m.enabled,
                   w.workspace_kind='GUEST' AND w.expires_at <= clock_timestamp() expired
            FROM core.workspace w
            LEFT JOIN core.workspace_module m
              ON m.workspace_id=w.id AND m.module_key=:module
            WHERE w.id=:w
            """
            ),
            {"w": context.workspace_id, "module": module_key},
        )
        .mappings()
        .one_or_none()
    )
    if row is None:  # 회수(삭제)된 공간
        raise ApiError(401, "SESSION_EXPIRED", "공간을 찾을 수 없습니다.")
    # 인증은 잠금 전에 만료를 봤다. 잠금을 기다리는 사이 만료될 수 있어 서버 현재 시각으로 다시 본다(FS-006b §4.2).
    if row["expired"]:
        raise ApiError(410, "WORKSPACE_EXPIRED", "게스트 공간이 만료되었습니다.")
    if not row["enabled"]:
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            "이 앱은 내 공간에서 사용하지 않도록 설정되어 있습니다.",
            {"reason": "MODULE_DISABLED", "moduleKey": module_key},
        )
    return replace(context, generation_id=row["active_generation_id"])


def read_scope(
    connection: Connection, context: AuthContext, module_key: str
) -> AuthContext:
    """조회용. 호출자는 REPEATABLE READ 트랜잭션 안에서 부른다."""
    return _scope(connection, context, module_key)


def write_scope(
    connection: Connection, context: AuthContext, module_key: str
) -> AuthContext:
    """쓰기용. 공간 잠금을 먼저 잡아 초기화 전환과 직렬화한 뒤 세대를 확정한다."""
    connection.execute(
        text("SELECT pg_advisory_xact_lock(:namespace,:workspace)"),
        {"namespace": WORKSPACE_LOCK_NAMESPACE, "workspace": context.workspace_id},
    )
    return _scope(connection, context, module_key)


def module_available(
    connection: Connection, workspace_id: int, module_key: str
) -> bool:
    """교차 조회용: 켜져 있고 활성 세대에 시드가 복사됐을 때만 True(W0-1).

    아직 열지 않은 솔루션은 '꺼짐'과 같게 다룬다 — interface 함수는 None을 돌려준다(DSN-01 S2).
    """
    return bool(
        connection.execute(
            text(
                """
            SELECT m.enabled AND m.seeded_generation_id IS NOT DISTINCT FROM w.active_generation_id
            FROM core.workspace_module m JOIN core.workspace w ON w.id=m.workspace_id
            WHERE m.workspace_id=:w AND m.module_key=:module
            """
            ),
            {"w": workspace_id, "module": module_key},
        ).scalar()
    )


def seed_ready(module_key: str) -> Callable[..., None]:
    """솔루션 라우터 의존성: 처음 열 때 그 솔루션 시드를 복사한다(W0-1 지연 복사).

    읽기 트랜잭션은 REPEATABLE READ·읽기 전용이라 그 안에서 복사할 수 없다. 요청 트랜잭션보다 먼저
    짧은 쓰기 트랜잭션에서 공간 잠금 → 다시 확인 → 복사 → 표시한다. 이미 복사됐으면 잠금 없이 끝난다.
    """
    from seed.copy import copy_module_seed

    def dependency(context: Annotated[AuthContext, Depends(resolve_auth)]) -> None:
        with get_engine().connect() as connection:
            ready = connection.execute(
                text(
                    """
                SELECT m.seeded_generation_id IS NOT DISTINCT FROM w.active_generation_id
                FROM core.workspace_module m JOIN core.workspace w ON w.id=m.workspace_id
                WHERE m.workspace_id=:w AND m.module_key=:module
                """
                ),
                {"w": context.workspace_id, "module": module_key},
            ).scalar()
        if ready is None or ready:
            return
        with get_engine().begin() as connection:
            connection.execute(
                text("SELECT pg_advisory_xact_lock(:namespace,:workspace)"),
                {
                    "namespace": WORKSPACE_LOCK_NAMESPACE,
                    "workspace": context.workspace_id,
                },
            )
            copy_module_seed(connection, context.workspace_id, module_key)

    return dependency
