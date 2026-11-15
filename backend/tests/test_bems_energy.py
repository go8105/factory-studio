"""BEMS-1f: 건물 에너지·공용 비용 배분·월간 보고서(DSN-16 F41~F44). FS_TODAY = 2026-09-24(목)."""

# ruff: noqa: F811
from decimal import Decimal

from sqlalchemy import text
from test_bems import (  # noqa: F401
    B,
    _advance,
    _call,
    _ok,
    _reason,
    bems,
)

MONTH = "2026-09"
TARGETS = "/energy-targets"


def _building(client, created, gross="2000"):
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/buildings",
            {"code": "BLD-A", "name": "본관", "floors": 3, "grossAreaM2": gross},
        ),
        201,
    )


def _place_zone(client, created, ids, zone, building_id, department, area):
    return _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/zones/{ids[zone]}",
            {
                "buildingId": building_id,
                "departmentCode": department,
                "floorAreaM2": area,
            },
        )
    )


def _readings(engine, created, ids, *, hours=3, kwh="10"):
    """공용 계측을 그 달에 직접 넣는다(1시간 진행은 업무 기준일 뒤만 만든다)."""
    params = {"w": created["workspaceId"], "g": created["generationId"]}
    with engine.begin() as c:
        for hour in range(hours):
            c.execute(
                text(
                    "INSERT INTO bems.energy_reading(workspace_id,generation_id,meter_id,period_start,value,source) "
                    "VALUES (:w,:g,:m, CAST(:t AS timestamptz), :v, 'SEED')"
                ),
                {
                    **params,
                    "m": ids["BM-HVAC"],
                    "t": f"2026-09-10T{hour:02d}:00:00+09:00",
                    "v": Decimal(kwh),
                },
            )


def test_building_energy_needs_area_and_target(bems):
    client, created, engine, ids = bems
    _readings(engine, created, ids)
    before = _ok(client.get(f"{B}/building-energy", params={"month": MONTH}))
    # 건물이 없으면 구역 면적 합으로 대신한다. 구역 면적도 없으면 원단위는 0이 아니라 모름이다.
    assert before["totalKwh"] == "30.00"
    assert before["euiKwhPerM2"] is None and before["targetKwh"] is None
    building = _building(client, created)
    _place_zone(client, created, ids, "Z-OFF", building["id"], None, "1000")
    with_area = _ok(client.get(f"{B}/building-energy", params={"month": MONTH}))
    assert with_area["grossAreaM2"] == "2000.00"
    assert with_area["euiKwhPerM2"] == "0.0150"  # 30 ÷ 2000
    assert with_area["achievement"] is None  # 목표가 없으면 달성률도 없다
    _ok(
        _call(
            client,
            created,
            "POST",
            TARGETS,
            {"targetMonth": MONTH, "targetKwh": "40"},
        ),
        201,
    )
    duplicate = _call(
        client, created, "POST", TARGETS, {"targetMonth": MONTH, "targetKwh": "50"}
    )
    assert duplicate.status_code == 400
    done = _ok(client.get(f"{B}/building-energy", params={"month": MONTH}))
    # 달성률 = 실적 ÷ 목표. 1 이하면 목표 이내(FEMS와 같은 규칙).
    assert done["achievement"] == "0.7500" and done["targetKwh"] == "40.00"
    zone = next(z for z in done["zones"] if z["zoneCode"] == "Z-OFF")
    assert zone["kwh"] == "30.00" and zone["euiKwhPerM2"] == "0.0300"


