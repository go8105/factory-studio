from __future__ import annotations
# ruff: noqa: I001

import json
import os
import statistics
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from seed.copy import copy_template
from seed.generate import create_template
from seed.validate import EXPECTED_COUNTS, validate_all


URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is required", allow_module_level=True)

engine = create_engine(URL)


def _reset() -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        tables = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspector.get_table_names(schema=schema)
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )


def _snapshot(workspace_id: int, generation_id: int) -> bytes:
    content: dict[str, object] = {}
    with engine.connect() as connection:
        for name in EXPECTED_COUNTS:
            schema, table = name.split(".")
            where = "id=:w" if name == "core.workspace" else "workspace_id=:w"
            params = {"w": workspace_id, "g": generation_id}
            columns = {
                row["name"]
                for row in inspect(connection).get_columns(table, schema=schema)
            }
            if name == "core.data_generation":
                where += " AND id=:g"
            elif "generation_id" in columns:
                where += " AND generation_id=:g"
            rows = (
                connection.execute(
                    text(
                        f'SELECT * FROM "{schema}"."{table}" WHERE {where} ORDER BY id'
                    ),
                    params,
                )
                .mappings()
                .all()
            )
            content[name] = [dict(row) for row in rows]
    return json.dumps(
        content, sort_keys=True, ensure_ascii=False, default=str, separators=(",", ":")
    ).encode()


def test_fs015_v1_to_v12_determinism_and_copy_benchmark(tmp_path: Path) -> None:
    seed_date = date(2026, 9, 23)
    _reset()
    with engine.begin() as connection:
        workspace_id, generation_id, counts = create_template(connection, seed_date)
        assert sum(counts.values()) == 7469
        assert (
            len(validate_all(connection, workspace_id, generation_id, seed_date)) == 12
        )
    first = _snapshot(workspace_id, generation_id)
    _reset()
    with engine.begin() as connection:
        workspace_id, generation_id, _ = create_template(connection, seed_date)
    assert first == _snapshot(workspace_id, generation_id)

    timings = []
    targets = [date(2026, 10, 7), date(2027, 1, 5)] + [
        date(2026, 10, 8 + index) for index in range(10)
    ]
    copied = []
    for index, target in enumerate(targets):
        with engine.begin() as connection:
            copied_workspace, copied_generation, counts, elapsed = copy_template(
                connection, workspace_id, generation_id, target, f"fs015-test-{index}"
            )
            assert sum(counts.values()) == 7467
            assert (
                len(
                    validate_all(
                        connection, copied_workspace, copied_generation, target
                    )
                )
                == 12
            )
            copied.append((copied_workspace, copied_generation, target))
            if index >= 2:
                timings.append(elapsed)
    report = {
        "runs": len(timings),
        "median_seconds": statistics.median(timings),
        "max_seconds": max(timings),
        "targets_verified": [target.isoformat() for _, _, target in copied[:2]],
    }
    (tmp_path / "benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    assert report["runs"] == 10
    assert report["max_seconds"] < 2
    _reset()
