"""FS-024b WMS API (AC-111~124). 검증 항목마다 테스트를 나눈다.

API 테스트는 `blank` fixture가 게스트의 WMS 시드(FS-024c)를 지운 빈 상태에서 시작하고,
기준정보(창고·위치·품목·단위)는 `wms` fixture가 API로 만든다. 시드 자체는 `test_seed_demo_flow`가 본다.
원천은 템플릿의 MES·ERP 시드를 읽기 전용 조회로 읽는다(D9): 입고 PL-0001~0006, 출하 SH-0001~0004
(PL-0001·0003·0005·0004), 매입 PI-0001~0004(확정)·PI-0006(확정 후 취소).
"""

from decimal import Decimal
from itertools import count
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

W = "/api/v1/wms"
_keys = count()


def _call(client, created, method: str, path: str, body=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{W}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": f"w{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _setup(client, created, conversion=True) -> dict:
    ids = {}
    for code, name, purpose, locations in (
        ("WH-RAW", "원자재 창고", "RAW", ("R-A01", "R-A02")),
        ("WH-FG", "완제품 창고", "FG", ("F-A01", "F-A02")),
    ):
        house = _ok(
            _call(
                client,
                created,
                "POST",
                "/warehouses",
                {"code": code, "name": name, "purpose": purpose},
            ),
            201,
        )
        for loc in locations:
            ids[loc] = _ok(
                _call(
                    client,
                    created,
                    "POST",
                    f"/warehouses/{house['id']}/locations",
                    {"code": loc, "name": loc},
                ),
                201,
            )["id"]
    candidates = _ok(client.get(f"{W}/lookups/mes-items"))
    assert {c["itemCode"] for c in candidates} == {
        "FG-C100",
        "FG-C200",
        "FG-T300",
        "RM-PBT",
        "RM-PIN",
    }
    items = _ok(
        _call(
            client,
            created,
            "POST",
            "/items/import",
            {"itemCodes": [c["itemCode"] for c in candidates]},
        ),
        201,
    )
    ids.update({i["itemCode"]: i["id"] for i in items})
    if conversion:
        _ok(
            _call(
                client,
                created,
                "POST",
                f"/items/{ids['RM-PIN']}/conversions",
                {"fromUnit": "BOX", "factor": "10000"},
            ),
            201,
        )
    return ids


WMS_TABLES = (
    "stock_reservation_line",
    "stock_reservation",
    "source_claim",
    "inbound_notice_line",
    "inbound_notice",
    "stock_move",
    "stock_document",
    "item_unit_conversion",
    "item",
    "storage_location",
    "warehouse",
)


def _clear(engine, created) -> None:
    with engine.begin() as connection:
        for table in WMS_TABLES:
            connection.execute(
                text(
                    f"DELETE FROM wms.{table} WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": created["workspaceId"], "g": created["generationId"]},
            )


@pytest.fixture
def blank(guest_space):
    client, created, engine = guest_space
    _clear(engine, created)
    return client, created


@pytest.fixture
def wms(blank):
    client, created = blank
    return client, created, _setup(client, created)


def _sync(client, created, kind: str, *keys: str) -> dict:
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/sources/sync",
            {"kind": kind, "sourceKeys": list(keys)},
        )
    )


def _stock(client, **params) -> list[dict]:
    return _ok(client.get(f"{W}/stock", params=params))["rows"]


def test_guest_has_wms_module(guest_space):
    client, _, _ = guest_space
    modules = {
        m["moduleKey"]: m["enabled"]
        for m in client.get("/api/v1/core/workspace/modules").json()["data"]
    }
    assert modules["wms"] is True


def test_master_rules(blank):
    """용도별 활성 창고 1개, 첫 위치는 기본, 기본 위치는 지우지 못한다."""
    client, created = blank
    ids = _setup(client, created, conversion=False)
    second = _call(
        client,
        created,
        "POST",
        "/warehouses",
        {"code": "WH-RAW2", "name": "예비", "purpose": "RAW"},
    )
    assert (
        second.status_code == 400
        and "purpose" in second.json()["error"]["details"]["fields"]
    )
    locations = _ok(
        client.get(
            f"{W}/warehouses/{_ok(client.get(f'{W}/warehouses'))[0]['id']}/locations"
        )
    )
    # 목록은 코드순이라 WH-FG가 먼저다.
    assert [(x["code"], x["isDefault"]) for x in locations] == [
        ("F-A01", True),
        ("F-A02", False),
    ]
    deleted = _call(client, created, "DELETE", f"/locations/{ids['R-A01']}")
    assert deleted.status_code == 409 and _reason(deleted) == "DEFAULT_LOCATION"
    same = _call(
        client,
        created,
        "POST",
        f"/items/{ids['RM-PIN']}/conversions",
        {"fromUnit": "EA", "factor": "1"},
    )
    assert same.status_code == 400


