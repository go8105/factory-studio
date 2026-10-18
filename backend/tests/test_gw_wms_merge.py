"""05: 적용 순서·이름 정규화·데이터 보존. 새 전용 _test DB만 사용한다."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fs.common.db import reset_engine
from fs.hr.work_setup import create_example_company
from seed.generate import create_template
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.fixture
def isolated_database(monkeypatch):
    source = os.environ.get("TEST_DATABASE_URL")
    if not source:
        pytest.skip("TEST_DATABASE_URL is required")
    url = make_url(source)
    assert (url.database or "").endswith("_test")
    name = f"gw_merge_{uuid4().hex}_test"
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    url = url.set(database=name)
    engine = create_engine(url)
    monkeypatch.setenv("DATABASE_URL", url.render_as_string(hide_password=False))
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv(
        "SESSION_SECRET", "synthetic-merge-acceptance-secret-32-characters"
    )
    reset_engine()
    try:
        yield engine
    finally:
        reset_engine()
        engine.dispose()
        with admin.connect() as c:
            c.exec_driver_sql(f'DROP DATABASE "{name}" WITH (FORCE)')
        admin.dispose()


def fingerprint(engine, columns=None):
    """Compare original columns, including business rows, without logging row values."""
    if columns is None:
        inspector = inspect(engine)
        columns = {
            f"{schema}.{table}": [
                x["name"] for x in inspector.get_columns(table, schema)
            ]
            for schema in inspector.get_schema_names()
            if schema not in {"public", "information_schema"}
            and not schema.startswith("pg_")
            for table in inspector.get_table_names(schema)
        }
    result = {}
    with engine.connect() as c:
        for table, names in columns.items():
            fields = ",".join(f'"{n}"' for n in names)
            values = c.exec_driver_sql(
                f"SELECT COALESCE(jsonb_agg(to_jsonb(t) ORDER BY to_jsonb(t)::text),'[]'::jsonb) FROM (SELECT {fields} FROM {table}) t"
            ).scalar_one()
            result[table] = (
                len(values),
                hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest(),
            )
    return columns, result


@pytest.mark.parametrize(
    "first", ["w2b1_wms", "gw_company_identity", "flow_board_custom"]
)
def test_merge_both_existing_branches_preserves_original_data(isolated_database, first):
    engine = isolated_database
    cfg = Config("backend/alembic.ini")
    command.upgrade(cfg, first)
    with engine.begin() as c:
        create_template(c, date(2026, 10, 18))
        co = create_example_company(
            c, "Synthetic-" + uuid4().hex, "Synthetic-" + uuid4().hex
        )
        # New branch data must survive too, not only old/common tables.
        if first == "w2b1_wms":
            c.exec_driver_sql(
                "INSERT INTO wms.lot(workspace_id,generation_id,item_id,lot_no,origin,received_on) SELECT workspace_id,generation_id,id,'MERGE-WITNESS','RECEIPT',CURRENT_DATE FROM wms.item ORDER BY id LIMIT 1"
            )
        if first == "gw_company_identity":
            # Direct fixture creates security history; it grants no production access.
            c.execute(
                text(
                    "INSERT INTO gw.collaboration_settings(workspace_id,generation_id,initialized_by_user_id) SELECT g.workspace_id,g.id,m.user_id FROM core.data_generation g JOIN core.company_member m ON m.workspace_id=g.workspace_id AND m.role='OWNER' WHERE g.workspace_id=:w"
                ),
                {"w": co["companyId"]},
            )
    columns, before = fingerprint(engine)
    command.upgrade(cfg, "head")
    assert fingerprint(engine, columns)[1] == before
    assert (
        subprocess.run(
            [sys.executable, "tools/verify_ddl_matches_schema.py"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    all_columns, integrated = fingerprint(engine)
    # Alembic -1 is ambiguous at a two-parent merge. Exercise only the
    # name normalization inverse, never remove either populated parent.
    path = Path("backend/alembic/versions/20261018_gw_wms_merge.py")
    spec = importlib.util.spec_from_file_location("merge_check", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as c:
        migration.op = Operations(MigrationContext.configure(c))
        migration.downgrade()
    assert fingerprint(engine, all_columns)[1] == integrated
    with engine.begin() as c:
        migration.op = Operations(MigrationContext.configure(c))
        migration.upgrade()
    assert fingerprint(engine, all_columns)[1] == integrated
    assert (
        subprocess.run(
            [sys.executable, "tools/verify_ddl_matches_schema.py"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    with engine.connect() as c:
        assert c.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalars().all() == ["gw_wms_merge"]
