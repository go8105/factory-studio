"""FEMS-1e: 에너지 경보(F31)와 설비 비교(F27) — DSN-15.

경보는 **상시 감시 서버가 아니다.** 규칙을 지금 한 번 보고 걸리면 올린다. 규칙당 진행 경보는
하나이고(UK_PARTIAL) 발생 → 확인 → 해제로만 간다. PEAK 경보는 BEMS가 읽는다(CMMS 신호 아님).
"""

from decimal import Decimal
from itertools import count

import pytest
from fs.common.auth import AuthContext
from fs.fems import interface as fems
from sqlalchemy import text

F = "/api/v1/fems"
_keys = count()


@pytest.fixture
def space(guest_space):
    return guest_space


def _headers(created):
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": f"al{next(_keys)}",
    }


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _channel(client) -> dict:
    meters = client.get(f"{F}/meters").json()["data"]
    meter = next(m for m in meters if m["channels"])
    return {**meter["channels"][0], "meterCode": meter["meterCode"]}


def _rule(client, created, **extra) -> dict:
    body = {
        "code": f"AL-{next(_keys)}",
        "name": "시간 사용량 임계",
        "alarmKind": "THRESHOLD",
        "meterChannelId": _channel(client)["id"],
        "threshold": "0.001",
        "unit": "kWh",
        **extra,
    }
    return _ok(
        client.post(f"{F}/alarm-rules", json=body, headers=_headers(created)), 201
    )


def _context(created) -> AuthContext:
    return AuthContext(
        actor_kind="GUEST",
        actor_key="test",
        workspace_id=created["workspaceId"],
        generation_id=created["generationId"],
        user_id=None,
        roles=("GUEST",),
        token=None,
    )


def test_rule_needs_a_channel_or_an_equipment(space):
    """무엇을 보는지 정해지지 않은 규칙은 만들 수 없다."""
    client, created, _ = space
    response = client.post(
        f"{F}/alarm-rules",
        json={
            "code": "AL-NOTARGET",
            "name": "대상 없음",
            "alarmKind": "THRESHOLD",
            "threshold": "1",
            "unit": "kWh",
        },
        headers=_headers(created),
    )
    assert response.status_code == 400
    assert "meterChannelId" in response.json()["error"]["details"]["fields"]


def test_rule_code_is_unique(space):
    client, created, _ = space
    rule = _rule(client, created)
    again = client.post(
        f"{F}/alarm-rules",
        json={
            "code": rule["code"],
            "name": "중복",
            "alarmKind": "THRESHOLD",
            "meterChannelId": _channel(client)["id"],
            "threshold": "1",
            "unit": "kWh",
        },
        headers=_headers(created),
    )
    assert again.status_code == 409


def test_evaluation_raises_once_per_rule(space):
    """같은 일로 경보가 쌓이면 아무도 보지 않게 된다. 규칙당 하나만 연다."""
    client, created, _ = space
    rule = _rule(client, created)
    first = _ok(
        client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201
    )
    assert rule["code"] in first["raised"]

    second = _ok(
        client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201
    )
    assert rule["code"] not in second["raised"]
    assert any("이미 진행 중인" in s for s in second["skipped"])
    assert len(_ok(client.get(f"{F}/alarms?openOnly=true"))) == 1


def test_alarm_goes_forward_only(space):
    """발생 → 확인 → 해제. 뒤로 가지 않는다."""
    client, created, _ = space
    _rule(client, created)
    _ok(client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201)
    alarm = _ok(client.get(f"{F}/alarms?openOnly=true"))[0]
    assert alarm["status"] == "OPEN"

    acked = _ok(
        client.post(f"{F}/alarms/{alarm['id']}/acknowledge", headers=_headers(created))
    )
    assert acked["status"] == "ACK" and acked["acknowledgedAt"]

    again = client.post(
        f"{F}/alarms/{alarm['id']}/acknowledge", headers=_headers(created)
    )
    assert again.status_code == 409

    cleared = _ok(
        client.post(f"{F}/alarms/{alarm['id']}/clear", headers=_headers(created))
    )
    assert cleared["status"] == "CLEARED" and cleared["clearedAt"]
    assert _ok(client.get(f"{F}/alarms?openOnly=true")) == []


def test_cleared_rule_can_raise_again(space):
    """해제한 뒤 같은 규칙이 다시 걸리면 새 경보가 올라온다."""
    client, created, _ = space
    rule = _rule(client, created)
    _ok(client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201)
    alarm = _ok(client.get(f"{F}/alarms?openOnly=true"))[0]
    _ok(client.post(f"{F}/alarms/{alarm['id']}/clear", headers=_headers(created)))
    again = _ok(
        client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201
    )
    assert rule["code"] in again["raised"]


def test_peak_rule_without_contract_power_stays_quiet(space):
    """계약전력이 없으면 비율을 낼 수 없다. 0으로 보고 올리지 않는다."""
    client, created, _ = space
    rule = _rule(client, created, alarmKind="PEAK", threshold="0.0001", unit="비율")
    result = _ok(
        client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201
    )
    assert rule["code"] not in result["raised"]


def test_inactive_rule_is_not_evaluated(space):
    client, created, _ = space
    rule = _rule(client, created, isActive=False)
    result = _ok(
        client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201
    )
    assert rule["code"] not in result["raised"]


def test_open_alarms_is_what_bems_reads(space):
    """DSN-15 6장. BEMS 피크 감축이 읽는 계약이다."""
    client, created, engine = space
    _rule(client, created)
    _ok(client.post(f"{F}/alarms/evaluate", json={}, headers=_headers(created)), 201)
    context = _context(created)
    with engine.begin() as c:
        rows = fems.open_alarms(c, context)
        assert rows and rows[0]["status"] == "OPEN"
        assert rows[0]["alarmKind"] == "THRESHOLD"
        assert Decimal(rows[0]["peakValue"]) > 0

        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='fems'"
            ),
            {"w": created["workspaceId"]},
        )
        assert fems.open_alarms(c, context) is None


def test_comparison_ranks_within_a_type_only(space):
    """사출기와 검사기의 원단위를 나란히 두면 뜻이 없다. 종류 안에서만 줄 세운다."""
    client, _, _ = space
    data = _ok(client.get(f"{F}/equipment-comparison"))
    assert data["groups"], "시드 배분이 있어야 한다"
    for group in data["groups"]:
        ranks = [r["rank"] for r in group["ranked"]]
        assert ranks == sorted(ranks) == list(range(1, len(ranks) + 1))
        values = [Decimal(r["intensity"]) for r in group["ranked"]]
        assert values == sorted(values)
        # 에너지원이 다르면 단위가 다르다 — 한 순위표 안의 단위는 하나여야 한다.
        assert {r["energyUnit"] for r in group["ranked"] + group["unranked"]} == {
            group["energyUnit"]
        }
        # 생산량이 없어 못 센 설비는 0위가 아니라 순위 밖이다.
        assert all(r["intensity"] is None for r in group["unranked"])