def test_sync_is_idempotent(wms):
    """AC-111: 같은 원천을 두 번 반영해도 전표 1건, 두 번째는 같은 전표."""
    client, created, _ = wms
    first = _sync(
        client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001", "MES:RECEIPT:PL-0001"
    )
    again = _sync(client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001")
    assert first["synced"] == 1 and len(first["results"]) == 1
    assert again["results"][0]["documentId"] == first["results"][0]["documentId"]
    docs = _ok(client.get(f"{W}/documents", params={"type": "MES_RECEIPT"}))
    assert len(docs) == 1 and docs[0]["documentNo"].startswith("WD-20260924-")
    assert docs[0]["sourceRef"] == "PL-0001" and docs[0]["status"] == "posted"


def test_stock_is_sum_of_posted_moves_and_posted_is_immutable(wms):
    """AC-112·113"""
    client, created, _ = wms
    _sync(client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001")
    rows = _stock(client, itemCode="FG-C100")
    # PL-0001 = E01·E04(FG-C100, 최종 양품 1,940씩)
    assert sorted((r["lotNo"], r["onHand"]) for r in rows) == [
        ("LT-0001", "1940.000"),
        ("LT-0004", "1940.000"),
    ]
    moves = _ok(client.get(f"{W}/moves", params={"itemCode": "FG-C100"}))
    assert sum(Decimal(m["qtyDelta"]) for m in moves) == Decimal(3880)
    doc_id = _ok(client.get(f"{W}/documents"))[0]["id"]
    blocked = _call(client, created, "PATCH", f"/documents/{doc_id}", {"note": "x"})
    assert blocked.status_code == 409 and _reason(blocked) == "POSTED_IMMUTABLE"
    assert _call(client, created, "DELETE", f"/documents/{doc_id}").status_code == 409


def test_shipment_uses_reflected_pallet_lots(wms):
    """AC-114: 반영된 팔레트면 LOT별, 아니면 LOT 미지정으로 차감."""
    client, created, _ = wms
    _sync(client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001")
    _sync(
        client, created, "ERP_SHIPMENT", "ERP:SHIPMENT:SH-0001", "ERP:SHIPMENT:SH-0002"
    )
    assert _stock(client, itemCode="FG-C100") == []  # PL-0001 전량 출하 → 0(숨김)
    c200 = _stock(
        client, itemCode="FG-C200"
    )  # SH-0002 = PL-0003(미반영) → LOT 미지정 음수
    assert [
        (r["lotNo"], r["onHand"], r["lotUnassigned"], r["negative"]) for r in c200
    ] == [(None, "-3842.000", True, True)]


def test_unit_conversion_and_missing_conversion(blank):
    """AC-115: BOX → EA 환산·원천 수량 보존. 환산이 없으면 반영 불가 사유."""
    client, created = blank
    ids = _setup(client, created, conversion=False)
    listed = _ok(client.get(f"{W}/sources", params={"kind": "ERP_PURCHASE"}))
    pi1 = next(r for r in listed["rows"] if r["sourceRef"] == "PI-0001")
    assert pi1["state"] == "blocked" and pi1["reason"] == {
        "code": "UNIT_CONVERSION_MISSING",
        "itemCode": "RM-PIN",
        "unit": "BOX",
    }
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/items/{ids['RM-PIN']}/conversions",
            {"fromUnit": "BOX", "factor": "10000"},
        ),
        201,
    )
    _sync(client, created, "ERP_PURCHASE", "ERP:PURCHASE:PI-0001")
    pin = next(m for m in _ok(client.get(f"{W}/moves", params={"itemCode": "RM-PIN"})))
    assert (pin["qtyDelta"], pin["sourceQty"], pin["sourceUnit"], pin["unit"]) == (
        "100000.000",
        "10.000",
        "BOX",
        "EA",
    )


def test_unregistered_item_blocks_only_that_source(wms, guest_space):
    """AC-116"""
    client, _, _ = wms
    # FG-C100만 등록한 새 공간: PL-0001(FG-C100)은 반영되고 PL-0005(FG-T300)는 품목 미등록.
    client2, created2 = _other_guest(client, guest_space[2])
    for code, name, purpose in (("WH-FG", "완제품", "FG"),):
        house = _ok(
            _call(
                client2,
                created2,
                "POST",
                "/warehouses",
                {"code": code, "name": name, "purpose": purpose},
            ),
            201,
        )
        _ok(
            _call(
                client2,
                created2,
                "POST",
                f"/warehouses/{house['id']}/locations",
                {"code": "F-A01", "name": "기본"},
            ),
            201,
        )
    _ok(
        _call(client2, created2, "POST", "/items/import", {"itemCodes": ["FG-C100"]}),
        201,
    )
    result = _sync(
        client2, created2, "MES_RECEIPT", "MES:RECEIPT:PL-0001", "MES:RECEIPT:PL-0005"
    )
    states = {r["sourceKey"]: (r["state"], r.get("reason")) for r in result["results"]}
    assert states["MES:RECEIPT:PL-0001"][0] == "synced"
    assert states["MES:RECEIPT:PL-0005"] == (
        "blocked",
        {"code": "ITEM_NOT_REGISTERED", "itemCode": "FG-T300"},
    )


def _other_guest(client, engine=None):
    """새 게스트 공간. engine을 주면 WMS 시드를 지운 빈 상태로 만든다."""
    other = TestClient(client.app, base_url="https://testserver")
    response = other.post(
        "/api/v1/core/guest-sessions", headers={"Idempotency-Key": str(uuid4())}
    )
    assert response.status_code == 201
    created = response.json()["data"]
    if engine is not None:
        _clear(engine, created)
    return other, created


def test_negative_stock_is_allowed_and_flagged(wms):
    """AC-117"""
    client, created, _ = wms
    _sync(client, created, "ERP_SHIPMENT", "ERP:SHIPMENT:SH-0003")
    negatives = _stock(client, negativeOnly="true")
    assert [(r["itemCode"], r["onHand"]) for r in negatives] == [
        ("FG-T300", "-1964.000")
    ]
    assert _ok(client.get(f"{W}/dashboard"))["negativeCount"] == 1


def test_cancelled_purchase_is_reversed_once(wms):
    """AC-118: 반영 뒤 ERP에서 취소한 매입은 취소 미반영 → 되돌림 1건. 반영 전에 취소된 매입은 반영하지 않는다."""
    client, created, _ = wms
    before = {
        r["sourceRef"]: r["state"]
        for r in _ok(
            client.get(f"{W}/sources", params={"kind": "ERP_PURCHASE", "state": "all"})
        )["rows"]
    }
    assert before["PI-0006"] == "cancelled"
    assert (
        _sync(client, created, "ERP_PURCHASE", "ERP:PURCHASE:PI-0006")["results"][0][
            "reason"
        ]["code"]
        == "SOURCE_CANCELLED"
    )
    _sync(client, created, "ERP_PURCHASE", "ERP:PURCHASE:PI-0004")
    invoice = next(
        i
        for i in client.get("/api/v1/erp/purchase-invoices").json()["data"]
        if i["invoiceNo"] == "PI-0004"
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/api/v1/erp/purchase-invoices/{invoice['id']}/cancel",
            {"reason": "공급사 반품"},
        )
    )
    rows = {
        r["sourceRef"]: r
        for r in _ok(client.get(f"{W}/sources", params={"kind": "ERP_PURCHASE"}))[
            "rows"
        ]
    }
    assert rows["PI-0004"]["state"] == "cancel_pending"
    first = _sync(client, created, "ERP_PURCHASE", "ERP:PURCHASE:PI-0004")["results"][0]
    again = _sync(client, created, "ERP_PURCHASE", "ERP:PURCHASE:PI-0004")["results"][0]
    assert (
        first["state"] == again["state"] == "reversed"
        and first["documentId"] == again["documentId"]
    )
    assert _stock(client, itemCode="RM-PBT") == []  # +200 → −200
    reversal = _ok(client.get(f"{W}/documents/{first['documentId']}"))
    assert reversal["documentType"] == "REVERSAL" and reversal["reversesDocumentNo"]


