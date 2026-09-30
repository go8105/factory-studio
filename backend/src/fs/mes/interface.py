"""MES 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6).

다른 솔루션(QMS·WMS·SPC)은 MES를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
MES를 꺼 두었으면 None을 돌려주고, 호출 쪽은 직접 입력으로 줄여 동작한다(D12).
호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다 — 다른 공간·세대는 보이지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext

# 최종 양품 = 정상 완료 LOT의 마지막 공정 양품(M-08 패킹과 같은 기준). 전량 불량 종결 LOT은 빠진다.
_INSPECTABLE = """
SELECT t.lot_no, i.item_code, i.name item_name, t.unit, last.good_qty final_good_qty,
       last.confirmed_at completed_at
FROM mes.lot t
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
CROSS JOIN LATERAL (
  SELECT x.good_qty, x.confirmed_at FROM mes.operation_execution e
  JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
   AND s.id=e.route_step_id
  JOIN mes.operation_result x ON x.workspace_id=e.workspace_id AND x.generation_id=e.generation_id
   AND x.execution_id=e.id
  WHERE e.workspace_id=t.workspace_id AND e.generation_id=t.generation_id AND e.lot_id=t.id
  ORDER BY s.sequence_no DESC LIMIT 1
) last
WHERE t.workspace_id=:w AND t.generation_id=:g AND t.status='completed'
  AND t.completion_reason='normal' AND last.good_qty > 0
"""


def _enabled(connection: Connection, scoped: AuthContext) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT enabled FROM core.workspace_module WHERE workspace_id=:w AND module_key='mes'"
            ),
            {"w": scoped.workspace_id},
        ).scalar()
    )


def _lot(row: Any) -> dict[str, Any]:
    return {
        "lotNo": row["lot_no"],
        "itemCode": row["item_code"],
        "itemName": row["item_name"],
        "finalGoodQty": str(row["final_good_qty"]),
        "unit": row["unit"],
        "completedAt": row["completed_at"].isoformat(),
    }


def inspectable_lots(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """검사할 수 있는 완료 LOT(최종 양품 > 0), 완료 시각 최신순. MES가 꺼져 있으면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(_INSPECTABLE + " ORDER BY last.confirmed_at DESC, t.lot_no DESC"),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [_lot(r) for r in rows]


def lot_snapshot(
    connection: Connection, scoped: AuthContext, lot_no: str
) -> dict[str, Any] | None:
    """LOT 1건의 스냅샷 값. MES가 꺼져 있거나 검사할 수 없는 LOT이면 None — 구분은 enabled()로 한다."""
    if not _enabled(connection, scoped):
        return None
    row = (
        connection.execute(
            text(_INSPECTABLE + " AND t.lot_no=:lot"),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "lot": lot_no},
        )
        .mappings()
        .first()
    )
    return None if row is None else _lot(row)


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """MES 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return _enabled(connection, scoped)


def items(
    connection: Connection, scoped: AuthContext, item_type: str | None = "finished"
) -> list[dict[str, Any]] | None:
    """사용 중인 품목. 기본은 완제품(QMS 검사 기준 대상), None이면 전 품목(WMS 가져오기). MES가 꺼져 있으면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT item_code, name, base_unit, item_type FROM mes.item "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active "
            "AND (CAST(:type AS text) IS NULL OR item_type=:type) ORDER BY item_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "type": item_type},
    ).mappings()
    return [
        {
            "itemCode": r["item_code"],
            "name": r["name"],
            "baseUnit": r["base_unit"],
            "itemType": r["item_type"],
        }
        for r in rows
    ]


# 확정 입고 팔레트 1건 = WMS 원천 1건(FS-024 7.1). 줄은 팔레트 아래 BOX에 담긴 LOT별 합계.
_RECEIPT_LINES = """
SELECT p.packing_no, r.received_at, t.lot_no, i.item_code, t.unit, sum(m.packed_qty) qty
FROM mes.finished_goods_receipt r
JOIN mes.packing_unit p ON p.workspace_id=r.workspace_id AND p.generation_id=r.generation_id
 AND p.id=r.packing_unit_id
JOIN mes.packing_unit b ON b.workspace_id=p.workspace_id AND b.generation_id=p.generation_id
 AND b.parent_packing_unit_id=p.id
JOIN mes.packing_member m ON m.workspace_id=b.workspace_id AND m.generation_id=b.generation_id
 AND m.packing_unit_id=b.id
JOIN mes.lot t ON t.workspace_id=m.workspace_id AND t.generation_id=m.generation_id AND t.id=m.lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.status='confirmed'
GROUP BY p.packing_no, r.received_at, t.lot_no, i.item_code, t.unit
ORDER BY r.received_at, p.packing_no, t.lot_no
"""

