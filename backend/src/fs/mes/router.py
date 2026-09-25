# 주의: 이 모듈은 `from __future__ import annotations`를 쓰지 않는다.
# _register가 만드는 엔드포인트의 본문 타입(payload)을 FastAPI가 실제 클래스로 읽어야 한다.
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Response
from pydantic import BaseModel

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.mes import repository as repo
from fs.mes import service
from fs.mes.repository import Master
from fs.mes.schema import (
    BomCreate,
    BomLines,
    BomRevise,
    ConversionCreate,
    ConversionUpdate,
    EquipmentCreate,
    EquipmentUpdate,
    ItemCreate,
    ItemUpdate,
    LocationCreate,
    LocationUpdate,
    ProcessCreate,
    ProcessUpdate,
    RouteCreate,
    RouteSteps,
    SiteCreate,
    SiteUpdate,
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


def _values(payload: BaseModel, nullable: frozenset[str]) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _register(
    path: str,
    master: Master,
    label: str,
    create_model: type[BaseModel],
    update_model: type[BaseModel],
    check: service.Check,
    nullable: frozenset[str] = frozenset(),
    listing: Callable[[AuthContext], list[dict[str, Any]]] | None = None,
    after=None,
    before=None,
) -> None:
    """기준정보 한 종류의 목록·단건·등록·수정·삭제 엔드포인트를 등록한다."""

    @router.get(path, name=f"list {path}")
    def list_(context: Auth) -> dict[str, object]:
        rows = listing(context) if listing else service.list_rows(context, master)
        return {"data": rows}

    @router.get(f"{path}/{{row_id}}", name=f"get {path}")
    def get_(context: Auth, row_id: int) -> dict[str, object]:
        return {"data": service.get_row(context, master, row_id, label)}

    @router.post(path, status_code=201, name=f"create {path}")
    def create_(
        payload: create_model,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> dict[str, object]:
        key = _mutation(context, x_csrf_token, idempotency_key)
        return {
            "data": service.create(
                context, master, payload.model_dump(), key, check, after
            )
        }

    @router.patch(f"{path}/{{row_id}}", name=f"update {path}")
    def update_(
        row_id: int,
        payload: update_model,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> dict[str, object]:
        key = _mutation(context, x_csrf_token, idempotency_key)
        values = _values(payload, nullable)
        return {
            "data": service.update(
                context, master, row_id, values, key, check, label, after
            )
        }

    @router.delete(f"{path}/{{row_id}}", status_code=204, name=f"delete {path}")
    def delete_(
        row_id: int,
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> Response:
        key = _mutation(context, x_csrf_token, idempotency_key)
        service.delete(
            context, master, row_id, key, label, before(row_id) if before else None
        )
        return Response(status_code=204)


_register("/sites", repo.SITE, "사업장", SiteCreate, SiteUpdate, service.check_site)
_register(
    "/locations",
    repo.LOCATION,
    "공간",
    LocationCreate,
    LocationUpdate,
    service.check_location,
    nullable=frozenset({"parent_location_id"}),
)
_register(
    "/equipments",
    repo.EQUIPMENT,
    "설비",
    EquipmentCreate,
    EquipmentUpdate,
    service.check_equipment,
)
_register(
    "/items",
    repo.ITEM,
    "품목",
    ItemCreate,
    ItemUpdate,
    service.check_item,
    listing=service.items_with_conversions,
)
_register(
    "/processes",
    repo.PROCESS,
    "공정",
    ProcessCreate,
    ProcessUpdate,
    service.check_process,
    listing=service.processes_with_equipment,
    after=service.save_process_equipment,
    before=service.delete_process_links,
)


# 단위 환산은 품목 아래에 둔다(/items/{id}/conversions).
@router.post("/items/{item_id}/conversions", status_code=201)
def post_conversion(
    item_id: int,
    payload: ConversionCreate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.create(
            context,
            repo.CONVERSION,
            payload.model_dump(),
            key,
            service.conversion_check(item_id),
        )
    }


@router.patch("/items/{item_id}/conversions/{row_id}")
def patch_conversion(
    item_id: int,
    row_id: int,
    payload: ConversionUpdate,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.update(
            context,
            repo.CONVERSION,
            row_id,
            _values(payload, frozenset()),
            key,
            service.conversion_check(item_id),
            "단위 환산",
        )
    }


@router.delete("/items/{item_id}/conversions/{row_id}", status_code=204)
def delete_conversion(
    item_id: int,
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> Response:
    key = _mutation(context, x_csrf_token, idempotency_key)
    service.delete(
        context,
        repo.CONVERSION,
        row_id,
        key,
        "단위 환산",
        service.conversion_owner(item_id, row_id),
    )
    return Response(status_code=204)


# ---- M-14 공정 경로 · M-15 BOM: 버전(초안 → 게시 → 폐기) ----
def _transition_endpoint(v: service.Versioned, target: str):
    # target은 클로저로 고정한다. 함수 인자로 두면 FastAPI가 쿼리 파라미터로 받는다.
    def change(
        row_id: int,
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> dict[str, object]:
        key = _mutation(context, x_csrf_token, idempotency_key)
        return {"data": service.transition(context, v, row_id, target, key)}

    return change


def _versions(path: str, v: service.Versioned, create_model: type[BaseModel]) -> None:
    @router.get(path, name=f"list {path}")
    def list_(context: Auth) -> dict[str, object]:
        return {"data": service.list_versions(context, v)}

    @router.post(path, status_code=201, name=f"create {path}")
    def create_(
        payload: create_model,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> dict[str, object]:
        key = _mutation(context, x_csrf_token, idempotency_key)
        return {"data": service.create_version(context, v, payload.model_dump(), key)}

    router.post(f"{path}/{{row_id}}/publish", name=f"publish {path}")(
        _transition_endpoint(v, "published")
    )
    router.post(f"{path}/{{row_id}}/retire", name=f"retire {path}")(
        _transition_endpoint(v, "retired")
    )

    @router.delete(f"{path}/{{row_id}}", status_code=204, name=f"delete {path}")
    def delete_(
        row_id: int,
        context: Auth,
        idempotency_key: IdempotencyKey = None,
        x_csrf_token: CsrfToken = None,
    ) -> Response:
        key = _mutation(context, x_csrf_token, idempotency_key)
        service.delete_version(context, v, row_id, key)
        return Response(status_code=204)


_versions("/routes", service.ROUTES, RouteCreate)
_versions("/boms", service.BOMS, BomCreate)


@router.post("/routes/{row_id}/revise", status_code=201)
def revise_route(
    row_id: int,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.revise_version(context, service.ROUTES, row_id, {}, key)}


@router.post("/boms/{row_id}/revise", status_code=201)
def revise_bom(
    row_id: int,
    payload: BomRevise,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.revise_version(
            context, service.BOMS, row_id, payload.model_dump(), key
        )
    }


@router.put("/routes/{row_id}/steps")
def put_steps(
    row_id: int,
    payload: RouteSteps,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    rows = [{"process_id": pid} for pid in payload.process_ids]
    return {
        "data": service.set_children(
            context, service.ROUTES, row_id, rows, key, service.validate_steps
        )
    }


@router.put("/boms/{row_id}/lines")
def put_lines(
    row_id: int,
    payload: BomLines,
    context: Auth,
    idempotency_key: IdempotencyKey = None,
    x_csrf_token: CsrfToken = None,
) -> dict[str, object]:
    key = _mutation(context, x_csrf_token, idempotency_key)
    rows = [line.model_dump() for line in payload.lines]
    return {
        "data": service.set_children(
            context, service.BOMS, row_id, rows, key, service.validate_lines
        )
    }
