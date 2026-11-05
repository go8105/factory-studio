"""W2b-1h 수불부(W-18)·분석(W-19)·점유(W-20) (DSN-13 F52·F54·F55·F37)."""

from decimal import Decimal

from test_wms import W, _call, _ok
from test_wms_reservations import post, receiving_env

__all__ = ["receiving_env"]


def _row(rows, item_code):
    return next(r for r in rows if r["itemCode"] == item_code)


def test_ledger_splits_opening_inbound_outbound_closing(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    post(env, "100", item="RM-PBT", loc=loc)
    # 같은 달 안에서 입고 100 · 출고 30 → 기말 70. 기초는 0이다(이전 달 전표가 없다).
    _ok(
        _call(
            env[0],
            env[1],
            "POST",
            "/documents",
            {
                "documentType": "ADJUSTMENT",
                "reasonCode": "SCRAP",
                "lines": [
                    {"itemId": env[3]["RM-PBT"], "locationId": loc, "qty": "-30"}
                ],
            },
        ),
        201,
    )
    docs = _ok(env[0].get(W + "/documents", params={"status": "draft"}))
    rows = docs["rows"] if isinstance(docs, dict) else docs
    for d in rows:
        _call(env[0], env[1], "POST", f"/documents/{d['id']}/post", {})

    report = _ok(env[0].get(W + "/ledger"))
    pbt = _row(report["rows"], "RM-PBT")
    assert pbt["opening"] == "0.000"
    assert pbt["inbound"] == "100.000"
    assert pbt["outbound"] == "30.000"  # 출고는 양수로 보여 준다
    assert pbt["closing"] == "70.000"


def test_analysis_flags_safety_and_max_and_stale(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    post(env, "5", item="RM-PBT", loc=loc)
    _ok(
        _call(
            env[0],
            env[1],
            "PATCH",
            f"/items/{env[3]['RM-PBT']}",
            {"safetyStock": "10", "maxStock": "100", "abcClass": "A"},
        )
    )
    report = _ok(env[0].get(W + "/analysis"))
    pbt = _row(report["rows"], "RM-PBT")
    assert pbt["onHand"] == "5.000"
    assert pbt["belowSafety"] is True  # 5 < 안전재고 10
    assert pbt["aboveMax"] is False
    assert pbt["abcClass"] == "A"
    # 출고가 한 번도 없으면 장기 체화로 본다.
    assert pbt["lastOutOn"] is None and pbt["stale"] is True
    assert pbt["turnover"] == "0.00"
    assert report["staleDays"] == 90


def test_occupancy_uses_capacity_when_set(receiving_env):
    env = receiving_env
    loc = env[3]["R-A01"]
    post(env, "40", item="RM-PBT", loc=loc)
    before = _ok(env[0].get(W + "/occupancy"))["rows"]
    a01 = next(r for r in before if r["locationCode"] == "R-A01")
    assert a01["onHand"] == "40.000"
    assert a01["capacityQty"] is None  # 용량이 없으면 점유율을 내지 않는다
    assert a01["usagePercent"] is None

    _ok(
        _call(
            env[0],
            env[1],
            "PATCH",
            f"/locations/{loc}",
            {"capacityQty": "50"},
        )
    )
    after = _ok(env[0].get(W + "/occupancy"))["rows"]
    a01 = next(r for r in after if r["locationCode"] == "R-A01")
    assert a01["capacityQty"] == "50.000"
    assert Decimal(a01["usagePercent"]) == Decimal("80.0")
    assert a01["over"] is False
