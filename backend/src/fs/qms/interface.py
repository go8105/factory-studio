"""QMS 읽기 전용 조회 인터페이스 (FS-023 D9·D10 · X1~X6).

MES는 QMS를 이 모듈로만 읽어 LOT 옆에 "QMS 보류" 배지·품질 판정을 표시한다. 보류는 MES 패킹을 막지 않는다.
QMS를 꺼 두었으면 None을 돌려주고, MES는 배지 없이 그대로 동작한다(D12).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.scope import module_available


def _enabled(connection: Connection, scoped: AuthContext) -> bool:
    return module_available(connection, scoped.workspace_id, "qms")


def is_enabled(connection: Connection, scoped: AuthContext) -> bool:
    """QMS 솔루션 활성화 여부."""
    return _enabled(connection, scoped)


def held_lot_nos(connection: Connection, scoped: AuthContext) -> set[str] | None:
    """활성 보류 중인 LOT 번호. QMS가 꺼져 있으면 None."""
    if not _enabled(connection, scoped):
        return None
    return set(
        connection.execute(
            text(
                "SELECT lot_no FROM qms.quality_hold "
                "WHERE workspace_id=:w AND generation_id=:g AND status='held'"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id},
        ).scalars()
    )


def active_hold_details(
    connection: Connection, scoped: AuthContext, lot_no: str
) -> dict[str, Any] | None:
    """특정 LOT의 활성 QMS 보류 상세. QMS가 꺼져 있으면 None, 보류가 없으면 {'active': False}."""
    if not _enabled(connection, scoped):
        return None
    row = (
        connection.execute(
            text(
                "SELECT hold_no, held_at, item_code FROM qms.quality_hold "
                "WHERE workspace_id=:w AND generation_id=:g AND status='held' AND lot_no=:lot_no "
                "ORDER BY held_at DESC, id DESC LIMIT 1"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "lot_no": lot_no},
        )
        .mappings()
        .first()
    )
    if not row:
        return {"active": False, "holdNo": None, "heldAt": None}
    return {
        "active": True,
        "holdNo": row["hold_no"],
        "heldAt": (
            row["held_at"].isoformat()
            if hasattr(row["held_at"], "isoformat")
            else str(row["held_at"])
        ),
        "itemCode": row["item_code"],
    }


def latest_results(
    connection: Connection, scoped: AuthContext, lot_nos: list[str]
) -> dict[str, str] | None:
    """LOT별 마지막 확정 검사 판정(PASS/FAIL). 검사가 없으면 키가 없다. QMS가 꺼져 있으면 None."""
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT DISTINCT ON (lot_no) lot_no, result FROM qms.inspection "
            "WHERE workspace_id=:w AND generation_id=:g AND status='confirmed' AND lot_no = ANY(:lots) "
            "ORDER BY lot_no, confirmed_at DESC, id DESC"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "lots": lot_nos},
    ).mappings()
    return {r["lot_no"]: r["result"] for r in rows}


def gauges(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]] | None:
    """폐기하지 않은 계측기 `[{code, name, gaugeKind, status, nextDueOn, isOverdue}]`. QMS 꺼짐이면 None.

    SPC가 측정에 쓴 계측기를 고를 때 읽는다(DSN-14 F61). 교정 도래는 저장하지 않고
    마지막 교정의 다음 기한에서 파생한다 — 기한이 지났으면 경고일 뿐 차단하지 않는다.
    """
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT g.code, g.name, g.gauge_kind, g.status, "
            " (SELECT c.next_due_on FROM qms.calibration c "
            "   WHERE c.workspace_id=g.workspace_id AND c.generation_id=g.generation_id "
            "     AND c.gauge_id=g.id ORDER BY c.calibrated_on DESC, c.id DESC LIMIT 1) next_due_on "
            "FROM qms.gauge g WHERE g.workspace_id=:w AND g.generation_id=:g "
            "  AND g.status <> 'RETIRED' ORDER BY g.code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    today = business_today()
    return [
        {
            "code": r["code"],
            "name": r["name"],
            "gaugeKind": r["gauge_kind"],
            "status": r["status"],
            "nextDueOn": None
            if r["next_due_on"] is None
            else r["next_due_on"].isoformat(),
            "isOverdue": r["next_due_on"] is not None and r["next_due_on"] < today,
        }
        for r in rows
    ]
