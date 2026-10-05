#!/usr/bin/env python3
"""DSN-00: 설계 메타데이터(schema.json·schema-target.json)로 빈 DB를 만들고 카탈로그와 대조한다.

제품 마이그레이션이 아니다. 목표 설계가 PostgreSQL에 실제로 적용되는지(문법·FK 대상 유일성·식)만 확인한다.
적용 대상 DB 이름은 `_target`으로 끝나야 하며, 실행할 때마다 지우고 새로 만든다.

  python3 tools/schema_ddl.py --print                       # DDL만 출력
  python3 tools/schema_ddl.py --schema docs/db/schema-metadata/schema-target.json --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"


def ddl(d: dict) -> list[str]:
    out = [
        f"CREATE SCHEMA {s}"
        for s in sorted({t["name"].split(".")[0] for t in d["tables"]})
    ]
    by_table: dict[str, list[dict]] = {}
    for c in d["constraints"]:
        by_table.setdefault(c["table"], []).append(c)
    for t in d["tables"]:
        parts = []
        for c in t["columns"]:
            col = f"{c['name']} {c['type']}"
            if c.get("default") == "GENERATED ALWAYS AS IDENTITY":
                col += " GENERATED ALWAYS AS IDENTITY"
            elif c.get("default") is not None:
                col += f" DEFAULT {c['default']}"
            if not c["nullable"]:
                col += " NOT NULL"
            parts.append(col)
        for c in by_table.get(t["name"], []):
            cols = ", ".join(c["columns"])
            if c["kind"] == "PK":
                parts.append(f"PRIMARY KEY ({cols})")
            elif c["kind"] == "UK":
                parts.append(f"UNIQUE ({cols})")
            elif c["kind"] == "CHECK":
                parts.append(f"CHECK ({c['expression']})")
        out.append(f"CREATE TABLE {t['name']} (\n  " + ",\n  ".join(parts) + "\n)")
    for c in d["constraints"]:
        cols = ", ".join(c["columns"])
        if c["kind"] == "INDEX":
            where = f" WHERE {c['expression']}" if c["expression"] else ""
            out.append(f"CREATE INDEX ON {c['table']} ({cols}){where}")
        elif c["kind"] == "UNIQUE_INDEX":
            out.append(
                f"CREATE UNIQUE INDEX ON {c['table']} ({cols}) WHERE {c['expression']}"
            )
        elif c["kind"] == "UK_PARTIAL":
            pred = re.split(
                r"\bWHERE\b", c["expression"], maxsplit=1, flags=re.IGNORECASE
            )[1].strip()
            out.append(f"CREATE UNIQUE INDEX ON {c['table']} ({cols}) WHERE {pred}")
    for r in d["relations"]:
        out.append(
            f"ALTER TABLE {r['source']} ADD FOREIGN KEY ({', '.join(r['columns'])}) "
            f"REFERENCES {r['target']} ({', '.join(r['target_columns'])}) "
            f"ON DELETE {r['on_delete']} ON UPDATE {r['on_update']}"
        )
    return out


def apply(d: dict, url: str) -> dict:
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from verify_ddl_matches_schema import compare

    target = make_url(url)
    name = target.database or ""
    if not name.endswith("_target"):
        raise SystemExit(f"DB 이름이 _target으로 끝나야 한다: {name}")
    admin = create_engine(target.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        c.exec_driver_sql(f'CREATE DATABASE "{name}"')
    admin.dispose()
    engine = create_engine(target)
    with engine.begin() as c:
        for statement in ddl(d):
            c.exec_driver_sql(statement.replace("%", "%%"))
    with engine.connect() as c:
        tx = c.begin()
        try:
            return compare(c, d)
        finally:
            tx.rollback()


def main() -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--schema", type=Path, default=TARGET)
    p.add_argument("--print", action="store_true", help="DDL만 출력")
    p.add_argument(
        "--apply", action="store_true", help="빈 *_target DB에 적용하고 카탈로그와 대조"
    )
    p.add_argument(
        "--url", help="기본: DATABASE_URL의 서버 + DB 이름 factory_studio_target"
    )
    p.add_argument(
        "--report", type=Path, default=ROOT / "docs/db/ddl-report-target.json"
    )
    a = p.parse_args()
    raw = a.schema.read_bytes()
    d = json.loads(raw)
    if a.print or not a.apply:
        print(";\n\n".join(ddl(d)) + ";")
        return 0
    url = (
        a.url or os.environ["DATABASE_URL"].rsplit("/", 1)[0] + "/factory_studio_target"
    )
    result = apply(d, url)
    result.update(
        schema=str(a.schema.resolve().relative_to(ROOT)),
        schema_sha256=hashlib.sha256(raw).hexdigest(),
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    a.report.write_text(rendered, encoding="utf-8")
    return int(bool(result["errors"]))


if __name__ == "__main__":
    sys.exit(main())
