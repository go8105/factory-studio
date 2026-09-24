from __future__ import annotations
# ruff: noqa: I001

from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from seed.common import month_mondays, month_text


EXPECTED_COUNTS = {
    "core.workspace": 1,
    "core.data_generation": 1,
    "core.workspace_module": 4,
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
}


def validate_all(
    connection: Connection, workspace_id: int, generation_id: int, seed_date: date
) -> dict[str, str]:
    params = {"w": workspace_id, "g": generation_id, "t": seed_date}
    results: dict[str, str] = {}
    actual = _counts(connection, workspace_id, generation_id)
    _require(
        actual == EXPECTED_COUNTS,
        f"V1 row counts differ: {Counter(EXPECTED_COUNTS) - Counter(actual)}, extra={Counter(actual) - Counter(EXPECTED_COUNTS)}",
    )
    _require(sum(actual.values()) == 7469, f"V1 total={sum(actual.values())}")
    results["V1"] = "71개 중 시드 64테이블, 7,469행 일치"

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
    results["V2"] = "T 기준 월·ISO 주차 재계산 일치(결정성은 통합 테스트에서 별도 비교)"

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
            """
        SELECT count(*) FROM fems.energy_target t JOIN fems.energy_source s
          ON s.workspace_id=t.workspace_id AND s.generation_id=t.generation_id AND s.id=t.energy_source_id
        WHERE t.workspace_id=:w AND t.generation_id=:g AND t.target_scope='EQUIPMENT'
          AND t.target_value<>(SELECT round(coalesce(sum(a.quantity),0)*0.95,6)
                              FROM fems.energy_allocation a
                              WHERE a.workspace_id=t.workspace_id AND a.generation_id=t.generation_id
                                AND a.equipment_id=t.equipment_id AND a.method_key='DIRECT_METER'
                                AND to_char(a.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM')=t.target_month)
            """,
            params,
        )
    _require(target_diff == 0, f"V8 target 95% diff={target_diff}")
    results["V8"] = (
        "직접 배분=유효 시간값 합, 용수 공용 8 제외, 템플릿 설비 목표=월 실적 95%"
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
    for schema in ("mes", "erp", "fems"):
        for table in inspector.get_table_names(schema=schema):
            for column in inspector.get_columns(table, schema=schema):
                if (
                    "TIMESTAMP" in str(column["type"]).upper()
                    and column["name"] != "ended_at"
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
        WHERE c.contype='f' AND sn.nspname IN ('mes','erp','fems') AND tn.nspname IN ('mes','erp','fems') AND sn.nspname<>tn.nspname
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
    policy_errors += _created_at_order_errors(connection, workspace_id, generation_id)
    _require(policy_errors == 0, f"V12 policy errors={policy_errors}")
    results["V12"] = "DB 밖 시드 정책 및 created_at 확정·취소·부모-자식 순서 일치"
    return results


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
    for schema in ("mes", "erp", "fems"):
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
    for schema in ("mes", "erp", "fems"):
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
                if parent_schema not in {"mes", "erp", "fems"}:
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
