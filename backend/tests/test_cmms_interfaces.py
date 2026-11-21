"""CMMS-1b: CMMS가 읽을 교차 조회 함수 (DSN-21 6장).

CMMS는 설비·금형·공조기를 대장으로 가져오고, 환경 경보·설비 원인 이상을 전환 대기 신호로 읽고,
예비품 재고를 WMS에서 본다. 여기서 보는 것은 **계약**이다 — 꺼진 솔루션은 None, 켜진 솔루션은
코드 문자열 스냅샷. 어느 함수도 상대 솔루션의 행을 바꾸지 않는다(FS-013 §6).
"""

import pytest
from fs.bems import interface as bems
from fs.common.auth import AuthContext
from fs.erp import interface as erp
from fs.mes import interface as mes
from fs.spc import interface as spc
from fs.wms import interface as wms
from sqlalchemy import text

MODULES = ("mes", "bems", "wms", "spc", "erp")


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


def _module(connection, scoped_context, key: str, enabled: bool) -> None:
    connection.execute(
        text(
            "UPDATE core.workspace_module SET enabled=:on "
            "WHERE workspace_id=:w AND module_key=:k"
        ),
        {"on": enabled, "w": scoped_context.workspace_id, "k": key},
    )


def test_every_reader_returns_none_when_source_is_off(scoped):
    """꺼진 솔루션은 빈 목록이 아니라 None이다 — 호출 쪽이 '없음'과 '꺼짐'을 구분해야 한다."""
    engine, context = scoped
    with engine.begin() as c:
        for key in MODULES:
            _module(c, context, key, False)
        assert mes.equipment(c, context) is None
        assert mes.molds(c, context) is None
        assert bems.hvac_units(c, context) is None
        assert bems.active_alarms(c, context) is None
        assert wms.stock_on_hand(c, context, ["ANY"]) is None
        assert wms.supply_items(c, context) is None
        assert spc.equipment_signals(c, context) is None
        assert erp.partners(c, context) is None
        assert not bems.enabled(c, context) and not wms.enabled(c, context)


def test_mes_equipment_and_molds_are_code_snapshots(scoped):
    """설비·금형은 코드와 이름만 넘긴다. 금형 타수는 누적이라 타수 주기 PM의 '현재 사용량'이 된다."""
    engine, context = scoped
    with engine.begin() as c:
        equipment = mes.equipment(c, context)
        assert equipment, "시드에 설비가 있어야 한다"
        assert {"equipmentCode", "name", "equipmentType", "locationCode"} == set(
            equipment[0]
        )
        assert all(isinstance(e["equipmentCode"], str) for e in equipment)
        assert [e["equipmentCode"] for e in equipment] == sorted(
            e["equipmentCode"] for e in equipment
        )

        molds = mes.molds(c, context)
        assert molds is not None
        assert all(m["status"] != "RETIRED" for m in molds)
        if molds:
            assert {
                "moldCode",
                "name",
                "cavity",
                "lifeShots",
                "shots",
                "status",
            } == set(molds[0])
            recorded = c.execute(
                text(
                    "SELECT COALESCE(sum(u.shots),0) FROM mes.mold_usage u "
                    "JOIN mes.mold m ON m.id=u.mold_id "
                    "WHERE u.workspace_id=:w AND u.generation_id=:g AND m.code=:code"
                ),
                {
                    "w": context.workspace_id,
                    "g": context.generation_id,
                    "code": molds[0]["moldCode"],
                },
            ).scalar_one()
            assert molds[0]["shots"] == str(recorded)


def test_bems_alarms_stay_until_cleared(scoped):
    """확인(acknowledged)은 '봤다'일 뿐이라 전환 대상에서 빠지지 않는다. 해제된 것만 빠진다."""
    engine, context = scoped
    with engine.begin() as c:
        units = bems.hvac_units(c, context)
        assert units and {"code", "name", "zoneCode", "zoneName", "ratedKw"} == set(
            units[0]
        )

        # (규칙, 센서)마다 미해제 경보는 1건뿐이다(UK_PARTIAL). 상태별로 다른 짝을 쓴다.
        pairs = c.execute(
            text(
                "SELECT r.id rule_id, s.id sensor_id FROM bems.sensor s "
                "JOIN bems.alarm_rule r ON r.workspace_id=s.workspace_id "
                " AND r.generation_id=s.generation_id AND r.zone_id=s.zone_id "
                "   AND r.metric=s.metric "
                "WHERE s.workspace_id=:w AND s.generation_id=:g "
                "  AND NOT EXISTS (SELECT 1 FROM bems.alarm a WHERE a.workspace_id=s.workspace_id "
                "    AND a.generation_id=s.generation_id AND a.alarm_rule_id=r.id "
                "    AND a.sensor_id=s.id AND a.status <> 'cleared') LIMIT 3"
            ),
            {"w": context.workspace_id, "g": context.generation_id},
        ).all()
        if len(pairs) < 3:
            pytest.skip("미해제 경보가 없는 (규칙, 센서) 짝이 3개 미만이다")

        before = len(bems.active_alarms(c, context))
        states = (
            ("raised", "NULL", "NULL"),
            ("acknowledged", "now()", "NULL"),
            ("cleared", "now()", "now()"),
        )
        ids = [
            c.execute(
                text(
                    "INSERT INTO bems.alarm(workspace_id,generation_id,alarm_rule_id,sensor_id,"
                    "status,raised_at,peak_value,acknowledged_at,cleared_at) "
                    f"VALUES (:w,:g,:r,:s,:st,now(),'30.0',{ack},{cleared}) RETURNING id"
                ),
                {
                    "w": context.workspace_id,
                    "g": context.generation_id,
                    "r": pair.rule_id,
                    "s": pair.sensor_id,
                    "st": status,
                },
            ).scalar_one()
            for pair, (status, ack, cleared) in zip(pairs, states, strict=True)
        ]
        alarms = bems.active_alarms(c, context)
        found = {a["alarmId"] for a in alarms}
        assert str(ids[0]) in found and str(ids[1]) in found  # raised·acknowledged
        assert str(ids[2]) not in found  # cleared
        assert len(alarms) == before + 2
        assert {"alarmId", "status", "metric", "severity", "zoneCode"} <= set(alarms[0])


