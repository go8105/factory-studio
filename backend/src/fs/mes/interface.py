"""MES 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6).

다른 솔루션(QMS)은 MES를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
MES를 꺼 두었으면 None을 돌려주고, 호출 쪽은 직접 입력으로 줄여 동작한다(D12).
호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다 — 다른 공간·세대는 보이지 않는다.
"""

from __future__ import annotations

from typing import Any

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


def items(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]] | None:
    """사용 중인 완제품 품목(검사 기준 대상). MES가 꺼져 있으면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT item_code, name, base_unit FROM mes.item "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active AND item_type='finished' "
            "ORDER BY item_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {"itemCode": r["item_code"], "name": r["name"], "baseUnit": r["base_unit"]}
        for r in rows
    ]
