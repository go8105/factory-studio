#!/usr/bin/env python3
"""GW-a: DSN-31 체험·조직만 목표 설계에서 이관한다.

실제 도입 A의 5개 GW 표와 CORE·ERP 변경은 이관하지 않는다.
삭제되는 제약 슬롯은 SERVICE/DB_POLICY로 남겨 기존 c번호를 보존한다.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from apply_w2a1 import key, relation_key

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
EXCLUDED = {
    "gw.collaboration_settings",
    "gw.person_identity_binding",
    "gw.role_grant",
    "gw.document_reader",
    "gw.step_assignment",
}
RETIRED = "GW-a 제약 번호 보존: "


def apply(current: dict, target: dict) -> bool:
    before = copy.deepcopy(current)
    wanted = [
        t
        for t in target["tables"]
        if t["name"].startswith("gw.") and t["name"] not in EXCLUDED
    ]
    names = {t["name"] for t in wanted}
    have = {t["name"]: t for t in current["tables"]}
    for table in wanted:
        mine = have.get(table["name"])
        if mine is None:
            current["tables"].append(copy.deepcopy(table))
            continue
        existing = {c["name"] for c in mine["columns"]}
        for column in table["columns"]:
            if column["name"] not in existing:
                if not column["nullable"] and column.get("default") is None:
                    raise ValueError(
                        f"운영 데이터에 안전하지 않은 칼럼: {table['name']}.{column['name']}"
                    )
                mine["columns"].append(copy.deepcopy(column))
    target_constraints = [c for c in target["constraints"] if c["table"] in names]
    target_keys = {key(c) for c in target_constraints}
    current_keys = {key(c) for c in current["constraints"]}
    fresh = [c for c in target_constraints if key(c) not in current_keys]
    for index, old in enumerate(current["constraints"]):
        if (
            old["table"] not in names
            or key(old) in target_keys
            or old["reason"].startswith(RETIRED)
        ):
            continue
        same = [
            c
            for c in fresh
            if c["table"] == old["table"] and c["columns"] == old["columns"]
        ]
        if len(same) > 1:
            raise ValueError(f"제약 교체 후보 중복: {old}")
        if same:
            current["constraints"][index] = copy.deepcopy(same[0])
            fresh.remove(same[0])
        else:
            if (old["table"], old["kind"], tuple(old["columns"])) not in {
                (
                    "gw.route_step",
                    "UK",
                    ("workspace_id", "generation_id", "route_id", "seq"),
                ),
                (
                    "gw.approval_step",
                    "UK",
                    ("workspace_id", "generation_id", "document_id", "seq"),
                ),
                ("gw.approval_document", "CHECK", ("source_status",)),
            }:
                raise ValueError(f"예상하지 못한 제약 삭제: {old}")
            # 배열을 줄이면 다른 스키마까지 운영 제약 이름이 바뀐다.
            current["constraints"][index] = {
                **old,
                "kind": "SERVICE/DB_POLICY",
                "expression": "DSN-31에서 제거한 DB 제약; 서비스 규칙은 별도 검증",
                "reason": RETIRED + old["kind"] + " 제거 (DSN-31)",
            }
    current["constraints"].extend(copy.deepcopy(fresh))
    existing_relations = {relation_key(r) for r in current["relations"]}
    current["relations"].extend(
        copy.deepcopy(r)
        for r in target["relations"]
        if r["source"] in names
        and r["target"] not in EXCLUDED
        and relation_key(r) not in existing_relations
    )
    for section, field in [("states", "table"), ("code_lists", "target")]:
        for item in target.get(section, []):
            if item.get(field) in names and item not in current[section]:
                current[section].append(copy.deepcopy(item))
    if current == before:
        return False
    current.update(
        version="0.21.0",
        task="GW-a",
        date="2026-10-09",
        migration_revision="gw_a_dsn31",
    )
    current["change_log"].append(
        {
            "version": "0.21.0",
            "task": "GW-a",
            "date": "2026-10-09",
            "change": "DSN-31 체험·조직 신규 11표와 기존 GW 6표 확장. 실제 도입 A 5표·CORE TEAM·ERP 통제는 제외. 제거 제약 슬롯 보존.",
            "status": "마이그레이션 gw_a_dsn31 적용 대상",
        }
    )
    return True


def main() -> None:
    current = json.loads(CURRENT.read_text())
    changed = apply(current, json.loads(TARGET.read_text()))
    if changed:
        CURRENT.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "changed": changed,
                "version": current["version"],
                "gw_tables": sum(
                    t["name"].startswith("gw.") for t in current["tables"]
                ),
                "tables": len(current["tables"]),
            }
        )
    )


if __name__ == "__main__":
    main()
