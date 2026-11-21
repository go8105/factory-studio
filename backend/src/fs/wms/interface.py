"""WMS 읽기 전용 조회 인터페이스 (FS-013 §6 · DSN-21 Q6).

CMMS가 WMS를 이 모듈로만 읽어 예비품 재고를 보고, ERP가 입고·수불을 읽어 매입·재고자산 평가를 한다
(DSN-11 F23·F35). **재고 원장은 WMS만 가진다**(FS-029 D50) — 읽는 쪽은 수량을 저장하지 않고
볼 때마다 여기서 읽는다.
WMS를 꺼 두었으면 None을 돌려주고, CMMS는 재고 칸 없이 동작한다.

호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """WMS 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "wms")


def stock_on_hand(
    connection: Connection, scoped: AuthContext, item_codes: list[str]
) -> dict[str, dict[str, Any]] | None:
    """품목 코드별 재고 `{itemCode: {qtyOnHand, unit, safetyStock, isShort}}`. WMS가 꺼져 있으면 None.

    재고는 `wms.stock_move`의 합이다(CMMS는 저장하지 않는다). 안전 재고가 설정된 품목만
    부족 여부를 가린다 — 기준이 없으면 '부족'이라고 말할 수 없다.

    목록에 없는(WMS에 등록되지 않은) 코드는 결과에서 빠진다. 호출 쪽이 '연결 안 됨'으로 다룬다.
    """
    if not enabled(connection, scoped):
        return None
    if not item_codes:
        return {}
    rows = connection.execute(
        text(
            "SELECT i.item_code, i.base_unit, i.safety_stock, "
            " COALESCE((SELECT sum(m.qty_delta) FROM wms.stock_move m "
            "   WHERE m.workspace_id=i.workspace_id AND m.generation_id=i.generation_id "
            "     AND m.item_id=i.id), 0) qty_on_hand "
            "FROM wms.item i WHERE i.workspace_id=:w AND i.generation_id=:g "
            "  AND i.item_code = ANY(:codes)"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "codes": list(item_codes),
        },
    ).mappings()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        on_hand = Decimal(str(row["qty_on_hand"]))
        safety = row["safety_stock"]
        out[row["item_code"]] = {
            "qtyOnHand": f"{on_hand:.3f}",
            "unit": row["base_unit"],
            "safetyStock": None if safety is None else f"{Decimal(str(safety)):.3f}",
            # 기준이 없으면 '부족하지 않다'가 아니라 **판단하지 않는다**(None).
            "isShort": None if safety is None else on_hand < Decimal(str(safety)),
        }
    return out


def supply_items(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """소모품(SUPPLY) 품목 `[{itemCode, name, baseUnit, safetyStock}]`. WMS가 꺼져 있으면 None.

    CMMS 예비품을 WMS 품목에 이어 붙일 때 고르는 목록이다(DSN-21 Q6).
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT item_code, name, base_unit, safety_stock FROM wms.item "
            "WHERE workspace_id=:w AND generation_id=:g AND item_class='SUPPLY' AND is_active "
            "ORDER BY item_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "itemCode": row["item_code"],
            "name": row["name"],
            "baseUnit": row["base_unit"],
            "safetyStock": None
            if row["safety_stock"] is None
            else f"{Decimal(str(row['safety_stock'])):.3f}",
        }
        for row in rows
    ]


# 검수에서 격리로 뺀 줄 = QMS 수입 검사 대상(DSN-13 F18). 공지 1건·줄 1개가 검사 1건의 원천이다.
_TO_INSPECT = """
SELECT n.notice_no, n.notice_kind, n.partner_ref, n.inspected_at, l.line_no, l.lot_no,
       l.quarantined_qty, i.item_code, i.name item_name, i.base_unit
FROM wms.inbound_notice n
JOIN wms.inbound_notice_line l ON l.workspace_id=n.workspace_id
 AND l.generation_id=n.generation_id AND l.notice_id=n.id
JOIN wms.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE n.workspace_id=:w AND n.generation_id=:g AND n.status='INSPECTED'
  AND l.quarantined_qty > 0
ORDER BY n.inspected_at DESC, n.notice_no, l.line_no
"""


def inbound_lots_to_inspect(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """검수에서 격리된 입고 줄 `[{sourceRef, noticeNo, noticeKind, partnerCode, lotNo, itemCode, qty, unit}]`.

    WMS가 꺼져 있으면 None. QMS 수입·반품 검사의 대상 목록이다(DSN-14 F11) —
    `noticeKind`가 SALES_RETURN이면 반품 검사, 나머지는 수입 검사다.
    이미 검사한 줄을 거르지 않는다. QMS가 자기 `source_ref`로 가린다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(_TO_INSPECT), {"w": scoped.workspace_id, "g": scoped.generation_id}
    ).mappings()
    return [
        {
            "sourceRef": f"{row['notice_no']}:{row['line_no']}",
            "noticeNo": row["notice_no"],
            "noticeKind": row["notice_kind"],
            "partnerCode": row["partner_ref"],
            "inspectedAt": row["inspected_at"].isoformat(),
            "lotNo": row["lot_no"],
            "itemCode": row["item_code"],
            "itemName": row["item_name"],
            "qty": f"{Decimal(str(row['quarantined_qty'])):.3f}",
            "unit": row["base_unit"],
        }
        for row in rows
    ]


