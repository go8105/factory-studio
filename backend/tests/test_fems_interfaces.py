"""FEMS-1b: FEMS가 읽을 교차 조회 함수 (DSN-15 6장).

FEMS는 MES에서 **설비·품목별 생산량**을 읽어 원단위의 분모로 쓰고(F51·Q3), 설비 부서 코드는
HR에서 읽는다. 설계서 §6은 부서를 ERP라고 적었지만 부서 표는 `hr.department` 하나뿐이고
HR이 이미 제공한다(DSN-30 Q1) — 설계서 오류라 HR을 쓴다.

여기서 보는 것은 **계약**이다: 꺼진 솔루션은 None, 켜진 솔루션은 코드 문자열 스냅샷.
어느 함수도 상대 솔루션의 행을 바꾸지 않는다(FS-013 §6).
"""

from datetime import date
from decimal import Decimal

import pytest
from fs.common.auth import AuthContext
from fs.fems import interface as fems
from fs.hr import interface as hr
from fs.mes import interface as mes
from sqlalchemy import text


@pytest.fixture
def scoped(guest_space):
    _, created, engine = guest_space
    context = AuthContext(
        actor_kind="GUEST",
        actor_key="test",
        workspace_id=created["workspaceId"],
        generation_id=created["generationId"],
        user_id=None,
        roles=("GUEST",),
        token=None,
    )
    return engine, context


def _module(connection, context, key: str, enabled: bool) -> None:
    connection.execute(
        text(
            "UPDATE core.workspace_module SET enabled=:on "
            "WHERE workspace_id=:w AND module_key=:k"
        ),
        {"on": enabled, "w": context.workspace_id, "k": key},
    )


def _busy_month(connection, context) -> str:
    """실적이 가장 많은 달. 시드 날짜가 밀려도 테스트가 따라간다."""
    return connection.execute(
        text(
            "SELECT to_char(confirmed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM') m "
            "FROM mes.operation_result WHERE workspace_id=:w AND generation_id=:g "
            "GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
        ),
        {"w": context.workspace_id, "g": context.generation_id},
    ).scalar_one()


def test_readers_return_none_when_source_is_off(scoped):
    """꺼진 솔루션은 빈 목록이 아니라 None이다 — '없음'과 '꺼짐'은 다르다."""
    engine, context = scoped
    with engine.begin() as c:
        _module(c, context, "mes", False)
        _module(c, context, "hr", False)
        assert mes.production_results(c, context, "2026-01") is None
        assert hr.departments(c, context) is None


def test_production_results_are_good_qty_per_equipment_and_item(scoped):
    """원단위 분모는 설비·품목별 **양품** 수량이다. 투입량도 산출량도 아니다."""
    engine, context = scoped
    with engine.begin() as c:
        month = _busy_month(c, context)
        rows = mes.production_results(c, context, month)
        assert rows, "시드에 확정 실적이 있어야 한다"
        expected = c.execute(
            text(
                "SELECT sum(r.good_qty) FROM mes.operation_result r "
                "WHERE r.workspace_id=:w AND r.generation_id=:g "
                "  AND to_char(r.confirmed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM')=:m"
            ),
            {"w": context.workspace_id, "g": context.generation_id, "m": month},
        ).scalar_one()
        assert sum(Decimal(r["goodQty"]) for r in rows) == expected
        # 설비·품목·단위마다 한 줄이고 줄이 겹치지 않는다.
        keys = [(r["equipmentCode"], r["itemCode"], r["unit"]) for r in rows]
        assert len(keys) == len(set(keys))
        for row in rows:
            assert Decimal(row["goodQty"]) >= 0
            assert row["resultCount"] >= 1
            assert row["firstConfirmedAt"] <= row["lastConfirmedAt"]


def test_production_results_stay_inside_the_month(scoped):
    """달 경계는 반개구간이다. 다른 달 실적이 섞이면 원단위가 틀린다."""
    engine, context = scoped
    with engine.begin() as c:
        month = _busy_month(c, context)
        total = sum(
            Decimal(r["goodQty"]) for r in mes.production_results(c, context, month)
        )
        months = c.execute(
            text(
                "SELECT DISTINCT to_char(confirmed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM') m "
                "FROM mes.operation_result WHERE workspace_id=:w AND generation_id=:g "
                "ORDER BY 1"
            ),
            {"w": context.workspace_id, "g": context.generation_id},
        ).scalars()
        every = sum(
            sum(Decimal(r["goodQty"]) for r in mes.production_results(c, context, m))
            for m in months
        )
        assert total < every or len(list(months)) == 1


def test_production_results_are_empty_not_none_for_a_quiet_month(scoped):
    """실적이 없는 달은 None이 아니라 빈 목록이다 — MES는 켜져 있다."""
    engine, context = scoped
    with engine.begin() as c:
        assert mes.production_results(c, context, "1999-01") == []


def test_departments_are_the_source_of_department_codes(scoped):
    """설비 부서 코드(DSN-15 F06)는 HR에서 온다. ERP에는 부서 표가 없다."""
    engine, context = scoped
    with engine.begin() as c:
        rows = hr.departments(c, context)
        assert rows, "시드에 부서가 있어야 한다"
        codes = [r["code"] for r in rows]
        assert len(codes) == len(set(codes))
        assert all(r["name"] for r in rows)
        # 상위 부서도 같은 목록 안의 코드다 — FEMS가 코드만 스냅샷으로 들고 간다.
        parents = {r["parentCode"] for r in rows if r["parentCode"]}
        assert parents <= set(codes)


