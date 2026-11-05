"""FEMS 업무 규칙과 트랜잭션 경계 (FS-011 §3 계층 규칙).

쓰기 순서: 공간 잠금 → 세대·모듈 재확인 → 멱등 키 → 대상 확인 → 검증 → 저장 → 영수증.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo, available_timezones

from sqlalchemy import Connection

from fs.common import master
from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.db import get_engine
from fs.common.engine import read
from fs.common.errors import ApiError
from fs.common.idempotency import find_receipt, request_digest, save_receipt
from fs.common.scope import read_scope, write_scope
from fs.fems import repository as repo
from fs.fems import tou
from fs.hr import interface as hr
from fs.mes import interface as mes

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


def _source_rules(
    connection: Connection,
    scoped: AuthContext,
    merged: dict[str, Any],
    current: dict[str, Any] | None,
    row_id: int | None,
) -> None:
    """에너지원 규칙 둘. 단위 변경 제한과, **발전 에너지원은 요금 부과 대상이 아니다**.

    발전은 만든 양이라 요금을 내지 않는다. 부과 대상으로 두면 요금제가 없다며 요금·월간 검토를
    막는다.
    """
    _unit_in_use(connection, scoped, merged, current, row_id)
    if merged.get("source_kind") == "GENERATION" and merged.get("is_billable"):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"isBillable": "발전 에너지원은 요금 부과 대상이 아닙니다."}},
        )


def _check_department(
    connection: Connection, scoped: AuthContext, code: str | None
) -> None:
    """설비 부서 코드는 HR 부서 코드다(DSN-30 Q1). HR을 껐으면 목록이 없어 형식만 본다.

    설계서 §6은 ERP `departments()`라고 적었지만 부서 표는 `hr.department` 하나뿐이다.
    """
    if code is None:
        return
    rows = hr.departments(connection, scoped)
    if rows is not None and code not in {r["code"] for r in rows}:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"departmentCode": "HR에 없는 부서 코드입니다."}},
        )


def list_departments(context: AuthContext) -> dict[str, Any]:
    """설비에 붙일 부서 후보. HR이 꺼져 있으면 목록이 아니라 꺼졌다고 답한다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = hr.departments(connection, scoped)
    if rows is None:
        return {"hrEnabled": False, "rows": []}
    return {
        "hrEnabled": True,
        "rows": [{"code": r["code"], "name": r["name"]} for r in rows if r["isActive"]],
    }


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
            # 행 하나에 매이지 않는 작업(가져오기·올리기)은 0으로 둔다 — 칸이 NOT NULL이다.
            result.get("id") or 0,
            result,
            status,
        )
        return result


