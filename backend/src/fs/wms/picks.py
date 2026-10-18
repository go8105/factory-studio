"""W2b-1d 피킹 지시(W-12) 업무 규칙 (DSN-13 F22·F23·F27, Q4·Q5).

- 출고 예약(wms.stock_reservation) 1건당 피킹 지시(wms.pick_order) 1건(c1482 UNIQUE).
- 취소(CANCELLED)된 피킹 지시가 있는 예약에서 재생성할 때는 기존 행을 OPEN으로 재개하고
  명세(wms.pick_line)를 다시 구성한다.
- LOT 배정(c1486):
  1) 보류(wms.lot_hold 활성·QMS 품질 보류·wms.lot.status='HOLD') 및
     만료(expiry_date < business_today() 또는 status='EXPIRED') LOT 제외.
     wms.lot은 LEFT JOIN하여 마스터 행이 없는 시드 LOT도 누락 없이 포함한다.
  2) 예약 줄에 지정된 LOT이 있고 가용하면 우선 존중한다.
     보류·만료로 사용할 수 없거나 가용 수량이 부족할 때만 FEFO(expiry_date ASC NULLS LAST)
     → FIFO(received_on ASC NULLS LAST) → 위치 코드 순으로 배정하고 대체 사유를 반환한다.
  3) 가용 재고 합계가 부족하면 409 INSUFFICIENT_AVAILABLE로 거절한다.
  4) 배정된 피킹 명세는 위치 코드(storage_location.code ASC) 순으로 sequence_no(1..N)를 부여한다.
"""

from collections import defaultdict
from datetime import date
from decimal import Decimal
from typing import Any

from fs.common.clock import business_today
from fs.common.scope import read_scope
from fs.qms import interface as qms
from fs.wms import receiving as rec
from fs.wms import service as base

S = base._S
q = rec._query


def _reservation_header(c, scoped, res_id: int, lock: bool = False) -> dict[str, Any]:
    row = (
        q(
            c,
            scoped,
            f"SELECT * FROM wms.stock_reservation WHERE {S} AND id=:id"
            + (" FOR UPDATE" if lock else ""),
            id=res_id,
        )
        .mappings()
        .first()
    )
    if row is None:
        raise base._not_found("예약")
    return dict(row)


def _reservation_lines(c, scoped, res_id: int) -> list[dict[str, Any]]:
    sql = f"""
    SELECT rl.id, rl.reservation_id, rl.line_no, rl.item_id, rl.location_id, rl.lot_no, rl.quantity,
           i.item_code, i.name AS item_name, i.base_unit, i.item_class, i.lot_tracked,
           loc.code AS location_code, loc.name AS location_name, loc.warehouse_id,
           w.code AS warehouse_code, w.name AS warehouse_name
    FROM wms.stock_reservation_line rl
    JOIN wms.item i
      ON i.workspace_id=rl.workspace_id AND i.generation_id=rl.generation_id AND i.id=rl.item_id
    JOIN wms.storage_location loc
      ON loc.workspace_id=rl.workspace_id AND loc.generation_id=rl.generation_id AND loc.id=rl.location_id
    JOIN wms.warehouse w
      ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
    WHERE rl.{S.replace(" AND ", " AND rl.")} AND rl.reservation_id=:res_id
    ORDER BY rl.line_no
    """
    return [dict(r) for r in q(c, scoped, sql, res_id=res_id).mappings()]


def _lot_metadata(
    c, scoped, item_ids: list[int]
) -> dict[tuple[int, str], dict[str, Any]]:
    if not item_ids:
        return {}
    sql = f"""
    SELECT l.id, l.item_id, l.lot_no, l.received_on, l.expiry_date, l.status AS raw_status,
           EXISTS (
               SELECT 1 FROM wms.lot_hold lh
               WHERE lh.workspace_id=l.workspace_id
                 AND lh.generation_id=l.generation_id
                 AND lh.lot_id=l.id
                 AND lh.released_at IS NULL
           ) AS has_active_hold
    FROM wms.lot l
    WHERE l.{S.replace(" AND ", " AND l.")}
      AND l.item_id = ANY(:item_ids)
    """
    return {
        (r["item_id"], r["lot_no"]): dict(r)
        for r in q(c, scoped, sql, item_ids=item_ids).mappings()
    }


