"""FEMS-1d: 수동 검침(F12)과 결측·이상값 보정(F14) — DSN-15 Q3.

보정은 **원 계측을 지우지 않는다.** 고친 값은 같은 구간의 새 input_revision(estimated)으로
들어가고 원 계측은 집계에서만 빠진다(invalid). 원래 값은 행에도, 보정 이력에도 남는다.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from itertools import count

import pytest
from sqlalchemy import text

F = "/api/v1/fems"
_keys = count()
KST = timezone(timedelta(hours=9))


@pytest.fixture
def fems(guest_space):
    return guest_space


def _headers(created):
    return {
        "X-CSRF-Token": created["csrfToken"],
        "Idempotency-Key": f"q{next(_keys)}",
    }


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _a_channel(engine, created) -> tuple[int, datetime, datetime]:
    """계측이 가장 많은 채널과 그 첫·마지막 구간."""
    with engine.begin() as c:
        row = c.execute(
            text(
                "SELECT meter_channel_id, min(period_start) lo, max(period_start) hi "
                "FROM fems.energy_reading WHERE workspace_id=:w AND generation_id=:g "
                "GROUP BY meter_channel_id ORDER BY count(*) DESC LIMIT 1"
            ),
            {"w": created["workspaceId"], "g": created["generationId"]},
        ).one()
    return row[0], row[1], row[2]


def _quality(client, channel_id, date_from=None, date_to=None):
    query = f"channelId={channel_id}"
    if date_from:
        query += f"&from={date_from}&to={date_to}"
    return _ok(client.get(f"{F}/reading-quality?{query}"))


def test_manual_reading_lands_as_an_entry_method(fems):
    """계측기 없는 연료·용수는 손으로 적는다. 입력 방법이 METER가 아니어야 구분된다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    slot = (last + timedelta(hours=1)).astimezone(KST).isoformat()
    row = _ok(
        client.post(
            f"{F}/readings",
            json={"channelId": channel_id, "periodStart": slot, "value": "12.5"},
            headers=_headers(created),
        ),
        201,
    )
    assert row["entryMethod"] == "MANUAL"
    assert row["quality"] == "valid" and row["inputRevision"] == 1
    assert "MANUAL-" in row["sourceKey"]


def test_manual_reading_does_not_overwrite(fems):
    """이미 값이 있는 구간은 덮지 않는다 — 고치는 것은 보정이고 이력이 남아야 한다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    body = {
        "channelId": channel_id,
        "periodStart": last.astimezone(KST).isoformat(),
        "value": "9",
    }
    response = client.post(f"{F}/readings", json=body, headers=_headers(created))
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "READING_EXISTS"


def test_unknown_channel_is_not_found(fems):
    client, created, _ = fems
    response = client.post(
        f"{F}/readings",
        json={
            "channelId": 999_999,
            "periodStart": "2026-09-01T00:00:00+09:00",
            "value": "1",
        },
        headers=_headers(created),
    )
    assert response.status_code == 404


def test_correction_keeps_the_original_and_supersedes_it(fems):
    """핵심 규칙. 원 계측은 남고 집계에서만 빠진다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    scope = {"w": created["workspaceId"], "g": created["generationId"]}
    with engine.begin() as c:
        before = c.execute(
            text(
                "SELECT id,value,quality,input_revision FROM fems.energy_reading "
                "WHERE workspace_id=:w AND generation_id=:g AND meter_channel_id=:ch "
                " AND period_start=:p"
            ),
            {**scope, "ch": channel_id, "p": last},
        ).one()

    saved = _ok(
        client.post(
            f"{F}/reading-corrections",
            json={
                "channelId": channel_id,
                "periodStart": last.astimezone(KST).isoformat(),
                "correctedValue": "77.5",
                "method": "PREVIOUS",
                "reason": "통신 끊김으로 0이 찍혔다",
            },
            headers=_headers(created),
        ),
        201,
    )
    assert Decimal(saved["originalValue"]) == before[1]
    assert Decimal(saved["correctedValue"]) == Decimal("77.5")
    assert saved["inputRevision"] == before[3] + 1

    with engine.begin() as c:
        rows = c.execute(
            text(
                "SELECT value,quality,input_revision FROM fems.energy_reading "
                "WHERE workspace_id=:w AND generation_id=:g AND meter_channel_id=:ch "
                " AND period_start=:p ORDER BY input_revision"
            ),
            {**scope, "ch": channel_id, "p": last},
        ).all()
    assert len(rows) == 2, "원 계측이 지워지지 않는다"
    assert rows[0][0] == before[1] and rows[0][1] == "invalid"
    assert rows[1][0] == Decimal("77.5") and rows[1][1] == "estimated"


def test_correction_fills_a_missing_slot(fems):
    """결측은 원래 값이 없다. original은 0이 아니라 null이다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    slot = last + timedelta(hours=2)
    saved = _ok(
        client.post(
            f"{F}/reading-corrections",
            json={
                "channelId": channel_id,
                "periodStart": slot.astimezone(KST).isoformat(),
                "correctedValue": "5",
                "method": "INTERPOLATE",
                "reason": "앞뒤 값으로 보간",
            },
            headers=_headers(created),
        ),
        201,
    )
    assert saved["originalValue"] is None and saved["inputRevision"] == 1


def test_reason_is_required(fems):
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    response = client.post(
        f"{F}/reading-corrections",
        json={
            "channelId": channel_id,
            "periodStart": last.astimezone(KST).isoformat(),
            "correctedValue": "5",
            "method": "MANUAL",
            "reason": "",
        },
        headers=_headers(created),
    )
    assert response.status_code == 400


def test_quality_screen_lists_issues_and_corrections(fems):
    client, created, engine = fems
    channel_id, _, _ = _a_channel(engine, created)
    data = _quality(client, channel_id)
    assert data["channel"]["id"] == channel_id
    assert data["readingCount"] > 0
    assert all(i["kind"] in ("MISSING", "ZERO_RUN", "SPIKE") for i in data["issues"])
    # 판단 근거를 함께 준다 — 숫자만 주면 못 고친다.
    assert all(i["note"] for i in data["issues"])
    assert data["corrections"] == []


def test_a_spike_is_found(fems):
    """중앙값의 3배를 넘는 값은 급증으로 잡는다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    _ok(
        client.post(
            f"{F}/readings",
            json={
                "channelId": channel_id,
                "periodStart": (last + timedelta(hours=1)).astimezone(KST).isoformat(),
                "value": "99999",
            },
            headers=_headers(created),
        ),
        201,
    )
    data = _quality(client, channel_id)
    assert any(i["kind"] == "SPIKE" for i in data["issues"])
