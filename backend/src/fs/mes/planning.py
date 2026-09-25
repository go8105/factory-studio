"""M-02 생산계획 · M-03 작업지시 (FS-020c).

계획은 draft → confirmed. 확정 계획의 라인에서 수량을 배정해 작업지시를 만든다.
작업지시는 draft → released(LOT 생성) → in_progress → completed / draft → cancelled.
진행·완료 전이는 공정 실행(FS-020d)에서 일어난다.
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


def _locked(message: str, reason: str, **details: Any) -> ApiError:
    return ApiError(409, "PRECONDITION_NOT_MET", message, {"reason": reason, **details})


# ---- 조회 ----
PLAN_SQL = f"""
SELECT id, plan_code, target_month, sales_plan_code, status, created_at
FROM mes.production_plan WHERE {_S}
"""
# 배정량 = 취소되지 않은 지시(draft 포함)의 계획수량 합계 (FS-006b §5)
LINE_SQL = """
SELECT l.id, l.production_plan_id, l.item_id, l.target_week, l.plan_qty, l.unit,
       coalesce(sum(o.plan_qty) FILTER (WHERE o.status <> 'cancelled'), 0) allocated_qty
FROM mes.production_plan_line l
LEFT JOIN mes.work_order o
  ON o.workspace_id=l.workspace_id AND o.generation_id=l.generation_id
 AND o.production_plan_line_id=l.id
WHERE l.workspace_id=:w AND l.generation_id=:g
"""
ORDER_SQL = """
SELECT o.id, o.order_no, o.item_id, o.route_version_id, o.bom_version_id,
       o.production_plan_line_id, o.plan_qty, o.unit, o.plan_start_date, o.plan_end_date,
       o.status, o.released_at, o.started_at, o.completed_at, o.completion_reason,
       o.cancel_reason, o.created_at, t.id lot_id, t.lot_no, t.status lot_status
FROM mes.work_order o
LEFT JOIN mes.lot t
  ON t.workspace_id=o.workspace_id AND t.generation_id=o.generation_id AND t.work_order_id=o.id
