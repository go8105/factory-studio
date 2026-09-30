"""FS-026b2 TX-W8~W9. Reservations and all ledger writes share workspace locking."""

from collections import defaultdict
from decimal import Decimal, localcontext

from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.erp import interface as erp
from fs.wms import inventory
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query


def _header(c, scoped, id, lock=False):
    row = (
        q(
            c,
            scoped,
            f"SELECT * FROM wms.stock_reservation WHERE {S} AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            id=id,
        )
        .mappings()
        .first()
    )
    if row is None:
        raise base._not_found("예약")
    return dict(row)


def _lines(c, scoped, id):
    return [
        dict(row)
        for row in q(
            c,
            scoped,
            f"SELECT * FROM wms.stock_reservation_line WHERE {S} AND reservation_id=:id ORDER BY line_no",
            id=id,
        ).mappings()
    ]


def _key(line):
    return (line["item_id"], line["location_id"], line["lot_no"])


def _balances(c, scoped):
    return {
        (r["itemId"], r["locationId"], r["lotNo"]): r for r in inventory.rows(c, scoped)
    }


def _detail(c, scoped, id):
    row = _header(c, scoped, id)
    balances = _balances(c, scoped)
    lines = []
    for line in _lines(c, scoped, id):
        balance = balances.get(_key(line), {})
        lines.append(
            {
                **base._row(line),
                **{
                    key: balance.get(key, "0")
                    for key in (
                        "onHand",
                        "normalOnHand",
                        "reservedQty",
                        "available",
                        "reservationShortage",
                    )
                },
            }
        )
    result = {**base._row(row), "lines": lines}
    orders = erp.shipment_orders(c, scoped)
    ref = row["shipment_order_ref"]
    result["shipmentOrderState"] = (
        "unlinked"
        if not ref
        else "unavailable"
        if orders is None
        else next(
            (o["status"] for o in orders if o["shipmentOrderNo"] == ref), "missing"
        )
    )
    result["shipmentOrderComparison"] = _compare_order(c, scoped, row, lines, orders)
    return result


def _compare_order(c, scoped, row, lines, orders):
    ref = row["shipment_order_ref"]
    if not ref:
        return {"state": "unlinked", "lines": []}
    if orders is None:
        return {"state": "unavailable", "lines": []}
    order = next((o for o in orders if o["shipmentOrderNo"] == ref), None)
    if order is None:
        return {"state": "missing", "lines": []}
    items = base._items_by_code(c, scoped)
    by_id = {x["id"]: x for x in items.values()}
    reserved = defaultdict(Decimal)
    ordered = defaultdict(Decimal)
    for line in lines:
        reserved[by_id[line["itemId"]]["item_code"]] += Decimal(line["quantity"])
    for line in order["lines"]:
        item = items.get(line["itemCode"])
        if item is None:
            return {"state": "conversion_missing", "lines": []}
        factor = (
            Decimal(1)
            if line["unit"] == item["base_unit"]
            else item["factors"].get(line["unit"])
        )
        if factor is None:
            return {"state": "conversion_missing", "lines": []}
        try:
            with localcontext() as precision:
                precision.prec = 50
                qty = rec._quantity(
                    Decimal(line["qty"]) * factor, "shipmentOrderRef", True
                )
        except ApiError:
            return {"state": "conversion_invalid", "lines": []}
        ordered[line["itemCode"]] += qty
    comparison = [
        {
            "itemCode": code,
            "unit": items[code]["base_unit"],
            "reservedQty": str(reserved.get(code, Decimal(0))),
            "orderQty": str(ordered.get(code, Decimal(0))),
        }
        for code in sorted(reserved.keys() | ordered.keys())
    ]
    return {
        "state": "match" if dict(reserved) == dict(ordered) else "mismatch",
        "lines": comparison,
    }


def get_reservation(context, id):
    with base._read() as c:
        return _detail(c, read_scope(c, context, base.MODULE), id)