# ---- 1b(BEMS): 시간별 요율 ----


def _electric_tariff(connection, context) -> dict:
    return (
        connection.execute(
            text(
                "SELECT t.id, t.tariff_code, t.usage_rate, t.effective_from, t.basic_charge "
                "FROM fems.tariff t JOIN fems.energy_source e ON e.workspace_id=t.workspace_id "
                " AND e.generation_id=t.generation_id AND e.id=t.energy_source_id "
                "WHERE t.workspace_id=:w AND t.generation_id=:g AND e.source_kind='ELECTRIC' "
                " AND e.is_billable ORDER BY t.effective_from DESC LIMIT 1"
            ),
            {"w": context.workspace_id, "g": context.generation_id},
        )
        .mappings()
        .one()
    )


def test_tariff_rates_is_none_when_fems_is_off(scoped):
    engine, context = scoped
    with engine.begin() as c:
        _module(c, context, "fems", False)
        assert fems.tariff_rates(c, context, "2026-01") is None


def test_flat_tariff_gives_the_usage_rate_for_every_hour(scoped):
    engine, context = scoped
    with engine.begin() as c:
        tariff = _electric_tariff(c, context)
        month = tariff["effective_from"]
        rows = fems.tariff_rates(c, context, month)
        assert len(rows) == 1 and rows[0]["kind"] == "FLAT"
        assert rows[0]["tariffCode"] == tariff["tariff_code"]
        days = rows[0]["rates"]
        assert len(days) in (28, 29, 30, 31) and all(
            len(v) == 24 for v in days.values()
        )
        assert {Decimal(x) for v in days.values() for x in v} == {tariff["usage_rate"]}
        assert Decimal(rows[0]["basicCharge"]) == tariff["basic_charge"]
        assert rows[0]["contractKw"] is None


def test_tou_rates_follow_day_kind_and_holiday_beats_saturday(scoped):
    """휴일 > 토요일 > 평일. 휴일이 토요일과 겹치면 휴일 요율이다(FEMS 요금 산정과 같은 규칙)."""
    engine, context = scoped
    with engine.begin() as c:
        tariff = _electric_tariff(c, context)
        month = tariff["effective_from"]
        c.execute(
            text(
                "UPDATE fems.tariff SET tariff_kind='TOU', contract_kw=300 WHERE id=:id"
            ),
            {"id": tariff["id"]},
        )
        for season in ("SUMMER", "SPRING_FALL", "WINTER"):
            for day_kind, load_band, rate in (
                ("WEEKDAY", "PEAK", 100),
                ("SATURDAY", "MID", 70),
                ("HOLIDAY", "OFF_PEAK", 40),
            ):
                c.execute(
                    text(
                        "INSERT INTO fems.tariff_band (workspace_id,generation_id,tariff_id,season,"
                        " day_kind,hour_from,hour_to,load_band,rate) "
                        "VALUES (:w,:g,:t,:season,:kind,0,24,:band,:rate)"
                    ),
                    {
                        "w": context.workspace_id,
                        "g": context.generation_id,
                        "t": tariff["id"],
                        "season": season,
                        "kind": day_kind,
                        "band": load_band,
                        "rate": rate,
                    },
                )
        year, mon = int(month[:4]), int(month[5:])
        days = [date(year, mon, d) for d in range(1, 29)]
        weekday = next(d for d in days if d.weekday() == 1)
        saturday = next(d for d in days if d.weekday() == 5)
        sunday = next(d for d in days if d.weekday() == 6)
        holiday_on_weekday = next(d for d in days if d.weekday() == 2)
        holiday_on_saturday = next(
            d for d in days if d.weekday() == 5 and d != saturday
        )
        for day in (holiday_on_weekday, holiday_on_saturday):
            c.execute(
                text(
                    "INSERT INTO core.holiday (workspace_id,generation_id,holiday_on,name,kind) "
                    "VALUES (:w,:g,:d,'테스트','COMPANY') ON CONFLICT DO NOTHING"
                ),
                {"w": context.workspace_id, "g": context.generation_id, "d": day},
            )
        rows = fems.tariff_rates(c, context, month)
        rates = rows[0]["rates"]
        assert rows[0]["kind"] == "TOU" and rows[0]["contractKw"] == "300.00"

        def one(day: date) -> Decimal:
            assert len({Decimal(x) for x in rates[day.isoformat()]}) == 1
            return Decimal(rates[day.isoformat()][0])

        assert one(weekday) == 100
        assert one(saturday) == 70
        assert one(sunday) == 40  # 달력에 없어도 일요일은 휴일
        assert one(holiday_on_weekday) == 40
        assert one(holiday_on_saturday) == 40  # 휴일이 토요일보다 세다


def test_tariff_rates_skip_a_month_without_a_tariff(scoped):
    engine, context = scoped
    with engine.begin() as c:
        assert fems.tariff_rates(c, context, "1999-01") == []
