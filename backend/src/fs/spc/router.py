# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""SPC API (/api/v1/spc, FS-028 모듈 설계 8장). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from datetime import date, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.spc import service
from fs.spc.schema import (
    CharacteristicCreate,
    CharacteristicUpdate,
    LimitPublish,
    Resolve,
    SubgroupCreate,
    VoidBody,
)

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]
From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


# 공통 엔진: CSRF·멱등 키 확인
_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _data(value: Any) -> dict[str, Any]:
    return {"data": value}


@router.get("/dashboard")
def get_dashboard(context: Auth):
    return _data(service.dashboard(context))


@router.get("/lookups/items")
def lookup_items(context: Auth):
    return _data(service.items(context))


@router.get("/characteristics")
def list_characteristics(context: Auth):
    return _data(service.characteristics(context))


@router.post("/characteristics", status_code=201)
def post_characteristic(
    payload: CharacteristicCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_characteristic(
            context,
            _values(payload, frozenset({"lsl", "usl", "target"})),
            _mutation(context, csrf, key),
        )
    )


@router.get("/characteristics/{characteristic_id}")
def get_characteristic(characteristic_id: int, context: Auth):
    return _data(service.characteristic(context, characteristic_id))


@router.patch("/characteristics/{characteristic_id}")
def patch_characteristic(
    characteristic_id: int,
    payload: CharacteristicUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_characteristic(
            context,
            characteristic_id,
            _values(payload, frozenset({"lsl", "usl", "target"})),
            _mutation(context, csrf, key),
        )
    )


@router.get("/characteristics/{characteristic_id}/chart")
def get_chart(
    characteristic_id: int, context: Auth, date_from: From = None, date_to: To = None
):
    return _data(service.chart(context, characteristic_id, date_from, date_to))


@router.get("/characteristics/{characteristic_id}/capability")
def get_capability(
    characteristic_id: int, context: Auth, date_from: From = None, date_to: To = None
):
    return _data(service.capability(context, characteristic_id, date_from, date_to))


@router.get("/characteristics/{characteristic_id}/limits")
def list_limits(characteristic_id: int, context: Auth):
    return _data(service.limits(context, characteristic_id))


@router.get("/characteristics/{characteristic_id}/limits/preview")
def preview_limit(
    characteristic_id: int,
    context: Auth,
    basis_from: Annotated[datetime, Query(alias="basisFrom")],
    basis_to: Annotated[datetime, Query(alias="basisTo")],
):
    return _data(
        service.preview_limit(context, characteristic_id, basis_from, basis_to)
    )


@router.post("/characteristics/{characteristic_id}/limits", status_code=201)
def post_limit(
    characteristic_id: int,
    payload: LimitPublish,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.publish_limit(
            context, characteristic_id, _values(payload), _mutation(context, csrf, key)
        )
    )


@router.get("/runs")
def list_runs(
    context: Auth, characteristic_id: Annotated[int, Query(alias="characteristicId")]
):
    return _data(service.runs(context, characteristic_id))


@router.get("/subgroups")
def list_subgroups(
    context: Auth,
    characteristic_id: Annotated[int | None, Query(alias="characteristicId")] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo")] = None,
    status: Literal["valid", "void"] | None = None,
):
    return _data(service.subgroups(context, characteristic_id, lot_no, status))


@router.post("/subgroups", status_code=201)
def post_subgroup(
    payload: SubgroupCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.record_subgroup(
            context,
            _values(payload, frozenset({"note"})),
            _mutation(context, csrf, key),
        )
    )


@router.post("/subgroups/{subgroup_id}/void")
def post_void(
    subgroup_id: int,
    payload: VoidBody,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.void_subgroup(
            context, subgroup_id, payload.reason, _mutation(context, csrf, key)
        )
    )


@router.get("/spec-violations")
def list_spec_violations(
    context: Auth,
    characteristic_id: Annotated[int | None, Query(alias="characteristicId")] = None,
    lot_no: Annotated[str | None, Query(alias="lotNo")] = None,
    status: Literal["open", "void"] | None = None,
):
    return _data(service.spec_violations(context, characteristic_id, lot_no, status))


@router.get("/signals")
def list_signals(
    context: Auth,
    status: Literal["open", "resolved", "void"] | None = None,
    characteristic_id: Annotated[int | None, Query(alias="characteristicId")] = None,
):
    return _data(service.signals(context, status, characteristic_id))


@router.post("/signals/{signal_id}/resolve")
def post_resolve(
    signal_id: int,
    payload: Resolve,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.resolve_signal(
            context, signal_id, _values(payload), _mutation(context, csrf, key)
        )
    )
