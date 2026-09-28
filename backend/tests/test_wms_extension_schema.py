"""FS-026a DB constraints only. No claim of receiving/reservation API coverage."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def scoped_db(guest_space):
    _, created, engine = guest_space
    with engine.connect() as connection:
        tx = connection.begin()
        scope = {"w": created["workspaceId"], "g": created["generationId"]}
        scope["wh"] = connection.execute(
            text(
                "SELECT id FROM wms.warehouse WHERE workspace_id=:w AND generation_id=:g LIMIT 1"
            ),
            scope,
        ).scalar_one()
        scope["item"] = connection.execute(
            text(
                "SELECT id FROM wms.item WHERE workspace_id=:w AND generation_id=:g AND item_class='RAW' LIMIT 1"
            ),
            scope,
        ).scalar_one()
        scope["loc"] = connection.execute(
            text(
                "SELECT id FROM wms.storage_location WHERE workspace_id=:w AND generation_id=:g AND is_default LIMIT 1"
            ),
            scope,
        ).scalar_one()
        yield connection, scope
        tx.rollback()


def notice(c, s):
    return c.execute(
        text(
            "INSERT INTO wms.inbound_notice (workspace_id,generation_id,warehouse_id,notice_no,business_key,expected_on) VALUES (:w,:g,:wh,:n,:n,current_date) RETURNING id"
        ),
        {**s, "n": str(uuid4())},
    ).scalar_one()


def reservation(c, s):
    return c.execute(
        text(
            "INSERT INTO wms.stock_reservation (workspace_id,generation_id,reservation_no,business_key) VALUES (:w,:g,:n,:n) RETURNING id"
        ),
        {**s, "n": str(uuid4())},
    ).scalar_one()


def rejected(c, sql, params):
    with pytest.raises(IntegrityError), c.begin_nested():
        c.execute(text(sql), params)


def test_inspection_quantity_all_or_none_and_conservation(scoped_db):
    c, s = scoped_db
    s["n"] = notice(c, s)
    base = "INSERT INTO wms.inbound_notice_line (workspace_id,generation_id,notice_id,line_no,item_id,normal_location_id,expected_qty,accepted_qty,quarantined_qty,shortage_qty,reason) VALUES (:w,:g,:n,1,:item,:loc,100,:a,:q,:short,'검증')"
    for a, q, short in [(95, 0, 2), (None, 0, 100), (101, 0, -1)]:
        rejected(c, base, {**s, "a": a, "q": q, "short": short})
    c.execute(text(base), {**s, "a": 0, "q": 0, "short": 100})
    c.execute(
        text(
            "UPDATE wms.inbound_notice SET status='INSPECTED',arrived_at=now(),inspected_at=now() WHERE id=:n"
        ),
        s,
    )
    assert (
        c.execute(
            text("SELECT stock_document_id FROM wms.inbound_notice WHERE id=:n"), s
        ).scalar_one()
        is None
    )


def test_claim_unique_until_release(scoped_db):
    c, s = scoped_db
    s.update(n=notice(c, s), key="ERP:PURCHASE:TEST", digest="a" * 64)
    sql = "INSERT INTO wms.source_claim (workspace_id,generation_id,notice_id,source_key,source_snapshot,source_digest) VALUES (:w,:g,:n,:key,'{}',:digest)"
    c.execute(text(sql), s)
    other = {**s, "n": notice(c, s)}
    rejected(c, sql, other)
    c.execute(
        text(
            "UPDATE wms.source_claim SET status='RELEASED',closed_at=now(),release_reason='재연결' WHERE workspace_id=:w AND generation_id=:g AND source_key=:key"
        ),
        s,
    )
    c.execute(text(sql), other)
    rejected(c, sql, {**other, "key": "ERP:PURCHASE:OTHER"})


def test_null_lot_duplicate_allocation_is_rejected(scoped_db):
    c, s = scoped_db
    s["r"] = reservation(c, s)
    sql = "INSERT INTO wms.stock_reservation_line (workspace_id,generation_id,reservation_id,line_no,item_id,location_id,quantity) VALUES (:w,:g,:r,:line,:item,:loc,1)"
    c.execute(text(sql), {**s, "line": 1})
    rejected(c, sql, {**s, "line": 2})
    s["r"] = reservation(c, s)
    c.execute(text(sql), {**s, "line": 1})


def test_incomplete_consumption_and_default_quarantine_rejected(scoped_db):
    c, s = scoped_db
    s["r"] = reservation(c, s)
    rejected(
        c,
        "UPDATE wms.stock_reservation SET status='CONSUMED',closed_at=now(),shipment_source_key='ERP:SHIPMENT:TEST' WHERE id=:r",
        s,
    )
    rejected(
        c, "UPDATE wms.storage_location SET location_type='QUARANTINE' WHERE id=:loc", s
    )
    rejected(
        c,
        "UPDATE wms.stock_reservation SET status='RELEASED',closed_at=now() WHERE id=:r",
        s,
    )


def test_cross_generation_fk_and_restrict(scoped_db):
    c, s = scoped_db
    s["n"] = notice(c, s)
    rejected(c, "UPDATE wms.inbound_notice SET generation_id=-1 WHERE id=:n", s)
    rejected(c, "DELETE FROM wms.warehouse WHERE id=:wh", s)


def test_inspection_document_and_default_location_compatibility(scoped_db):
    c, s = scoped_db
    assert (
        c.execute(
            text("SELECT location_type FROM wms.storage_location WHERE id=:loc"), s
        ).scalar_one()
        == "NORMAL"
    )
    c.execute(
        text(
            "INSERT INTO wms.stock_document (workspace_id,generation_id,document_no,document_type,status,source_key,document_on,document_month,posted_at) VALUES (:w,:g,'WD-FS026-TEST','WMS_INSPECTION','posted','WMS:INSPECTION:TEST',current_date,to_char(current_date,'YYYY-MM'),now())"
        ),
        s,
    )
    rejected(
        c,
        "INSERT INTO wms.stock_document (workspace_id,generation_id,document_no,document_type,status,document_on,document_month) VALUES (:w,:g,'WD-FS026-BAD','WMS_INSPECTION','draft',current_date,to_char(current_date,'YYYY-MM'))",
        s,
    )


def test_downgrade_guard_preserves_business_data(scoped_db):
    import importlib.util
    from pathlib import Path

    from sqlalchemy.exc import DBAPIError

    c, s = scoped_db
    s["n"] = notice(c, s)
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260928_fs026a_wms_receiving_reservation.py"
    )
    spec = importlib.util.spec_from_file_location("fs026_migration_test", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with pytest.raises(DBAPIError, match="downgrade refused"), c.begin_nested():
        c.exec_driver_sql(migration.DOWNGRADE_SQL[0])
    assert (
        c.execute(
            text("SELECT count(*) FROM wms.inbound_notice WHERE id=:n"), s
        ).scalar_one()
        == 1
    )
