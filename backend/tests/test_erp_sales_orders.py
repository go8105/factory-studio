"""FS-019b E-04 수주 API. 검증 항목마다 테스트를 나눈다."""

from uuid import uuid4

import pytest

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


def _id(client, path: str, field: str, code: str) -> int:
    rows = client.get(f"{BASE}{path}?limit=200").json()["data"]
    return next(r["id"] for r in rows if r[field] == code)


def _order(client, no: str) -> dict:
    orders = client.get(f"{BASE}/sales-orders").json()["data"]
    return next(o for o in orders if o["orderNo"] == no)


def _body(client, **override) -> dict:
    return {
        "orderNo": "SO-T01",
        "partnerId": _id(client, "/partners", "partnerCode", "C-002"),
        "orderedOn": "2026-09-24",
        "dueOn": "2026-10-08",
        "lines": [
            {"itemId": _id(client, "/items", "itemCode", "FG-T300"), "orderQty": "10"}
        ],
        **override,
    }


def test_seed_progress_counts_instructed_and_shipped(erp):
    client, _ = erp
    closed = _order(client, "SO-0001")["lines"][0]
    assert (closed["instructedQty"], closed["shippedQty"]) == ("3880.000", "3880.000")
    shipping = _order(client, "SO-0005")
    assert shipping["shipmentOrderCount"] == 2
    assert [x["shippedQty"] for x in shipping["lines"]] == ["0", "0", "0"]
    assert _order(client, "SO-0001")["quoteNo"] == "Q-0001"


def test_direct_order_uses_partner_price(erp):
    client, created = erp
    response = _call(client, created, "POST", "/sales-orders", _body(client))
    assert response.status_code == 201, response.text
    order = response.json()["data"]
    assert (order["status"], order["quotationId"]) == ("open", None)
    assert (order["lines"][0]["unitPrice"], order["totalAmount"]) == (
        "2400.0000",
        "24000",
    )


def test_missing_price_and_bad_due_date(erp):
    client, created = erp
    # 단가 세 자리(거래처·그룹·표준)가 모두 비어야 단가 없음이다(DSN-11 F06).
    bare = _call(
        client,
        created,
        "POST",
        "/items",
        {
            "itemCode": "SO-NOPRICE",
            "name": "단가 없는 품목",
            "baseUnit": "EA",
            "itemType": "finished",
            "taxCategory": "TAXABLE",
        },
    ).json()["data"]["id"]
    no_price = _body(client, lines=[{"itemId": bare, "orderQty": "1"}])
    response = _call(client, created, "POST", "/sales-orders", no_price)
    assert "lines" in response.json()["error"]["details"]["fields"]
    early = _call(
        client, created, "POST", "/sales-orders", _body(client, dueOn="2026-09-01")
    )
    assert "dueOn" in early.json()["error"]["details"]["fields"]


def test_open_order_can_be_edited(erp):
    client, created = erp
    order = _call(client, created, "POST", "/sales-orders", _body(client)).json()[
        "data"
    ]
    item = _id(client, "/items", "itemCode", "FG-C100")
    response = _call(
        client,
        created,
        "PATCH",
        f"/sales-orders/{order['id']}",
        {
            "dueOn": "2026-10-20",
            "lines": [{"itemId": item, "orderQty": "2", "unitPrice": "900"}],
        },
    )
    data = response.json()["data"]
    assert data["dueOn"] == "2026-10-20"
    assert [(x["lineNo"], x["unitPrice"]) for x in data["lines"]] == [(1, "900.0000")]


def test_order_with_shipment_order_is_locked(erp):
    client, created = erp
    order = _order(client, "SO-0005")
    patch = _call(
        client,
        created,
        "PATCH",
        f"/sales-orders/{order['id']}",
        {"dueOn": "2026-12-01"},
    )
    assert patch.status_code == 409 and _reason(patch) == "ORDER_LOCKED"
    cancel = _call(client, created, "POST", f"/sales-orders/{order['id']}/cancel")
    assert _reason(cancel) == "ORDER_LOCKED"


def test_cancel_open_order(erp):
    client, created = erp
    order = _order(client, "SO-0010")
    response = _call(client, created, "POST", f"/sales-orders/{order['id']}/cancel")
    assert response.json()["data"]["status"] == "cancelled"
    again = _call(client, created, "POST", f"/sales-orders/{order['id']}/cancel")
    assert _reason(again) == "ORDER_LOCKED"


def test_converted_order_keeps_partner(erp):
    client, created = erp
    order = _order(client, "SO-0007")
    other = _id(client, "/partners", "partnerCode", "C-001")
    response = _call(
        client, created, "PATCH", f"/sales-orders/{order['id']}", {"partnerId": other}
    )
    assert "partnerId" in response.json()["error"]["details"]["fields"]


def test_other_space_order_not_found(guest_space):
    client, created, _ = guest_space
    response = _call(client, created, "POST", "/sales-orders/999999999/cancel")
    assert response.status_code == 404
