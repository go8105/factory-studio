"""ERP-1b: ERP가 제공·소비하는 교차 조회 함수 (DSN-11 6장).

ERP는 WMS 입고·수불, MES 외주 실적, HR 급여 결과를 읽고, 발주·전표 합계·매출 요약을 내준다.
여기서 보는 것은 **계약**이다: 꺼진 솔루션은 None, 어느 함수도 상대의 행을 바꾸지 않는다(FS-013 §6).
"""

from datetime import date
from decimal import Decimal

import pytest
from fs.common.auth import AuthContext
from fs.erp import interface as erp
from fs.hr import interface as hr
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


def _scope(context):
    return {"w": context.workspace_id, "g": context.generation_id}


def _disable(connection, context, module: str) -> None:
    connection.execute(
        text(
            "UPDATE core.workspace_module SET enabled=false "
            "WHERE workspace_id=:w AND module_key=:m"
        ),
        {"w": context.workspace_id, "m": module},
    )


def test_disabled_solutions_answer_none_not_empty(scoped):
    """꺼진 솔루션은 빈 목록이 아니라 None이다 — '없다'와 '못 본다'는 다르다."""
    engine, context = scoped
    with engine.begin() as c:
        for module in ("erp", "wms", "mes"):
            _disable(c, context, module)
    with engine.connect() as c:
        assert erp.purchase_orders(c, context) is None
        assert erp.journal_summary(c, context, "2026-09") is None
        assert (
            erp.sales_summary(c, context, date(2026, 9, 1), date(2026, 9, 30)) is None
        )
        assert wms.receipts(c, context, date(2026, 9, 1), date(2026, 9, 30)) is None
        assert wms.stock_moves(c, context, "2026-09") is None
        assert mes.subcontract_results(c, context, "2026-09") is None


def test_wms_receipts_give_only_inspected_lines(scoped):
    engine, context = scoped
    with engine.connect() as c:
        rows = wms.receipts(c, context, date(2026, 1, 1), date(2026, 12, 31))
        statuses = c.execute(
            text(
                "SELECT status, count(*) FROM wms.inbound_notice "
                "WHERE workspace_id=:w AND generation_id=:g GROUP BY status"
            ),
            _scope(context),
        ).all()
    assert rows is not None
    inspected = dict(statuses).get("INSPECTED", 0)
    assert len(rows) == inspected
    for notice in rows:
        assert notice["noticeKind"] in ("PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT")
        assert notice["lines"]
        for line in notice["lines"]:
            # 정상·격리를 나눠 준다. 매입 대상은 읽는 쪽이 정한다.
            assert Decimal(line["acceptedQty"]) >= 0
            assert Decimal(line["quarantinedQty"]) >= 0


def test_wms_stock_moves_balance_opening_and_flow(scoped):
    engine, context = scoped
    with engine.connect() as c:
        rows = wms.stock_moves(c, context, "2026-09")
        total = c.execute(
            text(
                "SELECT count(*) FROM wms.item WHERE workspace_id=:w AND generation_id=:g"
            ),
            _scope(context),
        ).scalar_one()
    assert rows is not None and len(rows) == total  # 움직임이 없어도 품목은 모두 준다
    for row in rows:
        opening = Decimal(row["openingQty"])
        closing = Decimal(row["closingQty"])
        assert closing == opening + Decimal(row["inQty"]) - Decimal(row["outQty"])


def test_mes_subcontract_results_only_received(scoped):
    engine, context = scoped
    with engine.connect() as c:
        rows = mes.subcontract_results(c, context, "2026-09")
        pending = c.execute(
            text(
                "SELECT count(*) FROM mes.subcontract_order "
                "WHERE workspace_id=:w AND generation_id=:g AND received_at IS NULL"
            ),
            _scope(context),
        ).scalar_one()
    assert rows is not None
    # 보낸 뒤 아직 받지 않은 건은 치를 금액이 없어 빠진다.
    assert all(r["receivedAt"] for r in rows)
    assert pending >= 0


def test_hr_payroll_runs_feed_the_payroll_entry(scoped):
    """F94 급여 전표가 읽는 모양: 부서·항목별 합계만, 개인 금액은 없다."""
    engine, context = scoped
    with engine.connect() as c:
        run = hr.payroll_runs(c, context, "2026-08")
    assert run is not None and set(run) >= {"month", "confirmed", "lines"}
    for line in run["lines"]:
        assert set(line) >= {"departmentCode", "itemCode", "amount"}
        assert "employeeCode" not in line and "name" not in line


