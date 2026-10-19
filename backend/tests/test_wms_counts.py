"""W2b-1f 재고 실사(W-14)·재고 마감(W-15) 업무 규칙 (DSN-13 F35·F39, Q6)."""

from decimal import Decimal

from test_wms import W, _call, _ok, _reason
from test_wms_reservations import post, receiving_env

__all__ = ["receiving_env"]


def _create(env, **extra):
    body = {"warehouseId": env[3]["warehouse"], "kind": "FULL"}
    body.update(extra)
    return _call(env[0], env[1], "POST", "/count-orders", body)


def _act(env, count_id, action, body=None):
    return _call(
        env[0], env[1], "POST", f"/count-orders/{count_id}/{action}", body or {}
    )


def _on_hand(env, location_id, item_code):
    rows = _ok(env[0].get(W + "/stock"))
    rows = rows["rows"] if isinstance(rows, dict) else rows
    return sum(
        (
            Decimal(r["onHand"])
            for r in rows
            if r["locationId"] == location_id and r["itemCode"] == item_code
        ),
        Decimal(0),
    )


def test_count_snapshots_book_qty_and_adjusts_only_differences(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    post(env, "30", item="RM-PBT", loc=loc)
    post(env, "20", item="RM-PIN", loc=loc)

    order = _ok(_create(env), 201)
    assert order["status"] == "OPEN"
    assert order["countNo"].startswith("CT-")
    assert order["lineCount"] == 2
    # 장부 수량을 시작 시점에 굳힌다. 실사 전에는 차이가 없다.
    assert {line["itemCode"]: line["bookQty"] for line in order["lines"]} == {
        "RM-PBT": "30.000",
        "RM-PIN": "20.000",
    }
    assert all(line["diffQty"] is None for line in order["lines"])

    # 실사 중인 위치는 재고를 옮길 수 없다(실사 잠금).
    blocked = _call(
        env[0],
        env[1],
        "POST",
        "/documents",
        {
            "documentType": "ADJUSTMENT",
            "reasonCode": "COUNT",
            "lines": [{"itemId": env[3]["RM-PBT"], "locationId": loc, "qty": "1"}],
        },
    )
    doc_id = _ok(blocked, 201)["id"]
    posted = _call(env[0], env[1], "POST", f"/documents/{doc_id}/post", {})
    assert posted.status_code == 409 and _reason(posted) == "COUNT_IN_PROGRESS"

    pbt = next(x for x in order["lines"] if x["itemCode"] == "RM-PBT")
    cop = next(x for x in order["lines"] if x["itemCode"] == "RM-PIN")
    counted = _ok(
        _act(
            env,
            order["id"],
            "count",
            {
                "lines": [
                    {"lineId": pbt["id"], "countedQty": "28"},
                    {"lineId": cop["id"], "countedQty": "20"},
                ]
            },
        )
    )
    assert counted["status"] == "COUNTED"
    assert counted["diffCount"] == 1  # 차이가 있는 줄만 센다

    done = _ok(_act(env, order["id"], "adjust"))
    assert done["status"] == "ADJUSTED"
    assert done["stockDocumentId"]  # 차이가 있으니 CYCLE_COUNT 전표가 생긴다
    assert _on_hand(env, loc, "RM-PBT") == Decimal(28)
    assert _on_hand(env, loc, "RM-PIN") == Decimal(20)

    again = _act(env, order["id"], "adjust")
    assert again.status_code == 409 and _reason(again) == "INVALID_STATE"


def test_count_without_difference_closes_without_document(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    post(env, "15", item="RM-PBT", loc=loc)
    order = _ok(_create(env), 201)
    line = order["lines"][0]
    _ok(
        _act(
            env,
            order["id"],
            "count",
            {"lines": [{"lineId": line["id"], "countedQty": "15"}]},
        )
    )
    done = _ok(_act(env, order["id"], "adjust"))
    assert done["status"] == "ADJUSTED"
    assert done["stockDocumentId"] is None  # 차이가 없으면 전표를 만들지 않는다
    assert done["diffCount"] == 0


def test_count_rejects_second_open_order_and_allows_cancel(receiving_env):
    env = receiving_env
    post(env, "10", item="RM-PBT", loc=env[3]["R-A01"])
    first = _ok(_create(env), 201)
    dup = _create(env)
    assert dup.status_code == 409 and _reason(dup) == "COUNT_IN_PROGRESS"

    cancelled = _ok(_act(env, first["id"], "cancel"))
    assert cancelled["status"] == "CANCELLED"
    # 취소하면 잠금이 풀려 다시 시작할 수 있다.
    assert _ok(_create(env), 201)["status"] == "OPEN"


def test_count_requires_stock(receiving_env):
    empty = _create(receiving_env)
    assert empty.status_code == 409 and _reason(empty) == "NO_STOCK"


def test_period_close_blocks_documents_in_that_month(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    doc = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            "/documents",
            {
                "documentType": "ADJUSTMENT",
                "reasonCode": "COUNT",
                "lines": [{"itemId": env[3]["RM-PBT"], "locationId": loc, "qty": "5"}],
            },
        ),
        201,
    )
    _ok(_call(env[0], env[1], "POST", f"/documents/{doc['id']}/post", {}))
    month = doc["documentOn"][:7]

    periods = _ok(env[0].get(W + "/stock-periods"))
    assert any(p["periodMonth"] == month and p["status"] == "open" for p in periods)

    closed = _ok(
        _call(env[0], env[1], "POST", "/stock-periods/close", {"periodMonth": month})
    )
    assert closed["status"] == "closed"

    blocked = _call(
        env[0],
        env[1],
        "POST",
        "/documents",
        {
            "documentType": "ADJUSTMENT",
            "reasonCode": "COUNT",
            "documentOn": doc["documentOn"],
            "lines": [{"itemId": env[3]["RM-PBT"], "locationId": loc, "qty": "1"}],
        },
    )
    later = _call(
        env[0], env[1], "POST", f"/documents/{_ok(blocked, 201)['id']}/post", {}
    )
    assert later.status_code == 409 and _reason(later) == "PERIOD_CLOSED"

    _ok(_call(env[0], env[1], "POST", "/stock-periods/reopen", {"periodMonth": month}))
    assert _ok(
        _call(env[0], env[1], "POST", f"/documents/{_ok(blocked, 201)['id']}/post", {})
    )


def test_period_close_rejects_draft_documents(receiving_env):
    env = receiving_env
    doc = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            "/documents",
            {
                "documentType": "ADJUSTMENT",
                "reasonCode": "COUNT",
                "lines": [
                    {
                        "itemId": env[3]["RM-PBT"],
                        "locationId": env[3]["R-A01"],
                        "qty": "3",
                    }
                ],
            },
        ),
        201,
    )
    month = doc["documentOn"][:7]
    blocked = _call(
        env[0], env[1], "POST", "/stock-periods/close", {"periodMonth": month}
    )
    assert blocked.status_code == 409 and _reason(blocked) == "DRAFT_DOCUMENTS"
