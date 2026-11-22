"""E-29 지출결의서 (DSN-11 F46).

청구자·부서·지급 방법과 비용 계정별 명세를 적고 확정하면 **비용 전표**가 같은 트랜잭션에서 나온다.
규칙(E-18)의 EXPENSE_CLAIM은 지급 방법의 상대 계정을 정하는 데만 쓴다 — 차변 비용 계정은
명세가 직접 고르기 때문이다(한 결의서에 복리후생비와 여비교통비가 섞인다).

GW 결재 상태는 **읽기 전용 배지**다. 결재가 없어도 확정할 수 있다(E-11과 같은 규칙, DSN-31 F44 범위 밖).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import posting
from fs.erp.procurement import _next_no
from fs.erp.sales import _S, MODULE, _action, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

# 지급 방법별 대변 계정. 규칙에 없으면 확정하지 못하고 미반영으로 남는다.
PAY_ACCOUNT = {"BANK": "BANK", "CARD": "CARD_PAYABLE", "CASH": "BANK"}
CLAIM_SQL = """
SELECT c.id, c.claim_no, c.claimed_on, c.employee_id, c.department_id, c.pay_method,
       c.currency, c.total_amount, c.status, c.confirmed_at, c.cancelled_at,
       c.cancel_reason, e.code employee_code, e.name employee_name, d.code department_code
FROM erp.expense_claim c
JOIN erp.employee e ON e.workspace_id=c.workspace_id AND e.generation_id=c.generation_id
 AND e.id=c.employee_id
JOIN erp.department d ON d.workspace_id=c.workspace_id
 AND d.generation_id=c.generation_id AND d.id=c.department_id
WHERE c.workspace_id=:w AND c.generation_id=:g"""
LINE_SQL = """
SELECT l.id, l.expense_claim_id, l.line_no, l.account_id, l.amount, l.project_id, l.memo,
       a.account_code, a.account_name, p.code project_code
FROM erp.expense_claim_line l
JOIN erp.account a ON a.workspace_id=l.workspace_id AND a.generation_id=l.generation_id
 AND a.id=l.account_id
LEFT JOIN erp.project p ON p.workspace_id=l.workspace_id
 AND p.generation_id=l.generation_id AND p.id=l.project_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.expense_claim_id = ANY(:ids)
