"""E-09 매출채권 현황 · E-10 수금 등록·소명 (FS-019e). FS-014b 회계 계약.

- 잔액 = 원금 − Σ소명, 상태 OPEN/PARTIAL/CLOSED는 조회 때만 계산한다(저장 금지). 원금 0은 CLOSED 우선.
  취소 매출의 채권은 유효 집계에서 뺀다(원금 행은 남는다).
- 수금: draft에서만 수정·삭제, confirmed 후 금액 불변. 소명은 확정 뒤에도 추가·취소할 수 있다.
- 소명 추가: 매출(6) → 채권(7, id 오름차순) → 수금(7) 잠금 뒤 최신 합계로
  Σ소명 ≤ 수금액, Σ소명 ≤ 채권 원금을 모두 검사. 하나라도 넘으면 전체 롤백 + 어느 쪽인지.
- 소명 취소: 물리 DELETE + core.audit_event(같은 트랜잭션). 과입금은 막지 않는다(미소명 잔여).
- FIFO는 제안만 한다(저장 없음).
"""

from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.core.service import _audit
from fs.erp.sales import _S, MODULE, _action, _customer, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

# 유효 채권(취소 매출 제외)의 잔액·상태. 대시보드(019h)도 이 SQL을 쓴다.
RECEIVABLE_SQL = """
SELECT * FROM (
  SELECT rv.id, rv.sales_record_id, rv.partner_id, rv.amount, rv.due_date, rv.currency,
         r.recognized_at, sh.shipment_no, x.applied_amount,
         rv.amount - x.applied_amount balance,
         CASE WHEN rv.amount - x.applied_amount = 0 THEN 'CLOSED'
              WHEN x.applied_amount > 0 THEN 'PARTIAL' ELSE 'OPEN' END status
  FROM erp.receivable rv
  JOIN erp.sales_record r ON r.workspace_id=rv.workspace_id
   AND r.generation_id=rv.generation_id AND r.id=rv.sales_record_id
  JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id
   AND sh.generation_id=r.generation_id AND sh.id=r.shipment_id
  CROSS JOIN LATERAL (SELECT coalesce(sum(a.amount), 0) applied_amount
    FROM erp.receipt_apply a WHERE a.workspace_id=rv.workspace_id
     AND a.generation_id=rv.generation_id AND a.receivable_id=rv.id) x
  WHERE rv.workspace_id=:w AND rv.generation_id=:g AND r.cancelled_at IS NULL
) v WHERE true"""
APPLY_SQL = """
SELECT a.id, a.receipt_id, a.receivable_id, a.amount, a.applied_at, c.receipt_no,
       sh.shipment_no
FROM erp.receipt_apply a
JOIN erp.receipt c ON c.workspace_id=a.workspace_id AND c.generation_id=a.generation_id
 AND c.id=a.receipt_id
JOIN erp.receivable rv ON rv.workspace_id=a.workspace_id
 AND rv.generation_id=a.generation_id AND rv.id=a.receivable_id
JOIN erp.sales_record r ON r.workspace_id=rv.workspace_id
 AND r.generation_id=rv.generation_id AND r.id=rv.sales_record_id
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id AND sh.generation_id=r.generation_id
 AND sh.id=r.shipment_id
WHERE a.workspace_id=:w AND a.generation_id=:g"""
RECEIPT_SQL = """
SELECT c.id, c.receipt_no, c.partner_id, c.received_on, c.amount, c.currency, c.status,
       c.confirmed_at, c.created_at, x.applied_amount,
       c.amount - x.applied_amount unapplied_amount
FROM erp.receipt c
CROSS JOIN LATERAL (SELECT coalesce(sum(a.amount), 0) applied_amount
  FROM erp.receipt_apply a WHERE a.workspace_id=c.workspace_id
   AND a.generation_id=c.generation_id AND a.receipt_id=c.id) x
WHERE c.workspace_id=:w AND c.generation_id=:g"""


def receivables(connection, scoped, where: str = "", **params: Any):
    rows = _rows(
        connection,
        RECEIVABLE_SQL + where + " ORDER BY recognized_at, id",
        {**_s(scoped), **params},
    )
    applies = _rows(
        connection,
        APPLY_SQL + " AND a.receivable_id = ANY(:ids) ORDER BY a.applied_at, a.id",
        {**_s(scoped), "ids": [r["id"] for r in rows]},
    )
    for row in rows:
        row["applications"] = [a for a in applies if a["receivableId"] == row["id"]]
    return rows


def list_receivables(context, partner_id: int | None, status: str | None):
    where, params = "", {}
    if partner_id is not None:
        where += " AND partner_id=:p"
        params["p"] = partner_id
    if status is not None:
        where += " AND status=:status"
        params["status"] = status
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return receivables(connection, scoped, where, **params)


def _receipts(connection, scoped, where: str = "", **params: Any):
    rows = _rows(
        connection,
        RECEIPT_SQL + where + " ORDER BY c.received_on DESC, c.receipt_no DESC",
        {**_s(scoped), **params},
    )
    applies = _rows(
        connection,
        APPLY_SQL + " AND a.receipt_id = ANY(:ids) ORDER BY a.applied_at, a.id",
        {**_s(scoped), "ids": [r["id"] for r in rows]},
    )
    for row in rows:
        row["applications"] = [a for a in applies if a["receiptId"] == row["id"]]
    return rows


