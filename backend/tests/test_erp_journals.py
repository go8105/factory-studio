"""DSN-11 1e 회계: 자동 분개·전표 확정 규칙·역분개·미반영 현황·지출결의."""

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


def _account(client, code):
    return next(
        a for a in _get(client, "/accounts?limit=200") if a["accountCode"] == code
    )


def test_seed_sales_already_has_an_entry(erp):
    client, _ = erp
    entries = _get(client, "/journal-entries")
    sale = next(e for e in entries if e["entryKind"] == "SALE")
    assert sale["status"] == "confirmed"
    assert sale["debitTotal"] == sale["creditTotal"]
    codes = {line["accountCode"] for line in sale["lines"]}
    assert {"AR", "PRODUCT_SALES"} <= codes


def test_zero_tax_sale_has_no_tax_line(erp):
    client, _ = erp
    # SH-0003은 영세 매출이라 세액이 0이다. 0원 줄은 만들지 않는다.
    entries = _get(client, "/journal-entries")
    zero = next(
        e
        for e in entries
        if e["entryKind"] == "SALE"
        and all(line["accountCode"] != "VAT_PAYABLE" for line in e["lines"])
    )
    assert len(zero["lines"]) == 2


def test_confirming_a_purchase_creates_its_entry(erp):
    client, data = erp
    supplier = next(
        p for p in _get(client, "/partners") if p["partnerKind"] in ("SUPPLIER", "BOTH")
    )
    item = next(i for i in _get(client, "/items") if i["itemCode"] == "RM-PBT")
    invoice = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-JV-1",
            "partnerId": supplier["id"],
            "invoiceDate": "2026-09-24",
        },
    ).json()["data"]
    _call(
        client,
        data,
        "PUT",
        f"/purchase-invoices/{invoice['id']}/lines",
        {
            "lines": [
                {
                    "itemId": item["id"],
                    "quantity": "10",
                    "unit": "KG",
                    "unitPrice": "3500",
                }
            ]
        },
    )
    _call(client, data, "POST", f"/purchase-invoices/{invoice['id']}/confirm")
    found = client.get(
        f"{BASE}/journal-entries/for-source?sourceKind=purchase_invoice&sourceId={invoice['id']}"
    ).json()["data"]
    assert found["entry"] is not None
    assert found["entry"]["entryKind"] == "PURCHASE"
    assert found["entry"]["debitTotal"] == "38500.00"


def test_business_is_confirmed_even_when_the_rule_is_missing(erp):
    client, data = erp
    # 매입 규칙이 가리키는 계정을 끄면 전표를 만들 수 없다.
    raw = _account(client, "RAW_MATERIAL")
    off = _call(client, data, "PATCH", f"/accounts/{raw['id']}", {"isActive": False})
    assert off.status_code == 200, off.text
    supplier = next(
        p for p in _get(client, "/partners") if p["partnerKind"] in ("SUPPLIER", "BOTH")
    )
    item = next(i for i in _get(client, "/items") if i["itemCode"] == "RM-PIN")
    invoice = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-JV-2",
            "partnerId": supplier["id"],
            "invoiceDate": "2026-09-24",
        },
    ).json()["data"]
    _call(
        client,
        data,
        "PUT",
        f"/purchase-invoices/{invoice['id']}/lines",
        {
            "lines": [
                {
                    "itemId": item["id"],
                    "quantity": "1",
                    "unit": "BOX",
                    "unitPrice": "1000",
                }
            ]
        },
    )
    confirmed = _call(
        client, data, "POST", f"/purchase-invoices/{invoice['id']}/confirm"
    )
    # 업무는 확정된다. 막는 것은 회계이지 업무가 아니다.
    assert confirmed.status_code == 200
    assert confirmed.json()["data"]["status"] == "confirmed"
    waiting = _get(client, "/unposted")
    mine = next(
        r
        for r in waiting
        if r["sourceKind"] == "purchase_invoice" and r["sourceId"] == invoice["id"]
    )
    assert mine["reason"] == "NO_ACCOUNT" and mine["postable"] is False


