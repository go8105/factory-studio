"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import Connection

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.db import get_engine
from fs.common.engine import read
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.fems import repository as repo
from fs.fems import tou

MODULE = "fems"


SOURCE = master.Master(
    module=MODULE,
    table="fems.energy_source",
    columns=(
        "source_code",
        "name",
        "source_kind",
        "measure_unit",
        "is_billable",
        "is_active",
    ),
    sort={"sourceCode": "source_code", "name": "name", "createdAt": "created_at"},
    default_sort="source_code ASC",
    unique=("source_code",),
    filters={"active": "is_active"},
    # energy_source를 참조하는 테이블 (schema.json FK r99·r101·r103·r107·r110)
    references=(
        master.Reference("fems.meter_channel", "energy_source_id", "계측 채널"),
        master.Reference("fems.energy_factor", "energy_source_id", "환산·배출계수"),
        master.Reference("fems.tariff", "energy_source_id", "요금제"),
        master.Reference("fems.energy_target", "energy_source_id", "에너지 목표"),
        master.Reference("fems.energy_baseline", "energy_source_id", "기준선"),
    ),
    not_found="에너지원을 찾을 수 없습니다.",
    duplicate_field="sourceCode",
    duplicate_message="이미 사용 중인 코드입니다.",
    referenced_message=(
        "다른 기준정보가 참조 중이라 삭제할 수 없습니다. "
        "사용 안 함으로 바꾸면 새 입력에서 제외됩니다."
    ),
)


def _source(
    connection: Connection, scoped: AuthContext, source_id: int
) -> dict[str, Any] | None:
    """다른 기준정보가 에너지원을 고를 때 쓴다."""
    row = master.fetch(connection, SOURCE, scoped, source_id)
    return master.present(row) if row else None


def _unit_in_use(
    connection: Connection,
    scoped: AuthContext,
    merged: dict[str, Any],
    current: dict[str, Any] | None,
    row_id: int | None,
) -> None:
    # 계측값·계수·요금 단가는 계측 단위를 전제로 저장돼 있다. 단위를 바꾸면 하위 계산이 조용히 틀린다.
    if current is None or merged["measure_unit"] == current["measure_unit"]:
        return
    references = master.references(connection, SOURCE, scoped, row_id)
    if references:
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            "참조 중인 에너지원은 계측 단위를 바꿀 수 없습니다. 새 에너지원을 등록하세요.",
            {"reason": "UNIT_IN_USE", "references": references},
        )


# 공통 엔진: 조회 트랜잭션(REPEATABLE READ · 읽기 전용)
_read = read


def list_sources(
    context: AuthContext, active: bool | None, sort: str | None, offset: int, limit: int
) -> tuple[list[dict[str, Any]], int]:
    return master.listing(
        SOURCE,
        context,
        filters={"active": active},
        sort=sort,
        offset=offset,
        limit=limit,
    )


def get_source(context: AuthContext, source_id: int) -> dict[str, Any]:
    return master.detail(SOURCE, context, source_id)


def _replay(
    connection: Connection, scoped: AuthContext, operation: str, key: str, body: Any
) -> tuple[str, dict[str, Any] | None]:
    digest = request_digest(body)
    return digest, find_receipt(connection, scoped, operation, key, digest)


def _run_once(
    context: AuthContext,
    operation: str,
    key: str,
    body: Any,
    run: Any,
    status: int = 200,
    entity: str = "reading",
) -> dict[str, Any]:
    """멱등 쓰기 한 번. 같은 키로 다시 부르면 저장해 둔 결과를 그대로 돌려준다."""
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        digest, cached = _replay(connection, scoped, operation, key, body)
        if cached is not None:
            return cached
        result = run(connection, scoped)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            entity,
            result.get("id"),
            result,
            status,
        )
        return result


