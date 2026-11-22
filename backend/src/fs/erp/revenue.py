"""매출: TX-09 인식(출하 확정 안에서 호출) · E-07 매출 조회·취소 · E-08 세금계산서 (FS-019c·019d).

세액 정책은 이 파일 한 곳에서만 계산한다(호출부에서 재계산 금지):
- 품목 과세구분 TAXABLE 10%, ZERO·EXEMPT 0% (E-G01: 세율은 코드 상수).
- 명세별 공급가액(수량 × 수주 단가)과 세액(공급가액 × 세율)을 각각 1원 단위 사사오입한 뒤 합산.
- 채권은 같은 트랜잭션에서 원금 = 합계로 1건. 만기 = 인식일(Asia/Seoul) + 거래처 결제일수, 조건 없으면 NULL.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import posting
from fs.erp.sales import _S, MODULE, _action, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

TAX_RATE = {"TAXABLE": Decimal("0.10"), "ZERO": Decimal(0), "EXEMPT": Decimal(0)}
WON = Decimal(1)

LINES_SQL = """
SELECT sl.shipped_qty, l.unit_price, i.tax_category
FROM erp.shipment_line sl
JOIN erp.shipment_order_line sol ON sol.workspace_id=sl.workspace_id
 AND sol.generation_id=sl.generation_id AND sol.id=sl.shipment_order_line_id
JOIN erp.sales_order_line l ON l.workspace_id=sol.workspace_id
 AND l.generation_id=sol.generation_id AND l.id=sol.sales_order_line_id
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE sl.workspace_id=:w AND sl.generation_id=:g AND sl.shipment_id=:id
ORDER BY sl.id"""


def line_amounts(qty, price, category) -> tuple[Decimal, Decimal]:
    """명세 1줄의 (공급가액, 세액). 매입 전표(019f)도 이 함수로 계산한다."""
    supply = (Decimal(qty) * Decimal(price)).quantize(WON, ROUND_HALF_UP)
    return supply, (supply * TAX_RATE[category]).quantize(WON, ROUND_HALF_UP)


def amounts(lines) -> tuple[Decimal, Decimal]:
    """(공급가액, 세액) 합계. lines: (수량, 단가, 과세구분)."""
    pairs = [line_amounts(*line) for line in lines]
    return sum((p[0] for p in pairs), Decimal(0)), sum(
        (p[1] for p in pairs), Decimal(0)
    )


def recognize(connection, scoped, shipment_id: int, partner_id: int) -> int:
    params = {"w": scoped.workspace_id, "g": scoped.generation_id, "id": shipment_id}
    rows = connection.execute(text(LINES_SQL), params).all()
    supply, tax = amounts(rows)
    record_id = connection.execute(
        text(
            "INSERT INTO erp.sales_record (workspace_id, generation_id, shipment_id, "
            "partner_id, supply_amount, tax_amount, total_amount, recognized_at) "
            "SELECT :w, :g, :id, :p, :s, :t, :total, shipped_at FROM erp.shipment "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING id"
        ),
        {**params, "p": partner_id, "s": supply, "t": tax, "total": supply + tax},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO erp.receivable (workspace_id, generation_id, sales_record_id, "
            "partner_id, amount, due_date) "
            "SELECT r.workspace_id, r.generation_id, r.id, r.partner_id, r.total_amount, "
            "(r.recognized_at AT TIME ZONE 'Asia/Seoul')::date + p.payment_term_days "
            "FROM erp.sales_record r JOIN erp.partner p ON p.workspace_id=r.workspace_id "
            "AND p.generation_id=r.generation_id AND p.id=r.partner_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.id=:r"
        ),
        {**params, "r": record_id},
    )
    # 업무 확정과 같은 트랜잭션에서 전표를 만든다. 못 만들어도 매출은 선다(DSN-11 Q3).
    posting.post(connection, scoped, posting.SALE, record_id)
    return record_id


# ---- E-07 매출 ----
# 취소 막힘 이유(E-07 툴팁)는 서버가 정한다. 우선순위: 이미 취소 > 발급완료 > 소명 있음.
SALES_SQL = """
SELECT r.id, r.shipment_id, r.partner_id, r.supply_amount, r.tax_amount, r.total_amount,
       r.currency, r.recognized_at, r.cancelled_at, r.cancel_reason,
       sh.shipment_no, o.order_no, rv.id receivable_id, rv.due_date,
       coalesce((SELECT sum(a.amount) FROM erp.receipt_apply a
         WHERE a.workspace_id=rv.workspace_id AND a.generation_id=rv.generation_id
           AND a.receivable_id=rv.id), 0) applied_amount,
       t.id tax_invoice_id, t.status tax_invoice_status,
       CASE WHEN r.cancelled_at IS NOT NULL THEN 'ALREADY_CANCELLED'
            WHEN t.status='issued' THEN 'INVOICE_ISSUED'
            WHEN EXISTS (SELECT 1 FROM erp.receipt_apply a
              WHERE a.workspace_id=rv.workspace_id AND a.generation_id=rv.generation_id
                AND a.receivable_id=rv.id) THEN 'RECEIPT_APPLIED'
       END cancel_blocked_reason
