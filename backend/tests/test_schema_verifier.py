"""실제 PostgreSQL 카탈로그 변조를 대조 검사가 잡는지 검증한다."""

import importlib.util
import json
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Connection, create_engine
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "verify_ddl", ROOT / "tools/verify_ddl_matches_schema.py"
)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


@pytest.fixture
def db() -> Iterator[Connection]:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.fail(
            "TEST_DATABASE_URL is required; run against a migrated *_test database"
        )
    if not make_url(url).database.endswith("_test"):
        pytest.fail("Refusing mutation tests outside a *_test database")
    engine = create_engine(url)
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            yield connection
        finally:
            transaction.rollback()
    engine.dispose()


def check(db: Connection) -> list[str]:
    metadata = json.loads((ROOT / "docs/db/schema-metadata/schema.json").read_text())
    return verifier.compare(db, metadata)["errors"]


def test_baseline_matches(db: Connection) -> None:
    assert check(db) == []


@pytest.mark.parametrize(
    "ddl,expected",
    [
        (
            "ALTER TABLE erp.partner DROP CONSTRAINT c521_check; ALTER TABLE erp.partner ADD CONSTRAINT c521_check CHECK(payment_term_days > 0)",
            "CHECK expressions",
        ),
        (
            "ALTER TABLE erp.partner ALTER COLUMN payment_term_days SET NOT NULL",
            "nullable differs",
        ),
        ("ALTER TABLE erp.receipt ALTER COLUMN amount SET DEFAULT 10", "default"),
        ("ALTER TABLE erp.receipt ALTER COLUMN amount TYPE numeric(20,2)", "type"),
        (
            "ALTER TABLE erp.receipt DROP CONSTRAINT r147_fk; ALTER TABLE erp.receipt ADD CONSTRAINT r147_fk FOREIGN KEY(workspace_id,generation_id,partner_id) REFERENCES erp.partner(workspace_id,generation_id,id) ON DELETE CASCADE ON UPDATE RESTRICT",
            "FK scope/target/actions",
        ),
        (
            "ALTER TABLE erp.receipt DROP CONSTRAINT c455_uk; ALTER TABLE erp.receipt ADD CONSTRAINT c455_uk UNIQUE(workspace_id,generation_id,receipt_no,received_on)",
            "UK columns",
        ),
        (
            "DROP INDEX erp.c498_uidx; CREATE UNIQUE INDEX c498_uidx ON erp.tax_invoice(workspace_id,generation_id,approval_no) WHERE approval_no IS NULL",
            "index columns/unique/predicate",
        ),
        ("CREATE TABLE core.unexpected(id bigint)", "tables:"),
    ],
)
def test_drift_detected(db: Connection, ddl: str, expected: str) -> None:
    db.exec_driver_sql(ddl)
    assert any(expected in error for error in check(db))
