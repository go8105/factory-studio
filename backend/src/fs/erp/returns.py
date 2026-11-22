"""E-20 판매 반품 · E-24 구매 반품 (DSN-11 F16·F25).

매출 반품과 매입 반품은 같은 규칙이라 `ReturnKind` 설정 하나로 함께 처리한다.
- 원 문서(매출·매입 전표)를 반드시 참조한다. 반품 수량 ≤ 원 수량 − 이미 반품한 수량(SERVICE 검사).
- 확정하면 같은 트랜잭션에서 **채권·채무 조정(RETURN_CREDIT)** 1건을 만든다. 잔액은 저장하지 않고
  원금 − 소명 − 조정으로 파생한다(E-09·E-12와 같은 SQL).
- **전표는 아직 만들지 않는다.** 자동 분개는 1e(E-30·E-31) 몫이고, 그때 이 확정분을 읽어 반영한다.
- 확정 후 금액·명세 불변. 되돌리려면 취소한다(조정도 함께 지운다).
- 실물 반입·반출은 WMS가 한다. ERP는 금액만 본다.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import posting
from fs.erp.procurement import _next_no
from fs.erp.revenue import line_amounts
from fs.erp.sales import _S, MODULE, _action, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found


@dataclass(frozen=True)
class ReturnKind:
    table: str  # sales_return / purchase_return
    line_table: str  # sales_return_line / purchase_return_line
    fk: str  # sales_return_id / purchase_return_id
    source: str  # sales_record / purchase_invoice
    source_fk: str  # sales_record_id / purchase_invoice_id
    open_item: str  # receivable / payable
    partner_kinds: tuple[str, ...]
    prefix: str  # 번호 머리글
    label: str  # 판매 반품 / 구매 반품
    source_label: str  # 매출 / 매입

    @property
    def adjust(self) -> str:
        return f"{self.open_item}_adjust"

    @property
    def source_posting(self):
        from fs.erp import posting as _posting

        return (
            _posting.SALES_RETURN
            if self.table == "sales_return"
            else _posting.PURCHASE_RETURN
        )

    @property
    def apply(self) -> str:
        return "receipt_apply" if self.open_item == "receivable" else "payment_apply"

    @property
    def source_lines(self) -> str:
        """원 문서의 품목별 수량·단가를 주는 질의(별칭 없음)."""
        if self.source == "sales_record":
            return """
SELECT l.item_id, sum(l.shipped_qty) quantity, max(l.shipped_uom) unit
FROM erp.sales_record r
JOIN erp.shipment_line l ON l.workspace_id=r.workspace_id
 AND l.generation_id=r.generation_id AND l.shipment_id=r.shipment_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.id=:id
GROUP BY l.item_id"""
        return """
SELECT l.item_id, sum(l.quantity) quantity, max(l.unit) unit
FROM erp.purchase_invoice_line l
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.purchase_invoice_id=:id
GROUP BY l.item_id"""


SALES = ReturnKind(
    "sales_return",
    "sales_return_line",
    "sales_return_id",
    "sales_record",
    "sales_record_id",
    "receivable",
    ("CUSTOMER", "BOTH"),
    "SR",
    "판매 반품",
    "매출",
)
PURCHASE = ReturnKind(
    "purchase_return",
    "purchase_return_line",
    "purchase_return_id",
    "purchase_invoice",
    "purchase_invoice_id",
    "payable",
    ("SUPPLIER", "BOTH"),
    "PR-RET",
    "구매 반품",
    "매입",
)


def _head_sql(kind: ReturnKind) -> str:
    return f"""
SELECT t.id, t.return_no, t.partner_id, t.{kind.source_fk}, t.returned_on, t.reason,
       t.currency, t.supply_amount, t.tax_amount, t.total_amount, t.status,
       t.confirmed_at, t.cancelled_at, t.cancel_reason, p.partner_code, p.partner_name
FROM erp.{kind.table} t
JOIN erp.partner p ON p.workspace_id=t.workspace_id AND p.generation_id=t.generation_id
 AND p.id=t.partner_id
WHERE t.workspace_id=:w AND t.generation_id=:g"""


def _line_sql(kind: ReturnKind) -> str:
    return f"""
SELECT l.id, l.{kind.fk}, l.line_no, l.item_id, l.quantity, l.unit, l.unit_price,
       l.supply_amount, l.tax_amount, l.total_amount, i.item_code, i.name item_name
