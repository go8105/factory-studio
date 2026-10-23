"""QMS-1b: QMS가 읽을 교차 조회 함수 (DSN-14 6장).

QMS는 WMS에서 격리된 입고 줄을 수입 검사 대상으로 읽고, MES에서 공정 불량·공정 검사·LOT 계보를
읽는다. 여기서 보는 것은 **계약**이다 — 꺼진 솔루션은 None, 켜진 솔루션은 코드 문자열 스냅샷.
어느 함수도 상대 솔루션의 행을 바꾸지 않는다(FS-013 §6).
"""

import pytest
from fs.common.auth import AuthContext
from fs.mes import interface as mes
from fs.wms import interface as wms
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
    """불량 실적이 가장 많은 달. 시드 날짜가 밀려도 테스트가 따라간다."""
    return connection.execute(
        text(
            "SELECT to_char(confirmed_at AT TIME ZONE 'Asia/Seoul', 'YYYY-MM') m "
            "FROM mes.operation_result WHERE workspace_id=:w AND generation_id=:g "
            "  AND defect_qty > 0 GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
        ),
        {"w": context.workspace_id, "g": context.generation_id},
    ).scalar_one()


def test_readers_return_none_when_source_is_off(scoped):
    """꺼진 솔루션은 빈 목록이 아니라 None이다 — 호출 쪽이 '없음'과 '꺼짐'을 구분해야 한다."""
    engine, context = scoped
    with engine.begin() as c:
        _module(c, context, "wms", False)
        _module(c, context, "mes", False)
        assert wms.inbound_lots_to_inspect(c, context) is None
        assert wms.lots(c, context) is None
        assert mes.defects(c, context, "2026-01") is None
        assert mes.process_inspections(c, context, "2026-01") is None
        assert mes.lot_trace(c, context, "ANY") is None


def test_inbound_lots_to_inspect_is_quarantined_lines_only(scoped):
    """검수에서 격리된 줄만 검사 대상이다. 원천은 공지 번호:줄 번호로 집는다."""
    engine, context = scoped
    with engine.begin() as c:
        rows = wms.inbound_lots_to_inspect(c, context)
        expected = c.execute(
            text(
                "SELECT count(*) FROM wms.inbound_notice n "
                "JOIN wms.inbound_notice_line l ON l.workspace_id=n.workspace_id "
                " AND l.generation_id=n.generation_id AND l.notice_id=n.id "
                "WHERE n.workspace_id=:w AND n.generation_id=:g "
                "  AND n.status='INSPECTED' AND l.quarantined_qty > 0"
            ),
            {"w": context.workspace_id, "g": context.generation_id},
        ).scalar_one()
    assert len(rows) == expected > 0
    row = rows[0]
    assert row["sourceRef"] == f"{row['noticeNo']}:" + row["sourceRef"].split(":")[1]
    assert float(row["qty"]) > 0
    assert row["noticeKind"] in ("PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT")
    assert len({r["sourceRef"] for r in rows}) == len(rows)


def test_lots_filters_by_item_code(scoped):
    """LOT 대장은 품목으로 거른다. 시드에 LOT이 없어 합성 LOT 1건을 넣고 계약만 본다."""
    engine, context = scoped
    with engine.begin() as c:
        p = {"w": context.workspace_id, "g": context.generation_id}
        item = (
            c.execute(
                text(
                    "SELECT id, item_code FROM wms.item "
                    "WHERE workspace_id=:w AND generation_id=:g ORDER BY item_code LIMIT 1"
                ),
                p,
            )
            .mappings()
            .one()
        )
        c.execute(
            text(
                "INSERT INTO wms.lot(workspace_id,generation_id,item_id,lot_no,origin,"
                "received_on,status) VALUES (:w,:g,:i,'QMS-TEST-LOT','RECEIPT',"
                "DATE '2026-09-20','AVAILABLE')"
            ),
            {**p, "i": item["id"]},
        )
        every = wms.lots(c, context)
        one = wms.lots(c, context, item["item_code"])
        assert wms.lots(c, context, "없는품목") == []
    assert len(every) == len(one) == 1
    assert one[0]["lotNo"] == "QMS-TEST-LOT"
    assert one[0]["origin"] == "RECEIPT" and one[0]["status"] == "AVAILABLE"
    assert one[0]["receivedOn"] == "2026-09-20" and one[0]["expiryDate"] is None


def _defect_code(connection, context, code: str) -> int:
    """시드에 불량 코드가 없다. 코드가 붙은 불량을 만들어 계약을 본다."""
    return connection.execute(
        text(
            "INSERT INTO mes.defect_code(workspace_id,generation_id,code,name,category) "
            "VALUES (:w,:g,:c,'시험 불량','APPEARANCE') RETURNING id"
        ),
        {"w": context.workspace_id, "g": context.generation_id, "c": code},
    ).scalar_one()