def test_transfer_and_adjustment_rules(wms):
    """AC-119·120: 이동은 LOT·다른 위치, 합 0으로 저장. 조정은 사유 필수."""
    client, created, ids = wms
    _sync(client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001")
    no_lot = _call(
        client,
        created,
        "POST",
        "/documents",
        {
            "documentType": "TRANSFER",
            "lines": [
                {
                    "itemId": ids["FG-C100"],
                    "fromLocationId": ids["F-A01"],
                    "toLocationId": ids["F-A01"],
                    "qty": "10",
                }
            ],
        },
    )
    fields = no_lot.json()["error"]["details"]["fields"]
    assert no_lot.status_code == 400 and {
        "lines.0.lotNo",
        "lines.0.toLocationId",
    } <= set(fields)
    draft = _ok(
        _call(
            client,
            created,
            "POST",
            "/documents",
            {
                "documentType": "TRANSFER",
                "lines": [
                    {
                        "itemId": ids["FG-C100"],
                        "lotNo": "LT-0001",
                        "fromLocationId": ids["F-A01"],
                        "toLocationId": ids["F-A02"],
                        "qty": "500",
                    }
                ],
            },
        ),
        201,
    )
    assert [m["qtyDelta"] for m in draft["moves"]] == ["-500.000", "500.000"]
    _ok(_call(client, created, "POST", f"/documents/{draft['id']}/post"))
    lt1 = {r["locationCode"]: r["onHand"] for r in _stock(client, lotNo="LT-0001")}
    assert lt1 == {"F-A01": "1440.000", "F-A02": "500.000"}
    reasonless = _call(
        client,
        created,
        "POST",
        "/documents",
        {
            "documentType": "ADJUSTMENT",
            "lines": [
                {
                    "itemId": ids["FG-C100"],
                    "locationId": ids["F-A01"],
                    "lotNo": "LT-0004",
                    "qty": "-5",
                }
            ],
        },
    )
    assert (
        reasonless.status_code == 400
        and "reasonCode" in reasonless.json()["error"]["details"]["fields"]
    )
    other = _call(
        client,
        created,
        "POST",
        "/documents",
        {
            "documentType": "ADJUSTMENT",
            "reasonCode": "OTHER",
            "lines": [
                {
                    "itemId": ids["FG-C100"],
                    "locationId": ids["F-A01"],
                    "lotNo": "LT-0004",
                    "qty": "-5",
                }
            ],
        },
    )
    assert (
        other.status_code == 400
        and "note" in other.json()["error"]["details"]["fields"]
    )
    scrap = _ok(
        _call(
            client,
            created,
            "POST",
            "/documents",
            {
                "documentType": "ADJUSTMENT",
                "reasonCode": "SCRAP",
                "lines": [
                    {
                        "itemId": ids["FG-C100"],
                        "locationId": ids["F-A01"],
                        "lotNo": "LT-0004",
                        "qty": "-2000",
                    }
                ],
            },
        ),
        201,
    )
    posted = _ok(_call(client, created, "POST", f"/documents/{scrap['id']}/post"))
    assert posted["status"] == "posted" and [
        (n["lotNo"], n["onHand"]) for n in posted["negative"]
    ] == [("LT-0004", "-60.000")]


def test_running_execution_issues_are_not_sources(wms):
    """AC-121: W11(LT-0023) 조립은 실행 중 → 투입 원천이 아니다. 사출은 완료."""
    client, _, _ = wms
    keys = {
        r["sourceKey"]
        for r in _ok(
            client.get(f"{W}/sources", params={"kind": "MES_ISSUE", "state": "all"})
        )["rows"]
    }
    assert "MES:ISSUE:LT-0023:INJ" in keys and "MES:ISSUE:LT-0023:ASM" not in keys


def test_source_module_off_keeps_manual_documents(wms):
    """AC-122: MES를 끄면 MES 원천만 꺼짐, 수동 전표는 동작. WMS를 꺼도 MES API는 그대로."""
    client, created, ids = wms
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/mes",
            {"enabled": False},
        )
    )
    listed = _ok(client.get(f"{W}/sources", params={"kind": "MES_RECEIPT"}))
    assert listed["disabled"] is True and listed["sourceModule"] == "mes"
    assert (
        _ok(client.get(f"{W}/sources", params={"kind": "ERP_SHIPMENT"}))["disabled"]
        is False
    )
    opening = _ok(
        _call(
            client,
            created,
            "POST",
            "/documents",
            {
                "documentType": "OPENING",
                "lines": [
                    {"itemId": ids["RM-PBT"], "locationId": ids["R-A01"], "qty": "200"}
                ],
            },
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/documents/{opening['id']}/post"))
    assert _stock(client, itemCode="RM-PBT")[0]["onHand"] == "200.000"
    assert _ok(client.get(f"{W}/dashboard"))["pendingByKind"]["MES_RECEIPT"] is None
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/mes",
            {"enabled": True},
        )
    )
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/wms",
            {"enabled": False},
        )
    )
    assert client.get("/api/v1/mes/lots").status_code == 200
    assert client.get(f"{W}/stock").status_code == 409