def create_source(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    return master.create(SOURCE, context, values, key, check=_source_rules)


def update_source(
    context: AuthContext, source_id: int, values: dict[str, Any], key: str
) -> dict[str, Any]:
    return master.update(SOURCE, context, source_id, values, key, check=_source_rules)


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
        _check_department(connection, scoped, values.get("department_code"))
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
        if "department_code" in values:
            _check_department(connection, scoped, values["department_code"])
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


def _charges(
    connection: Connection,
    scoped: AuthContext,
    rows: list[dict[str, Any]],
    month_from: str,
    month_to: str,
    first: date,
    last: date,
) -> tuple[list[dict[str, Any]], str, bool]:
    """요금 산정 한 번. 요금 화면·대시보드·월간 검토가 **같은 계산**을 쓴다.

    TOU 요금제가 걸린 달이 있을 때만 시각별 계측을 읽는다 — 12개월치는 가볍지 않다.
    대시보드가 이것을 거치지 않고 `_billing(rows, tariffs)`를 부르던 때는 TOU 달의 사용
    요금이 빠지고 기본요금만 나왔다.
    """
    tariffs = repo.billing_tariffs(connection, scoped)
    tou_ids = [
        t["id"]
        for t in tariffs
        if t["tariff_kind"] == "TOU"
        and t["effective_from"] <= month_to
        and (t["effective_to"] is None or t["effective_to"] >= month_from)
    ]
    bands = repo.tariff_bands(connection, scoped, tou_ids)
    hourly = repo.hourly_consumption(connection, scoped, first, last) if tou_ids else []
    holiday_days = repo.holidays(connection, scoped, first, last) if tou_ids else set()
    return _billing(rows, tariffs, bands, hourly, holiday_days)


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
        sources, total, complete = _charges(
            connection, scoped, rows, month_from, month_to, first, last
        )
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
        charges = _charges(connection, scoped, monthly, month, month, first, last)
        summary = repo.allocation_summary(connection, scoped, {}, first, last)
        issues, recent = repo.quality_issues(connection, scoped, first, last)
        # F-01 보강: 진행 중인 경보와 그 달 피크. 저장하지 않고 센다.
        open_alarms = repo.list_alarms(connection, scoped, open_only=True)
        generation = repo.generation_quantity(connection, scoped, first, last)
        hourly = repo.hourly_consumption(connection, scoped, first, last)
    toe_sources, toe_total, toe_complete = _converted(rows, primary, "PRIMARY", "toe")
    _, emission_total, emission_complete = _converted(
        rows, emission, "EMISSION", "emission"
    )
    billed, charge_total, charge_complete = charges
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
    peak = max((Decimal(str(r["quantity"])) for r in hourly), default=None)
    return {
        "period": {"month": month, "from": first.isoformat(), "to": last.isoformat()},
        "openAlarms": [
            {
                "id": a["id"],
                "ruleCode": a["ruleCode"],
                "ruleName": a["ruleName"],
                "alarmKind": a["alarmKind"],
                "status": a["status"],
            }
            for a in open_alarms[:5]
        ],
        "openAlarmCount": len(open_alarms),
        # 발전은 소비가 아니라 따로 센다. 역송을 재지 않아 발전량 전체를 자가소비로 본다(1차 역송 0).
        "generation": [
            {
                "sourceCode": g["source_code"],
                "name": g["name"],
                "quantity": str(g["quantity"].quantize(SIX)),
                "unit": g["unit"],
            }
            for g in generation
        ],
        # 계측이 없는 달은 0이 아니라 모름이다.
        "peak": None if peak is None else str(peak.quantize(SIX)),
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


# ---------- 계측 올리기·생산량 가져오기 (F-15·F-05, DSN-15 F13·F51) ----------

MAX_UPLOAD_ROWS = 5000


def upload_readings(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """CSV로 받은 행을 검증해 반영한다(F13).

    **파일을 서버가 읽지 않는다.** 브라우저가 CSV를 풀어 행 배열로 보내고, 서버는 행마다
    검증해 받아들이거나 사유와 함께 돌려보낸다. 올린 기록은 합계만 남는다(설계 4-1).

    한 행이라도 틀리면 통째로 막지 않는다 — 500행 중 3행이 틀렸다고 497행을 버릴 이유가 없다.
    """

    def run(connection: Connection, scoped: AuthContext):
        channels = repo.channel_ids_by_code(connection, scoped)
        accepted, rejected = 0, []
        for index, row in enumerate(values["rows"], start=1):
            channel_id = channels.get(row["channel_code"])
            if channel_id is None:
                rejected.append(
                    f"{index}행: 채널 {row['channel_code']}을(를) 찾을 수 없습니다."
                )
                continue
            channel = repo.channel_for_reading(connection, scoped, channel_id)
            period_start = row["period_start"]
            existing = repo.channel_readings(
                connection,
                scoped,
                channel_id,
                period_start.date(),
                period_start.date(),
            )
            if any(r["period_start"] == period_start for r in existing):
                rejected.append(f"{index}행: 이미 계측값이 있는 구간입니다.")
                continue
            repo.insert_reading(
                connection,
                scoped,
                _reading_payload(
                    channel,
                    period_start,
                    row["value"],
                    "FILE",
                    f"{channel['channel_code']}:FILE-{period_start:%Y%m%dT%H}",
                    1,
                    "valid",
                ),
            )
            accepted += 1
        upload = repo.insert_upload(
            connection,
            scoped,
            {
                "upload_no": repo.next_upload_no(
                    connection, scoped, f"{business_today():%Y%m%d}"
                ),
                "file_name": values["file_name"],
                "row_count": len(values["rows"]),
                "accepted": accepted,
                "rejected": len(rejected),
                # 사유를 다 담지 않는다 — 1,000자 칸이고 화면이 전체를 받아 본다.
                "errors": "\n".join(rejected[:10])[:1000] or None,
            },
        )
        return {
            "id": upload["id"],
            "uploadNo": upload["upload_no"],
            "fileName": upload["file_name"],
            "rowCount": upload["row_count"],
            "acceptedCount": upload["accepted_count"],
            "rejectedCount": upload["rejected_count"],
            "rejected": rejected,
        }

    body = {
        "file_name": values["file_name"],
        "rows": [{**r, "period_start": str(r["period_start"])} for r in values["rows"]],
    }
    return _run_once(context, "fems.reading.upload", key, body, run, 201, "upload")


def import_production(context: AuthContext, month: str, key: str) -> dict[str, Any]:
    """MES 확정 실적을 생산량으로 가져온다(F51·Q3).

    1b `mes.production_results(month)`의 첫 소비자다. 설비 코드로만 맞추고 FK를 두지 않는다.
    **가져온 행은 초안**이다 — 확정은 사람이 F-05에서 한다.

    이미 같은 원천 키가 있으면 건너뛴다. 덮어쓰면 확정한 값이 조용히 바뀐다.
    """

    def run(connection: Connection, scoped: AuthContext):
        rows = mes.production_results(connection, scoped, month)
        if rows is None:
            raise _conflict_module_off()
        equipment = repo.equipment_ids_by_code(connection, scoped)
        existing = repo.production_keys(connection, scoped)
        first = date(int(month[:4]), int(month[5:]), 1)
        last = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
        imported, skipped = 0, []
        for row in rows:
            code = row["equipmentCode"]
            if not code:
                # FEMS 생산량은 설비별이다. 설비 없는 실적은 붙일 곳이 없다.
                skipped.append(
                    f"{row['itemCode']}: 설비가 없는 실적이라 가져올 수 없습니다."
                )
                continue
            equipment_id = equipment.get(code)
            if equipment_id is None:
                skipped.append(f"{code}: FEMS에 같은 코드의 설비가 없습니다.")
                continue
            source_key = f"MES:{month}:{code}:{row['itemCode']}"
            if source_key in existing:
                skipped.append(f"{code} {row['itemCode']}: 이미 가져왔습니다.")
                continue
            repo.insert_production(
                connection,
                scoped,
                {
                    "source_key": source_key,
                    "version_no": 1,
                    "equipment_id": equipment_id,
                    "item_code": row["itemCode"],
                    "period_start": datetime.combine(first, time()),
                    "period_end": datetime.combine(last, time()),
                    "production_qty": row["goodQty"],
                    "unit": row["unit"],
                },
            )
            imported += 1
        return {"month": month, "imported": imported, "skipped": skipped}

    return _run_once(
        context, "fems.production.import", key, {"month": month}, run, 201, "production"
    )


def _conflict_module_off() -> ApiError:
    return ApiError(
        409,
        "PRECONDITION_NOT_MET",
        "MES를 사용하지 않도록 설정했습니다. 생산 실적을 읽을 수 없습니다.",
        {"reason": "SOURCE_MODULE_DISABLED", "sourceModule": "mes"},
    )


# ---------- 에너지 경보 (F-18, DSN-15 F31) ----------

ALARM_KIND_LABEL = {
    "THRESHOLD": "시간 사용량 임계",
    "PEAK": "계약전력 대비 피크",
    "IDLE_USAGE": "비가동 시간 사용",
}


def list_alarm_rules(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            repo.alarm_rule_dict(r) for r in repo.list_alarm_rules(connection, scoped)
        ]


def create_alarm_rule(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """경보 규칙을 만든다. 채널이나 설비 중 **하나는 있어야** 무엇을 보는지 정해진다."""

    def run(connection: Connection, scoped: AuthContext):
        if repo.alarm_rule_code_taken(connection, scoped, values["code"]):
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 사용 중인 규칙 코드입니다.",
                {"reason": "DUPLICATE_CODE"},
            )
        if (
            values.get("meter_channel_id") is None
            and values.get("equipment_id") is None
        ):
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "입력값을 확인해 주세요.",
                {
                    "fields": {
                        "meterChannelId": "채널이나 설비 중 하나는 골라야 합니다."
                    }
                },
            )
        if (
            values.get("meter_channel_id") is not None
            and repo.channel_for_reading(connection, scoped, values["meter_channel_id"])
            is None
        ):
            raise ApiError(404, "NOT_FOUND", "계측 채널을 찾을 수 없습니다.")
        return repo.insert_alarm_rule(connection, scoped, values)

    return _run_once(context, "fems.alarm_rule.create", key, values, run, 201, "alarm")


def _peak_ratio(
    connection: Connection, scoped: AuthContext, rule: dict[str, Any], month: str
) -> tuple[Decimal, Decimal] | None:
    """피크 규칙: 그 달 최대 시간 사용량 ÷ 계약전력. 계약전력이 없으면 판단하지 않는다."""
    period = _month_period(connection, scoped, month)
    if period is None:
        return None
    _, first, last = period
    rows = repo.hourly_consumption(connection, scoped, first, last)
    if not rows:
        return None
    peak = max(Decimal(str(r["quantity"])) for r in rows)
    tariffs = repo.billing_tariffs(connection, scoped)
    contract = next(
        (
            t["contract_kw"]
            for t in tariffs
            if t["contract_kw"]
            and t["effective_from"] <= month
            and (t["effective_to"] is None or t["effective_to"] >= month)
        ),
        None,
    )
    if not contract:
        return None
    return peak, peak / contract


def evaluate_alarms(
    context: AuthContext, month: str | None, key: str
) -> dict[str, Any]:
    """규칙을 지금 한 번 본다(F31). **상시 감시 서버를 만들지 않는다**(FEMS 범위).

    규칙당 진행 경보는 하나다(UK_PARTIAL). 이미 열려 있으면 다시 올리지 않고 건너뛴다 —
    같은 일로 경보가 쌓이면 아무도 보지 않게 된다.
    """

    def run(connection: Connection, scoped: AuthContext):
        target = month or f"{business_today():%Y-%m}"
        period = _month_period(connection, scoped, target)
        rules = repo.list_alarm_rules(connection, scoped, active_only=True)
        already = repo.open_alarm_rule_ids(connection, scoped)
        raised, skipped = [], []
        idle_hours: set[Any] | None = None
        for rule in rules:
            if rule["id"] in already:
                skipped.append(f"{rule['code']}: 이미 진행 중인 경보가 있습니다.")
                continue
            hit = _rule_hit(connection, scoped, rule, target, period, idle_hours)
            if hit is None:
                continue
            value, idle_hours = hit
            repo.raise_alarm(connection, scoped, rule["id"], str(value))
            raised.append(rule["code"])
        return {"month": target, "raised": raised, "skipped": skipped}

    return _run_once(
        context, "fems.alarm.evaluate", key, {"month": month}, run, 201, "alarm"
    )


def _rule_hit(
    connection: Connection,
    scoped: AuthContext,
    rule: dict[str, Any],
    month: str,
    period: Any,
    idle_hours: set[Any] | None,
) -> tuple[Decimal, set[Any] | None] | None:
    """규칙 하나를 본다. 걸리면 (넘은 값, 비가동 시각 캐시)를 돌려준다."""
    threshold = Decimal(str(rule["threshold"]))
    if rule["alarm_kind"] == "PEAK":
        measured = _peak_ratio(connection, scoped, rule, month)
        if measured is None:
            return None
        peak, ratio = measured
        return (peak, idle_hours) if ratio > threshold else None

    if period is None or rule["meter_channel_id"] is None:
        return None
    _, first, last = period
    rows = repo.channel_readings(
        connection, scoped, rule["meter_channel_id"], first, last
    )
    if not rows:
        return None

    if rule["alarm_kind"] == "THRESHOLD":
        peak = max(Decimal(str(r["value"])) for r in rows)
        return (peak, idle_hours) if peak > threshold else None

    # IDLE_USAGE — MES 가동 구간 밖의 사용량. MES가 꺼져 있으면 판단하지 않는다.
    if idle_hours is None:
        runs = mes.operation_runs(connection, scoped, first, last)
        if runs is None:
            return None
        busy = set()
        for run_row in runs:
            started = datetime.fromisoformat(run_row["startedAt"])
            ended = (
                datetime.fromisoformat(run_row["endedAt"])
                if run_row["endedAt"]
                else started + HOUR
            )
            cursor = started.replace(minute=0, second=0, microsecond=0)
            while cursor < ended:
                busy.add(cursor)
                cursor += HOUR
        idle_hours = busy
    worst = Decimal(0)
    for row in rows:
        start = row["period_start"]
        if start.replace(minute=0, second=0, microsecond=0) in (idle_hours or set()):
            continue
        worst = max(worst, Decimal(str(row["value"])))
    return (worst, idle_hours) if worst > threshold else None


def list_alarms(context: AuthContext, open_only: bool) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_alarms(connection, scoped, open_only)


def change_alarm_status(
    context: AuthContext, alarm_id: int, status: str, key: str
) -> dict[str, Any]:
    """발생 → 확인 → 해제. 뒤로 가지 않는다 — 되돌릴 일이면 새 경보가 올라온다."""
    allowed = {"ACK": ("OPEN",), "CLEARED": ("OPEN", "ACK")}

    def run(connection: Connection, scoped: AuthContext):
        found = repo.get_alarm(connection, scoped, alarm_id)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "경보를 찾을 수 없습니다.")
        if found["status"] not in allowed[status]:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 경보에서는 할 수 없는 처리입니다.",
                {"reason": "BAD_STATE", "status": found["status"]},
            )
        repo.update_alarm_status(connection, scoped, alarm_id, status)
        return repo.get_alarm(connection, scoped, alarm_id)

    return _run_once(
        context,
        f"fems.alarm.{status.lower()}",
        key,
        {"id": alarm_id},
        run,
        200,
        "alarm",
    )


