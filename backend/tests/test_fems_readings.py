"""FS-018b F-02 계측 조회 API. 검증 항목마다 테스트를 나눈다.

시드 기준일 2026-09-24: 전력 9채널은 KST 08-25 01:00 ~ 09-24 00:00 매시,
가스·용수는 일 1건(다음 날 00:00 관측). ASM-02 09-07 11~16시 6행이 결측(invalid).
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine

BASE = "/api/v1/fems/readings"


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
            "/api/v1/core/guest-sessions", headers={"Idempotency-Key": "readings"}
        ).json()["data"]
        yield client, created
    reset_engine()


def _channel(client, code: str) -> int:
    for meter in client.get("/api/v1/fems/meters").json()["data"]:
        for channel in meter["channels"]:
            if channel["channelCode"] == code:
                return channel["id"]
    raise AssertionError(code)


def _source(client, code: str) -> int:
    rows = client.get("/api/v1/fems/energy-sources").json()["data"]
    return next(r["id"] for r in rows if r["sourceCode"] == code)


def test_default_range_ends_at_latest_reading_day(fems):
    client, _ = fems
    assert client.get(BASE).json()["range"] == {
        "from": "2026-09-17",
        "to": "2026-09-23",
    }


def test_default_range_counts_all_channels(fems):
    client, _ = fems
    # 전력 9채널 × 7일 × 24시간 + 가스 7 + 용수 7
    assert client.get(BASE).json()["page"]["total"] == 9 * 7 * 24 + 7 + 7


def test_one_day_is_site_timezone_day(fems):
    client, _ = fems
    rows = client.get(
        BASE,
        params={
            "from": "2026-09-10",
            "to": "2026-09-10",
            "channelId": _channel(client, "CH-MAIN-KWH"),
        },
    ).json()["data"]
    assert len(rows) == 24
    assert rows[0]["observedAt"] == "2026-09-09T16:00:00+00:00"  # 09-10 01:00 KST
    assert rows[-1]["observedAt"] == "2026-09-10T15:00:00+00:00"  # 09-11 00:00 KST


def test_invalid_rows_have_no_value(fems):
    client, _ = fems
    rows = client.get(
        BASE, params={"from": "2026-09-07", "to": "2026-09-07", "quality": "invalid"}
    ).json()["data"]
    assert len(rows) == 6
    assert {r["value"] for r in rows} == {None}


def test_missing_rows_stay_in_channel_listing(fems):
    client, _ = fems
    rows = client.get(
        BASE,
        params={
            "from": "2026-09-07",
            "to": "2026-09-07",
            "channelId": _channel(client, "CH-ASM-02-KWH"),
        },
    ).json()["data"]
    assert len(rows) == 24
    assert sum(r["quality"] == "invalid" for r in rows) == 6


def test_values_are_strings(fems):
    client, _ = fems
    row = client.get(BASE, params={"quality": "valid", "limit": 1}).json()["data"][0]
    assert isinstance(row["value"], str)


def test_channel_filter(fems):
    client, _ = fems
    rows = client.get(
        BASE, params={"channelId": _channel(client, "CH-INJ-01-KWH"), "limit": 200}
    ).json()["data"]
    assert {r["channelCode"] for r in rows} == {"CH-INJ-01-KWH"}


def test_energy_source_filter(fems):
    client, _ = fems
    body = client.get(BASE, params={"energySourceId": _source(client, "GAS")}).json()
    assert body["page"]["total"] == 7
    assert {r["unit"] for r in body["data"]} == {"Nm3"}


def test_quality_rejects_unknown_value(fems):
    client, _ = fems
    assert client.get(BASE, params={"quality": "missing"}).status_code == 400


def test_from_without_to_is_rejected(fems):
    client, _ = fems
    response = client.get(BASE, params={"from": "2026-09-01"})
    assert response.status_code == 400
    assert "to" in response.json()["error"]["details"]["fields"]


def test_reversed_range_is_rejected(fems):
    client, _ = fems
    response = client.get(BASE, params={"from": "2026-09-10", "to": "2026-09-01"})
    assert response.status_code == 400


def test_range_over_31_days_is_rejected(fems):
    client, _ = fems
    response = client.get(BASE, params={"from": "2026-08-01", "to": "2026-09-01"})
    assert response.status_code == 400


def test_sort_desc(fems):
    client, _ = fems
    rows = client.get(BASE, params={"sort": "observedAt:desc", "limit": 2}).json()[
        "data"
    ]
    assert rows[0]["observedAt"] >= rows[1]["observedAt"]


def test_sort_rejects_unknown_field(fems):
    client, _ = fems
    assert client.get(BASE, params={"sort": "value:asc"}).status_code == 400


def test_other_space_channel_returns_nothing(fems):
    client, _ = fems
    with TestClient(create_app(), base_url="https://testserver") as other:
        other.post("/api/v1/core/guest-sessions", headers={"Idempotency-Key": "other"})
        foreign = _channel(other, "CH-MAIN-KWH")
    assert client.get(BASE, params={"channelId": foreign}).json()["page"]["total"] == 0


def test_disabled_module_blocks_readings(fems):
    client, created = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    response = client.get(BASE)
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "MODULE_DISABLED"


def test_meters_include_channels(fems):
    client, _ = fems
    meters = client.get("/api/v1/fems/meters").json()["data"]
    assert len(meters) == 11
    assert sum(len(m["channels"]) for m in meters) == 11


def test_sites_list(fems):
    client, _ = fems
    sites = client.get("/api/v1/fems/sites").json()["data"]
    assert [s["timezone"] for s in sites] == ["Asia/Seoul"]
