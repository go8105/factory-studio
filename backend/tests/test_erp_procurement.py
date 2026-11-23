"""DSN-11 1d 구매: 요청 → 발주 → 입고 진행 파생 → 발주 입고 매입."""

from decimal import Decimal
from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


def _headers(data):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": uuid4().hex}


def _call(client, data, method, path, body=None):
    return client.request(method, f"{BASE}{path}", json=body, headers=_headers(data))


def _row(client, path, field, value):
    rows = client.get(f"{BASE}{path}?limit=200").json()["data"]
    return next(r for r in rows if r[field] == value)


@pytest.fixture
def erp(guest_space):
    return guest_space[0], guest_space[1]


def _supplier(client):
    return _row(client, "/partners", "partnerCode", "V-001")["id"]


def _item(client, code):
    return _row(client, "/items", "itemCode", code)["id"]


def _new_order(client, data, **over):
    body = {
        "partnerId": _supplier(client),
        "orderedOn": "2026-09-24",
        **over,
    }
    response = _call(client, data, "POST", "/purchase-orders", body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_request_runs_draft_confirm_then_order(erp):
    client, data = erp
    request = _call(
        client, data, "POST", "/purchase-requests", {"requestedOn": "2026-09-24"}
    ).json()["data"]
    assert request["status"] == "draft" and request["requestNo"].startswith("PR-")
    lines = _call(
        client,
        data,
        "PUT",
        f"/purchase-requests/{request['id']}/lines",
        {"lines": [{"itemId": _item(client, "RM-PBT"), "quantity": "50"}]},
    )
    assert lines.status_code == 200, lines.text
    # 단위를 비우면 품목 기준 단위를 쓴다.
    assert lines.json()["data"]["lines"][0]["unit"] == "KG"
    confirmed = _call(
        client, data, "POST", f"/purchase-requests/{request['id']}/confirm"
    )
    assert confirmed.json()["data"]["status"] == "confirmed"


def test_empty_request_is_not_confirmed(erp):
    client, data = erp
    request = _call(
        client, data, "POST", "/purchase-requests", {"requestedOn": "2026-09-24"}
    ).json()["data"]
    r = _call(client, data, "POST", f"/purchase-requests/{request['id']}/confirm")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "EMPTY_REQUEST"


def test_order_takes_the_purchase_price_when_the_line_has_none(erp):
    client, data = erp
    order = _new_order(client, data)
    lines = _call(
        client,
        data,
        "PUT",
        f"/purchase-orders/{order['id']}/lines",
        {"lines": [{"itemId": _item(client, "RM-PBT"), "quantity": "10"}]},
    )
    assert lines.status_code == 200, lines.text
    # V-001은 PG-BUY-A 구매 그룹에 속하고 RM-PBT 그룹 단가는 3350이다.
    assert lines.json()["data"]["lines"][0]["unitPrice"] == "3350.0000"
    assert lines.json()["data"]["totalAmount"] == "36850.00"


def test_order_pulls_the_pending_lines_of_a_confirmed_request(erp):
    client, data = erp
    request = _call(
        client, data, "POST", "/purchase-requests", {"requestedOn": "2026-09-24"}
    ).json()["data"]
    _call(
        client,
        data,
        "PUT",
        f"/purchase-requests/{request['id']}/lines",
        {"lines": [{"itemId": _item(client, "RM-PBT"), "quantity": "40"}]},
    )
    _call(client, data, "POST", f"/purchase-requests/{request['id']}/confirm")
    order = _new_order(client, data)
    loaded = _call(
        client,
        data,
        "POST",
        f"/purchase-orders/{order['id']}/load-request",
        {"requestId": request["id"]},
    )
    assert loaded.status_code == 200, loaded.text
    line = loaded.json()["data"]["lines"][0]
    assert line["quantity"] == "40.000" and line["purchaseRequestLineId"] is not None
    confirmed = _call(client, data, "POST", f"/purchase-orders/{order['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    # 발주가 확정되면 그 요청은 발주 완료로 넘어간다.
    assert (
        _row(client, "/purchase-requests", "id", request["id"])["status"] == "ordered"
    )


def test_a_draft_request_cannot_be_pulled(erp):
    client, data = erp
    request = _call(
        client, data, "POST", "/purchase-requests", {"requestedOn": "2026-09-24"}
    ).json()["data"]
    order = _new_order(client, data)
    r = _call(
        client,
        data,
        "POST",
        f"/purchase-orders/{order['id']}/load-request",
        {"requestId": request["id"]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "REQUEST_NOT_CONFIRMED"


def test_receipt_progress_comes_from_wms_and_is_not_stored(erp):
    client, _ = erp
    order = _row(client, "/purchase-orders", "poNo", "PO-SEED-0001")
    # 시드 입고는 100 중 95만 정상 입고다(3 격리·2 부족).
    assert order["receipt"]["state"] == "PARTIAL"
    assert order["receipt"]["receivedQty"] == "95.000"
    assert order["receipt"]["lines"][0]["openQty"] == "5.000"


def test_a_draft_order_has_no_receipt_progress(erp):
    client, data = erp
    order = _new_order(client, data)
    assert order["receipt"]["state"] == "NONE"


def test_an_order_with_receipts_is_not_cancelled(erp):
    client, data = erp
    order = _row(client, "/purchase-orders", "poNo", "PO-SEED-0001")
    r = _call(
        client,
        data,
        "POST",
        f"/purchase-orders/{order['id']}/cancel",
        {"reason": "테스트"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "RECEIPT_EXISTS"


def test_po_receipt_invoice_takes_accepted_qty_at_order_price(erp):
    client, data = erp
    order = _row(client, "/purchase-orders", "poNo", "PO-SEED-0001")
    invoice = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-PO-1",
            "partnerId": order["partnerId"],
            "invoiceDate": "2026-09-24",
            "invoiceKind": "PO_RECEIPT",
            "purchaseOrderId": order["id"],
            "sourceRef": _seed_notice_no(client),
        },
    )
    assert invoice.status_code == 201, invoice.text
    loaded = _call(
        client, data, "POST", f"/purchase-invoices/{invoice.json()['data']['id']}/load"
    )
    assert loaded.status_code == 200, loaded.text
    line = loaded.json()["data"]["lines"][0]
    # 정상 입고 95 × 발주 단가 3500. 격리 3은 매입하지 않는다.
    assert (line["quantity"], line["unitPrice"]) == ("95.000", "3500.0000")
    assert loaded.json()["data"]["supplyAmount"] == "332500.00"


def _seed_notice_no(client) -> str:
    """WMS가 이 발주를 가리키며 검수까지 마친 입고 번호."""
    body = client.get("/api/v1/wms/inbound-notices?pageSize=100").json()["data"]
    return next(
        r["noticeNo"]
        for r in body["rows"]
        if r["status"] == "INSPECTED" and r["partnerRef"] == "PO-SEED-0001"
    )


def test_po_receipt_invoice_needs_a_confirmed_order(erp):
    client, data = erp
    r = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-PO-2",
            "partnerId": _supplier(client),
            "invoiceDate": "2026-09-24",
            "invoiceKind": "PO_RECEIPT",
            "sourceRef": "IN-TEST",
        },
    )
    assert r.status_code == 400
    assert "purchaseOrderId" in r.json()["error"]["details"]["fields"]


def test_subcontract_invoice_needs_a_source_ref(erp):
    client, data = erp
    r = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-SC-1",
            "partnerId": _supplier(client),
            "invoiceDate": "2026-09-24",
            "invoiceKind": "SUBCONTRACT",
        },
    )
    assert r.status_code == 400
    assert "sourceRef" in r.json()["error"]["details"]["fields"]


