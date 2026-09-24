"""FS-018h F-08 요금 산정 API. 검증 항목마다 테스트를 나눈다.

시드 요금제: 전력 TR-ELEC-01(2025-09~2026-08, 기본 250,000 / 120원) → TR-ELEC-02(2026-09~, 130원),
가스 TR-GAS-01(30,000 / 1,100원), 용수 TR-WTR-01(15,000 / 1,300원). 계측은 08-25 ~ 09-23.
"""

from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/billing"


@pytest.fixture
def fems(clean_database: Engine, monkeypatch: pytest.MonkeyPatch):
    engine = clean_database
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv(
        "SESSION_SECRET", "fs018-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    with engine.begin() as connection:
        create_template(connection, date(2026, 9, 24))
    with TestClient(create_app(), base_url="https://testserver") as client:
        created = client.post(
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "billing"}
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


def _source(data, code):
    return next(s for s in data["sources"] if s["sourceCode"] == code)


def _main_usage(engine, created, month_start: str, month_end: str) -> Decimal:
    return _sql(
        engine,
        created,
        """
        SELECT sum(r.value) FROM fems.energy_reading r
        JOIN fems.meter_channel c ON c.id=r.meter_channel_id
        WHERE r.workspace_id=:w AND r.generation_id=:g AND c.channel_code='CH-MAIN-KWH'
          AND r.quality<>'invalid'
          AND r.observed_at > CAST(:a AS timestamptz) AND r.observed_at <= CAST(:b AS timestamptz)
        """,
        a=month_start,
        b=month_end,
    ).scalar_one()


def test_default_period_is_previous_and_current_month(fems):
    client, _, _ = fems
    period = _data(client)["period"]
    assert (period["from"], period["to"], period["monthToDate"]) == (
        "2026-08",
        "2026-09",
        True,
    )


def test_tariff_revision_splits_segments(fems):
    client, _, _ = fems
    segments = _source(_data(client), "ELEC")["segments"]
    assert [(s["month"], s["tariff"]["tariffCode"]) for s in segments] == [
        ("2026-08", "TR-ELEC-01"),
        ("2026-09", "TR-ELEC-02"),
    ]


def test_segment_amount_is_basic_plus_usage_times_rate(fems):
    client, created, engine = fems
    usage = _main_usage(engine, created, "2026-09-01 00:00+09", "2026-10-01 00:00+09")
    september = _source(_data(client), "ELEC")["segments"][1]
    assert Decimal(september["amount"]) == 250000 + (usage * 130).quantize(Decimal(1))


def test_previous_month_uses_previous_rate(fems):
    client, created, engine = fems
    usage = _main_usage(engine, created, "2026-08-01 00:00+09", "2026-09-01 00:00+09")
    august = _source(_data(client), "ELEC")["segments"][0]
    assert Decimal(august["usageCharge"]) == (usage * 120).quantize(Decimal(1))


def test_source_total_is_sum_of_segments(fems):
    client, _, _ = fems
    elec = _source(_data(client), "ELEC")
    assert Decimal(elec["total"]) == sum(Decimal(s["amount"]) for s in elec["segments"])


def test_grand_total_is_sum_of_sources(fems):
    client, _, _ = fems
    data = _data(client)
    assert Decimal(data["total"]) == sum(Decimal(s["total"]) for s in data["sources"])


def test_dashboard_charge_matches_billing_month(fems):
    client, _, _ = fems
    billing = _data(client, **{"from": "2026-09", "to": "2026-09"})
    dashboard = client.get("/api/v1/fems/dashboard").json()["data"]["charge"]
    assert dashboard["total"] == billing["total"]


def test_month_without_tariff_is_missing(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.tariff SET effective_from='2026-10' "
        "WHERE workspace_id=:w AND generation_id=:g AND tariff_code='TR-ELEC-02'",
    )
    data = _data(client)
    elec = _source(data, "ELEC")
    assert (elec["status"], elec["segments"][1]["amount"], data["complete"]) == (
        "TARIFF_MISSING",
        None,
        False,
    )


def test_missing_tariff_month_is_left_out_of_total(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.tariff SET effective_from='2026-10' "
        "WHERE workspace_id=:w AND generation_id=:g AND tariff_code='TR-ELEC-02'",
    )
    elec = _source(_data(client), "ELEC")
    assert Decimal(elec["total"]) == Decimal(elec["segments"][0]["amount"])


def test_non_billable_source_is_not_charged(fems):
    client, created, engine = fems
    _sql(
        engine,
        created,
        "UPDATE fems.energy_source SET is_billable=false "
        "WHERE workspace_id=:w AND generation_id=:g AND source_code='WATER'",
    )
    data = _data(client)
    water = _source(data, "WATER")
    assert (water["status"], water["total"], water["segments"]) == (
        "NOT_BILLABLE",
        None,
        [],
    )
    assert data["complete"] is True


def test_months_without_readings_are_not_billed(fems):
    client, _, _ = fems
    months = [
        s["month"]
        for s in _source(_data(client, **{"from": "2026-06", "to": "2026-09"}), "GAS")[
            "segments"
        ]
    ]
    assert months == ["2026-08", "2026-09"]


def test_amounts_are_strings(fems):
    client, _, _ = fems
    assert isinstance(_data(client)["total"], str)


def test_from_without_to_is_rejected(fems):
    client, _, _ = fems
    assert client.get(BASE, params={"from": "2026-08"}).status_code == 400


def test_reversed_months_are_rejected(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"from": "2026-09", "to": "2026-08"})
    assert response.status_code == 400


def test_more_than_12_months_is_rejected(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"from": "2025-09", "to": "2026-09"})
    assert response.status_code == 400


def test_disabled_module_blocks_billing(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    assert client.get(BASE).status_code == 409