def test_spc_equipment_signals_are_open_only(scoped):
    """미조치 이상만 넘긴다. 조치·무효는 전환 대상이 아니다."""
    engine, context = scoped
    with engine.begin() as c:
        signals = spc.equipment_signals(c, context)
        assert signals is not None
        open_count = c.execute(
            text(
                "SELECT count(*) FROM spc.signal "
                "WHERE workspace_id=:w AND generation_id=:g AND status='open'"
            ),
            {"w": context.workspace_id, "g": context.generation_id},
        ).scalar_one()
        assert len(signals) == open_count
        if signals:
            assert {"signalId", "equipmentCode", "lotNo", "chart", "rule"} <= set(
                signals[0]
            )
            assert all(s["equipmentCode"] for s in signals)


def test_wms_stock_is_read_not_stored(scoped):
    """재고는 stock_move 합이다. 안전 재고가 없으면 부족이라고 말하지 않는다."""
    engine, context = scoped
    with engine.begin() as c:
        supplies = wms.supply_items(c, context)
        assert supplies is not None
        assert wms.stock_on_hand(c, context, []) == {}
        assert wms.stock_on_hand(c, context, ["NO-SUCH-CODE"]) == {}

        if supplies:
            code = supplies[0]["itemCode"]
            stock = wms.stock_on_hand(c, context, [code])
            assert set(stock) == {code}
            row = stock[code]
            moved = c.execute(
                text(
                    "SELECT COALESCE(sum(m.qty_delta),0) FROM wms.stock_move m "
                    "JOIN wms.item i ON i.id=m.item_id "
                    "WHERE m.workspace_id=:w AND m.generation_id=:g AND i.item_code=:code"
                ),
                {
                    "w": context.workspace_id,
                    "g": context.generation_id,
                    "code": code,
                },
            ).scalar_one()
            assert row["qtyOnHand"] == f"{moved:.3f}"
            assert row["isShort"] == (
                row["safetyStock"] is not None
                and float(row["qtyOnHand"]) < float(row["safetyStock"])
            )


def test_erp_partners_can_be_narrowed_to_suppliers(scoped):
    """외주 업체는 매입하는 거래처만 고른다 — BOTH도 매입처다(DSN-11 F02)."""
    engine, context = scoped
    with engine.begin() as c:
        every = erp.partners(c, context)
        suppliers = erp.partners(c, context, "SUPPLIER")
        assert every is not None and suppliers is not None
        assert all(p["partnerKind"] in ("SUPPLIER", "BOTH") for p in suppliers)
        assert {p["partnerKind"] for p in suppliers} == {"SUPPLIER", "BOTH"}
        assert len(suppliers) < len(every)
        assert {"partnerCode", "partnerName", "partnerKind"} == set(suppliers[0])


def test_readers_do_not_change_the_source(scoped):
    """조회는 상대 솔루션의 행을 바꾸지 않는다(FS-013 §6)."""
    engine, context = scoped
    counts = (
        "SELECT (SELECT count(*) FROM bems.alarm WHERE workspace_id=:w), "
        "(SELECT count(*) FROM spc.signal WHERE workspace_id=:w), "
        "(SELECT count(*) FROM wms.stock_move WHERE workspace_id=:w)"
    )
    with engine.begin() as c:
        before = c.execute(text(counts), {"w": context.workspace_id}).one()
        bems.active_alarms(c, context)
        spc.equipment_signals(c, context)
        mes.equipment(c, context)
        mes.molds(c, context)
        wms.supply_items(c, context)
        after = c.execute(text(counts), {"w": context.workspace_id}).one()
    assert before == after
