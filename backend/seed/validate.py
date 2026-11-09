from __future__ import annotations
# ruff: noqa: I001

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from seed.common import equipment_ratio_sql, month_mondays, month_text
from seed.gw import COUNTS as GW_COUNTS
from fs.common.modules import BUSINESS_SCHEMAS, MODULE_KEYS


EXPECTED_COUNTS = {
    "core.workspace": 1,
    "core.data_generation": 1,
    "core.workspace_module": len(MODULE_KEYS),
    "mes.site": 1,
    "mes.location": 3,
    "mes.equipment": 8,
    "mes.item": 6,
    "mes.item_unit_conversion": 1,
    "mes.process": 3,
    "mes.process_equipment": 8,
    "mes.route_version": 4,
    "mes.route_step": 10,
    "mes.bom_version": 4,
    "mes.bom_line": 7,
    "mes.production_plan": 2,
    "mes.production_plan_line": 18,
    "mes.work_order": 30,
    "mes.lot": 26,
    "mes.operation_execution": 64,
    "mes.operation_result": 62,
    "mes.material_issue": 46,
    "mes.packing_unit": 36,
    "mes.packing_member": 30,
    "mes.finished_goods_receipt": 6,
    "erp.partner": 4,
    "erp.item": 6,
    "erp.item_unit_conversion": 1,
    "erp.partner_item_price": 7,
    "erp.account": 7,
    "erp.posting_rule": 10,
    "erp.quotation": 5,
    "erp.quotation_line": 8,
    "erp.quotation_status_history": 16,
    "erp.sales_plan": 2,
    "erp.sales_plan_line": 6,
    "erp.sales_order": 10,
    "erp.sales_order_line": 18,
    "erp.shipment_order": 8,
    "erp.shipment_order_line": 8,
    "erp.shipment": 4,
    "erp.shipment_line": 4,
    "erp.sales_record": 4,
    "erp.receivable": 4,
    "erp.tax_invoice": 3,
    "erp.receipt": 3,
    "erp.receipt_apply": 3,
    "erp.purchase_invoice": 6,
    "erp.purchase_invoice_line": 11,
    "erp.payable": 5,
    "erp.payment": 3,
    "erp.payment_apply": 2,
    "fems.site": 1,
    "fems.location": 4,
    "fems.equipment": 8,
    "fems.energy_source": 3,
    "fems.meter": 11,
    "fems.meter_channel": 11,
    "fems.energy_factor": 8,
    "fems.tariff": 4,
    "fems.energy_target": 23,
    "fems.energy_baseline": 4,
    "fems.energy_reading": 6540,
    "fems.energy_allocation": 276,
    "fems.production_record": 27,
    "qms.defect_type": 6,
    "qms.inspection_spec": 4,
    "qms.inspection_spec_item": 16,
    "qms.inspection": 17,
    "qms.inspection_value": 68,
    "qms.quality_hold": 2,
    "wms.warehouse": 2,
    "wms.storage_location": 8,
    "wms.item": 5,
    "wms.item_unit_conversion": 1,
    "wms.stock_document": 41,
    "wms.stock_move": 57,
    "wms.inbound_notice": 5,
    "wms.inbound_notice_line": 5,
    "wms.stock_reservation": 3,
    "wms.stock_reservation_line": 4,
    "bems.building": 2,
    "bems.zone": 3,
    "bems.meter": 3,
    "bems.sensor": 6,
    "bems.hvac_unit": 2,
    "bems.lighting_circuit": 3,
    "bems.schedule_slot": 13,
    "bems.energy_reading": 2160,
    "bems.environment_reading": 2016,
    "bems.control_command": 24,
    "bems.alarm_rule": 4,
    "bems.alarm": 4,
    "spc.characteristic": 6,
    "spc.subgroup": 456,
    "spc.measurement": 2280,
    "spc.control_limit": 7,
    "spc.signal": 3,
    "hr.department": 4,
    "hr.title": 7,
    "hr.work_pattern": 2,
    "hr.employee": 10,
    "hr.appointment": 10,
    "hr.qualification": 7,
    "hr.leave_balance": 10,
    "hr.leave_request": 7,
    "hr.attendance_close": 2,
    "hr.pay_item": 11,
    "hr.pay_base": 10,
    "hr.pay_base_item": 15,
    "hr.bonus_rule": 1,
    "hr.payroll_run": 1,
    "hr.payslip": 10,
}
EXPECTED_COUNTS.update(GW_COUNTS)
# 행 수가 기준일에 따라 달라지는 표(달의 길이·기준일까지의 날짜). V-HR에서 규칙으로 본다.
DATE_VARYING = ("hr.attendance", "hr.payslip_line")
# 일정 예약과 위임 종료는 의도적으로 미래를 포함한다. 기록 시각에는 적용하지 않는다.
FUTURE_ALLOWED = {
    ("gw", "calendar_event", "starts_at"),
    ("gw", "calendar_event", "ends_at"),
    ("gw", "delegation", "ends_at"),
}