FROM erp.sales_record r
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id AND sh.generation_id=r.generation_id
 AND sh.id=r.shipment_id
JOIN erp.shipment_order so ON so.workspace_id=sh.workspace_id
 AND so.generation_id=sh.generation_id AND so.id=sh.shipment_order_id
JOIN erp.sales_order o ON o.workspace_id=so.workspace_id AND o.generation_id=so.generation_id
 AND o.id=so.sales_order_id
LEFT JOIN erp.receivable rv ON rv.workspace_id=r.workspace_id
 AND rv.generation_id=r.generation_id AND rv.sales_record_id=r.id
LEFT JOIN erp.tax_invoice t ON t.workspace_id=r.workspace_id
 AND t.generation_id=r.generation_id AND t.sales_record_id=r.id
WHERE r.workspace_id=:w AND r.generation_id=:g"""
BLOCKED = {
    "ALREADY_CANCELLED": "이미 취소된 매출입니다.",
    "INVOICE_ISSUED": "세금계산서가 발급완료라 취소할 수 없습니다.",
    "RECEIPT_APPLIED": "수금 소명이 있어 취소할 수 없습니다. 소명을 먼저 취소하세요.",
}


def _sales(connection, scoped, where: str = "", **params: Any) -> list[dict[str, Any]]:
    return _rows(
        connection,
        SALES_SQL + where + " ORDER BY r.recognized_at DESC, r.id DESC",
        {**_s(scoped), **params},
    )


def _sale(connection, scoped, record_id: int) -> dict[str, Any]:
    found = _sales(connection, scoped, " AND r.id=:id", id=record_id)
    if not found:
        raise not_found()
    return found[0]


def list_sales(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _sales(connection, read_scope(connection, context, MODULE))


def _lock_sale(connection, scoped, record_id: int):
    """매출(순서 6) → 세금계산서(6) → 채권(7) 순서로 잠근다."""
    params = {**_s(scoped), "id": record_id}
    sale = connection.execute(
        text(
            "SELECT id, total_amount, cancelled_at, "
            "(recognized_at AT TIME ZONE 'Asia/Seoul')::date recognized_on FROM erp.sales_record "
            f"WHERE {_S} AND id=:id FOR UPDATE"
        ),
        params,
    ).first()
    if sale is None:
        raise not_found()
    invoice = connection.execute(
        text(
            f"SELECT id, status FROM erp.tax_invoice WHERE {_S} "
            "AND sales_record_id=:id FOR UPDATE"
        ),
        params,
    ).first()
    connection.execute(
        text(
            f"SELECT id FROM erp.receivable WHERE {_S} AND sales_record_id=:id FOR UPDATE"
        ),
        params,
    )
    return sale, invoice


def cancel_sale(context, record_id: int, reason: str, key: str):
    """매출 취소(FS-014b): 소명 0행, 발급대기 계산서는 함께 삭제, 발급완료면 거부.
    채권 원금은 남기고(유효 집계에서 제외), 출하 물류는 되돌리지 않는다."""

    def run(connection, scoped):
        _lock_sale(connection, scoped, record_id)
        blocked = _sale(connection, scoped, record_id)["cancelBlockedReason"]
        if blocked:
            raise _locked(BLOCKED[blocked], blocked)
        params = {**_s(scoped), "id": record_id}
        connection.execute(
            text(
                f"DELETE FROM erp.tax_invoice WHERE {_S} AND sales_record_id=:id "
                "AND status='pending'"
            ),
            params,
        )
        connection.execute(
            text(
                "UPDATE erp.sales_record SET cancelled_at=clock_timestamp(), "
                f"cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**params, "reason": reason},
        )
        return _sale(connection, scoped, record_id), "sales_record", record_id

    body = {"id": record_id, "reason": reason}
    return _action(context, "erp.sales_record.cancel", key, body, run)


# ---- E-08 세금계산서 ----
INVOICE_SQL = """
SELECT t.id, t.sales_record_id, t.partner_id, t.currency, t.status, t.approval_no,
       t.issued_on, t.created_at, r.supply_amount, r.tax_amount, r.total_amount,
       r.recognized_at, sh.shipment_no