# 완료된 공정 실행 1건 = WMS 원천 1건. 실행 중에는 투입을 지울 수 있어 제외한다.
_ISSUE_LINES = """
SELECT t.lot_no, pr.process_code, e.ended_at, i.item_code, mi.unit, sum(mi.issued_qty) qty
FROM mes.operation_execution e
JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id
JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
 AND s.id=e.route_step_id
JOIN mes.process pr ON pr.workspace_id=s.workspace_id AND pr.generation_id=s.generation_id
 AND pr.id=s.process_id
JOIN mes.material_issue mi ON mi.workspace_id=e.workspace_id AND mi.generation_id=e.generation_id
 AND mi.execution_id=e.id
JOIN mes.item i ON i.workspace_id=mi.workspace_id AND i.generation_id=mi.generation_id
 AND i.id=mi.material_item_id
WHERE e.workspace_id=:w AND e.generation_id=:g AND e.status='completed'
GROUP BY t.lot_no, pr.process_code, e.ended_at, i.item_code, mi.unit
ORDER BY e.ended_at, t.lot_no, pr.process_code, i.item_code
"""


def _grouped(rows: Any, key: Any, head: Any) -> list[dict[str, Any]]:
    grouped: dict[Any, dict[str, Any]] = {}
    for r in rows:
        entry = grouped.setdefault(key(r), {**head(r), "lines": []})
        line = {"itemCode": r["item_code"], "qty": str(r["qty"]), "unit": r["unit"]}
        if "lot_no" in r and "packing_no" in r:
            line["lotNo"] = r["lot_no"]
        entry["lines"].append(line)
    return list(grouped.values())


def finished_goods_receipts(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """확정 완제품 입고(팔레트) `[{packingNo, receivedAt, lines:[{lotNo, itemCode, qty, unit}]}]`. MES 꺼짐이면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(_RECEIPT_LINES), {"w": scoped.workspace_id, "g": scoped.generation_id}
    ).mappings()
    return _grouped(
        rows,
        lambda r: r["packing_no"],
        lambda r: {
            "packingNo": r["packing_no"],
            "receivedAt": r["received_at"].isoformat(),
        },
    )


def completed_material_issues(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """완료된 공정 실행의 자재 투입 `[{sourceRef:'LT-0013:INJ', endedAt, lines:[{itemCode, qty, unit}]}]`. MES 꺼짐이면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(_ISSUE_LINES), {"w": scoped.workspace_id, "g": scoped.generation_id}
    ).mappings()
    return _grouped(
        rows,
        lambda r: (r["lot_no"], r["process_code"]),
        lambda r: {
            "sourceRef": f"{r['lot_no']}:{r['process_code']}",
            "endedAt": r["ended_at"].isoformat(),
        },
    )


# 시작된 공정 실행 1건 = SPC 부분군의 틀(FS-028 D39). 진행 중이면 ended_at이 NULL이다.
_RUNS = """
SELECT t.lot_no, i.item_code, pr.process_code, eq.equipment_code, e.started_at, e.ended_at
FROM mes.operation_execution e
JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
 AND s.id=e.route_step_id
JOIN mes.process pr ON pr.workspace_id=s.workspace_id AND pr.generation_id=s.generation_id
 AND pr.id=s.process_id
JOIN mes.equipment eq ON eq.workspace_id=e.workspace_id AND eq.generation_id=e.generation_id
 AND eq.id=e.equipment_id
WHERE e.workspace_id=:w AND e.generation_id=:g AND e.started_at IS NOT NULL
  AND e.started_at < :end AND (e.ended_at IS NULL OR e.ended_at >= :start)
ORDER BY e.started_at, t.lot_no, pr.process_code
"""


def operation_runs(
    connection: Connection, scoped: AuthContext, date_from: date, date_to: date
) -> list[dict[str, Any]] | None:
    """기간과 겹치는 시작된 공정 실행 `[{lotNo, itemCode, processCode, equipmentCode, startedAt, endedAt}]`.

    진행 중이면 endedAt=None. 기간은 [date_from 00:00, date_to+1 00:00) 한국 시간. MES 꺼짐이면 None.
    """
    if not _enabled(connection, scoped):
        return None
    seoul = ZoneInfo("Asia/Seoul")
    start = datetime.combine(date_from, time(), seoul)
    end = datetime.combine(date_to + timedelta(days=1), time(), seoul)
    rows = connection.execute(
        text(_RUNS),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "start": start,
            "end": end,
        },
    ).mappings()
    return [
        {
            "lotNo": r["lot_no"],
            "itemCode": r["item_code"],
            "processCode": r["process_code"],
            "equipmentCode": r["equipment_code"],
            "startedAt": r["started_at"].isoformat(),
            "endedAt": None if r["ended_at"] is None else r["ended_at"].isoformat(),
        }
        for r in rows
    ]
