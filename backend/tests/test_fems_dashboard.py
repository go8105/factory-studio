"""FS-018f F-01 대시보드 API. 검증 항목마다 테스트를 나눈다.

기대값은 API를 거치지 않고 채널 계측값을 SQL로 직접 합해 만든다.
PRIMARY: 전력 0.000229 TOE/kWh, 가스 0.001040 TOE/Nm3. 전력 요금제 8월 TR-ELEC-01(120/kWh), 9월 TR-ELEC-02(130/kWh).
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/dashboard"
SIX = Decimal("0.000001")


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
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "dash"}
        ).json()["data"]
        yield client, created, engine
    reset_engine()


def _sql(engine: Engine, created, sql: str, **params):
    with engine.begin() as connection:
        return connection.execute(
            text(sql),
            {"w": created["workspaceId"], "g": created["generationId"], **params},
        )


def _september(engine: Engine, created, channel: str) -> Decimal:
    return _sql(
        engine,
        created,
        """
        SELECT sum(r.value) FROM fems.energy_reading r
        JOIN fems.meter_channel c ON c.id=r.meter_channel_id
        WHERE r.workspace_id=:w AND r.generation_id=:g AND c.channel_code=:ch
          AND r.quality<>'invalid'
          AND r.observed_at > TIMESTAMPTZ '2026-09-01 00:00+09'
          AND r.observed_at <= TIMESTAMPTZ '2026-09-24 00:00+09'
        """,
        ch=channel,
    ).scalar_one()


def _data(client, **params):
    return client.get(BASE, params=params).json()["data"]


def _charge(data, code: str) -> dict:
    return next(c for c in data["charge"]["sources"] if c["sourceCode"] == code)


def test_default_month_is_latest_reading_month_to_date(fems):
    client, _, _ = fems
    assert _data(client)["period"] == {
        "month": "2026-09",
        "from": "2026-09-01",
        "to": "2026-09-23",
    }


def test_primary_energy_converts_before_summing(fems):
    client, created, engine = fems
    elec = (_september(engine, created, "CH-MAIN-KWH") * Decimal("0.000229")).quantize(
        SIX
    )
    gas = (_september(engine, created, "CH-GAS-NM3") * Decimal("0.00104")).quantize(SIX)
    assert Decimal(_data(client)["primaryEnergy"]["total"]) == elec + gas


def test_water_is_not_in_primary_energy(fems):
    client, _, _ = fems
    water = next(
        s
        for s in _data(client)["primaryEnergy"]["sources"]
        if s["sourceCode"] == "WATER"
    )
    assert (water["status"], water["toe"]) == ("NOT_APPLICABLE", None)


def test_current_month_is_within_target(fems):
    # 비율표 9월 TOE 1.01 → 달성률 약 99%
    client, _, _ = fems
    target = _data(client)["target"]
    assert target["status"] == "SET"
    assert Decimal(target["achievementRate"]) <= 100


def test_previous_month_exceeds_target(fems):
    # 비율표 8월 TOE 0.96 → 달성률 약 104%
    client, _, _ = fems
    assert Decimal(_data(client, month="2026-08")["target"]["achievementRate"]) > 100


def test_achievement_rate_is_actual_over_target(fems):
    client, _, _ = fems
    target = _data(client)["target"]
    expected = (Decimal(target["actual"]) / Decimal(target["target"]) * 100).quantize(
        Decimal("0.1")
    )
    assert Decimal(target["achievementRate"]) == expected


def test_missing_target_is_unset(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "DELETE FROM fems.energy_target WHERE workspace_id=:w AND generation_id=:g "
        "AND target_scope='SITE' AND unit='TOE' AND target_month='2026-09'",
    )
    target = _data(client)["target"]
    assert (target["status"], target["achievementRate"]) == ("UNSET", None)


def test_electricity_charge_uses_current_tariff(fems):
    client, created, engine = fems
    usage = _september(engine, created, "CH-MAIN-KWH")
    elec = _charge(_data(client), "ELEC")
    assert elec["tariffCode"] == "TR-ELEC-02"
    assert Decimal(elec["amount"]) == (250000 + usage * 130).quantize(Decimal(1))


def test_previous_month_uses_previous_tariff(fems):
    client, _, _ = fems
    assert _charge(_data(client, month="2026-08"), "ELEC")["tariffCode"] == "TR-ELEC-01"


def test_missing_tariff_marks_charge_incomplete(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "DELETE FROM fems.tariff WHERE workspace_id=:w AND generation_id=:g "
        "AND tariff_code='TR-GAS-01'",
    )
    data = _data(client)
    assert (_charge(data, "GAS")["status"], data["charge"]["complete"]) == (
        "TARIFF_MISSING",
        False,
    )


def test_non_billable_source_has_no_charge(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.energy_source SET is_billable=false "
        "WHERE workspace_id=:w AND generation_id=:g AND source_code='WATER'",
    )
    codes = [c["sourceCode"] for c in _data(client)["charge"]["sources"]]
    assert "WATER" not in codes


def test_emission_matches_emissions_screen(fems):
    client, _, _ = fems
    emissions = client.get(
        "/api/v1/fems/emissions", params={"from": "2026-09-01", "to": "2026-09-23"}
    ).json()["data"]
    assert _data(client)["emission"]["total"] == emissions["totalEmission"]


def test_daily_trend_covers_each_day(fems):
    client, _, _ = fems
    daily = _data(client)["daily"]
    assert [d["date"] for d in daily][0::22] == ["2026-09-01", "2026-09-23"]
    assert len(daily) == 23


def test_daily_trend_adds_up_to_total(fems):
    client, _, _ = fems
    data = _data(client)
    daily = sum(Decimal(d["toe"]) for d in data["daily"])
    assert abs(daily - Decimal(data["primaryEnergy"]["total"])) <= Decimal("0.0001")


def test_top_equipment_is_five_kwh_rows_descending(fems):
    client, _, _ = fems
    top = _data(client)["topEquipment"]
    quantities = [Decimal(t["quantity"]) for t in top]
    assert len(top) == 5
    assert {t["unit"] for t in top} == {"kWh"}
    assert quantities == sorted(quantities, reverse=True)


def test_quality_issues_in_current_month(fems):
    client, _, _ = fems
    quality = _data(client)["quality"]
    assert (quality["issues"], len(quality["recent"])) == (6, 5)


def test_quality_issues_absent_in_previous_month(fems):
    client, _, _ = fems
    assert _data(client, month="2026-08")["quality"]["issues"] == 0


def test_month_without_readings_returns_zero(fems):
    client, _, _ = fems
    data = _data(client, month="2025-01")
    assert (data["primaryEnergy"]["total"], data["target"]["status"]) == ("0", "UNSET")


def test_month_format_is_validated(fems):
    client, _, _ = fems
    assert client.get(BASE, params={"month": "2026-13"}).status_code == 400


def test_disabled_module_blocks_dashboard(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    assert client.get(BASE).status_code == 409
