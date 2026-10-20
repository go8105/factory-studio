# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""CMMS API (/api/v1/cmms, FS-029 · DSN-21). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Query, Response
from pydantic import BaseModel

from fs.cmms import service
from fs.cmms.schema import (
    AssetCreate,
    AssetImport,
    AssetUpdate,
    FailureCodeCreate,
    FailureCodeUpdate,
)
from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.common.page import Page

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]

_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _page(rows_total: tuple[list[dict[str, Any]], int], page: Page) -> dict[str, Any]:
    rows, total = rows_total
    return {
        "data": rows,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


# 비워 둘 수 있는 칸 — 상세는 모르면 비운다. 상위 설비를 비우면 최상위가 된다.
ASSET_NULLABLE = frozenset(
    {
        "location",
        "parent_asset_id",
        "manufacturer",
        "model",
        "serial_no",
        "installed_on",
        "acquisition_cost",
        "criticality",
    }
)


# ── 설비 대장 (C-05) ────────────────────────────────────────────────────────


@router.get("/assets")
def list_assets(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    asset_type: Annotated[str | None, Query(alias="assetType")] = None,
    source: str | None = None,
    criticality: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.assets(
            context,
            filters={
                "assetType": asset_type,
                "source": source,
                "criticality": criticality,
                "active": active,
            },
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.get("/assets/tree")
def get_asset_tree(context: Auth):
    return {"data": service.asset_tree(context)}


@router.get("/assets/import-candidates")
def list_import_candidates(context: Auth, source: Annotated[str, Query()] = "MES"):
    return {"data": service.import_candidates(context, source)}


@router.post("/assets/import", status_code=201)
def post_asset_import(
    payload: AssetImport,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.import_assets(
            context,
            payload.source,
            payload.source_codes,
            _mutation(context, csrf, key),
        )
    }


@router.get("/assets/{asset_id}")
def get_asset(asset_id: int, context: Auth):
    return {"data": service.asset(context, asset_id)}


@router.post("/assets", status_code=201)
def post_asset(
    payload: AssetCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_asset(
            context, _values(payload, ASSET_NULLABLE), _mutation(context, csrf, key)
        )
    }


@router.patch("/assets/{asset_id}")
def patch_asset(
    asset_id: int,
    payload: AssetUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_asset(
            context,
            asset_id,
            _values(payload, ASSET_NULLABLE),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/assets/{asset_id}", status_code=204)
def delete_asset(
    asset_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_asset(context, asset_id, _mutation(context, csrf, key))
    return Response(status_code=204)


# ── 고장 코드 (C-09) ────────────────────────────────────────────────────────


@router.get("/failure-codes")
def list_failure_codes(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    kind: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    return _page(
        service.failure_codes(
            context,
            filters={"kind": kind, "active": active},
            sort=sort,
            offset=page.offset,
            limit=page.limit,
        ),
        page,
    )


@router.post("/failure-codes", status_code=201)
def post_failure_code(
    payload: FailureCodeCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.create_failure_code(
            context,
            _values(payload, frozenset({"cause_category"})),
            _mutation(context, csrf, key),
        )
    }


@router.patch("/failure-codes/{code_id}")
def patch_failure_code(
    code_id: int,
    payload: FailureCodeUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return {
        "data": service.update_failure_code(
            context,
            code_id,
            _values(payload, frozenset({"cause_category"})),
            _mutation(context, csrf, key),
        )
    }


@router.delete("/failure-codes/{code_id}", status_code=204)
def delete_failure_code(
    code_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    service.delete_failure_code(context, code_id, _mutation(context, csrf, key))
    return Response(status_code=204)