def test_available_is_normal_stock_minus_reservations_even_without_erp(wms):
    """FS-026 AC-151 replaces AC-123: demand is separate, ERP-off preserves availability."""
    client, created, _ = wms
    for pallet in ("PL-0001", "PL-0003", "PL-0005", "PL-0002", "PL-0004", "PL-0006"):
        _sync(client, created, "MES_RECEIPT", f"MES:RECEIPT:{pallet}")
    totals = {t["itemCode"]: t for t in _ok(client.get(f"{W}/stock"))["totals"]}
    for t in totals.values():
        assert Decimal(t["available"]) == Decimal(t["normalOnHand"]) - Decimal(
            t["reservedQty"]
        )
        assert t["openShipmentQty"] is not None
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/erp",
            {"enabled": False},
        )
    )
    totals_off = _ok(client.get(f"{W}/stock"))["totals"]
    assert all(t["openShipmentQty"] is None for t in totals_off)
    assert all(
        Decimal(t["available"])
        == Decimal(t["normalOnHand"]) - Decimal(t["reservedQty"])
        for t in totals_off
    )


def test_other_workspace_cannot_see_documents(wms):
    """AC-124"""
    client, created, _ = wms
    doc_id = _sync(client, created, "MES_RECEIPT", "MES:RECEIPT:PL-0001")["results"][0][
        "documentId"
    ]
    other, _ = _other_guest(client)
    assert other.get(f"{W}/documents/{doc_id}").status_code == 404
    # 다른 공간에는 그 공간의 시드 전표만 보인다.
    assert doc_id not in {d["id"] for d in other.get(f"{W}/documents").json()["data"]}


