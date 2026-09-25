"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

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


def _tariff_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "요금제를 찾을 수 없습니다.")


def _duplicate_tariff_code() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {"tariffCode": "이미 사용 중인 코드입니다."}},
    )


def _invalid_energy_source() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {"energySourceId": "유효하지 않은 에너지원입니다."}},
    )


def _invalid_effective_to() -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {
            "fields": {
                "effectiveTo": "적용 종료 연월은 적용 시작 연월 이상이어야 합니다."
            }
        },
    )


def _tariff_order(sort: str | None) -> str:
    if sort is None:
        return "tariff_code ASC"
    field, _, direction = sort.partition(":")
    column = repo.TARIFF_SORT.get(field)
    if column is None or direction not in ("asc", "desc"):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "정렬 조건이 올바르지 않습니다.",
            {"fields": {"sort": f"허용: {', '.join(repo.TARIFF_SORT)} (asc|desc)"}},
        )
    return f"{column} {direction.upper()}"


def list_tariffs(
    context: AuthContext,
    energy_source_id: int | None,
    sort: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    order = _tariff_order(sort)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_tariffs(
            connection, scoped, energy_source_id, order, offset, limit
        )


def get_tariff(context: AuthContext, tariff_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_tariff(connection, scoped, tariff_id)
    if found is None:
        raise _tariff_not_found()
    return found


def create_tariff(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.tariff.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        if not repo.source_exists(connection, scoped, values["energy_source_id"]):
            raise _invalid_energy_source()
        if (
            values.get("effective_to") is not None
            and values["effective_to"] < values["effective_from"]
        ):
            raise _invalid_effective_to()
        if repo.tariff_code_taken(connection, scoped, values["tariff_code"], None):
            raise _duplicate_tariff_code()
        conflicts = repo.find_overlapping_tariffs(
            connection,
            scoped,
            values["energy_source_id"],
            values["effective_from"],
            values.get("effective_to"),
        )
        if conflicts:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "같은 에너지원에 적용 기간이 겹치는 요금제가 있습니다.",
                {"reason": "PERIOD_OVERLAP", "conflicts": conflicts},
            )
        created = repo.insert_tariff(connection, scoped, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "tariff",
            created["id"],
            created,
            201,
        )
        return created


def update_tariff(
    context: AuthContext, tariff_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.tariff.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": tariff_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_tariff(connection, scoped, tariff_id)
        if current is None:
            raise _tariff_not_found()
        if "energy_source_id" in values and not repo.source_exists(
            connection, scoped, values["energy_source_id"]
        ):
            raise _invalid_energy_source()
        final_source_id = values.get("energy_source_id", current["energySourceId"])
        final_from = values.get("effective_from", current["effectiveFrom"])
        final_to = (
            values["effective_to"]
            if "effective_to" in values
            else current["effectiveTo"]
        )
        if final_to is not None and final_to < final_from:
            raise _invalid_effective_to()
        if "tariff_code" in values and repo.tariff_code_taken(
            connection, scoped, values["tariff_code"], tariff_id
        ):
            raise _duplicate_tariff_code()
        conflicts = repo.find_overlapping_tariffs(
            connection,
            scoped,
            final_source_id,
            final_from,
            final_to,
            exclude_tariff_id=tariff_id,
        )
        if conflicts:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "같은 에너지원에 적용 기간이 겹치는 요금제가 있습니다.",
                {"reason": "PERIOD_OVERLAP", "conflicts": conflicts},
            )
        updated = repo.update_tariff(connection, scoped, tariff_id, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "tariff",
            tariff_id,
            updated,
        )
        return updated


def delete_tariff(context: AuthContext, tariff_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.tariff.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": tariff_id})
        if cached is not None:
            return
        if repo.get_tariff(connection, scoped, tariff_id) is None:
            raise _tariff_not_found()
        repo.delete_tariff(connection, scoped, tariff_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "tariff",
            tariff_id,
            {},
            204,
        )


# ---- F-13 환산·배출계수 (FS-018k) ----
# 계수 단위는 유형과 에너지원 계측 단위로 서버가 정한다. 계산은 단위 끝(/kWh 등)이 채널 단위와 같을 때만 쓴다.
FACTOR_UNIT_PREFIX = {"PRIMARY": "TOE/", "EMISSION": "tCO2eq/"}


def _factor_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "계수를 찾을 수 없습니다.")


def _factor_field(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def _check_factor(
    connection: Connection,
    scoped: AuthContext,
    source_id: int,
    kind: str,
    year: str,
    value: str,
    exclude_id: int | None,
) -> None:
    if Decimal(value) <= 0:
        raise _factor_field("factorValue", "계수는 0보다 커야 합니다.")
    if repo.factor_taken(connection, scoped, source_id, kind, year, exclude_id):
        raise _factor_field(
            "effectiveYear", f"이 에너지원의 {year}년 계수가 이미 있습니다."
        )


def list_factors(
    context: AuthContext,
    factor_kind: str | None,
    energy_source_id: int | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_factors(
            connection, scoped, factor_kind, energy_source_id, offset, limit
        )


def get_factor(context: AuthContext, factor_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_factor(connection, scoped, factor_id)
    if found is None:
        raise _factor_not_found()
    return found


def create_factor(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_factor.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        source = repo.get_source(connection, scoped, values["energy_source_id"])
        if source is None:
            raise _invalid_energy_source()
        # 용수(UTILITY)는 TOE 합산·배출량 계산에서 빠진다. 계수를 두면 쓰이지 않는 값이 남는다.
        if source["sourceKind"] == "UTILITY":
            raise _factor_field(
                "energySourceId",
                "용수 등 UTILITY 에너지원은 환산·배출 계산 대상이 아닙니다.",
            )
        _check_factor(
            connection,
            scoped,
            source["id"],
            values["factor_kind"],
            values["effective_year"],
            values["factor_value"],
            None,
        )
        unit = FACTOR_UNIT_PREFIX[values["factor_kind"]] + source["measureUnit"]
        created = repo.insert_factor(
            connection, scoped, {**values, "factor_unit": unit}
        )
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_factor",
            created["id"],
            created,
            201,
        )
        return created


def update_factor(
    context: AuthContext, factor_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_factor.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": factor_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_factor(connection, scoped, factor_id)
        if current is None:
            raise _factor_not_found()
        _check_factor(
            connection,
            scoped,
            current["energySourceId"],
            current["factorKind"],
            values.get("effective_year", current["effectiveYear"]),
            values.get("factor_value", current["factorValue"]),
            factor_id,
        )
        updated = repo.update_factor(connection, scoped, factor_id, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_factor",
            factor_id,
            updated,
        )
        return updated


def delete_factor(context: AuthContext, factor_id: int, key: str) -> None:
    # 계수를 참조하는 테이블은 없다. 지우면 그 연도 계산이 "계수 없음"으로 바뀐다(추정으로 대체하지 않는다).
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.energy_factor.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": factor_id})
        if cached is not None:
            return
        if repo.get_factor(connection, scoped, factor_id) is None:
            raise _factor_not_found()
        repo.delete_factor(connection, scoped, factor_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "energy_factor",
            factor_id,
            {},
            204,
        )


# ---- F-02 계측 조회 (FS-018b) ----
MAX_READING_DAYS = 31
DEFAULT_READING_DAYS = 7


def _check_period(
    date_from: date | None, date_to: date | None, max_days: int = MAX_READING_DAYS
) -> None:
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
        if (date_to - date_from).days >= max_days:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "조회 기간이 너무 깁니다.",
                {"fields": {"to": f"최대 {max_days}일까지 조회합니다."}},
            )


def list_readings(
    context: AuthContext,
    filters: dict[str, Any],
    date_from: date | None,
    date_to: date | None,
    sort: str | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, dict[str, str] | None]:
    _check_period(date_from, date_to)
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


# ---- F-03 설비별 배분 (FS-018c) ----
def list_allocations(
    context: AuthContext,
    filters: dict[str, Any],
    date_from: date | None,
    date_to: date | None,
    include_superseded: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int, list[dict[str, Any]], dict[str, str] | None]:
    _check_period(date_from, date_to)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if date_to is None:
            date_to = repo.latest_allocation_date(connection, scoped)
            if date_to is None:
                return [], 0, [], None
            date_from = date_to - timedelta(days=DEFAULT_READING_DAYS - 1)
        rows, total = repo.list_allocations(
            connection,
            scoped,
            filters,
            date_from,
            date_to,
            include_superseded,
            offset,
            limit,
        )
        summary = repo.allocation_summary(
            connection, scoped, filters, date_from, date_to
        )
    return (
        rows,
        total,
        summary,
        {"from": date_from.isoformat(), "to": date_to.isoformat()},
    )


# ---- F-04 배출량 (FS-018d) ----
# 저장하지 않는 계산(FS-010 §7). 배출계수(EMISSION)만 쓴다. 1차에너지 환산계수(PRIMARY)와 섞지 않는다.
MAX_EMISSION_DAYS = 366
# 배출량 tCO2eq와 소비량 모두 소수 6자리로 낸다.
SIX = Decimal("0.000001")


def _converted_source(
    rows: list[dict[str, Any]],
    factors: dict[tuple[int, str], dict[str, Any]],
    kind: str,
    key: str,
) -> dict[str, Any]:
    """에너지원 1개의 소비량 × 연도별 계수. key는 결과 필드 이름(emission 또는 toe)."""
    head = rows[0]
    quantity = sum((r["quantity"] for r in rows), Decimal(0)).quantize(SIX)
    result: dict[str, Any] = {
        "energySourceId": head["source_id"],
        "sourceCode": head["source_code"],
        "name": head["name"],
        "sourceKind": head["source_kind"],
        "consumption": {"quantity": str(quantity), "unit": head["unit"]},
        "excludedReadings": sum(r["excluded"] for r in rows),
        key: None,
        "segments": [],
    }
    # 용수 같은 UTILITY는 대상 아님이다. 계수 누락(계산 불가)과 구별한다(FS-005g D-1).
    if head["source_kind"] == "UTILITY":
        result["status"] = "NOT_APPLICABLE"
        return result
    total = Decimal(0)
    status = "CALCULATED"
    for r in rows:
        factor = factors.get((head["source_id"], r["reading_year"]))
        segment: dict[str, Any] = {
            "year": r["reading_year"],
            "consumption": {
                "quantity": str(r["quantity"].quantize(SIX)),
                "unit": r["unit"],
            },
            "factor": None,
            key: None,
        }
        if factor is None:
            status = "FACTOR_MISSING"
        elif not factor["factor_unit"].endswith("/" + r["unit"]):
            status = "UNIT_MISMATCH"
            segment["factor"] = _factor(factor, r["reading_year"], kind)
        else:
            value = (r["quantity"] * factor["factor_value"]).quantize(SIX)
            segment["factor"] = _factor(factor, r["reading_year"], kind)
            segment[key] = str(value)
            total += value
        result["segments"].append(segment)
    result["status"] = status
    if status == "CALCULATED":
        result[key] = str(total)
    return result


def _converted(
    rows: list[dict[str, Any]],
    factors: dict[tuple[int, str], dict[str, Any]],
    kind: str,
    key: str,
) -> tuple[list[dict[str, Any]], str, bool]:
    """에너지원별 결과, 계산된 것만의 합계, 대상이 모두 계산됐는지."""
    groups: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for r in rows:
        groups.setdefault((r["source_id"], r["unit"]), []).append(r)
    sources = [_converted_source(g, factors, kind, key) for g in groups.values()]
    applicable = [s for s in sources if s["status"] != "NOT_APPLICABLE"]
    calculated = [s for s in applicable if s["status"] == "CALCULATED"]
    total = sum((Decimal(s[key]) for s in calculated), Decimal(0))
    return sources, str(total), len(calculated) == len(applicable)


def _factor(factor: dict[str, Any], year: str, kind: str) -> dict[str, str]:
    return {
        "kind": kind,
        "year": year,
        "value": str(factor["factor_value"]),
        "unit": factor["factor_unit"],
        "source": factor["source_note"],
    }


def emissions(
    context: AuthContext, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    _check_period(date_from, date_to, MAX_EMISSION_DAYS)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if date_to is None:
            # 기본은 가장 최근 계측일이 속한 달의 1일부터 그날까지(당월 누계).
            date_to = repo.latest_reading_date(connection, scoped)
            if date_to is None:
                return {
                    "period": None,
                    "sources": [],
                    "totalEmission": None,
                    "unit": "tCO2eq",
                    "complete": True,
                }
            date_from = date_to.replace(day=1)
        rows = repo.emission_consumption(connection, scoped, date_from, date_to)
        factors = repo.factors(connection, scoped, "EMISSION")
    # 계산된 에너지원만 합한다. 하나라도 계산 불가면 complete=false로 알린다.
    sources, total, complete = _converted(rows, factors, "EMISSION", "emission")
    return {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "sources": sources,
        "totalEmission": total,
        "unit": "tCO2eq",
        "complete": complete,
    }


# ---- F-01 대시보드 (FS-018f) ----
# 1차에너지(TOE)는 PRIMARY, 배출량은 EMISSION 계수로 따로 계산한다. 단위가 다른 에너지원은 TOE 환산 후에만 더한다.
WON = Decimal(1)


def _month_period(connection: Connection, scoped: AuthContext, month: str | None):
    latest = repo.latest_reading_date(connection, scoped)
    if month is None:
        if latest is None:
            return None
        month = latest.strftime("%Y-%m")
    first = date(int(month[:4]), int(month[5:]), 1)
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    last = next_month - timedelta(days=1)
    # 당월은 최근 계측일까지(누계). 계측이 없는 달은 달 전체를 기간으로 둔다.
    if latest is not None and first <= latest < last:
        last = latest
    return month, first, last


def _tariff_for(
    tariffs: list[dict[str, Any]], source_id: int, month: str
) -> dict[str, Any] | None:
    # 같은 에너지원의 기간 겹침은 F-14가 409로 막는다. 겹친 옛 데이터가 있으면 최신 시작월을 쓴다.
    for t in tariffs:
        if (
            t["energy_source_id"] == source_id
            and t["effective_from"] <= month
            and (t["effective_to"] is None or t["effective_to"] >= month)
        ):
            return t
    return None


def _billing(
    rows: list[dict[str, Any]], tariffs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str, bool]:
    """에너지원별로 월마다 그 달의 요금제를 적용한다. 요금제가 바뀌는 달에서 구간이 나뉜다.

    월 요금 = 기본요금 + 사용량 × 단가(원 단위 반올림). 시간대 가중치 없음(FS-008a F-08).
    """
    sources: dict[tuple[int, str], dict[str, Any]] = {}
    for r in rows:
        source = sources.setdefault(
            (r["source_id"], r["unit"]),
            {
                "energySourceId": r["source_id"],
                "sourceCode": r["source_code"],
                "name": r["name"],
                "unit": r["unit"],
                "status": "CALCULATED" if r["is_billable"] else "NOT_BILLABLE",
                "usage": Decimal(0),
                "total": Decimal(0),
                "segments": [],
            },
        )
        source["usage"] += r["quantity"]
        if not r["is_billable"]:
            continue
        tariff = _tariff_for(tariffs, r["source_id"], r["reading_month"])
        segment: dict[str, Any] = {
            "month": r["reading_month"],
            "usage": str(r["quantity"].quantize(SIX)),
            "tariff": None,
            "basicCharge": None,
            "usageCharge": None,
            "amount": None,
        }
        if tariff is None:
            source["status"] = "TARIFF_MISSING"
        else:
            usage_charge = (r["quantity"] * tariff["usage_rate"]).quantize(WON)
            basic = tariff["basic_charge"].quantize(WON)
            segment.update(
                tariff={
                    "tariffCode": tariff["tariff_code"],
                    "name": tariff["name"],
                    "basicCharge": str(tariff["basic_charge"]),
                    "usageRate": str(tariff["usage_rate"]),
                    "effectiveFrom": tariff["effective_from"],
                    "effectiveTo": tariff["effective_to"],
                },
                basicCharge=str(basic),
                usageCharge=str(usage_charge),
                amount=str(basic + usage_charge),
            )
            source["total"] += basic + usage_charge
        source["segments"].append(segment)
    result = []
    for source in sources.values():
        billable = source["status"] != "NOT_BILLABLE"
        source["usage"] = str(source["usage"].quantize(SIX))
        # 요금제가 빠진 달이 있으면 그 달을 뺀 부분 합계이며 status로 알린다.
        source["total"] = str(source["total"]) if billable else None
        result.append(source)
    billed = [s for s in result if s["status"] != "NOT_BILLABLE"]
    total = sum((Decimal(s["total"]) for s in billed), Decimal(0))
    return result, str(total), all(s["status"] == "CALCULATED" for s in billed)


MAX_BILLING_MONTHS = 12


def _months_between(first: str, last: str) -> int:
    return (int(last[:4]) - int(first[:4])) * 12 + int(last[5:]) - int(first[5:]) + 1


def billing(
    context: AuthContext, month_from: str | None, month_to: str | None
) -> dict[str, Any]:
    if (month_from is None) != (month_to is None):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "조회 기간은 시작월과 종료월을 함께 지정합니다.",
            {"fields": {"from" if month_from is None else "to": "필요합니다."}},
        )
    if month_from and month_to:
        span = _months_between(month_from, month_to)
        if span < 1:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "조회 기간이 올바르지 않습니다.",
                {"fields": {"to": "시작월 이후여야 합니다."}},
            )
        if span > MAX_BILLING_MONTHS:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "조회 기간이 너무 깁니다.",
                {"fields": {"to": f"최대 {MAX_BILLING_MONTHS}개월까지 조회합니다."}},
            )
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        latest = repo.latest_reading_date(connection, scoped)
        if month_to is None:
            if latest is None:
                return {
                    "period": None,
                    "sources": [],
                    "total": "0",
                    "currency": "KRW",
                    "complete": True,
                }
            # 기본은 전월 ~ 당월. 요금제 개정이 있으면 구간 분할이 바로 보인다.
            month_to = latest.strftime("%Y-%m")
            previous = latest.replace(day=1) - timedelta(days=1)
            month_from = previous.strftime("%Y-%m")
        _, first, _ = _month_period(connection, scoped, month_from)
        _, _, last = _month_period(connection, scoped, month_to)
        rows = repo.monthly_consumption(connection, scoped, first, last)
        tariffs = repo.billing_tariffs(connection, scoped)
    sources, total, complete = _billing(rows, tariffs)
    return {
        "period": {
            "from": month_from,
            "to": month_to,
            "dateFrom": first.isoformat(),
            "dateTo": last.isoformat(),
            # 마지막 달이 최근 계측일에서 끝나면 그 달은 당월 누계다.
            "monthToDate": latest is not None and last == latest,
        },
        "sources": sources,
        "total": total,
        "currency": "KRW",
        "complete": complete,
    }


def _daily_toe(
    rows: list[dict[str, Any]], factors: dict[tuple[int, str], dict[str, Any]]
) -> list[dict[str, str]]:
    daily: dict[str, Decimal] = {}
    for r in rows:
        daily.setdefault(r["reading_date"], Decimal(0))
        factor = factors.get((r["source_id"], r["reading_date"][:4]))
        if (
            r["source_kind"] == "UTILITY"
            or factor is None
            or not factor["factor_unit"].endswith("/" + r["unit"])
        ):
            continue
        daily[r["reading_date"]] += r["quantity"] * factor["factor_value"]
    return [{"date": d, "toe": str(v.quantize(SIX))} for d, v in sorted(daily.items())]


def dashboard(context: AuthContext, month: str | None) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        period = _month_period(connection, scoped, month)
        if period is None:
            return {"period": None}
        month, first, last = period
        rows = repo.emission_consumption(connection, scoped, first, last)
        primary = repo.factors(connection, scoped, "PRIMARY")
        emission = repo.factors(connection, scoped, "EMISSION")
        daily_rows = repo.daily_consumption(connection, scoped, first, last)
        target = repo.site_toe_target(connection, scoped, month)
        monthly = repo.monthly_consumption(connection, scoped, first, last)
        tariffs = repo.billing_tariffs(connection, scoped)
        summary = repo.allocation_summary(connection, scoped, {}, first, last)
        issues, recent = repo.quality_issues(connection, scoped, first, last)
    toe_sources, toe_total, toe_complete = _converted(rows, primary, "PRIMARY", "toe")
    _, emission_total, emission_complete = _converted(
        rows, emission, "EMISSION", "emission"
    )
    billed, charge_total, charge_complete = _billing(monthly, tariffs)
    # 대시보드는 한 달이라 구간이 하나다. 부과 대상만 요약한다.
    charges = [
        {
            "sourceCode": b["sourceCode"],
            "usage": {"quantity": b["usage"], "unit": b["unit"]},
            "tariffCode": (b["segments"][0]["tariff"] or {}).get("tariffCode")
            if b["segments"]
            else None,
            "amount": b["total"] if b["status"] == "CALCULATED" else None,
            "status": b["status"],
        }
        for b in billed
        if b["status"] != "NOT_BILLABLE"
    ]
    achievement = None
    if target:
        # 달성률 = 실적 ÷ 목표. 100% 이하면 목표 이내.
        achievement = str((Decimal(toe_total) / target * 100).quantize(Decimal("0.1")))
    return {
        "period": {"month": month, "from": first.isoformat(), "to": last.isoformat()},
        "primaryEnergy": {
            "total": toe_total,
            "unit": "TOE",
            "complete": toe_complete,
            "sources": toe_sources,
        },
        "target": {
            "status": "SET" if target else "UNSET",
            "target": str(target) if target else None,
            "actual": toe_total,
            "unit": "TOE",
            "achievementRate": achievement,
        },
        "charge": {
            "total": charge_total,
            "currency": "KRW",
            "complete": charge_complete,
            "sources": charges,
        },
        "emission": {
            "total": emission_total,
            "unit": "tCO2eq",
            "complete": emission_complete,
        },
        "daily": _daily_toe(daily_rows, primary),
        "topEquipment": [s for s in summary if s["unit"] == "kWh"][:5],
        "quality": {"issues": issues, "recent": recent},
    }


# ---- F-07 목표 대비 실적 (FS-018g) ----
# 범위(SITE·EQUIPMENT)가 다른 목표를 한 표에 합하지 않는다(FS-008a F-07). 목표 없으면 UNSET, 달성률 없음.
def _performance(target: Any, actual: Decimal | None) -> dict[str, Any]:
    if target is None:
        return {"target": None, "achievementRate": None, "status": "UNSET"}
    if actual is None:
        return {
            "target": str(target),
            "achievementRate": None,
            "status": "NOT_CALCULABLE",
        }
    rate = (actual / target * 100).quantize(Decimal("0.1")) if target else None
    return {
        "target": str(target),
        "achievementRate": str(rate) if rate is not None else None,
        "status": "WITHIN" if rate is not None and rate <= 100 else "EXCEEDED",
    }


def target_performance(context: AuthContext, month: str | None) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        period = _month_period(connection, scoped, month)
        if period is None:
            return {"period": None, "site": [], "equipment": []}
        month, first, last = period
        latest = repo.latest_reading_date(connection, scoped)
        rows = repo.emission_consumption(connection, scoped, first, last)
        primary = repo.factors(connection, scoped, "PRIMARY")
        targets = repo.targets_for_month(connection, scoped, month)
        sources = repo.active_sources(connection, scoped)
        summary = repo.allocation_summary(connection, scoped, {}, first, last)
    _, toe_total, toe_complete = _converted(rows, primary, "PRIMARY", "toe")
    consumption: dict[tuple[int, str], Decimal] = {}
    for r in rows:
        key = (r["source_id"], r["unit"])
        consumption[key] = consumption.get(key, Decimal(0)) + r["quantity"]
    site_targets = {
        t["energy_source_id"]: t for t in targets if t["target_scope"] == "SITE"
    }
    site = []
    for source in sources:
        target = site_targets.get(source["id"])
        unit = target["unit"] if target else source["measure_unit"]
        # 목표 단위와 실적 단위가 다르면 비교하지 않는다(단위 환산을 추측하지 않는다).
        actual = consumption.get((source["id"], unit))
        site.append(
            {
                "energySourceCode": source["source_code"],
                "name": source["name"],
                "unit": unit,
                "actual": str(actual.quantize(SIX)) if actual is not None else None,
                **_performance(target["target_value"] if target else None, actual),
            }
        )
    toe_target = site_targets.get(None)
    toe_actual = Decimal(toe_total) if toe_complete else None
    site.append(
        {
            "energySourceCode": None,
            "name": "사업장 전체 (1차에너지 환산)",
            "unit": "TOE",
            "actual": toe_total if toe_complete else None,
            **_performance(
                toe_target["target_value"] if toe_target else None, toe_actual
            ),
        }
    )
    equipment_targets = {
        (t["equipment_id"], t["unit"]): t
        for t in targets
        if t["target_scope"] == "EQUIPMENT"
    }
    target_units = {unit for _, unit in equipment_targets}
    equipment = []
    seen = set()
    for s in summary:
        key = (s["equipmentId"], s["unit"])
        if s["unit"] not in target_units:
            continue
        seen.add(key)
        target = equipment_targets.get(key)
        equipment.append(
            {
                "equipmentId": s["equipmentId"],
                "equipmentCode": s["equipmentCode"],
                "equipmentName": s["equipmentName"],
                "unit": s["unit"],
                "actual": s["quantity"],
                "estimatedDays": s["estimatedDays"],
                **_performance(
                    target["target_value"] if target else None, Decimal(s["quantity"])
                ),
            }
        )
    for key, target in equipment_targets.items():
        if key in seen:
            continue
        equipment.append(
            {
                "equipmentId": target["equipment_id"],
                "equipmentCode": target["equipment_code"],
                "equipmentName": target["equipment_name"],
                "unit": target["unit"],
                "actual": None,
                "estimatedDays": 0,
                **_performance(target["target_value"], None),
            }
        )
    equipment.sort(key=lambda e: e["equipmentCode"])
    return {
        "period": {
            "month": month,
            "from": first.isoformat(),
            "to": last.isoformat(),
            # 당월은 최근 계측일까지의 누계다. 목표도 같은 기준으로 만들어졌다(FS-005g 5.5).
            "monthToDate": latest is not None and first <= latest == last,
        },
        "site": site,
        "equipment": equipment,
    }


# ---- F-05 생산량 등록 (FS-018i) ----
# 확정은 불변, 정정은 같은 원천 키의 새 버전(초안)으로 한다(FS-005g, schema.json SERVICE/DB_POLICY).
MAX_PRODUCTION_DAYS = 366
REVISION_FIXED = ("equipment_id", "item_code", "unit")


def _production_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "생산량 기록을 찾을 수 없습니다.")


def _confirmed_locked() -> ApiError:
    return ApiError(
        409,
        "ALREADY_CONFIRMED",
        "확정된 생산량은 바꿀 수 없습니다. 정정은 새 버전으로 만드세요.",
    )


def _production_period(
    connection: Connection, scoped: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    """설비 사업장 시간대 기준 [시작일 00:00, 종료일+1 00:00)."""
    timezone = repo.site_timezone_of_equipment(
        connection, scoped, values["equipment_id"]
    )
    if timezone is None:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"equipmentId": "유효하지 않은 설비입니다."}},
        )
    start, end = values.pop("start_date"), values.pop("end_date")
    if end < start:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"endDate": "시작일 이후여야 합니다."}},
        )
    if (end - start).days >= MAX_PRODUCTION_DAYS:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"endDate": f"최대 {MAX_PRODUCTION_DAYS}일까지 입력합니다."}},
        )
    zone = ZoneInfo(timezone)
    values["period_start"] = datetime.combine(start, time(0), zone)
    values["period_end"] = datetime.combine(end + timedelta(days=1), time(0), zone)
    return values


