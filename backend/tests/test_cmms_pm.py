"""CMMS-1e: 예방보전 계획(C-04)·점검표·예비품(C-06).

FS-029 D49 · DSN-21 Q2·Q3·Q6 — 기준 3종(일 주기·운전 시간·금형 타수), 도래해도 사람이 만든다.
PM은 계획의 사용 항목을 모두 기록해야 닫히고, 범위 항목은 값으로 서버가 판정한다.
재고는 WMS에서 읽고 CMMS는 저장하지 않는다(D50).
"""

from datetime import date, timedelta
from itertools import count

import pytest
from sqlalchemy import text

C = "/api/v1/cmms"
_keys = count()
TODAY = date(2026, 9, 24)  # conftest의 FS_TODAY


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{C}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"e{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


@pytest.fixture
def cmms(guest_space):
    """빈 대장에 직접 등록 설비 하나와 MES에서 가져온 설비 하나."""
    client, created, engine = guest_space
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM cmms.asset WHERE workspace_id=:w AND generation_id=:g"),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )
    direct = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets",
            {"code": "PRESS-01", "name": "프레스 1호", "assetType": "OTHER"},
        ),
        201,
    )
    candidates = _ok(
        client.get(f"{C}/assets/import-candidates", params={"source": "MES"})
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            "/assets/import",
            {"source": "MES", "sourceCodes": [candidates[0]["sourceCode"]]},
        ),
        201,
    )
    imported = _ok(client.get(f"{C}/assets", params={"source": "MES"}))[0]
    return client, created, engine, direct, imported


def _plan(client, created, asset, **extra):
    body = {
        "assetId": asset["id"],
        "code": "PM-01",
        "title": "월간 점검",
        "startOn": TODAY.isoformat(),
        **extra,
    }
    return _call(client, created, "POST", "/pm-plans", body)


# ---------- 계획 기준 (C-04, Q2) ----------


def test_calendar_plan_due_date_counts_from_start_then_last_done(cmms):
    """다음 예정일 = (마지막 수행일 ?? 시작일) + 주기. 도래해도 사람이 만든다(D49)."""
    client, created, _, asset, _imported = cmms
    plan = _ok(_plan(client, created, asset, intervalDays=30), 201)
    row = next(r for r in _ok(client.get(f"{C}/pm-plans")) if r["id"] == plan["id"])
    assert row["dueOn"] == (TODAY + timedelta(days=30)).isoformat()
    assert row["isDue"] is False and row["unknown"] is False

    early = _call(client, created, "POST", f"/pm-plans/{plan['id']}/work-order", {})
    assert early.status_code == 409 and _reason(early) == "NOT_DUE"

    # 지난 시작일로 만든 계획은 이미 도래해 있다.
    past = _ok(
        _plan(
            client,
            created,
            asset,
            code="PM-02",
            startOn=(TODAY - timedelta(days=40)).isoformat(),
            intervalDays=30,
        ),
        201,
    )
    due = next(r for r in _ok(client.get(f"{C}/pm-plans")) if r["id"] == past["id"])
    assert due["dueOn"] == (TODAY - timedelta(days=10)).isoformat()
    assert due["isDue"] is True

    order = _ok(
        _call(client, created, "POST", f"/pm-plans/{past['id']}/work-order", {}), 201
    )
    assert order["kind"] == "PM" and order["source"] == "PM_PLAN"
    assert order["dueOn"] == due["dueOn"]

    # 같은 예정일로 두 번 만들 수 없다(UK_PARTIAL).
    again = _call(
        client, created, "POST", f"/pm-plans/{past['id']}/work-order", {}, key="pm-2"
    )
    assert again.status_code == 409 and _reason(again) == "ALREADY_CREATED"


