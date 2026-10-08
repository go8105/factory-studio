from __future__ import annotations
# ruff: noqa: I001

import json
import os
import statistics
from collections import Counter
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from collections.abc import Generator

import pytest
from sqlalchemy import create_engine, inspect, text

from seed.common import equipment_ratio_sql, month_mondays, month_text
from seed.copy import copy_template
from seed.generate import create_template
from seed.validate import (
    DATE_VARYING,
    EXPECTED_COUNTS,
    _counts,
    _created_at_order_errors,
    _scalar,
    validate_all,
)
from fs.common.modules import BUSINESS_SCHEMAS


URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is required", allow_module_level=True)

engine = create_engine(URL)


def _reset() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspector.get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )


def _snapshot(workspace_id: int, generation_id: int) -> bytes:
    content: dict[str, object] = {}
    with engine.connect() as connection:
        for name in EXPECTED_COUNTS:
            schema, table = name.split(".")
            where = "id=:w" if name == "core.workspace" else "workspace_id=:w"
            params = {"w": workspace_id, "g": generation_id}
            columns = {
                row["name"]
                for row in inspect(connection).get_columns(table, schema=schema)
            }
            if name == "core.data_generation":
                where += " AND id=:g"
            elif "generation_id" in columns:
                where += " AND generation_id=:g"
            rows = (
                connection.execute(
                    text(
                        f'SELECT * FROM "{schema}"."{table}" WHERE {where} ORDER BY id'
                    ),
                    params,
                )
                .mappings()
                .all()
            )
            content[name] = [dict(row) for row in rows]
    return json.dumps(
        content, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")
    ).encode()


@dataclass
class SeedFixtureData:
    first_snapshot: bytes
    second_snapshot: bytes
    template_workspace_id: int
    template_generation_id: int
    seed_date: date
    calendar_t1: tuple[int, int, date]
    calendar_t2: tuple[int, int, date]
    benchmark_timings: list[float]
    benchmark_targets: list[str]


@pytest.fixture(scope="module")
def seed_env() -> Generator[SeedFixtureData]:
    seed_date = date(2026, 9, 23)
    _reset()
    with engine.begin() as connection:
        workspace_id, generation_id, counts = create_template(connection, seed_date)
        # W1c: HR 시드 + 공통 휴일. 근태·명세 줄은 기준일에 따라 달라져 하한만 본다.
        fixed = sum(
            value
            for name, value in counts.items()
            if name not in ("hr.attendance", "hr.payslip_line")
        )
        # 14,795(검증기 기준) + core.holiday 16 — 휴일은 core라 validate의 표 수에 안 들어간다.
        assert (
            fixed == 14811
        )  # SPC +2,752, gw·cmms·hr 모듈 행 +3, HR 시드 +107, 휴일 +16
        assert counts["hr.attendance"] > 0 and counts["hr.payslip_line"] > 0
    first_snapshot = _snapshot(workspace_id, generation_id)

    _reset()
    with engine.begin() as connection:
        workspace_id, generation_id, _ = create_template(connection, seed_date)
    second_snapshot = _snapshot(workspace_id, generation_id)

    timings = []
    targets = [date(2026, 10, 7), date(2027, 1, 5)] + [
        date(2026, 10, 8 + index) for index in range(10)
    ]
    copied = []
    for index, target in enumerate(targets):
        with engine.begin() as connection:
            copied_workspace, copied_generation, counts, elapsed = copy_template(
                connection, workspace_id, generation_id, target, f"fs015-test-{index}"
            )
            fixed_copy = sum(
                value
                for name, value in counts.items()
                if name not in ("hr.attendance", "hr.payslip_line")
            )
            # 템플릿과 같되 core.workspace·data_generation 2행이 빠지고 휴일 16행이 더해진다.
            assert fixed_copy == 14809  # SPC +2,752, HR 시드 +107, 휴일 +16
            copied.append((copied_workspace, copied_generation, target))
            if index >= 2:
                timings.append(elapsed)

    yield SeedFixtureData(
        first_snapshot=first_snapshot,
        second_snapshot=second_snapshot,
        template_workspace_id=workspace_id,
        template_generation_id=generation_id,
        seed_date=seed_date,
        calendar_t1=copied[0],
        calendar_t2=copied[1],
        benchmark_timings=timings,
        benchmark_targets=[target.isoformat() for _, _, target in copied[:2]],
    )
    _reset()


def test_seed_determinism(seed_env: SeedFixtureData) -> None:
    assert seed_env.first_snapshot == seed_env.second_snapshot


def test_seed_v1_row_counts(seed_env: SeedFixtureData) -> None:
    with engine.connect() as connection:
        actual = _counts(
            connection, seed_env.template_workspace_id, seed_env.template_generation_id
        )
        # 근태·명세 줄은 기준일에 따라 행 수가 달라진다(검증기와 같은 기준).
        varying = {name: actual.pop(name, 0) for name in DATE_VARYING}
        assert actual == EXPECTED_COUNTS, (
            f"V1 row counts differ: {Counter(EXPECTED_COUNTS) - Counter(actual)}, extra={Counter(actual) - Counter(EXPECTED_COUNTS)}"
        )
        assert sum(actual.values()) == 14795, f"V1 total={sum(actual.values())}"
        assert all(varying.values()), f"V1 date-varying empty: {varying}"


