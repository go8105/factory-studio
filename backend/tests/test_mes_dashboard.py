"""FS-020g MES 대시보드(M-01). 대시보드 숫자를 다른 화면 API로 따로 계산한 값과 맞춘다."""

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

BASE = "/api/v1/mes"
KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def mes(guest_space):
    return guest_space[:2]


def _rows(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _dash(client, **params) -> dict:
    return client.get(f"{BASE}/dashboard", params=params).json()["data"]


def _in_month(value: str, month: str) -> bool:
    return datetime.fromisoformat(value).astimezone(KST).strftime("%Y-%m") == month


def test_default_month_is_business_month(mes):
    client, _ = mes
    assert _dash(client)["month"] == "2026-09"


def test_cards_match_other_screens(mes):
    client, _ = mes
    data = _dash(client)
    orders = _rows(client, "/work-orders")
    assert data["openOrders"] == sum(
        o["status"] in ("released", "in_progress") for o in orders
    )
    results = [
        r for r in _rows(client, "/results") if _in_month(r["confirmedAt"], "2026-09")
    ]
    good = sum(Decimal(r["goodQty"]) for r in results)
    output = sum(Decimal(r["inputQty"]) for r in results)
    assert Decimal(data["goodRate"]) == (good / output * 100).quantize(Decimal("0.1"))
    assert Decimal(data["goodRate"]) < 100  # 전량 불량 LOT이 있다
    # 당월 생산은 마지막 공정(검사, 3번째) 양품만 센다
    assert Decimal(data["producedQty"]) == sum(
        Decimal(r["goodQty"]) for r in results if r["sequenceNo"] == 3
    )
    receipts = _rows(client, "/finished-goods-receipts")
    assert data["receivedPallets"] == sum(
        _in_month(r["receivedAt"], "2026-09") for r in receipts
    )


def test_pipeline_and_pending_match_lots(mes):
    client, _ = mes
    data = _dash(client)
    lots = [x for x in _rows(client, "/lots") if x["status"] != "completed"]
    assert sum(p["running"] for p in data["pipeline"]) == sum(
        1 for x in lots if x["running"]
    )
    assert sum(p["waiting"] for p in data["pipeline"]) == sum(
        1 for x in lots if not x["running"] and x["nextStep"]
    )
    assert data["pending"]["unconfirmedResults"] == len(_rows(client, "/executions"))
    assert data["pending"]["unpackedLots"] == len(_rows(client, "/packable-lots"))


def test_defect_reasons_are_top_five_by_quantity(mes):
    client, _ = mes
    reasons = _dash(client)["defectReasons"]
    assert 0 < len(reasons) <= 5
    quantities = [Decimal(r["defectQty"]) for r in reasons]
    assert quantities == sorted(quantities, reverse=True)


def test_plan_vs_actual_uses_month_plan(mes):
    client, _ = mes
    rows = {r["itemId"]: r for r in _dash(client)["planVsActual"]}
    c100 = next(i["id"] for i in _rows(client, "/items") if i["itemCode"] == "FG-C100")
    lines = [
        line
        for plan in _rows(client, "/production-plans")
        if plan["targetMonth"] == "2026-09"
        for line in plan["lines"]
        if line["itemId"] == c100
    ]
    assert Decimal(rows[c100]["planQty"]) == sum(Decimal(x["planQty"]) for x in lines)
    assert Decimal(rows[c100]["allocatedQty"]) == sum(
        Decimal(x["allocatedQty"]) for x in lines
    )


def test_month_without_activity(mes):
    client, _ = mes
    data = _dash(client, month="2025-01")
    assert (data["producedQty"], data["goodRate"], data["receivedPallets"]) == (
        "0",
        None,
        0,
    )
    assert data["planVsActual"] == []


def test_month_format_is_validated(mes):
    client, _ = mes
    response = client.get(f"{BASE}/dashboard", params={"month": "2026-13"})
    assert response.status_code == 400
    assert "month" in response.json()["error"]["details"]["fields"]


def test_pipeline_follows_route_order(mes):
    client, _ = mes
    codes = {p["id"]: p["processCode"] for p in _rows(client, "/processes")}
    order = [codes[p["processId"]] for p in _dash(client)["pipeline"]]
    assert order == ["INJ", "ASM", "INS"]


def test_previous_month_block_matches_that_month(mes):
    """전월 블록은 그 달을 직접 조회한 값과 같아야 한다."""
    client, _ = mes
    this = _dash(client, month="2026-09")
    previous = _dash(client, month="2026-08")
    assert this["previous"]["month"] == "2026-08"
    if this["previous"]["samePeriod"]:
        # 진행 중인 달이면 전월도 같은 날까지만 세므로 전체 조회와 다를 수 있다.
        pytest.skip("조회 월이 진행 중이라 같은 기간 비교다")
    for key in ("producedQty", "goodRate", "receivedPallets"):
        assert this["previous"][key] == previous[key], key


def test_previous_month_crosses_the_year(mes):
    """1월의 전월은 지난해 12월이다."""
    client, _ = mes
    assert _dash(client, month="2026-01")["previous"]["month"] == "2025-12"


def test_running_month_compares_the_same_period(mes):
    """진행 중인 달은 전월도 같은 날까지만 센다 — 전월 전체보다 크지 않아야 한다."""
    client, _ = mes
    running = _dash(client)
    previous = running["previous"]
    whole = _dash(client, month=previous["month"])
    if not previous["samePeriod"]:
        pytest.skip("업무 기준일이 시드 범위 밖이라 진행 중인 달이 아니다")
    assert previous["receivedPallets"] <= whole["receivedPallets"]
    assert Decimal(previous["producedQty"]) <= Decimal(whole["producedQty"])