def test_usage_plans_need_a_mes_asset_and_report_unknown_when_mes_is_off(cmms):
    """운전 시간·타수 기준은 MES에서 가져온 설비에만. MES를 끄면 '모름'이고 만들 수 없다."""
    client, created, _, direct, imported = cmms
    wrong = _plan(client, created, direct, triggerKind="RUN_HOURS", intervalUsage="100")
    assert wrong.status_code == 400
    assert "triggerKind" in wrong.json()["error"]["details"]["fields"]

    missing_interval = _plan(
        client, created, imported, code="PM-X", triggerKind="RUN_HOURS"
    )
    assert missing_interval.status_code == 400
    assert "intervalUsage" in missing_interval.json()["error"]["details"]["fields"]

    plan = _ok(
        _plan(
            client,
            created,
            imported,
            code="PM-RH",
            triggerKind="RUN_HOURS",
            intervalUsage="1",
        ),
        201,
    )
    row = next(r for r in _ok(client.get(f"{C}/pm-plans")) if r["id"] == plan["id"])
    assert row["unknown"] is False and row["usageNow"] is not None
    assert row["dueOn"] is None  # 사용량 기준에는 날짜 예정일이 없다

    _ok(
        _call(
            client,
            created,
            "PATCH",
            "/api/v1/core/workspace/modules/mes",
            {"enabled": False},
        )
    )
    off = next(r for r in _ok(client.get(f"{C}/pm-plans")) if r["id"] == plan["id"])
    assert off["unknown"] is True and off["isDue"] is False
    blocked = _call(client, created, "POST", f"/pm-plans/{plan['id']}/work-order", {})
    assert blocked.status_code == 409 and _reason(blocked) == "USAGE_UNKNOWN"


# ---------- 점검표 (Q3) ----------


def _due_plan(client, created, asset):
    """이미 도래한 일 주기 계획 — 시작일이 지났으니 바로 작업지시를 만들 수 있다."""
    return _ok(
        _plan(
            client,
            created,
            asset,
            startOn=(TODAY - timedelta(days=40)).isoformat(),
            intervalDays=30,
        ),
        201,
    )


def test_pm_cannot_close_until_every_active_item_is_recorded(cmms):
    """Q3: 사용 항목을 모두 기록해야 닫힌다. 범위 항목은 값으로 서버가 판정한다."""
    client, created, _, asset, _imported = cmms
    plan = _due_plan(client, created, asset)
    ok_ng = _ok(
        _call(
            client,
            created,
            "POST",
            f"/pm-plans/{plan['id']}/items",
            {"name": "누유 확인", "method": "OK_NG"},
        )
    )["items"][0]
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/pm-plans/{plan['id']}/items",
            {
                "name": "유압",
                "method": "RANGE",
                "lowerLimit": "80",
                "upperLimit": "120",
                "unit": "bar",
            },
        )
    )
    items = _ok(client.get(f"{C}/pm-plans/{plan['id']}"))["items"]
    assert [i["method"] for i in items] == ["OK_NG", "RANGE"]
    range_item = items[1]

    no_limits = _call(
        client,
        created,
        "POST",
        f"/pm-plans/{plan['id']}/items",
        {"name": "온도", "method": "RANGE", "unit": "℃"},
    )
    assert no_limits.status_code == 400

    order = _ok(
        _call(client, created, "POST", f"/pm-plans/{plan['id']}/work-order", {}), 201
    )
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))

    detail = _ok(client.get(f"{C}/work-orders/{order['id']}"))
    assert [c["name"] for c in detail["checks"]] == ["누유 확인", "유압"]
    assert all(c["result"] is None for c in detail["checks"])

    blocked = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/complete",
        {"causeCategory": "OTHER", "action": "점검 완료"},
    )
    assert blocked.status_code == 409 and _reason(blocked) == "CHECKLIST_INCOMPLETE"

    # 범위 밖 값은 NG로 판정되고 메모가 필요하다.
    no_note = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/checks",
        {
            "checks": [
                {"checklistItemId": range_item["id"], "measuredValue": "140"},
            ]
        },
    )
    assert no_note.status_code == 400

    saved = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/checks",
            {
                "checks": [
                    {"checklistItemId": ok_ng["id"], "result": "OK"},
                    {
                        "checklistItemId": range_item["id"],
                        "measuredValue": "140",
                        "note": "규정 상한을 넘었다",
                    },
                ]
            },
        )
    )
    assert saved["hasNg"] is True
    assert [c["result"] for c in saved["checks"]] == ["OK", "NG"]

    done = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {"causeCategory": "SETTING", "action": "압력 재조정"},
        )
    )
    assert done["status"] == "COMPLETED" and done["restoredAt"] is None

    # 완료로만 마지막 수행일이 바뀐다 — 다음 예정일이 여기서부터 다시 센다.
    after = next(r for r in _ok(client.get(f"{C}/pm-plans")) if r["id"] == plan["id"])
    assert after["lastDoneOn"] is not None


