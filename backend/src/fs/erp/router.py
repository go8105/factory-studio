from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.erp import (
    dashboard,
    expenses,
    journals,
    overview,
    procurement,
    purchases,
    receipts,
    returns,
    revenue,
    sales,
    schema,
    service,
    shipping,
)

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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
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
    context: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = None,
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
    context: Auth,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    sort: str | None = None,
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


# ---- DSN-11 1c 기초등록: 같은 모양의 기준정보 다섯은 한 틀에서 만든다 ----
def master(path: str, resource: str, create, update, active: bool = True):
    """목록·상세·등록·수정·삭제 5개 경로를 등록한다. 손으로 25벌 적지 않는다."""

    def register(name, method, url, handler, **kwargs):
        handler.__name__ = f"{name}_{resource.replace('-', '_')}"
        router.add_api_route(url, handler, methods=[method], **kwargs)

    def list_rows(
        context: Auth,
        offset: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=200),
        sort: str | None = None,
        is_active: bool | None = Query(None, alias="active"),
    ):
        page = Page(offset, limit).checked()
        data, total = service.listing(
            context,
            resource,
            page.offset,
            page.limit,
            sort,
            {"is_active": is_active} if active else {},
        )
        return {
            "data": data,
            "page": {"offset": page.offset, "limit": page.limit, "total": total},
        }

    def get_row(row_id: int, context: Auth):
        return {"data": service.detail(context, resource, row_id)}

    def post_row(
        payload: create,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {"data": service.mutate(context, resource, payload.model_dump(), key)}

    def patch_row(
        row_id: int,
        payload: update,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {
            "data": service.mutate(
                context,
                resource,
                payload.model_dump(exclude_unset=True),
                key,
                row_id=row_id,
            )
        }

    def delete_row(
        row_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        service.mutate(context, resource, {}, key, row_id=row_id, deleting=True)
        return Response(status_code=204)

    register("list", "GET", path, list_rows)
    register("get", "GET", f"{path}/{{row_id}}", get_row)
    register("post", "POST", path, post_row, status_code=201)
    register("patch", "PATCH", f"{path}/{{row_id}}", patch_row)
    register("delete", "DELETE", f"{path}/{{row_id}}", delete_row, status_code=204)


master("/departments", "departments", schema.DepartmentCreate, schema.DepartmentUpdate)
master("/employees", "employees", schema.EmployeeCreate, schema.EmployeeUpdate)
master("/projects", "projects", schema.ProjectCreate, schema.ProjectUpdate)
master(
    "/price-groups", "price-groups", schema.PriceGroupCreate, schema.PriceGroupUpdate
)
master(
    "/group-prices",
    "group-prices",
    schema.GroupPriceCreate,
    schema.GroupPriceUpdate,
    active=False,
)


# 계정은 더하고 사용중단한다. 삭제는 service가 405로 막는다(지난 전표가 계정을 잃는다).
@router.post("/accounts", status_code=201)
def post_accounts(
    payload: schema.AccountCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": service.mutate(context, "accounts", payload.model_dump(), key)}


@router.patch("/accounts/{row_id}")
def patch_accounts(
    row_id: int,
    payload: schema.AccountUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": service.mutate(
            context,
            "accounts",
            payload.model_dump(exclude_unset=True),
            key,
            row_id=row_id,
        )
    }


# ---- FS-019b 영업: 견적·판매계획·수주 (목록은 페이지 없이 전체) ----
def _json(payload, nullable=frozenset()):
    values = payload.model_dump(mode="json", exclude_unset=True)
    for field, value in values.items():
        if value is None and field not in nullable:
            raise service.invalid(field, "null로 비울 수 없습니다.")
    return values


@router.get("/quotations")
def list_quotations(context: Auth):
    return {"data": sales.list_quotations(context)}


@router.get("/quotations/{quote_id}/revisions")
def list_quotation_revisions(quote_id: int, context: Auth):
    return {"data": sales.quotation_revisions(context, quote_id)}


@router.post("/quotations", status_code=201)
def post_quotation(
    payload: schema.QuotationCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": sales.create_quotation(context, payload.model_dump(mode="json"), key)
    }


@router.patch("/quotations/{quote_id}")
def patch_quotation(
    quote_id: int,
    payload: schema.QuotationUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = _json(payload, frozenset({"valid_until", "remark"}))
    return {"data": sales.update_quotation(context, quote_id, values, key)}


@router.put("/quotations/{quote_id}/lines")
def put_quotation_lines(
    quote_id: int,
    payload: schema.QuotationLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": sales.set_quotation_lines(context, quote_id, lines, key)}


@router.post("/quotations/{quote_id}/status")
def post_quotation_status(
    quote_id: int,
    payload: schema.QuotationStatus,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": sales.change_quotation_status(
            context, quote_id, payload.status, payload.reason, key
        )
    }


@router.post("/quotations/{quote_id}/revise", status_code=201)
def post_quotation_revise(
    quote_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.revise_quotation(context, quote_id, key)}


@router.post("/quotations/{quote_id}/convert", status_code=201)
def post_quotation_convert(
    quote_id: int,
    payload: schema.QuotationConvert,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": sales.convert_quotation(context, quote_id, values, key)}


@router.get("/sales-plans")
def list_sales_plans(context: Auth):
    return {"data": sales.list_plans(context)}


@router.post("/sales-plans", status_code=201)
def post_sales_plan(
    payload: schema.SalesPlanCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.create_plan(context, payload.model_dump(mode="json"), key)}


@router.patch("/sales-plans/{plan_id}")
def patch_sales_plan(
    plan_id: int,
    payload: schema.SalesPlanUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.update_plan(context, plan_id, _json(payload), key)}


@router.put("/sales-plans/{plan_id}/lines")
def put_sales_plan_lines(
    plan_id: int,
    payload: schema.SalesPlanLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": sales.set_plan_lines(context, plan_id, lines, key)}


@router.post("/sales-plans/{plan_id}/confirm")
def post_sales_plan_confirm(
    plan_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.confirm_plan(context, plan_id, key)}


@router.delete("/sales-plans/{plan_id}", status_code=204)
def delete_sales_plan(
    plan_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    sales.delete_plan(context, plan_id, key)
    return Response(status_code=204)


@router.get("/sales-orders")
def list_sales_orders(context: Auth):
    return {"data": sales.list_orders(context)}


@router.post("/sales-orders", status_code=201)
def post_sales_order(
    payload: schema.SalesOrderCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.create_order(context, payload.model_dump(mode="json"), key)}


@router.patch("/sales-orders/{order_id}")
def patch_sales_order(
    order_id: int,
    payload: schema.SalesOrderUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.update_order(context, order_id, _json(payload), key)}


@router.post("/sales-orders/{order_id}/cancel")
def post_sales_order_cancel(
    order_id: int, context: Auth, idempotency_key: Key = None, x_csrf_token: Csrf = None
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": sales.cancel_order(context, order_id, key)}


# ---- FS-019c 출하지시·출하 ----
@router.get("/shipment-orders")
def list_shipment_orders(context: Auth):
    return {"data": shipping.list_ship_orders(context)}


@router.post("/shipment-orders", status_code=201)
def post_shipment_order(
    payload: schema.ShipOrderCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": shipping.create_ship_order(context, values, key)}


@router.post("/shipment-orders/{ship_order_id}/cancel")
def post_shipment_order_cancel(
    ship_order_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": shipping.cancel_ship_order(context, ship_order_id, payload.reason, key)
    }


@router.get("/shipments")
def list_shipments(context: Auth):
    return {"data": shipping.list_shipments(context)}


@router.post("/shipments", status_code=201)
def post_shipment(
    payload: schema.ShipmentCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": shipping.confirm_shipment(context, values, key)}


# ---- FS-019d 매출·세금계산서 ----
@router.get("/sales-records")
def list_sales_records(context: Auth):
    return {"data": revenue.list_sales(context)}


@router.post("/sales-records/{record_id}/cancel")
def post_sales_record_cancel(
    record_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": revenue.cancel_sale(context, record_id, payload.reason, key)}


@router.get("/tax-invoices")
def list_tax_invoices(context: Auth):
    return {"data": revenue.list_invoices(context)}


@router.post("/tax-invoices", status_code=201)
def post_tax_invoice(
    payload: schema.TaxInvoiceCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": revenue.create_invoice(context, payload.sales_record_id, key)}


@router.post("/tax-invoices/{invoice_id}/issue")
def post_tax_invoice_issue(
    invoice_id: int,
    payload: schema.TaxInvoiceIssue,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": revenue.issue_invoice(context, invoice_id, values, key)}


# ---- FS-019e·019f 채권·채무와 수금·지급 소명 (같은 규칙, receipts.Side로 구분) ----
def _settlement_routes(
    side, open_path, money_path, create_schema, update_schema, lines
):
    @router.get(open_path, name=f"list_{side.open_item}s")
    def list_open(
        context: Auth,
        partner_id: int | None = Query(None, alias="partnerId", gt=0),
        status: Literal["OPEN", "PARTIAL", "CLOSED"] | None = None,
    ):
        return {"data": receipts.list_open_items(side, context, partner_id, status)}

    @router.get(money_path, name=f"list_{side.money}s")
    def list_money(context: Auth):
        return {"data": receipts.list_monies(side, context)}

    @router.post(money_path, status_code=201, name=f"post_{side.money}")
    def post_money(
        payload: create_schema,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        values = payload.model_dump(mode="json")
        return {"data": receipts.create_money(side, context, values, key)}

    @router.patch(money_path + "/{money_id}", name=f"patch_{side.money}")
    def patch_money(
        money_id: int,
        payload: update_schema,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        values = _json(payload)
        return {"data": receipts.update_money(side, context, money_id, values, key)}

    @router.post(money_path + "/{money_id}/confirm", name=f"confirm_{side.money}")
    def confirm_money(
        money_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {"data": receipts.confirm_money(side, context, money_id, key)}

    @router.delete(
        money_path + "/{money_id}", status_code=204, name=f"delete_{side.money}"
    )
    def delete_money(
        money_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        receipts.delete_money(side, context, money_id, key)
        return Response(status_code=204)

    @router.post(
        money_path + "/{money_id}/applications",
        status_code=201,
        name=f"post_{side.apply}",
    )
    def post_applications(
        money_id: int,
        payload: lines,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        rows = payload.model_dump(mode="json")["lines"]
        return {"data": receipts.add_applications(side, context, money_id, rows, key)}

    @router.delete(
        money_path + "/{money_id}/applications/{apply_id}",
        name=f"delete_{side.apply}",
    )
    def delete_application(
        money_id: int,
        apply_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {
            "data": receipts.delete_application(side, context, money_id, apply_id, key)
        }

    @router.get(money_path + "/{money_id}/fifo-suggestion", name=f"fifo_{side.money}")
    def fifo(money_id: int, context: Auth):
        return {"data": receipts.fifo_suggestion(side, context, money_id)}


_settlement_routes(
    receipts.RECEIVABLE,
    "/receivables",
    "/receipts",
    schema.ReceiptCreate,
    schema.ReceiptUpdate,
    schema.Applications,
)
_settlement_routes(
    receipts.PAYABLE,
    "/payables",
    "/payments",
    schema.PaymentCreate,
    schema.PaymentUpdate,
    schema.PaymentApplications,
)


# ---- FS-019f 매입 전표 ----
@router.get("/purchase-invoices")
def list_purchase_invoices(context: Auth):
    return {"data": purchases.list_invoices(context)}


@router.post("/purchase-invoices", status_code=201)
def post_purchase_invoice(
    payload: schema.PurchaseInvoiceCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": purchases.create_invoice(context, values, key)}


@router.patch("/purchase-invoices/{invoice_id}")
def patch_purchase_invoice(
    invoice_id: int,
    payload: schema.PurchaseInvoiceUpdate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = _json(payload, frozenset({"due_date"}))
    return {"data": purchases.update_invoice(context, invoice_id, values, key)}


@router.put("/purchase-invoices/{invoice_id}/lines")
def put_purchase_lines(
    invoice_id: int,
    payload: schema.PurchaseLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": purchases.set_lines(context, invoice_id, lines, key)}


@router.post("/purchase-invoices/{invoice_id}/confirm")
def post_purchase_confirm(
    invoice_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": purchases.confirm_invoice(context, invoice_id, key)}


@router.post("/purchase-invoices/{invoice_id}/cancel")
def post_purchase_cancel(
    invoice_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": purchases.cancel_invoice(context, invoice_id, payload.reason, key)}


@router.delete("/purchase-invoices/{invoice_id}", status_code=204)
def delete_purchase_invoice(
    invoice_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    purchases.delete_invoice(context, invoice_id, key)
    return Response(status_code=204)


# ---- DSN-11 1e 회계: E-30 전표 · E-31 미반영 · E-29 지출결의 ----
# E-14 분개 미리보기는 폐지했다. 이제 전표는 업무 확정과 함께 **실제로 생긴다**(posting.py).
@router.get("/journal-entries")
def list_journal_entries(
    context: Auth,
    month: str | None = None,
    status: Literal["draft", "confirmed", "reversed"] | None = None,
):
    return {"data": journals.list_entries(context, month, status)}


@router.get("/journal-entries/for-source")
def get_entry_for_source(
    context: Auth,
    source_kind: Annotated[str, Query(alias="sourceKind", max_length=30)],
    source_id: Annotated[int, Query(alias="sourceId", gt=0)],
):
    return {"data": journals.entry_for_source(context, source_kind, source_id)}


@router.post("/journal-entries", status_code=201)
def post_journal_entry(
    payload: schema.JournalEntryCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": journals.create_entry(context, values, key)}


@router.put("/journal-entries/{entry_id}/lines")
def put_journal_lines(
    entry_id: int,
    payload: schema.JournalLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": journals.set_lines(context, entry_id, lines, key)}


@router.post("/journal-entries/{entry_id}/confirm")
def post_journal_confirm(
    entry_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": journals.confirm_entry(context, entry_id, key)}


@router.post("/journal-entries/{entry_id}/reverse")
def post_journal_reverse(
    entry_id: int,
    payload: schema.ReverseIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": journals.reverse_entry(context, entry_id, payload.reason, key)}


@router.delete("/journal-entries/{entry_id}", status_code=204)
def delete_journal_entry(
    entry_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    journals.delete_entry(context, entry_id, key)
    return Response(status_code=204)


@router.get("/unposted")
def list_unposted(context: Auth):
    return {"data": journals.list_pending(context)}


@router.post("/unposted/post")
def post_unposted(
    payload: schema.PendingPost,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    targets = payload.model_dump(mode="json")["targets"]
    return {"data": journals.post_pending(context, targets, key)}


@router.get("/expense-claims")
def list_expense_claims(context: Auth):
    return {"data": expenses.list_claims(context)}


@router.post("/expense-claims", status_code=201)
def post_expense_claim(
    payload: schema.ExpenseClaimCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": expenses.create_claim(context, values, key)}


@router.put("/expense-claims/{claim_id}/lines")
def put_expense_lines(
    claim_id: int,
    payload: schema.ExpenseLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": expenses.set_lines(context, claim_id, lines, key)}


@router.post("/expense-claims/{claim_id}/confirm")
def post_expense_confirm(
    claim_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": expenses.confirm_claim(context, claim_id, key)}


@router.post("/expense-claims/{claim_id}/cancel")
def post_expense_cancel(
    claim_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": expenses.cancel_claim(context, claim_id, payload.reason, key)}


@router.delete("/expense-claims/{claim_id}", status_code=204)
def delete_expense_claim(
    claim_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    expenses.delete_claim(context, claim_id, key)
    return Response(status_code=204)


# ---- FS-019h 대시보드 ----
@router.get("/dashboard")
def get_dashboard(context: Auth, month: str | None = None):
    return {"data": dashboard.dashboard(context, month)}


@router.get("/purchase-invoices/{invoice_id}/gw-approval")
def get_purchase_approval(invoice_id: int, context: Auth):
    return {"data": purchases.approval_badge(context, invoice_id)}


# ---- DSN-11 1d 구매: E-22 요청 · E-23 발주 ----
@router.get("/purchase-requests")
def list_purchase_requests(context: Auth):
    return {"data": procurement.list_requests(context)}


@router.post("/purchase-requests", status_code=201)
def post_purchase_request(
    payload: schema.PurchaseRequestCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": procurement.create_request(context, values, key)}


@router.put("/purchase-requests/{request_id}/lines")
def put_request_lines(
    request_id: int,
    payload: schema.RequestLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": procurement.set_request_lines(context, request_id, lines, key)}


@router.post("/purchase-requests/{request_id}/confirm")
def post_request_confirm(
    request_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": procurement.confirm_request(context, request_id, key)}


@router.post("/purchase-requests/{request_id}/cancel")
def post_request_cancel(
    request_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": procurement.cancel_request(context, request_id, payload.reason, key)
    }


@router.delete("/purchase-requests/{request_id}", status_code=204)
def delete_purchase_request(
    request_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    procurement.delete_request(context, request_id, key)
    return Response(status_code=204)


@router.get("/purchase-orders")
def list_purchase_orders(context: Auth):
    return {"data": procurement.list_orders(context)}


@router.post("/purchase-orders", status_code=201)
def post_purchase_order(
    payload: schema.PurchaseOrderCreate,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    values = payload.model_dump(mode="json")
    return {"data": procurement.create_order(context, values, key)}


@router.put("/purchase-orders/{order_id}/lines")
def put_order_lines(
    order_id: int,
    payload: schema.PurchaseOrderLines,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    lines = payload.model_dump(mode="json")["lines"]
    return {"data": procurement.set_order_lines(context, order_id, lines, key)}


@router.post("/purchase-orders/{order_id}/load-request")
def post_order_load_request(
    order_id: int,
    payload: schema.LoadRequestIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {
        "data": procurement.load_request(context, order_id, payload.request_id, key)
    }


@router.post("/purchase-orders/{order_id}/confirm")
def post_order_confirm(
    order_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": procurement.confirm_order(context, order_id, key)}


@router.post("/purchase-orders/{order_id}/close")
def post_order_close(
    order_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": procurement.close_order(context, order_id, key)}


@router.post("/purchase-orders/{order_id}/cancel")
def post_order_cancel(
    order_id: int,
    payload: schema.CancelIn,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": procurement.cancel_order(context, order_id, payload.reason, key)}


@router.delete("/purchase-orders/{order_id}", status_code=204)
def delete_purchase_order(
    order_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    procurement.delete_order(context, order_id, key)
    return Response(status_code=204)


# ---- DSN-11 1d 반품: E-20 판매 · E-24 구매 ----
def returns_routes(path: str, kind, create_model) -> None:
    """판매 반품과 구매 반품은 규칙이 같다. 경로만 둘로 낸다."""

    def register(name, method, url, handler, **kwargs):
        handler.__name__ = f"{name}_{kind.table}"
        router.add_api_route(url, handler, methods=[method], **kwargs)

    def list_rows(context: Auth):
        return {"data": returns.listing(context, kind)}

    def post_row(
        payload: create_model,  # type: ignore[valid-type]
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        values = payload.model_dump(mode="json")
        return {"data": returns.create(context, kind, values, key)}

    def put_lines(
        return_id: int,
        payload: schema.ReturnLines,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        lines = payload.model_dump(mode="json")["lines"]
        return {"data": returns.set_lines(context, kind, return_id, lines, key)}

    def post_confirm(
        return_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {"data": returns.confirm(context, kind, return_id, key)}

    def post_cancel(
        return_id: int,
        payload: schema.CancelIn,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        return {"data": returns.cancel(context, kind, return_id, payload.reason, key)}

    def delete_row(
        return_id: int,
        context: Auth,
        idempotency_key: Key = None,
        x_csrf_token: Csrf = None,
    ):
        key = mutation(context, x_csrf_token, idempotency_key)
        returns.delete(context, kind, return_id, key)
        return Response(status_code=204)

    def get_returnable(source_id: int, context: Auth):
        return {"data": returns.returnable(context, kind, source_id)}

    register("list", "GET", path, list_rows)
    register("post", "POST", path, post_row, status_code=201)
    register("lines", "PUT", f"{path}/{{return_id}}/lines", put_lines)
    register("confirm", "POST", f"{path}/{{return_id}}/confirm", post_confirm)
    register("cancel", "POST", f"{path}/{{return_id}}/cancel", post_cancel)
    register("delete", "DELETE", f"{path}/{{return_id}}", delete_row, status_code=204)
    register("returnable", "GET", f"{path}-available/{{source_id}}", get_returnable)


returns_routes("/sales-returns", returns.SALES, schema.SalesReturnCreate)
returns_routes("/purchase-returns", returns.PURCHASE, schema.PurchaseReturnCreate)


# ---- DSN-11 1d 현황: E-21 영업 · E-25 구매 · E-26 재고 ----
@router.get("/sales-status")
def get_sales_status(context: Auth, date_from: date, date_to: date):
    return {"data": overview.sales_status(context, date_from, date_to)}


@router.get("/purchase-status")
def get_purchase_status(context: Auth, date_from: date, date_to: date):
    return {"data": overview.purchase_status(context, date_from, date_to)}


@router.get("/stock-status")
def get_stock_status(context: Auth):
    return {"data": overview.stock_status(context)}


@router.post("/purchase-invoices/{invoice_id}/load")
def post_invoice_load(
    invoice_id: int,
    context: Auth,
    idempotency_key: Key = None,
    x_csrf_token: Csrf = None,
):
    key = mutation(context, x_csrf_token, idempotency_key)
    return {"data": purchases.load_lines(context, invoice_id, key)}
