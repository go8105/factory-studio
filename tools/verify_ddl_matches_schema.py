#!/usr/bin/env python3
"""FS-009: PostgreSQL 18 카탈로그와 설계 메타데이터의 독립 대조.

실제 업무 데이터는 읽거나 수정하지 않는다. 식 정규화는 세션 임시 테이블에서
PostgreSQL 파서를 사용하며 검증 트랜잭션 전체를 롤백한다. migration import 없음.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ("core", "mes", "erp", "fems", "qms", "wms")


def ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def qualified(name: str) -> str:
    return ".".join(ident(part) for part in name.split("."))


def normalize_type(value: str) -> str:
    return (
        value.lower()
        .replace("character varying", "varchar")
        .replace("timestamp with time zone", "timestamptz")
        .replace(" ", "")
    )


def predicate(constraint: dict[str, Any]) -> str:
    expression = constraint["expression"]
    if constraint["kind"] == "UK_PARTIAL":
        return re.split(r"\bWHERE\b", expression, maxsplit=1, flags=re.IGNORECASE)[
            1
        ].strip()
    return expression


def compare(connection: Connection, metadata: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    inspector = inspect(connection)
    if connection.dialect.server_version_info[0] != 18:
        raise RuntimeError("PostgreSQL 18 is required")
    expected_tables = {t["name"]: t for t in metadata["tables"]}
    existing_schemas = set(inspector.get_schema_names())
    actual_tables = {
        f"{schema}.{name}"
        for schema in SCHEMAS
        if schema in existing_schemas
        for name in inspector.get_table_names(schema=schema)
    }
    if set(expected_tables) != actual_tables:
        errors.append(
            f"tables: missing={sorted(set(expected_tables) - actual_tables)}, extra={sorted(actual_tables - set(expected_tables))}"
        )
    for schema in SCHEMAS:
        if schema not in existing_schemas:
            errors.append(f"missing schema: {schema}")
    constraints = metadata["constraints"]
    actual_counts: Counter[str] = Counter(tables=len(actual_tables))
    for full_name in sorted(set(expected_tables) & actual_tables):
        schema, table = full_name.split(".")
        expected_columns = expected_tables[full_name]["columns"]
        actual_columns = inspector.get_columns(table, schema=schema)
        actual_counts["columns"] += len(actual_columns)
        if [c["name"] for c in expected_columns] != [c["name"] for c in actual_columns]:
            errors.append(f"{full_name}: column names/order differ")
        by_name = {c["name"]: c for c in actual_columns}
        # PostgreSQL가 실제 타입 문맥에서 식을 정규화하게 한다. 임시 객체만 생성한다.
        temp_name = "fs_verify_" + uuid4().hex
        temp_q = "pg_temp." + ident(temp_name)
        connection.exec_driver_sql(
            f"CREATE TEMP TABLE {ident(temp_name)} (LIKE {qualified(full_name)}) ON COMMIT DROP"
        )
        for column in expected_columns:
            name = column["name"]
            if name not in by_name:
                continue
            actual = by_name[name]
            actual_type = str(actual["type"].compile(dialect=connection.dialect))
            if normalize_type(column["type"]) != normalize_type(actual_type):
                errors.append(
                    f"{full_name}.{name}: type {actual_type} != {column['type']}"
                )
            if column["nullable"] != actual["nullable"]:
                errors.append(f"{full_name}.{name}: nullable differs")
            default = column.get("default")
            if default == "GENERATED ALWAYS AS IDENTITY":
                if not actual.get("identity", {}).get("always"):
                    errors.append(f"{full_name}.{name}: identity ALWAYS missing")
            else:
                if actual.get("identity"):
                    errors.append(f"{full_name}.{name}: unexpected identity")
                if default is None:
                    canonical = None
                else:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {temp_q} ALTER COLUMN {ident(name)} SET DEFAULT {default}"
                    )
                    canonical = connection.execute(
                        text(
                            "SELECT pg_get_expr(d.adbin,d.adrelid) FROM pg_attrdef d JOIN pg_attribute a ON a.attrelid=d.adrelid AND a.attnum=d.adnum WHERE d.adrelid=to_regclass(:t) AND a.attname=:c"
                        ),
                        {"t": temp_q, "c": name},
                    ).scalar_one()
                if canonical != actual.get("default"):
                    errors.append(
                        f"{full_name}.{name}: default {actual.get('default')!r} != {canonical!r}"
                    )
        local = [(i, c) for i, c in enumerate(constraints) if c["table"] == full_name]
        actual_pk = inspector.get_pk_constraint(table, schema=schema)
        actual_counts["PK"] += bool(actual_pk["constrained_columns"])
        expected_pk = [tuple(c["columns"]) for _, c in local if c["kind"] == "PK"]
        if expected_pk != [tuple(actual_pk["constrained_columns"])]:
            errors.append(f"{full_name}: PK differs")
        actual_uks = inspector.get_unique_constraints(table, schema=schema)
        actual_counts["UK"] += len(actual_uks)
        if Counter(
            tuple(c["columns"]) for _, c in local if c["kind"] == "UK"
        ) != Counter(tuple(c["column_names"]) for c in actual_uks):
            errors.append(f"{full_name}: UK columns/count differ")
        if any(
            c.get("dialect_options", {}).get("postgresql_nulls_not_distinct")
            for c in actual_uks
        ):
            errors.append(f"{full_name}: unexpected NULLS NOT DISTINCT")
        actual_checks = inspector.get_check_constraints(table, schema=schema)
        actual_counts["CHECK"] += len(actual_checks)
        expected_checks = []
        for i, c in local:
            if c["kind"] != "CHECK":
                continue
            check_name = f"verify_c{i}"
            connection.exec_driver_sql(
                f"ALTER TABLE {temp_q} ADD CONSTRAINT {check_name} CHECK ({c['expression']})"
            )
            canonical = connection.execute(
                text(
                    "SELECT pg_get_expr(conbin,conrelid) FROM pg_constraint WHERE conrelid=to_regclass(:t) AND conname=:n"
                ),
                {"t": temp_q, "n": check_name},
            ).scalar_one()
            expected_checks.append(canonical)
        real_checks = (
            connection.execute(
                text(
                    "SELECT pg_get_expr(conbin,conrelid) FROM pg_constraint WHERE conrelid=to_regclass(:t) AND contype='c'"
                ),
                {"t": full_name},
            )
            .scalars()
            .all()
        )
        if Counter(expected_checks) != Counter(real_checks):
            errors.append(f"{full_name}: CHECK expressions/count differ")
        expected_indexes = []
        for i, c in local:
            if c["kind"] not in ("INDEX", "UK_PARTIAL", "UNIQUE_INDEX"):
                continue
            unique = c["kind"] != "INDEX"
            pred = predicate(c) if unique else c["expression"]
            if pred:
                idx_name = f"verify_i{i}_{uuid4().hex[:8]}"
                columns = ",".join(ident(v) for v in c["columns"])
                connection.exec_driver_sql(
                    f"CREATE INDEX {idx_name} ON {temp_q} ({columns}) WHERE {pred}"
                )
                pred = connection.execute(
                    text(
                        "SELECT pg_get_expr(indpred,indrelid) FROM pg_index WHERE indexrelid=to_regclass(:n)"
                    ),
                    {"n": "pg_temp." + idx_name},
                ).scalar_one()
            expected_indexes.append((tuple(c["columns"]), unique, pred or None))
        indexes = [
            i
            for i in inspector.get_indexes(table, schema=schema)
            if not i.get("duplicates_constraint")
        ]
        actual_counts["INDEX"] += sum(not i["unique"] for i in indexes)
        actual_counts["UNIQUE_INDEX"] += sum(i["unique"] for i in indexes)
        actual_indexes = [
            (
                tuple(i["column_names"]),
                i["unique"],
                i.get("dialect_options", {}).get("postgresql_where"),
            )
            for i in indexes
        ]
        if Counter(expected_indexes) != Counter(actual_indexes):
            errors.append(f"{full_name}: index columns/unique/predicate differ")
        for idx in indexes:
            opts = idx.get("dialect_options", {})
            if (
                opts.get("postgresql_include")
                or opts.get("postgresql_nulls_not_distinct")
                or opts.get("postgresql_using", "btree") != "btree"
            ):
                errors.append(f"{full_name}: unexpected index options {idx['name']}")
        expected_fks = Counter(
            (
                tuple(r["columns"]),
                r["target"],
                tuple(r["target_columns"]),
                r["on_delete"],
                r["on_update"],
            )
            for r in metadata["relations"]
            if r["source"] == full_name
        )
        fks = inspector.get_foreign_keys(table, schema=schema)
        actual_counts["FK"] += len(fks)
        actual_fks = Counter(
            (
                tuple(r["constrained_columns"]),
                f"{r['referred_schema']}.{r['referred_table']}",
                tuple(r["referred_columns"]),
                r["options"].get("ondelete", "NO ACTION"),
                r["options"].get("onupdate", "NO ACTION"),
            )
            for r in fks
        )
        if expected_fks != actual_fks:
            errors.append(f"{full_name}: FK scope/target/actions/count differ")
        for fk in fks:
            if (
                fk["options"].get("deferrable")
                or fk["options"].get("match", "SIMPLE") != "SIMPLE"
            ):
                errors.append(f"{full_name}: unexpected FK deferrability/match")
        invalid = (
            connection.execute(
                text(
                    "SELECT conname FROM pg_constraint WHERE conrelid=to_regclass(:t) AND NOT convalidated"
                ),
                {"t": full_name},
            )
            .scalars()
            .all()
        )
        if invalid:
            errors.append(f"{full_name}: unvalidated constraints {invalid}")
        connection.exec_driver_sql(f"DROP TABLE {temp_q}")
    expected_counts = Counter(c["kind"] for c in constraints)
    expected_counts["UNIQUE_INDEX"] += expected_counts.pop("UK_PARTIAL", 0)
    service_policies = expected_counts.pop("SERVICE/DB_POLICY", 0)
    expected_counts.update(
        tables=len(expected_tables),
        columns=sum(len(t["columns"]) for t in metadata["tables"]),
        FK=len(metadata["relations"]),
    )
    if expected_counts != actual_counts:
        errors.append(
            f"counts differ: expected={dict(expected_counts)}, actual={dict(actual_counts)}"
        )
    return {
        "schema_version": metadata["version"],
        "server_version": connection.exec_driver_sql(
            "SHOW server_version"
        ).scalar_one(),
        "expected": dict(expected_counts),
        "actual": dict(actual_counts),
        "service_policies_not_db_constraints": service_policies,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--schema", type=Path, default=ROOT / "docs/db/schema-metadata/schema.json"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    source = args.schema.read_bytes()
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            result = compare(connection, json.loads(source))
        finally:
            transaction.rollback()
    result["schema_sha256"] = hashlib.sha256(source).hexdigest()
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    return int(bool(result["errors"]))


if __name__ == "__main__":
    sys.exit(main())