def _receipt(connection, scoped, receipt_id: int) -> dict[str, Any]:
    found = _receipts(connection, scoped, " AND c.id=:id", id=receipt_id)
    if not found:
        raise not_found()
    return found[0]


def list_receipts(context):
    with _read() as connection:
        return _receipts(connection, read_scope(connection, context, MODULE))


# ---- 수금 머리글 (draft → confirmed) ----
def _draft(connection, scoped, receipt_id: int) -> dict[str, Any]:
    receipt = _receipt(connection, scoped, receipt_id)
    if receipt["status"] != "draft":
        raise _locked("확정된 수금은 바꿀 수 없습니다.", "RECEIPT_CONFIRMED")
    return receipt


def _check_amount(values: dict[str, Any]) -> None:
    if "amount" in values and Decimal(values["amount"]) <= 0:
        raise invalid("amount", "수금액은 0보다 커야 합니다.")


def create_receipt(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        if _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.receipt WHERE {_S} AND receipt_no=:no",
            no=values["receipt_no"],
        ):
            raise invalid("receipt_no", "이미 사용 중인 수금번호입니다.")
        _customer(connection, scoped, values["partner_id"])
        _check_amount(values)
        receipt_id = connection.execute(
            text(
                "INSERT INTO erp.receipt (workspace_id, generation_id, receipt_no, "
                "partner_id, received_on, amount) VALUES "
                "(:w, :g, :receipt_no, :partner_id, :received_on, :amount) RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return _receipt(connection, scoped, receipt_id), "receipt", receipt_id

    return _action(context, "erp.receipt.create", key, values, run, 201)


def update_receipt(context, receipt_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        _draft(connection, scoped, receipt_id)
        if "receipt_no" in values and _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.receipt WHERE {_S} AND receipt_no=:no AND id<>:id",
            no=values["receipt_no"],
            id=receipt_id,
        ):
            raise invalid("receipt_no", "이미 사용 중인 수금번호입니다.")
        if "partner_id" in values:
            _customer(connection, scoped, values["partner_id"])
        _check_amount(values)
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE erp.receipt SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": receipt_id},
        )
        return _receipt(connection, scoped, receipt_id), "receipt", receipt_id

    body = {"id": receipt_id, **values}
    return _action(context, "erp.receipt.update", key, body, run)


def confirm_receipt(context, receipt_id: int, key: str):
    def run(connection, scoped):
        _draft(connection, scoped, receipt_id)
        connection.execute(
            text(
                "UPDATE erp.receipt SET status='confirmed', confirmed_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": receipt_id},
        )
        return _receipt(connection, scoped, receipt_id), "receipt", receipt_id

    return _action(context, "erp.receipt.confirm", key, {"id": receipt_id}, run)


def delete_receipt(context, receipt_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(
            connection, scoped, receipt_id
        )  # draft에는 소명이 없다(확정 후에만 소명)
        connection.execute(
            text(f"DELETE FROM erp.receipt WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": receipt_id},
        )
        return {}, "receipt", receipt_id

    _action(context, "erp.receipt.delete", key, {"id": receipt_id}, run, 204)


# ---- 소명 ----
def _sum(connection, scoped, column: str, row_id: int) -> Decimal:
    return connection.execute(
        text(
            f"SELECT coalesce(sum(amount), 0) FROM erp.receipt_apply WHERE {_S} "
            f"AND {column}=:id"
        ),
        {**_s(scoped), "id": row_id},
    ).scalar_one()


def _exceeded(message: str, **details: Any) -> ApiError:
    return ApiError(
        409, "LIMIT_EXCEEDED", message, {"reason": "LIMIT_EXCEEDED", **details}
    )


def add_applications(context, receipt_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        ids = sorted({line["receivable_id"] for line in lines})
        if len(ids) != len(lines):
            raise invalid("lines", "같은 채권이 두 번 있습니다.")
        params = {**_s(scoped), "ids": ids}
        # 잠금 순서: 매출(6) → 채권(7) id 오름차순 → 수금(7)
        connection.execute(
            text(
                f"SELECT id FROM erp.sales_record WHERE {_S} AND id IN (SELECT "
                f"sales_record_id FROM erp.receivable WHERE {_S} AND id = ANY(:ids)) "
                "ORDER BY id FOR UPDATE"
            ),
            params,
        )
        locked = {
            r.id: r
            for r in connection.execute(
                text(
                    f"SELECT id, partner_id, amount FROM erp.receivable WHERE {_S} "
                    "AND id = ANY(:ids) ORDER BY id FOR UPDATE"
                ),
                params,
            )
        }
        receipt = connection.execute(
            text(
                "SELECT id, partner_id, amount, status FROM erp.receipt "
                f"WHERE {_S} AND id=:id FOR UPDATE"
            ),
            {**_s(scoped), "id": receipt_id},
        ).first()
        if receipt is None:
            raise not_found()
        if receipt.status != "confirmed":
            raise _locked("확정한 수금만 소명할 수 있습니다.", "RECEIPT_NOT_CONFIRMED")
        valid = {
            r["id"]: r
            for r in receivables(connection, scoped, " AND id = ANY(:ids)", ids=ids)
        }
        total = Decimal(0)
        for n, line in enumerate(lines, 1):
            rid = line["receivable_id"]
            target = locked.get(rid)
            if target is None or target.partner_id != receipt.partner_id:
                raise invalid("lines", f"{n}번째 라인: 같은 거래처의 채권을 고르세요.")
            if rid not in valid:
                raise _locked(
                    "취소된 매출의 채권에는 소명할 수 없습니다.", "SALES_CANCELLED"
                )
            amount = Decimal(line["amount"])
            if amount <= 0:
                raise invalid("lines", f"{n}번째 라인: 소명액은 0보다 커야 합니다.")
            # 잠근 뒤 최신 합계로 채권 한도
            available = target.amount - _sum(connection, scoped, "receivable_id", rid)
            if amount > available:
                raise _exceeded(
                    "채권 잔액을 넘어 소명할 수 없습니다.",
                    limit="RECEIVABLE",
                    receivableId=rid,
                    shipmentNo=valid[rid]["shipmentNo"],
                    availableAmount=str(available),
                )
            total += amount
        available = receipt.amount - _sum(connection, scoped, "receipt_id", receipt_id)
        if total > available:
            raise _exceeded(
                "수금액의 미소명 잔여를 넘어 소명할 수 없습니다.",
                limit="RECEIPT",
                receiptId=receipt_id,
                availableAmount=str(available),
            )
        for n, line in enumerate(lines):
            apply_key = hashlib.sha256(f"{receipt_id}:{key}:{n}".encode()).hexdigest()
            connection.execute(
                text(
                    "INSERT INTO erp.receipt_apply (workspace_id, generation_id, receipt_id, "
                    "receivable_id, partner_id, amount, apply_key, applied_at) VALUES "
                    "(:w, :g, :rc, :rv, :p, :amount, :apply_key, clock_timestamp())"
                ),
                {
                    **_s(scoped),
                    "rc": receipt_id,
                    "rv": line["receivable_id"],
                    "p": receipt.partner_id,
                    "amount": line["amount"],
                    "apply_key": apply_key,
                },
            )
        return _receipt(connection, scoped, receipt_id), "receipt", receipt_id

    body = {"id": receipt_id, "lines": lines}
    return _action(context, "erp.receipt_apply.create", key, body, run, 201)


def delete_application(context, receipt_id: int, apply_id: int, key: str):
    """소명 취소 = 물리 삭제 + 감사 기록(같은 트랜잭션)."""

    def run(connection, scoped):
        row = connection.execute(
            text(
                "SELECT id, receivable_id, receipt_id, amount, apply_key, currency "
                f"FROM erp.receipt_apply WHERE {_S} AND id=:id AND receipt_id=:rc"
            ),
            {**_s(scoped), "id": apply_id, "rc": receipt_id},
        ).first()
        if row is None:
            raise not_found()
        for sql, target in (
            ("SELECT id FROM erp.receivable", row.receivable_id),
            ("SELECT id FROM erp.receipt", row.receipt_id),
            ("SELECT id FROM erp.receipt_apply", row.id),
        ):
            connection.execute(
                text(f"{sql} WHERE {_S} AND id=:id FOR UPDATE"),
                {**_s(scoped), "id": target},
            )
        connection.execute(
            text(f"DELETE FROM erp.receipt_apply WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": apply_id},
        )
        _audit(
            connection,
            scoped.workspace_id,
            scoped.actor_kind,
            scoped.actor_key,
            scoped.user_id,
            "erp.receipt_apply.delete",
            "erp.receipt_apply",
            str(apply_id),
            {
                "generationId": scoped.generation_id,
                "receiptId": row.receipt_id,
                "receivableId": row.receivable_id,
                "applyId": row.id,
                "applyKey": row.apply_key,
                "amount": str(row.amount),
                "currency": row.currency,
                "reason": "소명 취소",
            },
        )
        return _receipt(connection, scoped, receipt_id), "receipt", receipt_id

    body = {"id": receipt_id, "applyId": apply_id}
    return _action(context, "erp.receipt_apply.delete", key, body, run)


def fifo_suggestion(context, receipt_id: int) -> list[dict[str, Any]]:
    """미소명 잔여를 오래된 매출부터 채우는 제안. 저장하지 않는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        receipt = _receipt(connection, scoped, receipt_id)
        left = Decimal(receipt["unappliedAmount"])
        suggestion = []
        for row in receivables(
            connection,
            scoped,
            " AND partner_id=:p AND balance > 0",
            p=receipt["partnerId"],
        ):
            if left <= 0:
                break
            amount = min(left, Decimal(row["balance"]))
            suggestion.append({"receivableId": row["id"], "amount": str(amount)})
            left -= amount
        return suggestion
