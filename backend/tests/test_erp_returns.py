"""DSN-11 1d 반품: 원 문서 참조·수량 한도·확정 시 채권/채무 조정."""

from decimal import Decimal
from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


def _headers(data):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": uuid4().hex}


def _call(client, data, method, path, body=None):
    return client.request(method, f"{BASE}{path}", json=body, headers=_headers(data))


def _get(client, path):
    return client.get(f"{BASE}{path}").json()["data"]


@pytest.fixture
def erp(guest_space):
    return guest_space[0], guest_space[1]


def _receivable(client, shipment_no: str):
    return next(
        r for r in _get(client, "/receivables") if r["shipmentNo"] == shipment_no
    )


def _new_sales_return(client, data, shipment_no="SH-0004"):
    item = _receivable(client, shipment_no)
    body = {
        "partnerId": item["partnerId"],
        "salesRecordId": item["salesRecordId"],
        "returnedOn": "2026-09-24",
        "reason": "합성 반품 사유",
    }
    response = _call(client, data, "POST", "/sales-returns", body)
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_seeded_return_already_lowered_the_receivable_balance(erp):
    client, _ = erp
    item = _receivable(client, "SH-0002")
    # 원금 5,071,440 − 소명 0 − 반품 조정 132,000.
    assert item["amount"] == "5071440.00"
    assert item["adjustedAmount"] == "132000.00"
    assert item["balance"] == "4939440.00"


def test_return_quantity_cannot_exceed_what_was_shipped(erp):
    client, data = erp
    head = _new_sales_return(client, data)
    available = _get(client, f"/sales-returns-available/{head['salesRecordId']}")
    row = available[0]
    too_many = str(Decimal(row["returnableQty"]) + 1)
    r = _call(
        client,
        data,
        "PUT",
        f"/sales-returns/{head['id']}/lines",
        {"lines": [{"itemId": row["itemId"], "quantity": too_many}]},
    )
    assert r.status_code == 400
    assert "반품할 수 있는 수량은" in r.json()["error"]["details"]["fields"]["lines"]


def test_already_returned_quantity_is_subtracted(erp):
    client, _ = erp
    record = _receivable(client, "SH-0002")["salesRecordId"]
    available = _get(client, f"/sales-returns-available/{record}")
    # 출하 3,842 중 100을 이미 반품했다.
    assert available[0]["returnableQty"] == "3742.000"


def test_confirm_writes_a_return_credit_and_moves_the_balance(erp):
    client, data = erp
    head = _new_sales_return(client, data)
    available = _get(client, f"/sales-returns-available/{head['salesRecordId']}")
    before = _receivable(client, "SH-0004")["balance"]
    lines = _call(
        client,
        data,
        "PUT",
        f"/sales-returns/{head['id']}/lines",
        {"lines": [{"itemId": available[0]["itemId"], "quantity": "10"}]},
    )
    assert lines.status_code == 200, lines.text
    total = Decimal(lines.json()["data"]["totalAmount"])
    confirmed = _call(client, data, "POST", f"/sales-returns/{head['id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["data"]["status"] == "confirmed"
    after = _receivable(client, "SH-0004")["balance"]
    assert Decimal(before) - Decimal(after) == total


def test_cancel_takes_the_credit_back(erp):
    client, data = erp
    head = _new_sales_return(client, data)
    available = _get(client, f"/sales-returns-available/{head['salesRecordId']}")
    before = _receivable(client, "SH-0004")["balance"]
    _call(
        client,
        data,
        "PUT",
        f"/sales-returns/{head['id']}/lines",
        {"lines": [{"itemId": available[0]["itemId"], "quantity": "5"}]},
    )
    _call(client, data, "POST", f"/sales-returns/{head['id']}/confirm")
    cancelled = _call(
        client,
        data,
        "POST",
        f"/sales-returns/{head['id']}/cancel",
        {"reason": "오입력"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert _receivable(client, "SH-0004")["balance"] == before


def test_a_return_over_the_remaining_balance_is_refused(erp):
    client, data = erp
    head = _new_sales_return(client, data, "SH-0003")
    available = _get(client, f"/sales-returns-available/{head['salesRecordId']}")
    # SH-0003은 전액 수금 소명이 끝났다. 반품할 잔액이 없다.
    _call(
        client,
        data,
        "PUT",
        f"/sales-returns/{head['id']}/lines",
        {"lines": [{"itemId": available[0]["itemId"], "quantity": "1"}]},
    )
    r = _call(client, data, "POST", f"/sales-returns/{head['id']}/confirm")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "OVER_BALANCE"


def test_a_return_needs_the_partner_of_the_source(erp):
    client, data = erp
    item = _receivable(client, "SH-0004")
    other = next(
        p
        for p in _get(client, "/partners")
        if p["id"] != item["partnerId"] and p["partnerKind"] in ("CUSTOMER", "BOTH")
    )
    r = _call(
        client,
        data,
        "POST",
        "/sales-returns",
        {
            "partnerId": other["id"],
            "salesRecordId": item["salesRecordId"],
            "returnedOn": "2026-09-24",
            "reason": "거래처 불일치",
        },
    )
    assert r.status_code == 400
    assert "partnerId" in r.json()["error"]["details"]["fields"]


def test_purchase_return_lowers_the_payable(erp):
    client, _ = erp
    payable = next(p for p in _get(client, "/payables") if p["invoiceNo"] == "PI-0003")
    assert payable["adjustedAmount"] == "38500.00"
    assert Decimal(payable["amount"]) - Decimal(payable["balance"]) == Decimal(
        "38500.00"
    )


def test_purchase_return_uses_the_invoice_price(erp):
    client, data = erp
    payable = next(p for p in _get(client, "/payables") if p["invoiceNo"] == "PI-0004")
    head = _call(
        client,
        data,
        "POST",
        "/purchase-returns",
        {
            "partnerId": payable["partnerId"],
            "purchaseInvoiceId": payable["purchaseInvoiceId"],
            "returnedOn": "2026-09-24",
            "reason": "합성 반송 사유",
        },
    ).json()["data"]
    available = _get(
        client, f"/purchase-returns-available/{payable['purchaseInvoiceId']}"
    )
    pbt = next(r for r in available if r["itemCode"] == "RM-PBT")
    assert pbt["unitPrice"] == "3500.0000"
    lines = _call(
        client,
        data,
        "PUT",
        f"/purchase-returns/{head['id']}/lines",
        {"lines": [{"itemId": pbt["itemId"], "quantity": "10"}]},
    )
    assert lines.status_code == 200, lines.text
    assert lines.json()["data"]["totalAmount"] == "38500.00"
