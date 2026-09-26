"""FS-019h E-01 ERP 대시보드. 숫자를 다른 화면 API로 따로 계산한 값과 맞춘다."""

from decimal import Decimal

import pytest

BASE = "/api/v1/erp"


@pytest.fixture
def erp(guest_space):
    return guest_space[:2]


def _data(client, path: str):
    return client.get(f"{BASE}{path}").json()["data"]


def _sum(rows, key) -> Decimal:
    return sum((Decimal(r[key]) for r in rows), Decimal(0))


def test_balances_match_receivable_and_payable_screens(erp):
    client, _ = erp
    board = _data(client, "/dashboard")
    assert Decimal(board["receivableBalance"]) == _sum(
        _data(client, "/receivables"), "balance"
    )
    assert Decimal(board["payableBalance"]) == _sum(
        _data(client, "/payables"), "balance"
    )


def test_month_sales_match_sales_screen(erp):
    client, _ = erp
    sales = [s for s in _data(client, "/sales-records") if not s["cancelledAt"]]
    month = sales[0]["recognizedAt"][
        :7
    ]  # 가장 최근 매출의 달(UTC 기준 문자열이지만 시드는 KST 10시)
    board = _data(client, f"/dashboard?month={month}")
    same = [s for s in sales if s["recognizedAt"][:7] == month]
    assert Decimal(board["salesSupply"]) == _sum(same, "supplyAmount")
    assert board["salesCount"] == len(same)
    assert board["monthlySales"][-1] == {
        "month": month,
        "supplyAmount": board["salesSupply"],
    }
    assert len(board["monthlySales"]) == 6


def test_order_backlog_matches_order_screen(erp):
    client, _ = erp
    expected = sum(
        (Decimal(x["orderQty"]) - Decimal(x["shippedQty"])) * Decimal(x["unitPrice"])
        for o in _data(client, "/sales-orders")
        if o["status"] != "cancelled"
        for x in o["lines"]
    )
    assert Decimal(_data(client, "/dashboard")["orderBacklog"]) == expected.quantize(
        Decimal(1)
    )


def test_due_groups_keep_unset_separate(erp):
    client, _ = erp
    board = _data(client, "/dashboard")
    groups = {k: Decimal(v) for k, v in board["receivableByDue"].items()}
    assert sum(groups.values()) == Decimal(board["receivableBalance"])
    unset = _sum(
        [r for r in _data(client, "/receivables") if r["dueDate"] is None], "balance"
    )
    assert groups["unset"] == unset > 0  # 시드 SH-0002는 만기 없음


def test_top_receivables_sorted_by_balance(erp):
    client, _ = erp
    top = _data(client, "/dashboard")["topReceivables"]
    balances = [Decimal(t["balance"]) for t in top]
    assert balances == sorted(balances, reverse=True) and len(top) <= 5


def test_plan_vs_actual_uses_confirmed_plan(erp):
    client, _ = erp
    plan = next(p for p in _data(client, "/sales-plans") if p["status"] == "confirmed")
    board = _data(client, f"/dashboard?month={plan['targetMonth']}")
    assert _sum(board["planVsActual"], "planQty") == _sum(plan["lines"], "planQty")


def test_pending_counts(erp):
    client, _ = erp
    pending = _data(client, "/dashboard")["pending"]
    sales = [
        s
        for s in _data(client, "/sales-records")
        if not s["cancelledAt"]
        and Decimal(s["totalAmount"]) > 0
        and s["taxInvoiceStatus"] != "issued"
    ]
    receipts = [
        r
        for r in _data(client, "/receipts")
        if r["status"] == "confirmed" and Decimal(r["unappliedAmount"]) > 0
    ]
    assert pending == {
        "uninvoicedSales": len(sales),
        "unappliedReceipts": len(receipts),
    }


def test_bad_month_rejected(erp):
    client, _ = erp
    response = client.get(f"{BASE}/dashboard?month=2026-13")
    assert response.status_code == 400
