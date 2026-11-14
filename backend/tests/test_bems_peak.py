"""BEMS-1e: 피크 감축(DSN-16 F24·Q2). 제안 → 승인·실행 → 경보 해제 → 복귀. FS_TODAY = 2026-09-24(목)."""

# ruff: noqa: F811
from decimal import Decimal

from sqlalchemy import text
from test_bems import (  # noqa: F401
    B,
    _advance,
    _call,
    _command,
    _ok,
    _reason,
    bems,
)

PLANS = "/demand-plans"


CONTRACT_KW = Decimal(100)


def _peak_alarm(engine, created, *, ratio="0.9", peak="98", code="PEAK-1"):
    """FEMS 쪽에 진행 중인 피크 경보를 하나 만든다(BEMS는 조회로만 읽는다).

    PEAK 규칙의 한계값은 kW가 아니라 **계약전력 대비 비율**이고, 계약전력이 없으면 FEMS는
    피크를 판정하지도 않는다. 그래서 전력 요금제에 계약전력을 세워 둔다.
    """
    params = {"w": created["workspaceId"], "g": created["generationId"]}
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE fems.tariff SET contract_kw=:kw WHERE workspace_id=:w AND generation_id=:g "
                "AND tariff_code='TR-ELEC-02'"
            ),
            {**params, "kw": CONTRACT_KW},
        )
        channel = c.execute(
            text(
                "SELECT id FROM fems.meter_channel WHERE workspace_id=:w AND generation_id=:g "
                "ORDER BY id LIMIT 1"
            ),
            params,
        ).scalar_one()
        rule_id = c.execute(
            text(
                "INSERT INTO fems.alarm_rule(workspace_id,generation_id,code,name,alarm_kind,threshold,unit,meter_channel_id) "
                "VALUES (:w,:g,:code,'합성 피크','PEAK',:t,'%',:ch) RETURNING id"
            ),
            {**params, "code": code, "t": Decimal(ratio), "ch": channel},
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO fems.alarm(workspace_id,generation_id,alarm_rule_id,raised_at,peak_value,status) "
                "VALUES (:w,:g,:r,'2026-09-24T02:00:00+00:00',:p,'OPEN')"
            ),
            {**params, "r": rule_id, "p": Decimal(peak)},
        )
    return f"{code}@2026-09-24T02:00"


def _clear_alarm(engine, created):
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE fems.alarm SET status='CLEARED', cleared_at=now() "
                "WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )


def _run_units(client, created, ids):
    """두 공조기를 모두 냉방으로 돌려 둔다. 감축 대상은 운전 중인 공조기뿐이다."""
    for zone, unit in (("Z-OFF", "AHU-OFF"), ("Z-PRD", "AHU-PRD")):
        _command(client, created, ids, zone, command="POWER_ON", hvacUnitId=ids[unit])
        _command(
            client,
            created,
            ids,
            zone,
            command="SET_MODE",
            mode="COOL",
            hvacUnitId=ids[unit],
        )


def test_peak_alarms_report_fems_state(bems):
    client, created, engine, _ = bems
    empty = _ok(client.get(f"{B}/peak-alarms"))
    assert empty == {"femsEnabled": True, "rows": []}
    ref = _peak_alarm(engine, created)
    row = _ok(client.get(f"{B}/peak-alarms"))["rows"][0]
    # 한계 = 0.9 × 계약전력 100kW = 90kW, 측정 피크 98kW → 8kW를 줄여야 한다.
    assert (row["alarmRef"], row["overKw"], row["planId"]) == (ref, "8.00", None)


def test_plan_is_proposed_by_priority_and_meets_the_target(bems):
    client, created, engine, ids = bems
    _run_units(client, created, ids)
    # 생산동 공조기를 먼저 감축한다.
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/hvac-units/{ids['AHU-PRD']}",
            {"curtailPriority": 1},
        )
    )
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/hvac-units/{ids['AHU-OFF']}",
            {"curtailPriority": 2},
        )
    )
    ref = _peak_alarm(engine, created, ratio="0.9", peak="98")
    plan = _ok(_call(client, created, "POST", PLANS, {"alarmRef": ref}), 201)
    assert plan["status"] == "PROPOSED" and plan["planNo"].startswith("PK-2026")
    assert plan["targetReductionKw"] == "8.00"
    assert next(s["hvacCode"] for s in plan["steps"]) == "AHU-PRD"
    assert sum(Decimal(s["expectedKw"]) for s in plan["steps"]) >= Decimal(8)
    assert all(s["commandId"] is None for s in plan["steps"])
    # 같은 경보로 두 번 만들 수 없다.
    again = _call(client, created, "POST", PLANS, {"alarmRef": ref})
    assert again.status_code == 409 and _reason(again) == "PLAN_EXISTS"
    assert _ok(client.get(f"{B}/peak-alarms"))["rows"][0]["planId"] == plan["id"]


