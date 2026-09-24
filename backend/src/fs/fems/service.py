"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
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


def _charges(
    rows: list[dict[str, Any]],
    tariffs: dict[int, dict[str, Any]],
    billable: set[int],
) -> tuple[list[dict[str, Any]], str, bool]:
    usage: dict[int, dict[str, Any]] = {}
    for r in rows:
        entry = usage.setdefault(
            r["source_id"],
            {"code": r["source_code"], "unit": r["unit"], "quantity": Decimal(0)},
        )
        entry["quantity"] += r["quantity"]
    charges = []
    for source_id, entry in usage.items():
        if source_id not in billable:
            continue
        tariff = tariffs.get(source_id)
        item: dict[str, Any] = {
            "sourceCode": entry["code"],
            "usage": {
                "quantity": str(entry["quantity"].quantize(SIX)),
                "unit": entry["unit"],
            },
            "tariffCode": tariff["tariff_code"] if tariff else None,
            "amount": None,
            "status": "TARIFF_MISSING",
        }
        if tariff:
            # 기본요금 + 사용량 × 단가. 시간대 가중치 없음(FS-008a F-08).
            amount = tariff["basic_charge"] + entry["quantity"] * tariff["usage_rate"]
            item["amount"] = str(amount.quantize(WON))
            item["status"] = "CALCULATED"
        charges.append(item)
    total = sum((Decimal(c["amount"]) for c in charges if c["amount"]), Decimal(0))
    return charges, str(total), all(c["amount"] for c in charges)


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
        tariffs = repo.tariffs_for_month(connection, scoped, month)
        billable = repo.billable_sources(connection, scoped)
        summary = repo.allocation_summary(connection, scoped, {}, first, last)
        issues, recent = repo.quality_issues(connection, scoped, first, last)
    toe_sources, toe_total, toe_complete = _converted(rows, primary, "PRIMARY", "toe")
    _, emission_total, emission_complete = _converted(
        rows, emission, "EMISSION", "emission"
    )
    charges, charge_total, charge_complete = _charges(rows, tariffs, billable)
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