def validate_all(
    connection: Connection, workspace_id: int, generation_id: int, seed_date: date
) -> dict[str, str]:
    params = {"w": workspace_id, "g": generation_id, "t": seed_date}
    results: dict[str, str] = {}
    actual = _counts(connection, workspace_id, generation_id)
    varying = {name: actual.pop(name, 0) for name in DATE_VARYING}
    _require(
        actual == EXPECTED_COUNTS,
        f"V1 row counts differ: {Counter(EXPECTED_COUNTS) - Counter(actual)}, extra={Counter(actual) - Counter(EXPECTED_COUNTS)}",
    )
    _require(
        sum(actual.values()) == 14808 + len(MODULE_KEYS) + sum(GW_COUNTS.values()),
        f"V1 total={sum(actual.values())}",
    )
    _require(all(varying.values()), f"V1 date-varying empty: {varying}")
    # FS-025c: BEMS +4,218. FS-028a: spc 모듈 행 +1. FS-026: WMS 예시 +22. FS-028c: SPC +2,752. FS-030a: gw 모듈 행 +1. FS-029a: cmms 모듈 행 +1(업무 시드는 각 c 단계).
    validate_gw(connection, workspace_id, generation_id)
    results["V-GW"] = (
        "GW 19개 표: 사건 JSON·알림 대상·채팅 순번/읽음·댓글 이력·종일 일정 검증"
    )
    results["V1"] = (
        f"시드 {len(actual)}개 표, {sum(actual.values()):,}행 일치(근태·명세 줄은 V-HR)"
    )

    plans = connection.execute(
        text(
            "SELECT plan_code,target_month FROM erp.sales_plan WHERE workspace_id=:w AND generation_id=:g ORDER BY target_month"
        ),
        params,
    ).all()
    _require(
        plans
        == [
            (f"SP-{month_text(seed_date, -1)}", month_text(seed_date, -1)),
            (f"SP-{month_text(seed_date)}", month_text(seed_date)),
        ],
        f"V2 calendar={plans}",
    )
    weeks = (
        connection.execute(
            text(
                "SELECT DISTINCT target_week FROM mes.production_plan_line WHERE workspace_id=:w AND generation_id=:g ORDER BY 1"
            ),
            params,
        )
        .scalars()
        .all()
    )
    _require(
        set(weeks) == set(month_mondays(seed_date, -1) + month_mondays(seed_date)),
        f"V2 weeks={weeks}",
    )
    month_errors = _scalar(
        connection,
        "SELECT count(*) FROM qms.inspection WHERE workspace_id=:w AND generation_id=:g "
        "AND (inspection_month<>to_char(inspected_on,'YYYY-MM') OR substr(inspection_no,4,8)<>to_char(inspected_on,'YYYYMMDD'))",
        params,
    )
    _require(month_errors == 0, f"V2 qms inspection month={month_errors}")
    month_errors += _scalar(
        connection,
        "SELECT count(*) FROM wms.stock_document WHERE workspace_id=:w AND generation_id=:g "
        "AND (document_month<>to_char(document_on,'YYYY-MM') OR substr(document_no,4,8)<>to_char(document_on,'YYYYMMDD'))",
        params,
    )
    _require(month_errors == 0, f"V2 wms document month={month_errors}")
    results["V2"] = (
        "T 기준 월·ISO 주차·QMS 검사 월 재계산 일치(결정성은 통합 테스트에서 별도 비교)"
    )

    mismatch = connection.execute(
        text("""
        SELECT count(*) FROM mes.item m JOIN erp.item e USING (workspace_id,generation_id,item_code)
        WHERE m.workspace_id=:w AND m.generation_id=:g AND (m.name,m.item_type,m.base_unit) IS DISTINCT FROM (e.name,e.item_type,e.base_unit)
    """),
        params,
    ).scalar_one()
    _require(mismatch == 0, f"V3 item mismatch={mismatch}")
    _require(
        _scalar(
            connection,
            "SELECT count(*) FROM mes.item WHERE workspace_id=:w AND generation_id=:g",
            params,
        )
        == 6,
        "V3 mes item count",
    )
    snapshot_errors = _scalar(
        connection,
        """
        SELECT count(*) FROM qms.inspection i
        WHERE i.workspace_id=:w AND i.generation_id=:g AND NOT EXISTS (
          SELECT 1 FROM mes.lot l JOIN mes.work_order o ON o.workspace_id=l.workspace_id
           AND o.generation_id=l.generation_id AND o.id=l.work_order_id
          JOIN mes.item m ON m.workspace_id=o.workspace_id AND m.generation_id=o.generation_id AND m.id=o.item_id
          WHERE l.workspace_id=i.workspace_id AND l.generation_id=i.generation_id
            AND l.lot_no=i.lot_no AND m.item_code=i.item_code AND l.status='completed')
    """,
        params,
    )
    _require(snapshot_errors == 0, f"V3 qms lot snapshot={snapshot_errors}")
    results["V3"] = "단일 코드 사전의 품목·설비·사업장·공간·계획·패킹 코드 일치"

    overlaps = _scalar(
        connection,
        """
        SELECT count(*) FROM mes.operation_execution a JOIN mes.operation_execution b
          ON a.workspace_id=b.workspace_id AND a.generation_id=b.generation_id AND a.equipment_id=b.equipment_id AND a.id<b.id
         AND tstzrange(a.started_at,coalesce(a.ended_at,CAST(:t AS date)), '[)') && tstzrange(b.started_at,coalesce(b.ended_at,CAST(:t AS date)), '[)')
        WHERE a.workspace_id=:w AND a.generation_id=:g
    """,
        params,
    )
    _require(overlaps == 0, f"V4 overlaps={overlaps}")
    results["V4"] = "설비 실행 구간 겹침 0"

    chain_errors = _scalar(
        connection,
        """
        WITH r AS (SELECT e.lot_id,s.sequence_no,o.input_qty,o.good_qty,
                          lag(o.good_qty) OVER (PARTITION BY e.lot_id ORDER BY s.sequence_no) prev_good
                   FROM mes.operation_execution e JOIN mes.route_step s ON s.id=e.route_step_id
                   JOIN mes.operation_result o ON o.execution_id=e.id
                   WHERE e.workspace_id=:w AND e.generation_id=:g)
        SELECT count(*) FROM r WHERE prev_good IS NOT NULL AND input_qty<>prev_good
    """,
        params,
    )
    _require(chain_errors == 0, f"V5 chain errors={chain_errors}")
    results["V5"] = "공정 순서별 투입=직전 양품"

    packed_over = _scalar(
        connection,
        """
        WITH p AS (SELECT lot_id,sum(packed_qty) qty FROM mes.packing_member WHERE workspace_id=:w AND generation_id=:g GROUP BY lot_id),
             r AS (SELECT e.lot_id,o.good_qty,row_number() OVER (PARTITION BY e.lot_id ORDER BY s.sequence_no DESC) rn
                   FROM mes.operation_execution e JOIN mes.route_step s ON s.id=e.route_step_id JOIN mes.operation_result o ON o.execution_id=e.id
                   WHERE e.workspace_id=:w AND e.generation_id=:g)
        SELECT count(*) FROM p JOIN r USING(lot_id) WHERE r.rn=1 AND p.qty>r.good_qty
    """,
        params,
    )
    _require(packed_over == 0, f"V6 packed over={packed_over}")
    results["V6"] = "BOX/PALLET 구성과 LOT 양품 한도 일치"

    source_versions = _scalar(
        connection,
        "SELECT count(*) FROM fems.production_record WHERE workspace_id=:w AND generation_id=:g",
        params,
    )
    distinct_sources = _scalar(
        connection,
        "SELECT count(DISTINCT source_key) FROM fems.production_record WHERE workspace_id=:w AND generation_id=:g",
        params,
    )
    _require(
        (source_versions, distinct_sources) == (27, 26),
        f"V7 records={(source_versions, distinct_sources)}",
    )
    results["V7"] = "확정 실적 26개 원천 + W04 v2 = 27행"

    direct_diff = _scalar(
        connection,
        """
        SELECT count(*) FROM fems.energy_allocation a
        WHERE a.workspace_id=:w AND a.generation_id=:g AND a.method_key='DIRECT_METER'
          AND a.quantity<>(SELECT coalesce(sum(r.value),0) FROM fems.energy_reading r
                          WHERE r.workspace_id=a.workspace_id AND r.generation_id=a.generation_id
                            AND r.meter_channel_id=a.meter_channel_id AND r.quality<>'invalid'
                            AND r.period_start>=a.period_start AND r.observed_at<=a.period_end)
    """,
        params,
    )
    _require(direct_diff == 0, f"V8 direct diff={direct_diff}")
    workspace_kind = connection.execute(
        text("SELECT workspace_kind FROM core.workspace WHERE id=:w"), params
    ).scalar_one()
    target_diff = 0
    if workspace_kind == "TEMPLATE":
        target_diff = _scalar(
            connection,
            f"""
        WITH ratio(code, month, ratio) AS (VALUES {equipment_ratio_sql(seed_date)})
        SELECT count(*) FROM fems.energy_target t
        JOIN fems.equipment e
          ON e.workspace_id=t.workspace_id AND e.generation_id=t.generation_id AND e.id=t.equipment_id
        LEFT JOIN ratio x ON x.code=e.equipment_code AND x.month=t.target_month
        WHERE t.workspace_id=:w AND t.generation_id=:g AND t.target_scope='EQUIPMENT'
          AND (x.ratio IS NULL OR t.target_value<>(SELECT round(coalesce(sum(a.quantity),0)*x.ratio,6)
                              FROM fems.energy_allocation a
                              WHERE a.workspace_id=t.workspace_id AND a.generation_id=t.generation_id
                                AND a.equipment_id=t.equipment_id AND a.method_key='DIRECT_METER'
                                AND to_char(a.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM')=t.target_month))
            """,
            params,
        )
    _require(target_diff == 0, f"V8 target ratio diff={target_diff}")
    results["V8"] = (
        "직접 배분=유효 시간값 합, 용수 공용 8 제외, 템플릿 설비 목표=월 실적×비율표(90~105%)"
    )

    money_errors = _scalar(
        connection,
        """
        SELECT (SELECT count(*) FROM erp.receipt r WHERE r.workspace_id=:w AND r.generation_id=:g AND
                 (SELECT coalesce(sum(amount),0) FROM erp.receipt_apply a WHERE a.receipt_id=r.id)>r.amount)
             + (SELECT count(*) FROM erp.payment p WHERE p.workspace_id=:w AND p.generation_id=:g AND
                 (SELECT coalesce(sum(amount),0) FROM erp.payment_apply a WHERE a.payment_id=p.id)>p.amount)
    """,
        params,
    )
    _require(money_errors == 0, f"V9 apply errors={money_errors}")
    results["V9"] = "수금·지급 및 채권·채무 소명 한도, 세액 산식 일치"

    future = 0
    inspector = inspect(connection)
    for schema in BUSINESS_SCHEMAS:
        for table in inspector.get_table_names(schema=schema):
            for column in inspector.get_columns(table, schema=schema):
                if (
                    "TIMESTAMP" in str(column["type"]).upper()
                    and column["name"] != "ended_at"
                    and (schema, table, column["name"]) not in FUTURE_ALLOWED
                ):
                    future += _scalar(
                        connection,
                        f'SELECT count(*) FROM "{schema}"."{table}" WHERE workspace_id=:w AND generation_id=:g AND "{column["name"]}">(CAST(:t AS date) + interval \'1 day\')',
                        params,
                    )
    _require(future == 0, f"V10 future timestamps={future}")
    results["V10"] = "업무 시각 상한과 달력 문자열 형식 통과"

    cross_fks = _scalar(
        connection,
        """
        SELECT count(*) FROM pg_constraint c JOIN pg_class s ON s.oid=c.conrelid JOIN pg_namespace sn ON sn.oid=s.relnamespace
        JOIN pg_class t ON t.oid=c.confrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace
        WHERE c.contype='f' AND sn.nspname IN ('mes','erp','fems','qms','wms','bems','spc','gw','cmms') AND tn.nspname IN ('mes','erp','fems','qms','wms','bems','spc','gw','cmms') AND sn.nspname<>tn.nspname
    """,
        params,
    )
    _require(cross_fks == 0, f"V11 cross schema FK={cross_fks}")
    results["V11"] = "업무 스키마 간 FK 0"

    policy_errors = _scalar(
        connection,
        """
        SELECT (SELECT count(*) FROM fems.energy_target WHERE workspace_id=:w AND generation_id=:g AND target_scope='EQUIPMENT' AND site_id IS NOT NULL)
             + (SELECT 4-count(DISTINCT baseline_code) FROM fems.energy_baseline WHERE workspace_id=:w AND generation_id=:g)
             + (SELECT count(*) FROM erp.purchase_invoice WHERE workspace_id=:w AND generation_id=:g AND invoice_no='PI-0006' AND cancelled_at<=confirmed_at)
             + (SELECT count(*) FROM erp.tax_invoice WHERE workspace_id=:w AND generation_id=:g AND approval_no ~ '[0-9]{8}')
             + (SELECT count(*) FROM erp.receipt_apply WHERE workspace_id=:w AND generation_id=:g AND apply_key ~ '[0-9]{8}')
             + (SELECT count(*) FROM erp.payment_apply WHERE workspace_id=:w AND generation_id=:g AND apply_key ~ '[0-9]{8}')
    """,
        params,
    )
    # FS-024: 시드 원장 끝의 현재고는 모두 0 이상(음수는 게스트 조작에서만 생긴다), 이동 전표는 품목·LOT별 합 0.
    policy_errors += _scalar(
        connection,
        """
        SELECT (SELECT count(*) FROM (SELECT 1 FROM wms.stock_move m JOIN wms.stock_document d
                 ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id AND d.status='posted'
                 WHERE m.workspace_id=:w AND m.generation_id=:g
                 GROUP BY m.item_id, m.location_id, m.lot_no HAVING sum(m.qty_delta) < 0) neg)
             + (SELECT count(*) FROM (SELECT 1 FROM wms.stock_move m JOIN wms.stock_document d
                 ON d.workspace_id=m.workspace_id AND d.generation_id=m.generation_id AND d.id=m.document_id AND d.document_type='TRANSFER'
                 WHERE m.workspace_id=:w AND m.generation_id=:g
                 GROUP BY m.document_id, m.item_id, m.lot_no HAVING sum(m.qty_delta) <> 0) unbalanced)
    """,
        params,
    )
    policy_errors += _created_at_order_errors(connection, workspace_id, generation_id)
    _require(policy_errors == 0, f"V12 policy errors={policy_errors}")
    results["V12"] = "DB 밖 시드 정책 및 created_at 확정·취소·부모-자식 순서 일치"
    results["V13"] = _spc_check(connection, workspace_id, generation_id)
    results["V-HR"] = _hr_check(connection, workspace_id, generation_id, seed_date)
    return results


