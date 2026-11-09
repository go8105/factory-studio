"""BEMS-1c: 건물·층·부서, 조명 회로, 스케줄 휴일 구분(DSN-16 Q1·Q3). FS_TODAY = 2026-09-24(목)."""

# ruff: noqa: F811

from test_bems import (  # noqa: F401
    B,
    _advance,
    _call,
    _command,
    _ok,
    _reason,
    bems,
)

HOLIDAYS = "/api/v1/core/holidays"


def _building(client, created, code="BLD-A", floors=3):
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/buildings",
            {"code": code, "name": "본관", "floors": floors, "grossAreaM2": "2500.50"},
        ),
        201,
    )


def _circuit(client, created, ids, code="L-OFF", **extra):
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/lighting-circuits",
            {
                "zoneId": ids["Z-OFF"],
                "code": code,
                "name": "사무동 조명",
                "ratedKw": "6",
                **extra,
            },
        ),
        201,
    )


def _holiday(client, created, day="2026-09-24"):
    return _ok(
        _call(
            client,
            created,
            "POST",
            HOLIDAYS,
            {"date": day, "name": "임시 휴무", "kind": "COMPANY"},
        ),
        201,
    )


def test_zone_place_building_floor_department(bems):
    client, created, _, ids = bems
    building = _building(client, created)
    assert building["floors"] == 3 and building["grossAreaM2"] == "2500.50"
    no_building = _call(
        client, created, "PATCH", f"/zones/{ids['Z-OFF']}", {"floorLabel": "2F"}
    )
    assert no_building.status_code == 400
    assert "floorLabel" in no_building.json()["error"]["details"]["fields"]
    too_high = _call(
        client,
        created,
        "PATCH",
        f"/zones/{ids['Z-OFF']}",
        {"buildingId": building["id"], "floorLabel": "5F"},
    )
    assert too_high.status_code == 400
    zone = _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/zones/{ids['Z-OFF']}",
            {"buildingId": building["id"], "floorLabel": "B1", "departmentCode": "ADM"},
        )
    )
    assert (zone["buildingId"], zone["floorLabel"], zone["departmentCode"]) == (
        building["id"],
        "B1",
        "ADM",
    )
    # 건물을 비우면 층 표기도 비워야 한다.
    cleared = _call(
        client, created, "PATCH", f"/zones/{ids['Z-OFF']}", {"buildingId": None}
    )
    assert cleared.status_code == 400
    unknown = _call(
        client,
        created,
        "PATCH",
        f"/zones/{ids['Z-PRD']}",
        {"buildingId": 999999},
    )
    assert unknown.status_code == 400


def test_building_with_active_zone_cannot_be_deactivated(bems):
    client, created, _, ids = bems
    building = _building(client, created)
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/zones/{ids['Z-OFF']}",
            {"buildingId": building["id"]},
        )
    )
    blocked = _call(
        client, created, "PATCH", f"/buildings/{building['id']}", {"isActive": False}
    )
    assert (
        blocked.status_code == 409 and _reason(blocked) == "BUILDING_HAS_ACTIVE_ZONES"
    )
    _ok(_call(client, created, "PATCH", f"/zones/{ids['Z-OFF']}", {"isActive": False}))
    assert not _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/buildings/{building['id']}",
            {"isActive": False},
        )
    )["isActive"]


