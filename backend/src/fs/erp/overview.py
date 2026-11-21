"""E-21 영업 현황 · E-25 구매 현황 · E-26 재고 현황 (DSN-11 F17·F19·F26·F31).

세 화면 모두 **조회 계산**이다. 아무것도 저장하지 않는다.
- 영업 현황: 기간 매출, 수주 대비 출하, 미출하 잔량을 거래처·품목으로 묶는다.
- 구매 현황: 발주 대비 입고(WMS)·매입을 발주서별로 맞댄다. WMS가 꺼져 있으면 입고는 '모름'이다.
- 재고 현황: WMS 조회 함수 결과를 그대로 보여 준다. ERP는 재고를 들고 있지 않다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp.procurement import _orders
from fs.erp.sales import MODULE, _rows, _s
from fs.erp.service import _read
from fs.wms import interface as wms

SALES_SQL = """
SELECT p.partner_code, p.partner_name, i.item_code, i.name item_name,
       sum(l.shipped_qty) shipped_qty, sum(l.shipped_qty * ol.unit_price) supply_amount
FROM erp.sales_record r
JOIN erp.partner p ON p.workspace_id=r.workspace_id AND p.generation_id=r.generation_id
 AND p.id=r.partner_id
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id
 AND sh.generation_id=r.generation_id AND sh.id=r.shipment_id
JOIN erp.shipment_line l ON l.workspace_id=sh.workspace_id
 AND l.generation_id=sh.generation_id AND l.shipment_id=sh.id
JOIN erp.shipment_order_line sol ON sol.workspace_id=l.workspace_id
 AND sol.generation_id=l.generation_id AND sol.id=l.shipment_order_line_id
