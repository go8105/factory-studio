"""채권·채무와 수금·지급 소명 (FS-019e E-09·E-10, FS-019f E-12·E-13). FS-014b 회계 계약.

매출 쪽(채권·수금)과 매입 쪽(채무·지급)은 같은 규칙이라 `Side` 설정 하나로 함께 처리한다.
- 잔액 = 원금 − Σ소명, 상태 OPEN/PARTIAL/CLOSED는 조회 때만 계산한다(저장 금지). 원금 0은 CLOSED 우선.
  취소된 원천(매출·매입)의 채권·채무는 유효 집계에서 뺀다(원금 행은 남는다).
- 수금·지급: draft에서만 수정·삭제, confirmed 후 금액 불변. 소명은 확정 뒤에도 추가·취소할 수 있다.
- 소명 추가: 원천(6) → 채권·채무(7, id 오름차순) → 수금·지급(7) 잠금 뒤 최신 합계로
  Σ소명 ≤ 수금·지급액, Σ소명 ≤ 원금을 모두 검사. 하나라도 넘으면 전체 롤백 + 어느 쪽인지.
- 소명 취소: 물리 DELETE + core.audit_event(같은 트랜잭션). 과입금·과지급은 막지 않는다(미소명 잔여).
- FIFO는 제안만 한다(저장 없음).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.core.service import _audit
from fs.erp.repository import camel
from fs.erp.sales import _S, MODULE, _action, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found


@dataclass(frozen=True)
class Side:
    open_item: str  # receivable / payable
    money: str  # receipt / payment
    money_no: str  # receipt_no / payment_no
    money_on: str  # received_on / paid_on
    source: str  # sales_record / purchase_invoice
    source_join: str  # 원천·문서번호 조인(별칭 s)
    source_cols: str  # 원천 날짜, 문서번호
    source_valid: str  # 유효 원천 조건
    order: str  # 오래된 순 정렬(FIFO)
    doc: str  # 문서번호 컬럼(응답 키의 원본)
    partner_kind: str
    label: str  # 채권 / 채무
    money_label: str  # 수금 / 지급
    source_label: str  # 매출 / 매입

    @property
    def apply(self) -> str:
        return f"{self.money}_apply"

    @property
    def item_fk(self) -> str:
        return f"{self.open_item}_id"

    @property
    def adjust(self) -> str:
        return f"{self.open_item}_adjust"

    @property
    def money_fk(self) -> str:
        return f"{self.money}_id"


RECEIVABLE = Side(
    "receivable",
    "receipt",
    "receipt_no",
    "received_on",
    "sales_record",
    """JOIN erp.sales_record s ON s.workspace_id=rv.workspace_id
   AND s.generation_id=rv.generation_id AND s.id=rv.sales_record_id
  JOIN erp.shipment sh ON sh.workspace_id=s.workspace_id
   AND sh.generation_id=s.generation_id AND sh.id=s.shipment_id""",
    "s.recognized_at, sh.shipment_no",
    "s.cancelled_at IS NULL",
    "recognized_at",
    "shipment_no",
    "CUSTOMER",
    "채권",
    "수금",
    "매출",
)
PAYABLE = Side(
    "payable",
    "payment",
    "payment_no",
    "paid_on",
    "purchase_invoice",
    """JOIN erp.purchase_invoice s ON s.workspace_id=rv.workspace_id
   AND s.generation_id=rv.generation_id AND s.id=rv.purchase_invoice_id""",
    "s.invoice_date, s.invoice_no",
    "s.status='confirmed'",
    "invoice_date",
    "invoice_no",
    "SUPPLIER",
    "채무",
    "지급",
    "매입",
)


def _open_sql(side: Side) -> str:
    """유효 채권·채무의 잔액·상태. 대시보드(019h)도 이 SQL을 쓴다.

    잔액 = 원금 − 소명 − 조정(반품 대변·상계·대손). 조정도 저장하지 않고 여기서 뺀다(DSN-11 F75).
    """
    return f"""
SELECT * FROM (
  SELECT rv.id, rv.{side.source}_id, rv.partner_id, rv.amount, rv.due_date, rv.currency,
         {side.source_cols}, x.applied_amount, j.adjusted_amount,
         rv.amount - x.applied_amount - j.adjusted_amount balance,
         CASE WHEN rv.amount - x.applied_amount - j.adjusted_amount = 0 THEN 'CLOSED'
              WHEN x.applied_amount + j.adjusted_amount > 0 THEN 'PARTIAL'
              ELSE 'OPEN' END status
  FROM erp.{side.open_item} rv
  {side.source_join}
  CROSS JOIN LATERAL (SELECT coalesce(sum(a.amount), 0) applied_amount
    FROM erp.{side.apply} a WHERE a.workspace_id=rv.workspace_id
     AND a.generation_id=rv.generation_id AND a.{side.item_fk}=rv.id) x
  CROSS JOIN LATERAL (SELECT coalesce(sum(b.amount), 0) adjusted_amount
    FROM erp.{side.adjust} b WHERE b.workspace_id=rv.workspace_id
     AND b.generation_id=rv.generation_id AND b.{side.item_fk}=rv.id) j
  WHERE rv.workspace_id=:w AND rv.generation_id=:g AND {side.source_valid}
) v WHERE true"""


def _apply_sql(side: Side) -> str:
    return f"""
