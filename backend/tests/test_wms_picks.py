"""W2b-1d D-1: 피킹 지시 생성 · FEFO/FIFO LOT 배정 · 보류/만료 제외 검증."""

from decimal import Decimal

from sqlalchemy import text
from test_wms import W, _call, _ok, _reason
from test_wms_reservations import post, receiving_env, reserve

__all__ = ["receiving_env"]


def _create_lot(
    env,
    lot_no: str,
    received_on: str = "2026-09-01",
    expiry_date: str | None = None,
    item: str = "FG-C100",
    status: str = "AVAILABLE",
):
    body = {
        "itemId": env[3][item],
        "lotNo": lot_no,
        "origin": "MES",
        "receivedOn": received_on,
        "expiryDate": expiry_date,
        "status": status,
    }
    return _ok(_call(env[0], env[1], "POST", "/lots", body), 201)


def _hold_lot(env, lot_id: int, reason: str = "외관 불량 의심 보류"):
    return _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/lots/{lot_id}/hold",
            {"source": "MANUAL", "reason": reason},
        ),
        201,
    )


def _release_lot(env, lot_id: int):
    return _ok(_call(env[0], env[1], "POST", f"/lots/{lot_id}/release", {}))


def _create_pick(env, reservation_id: int):
    return _call(
        env[0],
        env[1],
        "POST",
        "/pick-orders",
        {"reservationId": reservation_id},
    )


def test_pick_order_respects_reserved_lot_and_prevents_duplicates(receiving_env):
    env = receiving_env
    loc_a01 = env[3]["F-A01"]
    _create_lot(env, "LOT-EARLY", received_on="2026-08-01", expiry_date="2099-06-01")
    _create_lot(env, "LOT-CHOSEN", received_on="2026-09-01", expiry_date="2099-12-01")
    post(env, "50", item="FG-C100", lot="LOT-EARLY", loc=loc_a01)
    post(env, "50", item="FG-C100", lot="LOT-CHOSEN", loc=loc_a01)

    # 사용자가 LOT-CHOSEN을 직접 지정해 예약한 경우, 더 빠른 유효기간(LOT-EARLY)이 있어도
    # 지정 LOT이 가용하면 그대로 존중한다.
    res = _ok(
        reserve(env, qty="30", item="FG-C100", location=loc_a01, lot="LOT-CHOSEN"),
        201,
    )
    pick = _ok(_create_pick(env, res["id"]), 201)
    assert pick["status"] == "OPEN"
    assert pick["pickNo"].startswith("PK-")
    assert pick["reservationId"] == res["id"]
    assert pick["lotSubstitutions"] == []
    assert len(pick["lines"]) == 1
    assert pick["lines"][0]["lotNo"] == "LOT-CHOSEN"
    assert Decimal(pick["lines"][0]["qty"]) == Decimal(30)
    assert pick["lines"][0]["pickedQty"] is None
    assert pick["lines"][0]["sequenceNo"] == 1

    # 이미 OPEN 피킹 지시가 있는 예약에 재생성 요청 시 409 PICK_ORDER_EXISTS
    dup = _create_pick(env, res["id"])
    assert dup.status_code == 409 and _reason(dup) == "PICK_ORDER_EXISTS"

    # 해제(RELEASED)된 예약은 피킹 지시 생성 불가 (409 INVALID_STATE)
    res2 = _ok(
        reserve(env, qty="10", item="FG-C100", location=loc_a01, lot="LOT-EARLY"),
        201,
    )
    _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/reservations/{res2['id']}/release",
            {"expectedVersion": res2["version"], "reason": "취소"},
        )
    )
    bad = _create_pick(env, res2["id"])
    assert bad.status_code == 409 and _reason(bad) == "INVALID_STATE"


