from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Response

from fs.common.auth import AuthContext, require_csrf, resolve_auth
from fs.common.errors import ApiError
from fs.common.page import Page
from fs.erp import (
    journal,
    purchases,
    receipts,
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


# ---- FS-019g 분개 미리보기 (저장 없음, GET만) ----
@router.get("/journal-preview")
def get_journal_preview(
    context: Auth,
    kind: Literal["SALES", "PURCHASE", "RECEIPT", "PAYMENT"],
    source_id: int | None = Query(None, alias="sourceId", gt=0),
    apply_id: int | None = Query(None, alias="applyId", gt=0),
):
    # 매출·매입은 원천 id, 수금·지급은 소명 행 id(소명 1행 = 분개 1세트)
    needed, field = (
        (source_id, "sourceId")
        if kind in ("SALES", "PURCHASE")
        else (apply_id, "applyId")
    )
    if needed is None:
        raise service.invalid(field, f"{kind}는 {field}가 필요합니다.")
    return {"data": journal.preview(context, kind, needed)}