def _lot_block_reason(
    item_id: int,
    lot_no: str | None,
    lot_map: dict[tuple[int, str], dict[str, Any]],
    qms_held: set[str],
    today: date,
) -> tuple[str, str] | None:
    if lot_no is None:
        return None
    info = lot_map.get((item_id, lot_no))
    if info and info["has_active_hold"]:
        return ("HOLD", "보류(HOLD) 상태")
    if lot_no in qms_held:
        return ("QMS_HOLD", "QMS 품질 보류 상태")
    if info and info["raw_status"] == "HOLD":
        return ("HOLD", "보류(HOLD) 상태")
    if info and (
        (info["expiry_date"] is not None and info["expiry_date"] < today)
        or info["raw_status"] == "EXPIRED"
    ):
        return ("EXPIRED", "유효기간 만료(EXPIRED)")
    return None


def _fefo_fifo_key(bucket: dict[str, Any]) -> tuple[Any, ...]:
    exp: date | None = bucket["expiry_date"]
    rec_on: date | None = bucket["received_on"]
    lot_no: str | None = bucket["lot_no"]
    return (
        0 if exp is not None else 1,
        exp or date.max,
        0 if rec_on is not None else 1,
        rec_on or date.max,
        0 if lot_no is not None else 1,
        lot_no or "",
        bucket["location_code"],
        bucket["location_id"],
    )