# ---------- 설비 비교 (F-17, DSN-15 F27) ----------


def equipment_comparison(context: AuthContext, month: str | None) -> dict[str, Any]:
    """같은 **종류** 설비끼리 원단위를 줄 세운다(F27). 저장하지 않는다.

    종류가 다른 설비는 비교하지 않는다 — 사출기와 검사기의 원단위를 나란히 두면 뜻이 없다.
    생산량이 없는 설비는 **0위가 아니라 순위 밖**이다. 나눌 수 없는 것과 나쁜 것은 다르다.
    """
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        period = _month_period(connection, scoped, month)
        if period is None:
            return {"month": None, "groups": []}
        month, first, last = period
        allocations = repo.allocation_summary(connection, scoped, {}, first, last)
        production = repo.production_by_equipment(connection, scoped, first, last)
        equipments, _ = repo.list_equipments(
            connection, scoped, None, None, "equipment_code ASC", 0, 500
        )
    types: dict[str, list[dict[str, Any]]] = {}
    by_id = {e["id"]: e for e in equipments}
    energy: dict[tuple[int, str], Decimal] = {}
    for row in allocations:
        key = (row["equipmentId"], row["unit"])
        energy[key] = energy.get(key, Decimal(0)) + Decimal(row["quantity"])
    for (equipment_id, unit), quantity in sorted(energy.items()):
        equipment = by_id.get(equipment_id)
        if equipment is None:
            continue
        made = production.get(equipment_id)
        kind = equipment["equipmentType"] or "미분류"
        types.setdefault(kind, []).append(
            {
                "equipmentId": equipment_id,
                "equipmentCode": equipment["equipmentCode"],
                "equipmentName": equipment["name"],
                "energy": str(quantity.quantize(SIX)),
                "energyUnit": unit,
                "production": None if made is None else str(made["qty"]),
                "productionUnit": None if made is None else made["unit"],
                # 생산량이 없으면 원단위는 0이 아니라 낼 수 없는 값이다.
                "intensity": None
                if not made or Decimal(str(made["qty"])) == 0
                else str((quantity / Decimal(str(made["qty"]))).quantize(SIX)),
            }
        )
    groups = []
    for kind, rows in sorted(types.items()):
        ranked = sorted(
            [r for r in rows if r["intensity"] is not None],
            key=lambda r: Decimal(r["intensity"]),
        )
        for index, row in enumerate(ranked, start=1):
            row["rank"] = index
        groups.append(
            {
                "equipmentType": kind,
                "ranked": ranked,
                # 비교할 수 없는 설비도 숨기지 않는다 — 왜 빠졌는지 보여야 한다.
                "unranked": [r for r in rows if r["intensity"] is None],
            }
        )
    return {"month": month, "groups": groups}