def test_lighting_circuit_rules_and_commands(bems):
    client, created, _, ids = bems
    wrong = _call(
        client,
        created,
        "POST",
        "/lighting-circuits",
        {
            "zoneId": ids["Z-PRD"],
            "code": "L-X",
            "name": "x",
            "ratedKw": "3",
            "meterId": ids["BM-LGT"],  # 사무동 계측기 — 다른 구역
        },
    )
    assert wrong.status_code == 400
    circuit = _circuit(client, created, ids, meterId=ids["BM-LGT"])
    assert (circuit["state"], circuit["controlSource"]) == ("OFF", "SCHEDULE")
    on = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="POWER_ON",
        lightingCircuitId=circuit["id"],
    )
    assert (on["result"], on["lightingCode"], on["hvacUnitId"]) == (
        "APPLIED",
        "L-OFF",
        None,
    )
    detail = _ok(client.get(f"{B}/lighting-circuits/{circuit['id']}/detail"))
    assert (detail["state"], detail["controlSource"]) == ("ON", "MANUAL")
    again = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="POWER_ON",
        lightingCircuitId=circuit["id"],
    )
    assert (again["result"], again["rejectReason"]) == ("REJECTED", "ALREADY_ON")
    mode = _call(
        client,
        created,
        "POST",
        "/commands",
        {
            "zoneId": ids["Z-OFF"],
            "command": "SET_MODE",
            "mode": "FAN",
            "lightingCircuitId": circuit["id"],
        },
    )
    assert mode.status_code == 400
    other_zone = _call(
        client,
        created,
        "POST",
        "/commands",
        {
            "zoneId": ids["Z-PRD"],
            "command": "POWER_OFF",
            "lightingCircuitId": circuit["id"],
        },
    )
    assert other_zone.status_code == 400
    # 조명 명령은 공조 이력에 섞이지 않는다.
    assert all(c["lightingCircuitId"] is None for c in _ok(client.get(f"{B}/commands")))
    unit = _ok(client.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail"))
    assert all(c["lightingCircuitId"] is None for c in unit["commands"])
    own = _ok(client.get(f"{B}/commands", params={"lightingCircuitId": circuit["id"]}))
    assert len(own) == 2


def test_lighting_schedule_switches_on_boundary(bems):
    client, created, _, ids = bems
    circuit = _circuit(client, created, ids)
    bad = _call(
        client,
        created,
        "PUT",
        f"/lighting-circuits/{circuit['id']}/schedule",
        {
            "slots": [
                {"dayKind": "WEEKDAY", "startHour": 1, "endHour": 3, "mode": "COOL"}
            ]
        },
    )
    assert bad.status_code == 400
    slots = _ok(
        _call(
            client,
            created,
            "PUT",
            f"/lighting-circuits/{circuit['id']}/schedule",
            {
                "slots": [
                    {"dayKind": "WEEKDAY", "startHour": 1, "endHour": 3, "mode": "ON"}
                ]
            },
        )
    )
    assert [(s["dayKind"], s["mode"]) for s in slots] == [("WEEKDAY", "ON")]
    hvac_bad = _call(
        client,
        created,
        "PUT",
        f"/hvac-units/{ids['AHU-OFF']}/schedule",
        {"slots": [{"dayKind": "WEEKDAY", "startHour": 1, "endHour": 3, "mode": "ON"}]},
    )
    assert hvac_bad.status_code == 400
    _ok(_advance(client, created, hours=2))  # 00:00, 01:00
    detail = _ok(client.get(f"{B}/lighting-circuits/{circuit['id']}/detail"))
    assert (detail["state"], detail["controlSource"]) == ("ON", "SCHEDULE")
    assert detail["commands"][0]["command"] == "POWER_ON"
    assert detail["commands"][0]["source"] == "SCHEDULE"
    _ok(_advance(client, created, hours=2))  # 02:00, 03:00 → 꺼짐
    detail = _ok(client.get(f"{B}/lighting-circuits/{circuit['id']}/detail"))
    assert detail["state"] == "OFF" and detail["commands"][0]["command"] == "POWER_OFF"


def test_holiday_uses_holiday_slots_else_weekend(bems):
    client, created, _, ids = bems
    _holiday(client, created)  # 2026-09-24(목)가 휴일
    unit = ids["AHU-OFF"]
    _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{unit}/schedule",
            {
                "slots": [
                    {
                        "dayKind": "WEEKDAY",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "COOL",
                    },
                    {
                        "dayKind": "WEEKEND",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "HEAT",
                    },
                ]
            },
        )
    )
    _ok(_advance(client, created))
    # 휴일 시간대가 하나도 없으면 주말을 따른다(평일 COOL이 아니다).
    assert _ok(client.get(f"{B}/hvac-units/{unit}/detail"))["state"] == "HEAT"
    slots = _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{unit}/schedule",
            {
                "slots": [
                    {
                        "dayKind": "HOLIDAY",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "FAN",
                    },
                    {
                        "dayKind": "WEEKEND",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "HEAT",
                    },
                    {
                        "dayKind": "WEEKDAY",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "COOL",
                    },
                ]
            },
        )
    )
    assert [s["dayKind"] for s in slots] == ["WEEKDAY", "WEEKEND", "HOLIDAY"]
    _ok(_advance(client, created))
    assert _ok(client.get(f"{B}/hvac-units/{unit}/detail"))["state"] == "FAN"


def test_non_holiday_thursday_still_follows_weekday(bems):
    client, created, _, ids = bems
    unit = ids["AHU-OFF"]
    _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{unit}/schedule",
            {
                "slots": [
                    {
                        "dayKind": "WEEKDAY",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "COOL",
                    },
                    {
                        "dayKind": "HOLIDAY",
                        "startHour": 0,
                        "endHour": 24,
                        "mode": "FAN",
                    },
                ]
            },
        )
    )
    _ok(_advance(client, created))
    assert _ok(client.get(f"{B}/hvac-units/{unit}/detail"))["state"] == "COOL"


def test_lookup_departments_follows_hr(bems):
    client, _, _, _ = bems
    lookup = _ok(client.get(f"{B}/lookups/departments"))
    assert set(lookup) == {"hrEnabled", "rows"}
