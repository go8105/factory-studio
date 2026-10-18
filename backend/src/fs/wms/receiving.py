"""FS-026b1 TX-W4..W7. Same workspace lock and ledger as FS-024.

Action timestamps and inspection document dates use one DB clock sample, never
FS_TODAY. ERP snapshots retain display timestamps; their digest excludes time.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, localcontext

from sqlalchemy import text

from fs.common.idempotency import request_digest
from fs.common.scope import read_scope
from fs.erp import interface as erp
from fs.wms import service as base

S = base._S
MAX_QTY = Decimal("999999999999999.999")


def _query(c, scoped, sql, **params):
    return c.execute(text(sql), {**base._s(scoped), **params})


def _now(c):
    return c.execute(text("SELECT clock_timestamp()")).scalar_one()


def _fail(path, message):
    raise base._fields({path: message})


def _reason(value, path="reason", required=False):
    result = value.strip() if value else None
    if required and not result:
        _fail(path, "사유를 입력해 주세요.")
    return result or None


def _quantity(value, path, positive=False):
    n = Decimal(str(value))
    if (
        not n.is_finite()
        or n < 0
        or n > MAX_QTY
        or (positive and not n)
        or n != n.quantize(base.Q3)
    ):
        _fail(path, "기본 단위의 유효 수량(소수 3자리 이내)을 입력해 주세요.")
    return n.quantize(base.Q3)


def _canonical(n):
    return format(Decimal(n).normalize(), "f")


def _next_no(c, scoped, now):
    stem = f"IN-{now.astimezone(base.SEOUL):%Y%m%d}-"
    used = _query(
        c,
        scoped,
        f"SELECT count(*) FROM wms.inbound_notice WHERE {S} AND notice_no LIKE :stem",
        stem=stem + "%",
    ).scalar_one()
    return f"{stem}{used + 1:03d}"


def _header(c, scoped, id, lock=False):
    found = (
        _query(
            c,
            scoped,
            f"SELECT * FROM wms.inbound_notice WHERE {S} AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            id=id,
        )
        .mappings()
        .first()
    )
    if found is None:
        raise base._not_found("입고 예정")
    return dict(found)


def _lines(c, scoped, id):
    return [
        dict(x)
        for x in _query(
            c,
            scoped,
            f"SELECT * FROM wms.inbound_notice_line WHERE {S} AND notice_id=:id ORDER BY line_no",
            id=id,
        ).mappings()
    ]


def claim(c, scoped, source_key=None, notice_id=None):
    where = "source_key=:key" if source_key is not None else "notice_id=:id"
    row = (
        _query(
            c,
            scoped,
            f"SELECT * FROM wms.source_claim WHERE {S} AND status<>'RELEASED' AND {where}",
            key=source_key,
            id=notice_id,
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def route(c, scoped, source):
    """Used by BOTH listing and sync, inside their existing transaction/scope."""
    found = claim(c, scoped, source_key=source["sourceKey"])
    if not found:
        return None
    if base._document_by_source(c, scoped, source["sourceKey"]):
        raise base._conflict("원천 경로가 충돌합니다.", "SOURCE_ROUTE_CONFLICT")
    notice = _header(c, scoped, found["notice_id"])
    state = (
        "inspection_pending"
        if found["status"] == "CLAIMED"
        else "inspected_cancelled"
        if source.get("cancelledAt")
        else "inspected"
    )
    number = None
    if notice["stock_document_id"]:
        number = _query(
            c,
            scoped,
            f"SELECT document_no FROM wms.stock_document WHERE {S} AND id=:id",
            id=notice["stock_document_id"],
        ).scalar_one()
    return {
        "sourceKey": source["sourceKey"],
        "state": state,
        "noticeId": notice["id"],
        "documentId": notice["stock_document_id"],
        "documentNo": number,
        "inspectionState": notice["status"],
        "sourceCancelled": bool(source.get("cancelledAt")),
        "reason": {"code": "SOURCE_CLAIMED"} if state == "inspection_pending" else None,
    }


def _detail(c, scoped, id):
    row = _header(c, scoped, id)
    result = base._row(row)
    result["lines"] = [base._row(x) for x in _lines(c, scoped, id)]
    linked = claim(c, scoped, notice_id=id)
    result["sourceClaim"] = base._row(linked) if linked else None
    if linked:
        sources = erp.purchase_receipts(c, scoped)
        if sources is None:
            result["sourceState"] = "unavailable"
        else:
            source = next(
                (
                    x
                    for x in sources
                    if "ERP:PURCHASE:" + x["invoiceNo"] == linked["source_key"]
                ),
                None,
            )
            result["sourceState"] = (
                "missing"
                if not source
                else "cancelled"
                if source["cancelledAt"]
                else "confirmed"
            )
    else:
        result["sourceState"] = "manual"
    return result


def get_notice(context, id):
    with base._read() as c:
        return _detail(c, read_scope(c, context, base.MODULE), id)


NOTICE_KINDS = {"PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT"}


def list_notices(
    context,
    status=None,
    warehouse_id=None,
    notice_kind=None,
    page=1,
    page_size=50,
    expected_from=None,
    expected_to=None,
):
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        where = S
        params = {}
        if status:
            where += " AND status=:status"
            params["status"] = status
        if warehouse_id:
            where += " AND warehouse_id=:warehouse"
            params["warehouse"] = warehouse_id
        if notice_kind:
            where += " AND notice_kind=:notice_kind"
            params["notice_kind"] = notice_kind
        if expected_from and expected_to and expected_from > expected_to:
            _fail("expectedTo", "예정일 끝은 시작 이후여야 합니다.")
        for key, value, op in [
            ("expected_from", expected_from, ">="),
            ("expected_to", expected_to, "<="),
        ]:
            if value:
                where += f" AND expected_on {op} :{key}"
                params[key] = value
        total = _query(
            c,
            scoped,
            f"SELECT count(*) FROM wms.inbound_notice WHERE {where}",
            **params,
        ).scalar_one()
        rows = [
            base._row(x)
            for x in _query(
                c,
                scoped,
                f"SELECT * FROM wms.inbound_notice WHERE {where} ORDER BY id DESC LIMIT :limit OFFSET :offset",
                **params,
                limit=page_size,
                offset=(page - 1) * page_size,
            ).mappings()
        ]
        return {"rows": rows, "total": total, "page": page, "pageSize": page_size}


def _version(row, values):
    if row["version"] != values["expected_version"]:
        raise base._conflict(
            "다른 변경이 있습니다. 다시 조회해 주세요.",
            "STALE_VERSION",
            currentVersion=row["version"],
        )


def _state(row, allowed):
    if row["status"] not in allowed:
        raise base._conflict(
            "현재 상태에서 처리할 수 없습니다.", "INVALID_STATE", status=row["status"]
        )


def _validate_lines(c, scoped, warehouse_id, lines):
    wh = base._warehouse(c, scoped, warehouse_id)
    if wh is None:
        raise base._not_found("창고")
    if not wh["isActive"]:
        _fail("warehouseId", "사용 중인 창고를 선택해 주세요.")
    normalized = []
    seen = set()
    for i, line in enumerate(lines):
        path = f"lines.{i}"
        item = base._item(c, scoped, line["item_id"])
        if item is None:
            raise base._not_found("품목")
        if not item["isActive"] or item["itemClass"] != wh["purpose"]:
            _fail(
                path + ".itemId", "창고 용도와 일치하는 사용 중인 품목을 선택해 주세요."
            )
        lot = line.get("lot_no")
        lot = (lot.strip() or None) if lot else None
        if bool(lot) != bool(item.get("lotTracked")):
            _fail(
                path + ".lotNo",
                "LOT 추적 품목은 LOT 필수, 추적하지 않는 품목은 LOT을 입력하지 않습니다.",
            )
        key = (item["id"], lot)
        if key in seen:
            _fail(path + ".itemId", "동일 품목·LOT이 중복되었습니다.")
        seen.add(key)
        qty = _quantity(line["expected_qty"], path + ".expectedQty", True)
        for field, kind in [
            ("normal_location_id", "NORMAL"),
            ("quarantine_location_id", "QUARANTINE"),
        ]:
            id = line.get(field)
            if id is None and field == "quarantine_location_id":
                continue
            loc = base._location(c, scoped, id)
            if loc is None:
                raise base._not_found("위치")
            allowed = (
                ("NORMAL", "RECEIVING")
                if field == "normal_location_id"
                else ("QUARANTINE",)
            )
            if (
                loc["warehouseId"] != warehouse_id
                or not loc["isActive"]
                or loc["locationType"] not in allowed
            ):
                _fail(
                    path + "." + base._camel(field),
                    "같은 창고의 사용 중인 "
                    + ("NORMAL 또는 RECEIVING" if field == "normal_location_id" else kind)
                    + " 위치를 선택해 주세요.",
                )
        normalized.append({**line, "lot_no": lot, "expected_qty": qty})
    return normalized


def _insert_lines(c, scoped, id, lines):
    for i, line in enumerate(lines, 1):
        _query(
            c,
            scoped,
            "INSERT INTO wms.inbound_notice_line(workspace_id,generation_id,notice_id,line_no,item_id,lot_no,expected_qty,normal_location_id,quarantine_location_id) VALUES (:w,:g,:id,:line,:item_id,:lot_no,:expected_qty,:normal_location_id,:quarantine_location_id)",
            id=id,
            line=i,
            **line,
        )


def create_notice(context, values, key):
    def fn(c, scoped):
        business = values["business_key"].strip()
        if not business:
            _fail("businessKey", "업무 번호를 입력해 주세요.")
        old = _query(
            c,
            scoped,
            f"SELECT id FROM wms.inbound_notice WHERE {S} AND business_key=:key",
            key=business,
        ).scalar_one_or_none()
        if old is not None:
            raise base._conflict(
                "이미 등록된 업무 번호입니다.", "BUSINESS_KEY_EXISTS", noticeId=old
            )
        lines = _validate_lines(c, scoped, values["warehouse_id"], values["lines"])
        kind = values.get("notice_kind") or "PURCHASE"
        if kind not in NOTICE_KINDS:
            _fail("noticeKind", "유효한 입고 구분을 선택해 주세요.")
        now = _now(c)
        id = _query(
            c,
            scoped,
            "INSERT INTO wms.inbound_notice(workspace_id,generation_id,notice_no,business_key,warehouse_id,notice_kind,expected_on,vehicle_no,partner_ref,created_at,updated_at) VALUES (:w,:g,:no,:business,:warehouse,:kind,:on,:vehicle,:partner,:now,:now) RETURNING id",
            no=_next_no(c, scoped, now),
            business=business,
            warehouse=values["warehouse_id"],
            kind=kind,
            on=values["expected_on"],
            vehicle=values.get("vehicle_no"),
            partner=values.get("partner_ref"),
            now=now,
        ).scalar_one()
        _insert_lines(c, scoped, id, lines)
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, "wms.inbound.create", key, values, fn, 201)


def update_notice(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        _version(row, values)
        _state(row, {"PLANNED"})
        lines = _validate_lines(c, scoped, values["warehouse_id"], values["lines"])
        kind = values.get("notice_kind") or row["notice_kind"]
        if kind not in NOTICE_KINDS:
            _fail("noticeKind", "유효한 입고 구분을 선택해 주세요.")
        linked = claim(c, scoped, notice_id=id)
        if linked:
            _match_expected(c, scoped, lines, linked["source_snapshot"])
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET warehouse_id=:warehouse,notice_kind=:kind,expected_on=:on,vehicle_no=:vehicle,partner_ref=:partner,updated_at=clock_timestamp(),version=version+1 WHERE {S} AND id=:id",
            warehouse=values["warehouse_id"],
            kind=kind,
            on=values["expected_on"],
            vehicle=values.get("vehicle_no"),
            partner=values.get("partner_ref"),
            id=id,
        )
        _query(
            c,
            scoped,
            f"DELETE FROM wms.inbound_notice_line WHERE {S} AND notice_id=:id",
            id=id,
        )
        _insert_lines(c, scoped, id, lines)
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.update:{id}", key, values, fn)


def _source(c, scoped, key):
    rows = erp.purchase_receipts(c, scoped)
    if rows is None:
        raise base._source_off("erp")
    source = next((x for x in rows if "ERP:PURCHASE:" + x["invoiceNo"] == key), None)
    if source is None:
        raise base._not_found("확정 매입 원천")
    if source["cancelledAt"]:
        raise base._conflict("취소된 원천입니다.", "SOURCE_CANCELLED")
    return source


def source_snapshot(c, scoped, source):
    """Canonical invoice + quantity semantics. confirmedAt is display-only."""
    items = base._items_by_code(c, scoped)
    grouped = {}
    for line in source["lines"]:
        code = line["itemCode"]
        item = items.get(code)
        if not item:
            _fail("sourceKey", "WMS 미등록 품목: " + code)
        factor = (
            Decimal(1)
            if line["unit"] == item["base_unit"]
            else item["factors"].get(line["unit"])
        )
        if factor is None:
            _fail("sourceKey", "단위 환산 없음: " + code + " " + line["unit"])
        qty = _quantity(line["qty"], "sourceKey", True)
        with localcontext() as precision:
            precision.prec = 50
            baseqty = _quantity(qty * factor, "sourceKey", True)
        group = grouped.setdefault(
            code,
            {
                "itemCode": code,
                "baseUnit": item["base_unit"],
                "baseQty": Decimal(0),
                "sources": defaultdict(Decimal),
            },
        )
        group["baseQty"] += baseqty
        group["sources"][(line["unit"], _canonical(factor))] += qty
    lines = []
    for code, group in sorted(grouped.items()):
        _quantity(group["baseQty"], "sourceKey", True)
        lines.append(
            {
                "itemCode": code,
                "baseUnit": group["baseUnit"],
                "baseQty": _canonical(group["baseQty"]),
                "sources": [
                    {"unit": unit, "factor": factor, "qty": _canonical(qty)}
                    for (unit, factor), qty in sorted(group["sources"].items())
                ],
            }
        )
    semantic = {"invoiceNo": source["invoiceNo"], "lines": lines}
    return {**semantic, "confirmedAt": source["confirmedAt"]}, request_digest(semantic)


def _match_expected(c, scoped, lines, snapshot):
    expected = defaultdict(Decimal)
    for line in lines:
        item = base._item(c, scoped, line["item_id"])
        if item is None:
            raise base._not_found("품목")
        expected[(item["itemCode"], item["baseUnit"])] += Decimal(line["expected_qty"])
    source = {
        (x["itemCode"], x["baseUnit"]): Decimal(x["baseQty"]) for x in snapshot["lines"]
    }
    if dict(expected) != source:
        _fail("sourceKey", "품목별 기본 단위 예정 수량이 원천과 다릅니다.")


def link_source(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        _state(row, {"PLANNED", "ARRIVED", "INSPECTED"})
        existing = claim(c, scoped, notice_id=id)
        if existing:
            if existing["source_key"] == values["source_key"]:
                return _detail(c, scoped, id), "inbound_notice", id
            raise base._conflict("다른 원천과 연결되어 있습니다.", "SOURCE_CLAIMED")
        _version(row, values)
        if base._document_by_source(c, scoped, values["source_key"]):
            raise base._conflict(
                "이미 원장에 반영된 원천입니다.", "SOURCE_ALREADY_POSTED"
            )
        if claim(c, scoped, source_key=values["source_key"]):
            raise base._conflict("다른 예정에 연결된 원천입니다.", "SOURCE_CLAIMED")
        snapshot, digest = source_snapshot(
            c, scoped, _source(c, scoped, values["source_key"])
        )
        _match_expected(c, scoped, _lines(c, scoped, id), snapshot)
        now = _now(c)
        done = row["status"] == "INSPECTED"
        _query(
            c,
            scoped,
            "INSERT INTO wms.source_claim(workspace_id,generation_id,source_key,notice_id,status,source_snapshot,source_digest,created_at,closed_at) VALUES (:w,:g,:key,:id,:status,CAST(:snapshot AS jsonb),:digest,:now,:closed)",
            key=values["source_key"],
            id=id,
            status="COMPLETED" if done else "CLAIMED",
            snapshot=json.dumps(snapshot),
            digest=digest,
            now=now,
            closed=now if done else None,
        )
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET version=version+1,updated_at=:now WHERE {S} AND id=:id",
            now=now,
            id=id,
        )
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.link:{id}", key, values, fn)


def unlink_source(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        _state(row, {"PLANNED", "ARRIVED"})
        _version(row, values)
        reason = _reason(values["reason"], required=True)
        linked = claim(c, scoped, notice_id=id)
        if not linked:
            raise base._conflict("연결된 원천이 없습니다.", "INVALID_STATE")
        now = _now(c)
        _query(
            c,
            scoped,
            f"UPDATE wms.source_claim SET status='RELEASED',closed_at=:now,release_reason=:reason WHERE {S} AND id=:id",
            now=now,
            reason=reason,
            id=linked["id"],
        )
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET version=version+1,updated_at=:now WHERE {S} AND id=:id",
            now=now,
            id=id,
        )
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.unlink:{id}", key, values, fn)


def arrive(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        if row["status"] in {"ARRIVED", "INSPECTED"}:
            return _detail(c, scoped, id), "inbound_notice", id
        _state(row, {"PLANNED"})
        _version(row, values)
        now = _now(c)
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET status='ARRIVED',arrived_at=:now,updated_at=:now,version=version+1 WHERE {S} AND id=:id",
            now=now,
            id=id,
        )
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.arrive:{id}", key, values, fn)


def cancel(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        reason = _reason(values["reason"], required=True)
        if row["status"] == "CANCELLED" and row["reason"] == reason:
            return _detail(c, scoped, id), "inbound_notice", id
        _state(row, {"PLANNED", "ARRIVED"})
        _version(row, values)
        now = _now(c)
        _query(
            c,
            scoped,
            f"UPDATE wms.source_claim SET status='RELEASED',closed_at=:now,release_reason=:reason WHERE {S} AND notice_id=:id AND status='CLAIMED'",
            now=now,
            reason=reason,
            id=id,
        )
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET status='CANCELLED',cancelled_at=:now,reason=:reason,updated_at=:now,version=version+1 WHERE {S} AND id=:id",
            now=now,
            reason=reason,
            id=id,
        )
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.cancel:{id}", key, values, fn)


def inspect_notice(context, id, values, key):
    def fn(c, scoped):
        row = _header(c, scoped, id, True)
        lines = _lines(c, scoped, id)
        supplied = {x["line_id"]: x for x in values["lines"]}
        input_positions = {x["line_id"]: i for i, x in enumerate(values["lines"])}
        if len(supplied) != len(values["lines"]) or set(supplied) != {
            x["id"] for x in lines
        }:
            _fail("lines", "예정의 모든 줄을 중복 없이 입력해 주세요.")
        normalized = []
        for line in lines:
            i = input_positions[line["id"]]
            v = supplied[line["id"]]
            q = {
                name: _quantity(v[name], f"lines.{i}." + base._camel(name))
                for name in ("accepted_qty", "quarantined_qty", "shortage_qty")
            }
            if sum(q.values()) != line["expected_qty"]:
                _fail(
                    f"lines.{i}.shortageQty",
                    "합격+격리+부족은 예정 수량과 같아야 합니다.",
                )
            reason = _reason(
                v.get("reason"),
                f"lines.{i}.reason",
                q["quarantined_qty"] > 0 or q["shortage_qty"] > 0,
            )
            if q["quarantined_qty"] and line["quarantine_location_id"] is None:
                _fail(f"lines.{i}.quarantinedQty", "격리 위치가 지정되지 않았습니다.")
            normalized.append({**q, "reason": reason})
        if row["status"] == "INSPECTED":
            if all(
                all(line[name] == v for name, v in result.items())
                for line, result in zip(lines, normalized, strict=True)
            ):
                return _detail(c, scoped, id), "inbound_notice", id
            raise base._conflict("이미 확정된 검수 내용과 다릅니다.", "INVALID_STATE")
        _state(row, {"ARRIVED"})
        _version(row, values)
        _validate_lines(c, scoped, row["warehouse_id"], lines)
        linked = claim(c, scoped, notice_id=id)
        if linked:
            if base._document_by_source(c, scoped, linked["source_key"]):
                raise base._conflict("원천 경로 충돌", "SOURCE_ROUTE_CONFLICT")
            snapshot, digest = source_snapshot(
                c, scoped, _source(c, scoped, linked["source_key"])
            )
            if digest != linked["source_digest"]:
                raise base._conflict(
                    "원천 의미 값이 변경되었습니다. 연결을 갱신해 주세요.",
                    "SOURCE_CHANGED",
                )
            _match_expected(c, scoped, lines, snapshot)
        now = _now(c)
        moves = []
        for line, result in zip(lines, normalized, strict=True):
            _query(
                c,
                scoped,
                f"UPDATE wms.inbound_notice_line SET accepted_qty=:accepted_qty,quarantined_qty=:quarantined_qty,shortage_qty=:shortage_qty,reason=:reason WHERE {S} AND id=:id",
                id=line["id"],
                **result,
            )
            total_received = result["accepted_qty"] + result["quarantined_qty"]
            if total_received > 0 and line.get("lot_no"):
                lot_no = line["lot_no"].strip()
                item = base._item(c, scoped, line["item_id"])
                shelf_days = (
                    int(item["shelfLifeDays"])
                    if item and item.get("shelfLifeDays")
                    else None
                )
                received_on = now.astimezone(base.SEOUL).date()
                expiry_date = (
                    received_on + timedelta(days=shelf_days)
                    if shelf_days and shelf_days > 0
                    else None
                )
                supplier_lot_no = None
                existing_lot = _query(
                    c,
                    scoped,
                    f"SELECT id FROM wms.lot WHERE {S} AND item_id=:item_id AND lot_no=:lot_no",
                    item_id=line["item_id"],
                    lot_no=lot_no,
                ).scalar_one_or_none()
                if not existing_lot:
                    _query(
                        c,
                        scoped,
                        "INSERT INTO wms.lot(workspace_id, generation_id, item_id, lot_no, origin, received_on, expiry_date, supplier_lot_no, status, created_at) "
                        "VALUES (:w, :g, :item_id, :lot_no, 'RECEIPT', :received_on, :expiry_date, :supplier_lot_no, 'AVAILABLE', :now)",
                        item_id=line["item_id"],
                        lot_no=lot_no,
                        received_on=received_on,
                        expiry_date=expiry_date,
                        supplier_lot_no=supplier_lot_no,
                        now=now,
                    )
            for qty, loc in [
                ("accepted_qty", "normal_location_id"),
                ("quarantined_qty", "quarantine_location_id"),
            ]:
                if result[qty]:
                    moves.append(
                        {
                            "item_id": line["item_id"],
                            "location_id": line[loc],
                            "lot_no": line["lot_no"],
                            "qty_delta": result[qty],
                            "source_qty": None,
                            "source_unit": None,
                        }
                    )
        doc_id = None
        if moves:
            doc_id = base._insert_document(
                c,
                scoped,
                {
                    "document_type": "WMS_INSPECTION",
                    "status": "posted",
                    "source_key": "WMS:INSPECTION:" + row["notice_no"],
                    "source_ref": row["notice_no"],
                    "document_on": now.astimezone(base.SEOUL).date(),
                    "posted_at": now,
                },
                moves,
                now.isoformat(),
            )
        _query(
            c,
            scoped,
            f"UPDATE wms.inbound_notice SET status='INSPECTED',inspected_at=:now,stock_document_id=:doc,updated_at=:now,version=version+1 WHERE {S} AND id=:id",
            id=id,
            now=now,
            doc=doc_id,
        )
        if linked:
            _query(
                c,
                scoped,
                f"UPDATE wms.source_claim SET status='COMPLETED',closed_at=:now WHERE {S} AND id=:id",
                id=linked["id"],
                now=now,
            )
        return _detail(c, scoped, id), "inbound_notice", id

    return base._action(context, f"wms.inbound.inspect:{id}", key, values, fn)


def guard_master(c, scoped, kind, id, all_history=False):
    """Protect receiving and reservation references before master mutations."""
    from fs.wms.reservations import guard_master as guard_reservations

    guard_reservations(c, scoped, kind, id, all_history)
    condition = {
        "warehouse": "n.warehouse_id=:id",
        "item": "l.item_id=:id",
        "location": "(l.normal_location_id=:id OR l.quarantine_location_id=:id)",
    }[kind]
    status = "" if all_history else " AND n.status IN ('PLANNED','ARRIVED')"
    count = _query(
        c,
        scoped,
        "SELECT count(DISTINCT n.id) FROM wms.inbound_notice n JOIN wms.inbound_notice_line l ON l.workspace_id=n.workspace_id AND l.generation_id=n.generation_id AND l.notice_id=n.id WHERE n.workspace_id=:w AND n.generation_id=:g AND "
        + condition
        + status,
        id=id,
    ).scalar_one()
    if count:
        raise base._referenced(
            "입고 예정이 참조하고 있습니다. 취소 또는 검수 처리를 먼저 해 주세요.",
            "입고 예정",
            count,
        )
