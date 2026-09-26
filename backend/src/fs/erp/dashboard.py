"""E-01 ERP 대시보드 (FS-019h). 조회 때 계산하고 저장하지 않는다. 앞 화면의 계산을 다시 구현하지 않는다.

- 미수금·미지급 = receipts.open_items(RECEIVABLE/PAYABLE)의 잔액 합(E-09·E-12와 같은 함수).
- 당월 매출 = 그 달(Asia/Seoul) 인식된 유효 매출의 공급가액·합계(E-07과 같은 행).
- 수주잔 = 취소 안 된 수주 명세의 (수주 − 출하) × 단가(E-04 진행률과 같은 SQL).
- 판매계획 대비 실적 = 그 달 확정 판매계획 수량 vs 그 달 유효 매출의 출하 수량(품목별).
- 만기별 미수: 연체 / 미도래 / 미설정(만기 NULL, 연체로 보지 않음 — E-G02).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.clock import business_today
from fs.common.scope import read_scope
from fs.erp.receipts import PAYABLE, RECEIVABLE, _monies, open_items
from fs.erp.sales import MODULE, _orders, _s
from fs.erp.service import _read, invalid

VALID_SALES = """
FROM erp.sales_record r
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.cancelled_at IS NULL"""
MONTH = "to_char(r.recognized_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM')"
PLAN_SQL = """
SELECT l.item_id, i.item_code, i.name, sum(l.plan_qty) plan_qty
FROM erp.sales_plan p
JOIN erp.sales_plan_line l ON l.workspace_id=p.workspace_id
 AND l.generation_id=p.generation_id AND l.sales_plan_id=p.id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE p.workspace_id=:w AND p.generation_id=:g AND p.status='confirmed'
  AND p.target_month=:month
GROUP BY l.item_id, i.item_code, i.name ORDER BY i.item_code"""
ACTUAL_SQL = f"""
SELECT sl.item_id, sum(sl.shipped_qty) qty
FROM erp.sales_record r
JOIN erp.shipment_line sl ON sl.workspace_id=r.workspace_id
 AND sl.generation_id=r.generation_id AND sl.shipment_id=r.shipment_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.cancelled_at IS NULL
  AND {MONTH}=:month
GROUP BY sl.item_id"""


def _months(month: str, count: int = 6) -> list[str]:
    year, mon = map(int, month.split("-"))
    out = []
    for _ in range(count):
        out.append(f"{year:04d}-{mon:02d}")
        year, mon = (year - 1, 12) if mon == 1 else (year, mon - 1)
    return out[::-1]


def _balance(rows) -> Decimal:
    return sum((Decimal(r["balance"]) for r in rows), Decimal(0))


def dashboard(context, month: str | None) -> dict[str, Any]:
    today = business_today()
    month = month or f"{today.year:04d}-{today.month:02d}"
    try:
        date.fromisoformat(f"{month}-01")
    except ValueError as error:
        raise invalid("month", "YYYY-MM") from error
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params = {**_s(scoped), "month": month}
        receivables = open_items(RECEIVABLE, connection, scoped)
        payables = open_items(PAYABLE, connection, scoped)
        trend = {
            r.m: r
            for r in connection.execute(
                text(
                    f"SELECT {MONTH} m, sum(r.supply_amount) supply, "
                    f"sum(r.total_amount) total, count(*) n {VALID_SALES} "
                    f"AND {MONTH} = ANY(:months) GROUP BY 1"
                ),
                {**params, "months": _months(month)},
            )
        }
        backlog = Decimal(0)
        for order in _orders(connection, scoped, " AND o.status<>'cancelled'"):
            for line in order["lines"]:
                left = Decimal(line["orderQty"]) - Decimal(line["shippedQty"])
                backlog += left * Decimal(line["unitPrice"])
        actual = {
            r.item_id: r.qty for r in connection.execute(text(ACTUAL_SQL), params)
        }
        plan = [
            {
                "itemId": r.item_id,
                "itemCode": r.item_code,
                "name": r.name,
                "planQty": str(r.plan_qty),
                "actualQty": str(actual.get(r.item_id, Decimal(0))),
            }
            for r in connection.execute(text(PLAN_SQL), params)
        ]
        uninvoiced = connection.execute(
            text(
                "SELECT count(*) "
                + VALID_SALES
                + " AND r.total_amount > 0 AND NOT EXISTS (SELECT 1 FROM erp.tax_invoice t "
                "WHERE t.workspace_id=r.workspace_id AND t.generation_id=r.generation_id "
                "AND t.sales_record_id=r.id AND t.status='issued')"
            ),
            params,
        ).scalar_one()
        receipts = _monies(RECEIVABLE, connection, scoped)
    by_partner: dict[int, Decimal] = {}
    due = {"overdue": Decimal(0), "notDue": Decimal(0), "unset": Decimal(0)}
    for r in receivables:
        balance = Decimal(r["balance"])
        if balance <= 0:
            continue
        by_partner[r["partnerId"]] = by_partner.get(r["partnerId"], 0) + balance
        group = (
            "unset"
            if r["dueDate"] is None
            else "overdue"
            if r["dueDate"] < today.isoformat()
            else "notDue"
        )
        due[group] += balance
    current = trend.get(month)
    return {
        "month": month,
        "salesSupply": str(current.supply if current else Decimal(0)),
        "salesTotal": str(current.total if current else Decimal(0)),
        "salesCount": current.n if current else 0,
        "receivableBalance": str(_balance(receivables)),
        "payableBalance": str(_balance(payables)),
        "orderBacklog": str(backlog.quantize(Decimal(1))),
        "monthlySales": [
            {"month": m, "supplyAmount": str(trend[m].supply if m in trend else 0)}
            for m in _months(month)
        ],
        "topReceivables": [
            {"partnerId": p, "balance": str(b)}
            for p, b in sorted(by_partner.items(), key=lambda x: -x[1])[:5]
        ],
        "receivableByDue": {k: str(v) for k, v in due.items()},
        "planVsActual": plan,
        "pending": {
            "uninvoicedSales": uninvoiced,
            "unappliedReceipts": sum(
                1
                for r in receipts
                if r["status"] == "confirmed" and Decimal(r["unappliedAmount"]) > 0
            ),
        },
    }