FROM erp.{kind.line_table} l
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.{kind.fk} = ANY(:ids)
ORDER BY l.{kind.fk}, l.line_no"""


def _returns(connection, scoped, kind: ReturnKind, where: str = "", **params: Any):
    heads = _rows(
        connection,
        _head_sql(kind) + where + " ORDER BY t.returned_on DESC, t.return_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(
        connection, _line_sql(kind), {**_s(scoped), "ids": [h["id"] for h in heads]}
    )
    key = _camel(kind.fk)
    for head in heads:
        head["lines"] = [x for x in lines if x[key] == head["id"]]
    return heads


def _one(connection, scoped, kind: ReturnKind, return_id: int, lock: bool = False):
    if lock:
        connection.execute(
            text(f"SELECT id FROM erp.{kind.table} WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": return_id},
        )
    found = _returns(connection, scoped, kind, " AND t.id=:id", id=return_id)
    if not found:
        raise not_found()
    return found[0]


def _draft(connection, scoped, kind: ReturnKind, return_id: int):
    row = _one(connection, scoped, kind, return_id, lock=True)
    if row["status"] != "draft":
        raise _locked(f"작성 중인 {kind.label}만 고칠 수 있습니다.", "RETURN_LOCKED")
    return row


def listing(context, kind: ReturnKind):
    with _read() as connection:
        return _returns(connection, read_scope(connection, context, MODULE), kind)


def _source(connection, scoped, kind: ReturnKind, source_id: int, partner_id: int):
    """원 문서가 이 공간의 살아 있는 문서이고 거래처가 같은지 본다."""
    valid = (
        "cancelled_at IS NULL"
        if kind.source == "sales_record"
        else "status='confirmed'"
    )
    row = connection.execute(
        text(
            f"SELECT partner_id FROM erp.{kind.source} WHERE {_S} AND id=:id AND {valid}"
        ),
        {**_s(scoped), "id": source_id},
    ).first()
    if row is None:
        raise invalid(
            f"{kind.source}_id", f"취소되지 않은 {kind.source_label} 문서를 선택하세요."
        )
    if row.partner_id != partner_id:
        raise invalid("partner_id", f"원 {kind.source_label}의 거래처와 달라요.")


def _returnable(connection, scoped, kind: ReturnKind, source_id: int, return_id: int):
    """원 수량 − 이미 반품한 수량(이 반품 제외). 품목별로 돌려준다."""
    original = {
        r.item_id: (Decimal(r.quantity), r.unit)
        for r in connection.execute(
            text(kind.source_lines), {**_s(scoped), "id": source_id}
        )
    }
    taken = {
        r.item_id: Decimal(r.quantity)
        for r in connection.execute(
            text(
                f"SELECT l.item_id, sum(l.quantity) quantity FROM erp.{kind.line_table} l "
                f"JOIN erp.{kind.table} t ON t.workspace_id=l.workspace_id "
                f"AND t.generation_id=l.generation_id AND t.id=l.{kind.fk} "
                f"WHERE l.workspace_id=:w AND l.generation_id=:g AND t.{kind.source_fk}=:id "
                "AND t.status <> 'cancelled' AND t.id IS DISTINCT FROM :self "
                "GROUP BY l.item_id"
            ),
            {**_s(scoped), "id": source_id, "self": return_id},
        )
    }
    return {
        item: (quantity - taken.get(item, Decimal(0)), unit)
        for item, (quantity, unit) in original.items()
    }


def create(context, kind: ReturnKind, values: dict[str, Any], key: str):
    def run(connection, scoped):
        row = connection.execute(
            text(
                f"SELECT partner_kind, is_active FROM erp.partner WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": values["partner_id"]},
        ).first()
        if (
            row is None
            or row.partner_kind not in kind.partner_kinds
            or not row.is_active
        ):
            raise invalid("partner_id", "현재 공간의 사용 중인 거래처를 선택하세요.")
        _source(connection, scoped, kind, values[kind.source_fk], values["partner_id"])
        return_no = _next_no(connection, scoped, kind.table, "return_no", kind.prefix)
        return_id = connection.execute(
            text(
                f"INSERT INTO erp.{kind.table} (workspace_id, generation_id, return_no, "
                f"partner_id, {kind.source_fk}, returned_on, reason, supply_amount, "
                "tax_amount, total_amount) VALUES (:w, :g, :no, :partner_id, :source_id, "
                ":returned_on, :reason, 0, 0, 0) RETURNING id"
            ),
            {
                **_s(scoped),
                **values,
                "source_id": values[kind.source_fk],
                "no": return_no,
            },
        ).scalar_one()
        return _one(connection, scoped, kind, return_id), kind.table, return_id

    return _action(context, f"erp.{kind.table}.create", key, values, run, 201)


def set_lines(context, kind: ReturnKind, return_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        head = _draft(connection, scoped, kind, return_id)
        allowed = _returnable(
            connection, scoped, kind, head[_camel(kind.source_fk)], return_id
        )
        taxes = {
            r.id: r.tax_category
            for r in connection.execute(
                text(f"SELECT id, tax_category FROM erp.item WHERE {_S}"), _s(scoped)
            )
        }
        prices = _source_prices(connection, scoped, kind, head[_camel(kind.source_fk)])
        rows = []
        wanted: dict[int, Decimal] = {}
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            item_id = line["item_id"]
            if item_id not in allowed:
                raise invalid(
                    "lines", where + f"원 {kind.source_label}에 없는 품목입니다."
                )
            quantity = Decimal(line["quantity"])
            if quantity <= 0:
                raise invalid("lines", where + "수량은 0보다 커야 합니다.")
            wanted[item_id] = wanted.get(item_id, Decimal(0)) + quantity
            if wanted[item_id] > allowed[item_id][0]:
                raise invalid(
                    "lines",
                    where
                    + f"반품할 수 있는 수량은 {allowed[item_id][0]}까지입니다"
                    + " (이미 반품한 수량을 뺀 값).",
                )
            price = prices[item_id]
            supply, tax = line_amounts(quantity, price, taxes[item_id])
            rows.append(
                {
                    "item_id": item_id,
                    "quantity": quantity,
                    "unit": allowed[item_id][1],
                    "unit_price": price,
                    "supply_amount": supply,
                    "tax_amount": tax,
                    "total_amount": supply + tax,
                }
            )
        _write_lines(connection, scoped, kind, return_id, rows)
        return _one(connection, scoped, kind, return_id), kind.table, return_id

    body = {"id": return_id, "lines": lines}
    return _action(context, f"erp.{kind.table}.lines", key, body, run)


def _camel(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(x.title() for x in rest)


def _source_prices(connection, scoped, kind: ReturnKind, source_id: int):
    """반품 단가는 원 문서의 단가다. 지금 단가표가 바뀌었어도 소급하지 않는다."""
    if kind.source == "sales_record":
        # 출하 명세에는 단가가 없다. 수주 명세까지 거슬러 올라가야 그때 판 값이 나온다.
        sql = """
