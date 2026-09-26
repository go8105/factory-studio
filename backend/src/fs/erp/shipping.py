"""E-05 출하지시 · E-06 출하 (FS-019c). TX-07·TX-08(+TX-09) — FS-006a·FS-006b §7.

- 출하지시: 수주 명세에서 수량을 배정. 수주 라인 잠금 뒤 Σ(취소 안 된 지시) ≤ 수주수량. 부분 지시 허용.
  open → shipped | cancelled(사유 필수). 취소분은 누계에서 빠진다.
- 출하: 지시당 1건, 지시 전 라인을 지시수량 그대로 1회 출하(서버 산출). 확정과 같은 트랜잭션에서
  매출·채권 생성(TX-09, revenue.py). 첫 공개는 작성 단계 없이 등록 = 확정이다.
- 패킹번호는 MES와 독립인 수기 코드(E-G04). ERP 안의 중복 번호만 막는다.
- 수주 상태는 수량과 같은 트랜잭션에서 재계산: 유효 지시 없음 open / 있음 shipping / 전 라인 출하 완료 closed.
- 잠금 순서(순서 6): 수주 → 수주 명세 → 출하지시 → 지시 명세. 공간 잠금이 이미 직렬화하지만 순서를 코드에 둔다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.scope import read_scope
from fs.erp import revenue
from fs.erp.sales import _S, MODULE, _action, _exists, _locked, _rows, _s
from fs.erp.service import _read, invalid, not_found

SHIP_ORDER_SQL = """
SELECT so.id, so.ship_order_no, so.sales_order_id, so.ordered_on, so.status,
       so.cancel_reason, so.created_at, o.order_no, o.partner_id,
       sh.id shipment_id, sh.shipment_no
FROM erp.shipment_order so
JOIN erp.sales_order o ON o.workspace_id=so.workspace_id
 AND o.generation_id=so.generation_id AND o.id=so.sales_order_id
LEFT JOIN erp.shipment sh ON sh.workspace_id=so.workspace_id
 AND sh.generation_id=so.generation_id AND sh.shipment_order_id=so.id
WHERE so.workspace_id=:w AND so.generation_id=:g"""
SHIP_ORDER_LINE_SQL = """
SELECT sol.id, sol.shipment_order_id, sol.sales_order_line_id, sol.order_qty,
       l.line_no, l.item_id, l.unit
FROM erp.shipment_order_line sol
JOIN erp.sales_order_line l ON l.workspace_id=sol.workspace_id
 AND l.generation_id=sol.generation_id AND l.id=sol.sales_order_line_id
WHERE sol.workspace_id=:w AND sol.generation_id=:g AND sol.shipment_order_id = ANY(:ids)
ORDER BY sol.shipment_order_id, l.line_no"""
SHIPMENT_SQL = """
SELECT sh.id, sh.shipment_no, sh.shipment_order_id, sh.shipped_at, sh.status,
       so.ship_order_no, o.order_no, o.partner_id, r.id sales_record_id,
       r.supply_amount, r.tax_amount, r.total_amount
FROM erp.shipment sh
JOIN erp.shipment_order so ON so.workspace_id=sh.workspace_id
 AND so.generation_id=sh.generation_id AND so.id=sh.shipment_order_id
JOIN erp.sales_order o ON o.workspace_id=so.workspace_id
 AND o.generation_id=so.generation_id AND o.id=so.sales_order_id
LEFT JOIN erp.sales_record r ON r.workspace_id=sh.workspace_id
 AND r.generation_id=sh.generation_id AND r.shipment_id=sh.id
