"""공통 엔진 — 요청 하나의 바깥 틀 (DSN-01 C, W0-4).

솔루션마다 같은 코드를 복사해 두던 세 가지를 한 곳으로 모은다.

- `read()`      조회 트랜잭션(REPEATABLE READ · 읽기 전용)
- `action()`    쓰기 한 건: 공간 잠금 → 세대·모듈 재확인 → 멱등 영수증 → 처리 → 영수증 저장(같은 트랜잭션)
- `mutation_key()` 라우터에서 CSRF와 멱등 키 확인

업무 규칙은 각 솔루션이 `action`에 넘기는 함수 안에 그대로 둔다. 이 파일은 순서와 경계만 책임진다.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import Connection

from fs.common.auth import AuthContext, require_csrf
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import write_scope

# 처리 함수: (연결, 범위 확정된 문맥) → (응답, 영수증 대상 이름, 대상 id)
Action = Callable[[Connection, AuthContext], tuple[Any, str, int]]


def read():
    """조회 트랜잭션. 같은 요청 안에서 본 값이 바뀌지 않고, 쓰기는 막힌다."""
    return (
        get_engine()
        .execution_options(isolation_level="REPEATABLE READ", postgresql_readonly=True)
        .begin()
    )


def action(
    module: str,
    context: AuthContext,
    operation: str,
    key: str,
    body: Any,
    fn: Action,
    status: int = 200,
) -> Any:
    """쓰기 한 건: 공간 잠금 → 멱등 영수증 확인 → 처리 → 영수증 저장(같은 트랜잭션)."""
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, module)
        digest = request_digest(body)
        cached = find_receipt(connection, scoped, operation, key, digest)
        if cached is not None:
            return cached
        result, entity, entity_id = fn(connection, scoped)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            entity,
            entity_id,
            result,
            status,
        )
        return result


def mutation_key(context: AuthContext, csrf: str | None, key: str | None) -> str:
    """쓰기 요청의 공통 입구: CSRF 확인 + 멱등 키 확인."""
    require_csrf(context, csrf)
    if not key or len(key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    return key