def test_pending_can_be_posted_once_the_reason_is_gone(erp):
    client, data = erp
    raw = _account(client, "RAW_MATERIAL")
    _call(client, data, "PATCH", f"/accounts/{raw['id']}", {"isActive": False})
    supplier = next(
        p for p in _get(client, "/partners") if p["partnerKind"] in ("SUPPLIER", "BOTH")
    )
    item = next(i for i in _get(client, "/items") if i["itemCode"] == "RM-PIN")
    invoice = _call(
        client,
        data,
        "POST",
        "/purchase-invoices",
        {
            "invoiceNo": "PI-JV-3",
            "partnerId": supplier["id"],
            "invoiceDate": "2026-09-24",
        },
    ).json()["data"]
    _call(
        client,
        data,
        "PUT",
        f"/purchase-invoices/{invoice['id']}/lines",
        {
            "lines": [
                {
                    "itemId": item["id"],
                    "quantity": "1",
                    "unit": "BOX",
                    "unitPrice": "1000",
                }
            ]
        },
    )
    _call(client, data, "POST", f"/purchase-invoices/{invoice['id']}/confirm")
    _call(client, data, "PATCH", f"/accounts/{raw['id']}", {"isActive": True})
    result = _call(
        client,
        data,
        "POST",
        "/unposted/post",
        {
            "targets": [
                {
                    "sourceKind": "purchase_invoice",
                    "entryKind": "PURCHASE",
                    "sourceId": invoice["id"],
                }
            ]
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["data"]["posted"] == 1
    found = client.get(
        f"{BASE}/journal-entries/for-source?sourceKind=purchase_invoice&sourceId={invoice['id']}"
    ).json()["data"]
    assert found["entry"] is not None


def _manual_entry(client, data, lines, entry_date="2026-09-24"):
    entry = _call(
        client, data, "POST", "/journal-entries", {"entryDate": entry_date}
    ).json()["data"]
    saved = _call(
        client, data, "PUT", f"/journal-entries/{entry['id']}/lines", {"lines": lines}
    )
    assert saved.status_code == 200, saved.text
    return entry["id"]


def test_unbalanced_entry_is_not_confirmed(erp):
    client, data = erp
    bank = _account(client, "BANK")["id"]
    sales = _account(client, "PRODUCT_SALES")["id"]
    entry_id = _manual_entry(
        client,
        data,
        [
            {"accountId": bank, "side": "DEBIT", "amount": "1000"},
            {"accountId": sales, "side": "CREDIT", "amount": "900"},
        ],
    )
    r = _call(client, data, "POST", f"/journal-entries/{entry_id}/confirm")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "NOT_BALANCED"


def test_one_line_entry_is_not_confirmed(erp):
    client, data = erp
    bank = _account(client, "BANK")["id"]
    entry_id = _manual_entry(
        client, data, [{"accountId": bank, "side": "DEBIT", "amount": "1000"}]
    )
    r = _call(client, data, "POST", f"/journal-entries/{entry_id}/confirm")
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "TOO_FEW_LINES"


def test_required_partner_is_enforced_on_the_line(erp):
    client, data = erp
    ar = _account(client, "AR")["id"]
    bank = _account(client, "BANK")["id"]
    entry = _call(
        client, data, "POST", "/journal-entries", {"entryDate": "2026-09-24"}
    ).json()["data"]
    r = _call(
        client,
        data,
        "PUT",
        f"/journal-entries/{entry['id']}/lines",
        {
            "lines": [
                {"accountId": ar, "side": "DEBIT", "amount": "1000"},
                {"accountId": bank, "side": "CREDIT", "amount": "1000"},
            ]
        },
    )
    assert r.status_code == 400
    assert "거래처가 필요합니다" in r.json()["error"]["details"]["fields"]["lines"]


def test_reversal_flips_the_sides_and_marks_the_original(erp):
    client, data = erp
    bank = _account(client, "BANK")["id"]
    sales = _account(client, "PRODUCT_SALES")["id"]
    entry_id = _manual_entry(
        client,
        data,
        [
            {"accountId": bank, "side": "DEBIT", "amount": "1000"},
            {"accountId": sales, "side": "CREDIT", "amount": "1000"},
        ],
    )
    _call(client, data, "POST", f"/journal-entries/{entry_id}/confirm")
    reversed_entry = _call(
        client,
        data,
        "POST",
        f"/journal-entries/{entry_id}/reverse",
        {"reason": "오입력"},
    )
    assert reversed_entry.status_code == 200, reversed_entry.text
    new = reversed_entry.json()["data"]
    assert new["entryKind"] == "REVERSAL" and new["reversalOfNo"]
    sides = {line["accountCode"]: line["side"] for line in new["lines"]}
    assert sides["BANK"] == "CREDIT" and sides["PRODUCT_SALES"] == "DEBIT"
    original = next(e for e in _get(client, "/journal-entries") if e["id"] == entry_id)
    assert original["status"] == "reversed"


def test_a_confirmed_entry_cannot_be_edited(erp):
    client, data = erp
    bank = _account(client, "BANK")["id"]
    sales = _account(client, "PRODUCT_SALES")["id"]
    entry_id = _manual_entry(
        client,
        data,
        [
            {"accountId": bank, "side": "DEBIT", "amount": "1000"},
            {"accountId": sales, "side": "CREDIT", "amount": "1000"},
        ],
    )
    _call(client, data, "POST", f"/journal-entries/{entry_id}/confirm")
    r = _call(
        client,
        data,
        "PUT",
        f"/journal-entries/{entry_id}/lines",
        {"lines": [{"accountId": bank, "side": "DEBIT", "amount": "1"}]},
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "ENTRY_LOCKED"


def test_expense_claim_posts_its_own_accounts(erp):
    client, data = erp
    employee = _get(client, "/employees")[0]
    department = _get(client, "/departments")[0]
    travel = _account(client, "TRAVEL_EXPENSE")["id"]
    claim = _call(
        client,
        data,
        "POST",
        "/expense-claims",
        {
            "claimedOn": "2026-09-24",
            "employeeId": employee["id"],
            "departmentId": department["id"],
            "payMethod": "CARD",
            "lines": [{"accountId": travel, "amount": "30000"}],
        },
    )
    assert claim.status_code == 201, claim.text
    claim_id = claim.json()["data"]["id"]
    confirmed = _call(client, data, "POST", f"/expense-claims/{claim_id}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    found = client.get(
        f"{BASE}/journal-entries/for-source?sourceKind=expense_claim&sourceId={claim_id}"
    ).json()["data"]
    entry = found["entry"]
    assert entry is not None and entry["entryKind"] == "EXPENSE_CLAIM"
    debit = next(line for line in entry["lines"] if line["side"] == "DEBIT")
    credit = next(line for line in entry["lines"] if line["side"] == "CREDIT")
    # 차변은 명세가 고른 계정, 대변은 지급 방법(카드 → 미지급금).
    assert debit["accountCode"] == "TRAVEL_EXPENSE"
    assert credit["accountCode"] == "CARD_PAYABLE"
    assert Decimal(debit["amount"]) == Decimal(credit["amount"]) == Decimal(30000)


def test_expense_claim_takes_expense_accounts_only(erp):
    client, data = erp
    employee = _get(client, "/employees")[0]
    department = _get(client, "/departments")[0]
    bank = _account(client, "BANK")["id"]
    r = _call(
        client,
        data,
        "POST",
        "/expense-claims",
        {
            "claimedOn": "2026-09-24",
            "employeeId": employee["id"],
            "departmentId": department["id"],
            "lines": [{"accountId": bank, "amount": "1000"}],
        },
    )
    assert r.status_code == 400
    assert "비용 계정" in r.json()["error"]["details"]["fields"]["lines"]


def test_a_claim_with_a_live_entry_is_not_cancelled(erp):
    client, data = erp
    employee = _get(client, "/employees")[0]
    department = _get(client, "/departments")[0]
    travel = _account(client, "TRAVEL_EXPENSE")["id"]
    claim_id = _call(
        client,
        data,
        "POST",
        "/expense-claims",
        {
            "claimedOn": "2026-09-24",
            "employeeId": employee["id"],
            "departmentId": department["id"],
            "lines": [{"accountId": travel, "amount": "10000"}],
        },
    ).json()["data"]["id"]
    _call(client, data, "POST", f"/expense-claims/{claim_id}/confirm")
    r = _call(
        client, data, "POST", f"/expense-claims/{claim_id}/cancel", {"reason": "취소"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "ENTRY_ALIVE"


def test_copied_workspace_keeps_its_entries_linked(erp):
    """복사본의 전표가 템플릿 id를 가리키면 안 된다 — 미반영 현황이 거짓으로 찬다."""
    client, _ = erp
    waiting = _get(client, "/unposted")
    posted = _get(client, "/journal-entries")
    assert posted, "시드가 만든 전표가 복사돼 있어야 한다"
    # 시드가 전부 전표로 반영했으므로 미반영은 비어 있어야 한다.
    assert waiting == []


def test_auto_entry_carries_the_required_partner(erp):
    """AR은 거래처 필수 계정이다. 자동 전표도 그 칸을 채워야 한다(E-18 requires_partner)."""
    client, _ = erp
    sale = next(e for e in _get(client, "/journal-entries") if e["entryKind"] == "SALE")
    ar = next(line for line in sale["lines"] if line["accountCode"] == "AR")
    assert ar["partnerId"] is not None and ar["partnerCode"]
    sales = next(
        line for line in sale["lines"] if line["accountCode"] == "PRODUCT_SALES"
    )
    # 거래처가 필요 없는 계정에는 넣지 않는다.
    assert sales["partnerId"] is None
