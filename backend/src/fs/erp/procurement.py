"""E-22 구매 요청 · E-23 발주서 · E-25 구매 현황 (DSN-11 F21·F22·F26).

- 요청: draft → confirmed → ordered(발주가 끌어갈 때). 발주 전에만 취소한다.
  원천은 MANUAL·CMMS·ELB·MES이고, 수동이 아니면 원천 번호가 있어야 하며 살아 있는 요청은 하나뿐이다.
- 발주: draft → confirmed → closed. 확정 후 명세 불변이고, 바꾸려면 취소하고 다시 낸다.
- **입고 진행은 저장하지 않는다.** WMS 입고(검수 완료분)를 발주번호로 읽어 그때그때 파생한다.
  WMS가 꺼져 있으면 0으로 보지 않고 '모름'이다 — 안 받은 것과 못 보는 것은 다르다.
- 매입 단가는 판매와 같은 3단 순서다: 거래처별 매입 단가 → 구매 단가 그룹 → 품목 표준 원가.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp.revenue import line_amounts
from fs.erp.sales import _S, MODULE, _action, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found
from fs.wms import interface as wms

SEOUL = "'Asia/Seoul'"
REQUEST_SQL = """
SELECT r.id, r.request_no, r.requested_on, r.department_id, r.employee_id, r.source,
       r.source_ref, r.status, r.confirmed_at, r.cancelled_at, r.cancel_reason,
       d.code department_code, e.code employee_code
FROM erp.purchase_request r
LEFT JOIN erp.department d ON d.workspace_id=r.workspace_id
 AND d.generation_id=r.generation_id AND d.id=r.department_id
LEFT JOIN erp.employee e ON e.workspace_id=r.workspace_id
 AND e.generation_id=r.generation_id AND e.id=r.employee_id
WHERE r.workspace_id=:w AND r.generation_id=:g"""
REQUEST_LINE_SQL = """
SELECT l.id, l.purchase_request_id, l.line_no, l.item_id, l.quantity, l.unit, l.needed_on,
       i.item_code, i.name item_name,
       EXISTS (SELECT 1 FROM erp.purchase_order_line o
         WHERE o.workspace_id=l.workspace_id AND o.generation_id=l.generation_id
           AND o.purchase_request_line_id=l.id) ordered
FROM erp.purchase_request_line l
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.purchase_request_id = ANY(:ids)
ORDER BY l.purchase_request_id, l.line_no"""
ORDER_SQL = """
SELECT o.id, o.po_no, o.partner_id, o.ordered_on, o.due_on, o.department_id, o.project_id,
       o.currency, o.supply_amount, o.tax_amount, o.total_amount, o.status, o.confirmed_at,
       o.closed_at, o.cancelled_at, o.cancel_reason, p.partner_code, p.partner_name,
       d.code department_code, j.code project_code,
       EXISTS (SELECT 1 FROM erp.purchase_invoice v
         WHERE v.workspace_id=o.workspace_id AND v.generation_id=o.generation_id
           AND v.purchase_order_id=o.id AND v.status <> 'cancelled') invoiced
FROM erp.purchase_order o
JOIN erp.partner p ON p.workspace_id=o.workspace_id AND p.generation_id=o.generation_id
 AND p.id=o.partner_id
LEFT JOIN erp.department d ON d.workspace_id=o.workspace_id
 AND d.generation_id=o.generation_id AND d.id=o.department_id
LEFT JOIN erp.project j ON j.workspace_id=o.workspace_id
 AND j.generation_id=o.generation_id AND j.id=o.project_id
WHERE o.workspace_id=:w AND o.generation_id=:g"""
ORDER_LINE_SQL = """
SELECT l.id, l.purchase_order_id, l.line_no, l.item_id, l.quantity, l.unit, l.unit_price,
       l.supply_amount, l.tax_amount, l.total_amount, l.purchase_request_line_id, l.due_on,
       i.item_code, i.name item_name
FROM erp.purchase_order_line l
JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id
 AND i.id=l.item_id
