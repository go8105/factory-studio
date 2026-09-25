"""FS-020c MES 생산계획(M-02)·작업지시(M-03) API. 검증 항목마다 테스트를 나눈다."""

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


def _item(client, code: str) -> dict:
    return next(i for i in _rows(client, "/items") if i["itemCode"] == code)


def _route(client, code: str, version: int = 1) -> dict:
    return next(
        r
        for r in _rows(client, "/routes")
        if r["routeCode"] == code and r["version"] == version
    )


def _open_line(client, item_code: str = "FG-C100") -> dict:
    """확정 계획 중 잔여가 가장 많은 라인."""
    item_id = _item(client, item_code)["id"]
    lines = [
        line
        for plan in _rows(client, "/production-plans")
        if plan["status"] == "confirmed"
        for line in plan["lines"]
        if line["itemId"] == item_id
    ]
    return max(lines, key=lambda line: Decimal(line["remainingQty"]))


def _order_body(client, line: dict, qty: str, **override) -> dict:
    return {
        "productionPlanLineId": line["id"],
        "routeVersionId": _route(client, "RT-C100")["id"],
        "planQty": qty,
        "planStartDate": "2026-09-28",
        "planEndDate": "2026-09-30",
        **override,
    }


def _line_after(client, line_id: int) -> dict:
    return next(
        line
        for plan in _rows(client, "/production-plans")
        for line in plan["lines"]
        if line["id"] == line_id
    )


# ---- M-02 생산계획 ----
def test_seed_plans_show_allocation(mes):
    client, _ = mes
    plans = _rows(client, "/production-plans")
    assert [p["planCode"] for p in plans] == ["PP-2026-09", "PP-2026-08"]
    assert all(p["status"] == "confirmed" for p in plans)
    for line in plans[0]["lines"]:
        assert Decimal(line["remainingQty"]) == Decimal(line["planQty"]) - Decimal(
            line["allocatedQty"]
        )
    assert any(Decimal(line["allocatedQty"]) > 0 for line in plans[0]["lines"])


def _draft_plan(client, created, key="plan") -> dict:
    response = _call(
        client,
        created,
        "POST",
        "/production-plans",
        key,
        {"planCode": "PP-2026-10", "targetMonth": "2026-10", "salesPlanCode": "  "},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]


def test_blank_sales_plan_code_is_stored_as_null(mes):
    client, created = mes
    plan = _draft_plan(client, created)
    assert (plan["status"], plan["salesPlanCode"], plan["lines"]) == ("draft", None, [])


def test_plan_lines_take_item_base_unit(mes):
    client, created = mes
    plan = _draft_plan(client, created)
    pbt = _item(client, "RM-PBT")
    response = _call(
        client,
        created,
        "PUT",
        f"/production-plans/{plan['id']}/lines",
        "lines",
        {"lines": [{"itemId": pbt["id"], "targetWeek": "2026-W41", "planQty": "12.5"}]},
    )
    assert response.status_code == 200
    line = response.json()["data"]["lines"][0]
    assert (line["unit"], line["planQty"], line["allocatedQty"]) == (
        "KG",
        "12.500",
        "0",
    )


@pytest.mark.parametrize(
    ("lines", "message"),
    [
        (
            [("FG-C100", "2026-W41", "10"), ("FG-C100", "2026-W41", "20")],
            "같은 품목·주차",
        ),
        ([("FG-C100", "2026-W41", "10.5")], "정수"),
    ],
    ids=["duplicate-week", "ea-integer"],
)
def test_plan_line_rules(mes, lines, message):
    client, created = mes
    plan = _draft_plan(client, created)
    body = {
        "lines": [
            {"itemId": _item(client, code)["id"], "targetWeek": week, "planQty": qty}
            for code, week, qty in lines
        ]
    }
    response = _call(
        client, created, "PUT", f"/production-plans/{plan['id']}/lines", "bad", body
    )
    assert response.status_code == 400
    assert message in response.json()["error"]["details"]["fields"]["lines"]


def test_empty_plan_cannot_be_confirmed(mes):
    client, created = mes
    plan = _draft_plan(client, created)
    response = _call(
        client, created, "POST", f"/production-plans/{plan['id']}/confirm", "conf"
    )
    assert response.status_code == 409
    assert _reason(response) == "EMPTY_PLAN"


