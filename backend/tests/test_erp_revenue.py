"""FS-019d E-07 매출 · E-08 세금계산서. 검증 항목마다 테스트를 나눈다."""

from uuid import uuid4

import pytest
from sqlalchemy import text

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _call(client, created, method: str, path: str, body=None):
    return client.request(
        method,
        f"{BASE}{path}",
        json=body,
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": str(uuid4())},
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _get(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _sale(client, shipment_no: str) -> dict:
    return next(
        s for s in _get(client, "/sales-records") if s["shipmentNo"] == shipment_no
    )


def _cancel(client, created, sale_id: int, reason="반품"):
    return _call(
        client, created, "POST", f"/sales-records/{sale_id}/cancel", {"reason": reason}
    )


def _new_invoice(client, created, sale_id: int):
    return _call(client, created, "POST", "/tax-invoices", {"salesRecordId": sale_id})


def test_seed_sales_show_cancel_block_reason(erp):
    client, _ = erp
    assert _sale(client, "SH-0001")["cancelBlockedReason"] == "INVOICE_ISSUED"
    pending = _sale(client, "SH-0002")
    assert (pending["cancelBlockedReason"], pending["taxInvoiceStatus"]) == (
        None,
        "pending",
    )
    applied = _sale(client, "SH-0004")
    assert (applied["cancelBlockedReason"], applied["appliedAmount"]) == (
        "RECEIPT_APPLIED",
        "200000.00",
    )


def test_cancel_deletes_pending_invoice_and_keeps_receivable(guest_space):
    client, created, engine = guest_space
    sale = _sale(client, "SH-0002")
    assert _cancel(client, created, sale["id"], reason="").status_code == 400
    data = _cancel(client, created, sale["id"]).json()["data"]
    assert (data["cancelReason"], data["taxInvoiceId"]) == ("반품", None)
    assert data["cancelledAt"] and data["cancelBlockedReason"] == "ALREADY_CANCELLED"
    assert all(t["salesRecordId"] != sale["id"] for t in _get(client, "/tax-invoices"))
    with engine.connect() as connection:
        amount = connection.execute(
            text("SELECT amount FROM erp.receivable WHERE sales_record_id=:id"),
            {"id": sale["id"]},
        ).scalar_one()
    assert str(amount) == sale["totalAmount"]  # 원금은 남는다
    assert _reason(_cancel(client, created, sale["id"])) == "ALREADY_CANCELLED"


def test_issued_invoice_blocks_cancel(erp):
    client, created = erp
    response = _cancel(client, created, _sale(client, "SH-0001")["id"])
    assert response.status_code == 409 and _reason(response) == "INVOICE_ISSUED"


def test_receipt_application_blocks_cancel(erp):
    client, created = erp
    response = _cancel(client, created, _sale(client, "SH-0004")["id"])
    assert _reason(response) == "RECEIPT_APPLIED"


def test_one_invoice_per_sale(erp):
    client, created = erp
    sale = _sale(client, "SH-0004")
    first = _new_invoice(client, created, sale["id"])
    assert first.status_code == 201 and first.json()["data"]["status"] == "pending"
    assert _reason(_new_invoice(client, created, sale["id"])) == "INVOICE_EXISTS"


def test_cancelled_sale_gets_no_invoice(erp):
    client, created = erp
    sale = _sale(client, "SH-0002")
    _cancel(client, created, sale["id"])
    assert _reason(_new_invoice(client, created, sale["id"])) == "SALES_CANCELLED"


def test_zero_amount_sale_is_allowed_but_not_invoiced(erp):
    """E-G07: 0원 매출은 성립하고 세금계산서만 거부한다."""
    client, created = erp
    partner = next(p for p in _get(client, "/partners") if p["partnerCode"] == "C-001")
    item = next(
        i for i in _get(client, "/items?limit=200") if i["itemCode"] == "FG-C100"
    )
    order = _call(
        client,
        created,
        "POST",
        "/sales-orders",
        {
            "orderNo": "SO-ZERO",
            "partnerId": partner["id"],
            "orderedOn": "2026-09-24",
            "dueOn": "2026-10-01",
            "lines": [{"itemId": item["id"], "orderQty": "1", "unitPrice": "0"}],
        },
    ).json()["data"]
    ship_order = _call(
        client,
        created,
        "POST",
        "/shipment-orders",
        {
            "shipOrderNo": "SH-O-ZERO",
            "salesOrderId": order["id"],
            "orderedOn": "2026-09-24",
            "lines": [{"salesOrderLineId": order["lines"][0]["id"], "orderQty": "1"}],
        },
    ).json()["data"]
    shipment = _call(
        client,
        created,
        "POST",
        "/shipments",
        {"shipmentNo": "SH-ZERO", "shipmentOrderId": ship_order["id"]},
    )
    assert (
        shipment.status_code == 201 and shipment.json()["data"]["totalAmount"] == "0.00"
    )
    response = _new_invoice(client, created, _sale(client, "SH-ZERO")["id"])
    assert response.status_code == 409 and _reason(response) == "ZERO_AMOUNT_SALE"


def test_issue_checks_date_and_approval_no(erp):
    client, created = erp
    invoice = next(t for t in _get(client, "/tax-invoices") if t["status"] == "pending")
    path = f"/tax-invoices/{invoice['id']}/issue"
    early = _call(
        client, created, "POST", path, {"approvalNo": "A-1", "issuedOn": "2020-01-01"}
    )
    assert "issuedOn" in early.json()["error"]["details"]["fields"]
    day = invoice["recognizedAt"][:10]
    dup = _call(
        client,
        created,
        "POST",
        path,
        {"approvalNo": "SYNTH-TI-0001", "issuedOn": "2026-09-24"},
    )
    assert "approvalNo" in dup.json()["error"]["details"]["fields"]
    issued = _call(
        client, created, "POST", path, {"approvalNo": "A-1", "issuedOn": "2026-09-24"}
    )
    assert issued.status_code == 200, issued.text
    assert (issued.json()["data"]["status"], issued.json()["data"]["approvalNo"]) == (
        "issued",
        "A-1",
    )
    assert day <= "2026-09-24"
    again = _call(
        client, created, "POST", path, {"approvalNo": "A-2", "issuedOn": "2026-09-24"}
    )
    assert _reason(again) == "ALREADY_ISSUED"
    cancel = _cancel(client, created, invoice["salesRecordId"])
    assert _reason(cancel) == "INVOICE_ISSUED"
