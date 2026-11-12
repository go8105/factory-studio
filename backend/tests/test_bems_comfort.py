"""BEMS-1d: 환경 지표 6종, 쾌적도(DSN-16 F13·F14), 설비 경보(F32). FS_TODAY = 2026-09-24(목)."""

# ruff: noqa: F811
from decimal import Decimal

from test_bems import (  # noqa: F401
    B,
    _advance,
    _call,
    _command,
    _ok,
    _reason,
    bems,
)

COMFORT = "/comfort-standards"
RULES = "/equipment-alarm-rules"


def _sensor(client, created, ids, zone, metric):
    return _ok(
        _call(
            client,
            created,
            "POST",
            "/sensors",
            {"zoneId": ids[zone], "code": f"S-{metric[:4]}", "metric": metric},
        ),
        201,
    )


def _standard(client, created, **body):
    return _call(client, created, "POST", COMFORT, body)


def _schedule(client, created, unit_id, start=0, end=24, day="WEEKDAY"):
    return _ok(
        _call(
            client,
            created,
            "PUT",
            f"/hvac-units/{unit_id}/schedule",
            {
                "slots": [
                    {
                        "dayKind": day,
                        "startHour": start,
                        "endHour": end,
                        "mode": "COOL",
                    }
                ]
            },
        )
    )


def test_six_metrics_have_their_own_units(bems):
    client, created, _, ids = bems
    units = {}
    for metric in ("PM25", "LUX", "OCCUPANCY"):
        units[metric] = _sensor(client, created, ids, "Z-OFF", metric)["unit"]
    assert units == {"PM25": "㎍/㎥", "LUX": "lx", "OCCUPANCY": "명"}
    # 환경 경보 규칙은 3종 그대로다(DSN-16은 센서만 6종으로 늘렸다).
    rejected = _call(
        client,
        created,
        "POST",
        "/alarm-rules",
        {
            "zoneId": ids["Z-OFF"],
            "metric": "PM25",
            "comparator": "HIGH",
            "threshold": "35",
            "durationHours": 2,
            "severity": "WARNING",
        },
    )
    assert rejected.status_code in (400, 422)


def test_advance_writes_the_new_metrics(bems):
    client, created, _, ids = bems
    for metric in ("PM25", "LUX", "OCCUPANCY"):
        _sensor(client, created, ids, "Z-OFF", metric)
    _ok(_advance(client, created))  # 2026-09-24 00:00 — 야간, 조명 꺼짐
    night = {
        r["metric"]: r["value"]
        for r in _ok(
            client.get(
                f"{B}/environment",
                params={"zoneId": ids["Z-OFF"], "from": "2026-09-24"},
            )
        )["readings"]
    }
    assert Decimal(night["OCCUPANCY"]) == 0  # 00시는 근무 시간이 아니다
    assert Decimal(night["LUX"]) == 0  # 자연광도 조명도 없다
    assert Decimal(night["PM25"]) > 0


def test_lighting_raises_lux(bems):
    client, created, _, ids = bems
    _sensor(client, created, ids, "Z-OFF", "LUX")
    circuit = _ok(
        _call(
            client,
            created,
            "POST",
            "/lighting-circuits",
            {
                "zoneId": ids["Z-OFF"],
                "code": "L-OFF",
                "name": "사무동 조명",
                "ratedKw": "6",
            },
        ),
        201,
    )
    _command(
        client,
        created,
        ids,
        "Z-OFF",
        command="POWER_ON",
        lightingCircuitId=circuit["id"],
    )
    _ok(_advance(client, created))
    lit = [
        r
        for r in _ok(
            client.get(
                f"{B}/environment",
                params={"zoneId": ids["Z-OFF"], "from": "2026-09-24"},
            )
        )["readings"]
        if r["metric"] == "LUX"
    ]
    assert Decimal(lit[0]["value"]) > 0


def test_comfort_ratio_counts_only_scheduled_hours(bems):
    client, created, _, ids = bems
    _schedule(client, created, ids["AHU-OFF"], 0, 2)  # 평일 00~02시만 근무
    assert (
        _standard(
            client, created, zoneKind="OFFICE", metric="TEMP", low="20", high="26"
        ).status_code
        == 201
    )
    duplicate = _standard(
        client, created, zoneKind="OFFICE", metric="TEMP", low="18", high="28"
    )
    assert duplicate.status_code == 400
    neither = _standard(client, created, zoneKind="OFFICE", metric="CO2")
    assert neither.status_code in (400, 422)
    _ok(_advance(client, created, hours=4))  # 00,01,02,03시
    row = next(
        r
        for r in _ok(client.get(f"{B}/comfort"))["rows"]
        if r["zoneCode"] == "Z-OFF" and r["metric"] == "TEMP"
    )
    # 00·01시만 스케줄 안이다. 02·03시 관측은 세지 않는다.
    assert row["hours"] == 2 and row["occupiedOnly"] is True
    assert row["ratio"] is not None and row["reason"] is None


