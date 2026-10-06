"""E-02 견적 · E-03 판매계획 · E-04 수주 (FS-019b).

견적: draft → confirmed → sent → accepted | rejected, 종결 전 어느 단계든 cancelled.
      confirmed 이후 내용 변경은 revision_no를 올린 새 행(개정본)으로만. 최신 = MAX(revision_no) 파생.
      상태 이력(quotation_status_history)은 추가만 한다. 그래서 견적은 삭제하지 않고 취소한다.
판매계획: draft → confirmed. 확정 후 불변. MES가 이 계획을 쓰는지는 ERP가 알 수 없다(단방향).
수주: 직접 등록 또는 견적 전환. 유효 출하지시가 생기면 헤더·라인·단가 불변(FS-006b).
쓰기는 모두 write_scope의 공간 잠금 뒤라 같은 공간의 쓰기는 직렬화된다.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from functools import partial
from typing import Any

from sqlalchemy import text

from fs.common.engine import action
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp.repository import present
from fs.erp.service import _read, invalid, not_found

MODULE = "erp"
_S = "workspace_id=:w AND generation_id=:g"
WON = Decimal(1)


def _s(context) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _locked(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


# 공통 엔진(fs.common.engine.action): 공간 잠금 → 멱등 영수증 → 처리 → 영수증 저장
_action = partial(action, MODULE)


def _rows(connection, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [present(r) for r in connection.execute(text(sql), params).mappings()]


def _exists(connection, scoped, sql: str, **params: Any) -> bool:
    return connection.execute(text(sql), {**_s(scoped), **params}).first() is not None


def _amount(qty, price, discount="0") -> str:
    """금액은 원 단위 반올림. 할인율은 %."""
    value = Decimal(qty) * Decimal(price) * (100 - Decimal(discount)) / 100
    return str(value.quantize(WON, ROUND_HALF_UP))


# 거래처·품목·일자의 판매 단가(사용 중, 적용 월 포함). 구간 겹침은 E-17이 막으므로 최대 1건.
def _price_sql(partner: str, item: str, on: str) -> str:
    return f"""(SELECT p.unit_price FROM erp.partner_item_price p
  WHERE p.workspace_id=:w AND p.generation_id=:g AND p.partner_id={partner}
    AND p.item_id={item} AND p.price_kind='SALE' AND p.is_active
    AND p.effective_from <= to_char({on}, 'YYYY-MM')
    AND (p.effective_to IS NULL OR p.effective_to >= to_char({on}, 'YYYY-MM'))
  ORDER BY p.effective_from DESC LIMIT 1)"""


def _customer(connection, scoped, partner_id: int) -> None:
    row = connection.execute(
        text(f"SELECT partner_kind, is_active FROM erp.partner WHERE {_S} AND id=:id"),
        {**_s(scoped), "id": partner_id},
    ).first()
    if row is None or row.partner_kind != "CUSTOMER":
        raise invalid("partner_id", "현재 공간의 고객 거래처를 선택하세요.")
    if not row.is_active:
        raise invalid("partner_id", "사용 중지된 거래처입니다.")


def _dates(first, last, field: str, message: str) -> None:
    if last is not None and last < first:
        raise invalid(field, message)


def _priced_lines(
    connection, scoped, partner_id: int, on, lines: list[dict], qty_key: str
) -> list[dict[str, Any]]:
    """라인 검증 + 단위(품목 기준 단위)·단가(비우면 거래처 단가) 결정."""
    items = {
        r.id: r
        for r in connection.execute(
            text(f"SELECT id, base_unit, is_active FROM erp.item WHERE {_S}"),
            _s(scoped),
        )
    }
    rows = []
    for n, line in enumerate(lines, 1):
        where = f"{n}번째 라인: "
        item = items.get(line["item_id"])
        if item is None or not item.is_active:
            raise invalid("lines", where + "사용 중인 품목을 선택하세요.")
        if Decimal(line[qty_key]) <= 0:
            raise invalid("lines", where + "수량은 0보다 커야 합니다.")
        if Decimal(line.get("discount_rate") or "0") > 100:
            raise invalid("lines", where + "할인율은 0~100입니다.")
        price = line.get("unit_price")
        if price is None:
            price = connection.execute(
                text("SELECT " + _price_sql(":p", ":i", "CAST(:on AS date)")),
                {**_s(scoped), "p": partner_id, "i": item.id, "on": on},
            ).scalar_one()
            if price is None:
                raise invalid(
                    "lines", where + "적용할 거래처 단가가 없습니다. 단가를 입력하세요."
                )
        rows.append({**line, "line_no": n, "unit": item.base_unit, "unit_price": price})
    return rows


def _insert_lines(connection, scoped, table: str, parent: str, parent_id: int, rows):
    connection.execute(
        text(f"DELETE FROM erp.{table} WHERE {_S} AND {parent}=:p"),
        {**_s(scoped), "p": parent_id},
    )
    for row in rows:
        values = {parent: parent_id, **row}
        connection.execute(
            text(
                f"INSERT INTO erp.{table} (workspace_id, generation_id, {','.join(values)}) "
                f"VALUES (:w, :g, {','.join(':' + k for k in values)})"
            ),
            {**_s(scoped), **values},
        )


# ---- E-02 견적 ----
QUOTE_SQL = """
SELECT * FROM (
  SELECT q.id, q.quote_no, q.revision_no, q.partner_id, q.quoted_on, q.valid_until,
         q.status, q.remark, q.created_at,
         q.revision_no = max(q.revision_no) OVER (PARTITION BY q.quote_no) is_latest,
         count(*) OVER (PARTITION BY q.quote_no) revision_count,
         (SELECT min(o.id) FROM erp.sales_order o
           WHERE o.workspace_id=q.workspace_id AND o.generation_id=q.generation_id
             AND o.quotation_id=q.id) sales_order_id
  FROM erp.quotation q WHERE q.workspace_id=:w AND q.generation_id=:g
) x WHERE true"""
QUOTE_LINE_SQL = f"""
SELECT l.id, l.quotation_id, l.line_no, l.item_id, l.quote_qty, l.unit, l.unit_price,
       l.discount_rate, {_price_sql("q.partner_id", "l.item_id", "q.quoted_on")} master_price
