from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.erp import schema, service

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Csrf = Annotated[str | None, Header(alias="X-CSRF-Token")]


def mutation(context, csrf, key):
    require_csrf(context, csrf)
    if not key or not key.strip() or len(key) > 100:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "Idempotency-Key가 필요합니다.",
            {"fields": {"Idempotency-Key": "1~100자 키가 필요합니다."}},
        )
    return key


@router.get("/partners")
def list_partners(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context, "partners", page.offset, page.limit, sort, {"is_active": active}
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/partners/{row_id}")
def get_partners(row_id: int, context: Auth):
    return {"data": service.detail(context, "partners", row_id)}


@router.post("/partners", status_code=201)
def post_partners(
    payload: schema.PartnerCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(context, "partners", payload.model_dump(), key)
    return {"data": result}


@router.patch("/partners/{row_id}")
def patch_partners(
    row_id: int,
    payload: schema.PartnerUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(
        context, "partners", payload.model_dump(exclude_unset=True), key, row_id=row_id
    )
    return {"data": result}


@router.delete("/partners/{row_id}", status_code=204)
def delete_partners(
    row_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    service.mutate(context, "partners", {}, key, row_id=row_id, deleting=True)
    return Response(status_code=204)


@router.get("/items")
def list_items(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context, "items", page.offset, page.limit, sort, {"is_active": active}
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/items/{row_id}")
def get_items(row_id: int, context: Auth):
    return {"data": service.detail(context, "items", row_id)}


@router.post("/items", status_code=201)
def post_items(
    payload: schema.ItemCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(context, "items", payload.model_dump(), key)
    return {"data": result}


@router.patch("/items/{row_id}")
def patch_items(
    row_id: int,
    payload: schema.ItemUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(
        context, "items", payload.model_dump(exclude_unset=True), key, row_id=row_id
    )
    return {"data": result}


@router.delete("/items/{row_id}", status_code=204)
def delete_items(
    row_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    service.mutate(context, "items", {}, key, row_id=row_id, deleting=True)
    return Response(status_code=204)


@router.get("/partner-prices")
def list_partner_prices(
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
    active: bool | None = None,
    partner_id: int | None = Query(None, alias="partnerId", gt=0),
    item_id: int | None = Query(None, alias="itemId", gt=0),
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context,
        "partner-prices",
        page.offset,
        page.limit,
        sort,
        {"partner_id": partner_id, "item_id": item_id, "is_active": active},
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/partner-prices/{row_id}")
def get_partner_prices(row_id: int, context: Auth):
    return {"data": service.detail(context, "partner-prices", row_id)}


@router.post("/partner-prices", status_code=201)
def post_partner_prices(
    payload: schema.PriceCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(context, "partner-prices", payload.model_dump(), key)
    return {"data": result}


@router.patch("/partner-prices/{row_id}")
def patch_partner_prices(
    row_id: int,
    payload: schema.PriceUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(
        context,
        "partner-prices",
        payload.model_dump(exclude_unset=True),
        key,
        row_id=row_id,
    )
    return {"data": result}


@router.delete("/partner-prices/{row_id}", status_code=204)
def delete_partner_prices(
    row_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    service.mutate(context, "partner-prices", {}, key, row_id=row_id, deleting=True)
    return Response(status_code=204)


@router.get("/items/{item_id}/conversions")
def list_conversions(
    item_id: int,
    context: Auth,
    offset: int = 0,
    limit: int = 50,
    sort: str | None = None,
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context, "conversions", page.offset, page.limit, sort, {"item_id": item_id}
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/items/{item_id}/conversions/{row_id}")
def get_conversions(item_id: int, row_id: int, context: Auth):
    return {"data": service.detail(context, "conversions", row_id, parent=item_id)}


@router.post("/items/{item_id}/conversions", status_code=201)
def post_conversions(
    item_id: int,
    payload: schema.ConversionCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(
        context, "conversions", payload.model_dump(), key, parent=item_id
    )
    return {"data": result}


@router.patch("/items/{item_id}/conversions/{row_id}")
def patch_conversions(
    item_id: int,
    row_id: int,
    payload: schema.ConversionUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    result = service.mutate(
        context,
        "conversions",
        payload.model_dump(exclude_unset=True),
        key,
        row_id=row_id,
        parent=item_id,
    )
    return {"data": result}


@router.delete("/items/{item_id}/conversions/{row_id}", status_code=204)
def delete_conversions(
    item_id: int,
    row_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    service.mutate(
        context, "conversions", {}, key, row_id=row_id, parent=item_id, deleting=True
    )
    return Response(status_code=204)


@router.get("/accounts")
def list_accounts(
    context: Auth, offset: int = 0, limit: int = 50, sort: str | None = None
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context, "accounts", page.offset, page.limit, sort, {}
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/accounts/{row_id}")
def get_accounts(row_id: int, context: Auth):
    return {"data": service.detail(context, "accounts", row_id)}


@router.get("/posting-rules")
def list_posting_rules(
    context: Auth, offset: int = 0, limit: int = 50, sort: str | None = None
):
    page = Page(offset, limit).checked()
    data, total = service.listing(
        context, "posting-rules", page.offset, page.limit, sort, {}
    )
    return {
        "data": data,
        "page": {"offset": page.offset, "limit": page.limit, "total": total},
    }


@router.get("/posting-rules/{row_id}")
def get_posting_rules(row_id: int, context: Auth):
    return {"data": service.detail(context, "posting-rules", row_id)}
