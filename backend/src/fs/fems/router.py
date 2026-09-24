from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.fems import service
from fs.fems.schema import (
    EnergySourceCreate,
    EnergySourceUpdate,
    EquipmentCreate,
    EquipmentUpdate,
    TariffCreate,
    TariffUpdate,
)

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]


def _mutation(context: AuthContext, csrf: str | None, key: str | None) -> str:
    require_csrf(context, csrf)
    if not key or len(key) > 100:
        raise ApiError(400, "VALIDATION_FAILED", "Idempotency-Key가 필요합니다.")
    return key


@router.get("/energy-sources")
def list_energy_sources(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    data, total = service.list_sources(context, active, sort, page.offset, page.limit)
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/energy-sources/{source_id}")
def get_energy_source(context: Auth, source_id: int) -> dict[str, object]:
    return {"data": service.get_source(context, source_id)}


@router.post("/energy-sources", status_code=201)
def post_energy_source(
    payload: EnergySourceCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.create_source(context, payload.model_dump(), key)}


@router.patch("/energy-sources/{source_id}")
def patch_energy_source(
    source_id: int,
    payload: EnergySourceUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise ApiError(400, "VALIDATION_FAILED", "null로 비울 수 있는 항목이 없습니다.")
    return {"data": service.update_source(context, source_id, values, key)}


@router.delete("/energy-sources/{source_id}", status_code=204)
def delete_energy_source(
    source_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> Response:
    key = _mutation(context, x_csrf_token, idempotency_key)
    service.delete_source(context, source_id, key)
    return Response(status_code=204)


@router.get("/locations")
def list_locations(context: Auth) -> dict[str, object]:
    return {"data": service.list_locations(context)}


@router.get("/equipments")
def list_equipments(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
    location_id: int | None = None,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    data, total = service.list_equipments(
        context, active, location_id, sort, page.offset, page.limit
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/equipments/{equipment_id}")
def get_equipment(context: Auth, equipment_id: int) -> dict[str, object]:
    return {"data": service.get_equipment(context, equipment_id)}


@router.post("/equipments", status_code=201)
def post_equipment(
    payload: EquipmentCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.create_equipment(context, payload.model_dump(), key)}


@router.patch("/equipments/{equipment_id}")
def patch_equipment(
    equipment_id: int,
    payload: EquipmentUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(exclude_unset=True)
    if any(value is None for value in values.values()):
        raise ApiError(400, "VALIDATION_FAILED", "null로 비울 수 있는 항목이 없습니다.")
    return {"data": service.update_equipment(context, equipment_id, values, key)}


@router.delete("/equipments/{equipment_id}", status_code=204)
def delete_equipment(
    equipment_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> Response:
    key = _mutation(context, x_csrf_token, idempotency_key)
    service.delete_equipment(context, equipment_id, key)
    return Response(status_code=204)


@router.get("/tariffs")
def list_tariffs(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    energy_source_id: Annotated[int | None, Query(alias="energySourceId")] = None,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    data, total = service.list_tariffs(
        context, energy_source_id, sort, page.offset, page.limit
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/tariffs/{tariff_id}")
def get_tariff(context: Auth, tariff_id: int) -> dict[str, object]:
    return {"data": service.get_tariff(context, tariff_id)}


@router.post("/tariffs", status_code=201)
def post_tariff(
    payload: TariffCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.create_tariff(context, payload.model_dump(), key)}


@router.patch("/tariffs/{tariff_id}")
def patch_tariff(
    tariff_id: int,
    payload: TariffUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(exclude_unset=True)
    non_null_fields = {
        "energy_source_id",
        "tariff_code",
        "name",
        "basic_charge",
        "usage_rate",
        "effective_from",
    }
    if any(values.get(f) is None for f in non_null_fields if f in values):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return {"data": service.update_tariff(context, tariff_id, values, key)}


@router.delete("/tariffs/{tariff_id}", status_code=204)
def delete_tariff(
    tariff_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> Response:
    key = _mutation(context, x_csrf_token, idempotency_key)
    service.delete_tariff(context, tariff_id, key)
    return Response(status_code=204)


@router.get("/sites")
def list_sites(context: Auth) -> dict[str, object]:
    return {"data": service.list_sites(context)}


@router.get("/meters")
def list_meters(context: Auth) -> dict[str, object]:
    return {"data": service.list_meters(context)}


@router.get("/readings")
def list_readings(
    context: Auth,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    site_id: Annotated[int | None, Query(alias="siteId")] = None,
    meter_id: Annotated[int | None, Query(alias="meterId")] = None,
    channel_id: Annotated[int | None, Query(alias="channelId")] = None,
    energy_source_id: Annotated[int | None, Query(alias="energySourceId")] = None,
    quality: Literal["valid", "estimated", "reset", "invalid"] | None = None,
    sort: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    filters = {
        key: value
        for key, value in {
            "site_id": site_id,
            "meter_id": meter_id,
            "channel_id": channel_id,
            "energy_source_id": energy_source_id,
            "quality": quality,
        }.items()
        if value is not None
    }
    data, total, period = service.list_readings(
        context, filters, date_from, date_to, sort, page.offset, page.limit
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
        "range": period,
    }


@router.get("/allocations")
def list_allocations(
    context: Auth,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    equipment_id: Annotated[int | None, Query(alias="equipmentId")] = None,
    energy_source_id: Annotated[int | None, Query(alias="energySourceId")] = None,
    method_key: Annotated[str | None, Query(alias="methodKey", max_length=40)] = None,
    include_superseded: Annotated[bool, Query(alias="includeSuperseded")] = False,
    offset: int = 0,
    limit: int = 50,
) -> dict[str, object]:
    page = Page(offset, limit).checked()
    filters = {
        key: value
        for key, value in {
            "equipment_id": equipment_id,
            "energy_source_id": energy_source_id,
            "method_key": method_key,
        }.items()
        if value is not None
    }
    data, total, summary, period = service.list_allocations(
        context,
        filters,
        date_from,
        date_to,
        include_superseded,
        page.offset,
        page.limit,
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
        "range": period,
        "summary": summary,
    }


@router.get("/emissions")
def get_emissions(
    context: Auth,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> dict[str, object]:
    return {"data": service.emissions(context, date_from, date_to)}


@router.get("/dashboard")
def get_dashboard(
    context: Auth,
    month: Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")] = None,
) -> dict[str, object]:
    return {"data": service.dashboard(context, month)}
