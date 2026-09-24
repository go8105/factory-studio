from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine, inspect, text


@pytest.fixture(scope="session")
def db_engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is required")
    engine = create_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture
def clean_database(db_engine: Engine) -> Iterator[Engine]:
    with db_engine.begin() as connection:
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )
    yield db_engine
    with db_engine.begin() as connection:
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )
