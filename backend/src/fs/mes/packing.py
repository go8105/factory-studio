"""M-08 패킹 · M-09 완제품 입고 (FS-020f, TX-10·TX-11, FS-006b §6).

BOX에 LOT 양품을 담고(open → closed), 닫힌 BOX를 PALLET에 묶어(open → closed) PALLET 단위로 입고한다(→ received).
BOX는 입고 뒤에도 closed로 두고 화면은 부모 PALLET 상태를 따른다. 입고 후 구성 변경·입고 취소는 첫 공개 범위 밖이다.
잠금: 공간 → LOT(id 순) → PALLET(id 순) → BOX(id 순). LOT 수량을 바꾸는 경로는 LOT부터 고정한다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.auth import AuthContext
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.mes import repository as repo
from fs.mes.planning import _next_code
from fs.mes.service import MODULE, _action, _field, _not_found, _read

_S = "workspace_id=:w AND generation_id=:g"


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


# LOT의 최종 양품 = 완료(normal) LOT의 마지막 단계 양품. 전량 불량 LOT은 0이라 담을 수 없다.
LOT_GOOD_SQL = """
SELECT t.id lot_id, t.lot_no, t.unit, o.item_id, o.order_no,
       (SELECT x.good_qty FROM mes.operation_execution e
          JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
           AND s.id=e.route_step_id
          JOIN mes.operation_result x ON x.workspace_id=e.workspace_id
           AND x.generation_id=e.generation_id AND x.execution_id=e.id
         WHERE e.workspace_id=t.workspace_id AND e.generation_id=t.generation_id AND e.lot_id=t.id
         ORDER BY s.sequence_no DESC LIMIT 1) final_good_qty,
       (SELECT coalesce(sum(m.packed_qty), 0) FROM mes.packing_member m
         WHERE m.workspace_id=t.workspace_id AND m.generation_id=t.generation_id
           AND m.lot_id=t.id) packed_qty
FROM mes.lot t JOIN mes.work_order o ON o.workspace_id=t.workspace_id
 AND o.generation_id=t.generation_id AND o.id=t.work_order_id
WHERE t.workspace_id=:w AND t.generation_id=:g AND t.status='completed'
  AND t.completion_reason='normal'
"""


def _lot_row(row: Any) -> dict[str, Any]:
    lot = repo.row_dict(row)
    lot["remainingQty"] = str(Decimal(lot["finalGoodQty"]) - Decimal(lot["packedQty"]))
    return lot


def packable_lots(context: AuthContext) -> list[dict[str, Any]]:
    """패킹할 양품이 남은 LOT(최종 공정까지 정상 완료)."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        rows = connection.execute(
            text(LOT_GOOD_SQL + " ORDER BY t.lot_no"), _s(scoped)
        ).mappings()
        return [lot for lot in map(_lot_row, rows) if Decimal(lot["remainingQty"]) > 0]


UNIT_SQL = """
SELECT u.id, u.packing_no, u.packing_kind, u.parent_packing_unit_id, u.status, u.created_at,
       p.packing_no parent_packing_no, p.status parent_status, r.received_at
FROM mes.packing_unit u
LEFT JOIN mes.packing_unit p ON p.workspace_id=u.workspace_id AND p.generation_id=u.generation_id
 AND p.id=u.parent_packing_unit_id
LEFT JOIN mes.finished_goods_receipt r ON r.workspace_id=u.workspace_id
 AND r.generation_id=u.generation_id AND r.packing_unit_id=u.id
WHERE u.workspace_id=:w AND u.generation_id=:g
"""
MEMBER_SQL = """
SELECT m.id, m.packing_unit_id, m.lot_id, t.lot_no, t.unit, o.item_id, m.packed_qty
FROM mes.packing_member m
JOIN mes.lot t ON t.workspace_id=m.workspace_id AND t.generation_id=m.generation_id AND t.id=m.lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
WHERE m.workspace_id=:w AND m.generation_id=:g
"""


