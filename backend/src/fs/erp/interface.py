"""ERP 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6, FS-024 7.2).

다른 솔루션(WMS·GW·EIP)은 ERP를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
ERP를 꺼 두었으면 None을 돌려주고, 호출 쪽은 기능을 줄여 동작한다(D12).
ERP는 다른 솔루션을 읽지 않는다 — 출하·매입은 재고를 확인하지 않는다(FS-024 D15).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available

_SHIPMENT_LINES = """
SELECT sh.shipment_no, sh.shipped_at, so.ship_order_no, row_number() OVER (PARTITION BY sh.id ORDER BY l.id) line_no, i.item_code, l.shipped_qty qty, l.shipped_uom unit, l.packing_no
FROM erp.shipment sh
JOIN erp.shipment_order so ON so.workspace_id=sh.workspace_id AND so.generation_id=sh.generation_id AND so.id=sh.shipment_order_id
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
    return module_available(connection, scoped.workspace_id, "erp")


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
                "shipmentOrderNo": r["ship_order_no"],
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
                "lineNo": r["line_no"],
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


def shipment_orders(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """Scoped ERP demand references, including open/shipped/cancelled states (FS-026)."""
    if not enabled(connection, scoped):
        return None
    sql = """
    SELECT so.ship_order_no,so.status,i.item_code,ol.order_qty,sl.unit,sl.line_no
    FROM erp.shipment_order so
    JOIN erp.shipment_order_line ol ON ol.workspace_id=so.workspace_id AND ol.generation_id=so.generation_id AND ol.shipment_order_id=so.id
    JOIN erp.sales_order_line sl ON sl.workspace_id=ol.workspace_id AND sl.generation_id=ol.generation_id AND sl.id=ol.sales_order_line_id
    JOIN erp.item i ON i.workspace_id=sl.workspace_id AND i.generation_id=sl.generation_id AND i.id=sl.item_id
    WHERE so.workspace_id=:w AND so.generation_id=:g
    ORDER BY so.ship_order_no,sl.line_no
    """
    grouped = {}
    for row in connection.execute(text(sql), _s(scoped)).mappings():
        entry = grouped.setdefault(
            row["ship_order_no"],
            {
                "shipmentOrderNo": row["ship_order_no"],
                "status": row["status"],
                "lines": [],
            },
        )
        entry["lines"].append(
            {
                "itemCode": row["item_code"],
                "qty": str(row["order_qty"]),
                "unit": row["unit"],
                "lineNo": row["line_no"],
            }
        )
    return list(grouped.values())


# FS-030: code-only approval snapshots. Never call GW from this provider.
def approval_source_digest(snapshot: dict) -> str:
    """Canonical v1 semantic values; display dates and status are excluded."""
    import hashlib
    import json

    values = {k: v for k, v in snapshot.items() if k not in {"display", "status"}}
    return hashlib.sha256(
        json.dumps(
            values, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
    ).hexdigest()


def approval_documents(connection, scoped, kind, *, search="", offset=0, limit=50):
    if not enabled(connection, scoped):
        return None
    from fs.common.errors import ApiError

    if (
        kind != "PURCHASE_INVOICE"
        or not 0 <= offset
        or not 1 <= limit <= 100
        or len(search) > 100
    ):
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "조회 조건을 확인해 주세요.",
            {"fields": {"kind": "매입 전표 조회 조건이 잘못되었습니다."}},
        )
    sql = """FROM erp.purchase_invoice p JOIN erp.partner v
      ON (v.workspace_id,v.generation_id,v.id)=(p.workspace_id,p.generation_id,p.partner_id)
      WHERE p.workspace_id=:w AND p.generation_id=:g AND p.status IN ('draft','confirmed')
      AND (strpos(lower(p.invoice_no),lower(:search))>0 OR strpos(lower(v.partner_name),lower(:search))>0)"""
    params = {**_s(scoped), "search": search, "offset": offset, "limit": limit}
    rows = connection.execute(
        text(
            "SELECT p.invoice_no,p.status,p.currency,p.supply_amount,p.tax_amount,p.total_amount,v.partner_name "
            + sql
            + " ORDER BY p.invoice_no OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return {
        "rows": [
            {
                "documentNo": r["invoice_no"],
                "status": r["status"],
                "currency": r["currency"],
                "partnerName": r["partner_name"],
                **{
                    k: format(r[v], ".2f")
                    for k, v in [
                        ("supplyAmount", "supply_amount"),
                        ("taxAmount", "tax_amount"),
                        ("totalAmount", "total_amount"),
                    ]
                },
            }
            for r in rows
        ],
        "total": connection.execute(
            text("SELECT count(*) " + sql), params
        ).scalar_one(),
        "offset": offset,
        "limit": limit,
    }


def approval_document(connection, scoped, kind, document_no):
    if not enabled(connection, scoped):
        return None
    if kind != "PURCHASE_INVOICE":
        return {"found": False}
    head = (
        connection.execute(
            text("""SELECT p.*,v.partner_code,v.partner_name FROM erp.purchase_invoice p
      JOIN erp.partner v ON (v.workspace_id,v.generation_id,v.id)=(p.workspace_id,p.generation_id,p.partner_id)
      WHERE p.workspace_id=:w AND p.generation_id=:g AND p.invoice_no=:no"""),
            {**_s(scoped), "no": document_no},
        )
        .mappings()
        .first()
    )
    if head is None:
        return {"found": False}
    lines = (
        connection.execute(
            text("""SELECT l.*,i.item_code FROM erp.purchase_invoice_line l
      JOIN erp.item i ON (i.workspace_id,i.generation_id,i.id)=(l.workspace_id,l.generation_id,l.item_id)
      WHERE l.workspace_id=:w AND l.generation_id=:g AND l.purchase_invoice_id=:id ORDER BY l.line_no"""),
            {**_s(scoped), "id": head["id"]},
        )
        .mappings()
        .all()
    )
    from fs.common.errors import ApiError

    if len(lines) > 200:
        raise ApiError(
            409,
            "PRECONDITION_NOT_MET",
            "원문 명세는 200행까지 연결할 수 있습니다.",
            {"reason": "SOURCE_TOO_LARGE"},
        )
    amounts = [
        ("supplyAmount", "supply_amount"),
        ("taxAmount", "tax_amount"),
        ("totalAmount", "total_amount"),
    ]
    snapshot = {
        "schemaVersion": 1,
        "kind": kind,
        "documentNo": head["invoice_no"].strip(),
        "partnerCode": head["partner_code"].strip(),
        "partnerName": head["partner_name"].strip(),
        "currency": head["currency"].strip(),
        **{k: format(head[v], ".2f") for k, v in amounts},
        "lines": [
            {
                "lineNo": r["line_no"],
                "itemCode": r["item_code"].strip(),
                "quantity": format(r["quantity"], ".3f"),
                "unit": r["unit"].strip(),
                "unitPrice": format(r["unit_price"], ".4f"),
                "currency": r["currency"].strip(),
                **{k: format(r[v], ".2f") for k, v in amounts},
            }
            for r in lines
        ],
        "display": {
            k: _iso(head[v])
            for k, v in [
                ("invoiceDate", "invoice_date"),
                ("dueDate", "due_date"),
                ("confirmedAt", "confirmed_at"),
                ("cancelledAt", "cancelled_at"),
            ]
        },
    }
    return {
        "found": True,
        "snapshot": snapshot,
        "digest": approval_source_digest(snapshot),
        "status": head["status"],
    }


def partners(
    connection: Connection, scoped: AuthContext, partner_kind: str | None = None
) -> list[dict[str, Any]] | None:
    """사용 중인 거래처 `[{partnerCode, partnerName, partnerKind}]`. ERP가 꺼져 있으면 None.

    CMMS가 외주 업체를 ERP 거래처에 이어 붙일 때 고르는 목록이다(DSN-21 Q5, SUPPLIER).
    비용 회계는 ERP 직접 매입으로 따로 처리하고, CMMS는 코드만 스냅샷으로 들고 있는다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT partner_code, partner_name, partner_kind FROM erp.partner "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active "
            "AND (CAST(:kind AS text) IS NULL OR partner_kind=:kind) ORDER BY partner_code"
        ),
        {**_s(scoped), "kind": partner_kind},
    ).mappings()
    return [
        {
            "partnerCode": row["partner_code"],
            "partnerName": row["partner_name"],
            "partnerKind": row["partner_kind"],
        }
        for row in rows
    ]


def purchase_orders(
    connection: Connection, scoped: AuthContext, open_only: bool = True
) -> list[dict[str, Any]] | None:
    """확정 발주 `[{poNo, partnerCode, partnerName, dueOn, status, lines:[...]}]`. ERP 꺼짐이면 None.

    WMS 입고 예정이 읽는다(DSN-11 §6). **확정한 발주만** 준다 — 초안은 아직 거래처에 나가지 않았다.
    `open_only`면 종결·취소를 뺀다. **입고 진행은 여기에 없다** — 얼마나 들어왔는지는 WMS가 알고,
    ERP는 저장하지 않고 WMS를 읽어 파생한다(DSN-11 §4-1 발주 진행 파생).
    """
    if not enabled(connection, scoped):
        return None
    where = " AND o.status='confirmed'" if open_only else " AND o.status<>'draft'"
    rows = connection.execute(
        text(
            "SELECT o.po_no, o.ordered_on, o.due_on, o.status, o.currency, o.total_amount, "
            "       p.partner_code, p.partner_name, "
            "       l.line_no, i.item_code, i.name item_name, l.quantity, l.unit, l.unit_price, l.due_on line_due_on "
            "FROM erp.purchase_order o "
            "JOIN erp.partner p ON p.workspace_id=o.workspace_id AND p.generation_id=o.generation_id "
            " AND p.id=o.partner_id "
            "JOIN erp.purchase_order_line l ON l.workspace_id=o.workspace_id "
            " AND l.generation_id=o.generation_id AND l.purchase_order_id=o.id "
            "JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id "
            " AND i.id=l.item_id "
            f"WHERE o.workspace_id=:w AND o.generation_id=:g{where} "
            "ORDER BY o.ordered_on, o.po_no, l.line_no"
        ),
        _s(scoped),
    ).mappings()
    orders: dict[str, dict[str, Any]] = {}
    for r in rows:
        order = orders.setdefault(
            r["po_no"],
            {
                "poNo": r["po_no"],
                "partnerCode": r["partner_code"],
                "partnerName": r["partner_name"],
                "orderedOn": r["ordered_on"].isoformat(),
                "dueOn": None if r["due_on"] is None else r["due_on"].isoformat(),
                "status": r["status"],
                "currency": r["currency"],
                "totalAmount": str(r["total_amount"]),
                "lines": [],
            },
        )
        order["lines"].append(
            {
                "lineNo": r["line_no"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "quantity": str(r["quantity"]),
                "unit": r["unit"],
                "unitPrice": str(r["unit_price"]),
                "dueOn": None
                if r["line_due_on"] is None
                else r["line_due_on"].isoformat(),
            }
        )
    return list(orders.values())


def journal_summary(
    connection: Connection, scoped: AuthContext, month: str
) -> dict[str, Any] | None:
    """그 달 **확정 전표**의 계정별 차·대 합계. ERP 꺼짐이면 None.

    EIP 경영 요약이 읽는다. 초안·역분개된 전표는 빼고 역분개 전표 자체는 넣는다 —
    정정은 지우는 것이 아니라 반대 전표를 더하는 것이라 합계가 맞는다.
    계정이 하나도 없으면 빈 목록이고, 그것은 '쓰지 않았다'가 아니라 '전표가 없다'이다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT a.account_code, a.account_name, a.account_class, a.normal_side, "
            "       sum(l.amount) FILTER (WHERE l.side='DEBIT') debit, "
            "       sum(l.amount) FILTER (WHERE l.side='CREDIT') credit "
            "FROM erp.journal_entry e "
            "JOIN erp.journal_line l ON l.workspace_id=e.workspace_id "
            " AND l.generation_id=e.generation_id AND l.journal_entry_id=e.id "
            "JOIN erp.account a ON a.workspace_id=l.workspace_id "
            " AND a.generation_id=l.generation_id AND a.id=l.account_id "
            "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.status<>'draft' "
            "  AND to_char(e.entry_date,'YYYY-MM')=:month "
            "GROUP BY a.account_code, a.account_name, a.account_class, a.normal_side "
            "ORDER BY a.account_code"
        ),
        {**_s(scoped), "month": month},
    ).mappings()
    accounts = [
        {
            "accountCode": r["account_code"],
            "accountName": r["account_name"],
            "accountClass": r["account_class"],
            "normalSide": r["normal_side"],
            "debit": str(r["debit"] or 0),
            "credit": str(r["credit"] or 0),
        }
        for r in rows
    ]
    return {"month": month, "accounts": accounts}


