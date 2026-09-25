"""FS-020f MES 패킹(M-08)·완제품 입고(M-09) API. 검증 항목마다 테스트를 나눈다."""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest

BASE = "/api/v1/mes"


@pytest.fixture
def mes(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _rows(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _call(client, created, method: str, path: str, key: str, body=None):
    return client.request(
        method, f"{BASE}{path}", json=body, headers=_headers(created, key)
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _unit(client, number: str) -> dict:
    return next(u for u in _rows(client, "/packing-units") if u["packingNo"] == number)


def _new(client, created, kind: str, key: str) -> dict:
    response = _call(
        client, created, "POST", "/packing-units", key, {"packingKind": kind}
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _put(client, created, box: dict, lot: dict, qty: str, key: str):
    return _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box['id']}/members",
        key,
        {"lotId": lot["lotId"], "packedQty": qty},
    )


def _closed_box(client, created, lot: dict, qty: str, key: str) -> dict:
    box = _new(client, created, "BOX", f"{key}-new")
    assert _put(client, created, box, lot, qty, f"{key}-put").status_code == 200
    _call(client, created, "POST", f"/packing-units/{box['id']}/close", f"{key}-close")
    return box


def test_seed_packing_units(mes):
    client, _ = mes
    units = _rows(client, "/packing-units")
    pallets = [u for u in units if u["packingKind"] == "PALLET"]
    assert len(pallets) == 6
    received = _unit(client, "PL-0002")
    assert (received["status"], len(received["childIds"])) == ("received", 4)
    assert received["receivedAt"] is not None
    assert Decimal(received["totalQty"]) > 0
    assert (
        sum(1 for u in units if u["packingKind"] == "BOX" and u["status"] == "open")
        == 1
    )


def test_packable_lots_have_remaining_good(mes):
    client, _ = mes
    lots = _rows(client, "/packable-lots")
    # 정상 완료되고 아직 다 담지 않은 LOT만. 전량 불량 LOT은 나오지 않는다.
    assert len(lots) == 2
    for lot in lots:
        assert Decimal(lot["remainingQty"]) == Decimal(lot["finalGoodQty"]) - Decimal(
            lot["packedQty"]
        )
        assert Decimal(lot["remainingQty"]) > 0


def test_new_units_are_numbered(mes):
    client, created = mes
    assert _new(client, created, "BOX", "b")["packingNo"] == "BX-0031"
    assert _new(client, created, "PALLET", "p")["packingNo"] == "PL-0007"


def test_box_cannot_exceed_lot_good(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    box = _new(client, created, "BOX", "box")
    over = str(Decimal(lot["remainingQty"]) + 1)
    response = _put(client, created, box, lot, over, "over")
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "EXCEEDS_GOOD_QTY"
    assert Decimal(details["availableQty"]) == Decimal(lot["remainingQty"])


def test_quantity_can_be_changed_within_box(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    box = _new(client, created, "BOX", "box")
    full = lot["remainingQty"]
    assert _put(client, created, box, lot, full, "full").status_code == 200
    # 같은 BOX의 기존 수량은 빼고 다시 계산하므로 같은 값으로 다시 저장할 수 있다.
    again = _put(client, created, box, lot, full, "again")
    assert again.status_code == 200
    removed = _put(client, created, box, lot, "0", "remove")
    assert removed.json()["data"]["members"] == []


def test_concurrent_boxes_cannot_overpack(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    boxes = [_new(client, created, "BOX", "b1"), _new(client, created, "BOX", "b2")]
    qty = str((Decimal(lot["remainingQty"]) * Decimal("0.6")).to_integral_value())

    def put(pair):
        box, key = pair
        return _put(client, created, box, lot, qty, key).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(put, zip(boxes, ["race-a", "race-b"], strict=True)))
    assert codes == [200, 409]


def test_box_holds_single_item(mes):
    client, created = mes
    first, second = _rows(client, "/packable-lots")
    assert first["itemId"] != second["itemId"]
    box = _new(client, created, "BOX", "box")
    _put(client, created, box, first, "10", "one")
    response = _put(client, created, box, second, "10", "two")
    assert _reason(response) == "MIXED_ITEM"


def test_all_defective_lot_cannot_be_packed(mes):
    client, created = mes
    defective = next(
        x for x in _rows(client, "/lots") if x["completionReason"] == "all_defective"
    )
    box = _new(client, created, "BOX", "box")
    response = _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box['id']}/members",
        "bad",
        {"lotId": defective["id"], "packedQty": "1"},
    )
    assert response.status_code == 400
    assert "lotId" in response.json()["error"]["details"]["fields"]


def test_lot_goes_in_box_not_pallet(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    pallet = _new(client, created, "PALLET", "pl")
    response = _put(client, created, pallet, lot, "1", "pl-put")
    assert _reason(response) == "NOT_A_BOX"


def test_close_rules(mes):
    client, created = mes
    empty = _new(client, created, "BOX", "empty")
    response = _call(
        client, created, "POST", f"/packing-units/{empty['id']}/close", "c"
    )
    assert _reason(response) == "UNIT_EMPTY"
    lot = _rows(client, "/packable-lots")[0]
    box = _closed_box(client, created, lot, "10", "cb")
    locked = _put(client, created, box, lot, "5", "after-close")
    assert _reason(locked) == "UNIT_CLOSED"


def test_pallet_needs_closed_boxes_and_one_item(mes):
    client, created = mes
    first, second = _rows(client, "/packable-lots")
    pallet = _new(client, created, "PALLET", "pl")
    open_box = _new(client, created, "BOX", "open")
    _put(client, created, open_box, first, "5", "open-put")
    not_closed = _call(
        client,
        created,
        "PUT",
        f"/packing-units/{open_box['id']}/parent",
        "attach-open",
        {"parentPackingUnitId": pallet["id"]},
    )
    assert _reason(not_closed) == "BOX_NOT_CLOSED"
    box_a = _closed_box(client, created, first, "10", "a")
    box_b = _closed_box(client, created, second, "10", "b")
    ok = _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box_a['id']}/parent",
        "attach-a",
        {"parentPackingUnitId": pallet["id"]},
    )
    assert ok.status_code == 200
    mixed = _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box_b['id']}/parent",
        "attach-b",
        {"parentPackingUnitId": pallet["id"]},
    )
    assert _reason(mixed) == "MIXED_ITEM"