def _units(connection, scoped, unit_id: int | None = None) -> list[dict[str, Any]]:
    units = [
        repo.row_dict(r)
        for r in connection.execute(
            text(UNIT_SQL + " ORDER BY u.packing_kind DESC, u.packing_no DESC"),
            _s(scoped),
        ).mappings()
    ]
    members = [
        repo.row_dict(r)
        for r in connection.execute(
            text(MEMBER_SQL + " ORDER BY m.id"), _s(scoped)
        ).mappings()
    ]
    by_id = {u["id"]: u for u in units}
    for unit in units:
        unit["members"] = [m for m in members if m["packingUnitId"] == unit["id"]]
        unit["childIds"] = [
            u["id"] for u in units if u["parentPackingUnitId"] == unit["id"]
        ]
    for unit in units:
        boxes = (
            [by_id[c] for c in unit["childIds"]]
            if unit["packingKind"] == "PALLET"
            else [unit]
        )
        rows = [m for box in boxes for m in box["members"]]
        unit["itemId"] = rows[0]["itemId"] if rows else None
        unit["unit"] = rows[0]["unit"] if rows else None
        unit["totalQty"] = str(sum((Decimal(m["packedQty"]) for m in rows), Decimal(0)))
        # BOX는 입고 뒤에도 closed로 두고 표시 상태는 부모 PALLET에서 계산한다(FS-006b §6).
        unit["displayStatus"] = (
            unit["parentStatus"]
            if unit["packingKind"] == "BOX"
            and unit["parentStatus"] in ("received", "shipped")
            else unit["status"]
        )
    return [by_id[unit_id]] if unit_id is not None else units