def sales_summary(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> dict[str, Any] | None:
    """기간 매출·채권 요약 `{salesAmount, salesCount, receivableOpen, partners:[...]}`. ERP 꺼짐이면 None.

    EIP 경영 요약과 CRM이 읽는다. 매출은 그 기간 **확정 매출**이고, 채권 미수는
    기간이 아니라 **지금 남은 금액**이다(원금 − 소명). 둘은 기준이 달라 더하지 않는다.
    """
    if not enabled(connection, scoped):
        return None
    period = {**_s(scoped), "date_from": date_from, "date_to": date_to}
    sales = connection.execute(
        text(
            "SELECT p.partner_code, p.partner_name, count(*) sales_count, "
            "       sum(s.total_amount) amount "
            "FROM erp.sales_record s "
            "JOIN erp.partner p ON p.workspace_id=s.workspace_id "
            " AND p.generation_id=s.generation_id AND p.id=s.partner_id "
            "WHERE s.workspace_id=:w AND s.generation_id=:g AND s.cancelled_at IS NULL "
            "  AND (s.recognized_at AT TIME ZONE 'Asia/Seoul')::date BETWEEN :date_from AND :date_to "
            "GROUP BY p.partner_code, p.partner_name ORDER BY p.partner_code"
        ),
        period,
    ).mappings()
    partners = [
        {
            "partnerCode": r["partner_code"],
            "partnerName": r["partner_name"],
            "salesCount": r["sales_count"],
            "amount": str(r["amount"] or 0),
        }
        for r in sales
    ]
    open_amount = connection.execute(
        text(
            "SELECT COALESCE((SELECT sum(r.amount) FROM erp.receivable r "
            "   WHERE r.workspace_id=:w AND r.generation_id=:g), 0) "
            " - COALESCE((SELECT sum(a.amount) FROM erp.receipt_apply a "
            "   WHERE a.workspace_id=:w AND a.generation_id=:g), 0)"
        ),
        _s(scoped),
    ).scalar_one()
    return {
        "from": date_from.isoformat(),
        "to": date_to.isoformat(),
        "salesAmount": str(sum(Decimal(p["amount"]) for p in partners)),
        "salesCount": sum(p["salesCount"] for p in partners),
        "receivableOpen": str(open_amount),
        "partners": partners,
    }
