"""FEMS-1b: FEMS가 읽을 교차 조회 함수 (DSN-15 6장).

FEMS는 MES에서 **설비·품목별 생산량**을 읽어 원단위의 분모로 쓰고(F51·Q3), 설비 부서 코드는
HR에서 읽는다. 설계서 §6은 부서를 ERP라고 적었지만 부서 표는 `hr.department` 하나뿐이고
HR이 이미 제공한다(DSN-30 Q1) — 설계서 오류라 HR을 쓴다.

여기서 보는 것은 **계약**이다: 꺼진 솔루션은 None, 켜진 솔루션은 코드 문자열 스냅샷.
어느 함수도 상대 솔루션의 행을 바꾸지 않는다(FS-013 §6).
"""

from decimal import Decimal

import pytest
from fs.common.auth import AuthContext
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
