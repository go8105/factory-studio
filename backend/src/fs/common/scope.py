"""업무 모듈의 범위 S 확정 (FS-006 TX-01·TX-05 순서).

세션에서 얻은 generation_id는 다른 트랜잭션에서 읽은 값이라 초기화와 경합할 수 있다.
업무 질의 직전에 같은 트랜잭션 안에서 활성 세대와 모듈 사용 여부를 다시 읽는다.
"""

from __future__ import annotations

from dataclasses import replace

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
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
            SELECT w.active_generation_id, m.enabled
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
    if row is None:
        raise ApiError(401, "SESSION_EXPIRED", "공간을 찾을 수 없습니다.")
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