WHERE l.workspace_id=:w AND l.generation_id=:g AND l.purchase_order_id = ANY(:ids)
ORDER BY l.purchase_order_id, l.line_no"""
# 매입 단가: 거래처별 매입 단가 → 구매 단가 그룹(시작일 최신) → 품목 표준 원가(DSN-11 F06).
PURCHASE_PRICE_SQL = """COALESCE(
 (SELECT p.unit_price FROM erp.partner_item_price p
  WHERE p.workspace_id=:w AND p.generation_id=:g AND p.partner_id=:partner
    AND p.item_id=:item AND p.price_kind='PURCHASE' AND p.is_active
    AND p.effective_from <= to_char(CAST(:on AS date), 'YYYY-MM')
    AND (p.effective_to IS NULL OR p.effective_to >= to_char(CAST(:on AS date), 'YYYY-MM'))
  ORDER BY p.effective_from DESC LIMIT 1),
 (SELECT gp.unit_price FROM erp.price_group_price gp
  JOIN erp.price_group pg ON pg.workspace_id=gp.workspace_id
   AND pg.generation_id=gp.generation_id AND pg.id=gp.price_group_id AND pg.is_active
  JOIN erp.partner pr ON pr.workspace_id=gp.workspace_id
   AND pr.generation_id=gp.generation_id AND pr.purchase_price_group_id=pg.id
  WHERE gp.workspace_id=:w AND gp.generation_id=:g AND pr.id=:partner
    AND gp.item_id=:item AND gp.valid_from <= CAST(:on AS date)
  ORDER BY gp.valid_from DESC LIMIT 1),
 (SELECT si.standard_cost FROM erp.item si
  WHERE si.workspace_id=:w AND si.generation_id=:g AND si.id=:item))"""


def _today(connection) -> date:
    return connection.execute(
        text(f"SELECT (clock_timestamp() AT TIME ZONE {SEOUL})::date")
    ).scalar_one()


def _next_no(connection, scoped, table: str, column: str, prefix: str) -> str:
    """사업장 시간대 날짜로 하루 단위 일련번호를 매긴다(UTC로 자르면 날이 어긋난다)."""
    today = _today(connection)
    taken = connection.execute(
        text(
            f"SELECT {column} FROM erp.{table} WHERE {_S} AND {column} LIKE :like "
            f"ORDER BY {column} DESC LIMIT 1"
        ),
        {**_s(scoped), "like": f"{prefix}-{today:%Y%m%d}-%"},
    ).scalar_one_or_none()
    serial = int(taken.rsplit("-", 1)[1]) + 1 if taken else 1
    return f"{prefix}-{today:%Y%m%d}-{serial:03d}"


# ---- E-22 구매 요청 ----
def _requests(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        REQUEST_SQL + where + " ORDER BY r.requested_on DESC, r.request_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(
        connection, REQUEST_LINE_SQL, {**_s(scoped), "ids": [h["id"] for h in heads]}
    )
    for head in heads:
        head["lines"] = [x for x in lines if x["purchaseRequestId"] == head["id"]]
    return heads


def _request(connection, scoped, request_id: int, lock: bool = False):
    if lock:
        connection.execute(
            text(
                f"SELECT id FROM erp.purchase_request WHERE {_S} AND id=:id FOR UPDATE"
            ),
            {**_s(scoped), "id": request_id},
        )
    found = _requests(connection, scoped, " AND r.id=:id", id=request_id)
    if not found:
        raise not_found()
    return found[0]


def list_requests(context):
    with _read() as connection:
        return _requests(connection, read_scope(connection, context, MODULE))


def _master(connection, scoped, table: str, row_id: int | None, field: str) -> None:
    if row_id is None:
        return
    if not _exists(
        connection,
        scoped,
        f"SELECT 1 FROM erp.{table} WHERE {_S} AND id=:id AND is_active",
        id=row_id,
    ):
        raise invalid(field, "현재 공간의 사용 중인 대상을 선택하세요.")


def create_request(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _master(
            connection,
            scoped,
            "department",
            values.get("department_id"),
            "department_id",
        )
        _master(
            connection, scoped, "employee", values.get("employee_id"), "employee_id"
        )
        if values["source"] != "MANUAL" and _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.purchase_request WHERE {_S} AND source=:source "
            "AND source_ref=:source_ref AND status <> 'cancelled'",
            source=values["source"],
            source_ref=values["source_ref"],
        ):
            raise invalid("source_ref", "같은 원천으로 살아 있는 요청이 이미 있습니다.")
        request_no = _next_no(
            connection, scoped, "purchase_request", "request_no", "PR"
        )
        request_id = connection.execute(
            text(
                "INSERT INTO erp.purchase_request (workspace_id, generation_id, request_no, "
                "requested_on, department_id, employee_id, source, source_ref) VALUES "
                "(:w, :g, :no, :requested_on, :department_id, :employee_id, :source, "
                ":source_ref) RETURNING id"
            ),
            {**_s(scoped), **values, "no": request_no},
        ).scalar_one()
        return _request(connection, scoped, request_id), "purchase_request", request_id

    return _action(context, "erp.purchase_request.create", key, values, run, 201)


def _request_draft(connection, scoped, request_id: int):
    request = _request(connection, scoped, request_id, lock=True)
    if request["status"] != "draft":
        raise _locked("작성 중인 요청만 고칠 수 있습니다.", "REQUEST_LOCKED")
    return request


def set_request_lines(context, request_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        _request_draft(connection, scoped, request_id)
        items = {
            r.id: r
            for r in connection.execute(
                text(
                    f"SELECT id, base_unit, is_active, track_stock FROM erp.item WHERE {_S}"
                ),
                _s(scoped),
            )
        }
        connection.execute(
            text(
                f"DELETE FROM erp.purchase_request_line WHERE {_S} AND purchase_request_id=:id"
            ),
            {**_s(scoped), "id": request_id},
        )
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            item = items.get(line["item_id"])
            if item is None or not item.is_active:
                raise invalid("lines", where + "사용 중인 품목을 선택하세요.")
            if Decimal(line["quantity"]) <= 0:
                raise invalid("lines", where + "수량은 0보다 커야 합니다.")
            connection.execute(
                text(
                    "INSERT INTO erp.purchase_request_line (workspace_id, generation_id, "
                    "purchase_request_id, line_no, item_id, quantity, unit, needed_on) "
                    "VALUES (:w, :g, :id, :n, :item_id, :quantity, :unit, :needed_on)"
                ),
                {
                    **_s(scoped),
                    **line,
                    "unit": line.get("unit") or item.base_unit,
                    "id": request_id,
                    "n": n,
                },
            )
        return _request(connection, scoped, request_id), "purchase_request", request_id

    body = {"id": request_id, "lines": lines}
    return _action(context, "erp.purchase_request.lines", key, body, run)


def confirm_request(context, request_id: int, key: str):
    def run(connection, scoped):
        request = _request_draft(connection, scoped, request_id)
        if not request["lines"]:
            raise _locked("명세가 없는 요청은 확정할 수 없습니다.", "EMPTY_REQUEST")
        connection.execute(
            text(
                "UPDATE erp.purchase_request SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": request_id},
        )
        return _request(connection, scoped, request_id), "purchase_request", request_id

    return _action(
        context, "erp.purchase_request.confirm", key, {"id": request_id}, run
    )


def cancel_request(context, request_id: int, reason: str, key: str):
    def run(connection, scoped):
        request = _request(connection, scoped, request_id, lock=True)
        if request["status"] in ("ordered", "cancelled"):
            raise _locked("발주로 넘어갔거나 이미 취소된 요청입니다.", "REQUEST_LOCKED")
        connection.execute(
            text(
                "UPDATE erp.purchase_request SET status='cancelled', "
                f"cancelled_at=clock_timestamp(), cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": request_id, "reason": reason},
        )
        return _request(connection, scoped, request_id), "purchase_request", request_id

    body = {"id": request_id, "reason": reason}
    return _action(context, "erp.purchase_request.cancel", key, body, run)


def delete_request(context, request_id: int, key: str) -> None:
    def run(connection, scoped):
        _request_draft(connection, scoped, request_id)
        for sql in (
            f"DELETE FROM erp.purchase_request_line WHERE {_S} AND purchase_request_id=:id",
            f"DELETE FROM erp.purchase_request WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": request_id})
        return {}, "purchase_request", request_id

    _action(context, "erp.purchase_request.delete", key, {"id": request_id}, run, 204)


# ---- E-23 발주서 ----
def receipts_by_po(connection, scoped, po_nos: list[str], since: date):
    """발주번호별 입고 수량. WMS는 발주번호를 `partner_ref`에 코드 문자열로 들고 있다.

    WMS가 꺼져 있으면 None이다 — 받은 적 없는 것(0)과 알 수 없는 것을 구분한다.
    """
    if not po_nos:
        return {}
    found = wms.receipts(connection, scoped, since, _today(connection))
    if found is None:
        return None
    wanted = set(po_nos)
    totals: dict[str, dict[str, Decimal]] = {no: {} for no in po_nos}
    for notice in found:
        if notice["partnerRef"] not in wanted:
            continue
        per_item = totals[notice["partnerRef"]]
        for line in notice["lines"]:
            per_item[line["itemCode"]] = per_item.get(
                line["itemCode"], Decimal(0)
            ) + Decimal(line["acceptedQty"])
    return totals


def _progress(lines: list[dict], received: dict[str, Decimal] | None) -> dict[str, Any]:
    """입고 진행은 저장하지 않고 발주 명세와 WMS 입고 수량을 맞대어 파생한다."""
    if received is None:
        return {"state": "UNKNOWN", "lines": []}
    detail = []
    for line in lines:
        got = received.get(line["itemCode"], Decimal(0))
        ordered = Decimal(line["quantity"])
        detail.append(
            {
                "lineNo": line["lineNo"],
                "itemCode": line["itemCode"],
                "orderedQty": str(ordered),
                "receivedQty": str(got),
                "openQty": str(max(ordered - got, Decimal(0))),
            }
        )
    total_ordered = sum((Decimal(x["orderedQty"]) for x in detail), Decimal(0))
    total_got = sum((Decimal(x["receivedQty"]) for x in detail), Decimal(0))
    if total_got <= 0:
        state = "NONE"
    elif all(Decimal(x["openQty"]) == 0 for x in detail):
        state = "COMPLETE"
    else:
        state = "PARTIAL"
    return {
        "state": state,
        "orderedQty": str(total_ordered),
        "receivedQty": str(total_got),
        "lines": detail,
    }


def _orders(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        ORDER_SQL + where + " ORDER BY o.ordered_on DESC, o.po_no DESC",
        {**_s(scoped), **params},
    )
    lines = _rows(
        connection, ORDER_LINE_SQL, {**_s(scoped), "ids": [h["id"] for h in heads]}
    )
    confirmed = [h for h in heads if h["status"] in ("confirmed", "closed")]
    live = {h["id"] for h in confirmed}
    received = (
        receipts_by_po(
            connection,
            scoped,
            [h["poNo"] for h in confirmed],
            min(date.fromisoformat(h["orderedOn"]) for h in confirmed),
        )
        if confirmed
        else {}
    )
    for head in heads:
        head["lines"] = [x for x in lines if x["purchaseOrderId"] == head["id"]]
        head["receipt"] = (
            _progress(
                head["lines"],
                None if received is None else received.get(head["poNo"], {}),
            )
            if head["id"] in live
            else {"state": "NONE", "lines": []}
        )
    return heads


def _order(connection, scoped, order_id: int, lock: bool = False):
    if lock:
        connection.execute(
            text(f"SELECT id FROM erp.purchase_order WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": order_id},
        )
    found = _orders(connection, scoped, " AND o.id=:id", id=order_id)
    if not found:
        raise not_found()
    return found[0]


def list_orders(context):
    with _read() as connection:
        return _orders(connection, read_scope(connection, context, MODULE))


def _supplier(connection, scoped, partner_id: int):
    row = connection.execute(
        text(f"SELECT partner_kind, is_active FROM erp.partner WHERE {_S} AND id=:id"),
        {**_s(scoped), "id": partner_id},
    ).first()
    if row is None or row.partner_kind not in ("SUPPLIER", "BOTH") or not row.is_active:
        raise invalid("partner_id", "현재 공간의 사용 중인 공급처를 선택하세요.")


def create_order(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        _supplier(connection, scoped, values["partner_id"])
        _master(
            connection,
            scoped,
            "department",
            values.get("department_id"),
            "department_id",
        )
        _master(connection, scoped, "project", values.get("project_id"), "project_id")
        if values.get("due_on") and values["due_on"] < values["ordered_on"]:
            raise invalid("due_on", "납기일은 발주일 이후여야 합니다.")
        po_no = _next_no(connection, scoped, "purchase_order", "po_no", "PO")
        order_id = connection.execute(
            text(
                "INSERT INTO erp.purchase_order (workspace_id, generation_id, po_no, "
                "partner_id, ordered_on, due_on, department_id, project_id, "
                "supply_amount, tax_amount, total_amount) VALUES "
                "(:w, :g, :no, :partner_id, :ordered_on, :due_on, :department_id, "
                ":project_id, 0, 0, 0) RETURNING id"
            ),
            {**_s(scoped), **values, "no": po_no},
        ).scalar_one()
        return _order(connection, scoped, order_id), "purchase_order", order_id

    return _action(context, "erp.purchase_order.create", key, values, run, 201)


def _order_draft(connection, scoped, order_id: int):
    order = _order(connection, scoped, order_id, lock=True)
    if order["status"] != "draft":
        raise _locked("작성 중인 발주만 고칠 수 있습니다.", "ORDER_LOCKED")
    return order


def set_order_lines(context, order_id: int, lines: list[dict], key: str):
    def run(connection, scoped):
        order = _order_draft(connection, scoped, order_id)
        items = {
            r.id: r
            for r in connection.execute(
                text(
                    "SELECT id, base_unit, is_active, tax_category FROM erp.item "
                    f"WHERE {_S}"
                ),
                _s(scoped),
            )
        }
        rows = []
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            item = items.get(line["item_id"])
            if item is None or not item.is_active:
                raise invalid("lines", where + "사용 중인 품목을 선택하세요.")
            if Decimal(line["quantity"]) <= 0:
                raise invalid("lines", where + "수량은 0보다 커야 합니다.")
            price = line.get("unit_price")
            if price is None:
                price = connection.execute(
                    text("SELECT " + PURCHASE_PRICE_SQL),
                    {
                        **_s(scoped),
                        "partner": order["partnerId"],
                        "item": item.id,
                        "on": order["orderedOn"],
                    },
                ).scalar_one()
                if price is None:
                    raise invalid(
                        "lines",
                        where + "적용할 매입 단가가 없습니다. 단가를 입력하세요.",
                    )
            supply, tax = line_amounts(line["quantity"], price, item.tax_category)
            rows.append(
                {
                    **line,
                    "unit": line.get("unit") or item.base_unit,
                    "unit_price": price,
                    "supply_amount": supply,
                    "tax_amount": tax,
                    "total_amount": supply + tax,
                }
            )
        _write_order_lines(connection, scoped, order_id, rows)
        return _order(connection, scoped, order_id), "purchase_order", order_id

    body = {"id": order_id, "lines": lines}
    return _action(context, "erp.purchase_order.lines", key, body, run)


def _write_order_lines(connection, scoped, order_id: int, rows: list[dict]) -> None:
    connection.execute(
        text(
            f"DELETE FROM erp.purchase_order_line WHERE {_S} AND purchase_order_id=:id"
        ),
        {**_s(scoped), "id": order_id},
    )
    for n, row in enumerate(rows, 1):
        connection.execute(
            text(
                "INSERT INTO erp.purchase_order_line (workspace_id, generation_id, "
                "purchase_order_id, line_no, item_id, quantity, unit, unit_price, "
                "supply_amount, tax_amount, total_amount, purchase_request_line_id, due_on) "
                "VALUES (:w, :g, :id, :n, :item_id, :quantity, :unit, :unit_price, "
                ":supply_amount, :tax_amount, :total_amount, :purchase_request_line_id, "
                ":due_on)"
            ),
            {
                **_s(scoped),
                "purchase_request_line_id": None,
                "due_on": None,
                **row,
                "id": order_id,
                "n": n,
            },
        )
    supply = sum((r["supply_amount"] for r in rows), Decimal(0))
    tax = sum((r["tax_amount"] for r in rows), Decimal(0))
    connection.execute(
        text(
            "UPDATE erp.purchase_order SET supply_amount=:s, tax_amount=:t, "
            f"total_amount=:total WHERE {_S} AND id=:id"
        ),
        {**_s(scoped), "s": supply, "t": tax, "total": supply + tax, "id": order_id},
    )


def load_request(context, order_id: int, request_id: int, key: str):
    """확정된 구매 요청의 아직 발주되지 않은 명세를 발주 명세로 끌어온다."""

    def run(connection, scoped):
        order = _order_draft(connection, scoped, order_id)
        request = _request(connection, scoped, request_id, lock=True)
        if request["status"] not in ("confirmed", "ordered"):
            raise _locked("확정한 요청만 불러올 수 있습니다.", "REQUEST_NOT_CONFIRMED")
        pending = [line for line in request["lines"] if not line["ordered"]]
        if not pending:
            raise _locked("이미 모두 발주한 요청입니다.", "REQUEST_ALREADY_ORDERED")
        items = {
            r.id: r
            for r in connection.execute(
                text(f"SELECT id, tax_category FROM erp.item WHERE {_S}"), _s(scoped)
            )
        }
        rows = [
            {
                "item_id": x["itemId"],
                "quantity": x["quantity"],
                "unit": x["unit"],
                "unit_price": None,
                "purchase_request_line_id": x["id"],
                "due_on": x["neededOn"],
            }
            for x in pending
        ]
        for row in rows:
            row["unit_price"] = connection.execute(
                text("SELECT " + PURCHASE_PRICE_SQL),
                {
                    **_s(scoped),
                    "partner": order["partnerId"],
                    "item": row["item_id"],
                    "on": order["orderedOn"],
                },
            ).scalar_one()
            if row["unit_price"] is None:
                raise _locked(
                    "매입 단가가 없는 품목이 있습니다. 단가를 먼저 등록하세요.",
                    "NO_PURCHASE_PRICE",
                )
            supply, tax = line_amounts(
                row["quantity"], row["unit_price"], items[row["item_id"]].tax_category
            )
            row.update(supply_amount=supply, tax_amount=tax, total_amount=supply + tax)
        # 불러오기는 명세를 갈아끼운다(작성 중이라 지울 것이 없거나 다시 고르는 중이다).
        _write_order_lines(connection, scoped, order_id, rows)
        return _order(connection, scoped, order_id), "purchase_order", order_id

    body = {"id": order_id, "requestId": request_id}
    return _action(context, "erp.purchase_order.load", key, body, run)


def confirm_order(context, order_id: int, key: str):
    def run(connection, scoped):
        order = _order_draft(connection, scoped, order_id)
        _supplier(connection, scoped, order["partnerId"])
        if not order["lines"]:
            raise _locked("명세가 없는 발주는 확정할 수 없습니다.", "EMPTY_ORDER")
        connection.execute(
            text(
                "UPDATE erp.purchase_order SET status='confirmed', "
                f"confirmed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": order_id},
        )
        # 요청에서 끌어온 명세가 있으면 그 요청을 발주 완료로 넘긴다.
        connection.execute(
            text(
                "UPDATE erp.purchase_request SET status='ordered' WHERE "
                f"{_S} AND status='confirmed' AND id IN (SELECT rl.purchase_request_id "
                "FROM erp.purchase_order_line l JOIN erp.purchase_request_line rl "
                "ON rl.workspace_id=l.workspace_id AND rl.generation_id=l.generation_id "
                "AND rl.id=l.purchase_request_line_id WHERE l.workspace_id=:w "
                "AND l.generation_id=:g AND l.purchase_order_id=:id)"
            ),
            {**_s(scoped), "id": order_id},
        )
        return _order(connection, scoped, order_id), "purchase_order", order_id

    return _action(context, "erp.purchase_order.confirm", key, {"id": order_id}, run)


def close_order(context, order_id: int, key: str):
    def run(connection, scoped):
        order = _order(connection, scoped, order_id, lock=True)
        if order["status"] != "confirmed":
            raise _locked("확정한 발주만 종결할 수 있습니다.", "ORDER_NOT_CONFIRMED")
        connection.execute(
            text(
                "UPDATE erp.purchase_order SET status='closed', "
                f"closed_at=clock_timestamp() WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": order_id},
        )
        return _order(connection, scoped, order_id), "purchase_order", order_id

    return _action(context, "erp.purchase_order.close", key, {"id": order_id}, run)


def cancel_order(context, order_id: int, reason: str, key: str):
    def run(connection, scoped):
        order = _order(connection, scoped, order_id, lock=True)
        if order["status"] in ("closed", "cancelled"):
            raise _locked("종결했거나 이미 취소한 발주입니다.", "ORDER_LOCKED")
        if order["invoiced"]:
            raise _locked(
                "매입 전표가 있는 발주는 취소할 수 없습니다.", "INVOICE_EXISTS"
            )
        # 받은 물건이 있으면 취소하지 않는다. WMS가 꺼져 있으면 입고도 있을 수 없다.
        if order["receipt"]["state"] in ("PARTIAL", "COMPLETE"):
            raise _locked("입고가 있는 발주는 취소할 수 없습니다.", "RECEIPT_EXISTS")
        connection.execute(
            text(
                "UPDATE erp.purchase_order SET status='cancelled', "
                f"cancelled_at=clock_timestamp(), cancel_reason=:reason WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": order_id, "reason": reason},
        )
        return _order(connection, scoped, order_id), "purchase_order", order_id

    body = {"id": order_id, "reason": reason}
    return _action(context, "erp.purchase_order.cancel", key, body, run)


def delete_order(context, order_id: int, key: str) -> None:
    def run(connection, scoped):
        _order_draft(connection, scoped, order_id)
        for sql in (
            f"DELETE FROM erp.purchase_order_line WHERE {_S} AND purchase_order_id=:id",
            f"DELETE FROM erp.purchase_order WHERE {_S} AND id=:id",
        ):
            connection.execute(text(sql), {**_s(scoped), "id": order_id})
        return {}, "purchase_order", order_id

    _action(context, "erp.purchase_order.delete", key, {"id": order_id}, run, 204)
