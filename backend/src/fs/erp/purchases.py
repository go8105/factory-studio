"""E-11 매입 전표 (FS-019f). 구매발주·입고검수 없이 원재료 매입만 직접 등록한다(그 앞은 WMS 범위).

- draft에서만 머리글·명세 수정/삭제. 명세 금액은 서버가 revenue.line_amounts로 계산(과세 10%, 영세·면세 0%).
- 확정: 공급처(SUPPLIER), 명세 1개 이상, 잠금 안에서 명세를 현재 과세구분으로 다시 계산해 머리글 합계와 맞춘다.
  만기 = 직접 입력 우선, 없으면 매입일 + 결제일수, 조건도 없으면 NULL. 같은 트랜잭션에서 채무 1건(원금 = 합계).
- 취소: 작성 중이면 바로, 확정 후에는 지급 소명 0행일 때만. 채무 원금은 남기고 유효 집계에서 뺀다.
  매입 취소는 세금계산서와 무관하다(계산서는 매출 전용).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp.revenue import line_amounts
from fs.erp.sales import _S, MODULE, _action, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

INVOICE_SQL = """
SELECT pi.id, pi.invoice_no, pi.partner_id, pi.invoice_date, pi.due_date, pi.currency,
       pi.supply_amount, pi.tax_amount, pi.total_amount, pi.status, pi.confirmed_at,
       pi.cancelled_at, pi.cancel_reason, pi.created_at, pv.id payable_id,
       coalesce((SELECT sum(a.amount) FROM erp.payment_apply a
         WHERE a.workspace_id=pv.workspace_id AND a.generation_id=pv.generation_id
           AND a.payable_id=pv.id), 0) applied_amount,
       CASE WHEN pi.status='cancelled' THEN 'ALREADY_CANCELLED'
            WHEN EXISTS (SELECT 1 FROM erp.payment_apply a
              WHERE a.workspace_id=pv.workspace_id AND a.generation_id=pv.generation_id
                AND a.payable_id=pv.id) THEN 'PAYMENT_APPLIED'
       END cancel_blocked_reason
FROM erp.purchase_invoice pi
LEFT JOIN erp.payable pv ON pv.workspace_id=pi.workspace_id
 AND pv.generation_id=pi.generation_id AND pv.purchase_invoice_id=pi.id
WHERE pi.workspace_id=:w AND pi.generation_id=:g"""
LINE_SQL = f"""
SELECT id, purchase_invoice_id, line_no, item_id, quantity, unit, unit_price,
       supply_amount, tax_amount, total_amount
