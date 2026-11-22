"""자동 분개와 회계 미반영 현황 (DSN-11 F43·F44·Q3).

업무를 확정할 때 **같은 트랜잭션에서** 분개 규칙(E-18)으로 전표를 만든다. 만들지 못하는 이유는
둘뿐이다 — 규칙이 없거나 그 달이 마감됐다. 그때는 **업무만 확정되고 전표는 비며**, 그 사실이
회계 미반영 현황(E-31)에 남아 나중에 일괄 반영된다. 업무를 막지 않는 것이 핵심이다:
회계가 준비되지 않았다고 물건이 안 나가지는 않는다.

- 원천 1건당 살아 있는 전표 1건(`UK_PARTIAL`). 역분개된 전표는 세지 않으므로 다시 만들 수 있다.
- 원천 문서마다 질의 하나를 둔다. 그 질의가 **확정 시 생성**과 **미반영 목록**에 함께 쓰인다 —
  두 벌로 적으면 한쪽만 고쳐져 목록과 생성이 어긋난다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.erp.sales import _S, _s

KST = "'Asia/Seoul'"
# 규칙이 쓰는 금액 기준. 원천마다 아래 질의가 같은 이름으로 돌려준다.
BASES = ("SUPPLY", "TAX", "TOTAL", "APPLY", "AMOUNT")


@dataclass(frozen=True)
class Source:
    """자동 분개의 원천 하나. `sql`은 확정된 문서를 한 줄씩 준다."""

    kind: str  # journal_entry.source_kind
    entry_kind: str  # journal_entry.entry_kind
    label: str
    # 돌려줄 칸: id, entry_date, partner_id, department_id, supply, tax, total, apply, ref
    sql: str
    # 문서번호가 전표 1건을 가리키는가. 수금 한 건이 여러 채권에 소명되면 번호가 겹치므로
    # 그때는 `source_ref`를 비운다(겹침 금지 인덱스가 문서번호에도 걸려 있다).
    unique_ref: bool = True


SALE = Source(
    "sales_record",
    "SALE",
    "매출",
    f"""
SELECT r.id, (r.recognized_at AT TIME ZONE {KST})::date entry_date, r.partner_id,
       NULL::bigint department_id, r.supply_amount supply, r.tax_amount tax,
       r.total_amount total, 0 apply, sh.shipment_no ref
FROM erp.sales_record r
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id
 AND sh.generation_id=r.generation_id AND sh.id=r.shipment_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.cancelled_at IS NULL""",
)
PURCHASE = Source(
    "purchase_invoice",
    "PURCHASE",
    "매입",
    """
SELECT p.id, p.invoice_date entry_date, p.partner_id, p.department_id,
       p.supply_amount supply, p.tax_amount tax, p.total_amount total, 0 apply,
       p.invoice_no ref
FROM erp.purchase_invoice p
WHERE p.workspace_id=:w AND p.generation_id=:g AND p.status='confirmed'
  AND p.invoice_kind <> 'SUBCONTRACT'""",
)
SUBCONTRACT = Source(
    "purchase_invoice",
    "SUBCONTRACT",
    "외주비",
    """
SELECT p.id, p.invoice_date entry_date, p.partner_id, p.department_id,
       p.supply_amount supply, p.tax_amount tax, p.total_amount total, 0 apply,
       p.invoice_no ref
FROM erp.purchase_invoice p
WHERE p.workspace_id=:w AND p.generation_id=:g AND p.status='confirmed'
  AND p.invoice_kind = 'SUBCONTRACT'""",
)
SALES_RETURN = Source(
    "sales_return",
    "SALES_RETURN",
    "판매 반품",
    """
SELECT t.id, t.returned_on entry_date, t.partner_id, NULL::bigint department_id,
       t.supply_amount supply, t.tax_amount tax, t.total_amount total, 0 apply,
       t.return_no ref
FROM erp.sales_return t
WHERE t.workspace_id=:w AND t.generation_id=:g AND t.status='confirmed'""",
)
PURCHASE_RETURN = Source(
    "purchase_return",
    "PURCHASE_RETURN",
    "구매 반품",
    """