def _candidate_buckets(
    c,
    scoped,
    res_id: int,
    item_ids: list[int],
    lot_map: dict[tuple[int, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    if not item_ids:
        return []
    on_hand_sql = f"""
    SELECT m.item_id,
           m.location_id,
           loc.warehouse_id,
           loc.code AS location_code,
           loc.name AS location_name,
           m.lot_no,
           SUM(m.qty_delta) AS on_hand,
           MIN(CASE WHEN m.qty_delta > 0 THEN d.document_on END) AS first_inbound_on
    FROM wms.stock_move m
    JOIN wms.stock_document d
      ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
    JOIN wms.storage_location loc
      ON loc.workspace_id=m.workspace_id AND loc.generation_id=m.generation_id AND loc.id=m.location_id
    JOIN wms.warehouse w
      ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
    WHERE m.{S.replace(" AND ", " AND m.")}
      AND d.status='posted'
      AND loc.is_active = TRUE
      AND w.is_active = TRUE
      AND loc.location_type = 'NORMAL'
      AND m.item_id = ANY(:item_ids)
    GROUP BY m.item_id, m.location_id, loc.warehouse_id, loc.code, loc.name, m.lot_no
    HAVING SUM(m.qty_delta) > 0
    """
    committed_sql = f"""
    SELECT item_id, location_id, lot_no, SUM(committed_qty) AS committed_qty
    FROM (
        SELECT rl.item_id, rl.location_id, rl.lot_no, SUM(rl.quantity) AS committed_qty
        FROM wms.stock_reservation_line rl
        JOIN wms.stock_reservation r
          ON r.workspace_id=rl.workspace_id AND r.generation_id=rl.generation_id AND r.id=rl.reservation_id
        LEFT JOIN wms.pick_order po
          ON po.workspace_id=r.workspace_id AND po.generation_id=r.generation_id AND po.reservation_id=r.id
        WHERE rl.{S.replace(" AND ", " AND rl.")}
          AND r.status = 'ACTIVE'
          AND r.id <> :res_id
          AND (po.id IS NULL OR po.status = 'CANCELLED')
          AND rl.item_id = ANY(:item_ids)
        GROUP BY rl.item_id, rl.location_id, rl.lot_no

        UNION ALL

        SELECT pl.item_id, pl.location_id, pl.lot_no, SUM(pl.qty) AS committed_qty
        FROM wms.pick_line pl
        JOIN wms.pick_order po
          ON po.workspace_id=pl.workspace_id AND po.generation_id=pl.generation_id AND po.id=pl.pick_order_id
        JOIN wms.stock_reservation r
          ON r.workspace_id=po.workspace_id AND r.generation_id=po.generation_id AND r.id=po.reservation_id
        WHERE pl.{S.replace(" AND ", " AND pl.")}
          AND r.status = 'ACTIVE'
          AND r.id <> :res_id
          AND po.status = 'OPEN'
          AND pl.item_id = ANY(:item_ids)
        GROUP BY pl.item_id, pl.location_id, pl.lot_no
    ) sub
    GROUP BY item_id, location_id, lot_no
    """
    committed_map = {
        (r["item_id"], r["location_id"], r["lot_no"]): Decimal(str(r["committed_qty"]))
        for r in q(
            c, scoped, committed_sql, res_id=res_id, item_ids=item_ids
        ).mappings()
    }
    buckets: list[dict[str, Any]] = []
    for r in q(c, scoped, on_hand_sql, item_ids=item_ids).mappings():
        key = (r["item_id"], r["location_id"], r["lot_no"])
        on_hand = Decimal(str(r["on_hand"]))
        other_committed = committed_map.get(key, Decimal(0))
        avail = max(Decimal(0), on_hand - other_committed)
        lot_info = (
            lot_map.get((r["item_id"], r["lot_no"]))
            if r["lot_no"] is not None
            else None
        )
        expiry_date = lot_info["expiry_date"] if lot_info else None
        received_on = (
            lot_info["received_on"]
            if (lot_info and lot_info["received_on"] is not None)
            else r["first_inbound_on"]
        )
        buckets.append(
            {
                "item_id": r["item_id"],
                "location_id": r["location_id"],
                "warehouse_id": r["warehouse_id"],
                "location_code": r["location_code"],
                "location_name": r["location_name"],
                "lot_no": r["lot_no"],
                "on_hand": on_hand,
                "avail": avail,
                "initial_avail": avail,
                "expiry_date": expiry_date,
                "received_on": received_on,
            }
        )
    return buckets


def _allocate_lines(
    c, scoped, res_id: int, res_lines: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    item_ids = sorted({rl["item_id"] for rl in res_lines})
    lot_map = _lot_metadata(c, scoped, item_ids)
    qms_held = set(qms.held_lot_nos(c, scoped) or ())
    today = business_today()
    buckets = _candidate_buckets(c, scoped, res_id, item_ids, lot_map)

    requested_by_item_wh: dict[tuple[int, int], Decimal] = defaultdict(Decimal)
    for rl in res_lines:
        requested_by_item_wh[(rl["item_id"], rl["warehouse_id"])] += Decimal(
            str(rl["quantity"])
        )

    def _is_bucket_eligible(b: dict[str, Any], lot_required: bool) -> bool:
        if lot_required and b["lot_no"] is None:
            return False
        if not lot_required and b["lot_no"] is not None:
            return (
                _lot_block_reason(b["item_id"], b["lot_no"], lot_map, qms_held, today)
                is None
            )
        return (
            _lot_block_reason(b["item_id"], b["lot_no"], lot_map, qms_held, today)
            is None
        )

    allocated_by_key: dict[tuple[int, int, str | None], dict[str, Any]] = {}

    def _take(b: dict[str, Any], qty: Decimal, item_code: str) -> None:
        b["avail"] -= qty
        key = (b["item_id"], b["location_id"], b["lot_no"])
        entry = allocated_by_key.get(key)
        if entry is None:
            allocated_by_key[key] = {
                "item_id": b["item_id"],
                "item_code": item_code,
                "location_id": b["location_id"],
                "location_code": b["location_code"],
                "lot_no": b["lot_no"],
                "qty": qty,
            }
        else:
            entry["qty"] += qty

    for rl in res_lines:
        item_id = rl["item_id"]
        wh_id = rl["warehouse_id"]
        req_loc_id = rl["location_id"]
        req_lot = rl["lot_no"]
        lot_required = bool(rl["lot_tracked"] or req_lot is not None)
        needed = Decimal(str(rl["quantity"]))

        item_wh_buckets = [
            b for b in buckets if b["item_id"] == item_id and b["warehouse_id"] == wh_id
        ]

        # 1) 예약 줄에 LOT이 지정되어 있으면 가용하고 보류/만료가 아닐 때 우선 존중
        if req_lot is not None:
            block = _lot_block_reason(item_id, req_lot, lot_map, qms_held, today)
            if block is None:
                # 1a) 예약된 정확한 위치 + LOT 우선
                for b in item_wh_buckets:
                    if (
                        b["location_id"] == req_loc_id
                        and b["lot_no"] == req_lot
                        and b["avail"] > 0
                    ):
                        take = min(needed, b["avail"])
                        _take(b, take, rl["item_code"])
                        needed -= take
                        break
                # 1b) 같은 창고 내 다른 위치의 동일 LOT
                if needed > 0:
                    same_lot_buckets = sorted(
                        (
                            b
                            for b in item_wh_buckets
                            if b["lot_no"] == req_lot and b["avail"] > 0
                        ),
                        key=lambda x: (x["location_code"], x["location_id"]),
                    )
                    for b in same_lot_buckets:
                        take = min(needed, b["avail"])
                        _take(b, take, rl["item_code"])
                        needed -= take
                        if needed == 0:
                            break
        elif not lot_required:
            # 비-LOT 품목이고 예약 줄에 LOT이 없으면 예약 위치의 비-LOT 재고 우선
            for b in item_wh_buckets:
                if (
                    b["location_id"] == req_loc_id
                    and b["lot_no"] is None
                    and b["avail"] > 0
                ):
                    take = min(needed, b["avail"])
                    _take(b, take, rl["item_code"])
                    needed -= take
                    break

        # 2) 남은 수량(보류/만료 대체 또는 수량 부족분 또는 LOT 미지정)은 FEFO → FIFO 순 배정
        if needed > 0:
            fefo_candidates = sorted(
                (
                    b
                    for b in item_wh_buckets
                    if b["avail"] > 0 and _is_bucket_eligible(b, lot_required)
                ),
                key=_fefo_fifo_key,
            )
            for b in fefo_candidates:
                take = min(needed, b["avail"])
                _take(b, take, rl["item_code"])
                needed -= take
                if needed == 0:
                    break

        # 3) 가용 재고 부족 시 409 INSUFFICIENT_AVAILABLE
        if needed > 0:
            total_req = requested_by_item_wh[(item_id, wh_id)]
            total_avail = sum(
                (
                    b["initial_avail"]
                    for b in item_wh_buckets
                    if _is_bucket_eligible(b, lot_required)
                ),
                Decimal(0),
            )
            excluded_lots: list[dict[str, Any]] = []
            seen_excluded: set[str] = set()
            candidates_to_check = [req_lot] if req_lot else []
            candidates_to_check.extend(
                b["lot_no"] for b in item_wh_buckets if b["lot_no"] is not None
            )
            for cand_lot in candidates_to_check:
                if cand_lot and cand_lot not in seen_excluded:
                    reason = _lot_block_reason(
                        item_id, cand_lot, lot_map, qms_held, today
                    )
                    if reason is not None:
                        seen_excluded.add(cand_lot)
                        excluded_lots.append(
                            {
                                "lotNo": cand_lot,
                                "reason": reason[0],
                                "reasonLabel": reason[1],
                            }
                        )
            raise base._conflict(
                f"피킹 가능한 가용 재고(보류·만료 제외)가 부족합니다. ({rl['item_code']})",
                "INSUFFICIENT_AVAILABLE",
                itemId=item_id,
                itemCode=rl["item_code"],
                warehouseCode=rl["warehouse_code"],
                requested=f"{total_req:.3f}",
                available=f"{total_avail:.3f}",
                excludedLots=excluded_lots,
            )

    # 4) 위치 코드 순 정렬 후 sequence_no, line_no 부여
    sorted_lines = sorted(
        allocated_by_key.values(),
        key=lambda x: (
            x["location_code"],
            x["item_code"],
            x["lot_no"] or "",
            x["location_id"],
        ),
    )
    for idx, line in enumerate(sorted_lines, 1):
        line["line_no"] = idx
        line["sequence_no"] = idx
    return sorted_lines


def _compute_substitutions(
    res_lines: list[dict[str, Any]],
    pick_lines: list[dict[str, Any]],
    lot_map: dict[tuple[int, str], dict[str, Any]],
    qms_held: set[str],
    today: date,
) -> list[dict[str, Any]]:
    """예약 줄의 지정 LOT과 실제 배정된 피킹 명세를 비교해 대체 사유 목록을 구성한다."""
    picked_by_item_lot: dict[tuple[int, str | None], Decimal] = defaultdict(Decimal)
    picked_by_item: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for pl in pick_lines:
        picked_by_item_lot[(pl["item_id"], pl["lot_no"])] += Decimal(str(pl["qty"]))
        picked_by_item[pl["item_id"]].append(pl)

    substitutions: list[dict[str, Any]] = []
    for rl in res_lines:
        req_lot = rl.get("lot_no")
        if not req_lot:
            continue
        item_id = rl["item_id"]
        req_qty = Decimal(str(rl["quantity"]))
        kept_qty = picked_by_item_lot.get((item_id, req_lot), Decimal(0))
        if kept_qty >= req_qty:
            continue
        block = _lot_block_reason(item_id, req_lot, lot_map, qms_held, today)
        if block is not None:
            reason_code, reason_label = block
        else:
            reason_code, reason_label = ("SHORTAGE", "예약 LOT 가용 수량 부족")
        replacement_lots = [
            {
                "lotNo": pl["lot_no"],
                "locationCode": pl["location_code"],
                "qty": f"{Decimal(str(pl['qty'])):.3f}",
            }
            for pl in picked_by_item.get(item_id, [])
            if pl["lot_no"] != req_lot
        ]
        rep_summary = (
            ", ".join(
                f"{x['lotNo'] or '미지정'}({x['locationCode']} · {x['qty']})"
                for x in replacement_lots
            )
            or "대체 LOT"
        )
        substitutions.append(
            {
                "lineNo": rl["line_no"],
                "itemId": item_id,
                "itemCode": rl["item_code"],
                "requestedLotNo": req_lot,
                "requestedLocationCode": rl["location_code"],
                "requestedQty": f"{req_qty:.3f}",
                "keptQty": f"{kept_qty:.3f}",
                "reason": reason_code,
                "reasonLabel": reason_label,
                "allocatedLots": replacement_lots,
                "message": (
                    f"예약 LOT {req_lot}이(가) {reason_label}이어서 "
                    f"FEFO/FIFO 기준으로 {rep_summary}을(를) 배정했습니다."
                ),
            }
        )
    return substitutions


def _pick_lines_for_orders(
    c, scoped, order_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    if not order_ids:
        return {}
    sql = f"""
    SELECT pl.id, pl.pick_order_id, pl.line_no, pl.sequence_no,
           pl.item_id, i.item_code, i.name AS item_name, i.item_class, i.base_unit, i.lot_tracked,
           pl.location_id, loc.code AS location_code, loc.name AS location_name,
           loc.warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name,
           pl.lot_no, pl.qty, pl.picked_qty, pl.created_at,
           l.expiry_date,
           COALESCE(
               l.received_on,
               (
                   SELECT MIN(d.document_on)
                   FROM wms.stock_move m
                   JOIN wms.stock_document d
                     ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id
                   WHERE m.workspace_id=pl.workspace_id
                     AND m.generation_id=pl.generation_id
                     AND m.item_id=pl.item_id
                     AND COALESCE(m.lot_no, '')=COALESCE(pl.lot_no, '')
                     AND d.status='posted'
                     AND m.qty_delta > 0
               )
           ) AS received_on
    FROM wms.pick_line pl
    JOIN wms.item i
      ON i.workspace_id=pl.workspace_id AND i.generation_id=pl.generation_id AND i.id=pl.item_id
    JOIN wms.storage_location loc
      ON loc.workspace_id=pl.workspace_id AND loc.generation_id=pl.generation_id AND loc.id=pl.location_id
    JOIN wms.warehouse w
      ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
    LEFT JOIN wms.lot l
      ON l.workspace_id=pl.workspace_id
     AND l.generation_id=pl.generation_id
     AND l.item_id=pl.item_id
     AND l.lot_no=pl.lot_no
    WHERE pl.{S.replace(" AND ", " AND pl.")}
      AND pl.pick_order_id = ANY(:order_ids)
    ORDER BY pl.pick_order_id, pl.sequence_no ASC, pl.line_no ASC
    """
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in q(c, scoped, sql, order_ids=order_ids).mappings():
        grouped[r["pick_order_id"]].append(dict(r))
    return grouped


def _format_pick_line(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "pickOrderId": r["pick_order_id"],
        "lineNo": r["line_no"],
        "sequenceNo": r["sequence_no"],
        "itemId": r["item_id"],
        "itemCode": r["item_code"],
        "itemName": r["item_name"],
        "itemClass": r["item_class"],
        "baseUnit": r["base_unit"],
        "lotTracked": r["lot_tracked"],
        "locationId": r["location_id"],
        "locationCode": r["location_code"],
        "locationName": r["location_name"],
        "warehouseId": r["warehouse_id"],
        "warehouseCode": r["warehouse_code"],
        "warehouseName": r["warehouse_name"],
        "lotNo": r["lot_no"],
        "expiryDate": str(r["expiry_date"]) if r.get("expiry_date") else None,
        "receivedOn": str(r["received_on"]) if r.get("received_on") else None,
        "qty": f"{Decimal(str(r['qty'])):.3f}",
        "pickedQty": (
            f"{Decimal(str(r['picked_qty'])):.3f}"
            if r.get("picked_qty") is not None
            else None
        ),
        "createdAt": (
            r["created_at"].isoformat()
            if hasattr(r["created_at"], "isoformat")
            else str(r["created_at"])
        ),
    }


def _enrich_orders(
    c, scoped, header_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if not header_rows:
        return []
    order_ids = [r["id"] for r in header_rows]
    raw_lines_by_order = _pick_lines_for_orders(c, scoped, order_ids)

    res_ids = sorted({r["reservation_id"] for r in header_rows})
    res_lines_by_res: dict[int, list[dict[str, Any]]] = defaultdict(list)
    all_item_ids: set[int] = set()
    for rl in q(
        c,
        scoped,
        f"""
        SELECT rl.id, rl.reservation_id, rl.line_no, rl.item_id, rl.location_id, rl.lot_no, rl.quantity,
               i.item_code, loc.code AS location_code
        FROM wms.stock_reservation_line rl
        JOIN wms.item i
          ON i.workspace_id=rl.workspace_id AND i.generation_id=rl.generation_id AND i.id=rl.item_id
        JOIN wms.storage_location loc
          ON loc.workspace_id=rl.workspace_id AND loc.generation_id=rl.generation_id AND loc.id=rl.location_id
        WHERE rl.{S.replace(" AND ", " AND rl.")}
          AND rl.reservation_id = ANY(:res_ids)
        ORDER BY rl.reservation_id, rl.line_no
        """,
        res_ids=res_ids,
    ).mappings():
        d = dict(rl)
        res_lines_by_res[d["reservation_id"]].append(d)
        all_item_ids.add(d["item_id"])

    lot_map = _lot_metadata(c, scoped, sorted(all_item_ids))
    qms_held = set(qms.held_lot_nos(c, scoped) or ())
    today = business_today()

    enriched: list[dict[str, Any]] = []
    for r in header_rows:
        oid = r["id"]
        raw_lines = raw_lines_by_order.get(oid, [])
        formatted_lines = [_format_pick_line(x) for x in raw_lines]
        total_qty = sum((Decimal(str(x["qty"])) for x in raw_lines), Decimal(0))
        has_picked = any(x.get("picked_qty") is not None for x in raw_lines)
        total_picked = (
            sum(
                (Decimal(str(x["picked_qty"] or 0)) for x in raw_lines),
                Decimal(0),
            )
            if has_picked
            else None
        )
        first_line = raw_lines[0] if raw_lines else None
        substitutions = _compute_substitutions(
            res_lines_by_res.get(r["reservation_id"], []),
            raw_lines,
            lot_map,
            qms_held,
            today,
        )
        enriched.append(
            {
                "id": oid,
                "pickNo": r["pick_no"],
                "reservationId": r["reservation_id"],
                "reservationNo": r["reservation_no"],
                "reservationStatus": r["reservation_status"],
                "shipmentOrderRef": r["shipment_order_ref"],
                "warehouseId": first_line["warehouse_id"]
                if first_line
                else r.get("warehouse_id"),
                "warehouseCode": first_line["warehouse_code"]
                if first_line
                else r.get("warehouse_code"),
                "warehouseName": first_line["warehouse_name"]
                if first_line
                else r.get("warehouse_name"),
                "status": r["status"],
                "pickedAt": r["picked_at"].isoformat() if r.get("picked_at") else None,
                "stockDocumentId": r.get("stock_document_id"),
                "stockDocumentNo": r.get("stock_document_no"),
                "cancelReason": r.get("cancel_reason"),
                "createdAt": (
                    r["created_at"].isoformat()
                    if hasattr(r["created_at"], "isoformat")
                    else str(r["created_at"])
                ),
                "lineCount": len(formatted_lines),
                "totalQty": f"{total_qty:.3f}",
                "totalPickedQty": (
                    f"{total_picked:.3f}" if total_picked is not None else None
                ),
                "lotSubstitutions": substitutions,
                "lines": formatted_lines,
            }
        )
    return enriched


PICK_ORDER_SELECT = f"""
SELECT po.id, po.pick_no, po.reservation_id, po.status, po.picked_at,
       po.stock_document_id, po.cancel_reason, po.created_at,
       r.reservation_no, r.status AS reservation_status, r.shipment_order_ref,
       d.document_no AS stock_document_no,
       wh.warehouse_id, wh.warehouse_code, wh.warehouse_name
FROM wms.pick_order po
JOIN wms.stock_reservation r
  ON r.workspace_id=po.workspace_id AND r.generation_id=po.generation_id AND r.id=po.reservation_id
LEFT JOIN wms.stock_document d
  ON d.workspace_id=po.workspace_id AND d.generation_id=po.generation_id AND d.id=po.stock_document_id
LEFT JOIN LATERAL (
    SELECT loc.warehouse_id, w.code AS warehouse_code, w.name AS warehouse_name
    FROM wms.stock_reservation_line rl
    JOIN wms.storage_location loc
      ON loc.workspace_id=rl.workspace_id AND loc.generation_id=rl.generation_id AND loc.id=rl.location_id
    JOIN wms.warehouse w
      ON w.workspace_id=loc.workspace_id AND w.generation_id=loc.generation_id AND w.id=loc.warehouse_id
    WHERE rl.workspace_id=po.workspace_id
      AND rl.generation_id=po.generation_id
      AND rl.reservation_id=po.reservation_id
    ORDER BY rl.line_no
    LIMIT 1
) wh ON TRUE
WHERE po.{S.replace(" AND ", " AND po.")}
"""


def _detail(c, scoped, pick_order_id: int) -> dict[str, Any]:
    row = (
        q(c, scoped, PICK_ORDER_SELECT + " AND po.id=:id", id=pick_order_id)
        .mappings()
        .first()
    )
    if row is None:
        raise base._not_found("피킹 지시")
    return _enrich_orders(c, scoped, [dict(row)])[0]


def get_pick_order(context: base.AuthContext, id: int) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        return _detail(c, scoped, id)


def list_pick_orders(
    context: base.AuthContext,
    status: str | None = None,
    warehouse_id: int | None = None,
    reservation_id: int | None = None,
    item_code: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    with base._read() as c:
        scoped = read_scope(c, context, base.MODULE)
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if status:
            clauses.append("po.status = :status")
            params["status"] = status
        if warehouse_id is not None:
            clauses.append("wh.warehouse_id = :warehouse_id")
            params["warehouse_id"] = warehouse_id
        if reservation_id is not None:
            clauses.append("po.reservation_id = :reservation_id")
            params["reservation_id"] = reservation_id
        if item_code:
            clauses.append(
                "EXISTS ("
                "  SELECT 1 FROM wms.pick_line pl "
                "  JOIN wms.item i ON i.workspace_id=pl.workspace_id "
                "   AND i.generation_id=pl.generation_id AND i.id=pl.item_id "
                "  WHERE pl.workspace_id=po.workspace_id "
                "    AND pl.generation_id=po.generation_id "
                "    AND pl.pick_order_id=po.id "
                "    AND i.item_code=:item_code"
                ")"
            )
            params["item_code"] = item_code

        where_extra = (" AND " + " AND ".join(clauses)) if clauses else ""
        count_sql = f"SELECT count(*) FROM ({PICK_ORDER_SELECT}{where_extra}) cnt"
        total = q(c, scoped, count_sql, **params).scalar_one()

        rows_sql = (
            f"{PICK_ORDER_SELECT}{where_extra} "
            "ORDER BY po.created_at DESC, po.id DESC "
            "LIMIT :limit OFFSET :offset"
        )
        raw_rows = [
            dict(r)
            for r in q(
                c,
                scoped,
                rows_sql,
                **params,
                limit=page_size,
                offset=(page - 1) * page_size,
            ).mappings()
        ]
        return {
            "rows": _enrich_orders(c, scoped, raw_rows),
            "total": total,
            "page": page,
            "pageSize": page_size,
        }


def create_pick_order(
    context: base.AuthContext, values: dict[str, Any], key: str
) -> dict[str, Any]:
    res_id = int(values["reservation_id"])

    def fn(c, scoped):
        res = _reservation_header(c, scoped, res_id, lock=True)
        if res["status"] != "ACTIVE":
            raise base._conflict(
                "활성(ACTIVE) 상태의 출고 예약만 피킹 지시를 생성할 수 있습니다.",
                "INVALID_STATE",
                reservationId=res_id,
                reservationStatus=res["status"],
            )

        existing = (
            q(
                c,
                scoped,
                f"SELECT * FROM wms.pick_order WHERE {S} AND reservation_id=:res_id FOR UPDATE",
                res_id=res_id,
            )
            .mappings()
            .first()
        )
        if existing is not None and existing["status"] != "CANCELLED":
            raise base._conflict(
                "이미 피킹 지시가 생성된 예약입니다.",
                "PICK_ORDER_EXISTS",
                pickOrderId=existing["id"],
                pickNo=existing["pick_no"],
                status=existing["status"],
            )

        res_lines = _reservation_lines(c, scoped, res_id)
        if not res_lines:
            raise base._conflict("예약 명세가 없습니다.", "INVALID_STATE")

        allocated_lines = _allocate_lines(c, scoped, res_id, res_lines)
        now = rec._now(c)

        if existing is not None:
            # c1482: (workspace_id, generation_id, reservation_id)는 무조건부 UNIQUE이므로
            # 취소된 지시가 있으면 기존 행을 OPEN으로 재개하고 명세를 교체한다.
            pick_order_id = existing["id"]
            q(
                c,
                scoped,
                f"DELETE FROM wms.pick_line WHERE {S} AND pick_order_id=:id",
                id=pick_order_id,
            )
            q(
                c,
                scoped,
                f"UPDATE wms.pick_order "
                f"SET status='OPEN', picked_at=NULL, stock_document_id=NULL, "
                f"    cancel_reason=NULL, created_at=:now "
                f"WHERE {S} AND id=:id",
                id=pick_order_id,
                now=now,
            )
        else:
            stem = f"PK-{now.astimezone(base.SEOUL):%Y%m%d}-"
            used = q(
                c,
                scoped,
                f"SELECT COALESCE(max(CAST(substring(pick_no FROM 13) AS bigint)), 0) "
                f"FROM wms.pick_order WHERE {S} AND pick_no LIKE :stem",
                stem=stem + "%",
            ).scalar_one()
            pick_no = f"{stem}{used + 1:03d}"
            pick_order_id = q(
                c,
                scoped,
                "INSERT INTO wms.pick_order("
                "  workspace_id, generation_id, pick_no, reservation_id, "
                "  status, picked_at, stock_document_id, cancel_reason, created_at"
                ") VALUES ("
                "  :w, :g, :pick_no, :res_id, 'OPEN', NULL, NULL, NULL, :now"
                ") RETURNING id",
                pick_no=pick_no,
                res_id=res_id,
                now=now,
            ).scalar_one()

        for line in allocated_lines:
            q(
                c,
                scoped,
                "INSERT INTO wms.pick_line("
                "  workspace_id, generation_id, pick_order_id, line_no, "
                "  item_id, location_id, lot_no, qty, picked_qty, sequence_no, created_at"
                ") VALUES ("
                "  :w, :g, :pick_order_id, :line_no, "
                "  :item_id, :location_id, :lot_no, :qty, NULL, :sequence_no, :now"
                ")",
                pick_order_id=pick_order_id,
                line_no=line["line_no"],
                item_id=line["item_id"],
                location_id=line["location_id"],
                lot_no=line["lot_no"],
                qty=line["qty"],
                sequence_no=line["sequence_no"],
                now=now,
            )

        return _detail(c, scoped, pick_order_id), "pick_order", pick_order_id

    return base._action(context, f"wms.pick.create:{res_id}", key, values, fn, 201)


def guard_master(c, scoped, kind: str, id: int, all_history: bool = False) -> None:
    condition = {
        "warehouse": "loc.warehouse_id=:id",
        "item": "pl.item_id=:id",
        "location": "pl.location_id=:id",
    }[kind]
    status_clause = "" if all_history else " AND po.status = 'OPEN'"
    count = q(
        c,
        scoped,
        "SELECT count(DISTINCT po.id) "
        "FROM wms.pick_order po "
        "JOIN wms.pick_line pl "
        "  ON pl.workspace_id=po.workspace_id AND pl.generation_id=po.generation_id AND pl.pick_order_id=po.id "
        "JOIN wms.storage_location loc "
        "  ON loc.workspace_id=pl.workspace_id AND loc.generation_id=pl.generation_id AND loc.id=pl.location_id "
        f"WHERE po.{S.replace(' AND ', ' AND po.')} AND " + condition + status_clause,
        id=id,
    ).scalar_one()
    if count:
        raise base._referenced(
            "피킹 지시가 참조하고 있습니다. 피킹 확정 또는 취소 처리를 먼저 해 주세요.",
            "피킹 지시",
            count,
        )