def list_reservations(context, status=None, item_code=None, page=1, page_size=50):
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        where = "r.workspace_id=:w AND r.generation_id=:g"
        params = {}
        if status:
            where += " AND r.status=:status"
            params["status"] = status
        if item_code:
            where += " AND EXISTS (SELECT 1 FROM wms.stock_reservation_line l JOIN wms.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id AND i.id=l.item_id WHERE l.workspace_id=r.workspace_id AND l.generation_id=r.generation_id AND l.reservation_id=r.id AND i.item_code=:item)"
            params["item"] = item_code
        total = q(
            c,
            scoped,
            "SELECT count(*) FROM wms.stock_reservation r WHERE " + where,
            **params,
        ).scalar_one()
        values = [
            base._row(row)
            for row in q(
                c,
                scoped,
                "SELECT r.* FROM wms.stock_reservation r WHERE "
                + where
                + " ORDER BY r.id DESC LIMIT :limit OFFSET :offset",
                **params,
                limit=page_size,
                offset=(page - 1) * page_size,
            ).mappings()
        ]
        return {"rows": values, "total": total, "page": page, "pageSize": page_size}


def create_reservation(context, values, key):
    def fn(c, scoped):
        business = values["business_key"].strip()
        if not business:
            rec._fail("businessKey", "업무 번호를 입력해 주세요.")
        old = q(
            c,
            scoped,
            f"SELECT id FROM wms.stock_reservation WHERE {S} AND business_key=:key",
            key=business,
        ).scalar_one_or_none()
        if old:
            raise base._conflict(
                "이미 등록한 예약 업무 번호입니다.",
                "BUSINESS_KEY_EXISTS",
                reservationId=old,
            )
        ref = values.get("shipment_order_ref")
        if ref is not None and not ref.strip():
            rec._fail("shipmentOrderRef", "출하지시 번호를 입력해 주세요.")
        ref = ref.strip() if ref else None
        # Reference is optional; ERP-off must not prevent manual reservations.
        balances = _balances(c, scoped)
        seen = set()
        lines = []
        for i, line in enumerate(values["lines"]):
            path = f"lines.{i}"
            item = base._item(c, scoped, line["item_id"])
            loc = base._location(c, scoped, line["location_id"])
            if item is None or loc is None:
                raise base._not_found("품목 또는 위치")
            wh = base._warehouse(c, scoped, loc["warehouseId"])
            if (
                not item["isActive"]
                or not loc["isActive"]
                or not wh["isActive"]
                or item["itemClass"] != wh["purpose"]
            ):
                rec._fail(
                    path + ".locationId",
                    "품목 용도와 일치하는 사용 중인 창고·위치를 선택해 주세요.",
                )
            if loc["locationType"] != "NORMAL":
                raise base._conflict(
                    "격리 재고는 예약할 수 없습니다.",
                    "QUARANTINE_NOT_RESERVABLE",
                    lineIndex=i,
                )
            lot = (line.get("lot_no") or "").strip() or None
            if bool(lot) != (item["itemClass"] == "FG"):
                rec._fail(
                    path + ".lotNo", "완제품 LOT 필수, 원자재 LOT은 지정하지 않습니다."
                )
            qty = rec._quantity(line["quantity"], path + ".quantity", True)
            normalized = {**line, "lot_no": lot, "quantity": qty}
            k = _key(normalized)
            if k in seen:
                rec._fail(path + ".locationId", "품목·위치·LOT이 중복되었습니다.")
            seen.add(k)
            available = Decimal(balances.get(k, {}).get("available", "0"))
            if qty > available:
                raise base._conflict(
                    "예약 가능한 수량이 부족합니다.",
                    "INSUFFICIENT_AVAILABLE",
                    lineIndex=i,
                    available=str(available),
                    requested=str(qty),
                )
            lines.append(normalized)
        now = rec._now(c)
        stem = f"RSV-{now.astimezone(base.SEOUL):%Y%m%d}-"
        seq = (
            q(
                c,
                scoped,
                f"SELECT count(*) FROM wms.stock_reservation WHERE {S} AND reservation_no LIKE :stem",
                stem=stem + "%",
            ).scalar_one()
            + 1
        )
        id = q(
            c,
            scoped,
            "INSERT INTO wms.stock_reservation(workspace_id,generation_id,reservation_no,business_key,shipment_order_ref,reason,created_at) VALUES (:w,:g,:no,:business,:ref,:reason,:now) RETURNING id",
            no=f"{stem}{seq:03}",
            business=business,
            ref=ref,
            reason=rec._reason(values.get("reason")),
            now=now,
        ).scalar_one()
        for i, line in enumerate(lines, 1):
            q(
                c,
                scoped,
                "INSERT INTO wms.stock_reservation_line(workspace_id,generation_id,reservation_id,line_no,item_id,location_id,lot_no,quantity,created_at) VALUES (:w,:g,:id,:n,:item_id,:location_id,:lot_no,:quantity,:now)",
                id=id,
                n=i,
                now=now,
                **line,
            )
        return _detail(c, scoped, id), "stock_reservation", id

    return base._action(context, "wms.reservation.create", key, values, fn, 201)