def test_range_inside_limits_is_ok_without_a_note(cmms):
    client, created, _, asset, _imported = cmms
    plan = _due_plan(client, created, asset)
    item = _ok(
        _call(
            client,
            created,
            "POST",
            f"/pm-plans/{plan['id']}/items",
            {
                "name": "유압",
                "method": "RANGE",
                "lowerLimit": "80",
                "upperLimit": "120",
                "unit": "bar",
            },
        )
    )["items"][0]
    order = _ok(
        _call(client, created, "POST", f"/pm-plans/{plan['id']}/work-order", {}), 201
    )
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    saved = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/checks",
            {"checks": [{"checklistItemId": item["id"], "measuredValue": "100"}]},
        )
    )
    assert saved["hasNg"] is False and saved["checks"][0]["result"] == "OK"


# ---------- 예비품 (C-06, Q6) ----------


def test_spare_part_stock_comes_from_wms_and_is_unknown_when_unlinked(cmms):
    """재고는 WMS에서 읽는다. 품목을 잇지 않았거나 WMS가 꺼졌으면 0이 아니라 '모름'이다."""
    client, created, _, _asset, _imported = cmms
    supplies = _ok(client.get(f"{C}/lookups/supply-items"))
    unlinked = _ok(
        _call(
            client,
            created,
            "POST",
            "/spare-parts",
            {"code": "SP-01", "name": "오링", "unit": "EA", "safetyStock": "5"},
        ),
        201,
    )
    rows = _ok(client.get(f"{C}/spare-parts"))
    row = next(r for r in rows if r["id"] == unlinked["id"])
    assert row["stockKnown"] is False and row["stock"] is None

    if supplies:
        linked = _ok(
            _call(
                client,
                created,
                "POST",
                "/spare-parts",
                {
                    "code": "SP-02",
                    "name": "소모품",
                    "unit": supplies[0]["baseUnit"],
                    "itemCode": supplies[0]["itemCode"],
                    "unitCost": "1200",
                },
            ),
            201,
        )
        rows = _ok(client.get(f"{C}/spare-parts"))
        found = next(r for r in rows if r["id"] == linked["id"])
        assert found["stockKnown"] is True
        assert set(found["stock"]) == {
            "qtyOnHand",
            "unit",
            "safetyStock",
            "isShort",
        }

        _ok(
            _call(
                client,
                created,
                "PATCH",
                "/api/v1/core/workspace/modules/wms",
                {"enabled": False},
            )
        )
        off = next(
            r for r in _ok(client.get(f"{C}/spare-parts")) if r["id"] == linked["id"]
        )
        assert off["stockKnown"] is False


def test_part_usage_snapshots_the_cost_and_does_not_move_stock(cmms):
    """부품 사용은 쓸 때의 단가를 스냅샷으로 남기고 재고를 움직이지 않는다(D50)."""
    client, created, engine, asset, _imported = cmms
    part = _ok(
        _call(
            client,
            created,
            "POST",
            "/spare-parts",
            {"code": "SP-01", "name": "오링", "unit": "EA", "unitCost": "1200"},
        ),
        201,
    )
    order = _ok(
        _call(
            client,
            created,
            "POST",
            "/work-orders",
            {"assetId": asset["id"], "title": "누유"},
        ),
        201,
    )
    early = _call(
        client,
        created,
        "POST",
        f"/work-orders/{order['id']}/parts",
        {"sparePartId": part["id"], "qty": "2"},
    )
    assert early.status_code == 409 and _reason(early) == "NOT_IN_PROGRESS"

    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    with engine.connect() as c:
        before = c.execute(
            text("SELECT count(*) FROM wms.stock_move WHERE workspace_id=:w"),
            {"w": created["workspaceId"]},
        ).scalar_one()
    used = _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/parts",
            {"sparePartId": part["id"], "qty": "2"},
        ),
        201,
    )
    assert used["parts"][0]["unitCost"] == "1200.0000"
    with engine.connect() as c:
        after = c.execute(
            text("SELECT count(*) FROM wms.stock_move WHERE workspace_id=:w"),
            {"w": created["workspaceId"]},
        ).scalar_one()
    assert before == after, "CMMS는 재고를 움직이지 않는다"

    # 단가를 바꿔도 이미 쓴 기록은 그대로다.
    _ok(
        _call(
            client, created, "PATCH", f"/spare-parts/{part['id']}", {"unitCost": "2000"}
        )
    )
    detail = _ok(client.get(f"{C}/work-orders/{order['id']}"))
    assert detail["parts"][0]["unitCost"] == "1200.0000"
