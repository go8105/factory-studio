"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

from datetime import date, timedelta
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


def _equipment_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "설비를 찾을 수 없습니다.")


def _duplicate_equipment_code() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {"equipmentCode": "이미 사용 중인 코드입니다."}},
    )


def _invalid_location() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {"locationId": "유효하지 않은 공간입니다."}},
    )


def _equipment_order(sort: str | None) -> str:
    if sort is None:
        return "equipment_code ASC"
    field, _, direction = sort.partition(":")
    column = repo.EQUIPMENT_SORT.get(field)
    if column is None or direction not in ("asc", "desc"):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "정렬 조건이 올바르지 않습니다.",
            {"fields": {"sort": f"허용: {', '.join(repo.EQUIPMENT_SORT)} (asc|desc)"}},
        )
    return f"{column} {direction.upper()}"


def list_equipments(
    context: AuthContext,
    active: bool | None,
    location_id: int | None,
    sort: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    order = _equipment_order(sort)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_equipments(
            connection, scoped, active, location_id, order, offset, limit
        )


def get_equipment(context: AuthContext, equipment_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_equipment(connection, scoped, equipment_id)
    if found is None:
        raise _equipment_not_found()
    return found


def list_locations(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_locations(connection, scoped)


def create_equipment(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.equipment.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        if not repo.location_exists(connection, scoped, values["location_id"]):
            raise _invalid_location()
        if repo.equipment_code_taken(
            connection, scoped, values["equipment_code"], None
        ):
            raise _duplicate_equipment_code()
        created = repo.insert_equipment(connection, scoped, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "equipment",
            created["id"],
            created,
            201,
        )
        return created


def update_equipment(
    context: AuthContext, equipment_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.equipment.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": equipment_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_equipment(connection, scoped, equipment_id)
        if current is None:
            raise _equipment_not_found()
        if "location_id" in values and not repo.location_exists(
            connection, scoped, values["location_id"]
        ):
            raise _invalid_location()
        if "location_id" in values and values["location_id"] != current["locationId"]:
            references = repo.equipment_meter_references(
                connection, scoped, equipment_id
            )
            if references:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "계측기가 연결된 설비는 공간을 바꿀 수 없습니다. 계측기를 먼저 정리하세요.",
                    {"reason": "LOCATION_IN_USE", "references": references},
                )
        if "equipment_code" in values and repo.equipment_code_taken(
            connection, scoped, values["equipment_code"], equipment_id
        ):
            raise _duplicate_equipment_code()
        updated = repo.update_equipment(connection, scoped, equipment_id, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "equipment",
            equipment_id,
            updated,
        )
        return updated


def delete_equipment(context: AuthContext, equipment_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.equipment.delete"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": equipment_id}
        )
        if cached is not None:
            return
        if repo.get_equipment(connection, scoped, equipment_id) is None:
            raise _equipment_not_found()
        references = repo.equipment_references(connection, scoped, equipment_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "다른 기준정보가 참조 중이라 삭제할 수 없습니다. 사용 안 함으로 바꾸면 새 입력에서 제외됩니다.",
                {"references": references},
            )
        repo.delete_equipment(connection, scoped, equipment_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "equipment",
            equipment_id,
            {},
            204,
        )


# ---- F-02 계측 조회 (FS-018b) ----
MAX_READING_DAYS = 31
DEFAULT_READING_DAYS = 7


def list_readings(
    context: AuthContext,
    filters: dict[str, Any],
    date_from: date | None,
    date_to: date | None,
    sort: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, dict[str, str] | None]:
    if (date_from is None) != (date_to is None):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "조회 기간은 시작일과 종료일을 함께 지정합니다.",
            {"fields": {"from" if date_from is None else "to": "필요합니다."}},
        )
    if date_from and date_to:
        if date_from > date_to:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "조회 기간이 올바르지 않습니다.",
                {"fields": {"to": "시작일 이후여야 합니다."}},
            )
        if (date_to - date_from).days >= MAX_READING_DAYS:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "조회 기간이 너무 깁니다.",
                {"fields": {"to": f"최대 {MAX_READING_DAYS}일까지 조회합니다."}},
            )
    order = "r.observed_at ASC"
    if sort is not None:
        field, _, direction = sort.partition(":")
        if field not in repo.READING_SORT or direction not in ("asc", "desc"):
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "정렬 조건이 올바르지 않습니다.",
                {"fields": {"sort": "허용: observedAt (asc|desc)"}},
            )
        order = f"{repo.READING_SORT[field]} {direction.upper()}"
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if date_to is None:
            # 기간을 주지 않으면 가장 최근 계측일까지 7일. 빈 화면으로 시작하지 않는다.
            date_to = repo.latest_reading_date(connection, scoped)
            if date_to is None:
                return [], 0, None
            date_from = date_to - timedelta(days=DEFAULT_READING_DAYS - 1)
        rows, total = repo.list_readings(
            connection, scoped, filters, date_from, date_to, order, offset, limit
        )
    return rows, total, {"from": date_from.isoformat(), "to": date_to.isoformat()}


def list_sites(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        return repo.list_sites(connection, read_scope(connection, context, MODULE))


def list_meters(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        return repo.list_meters(connection, read_scope(connection, context, MODULE))