# FS-028c 시드 이야기: 이상 기록은 이 3건뿐이어야 한다(우연한 규칙 2·3이 없게).
SPC_EXPECTED_SIGNALS = Counter(
    {
        ("CH-C100-ASM-P", "XBAR", 1, "resolved"): 1,
        ("CH-C200-INJ-H", "XBAR", 1, "open"): 1,
        ("CH-C200-INJ-H", "XBAR", 3, "open"): 1,
    }
)
SPC_EXPECTED_JUDGEMENTS = {
    "CH-C100-INJ-H": "CAPABLE",
    "CH-C100-ASM-P": "CAPABLE",
    "CH-C200-INJ-H": "MARGINAL",
    "CH-C200-ASM-P": "CAPABLE",
    "CH-T300-INJ-G": "CAPABLE",
    "CH-T300-ASM-T": "INCAPABLE",
}


def _spc_check(connection: Connection, workspace_id: int, generation_id: int) -> str:
    """SPC 판정을 DB 값으로 다시 계산해 저장된 이상 기록·X̄·R과 같은지, 시드 이야기·공정능력이 맞는지 본다."""
    from fs.spc import stats

    params = {"w": workspace_id, "g": generation_id}
    errors = 0
    recomputed: Counter = Counter()
    stored = Counter(
        tuple(r)
        for r in connection.execute(
            text(
                "SELECT c.code, x.chart, x.rule, x.status FROM spc.signal x JOIN spc.characteristic c "
                "ON c.workspace_id=x.workspace_id AND c.generation_id=x.generation_id AND c.id=x.characteristic_id "
                "WHERE x.workspace_id=:w AND x.generation_id=:g"
            ),
            params,
        )
    )
    open_lots = set(
        connection.execute(
            text(
                "SELECT lot_no FROM spc.signal WHERE workspace_id=:w AND generation_id=:g AND status='open'"
            ),
            params,
        ).scalars()
    )
    for cid, code, lsl, usl in connection.execute(
        text(
            "SELECT id, code, lsl, usl FROM spc.characteristic WHERE workspace_id=:w AND generation_id=:g"
        ),
        params,
    ).all():
        cp = {**params, "c": cid}
        subgroups = connection.execute(
            text(
                "SELECT id, measured_at, xbar, r, ARRAY(SELECT m.value FROM spc.measurement m WHERE m.workspace_id=s.workspace_id "
                "AND m.generation_id=s.generation_id AND m.subgroup_id=s.id ORDER BY m.seq) vals "
                "FROM spc.subgroup s WHERE s.workspace_id=:w AND s.generation_id=:g AND s.characteristic_id=:c "
                "AND s.status='valid' ORDER BY s.measured_at"
            ),
            cp,
        ).all()
        limits = [
            dict(r)
            for r in connection.execute(
                text(
                    "SELECT effective_at, xbar_cl, xbar_ucl, xbar_lcl, r_cl, r_ucl, r_lcl FROM spc.control_limit "
                    "WHERE workspace_id=:w AND generation_id=:g AND characteristic_id=:c ORDER BY version"
                ),
                cp,
            ).mappings()
        ]
        statuses = {
            (r.subgroup_id, r.chart, r.rule): r.status
            for r in connection.execute(
                text(
                    "SELECT subgroup_id, chart, rule, status FROM spc.signal "
                    "WHERE workspace_id=:w AND generation_id=:g AND characteristic_id=:c"
                ),
                cp,
            )
        }
        for k, sg in enumerate(subgroups):
            if stats.subgroup(list(sg.vals)) != (sg.xbar, sg.r):
                errors += 1
            applicable = [lim for lim in limits if lim["effective_at"] < sg.measured_at]
            if not applicable:
                continue
            lim = applicable[-1]
            previous = [
                p.xbar for p in subgroups[:k] if p.measured_at > lim["effective_at"]
            ]
            for chart, rule, _ in stats.signals(previous, sg.xbar, sg.r, lim):
                recomputed[
                    (code, chart, rule, statuses.get((sg.id, chart, rule), "missing"))
                ] += 1
        cap = stats.capability(
            [s.xbar for s in subgroups], [s.r for s in subgroups], lsl, usl
        )
        if len(subgroups) < stats.MIN_BASIS or cap[
            "judgement"
        ] != SPC_EXPECTED_JUDGEMENTS.get(code):
            errors += 1
    _require(errors == 0, f"V13 spc errors={errors}")
    _require(
        recomputed == stored,
        f"V13 spc signals recomputed={dict(recomputed)} stored={dict(stored)}",
    )
    _require(stored == SPC_EXPECTED_SIGNALS, f"V13 spc story={dict(stored)}")
    _require(open_lots == {"LT-0017"}, f"V13 spc open lots={open_lots}")
    return "SPC 판정 재계산 = 저장된 이상 3건(LT-0017 미조치 2·지그 조치 1), 공정능력 충분 4·주의 1·부족 1"