JOIN erp.sales_order_line ol ON ol.workspace_id=sol.workspace_id
 AND ol.generation_id=sol.generation_id AND ol.id=sol.sales_order_line_id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.cancelled_at IS NULL
  AND (r.recognized_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN :date_from AND :date_to
GROUP BY p.partner_code, p.partner_name, i.item_code, i.name
ORDER BY p.partner_code, i.item_code"""
# 수주 대비 출하: 출하지시로 나간 수량을 수주 명세에 맞댄다. 취소된 수주는 뺀다.
ORDER_PROGRESS_SQL = """
SELECT o.order_no, o.ordered_on, p.partner_code, p.partner_name, i.item_code,
       l.order_qty, coalesce(s.shipped_qty, 0) shipped_qty,
       l.order_qty - coalesce(s.shipped_qty, 0) open_qty, o.status
FROM erp.sales_order o
JOIN erp.partner p ON p.workspace_id=o.workspace_id AND p.generation_id=o.generation_id
 AND p.id=o.partner_id
JOIN erp.sales_order_line l ON l.workspace_id=o.workspace_id
 AND l.generation_id=o.generation_id AND l.sales_order_id=o.id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
LEFT JOIN LATERAL (
  SELECT sum(sl.shipped_qty) shipped_qty
  FROM erp.shipment_order so
  JOIN erp.shipment_order_line sol ON sol.workspace_id=so.workspace_id
   AND sol.generation_id=so.generation_id AND sol.shipment_order_id=so.id
   AND sol.item_id=l.item_id
  JOIN erp.shipment sh ON sh.workspace_id=so.workspace_id
   AND sh.generation_id=so.generation_id AND sh.shipment_order_id=so.id
  JOIN erp.shipment_line sl ON sl.workspace_id=sh.workspace_id
   AND sl.generation_id=sh.generation_id AND sl.shipment_id=sh.id
   AND sl.item_id=l.item_id
  WHERE so.workspace_id=o.workspace_id AND so.generation_id=o.generation_id
    AND so.sales_order_id=o.id
) s ON true
WHERE o.workspace_id=:w AND o.generation_id=:g AND o.status <> 'cancelled'
  AND o.ordered_on BETWEEN :date_from AND :date_to
ORDER BY o.ordered_on DESC, o.order_no, i.item_code"""


def sales_status(context, date_from: date, date_to: date) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params = {**_s(scoped), "date_from": date_from, "date_to": date_to}
        revenue = _rows(connection, SALES_SQL, params)
        progress = _rows(connection, ORDER_PROGRESS_SQL, params)
    total = sum((Decimal(r["supplyAmount"]) for r in revenue), Decimal(0))
    unshipped = sum((Decimal(r["openQty"]) for r in progress), Decimal(0))
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "revenue": revenue,
        "orders": progress,
        "supplyTotal": str(total),
        "openQtyTotal": str(unshipped),
    }


def purchase_status(context, date_from: date, date_to: date) -> dict[str, Any]:
    """발주 대비 입고·매입. 입고는 저장하지 않고 WMS에서 읽어 맞댄다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        orders = _orders(
            connection,
            scoped,
            " AND o.ordered_on BETWEEN :date_from AND :date_to",
            date_from=date_from,
            date_to=date_to,
        )
        invoiced = {
            r["purchase_order_id"]: r["total_amount"]
            for r in connection.execute(
                text(
                    "SELECT purchase_order_id, sum(total_amount) total_amount "
                    "FROM erp.purchase_invoice WHERE workspace_id=:w AND generation_id=:g "
                    "AND purchase_order_id IS NOT NULL AND status='confirmed' "
                    "GROUP BY purchase_order_id"
                ),
                _s(scoped),
            ).mappings()
        }
    rows = [
        {
            "poNo": o["poNo"],
            "orderedOn": o["orderedOn"],
            "partnerCode": o["partnerCode"],
            "partnerName": o["partnerName"],
            "status": o["status"],
            "totalAmount": o["totalAmount"],
            "invoicedAmount": str(invoiced.get(o["id"], Decimal(0))),
            "receiptState": o["receipt"]["state"],
            "orderedQty": o["receipt"].get("orderedQty"),
            "receivedQty": o["receipt"].get("receivedQty"),
        }
        for o in orders
        if o["status"] != "draft"
    ]
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "orders": rows,
        "orderTotal": str(sum((Decimal(r["totalAmount"]) for r in rows), Decimal(0))),
        "invoicedTotal": str(
            sum((Decimal(r["invoicedAmount"]) for r in rows), Decimal(0))
        ),
        # WMS가 꺼져 있으면 한 건이라도 UNKNOWN이 된다. 0으로 보지 않는다.
        "receiptKnown": all(r["receiptState"] != "UNKNOWN" for r in rows),
    }


def stock_status(context) -> dict[str, Any]:
    """E-26: ERP 품목 코드로 WMS 재고를 읽는다. WMS가 꺼져 있으면 조회 불가라고 말한다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        items = _rows(
            connection,
            "SELECT item_code, name, base_unit, track_stock FROM erp.item "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active "
            "ORDER BY item_code",
            _s(scoped),
        )
        tracked = [i["itemCode"] for i in items if i["trackStock"]]
        on_hand = wms.stock_on_hand(connection, scoped, tracked)
    if on_hand is None:
        return {"available": False, "rows": []}
    return {
        "available": True,
        "rows": [
            {
                "itemCode": item["itemCode"],
                "itemName": item["name"],
                "unit": (on_hand.get(item["itemCode"]) or {}).get("unit")
                or item["baseUnit"],
                # WMS에 없는 품목은 수량 0이 아니라 '연결 안 됨'이다.
                "linked": item["itemCode"] in on_hand,
                "qtyOnHand": (on_hand.get(item["itemCode"]) or {}).get("qtyOnHand"),
                "safetyStock": (on_hand.get(item["itemCode"]) or {}).get("safetyStock"),
                "isShort": (on_hand.get(item["itemCode"]) or {}).get("isShort"),
            }
            for item in items
            if item["trackStock"]
        ],
    }