def test_confirmed_plan_is_locked(mes):
    client, created = mes
    plan = next(p for p in _rows(client, "/production-plans"))
    for method, path, body in (
        ("PUT", f"/production-plans/{plan['id']}/lines", {"lines": []}),
        ("PATCH", f"/production-plans/{plan['id']}", {"salesPlanCode": "X"}),
        ("DELETE", f"/production-plans/{plan['id']}", None),
    ):
        response = _call(client, created, method, path, f"lock-{method}", body)
        assert response.status_code == 409
        assert _reason(response) == "PLAN_CONFIRMED"


def test_draft_plan_confirm_and_delete(mes):
    client, created = mes
    plan = _draft_plan(client, created)
    body = {
        "lines": [
            {
                "itemId": _item(client, "FG-C100")["id"],
                "targetWeek": "2026-W41",
                "planQty": "100",
            }
        ]
    }
    _call(client, created, "PUT", f"/production-plans/{plan['id']}/lines", "l", body)
    confirmed = _call(
        client, created, "POST", f"/production-plans/{plan['id']}/confirm", "c"
    )
    assert confirmed.json()["data"]["status"] == "confirmed"
    other = _call(
        client,
        created,
        "POST",
        "/production-plans",
        "p2",
        {"planCode": "PP-TMP", "targetMonth": "2026-11"},
    ).json()["data"]
    deleted = _call(client, created, "DELETE", f"/production-plans/{other['id']}", "d")
    assert deleted.status_code == 204


# ---- M-03 작업지시 ----
def test_create_order_from_confirmed_line(mes):
    client, created = mes
    line = _open_line(client)
    response = _call(
        client, created, "POST", "/work-orders", "wo", _order_body(client, line, "100")
    )
    assert response.status_code == 201, response.text
    order = response.json()["data"]
    assert (order["orderNo"], order["status"], order["lotNo"]) == (
        "WO-0031",
        "draft",
        None,
    )
    after = _line_after(client, line["id"])
    assert Decimal(after["allocatedQty"]) == Decimal(line["allocatedQty"]) + 100


def test_allocation_cannot_exceed_plan(mes):
    client, created = mes
    line = _open_line(client)
    over = str(Decimal(line["remainingQty"]) + 1)
    response = _call(
        client, created, "POST", "/work-orders", "over", _order_body(client, line, over)
    )
    assert response.status_code == 409
    details = response.json()["error"]["details"]
    assert details["reason"] == "PLAN_QTY_EXCEEDED"
    assert Decimal(details["remainingQty"]) == Decimal(line["remainingQty"])


def test_concurrent_orders_cannot_overallocate(mes):
    client, created = mes
    line = _open_line(client)
    # 잔여의 60%씩 두 건을 동시에 넣으면 한 건만 들어가야 한다(공간·계획 라인 잠금).
    qty = str((Decimal(line["remainingQty"]) * Decimal("0.6")).to_integral_value())

    def post(key: str):
        return _call(
            client, created, "POST", "/work-orders", key, _order_body(client, line, qty)
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        codes = sorted(pool.map(post, ["race-a", "race-b"]))
    assert codes == [201, 409]
    after = _line_after(client, line["id"])
    assert Decimal(after["remainingQty"]) >= 0


def test_draft_plan_line_is_rejected(mes):
    client, created = mes
    plan = _draft_plan(client, created)
    body = {
        "lines": [
            {
                "itemId": _item(client, "FG-C100")["id"],
                "targetWeek": "2026-W41",
                "planQty": "100",
            }
        ]
    }
    lines = _call(
        client, created, "PUT", f"/production-plans/{plan['id']}/lines", "l", body
    ).json()["data"]["lines"]
    response = _call(
        client,
        created,
        "POST",
        "/work-orders",
        "wo",
        _order_body(client, lines[0], "10"),
    )
    assert response.status_code == 400
    assert "productionPlanLineId" in response.json()["error"]["details"]["fields"]


def test_unpublished_or_foreign_route_is_rejected(mes):
    client, created = mes
    line = _open_line(client)
    draft = _call(
        client,
        created,
        "POST",
        f"/routes/{_route(client, 'RT-C100')['id']}/revise",
        "rv",
    ).json()["data"]
    unpublished = _call(
        client,
        created,
        "POST",
        "/work-orders",
        "wo1",
        _order_body(client, line, "10", routeVersionId=draft["id"]),
    )
    assert unpublished.status_code == 400
    foreign = _call(
        client,
        created,
        "POST",
        "/work-orders",
        "wo2",
        _order_body(client, line, "10", routeVersionId=_route(client, "RT-C200")["id"]),
    )
    assert foreign.status_code == 400
    assert "routeVersionId" in foreign.json()["error"]["details"]["fields"]


def test_draft_order_update_excludes_itself(mes):
    client, created = mes
    line = _open_line(client)
    remaining = line["remainingQty"]
    order = _call(
        client,
        created,
        "POST",
        "/work-orders",
        "all",
        _order_body(client, line, remaining),
    ).json()["data"]
    same = _call(
        client,
        created,
        "PATCH",
        f"/work-orders/{order['id']}",
        "same",
        {"planQty": remaining},
    )
    assert same.status_code == 200
    more = _call(
        client,
        created,
        "PATCH",
        f"/work-orders/{order['id']}",
        "more",
        {"planQty": str(Decimal(remaining) + 1)},
    )
    assert _reason(more) == "PLAN_QTY_EXCEEDED"


def test_cancel_needs_reason_and_returns_allocation(mes):
    client, created = mes
    line = _open_line(client)
    order = _call(
        client, created, "POST", "/work-orders", "wo", _order_body(client, line, "50")
    ).json()["data"]
    blank = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/cancel",
        "c0",
        {"cancelReason": "  "},
    )
    assert blank.status_code == 400
    ok = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/cancel",
        "c1",
        {"cancelReason": "계획 변경"},
    )
    assert (ok.json()["data"]["status"], ok.json()["data"]["cancelReason"]) == (
        "cancelled",
        "계획 변경",
    )
    assert _line_after(client, line["id"])["allocatedQty"] == line["allocatedQty"]