def test_seed_v2_calendar_months_and_weeks(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
        plans = connection.execute(
            text(
                "SELECT plan_code,target_month FROM erp.sales_plan WHERE workspace_id=:w AND generation_id=:g ORDER BY target_month"
            ),
            params,
        ).all()
        assert plans == [
            (
                f"SP-{month_text(seed_env.seed_date, -1)}",
                month_text(seed_env.seed_date, -1),
            ),
            (f"SP-{month_text(seed_env.seed_date)}", month_text(seed_env.seed_date)),
        ], f"V2 calendar={plans}"

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
        assert set(weeks) == set(
            month_mondays(seed_env.seed_date, -1) + month_mondays(seed_env.seed_date)
        ), f"V2 weeks={weeks}"


def test_seed_v3_code_dictionary_consistency(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
        mismatch = connection.execute(
            text("""
            SELECT count(*) FROM mes.item m JOIN erp.item e USING (workspace_id,generation_id,item_code)
            WHERE m.workspace_id=:w AND m.generation_id=:g AND (m.name,m.item_type,m.base_unit) IS DISTINCT FROM (e.name,e.item_type,e.base_unit)
        """),
            params,
        ).scalar_one()
        assert mismatch == 0, f"V3 item mismatch={mismatch}"
        assert (
            _scalar(
                connection,
                "SELECT count(*) FROM mes.item WHERE workspace_id=:w AND generation_id=:g",
                params,
            )
            == 6
        ), "V3 mes item count"


def test_seed_v4_equipment_execution_no_overlaps(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert overlaps == 0, f"V4 overlaps={overlaps}"


def test_seed_v5_process_chain_input_equals_prev_good(
    seed_env: SeedFixtureData,
) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert chain_errors == 0, f"V5 chain errors={chain_errors}"


def test_seed_v6_packing_lot_limit(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert packed_over == 0, f"V6 packed over={packed_over}"


def test_seed_v7_production_record_sources(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert (source_versions, distinct_sources) == (
            27,
            26,
        ), f"V7 records={(source_versions, distinct_sources)}"


def test_seed_v8_energy_allocation_and_equipment_targets(
    seed_env: SeedFixtureData,
) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert direct_diff == 0, f"V8 direct diff={direct_diff}"
        workspace_kind = connection.execute(
            text("SELECT workspace_kind FROM core.workspace WHERE id=:w"), params
        ).scalar_one()
        target_diff = 0
        if workspace_kind == "TEMPLATE":
            target_diff = _scalar(
                connection,
                f"""
            WITH ratio(code, month, ratio) AS (VALUES {equipment_ratio_sql(seed_env.seed_date)})
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
        assert target_diff == 0, f"V8 target ratio diff={target_diff}"


def test_seed_v9_money_apply_limits(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        assert money_errors == 0, f"V9 apply errors={money_errors}"


def test_seed_v10_timestamps_upper_bound(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    future = 0
    with engine.connect() as connection:
        inspector = inspect(connection)
        for schema in BUSINESS_SCHEMAS:
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
        assert future == 0, f"V10 future timestamps={future}"


def test_seed_v11_cross_schema_fk_zero(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
        cross_fks = _scalar(
            connection,
            """
            SELECT count(*) FROM pg_constraint c JOIN pg_class s ON s.oid=c.conrelid JOIN pg_namespace sn ON sn.oid=s.relnamespace
            JOIN pg_class t ON t.oid=c.confrelid JOIN pg_namespace tn ON tn.oid=t.relnamespace
            WHERE c.contype='f' AND sn.nspname IN ('mes','erp','fems') AND tn.nspname IN ('mes','erp','fems') AND sn.nspname<>tn.nspname
        """,
            params,
        )
        assert cross_fks == 0, f"V11 cross schema FK={cross_fks}"


def test_seed_v12_policy_and_created_at_order(seed_env: SeedFixtureData) -> None:
    params = {
        "w": seed_env.template_workspace_id,
        "g": seed_env.template_generation_id,
        "t": seed_env.seed_date,
    }
    with engine.connect() as connection:
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
        policy_errors += _created_at_order_errors(
            connection,
            seed_env.template_workspace_id,
            seed_env.template_generation_id,
        )
        assert policy_errors == 0, f"V12 policy errors={policy_errors}"


def test_seed_calendar_t1_2026_10_07(seed_env: SeedFixtureData) -> None:
    ws_id, gen_id, target = seed_env.calendar_t1
    with engine.connect() as connection:
        results = validate_all(connection, ws_id, gen_id, target)
        assert len(results) == 14  # W1c: V-HR 추가


def test_seed_calendar_t2_2027_01_05(seed_env: SeedFixtureData) -> None:
    ws_id, gen_id, target = seed_env.calendar_t2
    with engine.connect() as connection:
        results = validate_all(connection, ws_id, gen_id, target)
        assert len(results) == 14  # W1c: V-HR 추가


@pytest.mark.perf
def test_seed_copy_performance_benchmark(
    seed_env: SeedFixtureData, tmp_path: Path
) -> None:
    report = {
        "runs": len(seed_env.benchmark_timings),
        "median_seconds": statistics.median(seed_env.benchmark_timings),
        "max_seconds": max(seed_env.benchmark_timings),
        "targets_verified": seed_env.benchmark_targets,
    }
    (tmp_path / "benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    assert report["runs"] == 10
    assert report["max_seconds"] < 2