def test_defects_groups_by_result_and_stays_in_month(scoped):
    """불량 실적은 공정 실적 1건이 1행이고, 코드가 여러 개 붙어도 행이 늘지 않는다."""
    engine, context = scoped
    with engine.begin() as c:
        p = {"w": context.workspace_id, "g": context.generation_id}
        month = _busy_month(c, context)
        result_id = c.execute(
            text(
                "SELECT r.id FROM mes.operation_result r WHERE r.workspace_id=:w "
                "  AND r.generation_id=:g AND r.defect_qty > 0 "
                "  AND to_char(r.confirmed_at AT TIME ZONE 'Asia/Seoul','YYYY-MM')=:m "
                "ORDER BY r.id LIMIT 1"
            ),
            {**p, "m": month},
        ).scalar_one()
        for code, qty in (("QMS-TEST-A", "1.000"), ("QMS-TEST-B", "2.000")):
            c.execute(
                text(
                    "INSERT INTO mes.operation_defect(workspace_id,generation_id,"
                    "operation_result_id,defect_code_id,qty,disposition,decided_at) "
                    "VALUES (:w,:g,:r,:c,:q,'SCRAP',now())"
                ),
                {**p, "r": result_id, "c": _defect_code(c, context, code), "q": qty},
            )
        rows = mes.defects(c, context, month)
        other = mes.defects(c, context, "1999-01")
    assert rows and other == []
    assert all(r["confirmedAt"][:7] == month for r in rows)
    assert all(float(r["defectQty"]) > 0 for r in rows)
    assert len({(r["lotNo"], r["processCode"], r["confirmedAt"]) for r in rows}) == len(
        rows
    )
    coded = [r for r in rows if r["codes"]]
    assert len(coded) == 1 and len(coded[0]["codes"]) == 2
    assert coded[0]["codes"][0] == {
        "defectCode": "QMS-TEST-A",
        "defectName": "시험 불량",
        "category": "APPEARANCE",
        "qty": "1.000",
        "disposition": "SCRAP",
    }


def test_process_inspections_returns_confirmed_only(scoped):
    """확정본만 집계에 들어간다. draft는 번복될 수 있어 뺀다."""
    engine, context = scoped
    with engine.begin() as c:
        p = {"w": context.workspace_id, "g": context.generation_id}
        month = _busy_month(c, context)
        rows = (
            c.execute(
                text(
                    "SELECT e.id, r.confirmed_at FROM mes.operation_execution e "
                    "JOIN mes.operation_result r ON r.workspace_id=e.workspace_id "
                    " AND r.generation_id=e.generation_id AND r.execution_id=e.id "
                    "WHERE e.workspace_id=:w AND e.generation_id=:g "
                    "  AND to_char(r.confirmed_at AT TIME ZONE 'Asia/Seoul','YYYY-MM')=:m "
                    "ORDER BY e.id LIMIT 2"
                ),
                {**p, "m": month},
            )
            .mappings()
            .all()
        )
        for row, status in zip(rows, ("confirmed", "draft"), strict=True):
            c.execute(
                text(
                    "INSERT INTO mes.process_inspection(workspace_id,generation_id,"
                    "execution_id,timing,inspected_at,result,status) "
                    "VALUES (:w,:g,:e,'FIRST',:at,:res,:st)"
                ),
                {
                    **p,
                    "e": row["id"],
                    "at": row["confirmed_at"],
                    "res": "FAIL" if status == "confirmed" else None,
                    "st": status,
                },
            )
        found = mes.process_inspections(c, context, month)
        assert mes.process_inspections(c, context, "1999-01") == []
    assert len(found) == 1
    assert found[0]["timing"] == "FIRST" and found[0]["result"] == "FAIL"
    assert found[0]["failCount"] == 0 and found[0]["lotNo"] and found[0]["processCode"]


def test_lot_trace_reads_materials_and_kin(scoped):
    """LOT 계보는 투입 자재와 분할·재작업 관계까지 따라간다. 없는 LOT은 None."""
    engine, context = scoped
    with engine.begin() as c:
        p = {"w": context.workspace_id, "g": context.generation_id}
        parent, child = (
            c.execute(
                text(
                    "SELECT t.id, t.lot_no, t.unit FROM mes.lot t "
                    "WHERE t.workspace_id=:w AND t.generation_id=:g "
                    "  AND EXISTS (SELECT 1 FROM mes.operation_execution e "
                    "    JOIN mes.material_issue mi ON mi.workspace_id=e.workspace_id "
                    "     AND mi.generation_id=e.generation_id AND mi.execution_id=e.id "
                    "    WHERE e.workspace_id=t.workspace_id "
                    "      AND e.generation_id=t.generation_id AND e.lot_id=t.id) "
                    "ORDER BY t.id LIMIT 2"
                ),
                p,
            )
            .mappings()
            .all()
        )
        c.execute(
            text(
                "INSERT INTO mes.lot_genealogy(workspace_id,generation_id,parent_lot_id,"
                "child_lot_id,relation,qty,unit,related_at) "
                "VALUES (:w,:g,:p,:c,'SPLIT',5,:u,now())"
            ),
            {**p, "p": parent["id"], "c": child["id"], "u": parent["unit"]},
        )
        trace = mes.lot_trace(c, context, parent["lot_no"])
        down = mes.lot_trace(c, context, child["lot_no"])
        assert mes.lot_trace(c, context, "없는LOT") is None
        assert mes.enabled(c, context)
    assert trace["lotNo"] == parent["lot_no"] and trace["itemCode"]
    assert trace["materials"] and all(m["itemCode"] for m in trace["materials"])
    assert [k["lotNo"] for k in trace["children"]] == [child["lot_no"]]
    assert trace["children"][0]["relation"] == "SPLIT"
    assert trace["parents"] == [] and trace["usedIn"] == []
    assert [k["lotNo"] for k in down["parents"]] == [parent["lot_no"]]