def _purchase_order(connection, context, *, po_no="PO-TEST-1", status="confirmed"):
    scope = _scope(context)
    partner, item = connection.execute(
        text(
            "SELECT (SELECT id FROM erp.partner WHERE workspace_id=:w AND generation_id=:g ORDER BY id LIMIT 1),"
            "       (SELECT id FROM erp.item WHERE workspace_id=:w AND generation_id=:g ORDER BY id LIMIT 1)"
        ),
        scope,
    ).one()
    order_id = connection.execute(
        text(
            "INSERT INTO erp.purchase_order(workspace_id,generation_id,po_no,partner_id,ordered_on,"
            "due_on,currency,supply_amount,tax_amount,total_amount,status,confirmed_at,closed_at) "
            "VALUES (:w,:g,:no,:p,'2026-09-01','2026-09-20','KRW',100000,10000,110000,CAST(:s AS varchar),"
            "CASE WHEN CAST(:s AS varchar)='draft' THEN NULL ELSE now() END,"
            "CASE WHEN CAST(:s AS varchar)='closed' THEN now() END) RETURNING id"
        ),
        {**scope, "no": po_no, "p": partner, "s": status},
    ).scalar_one()
    connection.execute(
        text(
            "INSERT INTO erp.purchase_order_line(workspace_id,generation_id,purchase_order_id,line_no,"
            "item_id,quantity,unit,unit_price,supply_amount,tax_amount,total_amount) "
            "VALUES (:w,:g,:o,1,:i,10,'EA',10000,100000,10000,110000)"
        ),
        {**scope, "o": order_id, "i": item},
    )
    return order_id


def test_purchase_orders_give_confirmed_only_and_no_progress(scoped):
    engine, context = scoped
    with engine.begin() as c:
        _purchase_order(c, context, po_no="PO-DRAFT", status="draft")
        _purchase_order(c, context, po_no="PO-OPEN")
        _purchase_order(c, context, po_no="PO-CLOSED", status="closed")
    with engine.connect() as c:
        open_only = erp.purchase_orders(c, context)
        every = erp.purchase_orders(c, context, open_only=False)
    assert [o["poNo"] for o in open_only] == ["PO-OPEN"]
    assert sorted(o["poNo"] for o in every) == ["PO-CLOSED", "PO-OPEN"]
    order = open_only[0]
    assert order["lines"][0]["quantity"] == "10.000"
    # 입고 진행은 WMS가 안다. 여기에 두면 두 곳이 어긋난다.
    assert not any(k in order for k in ("receivedQty", "openQty", "progress"))


def _journal(connection, context, *, entry_no, status="confirmed", amount=50000):
    scope = _scope(context)
    account = connection.execute(
        text(
            "SELECT id FROM erp.account WHERE workspace_id=:w AND generation_id=:g ORDER BY id LIMIT 1"
        ),
        scope,
    ).scalar_one()
    entry = connection.execute(
        text(
            "INSERT INTO erp.journal_entry(workspace_id,generation_id,entry_no,entry_date,entry_kind,"
            "description,currency,status,confirmed_at) "
            "VALUES (:w,:g,:no,'2026-09-15','GENERAL','합성 전표','KRW',CAST(:s AS varchar),"
            "CASE WHEN CAST(:s AS varchar)='draft' THEN NULL ELSE now() END) RETURNING id"
        ),
        {**scope, "no": entry_no, "s": status},
    ).scalar_one()
    for line_no, side in ((1, "DEBIT"), (2, "CREDIT")):
        connection.execute(
            text(
                "INSERT INTO erp.journal_line(workspace_id,generation_id,journal_entry_id,line_no,"
                "account_id,side,amount) VALUES (:w,:g,:e,:n,:a,:side,:amount)"
            ),
            {
                **scope,
                "e": entry,
                "n": line_no,
                "a": account,
                "side": side,
                "amount": amount,
            },
        )


def test_journal_summary_counts_confirmed_and_reversed_only(scoped):
    engine, context = scoped
    with engine.begin() as c:
        _journal(c, context, entry_no="JE-DRAFT", status="draft")
        _journal(c, context, entry_no="JE-OK")
        _journal(c, context, entry_no="JE-REV", status="reversed", amount=20000)
    with engine.connect() as c:
        summary = erp.journal_summary(c, context, "2026-09")
        other = erp.journal_summary(c, context, "2026-10")
    assert summary["month"] == "2026-09" and summary["accounts"]
    row = summary["accounts"][0]
    # 초안은 빠지고, 역분개된 전표와 역분개 전표는 둘 다 센다(정정은 지우는 것이 아니다).
    assert Decimal(row["debit"]) == Decimal(70000)
    assert Decimal(row["credit"]) == Decimal(70000)
    assert other["accounts"] == []


def test_sales_summary_separates_period_sales_from_open_receivable(scoped):
    engine, context = scoped
    with engine.connect() as c:
        summary = erp.sales_summary(c, context, date(2026, 1, 1), date(2026, 12, 31))
        narrow = erp.sales_summary(c, context, date(2026, 1, 1), date(2026, 1, 2))
    assert set(summary) >= {"salesAmount", "salesCount", "receivableOpen", "partners"}
    assert summary["salesCount"] == sum(p["salesCount"] for p in summary["partners"])
    assert Decimal(summary["salesAmount"]) == sum(
        Decimal(p["amount"]) for p in summary["partners"]
    )
    # 채권 미수는 기간이 아니라 지금 남은 금액이라 기간을 좁혀도 같다.
    assert narrow["receivableOpen"] == summary["receivableOpen"]
    assert narrow["salesCount"] <= summary["salesCount"]