WHERE o.workspace_id=:w AND o.generation_id=:g
"""


def _line_dict(row: Any) -> dict[str, Any]:
    line = repo.row_dict(row)
    line["remainingQty"] = str(Decimal(line["planQty"]) - Decimal(line["allocatedQty"]))
    return line


def _plans(connection, scoped, plan_id: int | None = None) -> list[dict[str, Any]]:
    where = " AND id=:id" if plan_id else ""
    plans = [
        repo.row_dict(r)
        for r in connection.execute(
            text(PLAN_SQL + where + " ORDER BY target_month DESC, plan_code"),
            {**_s(scoped), "id": plan_id},
        ).mappings()
    ]
    line_where = " AND l.production_plan_id=:id" if plan_id else ""
    lines = [
        _line_dict(r)
        for r in connection.execute(
            text(
                LINE_SQL
                + line_where
                + " GROUP BY l.id ORDER BY l.target_week, l.item_id, l.id"
            ),
            {**_s(scoped), "id": plan_id},
        ).mappings()
    ]
    for plan in plans:
        plan["lines"] = [x for x in lines if x["productionPlanId"] == plan["id"]]
    return plans


def list_plans(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        return _plans(connection, read_scope(connection, context, MODULE))


def _orders(connection, scoped, order_id: int | None = None) -> list[dict[str, Any]]:
    where = " AND o.id=:id" if order_id else ""
    return [
        repo.row_dict(r)
        for r in connection.execute(
            text(ORDER_SQL + where + " ORDER BY o.order_no DESC, o.id DESC"),
            {**_s(scoped), "id": order_id},
        ).mappings()
    ]


def list_orders(context: AuthContext) -> list[dict[str, Any]]:
    with _read() as connection:
        return _orders(connection, read_scope(connection, context, MODULE))


# ---- M-02 생산계획 ----
def _plan(connection, scoped, plan_id: int, lock: bool = False) -> dict[str, Any]:
    row = (
        connection.execute(
            text(PLAN_SQL + " AND id=:id" + (" FOR UPDATE" if lock else "")),
            {**_s(scoped), "id": plan_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise _not_found("생산계획")
    return repo.row_dict(row)


def _draft_plan(connection, scoped, plan_id: int) -> dict[str, Any]:
    plan = _plan(connection, scoped, plan_id, lock=True)
    if plan["status"] != "draft":
        raise _locked("확정된 생산계획은 바꿀 수 없습니다.", "PLAN_CONFIRMED")
    return plan


def _clean_sales_code(values: dict[str, Any]) -> dict[str, Any]:
    # ERP 판매계획 코드는 문자열로만 보관한다(존재·상태 검증 없음, FS-013). 빈 값은 NULL.
    if "sales_plan_code" in values:
        code = (values["sales_plan_code"] or "").strip()
        values = {**values, "sales_plan_code": code or None}
    return values


def create_plan(context: AuthContext, values: dict[str, Any], key: str):
    def run(connection, scoped):
        if repo.exists_where(
            connection,
            scoped,
            "mes.production_plan",
            {"plan_code": values["plan_code"]},
        ):
            raise _field("planCode", "이미 사용 중인 코드입니다.")
        row = connection.execute(
            text(
                "INSERT INTO mes.production_plan "
                "(workspace_id, generation_id, plan_code, target_month, sales_plan_code) "
                "VALUES (:w, :g, :plan_code, :target_month, :sales_plan_code) RETURNING id"
            ),
            {**_s(scoped), **_clean_sales_code(values)},
        ).scalar_one()
        return _plans(connection, scoped, row)[0], "production_plan", row

    return _action(context, "mes.production_plan.create", key, values, run, 201)


def update_plan(context: AuthContext, plan_id: int, values: dict[str, Any], key: str):
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        if (
            "plan_code" in values
            and connection.execute(
                text(
                    f"SELECT 1 FROM mes.production_plan WHERE {_S} "
                    "AND plan_code=:code AND id<>:id"
                ),
                {**_s(scoped), "code": values["plan_code"], "id": plan_id},
            ).first()
        ):
            raise _field("planCode", "이미 사용 중인 코드입니다.")
        clean = _clean_sales_code(values)
        assignments = ",".join(f"{k}=:{k}" for k in clean)
        connection.execute(
            text(f"UPDATE mes.production_plan SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **clean, "id": plan_id},
        )
        return _plans(connection, scoped, plan_id)[0], "production_plan", plan_id

    return _action(
        context, "mes.production_plan.update", key, {"id": plan_id, **values}, run
    )


def set_plan_lines(
    context: AuthContext, plan_id: int, lines: list[dict[str, Any]], key: str
):
    """초안 계획의 라인을 통째로 바꾼다. 단위는 품목 기준 단위로 서버가 정한다."""

    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        items = {i["id"]: i for i in repo.list_rows(connection, scoped, repo.ITEM)}
        seen: set[tuple[int, str]] = set()
        rows = []
        for n, line in enumerate(lines, 1):
            where = f"{n}번째 라인: "
            item = items.get(line["item_id"])
            if item is None:
                raise _field("lines", where + "유효하지 않은 품목입니다.")
            pair = (item["id"], line["target_week"])
            if pair in seen:
                raise _field("lines", where + "같은 품목·주차가 이미 있습니다.")
            seen.add(pair)
            qty = Decimal(line["plan_qty"])
            if item["baseUnit"] == "EA" and qty != qty.to_integral_value():
                raise _field("lines", where + "EA 품목의 수량은 정수입니다.")
            rows.append({**line, "unit": item["baseUnit"]})
        # 초안 계획에는 지시가 없다(지시는 확정 계획에서만 만든다). 그래서 통째로 바꿔도 된다.
        repo.replace_children(
            connection,
            scoped,
            "mes.production_plan_line",
            "production_plan_id",
            plan_id,
            rows,
        )
        return _plans(connection, scoped, plan_id)[0], "production_plan", plan_id

    return _action(
        context, "mes.production_plan.lines", key, {"id": plan_id, "lines": lines}, run
    )


def confirm_plan(context: AuthContext, plan_id: int, key: str):
    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        if not repo.exists_where(
            connection,
            scoped,
            "mes.production_plan_line",
            {"production_plan_id": plan_id},
        ):
            raise _locked("라인이 없는 생산계획은 확정할 수 없습니다.", "EMPTY_PLAN")
        connection.execute(
            text(
                f"UPDATE mes.production_plan SET status='confirmed' WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": plan_id},
        )
        return _plans(connection, scoped, plan_id)[0], "production_plan", plan_id

    return _action(context, "mes.production_plan.confirm", key, {"id": plan_id}, run)


def delete_plan(context: AuthContext, plan_id: int, key: str) -> None:
    def run(connection, scoped):
        _draft_plan(connection, scoped, plan_id)
        repo.replace_children(
            connection,
            scoped,
            "mes.production_plan_line",
            "production_plan_id",
            plan_id,
            [],
        )
        connection.execute(
            text(f"DELETE FROM mes.production_plan WHERE {_S} AND id=:id"),
            {**_s(scoped), "id": plan_id},
        )
        return {}, "production_plan", plan_id

    _action(context, "mes.production_plan.delete", key, {"id": plan_id}, run, 204)


# ---- M-03 작업지시 ----
def _order(connection, scoped, order_id: int, lock: bool = False) -> dict[str, Any]:
    if lock:
        connection.execute(
            text(f"SELECT 1 FROM mes.work_order WHERE {_S} AND id=:id FOR UPDATE"),
            {**_s(scoped), "id": order_id},
        )
    rows = _orders(connection, scoped, order_id)
    if not rows:
        raise _not_found("작업지시")
    return rows[0]


def _lock_line(connection, scoped, line_id: int) -> dict[str, Any]:
    """계획 라인을 잠그고 확정 여부·품목·단위를 돌려준다(배정 합계 검사 전 잠금, FS-006b)."""
    row = (
        connection.execute(
            text(
                "SELECT l.id, l.item_id, l.unit, l.plan_qty, p.status plan_status "
                "FROM mes.production_plan_line l JOIN mes.production_plan p "
                "ON p.workspace_id=l.workspace_id AND p.generation_id=l.generation_id "
                "AND p.id=l.production_plan_id "
                "WHERE l.workspace_id=:w AND l.generation_id=:g AND l.id=:id "
                "FOR UPDATE OF l"
            ),
            {**_s(scoped), "id": line_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        raise _field("productionPlanLineId", "유효하지 않은 계획 라인입니다.")
    if row["plan_status"] != "confirmed":
        raise _field(
            "productionPlanLineId", "확정된 생산계획의 라인에서만 지시를 만듭니다."
        )
    return dict(row)


def _check_allocation(
    connection, scoped, line: dict[str, Any], qty: Decimal, except_order: int | None
) -> None:
    allocated = connection.execute(
        text(
            f"SELECT coalesce(sum(plan_qty), 0) FROM mes.work_order WHERE {_S} "
            "AND production_plan_line_id=:line AND status<>'cancelled' "
            "AND id IS DISTINCT FROM :except"
        ),
        {**_s(scoped), "line": line["id"], "except": except_order},
    ).scalar_one()
    remaining = line["plan_qty"] - allocated
    if qty > remaining:
        raise _locked(
            f"계획 잔여 수량({remaining.normalize():f})을 넘습니다.",
            "PLAN_QTY_EXCEEDED",
            planQty=str(line["plan_qty"]),
            allocatedQty=str(allocated),
            remainingQty=str(remaining),
        )


def _check_version(
    connection,
    scoped,
    master: repo.Master,
    version_id: int | None,
    item_id: int,
    field: str,
) -> None:
    if version_id is None:
        return
    version = repo.get_row(connection, scoped, master, version_id)
    if version is None or version["itemId"] != item_id:
        raise _field(field, "지시 품목의 버전만 고를 수 있습니다.")
    if version["status"] != "published":
        raise _field(field, "게시된 버전만 고를 수 있습니다.")


def _check_order(connection, scoped, final: dict[str, Any], item_id: int, unit: str):
    qty = Decimal(final["plan_qty"])
    if qty <= 0:
        raise _field("planQty", "수량은 0보다 커야 합니다.")
    if unit == "EA" and qty != qty.to_integral_value():
        raise _field("planQty", "EA 품목의 수량은 정수입니다.")
    if final["plan_end_date"] < final["plan_start_date"]:
        raise _field("planEndDate", "종료일은 시작일 이후여야 합니다.")
    _check_version(
        connection,
        scoped,
        repo.ROUTE,
        final["route_version_id"],
        item_id,
        "routeVersionId",
    )
    _check_version(
        connection,
        scoped,
        repo.BOM,
        final.get("bom_version_id"),
        item_id,
        "bomVersionId",
    )


def _next_code(connection, scoped, table: str, column: str, prefix: str) -> str:
    """접두사 뒤 숫자의 최댓값 + 1 (WO-0031, LT-0027 …). 공간 잠금 안에서만 부른다."""
    last = connection.execute(
        text(
            f"SELECT max(substring({column} FROM :pattern)::int) FROM {table} "
            f"WHERE {_S} AND {column} ~ :regex"
        ),
        {**_s(scoped), "pattern": f"^{prefix}(\\d+)$", "regex": f"^{prefix}\\d+$"},
    ).scalar_one()
    return f"{prefix}{(last or 0) + 1:04d}"


def create_order(context: AuthContext, values: dict[str, Any], key: str):
    def run(connection, scoped):
        line = _lock_line(connection, scoped, values["production_plan_line_id"])
        _check_order(connection, scoped, values, line["item_id"], line["unit"])
        _check_allocation(connection, scoped, line, Decimal(values["plan_qty"]), None)
        order_no = _next_code(connection, scoped, "mes.work_order", "order_no", "WO-")
        order_id = connection.execute(
            text(
                "INSERT INTO mes.work_order (workspace_id, generation_id, order_no, item_id, "
                "route_version_id, bom_version_id, production_plan_line_id, plan_qty, unit, "
                "plan_start_date, plan_end_date) VALUES (:w, :g, :order_no, :item_id, "
                ":route_version_id, :bom_version_id, :production_plan_line_id, :plan_qty, "
                ":unit, :plan_start_date, :plan_end_date) RETURNING id"
            ),
            {
                **_s(scoped),
                **values,
                "order_no": order_no,
                "item_id": line["item_id"],
                "unit": line["unit"],
            },
        ).scalar_one()
        return _order(connection, scoped, order_id), "work_order", order_id

    return _action(context, "mes.work_order.create", key, values, run, 201)


def _draft_order(connection, scoped, order_id: int) -> dict[str, Any]:
    order = _order(connection, scoped, order_id, lock=True)
    if order["status"] != "draft":
        raise _locked(
            "발행한 작업지시는 바꾸거나 취소할 수 없습니다.", "ORDER_RELEASED"
        )
    return order


def update_order(context: AuthContext, order_id: int, values: dict[str, Any], key: str):
    if not values:
        raise ApiError(400, "VALIDATION_FAILED", "변경할 항목이 없습니다.")

    def run(connection, scoped):
        order = _draft_order(connection, scoped, order_id)
        line = _lock_line(connection, scoped, order["productionPlanLineId"])
        final = {
            "plan_qty": order["planQty"],
            "plan_start_date": order["planStartDate"],
            "plan_end_date": order["planEndDate"],
            "route_version_id": order["routeVersionId"],
            "bom_version_id": order["bomVersionId"],
            **values,
        }
        _check_order(connection, scoped, final, line["item_id"], line["unit"])
        # draft 변경은 자기 자신을 합계에서 빼고 다시 계산한다(FS-006b).
        _check_allocation(
            connection, scoped, line, Decimal(final["plan_qty"]), order_id
        )
        assignments = ",".join(f"{k}=:{k}" for k in values)
        connection.execute(
            text(f"UPDATE mes.work_order SET {assignments} WHERE {_S} AND id=:id"),
            {**_s(scoped), **values, "id": order_id},
        )
        return _order(connection, scoped, order_id), "work_order", order_id

    return _action(
        context, "mes.work_order.update", key, {"id": order_id, **values}, run
    )


def cancel_order(context: AuthContext, order_id: int, reason: str, key: str):
    def run(connection, scoped):
        _draft_order(connection, scoped, order_id)
        connection.execute(
            text(
                f"UPDATE mes.work_order SET status='cancelled', cancel_reason=:reason "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "reason": reason, "id": order_id},
        )
        return _order(connection, scoped, order_id), "work_order", order_id

    return _action(
        context, "mes.work_order.cancel", key, {"id": order_id, "reason": reason}, run
    )


def _create_lot(connection, scoped, order: dict[str, Any]) -> None:
    # 1지시 : 1LOT (UK work_order_id, 갭 M-G04 의도 확정)
    connection.execute(
        text(
            "INSERT INTO mes.lot (workspace_id, generation_id, lot_no, work_order_id, "
            "route_version_id, unit) VALUES (:w, :g, :lot_no, :order, :route, :unit)"
        ),
        {
            **_s(scoped),
            "lot_no": _next_code(connection, scoped, "mes.lot", "lot_no", "LT-"),
            "order": order["id"],
            "route": order["routeVersionId"],
            "unit": order["unit"],
        },
    )


def release_order(context: AuthContext, order_id: int, key: str):
    """draft → released. 경로·BOM이 여전히 게시 상태인지 확인하고 LOT을 같은 트랜잭션에서 만든다."""

    def run(connection, scoped):
        order = _draft_order(connection, scoped, order_id)
        for master, field, value in (
            (repo.ROUTE, "routeVersionId", order["routeVersionId"]),
            (repo.BOM, "bomVersionId", order["bomVersionId"]),
        ):
            if (
                value is not None
                and repo.get_row(connection, scoped, master, value)["status"]
                != "published"
            ):
                raise _locked(
                    "게시 상태가 아닌 경로·BOM으로는 발행할 수 없습니다. 지시를 수정하세요.",
                    "VERSION_NOT_PUBLISHED",
                    field=field,
                )
        connection.execute(
            text(
                f"UPDATE mes.work_order SET status='released', released_at=clock_timestamp() "
                f"WHERE {_S} AND id=:id"
            ),
            {**_s(scoped), "id": order_id},
        )
        _create_lot(connection, scoped, order)
        return _order(connection, scoped, order_id), "work_order", order_id

    return _action(context, "mes.work_order.release", key, {"id": order_id}, run)


def create_missing_lot(context: AuthContext, order_id: int, key: str):
    """발행됐지만 LOT이 아직 없는 지시(FS-006 '발행 후 LOT 생성 전')의 LOT을 만든다."""

    def run(connection, scoped):
        order = _order(connection, scoped, order_id, lock=True)
        if order["status"] != "released" or order["lotId"] is not None:
            raise _locked(
                "LOT이 없는 발행 지시에서만 LOT을 만들 수 있습니다.", "LOT_NOT_ALLOWED"
            )
        _create_lot(connection, scoped, order)
        return _order(connection, scoped, order_id), "work_order", order_id

    return _action(context, "mes.work_order.lot", key, {"id": order_id}, run, 201)