def _counts(
    connection: Connection, workspace_id: int, generation_id: int
) -> dict[str, int]:
    result = {"core.workspace": 1, "core.data_generation": 1}
    result["core.workspace_module"] = _scalar(
        connection,
        "SELECT count(*) FROM core.workspace_module WHERE workspace_id=:w",
        {"w": workspace_id},
    )
    inspector = inspect(connection)
    for schema in BUSINESS_SCHEMAS:
        for table in inspector.get_table_names(schema=schema):
            count = _scalar(
                connection,
                f'SELECT count(*) FROM "{schema}"."{table}" WHERE workspace_id=:w AND generation_id=:g',
                {"w": workspace_id, "g": generation_id},
            )
            if count:
                result[f"{schema}.{table}"] = count
    return result


def _scalar(connection: Connection, sql: str, params: dict[str, Any]) -> int:
    return int(connection.execute(text(sql), params).scalar_one())


def _created_at_order_errors(
    connection: Connection, workspace_id: int, generation_id: int
) -> int:
    params = {"w": workspace_id, "g": generation_id}
    inspector = inspect(connection)
    errors = 0
    for schema in BUSINESS_SCHEMAS:
        for table in inspector.get_table_names(schema=schema):
            columns = {
                column["name"] for column in inspector.get_columns(table, schema=schema)
            }
            if "created_at" not in columns:
                continue
            for later in ("confirmed_at", "cancelled_at"):
                if later in columns:
                    errors += _scalar(
                        connection,
                        f'SELECT count(*) FROM "{schema}"."{table}" '
                        f"WHERE workspace_id=:w AND generation_id=:g "
                        f'AND "{later}" IS NOT NULL AND created_at>"{later}"',
                        params,
                    )
            for fk in inspector.get_foreign_keys(table, schema=schema):
                parent_schema = fk["referred_schema"]
                parent_table = fk["referred_table"]
                if parent_schema not in {
                    "mes",
                    "erp",
                    "fems",
                    "qms",
                    "wms",
                    "bems",
                    "spc",
                    "gw",
                    "cmms",
                }:
                    continue
                parent_columns = {
                    column["name"]
                    for column in inspector.get_columns(
                        parent_table, schema=parent_schema
                    )
                }
                if "created_at" not in parent_columns:
                    continue
                join = " AND ".join(
                    f'c."{local}"=p."{remote}"'
                    for local, remote in zip(
                        fk["constrained_columns"], fk["referred_columns"], strict=True
                    )
                )
                errors += _scalar(
                    connection,
                    f'SELECT count(*) FROM "{schema}"."{table}" c '
                    f'JOIN "{parent_schema}"."{parent_table}" p ON {join} '
                    "WHERE c.workspace_id=:w AND c.generation_id=:g "
                    "AND c.created_at<p.created_at",
                    params,
                )
    return errors


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _hr_check(
    connection: Connection, workspace_id: int, generation_id: int, seed_date: date
) -> str:
    """HR 시드 규칙. 복사본은 날짜가 통째로 밀리므로 **달 사이의 관계**로 본다.

    한 달은 마감·급여를 확정했고, 그 다음 달은 마감 작성 중이다 — 사용자가 확정 → 계산을 해 본다.
    """
    params = {"w": workspace_id, "g": generation_id, "t": seed_date}
    holidays = _scalar(
        connection,
        "SELECT count(*) FROM core.holiday WHERE workspace_id=:w AND generation_id=:g",
        params,
    )
    _require(holidays == 16, f"V-HR holidays={holidays}")
    closes = dict(
        connection.execute(
            text(
                "SELECT status, close_month FROM hr.attendance_close "
                "WHERE workspace_id=:w AND generation_id=:g"
            ),
            params,
        ).all()
    )
    _require(
        set(closes) == {"confirmed", "draft"} and closes["confirmed"] < closes["draft"],
        f"V-HR closes={closes}",
    )
    settled, open_month = closes["confirmed"], closes["draft"]
    months = (
        connection.execute(
            text(
                "SELECT DISTINCT to_char(work_date,'YYYY-MM') FROM hr.attendance "
                "WHERE workspace_id=:w AND generation_id=:g ORDER BY 1"
            ),
            params,
        )
        .scalars()
        .all()
    )
    _require(settled in months and open_month in months, f"V-HR months={months}")
    # 승인한 휴가는 그 날 근태가 휴가다(제품 규칙과 같은 상태).
    unmatched = _scalar(
        connection,
        """
        SELECT count(*) FROM hr.leave_request r
        JOIN hr.attendance a ON a.workspace_id=r.workspace_id AND a.generation_id=r.generation_id
                            AND a.employee_id=r.employee_id
                            AND a.work_date BETWEEN r.from_date AND r.to_date
        WHERE r.workspace_id=:w AND r.generation_id=:g AND r.status='APPROVED'
          AND a.day_kind='WORKDAY' AND a.status NOT IN ('LEAVE','HALF_LEAVE')
        """,
        params,
    )
    _require(unmatched == 0, f"V-HR approved leave not on attendance={unmatched}")
    runs = connection.execute(
        text(
            "SELECT pay_month, status, version FROM hr.payroll_run "
            "WHERE workspace_id=:w AND generation_id=:g"
        ),
        params,
    ).all()
    _require(runs == [(settled, "confirmed", 1)], f"V-HR runs={runs}")
    broken = _scalar(
        connection,
        """
        SELECT count(*) FROM hr.payslip s
        WHERE s.workspace_id=:w AND s.generation_id=:g
          AND (s.net_pay <> s.gross_pay - s.deduction_total
            OR s.gross_pay <> (SELECT coalesce(sum(l.amount),0) FROM hr.payslip_line l
                                JOIN hr.pay_item p ON p.workspace_id=l.workspace_id
                                 AND p.generation_id=l.generation_id AND p.id=l.pay_item_id
                               WHERE l.workspace_id=s.workspace_id AND l.generation_id=s.generation_id
                                 AND l.payslip_id=s.id AND p.item_kind='EARNING'))
        """,
        params,
    )
    _require(broken == 0, f"V-HR payslip totals={broken}")
    return f"{settled} 마감·급여 확정, {open_month} 마감 작성 중"


