from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.fems import service
from fs.fems.schema import (
    EnergySourceCreate,
    EnergySourceUpdate,
    EquipmentCreate,
    EquipmentUpdate,
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