# ---------- 절감 활동 (F-19, DSN-15 F32·Q5) ----------

DAYS_PER_YEAR = Decimal(365)


def _saving_error(field: str, message: str) -> ApiError:
    return ApiError(
        400,
        "VALIDATION_FAILED",
        "입력값을 확인해 주세요.",
        {"fields": {field: message}},
    )


def list_savings(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_savings(connection, scoped)


def create_saving(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """절감 과제를 계획 상태로 만든다. 비교 전 기간은 시행일 앞에서 끝나야 한다."""

    def run(connection: Connection, scoped: AuthContext):
        if values["baseline_end_on"] <= values["baseline_start_on"]:
            raise _saving_error("baselineEndOn", "비교 전 끝은 시작보다 뒤여야 합니다.")
        if values["baseline_end_on"] > values["start_on"]:
            raise _saving_error(
                "baselineEndOn", "비교 전 기간은 시행일 앞에서 끝나야 합니다."
            )
        review_end = values.get("review_end_on")
        if review_end is not None and review_end <= values["start_on"]:
            raise _saving_error("reviewEndOn", "검증 끝은 시행일보다 뒤여야 합니다.")
        if not repo.source_exists(connection, scoped, values["energy_source_id"]):
            raise _invalid_energy_source()
        equipment_id = values.get("equipment_id")
        if (
            equipment_id is not None
            and repo.site_timezone_of_equipment(connection, scoped, equipment_id)
            is None
        ):
            raise _saving_error("equipmentId", "유효하지 않은 설비입니다.")
        if repo.saving_code_taken(connection, scoped, values["code"]):
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이미 사용 중인 과제 코드입니다.",
                {"reason": "DUPLICATE_CODE"},
            )
        return repo.insert_saving(
            connection, scoped, {**values, "currency": "KRW", "status": "PLANNED"}
        )

    body = {k: str(v) for k, v in values.items()}
    return _run_once(context, "fems.saving.create", key, body, run, 201, "saving")


def change_saving_status(
    context: AuthContext, saving_id: int, action: str, key: str
) -> dict[str, Any]:
    """시행 시작(계획 → 시행)과 취소. 검증한 과제는 바꾸지 않는다."""
    moves = {"start": ("PLANNED", "ACTIVE"), "cancel": (None, "CANCELLED")}
    source, target = moves[action]

    def run(connection: Connection, scoped: AuthContext):
        found = repo.get_saving(connection, scoped, saving_id)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "절감 과제를 찾을 수 없습니다.")
        allowed = (source,) if source else ("PLANNED", "ACTIVE")
        if found["status"] not in allowed:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 과제에서는 할 수 없는 처리입니다.",
                {"reason": "BAD_STATE", "status": found["status"]},
            )
        return repo.update_saving(connection, scoped, saving_id, {"status": target})

    return _run_once(
        context,
        f"fems.saving.{action}",
        key,
        {"id": saving_id},
        run,
        200,
        "saving",
    )


