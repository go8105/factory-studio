"""FS-018e 에너지 목표 비율표 (FS-005g 5.5, sv-20260924-2). 검증 항목마다 테스트를 나눈다.

test_seed.py(antigravity 소유)의 V8은 비율표 적용만 확인한다. 여기서는 새 규칙 자체를 본다.
"""

from datetime import date
from decimal import Decimal

import pytest
from seed.common import TARGET_RATIOS, month_text
from seed.generate import create_template
from sqlalchemy import Engine, text

SEED_DATE = date(2026, 9, 24)


@pytest.fixture
def template(clean_database: Engine):
    with clean_database.begin() as connection:
        create_template(connection, SEED_DATE)
        workspace_id, generation_id = connection.execute(
            text(
                "SELECT id, active_generation_id FROM core.workspace "
                "WHERE workspace_kind='TEMPLATE'"
            )
        ).one()
    return clean_database, {"w": workspace_id, "g": generation_id}


def _rows(engine: Engine, params, sql: str, **extra):
    with engine.connect() as connection:
        return connection.execute(text(sql), {**params, **extra}).all()


def test_ratios_stay_within_90_to_105_percent():
    ratios = [r for pair in TARGET_RATIOS.values() for r in pair]
    assert min(ratios) >= Decimal("0.90") and max(ratios) <= Decimal("1.05")


def test_ratios_are_not_all_equal():
    assert len({r for pair in TARGET_RATIOS.values() for r in pair}) > 5


def test_equipment_targets_mix_achieved_and_exceeded(template):
    engine, params = template
    rows = _rows(
        engine,
        params,
        """
        SELECT t.target_value >= sum(a.quantity)
        FROM fems.energy_target t
        JOIN fems.energy_allocation a
          ON a.workspace_id=t.workspace_id AND a.generation_id=t.generation_id
         AND a.equipment_id=t.equipment_id AND a.method_key='DIRECT_METER'
         AND to_char(a.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM')=t.target_month
        WHERE t.workspace_id=:w AND t.generation_id=:g AND t.target_scope='EQUIPMENT'
        GROUP BY t.id, t.target_value
        """,
    )
    achieved = {row[0] for row in rows}
    assert achieved == {True, False}


def test_site_electricity_target_uses_ratio_table(template):
    engine, params = template
    month = month_text(SEED_DATE, -1)
    (target, actual) = _rows(
        engine,
        params,
        """
        SELECT t.target_value,
               (SELECT sum(r.value) FROM fems.energy_reading r
                JOIN fems.meter_channel c ON c.id=r.meter_channel_id
                WHERE r.workspace_id=:w AND r.generation_id=:g AND c.channel_code='CH-MAIN-KWH'
                  AND r.quality<>'invalid'
                  AND to_char(r.period_start AT TIME ZONE 'Asia/Seoul','YYYY-MM')=:m)
        FROM fems.energy_target t JOIN fems.energy_source s ON s.id=t.energy_source_id
        WHERE t.workspace_id=:w AND t.generation_id=:g AND t.target_scope='SITE'
          AND s.source_code='ELEC' AND t.target_month=:m
        """,
        m=month,
    )[0]
    assert target == (actual * TARGET_RATIOS["ELEC"][0]).quantize(Decimal("0.000001"))


def test_target_row_count_is_unchanged(template):
    engine, params = template
    (count,) = _rows(
        engine,
        params,
        "SELECT count(*) FROM fems.energy_target WHERE workspace_id=:w AND generation_id=:g",
    )[0]
    assert count == 23


def test_ins02_current_month_target_stays_unset(template):
    engine, params = template
    rows = _rows(
        engine,
        params,
        """
        SELECT 1 FROM fems.energy_target t JOIN fems.equipment e ON e.id=t.equipment_id
        WHERE t.workspace_id=:w AND t.generation_id=:g
          AND e.equipment_code='INS-02' AND t.target_month=:m
        """,
        m=month_text(SEED_DATE, 0),
    )
    assert rows == []
