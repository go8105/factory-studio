"""DSN-11 1c 기초등록: 부서·담당자·프로젝트, 단가 그룹, 계정 보강, 거래처 BOTH."""

from uuid import uuid4

import pytest

BASE = "/api/v1/erp"


def _headers(data, key=None):
    return {"X-CSRF-Token": data["csrfToken"], "Idempotency-Key": key or uuid4().hex}


def _call(client, data, method, path, body=None):
    return client.request(method, f"{BASE}{path}", json=body, headers=_headers(data))


def _row(client, path, field, value):
    rows = client.get(f"{BASE}{path}?limit=200").json()["data"]
    return next(r for r in rows if r[field] == value)


@pytest.fixture
def erp(guest_space):
    return guest_space[0], guest_space[1]


def _quote_price(client, data, partner_code, item_code, no):
    """견적 라인을 단가 없이 넣고 서버가 고른 단가를 돌려준다."""
    partner = _row(client, "/partners", "partnerCode", partner_code)["id"]
    item = _row(client, "/items", "itemCode", item_code)["id"]
    quote = _call(
        client,
        data,
        "POST",
        "/quotations",
        {"quoteNo": no, "partnerId": partner, "quotedOn": "2026-09-24"},
    ).json()["data"]
    lines = _call(
        client,
        data,
        "PUT",
        f"/quotations/{quote['id']}/lines",
        {"lines": [{"itemId": item, "quoteQty": "10"}]},
    )
    assert lines.status_code == 200, lines.text
    return lines.json()["data"]["lines"][0]["unitPrice"]


def test_partner_price_wins_over_group(erp):
    client, data = erp
    # C-001은 FG-C100에 거래처별 단가 850이 있고, 그룹 단가는 860이다.
    assert _quote_price(client, data, "C-001", "FG-C100", "Q-P01") == "850.0000"


def test_group_price_fills_in_when_partner_price_is_missing(erp):
    client, data = erp
    # C-002는 FG-C200에 거래처별 단가가 없고 PG-SALE-A에 속한다.
    assert _quote_price(client, data, "C-002", "FG-C200", "Q-P02") == "1210.0000"


def test_standard_price_is_the_last_resort(erp):
    client, data = erp
    # C-003은 FG-C100 단가도 단가 그룹도 없다. 품목 표준 판매가를 쓴다.
    assert _quote_price(client, data, "C-003", "FG-C100", "Q-P03") == "850.0000"


def test_no_price_anywhere_is_refused_not_guessed(erp):
    client, data = erp
    item = _call(
        client,
        data,
        "POST",
        "/items",
        {
            "itemCode": "NO-PRICE",
            "name": "단가 없는 품목",
            "baseUnit": "EA",
            "itemType": "finished",
            "taxCategory": "TAXABLE",
        },
    ).json()["data"]
    partner = _row(client, "/partners", "partnerCode", "C-003")["id"]
    quote = _call(
        client,
        data,
        "POST",
        "/quotations",
        {"quoteNo": "Q-P04", "partnerId": partner, "quotedOn": "2026-09-24"},
    ).json()["data"]
    r = _call(
        client,
        data,
        "PUT",
        f"/quotations/{quote['id']}/lines",
        {"lines": [{"itemId": item["id"], "quoteQty": "10"}]},
    )
    assert r.status_code == 400
    assert "적용할 단가가 없습니다" in r.json()["error"]["details"]["fields"]["lines"]


def test_sale_slot_refuses_a_purchase_price_group(erp):
    client, data = erp
    group = _row(client, "/price-groups", "code", "PG-BUY-A")["id"]
    r = _call(
        client,
        data,
        "POST",
        "/partners",
        {
            "partnerCode": "P-WRONG",
            "partnerName": "그룹 잘못",
            "partnerKind": "CUSTOMER",
            "salePriceGroupId": group,
        },
    )
    assert r.status_code == 400
    assert (
        "판매 단가 그룹" in r.json()["error"]["details"]["fields"]["salePriceGroupId"]
    )


def test_both_partner_serves_sales_and_purchases(erp):
    client, data = erp
    assert _quote_price(client, data, "B-001", "FG-C200", "Q-P05") == "1210.0000"
    payment = _call(
        client,
        data,
        "POST",
        "/payments",
        {
            "paymentNo": "PY-BOTH",
            "partnerId": _row(client, "/partners", "partnerCode", "B-001")["id"],
            "paidOn": "2026-09-24",
            "amount": "1000",
        },
    )
    assert payment.status_code == 201, payment.text


def test_accounts_are_disabled_not_deleted(erp):
    client, data = erp
    account = _row(client, "/accounts", "accountCode", "AR")
    assert (
        _call(client, data, "DELETE", f"/accounts/{account['id']}").status_code == 405
    )
    off = _call(
        client, data, "PATCH", f"/accounts/{account['id']}", {"isActive": False}
    )
    assert off.status_code == 200 and off.json()["data"]["isActive"] is False


def test_account_class_is_frozen_once_the_account_is_used(erp):
    client, data = erp
    account = _row(client, "/accounts", "accountCode", "AR")
    r = _call(
        client, data, "PATCH", f"/accounts/{account['id']}", {"accountClass": "EXPENSE"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["details"]["reason"] == "ACCOUNT_IN_USE"
    # 이름은 바꿀 수 있다 — 전표의 뜻이 달라지지 않는다.
    renamed = _call(
        client, data, "PATCH", f"/accounts/{account['id']}", {"accountName": "매출채권"}
    )
    assert renamed.status_code == 200


def test_project_end_cannot_precede_start(erp):
    client, data = erp
    r = _call(
        client,
        data,
        "POST",
        "/projects",
        {
            "code": "PJ-BAD",
            "name": "거꾸로 기간",
            "startOn": "2026-09-30",
            "endOn": "2026-09-01",
        },
    )
    assert r.status_code == 400
    assert "endOn" in r.json()["error"]["details"]["fields"]


def test_department_with_employees_is_not_deleted(erp):
    client, data = erp
    department = _row(client, "/departments", "code", "D-SALES")["id"]
    r = _call(client, data, "DELETE", f"/departments/{department}")
    assert r.status_code == 409
    body = r.json()["error"]
    assert body["code"] == "REFERENCED_BY_OTHERS"
    assert any(ref["label"] == "담당자" for ref in body["details"]["references"])


def test_employee_takes_a_department_from_this_space_only(erp):
    client, data = erp
    r = _call(
        client,
        data,
        "POST",
        "/employees",
        {"code": "E-GHOST", "name": "없는 부서", "departmentId": 999999},
    )
    assert r.status_code == 400
    assert "departmentId" in r.json()["error"]["details"]["fields"]


def test_cost_center_kind_is_one_of_three(erp):
    client, _ = erp
    kinds = {
        row["costCenterKind"]
        for row in client.get(f"{BASE}/departments").json()["data"]
    }
    assert kinds == {"MFG", "SALES", "ADMIN"}


def test_posting_rules_cover_fourteen_transaction_kinds(erp):
    client, _ = erp
    rows = client.get(f"{BASE}/posting-rules?limit=200").json()["data"]
    assert len({row["transactionKind"] for row in rows}) == 14
    for kind in ("SALES_RETURN", "SUBCONTRACT", "PAYROLL", "COGS"):
        lines = [row for row in rows if row["transactionKind"] == kind]
        assert {row["entrySide"] for row in lines} == {"DEBIT", "CREDIT"}