def list_units(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        return _units(connection, read_scope(connection, context, MODULE))


def list_receipts(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        units = {u["id"]: u for u in _units(connection, scoped)}
        rows = connection.execute(
            text(
                f"SELECT id, packing_unit_id, received_at, status FROM mes.finished_goods_receipt "
                f"WHERE {_S} ORDER BY received_at DESC, id DESC"
            ),
            _s(scoped),
        ).mappings()
        return [
            {
                **repo.row_dict(r),
                "packingNo": units[r["packing_unit_id"]]["packingNo"],
                "itemId": units[r["packing_unit_id"]]["itemId"],
                "totalQty": units[r["packing_unit_id"]]["totalQty"],
                "unitStatus": units[r["packing_unit_id"]]["status"],
            }
            for r in rows
        ]


def _lock_units(connection, scoped, ids: list[int]) -> dict[int, dict[str, Any]]:
    """PALLET 먼저, 그다음 BOX를 id 순으로 잠근다."""
    rows = (
        connection.execute(
            text(
                f"SELECT id, packing_no, packing_kind, parent_packing_unit_id, status "
                f"FROM mes.packing_unit WHERE {_S} AND id = ANY(:ids) "
                "ORDER BY (packing_kind='BOX'), id FOR UPDATE"
            ),
            {**_s(scoped), "ids": ids},
        )
        .mappings()
        .all()
    )
    found = {r["id"]: dict(r) for r in rows}
    if len(found) != len(set(ids)):
        raise _not_found("패킹 단위")
    return found


def create_unit(context: AuthContext, kind: str, key: str):
    def run(connection, scoped):
        prefix = "BX-" if kind == "BOX" else "PL-"
        number = _next_code(
            connection, scoped, "mes.packing_unit", "packing_no", prefix
        )
        unit_id = connection.execute(
            text(
                "INSERT INTO mes.packing_unit (workspace_id, generation_id, packing_no, packing_kind) "
                "VALUES (:w, :g, :no, :kind) RETURNING id"
            ),
            {**_s(scoped), "no": number, "kind": kind},
        ).scalar_one()
        return _units(connection, scoped, unit_id)[0], "packing_unit", unit_id

    return _action(context, "mes.packing_unit.create", key, {"kind": kind}, run, 201)


def delete_unit(context: AuthContext, unit_id: int, key: str) -> None:
    def run(connection, scoped):
        unit = _lock_units(connection, scoped, [unit_id])[unit_id]
        current = _units(connection, scoped, unit_id)[0]
        if unit["status"] != "open" or current["members"] or current["childIds"]:
            raise _conflict("비어 있는 열린 포장만 지울 수 있습니다.", "UNIT_NOT_EMPTY")
        connection.execute(
            text(f"DELETE FROM mes.packing_unit WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": unit_id},
        )
        return {}, "packing_unit", unit_id

    _action(context, "mes.packing_unit.delete", key, {"id": unit_id}, run, 204)


def set_member(context: AuthContext, box_id: int, lot_id: int, qty: str, key: str):
    """열린 BOX에 LOT 양품을 담거나(수량 0이면 뺀다) 수량을 바꾼다. LOT 합계 ≤ 최종 양품(M-G08)."""

    def run(connection, scoped):
        # 잠금: LOT 먼저(잔여 계산 근거 고정) → BOX
        connection.execute(
            text(f"SELECT 1 FROM mes.lot WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": lot_id},
        )
        box = _lock_units(connection, scoped, [box_id])[box_id]
        if box["packing_kind"] != "BOX":
            raise _conflict(
                "LOT은 BOX에만 담습니다. PALLET에는 닫힌 BOX를 묶습니다.", "NOT_A_BOX"
            )
        if box["status"] != "open":
            raise _conflict("닫힌 BOX의 내용은 바꿀 수 없습니다.", "UNIT_CLOSED")
        amount = Decimal(qty)
        current = _units(connection, scoped, box_id)[0]
        existing = next((m for m in current["members"] if m["lotId"] == lot_id), None)
        if amount == 0:
            if existing is None:
                raise _not_found("BOX 구성")
            connection.execute(
                text(f"DELETE FROM mes.packing_member WHERE {_S} AND id=:id"),
                {**_s(scoped), "id": existing["id"]},
            )
            return _units(connection, scoped, box_id)[0], "packing_unit", box_id
        lot_row = (
            connection.execute(
                text(LOT_GOOD_SQL + " AND t.id=:id"), {**_s(scoped), "id": lot_id}
            )
            .mappings()
            .first()
        )
        if lot_row is None:
            raise _field(
                "lotId", "최종 공정까지 정상 완료된 LOT만 담습니다(전량 불량 LOT 제외)."
            )
        lot = _lot_row(lot_row)
        if lot["unit"] == "EA" and amount != amount.to_integral_value():
            raise _field("packedQty", "EA 수량은 정수입니다.")
        others = [m for m in current["members"] if m["lotId"] != lot_id]
        if others and (others[0]["itemId"], others[0]["unit"]) != (
            lot["itemId"],
            lot["unit"],
        ):
            raise _conflict("한 BOX에는 같은 품목·단위만 담습니다.", "MIXED_ITEM")
        # 이 BOX의 기존 수량을 빼고 다시 합산한다
        packed_elsewhere = Decimal(lot["packedQty"]) - (
            Decimal(existing["packedQty"]) if existing else 0
        )
        available = Decimal(lot["finalGoodQty"]) - packed_elsewhere
        if amount > available:
            raise _conflict(
                f"LOT {lot['lotNo']}의 담을 수 있는 양품은 {available.normalize():f}입니다.",
                "EXCEEDS_GOOD_QTY",
                availableQty=str(available),
            )
        if existing:
            connection.execute(
                text(
                    f"UPDATE mes.packing_member SET packed_qty=:q WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "q": amount, "id": existing["id"]},
            )
        else:
            connection.execute(
                text(
                    "INSERT INTO mes.packing_member (workspace_id, generation_id, packing_unit_id, "
                    "lot_id, packed_qty) VALUES (:w, :g, :box, :lot, :q)"
                ),
                {**_s(scoped), "box": box_id, "lot": lot_id, "q": amount},
            )
        return _units(connection, scoped, box_id)[0], "packing_unit", box_id

    return _action(
        context,
        "mes.packing_member.set",
        key,
        {"box": box_id, "lot": lot_id, "qty": qty},
        run,
    )


def close_unit(context: AuthContext, unit_id: int, key: str):
    def run(connection, scoped):
        unit = _lock_units(connection, scoped, [unit_id])[unit_id]
        if unit["status"] != "open":
            raise _conflict("열린 포장만 닫을 수 있습니다.", "UNIT_CLOSED")
        current = _units(connection, scoped, unit_id)[0]
        if unit["packing_kind"] == "BOX" and not current["members"]:
            raise _conflict("빈 BOX는 닫을 수 없습니다.", "UNIT_EMPTY")
        if unit["packing_kind"] == "PALLET":
            if not current["childIds"]:
                raise _conflict("빈 PALLET은 닫을 수 없습니다.", "UNIT_EMPTY")
            boxes = _lock_units(connection, scoped, current["childIds"])
            if any(b["status"] != "closed" for b in boxes.values()):
                raise _conflict("모든 BOX가 닫혀야 PALLET을 닫습니다.", "BOX_OPEN")
        connection.execute(
            text(f"UPDATE mes.packing_unit SET status='closed' WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": unit_id},
        )
        return _units(connection, scoped, unit_id)[0], "packing_unit", unit_id

    return _action(context, "mes.packing_unit.close", key, {"id": unit_id}, run)


def set_parent(context: AuthContext, box_id: int, pallet_id: int | None, key: str):
    """닫힌 BOX를 열린 PALLET에 묶거나(pallet_id) 푼다(None). 이전·새 PALLET을 모두 잠근다."""

    def run(connection, scoped):
        box_row = connection.execute(
            text(
                f"SELECT parent_packing_unit_id FROM mes.packing_unit WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": box_id},
        ).first()
        if box_row is None:
            raise _not_found("패킹 단위")
        old = box_row.parent_packing_unit_id
        locked = _lock_units(
            connection, scoped, [i for i in {box_id, old, pallet_id} if i is not None]
        )
        box = locked[box_id]
        if box["packing_kind"] != "BOX" or box["status"] != "closed":
            raise _conflict("닫힌 BOX만 PALLET에 묶거나 풉니다.", "BOX_NOT_CLOSED")
        if box["parent_packing_unit_id"] != old:
            raise _conflict("다른 요청이 BOX를 옮겼습니다. 다시 시도하세요.", "CHANGED")
        if old is not None and locked[old]["status"] != "open":
            raise _conflict("닫힌 PALLET의 구성은 바꿀 수 없습니다.", "UNIT_CLOSED")
        if pallet_id is not None:
            pallet = locked[pallet_id]
            if pallet["packing_kind"] != "PALLET":
                raise _field("parentPackingUnitId", "BOX의 상위는 PALLET만 됩니다.")
            if pallet["status"] != "open":
                raise _conflict("닫힌 PALLET의 구성은 바꿀 수 없습니다.", "UNIT_CLOSED")
            target = _units(connection, scoped, pallet_id)[0]
            mine = _units(connection, scoped, box_id)[0]
            if target["itemId"] is not None and (target["itemId"], target["unit"]) != (
                mine["itemId"],
                mine["unit"],
            ):
                raise _conflict(
                    "한 PALLET에는 같은 품목·단위 BOX만 묶습니다.", "MIXED_ITEM"
                )
        connection.execute(
            text(
                f"UPDATE mes.packing_unit SET parent_packing_unit_id=:p WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "p": pallet_id, "id": box_id},
        )
        return _units(connection, scoped, box_id)[0], "packing_unit", box_id

    return _action(
        context,
        "mes.packing_unit.parent",
        key,
        {"box": box_id, "pallet": pallet_id},
        run,
    )


def receive(context: AuthContext, pallet_id: int, key: str):
    """TX-11 완제품 입고: 닫힌 PALLET(하위 BOX 모두 closed)만. PALLET closed → received."""

    def run(connection, scoped):
        pallet = _lock_units(connection, scoped, [pallet_id])[pallet_id]
        if pallet["packing_kind"] != "PALLET":
            raise _conflict("입고는 PALLET 단위로만 합니다.", "NOT_A_PALLET")
        if pallet["status"] != "closed":
            reason = (
                "ALREADY_RECEIVED"
                if pallet["status"] in ("received", "shipped")
                else "UNIT_OPEN"
            )
            raise _conflict("닫힌 PALLET만 입고할 수 있습니다(재입고 불가).", reason)
        current = _units(connection, scoped, pallet_id)[0]
        boxes = _lock_units(connection, scoped, current["childIds"])
        if not boxes or any(b["status"] != "closed" for b in boxes.values()):
            raise _conflict("모든 BOX가 닫혀야 입고합니다.", "BOX_OPEN")
        connection.execute(
            text(
                "INSERT INTO mes.finished_goods_receipt (workspace_id, generation_id, "
                "packing_unit_id, received_at) VALUES (:w, :g, :p, clock_timestamp())"
            ),
            {**_s(scoped), "p": pallet_id},
        )
        connection.execute(
            text(
                f"UPDATE mes.packing_unit SET status='received' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": pallet_id},
        )
        return (
            _units(connection, scoped, pallet_id)[0],
            "finished_goods_receipt",
            pallet_id,
        )

    return _action(
        context, "mes.finished_goods_receipt.create", key, {"id": pallet_id}, run, 201
    )