WHERE sh.workspace_id=:w AND sh.generation_id=:g"""
SHIPMENT_LINE_SQL = f"""
SELECT id, shipment_id, shipment_order_line_id, packing_no, shipped_qty, item_id, shipped_uom
FROM erp.shipment_line WHERE {_S} AND shipment_id = ANY(:ids) ORDER BY shipment_id, id"""


def _with_lines(connection, scoped, heads, sql: str, parent: str):
    lines = _rows(connection, sql, {**_s(scoped), "ids": [h["id"] for h in heads]})
    for head in heads:
        head["lines"] = [x for x in lines if x[parent] == head["id"]]
    return heads


def _ship_orders(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        SHIP_ORDER_SQL + where + " ORDER BY so.ordered_on DESC, so.ship_order_no DESC",
        {**_s(scoped), **params},
    )
    return _with_lines(
        connection, scoped, heads, SHIP_ORDER_LINE_SQL, "shipmentOrderId"
    )


def _ship_order(connection, scoped, ship_order_id: int) -> dict[str, Any]:
    found = _ship_orders(connection, scoped, " AND so.id=:id", id=ship_order_id)
    if not found:
        raise not_found()
    return found[0]


def _shipments(connection, scoped, where: str = "", **params: Any):
    heads = _rows(
        connection,
        SHIPMENT_SQL + where + " ORDER BY sh.shipped_at DESC, sh.shipment_no DESC",
        {**_s(scoped), **params},
    )
    return _with_lines(connection, scoped, heads, SHIPMENT_LINE_SQL, "shipmentId")


def list_ship_orders(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _ship_orders(connection, read_scope(connection, context, MODULE))


def list_shipments(context) -> list[dict[str, Any]]:
    with _read() as connection:
        return _shipments(connection, read_scope(connection, context, MODULE))


def _lock_order(connection, scoped, order_id: int):
    """수주 → 수주 명세 순서로 잠근다. 명세 {id: 행}을 돌려준다."""
    order = connection.execute(
        text(
            f"SELECT id, status, partner_id FROM erp.sales_order WHERE {_S} "
            "AND id=:id FOR UPDATE"
        ),
        {**_s(scoped), "id": order_id},
    ).first()
    if order is None:
        raise not_found()
    lines = connection.execute(
        text(
            f"SELECT id, line_no, order_qty FROM erp.sales_order_line WHERE {_S} "
            "AND sales_order_id=:id ORDER BY id FOR UPDATE"
        ),
        {**_s(scoped), "id": order_id},
    )
    return order, {line.id: line for line in lines}


def _allocated(connection, scoped, order_id: int) -> dict[int, Decimal]:
    """수주 명세별 취소 안 된 출하지시 누계. 수주 명세를 잠근 뒤에만 부른다."""
    rows = connection.execute(
        text(
            "SELECT sol.sales_order_line_id, sum(sol.order_qty) qty "
            "FROM erp.shipment_order_line sol JOIN erp.shipment_order so "
            "ON so.workspace_id=sol.workspace_id AND so.generation_id=sol.generation_id "
            "AND so.id=sol.shipment_order_id "
            "WHERE sol.workspace_id=:w AND sol.generation_id=:g "
            "AND so.sales_order_id=:id AND so.status<>'cancelled' "
            "GROUP BY sol.sales_order_line_id"
        ),
        {**_s(scoped), "id": order_id},
    )
    return {r.sales_order_line_id: r.qty for r in rows}


def refresh_order_status(connection, scoped, order_id: int) -> None:
    """수주 상태 재계산(FS-006b §7.1). 취소된 수주는 건드리지 않는다."""
    connection.execute(
        text("""
UPDATE erp.sales_order o SET status = CASE
  WHEN NOT EXISTS (
    SELECT 1 FROM erp.sales_order_line l
    WHERE l.workspace_id=o.workspace_id AND l.generation_id=o.generation_id
      AND l.sales_order_id=o.id AND l.order_qty > coalesce((
        SELECT sum(sl.shipped_qty) FROM erp.shipment_line sl
        JOIN erp.shipment_order_line sol ON sol.workspace_id=sl.workspace_id
         AND sol.generation_id=sl.generation_id AND sol.id=sl.shipment_order_line_id
        JOIN erp.shipment sh ON sh.workspace_id=sl.workspace_id
         AND sh.generation_id=sl.generation_id AND sh.id=sl.shipment_id
        WHERE sl.workspace_id=l.workspace_id AND sl.generation_id=l.generation_id
          AND sol.sales_order_line_id=l.id AND sh.status='confirmed'), 0))
  THEN 'closed'
  WHEN EXISTS (
    SELECT 1 FROM erp.shipment_order so
    WHERE so.workspace_id=o.workspace_id AND so.generation_id=o.generation_id
      AND so.sales_order_id=o.id AND so.status<>'cancelled')
  THEN 'shipping'
  ELSE 'open' END
