"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection

from fs.common.auth import AuthContext
from fs.common.db import get_engine
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.fems import repository as repo

MODULE = "fems"


def _not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "에너지원을 찾을 수 없습니다.")


def _duplicate_code() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {"sourceCode": "이미 사용 중인 코드입니다."}},
    )


def _order(sort: str | None) -> str:
    if sort is None:
        return "source_code ASC"
    field, _, direction = sort.partition(":")
    column = repo.SOURCE_SORT.get(field)
    if column is None or direction not in ("asc", "desc"):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "정렬 조건이 올바르지 않습니다.",
            {"fields": {"sort": f"허용: {', '.join(repo.SOURCE_SORT)} (asc|desc)"}},
        )
    return f"{column} {direction.upper()}"


def _read():
    engine = get_engine().execution_options(
        isolation_level="REPEATABLE READ", postgresql_readonly=True
    )
    return engine.begin()


def list_sources(
    context: AuthContext, active: bool | None, sort: str | None, offset: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    order = _order(sort)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_sources(connection, scoped, active, order, offset, limit)


def get_source(context: AuthContext, source_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_source(connection, scoped, source_id)
    if found is None:
        raise _not_found()
    return found


def _replay(
    connection: Connection, scoped: AuthContext, operation: str, key: str, body: Any
) -> tuple[str, dict[str, Any] | None]:
    digest = request_digest(body)
    return digest, find_receipt(connection, scoped, operation, key, digest)


def create_source(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_source.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        if repo.code_taken(connection, scoped, values["source_code"], None):
            raise _duplicate_code()
        created = repo.insert_source(connection, scoped, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_source",
            created["id"],
            created,
            201,
        )
        return created


def update_source(
    context: AuthContext, source_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_source.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": source_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_source(connection, scoped, source_id)
        if current is None:
            raise _not_found()
        if "source_code" in values and repo.code_taken(
            connection, scoped, values["source_code"], source_id
        ):
            raise _duplicate_code()
        # 계측값·계수·요금 단가는 계측 단위를 전제로 저장돼 있다. 단위를 바꾸면 하위 계산이 조용히 틀린다.
        if values.get("measure_unit", current["measureUnit"]) != current["measureUnit"]:
            references = repo.source_references(connection, scoped, source_id)
            if references:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "참조 중인 에너지원은 계측 단위를 바꿀 수 없습니다. 새 에너지원을 등록하세요.",
                    {"reason": "UNIT_IN_USE", "references": references},
                )
        updated = repo.update_source(connection, scoped, source_id, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_source",
            source_id,
            updated,
        )
        return updated


def delete_source(context: AuthContext, source_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_source.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": source_id})
        if cached is not None:
            return
        if repo.get_source(connection, scoped, source_id) is None:
            raise _not_found()
        references = repo.source_references(connection, scoped, source_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "다른 기준정보가 참조 중이라 삭제할 수 없습니다. 사용 안 함으로 바꾸면 새 입력에서 제외됩니다.",
                {"references": references},
            )
        repo.delete_source(connection, scoped, source_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_source",
            source_id,
            {},
            204,
        )
