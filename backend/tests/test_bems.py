"""FS-025b BEMS API (AC-125~138). 검증 항목마다 테스트를 나눈다.

BEMS 시드는 FS-025c다. 기준정보(구역·계측기·센서·공조기)는 `bems` fixture가 API로 만든다.
FEMS는 템플릿 시드(T−30~T−1 수전·설비 배분)를 읽기 전용 조회로 읽는다(D9). FS_TODAY = 2026-09-24(목).
시뮬레이션은 관측 이력이 없으면 T 00:00(KST)부터 시작하고 T+1 00:00 전까지만 진행한다.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from itertools import count
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

B = "/api/v1/bems"
SEOUL = ZoneInfo("Asia/Seoul")
T = datetime(2026, 9, 24, tzinfo=SEOUL)
_keys = count()


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{B}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"b{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _setup(client, created) -> dict:
    ids = {}
    for code, name, kind in (
        ("Z-OFF", "사무동", "OFFICE"),
        ("Z-PRD", "생산동", "PRODUCTION"),
    ):
        ids[code] = _ok(
            _call(
                client,
                created,
                "POST",
                "/zones",
                {"code": code, "name": name, "kind": kind},
            ),
            201,
        )["id"]
    for code, zone, usage in (
        ("BM-HVAC", "Z-OFF", "HVAC"),
        ("BM-HVAC2", "Z-PRD", "HVAC"),
        ("BM-LGT", "Z-OFF", "LIGHTING"),
    ):
        ids[code] = _ok(
            _call(
                client,
                created,
                "POST",
                "/meters",
                {"zoneId": ids[zone], "code": code, "name": code, "usage": usage},
            ),
            201,
        )["id"]
    for zone in ("Z-OFF", "Z-PRD"):
        for metric in ("TEMP", "HUMIDITY", "CO2"):
            code = f"S-{zone[2:]}-{metric[:3]}"
            ids[code] = _ok(
                _call(
                    client,
                    created,
                    "POST",
                    "/sensors",
                    {"zoneId": ids[zone], "code": code, "metric": metric},
                ),
                201,
            )["id"]
    for code, zone, meter in (
        ("AHU-OFF", "Z-OFF", "BM-HVAC"),
        ("AHU-PRD", "Z-PRD", "BM-HVAC2"),
    ):
        ids[code] = _ok(
            _call(
                client,
                created,
                "POST",
                "/hvac-units",
                {
                    "zoneId": ids[zone],
                    "code": code,
                    "name": code,
                    "meterId": ids[meter],
                    "ratedKw": "12",
                },
            ),
            201,
        )["id"]
    return ids


BEMS_TABLES = (
    "alarm",
    "alarm_rule",
    "control_command",
    "schedule_slot",
    "environment_reading",
    "energy_reading",
    "hvac_unit",
    "sensor",
    "meter",
    "zone",
)


@pytest.fixture
def bems(guest_space):
    """시드(FS-025c)를 지운 빈 BEMS에서 기준정보를 새로 만든다."""
    client, created, engine = guest_space
    with engine.begin() as connection:
        for table in BEMS_TABLES:
            connection.execute(
                text(
                    f"DELETE FROM bems.{table} WHERE workspace_id=:w AND generation_id=:g"
                ),
                {"w": created["workspaceId"], "g": created["generationId"]},
            )
    return client, created, engine, _setup(client, created)


def test_seeded_demo(guest_space):
    """FS-025c 시드: 분해 30일 잔여 음수 없음, 사무동 CO₂ 확인 대기 1건, 진행은 T 00:00부터."""
    client, _, _ = guest_space
    rows = _ok(client.get(f"{B}/breakdown"))["rows"]
    assert len(rows) == 30 and not any(r["mismatch"] for r in rows)
    assert all(Decimal(r["common"]) > 0 and r["missingHours"] == 0 for r in rows)
    board = _ok(client.get(f"{B}/dashboard"))
    assert [(a["zoneCode"], a["metric"], a["status"]) for a in board["alarms"]] == [
        ("Z-OFF", "CO2", "raised")
    ]
    assert board["clock"]["next"].startswith("2026-09-24T00:00")
    unit = _ok(client.get(f"{B}/hvac-overview"))[0]
    assert (unit["code"], unit["state"], unit["controlSource"]) == (
        "AHU-OFF",
        "OFF",
        "SCHEDULE",
    )
    assert len(_ok(client.get(f"{B}/alarms", params={"status": "cleared"}))) == 3


def _command(client, created, ids, zone, **body):
    return _ok(
        _call(client, created, "POST", "/commands", {"zoneId": ids[zone], **body}), 201
    )


def _advance(client, created, hours=1, key=None):
    return _call(client, created, "POST", "/simulation/advance", {"hours": hours}, key)


def _seed_reading(engine, created, sensor_id, at, value):
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO bems.environment_reading(workspace_id,generation_id,sensor_id,period_start,value,source) "
                "VALUES (:w,:g,:s,:t,:v,'SEED')"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "s": sensor_id,
                "t": at,
                "v": value,
            },
        )


def test_guest_has_bems_module(guest_space):
    client, _, _ = guest_space
    modules = {
        m["moduleKey"]: m["enabled"]
        for m in client.get("/api/v1/core/workspace/modules").json()["data"]
    }
    assert modules["bems"] is True


def test_master_rules(bems):
    client, created, _, ids = bems
    sensors = _ok(client.get(f"{B}/sensors", params={"zoneId": ids["Z-OFF"]}))
    assert {s["metric"]: s["unit"] for s in sensors} == {
        "TEMP": "℃",
        "HUMIDITY": "%",
        "CO2": "ppm",
    }
    dup = _call(
        client,
        created,
        "POST",
        "/sensors",
        {"zoneId": ids["Z-OFF"], "code": "S-DUP", "metric": "TEMP"},
    )
    assert (
        dup.status_code == 400 and "metric" in dup.json()["error"]["details"]["fields"]
    )
    wrong = _call(
        client,
        created,
        "POST",
        "/hvac-units",
        {
            "zoneId": ids["Z-OFF"],
            "code": "AHU-X",
            "name": "x",
            "meterId": ids["BM-LGT"],
            "ratedKw": "5",
        },
    )
    assert (
        wrong.status_code == 400
        and "meterId" in wrong.json()["error"]["details"]["fields"]
    )


def test_setpoint_is_changed_only_by_valid_command(bems):
    """AC-128: 범위 밖은 REJECTED 기록, 현재 설정값은 그대로."""
    client, created, _, ids = bems
    bad = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_SETPOINT",
        setpointKind="COOL_TEMP",
        value="31",
    )
    narrow = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_SETPOINT",
        setpointKind="COOL_TEMP",
        value="21",
    )
    assert (bad["result"], bad["rejectReason"]) == ("REJECTED", "OUT_OF_RANGE")
    assert narrow["rejectReason"] == "BAND_TOO_NARROW"
    unit = _ok(client.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail"))
    assert unit["setpoints"]["COOL_TEMP"] == "26"
    good = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_SETPOINT",
        setpointKind="COOL_TEMP",
        value="23",
    )
    assert good["result"] == "APPLIED"
    unit = _ok(client.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail"))
    assert unit["setpoints"]["COOL_TEMP"] == "23.00" and len(unit["commands"]) == 3
    off = _command(
        client, created, ids, "Z-OFF", command="POWER_OFF", hvacUnitId=ids["AHU-OFF"]
    )
    assert off["rejectReason"] == "ALREADY_OFF"


def test_schedule_overlap_is_rejected(bems):
    """AC-134"""
    client, created, _, ids = bems
    bad = _call(
        client,
        created,
        "PUT",
        f"/hvac-units/{ids['AHU-OFF']}/schedule",
        {
            "slots": [
                {"dayKind": "WEEKDAY", "startHour": 8, "endHour": 19, "mode": "COOL"},
                {"dayKind": "WEEKDAY", "startHour": 18, "endHour": 20, "mode": "FAN"},
            ]
        },
    )
    assert (
        bad.status_code == 400 and "slots.1" in bad.json()["error"]["details"]["fields"]
    )
    ok = _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{ids['AHU-OFF']}/schedule",
            {
                "slots": [
                    {
                        "dayKind": "WEEKDAY",
                        "startHour": 8,
                        "endHour": 19,
                        "mode": "COOL",
                    },
                    {
                        "dayKind": "WEEKEND",
                        "startHour": 10,
                        "endHour": 16,
                        "mode": "FAN",
                    },
                ]
            },
        )
    )
    assert len(ok) == 2


def test_advance_is_idempotent(bems):
    """AC-130: 같은 요청을 다시 보내도 관측은 한 번만."""
    client, created, _, _ = bems
    first = _ok(_advance(client, created, key="adv-1"))
    again = _ok(_advance(client, created, key="adv-1"))
    assert (
        first == again
        and first["hours"] == 1
        and first["from"].startswith("2026-09-24T00:00")
    )
    readings = _ok(
        client.get(f"{B}/energy", params={"from": "2026-09-24", "to": "2026-09-24"})
    )
    assert len(readings) == 3  # 계측기 3개 × 1시간
    clock = _ok(client.get(f"{B}/simulation/clock"))
    assert clock["next"].startswith("2026-09-24T01:00") and clock["canAdvance"]
    nxt = _ok(_advance(client, created))
    assert nxt["from"].startswith("2026-09-24T01:00")


def test_lower_cooling_setpoint_cools_more_and_uses_more_power(bems):
    """AC-131: 냉방 설정 23℃ 구역은 26℃ 구역보다 다음 시간 온도가 낮고 공조 전력이 크다."""
    client, created, engine, ids = bems
    for zone in ("OFF", "PRD"):
        _seed_reading(
            engine, created, ids[f"S-{zone}-TEM"], T - timedelta(hours=1), "28"
        )
    _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_SETPOINT",
        setpointKind="COOL_TEMP",
        value="23",
    )
    for unit, zone in (("AHU-OFF", "Z-OFF"), ("AHU-PRD", "Z-PRD")):
        _command(
            client,
            created,
            ids,
            zone,
            command="SET_MODE",
            hvacUnitId=ids[unit],
            mode="COOL",
        )
    _ok(_advance(client, created))
    temps = {
        z: _ok(
            client.get(
                f"{B}/environment",
                params={"zoneId": ids[z], "from": "2026-09-24", "to": "2026-09-24"},
            )
        )
        for z in ("Z-OFF", "Z-PRD")
    }
    value = {
        z: next(
            Decimal(r["value"]) for r in temps[z]["readings"] if r["metric"] == "TEMP"
        )
        for z in temps
    }
    assert value["Z-OFF"] < value["Z-PRD"]
    power = {
        r["meterCode"]: Decimal(r["value"])
        for r in _ok(client.get(f"{B}/energy", params={"from": "2026-09-24"}))
    }
    assert power["BM-HVAC"] > power["BM-HVAC2"] > 0


def test_manual_command_returns_to_schedule_at_boundary(bems):
    """AC-129: 수동 운전은 다음 스케줄 경계에서 스케줄로 돌아가고 SCHEDULE 명령으로 남는다."""
    client, created, _, ids = bems
    _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{ids['AHU-OFF']}/schedule",
            {
                "slots": [
                    {"dayKind": "WEEKDAY", "startHour": 1, "endHour": 3, "mode": "COOL"}
                ]
            },
        )
    )
    _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_MODE",
        hvacUnitId=ids["AHU-OFF"],
        mode="FAN",
    )
    _ok(_advance(client, created))  # 00:00 — 경계 아님, 수동 FAN 유지
    unit = _ok(client.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail"))
    assert (unit["state"], unit["controlSource"]) == ("FAN", "MANUAL")
    _ok(_advance(client, created))  # 01:00 — 스케줄 COOL 시작
    unit = _ok(client.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail"))
    assert (unit["state"], unit["controlSource"]) == ("COOL", "SCHEDULE")
    assert (
        unit["commands"][0]["source"] == "SCHEDULE"
        and unit["commands"][0]["command"] == "SET_MODE"
    )


def test_alarm_raise_acknowledge_clear(bems):
    """AC-132·133: 조건이 지속되면 1건 발생, 확인은 사람, 조건이 풀리면 해제. 해제된 경보는 확인 불가."""
    client, created, _, ids = bems
    rule = _ok(
        _call(
            client,
            created,
            "POST",
            "/alarm-rules",
            {
                "zoneId": ids["Z-OFF"],
                "metric": "CO2",
                "comparator": "HIGH",
                "threshold": "400",
                "durationHours": 2,
                "severity": "WARNING",
            },
        ),
        201,
    )
    assert _ok(_advance(client, created))["raised"] == 0  # 1시간만 참
    assert _ok(_advance(client, created))["raised"] == 1
    assert _ok(_advance(client, created))["raised"] == 0  # 이미 발생 — 1건 유지
    alarm = _ok(client.get(f"{B}/alarms", params={"status": "raised"}))[0]
    acked = _ok(
        _call(
            client,
            created,
            "POST",
            f"/alarms/{alarm['id']}/acknowledge",
            {"note": "환기 지시"},
        )
    )
    assert (acked["status"], acked["ackNote"]) == ("acknowledged", "환기 지시")
    again = _call(client, created, "POST", f"/alarms/{alarm['id']}/acknowledge", {})
    assert again.status_code == 409 and _reason(again) == "NOT_RAISED"
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/alarm-rules/{rule['id']}",
            {"threshold": "5000"},
        )
    )
    assert _ok(_advance(client, created))["cleared"] == 1
    cleared = _ok(client.get(f"{B}/alarms", params={"status": "cleared"}))
    assert len(cleared) == 1 and cleared[0]["clearedAt"]


def test_simulation_stops_before_next_business_day(bems):
    """AC-135"""
    client, created, _, _ = bems
    for _ in range(4):
        _ok(_advance(client, created, hours=6))
    blocked = _advance(client, created)
    assert blocked.status_code == 409 and _reason(blocked) == "SIMULATION_LIMIT"


def test_breakdown_adds_up_and_flags_negative_residual(bems):
    """AC-125·126: 전체 = 제조 + 공용 + 잔여, 잔여 음수는 불일치."""
    client, created, engine, ids = bems
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO bems.energy_reading(workspace_id,generation_id,meter_id,period_start,value,source) "
                "VALUES (:w,:g,:m,:t,99999,'SEED')"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "m": ids["BM-LGT"],
                "t": T - timedelta(days=5),
            },
        )
    rows = _ok(client.get(f"{B}/breakdown"))["rows"]
    assert len(rows) == 30
    for r in rows:
        assert Decimal(r["site"]) == Decimal(r["manufacturing"]) + Decimal(
            r["common"]
        ) + Decimal(r["residual"])
        assert r["mismatch"] == (Decimal(r["residual"]) < 0)
    flagged = [r for r in rows if r["mismatch"]]
    assert [r["period"] for r in flagged] == ["2026-09-19"]
    month = _ok(client.get(f"{B}/breakdown", params={"granularity": "month"}))["rows"]
    assert {r["period"] for r in month} <= {"2026-08", "2026-09"}


def test_fems_off_only_blocks_breakdown(bems):
    """AC-127: FEMS를 끄면 분해만 409, 나머지는 동작. BEMS를 꺼도 FEMS는 그대로."""
    client, created, _, _ = bems
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/fems",
            {"enabled": False},
        )
    )
    blocked = client.get(f"{B}/breakdown")
    assert blocked.status_code == 409 and _reason(blocked) == "SOURCE_MODULE_DISABLED"
    board = _ok(client.get(f"{B}/dashboard"))
    assert board["week"] is None and len(board["zones"]) == 2
    _ok(_advance(client, created))
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/fems",
            {"enabled": True},
        )
    )
    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/bems",
            {"enabled": False},
        )
    )
    assert client.get("/api/v1/fems/dashboard").status_code == 200
    assert client.get(f"{B}/dashboard").status_code == 409


def test_other_workspace_cannot_see_bems(bems):
    """AC-137"""
    client, created, _, ids = bems
    mine = _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="SET_SETPOINT",
        setpointKind="COOL_TEMP",
        value="24",
    )
    other = TestClient(client.app, base_url="https://testserver")
    assert (
        other.post(
            "/api/v1/core/guest-sessions",
            json={"nickname": "테스트 게스트"},
            headers={"Idempotency-Key": str(uuid4())},
        ).status_code
        == 201
    )
    assert other.get(f"{B}/hvac-units/{ids['AHU-OFF']}/detail").status_code == 404
    # 다른 공간에는 자기 시드 명령만 보인다.
    assert mine["id"] not in {
        c["id"] for c in other.get(f"{B}/commands").json()["data"]
    }