FROM erp.quotation_line l
JOIN erp.quotation q ON q.workspace_id=l.workspace_id AND q.generation_id=l.generation_id
 AND q.id=l.quotation_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.quotation_id = ANY(:ids)
ORDER BY l.quotation_id, l.line_no"""
HISTORY_SQL = f"""
SELECT id, quotation_id, status, changed_at, reason FROM erp.quotation_status_history
WHERE {_S} AND quotation_id = ANY(:ids) ORDER BY changed_at, id"""
QUOTE_FLOW = {
    "draft": {"confirmed", "cancelled"},
    "confirmed": {"sent", "cancelled"},
    "sent": {"accepted", "rejected", "cancelled"},
}
REVISABLE = {"confirmed", "sent", "rejected"}


def _quotes(connection, scoped, where: str, **params: Any) -> list[dict[str, Any]]:
    quotes = _rows(
        connection,
        QUOTE_SQL + where + " ORDER BY quote_no DESC, revision_no DESC",
        {**_s(scoped), **params},
    )
    ids = [q["id"] for q in quotes]
    lines = _rows(connection, QUOTE_LINE_SQL, {**_s(scoped), "ids": ids})
    history = _rows(connection, HISTORY_SQL, {**_s(scoped), "ids": ids})
    for quote in quotes:
        quote["lines"] = [
            {
                **line,
                "amount": _amount(
                    line["quoteQty"], line["unitPrice"], line["discountRate"]
                ),
                # 출처는 저장하지 않는다. 현재 거래처 단가와 같은지로 보여 준다.
                "priceSource": "partner_price"
                if line["masterPrice"] is not None
                and Decimal(line["masterPrice"]) == Decimal(line["unitPrice"])
                else "manual",
            }
            for line in lines
            if line["quotationId"] == quote["id"]
        ]
        quote["totalAmount"] = str(sum(Decimal(x["amount"]) for x in quote["lines"]))
        quote["history"] = [h for h in history if h["quotationId"] == quote["id"]]
    return quotes


def _quote(connection, scoped, quote_id: int) -> dict[str, Any]:
    found = _quotes(connection, scoped, " AND id=:id", id=quote_id)
    if not found:
        raise not_found()
    return found[0]


def _latest(connection, scoped, quote_id: int) -> dict[str, Any]:
    quote = _quote(connection, scoped, quote_id)
    if not quote["isLatest"]:
        raise _locked("이전 개정본은 읽기 전용입니다.", "NOT_LATEST_REVISION")
    return quote


def _draft_quote(connection, scoped, quote_id: int) -> dict[str, Any]:
    quote = _latest(connection, scoped, quote_id)
    if quote["status"] != "draft":
        raise _locked(
            "작성 중인 견적만 고칠 수 있습니다. 개정본을 만드세요.", "QUOTATION_LOCKED"
        )
    return quote


def _history(connection, scoped, quote_id: int, status: str, reason=None) -> None:
    connection.execute(
        text(
            "INSERT INTO erp.quotation_status_history "
            "(workspace_id, generation_id, quotation_id, status, changed_at, reason) "
            "VALUES (:w, :g, :id, :status, clock_timestamp(), :reason)"
        ),
        {**_s(scoped), "id": quote_id, "status": status, "reason": reason},
    )


def list_quotations(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _quotes(
            connection, read_scope(connection, context, MODULE), " AND is_latest"
        )


def quotation_revisions(context, quote_id: int) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        quote = _quote(connection, scoped, quote_id)
        return _quotes(connection, scoped, " AND quote_no=:no", no=quote["quoteNo"])


def create_quotation(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        if _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.quotation WHERE {_S} AND quote_no=:no",
            no=values["quote_no"],
        ):
            raise invalid("quote_no", "이미 사용 중인 견적번호입니다.")
        _customer(connection, scoped, values["partner_id"])
        _dates(
            values["quoted_on"],
            values["valid_until"],
            "valid_until",
            "유효기한은 견적일 이후여야 합니다.",
        )
        quote_id = connection.execute(
            text(
                "INSERT INTO erp.quotation (workspace_id, generation_id, quote_no, "
                "partner_id, quoted_on, valid_until, remark) VALUES "
                "(:w, :g, :quote_no, :partner_id, :quoted_on, :valid_until, :remark) "
                "RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        _history(connection, scoped, quote_id, "draft")
        return _quote(connection, scoped, quote_id), "quotation", quote_id

    return _action(context, "erp.quotation.create", key, values, run, 201)


def update_quotation(context, quote_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        quote = _draft_quote(connection, scoped, quote_id)
        if "partner_id" in values:
            _customer(connection, scoped, values["partner_id"])
        quoted_on = values.get("quoted_on", quote["quotedOn"])
        valid_until = values.get("valid_until", quote["validUntil"])
        _dates(
            quoted_on, valid_until, "valid_until", "유효기한은 견적일 이후여야 합니다."
        )
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE erp.quotation SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": quote_id},
        )
        return _quote(connection, scoped, quote_id), "quotation", quote_id

    return _action(
        context, "erp.quotation.update", key, {"id": quote_id, **values}, run
    )


def set_quotation_lines(context, quote_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        quote = _draft_quote(connection, scoped, quote_id)
        rows = _priced_lines(
            connection,
            scoped,
            quote["partnerId"],
            quote["quotedOn"],
            lines,
            "quote_qty",
        )
        _insert_lines(
            connection, scoped, "quotation_line", "quotation_id", quote_id, rows
        )
        return _quote(connection, scoped, quote_id), "quotation", quote_id

    return _action(
        context, "erp.quotation.lines", key, {"id": quote_id, "lines": lines}, run
    )


def change_quotation_status(context, quote_id: int, status: str, reason, key: str):
    def run(connection, scoped):
        quote = _latest(connection, scoped, quote_id)
        if status not in QUOTE_FLOW.get(quote["status"], set()):
            raise _locked(
                "지금 상태에서는 바꿀 수 없는 상태입니다.",
                "INVALID_TRANSITION",
                current=quote["status"],
            )
        if status in ("rejected", "cancelled") and not reason:
            raise invalid("reason", "사유를 입력하세요.")
        if status == "confirmed" and not quote["lines"]:
            raise _locked("라인이 없는 견적은 확정할 수 없습니다.", "EMPTY_QUOTATION")
        connection.execute(
            text(f"UPDATE erp.quotation SET status=:status WHERE {_S} AND id=:id"),
            {**_s(scoped), "status": status, "id": quote_id},
        )
        _history(connection, scoped, quote_id, status, reason)
        return _quote(connection, scoped, quote_id), "quotation", quote_id

    body = {"id": quote_id, "status": status, "reason": reason}
    return _action(context, "erp.quotation.status", key, body, run)


def revise_quotation(context, quote_id: int, key: str):
    """확정 이후 견적을 새 개정본(draft)으로 복제한다. 원본은 그대로 남는다."""

    def run(connection, scoped):
        quote = _latest(connection, scoped, quote_id)
        if quote["status"] not in REVISABLE:
            raise _locked(
                "확정·제출·거절된 견적만 개정할 수 있습니다.",
                "REVISE_NOT_ALLOWED",
                current=quote["status"],
            )
        new_id = connection.execute(
            text(
                "INSERT INTO erp.quotation (workspace_id, generation_id, quote_no, "
                "revision_no, partner_id, quoted_on, valid_until, remark) "
                "SELECT workspace_id, generation_id, quote_no, revision_no + 1, "
                f"partner_id, quoted_on, valid_until, remark FROM erp.quotation "
                f"WHERE {_S} AND id=:id RETURNING id"
            ),
            {**_s(scoped), "id": quote_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO erp.quotation_line (workspace_id, generation_id, quotation_id, "
                "line_no, item_id, quote_qty, unit, unit_price, discount_rate) "
                "SELECT workspace_id, generation_id, :new, line_no, item_id, quote_qty, "
                f"unit, unit_price, discount_rate FROM erp.quotation_line "
                f"WHERE {_S} AND quotation_id=:id"
            ),
            {**_s(scoped), "id": quote_id, "new": new_id},
        )
        _history(
            connection, scoped, new_id, "draft", f"{quote['revisionNo']}차에서 개정"
        )
        return _quote(connection, scoped, new_id), "quotation", new_id

    return _action(context, "erp.quotation.revise", key, {"id": quote_id}, run, 201)


def convert_quotation(context, quote_id: int, values: dict[str, Any], key: str):
    """제출·수락된 최신 견적을 수주로 전환한다. 할인은 수주 단가에 반영한다."""

    def run(connection, scoped):
        quote = _latest(connection, scoped, quote_id)
        if quote["salesOrderId"] is not None:
            raise _locked(
                "이미 수주로 전환된 견적입니다.",
                "ALREADY_CONVERTED",
                salesOrderId=quote["salesOrderId"],
            )
        if quote["status"] not in ("sent", "accepted"):
            raise _locked(
                "제출 또는 수락된 견적만 수주로 전환할 수 있습니다.",
                "INVALID_TRANSITION",
                current=quote["status"],
            )
        lines = [
            {
                "line_no": line["lineNo"],
                "item_id": line["itemId"],
                "order_qty": line["quoteQty"],
                "unit": line["unit"],
                "unit_price": str(
                    (
                        Decimal(line["unitPrice"])
                        * (100 - Decimal(line["discountRate"]))
                        / 100
                    ).quantize(Decimal("0.0001"), ROUND_HALF_UP)
                ),
            }
            for line in quote["lines"]
        ]
        order_id = _insert_order(
            connection,
            scoped,
            {**values, "partner_id": quote["partnerId"], "quotation_id": quote_id},
            lines,
        )
        if quote["status"] == "sent":
            connection.execute(
                text(
                    f"UPDATE erp.quotation SET status='accepted' WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "id": quote_id},
            )
            _history(
                connection,
                scoped,
                quote_id,
                "accepted",
                f"수주 {values['order_no']} 전환",
            )
        return _order(connection, scoped, order_id), "sales_order", order_id

    body = {"id": quote_id, **values}
    return _action(context, "erp.quotation.convert", key, body, run, 201)


# ---- E-03 판매계획 ----
PLAN_SQL = f"""
SELECT id, plan_code, target_month, status, confirmed_at, created_at
FROM erp.sales_plan WHERE {_S}"""
PLAN_LINE_SQL = f"""
SELECT id, sales_plan_id, item_id, plan_qty, unit FROM erp.sales_plan_line
WHERE {_S} AND sales_plan_id = ANY(:ids) ORDER BY sales_plan_id, id"""


def _plans(connection, scoped, where: str = "", **params: Any) -> list[dict[str, Any]]:
    plans = _rows(
        connection,
        PLAN_SQL + where + " ORDER BY target_month DESC, plan_code",
        {**_s(scoped), **params},
    )
    lines = _rows(
        connection, PLAN_LINE_SQL, {**_s(scoped), "ids": [p["id"] for p in plans]}
    )
    for plan in plans:
        plan["lines"] = [x for x in lines if x["salesPlanId"] == plan["id"]]
    return plans


def _draft_plan(connection, scoped, plan_id: int) -> dict[str, Any]:
    found = _plans(connection, scoped, " AND id=:id", id=plan_id)
    if not found:
        raise not_found()
    if found[0]["status"] != "draft":
        raise _locked(
            "확정된 판매계획은 바꿀 수 없습니다. 새 계획을 만드세요.", "PLAN_CONFIRMED"
        )
    return found[0]


def _plan_code_free(connection, scoped, code: str, plan_id: int | None) -> None:
    if _exists(
        connection,
        scoped,
        f"SELECT 1 FROM erp.sales_plan WHERE {_S} AND plan_code=:code "
        "AND id IS DISTINCT FROM :id",
        code=code,
        id=plan_id,
    ):
        raise invalid("plan_code", "이미 사용 중인 코드입니다.")


def list_plans(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _plans(connection, read_scope(connection, context, MODULE))


def create_plan(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _plan_code_free(connection, scoped, values["plan_code"], None)
        plan_id = connection.execute(
            text(
                "INSERT INTO erp.sales_plan (workspace_id, generation_id, plan_code, "
                "target_month) VALUES (:w, :g, :plan_code, :target_month) RETURNING id"
            ),
            {**_s(scoped), **values},
        ).scalar_one()
        return (
            _plans(connection, scoped, " AND id=:id", id=plan_id)[0],
            "sales_plan",
            plan_id,
        )

    return _action(context, "erp.sales_plan.create", key, values, run, 201)


def update_plan(context, plan_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        if "plan_code" in values:
            _plan_code_free(connection, scoped, values["plan_code"], plan_id)
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE erp.sales_plan SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": plan_id},
        )
        return (
            _plans(connection, scoped, " AND id=:id", id=plan_id)[0],
            "sales_plan",
            plan_id,
        )

    return _action(
        context, "erp.sales_plan.update", key, {"id": plan_id, **values}, run
    )


def set_plan_lines(context, plan_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        items = {
            r.id: r
            for r in connection.execute(
                text(f"SELECT id, base_unit, is_active FROM erp.item WHERE {_S}"),
                _s(scoped),
            )
        }
        rows, seen = [], set()
        for n, line in enumerate(lines, 1):
            item = items.get(line["item_id"])
            if item is None or not item.is_active:
                raise invalid("lines", f"{n}번째 라인: 사용 중인 품목을 선택하세요.")
            if item.id in seen:
                raise invalid("lines", f"{n}번째 라인: 같은 품목이 이미 있습니다.")
            seen.add(item.id)
            rows.append({**line, "unit": item.base_unit})
        _insert_lines(
            connection, scoped, "sales_plan_line", "sales_plan_id", plan_id, rows
        )
        return (
            _plans(connection, scoped, " AND id=:id", id=plan_id)[0],
            "sales_plan",
            plan_id,
        )

    return _action(
        context, "erp.sales_plan.lines", key, {"id": plan_id, "lines": lines}, run
    )


def confirm_plan(context, plan_id: int, key: str):
    def run(connection, scoped):
        plan = _draft_plan(connection, scoped, plan_id)
        if not plan["lines"]:
            raise _locked("라인이 없는 판매계획은 확정할 수 없습니다.", "EMPTY_PLAN")
        connection.execute(
            text(
                "UPDATE erp.sales_plan SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": plan_id},
        )
        return (
            _plans(connection, scoped, " AND id=:id", id=plan_id)[0],
            "sales_plan",
            plan_id,
        )

    return _action(context, "erp.sales_plan.confirm", key, {"id": plan_id}, run)


def delete_plan(context, plan_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        for sql in (
            f"DELETE FROM erp.sales_plan_line WHERE {_S} AND sales_plan_id=:id",
            f"DELETE FROM erp.sales_plan WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": plan_id})
        return {}, "sales_plan", plan_id

    _action(context, "erp.sales_plan.delete", key, {"id": plan_id}, run, 204)


# ---- E-04 수주 ----
ORDER_SQL = """
SELECT o.id, o.order_no, o.partner_id, o.ordered_on, o.due_on, o.status, o.quotation_id,
       o.created_at, q.quote_no, q.revision_no quote_revision_no,
       (SELECT count(*) FROM erp.shipment_order so
         WHERE so.workspace_id=o.workspace_id AND so.generation_id=o.generation_id
           AND so.sales_order_id=o.id AND so.status<>'cancelled') shipment_order_count
