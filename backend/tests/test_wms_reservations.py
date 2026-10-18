"""FS-026b2 AC-151~158: scoped PostgreSQL ledger/reservation transactions."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
import test_wms_receiving as receiving_tests
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_wms import W, _call, _ok, _reason, _sync
from test_wms_receiving import (
    act,
    inspect_body,
    notice,
)

receiving_env = receiving_tests.receiving_env


def reserve(env, qty="40", item="RM-PBT", location=None, lot=None, **overrides):
    body = {
        "businessKey": uuid4().hex,
        "lines": [
            {
                "itemId": env[3][item],
                "locationId": location or env[3]["R-A01"],
                "lotNo": lot,
                "quantity": qty,
            }
        ],
    }
    body.update(overrides)
    return _call(env[0], env[1], "POST", "/reservations", body)


def action(env, r, command, **values):
    return _call(
        env[0],
        env[1],
        "POST",
        f"/reservations/{r['id']}/{command}",
        {"expectedVersion": r["version"], **values},
    )


def raw_stock(env):
    n = notice(env)
    n = _ok(act(env, n, "arrive"))
    return _ok(act(env, n, "inspect", **inspect_body(n)))


def stock(env, **filters):
    return _ok(env[0].get(W + "/stock", params=filters))


def post(env, qty, item="RM-PBT", lot=None, loc=None):
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
                        "itemId": env[3][item],
                        "locationId": loc or env[3]["R-A01"],
                        "lotNo": lot,
                        "qty": qty,
                    }
                ],
            },
        ),
        201,
    )
    return _ok(_call(env[0], env[1], "POST", f"/documents/{doc['id']}/post"))


def shipment_reservation(env, ref="SH-0004", **overrides):
    source = next(
        x
        for x in _ok(env[0].get(W + "/reservation-sources"))["shipments"]
        if x["shipmentNo"] == ref
    )
    for packing in {x["packingNo"] for x in source["lines"] if x["packingNo"]}:
        _sync(env[0], env[1], "MES_RECEIPT", "MES:RECEIPT:" + packing)
    # Seed sources have full pallet allocations; use the actual ledger LOTs.
    item_codes = {x["itemCode"] for x in source["lines"]}
    rows = [
        x
        for x in stock(env)["rows"]
        if x["itemCode"] in item_codes and Decimal(x["onHand"]) > 0
    ]
    lines = [
        {
            "itemId": r["itemId"],
            "locationId": r["locationId"],
            "lotNo": r["lotNo"],
            "quantity": r["onHand"],
        }
        for r in rows
    ]
    return _ok(
        reserve(
            env, lines=lines, shipmentOrderRef=source["shipmentOrderNo"], **overrides
        ),
        201,
    ), source


def test_available_excludes_quarantine_and_does_not_double_count_demand(
    receiving_env, monkeypatch
):
    from fs.wms import inventory

    env = receiving_env
    raw_stock(env)
    r = _ok(reserve(env), 201)
    assert r["status"] == "ACTIVE"
    normal = stock(env, locationId=env[3]["R-A01"])["rows"][0]
    assert {
        key: Decimal(normal[key])
        for key in ("onHand", "normalOnHand", "reservedQty", "available")
    } == {"onHand": 95, "normalOnHand": 95, "reservedQty": 40, "available": 55}
    held = stock(env, locationId=env[3]["quarantine"])["rows"][0]
    assert Decimal(held["quarantinedOnHand"]) == 3 and Decimal(held["available"]) == 0
    # FG demand is a reference, never a second deduction from available.
    post(env, "95", item="FG-C100", lot="FG-TEST", loc=env[3]["F-A01"])
    _ok(reserve(env, item="FG-C100", lot="FG-TEST", location=env[3]["F-A01"]), 201)
    monkeypatch.setattr(
        inventory.erp, "open_shipment_qty", lambda *_: {"FG-C100": "40"}
    )
    total = stock(env, itemCode="FG-C100")["totals"][0]
    assert Decimal(total["available"]) == 55 and total["openShipmentQty"] == "40"
    dashboard = _ok(env[0].get(W + "/dashboard", params={"month": "2000-01"}))
    assert (
        next(x for x in dashboard["items"] if x["itemCode"] == "FG-C100")["available"]
        == total["available"]
    )
    assert dashboard["flows"] == []


def test_release_replay_and_reserved_only_rows(receiving_env):
    env = receiving_env
    raw_stock(env)
    r = _ok(reserve(env), 201)
    post(env, "-95")
    row = stock(env, locationId=env[3]["R-A01"])["rows"][0]
    assert (
        Decimal(row["onHand"]) == 0
        and Decimal(row["reservedQty"]) == 40
        and Decimal(row["available"]) == -40
    )
    assert _reason(reserve(env, "1")) == "INSUFFICIENT_AVAILABLE"
    released = _ok(action(env, r, "release", reason="출고 계획 취소"))
    replay = _ok(action(env, r, "release", reason="출고 계획 취소"))
    assert (
        released["closedAt"] == replay["closedAt"]
        and released["version"] == replay["version"]
    )
    assert stock(env, locationId=env[3]["R-A01"])["rows"] == []
    assert action(env, r, "release", reason="다른 사유").status_code == 409


@pytest.mark.parametrize(
    "bad",
    ["quantity", "precision", "zero", "lot", "quarantine", "duplicate", "second_short"],
)
def test_invalid_or_partial_reservations_are_atomic(receiving_env, bad):
    env = receiving_env
    raw_stock(env)
    line = {"itemId": env[3]["RM-PBT"], "locationId": env[3]["R-A01"], "quantity": "10"}
    lines = [line]
    expected = 400
    if bad == "quantity":
        line["quantity"] = "-1"
    if bad == "precision":
        line["quantity"] = "0.0001"
    if bad == "zero":
        line["quantity"] = "0"
    if bad == "lot":
        line["lotNo"] = "RAW-LOT"
    if bad == "quarantine":
        line["locationId"] = env[3]["quarantine"]
        expected = 409
    if bad == "duplicate":
        lines.append(dict(line))
    if bad == "second_short":
        lines.append({**line, "locationId": env[3]["R-A02"]})
        expected = 409
    response = reserve(env, lines=lines)
    assert response.status_code == expected, response.text
    if expected == 400:
        assert response.json()["error"]["details"]["fields"]
    assert _ok(env[0].get(W + "/reservations"))["total"] == 0
    assert (
        Decimal(stock(env, locationId=env[3]["R-A01"])["rows"][0]["reservedQty"]) == 0
    )


def test_consumption_is_once_and_shares_server_time(receiving_env, monkeypatch):
    env = receiving_env
    r, src = shipment_reservation(env)
    monkeypatch.setenv("FS_TODAY", "1999-01-01")
    done = _ok(action(env, r, "consume-shipment", sourceKey=src["sourceKey"]))
    again = _ok(action(env, r, "consume-shipment", sourceKey=src["sourceKey"]))
    assert (
        done["stockDocumentId"] == again["stockDocumentId"]
        and done["status"] == "CONSUMED"
    )
    result = _sync(env[0], env[1], "ERP_SHIPMENT", src["sourceKey"])
    assert result["results"][0]["documentId"] == done["stockDocumentId"]
    doc = _ok(env[0].get(f"{W}/documents/{done['stockDocumentId']}"))
    assert doc["postedAt"] == done["closedAt"] and doc["documentOn"] != "1999-01-01"
    assert all(x["movedAt"] == done["closedAt"] for x in doc["moves"])
    assert all(Decimal(x["qtyDelta"]) < 0 for x in doc["moves"])
    assert (
        action(env, r, "consume-shipment", sourceKey="ERP:SHIPMENT:SH-0001").status_code
        == 409
    )
    assert action(env, done, "release", reason="취소").status_code == 409


def test_direct_sync_keeps_reservation_and_shortage_is_not_hidden(receiving_env):
    env = receiving_env
    r, src = shipment_reservation(env)
    _sync(env[0], env[1], "ERP_SHIPMENT", src["sourceKey"])
    assert (
        _reason(action(env, r, "consume-shipment", sourceKey=src["sourceKey"]))
        == "SOURCE_ALREADY_POSTED"
    )
    rows = stock(env)["rows"]
    row = next(x for x in rows if x["itemId"] == r["lines"][0]["itemId"])
    assert Decimal(row["onHand"]) == 0 and Decimal(row["available"]) == -Decimal(
        row["reservedQty"]
    )
    current = _ok(env[0].get(f"{W}/reservations/{r['id']}"))
    assert current["status"] == "ACTIVE"
    line = r["lines"][0]
    # More stock elsewhere must not conceal the shortage of this location/LOT.
    item = next(
        k for k, v in env[3].items() if v == line["itemId"] and k.startswith("FG-")
    )
    post(
        env,
        str(
            sum(
                Decimal(x["quantity"])
                for x in r["lines"]
                if x["itemId"] == line["itemId"]
            )
            + 1
        ),
        item=item,
        lot=line["lotNo"],
        loc=env[3]["F-A02"],
    )
    total = stock(env, itemCode=item)["totals"][0]
    assert Decimal(total["available"]) > 0 and Decimal(total["reservationShortage"]) > 0


def test_consumption_allows_negative_actual_stock(receiving_env):
    env = receiving_env
    r, src = shipment_reservation(env)
    line = r["lines"][0]
    item = next(
        k for k, v in env[3].items() if v == line["itemId"] and k.startswith("FG-")
    )
    post(env, "-1", item=item, lot=line["lotNo"], loc=line["locationId"])
    done = _ok(action(env, r, "consume-shipment", sourceKey=src["sourceKey"]))
    assert done["negativeWarnings"] and done["status"] == "CONSUMED"
    assert any(Decimal(x["onHand"]) == -1 for x in stock(env)["rows"])


@pytest.mark.parametrize("mismatch", ["quantity", "lot", "order", "mixed"])
def test_shipment_mismatch_preserves_active_reservation(
    receiving_env, monkeypatch, mismatch
):
    from fs.wms import reservations

    env = receiving_env
    r, src = shipment_reservation(env)
    original = reservations.erp.confirmed_shipments

    def changed(c, scope):
        rows = deepcopy(original(c, scope))
        s = next(x for x in rows if x["shipmentNo"] == src["shipmentNo"])
        if mismatch == "quantity":
            s["lines"][0]["qty"] = str(Decimal(s["lines"][0]["qty"]) + 1)
        if mismatch == "lot":
            s["lines"][0]["packingNo"] = "PL-UNKNOWN"
        if mismatch == "order":
            s["shipmentOrderNo"] = "SO-OTHER"
        if mismatch == "mixed":
            s["lines"].append({**s["lines"][0], "packingNo": None})
        return rows

    monkeypatch.setattr(reservations.erp, "confirmed_shipments", changed)
    response = action(env, r, "consume-shipment", sourceKey=src["sourceKey"])
    assert response.status_code == 409 and _reason(response) == "SHIPMENT_MISMATCH"
    assert _ok(env[0].get(f"{W}/reservations/{r['id']}"))["status"] == "ACTIVE"
    assert not any(
        x["sourceKey"] == src["sourceKey"] for x in _ok(env[0].get(W + "/documents"))
    )


@pytest.mark.parametrize("race", ["reserve", "consume"])
def test_real_connection_races(receiving_env, monkeypatch, race):
    from fs.common import engine

    env = receiving_env
    if race == "reserve":
        raw_stock(env)
    else:
        r, src = shipment_reservation(env)
    original = engine.write_scope
    pids = set()
    barrier = Barrier(2)

    def lock(c, *args, **kwargs):
        pids.add(c.execute(text("SELECT pg_backend_pid()")).scalar_one())
        barrier.wait(timeout=15)
        return original(c, *args, **kwargs)

    monkeypatch.setattr(engine, "write_scope", lock)

    def request(index):
        with TestClient(env[0].app, base_url=str(env[0].base_url)) as client:
            client.cookies.update(env[0].cookies)
            parallel = (client, *env[1:])
            if race == "reserve":
                return reserve(parallel, "60")
            if index == 0:
                return action(
                    parallel, r, "consume-shipment", sourceKey=src["sourceKey"]
                )
            return _call(
                client,
                env[1],
                "POST",
                "/sources/sync",
                {"kind": "ERP_SHIPMENT", "sourceKeys": [src["sourceKey"]]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, [0, 1]))
    assert len(pids) == 2
    if race == "reserve":
        assert sorted(x.status_code for x in results) == [201, 409]
        assert (
            Decimal(stock(env, locationId=env[3]["R-A01"])["rows"][0]["reservedQty"])
            == 60
        )
    else:
        assert results[0].status_code in {200, 409} and results[1].status_code == 200
        documents = [
            x
            for x in _ok(env[0].get(W + "/documents"))
            if x["sourceKey"] == src["sourceKey"]
        ]
        assert len(documents) == 1
        state = _ok(env[0].get(f"{W}/reservations/{r['id']}"))["status"]
        assert state == ("CONSUMED" if results[0].status_code == 200 else "ACTIVE")


def test_ac154_unreserved_shipment_allows_negative_availability(
    receiving_env, monkeypatch
):
    from fs.wms import service

    env = receiving_env
    loc = env[3]["F-A01"]
    monkeypatch.setattr(
        service.mes,
        "finished_goods_receipts",
        lambda *_: [
            {
                "packingNo": "PL-DEMO",
                "receivedAt": "2026-09-24T03:00:00+00:00",
                "lines": [
                    {
                        "itemCode": "FG-C100",
                        "qty": "70",
                        "unit": "EA",
                        "lotNo": "DEMO-LOT",
                    }
                ],
            }
        ],
    )
    _sync(env[0], env[1], "MES_RECEIPT", "MES:RECEIPT:PL-DEMO")
    post(env, "25", item="FG-C100", lot="DEMO-LOT", loc=loc)
    _ok(reserve(env, item="FG-C100", location=loc, lot="DEMO-LOT"), 201)
    monkeypatch.setattr(
        service.erp,
        "confirmed_shipments",
        lambda *_: [
            {
                "shipmentNo": "SH-DEMO",
                "shipmentOrderNo": "SO-DEMO",
                "shippedAt": "2026-09-24T04:00:00+00:00",
                "lines": [
                    {
                        "lineNo": 1,
                        "itemCode": "FG-C100",
                        "qty": "70",
                        "unit": "EA",
                        "packingNo": "PL-DEMO",
                    }
                ],
            }
        ],
    )
    _sync(env[0], env[1], "ERP_SHIPMENT", "ERP:SHIPMENT:SH-DEMO")
    row = stock(env, itemCode="FG-C100", lotNo="DEMO-LOT")["rows"][0]
    assert tuple(
        Decimal(row[k])
        for k in ("normalOnHand", "reservedQty", "available", "reservationShortage")
    ) == (25, 40, -15, 15)
    assert (
        _reason(reserve(env, "1", item="FG-C100", location=loc, lot="DEMO-LOT"))
        == "INSUFFICIENT_AVAILABLE"
    )


def test_erp_off_master_guards_and_reference_comparison(receiving_env):
    env = receiving_env
    raw_stock(env)
    r = _ok(reserve(env), 201)
    for path in [
        f"/items/{env[3]['RM-PBT']}",
        f"/warehouses/{env[3]['warehouse']}",
        f"/locations/{env[3]['R-A01']}",
    ]:
        assert (
            _call(env[0], env[1], "PATCH", path, {"isActive": False}).status_code == 409
        )
    assert (
        _call(
            env[0],
            env[1],
            "PATCH",
            f"/locations/{env[3]['R-A01']}",
            {"locationType": "QUARANTINE"},
        ).status_code
        == 409
    )
    fg, src = shipment_reservation(env)
    assert fg["shipmentOrderComparison"]["state"] == "match"
    _ok(
        _call(
            env[0],
            env[1],
            "PATCH",
            "/api/v1/core/workspace/modules/erp",
            {"enabled": False},
        )
    )
    assert Decimal(stock(env, locationId=env[3]["R-A01"])["rows"][0]["available"]) == 55
    assert _ok(env[0].get(W + "/reservation-sources"))["enabled"] is False
    detail = _ok(env[0].get(f"{W}/reservations/{fg['id']}"))
    assert detail["shipmentOrderComparison"]["state"] == "unavailable"
    response = action(env, fg, "consume-shipment", sourceKey=src["sourceKey"])
    assert response.status_code == 409 and _reason(response) == "SOURCE_MODULE_DISABLED"
    _ok(reserve(env, "5"), 201)
    _ok(action(env, r, "release", reason="ERP 없이 해제"))


def test_fg_lot_scope_and_permanent_business_key(receiving_env):
    from test_wms import _other_guest

    env = receiving_env
    raw_stock(env)
    assert reserve(env, item="FG-C100", location=env[3]["F-A01"]).status_code == 400
    r = _ok(reserve(env, businessKey="RES-UNIQUE"), 201)
    assert _reason(reserve(env, businessKey="RES-UNIQUE")) == "BUSINESS_KEY_EXISTS"
    other, auth = _other_guest(env[0])
    try:
        assert other.get(f"{W}/reservations/{r['id']}").status_code == 404
        assert (
            _call(
                other,
                auth,
                "POST",
                f"/reservations/{r['id']}/release",
                {"expectedVersion": 1, "reason": "다른 공간"},
            ).status_code
            == 404
        )
    finally:
        other.close()
    assert (
        _ok(env[0].get(W + "/reservations", params={"itemCode": "FG-C100"}))["total"]
        == 0
    )
    _ok(_call(env[0], env[1], "POST", "/api/v1/core/workspace/generations"), 201)
    assert env[0].get(f"{W}/reservations/{r['id']}").status_code == 404


def test_copy_reservation_states_dates_and_consumed_document(receiving_env):
    from datetime import date, timedelta

    from seed.copy import copy_template

    env = receiving_env
    raw_stock(env)
    active = _ok(reserve(env, "10"), 201)
    released = _ok(reserve(env, "10"), 201)
    _ok(action(env, released, "release", reason="예약 해제"))
    used, src = shipment_reservation(env)
    _ok(action(env, used, "consume-shipment", sourceKey=src["sourceKey"]))
    with env[2].begin() as c:
        seed = c.execute(
            text("SELECT seed_date FROM core.data_generation WHERE id=:g"),
            {"g": env[1]["generationId"]},
        ).scalar_one()
        w, g, _, _ = copy_template(
            c,
            env[1]["workspaceId"],
            env[1]["generationId"],
            seed + timedelta(days=3),
            "res-copy-" + uuid4().hex,
        )
        rows = (
            c.execute(
                text(
                    "SELECT * FROM wms.stock_reservation WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": w, "g": g},
            )
            .mappings()
            .all()
        )
        assert {x["status"] for x in rows} == {"ACTIVE", "RELEASED", "CONSUMED"}
        cloned = next(x for x in rows if x["status"] == "ACTIVE")
        assert (
            cloned["business_key"] == active["businessKey"]
            and cloned["id"] != active["id"]
        )
        assert date.fromisoformat(cloned["reservation_no"][4:12]) - date.fromisoformat(
            active["reservationNo"][4:12]
        ) == timedelta(days=3)
        consumed = next(x for x in rows if x["status"] == "CONSUMED")
        key = c.execute(
            text(
                "SELECT source_key FROM wms.stock_document WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {"w": w, "g": g, "id": consumed["stock_document_id"]},
        ).scalar_one()
        assert key == src["sourceKey"] == consumed["shipment_source_key"]


def test_shipment_preview_is_readonly_and_matches_consume(receiving_env):
    env = receiving_env
    r, src = shipment_reservation(env)
    params = {"sourceKey": src["sourceKey"]}
    preview = _ok(
        env[0].get(f"{W}/reservations/{r['id']}/shipment-preview", params=params)
    )
    assert preview == {"matches": True, "negativeWarnings": []}
    assert _ok(env[0].get(f"{W}/reservations/{r['id']}"))["status"] == "ACTIVE"
    _ok(action(env, r, "consume-shipment", **params))
    assert (
        env[0]
        .get(f"{W}/reservations/{r['id']}/shipment-preview", params=params)
        .status_code
        == 409
    )


def test_notice_date_and_reservation_shortage_filters(receiving_env):
    env = receiving_env
    n = raw_stock(env)
    assert (
        _ok(
            env[0].get(
                W + "/inbound-notices",
                params={"expectedFrom": n["expectedOn"], "expectedTo": n["expectedOn"]},
            )
        )["total"]
        == 1
    )
    assert (
        _ok(env[0].get(W + "/inbound-notices", params={"expectedFrom": "2099-01-01"}))[
            "total"
        ]
        == 0
    )
    assert (
        env[0]
        .get(
            W + "/inbound-notices",
            params={"expectedFrom": "2099-01-01", "expectedTo": "2000-01-01"},
        )
        .status_code
        == 400
    )
    r = _ok(reserve(env), 201)
    assert (
        _ok(env[0].get(W + "/reservations", params={"shortageOnly": True}))["total"]
        == 0
    )
    post(env, "-70")
    page = _ok(env[0].get(W + "/reservations", params={"shortageOnly": True}))
    assert page["total"] == 1 and page["rows"][0]["id"] == r["id"]
    held = stock(env, locationType="QUARANTINE")["rows"]
    assert len(held) == 1 and held[0]["quarantinedOnHand"] == "3.000"


def test_reservation_lot_tracked_validation_and_hold_expired_blocking(
    receiving_env, monkeypatch
):
    """W2b-1d D-4: 완제품/원자재 대신 lotTracked 기준 검증 및 HOLD/EXPIRED LOT 예약 차단."""
    from fs.wms import reservations as rsv_mod

    env = receiving_env
    loc_fg = env[3]["F-A01"]
    loc_rm = env[3]["R-A01"]

    # 1. lot_tracked=True 품목(FG-C100)에 lotNo 누락 -> 400
    res_no_lot = reserve(env, qty="10", item="FG-C100", location=loc_fg, lot=None)
    assert res_no_lot.status_code == 400
    assert (
        "LOT 추적 품목은 LOT 필수"
        in res_no_lot.json()["error"]["details"]["fields"]["lines.0.lotNo"]
    )

    # 2. lot_tracked=False 품목(RM-PBT)에 lotNo 지정 -> 400
    res_extra_lot = reserve(
        env, qty="10", item="RM-PBT", location=loc_rm, lot="LOT-ILLEGAL"
    )
    assert res_extra_lot.status_code == 400
    assert (
        "LOT 추적 품목은 LOT 필수"
        in res_extra_lot.json()["error"]["details"]["fields"]["lines.0.lotNo"]
    )

    # 3. 보류/만료 LOT 등록
    lot_hold_body = {
        "itemId": env[3]["FG-C100"],
        "lotNo": "LOT-RSV-HOLD",
        "origin": "MES",
        "receivedOn": "2026-09-01",
        "status": "AVAILABLE",
    }
    lot_hold_res = _ok(_call(env[0], env[1], "POST", "/lots", lot_hold_body), 201)
    _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/lots/{lot_hold_res['id']}/hold",
            {"source": "MANUAL", "reason": "품질 조사 보류"},
        ),
        201,
    )
    post(env, "50", item="FG-C100", lot="LOT-RSV-HOLD", loc=loc_fg)

    lot_exp_body = {
        "itemId": env[3]["FG-C100"],
        "lotNo": "LOT-RSV-EXPIRED",
        "origin": "MES",
        "receivedOn": "2026-01-01",
        "expiryDate": "2026-01-10",
        "status": "AVAILABLE",
    }
    _ok(_call(env[0], env[1], "POST", "/lots", lot_exp_body), 201)
    post(env, "50", item="FG-C100", lot="LOT-RSV-EXPIRED", loc=loc_fg)

    lot_qms_body = {
        "itemId": env[3]["FG-C100"],
        "lotNo": "LOT-RSV-QMS",
        "origin": "MES",
        "receivedOn": "2026-09-01",
        "expiryDate": "2099-12-31",
        "status": "AVAILABLE",
    }
    _ok(_call(env[0], env[1], "POST", "/lots", lot_qms_body), 201)
    post(env, "50", item="FG-C100", lot="LOT-RSV-QMS", loc=loc_fg)

    lot_normal_body = {
        "itemId": env[3]["FG-C100"],
        "lotNo": "LOT-RSV-OK",
        "origin": "MES",
        "receivedOn": "2026-09-01",
        "expiryDate": "2099-12-31",
        "status": "AVAILABLE",
    }
    _ok(_call(env[0], env[1], "POST", "/lots", lot_normal_body), 201)
    post(env, "50", item="FG-C100", lot="LOT-RSV-OK", loc=loc_fg)

    # 4. WMS 활성 보류 LOT 예약 차단 -> 409 LOT_HOLD
    r_hold = reserve(env, qty="10", item="FG-C100", location=loc_fg, lot="LOT-RSV-HOLD")
    assert r_hold.status_code == 409 and _reason(r_hold) == "LOT_HOLD"

    # 5. 유효기간 만료 LOT 예약 차단 -> 409 LOT_EXPIRED
    r_exp = reserve(
        env, qty="10", item="FG-C100", location=loc_fg, lot="LOT-RSV-EXPIRED"
    )
    assert r_exp.status_code == 409 and _reason(r_exp) == "LOT_EXPIRED"

    # 6. QMS 보류 LOT 예약 차단 -> 409 LOT_QMS_HOLD
    monkeypatch.setattr(rsv_mod.qms, "held_lot_nos", lambda *_: {"LOT-RSV-QMS"})
    r_qms = reserve(env, qty="10", item="FG-C100", location=loc_fg, lot="LOT-RSV-QMS")
    assert r_qms.status_code == 409 and _reason(r_qms) == "LOT_QMS_HOLD"

    # 7. 정상 LOT은 예약 성공 및 피킹 지시 연결 필드 검증
    r_ok = _ok(
        reserve(env, qty="20", item="FG-C100", location=loc_fg, lot="LOT-RSV-OK"), 201
    )
    assert r_ok["status"] == "ACTIVE"

    # 목록 및 상세에서 피킹 필드 기본값(None) 확인
    detail = _ok(env[0].get(f"{W}/reservations/{r_ok['id']}"))
    assert detail["pickOrderId"] is None
    assert detail["pickOrderNo"] is None
    assert detail["pickOrderStatus"] is None

    res_list = _ok(env[0].get(f"{W}/reservations"))
    row_in_list = next(x for x in res_list["rows"] if x["id"] == r_ok["id"])
    assert row_in_list["pickOrderId"] is None
    assert row_in_list["pickOrderStatus"] is None

    # 피킹 지시 생성
    pick = _ok(
        _call(
            env[0],
            env[1],
            "POST",
            "/pick-orders",
            {"reservationId": r_ok["id"]},
        ),
        201,
    )
    assert pick["status"] == "OPEN"

    # 상세 및 목록에서 피킹 지시 필드 연계 확인
    detail2 = _ok(env[0].get(f"{W}/reservations/{r_ok['id']}"))
    assert detail2["pickOrderId"] == pick["id"]
    assert detail2["pickOrderNo"] == pick["pickNo"]
    assert detail2["pickOrderStatus"] == "OPEN"

    res_list2 = _ok(env[0].get(f"{W}/reservations"))
    row_in_list2 = next(x for x in res_list2["rows"] if x["id"] == r_ok["id"])
    assert row_in_list2["pickOrderId"] == pick["id"]
    assert row_in_list2["pickOrderNo"] == pick["pickNo"]
    assert row_in_list2["pickOrderStatus"] == "OPEN"
