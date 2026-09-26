"""FS-019f E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명. 검증 항목마다 테스트를 나눈다."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
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


def _id(client, path: str, field: str, code: str) -> int:
    return next(r["id"] for r in _get(client, f"{path}?limit=200") if r[field] == code)


def _invoice(client, no: str) -> dict:
    return next(i for i in _get(client, "/purchase-invoices") if i["invoiceNo"] == no)


def _payable(client, no: str) -> dict:
    return next(p for p in _get(client, "/payables") if p["invoiceNo"] == no)


def _draft(client, created, lines=None, **header) -> dict:
    body = {
        "invoiceNo": "PI-T1",
        "partnerId": _id(client, "/partners", "partnerCode", "V-001"),
        "invoiceDate": "2026-09-20",
        **header,
    }
    invoice = _call(client, created, "POST", "/purchase-invoices", body).json()["data"]
    pbt = _id(client, "/items", "itemCode", "RM-PBT")
    lines = (
        lines
        if lines is not None
        else [{"itemId": pbt, "quantity": "100", "unit": "KG", "unitPrice": "3500"}]
    )
    response = _call(
        client,
        created,
        "PUT",
        f"/purchase-invoices/{invoice['id']}/lines",
        {"lines": lines},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


def _payment(client, created, amount: str, confirm=True) -> dict:
    body = {
        "paymentNo": f"PM-{uuid4().hex[:8]}",
        "partnerId": _id(client, "/partners", "partnerCode", "V-001"),
        "paidOn": "2026-09-24",
        "amount": amount,
    }
    payment = _call(client, created, "POST", "/payments", body).json()["data"]
    if confirm:
        payment = _call(
            client, created, "POST", f"/payments/{payment['id']}/confirm"
        ).json()["data"]
    return payment


def _apply(client, created, payment_id: int, lines):
    body = {"lines": [{"payableId": p, "amount": a} for p, a in lines]}
    return _call(client, created, "POST", f"/payments/{payment_id}/applications", body)


# ---- E-11 매입 전표 ----
def test_seed_invoices_and_payables(erp):
    client, _ = erp
    assert _invoice(client, "PI-0006")["cancelBlockedReason"] == "ALREADY_CANCELLED"
    assert _invoice(client, "PI-0002")["cancelBlockedReason"] == "PAYMENT_APPLIED"
    rows = {p["invoiceNo"]: p["status"] for p in _get(client, "/payables")}
    assert rows == {
        "PI-0001": "CLOSED",
        "PI-0002": "PARTIAL",
        "PI-0003": "OPEN",
        "PI-0004": "OPEN",
    }  # 취소 매입 PI-0006 제외


def test_lines_are_priced_by_server_and_totaled(erp):
    client, created = erp
    invoice = _draft(client, created)
    line = invoice["lines"][0]
    assert (line["supplyAmount"], line["taxAmount"], line["totalAmount"]) == (
        "350000.00",
        "35000.00",
        "385000.00",
    )
    assert (invoice["totalAmount"], invoice["status"]) == ("385000.00", "draft")


def test_only_raw_items_and_known_units(erp):
    client, created = erp
    invoice = _draft(client, created)
    path = f"/purchase-invoices/{invoice['id']}/lines"
    finished = _id(client, "/items", "itemCode", "FG-C100")
    pbt = _id(client, "/items", "itemCode", "RM-PBT")
    for line, message in [
        (
            {"itemId": finished, "quantity": "1", "unit": "EA", "unitPrice": "1"},
            "원재료",
        ),
        ({"itemId": pbt, "quantity": "1", "unit": "L", "unitPrice": "1"}, "단위"),
    ]:
        response = _call(client, created, "PUT", path, {"lines": [line]})
        assert message in response.json()["error"]["details"]["fields"]["lines"]


def test_customer_partner_rejected(erp):
    client, created = erp
    body = {
        "invoiceNo": "PI-T2",
        "partnerId": _id(client, "/partners", "partnerCode", "C-001"),
        "invoiceDate": "2026-09-20",
    }
    response = _call(client, created, "POST", "/purchase-invoices", body)
    assert "partnerId" in response.json()["error"]["details"]["fields"]


def test_confirm_creates_payable_with_term_due_date(erp):
    client, created = erp
    invoice = _draft(client, created)
    confirmed = _call(
        client, created, "POST", f"/purchase-invoices/{invoice['id']}/confirm"
    ).json()["data"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["dueDate"] == str(date(2026, 9, 20) + timedelta(days=30))
    payable = _payable(client, "PI-T1")
    assert (payable["amount"], payable["dueDate"], payable["status"]) == (
        "385000.00",
        confirmed["dueDate"],
        "OPEN",
    )
    locked = _call(
        client,
        created,
        "PATCH",
        f"/purchase-invoices/{invoice['id']}",
        {"dueDate": None},
    )
    assert _reason(locked) == "INVOICE_LOCKED"


def test_manual_due_date_wins(erp):
    client, created = erp
    invoice = _draft(client, created, dueDate="2026-12-31")
    _call(client, created, "POST", f"/purchase-invoices/{invoice['id']}/confirm")
    assert _payable(client, "PI-T1")["dueDate"] == "2026-12-31"


def test_empty_invoice_cannot_confirm(erp):
    client, created = erp
    invoice = _draft(client, created, lines=[])
    response = _call(
        client, created, "POST", f"/purchase-invoices/{invoice['id']}/confirm"
    )
    assert _reason(response) == "EMPTY_INVOICE"


def test_cancel_rules(erp):
    client, created = erp
    draft = _draft(client, created)
    cancel = _call(
        client,
        created,
        "POST",
        f"/purchase-invoices/{draft['id']}/cancel",
        {"reason": "중복"},
    )
    assert cancel.json()["data"]["status"] == "cancelled"
    open_one = _invoice(client, "PI-0003")
    _call(
        client,
        created,
        "POST",
        f"/purchase-invoices/{open_one['id']}/cancel",
        {"reason": "반품"},
    )
    assert all(p["invoiceNo"] != "PI-0003" for p in _get(client, "/payables"))
    applied = _call(
        client,
        created,
        "POST",
        f"/purchase-invoices/{_invoice(client, 'PI-0002')['id']}/cancel",
        {"reason": "x"},
    )
    assert _reason(applied) == "PAYMENT_APPLIED"


# ---- E-12·E-13 채무·지급 소명 (019e와 같은 규칙) ----
def test_draft_payment_cannot_apply(erp):
    client, created = erp
    payment = _payment(client, created, "100", confirm=False)
    response = _apply(
        client, created, payment["id"], [(_payable(client, "PI-0003")["id"], "1")]
    )
    assert _reason(response) == "PAYMENT_NOT_CONFIRMED"


def test_payable_limit_names_invoice(erp):
    client, created = erp
    payable = _payable(client, "PI-0002")
    payment = _payment(client, created, "99999999")
    response = _apply(client, created, payment["id"], [(payable["id"], "99999999")])
    details = response.json()["error"]["details"]
    assert (details["limit"], details["invoiceNo"], details["availableAmount"]) == (
        "PAYABLE",
        "PI-0002",
        payable["balance"],
    )


def test_concurrent_payments_cannot_exceed_payable(erp):
    client, created = erp
    payable = _payable(client, "PI-0003")
    half = str(int(float(payable["balance"]) * 0.6))
    payments = [_payment(client, created, half) for _ in range(2)]

    def post(payment) -> int:
        return _apply(
            client, created, payment["id"], [(payable["id"], half)]
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(post, payments)) == [201, 409]


def test_cancelled_purchase_payable_rejects_application(erp):
    client, created = erp
    payable_id = _payable(client, "PI-0003")["id"]
    invoice = _invoice(client, "PI-0003")
    _call(
        client,
        created,
        "POST",
        f"/purchase-invoices/{invoice['id']}/cancel",
        {"reason": "x"},
    )
    payment = _payment(client, created, "100")
    assert _reason(_apply(client, created, payment["id"], [(payable_id, "1")])) == (
        "PURCHASE_CANCELLED"
    )


def test_payment_application_delete_is_audited_and_fifo(guest_space):
    client, created, engine = guest_space
    payment = _payment(client, created, "1000")
    fifo = _get(client, f"/payments/{payment['id']}/fifo-suggestion")
    assert fifo == [
        {"payableId": _payable(client, "PI-0002")["id"], "amount": "1000.00"}
    ]
    data = _apply(
        client, created, payment["id"], [(fifo[0]["payableId"], "1000")]
    ).json()["data"]
    apply_id = data["applications"][0]["id"]
    _call(
        client, created, "DELETE", f"/payments/{payment['id']}/applications/{apply_id}"
    )
    with engine.connect() as connection:
        summary = connection.execute(
            text(
                "SELECT summary FROM core.audit_event WHERE action='erp.payment_apply.delete' "
                "AND entity_key=:key"
            ),
            {"key": str(apply_id)},
        ).scalar_one()
    assert summary["payableId"] == fifo[0]["payableId"]