FROM erp.tax_invoice t
JOIN erp.sales_record r ON r.workspace_id=t.workspace_id AND r.generation_id=t.generation_id
 AND r.id=t.sales_record_id
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id AND sh.generation_id=r.generation_id
 AND sh.id=r.shipment_id
WHERE t.workspace_id=:w AND t.generation_id=:g"""


def _invoices(connection, scoped, where: str = "", **params: Any):
    return _rows(
        connection,
        INVOICE_SQL + where + " ORDER BY t.created_at DESC, t.id DESC",
        {**_s(scoped), **params},
    )


def list_invoices(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _invoices(connection, read_scope(connection, context, MODULE))


def _issuable(sale) -> None:
    if sale.cancelled_at is not None:
        raise _locked(
            "취소된 매출에는 세금계산서를 만들 수 없습니다.", "SALES_CANCELLED"
        )
    if sale.total_amount == 0:
        # E-G07 결정(2026-09-26): 0원 매출은 허용하지만 세금계산서는 발급하지 않는다.
        raise _locked("0원 매출은 세금계산서를 발급하지 않습니다.", "ZERO_AMOUNT_SALE")


def create_invoice(context, record_id: int, key: str):
    def run(connection, scoped):
        sale, invoice = _lock_sale(connection, scoped, record_id)
        _issuable(sale)
        if invoice is not None:
            raise _locked(
                "이 매출에는 이미 세금계산서가 있습니다.",
                "INVOICE_EXISTS",
                taxInvoiceId=invoice.id,
            )
        invoice_id = connection.execute(
            text(
                "INSERT INTO erp.tax_invoice (workspace_id, generation_id, sales_record_id, "
                "partner_id) SELECT workspace_id, generation_id, id, partner_id "
                f"FROM erp.sales_record WHERE {_S} AND id=:id RETURNING id"
            ),
            {**_s(scoped), "id": record_id},
        ).scalar_one()
        return (
            _invoices(connection, scoped, " AND t.id=:id", id=invoice_id)[0],
            "tax_invoice",
            invoice_id,
        )

    return _action(
        context, "erp.tax_invoice.create", key, {"salesRecordId": record_id}, run, 201
    )


def issue_invoice(context, invoice_id: int, values: dict[str, Any], key: str):
    def run(connection, scoped):
        found = connection.execute(
            text(f"SELECT sales_record_id FROM erp.tax_invoice WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": invoice_id},
        ).first()
        if found is None:
            raise not_found()
        sale, invoice = _lock_sale(connection, scoped, found.sales_record_id)
        _issuable(sale)
        if invoice.status != "pending":
            raise _locked("이미 발급완료된 세금계산서입니다.", "ALREADY_ISSUED")
        if values["issued_on"] < sale.recognized_on.isoformat():
            raise invalid(
                "issued_on", f"발급일은 매출일({sale.recognized_on}) 이후여야 합니다."
            )
        if connection.execute(
            text(f"SELECT 1 FROM erp.tax_invoice WHERE {_S} AND approval_no=:no"),
            {**_s(scoped), "no": values["approval_no"]},
        ).first():
            raise invalid("approval_no", "이미 사용 중인 승인번호입니다.")
        connection.execute(
            text(
                "UPDATE erp.tax_invoice SET status='issued', approval_no=:approval_no, "
                f"issued_on=:issued_on WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), **values, "id": invoice_id},
        )
        return (
            _invoices(connection, scoped, " AND t.id=:id", id=invoice_id)[0],
            "tax_invoice",
            invoice_id,
        )

    return _action(
        context, "erp.tax_invoice.issue", key, {"id": invoice_id, **values}, run
    )


if __name__ == "__main__":
    # 1원 사사오입은 명세마다: 3 × 333.35 = 1000.05 → 1000, 세액 100 / ZERO는 세액 0
    assert amounts([("3", "333.35", "TAXABLE"), ("1", "5", "ZERO")]) == (1005, 100)
    assert amounts([("1", "4.5", "TAXABLE")]) == (5, 1)  # 4.5→5, 0.5→1
    print("ok")
