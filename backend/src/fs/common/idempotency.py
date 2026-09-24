from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.errors import ApiError


def request_digest(body: Any) -> str:
    canonical = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    return hashlib.sha256(canonical).hexdigest()


def find_receipt(
    connection: Connection,
    context: AuthContext,
    operation_key: str,
    request_key: str,
    digest: str,
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                """
            SELECT request_hash,response_summary,http_status,created_at
            FROM core.request_receipt
            WHERE workspace_id=:w AND generation_id=:g AND actor_kind=:kind
              AND actor_key=:actor AND operation_key=:operation AND request_key=:request
            FOR UPDATE
            """
            ),
            {
                "w": context.workspace_id,
                "g": context.generation_id,
                "kind": context.actor_kind,
                "actor": context.actor_key,
                "operation": operation_key,
                "request": request_key,
            },
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return None
    if row["created_at"] <= datetime.now(UTC) - timedelta(hours=24):
        raise ApiError(422, "IDEMPOTENCY_CONFLICT", "만료된 멱등 키입니다.")
    if row["request_hash"] != digest:
        raise ApiError(422, "IDEMPOTENCY_CONFLICT", "같은 키의 요청 본문이 다릅니다.")
    return dict(row["response_summary"])


def save_receipt(
    connection: Connection,
    context: AuthContext,
    operation_key: str,
    request_key: str,
    digest: str,
    entity_kind: str,
    entity_id: int,
    response: dict[str, Any],
    status: int = 200,
) -> None:
    connection.execute(
        text(
            """
            INSERT INTO core.request_receipt
              (workspace_id,generation_id,actor_user_id,operation_key,request_key,
               request_hash,entity_kind,entity_id,response_summary,http_status,
               completed_at,actor_kind,actor_key)
            VALUES
              (:w,:g,:user,:operation,:request,:digest,:entity,:entity_id,
               CAST(:response AS jsonb),:status,now(),:kind,:actor)
            """
        ),
        {
            "w": context.workspace_id,
            "g": context.generation_id,
            "user": context.user_id,
            "operation": operation_key,
            "request": request_key,
            "digest": digest,
            "entity": entity_kind,
            "entity_id": entity_id,
            "response": json.dumps(response, ensure_ascii=False),
            "status": status,
            "kind": context.actor_kind,
            "actor": context.actor_key,
        },
    )