def _period_energy(
    connection: Connection,
    scoped: AuthContext,
    saving: dict[str, Any],
    first: date,
    last: date,
) -> Decimal:
    """과제 대상의 기간 사용량. 설비가 있으면 그 설비의 배분량, 없으면 사업장 수전 합계다."""
    if saving["equipmentId"] is not None:
        rows = repo.allocation_summary(
            connection,
            scoped,
            {
                "equipment_id": saving["equipmentId"],
                "energy_source_id": saving["energySourceId"],
            },
            first,
            last,
        )
        return sum((Decimal(r["quantity"]) for r in rows), Decimal(0))
    rows = repo.emission_consumption(connection, scoped, first, last)
    return sum(
        (r["quantity"] for r in rows if r["source_id"] == saving["energySourceId"]),
        Decimal(0),
    )


def verify_saving(context: AuthContext, saving_id: int, key: str) -> dict[str, Any]:
    """시행 전·후 같은 길이를 견줘 실제 절감을 잰다(Q5). 검증하면 바꾸지 않는다.

    실제 절감 = (비교 전 원단위 − 비교 후 원단위) × 비교 후 생산량, 연 환산.
    **설비가 없는 과제는 생산량으로 보정할 수 없어** 사용량 차이를 그대로 쓰고 응답이 그렇다고 밝힌다.

    shortcut: 비교 기간에 빠진 날이 있어도 센 만큼만 합한다, 계측 완결성 검사가 생기면 막는다.
    """

    def run(connection: Connection, scoped: AuthContext):
        saving = repo.get_saving(connection, scoped, saving_id)
        if saving is None:
            raise ApiError(404, "NOT_FOUND", "절감 과제를 찾을 수 없습니다.")
        if saving["status"] != "ACTIVE":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "시행 중인 과제만 검증할 수 있습니다.",
                {"reason": "BAD_STATE", "status": saving["status"]},
            )
        b_from = date.fromisoformat(saving["baselineStartOn"])
        b_to = date.fromisoformat(saving["baselineEndOn"])  # 끝은 포함하지 않는다
        start = date.fromisoformat(saving["startOn"])
        length = (b_to - b_from).days
        a_to = start + timedelta(days=length)
        latest = repo.latest_reading_date(connection, scoped)
        if latest is None or a_to - timedelta(days=1) > latest:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                f"비교 후 기간이 아직 끝나지 않았습니다({a_to - timedelta(days=1)}까지 필요).",
                {"reason": "PERIOD_NOT_ELAPSED"},
            )
        day = timedelta(days=1)
        e0 = _period_energy(connection, scoped, saving, b_from, b_to - day)
        e1 = _period_energy(connection, scoped, saving, start, a_to - day)
        if e0 <= 0 or e1 <= 0:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "비교 전·후 기간 중 사용량이 없는 쪽이 있습니다.",
                {"reason": "NO_DATA"},
            )
        adjusted = saving["equipmentId"] is not None
        p0 = p1 = None
        if adjusted:
            equipment_id = saving["equipmentId"]
            before = repo.production_by_equipment(
                connection, scoped, b_from, b_to - day, prorate=True
            ).get(equipment_id)
            after = repo.production_by_equipment(
                connection, scoped, start, a_to - day, prorate=True
            ).get(equipment_id)
            p0 = Decimal(str(before["qty"])) if before else Decimal(0)
            p1 = Decimal(str(after["qty"])) if after else Decimal(0)
            if p0 <= 0 or p1 <= 0:
                raise ApiError(
                    409,
                    "PRECONDITION_NOT_MET",
                    "비교 전·후 기간의 생산량이 없어 원단위를 낼 수 없습니다.",
                    {"reason": "NO_PRODUCTION"},
                )
            period_saving = (e0 / p0 - e1 / p1) * p1
        else:
            period_saving = e0 - e1
        annual = (period_saving * DAYS_PER_YEAR / length).quantize(SIX)
        done = repo.update_saving(
            connection,
            scoped,
            saving_id,
            {
                "status": "VERIFIED",
                "measured_saving": annual,
                "verified_at": datetime.now(ZoneInfo("UTC")),
            },
        )
        return {
            **done,
            "evidence": {
                "days": length,
                "productionAdjusted": adjusted,
                "baseline": {
                    "from": b_from.isoformat(),
                    "to": (b_to - day).isoformat(),
                    "energy": str(e0.quantize(SIX)),
                    "production": None if p0 is None else str(p0.quantize(SIX)),
                },
                "after": {
                    "from": start.isoformat(),
                    "to": (a_to - day).isoformat(),
                    "energy": str(e1.quantize(SIX)),
                    "production": None if p1 is None else str(p1.quantize(SIX)),
                },
                "periodSaving": str(period_saving.quantize(SIX)),
            },
        }

    return _run_once(
        context, "fems.saving.verify", key, {"id": saving_id}, run, 200, "saving"
    )


# ---------- 월간 에너지 검토 (F-20, DSN-15 F33·Q5) ----------


def _gaps(sources: list[dict[str, Any]], fine: tuple[str, ...]) -> list[str]:
    """계산이 안 된 에너지원. 확정본에 부분 합계를 넣지 않으려고 센다."""
    return [
        f"{s['sourceCode']}({s['status']})" for s in sources if s["status"] not in fine
    ]


def _incomplete(what: str, gaps: list[str]) -> ApiError:
    return ApiError(
        409,
        "PRECONDITION_NOT_MET",
        f"{what}을(를) 낼 수 없는 에너지원이 있어 만들 수 없습니다: {', '.join(gaps)}",
        {"reason": "INCOMPLETE", "sources": gaps},
    )


def _coverage(
    connection: Connection, scoped: AuthContext, first: date, last: date, span: int
) -> dict[str, Any]:
    found = repo.reading_coverage(connection, scoped, first, last)
    return {**found, "expectedDays": span, "partial": found["days"] < span}


