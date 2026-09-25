"""FS-018c F-03 설비별 배분 API. 검증 항목마다 테스트를 나눈다.

시드: 전력 DIRECT_METER 8설비 × 30일, 용수 RUNTIME_SHARE 사출기 가동일 36행.
구간은 KST [D 00:00, D+1 00:00), 마지막 날 09-23. ASM-02 09-07은 estimated(결측 6시간).
"""

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from fs.main import create_app
from sqlalchemy import Engine, text

BASE = "/api/v1/fems/allocations"
DAY = {"from": "2026-09-10", "to": "2026-09-10"}


@pytest.fixture
def fems(guest_space):
    return guest_space


def _equipment(client, code: str) -> int:
    rows = client.get("/api/v1/fems/equipments", params={"limit": 200}).json()["data"]
    return next(r["id"] for r in rows if r["equipmentCode"] == code)


def _supersede(engine: Engine, created, equipment_code: str, **overrides) -> None:
    """같은 설비·채널·구간(09-10)에 새 결과를 한 행 추가한다."""
    values = {"method_key": "DIRECT_METER", "quality": "valid", "quantity": 1}
    values.update(overrides)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO fems.energy_allocation
                  (workspace_id,generation_id,equipment_id,meter_channel_id,period_start,period_end,
                   quantity,unit,method_key,method_version,input_revision,quality,basis)
                SELECT a.workspace_id,a.generation_id,a.equipment_id,a.meter_channel_id,
                       a.period_start,a.period_end,:quantity,a.unit,:method_key,2,2,:quality,
                       '{"summed_hours": 24, "missing_hours": 0}'
                FROM fems.energy_allocation a
                JOIN fems.equipment eq ON eq.id=a.equipment_id
                WHERE a.workspace_id=:w AND a.generation_id=:g AND eq.equipment_code=:code
                  AND a.method_key='DIRECT_METER'
                  AND a.period_start=TIMESTAMPTZ '2026-09-10 00:00+09'
                """
            ),
            {
                **values,
                "w": created["workspaceId"],
                "g": created["generationId"],
                "code": equipment_code,
            },
        )


def test_default_range_ends_at_latest_allocation_day(fems):
    client, _, _ = fems
    assert client.get(BASE).json()["range"] == {
        "from": "2026-09-17",
        "to": "2026-09-23",
    }


def test_direct_meter_rows_for_default_week(fems):
    client, _, _ = fems
    body = client.get(BASE, params={"methodKey": "DIRECT_METER"}).json()
    assert body["page"]["total"] == 8 * 7


def test_one_day_is_site_timezone_day(fems):
    client, _, _ = fems
    rows = client.get(
        BASE,
        params={
            **DAY,
            "equipmentId": _equipment(client, "INJ-01"),
            "methodKey": "DIRECT_METER",
        },
    ).json()["data"]
    assert [(r["periodStart"], r["periodEnd"]) for r in rows] == [
        ("2026-09-09T15:00:00+00:00", "2026-09-10T15:00:00+00:00")
    ]


def test_estimated_row_exposes_basis(fems):
    client, _, _ = fems
    rows = client.get(
        BASE,
        params={
            "from": "2026-09-07",
            "to": "2026-09-07",
            "equipmentId": _equipment(client, "ASM-02"),
        },
    ).json()["data"]
    assert rows[0]["quality"] == "estimated"
    assert rows[0]["basis"] == {"summed_hours": 18, "missing_hours": 6}


def test_runtime_share_basis_is_exposed(fems):
    client, _, _ = fems
    rows = client.get(BASE, params={"methodKey": "RUNTIME_SHARE", "limit": 1}).json()[
        "data"
    ]
    assert set(rows[0]["basis"]) == {
        "runtime_hours",
        "common_unallocated",
        "active_equipment_count",
    }


def test_quantity_is_string(fems):
    client, _, _ = fems
    assert isinstance(client.get(BASE).json()["data"][0]["quantity"], str)


def test_superseded_result_is_hidden_by_default(fems):
    client, created, engine = fems
    _supersede(engine, created, "INJ-01")
    rows = client.get(
        BASE,
        params={
            **DAY,
            "equipmentId": _equipment(client, "INJ-01"),
            "methodKey": "DIRECT_METER",
        },
    ).json()["data"]
    assert [(r["inputRevision"], r["isLatest"]) for r in rows] == [(2, True)]


def test_include_superseded_shows_previous_result(fems):
    client, created, engine = fems
    _supersede(engine, created, "INJ-01")
    rows = client.get(
        BASE,
        params={
            **DAY,
            "equipmentId": _equipment(client, "INJ-01"),
            "methodKey": "DIRECT_METER",
            "includeSuperseded": "true",
        },
    ).json()["data"]
    assert sorted((r["inputRevision"], r["isLatest"]) for r in rows) == [
        (1, False),
        (2, True),
    ]


def test_method_filter_keeps_latest_judgement(fems):
    client, created, engine = fems
    # 09-10 INJ-01 전력을 다른 방법으로 재산정. DIRECT_METER로 걸러도 옛 결과를 현재로 내면 안 된다.
    _supersede(engine, created, "INJ-01", method_key="RECALC_TEST")
    body = client.get(
        BASE,
        params={
            **DAY,
            "equipmentId": _equipment(client, "INJ-01"),
            "methodKey": "DIRECT_METER",
        },
    ).json()
    assert body["page"]["total"] == 0


def test_summary_uses_latest_result_only(fems):
    client, created, engine = fems
    _supersede(engine, created, "INJ-01", quantity=0)
    summary = client.get(BASE, params=DAY).json()["summary"]
    kwh = next(
        s for s in summary if s["equipmentCode"] == "INJ-01" and s["unit"] == "kWh"
    )
    assert Decimal(kwh["quantity"]) == 0


def test_summary_excludes_invalid_results(fems):
    client, created, engine = fems
    _supersede(engine, created, "INJ-01", quality="invalid")
    summary = client.get(BASE, params=DAY).json()["summary"]
    assert not any(
        s["equipmentCode"] == "INJ-01" and s["unit"] == "kWh" for s in summary
    )


def test_summary_counts_estimated_days(fems):
    client, _, _ = fems
    summary = client.get(
        BASE, params={"from": "2026-09-07", "to": "2026-09-07"}
    ).json()["summary"]
    asm = next(s for s in summary if s["equipmentCode"] == "ASM-02")
    assert (asm["days"], asm["estimatedDays"]) == (1, 1)


def test_summary_never_mixes_units(fems):
    client, _, _ = fems
    summary = client.get(BASE).json()["summary"]
    assert {s["unit"] for s in summary} == {"kWh", "m3"}
    injector = [s for s in summary if s["equipmentCode"] == "INJ-01"]
    assert sorted(s["unit"] for s in injector) == ["kWh", "m3"]


def test_reversed_range_is_rejected(fems):
    client, _, _ = fems
    response = client.get(BASE, params={"from": "2026-09-10", "to": "2026-09-01"})
    assert response.status_code == 400


def test_other_space_equipment_returns_nothing(fems):
    client, _, _ = fems
    with TestClient(create_app(), base_url="https://testserver") as other:
        other.post("/api/v1/core/guest-sessions", headers={"Idempotency-Key": "o"})
        foreign = _equipment(other, "INJ-01")
    body = client.get(BASE, params={"equipmentId": foreign}).json()
    assert (body["page"]["total"], body["summary"]) == (0, [])


def test_disabled_module_blocks_allocations(fems):
    client, created, _ = fems
    client.patch(
        "/api/v1/core/workspace/modules/fems",
        json={"enabled": False},
        headers={"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": "off"},
    )
    assert client.get(BASE).status_code == 409
