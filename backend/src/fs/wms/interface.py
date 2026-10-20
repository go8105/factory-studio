"""WMS 읽기 전용 조회 인터페이스 (FS-013 §6 · DSN-21 Q6).

CMMS가 WMS를 이 모듈로만 읽어 예비품 재고를 본다. **재고 원장은 WMS만 가진다**(FS-029 D50) —
CMMS는 수량을 저장하지 않고 볼 때마다 여기서 읽는다.
WMS를 꺼 두었으면 None을 돌려주고, CMMS는 재고 칸 없이 동작한다.

호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """WMS 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "wms")


def stock_on_hand(
    connection: Connection, scoped: AuthContext, item_codes: list[str]
) -> dict[str, dict[str, Any]] | None:
    """품목 코드별 재고 `{itemCode: {qtyOnHand, unit, safetyStock, isShort}}`. WMS가 꺼져 있으면 None.

    재고는 `wms.stock_move`의 합이다(CMMS는 저장하지 않는다). 안전 재고가 설정된 품목만
    부족 여부를 가린다 — 기준이 없으면 '부족'이라고 말할 수 없다.

    목록에 없는(WMS에 등록되지 않은) 코드는 결과에서 빠진다. 호출 쪽이 '연결 안 됨'으로 다룬다.
    """
    if not enabled(connection, scoped):
        return None
    if not item_codes:
        return {}
    rows = connection.execute(
        text(
            "SELECT i.item_code, i.base_unit, i.safety_stock, "
            " COALESCE((SELECT sum(m.qty_delta) FROM wms.stock_move m "
            "   WHERE m.workspace_id=i.workspace_id AND m.generation_id=i.generation_id "
            "     AND m.item_id=i.id), 0) qty_on_hand "
            "FROM wms.item i WHERE i.workspace_id=:w AND i.generation_id=:g "
            "  AND i.item_code = ANY(:codes)"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "codes": list(item_codes),
        },
    ).mappings()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        on_hand = Decimal(str(row["qty_on_hand"]))
        safety = row["safety_stock"]
        out[row["item_code"]] = {
            "qtyOnHand": f"{on_hand:.3f}",
            "unit": row["base_unit"],
            "safetyStock": None if safety is None else f"{Decimal(str(safety)):.3f}",
            "isShort": safety is not None and on_hand < Decimal(str(safety)),
        }
    return out


def supply_items(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """소모품(SUPPLY) 품목 `[{itemCode, name, baseUnit, safetyStock}]`. WMS가 꺼져 있으면 None.

    CMMS 예비품을 WMS 품목에 이어 붙일 때 고르는 목록이다(DSN-21 Q6).
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT item_code, name, base_unit, safety_stock FROM wms.item "
            "WHERE workspace_id=:w AND generation_id=:g AND item_class='SUPPLY' AND is_active "
            "ORDER BY item_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "itemCode": row["item_code"],
            "name": row["name"],
            "baseUnit": row["base_unit"],
            "safetyStock": None
            if row["safety_stock"] is None
            else f"{Decimal(str(row['safety_stock'])):.3f}",
        }
        for row in rows
    ]
