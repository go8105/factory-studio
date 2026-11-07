"""BEMS-1b: BEMS가 제공·소비하는 교차 조회 함수 (DSN-16 6장).

BEMS는 core 휴일 달력과 FEMS 시간별 요율을 읽고, 확정한 월간 보고서를 EIP에 내준다.
여기서 보는 것은 **계약**이다: 꺼진 솔루션은 None, 어느 함수도 상대의 행을 바꾸지 않는다(FS-013 §6).
"""

from datetime import date

import pytest
from fs.bems import interface as bems
from fs.common.auth import AuthContext
from fs.core import interface as core
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


def _scope(context):
    return {"w": context.workspace_id, "g": context.generation_id}


def _holiday(connection, context, day: date, name: str = "테스트") -> None:
    connection.execute(
        text(
            "INSERT INTO core.holiday (workspace_id,generation_id,holiday_on,name,kind) "
            "VALUES (:w,:g,:day,:name,'COMPANY') "
            "ON CONFLICT (workspace_id,generation_id,holiday_on) DO UPDATE SET name=:name"
        ),
        {**_scope(context), "day": day, "name": name},
    )


def test_holidays_are_listed_by_date_with_kind(scoped):
    engine, context = scoped
    with engine.begin() as c:
        _holiday(c, context, date(2031, 5, 6), "창립기념일")
        _holiday(c, context, date(2031, 5, 2), "임시 휴무")
        rows = core.holidays(c, context, date(2031, 5, 1), date(2031, 5, 31))
        assert [r["date"] for r in rows] == ["2031-05-02", "2031-05-06"]
        assert rows[1] == {
            "date": "2031-05-06",
            "name": "창립기념일",
            "kind": "COMPANY",
        }


def test_holidays_include_both_ends_and_exclude_outside(scoped):
    engine, context = scoped
    with engine.begin() as c:
        for day in (date(2032, 3, 1), date(2032, 3, 31), date(2032, 4, 1)):
            _holiday(c, context, day)
        rows = core.holidays(c, context, date(2032, 3, 1), date(2032, 3, 31))
        assert [r["date"] for r in rows] == ["2032-03-01", "2032-03-31"]


def _review(connection, context, month, version, status, kwh):
    connection.execute(
        text(
            "INSERT INTO bems.energy_review (workspace_id,generation_id,review_month,version,status,"
            " total_kwh,eui_kwh_m2,total_cost,currency,confirmed_at) "
            "VALUES (:w,:g,:month,:version,CAST(:status AS varchar),:kwh,1.5,100000,'KRW',"
            " CASE WHEN CAST(:status AS varchar)='draft' THEN NULL ELSE now() END)"
        ),
        {
            **_scope(context),
            "month": month,
            "version": version,
            "status": status,
            "kwh": kwh,
        },
    )


def test_monthly_summary_is_none_when_bems_is_off(scoped):
    engine, context = scoped
    with engine.begin() as c:
        c.execute(
            text(
                "UPDATE core.workspace_module SET enabled=false "
                "WHERE workspace_id=:w AND module_key='bems'"
            ),
            {"w": context.workspace_id},
        )
        assert bems.monthly_summary(c, context, "2031-05") is None


def test_monthly_summary_without_a_confirmed_review_is_none_not_zero(scoped):
    """'쓰지 않았다'와 '아직 안 만들었다'를 섞지 않는다 — 초안만 있어도 값이 없다."""
    engine, context = scoped
    with engine.begin() as c:
        _review(c, context, "2031-05", 1, "draft", 500)
        summary = bems.monthly_summary(c, context, "2031-05")
        assert summary["month"] == "2031-05"
        assert set(summary["metrics"].values()) == {None}
        assert set(summary["metrics"]) == {
            "commonKwh",
            "euiKwhPerM2",
            "commonCost",
            "targetAchievement",
            "comfortRatio",
        }


def test_monthly_summary_reads_only_the_latest_confirmed_version(scoped):
    engine, context = scoped
    with engine.begin() as c:
        _review(c, context, "2031-06", 1, "superseded", 100)
        _review(c, context, "2031-06", 2, "confirmed", 200)
        _review(c, context, "2031-06", 3, "draft", 999)
        metrics = bems.monthly_summary(c, context, "2031-06")["metrics"]
        assert metrics["commonKwh"] == "200.00"
        assert metrics["euiKwhPerM2"] == "1.5000"
        assert metrics["targetAchievement"] is None