def release(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        reason = rec._reason(values["reason"], required=True)
        if row["status"] == "RELEASED":
            if reason != row["reason"]:
                raise base._conflict(
                    "이미 해제한 예약의 사유와 다릅니다.", "INVALID_STATE"
                )
            return _detail(c, scoped, id), "stock_reservation", id
        rec._state(row, {"ACTIVE"})
        rec._version(row, values)
        q(
            c,
            scoped,
            f"UPDATE wms.stock_reservation SET status='RELEASED',closed_at=:now,reason=:reason,version=version+1 WHERE {S} AND id=:id",
            id=id,
            now=rec._now(c),
            reason=reason,
        )
        return _detail(c, scoped, id), "stock_reservation", id

    return base._action(context, f"wms.reservation.release:{id}", key, values, fn)


def _match_shipment(c, scoped, row, lines, source):
    if (
        row["shipment_order_ref"]
        and row["shipment_order_ref"] != source["shipmentOrderNo"]
    ):
        raise base._conflict(
            "참고 출하지시와 실제 출하의 지시가 다릅니다.", "SHIPMENT_MISMATCH"
        )
    items = base._items_by_code(c, scoped)
    by_id = {item["id"]: item for item in items.values()}
    reserved = defaultdict(Decimal)
    reserved_lots = defaultdict(Decimal)
    for line in lines:
        item = by_id[line["item_id"]]
        if item["item_class"] != "FG":
            raise base._conflict(
                "원자재 예약은 고객 출하 소진을 지원하지 않습니다.", "SHIPMENT_MISMATCH"
            )
        reserved[item["item_code"]] += line["quantity"]
        reserved_lots[(item["item_code"], line["lot_no"])] += line["quantity"]
    packed = [bool(line.get("packingNo")) for line in source["lines"]]
    if any(packed) and not all(packed):
        raise base._conflict(
            "팔레트 지정/미지정이 섞인 출하는 연결할 수 없습니다.", "SHIPMENT_MISMATCH"
        )
    shipped = defaultdict(Decimal)
    lots = defaultdict(Decimal)
    seen_packing = set()
    for line in source["lines"]:
        packing_key = (line["itemCode"], line.get("packingNo"))
        if line.get("packingNo") and packing_key in seen_packing:
            raise base._conflict(
                "동일 팔레트가 중복된 출하는 연결할 수 없습니다.", "SHIPMENT_MISMATCH"
            )
        seen_packing.add(packing_key)
        item = items.get(line["itemCode"])
        if not item or item["item_class"] != "FG":
            raise base._conflict(
                "출하 품목을 예약과 대조할 수 없습니다.", "SHIPMENT_MISMATCH"
            )
        factor = (
            Decimal(1)
            if line["unit"] == item["base_unit"]
            else item["factors"].get(line["unit"])
        )
        if factor is None:
            rec._fail("sourceKey", "출하 단위 환산이 없습니다.")
        with localcontext() as precision:
            precision.prec = 50
            qty = rec._quantity(Decimal(line["qty"]) * factor, "sourceKey", True)
        shipped[line["itemCode"]] += qty
        if line.get("packingNo"):
            allocation = base._receipt_lots(c, scoped, line["packingNo"], item["id"])
            if (
                not allocation
                or any(x["lot_no"] is None for x in allocation)
                or sum(x["qty"] for x in allocation) != qty
            ):
                raise base._conflict(
                    "팔레트의 입고 LOT·수량을 대조할 수 없습니다.", "SHIPMENT_MISMATCH"
                )
            for x in allocation:
                lots[(line["itemCode"], x["lot_no"])] += x["qty"]
    if dict(reserved) != dict(shipped) or (
        all(packed) and dict(reserved_lots) != dict(lots)
    ):
        raise base._conflict(
            "예약과 출하의 품목·수량·LOT이 다릅니다.", "SHIPMENT_MISMATCH"
        )
    return by_id


def consume(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        if row["status"] == "CONSUMED":
            if row["shipment_source_key"] != values["source_key"]:
                raise base._conflict(
                    "다른 출하로 이미 소진한 예약입니다.", "INVALID_STATE"
                )
            return (
                _consumed(c, scoped, id, row["stock_document_id"]),
                "stock_reservation",
                id,
            )
        rec._state(row, {"ACTIVE"})
        rec._version(row, values)
        if base._document_by_source(c, scoped, values["source_key"]):
            raise base._conflict(
                "이미 반영된 출하입니다. 예약은 유지됩니다.", "SOURCE_ALREADY_POSTED"
            )
        sources = erp.confirmed_shipments(c, scoped)
        if sources is None:
            raise base._source_off("erp")
        source = next(
            (
                s
                for s in sources
                if "ERP:SHIPMENT:" + s["shipmentNo"] == values["source_key"]
            ),
            None,
        )
        if source is None:
            raise base._not_found("확정 출하")
        lines = _lines(c, scoped, id)
        items = _match_shipment(c, scoped, row, lines, source)
        now = rec._now(c)
        moves = [
            {
                "item_id": line["item_id"],
                "location_id": line["location_id"],
                "lot_no": line["lot_no"],
                "qty_delta": -line["quantity"],
                "source_qty": line["quantity"],
                "source_unit": items[line["item_id"]]["base_unit"],
            }
            for line in lines
        ]
        doc = base._insert_document(
            c,
            scoped,
            {
                "document_type": "ERP_SHIPMENT",
                "status": "posted",
                "source_key": values["source_key"],
                "source_ref": source["shipmentNo"],
                "document_on": now.astimezone(base.SEOUL).date(),
                "posted_at": now,
            },
            moves,
            now.isoformat(),
        )
        q(
            c,
            scoped,
            f"UPDATE wms.stock_reservation SET status='CONSUMED',closed_at=:now,shipment_source_key=:key,stock_document_id=:doc,version=version+1 WHERE {S} AND id=:id",
            id=id,
            now=now,
            key=values["source_key"],
            doc=doc,
        )
        return _consumed(c, scoped, id, doc), "stock_reservation", id

    return base._action(context, f"wms.reservation.consume:{id}", key, values, fn)


def _consumed(c, scoped, id, doc):
    return {
        **_detail(c, scoped, id),
        "negativeWarnings": base._negatives(c, scoped, doc),
    }


def sources(context):
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        orders = erp.shipment_orders(c, scoped)
        shipments = erp.confirmed_shipments(c, scoped)
        if orders is None:
            return {"enabled": False, "orders": [], "shipments": []}
        return {
            "enabled": True,
            "orders": orders,
            "shipments": [
                {**s, "sourceKey": "ERP:SHIPMENT:" + s["shipmentNo"]}
                for s in shipments
                if not base._document_by_source(
                    c, scoped, "ERP:SHIPMENT:" + s["shipmentNo"]
                )
            ],
        }


def guard_master(c, scoped, kind, id, all_history=False):
    condition = {
        "warehouse": "loc.warehouse_id=:id",
        "item": "l.item_id=:id",
        "location": "l.location_id=:id",
    }[kind]
    state = "" if all_history else " AND r.status='ACTIVE'"
    count = q(
        c,
        scoped,
        "SELECT count(DISTINCT r.id) FROM wms.stock_reservation r JOIN wms.stock_reservation_line l ON l.workspace_id=r.workspace_id AND l.generation_id=r.generation_id AND l.reservation_id=r.id JOIN wms.storage_location loc ON loc.workspace_id=l.workspace_id AND loc.generation_id=l.generation_id AND loc.id=l.location_id WHERE r.workspace_id=:w AND r.generation_id=:g AND "
        + condition
        + state,
        id=id,
    ).scalar_one()
    if count:
        raise base._referenced(
            "예약이 참조하고 있습니다. 먼저 예약을 해제하거나 소진해 주세요.",
            "예약",
            count,
        )