def test_release_creates_lot_and_locks_order(mes):
    client, created = mes
    line = _open_line(client)
    order = _call(
        client, created, "POST", "/work-orders", "wo", _order_body(client, line, "10")
    ).json()["data"]
    released = _call(
        client, created, "POST", f"/work-orders/{order['id']}/release", "r"
    )
    data = released.json()["data"]
    assert (data["status"], data["lotNo"], data["lotStatus"]) == (
        "released",
        "LT-0027",
        "ready",
    )
    assert data["releasedAt"] is not None
    for method, path, body in (
        ("PATCH", f"/work-orders/{order['id']}", {"planQty": "5"}),
        ("POST", f"/work-orders/{order['id']}/cancel", {"cancelReason": "x"}),
        ("POST", f"/work-orders/{order['id']}/release", None),
    ):
        response = _call(client, created, method, path, f"after-{path}", body)
        assert _reason(response) == "ORDER_RELEASED"


def test_release_rechecks_published_route(mes):
    client, created = mes
    line = _open_line(client)
    order = _call(
        client, created, "POST", "/work-orders", "wo", _order_body(client, line, "10")
    ).json()["data"]
    _call(client, created, "POST", f"/routes/{order['routeVersionId']}/retire", "ret")
    response = _call(
        client, created, "POST", f"/work-orders/{order['id']}/release", "r"
    )
    assert response.status_code == 409
    assert _reason(response) == "VERSION_NOT_PUBLISHED"


def test_released_order_without_lot_gets_one(mes):
    client, created = mes
    waiting = [
        o
        for o in _rows(client, "/work-orders")
        if o["status"] == "released" and o["lotId"] is None
    ]
    assert len(waiting) == 3
    target = waiting[0]
    first = _call(client, created, "POST", f"/work-orders/{target['id']}/lot", "lot")
    assert first.status_code == 201
    assert first.json()["data"]["lotStatus"] == "ready"
    again = _call(client, created, "POST", f"/work-orders/{target['id']}/lot", "lot2")
    assert _reason(again) == "LOT_NOT_ALLOWED"


def test_order_without_bom_is_allowed(mes):
    client, created = mes
    line = _open_line(client)
    response = _call(
        client,
        created,
        "POST",
        "/work-orders",
        "nobom",
        _order_body(client, line, "10", bomVersionId=None),
    )
    assert response.status_code == 201
    assert response.json()["data"]["bomVersionId"] is None


def test_order_requires_csrf(mes):
    client, _ = mes
    response = client.post(
        f"{BASE}/work-orders", json={}, headers={"Idempotency-Key": "k"}
    )
    assert response.status_code in (400, 403)