def list_reviews(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_reviews(connection, scoped)


def create_review(
    context: AuthContext, month: str, issues: str | None, key: str
) -> dict[str, Any]:
    """그 달 스냅샷 초안을 만든다. **계산은 지금 하고, 확정은 그 값을 그대로 굳힌다.**

    1차에너지는 PRIMARY 계수, 배출은 EMISSION 계수로 따로 환산한다(AGENTS §3). 계수나
    요금제가 빠진 에너지원이 있으면 부분 합계를 확정본에 남기지 않으려고 만들지 않는다.
    """

    def run(connection: Connection, scoped: AuthContext):
        _, first, last = _month_period(connection, scoped, month)
        month_days = calendar.monthrange(first.year, first.month)[1]
        coverage = _coverage(connection, scoped, first, last, month_days)
        if coverage["days"] == 0:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 달에는 계측값이 없어 검토를 만들 수 없습니다.",
                {"reason": "NO_READINGS"},
            )
        rows = repo.emission_consumption(connection, scoped, first, last)
        toe_sources, toe_total, _ = _converted(
            rows, repo.factors(connection, scoped, "PRIMARY"), "PRIMARY", "toe"
        )
        em_sources, em_total, _ = _converted(
            rows, repo.factors(connection, scoped, "EMISSION"), "EMISSION", "emission"
        )
        for what, found in (("1차에너지", toe_sources), ("배출량", em_sources)):
            gaps = _gaps(found, ("CALCULATED", "NOT_APPLICABLE"))
            if gaps:
                raise _incomplete(what, gaps)
        monthly = repo.monthly_consumption(connection, scoped, first, last)
        billed, cost_total, _ = _charges(
            connection, scoped, monthly, month, month, first, last
        )
        gaps = _gaps(billed, ("CALCULATED", "NOT_BILLABLE"))
        if gaps:
            raise _incomplete("요금", gaps)
        target = repo.site_toe_target(connection, scoped, month)
        achievement = (
            None
            if not target
            else (Decimal(toe_total) / target * 100).quantize(Decimal("0.0001"))
        )
        note = (issues or "").strip()[:1800]
        if coverage["partial"]:
            # 확정본에 남는 곳은 이 칸뿐이라, 달 전체가 아니라는 사실을 여기에 적는다.
            note += (
                f"\n※ 계측 {coverage['days']}일/{month_days}일분 "
                f"({coverage['from']} ~ {coverage['to']})"
            )
        repo.drop_drafts(connection, scoped, "energy_review", "review_month", month)
        review_id = repo.insert_review(
            connection,
            scoped,
            {
                "review_month": month,
                "version": repo.next_version(
                    connection, scoped, "energy_review", "review_month", month
                ),
                "status": "draft",
                "primary_energy_toe": Decimal(toe_total).quantize(Decimal("0.0001")),
                "energy_cost": Decimal(cost_total),
                "currency": "KRW",
                "emission_tco2e": Decimal(em_total).quantize(Decimal("0.0001")),
                "target_achievement": achievement,
                "issues": note.strip() or None,
            },
        )
        return {**repo.get_review(connection, scoped, review_id), "coverage": coverage}

    return _run_once(
        context,
        "fems.review.create",
        key,
        {"month": month, "issues": issues},
        run,
        201,
        "review",
    )


def _confirm_period(
    context: AuthContext,
    key: str,
    operation: str,
    table: str,
    column: str,
    row_id: int,
    get: Any,
) -> dict[str, Any]:
    """초안을 확정한다. 확정본은 다시 바꾸지 않고, 고치려면 새 초안을 만든다."""

    def run(connection: Connection, scoped: AuthContext):
        found = get(connection, scoped, row_id)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "찾을 수 없습니다.")
        if found["status"] != "draft":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "초안만 확정할 수 있습니다.",
                {"reason": "BAD_STATE", "status": found["status"]},
            )
        repo.confirm_snapshot(connection, scoped, table, column, row_id)
        return get(connection, scoped, row_id)

    return _run_once(context, operation, key, {"id": row_id}, run, 200, table)


def confirm_review(context: AuthContext, review_id: int, key: str) -> dict[str, Any]:
    return _confirm_period(
        context,
        key,
        "fems.review.confirm",
        "energy_review",
        "review_month",
        review_id,
        repo.get_review,
    )


# ---------- 온실가스 명세서 (F-21, DSN-15 F35·Q6) ----------

GHG_SCOPE = {"FUEL": 1, "ELECTRIC": 2, "HEAT": 2}


