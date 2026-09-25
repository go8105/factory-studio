"""M-04 LOT 현황 · M-05 공정 실행 (FS-020d).

공정 시작(TX-01): 공간 → 작업지시 → LOT 잠금 뒤 경로 순서·선행 양품·허용 설비·설비 점유를 확인하고 실행을 만든다.
공정 완료(TX-02): 실적(양품·불량) 1건을 확정하면서 실행을 completed로 바꾸고, 마지막 공정이거나 양품이 0이면
LOT·작업지시를 함께 completed로 종결한다. 실적은 확정 후 수정하지 않는다(operation_result UPDATE/DELETE 금지).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from sqlalchemy import text

from fs.common.auth import AuthContext
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.mes import repository as repo
from fs.mes.service import MODULE, _action, _field, _not_found, _read

_S = "workspace_id=:w AND generation_id=:g"


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _conflict(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


LOT_SQL = """
SELECT t.id, t.lot_no, t.status, t.completion_reason, t.route_version_id, t.unit,
       o.id work_order_id, o.order_no, o.item_id, o.plan_qty, o.status order_status,
       o.bom_version_id, r.route_code, r.version route_version
FROM mes.lot t
JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id
 AND o.id=t.work_order_id
JOIN mes.route_version r ON r.workspace_id=t.workspace_id AND r.generation_id=t.generation_id
 AND r.id=t.route_version_id
WHERE t.workspace_id=:w AND t.generation_id=:g
"""
STEP_SQL = """
SELECT s.id route_step_id, s.route_version_id, s.sequence_no, s.process_id,
       e.id execution_id, e.lot_id, e.equipment_id, e.status execution_status,
       e.started_at, e.ended_at,
       x.input_qty, x.good_qty, x.defect_qty, x.defect_reason, x.confirmed_at
FROM mes.route_step s
LEFT JOIN mes.operation_execution e
  ON e.workspace_id=s.workspace_id AND e.generation_id=s.generation_id
 AND e.route_step_id=s.id AND e.lot_id=:lot
LEFT JOIN mes.operation_result x
  ON x.workspace_id=e.workspace_id AND x.generation_id=e.generation_id AND x.execution_id=e.id
