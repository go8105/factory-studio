"""FS-018d F-04 배출량 API. 검증 항목마다 테스트를 나눈다.

기대값은 API 구현을 거치지 않고 수전(CH-MAIN-KWH)·가스 채널 계측값을 직접 합해 만든다.
시드 EMISSION 계수: 전력 2025=0.000470, 2026=0.000460 tCO2eq/kWh, 가스 0.002220 tCO2eq/Nm3.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/emissions"
SEPT = {"from": "2026-09-01", "to": "2026-09-23"}
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
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "emis"}
        ).json()["data"]
        yield client, created, engine
    reset_engine()


def _sql(engine: Engine, created, sql: str, **params):
    with engine.begin() as connection:
        return connection.execute(
            text(sql),
            {"w": created["workspaceId"], "g": created["generationId"], **params},
        )


def _channel_sum(engine: Engine, created, channel: str) -> Decimal:
    """09-01 01:00 ~ 09-24 00:00 KST의 유효 계측값 합."""
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


def _source(body, code: str) -> dict:
    return next(s for s in body["data"]["sources"] if s["sourceCode"] == code)


def test_default_period_is_month_to_latest_day(fems):
    client, _, _ = fems
    assert client.get(BASE).json()["data"]["period"] == SEPT


def test_electricity_uses_top_level_meter_only(fems):
    client, created, engine = fems
    elec = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    expected = _channel_sum(engine, created, "CH-MAIN-KWH").quantize(SIX)
    assert Decimal(elec["consumption"]["quantity"]) == expected


def test_electricity_emission_uses_2026_factor(fems):
    client, created, engine = fems
    elec = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    expected = (
        _channel_sum(engine, created, "CH-MAIN-KWH") * Decimal("0.00046")
    ).quantize(SIX)
    assert Decimal(elec["emission"]) == expected
    assert elec["segments"][0]["factor"]["kind"] == "EMISSION"


def test_gas_emission_is_calculated(fems):
    client, created, engine = fems
    gas = _source(client.get(BASE, params=SEPT).json(), "GAS")
    expected = (
        _channel_sum(engine, created, "CH-GAS-NM3") * Decimal("0.00222")
    ).quantize(SIX)
    assert (gas["status"], Decimal(gas["emission"])) == ("CALCULATED", expected)


def test_utility_is_not_applicable(fems):
    client, _, _ = fems
    water = _source(client.get(BASE, params=SEPT).json(), "WATER")
    assert (water["status"], water["emission"]) == ("NOT_APPLICABLE", None)


def test_total_is_sum_of_calculated_sources(fems):
    client, _, _ = fems
    data = client.get(BASE, params=SEPT).json()["data"]
    parts = [Decimal(s["emission"]) for s in data["sources"] if s["emission"]]
    assert Decimal(data["totalEmission"]) == sum(parts)
    assert (data["unit"], data["complete"]) == ("tCO2eq", True)


def test_missing_factor_is_not_calculable(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "DELETE FROM fems.energy_factor f USING fems.energy_source e "
        "WHERE e.id=f.energy_source_id AND f.workspace_id=:w AND f.generation_id=:g "
        "AND e.source_code='GAS' AND f.factor_kind='EMISSION' AND f.effective_year='2026'",
    )
    data = client.get(BASE, params=SEPT).json()["data"]
    gas = _source({"data": data}, "GAS")
    assert (gas["status"], gas["emission"], data["complete"]) == (
        "FACTOR_MISSING",
        None,
        False,
    )


def test_primary_factor_is_never_used_for_emission(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "DELETE FROM fems.energy_factor f USING fems.energy_source e "
        "WHERE e.id=f.energy_source_id AND f.workspace_id=:w AND f.generation_id=:g "
        "AND e.source_code='ELEC' AND f.factor_kind='EMISSION'",
    )
    elec = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    assert elec["status"] == "FACTOR_MISSING"


def test_factor_unit_mismatch_is_not_calculated(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.energy_factor f SET factor_unit='tCO2eq/MWh' FROM fems.energy_source e "
        "WHERE e.id=f.energy_source_id AND f.workspace_id=:w AND f.generation_id=:g "
        "AND e.source_code='ELEC' AND f.factor_kind='EMISSION' AND f.effective_year='2026'",
    )
    elec = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    assert (elec["status"], elec["emission"]) == ("UNIT_MISMATCH", None)


def test_invalid_readings_are_excluded_and_counted(fems):
    client, created, engine = fems
    before = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    _sql(
        engine,
        created,
        "UPDATE fems.energy_reading r SET quality='invalid' FROM fems.meter_channel c "
        "WHERE c.id=r.meter_channel_id AND r.workspace_id=:w AND r.generation_id=:g "
        "AND c.channel_code='CH-MAIN-KWH' AND r.observed_at=TIMESTAMPTZ '2026-09-10 12:00+09'",
    )
    after = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    assert after["excludedReadings"] == 1
    assert Decimal(after["consumption"]["quantity"]) < Decimal(
        before["consumption"]["quantity"]
    )


def test_meter_multiplier_is_applied(fems):
    client, created, engine = fems
    before = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    _sql(
        engine,
        created,
        "UPDATE fems.meter_channel SET multiplier=2 "
        "WHERE workspace_id=:w AND generation_id=:g AND channel_code='CH-MAIN-KWH'",
    )
    after = _source(client.get(BASE, params=SEPT).json(), "ELEC")
    assert Decimal(after["consumption"]["quantity"]) == 2 * Decimal(
        before["consumption"]["quantity"]
    )


def test_period_crossing_years_uses_each_years_factor(fems):
    client, created, engine = fems
    # 2025-12-31 23~24시, 2026-01-01 00~01시 수전 계측값 100 kWh씩
    for observed, key in (
        ("2026-01-01 00:00+09", "Y-2025"),
        ("2026-01-01 01:00+09", "Y-2026"),
    ):
        _sql(
            engine,
            created,
            """
            INSERT INTO fems.energy_reading
              (workspace_id,generation_id,meter_channel_id,observed_at,period_start,
               value,unit,quality,source_key,input_revision)
            SELECT c.workspace_id,c.generation_id,c.id,CAST(:obs AS timestamptz),
                   CAST(:obs AS timestamptz) - interval '1 hour',100,'kWh','valid',:key,1
            FROM fems.meter_channel c
            WHERE c.workspace_id=:w AND c.generation_id=:g AND c.channel_code='CH-MAIN-KWH'
            """,
            obs=observed,
            key=key,
        )
    elec = _source(
        client.get(BASE, params={"from": "2025-12-31", "to": "2026-01-01"}).json(),
        "ELEC",
    )
    assert [
        (s["year"], s["factor"]["value"], s["emission"]) for s in elec["segments"]
    ] == [("2025", "0.000470", "0.047000"), ("2026", "0.000460", "0.046000")]


def test_values_are_strings(fems):
    client, _, _ = fems
    data = client.get(BASE, params=SEPT).json()["data"]
    assert isinstance(data["totalEmission"], str)


def test_period_over_366_days_is_rejected(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"from": "2025-01-01", "to": "2026-01-05"})
    assert response.status_code == 400


def test_disabled_module_blocks_emissions(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    assert client.get(BASE).status_code == 409
