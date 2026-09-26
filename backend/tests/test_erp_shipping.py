"""FS-019c E-05 출하지시 · E-06 출하(+TX-09 매출·채권). 검증 항목마다 테스트를 나눈다."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        f"{BASE}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or str(uuid4()),
        },
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _get(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _order(client, no: str) -> dict:
    return next(o for o in _get(client, "/sales-orders") if o["orderNo"] == no)


def _ship_order(client, no: str) -> dict:
    return next(s for s in _get(client, "/shipment-orders") if s["shipOrderNo"] == no)


def _instruct(client, created, order_no: str, qtys: list[str], no="SH-O-T1", key=None):
    order = _order(client, order_no)
    lines = [
        {"salesOrderLineId": line["id"], "orderQty": q}
        for line, q in zip(order["lines"], qtys, strict=False)
        if q
    ]
    body = {
        "shipOrderNo": no,
        "salesOrderId": order["id"],
        "orderedOn": "2026-09-24",
        "lines": lines,
    }
    return _call(client, created, "POST", "/shipment-orders", body, key)


def _ship(client, created, ship_order_id: int, no="SH-T1", lines=None, key=None):
    body = {"shipmentNo": no, "shipmentOrderId": ship_order_id, "lines": lines or []}
    return _call(client, created, "POST", "/shipments", body, key)


def test_seed_ship_orders_and_shipments(erp):
    client, _ = erp
    assert _ship_order(client, "SH-O-0001")["shipmentNo"] == "SH-0001"
    assert _ship_order(client, "SH-O-0005")["status"] == "open"
    shipment = next(
        s for s in _get(client, "/shipments") if s["shipmentNo"] == "SH-0001"
    )
    assert shipment["lines"][0]["packingNo"] == "PL-0001"
    assert shipment["totalAmount"] == "3627800.00"


def test_partial_instruction_moves_order_to_shipping(erp):
    client, created = erp
    response = _instruct(client, created, "SO-0007", ["500"])
    assert response.status_code == 201, response.text
    assert response.json()["data"]["lines"][0]["orderQty"] == "500.000"
    assert _order(client, "SO-0007")["status"] == "shipping"


def test_instruction_over_order_qty_rejected(erp):
    client, created = erp
    _instruct(client, created, "SO-0007", ["1500"])
    response = _instruct(client, created, "SO-0007", ["600"], no="SH-O-T2")
    assert response.status_code == 409 and _reason(response) == "ORDER_QTY_EXCEEDED"
    details = response.json()["error"]["details"]
    assert (details["lineNo"], details["remainingQty"]) == (1, "500.000")


def test_concurrent_instructions_cannot_exceed(erp):
    client, created = erp

    def post(n: int) -> int:
        return _instruct(
            client, created, "SO-0007", ["1500"], no=f"SH-O-R{n}", key=f"race-{n}"
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(post, [1, 2])) == [201, 409]
    line = _order(client, "SO-0007")["lines"][0]
    assert line["instructedQty"] == "1500.000"


def test_line_of_other_order_rejected(erp):
    client, created = erp
    other = _order(client, "SO-0008")["lines"][0]["id"]
    order = _order(client, "SO-0007")
    body = {
        "shipOrderNo": "SH-O-T1",
        "salesOrderId": order["id"],
        "orderedOn": "2026-09-24",
        "lines": [{"salesOrderLineId": other, "orderQty": "1"}],
    }
    response = _call(client, created, "POST", "/shipment-orders", body)
    assert response.status_code == 400
    assert "lines" in response.json()["error"]["details"]["fields"]


def test_cancelled_instruction_frees_quantity(erp):
    client, created = erp
    first = _instruct(client, created, "SO-0007", ["2000"]).json()["data"]
    no_reason = _call(
        client,
        created,
        "POST",
        f"/shipment-orders/{first['id']}/cancel",
        {"reason": ""},
    )
    assert no_reason.status_code == 400
    cancelled = _call(
        client,
        created,
        "POST",
        f"/shipment-orders/{first['id']}/cancel",
        {"reason": "수량 변경"},
    ).json()["data"]
    assert (cancelled["status"], cancelled["cancelReason"]) == (
        "cancelled",
        "수량 변경",
    )
    assert _order(client, "SO-0007")["status"] == "open"
    again = _instruct(client, created, "SO-0007", ["2000"], no="SH-O-T2")
    assert again.status_code == 201
    ship = _ship(client, created, first["id"])
    assert _reason(ship) == "SHIPMENT_ORDER_NOT_OPEN"


def test_cancelled_order_not_shippable(erp):
    client, created = erp
    order = _order(client, "SO-0010")
    _call(client, created, "POST", f"/sales-orders/{order['id']}/cancel")
    response = _instruct(client, created, "SO-0010", ["1"])
    assert _reason(response) == "ORDER_NOT_SHIPPABLE"


def test_shipment_ships_full_quantity_and_recognizes_sale(guest_space):
    client, created, engine = guest_space
    ship_order = _ship_order(client, "SH-O-0006")  # SO-0005 line2 FG-T300(ZERO) 1964
    response = _ship(
        client,
        created,
        ship_order["id"],
        lines=[
            {
                "shipmentOrderLineId": ship_order["lines"][0]["id"],
                "packingNo": " PL-T1 ",
            }
        ],
    )
    assert response.status_code == 201, response.text
    shipment = response.json()["data"]
    assert [(x["shippedQty"], x["packingNo"]) for x in shipment["lines"]] == [
        ("1964.000", "PL-T1")
    ]
    # 1964 × 2400 = 4,713,600, 영세율 세액 0
    assert (shipment["supplyAmount"], shipment["taxAmount"]) == ("4713600.00", "0.00")
    assert _ship_order(client, "SH-O-0006")["status"] == "shipped"
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT rv.amount, rv.due_date, "
                "(r.recognized_at AT TIME ZONE 'Asia/Seoul')::date AS day "
                "FROM erp.receivable rv JOIN erp.sales_record r ON r.id=rv.sales_record_id "
                "WHERE r.id=:id"
            ),
            {"id": shipment["salesRecordId"]},
        ).one()
    assert row.amount == 4713600
    assert row.due_date == row.day + timedelta(days=60)  # C-002 결제조건 60일
    assert isinstance(row.day, date)


def test_taxable_line_adds_ten_percent(erp):
    client, created = erp
    ship_order = _ship_order(client, "SH-O-0005")  # SO-0005 line1 FG-C100 3880 × 870
    shipment = _ship(client, created, ship_order["id"]).json()["data"]
    assert (
        shipment["supplyAmount"],
        shipment["taxAmount"],
        shipment["totalAmount"],
    ) == (
        "3375600.00",
        "337560.00",
        "3713160.00",
    )


def test_all_lines_shipped_closes_order(erp):
    client, created = erp
    ship_order = _instruct(client, created, "SO-0007", ["2000", "2000"]).json()["data"]
    _ship(client, created, ship_order["id"])
    order = _order(client, "SO-0007")
    assert order["status"] == "closed"
    assert [x["shippedQty"] for x in order["lines"]] == ["2000.000", "2000.000"]


def test_duplicate_packing_no_rejected(erp):
    client, created = erp
    ship_order = _ship_order(client, "SH-O-0005")
    lines = [
        {"shipmentOrderLineId": ship_order["lines"][0]["id"], "packingNo": "PL-0001"}
    ]
    response = _ship(client, created, ship_order["id"], lines=lines)
    assert (
        response.status_code == 409 and _reason(response) == "PACKING_ALREADY_SHIPPED"
    )
    assert _ship_order(client, "SH-O-0005")["status"] == "open"


def test_shipped_order_cannot_ship_or_cancel_again(erp):
    client, created = erp
    ship_order = _ship_order(client, "SH-O-0005")
    _ship(client, created, ship_order["id"])
    again = _ship(client, created, ship_order["id"], no="SH-T2")
    assert _reason(again) == "SHIPMENT_ORDER_NOT_OPEN"
    cancel = _call(
        client,
        created,
        "POST",
        f"/shipment-orders/{ship_order['id']}/cancel",
        {"reason": "x"},
    )
    assert _reason(cancel) == "SHIPMENT_ORDER_NOT_OPEN"


def test_replayed_confirm_creates_one_sale(guest_space):
    client, created, engine = guest_space
    ship_order = _ship_order(client, "SH-O-0005")
    first = _ship(client, created, ship_order["id"], key="k-ship")
    second = _ship(client, created, ship_order["id"], key="k-ship")
    assert first.json()["data"]["id"] == second.json()["data"]["id"]
    with engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM erp.sales_record WHERE shipment_id=:id"),
            {"id": first.json()["data"]["id"]},
        ).scalar_one()
    assert count == 1
