"""FS-026b2 live ledger + active reservation view. No stored stock balances."""

from decimal import Decimal

from sqlalchemy import text

from fs.erp import interface as erp
from fs.wms import service as base

SQL = """
WITH amounts AS (
 SELECT m.item_id,m.location_id,m.lot_no,sum(m.qty_delta) on_hand,0::numeric reserved_qty
 FROM wms.stock_move m JOIN wms.stock_document d
 ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
 WHERE m.workspace_id=:w AND m.generation_id=:g AND d.status='posted'
 GROUP BY m.item_id,m.location_id,m.lot_no
 UNION ALL
 SELECT l.item_id,l.location_id,l.lot_no,0::numeric,sum(l.quantity)
 FROM wms.stock_reservation_line l JOIN wms.stock_reservation r
 ON r.workspace_id=l.workspace_id AND r.generation_id=l.generation_id AND r.id=l.reservation_id
 WHERE l.workspace_id=:w AND l.generation_id=:g AND r.status='ACTIVE'
 GROUP BY l.item_id,l.location_id,l.lot_no
), balances AS (
 SELECT item_id,location_id,lot_no,sum(on_hand) on_hand,sum(reserved_qty) reserved_qty
 FROM amounts GROUP BY item_id,location_id,lot_no
)
SELECT b.*,i.item_code,i.name item_name,i.item_class,i.base_unit unit,
 l.code location_code,l.location_type,h.id warehouse_id,h.code warehouse_code
 FROM balances b
 JOIN wms.item i ON i.workspace_id=:w AND i.generation_id=:g AND i.id=b.item_id
 JOIN wms.storage_location l ON l.workspace_id=:w AND l.generation_id=:g AND l.id=b.location_id
 JOIN wms.warehouse h ON h.workspace_id=:w AND h.generation_id=:g AND h.id=l.warehouse_id
 WHERE (b.on_hand<>0 OR b.reserved_qty<>0)
"""


def rows(c, scoped, filters=None):
    filters = filters or {}
    where = ""
    params = {}
    for key, expr in [
        ("itemCode", "i.item_code"),
        ("warehouseId", "h.id"),
        ("locationId", "l.id"),
        ("locationType", "l.location_type"),
        ("lotNo", "b.lot_no"),
    ]:
        if filters.get(key) is not None:
            where += f" AND {expr}=:{key}"
            params[key] = filters[key]
    if filters.get("negativeOnly"):
        where += " AND b.on_hand<0"
    if filters.get("unassignedOnly"):
        where += " AND i.item_class='FG' AND b.lot_no IS NULL"
    result = []
    for row in c.execute(
        text(SQL + where + " ORDER BY h.code,l.code,i.item_code,b.lot_no NULLS FIRST"),
        {**base._s(scoped), **params},
    ).mappings():
        normal = (
            row["on_hand"]
            if row["location_type"] in ("NORMAL", "SHIPPING")
            else Decimal(0)
        )
        held = row["on_hand"] - normal
        available = normal - row["reserved_qty"]
        result.append(
            {
                **base._row(row),
                "normalOnHand": str(normal),
                "quarantinedOnHand": str(held),
                "available": str(available),
                "reservationShortage": str(max(Decimal(0), -available)),
                "negative": row["on_hand"] < 0,
                "lotUnassigned": row["item_class"] == "FG" and row["lot_no"] is None,
            }
        )
    return result


QUANTITIES = (
    "onHand",
    "normalOnHand",
    "quarantinedOnHand",
    "reservedQty",
    "available",
    "reservationShortage",
)


def totals(c, scoped, values):
    grouped = {}
    demand = erp.open_shipment_qty(c, scoped)
    for row in values:
        item = grouped.setdefault(
            row["itemCode"],
            {
                **{
                    key: row[key]
                    for key in ("itemCode", "itemName", "itemClass", "unit")
                },
                **dict.fromkeys(QUANTITIES, Decimal(0)),
                "negative": False,
            },
        )
        for key in QUANTITIES:
            item[key] += Decimal(row[key])
        # A shortage at one location must survive offsetting stock elsewhere.
        item["negative"] = item["negative"] or row["negative"]
    return [
        {
            **item,
            **{key: str(item[key]) for key in QUANTITIES},
            "openShipmentQty": None
            if demand is None or item["itemClass"] != "FG"
            else demand.get(code, "0"),
        }
        for code, item in sorted(grouped.items())
    ]
