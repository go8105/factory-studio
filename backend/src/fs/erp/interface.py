"""ERP 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6, FS-024 7.2).

다른 솔루션(WMS)은 ERP를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
ERP를 꺼 두었으면 None을 돌려주고, 호출 쪽은 기능을 줄여 동작한다(D12).
ERP는 다른 솔루션을 읽지 않는다 — 출하·매입은 재고를 확인하지 않는다(FS-024 D15).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext

_SHIPMENT_LINES = """
SELECT sh.shipment_no, sh.shipped_at, i.item_code, l.shipped_qty qty, l.shipped_uom unit, l.packing_no
FROM erp.shipment sh
JOIN erp.shipment_line l ON l.workspace_id=sh.workspace_id AND l.generation_id=sh.generation_id
 AND l.shipment_id=sh.id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id AND i.id=l.item_id
WHERE sh.workspace_id=:w AND sh.generation_id=:g AND sh.status='confirmed'
ORDER BY sh.shipped_at, sh.shipment_no, l.id
"""

# 확정됐던 매입만(초안 제외). 확정 후 취소된 매입은 cancelledAt으로 알린다.
_PURCHASE_LINES = """
SELECT p.invoice_no, p.confirmed_at, p.cancelled_at, i.item_code, l.quantity qty, l.unit
FROM erp.purchase_invoice p
JOIN erp.purchase_invoice_line l ON l.workspace_id=p.workspace_id AND l.generation_id=p.generation_id
 AND l.purchase_invoice_id=p.id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id AND i.id=l.item_id
WHERE p.workspace_id=:w AND p.generation_id=:g AND p.confirmed_at IS NOT NULL
ORDER BY p.confirmed_at, p.invoice_no, l.line_no
"""

_OPEN_SHIPMENT_QTY = """
SELECT i.item_code, sum(ol.order_qty) qty
FROM erp.shipment_order so
JOIN erp.shipment_order_line ol ON ol.workspace_id=so.workspace_id AND ol.generation_id=so.generation_id
 AND ol.shipment_order_id=so.id
JOIN erp.sales_order_line sl ON sl.workspace_id=ol.workspace_id AND sl.generation_id=ol.generation_id
 AND sl.id=ol.sales_order_line_id
JOIN erp.item i ON i.workspace_id=sl.workspace_id AND i.generation_id=sl.generation_id AND i.id=sl.item_id
WHERE so.workspace_id=:w AND so.generation_id=:g AND so.status='open'
GROUP BY i.item_code
"""


def _s(scoped: AuthContext) -> dict[str, int]:
    return {"w": scoped.workspace_id, "g": scoped.generation_id}


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """ERP 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return bool(
        connection.execute(
            text(
                "SELECT enabled FROM core.workspace_module WHERE workspace_id=:w AND module_key='erp'"
            ),
            {"w": scoped.workspace_id},
        ).scalar()
    )


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


def confirmed_shipments(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """확정 출하 `[{shipmentNo, shippedAt, lines:[{itemCode, qty, unit, packingNo}]}]`. ERP 꺼짐이면 None."""
    if not enabled(connection, scoped):
        return None
    grouped: dict[str, dict[str, Any]] = {}
    for r in connection.execute(text(_SHIPMENT_LINES), _s(scoped)).mappings():
        entry = grouped.setdefault(
            r["shipment_no"],
            {
                "shipmentNo": r["shipment_no"],
                "shippedAt": _iso(r["shipped_at"]),
                "lines": [],
            },
        )
        entry["lines"].append(
            {
                "itemCode": r["item_code"],
                "qty": str(r["qty"]),
                "unit": r["unit"],
                "packingNo": r["packing_no"],
            }
        )
    return list(grouped.values())


def purchase_receipts(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """확정(또는 확정 후 취소)된 매입 `[{invoiceNo, confirmedAt, cancelledAt, lines:[{itemCode, qty, unit}]}]`. ERP 꺼짐이면 None."""
    if not enabled(connection, scoped):
        return None
    grouped: dict[str, dict[str, Any]] = {}
    for r in connection.execute(text(_PURCHASE_LINES), _s(scoped)).mappings():
        entry = grouped.setdefault(
            r["invoice_no"],
            {
                "invoiceNo": r["invoice_no"],
                "confirmedAt": _iso(r["confirmed_at"]),
                "cancelledAt": _iso(r["cancelled_at"]),
                "lines": [],
            },
        )
        entry["lines"].append(
            {"itemCode": r["item_code"], "qty": str(r["qty"]), "unit": r["unit"]}
        )
    return list(grouped.values())


def open_shipment_qty(
    connection: Connection, scoped: AuthContext
) -> dict[str, str] | None:
    """미출하(open) 출하지시 수량 품목별 합 `{itemCode: qty}`. ERP 꺼짐이면 None."""
    if not enabled(connection, scoped):
        return None
    return {
        r["item_code"]: str(r["qty"])
        for r in connection.execute(text(_OPEN_SHIPMENT_QTY), _s(scoped)).mappings()
    }
