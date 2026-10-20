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


def constraint_name(index: int, kind: str) -> str:
    suffix = {
        "PK": "pk",
        "UK": "uk",
        "CHECK": "check",
        "INDEX": "idx",
        "UK_PARTIAL": "uidx",
        "UNIQUE_INDEX": "uidx",
    }[kind]
    return f"c{index}_{suffix}"


def create_sql(c: dict, index: int) -> str | None:
    """제약 하나를 만드는 SQL. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다."""
    if c["kind"] == "SERVICE/DB_POLICY":
        return None
    name, table, cols = (
        constraint_name(index, c["kind"]),
        c["table"],
        ",".join(c["columns"]),
    )
    if c["kind"] == "PK":
        return f"ALTER TABLE {table} ADD CONSTRAINT {name} PRIMARY KEY ({cols})"
    if c["kind"] == "UK":
        return f"ALTER TABLE {table} ADD CONSTRAINT {name} UNIQUE ({cols})"
    if c["kind"] == "CHECK":
        return f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({c['expression']})"
    if c["kind"] == "INDEX":
        where = f" WHERE {c['expression']}" if c["expression"] else ""
        return f"CREATE INDEX {name} ON {table} ({cols}){where}"
    if c["kind"] in ("UK_PARTIAL", "UNIQUE_INDEX"):
        predicate = re.split(
            r"\bWHERE\b", c["expression"], maxsplit=1, flags=re.IGNORECASE
        )[1].strip()
        return f"CREATE UNIQUE INDEX {name} ON {table} ({cols}) WHERE {predicate}"
    return None


def drop_sql(c: dict, index: int) -> str | None:
    if c["kind"] == "SERVICE/DB_POLICY":
        return None
    name = constraint_name(index, c["kind"])
    if c["kind"] in ("INDEX", "UK_PARTIAL", "UNIQUE_INDEX"):
        return f"DROP INDEX {c['table'].split('.', 1)[0]}.{name}"
    return f"ALTER TABLE {c['table']} DROP CONSTRAINT {name}"


def foreign_key_sql(r: dict, index: int) -> str:
    return (
        f"ALTER TABLE {r['source']} ADD CONSTRAINT r{index}_fk FOREIGN KEY ({','.join(r['columns'])}) "
        f"REFERENCES {r['target']} ({','.join(r['target_columns'])}) "
        f"ON DELETE {r['on_delete']} ON UPDATE {r['on_update']}"
    )


