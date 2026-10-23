"""CMMS-1f: 보전 개요(C-01)·지표(C-07)·비용(C-10).

FS-029 D51 — MTTR = Σ(복구 − 정지) ÷ 고장 건수, MTBF = (기간 시간 − Σ정지) ÷ 고장 건수,
PM 준수율 = 예정일까지 완료한 비율(유예 0일). 모두 조회할 때 계산하고 저장하지 않는다.
보전 비용 = 부품 + 인건비 + 외주(DSN-21 Q5).
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from itertools import count
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import text

C = "/api/v1/cmms"
SEOUL = ZoneInfo("Asia/Seoul")
TODAY = date(2026, 9, 24)  # conftest의 FS_TODAY
_keys = count()


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{C}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"m{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


@pytest.fixture
def shop(guest_space):
    """설비 하나·정비원 하나·예비품 하나가 있는 빈 CMMS."""
    client, created, engine = guest_space
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM cmms.asset WHERE workspace_id=:w AND generation_id=:g"),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )
    asset = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets",
            {"code": "PRESS-01", "name": "프레스 1호", "assetType": "OTHER"},
        ),
        201,
    )
    tech = _ok(
        _call(
            client,
            created,
            "POST",
            "/technicians",
            {
                "code": "T-01",
                "name": "김보전",
                "skill": "MECHANICAL",
                "hourlyRate": "30000",
            },
        ),
        201,
    )
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
    return client, created, engine, asset, tech, part


def _finished_bm(client, created, engine, asset, failure_hours_ago, repair_hours):
    """완료된 고장 작업지시 하나. 시각은 지표를 재현하려고 DB에서 직접 맞춘다(합성 값)."""
    order = _ok(
        _call(
            client,
            created,
            "POST",
            "/work-orders",
            {"assetId": asset["id"], "title": "고장"},
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {"causeCategory": "WEAR", "action": "교체"},
        )
    )
    failure = datetime.combine(TODAY, datetime.min.time(), SEOUL) - timedelta(
        hours=failure_hours_ago
    )
    restored = failure + timedelta(hours=repair_hours)
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE cmms.work_order SET requested_at=:f, started_at=:f, "
                "failure_at=:f, restored_at=:r, completed_at=:r "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {
                "f": failure,
                "r": restored,
                "w": created["workspaceId"],
                "g": created["generationId"],
                "id": order["id"],
            },
        )
    return order


# ---------- 지표 (C-07, D51) ----------


def test_metrics_are_empty_without_failures(shop):
    """고장이 0건이면 MTTR·MTBF는 null이다 — 0이 아니라 '고장 없음'이다."""
    client, _created, _engine, _asset, _tech, _part = shop
    data = _ok(client.get(f"{C}/metrics"))
    assert data["failures"] == 0
    assert data["mttr"] is None and data["mtbf"] is None
    assert data["byAsset"] == [] and data["pareto"] == []
    assert data["pmTotal"] == 0 and data["pmRate"] is None


def test_mttr_and_mtbf_use_the_recorded_times(shop):
    """MTTR = 평균 복구 시간, MTBF = (기간 시간 − 정지 시간) ÷ 고장 건수."""
    client, created, engine, asset, _tech, _part = shop
    _finished_bm(client, created, engine, asset, failure_hours_ago=48, repair_hours=2)
    _finished_bm(client, created, engine, asset, failure_hours_ago=24, repair_hours=4)

    start = (TODAY - timedelta(days=6)).isoformat()
    data = _ok(
        client.get(f"{C}/metrics", params={"from": start, "to": TODAY.isoformat()})
    )
    assert data["failures"] == 2
    assert data["downtime"] == "6.0"
    assert data["mttr"] == "3.0"  # (2 + 4) ÷ 2
    period = Decimal(data["periodHours"])
    assert period == Decimal("168.0")  # 7일
    assert data["mtbf"] == str((period - Decimal("6.0")) / 2)

    [row] = data["byAsset"]
    assert row["assetCode"] == "PRESS-01" and row["failures"] == 2
    assert row["mttr"] == "3.0"
    # 파레토는 원인별로 센다.
    assert [(p["kind"], p["name"], p["count"]) for p in data["pareto"]] == [
        ("CAUSE", "WEAR", 2)
    ]


def test_downtime_counts_only_the_overlap_with_the_period(shop):
    """기간 밖까지 세면 두 달 보고서의 합이 전체와 맞지 않는다 — 겹친 부분만 센다."""
    client, created, engine, asset, _tech, _part = shop
    # 기간 시작 1시간 전에 멈춰 3시간 걸렸다 → 기간 안은 2시간.
    _finished_bm(client, created, engine, asset, failure_hours_ago=1, repair_hours=3)
    data = _ok(
        client.get(
            f"{C}/metrics",
            params={"from": TODAY.isoformat(), "to": TODAY.isoformat()},
        )
    )
    # 정지 시작이 기간 밖이라 고장 건수에 들지 않는다.
    assert data["failures"] == 0


def test_pm_compliance_counts_due_dates_in_the_period(shop):
    """예정일이 기간 안인 PM 중 예정일까지 완료한 비율. 유예는 없다."""
    client, created, engine, asset, _tech, _part = shop
    plan = _ok(
        _call(
            client,
            created,
            "POST",
            "/pm-plans",
            {
                "assetId": asset["id"],
                "code": "PM-01",
                "title": "월간 점검",
                "startOn": (TODAY - timedelta(days=40)).isoformat(),
                "intervalDays": 30,
            },
        ),
        201,
    )
    order = _ok(
        _call(client, created, "POST", f"/pm-plans/{plan['id']}/work-order", {}), 201
    )
    data = _ok(
        client.get(
            f"{C}/metrics",
            params={
                "from": (TODAY - timedelta(days=30)).isoformat(),
                "to": TODAY.isoformat(),
            },
        )
    )
    assert data["pmTotal"] == 1 and data["pmKept"] == 0  # 아직 완료 전
    assert data["pmRate"] == "0.0"

    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {"causeCategory": "OTHER", "action": "점검 완료"},
        )
    )
    # 예정일은 10일 전인데 오늘 닫았으니 늦었다 — 준수가 아니다.
    late = _ok(
        client.get(
            f"{C}/metrics",
            params={
                "from": (TODAY - timedelta(days=30)).isoformat(),
                "to": TODAY.isoformat(),
            },
        )
    )
    assert late["pmTotal"] == 1 and late["pmKept"] == 0

    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE cmms.work_order SET due_on=(completed_at AT TIME ZONE 'Asia/Seoul')::date "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {
                "w": created["workspaceId"],
                "g": created["generationId"],
                "id": order["id"],
            },
        )
    kept = _ok(
        client.get(
            f"{C}/metrics",
            params={
                "from": (TODAY - timedelta(days=30)).isoformat(),
                "to": (TODAY + timedelta(days=30)).isoformat(),
            },
        )
    )
    assert kept["pmKept"] == 1 and kept["pmRate"] == "100.0"


# ---------- 비용 (C-10, Q5) ----------


def test_cost_adds_parts_labor_and_external(shop):
    """보전 비용 = 부품(수량 × 사용 단가) + 인건비(분 ÷ 60 × 시간당) + 외주. 저장하지 않는다."""
    client, created, _engine, asset, tech, part = shop
    vendor = _ok(
        _call(
            client, created, "POST", "/vendors", {"code": "V-01", "name": "한빛정비"}
        ),
        201,
    )
    order = _ok(
        _call(
            client,
            created,
            "POST",
            "/work-orders",
            {"assetId": asset["id"], "title": "고장", "technicianId": tech["id"]},
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/logs",
            {"minutes": 120, "note": "분해 점검"},
        ),
        201,
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/parts",
            {"sparePartId": part["id"], "qty": "3"},
        ),
        201,
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/complete",
            {
                "causeCategory": "WEAR",
                "action": "교체",
                "vendorId": vendor["id"],
                "externalCost": "50000",
            },
        )
    )
    data = _ok(client.get(f"{C}/cost"))
    assert data["orderCount"] == 1
    assert data["partCost"] == "3600"  # 3 × 1,200
    assert data["laborCost"] == "60000"  # 120분 ÷ 60 × 30,000
    assert data["externalCost"] == "50000"
    assert data["totalCost"] == "113600"
    [by_asset] = data["byAsset"]
    assert by_asset["group"] == "PRESS-01" and by_asset["totalCost"] == "113600"
    assert by_asset["bmCount"] == 1 and by_asset["pmCount"] == 0
    assert len(data["byMonth"]) == 1

    # 단가를 바꿔도 지난 비용은 그대로다 — 쓸 때의 단가를 스냅샷으로 남겼다.
    _ok(
        _call(
            client, created, "PATCH", f"/spare-parts/{part['id']}", {"unitCost": "5000"}
        )
    )
    assert _ok(client.get(f"{C}/cost"))["partCost"] == "3600"


def test_cost_ignores_unfinished_orders(shop):
    """완료한 작업지시만 센다 — 진행 중인 것은 아직 얼마가 들지 모른다."""
    client, created, _engine, asset, tech, part = shop
    order = _ok(
        _call(
            client,
            created,
            "POST",
            "/work-orders",
            {"assetId": asset["id"], "title": "고장", "technicianId": tech["id"]},
        ),
        201,
    )
    _ok(_call(client, created, "POST", f"/work-orders/{order['id']}/start", {}))
    _ok(
        _call(
            client,
            created,
            "POST",
            f"/work-orders/{order['id']}/parts",
            {"sparePartId": part["id"], "qty": "2"},
        ),
        201,
    )
    data = _ok(client.get(f"{C}/cost"))
    assert data["orderCount"] == 0 and data["totalCost"] == "0"


# ---------- 개요 (C-01) ----------


def test_overview_shows_what_to_do_now(shop):
    """지금 해야 할 것 — 미조치 작업지시·전환 대기·도래 PM·부족 예비품."""
    client, created, _engine, asset, _tech, _part = shop
    plan = _ok(
        _call(
            client,
            created,
            "POST",
            "/pm-plans",
            {
                "assetId": asset["id"],
                "code": "PM-01",
                "title": "월간 점검",
                "startOn": (TODAY - timedelta(days=40)).isoformat(),
                "intervalDays": 30,
            },
        ),
        201,
    )
    _ok(
        _call(
            client,
            created,
            "POST",
            "/work-orders",
            {"assetId": asset["id"], "title": "이상 소음"},
        ),
        201,
    )
    data = _ok(client.get(f"{C}/overview"))
    assert data["assetCount"] == 1 and data["requested"] == 1
    assert data["openBm"] == 1 and data["inProgress"] == 0
    assert [p["code"] for p in data["duePlans"]] == [plan["code"]]
    assert data["sources"] == {"bems": True, "spc": True}
    assert isinstance(data["pendingSignals"], int)
    assert data["unknownPlans"] == 0
    assert data["shortParts"] == []  # WMS 품목을 잇지 않아 '모름'이다
