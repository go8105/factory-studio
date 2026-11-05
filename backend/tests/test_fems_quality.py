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


def test_dashboard_counts_a_corrected_slot_once(fems):
    """보정하면 원본(invalid)과 보정본(estimated)이 같은 구간에 둘 남는다 — 이상 건수는 하나만 센다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    month = last.astimezone(KST).strftime("%Y-%m")
    before = _ok(client.get(f"{F}/dashboard?month={month}"))["quality"]["issues"]
    _ok(
        client.post(
            f"{F}/reading-corrections",
            json={
                "channelId": channel_id,
                "periodStart": last.astimezone(KST).isoformat(),
                "correctedValue": "77.5",
                "method": "PREVIOUS",
                "reason": "통신 끊김",
            },
            headers=_headers(created),
        ),
        201,
    )
    after = _ok(client.get(f"{F}/dashboard?month={month}"))["quality"]["issues"]
    # 이 구간이 valid였다면 +1(보정본), 이미 이상이었다면 +0. 원본까지 세면 +2가 된다.
    assert after - before <= 1


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


# ---------- CSV 올리기 (F13) ----------


def _channel_code(engine, created, channel_id: int) -> str:
    with engine.begin() as c:
        return c.execute(
            text(
                "SELECT channel_code FROM fems.meter_channel "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "id": channel_id,
            },
        ).scalar_one()


def test_upload_takes_the_good_rows_and_names_the_bad_ones(fems):
    """한 행이 틀렸다고 나머지를 버리지 않는다. 사유를 행 번호와 함께 돌려준다."""
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    code = _channel_code(engine, created, channel_id)
    rows = [
        {
            "channelCode": code,
            "periodStart": (last + timedelta(hours=3)).astimezone(KST).isoformat(),
            "value": "11",
        },
        {
            "channelCode": "NO-SUCH-CH",
            "periodStart": (last + timedelta(hours=4)).astimezone(KST).isoformat(),
            "value": "12",
        },
        {
            # 이미 값이 있는 구간 — 올리기로 덮지 않는다.
            "channelCode": code,
            "periodStart": last.astimezone(KST).isoformat(),
            "value": "13",
        },
    ]
    saved = _ok(
        client.post(
            f"{F}/reading-uploads",
            json={"fileName": "2026-09.csv", "rows": rows},
            headers=_headers(created),
        ),
        201,
    )
    assert saved["rowCount"] == 3
    assert saved["acceptedCount"] == 1 and saved["rejectedCount"] == 2
    assert saved["uploadNo"].startswith("UP-")
    assert any("NO-SUCH-CH" in r for r in saved["rejected"])
    assert any("이미 계측값이 있는" in r for r in saved["rejected"])


def test_uploaded_rows_are_marked_as_file_entry(fems):
    client, created, engine = fems
    channel_id, _, last = _a_channel(engine, created)
    code = _channel_code(engine, created, channel_id)
    slot = last + timedelta(hours=5)
    _ok(
        client.post(
            f"{F}/reading-uploads",
            json={
                "fileName": "a.csv",
                "rows": [
                    {
                        "channelCode": code,
                        "periodStart": slot.astimezone(KST).isoformat(),
                        "value": "7",
                    }
                ],
            },
            headers=_headers(created),
        ),
        201,
    )
    with engine.begin() as c:
        method = c.execute(
            text(
                "SELECT entry_method FROM fems.energy_reading "
                "WHERE workspace_id=:w AND generation_id=:g AND meter_channel_id=:ch "
                " AND period_start=:p"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "ch": channel_id,
                "p": slot,
            },
        ).scalar_one()
    assert method == "FILE"


# ---------- MES 생산량 가져오기 (F51) ----------


def _busy_month(engine, created) -> str:
    with engine.begin() as c:
        return c.execute(
            text(
                "SELECT to_char(confirmed_at AT TIME ZONE 'Asia/Seoul','YYYY-MM') m "
                "FROM mes.operation_result WHERE workspace_id=:w AND generation_id=:g "
                "GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
            ),
            {"w": created["workspaceId"], "g": created["generationId"]},
        ).scalar_one()


def test_import_brings_mes_results_in_as_drafts(fems):
    """1b production_results의 첫 소비자. 가져온 행은 초안이고 확정은 사람이 한다."""
    client, created, engine = fems
    month = _busy_month(engine, created)
    saved = _ok(
        client.post(
            f"{F}/production-records/import",
            json={"month": month},
            headers=_headers(created),
        ),
        201,
    )
    assert saved["month"] == month
    assert saved["imported"] > 0, "시드 실적이 있어야 한다"
    with engine.begin() as c:
        rows = c.execute(
            text(
                "SELECT status,source_key FROM fems.production_record "
                "WHERE workspace_id=:w AND generation_id=:g AND source_key LIKE :p"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "p": f"MES:{month}:%",
            },
        ).all()
    assert len(rows) == saved["imported"]
    assert all(r[0] == "draft" for r in rows)


def test_import_twice_does_not_duplicate(fems):
    """덮어쓰면 확정한 값이 조용히 바뀐다. 이미 가져온 것은 건너뛴다."""
    client, created, engine = fems
    month = _busy_month(engine, created)
    first = _ok(
        client.post(
            f"{F}/production-records/import",
            json={"month": month},
            headers=_headers(created),
        ),
        201,
    )
    second = _ok(
        client.post(
            f"{F}/production-records/import",
            json={"month": month},
            headers=_headers(created),
        ),
        201,
    )
    assert second["imported"] == 0
    assert len(second["skipped"]) >= first["imported"]
    assert all("이미 가져왔습니다" in s for s in second["skipped"][: first["imported"]])


def test_import_says_so_when_mes_is_off(fems):
    client, created, engine = fems
    month = _busy_month(engine, created)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='mes'"
            ),
            {"w": created["workspaceId"]},
        )
    response = client.post(
        f"{F}/production-records/import",
        json={"month": month},
        headers=_headers(created),
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"]["reason"] == "SOURCE_MODULE_DISABLED"