SELECT t.id, t.returned_on entry_date, t.partner_id, NULL::bigint department_id,
       t.supply_amount supply, t.tax_amount tax, t.total_amount total, 0 apply,
       t.return_no ref
FROM erp.purchase_return t
WHERE t.workspace_id=:w AND t.generation_id=:g AND t.status='confirmed'""",
)
RECEIPT = Source(
    "receipt_apply",
    "RECEIPT",
    "수금 소명",
    f"""
SELECT a.id, (a.applied_at AT TIME ZONE {KST})::date entry_date, a.partner_id,
       NULL::bigint department_id, 0 supply, 0 tax, a.amount total, a.amount apply,
       c.receipt_no ref
FROM erp.receipt_apply a
JOIN erp.receipt c ON c.workspace_id=a.workspace_id AND c.generation_id=a.generation_id
 AND c.id=a.receipt_id
WHERE a.workspace_id=:w AND a.generation_id=:g""",
    unique_ref=False,
)
PAYMENT = Source(
    "payment_apply",
    "PAYMENT",
    "지급 소명",
    f"""
SELECT a.id, (a.applied_at AT TIME ZONE {KST})::date entry_date, a.partner_id,
       NULL::bigint department_id, 0 supply, 0 tax, a.amount total, a.amount apply,
       c.payment_no ref
FROM erp.payment_apply a
JOIN erp.payment c ON c.workspace_id=a.workspace_id AND c.generation_id=a.generation_id
 AND c.id=a.payment_id
WHERE a.workspace_id=:w AND a.generation_id=:g""",
    unique_ref=False,
)
EXPENSE_CLAIM = Source(
    "expense_claim",
    "EXPENSE_CLAIM",
    "지출결의",
    """
SELECT c.id, c.claimed_on entry_date, NULL::bigint partner_id, c.department_id,
       0 supply, 0 tax, c.total_amount total, 0 apply, c.claim_no ref