SELECT l.item_id, max(ol.unit_price) unit_price
FROM erp.sales_record r
JOIN erp.shipment sh ON sh.workspace_id=r.workspace_id
 AND sh.generation_id=r.generation_id AND sh.id=r.shipment_id
JOIN erp.shipment_line l ON l.workspace_id=sh.workspace_id
 AND l.generation_id=sh.generation_id AND l.shipment_id=sh.id
JOIN erp.shipment_order_line sol ON sol.workspace_id=l.workspace_id
 AND sol.generation_id=l.generation_id AND sol.id=l.shipment_order_line_id
JOIN erp.sales_order_line ol ON ol.workspace_id=sol.workspace_id
 AND ol.generation_id=sol.generation_id AND ol.id=sol.sales_order_line_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.id=:id GROUP BY l.item_id"""
    else:
        sql = """
SELECT l.item_id, max(l.unit_price) unit_price FROM erp.purchase_invoice_line l
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.purchase_invoice_id=:id
GROUP BY l.item_id"""
    return {
        r.item_id: r.unit_price
        for r in connection.execute(text(sql), {**_s(scoped), "id": source_id})
    }


def _write_lines(connection, scoped, kind: ReturnKind, return_id: int, rows) -> None:
    connection.execute(
        text(f"DELETE FROM erp.{kind.line_table} WHERE {_S} AND {kind.fk}=:id"),
        {**_s(scoped), "id": return_id},
    )
    for n, row in enumerate(rows, 1):
        connection.execute(
            text(
                f"INSERT INTO erp.{kind.line_table} (workspace_id, generation_id, "
                f"{kind.fk}, line_no, item_id, quantity, unit, unit_price, supply_amount, "
                "tax_amount, total_amount) VALUES (:w, :g, :id, :n, :item_id, :quantity, "
                ":unit, :unit_price, :supply_amount, :tax_amount, :total_amount)"
            ),
            {**_s(scoped), **row, "id": return_id, "n": n},
        )
    supply = sum((r["supply_amount"] for r in rows), Decimal(0))
    tax = sum((r["tax_amount"] for r in rows), Decimal(0))
    connection.execute(
        text(
            f"UPDATE erp.{kind.table} SET supply_amount=:s, tax_amount=:t, "
            f"total_amount=:total WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "s": supply, "t": tax, "total": supply + tax, "id": return_id},
    )


def _open_item(connection, scoped, kind: ReturnKind, source_id: int):
    """원 문서의 채권·채무 1건. 잠금 순서는 원천(6) → 채권·채무(7)다."""
    row = connection.execute(
        text(
            f"SELECT id, amount, partner_id, currency FROM erp.{kind.open_item} "
            f"WHERE {_S} AND {kind.source_fk}=:id FOR UPDATE"
        ),
        {**_s(scoped), "id": source_id},
    ).first()
    if row is None:
        raise _locked(
            f"원 {kind.source_label}의 {kind.open_item} 기록이 없습니다.",
            "NO_OPEN_ITEM",
        )
    return row


def confirm(context, kind: ReturnKind, return_id: int, key: str):
    def run(connection, scoped):
        head = _draft(connection, scoped, kind, return_id)
        if not head["lines"]:
            raise _locked(
                f"명세가 없는 {kind.label}은 확정할 수 없습니다.", "EMPTY_RETURN"
            )
        source_id = head[_camel(kind.source_fk)]
        item = _open_item(connection, scoped, kind, source_id)
        total = Decimal(head["totalAmount"])
        applied = connection.execute(
            text(
                f"SELECT coalesce(sum(amount), 0) FROM erp.{kind.apply} "
                f"WHERE {_S} AND {kind.open_item}_id=:id"
            ),
            {**_s(scoped), "id": item.id},
        ).scalar_one()
        adjusted = connection.execute(
            text(
                f"SELECT coalesce(sum(amount), 0) FROM erp.{kind.adjust} "
                f"WHERE {_S} AND {kind.open_item}_id=:id"
            ),
            {**_s(scoped), "id": item.id},
        ).scalar_one()
        if applied + adjusted + total > item.amount:
            raise _locked(
                "반품 금액이 남은 잔액을 넘습니다. 소명·조정을 먼저 정리하세요.",
                "OVER_BALANCE",
                balance=str(item.amount - applied - adjusted),
            )
        connection.execute(
            text(
                f"UPDATE erp.{kind.table} SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": return_id},
        )
        connection.execute(
            text(
                f"INSERT INTO erp.{kind.adjust} (workspace_id, generation_id, "
                f"{kind.open_item}_id, partner_id, adjust_kind, amount, adjusted_on, "
                "source_id, reason, apply_key) VALUES (:w, :g, :item, :partner, "
                "'RETURN_CREDIT', :amount, :on, :source, :reason, :apply_key)"
            ),
            {
                **_s(scoped),
                "item": item.id,
                "partner": item.partner_id,
                "amount": total,
                "on": head["returnedOn"],
                "source": return_id,
                "reason": head["reason"],
                "apply_key": f"{kind.table}:{return_id}",
            },
        )
        posting.post(connection, scoped, kind.source_posting, return_id)
        return _one(connection, scoped, kind, return_id), kind.table, return_id

    return _action(context, f"erp.{kind.table}.confirm", key, {"id": return_id}, run)


def cancel(context, kind: ReturnKind, return_id: int, reason: str, key: str):
    def run(connection, scoped):
        head = _one(connection, scoped, kind, return_id, lock=True)
        if head["status"] == "cancelled":
            raise _locked(f"이미 취소한 {kind.label}입니다.", "ALREADY_CANCELLED")
        connection.execute(
            text(f"DELETE FROM erp.{kind.adjust} WHERE {_S} AND apply_key=:apply_key"),
            {**_s(scoped), "apply_key": f"{kind.table}:{return_id}"},
        )
        connection.execute(
            text(
                f"UPDATE erp.{kind.table} SET status='cancelled', "
                f"cancelled_at=clock_timestamp(), cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": return_id, "reason": reason},
        )
        return _one(connection, scoped, kind, return_id), kind.table, return_id

    body = {"id": return_id, "reason": reason}
    return _action(context, f"erp.{kind.table}.cancel", key, body, run)


def delete(context, kind: ReturnKind, return_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft(connection, scoped, kind, return_id)
        for sql in (
            f"DELETE FROM erp.{kind.line_table} WHERE {_S} AND {kind.fk}=:id",
            f"DELETE FROM erp.{kind.table} WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": return_id})
        return {}, kind.table, return_id

    _action(context, f"erp.{kind.table}.delete", key, {"id": return_id}, run, 204)


def returnable(context, kind: ReturnKind, source_id: int):
    """화면이 보여 줄 '아직 반품할 수 있는 수량'. 저장하지 않는다."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        if not _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.{kind.source} WHERE {_S} AND id=:id",
            id=source_id,
        ):
            raise not_found()
        allowed = _returnable(connection, scoped, kind, source_id, 0)
        prices = _source_prices(connection, scoped, kind, source_id)
        names = {
            r.id: (r.item_code, r.name)
            for r in connection.execute(
                text(f"SELECT id, item_code, name FROM erp.item WHERE {_S}"), _s(scoped)
            )
        }
        return [
            {
                "itemId": item,
                "itemCode": names[item][0],
                "itemName": names[item][1],
                "unit": unit,
                "returnableQty": str(quantity),
                "unitPrice": str(prices[item]),
            }
            for item, (quantity, unit) in sorted(allowed.items())
            if quantity > 0
        ]
