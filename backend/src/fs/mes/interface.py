"""MES 읽기 전용 조회 인터페이스 (FS-023 D9 · X1~X6).

다른 솔루션(QMS·WMS·SPC·CMMS)은 MES를 이 모듈로만 읽는다. 반환은 값(dict/list)이며 행을 잠그지 않는다.
MES를 꺼 두었으면 None을 돌려주고, 호출 쪽은 직접 입력으로 줄여 동작한다(D12).
호출자의 범위(scoped: 활성 세대가 확정된 AuthContext)로만 조회한다 — 다른 공간·세대는 보이지 않는다.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext
from fs.common.scope import module_available

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
    return module_available(connection, scoped.workspace_id, "mes")


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


def equipment(
    connection: Connection, scoped: AuthContext
) -> list[dict[str, Any]] | None:
    """사용 중인 설비 `[{equipmentCode, name, equipmentType, locationCode}]`. MES가 꺼져 있으면 None.

    CMMS가 설비 대장으로 가져온다(FS-029 D46). 코드만 스냅샷으로 넘기고 FK는 걸지 않는다.
    """
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT e.equipment_code, e.name, e.equipment_type, l.location_code "
            "FROM mes.equipment e "
            "LEFT JOIN mes.location l ON l.workspace_id=e.workspace_id "
            " AND l.generation_id=e.generation_id AND l.id=e.location_id "
            "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.is_active "
            "ORDER BY e.equipment_code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "equipmentCode": row["equipment_code"],
            "name": row["name"],
            "equipmentType": row["equipment_type"],
            "locationCode": row["location_code"],
        }
        for row in rows
    ]


def molds(connection: Connection, scoped: AuthContext) -> list[dict[str, Any]] | None:
    """폐기하지 않은 금형 `[{moldCode, name, cavity, lifeShots, shots, status}]`. MES가 꺼져 있으면 None.

    CMMS가 대장(종류 MOLD)으로 가져오고 타수 기준 PM에 쓴다(DSN-21 Q1·Q2).
    shots는 지금까지 누적 타수다 — 타수 주기 PM의 '현재 사용량'이 된다.
    """
    if not _enabled(connection, scoped):
        return None
    rows = connection.execute(
        text(
            "SELECT m.code, m.name, m.cavity, m.life_shots, m.status, "
            " COALESCE((SELECT sum(u.shots) FROM mes.mold_usage u "
            "   WHERE u.workspace_id=m.workspace_id AND u.generation_id=m.generation_id "
            "     AND u.mold_id=m.id), 0) shots "
            "FROM mes.mold m WHERE m.workspace_id=:w AND m.generation_id=:g "
            "  AND m.status <> 'RETIRED' ORDER BY m.code"
        ),
        {"w": scoped.workspace_id, "g": scoped.generation_id},
    ).mappings()
    return [
        {
            "moldCode": row["code"],
            "name": row["name"],
            "cavity": row["cavity"],
            "lifeShots": str(row["life_shots"]),
            "shots": str(row["shots"]),
            "status": row["status"],
        }
        for row in rows
    ]


def _month_bounds(month: str) -> tuple[datetime, datetime]:
    """'YYYY-MM' → [그 달 1일 00:00, 다음 달 1일 00:00) 한국 시간."""
    year, mon = int(month[:4]), int(month[5:7])
    seoul = ZoneInfo("Asia/Seoul")
    start = datetime(year, mon, 1, tzinfo=seoul)
    end = datetime(year + (mon == 12), mon % 12 + 1, 1, tzinfo=seoul)
    return start, end


# 확정 공정 실적 중 불량이 난 건. 불량 코드(operation_defect)는 있으면 붙이고 없으면 사유 문자열만 남는다.
_DEFECTS = """
SELECT t.lot_no, i.item_code, i.name item_name, pr.process_code, eq.equipment_code,
       r.confirmed_at, r.input_qty, r.good_qty, r.defect_qty, r.unit, r.defect_reason,
       d.qty code_qty, d.disposition, c.code defect_code, c.name defect_name, c.category