FROM erp.sales_order o
LEFT JOIN erp.quotation q ON q.workspace_id=o.workspace_id
 AND q.generation_id=o.generation_id AND q.id=o.quotation_id
WHERE o.workspace_id=:w AND o.generation_id=:g"""
# 출하 진행률: 지시 = 취소 안 된 출하지시 수량, 출하 = 확정 출하 수량 (E-04)
ORDER_LINE_SQL = """
SELECT l.id, l.sales_order_id, l.line_no, l.item_id, l.order_qty, l.unit, l.unit_price,
  coalesce((SELECT sum(sol.order_qty) FROM erp.shipment_order_line sol
    JOIN erp.shipment_order so ON so.workspace_id=sol.workspace_id
     AND so.generation_id=sol.generation_id AND so.id=sol.shipment_order_id
    WHERE sol.workspace_id=l.workspace_id AND sol.generation_id=l.generation_id
      AND sol.sales_order_line_id=l.id AND so.status<>'cancelled'), 0) instructed_qty,
  coalesce((SELECT sum(sl.shipped_qty) FROM erp.shipment_line sl
    JOIN erp.shipment sh ON sh.workspace_id=sl.workspace_id
     AND sh.generation_id=sl.generation_id AND sh.id=sl.shipment_id
    JOIN erp.shipment_order_line sol ON sol.workspace_id=sl.workspace_id
     AND sol.generation_id=sl.generation_id AND sol.id=sl.shipment_order_line_id
    WHERE sl.workspace_id=l.workspace_id AND sl.generation_id=l.generation_id
      AND sol.sales_order_line_id=l.id AND sh.status='confirmed'), 0) shipped_qty