def test_pick_order_excludes_hold_and_expired_and_allocates_fefo_fifo(
    receiving_env, monkeypatch
):
    from fs.wms import picks

    env = receiving_env
    loc_a01 = env[3]["F-A01"]
    loc_a02 = env[3]["F-A02"]

    lot_held = _create_lot(
        env, "LOT-HELD", received_on="2026-07-01", expiry_date="2099-01-01"
    )
    _create_lot(env, "LOT-EXPIRED", received_on="2025-01-01", expiry_date="2025-12-31")
    _create_lot(env, "LOT-QMS-HELD", received_on="2026-07-05", expiry_date="2099-02-01")
    _create_lot(env, "LOT-FEFO-1", received_on="2026-08-10", expiry_date="2099-05-01")
    _create_lot(env, "LOT-FEFO-2", received_on="2026-08-01", expiry_date="2099-08-01")
    _create_lot(env, "LOT-FIFO-1", received_on="2026-08-01", expiry_date=None)

    post(env, "40", item="FG-C100", lot="LOT-HELD", loc=loc_a01)
    post(env, "40", item="FG-C100", lot="LOT-EXPIRED", loc=loc_a01)
    post(env, "40", item="FG-C100", lot="LOT-QMS-HELD", loc=loc_a01)
    # LOT-FEFO-1(유효기간 더 빠름)은 F-A02에, LOT-FEFO-2(유효기간 더 늦음)는 F-A01에 배치
    post(env, "25", item="FG-C100", lot="LOT-FEFO-1", loc=loc_a02)
    post(env, "25", item="FG-C100", lot="LOT-FEFO-2", loc=loc_a01)
    post(env, "25", item="FG-C100", lot="LOT-FIFO-1", loc=loc_a01)

    res = _ok(
        reserve(env, qty="40", item="FG-C100", location=loc_a01, lot="LOT-HELD"),
        201,
    )

    # 예약 후 LOT-HELD를 보류 처리하고, LOT-QMS-HELD는 QMS 보류로 설정
    _hold_lot(env, lot_held["id"], "수분 함량 재검 보류")
    monkeypatch.setattr(picks.qms, "held_lot_nos", lambda *_: {"LOT-QMS-HELD"})

    pick = _ok(_create_pick(env, res["id"]), 201)

    # 1) HOLD(LOT-HELD), EXPIRED(LOT-EXPIRED), QMS_HOLD(LOT-QMS-HELD)는 모두 제외되고
    #    FEFO 1순위 LOT-FEFO-1(25 EA, F-A02) + 2순위 LOT-FEFO-2(15 EA, F-A01)가 배정된다.
    # 2) 피킹 동선(sequenceNo)은 위치 코드(F-A01 -> F-A02) 순으로 1, 2가 부여된다.
    assert [
        (x["sequenceNo"], x["locationCode"], x["lotNo"], Decimal(x["qty"]))
        for x in pick["lines"]
    ] == [
        (1, "F-A01", "LOT-FEFO-2", Decimal(15)),
        (2, "F-A02", "LOT-FEFO-1", Decimal(25)),
    ]

    # 3) 예약 LOT(LOT-HELD)을 쓰지 못한 사실과 사유가 반환된다 (상세/목록 조회에서도 동일)
    assert len(pick["lotSubstitutions"]) == 1
    sub = pick["lotSubstitutions"][0]
    assert sub["requestedLotNo"] == "LOT-HELD"
    assert sub["reason"] == "HOLD"
    assert "보류" in sub["reasonLabel"]
    assert {x["lotNo"] for x in sub["allocatedLots"]} == {"LOT-FEFO-1", "LOT-FEFO-2"}

    detail = _ok(env[0].get(f"{W}/pick-orders/{pick['id']}"))
    assert len(detail["lotSubstitutions"]) == 1
    assert detail["lotSubstitutions"][0]["requestedLotNo"] == "LOT-HELD"


def test_pick_order_fifo_nulls_last_and_seed_lot_left_join(receiving_env):
    env = receiving_env
    loc_a01 = env[3]["F-A01"]

    # 예약용 LOT(보류시킬 LOT)과 유효기간 없는 LOT 2개 + wms.lot 행이 없는 시드형 LOT 1개
    lot_reserved = _create_lot(
        env, "LOT-RSV-HOLD", received_on="2026-07-01", expiry_date=None
    )
    _create_lot(env, "LOT-NOEXP-LATE", received_on="2026-09-10", expiry_date=None)
    _create_lot(env, "LOT-NOEXP-EARLY", received_on="2026-08-01", expiry_date=None)

    post(env, "30", item="FG-C100", lot="LOT-RSV-HOLD", loc=loc_a01)
    post(env, "20", item="FG-C100", lot="LOT-NOEXP-LATE", loc=loc_a01)
    post(env, "20", item="FG-C100", lot="LOT-NOEXP-EARLY", loc=loc_a01)
    # wms.lot 마스터 행 없이 원장 이동만 있는 LOT (시드 LT-0001~0012와 동일 조건)
    post(env, "15", item="FG-C100", lot="LT-SEED-ONLY", loc=loc_a01)

    res = _ok(
        reserve(env, qty="30", item="FG-C100", location=loc_a01, lot="LOT-RSV-HOLD"),
        201,
    )
    _hold_lot(env, lot_reserved["id"], "보류 테스트")

    pick = _ok(_create_pick(env, res["id"]), 201)
    # expiry_date가 모두 NULL이므로 received_on 빠른 순(FIFO):
    # LOT-NOEXP-EARLY(2026-08-01, 20) -> LOT-NOEXP-LATE(2026-09-10, 10)
    assert [(x["lotNo"], Decimal(x["qty"])) for x in pick["lines"]] == [
        ("LOT-NOEXP-EARLY", Decimal(20)),
        ("LOT-NOEXP-LATE", Decimal(10)),
    ]

    # wms.lot 행이 없는 LT-SEED-ONLY를 직접 예약해도 LEFT JOIN 덕분에 정상 배정된다.
    res_seed = _ok(
        reserve(env, qty="15", item="FG-C100", location=loc_a01, lot="LT-SEED-ONLY"),
        201,
    )
    pick_seed = _ok(_create_pick(env, res_seed["id"]), 201)
    assert len(pick_seed["lines"]) == 1
    assert pick_seed["lines"][0]["lotNo"] == "LT-SEED-ONLY"
    assert Decimal(pick_seed["lines"][0]["qty"]) == Decimal(15)