def list_ghg(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_ghg(connection, scoped)


def get_ghg(context: AuthContext, ghg_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_ghg(connection, scoped, ghg_id)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "명세서를 찾을 수 없습니다.")
        year = int(found["inventoryYear"])
        coverage = _coverage(
            connection,
            scoped,
            date(year, 1, 1),
            date(year, 12, 31),
            (date(year, 12, 31) - date(year, 1, 1)).days + 1,
        )
    return {**found, "coverage": coverage}


def create_ghg(context: AuthContext, year: str, key: str) -> dict[str, Any]:
    """연간 Scope 1·2 초안. 설비(시설)·에너지원별 활동량 × **그 연도** 배출 계수다.

    Scope 1 = 연료, Scope 2 = 전력·열. 합계는 줄의 합이다 — 따로 계산하지 않는다.
    설비에 배분되지 않은 나머지는 사업장 공용 줄로 넣어 **사업장 합계와 맞춘다**.
    배출 계수가 없는 에너지원이 있으면 부분 합계를 확정본에 남기지 않으려고 만들지 않는다.

    shortcut: 연 전체를 덮는지는 막지 않고 coverage로 알린다, 명세서에 칸이 생기면 저장한다.
    """

    def run(connection: Connection, scoped: AuthContext):
        first, last = date(int(year), 1, 1), date(int(year), 12, 31)
        coverage = _coverage(connection, scoped, first, last, 365)
        if coverage["days"] == 0:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 해에는 계측값이 없어 명세서를 만들 수 없습니다.",
                {"reason": "NO_READINGS"},
            )
        site = repo.emission_consumption(connection, scoped, first, last)
        factors = repo.factors(connection, scoped, "EMISSION")
        sources: dict[str, dict[str, Any]] = {}
        gaps: list[str] = []
        for row in site:
            if row["source_kind"] not in GHG_SCOPE:
                continue
            factor = factors.get((row["source_id"], year))
            if factor is None or not factor["factor_unit"].endswith("/" + row["unit"]):
                gaps.append(f"{row['source_code']}(계수 없음·단위 불일치)")
                continue
            entry = sources.setdefault(
                row["source_code"],
                {
                    "id": row["source_id"],
                    "scope": GHG_SCOPE[row["source_kind"]],
                    "unit": row["unit"],
                    "factor": factor["factor_value"],
                    "site": Decimal(0),
                    "allocated": Decimal(0),
                },
            )
            entry["site"] += row["quantity"]
        if gaps:
            raise _incomplete("배출 계수", sorted(set(gaps)))
        lines: list[dict[str, Any]] = []
        for row in repo.allocation_summary(connection, scoped, {}, first, last):
            entry = sources.get(row["energySourceCode"])
            if entry is None or row["unit"] != entry["unit"]:
                continue
            qty = Decimal(row["quantity"])
            entry["allocated"] += qty
            lines.append(_ghg_line(entry, row["equipmentId"], qty))
        for entry in sources.values():
            rest = entry["site"] - entry["allocated"]
            if rest > 0:
                lines.append(_ghg_line(entry, None, rest))
        repo.drop_drafts(
            connection,
            scoped,
            "ghg_inventory",
            "inventory_year",
            year,
            ("ghg_inventory_line", "ghg_inventory_id"),
        )
        scope1 = sum((ln["emission"] for ln in lines if ln["scope"] == 1), Decimal(0))
        scope2 = sum((ln["emission"] for ln in lines if ln["scope"] == 2), Decimal(0))
        ghg_id = repo.insert_ghg(
            connection,
            scoped,
            {
                "year": year,
                "version": repo.next_version(
                    connection, scoped, "ghg_inventory", "inventory_year", year
                ),
                "scope1": scope1,
                "scope2": scope2,
            },
            lines,
        )
        return {**repo.get_ghg(connection, scoped, ghg_id), "coverage": coverage}

    return _run_once(context, "fems.ghg.create", key, {"year": year}, run, 201, "ghg")


def _ghg_line(
    entry: dict[str, Any], equipment_id: int | None, qty: Decimal
) -> dict[str, Any]:
    return {
        "equipment": equipment_id,
        "source": entry["id"],
        "scope": entry["scope"],
        "qty": qty.quantize(SIX),
        "unit": entry["unit"],
        "factor": entry["factor"],
        "emission": (qty * entry["factor"]).quantize(Decimal("0.0001")),
    }


def confirm_ghg(context: AuthContext, ghg_id: int, key: str) -> dict[str, Any]:
    return _confirm_period(
        context,
        key,
        "fems.ghg.confirm",
        "ghg_inventory",
        "inventory_year",
        ghg_id,
        lambda c, s, i: repo.get_ghg(c, s, i),
    )


# ---------- 비용 배분 (F-22, DSN-15 F43·Q4) ----------

CENT = Decimal("0.01")


