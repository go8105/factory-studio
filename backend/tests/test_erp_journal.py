"""FS-019g E-14 분개 미리보기. 규칙별 금액을 원천 API 값과 맞춘다."""

from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _get(client, path: str):
    return client.get(f"{BASE}{path}")


def _data(client, path: str):
    return _get(client, path).json()["data"]


def _lines(preview) -> list[tuple[str, str, str]]:
    return [(x["entrySide"], x["accountCode"], x["amount"]) for x in preview["lines"]]


def test_sales_rule_uses_total_supply_tax(erp):
    client, _ = erp
    sale = next(
        s for s in _data(client, "/sales-records") if s["shipmentNo"] == "SH-0001"
    )
    preview = _data(client, f"/journal-preview?kind=SALES&sourceId={sale['id']}")
    assert _lines(preview) == [
        ("DEBIT", "AR", sale["totalAmount"]),
        ("CREDIT", "PRODUCT_SALES", sale["supplyAmount"]),
        ("CREDIT", "VAT_PAYABLE", sale["taxAmount"]),
    ]
    assert preview["balanced"] and preview["unapplied"] is None
    assert preview["lines"][0]["accountName"] == "외상매출금"


def test_purchase_rule(erp):
    client, _ = erp
    invoice = next(
        i for i in _data(client, "/purchase-invoices") if i["invoiceNo"] == "PI-0001"
    )
    preview = _data(client, f"/journal-preview?kind=PURCHASE&sourceId={invoice['id']}")
    assert _lines(preview) == [
        ("DEBIT", "RAW_MATERIAL", invoice["supplyAmount"]),
        ("DEBIT", "VAT_RECEIVABLE", invoice["taxAmount"]),
        ("CREDIT", "AP", invoice["totalAmount"]),
    ]
    assert preview["debitTotal"] == preview["creditTotal"] == invoice["totalAmount"]


def test_receipt_previews_one_application_and_keeps_unapplied_outside(erp):
    client, _ = erp
    receipt = next(r for r in _data(client, "/receipts") if r["receiptNo"] == "RC-0002")
    apply = receipt["applications"][0]
    preview = _data(client, f"/journal-preview?kind=RECEIPT&applyId={apply['id']}")
    assert _lines(preview) == [
        ("DEBIT", "BANK", apply["amount"]),
        ("CREDIT", "AR", apply["amount"]),
    ]
    assert preview["unapplied"] == receipt["unappliedAmount"] == "100000.00"


def test_payment_rule(erp):
    client, _ = erp
    payment = next(p for p in _data(client, "/payments") if p["paymentNo"] == "PM-0002")
    apply = payment["applications"][0]
    preview = _data(client, f"/journal-preview?kind=PAYMENT&applyId={apply['id']}")
    assert _lines(preview) == [
        ("DEBIT", "AP", apply["amount"]),
        ("CREDIT", "BANK", apply["amount"]),
    ]


def test_cancelled_or_draft_source_is_not_postable(erp):
    client, created = erp
    draft = next(
        i for i in _data(client, "/purchase-invoices") if i["status"] == "draft"
    )
    response = _get(client, f"/journal-preview?kind=PURCHASE&sourceId={draft['id']}")
    assert response.json()["error"]["details"]["reason"] == "NOT_POSTABLE"
    sale = next(
        s for s in _data(client, "/sales-records") if s["shipmentNo"] == "SH-0002"
    )
    client.post(
        f"{BASE}/sales-records/{sale['id']}/cancel",
        json={"reason": "x"},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": str(uuid4())},
    )
    response = _get(client, f"/journal-preview?kind=SALES&sourceId={sale['id']}")
    assert response.status_code == 409


def test_required_id_and_other_space(erp):
    client, _ = erp
    missing = _get(client, "/journal-preview?kind=RECEIPT&sourceId=1")
    assert "applyId" in missing.json()["error"]["details"]["fields"]
    assert (
        _get(client, "/journal-preview?kind=SALES&sourceId=999999999").status_code
        == 404
    )


def test_preview_is_not_saved(guest_space):
    client, _, engine = guest_space
    from sqlalchemy import text

    sale = _data(client, "/sales-records")[0]
    with engine.connect() as connection:
        before = connection.execute(
            text("SELECT count(*) FROM core.request_receipt")
        ).scalar_one()
    _data(client, f"/journal-preview?kind=SALES&sourceId={sale['id']}")
    with engine.connect() as connection:
        after = connection.execute(
            text("SELECT count(*) FROM core.request_receipt")
        ).scalar_one()
    assert before == after  # GET만, 요청 결과·전표 저장 없음