ORDER BY l.expense_claim_id, l.line_no"""


def _claims(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        CLAIM_SQL + where + " ORDER BY c.claimed_on DESC, c.claim_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(connection, LINE_SQL, {**_s(scoped), "ids": [h["id"] for h in heads]})
    for head in heads:
        head["lines"] = [x for x in lines if x["expenseClaimId"] == head["id"]]
    return heads


def _claim(connection, scoped, claim_id: int, lock: bool = False):
    if lock:
        connection.execute(
            text(f"SELECT id FROM erp.expense_claim WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": claim_id},
        )
    found = _claims(connection, scoped, " AND c.id=:id", id=claim_id)
    if not found:
        raise not_found()
    return found[0]


def list_claims(context):
    with _read() as connection:
        return _claims(connection, read_scope(connection, context, MODULE))


def _master(connection, scoped, table: str, row_id: int, field: str) -> None:
    if not connection.execute(
        text(f"SELECT 1 FROM erp.{table} WHERE {_S} AND id=:id AND is_active"),
        {**_s(scoped), "id": row_id},
    ).first():
        raise invalid(field, "현재 공간의 사용 중인 대상을 선택하세요.")


def create_claim(context, values: dict[str, Any], key: str):
    """합계 > 0이 DB 제약이라 머리글과 첫 명세를 함께 받는다."""

    def run(connection, scoped):
        _master(connection, scoped, "employee", values["employee_id"], "employee_id")
        _master(
            connection, scoped, "department", values["department_id"], "department_id"
        )
        lines = values["lines"]
        total = _checked_lines(connection, scoped, lines)
        claim_no = _next_no(connection, scoped, "expense_claim", "claim_no", "EC")
        header = {k: v for k, v in values.items() if k != "lines"}
        claim_id = connection.execute(
            text(
                "INSERT INTO erp.expense_claim (workspace_id, generation_id, claim_no, "
                "claimed_on, employee_id, department_id, pay_method, total_amount) "
                "VALUES (:w, :g, :no, :claimed_on, :employee_id, :department_id, "
                ":pay_method, :total) RETURNING id"
            ),
            {**_s(scoped), **header, "no": claim_no, "total": total},
        ).scalar_one()
        _write_lines(connection, scoped, claim_id, lines)
        return _claim(connection, scoped, claim_id), "expense_claim", claim_id

    return _action(context, "erp.expense_claim.create", key, values, run, 201)


def _checked_lines(connection, scoped, lines: list[dict]) -> Decimal:
    """비용 계정만, 금액은 양수, 합계는 0보다 커야 한다(DB 제약과 같은 규칙)."""
    accounts = {
        r.id: r
        for r in connection.execute(
            text(f"SELECT id, account_class, is_active FROM erp.account WHERE {_S}"),
            _s(scoped),
        )
    }
    total = Decimal(0)
    for n, line in enumerate(lines, 1):
        where = f"{n}번째 라인: "
        account = accounts.get(line["account_id"])
        if account is None or not account.is_active:
            raise invalid("lines", where + "사용 중인 계정을 선택하세요.")
        if account.account_class not in ("EXPENSE", "MFG_COST"):
            raise invalid(
                "lines", where + "비용 계정(판매비와관리비·제조원가)만 쓸 수 있습니다."
            )
        if Decimal(line["amount"]) <= 0:
            raise invalid("lines", where + "금액은 0보다 커야 합니다.")
        total += Decimal(line["amount"])
    if total <= 0:
        raise invalid("lines", "명세가 한 줄 이상 있어야 합니다.")
    return total


def _write_lines(connection, scoped, claim_id: int, lines: list[dict]) -> None:
    connection.execute(
        text(f"DELETE FROM erp.expense_claim_line WHERE {_S} AND expense_claim_id=:id"),
        {**_s(scoped), "id": claim_id},
    )
    for n, line in enumerate(lines, 1):
        connection.execute(
            text(
                "INSERT INTO erp.expense_claim_line (workspace_id, generation_id, "
                "expense_claim_id, line_no, account_id, amount, project_id, memo) "
                "VALUES (:w, :g, :id, :n, :account_id, :amount, :project_id, :memo)"
            ),
            {
                **_s(scoped),
                "project_id": None,
                "memo": None,
                **line,
                "id": claim_id,
                "n": n,
            },
        )


def _draft(connection, scoped, claim_id: int):
    claim = _claim(connection, scoped, claim_id, lock=True)
    if claim["status"] != "draft":
        raise _locked("작성 중인 결의서만 고칠 수 있습니다.", "CLAIM_LOCKED")
    return claim


def set_lines(context, claim_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        _draft(connection, scoped, claim_id)
        total = _checked_lines(connection, scoped, lines)
        _write_lines(connection, scoped, claim_id, lines)
        connection.execute(
            text(f"UPDATE erp.expense_claim SET total_amount=:t WHERE {_S} AND id=:id"),
            {**_s(scoped), "t": total, "id": claim_id},
        )
        return _claim(connection, scoped, claim_id), "expense_claim", claim_id

    body = {"id": claim_id, "lines": lines}
    return _action(context, "erp.expense_claim.lines", key, body, run)


def _expense_entry(connection, scoped, claim) -> str | None:
    """비용 전표: 명세의 비용 계정을 차변에, 지급 방법의 상대 계정을 대변에."""
    if posting.month_closed(connection, scoped, claim["claimedOn"]):
        return posting.MONTH_CLOSED
    credit_code = PAY_ACCOUNT[claim["payMethod"]]
    account = connection.execute(
        text(
            f"SELECT id FROM erp.account WHERE {_S} AND account_code=:code AND is_active"
        ),
        {**_s(scoped), "code": credit_code},
    ).scalar_one_or_none()
    if account is None:
        return posting.NO_ACCOUNT
    lines = [
        {
            "account_id": line["accountId"],
            "side": "DEBIT",
            "amount": Decimal(line["amount"]),
            "department_id": claim["departmentId"],
            "project_id": line["projectId"],
            "memo": line["memo"],
        }
        for line in claim["lines"]
    ]
    lines.append(
        {
            "account_id": account,
            "side": "CREDIT",
            "amount": Decimal(claim["totalAmount"]),
        }
    )
    posting.write_entry(
        connection,
        scoped,
        entry_kind="EXPENSE_CLAIM",
        entry_date=claim["claimedOn"],
        lines=lines,
        description=f"지출결의 {claim['claimNo']}",
        source_kind="expense_claim",
        source_id=claim["id"],
        source_ref=claim["claimNo"],
        department_id=claim["departmentId"],
    )
    return None


def post_claim(connection, scoped, claim_id: int) -> str | None:
    """E-31 일괄 반영·시드가 쓰는 입구. 결의서는 규칙이 아니라 명세로 전표를 만든다."""
    claim = _claim(connection, scoped, claim_id)
    if claim["status"] != "confirmed":
        return None
    return _expense_entry(connection, scoped, claim)


def claim_reason(connection, scoped, claim_id: int) -> str | None:
    """전표를 못 만드는 이유(만들 수 있으면 None). 만들지는 않는다."""
    claim = _claim(connection, scoped, claim_id)
    if posting.month_closed(connection, scoped, claim["claimedOn"]):
        return posting.MONTH_CLOSED
    found = connection.execute(
        text(
            f"SELECT 1 FROM erp.account WHERE {_S} AND account_code=:code AND is_active"
        ),
        {**_s(scoped), "code": PAY_ACCOUNT[claim["payMethod"]]},
    ).first()
    return None if found else posting.NO_ACCOUNT


def confirm_claim(context, claim_id: int, key: str):
    def run(connection, scoped):
        claim = _draft(connection, scoped, claim_id)
        if not claim["lines"]:
            raise _locked("명세가 없는 결의서는 확정할 수 없습니다.", "EMPTY_CLAIM")
        connection.execute(
            text(
                "UPDATE erp.expense_claim SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": claim_id},
        )
        # 전표를 못 만들어도 결의서는 확정된다. 사유는 E-31에 남는다(Q3).
        _expense_entry(connection, scoped, _claim(connection, scoped, claim_id))
        return _claim(connection, scoped, claim_id), "expense_claim", claim_id

    return _action(context, "erp.expense_claim.confirm", key, {"id": claim_id}, run)


def cancel_claim(context, claim_id: int, reason: str, key: str):
    def run(connection, scoped):
        claim = _claim(connection, scoped, claim_id, lock=True)
        if claim["status"] == "cancelled":
            raise _locked("이미 취소한 결의서입니다.", "ALREADY_CANCELLED")
        entry = connection.execute(
            text(
                f"SELECT id, status FROM erp.journal_entry WHERE {_S} "
                "AND source_kind='expense_claim' AND source_id=:id AND status='confirmed'"
            ),
            {**_s(scoped), "id": claim_id},
        ).first()
        if entry is not None:
            raise _locked(
                "비용 전표가 살아 있습니다. 전표를 먼저 역분개하세요.",
                "ENTRY_ALIVE",
                entryId=entry.id,
            )
        connection.execute(
            text(
                "UPDATE erp.expense_claim SET status='cancelled', "
                f"cancelled_at=clock_timestamp(), cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": claim_id, "reason": reason},
        )
        return _claim(connection, scoped, claim_id), "expense_claim", claim_id

    body = {"id": claim_id, "reason": reason}
    return _action(context, "erp.expense_claim.cancel", key, body, run)


def delete_claim(context, claim_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(connection, scoped, claim_id)
        for sql in (
            f"DELETE FROM erp.expense_claim_line WHERE {_S} AND expense_claim_id=:id",
            f"DELETE FROM erp.expense_claim WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": claim_id})
        return {}, "expense_claim", claim_id

    _action(context, "erp.expense_claim.delete", key, {"id": claim_id}, run, 204)