def list_cost_runs(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_cost_runs(connection, scoped)


def _with_totals(run: dict[str, Any]) -> dict[str, Any]:
    """줄에서 부서별 합계를 낸다. 부서가 없는 설비는 '미지정'으로 따로 묶는다."""
    by_department: dict[str, Decimal] = {}
    for line in run["lines"]:
        key = line["departmentCode"] or "미지정"
        by_department[key] = by_department.get(key, Decimal(0)) + Decimal(line["cost"])
    return {
        **run,
        "total": str(sum((Decimal(ln["cost"]) for ln in run["lines"]), Decimal(0))),
        "byDepartment": [
            {"departmentCode": k, "cost": str(v)}
            for k, v in sorted(by_department.items(), key=lambda kv: -kv[1])
        ],
    }


def get_cost_run(context: AuthContext, run_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        found = repo.get_cost_run(connection, scoped, run_id)
        if found is None:
            raise ApiError(404, "NOT_FOUND", "비용 배분을 찾을 수 없습니다.")
    return _with_totals(found)


def create_cost_run(context: AuthContext, month: str, key: str) -> dict[str, Any]:
    """그 달 청구 총액을 설비의 배분량 비율로 나눈다(F43). 사업장 합계를 넘지 않는다.

    비용 = 월 요금(기본요금 + 사용 요금) × 설비 배분량 ÷ 사업장 사용량. TOU 요금제면 월 요금이 이미
    시간대별 요율을 반영한 값이다. 기본요금은 사용량 비율로 나눈다.

    shortcut: 설비별 부하 시간대를 따로 반영하지 않고 평균 요율로 나눈다 — 배분이 일 단위라
    설비의 시간별 프로필이 없다. 시간별 배분이 생기면 설비의 시각별 사용량 × 요율로 바꾼다.

    설비에 배분되지 않은 사용량(공용)의 비용은 어느 설비에도 넣지 않고 `unallocatedCost`로
    돌려준다 — 설비에 떠넘기면 설비 비용이 부풀어 오른다.
    """

    def run(connection: Connection, scoped: AuthContext):
        _, first, last = _month_period(connection, scoped, month)
        month_days = calendar.monthrange(first.year, first.month)[1]
        coverage = _coverage(connection, scoped, first, last, month_days)
        if coverage["days"] == 0:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 달에는 계측값이 없어 비용을 배분할 수 없습니다.",
                {"reason": "NO_READINGS"},
            )
        monthly = repo.monthly_consumption(connection, scoped, first, last)
        billed, _, _ = _charges(connection, scoped, monthly, month, month, first, last)
        gaps = _gaps(billed, ("CALCULATED", "NOT_BILLABLE"))
        if gaps:
            raise _incomplete("요금", gaps)
        by_code = {b["sourceCode"]: b for b in billed if b["status"] == "CALCULATED"}
        quantity: dict[tuple[int, str], Decimal] = {}
        for row in repo.allocation_summary(connection, scoped, {}, first, last):
            entry = by_code.get(row["energySourceCode"])
            if entry is None or row["unit"] != entry["unit"]:
                continue
            k = (row["equipmentId"], row["energySourceCode"])
            quantity[k] = quantity.get(k, Decimal(0)) + Decimal(row["quantity"])
        departments = repo.equipment_departments(connection, scoped)
        items = repo.main_items(connection, scoped, first, last)
        lines: list[dict[str, Any]] = []
        spent = Decimal(0)
        for code, entry in by_code.items():
            allocated = sum(
                (q for (_, c), q in quantity.items() if c == code), Decimal(0)
            )
            # 배분량이 사업장 사용량보다 크면(드물다) 합이 총액을 넘지 않게 분모를 키운다.
            base = max(Decimal(entry["usage"]), allocated)
            if base <= 0:
                continue
            for (equipment_id, c), qty in quantity.items():
                if c != code:
                    continue
                cost = (Decimal(entry["total"]) * qty / base).quantize(CENT)
                spent += cost
                lines.append(
                    {
                        "equipment": equipment_id,
                        "source": entry["energySourceId"],
                        "department": departments.get(equipment_id),
                        "item": items.get(equipment_id),
                        "qty": qty.quantize(SIX),
                        "unit": entry["unit"],
                        "cost": cost,
                    }
                )
        site_total = sum((Decimal(e["total"]) for e in by_code.values()), Decimal(0))
        repo.drop_drafts(
            connection,
            scoped,
            "cost_run",
            "cost_month",
            month,
            ("cost_allocation_line", "cost_run_id"),
        )
        run_id = repo.insert_cost_run(
            connection,
            scoped,
            month,
            repo.next_version(connection, scoped, "cost_run", "cost_month", month),
            lines,
        )
        found = repo.get_cost_run(connection, scoped, run_id)
        return {
            **_with_totals(found),
            "unallocatedCost": str(max(site_total - spent, Decimal(0)).quantize(CENT)),
            "coverage": coverage,
        }

    return _run_once(
        context, "fems.cost_run.create", key, {"month": month}, run, 201, "cost_run"
    )


def confirm_cost_run(context: AuthContext, run_id: int, key: str) -> dict[str, Any]:
    return _confirm_period(
        context,
        key,
        "fems.cost_run.confirm",
        "cost_run",
        "cost_month",
        run_id,
        repo.get_cost_run,
    )


# ---------- 고지서 대조 (F-23, DSN-15 F42) ----------


def list_bills(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return repo.list_bills(connection, scoped)


def create_bill(
    context: AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    """실제 청구 금액을 넣고 **입력 시점의 산정 금액**과 견준다. 회계 처리는 ERP 매입이다.

    산정 금액은 그때의 스냅샷이다 — 나중에 계측이 바뀌어도 이 고지서와 견준 값은 그대로 남는다.
    차이가 있으면 사유가 있어야 한다. 사유 없는 차이는 나중에 아무도 설명할 수 없다.
    """

    def run(connection: Connection, scoped: AuthContext):
        source_id, month = values["energy_source_id"], values["bill_month"]
        if not repo.source_exists(connection, scoped, source_id):
            raise _invalid_energy_source()
        _, first, last = _month_period(connection, scoped, month)
        monthly = repo.monthly_consumption(connection, scoped, first, last)
        billed, _, _ = _charges(connection, scoped, monthly, month, month, first, last)
        entry = next((b for b in billed if b["energySourceId"] == source_id), None)
        if entry is None:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 달에는 그 에너지원의 계측값이 없어 산정할 수 없습니다.",
                {"reason": "NO_READINGS"},
            )
        if entry["status"] == "NOT_BILLABLE":
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "요금 부과 대상이 아닌 에너지원이라 고지서가 없습니다.",
                {"reason": "NOT_BILLABLE"},
            )
        if entry["status"] != "CALCULATED":
            raise _incomplete(
                "산정 금액", [f"{entry['sourceCode']}({entry['status']})"]
            )
        if repo.bill_taken(connection, scoped, source_id, month):
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "이 달 고지서가 이미 있습니다. 지우고 다시 넣으세요.",
                {"reason": "DUPLICATE"},
            )
        calculated = Decimal(entry["total"]).quantize(CENT)
        note = (values.get("note") or "").strip()
        if abs(values["billed_amount"] - calculated) >= 1 and len(note) < 2:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "입력값을 확인해 주세요.",
                {"fields": {"note": "산정과 다르면 차이 사유를 적어야 합니다."}},
            )
        bill_id = repo.insert_bill(
            connection,
            scoped,
            {
                "source": source_id,
                "month": month,
                "qty": values["billed_qty"],
                "billed": values["billed_amount"],
                "calculated": calculated,
                "note": note or None,
            },
        )
        month_days = calendar.monthrange(first.year, first.month)[1]
        return {
            **repo.get_bill(connection, scoped, bill_id),
            "coverage": _coverage(connection, scoped, first, last, month_days),
        }

    body = {k: str(v) for k, v in values.items()}
    return _run_once(context, "fems.bill.create", key, body, run, 201, "bill")


def delete_bill(context: AuthContext, bill_id: int, key: str) -> dict[str, Any]:
    def run(connection: Connection, scoped: AuthContext):
        if repo.get_bill(connection, scoped, bill_id) is None:
            raise ApiError(404, "NOT_FOUND", "고지서를 찾을 수 없습니다.")
        repo.delete_bill(connection, scoped, bill_id)
        return {"id": bill_id}

    return _run_once(
        context, "fems.bill.delete", key, {"id": bill_id}, run, 200, "bill"
    )