FROM erp.expense_claim c
WHERE c.workspace_id=:w AND c.generation_id=:g AND c.status='confirmed'""",
)
SOURCES = (
    SALE,
    PURCHASE,
    SUBCONTRACT,
    SALES_RETURN,
    PURCHASE_RETURN,
    RECEIPT,
    PAYMENT,
    EXPENSE_CLAIM,
)
BY_KEY = {f"{s.kind}:{s.entry_kind}": s for s in SOURCES}
# 막힌 이유. 업무는 이미 확정됐고 전표만 없다.
NO_RULE = "NO_RULE"
MONTH_CLOSED = "MONTH_CLOSED"
NO_ACCOUNT = "NO_ACCOUNT"
REASONS = {
    NO_RULE: "분개 규칙이 없습니다(E-18).",
    MONTH_CLOSED: "그 달이 마감됐습니다.",
    NO_ACCOUNT: "규칙이 가리키는 계정이 사용 중지됐습니다.",
}


def as_date(value) -> date:
    """날짜는 SQL에서 date로, 화면 응답에서 ISO 문자열로 온다. 한 가지로 맞춘다."""
    return date.fromisoformat(value) if isinstance(value, str) else value


def month_closed(connection, scoped, entry_date) -> bool:
    """회계 월이 닫혔는가. 기간 행이 없으면 열린 것으로 본다(1f에서 닫는 화면이 생긴다)."""
    return bool(
        connection.execute(
            text(
                f"SELECT 1 FROM erp.fiscal_period WHERE {_S} "
                "AND period_month=to_char(CAST(:on AS date), 'YYYY-MM') AND status='closed'"
            ),
            {**_s(scoped), "on": entry_date},
        ).first()
    )


def _rules(connection, scoped, entry_kind: str) -> list[Any]:
    return connection.execute(
        text(
            "SELECT r.line_no, r.entry_side, r.amount_basis, r.account_id, r.account_code, "
            "       a.is_active, a.requires_partner, a.requires_department "
            "FROM erp.posting_rule r JOIN erp.account a ON a.workspace_id=r.workspace_id "
            " AND a.generation_id=r.generation_id AND a.id=r.account_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.transaction_kind=:kind "
            "ORDER BY r.line_no"
        ),
        {**_s(scoped), "kind": entry_kind},
    ).all()


def _next_entry_no(connection, scoped, entry_date) -> str:
    entry_date = as_date(entry_date)
    taken = connection.execute(
        text(
            f"SELECT entry_no FROM erp.journal_entry WHERE {_S} AND entry_no LIKE :like "
            "ORDER BY entry_no DESC LIMIT 1"
        ),
        {**_s(scoped), "like": f"JV-{entry_date:%Y%m%d}-%"},
    ).scalar_one_or_none()
    serial = int(taken.rsplit("-", 1)[1]) + 1 if taken else 1
    return f"JV-{entry_date:%Y%m%d}-{serial:03d}"


def write_entry(
    connection,
    scoped,
    *,
    entry_kind: str,
    entry_date,
    lines: list[dict[str, Any]],
    description: str,
    source_kind: str | None = None,
    source_id: int | None = None,
    source_ref: str | None = None,
    department_id: int | None = None,
    status: str = "confirmed",
    reversal_of_id: int | None = None,
) -> int:
    """전표 한 건을 쓴다. 차대 일치는 부르는 쪽이 이미 확인했다."""
    entry_id = connection.execute(
        text(
            "INSERT INTO erp.journal_entry (workspace_id, generation_id, entry_no, "
            "entry_date, entry_kind, source_kind, source_id, source_ref, description, "
            "department_id, status, confirmed_at, reversal_of_id) VALUES (:w, :g, :no, "
            ":on, :kind, :source_kind, :source_id, :source_ref, :description, "
            ":department_id, :status, "
            "CASE WHEN CAST(:status AS varchar)='draft' THEN NULL "
            "ELSE clock_timestamp() END, :reversal) "
            "RETURNING id"
        ),
        {
            **_s(scoped),
            "no": _next_entry_no(connection, scoped, entry_date),
            "on": entry_date,
            "kind": entry_kind,
            "source_kind": source_kind,
            "source_id": source_id,
            "source_ref": source_ref,
            "description": description,
            "department_id": department_id,
            "status": status,
            "reversal": reversal_of_id,
        },
    ).scalar_one()
    for n, line in enumerate(lines, 1):
        connection.execute(
            text(
                "INSERT INTO erp.journal_line (workspace_id, generation_id, "
                "journal_entry_id, line_no, account_id, side, amount, partner_id, "
                "department_id, project_id, memo) VALUES (:w, :g, :entry, :n, "
                ":account_id, :side, :amount, :partner_id, :department_id, "
                ":project_id, :memo)"
            ),
            {
                **_s(scoped),
                "entry": entry_id,
                "n": n,
                # 이름은 라인 dict의 키와 같아야 한다. 어긋나면 관리항목이 조용히 비워진다.
                "partner_id": None,
                "department_id": None,
                "project_id": None,
                "memo": None,
                **line,
            },
        )
    return entry_id


def _amounts(row) -> dict[str, Decimal]:
    total = Decimal(str(row.total))
    return {
        "SUPPLY": Decimal(str(row.supply)),
        "TAX": Decimal(str(row.tax)),
        "TOTAL": total,
        "APPLY": Decimal(str(row.apply)),
        "AMOUNT": total,
    }


def build(connection, scoped, source: Source, row) -> tuple[list[dict], str | None]:
    """규칙으로 전표 라인을 만든다. 못 만들면 (빈 목록, 이유)."""
    rules = _rules(connection, scoped, source.entry_kind)
    if not rules:
        return [], NO_RULE
    if any(not r.is_active for r in rules):
        return [], NO_ACCOUNT
    amounts = _amounts(row)
    lines = []
    for rule in rules:
        amount = amounts[rule.amount_basis]
        if amount <= 0:
            continue  # 영세·면세 매출의 세액처럼 0인 줄은 넣지 않는다(금액 > 0 제약).
        lines.append(
            {
                "account_id": rule.account_id,
                "side": rule.entry_side,
                "amount": amount,
                "partner_id": row.partner_id if rule.requires_partner else None,
                "department_id": row.department_id
                if rule.requires_department
                else None,
            }
        )
    if len(lines) < 2:
        return [], NO_RULE
    debit = sum((x["amount"] for x in lines if x["side"] == "DEBIT"), Decimal(0))
    credit = sum((x["amount"] for x in lines if x["side"] == "CREDIT"), Decimal(0))
    if debit != credit or debit <= 0:
        return [], NO_RULE
    return lines, None


def post(connection, scoped, source: Source, source_id: int) -> str | None:
    """원천 1건을 전표로 만든다. 못 만들면 이유를 돌려주고 업무는 그대로 둔다."""
    if source is EXPENSE_CLAIM:
        # 지출결의는 규칙이 아니라 **명세가 고른 비용 계정**으로 전표를 만든다(F46).
        from fs.erp import expenses

        if _already(connection, scoped, source, source_id):
            return None
        return expenses.post_claim(connection, scoped, source_id)
    row = connection.execute(
        text(_with_id(source.sql)),
        {**_s(scoped), "id": source_id},
    ).first()
    if row is None:
        return None
    if _already(connection, scoped, source, source_id):
        return None
    if month_closed(connection, scoped, row.entry_date):
        return MONTH_CLOSED
    lines, reason = build(connection, scoped, source, row)
    if reason:
        return reason
    write_entry(
        connection,
        scoped,
        entry_kind=source.entry_kind,
        entry_date=row.entry_date,
        lines=lines,
        description=f"{source.label} {row.ref}",
        source_kind=source.kind,
        source_id=source_id,
        source_ref=row.ref if source.unique_ref else None,
        department_id=row.department_id,
    )
    return None


def _with_id(sql: str) -> str:
    """원천 질의에 id 조건을 더한다. 바깥 질의로 감싸 ORDER BY·GROUP BY에 영향을 주지 않는다."""
    return f"SELECT * FROM ({sql}) src WHERE src.id=:id"


def _already(connection, scoped, source: Source, source_id: int) -> bool:
    return bool(
        connection.execute(
            text(
                f"SELECT 1 FROM erp.journal_entry WHERE {_S} AND source_kind=:kind "
                "AND source_id=:id AND entry_kind=:entry_kind AND status <> 'reversed'"
            ),
            {
                **_s(scoped),
                "kind": source.kind,
                "id": source_id,
                "entry_kind": source.entry_kind,
            },
        ).first()
    )


def source_exists(connection, scoped, source_kind: str, source_id: int) -> bool:
    """그 원천 문서가 이 공간에 있는가. 없으면 '전표가 아직 없다'가 아니라 404다."""
    return any(
        connection.execute(
            text(_with_id(source.sql)), {**_s(scoped), "id": source_id}
        ).first()
        is not None
        for source in SOURCES
        if source.kind == source_kind
    )


def pending(connection, scoped) -> list[dict[str, Any]]:
    """확정했는데 전표가 없는 업무. 왜 없는지도 함께 말한다(E-31)."""
    out = []
    for source in SOURCES:
        rows = connection.execute(
            text(
                f"SELECT * FROM ({source.sql}) src WHERE NOT EXISTS ("
                "  SELECT 1 FROM erp.journal_entry j WHERE j.workspace_id=:w "
                "   AND j.generation_id=:g AND j.source_kind=:kind AND j.source_id=src.id "
                "   AND j.entry_kind=:entry_kind AND j.status <> 'reversed')"
                " ORDER BY src.entry_date, src.id"
            ),
            {**_s(scoped), "kind": source.kind, "entry_kind": source.entry_kind},
        ).all()
        for row in rows:
            if source is EXPENSE_CLAIM:
                from fs.erp import expenses

                reason = expenses.claim_reason(connection, scoped, row.id)
            elif month_closed(connection, scoped, row.entry_date):
                reason = MONTH_CLOSED
            else:
                _, reason = build(connection, scoped, source, row)
            out.append(
                {
                    "sourceKind": source.kind,
                    "entryKind": source.entry_kind,
                    "sourceId": row.id,
                    "label": source.label,
                    "ref": row.ref,
                    "entryDate": row.entry_date.isoformat(),
                    "amount": str(row.total),
                    "reason": reason,
                    "reasonText": REASONS.get(reason, "") if reason else "",
                    "postable": reason is None,
                }
            )
    return sorted(out, key=lambda x: (x["entryDate"], x["label"], x["ref"]))
