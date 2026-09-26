"""E-14 분개 미리보기 (FS-019g). 저장하지 않고 조회 때마다 분개 규칙(E-18)으로 계산한다.

- 4거래 유형: SALES(매출 1건) · PURCHASE(확정 매입 1건) · RECEIPT/PAYMENT(소명 1행 = 분개 1세트).
- 금액 기준(amount_basis): TOTAL·SUPPLY·TAX는 원천 금액, APPLY는 소명액. 수금·지급 원액은 분개하지 않는다.
- 미소명 잔여는 분개 라인에 넣지 않고 `unapplied`로 따로 준다(선수금·선급금 계정 없음).
- 취소된 매출·매입, 작성 중 매입은 미리보기 대상이 아니다(409 NOT_POSTABLE).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp.receipts import PAYABLE, RECEIVABLE
from fs.erp.sales import _S, MODULE, _locked, _s
from fs.erp.service import _read, not_found

RULE_KIND = {
    "SALES": "SALE",
    "RECEIPT": "RECEIPT",
    "PURCHASE": "PURCHASE",
    "PAYMENT": "PAYMENT",
}
RULES_SQL = """
SELECT r.line_no, r.entry_side, r.account_code, a.account_name, r.amount_basis
FROM erp.posting_rule r
JOIN erp.account a ON a.workspace_id=r.workspace_id AND a.generation_id=r.generation_id
 AND a.id=r.account_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.transaction_kind=:kind
ORDER BY r.line_no"""


def _source(connection, scoped, kind: str, row_id: int) -> dict[str, Any]:
    """금액 기준별 금액과 화면 설명. 없으면 404, 대상이 아니면 409."""
    params = {**_s(scoped), "id": row_id}
    if kind == "SALES":
        row = connection.execute(
            text(
                "SELECT r.supply_amount, r.tax_amount, r.total_amount, r.cancelled_at, "
                "sh.shipment_no doc FROM erp.sales_record r JOIN erp.shipment sh "
                "ON sh.workspace_id=r.workspace_id AND sh.generation_id=r.generation_id "
                "AND sh.id=r.shipment_id WHERE r.workspace_id=:w AND r.generation_id=:g "
                "AND r.id=:id"
            ),
            params,
        ).first()
        if row is None:
            raise not_found()
        if row.cancelled_at is not None:
            raise _locked("취소된 매출은 분개하지 않습니다.", "NOT_POSTABLE")
        return {
            "doc": row.doc,
            "SUPPLY": row.supply_amount,
            "TAX": row.tax_amount,
            "TOTAL": row.total_amount,
        }
    if kind == "PURCHASE":
        row = connection.execute(
            text(
                "SELECT supply_amount, tax_amount, total_amount, status, invoice_no doc "
                f"FROM erp.purchase_invoice WHERE {_S} AND id=:id"
            ),
            params,
        ).first()
        if row is None:
            raise not_found()
        if row.status != "confirmed":
            raise _locked("확정된 매입만 분개합니다.", "NOT_POSTABLE")
        return {
            "doc": row.doc,
            "SUPPLY": row.supply_amount,
            "TAX": row.tax_amount,
            "TOTAL": row.total_amount,
        }
    side = RECEIVABLE if kind == "RECEIPT" else PAYABLE
    row = connection.execute(
        text(
            f"SELECT a.amount, c.{side.money_no} doc, c.amount - (SELECT sum(x.amount) "
            f"FROM erp.{side.apply} x WHERE x.workspace_id=c.workspace_id "
            f"AND x.generation_id=c.generation_id AND x.{side.money_fk}=c.id) unapplied "
            f"FROM erp.{side.apply} a JOIN erp.{side.money} c "
            "ON c.workspace_id=a.workspace_id AND c.generation_id=a.generation_id "
            f"AND c.id=a.{side.money_fk} WHERE a.workspace_id=:w "
            "AND a.generation_id=:g AND a.id=:id"
        ),
        params,
    ).first()
    if row is None:
        raise not_found()
    return {"doc": row.doc, "APPLY": row.amount, "unapplied": row.unapplied}


def preview(context, kind: str, row_id: int) -> dict[str, Any]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        source = _source(connection, scoped, kind, row_id)
        rules = connection.execute(
            text(RULES_SQL), {**_s(scoped), "kind": RULE_KIND[kind]}
        ).all()
    lines = [
        {
            "lineNo": r.line_no,
            "entrySide": r.entry_side,
            "accountCode": r.account_code,
            "accountName": r.account_name,
            "amountBasis": r.amount_basis,
            "amount": str(source[r.amount_basis]),
        }
        for r in rules
    ]
    total = {
        side: sum(
            (Decimal(x["amount"]) for x in lines if x["entrySide"] == side), Decimal(0)
        )
        for side in ("DEBIT", "CREDIT")
    }
    return {
        "kind": kind,
        "id": row_id,
        "doc": source["doc"],
        "lines": lines,
        "debitTotal": str(total["DEBIT"]),
        "creditTotal": str(total["CREDIT"]),
        "balanced": total["DEBIT"] == total["CREDIT"],
        # 미소명 잔여(수금·지급)는 분개 표 밖 안내. 매출·매입은 null.
        "unapplied": None if "unapplied" not in source else str(source["unapplied"]),
    }