def test_approval_issues_peak_commands_and_restore_waits_for_the_alarm(bems):
    client, created, engine, ids = bems
    _run_units(client, created, ids)
    ref = _peak_alarm(engine, created, ratio="0.9", peak="92")
    plan = _ok(_call(client, created, "POST", PLANS, {"alarmRef": ref}), 201)
    early = _call(client, created, "POST", f"{PLANS}/{plan['id']}/restore")
    assert early.status_code == 409 and _reason(early) == "WRONG_STATUS"

    approved = _ok(
        _call(
            client, created, "POST", f"{PLANS}/{plan['id']}/approve", {"note": "승인"}
        )
    )
    assert approved["status"] == "EXECUTED" and approved["decisionNote"] == "승인"
    assert all(s["commandId"] is not None for s in approved["steps"])
    commands = _ok(client.get(f"{B}/commands"))
    peak = [c for c in commands if c["source"] == "PEAK"]
    assert peak and all(c["demandPlanId"] == plan["id"] for c in peak)

    blocked = _call(client, created, "POST", f"{PLANS}/{plan['id']}/restore")
    assert blocked.status_code == 409 and _reason(blocked) == "ALARM_OPEN"
    assert _ok(client.get(f"{B}{PLANS}/{plan['id']}"))["alarmOpen"] is True

    _clear_alarm(engine, created)
    restored = _ok(client.get(f"{B}{PLANS}/{plan['id']}"))
    assert restored["alarmOpen"] is False
    done = _ok(_call(client, created, "POST", f"{PLANS}/{plan['id']}/restore"))
    assert done["status"] == "RESTORED" and done["restoredAt"]
    assert all(s["restoreCommandId"] is not None for s in done["steps"])
    # 운전 상태를 바꾼 단계의 공조기는 스케줄 운전으로 돌아간다.
    # 설정값만 올린 단계는 운전 상태를 건드리지 않았으므로 출처도 그대로다.
    for step in done["steps"]:
        unit = _ok(client.get(f"{B}/hvac-units/{step['hvacUnitId']}/detail"))
        if step["action"] == "RAISE_SETPOINT":
            assert unit["setpoints"]["COOL_TEMP"] == "26.00"
        else:
            assert unit["controlSource"] == "SCHEDULE"


def test_rejected_plan_frees_the_alarm(bems):
    client, created, engine, ids = bems
    _run_units(client, created, ids)
    ref = _peak_alarm(engine, created, ratio="0.9", peak="92")
    plan = _ok(_call(client, created, "POST", PLANS, {"alarmRef": ref}), 201)
    rejected = _ok(
        _call(
            client,
            created,
            "POST",
            f"{PLANS}/{plan['id']}/reject",
            {"note": "생산 중이라 보류"},
        )
    )
    assert rejected["status"] == "REJECTED" and rejected["decidedAt"]
    assert not [c for c in _ok(client.get(f"{B}/commands")) if c["source"] == "PEAK"]
    # 반려했으면 같은 경보로 다시 제안할 수 있다.
    again = _ok(_call(client, created, "POST", PLANS, {"alarmRef": ref}), 201)
    assert again["id"] != plan["id"]
    assert len(_ok(client.get(f"{B}{PLANS}"))) == 2


def test_plan_needs_a_running_unit_and_a_real_overage(bems):
    client, created, engine, _ = bems
    under = _peak_alarm(engine, created, ratio="0.9", peak="90", code="PEAK-LOW")
    nothing = _call(client, created, "POST", PLANS, {"alarmRef": under})
    assert nothing.status_code == 409 and _reason(nothing) == "NO_REDUCTION"
    ref = _peak_alarm(engine, created, ratio="0.9", peak="95", code="PEAK-2")
    # 공조기가 모두 정지 상태라 감축할 것이 없다.
    idle = _call(client, created, "POST", PLANS, {"alarmRef": ref})
    assert idle.status_code == 409 and _reason(idle) == "NO_CURTAILABLE_UNIT"
    unknown = _call(
        client, created, "POST", PLANS, {"alarmRef": "NOPE@2026-01-01T00:00"}
    )
    assert unknown.status_code == 400