def list_production(
    context: AuthContext,
    filters: dict[str, Any],
    include_history: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_production(
            connection, scoped, filters, include_history, offset, limit
        )


def get_production(context: AuthContext, record_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_production(connection, scoped, record_id)
    if found is None:
        raise _production_not_found()
    return found


def _receipt(connection, scoped, operation, key, digest, record_id, data, status=200):
    save_receipt(
        connection,
        scoped,
        operation,
        key,
        digest,
        "production_record",
        record_id,
        data,
        status,
    )


def create_production(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    body = {
        **values,
        "start_date": str(values["start_date"]),
        "end_date": str(values["end_date"]),
    }
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.production_record.create"
        digest, cached = _replay(connection, scoped, operation, key, body)
        if cached is not None:
            return cached
        values = _production_period(connection, scoped, dict(values))
        day = values["period_start"].strftime("%Y%m%d")
        values["source_key"] = repo.next_manual_source_key(connection, scoped, day)
        values["version_no"] = 1
        record_id = repo.insert_production(connection, scoped, values)
        created = repo.get_production(connection, scoped, record_id)
        _receipt(connection, scoped, operation, key, digest, record_id, created, 201)
        return created


def update_production(
    context: AuthContext, record_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    body = {"id": record_id, **{k: str(v) for k, v in values.items()}}
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.production_record.update"
        digest, cached = _replay(connection, scoped, operation, key, body)
        if cached is not None:
            return cached
        current = repo.get_production(connection, scoped, record_id, lock=True)
        if current is None:
            raise _production_not_found()
        if current["status"] == "confirmed":
            raise _confirmed_locked()
        fixed = {
            "equipment_id": current["equipmentId"],
            "item_code": current["itemCode"],
            "unit": current["unit"],
        }
        changed = [f for f in REVISION_FIXED if f in values and values[f] != fixed[f]]
        if current["versionNo"] > 1 and changed:
            # 개정은 같은 기록의 정정이다. 설비·품목·단위가 바뀌면 다른 기록이다.
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "정정 버전은 설비·품목·단위를 바꿀 수 없습니다. 새 기록으로 등록하세요.",
                {"reason": "REVISION_FIELDS_FIXED", "fields": changed},
            )
        merged = {
            **fixed,
            "start_date": date.fromisoformat(current["startDate"]),
            "end_date": date.fromisoformat(current["endDate"]),
            **values,
        }
        merged = _production_period(connection, scoped, merged)
        changes = {
            k: v for k, v in merged.items() if k in values or k.startswith("period_")
        }
        repo.update_production(connection, scoped, record_id, changes)
        updated = repo.get_production(connection, scoped, record_id)
        _receipt(connection, scoped, operation, key, digest, record_id, updated)
        return updated


def delete_production(context: AuthContext, record_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.production_record.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": record_id})
        if cached is not None:
            return
        current = repo.get_production(connection, scoped, record_id, lock=True)
        if current is None:
            raise _production_not_found()
        if current["status"] == "confirmed":
            raise _confirmed_locked()
        repo.delete_production(connection, scoped, record_id)
        _receipt(connection, scoped, operation, key, digest, record_id, {}, 204)


def confirm_production(
    context: AuthContext, record_id: int, key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.production_record.confirm"
        digest, cached = _replay(connection, scoped, operation, key, {"id": record_id})
        if cached is not None:
            return cached
        current = repo.get_production(connection, scoped, record_id, lock=True)
        if current is None:
            raise _production_not_found()
        if current["status"] == "confirmed":
            raise _confirmed_locked()
        # 최신 확정 기록끼리 같은 설비·품목·단위의 구간 중복을 거부한다(생산량 이중 합산 방지).
        conflicts = repo.overlapping_production(connection, scoped, current)
        if conflicts:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "같은 설비·품목의 확정 생산량과 기간이 겹칩니다.",
                {
                    "reason": "PERIOD_OVERLAP",
                    "conflicts": [
                        {
                            "id": c["id"],
                            "sourceKey": c["sourceKey"],
                            "startDate": c["startDate"],
                            "endDate": c["endDate"],
                        }
                        for c in conflicts
                    ],
                },
            )
        repo.confirm_production(connection, scoped, record_id)
        confirmed = repo.get_production(connection, scoped, record_id)
        _receipt(connection, scoped, operation, key, digest, record_id, confirmed)
        return confirmed


def revise_production(context: AuthContext, record_id: int, key: str) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.production_record.revise"
        digest, cached = _replay(connection, scoped, operation, key, {"id": record_id})
        if cached is not None:
            return cached
        current = repo.get_production(connection, scoped, record_id, lock=True)
        if current is None:
            raise _production_not_found()
        versions = repo.source_versions(connection, scoped, current["sourceKey"])
        if current["status"] != "confirmed" or not current["isLatest"]:
            reason = (
                "DRAFT_EXISTS"
                if any(v["status"] == "draft" for v in versions)
                else "NOT_LATEST"
            )
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "정정은 원천 키의 최신 확정 버전에서만 만들 수 있습니다.",
                {"reason": reason},
            )
        values = {
            "source_key": current["sourceKey"],
            "version_no": max(v["version_no"] for v in versions) + 1,
            "equipment_id": current["equipmentId"],
            "item_code": current["itemCode"],
            "period_start": current["periodStart"],
            "period_end": current["periodEnd"],
            "production_qty": current["productionQty"],
            "unit": current["unit"],
        }
        new_id = repo.insert_production(connection, scoped, values)
        created = repo.get_production(connection, scoped, new_id)
        _receipt(connection, scoped, operation, key, digest, new_id, created, 201)
        return created


# ---- F-06 원단위 분석 (FS-018j) ----
# 원단위 = 생산 구간에 포함된 설비 일별 배분(현재 결과, invalid 제외)의 합 ÷ 생산량(FS-005g 5.6).
# 부분 구간을 비례 추정하지 않는다. 에너지원이 다르면 단위별로 따로 내고, 합계는 PRIMARY 환산(TOE)만.
MAX_INTENSITY_DAYS = 92
DEFAULT_INTENSITY_DAYS = 31
FINAL_PROCESS = "INS"  # 품목 원단위 분모 = 최종 공정(검사) 양품(FS-005g 5.5 D-2)


def _lot_of(source_key: str) -> str | None:
    # 원천 키 규칙 MES:<LOT>:<공정>(FS-005g 5.6). 직접 입력(MAN-)은 LOT 정보가 없다.
    parts = source_key.split(":")
    return parts[1] if len(parts) == 3 and parts[0] == "MES" else None


def _record_energy(
    record: dict[str, Any],
    allocations: list[dict[str, Any]],
    factors: dict[tuple[int, str], dict[str, Any]],
) -> tuple[dict[str, Decimal], Decimal | None]:
    """기록 구간 안에 완전히 들어가는 배분만 단위별로 합하고 TOE로도 환산한다."""
    start = datetime.fromisoformat(record["periodStart"])
    end = datetime.fromisoformat(record["periodEnd"])
    energy: dict[str, Decimal] = {}
    toe: Decimal | None = Decimal(0)
    for a in allocations:
        if (
            a["equipment_id"] != record["equipmentId"]
            or a["period_start"] < start
            or a["period_end"] > end
        ):
            continue
        energy[a["unit"]] = energy.get(a["unit"], Decimal(0)) + a["quantity"]
        if a["source_code"] == "WATER" or toe is None:
            continue
        year = (
            (a["period_end"] - timedelta(microseconds=1))
            .astimezone(ZoneInfo(a["timezone"]))
            .strftime("%Y")
        )
        factor = factors.get((a["energy_source_id"], year))
        if factor is None or not factor["factor_unit"].endswith("/" + a["unit"]):
            toe = None  # 계수가 없으면 환산 합계를 내지 않는다(부분 합을 전체처럼 보이지 않게).
        else:
            toe += a["quantity"] * factor["factor_value"]
    return energy, toe


def _per_unit(value: Decimal, qty: Decimal) -> str:
    return str((value / qty).quantize(SIX))


def intensity(
    context: AuthContext, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    _check_period(date_from, date_to, MAX_INTENSITY_DAYS)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if date_to is None:
            date_to = repo.latest_reading_date(connection, scoped)
            if date_to is None:
                return {"period": None, "records": [], "items": []}
            date_from = date_to - timedelta(days=DEFAULT_INTENSITY_DAYS - 1)
        production = repo.effective_production(connection, scoped)
        allocations = repo.current_allocations(connection, scoped, date_from, date_to)
        factors = repo.factors(connection, scoped, "PRIMARY")
        baselines = repo.item_baselines(connection, scoped)
    first, last = date_from.isoformat(), date_to.isoformat()
    inside = [p for p in production if p["startDate"] >= first and p["endDate"] <= last]
    records = []
    energy_of: dict[int, dict[str, Decimal]] = {}
    for p in sorted(inside, key=lambda r: (r["startDate"], r["sourceKey"])):
        energy, toe = _record_energy(p, allocations, factors)
        energy_of[p["id"]] = energy
        qty = Decimal(p["productionQty"])
        status = (
            "NO_PRODUCTION" if qty == 0 else "NO_ENERGY" if not energy else "CALCULATED"
        )
        records.append(
            {
                "id": p["id"],
                "sourceKey": p["sourceKey"],
                "versionNo": p["versionNo"],
                "equipmentCode": p["equipmentCode"],
                "equipmentName": p["equipmentName"],
                "itemCode": p["itemCode"],
                "startDate": p["startDate"],
                "endDate": p["endDate"],
                "productionQty": p["productionQty"],
                "unit": p["unit"],
                "energy": [
                    {"quantity": str(v.quantize(SIX)), "unit": u}
                    for u, v in sorted(energy.items())
                ],
                "intensity": [
                    {"value": _per_unit(v, qty), "unit": f"{u}/{p['unit']}"}
                    for u, v in sorted(energy.items())
                ]
                if status == "CALCULATED"
                else [],
                "toePerUnit": _per_unit(toe, qty)
                if status == "CALCULATED" and toe is not None
                else None,
                "status": status,
            }
        )
    # 품목 원단위: 모든 공정 기록이 기간 안에 있고 검사까지 끝난 LOT만 묶는다.
    lots: dict[str, list[dict[str, Any]]] = {}
    for p in production:
        lot = _lot_of(p["sourceKey"])
        if lot:
            lots.setdefault(lot, []).append(p)
    inside_ids = {p["id"] for p in inside}
    items: dict[str, dict[str, Any]] = {}
    for lot, lot_records in sorted(lots.items()):
        finals = [r for r in lot_records if r["equipmentType"] == FINAL_PROCESS]
        if not finals or any(r["id"] not in inside_ids for r in lot_records):
            continue
        item = items.setdefault(
            lot_records[0]["itemCode"],
            {
                "lots": [],
                "energy": Decimal(0),
                "output": Decimal(0),
                "unit": finals[0]["unit"],
            },
        )
        item["lots"].append(lot)
        item["energy"] += sum(
            energy_of[r["id"]].get("kWh", Decimal(0)) for r in lot_records
        )
        item["output"] += sum(Decimal(r["productionQty"]) for r in finals)
    item_rows = []
    for code, item in sorted(items.items()):
        value = item["energy"] / item["output"] if item["output"] else None
        base = baselines.get(code)
        comparable = (
            base is not None
            and base["source_code"] == "ELEC"
            and base["unit"] == f"kWh/{item['unit']}"
        )
        item_rows.append(
            {
                "itemCode": code,
                "lots": item["lots"],
                "energy": {
                    "quantity": str(item["energy"].quantize(SIX)),
                    "unit": "kWh",
                },
                "output": {"quantity": str(item["output"]), "unit": item["unit"]},
                "intensity": str(value.quantize(SIX)) if value is not None else None,
                "intensityUnit": f"kWh/{item['unit']}",
                "status": "CALCULATED" if value is not None else "NO_PRODUCTION",
                "baseline": {
                    "code": base["baseline_code"],
                    "value": str(base["baseline_value"]),
                    "unit": base["unit"],
                    "periodFrom": base["period_from"],
                    "periodTo": base["period_to"],
                }
                if comparable
                else None,
                "changeRate": str(
                    (
                        (value - base["baseline_value"]) / base["baseline_value"] * 100
                    ).quantize(Decimal("0.1"))
                    + 0  # -0.0을 0.0으로
                )
                if comparable and value is not None
                else None,
            }
        )
    return {
        "period": {"from": first, "to": last},
        "records": records,
        "items": item_rows,
    }