SELECT a.id, a.{side.money_fk}, a.{side.item_fk}, a.amount, a.applied_at,
       c.{side.money_no}, {side.source_cols.split(", ")[1]}
FROM erp.{side.apply} a
JOIN erp.{side.money} c ON c.workspace_id=a.workspace_id
 AND c.generation_id=a.generation_id AND c.id=a.{side.money_fk}
JOIN erp.{side.open_item} rv ON rv.workspace_id=a.workspace_id
 AND rv.generation_id=a.generation_id AND rv.id=a.{side.item_fk}
{side.source_join}
WHERE a.workspace_id=:w AND a.generation_id=:g"""


def _money_sql(side: Side) -> str:
    return f"""
SELECT c.id, c.{side.money_no}, c.partner_id, c.{side.money_on}, c.amount, c.currency,
       c.status, c.confirmed_at, c.created_at, x.applied_amount,
       c.amount - x.applied_amount unapplied_amount
FROM erp.{side.money} c
CROSS JOIN LATERAL (SELECT coalesce(sum(a.amount), 0) applied_amount
  FROM erp.{side.apply} a WHERE a.workspace_id=c.workspace_id
   AND a.generation_id=c.generation_id AND a.{side.money_fk}=c.id) x
WHERE c.workspace_id=:w AND c.generation_id=:g"""


def open_items(side: Side, connection, scoped, where: str = "", **params: Any):
    rows = _rows(
        connection,
        _open_sql(side) + where + f" ORDER BY {side.order}, id",
        {**_s(scoped), **params},
    )
    applies = _rows(
        connection,
        _apply_sql(side)
        + f" AND a.{side.item_fk} = ANY(:ids) ORDER BY a.applied_at, a.id",
        {**_s(scoped), "ids": [r["id"] for r in rows]},
    )
    key = camel(side.item_fk)
    for row in rows:
        row["applications"] = [a for a in applies if a[key] == row["id"]]
    return rows


def list_open_items(side: Side, context, partner_id: int | None, status: str | None):
    where, params = "", {}
    if partner_id is not None:
        where += " AND partner_id=:p"
        params["p"] = partner_id
    if status is not None:
        where += " AND status=:status"
        params["status"] = status
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return open_items(side, connection, scoped, where, **params)


def _monies(side: Side, connection, scoped, where: str = "", **params: Any):
    rows = _rows(
        connection,
        _money_sql(side)
        + where
        + f" ORDER BY c.{side.money_on} DESC, c.{side.money_no} DESC",
        {**_s(scoped), **params},
    )
    applies = _rows(
        connection,
        _apply_sql(side)
        + f" AND a.{side.money_fk} = ANY(:ids) ORDER BY a.applied_at, a.id",
        {**_s(scoped), "ids": [r["id"] for r in rows]},
    )
    key = camel(side.money_fk)
    for row in rows:
        row["applications"] = [a for a in applies if a[key] == row["id"]]
    return rows


def _money(side: Side, connection, scoped, money_id: int) -> dict[str, Any]:
    found = _monies(side, connection, scoped, " AND c.id=:id", id=money_id)
    if not found:
        raise not_found()
    return found[0]


def list_monies(side: Side, context):
    with _read() as connection:
        return _monies(side, connection, read_scope(connection, context, MODULE))


# ---- 수금·지급 머리글 (draft → confirmed) ----
def _draft(side: Side, connection, scoped, money_id: int) -> dict[str, Any]:
    money = _money(side, connection, scoped, money_id)
    if money["status"] != "draft":
        raise _locked(
            f"확정된 {side.money_label}은 바꿀 수 없습니다.",
            f"{side.money.upper()}_CONFIRMED",
        )
    return money


def _check(side: Side, connection, scoped, values: dict[str, Any], money_id=None):
    if side.money_no in values and _exists(
        connection,
        scoped,
        f"SELECT 1 FROM erp.{side.money} WHERE {_S} AND {side.money_no}=:no "
        "AND id IS DISTINCT FROM :id",
        no=values[side.money_no],
        id=money_id,
    ):
        raise invalid(side.money_no, f"이미 사용 중인 {side.money_label}번호입니다.")
    if "partner_id" in values:
        row = connection.execute(
            text(
                f"SELECT partner_kind, is_active FROM erp.partner WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": values["partner_id"]},
        ).first()
        if (
            row is None
            or row.partner_kind not in (side.partner_kind, "BOTH")
            or not row.is_active
        ):
            raise invalid("partner_id", "현재 공간의 사용 중인 거래처를 선택하세요.")
    if "amount" in values and Decimal(values["amount"]) <= 0:
        raise invalid("amount", f"{side.money_label}액은 0보다 커야 합니다.")


def create_money(side: Side, context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _check(side, connection, scoped, values)
        money_id = connection.execute(
            text(
                f"INSERT INTO erp.{side.money} (workspace_id, generation_id, "
                f"{side.money_no}, partner_id, {side.money_on}, amount) VALUES "
                f"(:w, :g, :{side.money_no}, :partner_id, :{side.money_on}, :amount) "
                "RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return _money(side, connection, scoped, money_id), side.money, money_id

    return _action(context, f"erp.{side.money}.create", key, values, run, 201)


def update_money(side: Side, context, money_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        _draft(side, connection, scoped, money_id)
        _check(side, connection, scoped, values, money_id)
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE erp.{side.money} SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": money_id},
        )
        return _money(side, connection, scoped, money_id), side.money, money_id

    body = {"id": money_id, **values}
    return _action(context, f"erp.{side.money}.update", key, body, run)


def confirm_money(side: Side, context, money_id: int, key: str):
    def run(connection, scoped):
        _draft(side, connection, scoped, money_id)
        connection.execute(
            text(
                f"UPDATE erp.{side.money} SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": money_id},
        )
        return _money(side, connection, scoped, money_id), side.money, money_id

    return _action(context, f"erp.{side.money}.confirm", key, {"id": money_id}, run)


def delete_money(side: Side, context, money_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(side, connection, scoped, money_id)  # draft에는 소명이 없다(확정 후에만)
        connection.execute(
            text(f"DELETE FROM erp.{side.money} WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": money_id},
        )
        return {}, side.money, money_id

    _action(context, f"erp.{side.money}.delete", key, {"id": money_id}, run, 204)


# ---- 소명 ----
def _sum(side: Side, connection, scoped, column: str, row_id: int) -> Decimal:
    return connection.execute(
        text(
            f"SELECT coalesce(sum(amount), 0) FROM erp.{side.apply} WHERE {_S} "
            f"AND {column}=:id"
        ),
        {**_s(scoped), "id": row_id},
    ).scalar_one()


def _exceeded(message: str, **details: Any) -> ApiError:
    return ApiError(
        409, "LIMIT_EXCEEDED", message, {"reason": "LIMIT_EXCEEDED", **details}
    )


def add_applications(side: Side, context, money_id: int, lines: list[dict], key: str):
    item_key = camel(side.item_fk)

    def run(connection, scoped):
        ids = sorted({line[side.item_fk] for line in lines})
        if len(ids) != len(lines):
            raise invalid("lines", f"같은 {side.label}이 두 번 있습니다.")
        params = {**_s(scoped), "ids": ids}
        # 잠금 순서: 원천(6) → 채권·채무(7) id 오름차순 → 수금·지급(7)
        connection.execute(
            text(
                f"SELECT id FROM erp.{side.source} WHERE {_S} AND id IN (SELECT "
                f"{side.source}_id FROM erp.{side.open_item} WHERE {_S} "
                "AND id = ANY(:ids)) ORDER BY id FOR UPDATE"
            ),
            params,
        )
        locked = {
            r.id: r
            for r in connection.execute(
                text(
                    f"SELECT id, partner_id, amount FROM erp.{side.open_item} "
                    f"WHERE {_S} AND id = ANY(:ids) ORDER BY id FOR UPDATE"
                ),
                params,
            )
        }
        money = connection.execute(
            text(
                f"SELECT id, partner_id, amount, status FROM erp.{side.money} "
                f"WHERE {_S} AND id=:id FOR UPDATE"
            ),
            {**_s(scoped), "id": money_id},
        ).first()
        if money is None:
            raise not_found()
        if money.status != "confirmed":
            raise _locked(
                f"확정한 {side.money_label}만 소명할 수 있습니다.",
                f"{side.money.upper()}_NOT_CONFIRMED",
            )
        valid = {
            r["id"]: r
            for r in open_items(
                side, connection, scoped, " AND id = ANY(:ids)", ids=ids
            )
        }
        total = Decimal(0)
        for n, line in enumerate(lines, 1):
            rid = line[side.item_fk]
            target = locked.get(rid)
            if target is None or target.partner_id != money.partner_id:
                raise invalid(
                    "lines", f"{n}번째 라인: 같은 거래처의 {side.label}을 고르세요."
                )
            if rid not in valid:
                raise _locked(
                    f"취소된 {side.source_label}의 {side.label}에는 소명할 수 없습니다.",
                    f"{'SALES' if side is RECEIVABLE else 'PURCHASE'}_CANCELLED",
                )
            amount = Decimal(line["amount"])
            if amount <= 0:
                raise invalid("lines", f"{n}번째 라인: 소명액은 0보다 커야 합니다.")
            # 잠근 뒤 최신 합계로 원금 한도
            available = target.amount - _sum(
                side, connection, scoped, side.item_fk, rid
            )
            if amount > available:
                raise _exceeded(
                    f"{side.label} 잔액을 넘어 소명할 수 없습니다.",
                    **{
                        "limit": side.open_item.upper(),
                        item_key: rid,
                        camel(side.doc): valid[rid][camel(side.doc)],
                        "availableAmount": str(available),
                    },
                )
            total += amount
        available = money.amount - _sum(
            side, connection, scoped, side.money_fk, money_id
        )
        if total > available:
            raise _exceeded(
                f"{side.money_label}액의 미소명 잔여를 넘어 소명할 수 없습니다.",
                **{
                    "limit": side.money.upper(),
                    camel(side.money_fk): money_id,
                    "availableAmount": str(available),
                },
            )
        for n, line in enumerate(lines):
            apply_key = hashlib.sha256(f"{money_id}:{key}:{n}".encode()).hexdigest()
            connection.execute(
                text(
                    f"INSERT INTO erp.{side.apply} (workspace_id, generation_id, "
                    f"{side.money_fk}, {side.item_fk}, partner_id, amount, apply_key, "
                    "applied_at) VALUES "
                    "(:w, :g, :money, :item, :p, :amount, :apply_key, clock_timestamp())"
                ),
                {
                    **_s(scoped),
                    "money": money_id,
                    "item": line[side.item_fk],
                    "p": money.partner_id,
                    "amount": line["amount"],
                    "apply_key": apply_key,
                },
            )
        return _money(side, connection, scoped, money_id), side.money, money_id

    body = {"id": money_id, "lines": lines}
    return _action(context, f"erp.{side.apply}.create", key, body, run, 201)


def delete_application(side: Side, context, money_id: int, apply_id: int, key: str):
    """소명 취소 = 물리 삭제 + 감사 기록(같은 트랜잭션)."""

    def run(connection, scoped):
        row = connection.execute(
            text(
                f"SELECT id, {side.item_fk} item_id, {side.money_fk} money_id, amount, "
                f"apply_key, currency FROM erp.{side.apply} WHERE {_S} AND id=:id "
                f"AND {side.money_fk}=:money"
            ),
            {**_s(scoped), "id": apply_id, "money": money_id},
        ).first()
        if row is None:
            raise not_found()
        for table, target in (
            (side.open_item, row.item_id),
            (side.money, row.money_id),
            (side.apply, row.id),
        ):
            connection.execute(
                text(f"SELECT id FROM erp.{table} WHERE {_S} AND id=:id FOR UPDATE"),
                {**_s(scoped), "id": target},
            )
        connection.execute(
            text(f"DELETE FROM erp.{side.apply} WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": apply_id},
        )
        _audit(
            connection,
            scoped.workspace_id,
            scoped.actor_kind,
            scoped.actor_key,
            scoped.user_id,
            f"erp.{side.apply}.delete",
            f"erp.{side.apply}",
            str(apply_id),
            {
                "generationId": scoped.generation_id,
                camel(side.money_fk): row.money_id,
                camel(side.item_fk): row.item_id,
                "applyId": row.id,
                "applyKey": row.apply_key,
                "amount": str(row.amount),
                "currency": row.currency,
                "reason": "소명 취소",
            },
        )
        return _money(side, connection, scoped, money_id), side.money, money_id

    body = {"id": money_id, "applyId": apply_id}
    return _action(context, f"erp.{side.apply}.delete", key, body, run)


def fifo_suggestion(side: Side, context, money_id: int) -> list[dict[str, Any]]:
    """미소명 잔여를 오래된 원천부터 채우는 제안. 저장하지 않는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        money = _money(side, connection, scoped, money_id)
        left = Decimal(money["unappliedAmount"])
        suggestion = []
        for row in open_items(
            side,
            connection,
            scoped,
            " AND partner_id=:p AND balance > 0",
            p=money["partnerId"],
        ):
            if left <= 0:
                break
            amount = min(left, Decimal(row["balance"]))
            suggestion.append({camel(side.item_fk): row["id"], "amount": str(amount)})
            left -= amount
        return suggestion