WHERE s.workspace_id=:w AND s.generation_id=:g AND s.route_version_id=:route
ORDER BY s.sequence_no
"""


def _steps(connection, scoped, lot: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        repo.row_dict(r)
        for r in connection.execute(
            text(STEP_SQL),
            {**_s(scoped), "lot": lot["id"], "route": lot["routeVersionId"]},
        ).mappings()
    ]


def _next_step(
    lot: dict[str, Any], steps: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """다음에 시작할 단계와 그 투입 수량. 첫 단계는 지시 수량, 이후는 직전 단계 양품(FS-006)."""
    if lot["status"] == "completed":
        return None
    input_qty = lot["planQty"]
    for step in steps:
        if step["executionId"] is None:
            return {**step, "inputQty": input_qty}
        if step["executionStatus"] != "completed":
            return None  # 진행 중인 단계가 있다
        input_qty = step["goodQty"]
    return None


def _running_step(
    lot: dict[str, Any], steps: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """진행 중 단계와 그 투입 수량(첫 단계 = 지시 수량, 이후 = 직전 양품)."""
    for index, step in enumerate(steps):
        if step["executionStatus"] == "running":
            before = lot["planQty"] if index == 0 else steps[index - 1]["goodQty"]
            return {**step, "inputQty": before}
    return None


def _summary(lot: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    done = [s for s in steps if s["executionStatus"] == "completed"]
    return {
        **lot,
        "stepCount": len(steps),
        "completedSteps": len(done),
        "finalGoodQty": done[-1]["goodQty"]
        if lot["status"] == "completed" and done
        else None,
        "running": _running_step(lot, steps),
        "nextStep": _next_step(lot, steps),
    }


def list_lots(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        lots = [
            repo.row_dict(r)
            for r in connection.execute(
                text(LOT_SQL + " ORDER BY t.lot_no DESC"), _s(scoped)
            ).mappings()
        ]
        # ponytail: LOT마다 단계 조회(N+1). 한 공간 LOT 수십 건 규모라 충분하다. 수백 건이면 한 번에 묶는다.
        return [_summary(lot, _steps(connection, scoped, lot)) for lot in lots]


def get_lot(context: AuthContext, lot_id: int) -> dict[str, Any]:
    """추적성 한 화면: 단계별 실행·설비·실적과 투입 자재를 한 번에 돌려준다(FS-010 §9)."""
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        row = (
            connection.execute(
                text(LOT_SQL + " AND t.id=:id"), {**_s(scoped), "id": lot_id}
            )
            .mappings()
            .first()
        )
        if row is None:
            raise _not_found("LOT")
        lot = repo.row_dict(row)
        steps = _steps(connection, scoped, lot)
        issues = [
            repo.row_dict(r)
            for r in connection.execute(
                text(
                    "SELECT m.id, m.execution_id, m.material_item_id, m.material_lot_id, "
                    "m.bom_version_id, m.issued_qty, m.unit, m.issued_at "
                    "FROM mes.material_issue m JOIN mes.operation_execution e "
                    "ON e.workspace_id=m.workspace_id AND e.generation_id=m.generation_id "
                    "AND e.id=m.execution_id "
                    "WHERE m.workspace_id=:w AND m.generation_id=:g AND e.lot_id=:lot "
                    "ORDER BY m.issued_at, m.id"
                ),
                {**_s(scoped), "lot": lot_id},
            ).mappings()
        ]
    for step in steps:
        step["materialIssues"] = [
            i for i in issues if i["executionId"] == step["executionId"]
        ]
    return {**_summary(lot, steps), "steps": steps}


def list_running(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        return [
            repo.row_dict(r)
            for r in connection.execute(
                text(
                    "SELECT e.id, e.lot_id, t.lot_no, e.route_step_id, s.sequence_no, "
                    "s.process_id, e.equipment_id, e.started_at, e.unit "
                    "FROM mes.operation_execution e "
                    "JOIN mes.lot t ON t.workspace_id=e.workspace_id "
                    "AND t.generation_id=e.generation_id AND t.id=e.lot_id "
                    "JOIN mes.route_step s ON s.workspace_id=e.workspace_id "
                    "AND s.generation_id=e.generation_id AND s.id=e.route_step_id "
                    "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.status='running' "
                    "ORDER BY e.started_at, e.id"
                ),
                _s(scoped),
            ).mappings()
        ]


# ---- 잠금 (공간 → 작업지시 → LOT → 실행, FS-006a 락 순서) ----
def _lock_lot(connection, scoped, lot_id: int) -> dict[str, Any]:
    row = (
        connection.execute(
            text(LOT_SQL + " AND t.id=:id FOR UPDATE OF o, t"),
            {**_s(scoped), "id": lot_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise _not_found("LOT")
    return repo.row_dict(row)


def start(context: AuthContext, lot_id: int, values: dict[str, Any], key: str):
    """TX-01 공정 시작. 다음 단계만, 허용·활성 설비만, 같은 설비에 미종료 실행이 없을 때만."""

    def run(connection, scoped):
        lot = _lock_lot(connection, scoped, lot_id)
        if (
            lot["orderStatus"] not in ("released", "in_progress")
            or lot["status"] == "completed"
        ):
            raise _conflict(
                "발행되어 진행 중인 LOT만 공정을 시작할 수 있습니다.",
                "LOT_NOT_STARTABLE",
            )
        steps = _steps(connection, scoped, lot)
        step = _next_step(lot, steps)
        if step is None:
            raise _conflict(
                "진행 중인 공정이 끝나야 다음 공정을 시작할 수 있습니다.",
                "STEP_RUNNING",
            )
        if values["route_step_id"] != step["routeStepId"]:
            raise _conflict(
                f"경로 순서대로만 시작합니다. 다음 공정은 {step['sequenceNo']}번째입니다.",
                "OUT_OF_ORDER",
                nextRouteStepId=step["routeStepId"],
            )
        equipment = repo.get_row(
            connection, scoped, repo.EQUIPMENT, values["equipment_id"]
        )
        if equipment is None or not equipment["isActive"]:
            raise _field("equipmentId", "사용 중인 설비만 고를 수 있습니다.")
        process = repo.get_row(connection, scoped, repo.PROCESS, step["processId"])
        if not process["isActive"]:
            raise _conflict(
                "사용 안 함인 공정은 실행할 수 없습니다.", "PROCESS_INACTIVE"
            )
        allowed = repo.process_equipment_ids(connection, scoped).get(
            step["processId"], []
        )
        if equipment["id"] not in allowed:
            raise _field("equipmentId", "이 공정에 허용된 설비가 아닙니다.")
        # 설비 동시 점유 금지(M-G07): 공간 잠금으로 직렬화된 상태에서 미종료 실행을 확인한다.
        busy = connection.execute(
            text(
                "SELECT t.lot_no FROM mes.operation_execution e JOIN mes.lot t "
                "ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id "
                "AND t.id=e.lot_id "
                "WHERE e.workspace_id=:w AND e.generation_id=:g "
                "AND e.equipment_id=:eq AND e.ended_at IS NULL"
            ),
            {**_s(scoped), "eq": equipment["id"]},
        ).scalar()
        if busy:
            raise _conflict(
                f"설비가 {busy} 공정을 실행 중입니다. 끝난 뒤에 시작하세요.",
                "EQUIPMENT_BUSY",
                lotNo=busy,
            )
        if lot["status"] == "ready":
            # 첫 공정 시작: 지시 released → in_progress, LOT ready → in_progress (같은 트랜잭션)
            connection.execute(
                text(
                    f"UPDATE mes.work_order SET status='in_progress', started_at=now() "
                    f"WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "id": lot["workOrderId"]},
            )
            connection.execute(
                text(f"UPDATE mes.lot SET status='in_progress' WHERE {_S} AND id=:id"),
                {**_s(scoped), "id": lot_id},
            )
        execution_id = connection.execute(
            text(
                "INSERT INTO mes.operation_execution (workspace_id, generation_id, lot_id, "
                "route_version_id, route_step_id, equipment_id, unit, started_at) "
                "VALUES (:w, :g, :lot, :route, :step, :eq, :unit, now()) RETURNING id"
            ),
            {
                **_s(scoped),
                "lot": lot_id,
                "route": lot["routeVersionId"],
                "step": step["routeStepId"],
                "eq": equipment["id"],
                "unit": lot["unit"],
            },
        ).scalar_one()
        return _detail(connection, scoped, lot_id), "operation_execution", execution_id

    return _action(
        context,
        "mes.operation_execution.start",
        key,
        {"lotId": lot_id, **values},
        run,
        201,
    )


def confirm_result(
    context: AuthContext, execution_id: int, values: dict[str, Any], key: str
):
    """TX-02 공정 완료 = 실적 확정. 투입은 서버가 정하고 양품 + 불량 = 투입이어야 한다."""

    def run(connection, scoped):
        lot_id = connection.execute(
            text(f"SELECT lot_id FROM mes.operation_execution WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": execution_id},
        ).scalar()
        if lot_id is None:
            raise _not_found("공정 실행")
        lot = _lock_lot(connection, scoped, lot_id)
        execution = (
            connection.execute(
                text(
                    f"SELECT id, route_step_id, status FROM mes.operation_execution "
                    f"WHERE {_S} AND id=:id FOR UPDATE"
                ),
                {**_s(scoped), "id": execution_id},
            )
            .mappings()
            .one()
        )
        if execution["status"] != "running":
            raise _conflict("이미 실적을 확정한 공정입니다.", "ALREADY_COMPLETED")
        steps = _steps(connection, scoped, lot)
        index = next(
            i
            for i, s in enumerate(steps)
            if s["routeStepId"] == execution["route_step_id"]
        )
        input_qty = Decimal(
            lot["planQty"] if index == 0 else steps[index - 1]["goodQty"]
        )
        good, defect = Decimal(values["good_qty"]), Decimal(values["defect_qty"])
        if lot["unit"] == "EA" and (
            good != good.to_integral_value() or defect != defect.to_integral_value()
        ):
            raise _field("goodQty", "EA 수량은 정수입니다.")
        if good + defect != input_qty:
            raise _field(
                "goodQty",
                f"양품 + 불량은 투입 수량 {input_qty.normalize():f}과 같아야 합니다.",
            )
        reason = (values.get("defect_reason") or "").strip() or None
        if defect > 0 and reason is None:
            raise _field("defectReason", "불량이 있으면 사유를 입력하세요.")
        connection.execute(
            text(
                "INSERT INTO mes.operation_result (workspace_id, generation_id, execution_id, "
                "input_qty, output_qty, good_qty, defect_qty, unit, defect_reason, confirmed_at) "
                "VALUES (:w, :g, :e, :input, :input, :good, :defect, :unit, :reason, now())"
            ),
            {
                **_s(scoped),
                "e": execution_id,
                "input": input_qty,
                "good": good,
                "defect": defect,
                "unit": lot["unit"],
                "reason": reason,
            },
        )
        connection.execute(
            text(
                f"UPDATE mes.operation_execution SET status='completed', ended_at=now() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": execution_id},
        )
        # 마지막 공정이면 정상 완료, 중간 공정 양품이 0이면 후행 공정 없이 전량 불량 종결(FS-006)
        last = index == len(steps) - 1
        if last or good == 0:
            reason_code = "all_defective" if good == 0 else "normal"
            connection.execute(
                text(
                    f"UPDATE mes.lot SET status='completed', completion_reason=:r "
                    f"WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "r": reason_code, "id": lot_id},
            )
            connection.execute(
                text(
                    f"UPDATE mes.work_order SET status='completed', completed_at=now(), "
                    f"completion_reason=:r WHERE {_S} AND id=:id"
                ),
                {**_s(scoped), "r": reason_code, "id": lot["workOrderId"]},
            )
        return _detail(connection, scoped, lot_id), "operation_result", execution_id

    return _action(
        context,
        "mes.operation_result.confirm",
        key,
        {"id": execution_id, **values},
        run,
    )


def _detail(connection, scoped, lot_id: int) -> dict[str, Any]:
    row = (
        connection.execute(
            text(LOT_SQL + " AND t.id=:id"), {**_s(scoped), "id": lot_id}
        )
        .mappings()
        .one()
    )
    lot = repo.row_dict(row)
    steps = _steps(connection, scoped, lot)
    return {**_summary(lot, steps), "steps": steps}
