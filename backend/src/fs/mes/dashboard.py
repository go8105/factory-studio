"""M-01 MES 대시보드 (FS-020g). 조회 시 계산하고 저장하지 않는다.

- 당월 생산 = 그 달에 확정된 **마지막 공정** 양품. 공정별 양품을 합산하지 않는다(FS-006b §5).
- 양품률 = 그 달 확정 실적의 Σ양품 ÷ Σ산출(전 공정, FS-008a M-01). 시드의 전량 불량 LOT 때문에 100%가 아니다.
- 공정별 진행 = 완료되지 않은 LOT이 지금 어느 공정에 실행 중이거나 시작을 기다리는지.
- 설비 가동률은 설비 상태 컬럼이 없어 계산하지 않는다(M-G06, 화면 안내).
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text

from fs.common.auth import AuthContext
from fs.common.clock import business_today
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.mes import repository as repo
from fs.mes.execution import LOT_SQL, _steps, _summary
from fs.mes.packing import LOT_GOOD_SQL, _lot_row
from fs.mes.service import MODULE, _read

_S = "workspace_id=:w AND generation_id=:g"
KST = ZoneInfo("Asia/Seoul")


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def _month_range(month: str | None) -> tuple[str, datetime, datetime]:
    if month is None:
        today = business_today()
        month = f"{today.year:04d}-{today.month:02d}"
    try:
        start = date.fromisoformat(f"{month}-01")
    except ValueError as error:
        raise ApiError(
            400,
            "VALIDATION_FAILED",
            "입력값을 확인해 주세요.",
            {"fields": {"month": "YYYY-MM"}},
        ) from error
    end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    # 월 경계는 한국 시각으로 자른다(시드·사업장 기본 시간대 Asia/Seoul).
    return (
        month,
        datetime.combine(start, datetime.min.time(), KST),
        datetime.combine(end, datetime.min.time(), KST),
    )


def _produced_and_rate(results) -> tuple[Decimal, str | None]:
    """마지막 공정 양품(생산량)과 전 공정 Σ양품÷Σ산출(양품률)."""
    good = sum((r["good_qty"] for r in results), Decimal(0))
    output = sum((r["output_qty"] for r in results), Decimal(0))
    produced = sum(
        (r["good_qty"] for r in results if r["sequence_no"] == r["last_sequence"]),
        Decimal(0),
    )
    rate = None if output == 0 else str((good / output * 100).quantize(Decimal("0.1")))
    return produced, rate


def _previous_month(month: str) -> tuple[str, datetime, datetime, bool]:
    """바로 앞 달. 조회 월이 1월이면 지난해 12월이다.

    진행 중인 달을 전월 **전체**와 비교하면 늘 크게 모자라 보인다(22일까지 쌓인 값을
    30일치와 견주는 꼴). 그래서 이달을 볼 때는 전월도 **같은 날까지만** 센다.
    네 번째 값이 그 '같은 기간'인지 여부다.
    """
    year, mon = (int(part) for part in month.split("-"))
    year, mon = (year - 1, 12) if mon == 1 else (year, mon - 1)
    prev_month, start, end = _month_range(f"{year:04d}-{mon:02d}")
    today = business_today()
    if month != f"{today.year:04d}-{today.month:02d}":
        return prev_month, start, end, False
    # 이달에 흐른 일수만큼만 전월에서 센다. 전월이 더 짧으면 전월 끝까지다.
    elapsed = timedelta(days=today.day - 1)
    return prev_month, start, min(start + elapsed, end), True


RESULT_SQL = """
SELECT x.good_qty, x.output_qty, x.defect_qty, x.defect_reason, s.sequence_no,
       (SELECT max(s2.sequence_no) FROM mes.route_step s2
         WHERE s2.workspace_id=s.workspace_id AND s2.generation_id=s.generation_id
           AND s2.route_version_id=s.route_version_id) last_sequence
FROM mes.operation_result x
JOIN mes.operation_execution e ON e.workspace_id=x.workspace_id AND e.generation_id=x.generation_id
 AND e.id=x.execution_id
JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id
 AND s.id=e.route_step_id