def create_source(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    return master.create(SOURCE, context, values, key)


def update_source(
    context: AuthContext, source_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    return master.update(SOURCE, context, source_id, values, key, check=_unit_in_use)


def delete_source(context: AuthContext, source_id: int, key: str) -> None:
    master.delete(SOURCE, context, source_id, key)


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
        bands = repo.tariff_bands(connection, scoped, [tariff_id])[tariff_id]
    # 단일요금제는 구간이 없다. 빈 목록이 곧 그 사실이다.
    return {**found, "bands": [_band_dict(b) for b in bands]}


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


def replace_tariff_bands(
    context: AuthContext, tariff_id: int, bands: list[dict[str, Any]], key: str
) -> dict[str, Any]:
    """TOU 구간표를 통째로 바꾼다(F05·Q1).

    저장 전에 **계절·요일마다 0~24시를 빈틈·겹침 없이 덮는지** 본다. DB CHECK는 구간 하나의
    모양까지만 보고, 구간 사이의 빈틈은 여러 행을 함께 봐야 알 수 있다.
    """
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.tariff.bands"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": tariff_id, "bands": bands}
        )
        if cached is not None:
            return cached
        current = repo.get_tariff(connection, scoped, tariff_id)
        if current is None:
            raise _tariff_not_found()
        if current["tariffKind"] != "TOU":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "단일요금제에는 시간대 구간을 둘 수 없습니다. 요금제 종류를 TOU로 바꾸세요.",
                {"reason": "NOT_TOU"},
            )
        errors = tou.coverage_errors(bands)
        if errors:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "시간대 구간이 하루를 덮지 못합니다.",
                {"fields": {"bands": " ".join(errors)}},
            )
        rows = repo.replace_tariff_bands(connection, scoped, tariff_id, bands)
        result = {"tariffId": tariff_id, "bands": [_band_dict(r) for r in rows]}
        save_receipt(
            connection, scoped, operation, key, digest, "tariff", tariff_id, result, 200
        )
        return result


def _band_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "season": row["season"],
        "dayKind": row["day_kind"],
        "hourFrom": row["hour_from"],
        "hourTo": row["hour_to"],
        "loadBand": row["load_band"],
        "rate": str(row["rate"]),
    }


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
        source = _source(connection, scoped, values["energy_source_id"])
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


# ---- F-09 사업장·공간 (FS-018m) ----
def _site_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "사업장을 찾을 수 없습니다.")


def _location_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "공간을 찾을 수 없습니다.")


def _check_site(
    connection: Connection,
    scoped: AuthContext,
    values: dict[str, Any],
    site_id: int | None,
) -> None:
    if "timezone" in values and values["timezone"] not in available_timezones():
        raise _field("timezone", "IANA 시간대 이름이어야 합니다(예: Asia/Seoul).")
    if "site_code" in values and repo.site_code_taken(
        connection, scoped, values["site_code"], site_id
    ):
        raise _field("siteCode", "이미 사용 중인 코드입니다.")


