#!/usr/bin/env python3
"""설계(schema.json)에서 alembic 마이그레이션 파일을 만든다 — 일괄 개발(W…) 단계용.

표를 손으로 옮기면 틀린다(W1a는 20표, W2a는 110표). 생성한 파일은 **고정된 SQL 목록**이라
실행할 때 JSON을 읽지 않는다. 설계와 실제 DB가 같은지는 tools/verify_ddl_matches_schema.py가 확인한다.

  python3 tools/build_migration.py --revision w1a_hr --down w01_lazy_seed \\
      --tables 'hr.*' core.holiday --module-key hr \\
      --out backend/alembic/versions/20261006_w1a_hr_schema.py --title "W1a HR 스키마"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"


def matches(name: str, patterns: list[str]) -> bool:
    return any(
        name == p or (p.endswith(".*") and name.startswith(p[:-1])) for p in patterns
    )


def column_sql(c: dict) -> str:
    sql = f"{c['name']} {c['type']}"
    if c.get("default") == "GENERATED ALWAYS AS IDENTITY":
        sql += " GENERATED ALWAYS AS IDENTITY"
    elif c.get("default") is not None:
        sql += f" DEFAULT {c['default']}"
    if not c["nullable"]:
        sql += " NOT NULL"
    return sql


def build(
    design: dict, patterns: list[str], module_key: str | None
) -> tuple[list[str], list[str], list[str]]:
    """(생성 SQL, 되돌리기 SQL, 새 스키마 이름)"""
    tables = [t for t in design["tables"] if matches(t["name"], patterns)]
    names = {t["name"] for t in tables}
    have = {
        t["name"].split(".", 1)[0] for t in design["tables"] if t["name"] not in names
    }
    schemas = sorted({t["name"].split(".", 1)[0] for t in tables} - have)
    up: list[str] = [f"CREATE SCHEMA {s}" for s in schemas]
    for t in tables:
        columns = ", ".join(column_sql(c) for c in t["columns"])
        up.append(f"CREATE TABLE {t['name']} ({columns})")
    for i, c in enumerate(design["constraints"]):
        if c["table"] not in names:
            continue
        cols = ",".join(c["columns"])
        if c["kind"] == "PK":
            up.append(
                f"ALTER TABLE {c['table']} ADD CONSTRAINT c{i}_pk PRIMARY KEY ({cols})"
            )
        elif c["kind"] == "UK":
            up.append(
                f"ALTER TABLE {c['table']} ADD CONSTRAINT c{i}_uk UNIQUE ({cols})"
            )
        elif c["kind"] == "CHECK":
            up.append(
                f"ALTER TABLE {c['table']} ADD CONSTRAINT c{i}_check CHECK ({c['expression']})"
            )
        elif c["kind"] == "INDEX":
            where = f" WHERE {c['expression']}" if c["expression"] else ""
            up.append(f"CREATE INDEX c{i}_idx ON {c['table']} ({cols}){where}")
        elif c["kind"] in ("UK_PARTIAL", "UNIQUE_INDEX"):
            predicate = re.split(
                r"\bWHERE\b", c["expression"], maxsplit=1, flags=re.IGNORECASE
            )[1].strip()
            up.append(
                f"CREATE UNIQUE INDEX c{i}_uidx ON {c['table']} ({cols}) WHERE {predicate}"
            )
        # SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
    for i, r in enumerate(design["relations"]):
        if r["source"] not in names:
            continue
        up.append(
            f"ALTER TABLE {r['source']} ADD CONSTRAINT r{i}_fk FOREIGN KEY ({','.join(r['columns'])}) "
            f"REFERENCES {r['target']} ({','.join(r['target_columns'])}) "
            f"ON DELETE {r['on_delete']} ON UPDATE {r['on_update']}"
        )
    down = [f"DROP TABLE {t['name']}" for t in reversed(tables)]
    down += [f"DROP SCHEMA {s}" for s in schemas]
    module = []
    if module_key:
        for table in ("core.workspace_module", "core.app_review"):
            new = next(
                c["expression"]
                for c in design["constraints"]
                if c["table"] == table
                and c["kind"] == "CHECK"
                and "module_key IN" in c["expression"]
            )
            index = next(
                i
                for i, c in enumerate(design["constraints"])
                if c["table"] == table
                and c["kind"] == "CHECK"
                and "module_key IN" in c["expression"]
            )
            old = new.rstrip(")")[: -len(f", '{module_key}'")] + ")"
            module.append((table, f"c{index}_check", old, new))
    return up, down, module


def render(args, up: list[str], down: list[str], module: list, digest: str) -> str:
    quoted = ",\n".join(f'    "{s}"' for s in up)
    down_quoted = ",\n".join(f'    "{s}"' for s in down)
    module_rows = ",\n".join(
        f'    ("{t}", "{n}", "{o}", "{w}")'.replace("'", "'") for t, n, o, w in module
    )
    return f'''"""{args.title}.

설계 schema.json {args.version}({args.task})에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: {digest}
"""

from alembic import op

revision = "{args.revision}"
down_revision = "{args.down}"
branch_labels = None
depends_on = None

STATEMENTS = [
{quoted},
]
DROPS = [
{down_quoted},
]
# 모듈 키: (표, 제약 이름, 옛 식, 새 식)
MODULE_CHECKS = [
{module_rows},
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)
    for table, name, _old, new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {{table}} DROP CONSTRAINT {{name}}")
        op.execute(f"ALTER TABLE {{table}} ADD CONSTRAINT {{name}} CHECK ({{new}})")


def downgrade() -> None:
    # 모듈 행·평가가 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 멈추는 쪽이 안전하다.
    for table, name, old, _new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {{table}} DROP CONSTRAINT {{name}}")
        op.execute(f"ALTER TABLE {{table}} ADD CONSTRAINT {{name}} CHECK ({{old}})")
    for statement in DROPS:
        op.execute(statement)
'''


def main() -> None:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--revision", required=True)
    p.add_argument("--down", required=True)
    p.add_argument("--tables", nargs="+", required=True, help="hr.* core.holiday")
    p.add_argument("--module-key")
    p.add_argument("--title", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raw = CURRENT.read_bytes()
    design = json.loads(raw)
    args.version, args.task = design["version"], design["task"]
    up, down, module = build(design, args.tables, args.module_key)
    args.out.write_text(
        render(args, up, down, module, hashlib.sha256(raw).hexdigest()),
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), "statements": len(up)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