def test_pick_order_insufficient_available_and_cancelled_reopen(receiving_env):
    env = receiving_env
    loc_a01 = env[3]["F-A01"]

    lot_only = _create_lot(
        env, "LOT-ONLY-ONE", received_on="2026-09-01", expiry_date="2099-10-01"
    )
    post(env, "40", item="FG-C100", lot="LOT-ONLY-ONE", loc=loc_a01)

    res = _ok(
        reserve(env, qty="40", item="FG-C100", location=loc_a01, lot="LOT-ONLY-ONE"),
        201,
    )
    _hold_lot(env, lot_only["id"], "전량 보류")

    # 보류 제외 후 가용 재고가 0이므로 409 INSUFFICIENT_AVAILABLE + details 반환
    short = _create_pick(env, res["id"])
    assert short.status_code == 409 and _reason(short) == "INSUFFICIENT_AVAILABLE"
    details = short.json()["error"]["details"]
    assert details["itemCode"] == "FG-C100"
    assert Decimal(details["requested"]) == Decimal(40)
    assert Decimal(details["available"]) == Decimal(0)
    assert any(
        x["lotNo"] == "LOT-ONLY-ONE" and x["reason"] == "HOLD"
        for x in details["excludedLots"]
    )

    # 보류를 해제하면 정상 생성된다
    _release_lot(env, lot_only["id"])
    pick = _ok(_create_pick(env, res["id"]), 201)
    assert pick["status"] == "OPEN"

    # c1482 검증: 취소(CANCELLED) 상태인 pick_order가 있을 때 같은 예약으로 재생성하면
    # UniqueViolation 없이 기존 행을 OPEN으로 되살린다.
    with env[2].begin() as c:
        c.execute(
            text(
                "UPDATE wms.pick_order SET status='CANCELLED', cancel_reason='현장 요청 취소' WHERE id=:id"
            ),
            {"id": pick["id"]},
        )

    reopened = _ok(_create_pick(env, res["id"]), 201)
    assert reopened["id"] == pick["id"]
    assert reopened["status"] == "OPEN"
    assert reopened["cancelReason"] is None
    assert len(reopened["lines"]) == 1
    assert Decimal(reopened["lines"][0]["qty"]) == Decimal(40)

    # OPEN 피킹 지시가 참조 중인 위치/품목 비활성화 차단(guard_master)
    assert (
        _call(
            env[0], env[1], "PATCH", f"/locations/{loc_a01}", {"isActive": False}
        ).status_code
        == 409
    )


def test_partial_reserved_lot_shortage_and_shipping_normal_stock(receiving_env):
    env = receiving_env
    loc_a01 = env[3]["F-A01"]
    fg_wh = next(
        x["id"] for x in _ok(env[0].get(W + "/warehouses")) if x["code"] == "WH-FG"
    )

    _create_lot(env, "LOT-PART", received_on="2026-08-01", expiry_date="2099-09-01")
    _create_lot(env, "LOT-FILL", received_on="2026-08-05", expiry_date="2099-05-01")
    post(env, "40", item="FG-C100", lot="LOT-PART", loc=loc_a01)
    post(env, "30", item="FG-C100", lot="LOT-FILL", loc=loc_a01)

    res = _ok(
        reserve(env, qty="40", item="FG-C100", location=loc_a01, lot="LOT-PART"),
        201,
    )
    # 예약 후 LOT-PART 재고 중 25가 폐기/차감되어 가용이 15만 남은 상황
    post(env, "-25", item="FG-C100", lot="LOT-PART", loc=loc_a01)

    pick = _ok(_create_pick(env, res["id"]), 201)
    # LOT-PART의 가용 15는 그대로 존중하고, 부족분 25는 FEFO로 LOT-FILL에서 채운다
    assert [(x["lotNo"], Decimal(x["qty"])) for x in pick["lines"]] == [
        ("LOT-FILL", Decimal(25)),
        ("LOT-PART", Decimal(15)),
    ]
    assert len(pick["lotSubstitutions"]) == 1
    sub = pick["lotSubstitutions"][0]
    assert sub["requestedLotNo"] == "LOT-PART"
    assert sub["reason"] == "SHORTAGE"
    assert Decimal(sub["keptQty"]) == Decimal(15)

    # (가) SHIPPING(출고장) 위치 재고는 격리(quarantinedOnHand)가 아니라 정상(normalOnHand)으로 집계된다
    shp_loc = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/warehouses/{fg_wh}/locations",
            {
                "code": "F-SHP",
                "name": "완제품 출고장",
                "locationType": "SHIPPING",
                "isDefault": False,
            },
        ),
        201,
    )
    post(env, "10", item="FG-C100", lot="LOT-FILL", loc=shp_loc["id"])
    shp_stock = _ok(env[0].get(W + "/stock", params={"locationId": shp_loc["id"]}))[
        "rows"
    ][0]
    assert Decimal(shp_stock["normalOnHand"]) == Decimal(10)
    assert Decimal(shp_stock["quarantinedOnHand"]) == Decimal(0)