def test_direct_invoice_has_no_source(erp):
    client, data = erp
    r = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-D-1",
            "partnerId": _supplier(client),
            "invoiceDate": "2026-09-24",
        },
    )
    assert r.status_code == 201
    assert r.json()["data"]["invoiceKind"] == "DIRECT"
    loaded = _call(
        client, data, "POST", f"/purchase-invoices/{r.json()['data']['id']}/load"
    )
    assert loaded.status_code == 409
    assert loaded.json()["error"]["details"]["reason"] == "NO_SOURCE"


def test_purchase_status_pairs_orders_with_receipts(erp):
    client, _ = erp
    body = client.get(
        f"{BASE}/purchase-status?date_from=2020-01-01&date_to=2030-12-31"
    ).json()["data"]
    row = next(r for r in body["orders"] if r["poNo"] == "PO-SEED-0001")
    assert row["receiptState"] == "PARTIAL" and row["invoicedAmount"] == "0"
    assert body["receiptKnown"] is True


def test_stock_status_reads_wms(erp):
    client, _ = erp
    body = client.get(f"{BASE}/stock-status").json()["data"]
    assert body["available"] is True
    row = next(r for r in body["rows"] if r["itemCode"] == "RM-PBT")
    assert row["linked"] is True and row["qtyOnHand"] is not None
    # ERP에만 있는 품목은 수량 0이 아니라 '연결 안 됨'이다.
    assert any(not r["linked"] and r["qtyOnHand"] is None for r in body["rows"])


def test_stock_status_does_not_judge_without_a_safety_stock(erp):
    """기준이 없으면 '충분'이 아니라 '판단 안 함'이다(DSN-01 S2와 같은 태도)."""
    client, _ = erp
    rows = client.get(f"{BASE}/stock-status").json()["data"]["rows"]
    unset = [r for r in rows if r["linked"] and r["safetyStock"] is None]
    assert unset and all(r["isShort"] is None for r in unset)


def test_sales_status_counts_shipped_against_each_order_line(erp):
    """E-21은 테스트가 없어 1d 내내 500이었다(출하지시 명세에 item_id가 없다)."""
    client, _ = erp
    body = client.get(
        f"{BASE}/sales-status?date_from=2020-01-01&date_to=2030-12-31"
    ).json()["data"]
    assert body["orders"], body
    shipped = [r for r in body["orders"] if Decimal(r["shippedQty"]) > 0]
    assert shipped, body["orders"]
    for row in body["orders"]:
        assert Decimal(row["openQty"]) == Decimal(row["orderQty"]) - Decimal(
            row["shippedQty"]
        )
        # 출하는 수주 수량을 넘지 않는다(명세를 섞어 세면 넘는다).
        assert Decimal(row["shippedQty"]) <= Decimal(row["orderQty"])
    assert Decimal(body["supplyTotal"]) > 0