def test_comfort_without_schedule_is_unknown_not_zero(bems):
    client, created, _, _ = bems
    assert (
        _standard(
            client, created, zoneKind="OFFICE", metric="TEMP", low="20", high="26"
        ).status_code
        == 201
    )
    assert (
        _standard(
            client,
            created,
            zoneKind="PRODUCTION",
            metric="TEMP",
            low="18",
            high="28",
            occupiedOnly=False,
        ).status_code
        == 201
    )
    _ok(_advance(client, created, hours=2))
    rows = {
        (r["zoneCode"], r["metric"]): r for r in _ok(client.get(f"{B}/comfort"))["rows"]
    }
    office = rows[("Z-OFF", "TEMP")]
    assert office["ratio"] is None and office["reason"] == "NO_SCHEDULE"
    # 근무 시간만이 아니면 스케줄이 없어도 전체 관측으로 센다.
    production = rows[("Z-PRD", "TEMP")]
    assert production["hours"] == 2 and production["ratio"] is not None


def test_equipment_alarm_on_consecutive_rejections(bems):
    client, created, _, ids = bems
    _ok(
        _call(
            client,
            created,
            "POST",
            RULES,
            {
                "code": "EQ-REJECT",
                "condition": "COMMAND_REJECTED",
                "threshold": "2",
                "severity": "WARNING",
            },
        ),
        201,
    )
    # 꺼진 공조기를 두 번 더 끄면 거부 2연속.
    for _ in range(2):
        assert (
            _command(
                client,
                created,
                ids,
                "Z-OFF",
                command="POWER_OFF",
                hvacUnitId=ids["AHU-OFF"],
            )["result"]
            == "REJECTED"
        )
    assert not _ok(client.get(f"{B}/equipment-alarms"))  # 진행 전에는 판정하지 않는다
    _ok(_advance(client, created))
    alarm = _ok(client.get(f"{B}/equipment-alarms", params={"status": "raised"}))[0]
    assert (alarm["ruleCode"], alarm["hvacCode"], alarm["condition"]) == (
        "EQ-REJECT",
        "AHU-OFF",
        "COMMAND_REJECTED",
    )
    acknowledged = _ok(
        _call(client, created, "POST", f"/equipment-alarms/{alarm['id']}/acknowledge")
    )
    assert acknowledged["status"] == "acknowledged"
    again = _call(
        client, created, "POST", f"/equipment-alarms/{alarm['id']}/acknowledge"
    )
    assert again.status_code == 409 and _reason(again) == "NOT_RAISED"
    # 적용 명령이 하나 끼면 연속이 끊겨 해제된다.
    _command(
        client, created, ids, "Z-OFF", command="POWER_ON", hvacUnitId=ids["AHU-OFF"]
    )
    _ok(_advance(client, created))
    assert not _ok(client.get(f"{B}/equipment-alarms", params={"status": "raised"}))
    assert _ok(client.get(f"{B}/equipment-alarms", params={"status": "cleared"}))


def test_long_run_needs_a_known_stop(bems):
    client, created, _, ids = bems
    _ok(
        _call(
            client,
            created,
            "POST",
            RULES,
            {
                "code": "EQ-LONGRUN",
                "condition": "LONG_RUN",
                "threshold": "2",
                "severity": "CRITICAL",
            },
        ),
        201,
    )
    # 정지 이력 없이 켜 두면 얼마나 돌았는지 알 수 없어 경보하지 않는다.
    _command(
        client, created, ids, "Z-OFF", command="POWER_ON", hvacUnitId=ids["AHU-OFF"]
    )
    _ok(_advance(client, created, hours=4))
    assert not _ok(client.get(f"{B}/equipment-alarms", params={"status": "raised"}))
    # 한 번 끄고 다시 켜면 그때부터 잰다.
    _command(
        client, created, ids, "Z-OFF", command="POWER_OFF", hvacUnitId=ids["AHU-OFF"]
    )
    _command(
        client, created, ids, "Z-OFF", command="POWER_ON", hvacUnitId=ids["AHU-OFF"]
    )
    _ok(_advance(client, created, hours=3))
    raised = _ok(client.get(f"{B}/equipment-alarms", params={"status": "raised"}))
    assert [a["condition"] for a in raised] == ["LONG_RUN"]


def test_equipment_rule_targets_one_unit(bems):
    client, created, _, ids = bems
    missing = _call(
        client,
        created,
        "POST",
        RULES,
        {
            "code": "EQ-ONE",
            "condition": "LONG_RUN",
            "hvacUnitId": 999999,
            "threshold": "2",
            "severity": "WARNING",
        },
    )
    assert missing.status_code == 400
    rule = _ok(
        _call(
            client,
            created,
            "POST",
            RULES,
            {
                "code": "EQ-ONE",
                "condition": "COMMAND_REJECTED",
                "hvacUnitId": ids["AHU-PRD"],
                "threshold": "1",
                "severity": "WARNING",
            },
        ),
        201,
    )
    assert rule["hvacUnitId"] == ids["AHU-PRD"]
    _command(
        client, created, ids, "Z-OFF", command="POWER_OFF", hvacUnitId=ids["AHU-OFF"]
    )
    _ok(_advance(client, created))
    # 규칙이 생산동 공조기만 보므로 사무동 거부는 경보가 되지 않는다.
    assert not [
        a
        for a in _ok(client.get(f"{B}/equipment-alarms"))
        if a["hvacCode"] == "AHU-OFF"
    ]
