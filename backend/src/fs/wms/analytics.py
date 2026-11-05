"""W2b-1h 재고 수불부(W-18)·재고 분석(W-19)·위치 점유(W-20) (DSN-13 F52·F54·F55·F37).

표를 새로 만들지 않는다. 셋 다 원장(wms.stock_move)과 마스터를 집계해 조회할 때 계산한다.
- 수불부: 기간 기초 = 시작일 앞의 합계, 입고·출고 = 기간 안의 양수·음수, 기말 = 기초+입고+출고.
- 분석: 안전재고 부족·최대재고 초과(F37), 마지막 출고 후 경과일로 장기 체화(F54).
- 점유: 위치 용량 대비 현재고. 용량이 없으면(NULL) 점유율을 내지 않는다.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fs.common.clock import business_today
from fs.common.scope import read_scope
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query

STALE_DAYS = 90  # 마지막 출고 후 이 날짜를 넘기면 장기 체화로 본다(F54).


def _num(value: Any) -> str:
    return f"{Decimal(str(value or 0)):.3f}"


def ledger(
    context: base.AuthContext,
    month: str | None = None,
    warehouse_id: int | None = None,
    item_id: int | None = None,
) -> dict[str, Any]:
    """W-18 재고 수불부 — 기간 기초·입고·출고·기말 (F52)."""
    today = business_today()
    month = month or f"{today:%Y-%m}"
    start = date.fromisoformat(month + "-01")
    end = (start.replace(day=28) + timedelta(days=4)).replace(day=1)

    where, params = "", {"start": start, "end": end}
    if warehouse_id:
        where += " AND loc.warehouse_id=:warehouse_id"
        params["warehouse_id"] = warehouse_id
    if item_id:
        where += " AND m.item_id=:item_id"
        params["item_id"] = item_id

    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        rows = q(
            c,
            scoped,
            f"""
            SELECT m.item_id, i.item_code, i.name AS item_name, i.base_unit,
                   loc.warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
                   SUM(CASE WHEN d.document_on < :start THEN m.qty_delta ELSE 0 END) AS opening,
                   SUM(CASE WHEN d.document_on >= :start AND d.document_on < :end
                             AND m.qty_delta > 0 THEN m.qty_delta ELSE 0 END) AS inbound,
                   SUM(CASE WHEN d.document_on >= :start AND d.document_on < :end
                             AND m.qty_delta < 0 THEN m.qty_delta ELSE 0 END) AS outbound,
                   SUM(CASE WHEN d.document_on < :end THEN m.qty_delta ELSE 0 END) AS closing
            FROM wms.stock_move m
            JOIN wms.stock_document d
              ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
            JOIN wms.storage_location loc
              ON loc.workspace_id=m.workspace_id AND loc.generation_id=m.generation_id AND loc.id=m.location_id
            JOIN wms.warehouse w
              ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
            JOIN wms.item i
              ON i.workspace_id=m.workspace_id AND i.generation_id=m.generation_id AND i.id=m.item_id
            WHERE m.{S.replace(" AND ", " AND m.")}
              AND d.status='posted' {where}
            GROUP BY m.item_id, i.item_code, i.name, i.base_unit,
                     loc.warehouse_id, w.code, w.name
            HAVING SUM(CASE WHEN d.document_on < :end THEN m.qty_delta ELSE 0 END) <> 0
                OR SUM(CASE WHEN d.document_on >= :start AND d.document_on < :end
                             THEN abs(m.qty_delta) ELSE 0 END) <> 0
            ORDER BY w.code, i.item_code
            """,
            **params,
        ).mappings()
        return {
            "month": month,
            "rows": [
                {
                    "id": f"{r['warehouse_id']}-{r['item_id']}",
                    "itemId": r["item_id"],
                    "itemCode": r["item_code"],
                    "itemName": r["item_name"],
                    "baseUnit": r["base_unit"],
                    "warehouseId": r["warehouse_id"],
                    "warehouseCode": r["warehouse_code"],
                    "warehouseName": r["warehouse_name"],
                    "opening": _num(r["opening"]),
                    "inbound": _num(r["inbound"]),
                    # 출고는 음수로 쌓이니 보기 좋게 양수로 돌려준다.
                    "outbound": _num(-Decimal(str(r["outbound"] or 0))),
                    "closing": _num(r["closing"]),
                }
                for r in rows
            ],
        }


def analysis(
    context: base.AuthContext, warehouse_id: int | None = None
) -> dict[str, Any]:
    """W-19 재고 분석 — 안전재고·최대재고 경고(F37)와 회전율·장기 체화(F54)."""
    today = business_today()
    since = today - timedelta(days=STALE_DAYS)
    where, params = "", {"since": since}
    if warehouse_id:
        where += " AND loc.warehouse_id=:warehouse_id"
        params["warehouse_id"] = warehouse_id

    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        rows = q(
            c,
            scoped,
            f"""
            SELECT i.id AS item_id, i.item_code, i.name AS item_name, i.base_unit,
                   i.safety_stock, i.max_stock, i.abc_class,
                   SUM(m.qty_delta) AS on_hand,
                   SUM(CASE WHEN m.qty_delta < 0 AND d.document_on >= :since
                            THEN -m.qty_delta ELSE 0 END) AS out_recent,
                   MAX(CASE WHEN m.qty_delta < 0 THEN d.document_on END) AS last_out_on
            FROM wms.stock_move m
            JOIN wms.stock_document d
              ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
            JOIN wms.storage_location loc
              ON loc.workspace_id=m.workspace_id AND loc.generation_id=m.generation_id AND loc.id=m.location_id
            JOIN wms.item i
              ON i.workspace_id=m.workspace_id AND i.generation_id=m.generation_id AND i.id=m.item_id
            WHERE m.{S.replace(" AND ", " AND m.")}
              AND d.status='posted' {where}
            GROUP BY i.id, i.item_code, i.name, i.base_unit, i.safety_stock, i.max_stock, i.abc_class
            HAVING SUM(m.qty_delta) <> 0
            ORDER BY i.item_code
            """,
            **params,
        ).mappings()
        out = []
        for r in rows:
            on_hand = Decimal(str(r["on_hand"] or 0))
            out_recent = Decimal(str(r["out_recent"] or 0))
            safety = r["safety_stock"]
            maximum = r["max_stock"]
            last_out = r["last_out_on"]
            out.append(
                {
                    "id": r["item_id"],
                    "itemId": r["item_id"],
                    "itemCode": r["item_code"],
                    "itemName": r["item_name"],
                    "baseUnit": r["base_unit"],
                    "abcClass": r["abc_class"],
                    "onHand": _num(on_hand),
                    "safetyStock": None if safety is None else _num(safety),
                    "maxStock": None if maximum is None else _num(maximum),
                    "belowSafety": safety is not None
                    and on_hand < Decimal(str(safety)),
                    "aboveMax": maximum is not None and on_hand > Decimal(str(maximum)),
                    "outRecent": _num(out_recent),
                    # 회전율 = 최근 90일 출고 ÷ 현재고. 재고가 없으면 계산하지 않는다.
                    "turnover": (
                        None
                        if on_hand <= 0
                        else f"{(out_recent / on_hand).quantize(Decimal('0.01'))}"
                    ),
                    "lastOutOn": None if last_out is None else str(last_out),
                    "staleDays": None if last_out is None else (today - last_out).days,
                    "stale": last_out is None or (today - last_out).days >= STALE_DAYS,
                }
            )
        return {"staleDays": STALE_DAYS, "rows": out}


def occupancy(
    context: base.AuthContext, warehouse_id: int | None = None
) -> dict[str, Any]:
    """W-20 위치 점유 — 용량 대비 현재고 (F55). 용량이 없는 칸은 점유율을 내지 않는다."""
    where, params = "", {}
    if warehouse_id:
        where += " AND loc.warehouse_id=:warehouse_id"
        params["warehouse_id"] = warehouse_id

    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        rows = q(
            c,
            scoped,
            f"""
            SELECT loc.id, loc.code, loc.name, loc.location_type, loc.capacity_qty,
                   loc.mix_items, loc.mix_lots, loc.is_active,
                   w.code AS warehouse_code, w.name AS warehouse_name,
                   COALESCE(s.on_hand, 0) AS on_hand,
                   COALESCE(s.item_count, 0) AS item_count,
                   COALESCE(s.lot_count, 0) AS lot_count
            FROM wms.storage_location loc
            JOIN wms.warehouse w
              ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
            LEFT JOIN (
                SELECT m.location_id,
                       SUM(m.qty_delta) AS on_hand,
                       count(DISTINCT m.item_id) FILTER (WHERE m.qty_delta <> 0) AS item_count,
                       count(DISTINCT m.lot_no) FILTER (WHERE m.lot_no IS NOT NULL) AS lot_count
                FROM wms.stock_move m
                JOIN wms.stock_document d
                  ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
                WHERE m.workspace_id=:w AND m.generation_id=:g AND d.status='posted'
                GROUP BY m.location_id
            ) s ON s.location_id = loc.id
            WHERE loc.{S.replace(" AND ", " AND loc.")} {where}
            ORDER BY w.code, loc.code
            """,
            **params,
        ).mappings()
        out = []
        for r in rows:
            on_hand = Decimal(str(r["on_hand"] or 0))
            capacity = r["capacity_qty"]
            ratio = None
            if capacity is not None and Decimal(str(capacity)) > 0:
                ratio = f"{(on_hand / Decimal(str(capacity)) * 100).quantize(Decimal('0.1'))}"
            out.append(
                {
                    "id": r["id"],
                    "locationId": r["id"],
                    "locationCode": r["code"],
                    "locationName": r["name"],
                    "locationType": r["location_type"],
                    "warehouseCode": r["warehouse_code"],
                    "warehouseName": r["warehouse_name"],
                    "isActive": r["is_active"],
                    "capacityQty": None if capacity is None else _num(capacity),
                    "onHand": _num(on_hand),
                    "usagePercent": ratio,
                    "over": ratio is not None and Decimal(ratio) > 100,
                    "itemCount": r["item_count"],
                    "lotCount": r["lot_count"],
                    "mixItems": r["mix_items"],
                    "mixLots": r["mix_lots"],
                }
            )
        return {"rows": out}
