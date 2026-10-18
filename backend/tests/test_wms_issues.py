"""W2b-1e 생산 불출(W-13) 업무 규칙 (DSN-13 F25, Q4·Q5)."""

from decimal import Decimal

from test_wms import W, _call, _ok, _reason
from test_wms_picks import _create_lot, _hold_lot
from test_wms_reservations import post, receiving_env

__all__ = ["receiving_env"]


def _line_location(env, code="R-LINE", kind="LINE"):
    return _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/warehouses/{env[3]['warehouse']}/locations",
            {"code": code, "name": "생산 라인", "locationType": kind},
        ),
        201,
    )["id"]


def _lot_item(env, code="RAW-LOT"):
    """LOT 추적 원자재를 하나 만든다. 시드의 RM-PBT는 lot_tracked=false라 LOT을 못 넣는다."""
    item = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            "/items",
            {
                "itemCode": code,
                "name": "LOT 추적 자재",
                "baseUnit": "KG",
                "itemClass": "RAW",
                "lotTracked": True,
            },
        ),
        201,
    )
    env[3][code] = item["id"]
    return item["id"]


def _create(env, line_location_id, lines, **extra):
    body = {"lineLocationId": line_location_id, "lines": lines}
    body.update(extra)
    return _call(env[0], env[1], "POST", "/issue-requests", body)


def _confirm(env, request_id, lines=None):
    body = {} if lines is None else {"lines": lines}
    return _call(env[0], env[1], "POST", f"/issue-requests/{request_id}/confirm", body)


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


def test_issue_request_allocates_fefo_and_moves_stock_to_line(receiving_env):
    env = receiving_env
    line_id = _line_location(env)
    loc = env[3]["R-A01"]
    item_id = _lot_item(env)
    _create_lot(
        env,
        "LOT-OLD",
        received_on="2026-07-01",
        expiry_date="2099-01-01",
        item="RAW-LOT",
    )
    _create_lot(
        env,
        "LOT-NEW",
        received_on="2026-08-01",
        expiry_date="2099-12-01",
        item="RAW-LOT",
    )
    post(env, "40", item="RAW-LOT", lot="LOT-OLD", loc=loc)
    post(env, "40", item="RAW-LOT", lot="LOT-NEW", loc=loc)

    req = _ok(
        _create(
            env, line_id, [{"itemId": item_id, "qty": "50"}], workOrderNo="WO-2026-001"
        ),
        201,
    )
    assert req["status"] == "OPEN"
    assert req["requestNo"].startswith("IR-")
    assert req["workOrderNo"] == "WO-2026-001"
    assert req["lineLocationType"] == "LINE"

    # FEFO: 유효기간이 빠른 LOT-OLD(40)를 먼저 쓰고 모자란 10을 LOT-NEW에서 채운다.
    preview = req["allocationPreview"]
    assert [p["lotNo"] for p in preview] == ["LOT-OLD", "LOT-NEW"]
    assert [Decimal(p["qty"]) for p in preview] == [Decimal(40), Decimal(10)]
    assert req["shortages"] == []

    done = _ok(_confirm(env, req["id"]))
    assert done["status"] == "ISSUED"
    assert done["issuedAt"] and done["stockDocumentId"]
    assert Decimal(done["lines"][0]["issuedQty"]) == Decimal(50)

    # 원장: 보관 칸에서 50이 빠지고 라인 칸에 50이 들어온다. 총량은 그대로다.
    assert _on_hand(env, loc, "RAW-LOT") == Decimal(30)
    assert _on_hand(env, line_id, "RAW-LOT") == Decimal(50)

    # 재확정은 409로 막고 전표를 더 만들지 않는다.
    again = _confirm(env, req["id"])
    assert again.status_code == 409 and _reason(again) == "INVALID_STATE"


def test_issue_request_skips_held_lot_and_rejects_when_short(receiving_env):
    env = receiving_env
    line_id = _line_location(env, code="R-LINE2")
    loc = env[3]["R-A01"]
    item_id = _lot_item(env, code="RAW-LOT2")
    held = _create_lot(env, "LOT-HELD", received_on="2026-07-01", item="RAW-LOT2")
    _create_lot(env, "LOT-FREE", received_on="2026-09-01", item="RAW-LOT2")
    post(env, "30", item="RAW-LOT2", lot="LOT-HELD", loc=loc)
    post(env, "20", item="RAW-LOT2", lot="LOT-FREE", loc=loc)
    _hold_lot(env, held["id"])

    # 보류 LOT 30은 가용에서 빠지므로 25를 요청하면 20만 남아 부족하다.
    req = _ok(_create(env, line_id, [{"itemId": item_id, "qty": "25"}]), 201)
    assert [s["shortageQty"] for s in req["shortages"]] == ["5.000"]
    assert [p["lotNo"] for p in req["allocationPreview"]] == ["LOT-FREE"]

    short = _confirm(env, req["id"])
    assert short.status_code == 409 and _reason(short) == "INSUFFICIENT_AVAILABLE"

    # 부분 불출(20)은 통과한다.
    ok = _ok(
        _confirm(env, req["id"], [{"lineId": req["lines"][0]["id"], "issuedQty": "20"}])
    )
    assert ok["status"] == "ISSUED"
    assert _on_hand(env, line_id, "RAW-LOT2") == Decimal(20)
    assert _on_hand(env, loc, "RAW-LOT2") == Decimal(30)  # 보류 LOT은 그대로 남는다


def test_issue_request_cancel_requires_reason_and_keeps_stock(receiving_env):
    env = receiving_env
    line_id = _line_location(env, code="R-LINE3")
    loc = env[3]["R-A01"]
    post(env, "10", item="RM-PBT", loc=loc)
    req = _ok(_create(env, line_id, [{"itemId": env[3]["RM-PBT"], "qty": "5"}]), 201)

    blank = _call(
        env[0],
        env[1],
        "POST",
        f"/issue-requests/{req['id']}/cancel",
        {"cancelReason": "  "},
    )
    assert blank.status_code == 400

    done = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/issue-requests/{req['id']}/cancel",
            {"cancelReason": "작업지시 취소"},
        )
    )
    assert done["status"] == "CANCELLED"
    assert done["cancelReason"] == "작업지시 취소"
    assert done["issuedAt"] is None and done["stockDocumentId"] is None
    assert _on_hand(env, loc, "RM-PBT") == Decimal(10)  # 재고는 움직이지 않는다
    assert _on_hand(env, line_id, "RM-PBT") == Decimal(0)

    after = _confirm(env, req["id"])
    assert after.status_code == 409 and _reason(after) == "INVALID_STATE"


def test_issue_request_rejects_bad_line_location_and_duplicate_items(receiving_env):
    env = receiving_env
    quarantine = env[3]["quarantine"]
    bad = _create(env, quarantine, [{"itemId": env[3]["RM-PBT"], "qty": "1"}])
    assert bad.status_code == 400

    line_id = _line_location(env, code="R-LINE4")
    dup = _create(
        env,
        line_id,
        [
            {"itemId": env[3]["RM-PBT"], "qty": "1"},
            {"itemId": env[3]["RM-PBT"], "qty": "2"},
        ],
    )
    assert dup.status_code == 400