FROM mes.operation_result r
JOIN mes.operation_execution e ON e.workspace_id=r.workspace_id
 AND e.generation_id=r.generation_id AND e.id=r.execution_id
JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
 AND s.id=e.route_step_id
JOIN mes.process pr ON pr.workspace_id=s.workspace_id AND pr.generation_id=s.generation_id
 AND pr.id=s.process_id
LEFT JOIN mes.equipment eq ON eq.workspace_id=e.workspace_id AND eq.generation_id=e.generation_id
 AND eq.id=e.equipment_id
LEFT JOIN mes.operation_defect d ON d.workspace_id=r.workspace_id
 AND d.generation_id=r.generation_id AND d.operation_result_id=r.id
LEFT JOIN mes.defect_code c ON c.workspace_id=d.workspace_id AND c.generation_id=d.generation_id
 AND c.id=d.defect_code_id
WHERE r.workspace_id=:w AND r.generation_id=:g AND r.defect_qty > 0
  AND r.confirmed_at >= :start AND r.confirmed_at < :end
ORDER BY r.confirmed_at, t.lot_no, pr.process_code, c.code
"""


def defects(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 확정된 공정 불량 `[{lotNo, itemCode, processCode, defectQty, codes:[...]}]`. MES 꺼짐이면 None.

    QMS가 파레토·PPM을 내는 원천이다(DSN-14 F34). 불량 코드는 `mes.operation_defect`가 있을 때만
    채워진다 — 코드 없이 사유만 적은 실적은 `codes`가 빈 목록이고 `reason`으로 본다.
    """
    if not _enabled(connection, scoped):
        return None
    start, end = _month_bounds(month)
    rows = connection.execute(
        text(_DEFECTS),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "start": start,
            "end": end,
        },
    ).mappings()
    out: dict[Any, dict[str, Any]] = {}
    for r in rows:
        entry = out.setdefault(
            (r["lot_no"], r["process_code"], r["confirmed_at"]),
            {
                "lotNo": r["lot_no"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "processCode": r["process_code"],
                "equipmentCode": r["equipment_code"],
                "confirmedAt": r["confirmed_at"].isoformat(),
                "inputQty": str(r["input_qty"]),
                "goodQty": str(r["good_qty"]),
                "defectQty": str(r["defect_qty"]),
                "unit": r["unit"],
                "reason": r["defect_reason"],
                "codes": [],
            },
        )
        if r["defect_code"] is not None:
            entry["codes"].append(
                {
                    "defectCode": r["defect_code"],
                    "defectName": r["defect_name"],
                    "category": r["category"],
                    "qty": str(r["code_qty"]),
                    "disposition": r["disposition"],
                }
            )
    return list(out.values())


_PRODUCTION = """
SELECT eq.equipment_code, eq.name equipment_name, i.item_code, i.name item_name, r.unit,
       sum(r.good_qty) good_qty, count(*) result_count,
       min(r.confirmed_at) first_confirmed_at, max(r.confirmed_at) last_confirmed_at
FROM mes.operation_result r
JOIN mes.operation_execution e ON e.workspace_id=r.workspace_id
 AND e.generation_id=r.generation_id AND e.id=r.execution_id
JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
LEFT JOIN mes.equipment eq ON eq.workspace_id=e.workspace_id AND eq.generation_id=e.generation_id
 AND eq.id=e.equipment_id
WHERE r.workspace_id=:w AND r.generation_id=:g
  AND r.confirmed_at >= :start AND r.confirmed_at < :end
GROUP BY eq.equipment_code, eq.name, i.item_code, i.name, r.unit
ORDER BY eq.equipment_code NULLS LAST, i.item_code
"""


def production_results(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 확정 실적의 **설비·품목별 양품 수량**. MES 꺼짐이면 None.

    FEMS 원단위의 분모다(DSN-15 F51·Q3). 에너지를 설비별로 배분하므로 생산량도 설비별이다.

    **합계를 품목 총생산으로 보면 안 된다.** 한 LOT이 사출 → 조립 → 검사를 거치면 공정마다
    행이 하나씩 나온다. 설비별로 나눠 쓸 때만 맞는 값이다.

    수량은 `good_qty`(양품)다 — 원단위 분모는 쓸 수 있게 만든 양이지 투입량이 아니다.
    **설비가 없는 실적은 `equipmentCode`가 None**이고, FEMS 생산량은 설비별이라 가져올 수 없다.
    """
    if not _enabled(connection, scoped):
        return None
    start, end = _month_bounds(month)
    rows = connection.execute(
        text(_PRODUCTION),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "start": start,
            "end": end,
        },
    ).mappings()
    return [
        {
            "equipmentCode": r["equipment_code"],
            "equipmentName": r["equipment_name"],
            "itemCode": r["item_code"],
            "itemName": r["item_name"],
            "unit": r["unit"],
            "goodQty": str(r["good_qty"]),
            "resultCount": r["result_count"],
            "firstConfirmedAt": r["first_confirmed_at"].isoformat(),
            "lastConfirmedAt": r["last_confirmed_at"].isoformat(),
        }
        for r in rows
    ]


def process_inspections(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 확정된 공정 검사 `[{lotNo, itemCode, processCode, timing, result, failCount}]`. MES 꺼짐이면 None.

    draft는 빼고 확정본만 돌려준다 — QMS 집계는 번복되지 않는 값만 쓴다.
    """
    if not _enabled(connection, scoped):
        return None
    start, end = _month_bounds(month)
    rows = connection.execute(
        text(
            "SELECT t.lot_no, i.item_code, pr.process_code, p.timing, p.inspected_at, p.result, "
            " (SELECT count(*) FROM mes.process_inspection_value v "
            "   WHERE v.workspace_id=p.workspace_id AND v.generation_id=p.generation_id "
            "     AND v.process_inspection_id=p.id AND v.judgement='FAIL') fail_count "
            "FROM mes.process_inspection p "
            "JOIN mes.operation_execution e ON e.workspace_id=p.workspace_id "
            " AND e.generation_id=p.generation_id AND e.id=p.execution_id "
            "JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id "
            " AND t.id=e.lot_id "
            "JOIN mes.work_order o ON o.workspace_id=t.workspace_id "
            " AND o.generation_id=t.generation_id AND o.id=t.work_order_id "
            "JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id "
            " AND i.id=o.item_id "
            "JOIN mes.route_step s ON s.workspace_id=e.workspace_id "
            " AND s.generation_id=e.generation_id AND s.id=e.route_step_id "
            "JOIN mes.process pr ON pr.workspace_id=s.workspace_id "
            " AND pr.generation_id=s.generation_id AND pr.id=s.process_id "
            "WHERE p.workspace_id=:w AND p.generation_id=:g AND p.status='confirmed' "
            "  AND p.inspected_at >= :start AND p.inspected_at < :end "
            "ORDER BY p.inspected_at, t.lot_no, pr.process_code"
        ),
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
            "timing": r["timing"],
            "inspectedAt": r["inspected_at"].isoformat(),
            "result": r["result"],
            "failCount": r["fail_count"],
        }
        for r in rows
    ]


_KIN = """
SELECT g.relation, g.qty, g.unit, g.related_at, t.lot_no, i.item_code, i.name item_name
FROM mes.lot_genealogy g
JOIN mes.lot t ON t.workspace_id=g.workspace_id AND t.generation_id=g.generation_id
 AND t.id = g.{other}_lot_id
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id
WHERE g.workspace_id=:w AND g.generation_id=:g AND g.{side}_lot_id=:lot
ORDER BY g.related_at, t.lot_no
"""


def _kin(connection: Connection, scoped: AuthContext, lot_id: int, side: str) -> Any:
    other = "parent" if side == "child" else "child"
    rows = connection.execute(
        text(_KIN.format(side=side, other=other)),
        {"w": scoped.workspace_id, "g": scoped.generation_id, "lot": lot_id},
    ).mappings()
    return [
        {
            "lotNo": r["lot_no"],
            "itemCode": r["item_code"],
            "itemName": r["item_name"],
            "relation": r["relation"],
            "qty": str(r["qty"]),
            "unit": r["unit"],
            "relatedAt": r["related_at"].isoformat(),
        }
        for r in rows
    ]


def lot_trace(
    connection: Connection, scoped: AuthContext, lot_no: str
) -> dict[str, Any] | None:
    """LOT 계보 역추적. MES가 꺼져 있거나 없는 LOT이면 None — 구분은 enabled()로 한다.

    `{lotNo, itemCode, orderNo, materials, parents, children, usedIn}`.
    QMS 클레임이 LOT에서 원자재·설비까지 거슬러 갈 때 쓴다(DSN-14 F43).
    자재 LOT은 MES 반제품이면 `lotNo`, WMS 원자재면 `lotNo`에 코드 문자열이 들어간다.
    """
    if not _enabled(connection, scoped):
        return None
    head = (
        connection.execute(
            text(
                "SELECT t.id, t.lot_no, t.status, t.completion_reason, t.unit, t.created_at, "
                " o.order_no, i.item_code, i.name item_name "
                "FROM mes.lot t "
                "JOIN mes.work_order o ON o.workspace_id=t.workspace_id "
                " AND o.generation_id=t.generation_id AND o.id=t.work_order_id "
                "JOIN mes.item i ON i.workspace_id=o.workspace_id "
                " AND i.generation_id=o.generation_id AND i.id=o.item_id "
                "WHERE t.workspace_id=:w AND t.generation_id=:g AND t.lot_no=:lot"
            ),
            {"w": scoped.workspace_id, "g": scoped.generation_id, "lot": lot_no},
        )
        .mappings()
        .first()
    )
    if head is None:
        return None
    params = {"w": scoped.workspace_id, "g": scoped.generation_id, "lot": head["id"]}
    materials = connection.execute(
        text(
            "SELECT i.item_code, i.name item_name, mi.issued_qty, mi.unit, mi.issued_at, "
            " pr.process_code, COALESCE(ml.lot_no, mi.material_lot_no) lot_no "
            "FROM mes.material_issue mi "
            "JOIN mes.operation_execution e ON e.workspace_id=mi.workspace_id "
            " AND e.generation_id=mi.generation_id AND e.id=mi.execution_id "
            "JOIN mes.item i ON i.workspace_id=mi.workspace_id "
            " AND i.generation_id=mi.generation_id AND i.id=mi.material_item_id "
            "JOIN mes.route_step s ON s.workspace_id=e.workspace_id "
            " AND s.generation_id=e.generation_id AND s.id=e.route_step_id "
            "JOIN mes.process pr ON pr.workspace_id=s.workspace_id "
            " AND pr.generation_id=s.generation_id AND pr.id=s.process_id "
            "LEFT JOIN mes.lot ml ON ml.workspace_id=mi.workspace_id "
            " AND ml.generation_id=mi.generation_id AND ml.id=mi.material_lot_id "
            "WHERE mi.workspace_id=:w AND mi.generation_id=:g AND e.lot_id=:lot "
            "ORDER BY mi.issued_at, i.item_code"
        ),
        params,
    ).mappings()
    used_in = connection.execute(
        text(
            "SELECT t.lot_no, i.item_code, i.name item_name, mi.issued_qty, mi.unit, mi.issued_at "
            "FROM mes.material_issue mi "
            "JOIN mes.operation_execution e ON e.workspace_id=mi.workspace_id "
            " AND e.generation_id=mi.generation_id AND e.id=mi.execution_id "
            "JOIN mes.lot t ON t.workspace_id=e.workspace_id "
            " AND t.generation_id=e.generation_id AND t.id=e.lot_id "
            "JOIN mes.work_order o ON o.workspace_id=t.workspace_id "
            " AND o.generation_id=t.generation_id AND o.id=t.work_order_id "
            "JOIN mes.item i ON i.workspace_id=o.workspace_id "
            " AND i.generation_id=o.generation_id AND i.id=o.item_id "
            "WHERE mi.workspace_id=:w AND mi.generation_id=:g AND mi.material_lot_id=:lot "
            "ORDER BY mi.issued_at, t.lot_no"
        ),
        params,
    ).mappings()
    return {
        "lotNo": head["lot_no"],
        "itemCode": head["item_code"],
        "itemName": head["item_name"],
        "orderNo": head["order_no"],
        "status": head["status"],
        "completionReason": head["completion_reason"],
        "unit": head["unit"],
        "createdAt": head["created_at"].isoformat(),
        "materials": [
            {
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "lotNo": r["lot_no"],
                "qty": str(r["issued_qty"]),
                "unit": r["unit"],
                "processCode": r["process_code"],
                "issuedAt": r["issued_at"].isoformat(),
            }
            for r in materials
        ],
        "parents": _kin(connection, scoped, head["id"], "child"),
        "children": _kin(connection, scoped, head["id"], "parent"),
        "usedIn": [
            {
                "lotNo": r["lot_no"],
                "itemCode": r["item_code"],
                "itemName": r["item_name"],
                "qty": str(r["issued_qty"]),
                "unit": r["unit"],
                "issuedAt": r["issued_at"].isoformat(),
            }
            for r in used_in
        ],
    }


def subcontract_results(
    connection: Connection, scoped: AuthContext, month: str
) -> list[dict[str, Any]] | None:
    """그 달 **받은** 외주 실적 `[{scNo, subcontractorCode, itemCode, processCode, goodQty, defectQty, unit, receivedAt}]`.

    ERP 외주비 매입(DSN-11 F34)이 읽는다. 외주 발주·입고는 MES가 가지고 ERP는 매입·전표만 만든다.
    **받은 것만** 준다 — 보낸 뒤 아직 받지 않은 건은 치를 금액이 정해지지 않았다.
    수량은 `good_qty`(양품)다. 불량은 함께 주되 금액 산정은 읽는 쪽이 정한다. MES 꺼짐이면 None.
    """
    if not _enabled(connection, scoped):
        return None
    start, end = _month_bounds(month)
    rows = connection.execute(
        text(
            "SELECT o.sc_no, o.subcontractor_code, o.qty, o.good_qty, o.defect_qty, o.unit, "
            "       o.received_at, i.item_code, i.name item_name, p.process_code "
            "FROM mes.subcontract_order o "
            "JOIN mes.lot t ON t.workspace_id=o.workspace_id AND t.generation_id=o.generation_id "
            " AND t.id=o.lot_id "
            "JOIN mes.work_order wo ON wo.workspace_id=t.workspace_id "
            " AND wo.generation_id=t.generation_id AND wo.id=t.work_order_id "
            "JOIN mes.item i ON i.workspace_id=wo.workspace_id AND i.generation_id=wo.generation_id "
            " AND i.id=wo.item_id "
            "LEFT JOIN mes.route_step s ON s.workspace_id=o.workspace_id "
            " AND s.generation_id=o.generation_id AND s.id=o.route_step_id "
            "LEFT JOIN mes.process p ON p.workspace_id=s.workspace_id "
            " AND p.generation_id=s.generation_id AND p.id=s.process_id "
            "WHERE o.workspace_id=:w AND o.generation_id=:g AND o.received_at IS NOT NULL "
            "  AND o.received_at >= :start AND o.received_at < :end "
            "ORDER BY o.received_at, o.sc_no"
        ),
        {
            "w": scoped.workspace_id,
            "g": scoped.generation_id,
            "start": start,
            "end": end,
        },
    ).mappings()
    return [
        {
            "scNo": r["sc_no"],
            "subcontractorCode": r["subcontractor_code"],
            "itemCode": r["item_code"],
            "itemName": r["item_name"],
            "processCode": r["process_code"],
            "qty": str(r["qty"]),
            "goodQty": str(r["good_qty"]),
            "defectQty": str(r["defect_qty"]),
            "unit": r["unit"],
            "receivedAt": r["received_at"].isoformat(),
        }
        for r in rows
    ]