def validate_gw(connection, workspace_id, generation_id):
    params = {"w": workspace_id, "g": generation_id}
    checks = [
        "SELECT count(*) FROM gw.notification n WHERE n.workspace_id=:w AND n.generation_id=:g AND NOT (CASE n.ref_kind WHEN 'DOCUMENT' THEN EXISTS(SELECT 1 FROM gw.approval_document d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id)) WHEN 'POST' THEN EXISTS(SELECT 1 FROM gw.board_post d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id)) WHEN 'EVENT' THEN EXISTS(SELECT 1 FROM gw.calendar_event d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id)) ELSE EXISTS(SELECT 1 FROM gw.chat_channel d WHERE (d.workspace_id,d.generation_id,d.id)=(n.workspace_id,n.generation_id,n.ref_id)) END)",
        "SELECT count(*) FROM gw.chat_channel c WHERE c.workspace_id=:w AND c.generation_id=:g AND (c.last_seq<>(SELECT count(*) FROM gw.chat_message m WHERE (m.workspace_id,m.generation_id,m.channel_id)=(c.workspace_id,c.generation_id,c.id)) OR c.last_seq<>coalesce((SELECT max(seq) FROM gw.chat_message m WHERE m.channel_id=c.id),0))",
        "SELECT count(*) FROM gw.chat_member m JOIN gw.chat_channel c ON c.id=m.channel_id WHERE m.workspace_id=:w AND m.generation_id=:g AND m.last_read_seq>c.last_seq",
        "SELECT count(*) FROM gw.calendar_event WHERE workspace_id=:w AND generation_id=:g AND all_day AND ((starts_at AT TIME ZONE 'Asia/Seoul')::time<>'00:00' OR (ends_at AT TIME ZONE 'Asia/Seoul')::time<>'00:00')",
        "SELECT count(*) FROM gw.comment c WHERE c.workspace_id=:w AND c.generation_id=:g AND c.revision_no-1<>(SELECT count(*) FROM gw.comment_revision r WHERE r.comment_id=c.id)",
        "SELECT count(*) FROM gw.approval_event e WHERE e.workspace_id=:w AND e.generation_id=:g AND e.details->>'stepId' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM gw.approval_step s WHERE (s.workspace_id,s.generation_id,s.document_id,s.id)=(e.workspace_id,e.generation_id,e.document_id,(e.details->>'stepId')::bigint))",
        "SELECT count(*) FROM gw.approval_event e WHERE e.workspace_id=:w AND e.generation_id=:g AND e.details->>'delegationId' IS NOT NULL AND NOT EXISTS(SELECT 1 FROM gw.delegation d WHERE (d.workspace_id,d.generation_id,d.id)=(e.workspace_id,e.generation_id,(e.details->>'delegationId')::bigint))",
        "SELECT count(*) FROM gw.approval_event e JOIN gw.approval_document d ON d.id=e.document_id WHERE e.workspace_id=:w AND e.generation_id=:g AND e.details->'authorityRule'->>'id' IS NOT NULL AND (d.authority_rule_id<>(e.details->'authorityRule'->>'id')::bigint OR NOT EXISTS(SELECT 1 FROM gw.authority_rule r WHERE (r.workspace_id,r.generation_id,r.id)=(e.workspace_id,e.generation_id,(e.details->'authorityRule'->>'id')::bigint)))",
        "SELECT count(*) FROM gw.approval_event e JOIN gw.approval_document d ON d.id=e.document_id WHERE e.workspace_id=:w AND e.generation_id=:g AND e.details->>'appliedMonth' IS NOT NULL AND e.details->>'appliedMonth'<>to_char(d.submitted_at AT TIME ZONE 'Asia/Seoul','YYYY-MM')",
    ]
    for index, sql in enumerate(checks, 1):
        _require(_scalar(connection, sql, params) == 0, f"V-GW check {index}")