def lots(
    connection: Connection, scoped: AuthContext, item_code: str | None = None
) -> list[dict[str, Any]] | None:
    """LOT 대장 `[{lotNo, itemCode, origin, status, receivedOn, supplierLotNo, expiryDate}]`. WMS 꺼짐이면 None.

    품목 코드를 주면 그 품목만. QMS가 검사 대상 LOT을 직접 고를 때 쓴다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT t.lot_no, t.origin, t.status, t.received_on, t.supplier_lot_no, "
            " t.expiry_date, i.item_code, i.name item_name, i.base_unit "
            "FROM wms.lot t "
            "JOIN wms.item i ON i.workspace_id=t.workspace_id "
            " AND i.generation_id=t.generation_id AND i.id=t.item_id "
            "WHERE t.workspace_id=:w AND t.generation_id=:g "
            "  AND (CAST(:code AS text) IS NULL OR i.item_code=:code) "
            "ORDER BY t.received_on DESC, t.lot_no"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "code": item_code},
    ).mappings()
    return [
        {
            "lotNo": row["lot_no"],
            "itemCode": row["item_code"],
            "itemName": row["item_name"],
            "unit": row["base_unit"],
            "origin": row["origin"],
            "status": row["status"],
            "receivedOn": row["received_on"].isoformat(),
            "supplierLotNo": row["supplier_lot_no"],
            "expiryDate": None
            if row["expiry_date"] is None
            else row["expiry_date"].isoformat(),
        }
        for row in rows
    ]


def receipts(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> list[dict[str, Any]] | None:
    """검수를 마친 입고 `[{noticeNo, noticeKind, partnerRef, inspectedAt, lines:[...]}]`. WMS 꺼짐이면 None.

    ERP 매입이 발주 입고분을 읽는다(DSN-11 F23 PO_RECEIPT). **검수한 것만** 준다 —
    도착만 하고 검수 전인 입고는 아직 받은 수량이 정해지지 않았다.
    `acceptedQty`는 정상 입고, `quarantinedQty`는 격리다. 격리분은 매입 대상이 아니라고 읽는 쪽이 정한다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT n.notice_no, n.notice_kind, n.partner_ref, n.inspected_at, n.warehouse_id, "
            "       l.line_no, i.item_code, i.base_unit, l.accepted_qty, l.quarantined_qty, l.shortage_qty "
            "FROM wms.inbound_notice n "
            "JOIN wms.inbound_notice_line l ON l.workspace_id=n.workspace_id "
            " AND l.generation_id=n.generation_id AND l.notice_id=n.id "
            "JOIN wms.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id "
            " AND i.id=l.item_id "
            "WHERE n.workspace_id=:w AND n.generation_id=:g AND n.status='INSPECTED' "
            "  AND n.inspected_at >= CAST(:date_from AS date) "
            "  AND n.inspected_at < CAST(:date_to AS date) + interval '1 day' "
            "ORDER BY n.inspected_at, n.notice_no, l.line_no"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    ).mappings()
    notices: dict[str, dict[str, Any]] = {}
    for r in rows:
        notice = notices.setdefault(
            r["notice_no"],
            {
                "noticeNo": r["notice_no"],
                "noticeKind": r["notice_kind"],
                "partnerRef": r["partner_ref"],
                "inspectedAt": r["inspected_at"].isoformat(),
                "lines": [],
            },
        )
        notice["lines"].append(
            {
                "lineNo": r["line_no"],
                "itemCode": r["item_code"],
                "unit": r["base_unit"],
                "acceptedQty": f"{Decimal(str(r['accepted_qty'])):.3f}",
                "quarantinedQty": f"{Decimal(str(r['quarantined_qty'])):.3f}",
                "shortageQty": f"{Decimal(str(r['shortage_qty'])):.3f}",
            }
        )
    return list(notices.values())


def stock_moves(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 품목별 수불 `[{itemCode, unit, openingQty, inQty, outQty, closingQty}]`. WMS 꺼짐이면 None.

    ERP 재고자산 평가(DSN-11 F35)가 월 이동평균 단가를 낼 때 **수량**을 여기서 읽는다.
    금액은 ERP의 매입 금액이라 여기서 주지 않는다. 확정(posted) 전표만 센다.
    움직임이 없어도 기초 수량이 있으면 준다 — 그 달 재고가 0이라는 뜻이 아니다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT i.item_code, i.base_unit, "
            " COALESCE(sum(m.qty_delta) FILTER (WHERE d.document_month < :month), 0) opening, "
            " COALESCE(sum(m.qty_delta) FILTER (WHERE d.document_month = :month AND m.qty_delta > 0), 0) moved_in, "
            " COALESCE(-sum(m.qty_delta) FILTER (WHERE d.document_month = :month AND m.qty_delta < 0), 0) moved_out "
            "FROM wms.item i "
            "LEFT JOIN wms.stock_move m ON m.workspace_id=i.workspace_id "
            " AND m.generation_id=i.generation_id AND m.item_id=i.id "
            "LEFT JOIN wms.stock_document d ON d.workspace_id=m.workspace_id "
            " AND d.generation_id=m.generation_id AND d.id=m.document_id AND d.status='posted' "
            "WHERE i.workspace_id=:w AND i.generation_id=:g "
            "GROUP BY i.item_code, i.base_unit ORDER BY i.item_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "month": month},
    ).mappings()
    out = []
    for r in rows:
        opening = Decimal(str(r["opening"]))
        moved_in = Decimal(str(r["moved_in"]))
        moved_out = Decimal(str(r["moved_out"]))
        out.append(
            {
                "itemCode": r["item_code"],
                "unit": r["base_unit"],
                "openingQty": f"{opening:.3f}",
                "inQty": f"{moved_in:.3f}",
                "outQty": f"{moved_out:.3f}",
                "closingQty": f"{opening + moved_in - moved_out:.3f}",
            }
        )
    return out
