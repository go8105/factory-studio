from __future__ import annotations

import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from fs.common.db import reset_engine
from fs.core.service import _business_table_order
from fs.main import create_app
from seed.generate import create_template
from sqlalchemy import Engine, create_engine, inspect, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    if not (make_url(url).database or "").endswith("_test"):
        raise pytest.UsageError("TEST_DATABASE_URL database must end in _test")
    engine = create_engine(url)
    yield engine
    engine.dispose()


def _truncate_database(engine: Engine) -> None:
    with engine.begin() as connection:
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )


@pytest.fixture
def clean_database(db_engine: Engine) -> Iterator[Engine]:
    """Legacy seed/portal tests own the whole database, before guest_template starts."""
    _truncate_database(db_engine)
    yield db_engine
    _truncate_database(db_engine)


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Run whole-database fixtures before the shared-template session, even with CLI file order."""
    for item in items:
        fixtures = set(getattr(item, "fixturenames", ()))
        if "guest_template" in fixtures and fixtures.intersection(
            {"clean_database", "common_env", "seed_env"}
        ):
            raise pytest.UsageError(
                f"{item.nodeid}: whole-DB and guest fixtures cannot mix"
            )
    items.sort(key=lambda item: "guest_template" in getattr(item, "fixturenames", ()))


@dataclass(frozen=True)
class GuestTemplate:
    engine: Engine
    workspace_id: int
    business_tables: tuple[str, ...]


def _template_snapshot(template: GuestTemplate) -> tuple[str, ...]:
    tables = (
        *template.business_tables,
        "core.workspace",
        "core.data_generation",
        "core.workspace_module",
    )
    with template.engine.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    "SELECT md5(COALESCE(string_agg(row_to_json(t)::text, '' ORDER BY id), '')) "
                    f"FROM {table} t WHERE {'id' if table == 'core.workspace' else 'workspace_id'}=:w"
                ),
                {"w": template.workspace_id},
            ).scalar_one()
            for table in tables
        )


def _delete_test_guests(template: GuestTemplate) -> None:
    """Remove all guests created by this test, including extra clients and retired generations."""
    with template.engine.begin() as connection:
        guests = (
            connection.execute(
                text("SELECT id FROM core.workspace WHERE workspace_kind='GUEST'")
            )
            .scalars()
            .all()
        )
        if not guests:
            return
        params = {"guests": guests}
        # Resolve the FK order once per session; self-references are deleted in one statement.
        for table in reversed(template.business_tables):
            connection.execute(
                text(f"DELETE FROM {table} WHERE workspace_id=ANY(:guests)"), params
            )
        for table in ("request_receipt", "audit_event", "job_run", "workspace_module"):
            connection.execute(
                text(f"DELETE FROM core.{table} WHERE workspace_id=ANY(:guests)"),
                params,
            )
        connection.execute(
            text(
                "UPDATE core.workspace SET active_generation_id=NULL WHERE id=ANY(:guests)"
            ),
            params,
        )
        connection.execute(
            text("DELETE FROM core.data_generation WHERE workspace_id=ANY(:guests)"),
            params,
        )
        connection.execute(
            text("DELETE FROM core.workspace WHERE id=ANY(:guests)"), params
        )


@pytest.fixture(scope="session")
def guest_template(db_engine: Engine) -> Iterator[GuestTemplate]:
    """One seed generation for all guest-space tests; legacy destructive fixtures run first."""
    _truncate_database(db_engine)
    with db_engine.begin() as connection:
        workspace_id, _, _ = create_template(connection, date(2026, 9, 24))
        tables = tuple(_business_table_order(connection))
    template = GuestTemplate(db_engine, workspace_id, tables)
    snapshot = _template_snapshot(template)
    yield template
    assert _template_snapshot(template) == snapshot, (
        "A guest test modified the shared template"
    )
    with db_engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM core.workspace WHERE workspace_kind='GUEST'")
            ).scalar_one()
            == 0
        )


@pytest.fixture
def guest_space(guest_template: GuestTemplate, monkeypatch: pytest.MonkeyPatch):
    """A fresh API-created guest per test; the immutable template survives guest cleanup."""
    engine = guest_template.engine
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("FS_TODAY", "2026-09-24")
    monkeypatch.setenv("GUEST_LIMIT", "10000")
    monkeypatch.setenv(
        "SESSION_SECRET", "fs018-synthetic-test-secret-at-least-32-characters"
    )
    reset_engine()
    try:
        with TestClient(create_app(), base_url="https://testserver") as client:
            response = client.post(
                "/api/v1/core/guest-sessions",
                json={"nickname": "테스트 게스트"},
                headers={"Idempotency-Key": str(uuid4())},
            )
            assert response.status_code == 201, response.text
            yield client, response.json()["data"], engine
    finally:
        reset_engine()
        _delete_test_guests(guest_template)
