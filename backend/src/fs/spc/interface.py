"""SPC 읽기 전용 조회 인터페이스 (FS-028 D44 · FS-023 D9 X1~X6 · DSN-17 Q4).

QMS는 SPC를 이 모듈로만 읽어 검사 대기·검사 목록의 LOT 옆에 "SPC 이상" 배지를 표시하고,
규격 이탈을 부적합 보고 후보로 가져간다. CMMS는 설비 원인 이상을 작업지시 전환 대기로 읽는다(FS-029 D48).
배지는 판정·보류를 막거나 바꾸지 않는다. SPC를 꺼 두었으면 None을 돌려주고, QMS는 배지 없이 동작한다.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available


def enabled(connection: Connection, scoped: AuthContext) -> bool:
    """SPC 사용 여부. None 반환이 '꺼짐'인지 '대상 없음'인지 구분할 때 쓴다."""
    return module_available(connection, scoped.workspace_id, "spc")


def open_signal_lot_nos(
    connection: Connection, scoped: AuthContext, lot_nos: list[str]
) -> set[str] | None:
    """미조치(open) 이상 기록이 있는 LOT 번호. SPC가 꺼져 있으면 None."""
    if not enabled(connection, scoped):
        return None
    if not lot_nos:
        return set()
    return set(
        connection.execute(
            text(
                "SELECT DISTINCT lot_no FROM spc.signal "
                "WHERE workspace_id=:w AND generation_id=:g AND status='open' AND lot_no = ANY(:lots)"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "lots": lot_nos},
        ).scalars()
    )


def spec_violations(
    connection: Connection, scoped: AuthContext, since: datetime
) -> list[dict[str, Any]] | None:
    """since 이후의 무효가 아닌 규격 이탈(LOT·특성·값·방향). SPC가 꺼져 있으면 None.

    QMS가 부적합 보고 후보로 읽는다(Q4). 보고 여부는 QMS가 정하고 SPC는 관여하지 않는다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT v.lot_no, c.code characteristic_code, c.name characteristic_name, c.item_code, "
            "c.process_code, c.unit, v.value, v.side, v.limit_value, v.detected_at "
            "FROM spc.spec_violation v JOIN spc.characteristic c "
            "ON c.workspace_id=v.workspace_id AND c.generation_id=v.generation_id AND c.id=v.characteristic_id "
            "WHERE v.workspace_id=:w AND v.generation_id=:g AND v.voided_at IS NULL AND v.detected_at>=:since "
            "ORDER BY v.detected_at DESC, v.id DESC"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "since": since},
    ).mappings()
    return [
        {
            "lotNo": row["lot_no"],
            "characteristicCode": row["characteristic_code"],
            "characteristicName": row["characteristic_name"],
            "itemCode": row["item_code"],
            "processCode": row["process_code"],
            "unit": row["unit"],
            "value": str(row["value"]),
            "side": row["side"],
            "limitValue": str(row["limit_value"]),
            "detectedAt": row["detected_at"].isoformat(),
        }
        for row in rows
    ]


def equipment_signals(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """조치하지 않은 **설비 원인** 이상. SPC가 꺼져 있으면 None.

    CMMS가 전환 대기 신호로 읽어 고장 작업지시를 만든다(FS-029 D48). 설비 코드는 부분군에 남은
    MES 스냅샷이다. 전환해도 SPC 쪽 상태는 바뀌지 않는다 — 조치 완료는 SPC에서 따로 한다.

    원인 분류가 아직 없는(미조치) 이상이므로 '설비 원인'은 규칙이 아니라 **설비가 특정되는가**로 가린다.
    """
    if not enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT x.id, s.equipment_code, x.lot_no, c.code characteristic_code, "
            "c.name characteristic_name, c.item_code, c.process_code, x.chart, x.rule, "
            "x.value, x.detected_at "
            "FROM spc.signal x "
            "JOIN spc.subgroup s ON s.workspace_id=x.workspace_id AND s.generation_id=x.generation_id "
            " AND s.id=x.subgroup_id "
            "JOIN spc.characteristic c ON c.workspace_id=x.workspace_id "
            " AND c.generation_id=x.generation_id AND c.id=x.characteristic_id "
            "WHERE x.workspace_id=:w AND x.generation_id=:g AND x.status='open' "
            "ORDER BY x.detected_at DESC, x.id DESC"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "signalId": str(row["id"]),
            "equipmentCode": row["equipment_code"],
            "lotNo": row["lot_no"],
            "characteristicCode": row["characteristic_code"],
            "characteristicName": row["characteristic_name"],
            "itemCode": row["item_code"],
            "processCode": row["process_code"],
            "chart": row["chart"],
            "rule": row["rule"],
            "value": str(row["value"]),
            "detectedAt": row["detected_at"].isoformat(),
        }
        for row in rows
    ]
