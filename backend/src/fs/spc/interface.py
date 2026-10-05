"""SPC 읽기 전용 조회 인터페이스 (FS-028 D44 · FS-023 D9 X1~X6).

QMS는 SPC를 이 모듈로만 읽어 검사 대기·검사 목록의 LOT 옆에 "SPC 이상" 배지를 표시한다.
배지는 판정·보류를 막거나 바꾸지 않는다. SPC를 꺼 두었으면 None을 돌려주고, QMS는 배지 없이 동작한다.
"""

from __future__ import annotations

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