def test_seed_demo_flow(guest_space):
    """FS-024c 시드: 미반영 원천·음수 없음·이동 초안이 보이고, 시드 상태에서 반영·확정할 수 있다."""
    client, created, _ = guest_space
    pending = {
        kind: {
            r["sourceRef"]
            for r in _ok(client.get(f"{W}/sources", params={"kind": kind}))["rows"]
        }
        for kind in ("MES_RECEIPT", "ERP_SHIPMENT", "ERP_PURCHASE", "MES_ISSUE")
    }
    assert pending["MES_RECEIPT"] == {"PL-0006"}
    assert pending["ERP_SHIPMENT"] == {"SH-0004"}
    assert pending["ERP_PURCHASE"] == {"PI-0004"}
    assert pending["MES_ISSUE"] and all(
        ref >= "LT-0013" for ref in pending["MES_ISSUE"]
    )
    assert _stock(client, negativeOnly="true") == []
    docs = _ok(client.get(f"{W}/documents"))
    assert len(docs) == 41 and all(
        d["documentNo"][3:11] == d["documentOn"].replace("-", "")
        and d["documentMonth"] == d["documentOn"][:7]
        for d in docs
    )
    reversal = next(d for d in docs if d["documentType"] == "REVERSAL")
    assert reversal["sourceRef"] == "PI-0006" and reversal["reversesDocumentNo"]
    draft = next(d for d in docs if d["status"] == "draft")
    assert draft["documentType"] == "TRANSFER"
    _ok(_call(client, created, "POST", f"/documents/{draft['id']}/post"))
    lt10 = {r["locationCode"]: r["onHand"] for r in _stock(client, lotNo="LT-0010")}
    assert lt10 == {"F-A01": "1440.000", "F-A02": "500.000"}
    assert _sync(client, created, "ERP_SHIPMENT", "ERP:SHIPMENT:SH-0004")["synced"] == 1
    assert _stock(client, itemCode="FG-C200", lotNo="LT-0008") == []
