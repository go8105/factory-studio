"""FS-018g F-07 목표 대비 실적 API. 검증 항목마다 테스트를 나눈다.

시드 목표는 FS-018e 비율표(월·대상별 90~105%)라 달성·초과가 섞인다. INS-02 당월 목표는 미설정.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/targets/performance"


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
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "targets"}
        ).json()["data"]
        yield client, created, engine
    reset_engine()


def _sql(engine: Engine, created, sql: str, **params):
    with engine.begin() as connection:
        return connection.execute(
            text(sql),
            {"w": created["workspaceId"], "g": created["generationId"], **params},
        )


def _data(client, **params):
    return client.get(BASE, params=params).json()["data"]


def _site(data, code):
    return next(r for r in data["site"] if r["energySourceCode"] == code)


def _equipment(data, code):
    return next(r for r in data["equipment"] if r["equipmentCode"] == code)


def test_site_section_has_each_source_and_toe_total(fems):
    client, _, _ = fems
    assert [(r["energySourceCode"], r["unit"]) for r in _data(client)["site"]] == [
        ("ELEC", "kWh"),
        ("GAS", "Nm3"),
        ("WATER", "m3"),
        (None, "TOE"),
    ]


def test_site_electricity_actual_is_main_meter_sum(fems):
    client, created, engine = fems
    expected = _sql(
        engine,
        created,
        """
        SELECT sum(r.value) FROM fems.energy_reading r
        JOIN fems.meter_channel c ON c.id=r.meter_channel_id
        WHERE r.workspace_id=:w AND r.generation_id=:g AND c.channel_code='CH-MAIN-KWH'
          AND r.quality<>'invalid'
          AND r.observed_at > TIMESTAMPTZ '2026-09-01 00:00+09'
          AND r.observed_at <= TIMESTAMPTZ '2026-09-24 00:00+09'
        """,
    ).scalar_one()
    assert Decimal(_site(_data(client), "ELEC")["actual"]) == expected


def test_achievement_rate_is_actual_over_target(fems):
    client, _, _ = fems
    elec = _site(_data(client), "ELEC")
    expected = (Decimal(elec["actual"]) / Decimal(elec["target"]) * 100).quantize(
        Decimal("0.1")
    )
    assert Decimal(elec["achievementRate"]) == expected


def test_toe_row_matches_dashboard(fems):
    client, _, _ = fems
    toe = _site(_data(client), None)
    dashboard = client.get("/api/v1/fems/dashboard").json()["data"]["target"]
    assert (toe["actual"], toe["achievementRate"]) == (
        dashboard["actual"],
        dashboard["achievementRate"],
    )


def test_site_results_mix_within_and_exceeded(fems):
    client, _, _ = fems
    assert {r["status"] for r in _data(client)["site"]} == {"WITHIN", "EXCEEDED"}


def test_water_is_compared_in_its_own_unit(fems):
    client, _, _ = fems
    water = _site(_data(client), "WATER")
    assert (water["unit"], water["status"] in {"WITHIN", "EXCEEDED"}) == ("m3", True)


def test_unit_mismatch_is_not_calculated(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.energy_target t SET unit='MWh' FROM fems.energy_source e "
        "WHERE e.id=t.energy_source_id AND t.workspace_id=:w AND t.generation_id=:g "
        "AND t.target_scope='SITE' AND e.source_code='ELEC' AND t.target_month='2026-09'",
    )
    elec = _site(_data(client), "ELEC")
    assert (elec["status"], elec["achievementRate"]) == ("NOT_CALCULABLE", None)


def test_equipment_without_target_is_unset(fems):
    client, _, _ = fems
    ins02 = _equipment(_data(client), "INS-02")
    assert (ins02["status"], ins02["target"], ins02["achievementRate"]) == (
        "UNSET",
        None,
        None,
    )


def test_equipment_actual_is_allocation_sum(fems):
    client, created, engine = fems
    expected = _sql(
        engine,
        created,
        """
        SELECT sum(a.quantity) FROM fems.energy_allocation a
        JOIN fems.equipment q ON q.id=a.equipment_id
        WHERE a.workspace_id=:w AND a.generation_id=:g AND q.equipment_code='INJ-01'
          AND a.unit='kWh' AND a.period_start >= TIMESTAMPTZ '2026-09-01 00:00+09'
        """,
    ).scalar_one()
    assert Decimal(_equipment(_data(client), "INJ-01")["actual"]) == expected


def test_equipment_results_mix_within_and_exceeded(fems):
    client, _, _ = fems
    statuses = {r["status"] for r in _data(client)["equipment"]}
    assert {"WITHIN", "EXCEEDED"} <= statuses


def test_equipment_estimated_days_are_reported(fems):
    client, _, _ = fems
    assert _equipment(_data(client), "ASM-02")["estimatedDays"] == 1


def test_equipment_target_without_actual_is_not_calculable(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "DELETE FROM fems.energy_allocation a USING fems.equipment q "
        "WHERE q.id=a.equipment_id AND a.workspace_id=:w AND a.generation_id=:g "
        "AND q.equipment_code='INJ-01' AND a.period_start >= TIMESTAMPTZ '2026-09-01 00:00+09'",
    )
    inj01 = _equipment(_data(client), "INJ-01")
    assert (inj01["actual"], inj01["status"]) == (None, "NOT_CALCULABLE")


def test_equipment_section_is_kwh_only(fems):
    client, _, _ = fems
    assert {r["unit"] for r in _data(client)["equipment"]} == {"kWh"}


def test_current_month_is_month_to_date(fems):
    client, _, _ = fems
    assert _data(client)["period"]["monthToDate"] is True


def test_previous_month_is_full_month(fems):
    client, _, _ = fems
    period = _data(client, month="2026-08")["period"]
    assert (period["to"], period["monthToDate"]) == ("2026-08-31", False)


def test_previous_month_has_ins02_target(fems):
    client, _, _ = fems
    assert _equipment(_data(client, month="2026-08"), "INS-02")["status"] != "UNSET"


def test_month_format_is_validated(fems):
    client, _, _ = fems
    assert client.get(BASE, params={"month": "2026-9"}).status_code == 400


def test_disabled_module_blocks_targets(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    assert client.get(BASE).status_code == 409