def build(
    design: dict,
    patterns: list[str],
    module_key: str | None,
    previous: dict | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """(생성 SQL, 되돌리기 SQL, 모듈 키 CHECK)

    previous(지난 설계)를 주면 **달라진 것만** 만든다 — 이미 있는 표에는 칼럼을 더하고,
    바뀐 제약은 지웠다 다시 만든다. 제약 이름은 schema.json 배열의 순번이라 순번이 곧 이름이다.
    """
    tables = [t for t in design["tables"] if matches(t["name"], patterns)]
    names = {t["name"] for t in tables}
    old_tables = {t["name"]: t for t in (previous or {}).get("tables", [])}
    old_constraints = (previous or {}).get("constraints", [])
    old_relations = (previous or {}).get("relations", [])
    fresh = [t for t in tables if t["name"] not in old_tables]
    kept = {t["name"] for t in tables if t["name"] in old_tables}
    have = {
        t["name"].split(".", 1)[0]
        for t in design["tables"]
        if t["name"] not in {x["name"] for x in fresh}
    }
    schemas = sorted({t["name"].split(".", 1)[0] for t in fresh} - have)

    up: list[str] = [f"CREATE SCHEMA {s}" for s in schemas]
    for t in fresh:
        up.append(
            f"CREATE TABLE {t['name']} ({', '.join(column_sql(c) for c in t['columns'])})"
        )
    added: list[tuple[str, str]] = []
    for t in tables:
        if t["name"] not in kept:
            continue
        existing = {c["name"] for c in old_tables[t["name"]]["columns"]}
        for c in t["columns"]:
            if c["name"] in existing:
                continue
            if not c["nullable"] and not c.get("default"):
                raise SystemExit(
                    f"{t['name']}.{c['name']}: 이미 있는 표에 NOT NULL을 기본값 없이 더할 수 없다"
                )
            up.append(f"ALTER TABLE {t['name']} ADD COLUMN {column_sql(c)}")
            added.append((t["name"], c["name"]))

    # 바뀐 제약은 옛 이름을 먼저 지운다.
    replaced: list[int] = []
    for i, c in enumerate(design["constraints"]):
        if c["table"] not in kept or i >= len(old_constraints):
            continue
        if old_constraints[i] != c and old_constraints[i]["table"] == c["table"]:
            statement = drop_sql(old_constraints[i], i)
            if statement:
                up.append(statement)
            replaced.append(i)
    for i, c in enumerate(design["constraints"]):
        if c["table"] not in names:
            continue
        if i < len(old_constraints) and old_constraints[i] == c:
            continue
        statement = create_sql(c, i)
        if statement:
            up.append(statement)
    for i, r in enumerate(design["relations"]):
        if r["source"] not in names:
            continue
        if i < len(old_relations) and old_relations[i] == r:
            continue
        up.append(foreign_key_sql(r, i))

    # 새 FK/제약을 먼저 해제한다. 기존 표 → 새 표 참조 및 self-FK도 있어
    # 표/칼럼부터 지우면 RESTRICT에서 실패하거나 제약이 묵시 삭제된다.
    down: list[str] = []
    for i, r in reversed(list(enumerate(design["relations"]))):
        if r["source"] in names and not (
            i < len(old_relations) and old_relations[i] == r
        ):
            down.append(f"ALTER TABLE {r['source']} DROP CONSTRAINT r{i}_fk")
    for i, c in reversed(list(enumerate(design["constraints"]))):
        if c["table"] not in names or (
            i < len(old_constraints) and old_constraints[i] == c
        ):
            continue
        statement = drop_sql(c, i)
        if statement:
            down.append(statement)
    down.extend(f"ALTER TABLE {t} DROP COLUMN {c}" for t, c in reversed(added))
    down.extend(f"DROP TABLE {t['name']}" for t in reversed(fresh))
    down.extend(f"DROP SCHEMA {s}" for s in schemas)
    for i in reversed(replaced):
        back = create_sql(old_constraints[i], i)
        if back:
            down.append(back)

    module = []
    if module_key:
        for table in ("core.workspace_module", "core.app_review"):
            index, new = next(
                (i, c["expression"])
                for i, c in enumerate(design["constraints"])
                if c["table"] == table
                and c["kind"] == "CHECK"
                and "module_key IN" in c["expression"]
            )
            tail = f", '{module_key}')"
            if not new.endswith(tail):
                continue  # 이미 목록에 있는 모듈 키다. CHECK를 바꿀 것이 없다.
            module.append((table, f"c{index}_check", new[: -len(tail)] + ")", new))
    return up, down, module


def render(args, up: list[str], down: list[str], module: list, digest: str) -> str:
    # 비어 있을 수 있으니 줄마다 쉼표를 붙인다 — join은 빈 목록에서 쉼표만 남긴다.
    quoted = "".join(f'    "{s}",\n' for s in up).rstrip("\n")
    down_quoted = "".join(f'    "{s}",\n' for s in down).rstrip("\n")
    # 빈 목록은 ruff format이 한 줄로 줄인다. 처음부터 한 줄로 만든다.
    module_rows = "".join(
        f'    ("{t}", "{n}", "{o}", "{w}"),\n' for t, n, o, w in module
    ).rstrip("\n")
    module_block = f"[\n{module_rows}\n]" if module else "[]"
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
{quoted}
]
DROPS = [
{down_quoted}
]
# 모듈 키: (표, 제약 이름, 옛 식, 새 식)
MODULE_CHECKS = {module_block}


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
    p.add_argument(
        "--previous",
        type=Path,
        help="지난 설계 schema.json. 주면 달라진 것만 만든다(이미 있는 표에 칼럼·제약 추가)",
    )
    p.add_argument("--title", required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    raw = CURRENT.read_bytes()
    design = json.loads(raw)
    args.version, args.task = design["version"], design["task"]
    previous = (
        json.loads(args.previous.read_text(encoding="utf-8")) if args.previous else None
    )
    up, down, module = build(design, args.tables, args.module_key, previous)
    args.out.write_text(
        render(args, up, down, module, hashlib.sha256(raw).hexdigest()),
        encoding="utf-8",
    )
    print(json.dumps({"out": str(args.out), "statements": len(up)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