FROM erp.purchase_invoice_line WHERE {_S} AND purchase_invoice_id = ANY(:ids)
ORDER BY purchase_invoice_id, line_no"""
BLOCKED = {
    "ALREADY_CANCELLED": "이미 취소된 매입입니다.",
    "PAYMENT_APPLIED": "지급 소명이 있어 취소할 수 없습니다. 소명을 먼저 취소하세요.",
}


def _invoices(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        INVOICE_SQL + where + " ORDER BY pi.invoice_date DESC, pi.invoice_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(connection, LINE_SQL, {**_s(scoped), "ids": [h["id"] for h in heads]})
    for head in heads:
        head["lines"] = [x for x in lines if x["purchaseInvoiceId"] == head["id"]]
    return heads


def _invoice(connection, scoped, invoice_id: int, lock: bool = False) -> dict[str, Any]:
    if lock:  # 매입 전표는 잠금 순서 6단계(원천 거래)
        connection.execute(
            text(
                f"SELECT id FROM erp.purchase_invoice WHERE {_S} AND id=:id FOR UPDATE"
            ),
            {**_s(scoped), "id": invoice_id},
        )
    found = _invoices(connection, scoped, " AND pi.id=:id", id=invoice_id)
    if not found:
        raise not_found()
    return found[0]


def _draft(connection, scoped, invoice_id: int) -> dict[str, Any]:
    invoice = _invoice(connection, scoped, invoice_id, lock=True)
    if invoice["status"] != "draft":
        raise _locked("작성 중인 매입만 고칠 수 있습니다.", "INVOICE_LOCKED")
    return invoice


def list_invoices(context):
    with _read() as connection:
        return _invoices(connection, read_scope(connection, context, MODULE))


def _supplier(connection, scoped, partner_id: int):
    row = connection.execute(
        text(
            "SELECT partner_kind, is_active, payment_term_days FROM erp.partner "
            f"WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "id": partner_id},
    ).first()
    if row is None or row.partner_kind != "SUPPLIER" or not row.is_active:
        raise invalid("partner_id", "현재 공간의 사용 중인 공급처를 선택하세요.")
    return row


def _no_free(connection, scoped, no: str, invoice_id=None) -> None:
    if _exists(
        connection,
        scoped,
        f"SELECT 1 FROM erp.purchase_invoice WHERE {_S} AND invoice_no=:no "
        "AND id IS DISTINCT FROM :id",
        no=no,
        id=invoice_id,
    ):
        raise invalid("invoice_no", "이미 사용 중인 전표번호입니다.")


def create_invoice(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _no_free(connection, scoped, values["invoice_no"])
        _supplier(connection, scoped, values["partner_id"])
        invoice_id = connection.execute(
            text(
                "INSERT INTO erp.purchase_invoice (workspace_id, generation_id, "
                "invoice_no, partner_id, invoice_date, due_date) VALUES "
                "(:w, :g, :invoice_no, :partner_id, :invoice_date, :due_date) RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return _invoice(connection, scoped, invoice_id), "purchase_invoice", invoice_id

    return _action(context, "erp.purchase_invoice.create", key, values, run, 201)


def update_invoice(context, invoice_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        _draft(connection, scoped, invoice_id)
        if "invoice_no" in values:
            _no_free(connection, scoped, values["invoice_no"], invoice_id)
        if "partner_id" in values:
            _supplier(connection, scoped, values["partner_id"])
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(
                f"UPDATE erp.purchase_invoice SET {assignments} WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), **values, "id": invoice_id},
        )
        return _invoice(connection, scoped, invoice_id), "purchase_invoice", invoice_id

    body = {"id": invoice_id, **values}
    return _action(context, "erp.purchase_invoice.update", key, body, run)


def _items(connection, scoped) -> dict[int, dict[str, Any]]:
    """원재료 품목과 허용 단위(기준 단위 + 단위환산 원 단위)."""
    items = {
        r.id: {
            "type": r.item_type,
            "tax": r.tax_category,
            "units": {r.base_unit},
            "active": r.is_active,
        }
        for r in connection.execute(
            text(
                "SELECT id, item_type, tax_category, base_unit, is_active FROM erp.item "
                f"WHERE {_S}"
            ),
            _s(scoped),
        )
    }
    for r in connection.execute(
        text(f"SELECT item_id, from_unit FROM erp.item_unit_conversion WHERE {_S}"),
        _s(scoped),
    ):
        items[r.item_id]["units"].add(r.from_unit)
    return items


def _priced(line: dict[str, Any], tax: str) -> dict[str, Any]:
    supply, tax_amount = line_amounts(line["quantity"], line["unit_price"], tax)
    return {
        **line,
        "supply_amount": supply,
        "tax_amount": tax_amount,
        "total_amount": supply + tax_amount,
    }


def _write_lines(connection, scoped, invoice_id: int, rows: list[dict]) -> None:
    """명세를 통째로 바꾸고 머리글 합계를 명세 합계로 맞춘다."""
    connection.execute(
        text(
            f"DELETE FROM erp.purchase_invoice_line WHERE {_S} AND purchase_invoice_id=:id"
        ),
        {**_s(scoped), "id": invoice_id},
    )
    for n, row in enumerate(rows, 1):
        connection.execute(
            text(
                "INSERT INTO erp.purchase_invoice_line (workspace_id, generation_id, "
                "purchase_invoice_id, line_no, item_id, quantity, unit, unit_price, "
                "supply_amount, tax_amount, total_amount) VALUES (:w, :g, :id, :n, "
                ":item_id, :quantity, :unit, :unit_price, :supply_amount, :tax_amount, "
                ":total_amount)"
            ),
            {**_s(scoped), **row, "id": invoice_id, "n": n},
        )
    supply = sum((r["supply_amount"] for r in rows), Decimal(0))
    tax = sum((r["tax_amount"] for r in rows), Decimal(0))
    connection.execute(
        text(
            "UPDATE erp.purchase_invoice SET supply_amount=:s, tax_amount=:t, "
            f"total_amount=:total WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "s": supply, "t": tax, "total": supply + tax, "id": invoice_id},
    )


def set_lines(context, invoice_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        _draft(connection, scoped, invoice_id)
        items = _items(connection, scoped)
        rows = []
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            item = items.get(line["item_id"])
            if item is None or not item["active"]:
                raise invalid("lines", where + "사용 중인 품목을 선택하세요.")
            if item["type"] != "raw":
                raise invalid("lines", where + "원재료 품목만 매입할 수 있습니다.")
            if line["unit"] not in item["units"]:
                raise invalid(
                    "lines",
                    where + f"단위는 {', '.join(sorted(item['units']))} 중 하나입니다.",
                )
            if Decimal(line["quantity"]) <= 0:
                raise invalid("lines", where + "수량은 0보다 커야 합니다.")
            rows.append(_priced(line, item["tax"]))
        _write_lines(connection, scoped, invoice_id, rows)
        return _invoice(connection, scoped, invoice_id), "purchase_invoice", invoice_id

    body = {"id": invoice_id, "lines": lines}
    return _action(context, "erp.purchase_invoice.lines", key, body, run)


def confirm_invoice(context, invoice_id: int, key: str):
    def run(connection, scoped):
        invoice = _draft(connection, scoped, invoice_id)
        partner = _supplier(connection, scoped, invoice["partnerId"])
        if not invoice["lines"]:
            raise _locked("명세가 없는 매입은 확정할 수 없습니다.", "EMPTY_INVOICE")
        # 확정 순간의 과세구분으로 다시 계산해 머리글과 맞춘다(이후 마스터 변경은 소급하지 않는다).
        items = _items(connection, scoped)
        rows = [
            _priced(
                {
                    "item_id": x["itemId"],
                    "quantity": x["quantity"],
                    "unit": x["unit"],
                    "unit_price": x["unitPrice"],
                },
                items[x["itemId"]]["tax"],
            )
            for x in invoice["lines"]
        ]
        _write_lines(connection, scoped, invoice_id, rows)
        connection.execute(
            text(
                "UPDATE erp.purchase_invoice SET status='confirmed', "
                "confirmed_at=clock_timestamp(), "
                "due_date=coalesce(due_date, invoice_date + CAST(:days AS integer)) "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "days": partner.payment_term_days, "id": invoice_id},
        )
        connection.execute(
            text(
                "INSERT INTO erp.payable (workspace_id, generation_id, purchase_invoice_id, "
                "partner_id, amount, due_date) SELECT workspace_id, generation_id, id, "
                f"partner_id, total_amount, due_date FROM erp.purchase_invoice "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": invoice_id},
        )
        return _invoice(connection, scoped, invoice_id), "purchase_invoice", invoice_id

    return _action(
        context, "erp.purchase_invoice.confirm", key, {"id": invoice_id}, run
    )


def delete_invoice(context, invoice_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(connection, scoped, invoice_id)
        for sql in (
            f"DELETE FROM erp.purchase_invoice_line WHERE {_S} AND purchase_invoice_id=:id",
            f"DELETE FROM erp.purchase_invoice WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": invoice_id})
        return {}, "purchase_invoice", invoice_id

    _action(context, "erp.purchase_invoice.delete", key, {"id": invoice_id}, run, 204)


def cancel_invoice(context, invoice_id: int, reason: str, key: str):
    def run(connection, scoped):
        _invoice(connection, scoped, invoice_id, lock=True)  # 매입(6)
        connection.execute(  # → 채무(7). 지급 소명 추가도 이 순서로 잠근다.
            text(
                f"SELECT id FROM erp.payable WHERE {_S} AND purchase_invoice_id=:id "
                "FOR UPDATE"
            ),
            {**_s(scoped), "id": invoice_id},
        )
        blocked = _invoice(connection, scoped, invoice_id)["cancelBlockedReason"]
        if blocked:
            raise _locked(BLOCKED[blocked], blocked)
        connection.execute(
            text(
                "UPDATE erp.purchase_invoice SET status='cancelled', "
                f"cancelled_at=clock_timestamp(), cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": invoice_id, "reason": reason},
        )
        return _invoice(connection, scoped, invoice_id), "purchase_invoice", invoice_id

    body = {"id": invoice_id, "reason": reason}
    return _action(context, "erp.purchase_invoice.cancel", key, body, run)
