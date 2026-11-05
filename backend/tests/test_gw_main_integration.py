"""Pinned-parent upgrade witnesses and transactional name-only integration checks."""

# ruff: noqa: F401,F811
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import event, text
from sqlalchemy.exc import DBAPIError
from test_gw_wms_merge import fingerprint, isolated_database

ROOT = Path(__file__).resolve().parents[2]


def migration():
    path = ROOT / "backend/alembic/versions/20261105_gw_main_ready02_merge.py"
    spec = importlib.util.spec_from_file_location("gw_main_merge_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def object_names(engine):
    with engine.connect() as c:
        return c.exec_driver_sql(
            "SELECT n.nspname,c.relname,c.oid FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname IN ('core','gw') ORDER BY 1,2"
        ).all(), c.exec_driver_sql(
            "SELECT conrelid,conname,oid,conindid,pg_get_constraintdef(oid) FROM pg_constraint WHERE connamespace IN ('core'::regnamespace,'gw'::regnamespace) ORDER BY 1,2"
        ).all()


@pytest.mark.parametrize("pin", ["4c898ac", "783a2c1"])
def test_pinned_parent_data_survives_upgrade(isolated_database, tmp_path, pin):
    engine = isolated_database
    # Export only the immutable pin, under this repository's ignored work tree.
    source = tmp_path / pin
    source.mkdir()
    archive = subprocess.run(
        ["git", "archive", pin, "backend", "tools", "docs/db/schema-metadata"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    subprocess.run(["tar", "-x", "-C", str(source)], input=archive, check=True)
    child = source / "backend/tests/test_upgrade_witness.py"
    common = """
import os
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, text
from alembic import command
from alembic.config import Config
from seed.generate import create_template
import fs
assert Path(fs.__file__).resolve().is_relative_to(Path.cwd())
"""
    if pin == "4c898ac":
        body = """
from test_gw_company_acceptance import ten_people
from test_gw_company_work import api
from test_gw_evidence import prepare
import test_gw_evidence
import pyotp
from uuid import uuid4
@pytest.fixture
def isolated_database():
    engine = create_engine(os.environ["DATABASE_URL"])
    yield engine
    engine.dispose()
def test_seed(ten_people, monkeypatch):
    engine, co, clients, people, bindings, passwords = ten_people
    admin = clients[0]
    start = admin.post("/api/v1/core/security/enrollment/start", json={"password":passwords[0]}, headers={"X-CSRF-Token":admin.csrf})
    assert start.status_code == 200
    setup = start.json()["data"]
    confirmed = admin.post("/api/v1/core/security/enrollment/confirm", json={"factorId":setup["factorId"],"code":pyotp.TOTP(setup["setupKey"]).now()}, headers={"X-CSRF-Token":admin.csrf})
    assert confirmed.status_code == 200
    challenge = admin.post("/api/v1/core/sessions", json={"loginId":"synthetic-owner","password":passwords[0]}, headers={"Idempotency-Key":str(uuid4())})
    assert challenge.status_code == 202
    with engine.begin() as c:
        c.exec_driver_sql("UPDATE core.mfa_factor SET last_used_step=NULL WHERE state='ACTIVE'")
    signedin = admin.post("/api/v1/core/security/login/verify", json={"code":pyotp.TOTP(setup["setupKey"]).now()}, headers={"X-CSRF-Token":challenge.json()["data"]["challengeCsrfToken"]})
    assert signedin.status_code == 201
    admin.csrf = signedin.json()["data"]["csrfToken"]
    owner = next(p for p in people if p["code"] == "SYN-001")
    monkeypatch.setattr(test_gw_evidence,"initialize",lambda env:owner["id"])
    monkeypatch.setattr(test_gw_evidence,"connect_staff",lambda env:None)
    envelope, signed = prepare((engine,co,admin,clients[1]),monkeypatch)
    for state in ("PASS","FAIL"):
        data = envelope | {"runId":str(uuid4()),"result":state}
        assert api(admin,co,"operating-evidence",signed(data)).status_code == 200
    assert api(clients[1],co,"operating-evidence",method="GET").status_code == 403
    assert not api(admin,co,"operations",method="GET").json()["data"]["ready"]
    with engine.connect() as c:
        assert c.scalar(text("SELECT count(*) FROM core.mfa_factor WHERE state='ACTIVE'")) == 1
        assert c.scalar(text("SELECT count(*) FROM core.recovery_code")) > 0
"""
    else:
        body = """
from fs.hr.work_setup import create_example_company
def test_seed():
    command.upgrade(Config("backend/alembic.ini"),"head")
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as c:
        create_template(c,date(2026,10,18))
        create_example_company(c,"Synthetic-upgrade-owner","Synthetic-upgrade-password")
        c.exec_driver_sql("INSERT INTO core.auth_session(user_id,token_hash,csrf_token_hash,expires_at) SELECT id,'synthetic-upgrade-session','synthetic-upgrade-csrf',clock_timestamp()+interval '1 hour' FROM core.app_user ORDER BY id LIMIT 1")
        c.exec_driver_sql("INSERT INTO cmms.asset(workspace_id,generation_id,code,name,asset_type,source) SELECT workspace_id,id,'UPGRADE-WITNESS','Synthetic asset','OTHER','CMMS' FROM core.data_generation ORDER BY id LIMIT 1")
        c.exec_driver_sql("INSERT INTO qms.gauge(workspace_id,generation_id,code,name,gauge_kind,calibration_cycle_days) SELECT workspace_id,id,'UPGRADE-WITNESS','Synthetic gauge','Synthetic',30 FROM core.data_generation ORDER BY id LIMIT 1")
        assert c.scalar(text("SELECT count(*) FROM cmms.asset")) > 0
        assert c.scalar(text("SELECT count(*) FROM qms.gauge")) > 0
    engine.dispose()
"""
    child.write_text(common + body)
    env = os.environ | {
        "DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "TEST_DATABASE_URL": engine.url.render_as_string(hide_password=False),
        "PYTHONPATH": os.pathsep.join(
            str(source / p) for p in ("backend/src", "backend", "backend/tests")
        ),
        "COOKIE_SECURE": "false",
        "FS_SECURITY_MODE": "TEAM_TEST",
        "SESSION_SECRET": "synthetic-upgrade-session-secret-32-characters",
    }
    import json

    from cryptography.fernet import Fernet

    env["FS_SECURITY_KEYS"] = json.dumps({"v1": Fernet.generate_key().decode()})
    env["FS_SECURITY_KEY_ID"] = "v1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(child), "-q", "--tb=short"],
        cwd=source,
        env=env,
        capture_output=True,
        check=False,
    )
    # Private test failure details, never account/key material on stdout.
    (tmp_path / "pinned-seed.log").write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, "pinned witness failed; inspect private work log"
    columns, before = fingerprint(engine)
    command.upgrade(Config("backend/alembic.ini"), "head")
    assert fingerprint(engine, columns)[1] == before
    module = migration()
    identities = object_names(engine)
    with engine.begin() as c:
        module.op = Operations(MigrationContext.configure(c))
        module.downgrade()
    assert fingerprint(engine, columns)[1] == before
    with engine.begin() as c:
        module.op = Operations(MigrationContext.configure(c))
        module.upgrade()
    assert object_names(engine) == identities
    assert fingerprint(engine, columns)[1] == before
    with engine.connect() as c:
        assert (
            c.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one()
            == "gw_main_ready02_merge"
        )
        if pin == "783a2c1":
            assert set(
                c.exec_driver_sql("SELECT assurance FROM core.auth_session").scalars()
            ) == {"PASSWORD"}
            assert (
                c.exec_driver_sql("SELECT count(*) FROM core.mfa_factor").scalar_one()
                == 0
            )
    assert (
        subprocess.run(
            [sys.executable, "tools/verify_ddl_matches_schema.py"],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


def test_names_inverse_preserves_oids_and_data(isolated_database):
    engine = isolated_database
    command.upgrade(Config("backend/alembic.ini"), "head")
    module = migration()
    before = object_names(engine)
    assert len(module.RENAMES) == 92
    with engine.connect() as c:
        assert (
            c.scalar(
                text(
                    "SELECT count(*) FROM pg_constraint WHERE conrelid='gw.approval_step'::regclass AND conname IN ('c1335_uk','c1546_uk')"
                )
            )
            == 2
        )
    columns, rows = fingerprint(engine)
    with engine.begin() as c:
        module.op = Operations(MigrationContext.configure(c))
        module.downgrade()
    with engine.begin() as c:
        module.op = Operations(MigrationContext.configure(c))
        module.upgrade()
    assert object_names(engine) == before
    assert fingerprint(engine, columns)[1] == rows


@pytest.mark.parametrize(
    "fault", ["missing", "occupied", "definition", "interrupted", "permission"]
)
def test_name_normalization_failure_is_atomic(isolated_database, fault):
    engine = isolated_database
    cfg = Config("backend/alembic.ini")
    command.upgrade(cfg, "gw_readiness")
    command.upgrade(cfg, "fems1")
    module = migration()
    item = next(x for x in module.RENAMES if x["kind"] == "CHECK")
    table, old = item["table"], item["from"]
    with engine.begin() as c:
        if fault == "missing":
            c.exec_driver_sql(
                f'ALTER TABLE {table} RENAME CONSTRAINT "{old}" TO synthetic_missing'
            )
        elif fault == "occupied":
            c.exec_driver_sql(
                f'ALTER TABLE {table} ADD CONSTRAINT "{item["to"]}" CHECK (true)'
            )
        elif fault == "definition":
            c.exec_driver_sql(f'ALTER TABLE {table} DROP CONSTRAINT "{old}"')
            c.exec_driver_sql(
                f'ALTER TABLE {table} ADD CONSTRAINT "{old}" CHECK (true)'
            )
    before = object_names(engine)
    columns, rows = fingerprint(engine)
    with engine.connect() as c:
        heads = c.exec_driver_sql(
            "SELECT version_num FROM alembic_version ORDER BY 1"
        ).all()

    def interrupt(conn, cursor, statement, parameters, context, executemany):
        if "RENAME" in statement:
            interrupt.count += 1
            if interrupt.count == 2:
                raise RuntimeError("synthetic interruption")

    interrupt.count = 0
    if fault == "interrupted":
        # Alembic opens its own engine; inject into the actual engine class.
        from sqlalchemy.engine import Engine

        event.listen(Engine, "before_cursor_execute", interrupt)
    try:
        if fault == "permission":
            with pytest.raises(DBAPIError), engine.begin() as c:
                c.exec_driver_sql("SET LOCAL ROLE pg_read_all_data")
                module.op = Operations(MigrationContext.configure(c))
                module.upgrade()
        else:
            with pytest.raises(RuntimeError):
                command.upgrade(cfg, "head")
    finally:
        if fault == "interrupted":
            event.remove(Engine, "before_cursor_execute", interrupt)
    assert object_names(engine) == before
    assert fingerprint(engine, columns)[1] == rows
    with engine.connect() as c:
        assert (
            c.exec_driver_sql(
                "SELECT version_num FROM alembic_version ORDER BY 1"
            ).all()
            == heads
        )
