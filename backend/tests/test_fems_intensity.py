"""FS-018j F-06 원단위 분석 API. 검증 항목마다 테스트를 나눈다.

핵심 검증: 시드 기준선(FS-005g 5.5 D-2 산식)을 같은 LOT(W01~W06 = LT-0013~0018)로 재현한다.
LT-0018 검사 생산량 0(전량 불량), LT-0016 검사는 v2(1,940)가 현재 확정본.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine

BASE = "/api/v1/fems/intensity"
ALL = {"from": "2026-08-25", "to": "2026-09-23"}


@pytest.fixture
def fems(clean_database: Engine, monkeypatch: pytest.MonkeyPatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    # 게스트 복사 기준일을 템플릿 날짜로 고정한다(실제 날짜가 바뀌어도 결과가 같다).
    monkeypatch.setenv("FS_TODAY", "2026-09-24")
    monkeypatch.setenv(
        "SESSION_SECRET", "fs018-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
    with TestClient(create_app(), base_url="https://testserver") as client:
        created = client.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "intensity"}
        ).json()["data"]
        yield client, created
    reset_engine()


def _h(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _data(client, **params):
    return client.get(BASE, params=params or ALL).json()["data"]


def _item(data, code):
    return next(i for i in data["items"] if i["itemCode"] == code)


def _record(data, key):
    return next(r for r in data["records"] if r["sourceKey"] == key)


@pytest.mark.parametrize("item", ["FG-C100", "FG-C200", "FG-T300"])
def test_item_intensity_reproduces_seed_baseline(fems, item):
    client, _ = fems
    row = _item(_data(client), item)
    assert row["intensity"] == row["baseline"]["value"]


def test_item_uses_only_completed_lots(fems):
    client, _ = fems
    assert _item(_data(client), "FG-C100")["lots"] == ["LT-0013", "LT-0016"]


def test_item_denominator_is_final_process_output(fems):
    client, _ = fems
    # LT-0013 검사 1,940 + LT-0016 검사 v2 1,940 (v1 1,904 오입력은 쓰지 않는다)
    assert _item(_data(client), "FG-C100")["output"]["quantity"] == "3880.000"


def test_zero_output_lot_counts_energy_but_not_output(fems):
    client, _ = fems
    t300 = _item(_data(client), "FG-T300")
    assert "LT-0018" in t300["lots"]
    assert Decimal(t300["output"]["quantity"]) == Decimal(
        _record(_data(client), "MES:LT-0015:INS")["productionQty"]
    )


def test_zero_production_record_is_not_calculated(fems):
    client, _ = fems
    record = _record(_data(client), "MES:LT-0018:INS")
    assert (record["status"], record["intensity"], record["toePerUnit"]) == (
        "NO_PRODUCTION",
        [],
        None,
    )


def test_record_intensity_is_energy_over_quantity(fems):
    client, _ = fems
    record = _record(_data(client), "MES:LT-0013:ASM")
    kwh = next(e for e in record["energy"] if e["unit"] == "kWh")
    value = next(i for i in record["intensity"] if i["unit"] == "kWh/EA")
    expected = (Decimal(kwh["quantity"]) / Decimal(record["productionQty"])).quantize(
        Decimal("0.000001")
    )
    assert Decimal(value["value"]) == expected


def test_energy_sources_are_kept_separate(fems):
    client, _ = fems
    units = {i["unit"] for i in _record(_data(client), "MES:LT-0013:INJ")["intensity"]}
    assert units == {"kWh/EA", "m3/EA"}


def test_toe_excludes_water(fems):
    client, _ = fems
    record = _record(_data(client), "MES:LT-0013:INJ")
    kwh = next(e for e in record["energy"] if e["unit"] == "kWh")
    expected = (
        Decimal(kwh["quantity"])
        * Decimal("0.000229")
        / Decimal(record["productionQty"])
    ).quantize(Decimal("0.000001"))
    assert Decimal(record["toePerUnit"]) == expected


def test_superseded_version_is_not_used(fems):
    client, _ = fems
    rows = [r for r in _data(client)["records"] if r["sourceKey"] == "MES:LT-0016:INS"]
    assert [r["versionNo"] for r in rows] == [2]


def test_draft_record_is_not_used(fems):
    client, created = fems
    equipment = next(
        e["id"]
        for e in client.get("/api/v1/fems/equipments", params={"limit": 200}).json()[
            "data"
        ]
        if e["equipmentCode"] == "INS-01"
    )
    client.post(
        "/api/v1/fems/production-records",
        json={
            "equipmentId": equipment,
            "itemCode": "FG-C100",
            "startDate": "2026-09-20",
            "endDate": "2026-09-20",
            "productionQty": "10",
            "unit": "EA",
        },
        headers=_h(created, "draft"),
    )
    keys = [r["sourceKey"] for r in _data(client)["records"]]
    assert not any(k.startswith("MAN-") for k in keys)


def test_manual_record_has_record_intensity_only(fems):
    client, created = fems
    equipment = next(
        e["id"]
        for e in client.get("/api/v1/fems/equipments", params={"limit": 200}).json()[
            "data"
        ]
        if e["equipmentCode"] == "INS-01"
    )
    record = client.post(
        "/api/v1/fems/production-records",
        json={
            "equipmentId": equipment,
            "itemCode": "FG-X900",
            "startDate": "2026-09-22",
            "endDate": "2026-09-22",
            "productionQty": "10",
            "unit": "EA",
        },
        headers=_h(created, "manual"),
    ).json()["data"]
    client.post(
        f"/api/v1/fems/production-records/{record['id']}/confirm",
        headers=_h(created, "manual-f"),
    )
    data = _data(client)
    assert _record(data, record["sourceKey"])["status"] == "CALCULATED"
    assert "FG-X900" not in [i["itemCode"] for i in data["items"]]


def test_lot_cut_by_period_is_excluded_from_item(fems):
    client, _ = fems
    # LT-0013 사출이 08-25~08-27이라 08-27부터 보면 LT-0013은 품목 원단위에서 빠진다.
    lots = _item(
        _data(client, **{"from": "2026-08-27", "to": "2026-09-23"}), "FG-C100"
    )["lots"]
    assert "LT-0013" not in lots


def test_change_rate_against_baseline(fems):
    client, _ = fems
    assert _item(_data(client), "FG-C100")["changeRate"] == "0.0"


def test_draft_baseline_is_not_compared(fems):
    client, _ = fems
    # T300은 확정 BL-T300-01과 초안 BL-T300-02가 있다. 초안은 비교에 쓰지 않는다.
    assert _item(_data(client), "FG-T300")["baseline"]["code"] == "BL-T300-01"


def test_values_are_strings(fems):
    client, _ = fems
    assert isinstance(_item(_data(client), "FG-C100")["intensity"], str)


def test_default_period_is_31_days_to_latest(fems):
    client, _ = fems
    period = client.get(BASE).json()["data"]["period"]
    assert period == {"from": "2026-08-24", "to": "2026-09-23"}


def test_period_over_92_days_is_rejected(fems):
    client, _ = fems
    response = client.get(BASE, params={"from": "2026-05-01", "to": "2026-09-01"})
    assert response.status_code == 400


def test_disabled_module_blocks_intensity(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers=_h(created, "off"),
    )
    assert client.get(BASE).status_code == 409