def create_site(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.site.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        _check_site(connection, scoped, values, None)
        created = repo.insert_site(connection, scoped, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "site",
            created["id"],
            created,
            201,
        )
        return created


def update_site(
    context: AuthContext, site_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.site.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": site_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_site(connection, scoped, site_id)
        if current is None:
            raise _site_not_found()
        _check_site(connection, scoped, values, site_id)
        # 계측값·배분·생산량의 날짜 경계는 사업장 시간대로 정한다. 기록이 있는데 바꾸면 지난 일별 합계가 조용히 달라진다.
        if values.get("timezone", current["timezone"]) != current["timezone"]:
            references = repo.site_time_usage(connection, scoped, site_id)
            if references:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "기록이 있는 사업장은 시간대를 바꿀 수 없습니다. 날짜 경계가 달라져 지난 합계가 바뀝니다.",
                    {"reason": "TIMEZONE_IN_USE", "references": references},
                )
        updated = repo.update_site(connection, scoped, site_id, values)
        save_receipt(
            connection, scoped, operation, key, digest, "site", site_id, updated
        )
        return updated


def delete_site(context: AuthContext, site_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.site.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": site_id})
        if cached is not None:
            return
        if repo.get_site(connection, scoped, site_id) is None:
            raise _site_not_found()
        references = repo.site_references(connection, scoped, site_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "공간·계측기·목표가 있는 사업장은 삭제할 수 없습니다.",
                {"references": references},
            )
        repo.delete_site(connection, scoped, site_id)
        save_receipt(
            connection, scoped, operation, key, digest, "site", site_id, {}, 204
        )


def _check_location(
    connection: Connection,
    scoped: AuthContext,
    site_id: int,
    values: dict[str, Any],
    location_id: int | None,
) -> None:
    parent_id = values.get("parent_location_id")
    if parent_id is not None:
        parent = repo.get_location(connection, scoped, parent_id)
        if parent is None or parent["siteId"] != site_id:
            raise _field(
                "parentLocationId", "같은 사업장의 공간만 상위로 지정할 수 있습니다."
            )
        if location_id is not None and location_id in repo.location_ancestors(
            connection, scoped, parent_id
        ):
            raise _field(
                "parentLocationId",
                "자기 자신이나 하위 공간을 상위로 지정할 수 없습니다.",
            )
    if "location_code" in values and repo.location_code_taken(
        connection, scoped, site_id, values["location_code"], location_id
    ):
        raise _field("locationCode", "이 사업장에 이미 있는 공간 코드입니다.")


def create_location(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.location.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        if repo.get_site(connection, scoped, values["site_id"]) is None:
            raise _field("siteId", "유효하지 않은 사업장입니다.")
        _check_location(connection, scoped, values["site_id"], values, None)
        created = repo.insert_location(connection, scoped, values)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "location",
            created["id"],
            created,
            201,
        )
        return created


def update_location(
    context: AuthContext, location_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.location.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": location_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_location(connection, scoped, location_id)
        if current is None:
            raise _location_not_found()
        _check_location(connection, scoped, current["siteId"], values, location_id)
        updated = repo.update_location(connection, scoped, location_id, values)
        save_receipt(
            connection, scoped, operation, key, digest, "location", location_id, updated
        )
        return updated


def delete_location(context: AuthContext, location_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.location.delete"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": location_id}
        )
        if cached is not None:
            return
        if repo.get_location(connection, scoped, location_id) is None:
            raise _location_not_found()
        references = repo.location_references(connection, scoped, location_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "하위 공간·설비·계측기가 있는 공간은 삭제할 수 없습니다.",
                {"references": references},
            )
        repo.delete_location(connection, scoped, location_id)
        save_receipt(
            connection, scoped, operation, key, digest, "location", location_id, {}, 204
        )


# ---- F-12 계측기·채널 (FS-018l) ----
# 계측값·배분이 쌓인 뒤 소유(공간·설비·부모)나 채널 단위를 바꾸면 지난 합계가 조용히 달라진다.
METER_LOCKED = ("location_id", "equipment_id", "parent_meter_id")
CHANNEL_LOCKED = ("energy_source_id", "measurement_kind", "unit")
METER_KEYS = {
    "location_id": "locationId",
    "equipment_id": "equipmentId",
    "parent_meter_id": "parentMeterId",
}
CHANNEL_KEYS = {
    "energy_source_id": "energySourceId",
    "measurement_kind": "measurementKind",
    "unit": "unit",
    "channel_code": "channelCode",
    "multiplier": "multiplier",
}


def _field(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def _meter_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "계측기를 찾을 수 없습니다.")


def _channel_not_found() -> ApiError:
    return ApiError(404, "NOT_FOUND", "채널을 찾을 수 없습니다.")


def _check_meter(
    connection: Connection,
    scoped: AuthContext,
    final: dict[str, Any],
    meter_id: int | None,
) -> int:
    """최종 값 검증. 계측기의 사업장(공간의 사업장)을 돌려준다."""
    site_id = repo.location_site(connection, scoped, final["location_id"])
    if site_id is None:
        raise _field("locationId", "유효하지 않은 공간입니다.")
    if final["equipment_id"] is not None:
        equipment = repo.get_equipment(connection, scoped, final["equipment_id"])
        if equipment is None or equipment["locationId"] != final["location_id"]:
            raise _field(
                "equipmentId", "계측기와 같은 공간의 설비만 연결할 수 있습니다."
            )
    if final["parent_meter_id"] is not None:
        parent = repo.get_meter(connection, scoped, final["parent_meter_id"])
        if parent is None or parent["siteId"] != site_id:
            raise _field(
                "parentMeterId", "같은 사업장의 계측기만 부모로 지정할 수 있습니다."
            )
        if meter_id is not None and meter_id in repo.meter_ancestors(
            connection, scoped, final["parent_meter_id"]
        ):
            raise _field(
                "parentMeterId",
                "자기 자신이나 하위 계측기를 부모로 지정할 수 없습니다.",
            )
    if repo.meter_code_taken(connection, scoped, final["meter_code"], meter_id):
        raise _field("meterCode", "이미 사용 중인 코드입니다.")
    return site_id


def get_meter(context: AuthContext, meter_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_meter(connection, scoped, meter_id)
    if found is None:
        raise _meter_not_found()
    return found


def create_meter(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter.create"
        digest, cached = _replay(connection, scoped, operation, key, values)
        if cached is not None:
            return cached
        site_id = _check_meter(connection, scoped, values, None)
        meter_id = repo.insert_meter(connection, scoped, {**values, "site_id": site_id})
        created = repo.get_meter(connection, scoped, meter_id)
        save_receipt(
            connection, scoped, operation, key, digest, "meter", meter_id, created, 201
        )
        return created


def update_meter(
    context: AuthContext, meter_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter.update"
        digest, cached = _replay(
            connection, scoped, operation, key, {"id": meter_id, **values}
        )
        if cached is not None:
            return cached
        current = repo.get_meter(connection, scoped, meter_id)
        if current is None:
            raise _meter_not_found()
        final = {
            "meter_code": values.get("meter_code", current["meterCode"]),
            **{
                column: values[column] if column in values else current[api]
                for column, api in METER_KEYS.items()
            },
        }
        changed = [c for c in METER_LOCKED if final[c] != current[METER_KEYS[c]]]
        if changed:
            references = repo.channel_usage(connection, scoped, meter_id=meter_id)
            if references:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "계측값이 있는 계측기는 공간·설비·부모 계측기를 바꿀 수 없습니다. 새 계측기를 등록하세요.",
                    {
                        "reason": "METER_IN_USE",
                        "fields": [METER_KEYS[c] for c in changed],
                        "references": references,
                    },
                )
        site_id = _check_meter(connection, scoped, final, meter_id)
        repo.update_meter(connection, scoped, meter_id, {**values, "site_id": site_id})
        updated = repo.get_meter(connection, scoped, meter_id)
        save_receipt(
            connection, scoped, operation, key, digest, "meter", meter_id, updated
        )
        return updated


def delete_meter(context: AuthContext, meter_id: int, key: str) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter.delete"
        digest, cached = _replay(connection, scoped, operation, key, {"id": meter_id})
        if cached is not None:
            return
        if repo.get_meter(connection, scoped, meter_id) is None:
            raise _meter_not_found()
        references = repo.meter_references(connection, scoped, meter_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "하위 계측기나 채널이 있어 삭제할 수 없습니다. 먼저 정리하세요.",
                {"references": references},
            )
        repo.delete_meter(connection, scoped, meter_id)
        save_receipt(
            connection, scoped, operation, key, digest, "meter", meter_id, {}, 204
        )


def _check_channel(
    connection: Connection,
    scoped: AuthContext,
    meter_id: int,
    final: dict[str, Any],
    channel_id: int | None,
) -> None:
    source = _source(connection, scoped, final["energy_source_id"])
    if source is None:
        raise _invalid_energy_source()
    # 기간 합계·환산·요금은 누적 채널 값을 에너지원 계측 단위로 본다. 순시(kW 등)만 단위가 달라도 된다.
    if (
        final["measurement_kind"] == "CUMULATIVE"
        and final["unit"] != source["measureUnit"]
    ):
        raise _field(
            "unit",
            f"누적 채널 단위는 에너지원 계측 단위({source['measureUnit']})와 같아야 합니다.",
        )
    if Decimal(final["multiplier"]) <= 0:
        raise _field("multiplier", "계기 배수는 0보다 커야 합니다.")
    if repo.channel_code_taken(
        connection, scoped, meter_id, final["channel_code"], channel_id
    ):
        raise _field("channelCode", "이 계측기에 이미 있는 채널 코드입니다.")


def create_channel(
    context: AuthContext, meter_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter_channel.create"
        digest, cached = _replay(
            connection, scoped, operation, key, {"meterId": meter_id, **values}
        )
        if cached is not None:
            return cached
        if repo.get_meter(connection, scoped, meter_id) is None:
            raise _meter_not_found()
        _check_channel(connection, scoped, meter_id, values, None)
        channel_id = repo.insert_channel(
            connection, scoped, {**values, "meter_id": meter_id}
        )
        created = repo.get_channel(connection, scoped, meter_id, channel_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "meter_channel",
            channel_id,
            created,
            201,
        )
        return created


def update_channel(
    context: AuthContext,
    meter_id: int,
    channel_id: int,
    values: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter_channel.update"
        digest, cached = _replay(
            connection,
            scoped,
            operation,
            key,
            {"meterId": meter_id, "id": channel_id, **values},
        )
        if cached is not None:
            return cached
        current = repo.get_channel(connection, scoped, meter_id, channel_id)
        if current is None:
            raise _channel_not_found()
        final = {
            column: values.get(column, current[api])
            for column, api in CHANNEL_KEYS.items()
        }
        changed = [c for c in CHANNEL_LOCKED if final[c] != current[CHANNEL_KEYS[c]]]
        if changed and current["observed"]:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "계측값이나 배분 결과가 있는 채널은 에너지원·측정 종류·단위를 바꿀 수 없습니다. 새 채널을 등록하세요.",
                {
                    "reason": "CHANNEL_IN_USE",
                    "fields": [CHANNEL_KEYS[c] for c in changed],
                    "references": repo.channel_usage(
                        connection, scoped, channel_id=channel_id
                    ),
                },
            )
        _check_channel(connection, scoped, meter_id, final, channel_id)
        repo.update_channel(connection, scoped, channel_id, values)
        updated = repo.get_channel(connection, scoped, meter_id, channel_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "meter_channel",
            channel_id,
            updated,
        )
        return updated


def delete_channel(
    context: AuthContext, meter_id: int, channel_id: int, key: str
) -> None:
    with get_engine().begin() as connection:
        scoped = write_scope(connection, context, MODULE)
        operation = "fems.meter_channel.delete"
        digest, cached = _replay(
            connection, scoped, operation, key, {"meterId": meter_id, "id": channel_id}
        )
        if cached is not None:
            return
        if repo.get_channel(connection, scoped, meter_id, channel_id) is None:
            raise _channel_not_found()
        references = repo.channel_usage(connection, scoped, channel_id=channel_id)
        if references:
            raise ApiError(
                409,
                "REFERENCED_BY_OTHERS",
                "계측값이나 배분 결과가 있는 채널은 삭제할 수 없습니다. 사용 안 함으로 바꾸세요.",
                {"references": references},
            )
        repo.delete_channel(connection, scoped, channel_id)
        save_receipt(
            connection,
            scoped,
            operation,
            key,
            digest,
            "meter_channel",
            channel_id,
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


def _tou_charge(
    hourly: list[dict[str, Any]],
    bands: list[dict[str, Any]],
    holiday_days: set[date],
) -> tuple[Decimal, dict[str, dict[str, Decimal]]]:
    """시간 사용량마다 그 시각의 요율을 곱해 더한다(Q1). 부하 구분별 소계도 함께 낸다.

    구간표에 없는 시각은 **버리지 않고 요율 0으로 센다** — 사용량이 사라지면 합계가 조용히
    틀린다. 구간 완전성은 요금제를 저장할 때 막으므로 여기까지 오는 일은 없어야 한다.
    """
    table = tou.rate_lookup(bands)
    charge = Decimal(0)
    by_band: dict[str, dict[str, Decimal]] = {
        band: {"usage": Decimal(0), "charge": Decimal(0)} for band in tou.LOAD_BANDS
    }
    for row in hourly:
        day = row["reading_date"]
        key = (
            tou.season_of(day.month),
            tou.day_kind_of(day, holiday_days),
            row["hour"],
        )
        band = table.get(key)
        rate = band["rate"] if band else Decimal(0)
        amount = row["quantity"] * rate
        charge += amount
        bucket = by_band[band["load_band"]] if band else None
        if bucket is not None:
            bucket["usage"] += row["quantity"]
            bucket["charge"] += amount
    return charge, by_band


def _billing(
    rows: list[dict[str, Any]],
    tariffs: list[dict[str, Any]],
    bands: dict[int, list[dict[str, Any]]] | None = None,
    hourly: list[dict[str, Any]] | None = None,
    holiday_days: set[date] | None = None,
) -> tuple[list[dict[str, Any]], str, bool]:
    """에너지원별로 월마다 그 달의 요금제를 적용한다. 요금제가 바뀌는 달에서 구간이 나뉜다.

    FLAT: 기본요금 + 사용량 × 단가. TOU: **계약전력 × 기본요금 단가** + Σ(시간 사용량 × 그
    시각의 요율)(Q1). 둘 다 원 단위 반올림이다.
    """
    bands = bands or {}
    holiday_days = holiday_days or set()
    by_month: dict[tuple[int, str], list[dict[str, Any]]] = {}
    for row in hourly or []:
        by_month.setdefault(
            (row["source_id"], row["reading_date"].strftime("%Y-%m")), []
        ).append(row)
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
            is_tou = tariff.get("tariff_kind") == "TOU"
            band_rows = bands.get(tariff.get("id"), [])
            if is_tou:
                hours = by_month.get((r["source_id"], r["reading_month"]), [])
                raw_charge, by_band = _tou_charge(hours, band_rows, holiday_days)
                usage_charge = raw_charge.quantize(WON)
                basic = (
                    (tariff["contract_kw"] or Decimal(0)) * tariff["basic_charge"]
                ).quantize(WON)
                segment["loadBands"] = [
                    {
                        "loadBand": name,
                        "usage": str(value["usage"].quantize(SIX)),
                        "charge": str(value["charge"].quantize(WON)),
                    }
                    for name, value in by_band.items()
                ]
            else:
                usage_charge = (r["quantity"] * tariff["usage_rate"]).quantize(WON)
                basic = tariff["basic_charge"].quantize(WON)
            segment.update(
                tariff={
                    "tariffCode": tariff["tariff_code"],
                    "name": tariff["name"],
                    "tariffKind": tariff.get("tariff_kind", "FLAT"),
                    "contractKw": None
                    if tariff.get("contract_kw") is None
                    else str(tariff["contract_kw"]),
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
        # TOU 요금제가 걸린 달이 있을 때만 시각별 계측을 읽는다 — 12개월치는 가볍지 않다.
        tou_ids = [
            t["id"]
            for t in tariffs
            if t["tariff_kind"] == "TOU"
            and t["effective_from"] <= month_to
            and (t["effective_to"] is None or t["effective_to"] >= month_from)
        ]
        bands = repo.tariff_bands(connection, scoped, tou_ids)
        hourly = (
            repo.hourly_consumption(connection, scoped, first, last) if tou_ids else []
        )
        holiday_days = (
            repo.holidays(connection, scoped, first, last) if tou_ids else set()
        )
    sources, total, complete = _billing(rows, tariffs, bands, hourly, holiday_days)
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


# ---------- 부하 패턴·피크 (F-16, DSN-15 F25·F26) ----------

# 기저부하는 밤에 돌지 않아도 쓰는 양이다. 0~6시를 본다.
BASE_LOAD_HOURS = range(6)


def load_pattern(
    context: AuthContext, month: str | None, energy_source_id: int | None
) -> dict[str, Any]:
    """시간대·요일 프로파일, 기저부하, 수요전력 피크(F25·F26). **저장하지 않는다.**

    수요전력은 **1시간 계측의 최대값으로 근사**한다(Q2). 15분 수요를 재지 않으므로 실제
    최대수요전력보다 낮게 나온다 — 화면이 "1시간 근사"라고 밝힌다.

    계약전력이 없는 요금제(FLAT)면 비율을 내지 않는다. 0%가 아니라 '모름'이다.
    """
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        period = _month_period(connection, scoped, month)
        if period is None:
            return {
                "month": None,
                "source": None,
                "profile": [],
                "peak": None,
                "baseLoad": None,
                "hasHolidayCalendar": False,
            }
        month, first, last = period
        sources = repo.active_sources(connection, scoped)
        source = next(
            (s for s in sources if s["id"] == energy_source_id),
            next((s for s in sources if s["source_code"] == "ELEC"), None)
            or (sources[0] if sources else None),
        )
        if source is None:
            return {
                "month": month,
                "source": None,
                "profile": [],
                "peak": None,
                "baseLoad": None,
                "hasHolidayCalendar": False,
            }
        rows = repo.hourly_consumption(connection, scoped, first, last, source["id"])
        holiday_days = repo.holidays(connection, scoped, first, last)
        tariffs = repo.billing_tariffs(connection, scoped)
    tariff = _tariff_for(tariffs, source["id"], month)
    contract_kw = (tariff or {}).get("contract_kw")

    # 시간 × 요일 구분 평균. 같은 칸에 며칠이 들어가므로 합이 아니라 평균이어야 비교된다.
    buckets: dict[tuple[str, int], list[Decimal]] = {}
    peak: dict[str, Any] | None = None
    base_values: list[Decimal] = []
    for row in rows:
        day_kind = tou.day_kind_of(row["reading_date"], holiday_days)
        buckets.setdefault((day_kind, row["hour"]), []).append(row["quantity"])
        if row["hour"] in BASE_LOAD_HOURS:
            base_values.append(row["quantity"])
        if peak is None or row["quantity"] > peak["value"]:
            peak = {
                "value": row["quantity"],
                "date": row["reading_date"],
                "hour": row["hour"],
            }
    profile = [
        {
            "dayKind": day_kind,
            "hour": hour,
            "days": len(values),
            "average": str((sum(values) / len(values)).quantize(SIX)),
            "max": str(max(values).quantize(SIX)),
        }
        for (day_kind, hour), values in sorted(buckets.items())
    ]
    return {
        "month": month,
        "source": {
            "id": source["id"],
            "sourceCode": source["source_code"],
            "name": source["name"],
            "unit": source["measure_unit"],
        },
        "sources": [
            {"id": s["id"], "sourceCode": s["source_code"], "name": s["name"]}
            for s in sources
        ],
        "profile": profile,
        "peak": None
        if peak is None
        else {
            "value": str(peak["value"].quantize(SIX)),
            "date": peak["date"].isoformat(),
            "hour": peak["hour"],
            "contractKw": None if contract_kw is None else str(contract_kw),
            # 계약전력이 없으면 비율은 0이 아니라 모름이다.
            "contractRatio": None
            if not contract_kw
            else str((peak["value"] * 100 / contract_kw).quantize(Decimal("0.1"))),
        },
        # 기저부하 = 밤(0~6시) 시간 사용량의 최솟값. 멈춰도 빠지지 않는 양이다.
        "baseLoad": None
        if not base_values
        else {
            "value": str(min(base_values).quantize(SIX)),
            "average": str((sum(base_values) / len(base_values)).quantize(SIX)),
            "hours": f"{BASE_LOAD_HOURS.start}~{BASE_LOAD_HOURS.stop}",
        },
        # 휴일 달력이 비어 있으면 일요일만 휴일로 본다 — 화면이 그 사실을 밝힌다.
        "hasHolidayCalendar": bool(holiday_days),
    }


# ---------- 계측 품질 (F-15, DSN-15 F12·F14) ----------

# 0이 몇 시간 이어지면 멈춘 것이 아니라 못 읽은 것으로 본다.
ZERO_RUN_HOURS = 3
# 중앙값의 몇 배를 넘으면 급증으로 본다. 평균이 아니라 중앙값이어야 한 번의 급증에 흔들리지 않는다.
SPIKE_FACTOR = Decimal(3)
HOUR = timedelta(hours=1)


def _median(values: list[Decimal]) -> Decimal:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if not ordered:
        return Decimal(0)
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _detect(rows: list[dict[str, Any]], zone: ZoneInfo) -> list[dict[str, Any]]:
    """결측·0 연속·급증을 찾는다. **판단 근거를 함께 돌려준다** — 숫자만 주면 못 고친다."""
    found: list[dict[str, Any]] = []
    by_period = {r["period_start"]: r for r in rows}
    if not rows:
        return found
    values = [Decimal(str(r["value"])) for r in rows]
    median = _median([v for v in values if v > 0])

    # 1) 빠진 시각. 첫 계측과 마지막 계측 사이만 본다 — 바깥은 아직 안 잰 것이지 결측이 아니다.
    cursor = min(by_period)
    last = max(by_period)
    while cursor < last:
        cursor += HOUR
        if cursor not in by_period and cursor < last:
            found.append(
                {
                    "kind": "MISSING",
                    "periodStart": cursor.astimezone(zone).isoformat(),
                    "value": None,
                    "note": "계측값이 없습니다.",
                }
            )

    # 2) 0이 이어지는 구간. 한두 시간은 정지일 수 있어 ZERO_RUN_HOURS부터 본다.
    run: list[dict[str, Any]] = []
    for row in sorted(rows, key=lambda r: r["period_start"]):
        if Decimal(str(row["value"])) == 0:
            run.append(row)
            continue
        if len(run) >= ZERO_RUN_HOURS:
            found.extend(_zero_run(run, zone))
        run = []
    if len(run) >= ZERO_RUN_HOURS:
        found.extend(_zero_run(run, zone))

    # 3) 급증. 중앙값이 0이면(거의 안 쓰는 채널) 판단하지 않는다.
    if median > 0:
        for row in rows:
            value = Decimal(str(row["value"]))
            if value > median * SPIKE_FACTOR:
                found.append(
                    {
                        "kind": "SPIKE",
                        "periodStart": row["period_start"].astimezone(zone).isoformat(),
                        "value": str(value),
                        "note": f"중앙값 {median:.3f}의 {SPIKE_FACTOR}배를 넘습니다.",
                    }
                )
    found.sort(key=lambda f: f["periodStart"])
    return found


def _zero_run(run: list[dict[str, Any]], zone: ZoneInfo) -> list[dict[str, Any]]:
    note = f"0이 {len(run)}시간 이어집니다."
    return [
        {
            "kind": "ZERO_RUN",
            "periodStart": row["period_start"].astimezone(zone).isoformat(),
            "value": "0",
            "note": note,
        }
        for row in run
    ]


def reading_quality(
    context: AuthContext, channel_id: int, date_from: date | None, date_to: date | None
) -> dict[str, Any]:
    """한 채널의 결측·이상값과 보정 이력(F14). 저장하지 않고 그때그때 훑는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        channel = repo.channel_for_reading(connection, scoped, channel_id)
        if channel is None:
            raise ApiError(404, "NOT_FOUND", "계측 채널을 찾을 수 없습니다.")
        if date_to is None:
            latest = repo.latest_reading_date(connection, scoped)
            if latest is None:
                return {
                    "channel": None,
                    "period": None,
                    "issues": [],
                    "corrections": [],
                }
            date_to = latest
            date_from = date_to - timedelta(days=DEFAULT_READING_DAYS - 1)
        _check_period(date_from, date_to)
        rows = repo.channel_readings(connection, scoped, channel_id, date_from, date_to)
        corrections = repo.list_corrections(connection, scoped)
    zone = ZoneInfo(channel["timezone"])
    return {
        "channel": {
            "id": channel["id"],
            "channelCode": channel["channel_code"],
            "name": channel["name"],
            "unit": channel["unit"],
            "meterCode": channel["meter_code"],
        },
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "readingCount": len(rows),
        "issues": _detect(rows, zone),
        "corrections": [
            {
                "id": c["id"],
                "channelCode": c["channel_code"],
                "periodStart": c["period_start"].astimezone(zone).isoformat(),
                "originalValue": None
                if c["original_value"] is None
                else str(c["original_value"]),
                "correctedValue": str(c["corrected_value"]),
                "method": c["method"],
                "reason": c["reason"],
                "correctedAt": c["corrected_at"].isoformat(),
            }
            for c in corrections
        ],
    }


def _reading_payload(
    channel: dict[str, Any],
    period_start: datetime,
    value: str,
    entry_method: str,
    source_key: str,
    revision: int,
    quality: str,
) -> dict[str, Any]:
    return {
        "meter_channel_id": channel["id"],
        # 구간형 계측이라 관측 시각은 구간 끝이다(시드와 같은 규칙).
        "observed_at": period_start + HOUR,
        "period_start": period_start,
        "value": value,
        "unit": channel["unit"],
        "quality": quality,
        "source_key": source_key,
        "input_revision": revision,
        "entry_method": entry_method,
    }


def _reading_dict(row: dict[str, Any]) -> dict[str, Any]:
    """영수증(멱등 재생)에 그대로 들어가므로 날짜를 문자열로 바꾼다."""
    return {
        "id": row["id"],
        "meterChannelId": row["meter_channel_id"],
        "observedAt": row["observed_at"].isoformat(),
        "periodStart": None
        if row["period_start"] is None
        else row["period_start"].isoformat(),
        "value": str(row["value"]),
        "unit": row["unit"],
        "quality": row["quality"],
        "sourceKey": row["source_key"],
        "inputRevision": row["input_revision"],
        "entryMethod": row["entry_method"],
    }


def create_manual_reading(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """계측기가 없는 연료·용수를 손으로 적는다(F12).

    같은 채널·구간에 이미 값이 있으면 덮지 않는다 — 고치는 것은 **보정**이고 이력이 남아야 한다.
    """

    def run(connection: Connection, scoped: AuthContext):
        channel = repo.channel_for_reading(connection, scoped, values["channel_id"])
        if channel is None:
            raise ApiError(404, "NOT_FOUND", "계측 채널을 찾을 수 없습니다.")
        period_start = values["period_start"]
        existing = repo.channel_readings(
            connection,
            scoped,
            channel["id"],
            period_start.date(),
            period_start.date(),
        )
        if any(r["period_start"] == period_start for r in existing):
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 구간에는 이미 계측값이 있습니다. 고치려면 보정을 쓰세요.",
                {"reason": "READING_EXISTS"},
            )
        row = repo.insert_reading(
            connection,
            scoped,
            _reading_payload(
                channel,
                period_start,
                values["value"],
                "MANUAL",
                f"{channel['channel_code']}:MANUAL-{period_start:%Y%m%dT%H}",
                1,
                "valid",
            ),
        )
        return _reading_dict(row)

    return _run_once(context, "fems.reading.manual", key, values, run, 201)


def create_correction(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """결측·이상값을 고친다(F14). **원 계측은 지우지 않는다.**

    고친 값은 같은 구간의 새 `input_revision` 행(quality=estimated)으로 들어가고, 원 계측은
    집계에서만 빠진다(quality=invalid). 원래 값은 행에도, 보정 이력에도 남는다.
    """

    def run(connection: Connection, scoped: AuthContext):
        channel = repo.channel_for_reading(connection, scoped, values["channel_id"])
        if channel is None:
            raise ApiError(404, "NOT_FOUND", "계측 채널을 찾을 수 없습니다.")
        period_start = values["period_start"]
        rows = repo.channel_readings(
            connection, scoped, channel["id"], period_start.date(), period_start.date()
        )
        original = next((r for r in rows if r["period_start"] == period_start), None)
        revision = (original["input_revision"] + 1) if original else 1
        if original is not None:
            repo.supersede_reading(connection, scoped, original["id"])
        row = repo.insert_reading(
            connection,
            scoped,
            _reading_payload(
                channel,
                period_start,
                values["corrected_value"],
                original["entry_method"] if original else "MANUAL",
                f"{channel['channel_code']}:FIX-{period_start:%Y%m%dT%H}-r{revision}",
                revision,
                "estimated",
            ),
        )
        correction = repo.insert_correction(
            connection,
            scoped,
            {
                "channel": channel["id"],
                "period_start": period_start,
                "original": None if original is None else original["value"],
                "corrected": values["corrected_value"],
                "method": values["method"],
                "reason": values["reason"],
            },
        )
        return {
            "id": correction["id"],
            "readingId": row["id"],
            "inputRevision": row["input_revision"],
            "originalValue": None
            if correction["original_value"] is None
            else str(correction["original_value"]),
            "correctedValue": str(correction["corrected_value"]),
            "method": correction["method"],
            "reason": correction["reason"],
        }

    return _run_once(context, "fems.reading.correction", key, values, run, 201)