WHERE o.workspace_id=:w AND o.generation_id=:g
  AND o.id=:id AND o.status<>'cancelled'"""),
        {**_s(scoped), "id": order_id},
    )


# ---- TX-07 출하지시 ----
def create_ship_order(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        order, order_lines = _lock_order(connection, scoped, values["sales_order_id"])
        if order.status not in ("open", "shipping"):
            raise _locked(
                "접수 또는 출하 중인 수주만 출하지시할 수 있습니다.",
                "ORDER_NOT_SHIPPABLE",
                current=order.status,
            )
        if _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.shipment_order WHERE {_S} AND ship_order_no=:no",
            no=values["ship_order_no"],
        ):
            raise invalid("ship_order_no", "이미 사용 중인 출하지시번호입니다.")
        allocated = _allocated(connection, scoped, order.id)
        seen: set[int] = set()
        for n, line in enumerate(values["lines"], 1):
            target = order_lines.get(line["sales_order_line_id"])
            if target is None:
                raise invalid("lines", f"{n}번째 라인: 이 수주의 명세가 아닙니다.")
            if target.id in seen:
                raise invalid("lines", f"{n}번째 라인: 같은 수주 명세가 이미 있습니다.")
            seen.add(target.id)
            qty = Decimal(line["order_qty"])
            if qty <= 0:
                raise invalid("lines", f"{n}번째 라인: 수량은 0보다 커야 합니다.")
            remaining = target.order_qty - allocated.get(target.id, 0)
            if qty > remaining:
                raise _locked(
                    "출하지시 합계가 수주수량을 넘습니다.",
                    "ORDER_QTY_EXCEEDED",
                    lineNo=target.line_no,
                    remainingQty=str(remaining),
                )
        ship_order_id = connection.execute(
            text(
                "INSERT INTO erp.shipment_order (workspace_id, generation_id, "
                "ship_order_no, sales_order_id, ordered_on) VALUES "
                "(:w, :g, :no, :order, :on) RETURNING id"
            ),
            {
                **_s(scoped),
                "no": values["ship_order_no"],
                "order": order.id,
                "on": values["ordered_on"],
            },
        ).scalar_one()
        for line in values["lines"]:
            connection.execute(
                text(
                    "INSERT INTO erp.shipment_order_line (workspace_id, generation_id, "
                    "shipment_order_id, sales_order_line_id, order_qty, sales_order_id) "
                    "VALUES (:w, :g, :so, :line, :qty, :order)"
                ),
                {
                    **_s(scoped),
                    "so": ship_order_id,
                    "line": line["sales_order_line_id"],
                    "qty": line["order_qty"],
                    "order": order.id,
                },
            )
        refresh_order_status(connection, scoped, order.id)
        result = _ship_order(connection, scoped, ship_order_id)
        return result, "shipment_order", ship_order_id

    return _action(context, "erp.shipment_order.create", key, values, run, 201)


def _lock_ship_order(connection, scoped, ship_order_id: int):
    """수주 → 수주 명세 → 출하지시 → 지시 명세 순서로 잠근다."""
    head = connection.execute(
        text(f"SELECT sales_order_id FROM erp.shipment_order WHERE {_S} AND id=:id"),
        {**_s(scoped), "id": ship_order_id},
    ).first()
    if head is None:
        raise not_found()
    order, _ = _lock_order(connection, scoped, head.sales_order_id)
    ship_order = connection.execute(
        text(
            f"SELECT id, status FROM erp.shipment_order WHERE {_S} AND id=:id FOR UPDATE"
        ),
        {**_s(scoped), "id": ship_order_id},
    ).one()
    lines = connection.execute(
        text(
            "SELECT sol.id, sol.order_qty, l.item_id, l.unit "
            "FROM erp.shipment_order_line sol JOIN erp.sales_order_line l "
            "ON l.workspace_id=sol.workspace_id AND l.generation_id=sol.generation_id "
            "AND l.id=sol.sales_order_line_id "
            "WHERE sol.workspace_id=:w AND sol.generation_id=:g "
            "AND sol.shipment_order_id=:id ORDER BY sol.id FOR UPDATE OF sol"
        ),
        {**_s(scoped), "id": ship_order_id},
    ).all()
    if ship_order.status != "open":
        raise _locked(
            "미출하 출하지시만 처리할 수 있습니다.",
            "SHIPMENT_ORDER_NOT_OPEN",
            current=ship_order.status,
        )
    return order, lines


def cancel_ship_order(context, ship_order_id: int, reason: str, key: str):
    def run(connection, scoped):
        order, _ = _lock_ship_order(connection, scoped, ship_order_id)
        connection.execute(
            text(
                "UPDATE erp.shipment_order SET status='cancelled', cancel_reason=:reason "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": ship_order_id, "reason": reason},
        )
        refresh_order_status(connection, scoped, order.id)
        result = _ship_order(connection, scoped, ship_order_id)
        return result, "shipment_order", ship_order_id

    body = {"id": ship_order_id, "reason": reason}
    return _action(context, "erp.shipment_order.cancel", key, body, run)


# ---- TX-08 출하 확정 (+ TX-09 매출) ----
def confirm_shipment(context, values: dict[str, Any], key: str):
    def run(connection, scoped):
        order, lines = _lock_ship_order(connection, scoped, values["shipment_order_id"])
        if _exists(
            connection,
            scoped,
            f"SELECT 1 FROM erp.shipment WHERE {_S} AND shipment_no=:no",
            no=values["shipment_no"],
        ):
            raise invalid("shipment_no", "이미 사용 중인 출하번호입니다.")
        ids = {line.id for line in lines}
        packing: dict[int, str | None] = {}
        for n, given in enumerate(values.get("lines") or [], 1):
            if given["shipment_order_line_id"] not in ids:
                raise invalid("lines", f"{n}번째 라인: 이 출하지시의 명세가 아닙니다.")
            code = (given.get("packing_no") or "").strip() or None
            if code is not None and code in packing.values():
                raise invalid("lines", f"{n}번째 라인: 같은 패킹번호가 이미 있습니다.")
            packing[given["shipment_order_line_id"]] = code
        codes = [c for c in packing.values() if c]
        used = (
            connection.execute(
                text(
                    f"SELECT packing_no FROM erp.shipment_line WHERE {_S} "
                    "AND packing_no = ANY(:codes) ORDER BY packing_no"
                ),
                {**_s(scoped), "codes": codes},
            )
            .scalars()
            .all()
        )
        if used:
            raise _locked(
                "이미 출하한 패킹번호입니다.",
                "PACKING_ALREADY_SHIPPED",
                packingNos=used,
            )
        shipment_id = connection.execute(
            text(
                "INSERT INTO erp.shipment (workspace_id, generation_id, shipment_no, "
                "shipment_order_id, shipped_at, status) VALUES "
                "(:w, :g, :no, :so, clock_timestamp(), 'confirmed') RETURNING id"
            ),
            {
                **_s(scoped),
                "no": values["shipment_no"],
                "so": values["shipment_order_id"],
            },
        ).scalar_one()
        for line in lines:
            connection.execute(
                text(
                    "INSERT INTO erp.shipment_line (workspace_id, generation_id, "
                    "shipment_id, shipment_order_line_id, packing_no, shipped_qty, "
                    "shipment_order_id, item_id, shipped_uom) VALUES "
                    "(:w, :g, :sh, :sol, :packing, :qty, :so, :item, :unit)"
                ),
                {
                    **_s(scoped),
                    "sh": shipment_id,
                    "sol": line.id,
                    "packing": packing.get(line.id),
                    "qty": line.order_qty,
                    "so": values["shipment_order_id"],
                    "item": line.item_id,
                    "unit": line.unit,
                },
            )
        connection.execute(
            text(
                f"UPDATE erp.shipment_order SET status='shipped' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": values["shipment_order_id"]},
        )
        revenue.recognize(connection, scoped, shipment_id, order.partner_id)
        refresh_order_status(connection, scoped, order.id)
        result = _shipments(connection, scoped, " AND sh.id=:id", id=shipment_id)[0]
        return result, "shipment", shipment_id

    return _action(context, "erp.shipment.confirm", key, values, run, 201)