def test_cost_allocation_splits_by_department_area(bems):
    client, created, engine, ids = bems
    _readings(engine, created, ids)
    no_department = _call(client, created, "POST", "/cost-runs", {"month": MONTH})
    assert no_department.status_code == 409
    assert _reason(no_department) == "NO_DEPARTMENT_AREA"
    building = _building(client, created)
    _place_zone(client, created, ids, "Z-OFF", building["id"], "ADM", "1000")
    _place_zone(client, created, ids, "Z-PRD", building["id"], "PROD", "3000")
    run = _ok(_call(client, created, "POST", "/cost-runs", {"month": MONTH}), 201)
    assert run["status"] == "draft" and run["version"] == 1
    assert run["totalKwh"] == "30.00" and Decimal(run["totalCost"]) > 0
    codes = {line["departmentCode"]: line for line in run["lines"]}
    assert set(codes) == {"ADM", "PROD"}
    assert codes["ADM"]["share"] == "0.250000"
    # 줄의 합은 총액과 정확히 같다(끝수는 마지막 줄이 떠안는다).
    assert sum(Decimal(line["cost"]) for line in run["lines"]) == Decimal(
        run["totalCost"]
    )
    confirmed = _ok(_call(client, created, "POST", f"/cost-runs/{run['id']}/confirm"))
    assert confirmed["status"] == "confirmed" and confirmed["confirmedAt"]
    again = _call(client, created, "POST", f"/cost-runs/{run['id']}/confirm")
    assert again.status_code == 409 and _reason(again) == "BAD_STATE"
    # 다시 계산하면 새 버전 초안이 되고, 확정하면 옛 확정본은 대체된다.
    second = _ok(_call(client, created, "POST", "/cost-runs", {"month": MONTH}), 201)
    assert second["version"] == 2
    _ok(_call(client, created, "POST", f"/cost-runs/{second['id']}/confirm"))
    states = {r["version"]: r["status"] for r in _ok(client.get(f"{B}/cost-runs"))}
    assert states == {1: "superseded", 2: "confirmed"}


def test_review_takes_only_confirmed_cost(bems):
    client, created, engine, ids = bems
    _readings(engine, created, ids)
    no_area = _call(client, created, "POST", "/reviews", {"month": MONTH})
    assert no_area.status_code == 409 and _reason(no_area) == "NO_AREA"
    building = _building(client, created)
    _place_zone(client, created, ids, "Z-OFF", building["id"], "ADM", "1000")
    draft = _ok(
        _call(
            client, created, "POST", "/reviews", {"month": MONTH, "issues": "시운전"}
        ),
        201,
    )
    # 확정한 배분이 없으면 비용은 0이다 — 초안 비용을 보고서에 싣지 않는다.
    assert draft["totalCost"] == "0.00" and draft["issues"] == "시운전"
    assert draft["euiKwhPerM2"] == "0.0150"
    run = _ok(_call(client, created, "POST", "/cost-runs", {"month": MONTH}), 201)
    _ok(_call(client, created, "POST", f"/cost-runs/{run['id']}/confirm"))
    second = _ok(_call(client, created, "POST", "/reviews", {"month": MONTH}), 201)
    # 옛 초안은 남지 않는다(작업 중인 계산이다). 지웠으므로 버전도 다시 1이다.
    assert second["version"] == 1 and Decimal(second["totalCost"]) > 0
    assert [r["version"] for r in _ok(client.get(f"{B}/reviews"))] == [1]
    confirmed = _ok(_call(client, created, "POST", f"/reviews/{second['id']}/confirm"))
    assert confirmed["status"] == "confirmed"
    blocked = _call(client, created, "POST", f"/reviews/{second['id']}/confirm")
    assert blocked.status_code == 409
    # 확정본은 남으므로 다음 초안은 2가 되고, 확정하면 옛 확정본을 대체한다.
    third = _ok(_call(client, created, "POST", "/reviews", {"month": MONTH}), 201)
    assert third["version"] == 2
    _ok(_call(client, created, "POST", f"/reviews/{third['id']}/confirm"))
    states = {r["version"]: r["status"] for r in _ok(client.get(f"{B}/reviews"))}
    assert states == {1: "superseded", 2: "confirmed"}


def test_month_without_readings_is_refused(bems):
    client, created, _, _ = bems
    empty = _ok(client.get(f"{B}/building-energy", params={"month": "2026-01"}))
    assert empty["totalKwh"] == "0.00" and empty["zones"] == []
    for path in ("/cost-runs", "/reviews"):
        refused = _call(client, created, "POST", path, {"month": "2026-01"})
        assert refused.status_code == 409 and _reason(refused) == "NO_READINGS"