WHERE x.workspace_id=:w AND x.generation_id=:g AND x.confirmed_at >= :start AND x.confirmed_at < :end
"""


def dashboard(context: AuthContext, month: str | None) -> dict[str, Any]:
    month, start, end = _month_range(month)
    with _read() as connection:
        scoped = read_scope(connection, context, MODULE)
        params = {**_s(scoped), "start": start, "end": end}
        results = connection.execute(text(RESULT_SQL), params).mappings().all()
        open_orders = connection.execute(
            text(
                f"SELECT count(*) FROM mes.work_order WHERE {_S} "
                "AND status IN ('released','in_progress')"
            ),
            params,
        ).scalar_one()
        received_sql = text(
            f"SELECT count(*) FROM mes.finished_goods_receipt WHERE {_S} "
            "AND received_at >= :start AND received_at < :end"
        )
        received = connection.execute(received_sql, params).scalar_one()
        prev_month, prev_start, prev_end, same_period = _previous_month(month)
        prev_params = {**params, "start": prev_start, "end": prev_end}
        prev_produced, prev_rate = _produced_and_rate(
            connection.execute(text(RESULT_SQL), prev_params).mappings().all()
        )
        previous = {
            "month": prev_month,
            "samePeriod": same_period,
            "producedQty": str(prev_produced),
            "goodRate": prev_rate,
            "receivedPallets": connection.execute(
                received_sql, prev_params
            ).scalar_one(),
        }
        lots = [
            _summary(lot, _steps(connection, scoped, lot))
            for lot in (
                repo.row_dict(r)
                for r in connection.execute(
                    text(LOT_SQL + " AND t.status <> 'completed'"), params
                ).mappings()
            )
        ]
        # 파이프라인은 경로 순서(사출 → 조립 → 검사)로 둔다. 공정마다 경로 안의 가장 앞 순번으로 정렬하고,
        # 경로에 없는 공정은 뒤로 보낸다.
        processes = [
            dict(r)
            for r in connection.execute(
                text(
                    "SELECT p.id, min(s.sequence_no) first_sequence FROM mes.process p "
                    "LEFT JOIN mes.route_step s ON s.workspace_id=p.workspace_id "
                    "AND s.generation_id=p.generation_id AND s.process_id=p.id "
                    "WHERE p.workspace_id=:w AND p.generation_id=:g "
                    "GROUP BY p.id ORDER BY min(s.sequence_no) NULLS LAST, p.id"
                ),
                params,
            ).mappings()
        ]
        packable = [
            lot
            for lot in map(
                _lot_row, connection.execute(text(LOT_GOOD_SQL), params).mappings()
            )
            if Decimal(lot["remainingQty"]) > 0
        ]
        plan = [
            repo.row_dict(r)
            for r in connection.execute(
                text(
                    # 계획 대비 실적: 그 달 확정 계획의 품목별 계획·지시 배정·최종 양품(완료 LOT)
                    "SELECT l.item_id, sum(l.plan_qty) plan_qty, "
                    "coalesce(sum(o.allocated), 0) allocated_qty, "
                    "coalesce(sum(o.final_good), 0) final_good_qty "
                    "FROM mes.production_plan_line l "
                    "JOIN mes.production_plan p ON p.workspace_id=l.workspace_id "
                    "AND p.generation_id=l.generation_id AND p.id=l.production_plan_id "
                    "LEFT JOIN LATERAL ("
                    " SELECT sum(w.plan_qty) FILTER (WHERE w.status <> 'cancelled') allocated,"
                    "  sum(g.good) final_good FROM mes.work_order w"
                    "  LEFT JOIN LATERAL ("
                    "   SELECT x.good_qty good FROM mes.lot t"
                    "   JOIN mes.operation_execution e ON e.workspace_id=t.workspace_id"
                    "    AND e.generation_id=t.generation_id AND e.lot_id=t.id"
                    "   JOIN mes.route_step s ON s.workspace_id=e.workspace_id"
                    "    AND s.generation_id=e.generation_id AND s.id=e.route_step_id"
                    "   JOIN mes.operation_result x ON x.workspace_id=e.workspace_id"
                    "    AND x.generation_id=e.generation_id AND x.execution_id=e.id"
                    "   WHERE t.workspace_id=w.workspace_id AND t.generation_id=w.generation_id"
                    "    AND t.work_order_id=w.id AND t.status='completed'"
                    "   ORDER BY s.sequence_no DESC LIMIT 1) g ON true"
                    "  WHERE w.workspace_id=l.workspace_id AND w.generation_id=l.generation_id"
                    "   AND w.production_plan_line_id=l.id) o ON true "
                    "WHERE l.workspace_id=:w AND l.generation_id=:g "
                    "AND p.status='confirmed' AND p.target_month=:month "
                    "GROUP BY l.item_id ORDER BY l.item_id"
                ),
                {**params, "month": month},
            ).mappings()
        ]

    produced, good_rate = _produced_and_rate(results)
    reasons: dict[str, Decimal] = {}
    for r in results:
        if r["defect_qty"] > 0:
            reasons[r["defect_reason"]] = (
                reasons.get(r["defect_reason"], Decimal(0)) + r["defect_qty"]
            )
    pipeline = {
        p["id"]: {"processId": p["id"], "running": 0, "waiting": 0} for p in processes
    }
    for lot in lots:
        if lot["running"]:
            pipeline[lot["running"]["processId"]]["running"] += 1
        elif lot["nextStep"]:
            pipeline[lot["nextStep"]["processId"]]["waiting"] += 1
    return {
        "month": month,
        "openOrders": open_orders,
        "producedQty": str(produced),
        "goodRate": good_rate,
        "receivedPallets": received,
        # 전월 같은 집계. 비교할 수 없는 값(진행 중 지시는 월과 무관)은 넣지 않는다.
        "previous": previous,
        "pipeline": list(pipeline.values()),
        "defectReasons": [
            {"reason": k, "defectQty": str(v)}
            for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:5]
        ],
        "planVsActual": plan,
        "pending": {
            "unconfirmedResults": sum(1 for lot in lots if lot["running"]),
            "unpackedLots": len(packable),
        },
    }