def test_receive_pallet_flow(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    pallet = _new(client, created, "PALLET", "pl")
    box = _closed_box(client, created, lot, lot["remainingQty"], "box")
    _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box['id']}/parent",
        "attach",
        {"parentPackingUnitId": pallet["id"]},
    )
    open_pallet = _call(
        client,
        created,
        "POST",
        "/finished-goods-receipts",
        "early",
        {"packingUnitId": pallet["id"]},
    )
    assert _reason(open_pallet) == "UNIT_OPEN"
    _call(client, created, "POST", f"/packing-units/{pallet['id']}/close", "close")
    received = _call(
        client,
        created,
        "POST",
        "/finished-goods-receipts",
        "recv",
        {"packingUnitId": pallet["id"]},
    )
    assert received.status_code == 201
    data = received.json()["data"]
    assert (data["status"], data["totalQty"]) == (
        "received",
        str(Decimal(lot["remainingQty"])),
    )
    # 하위 BOX는 closed로 두고 표시 상태만 부모를 따른다(FS-006b)
    box_after = _unit(client, box["packingNo"])
    assert (box_after["status"], box_after["displayStatus"]) == ("closed", "received")
    again = _call(
        client,
        created,
        "POST",
        "/finished-goods-receipts",
        "again",
        {"packingUnitId": pallet["id"]},
    )
    assert _reason(again) == "ALREADY_RECEIVED"
    detach = _call(
        client,
        created,
        "PUT",
        f"/packing-units/{box['id']}/parent",
        "detach",
        {"parentPackingUnitId": None},
    )
    assert _reason(detach) == "UNIT_CLOSED"
    assert any(
        r["packingNo"] == pallet["packingNo"]
        for r in _rows(client, "/finished-goods-receipts")
    )


def test_box_cannot_be_received(mes):
    client, created = mes
    lot = _rows(client, "/packable-lots")[0]
    box = _closed_box(client, created, lot, "5", "box")
    response = _call(
        client,
        created,
        "POST",
        "/finished-goods-receipts",
        "box",
        {"packingUnitId": box["id"]},
    )
    assert _reason(response) == "NOT_A_PALLET"


def test_only_empty_open_unit_can_be_deleted(mes):
    client, created = mes
    empty = _new(client, created, "BOX", "empty")
    assert (
        _call(
            client, created, "DELETE", f"/packing-units/{empty['id']}", "d"
        ).status_code
        == 204
    )
    used = _unit(client, "PL-0002")
    response = _call(client, created, "DELETE", f"/packing-units/{used['id']}", "d2")
    assert _reason(response) == "UNIT_NOT_EMPTY"