FROM erp.sales_order_line l
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.sales_order_id = ANY(:ids)
ORDER BY l.sales_order_id, l.line_no"""


def _orders(connection, scoped, where: str = "", **params: Any) -> list[dict[str, Any]]:
    orders = _rows(
        connection,
        ORDER_SQL + where + " ORDER BY o.ordered_on DESC, o.order_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(
        connection, ORDER_LINE_SQL, {**_s(scoped), "ids": [o["id"] for o in orders]}
    )
    for order in orders:
        order["lines"] = [
            {**x, "amount": _amount(x["orderQty"], x["unitPrice"])}
            for x in lines
            if x["salesOrderId"] == order["id"]
        ]
        order["totalAmount"] = str(sum(Decimal(x["amount"]) for x in order["lines"]))
    return orders


def _order(connection, scoped, order_id: int) -> dict[str, Any]:
    found = _orders(connection, scoped, " AND o.id=:id", id=order_id)
    if not found:
        raise not_found()
    return found[0]


def _open_order(connection, scoped, order_id: int) -> dict[str, Any]:
    order = _order(connection, scoped, order_id)
    if order["status"] != "open" or order["shipmentOrderCount"]:
        raise _locked(
            "출하지시가 있거나 종결된 수주는 바꿀 수 없습니다.",
            "ORDER_LOCKED",
            current=order["status"],
        )
    return order


def _insert_order(connection, scoped, values: dict[str, Any], lines) -> int:
    if _exists(
        connection,
        scoped,
        f"SELECT 1 FROM erp.sales_order WHERE {_S} AND order_no=:no",
        no=values["order_no"],
    ):
        raise invalid("order_no", "이미 사용 중인 수주번호입니다.")
    _dates(
        values["ordered_on"],
        values["due_on"],
        "due_on",
        "납기일은 수주일 이후여야 합니다.",
    )
    order_id = connection.execute(
        text(
            "INSERT INTO erp.sales_order (workspace_id, generation_id, order_no, "
            "partner_id, ordered_on, due_on, quotation_id) VALUES "
            "(:w, :g, :order_no, :partner_id, :ordered_on, :due_on, :quotation_id) "
            "RETURNING id"
        ),
        {**_s(scoped), "quotation_id": None, **values},
    ).scalar_one()
    _insert_lines(
        connection, scoped, "sales_order_line", "sales_order_id", order_id, lines
    )
    return order_id


def list_orders(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _orders(connection, read_scope(connection, context, MODULE))


def create_order(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        header = {k: v for k, v in values.items() if k != "lines"}
        _customer(connection, scoped, header["partner_id"])
        lines = _priced_lines(
            connection,
            scoped,
            header["partner_id"],
            header["ordered_on"],
            values["lines"],
            "order_qty",
        )
        order_id = _insert_order(connection, scoped, header, lines)
        return _order(connection, scoped, order_id), "sales_order", order_id

    return _action(context, "erp.sales_order.create", key, values, run, 201)


def update_order(context, order_id: int, values: dict[str, Any], key: str):
    if not values:
        raise invalid("body", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        order = _open_order(connection, scoped, order_id)
        header = {k: v for k, v in values.items() if k != "lines"}
        if "partner_id" in header:
            if order["quotationId"] is not None:
                raise invalid(
                    "partner_id", "견적에서 전환한 수주는 거래처를 바꿀 수 없습니다."
                )
            _customer(connection, scoped, header["partner_id"])
        merged = {
            "partner_id": order["partnerId"],
            "ordered_on": order["orderedOn"],
            "due_on": order["dueOn"],
            **header,
        }
        _dates(
            merged["ordered_on"],
            merged["due_on"],
            "due_on",
            "납기일은 수주일 이후여야 합니다.",
        )
        if header:
            assignments = ",".join(f"{k}=:{k}" for k in header)
            connection.execute(
                text(f"UPDATE erp.sales_order SET {assignments} WHERE {_S} AND id=:id"),
                {**_s(scoped), **header, "id": order_id},
            )
        if "lines" in values:
            rows = _priced_lines(
                connection,
                scoped,
                merged["partner_id"],
                merged["ordered_on"],
                values["lines"],
                "order_qty",
            )
            _insert_lines(
                connection, scoped, "sales_order_line", "sales_order_id", order_id, rows
            )
        return _order(connection, scoped, order_id), "sales_order", order_id

    return _action(
        context, "erp.sales_order.update", key, {"id": order_id, **values}, run
    )


def cancel_order(context, order_id: int, key: str):
    def run(connection, scoped):
        _open_order(connection, scoped, order_id)
        connection.execute(
            text(
                f"UPDATE erp.sales_order SET status='cancelled' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": order_id},
        )
        return _order(connection, scoped, order_id), "sales_order", order_id

    return _action(context, "erp.sales_order.cancel", key, {"id": order_id}, run)
