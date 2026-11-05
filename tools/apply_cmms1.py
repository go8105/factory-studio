#!/usr/bin/env python3
"""CMMS-1a: 승인된 목표 설계(schema-target.json)의 CMMS 보강을 제품 설계(schema.json)로 옮긴다.

CMMS는 FS-029a로 DB 6표만 있고 API·화면이 없다(D76). 이 단계는 그 DB를 목표 설계(DSN-21)까지 올린다.
  - 새 표 6개 (점검 항목·결과, 정비원, 외주 업체, 고장 코드, 설비별 예비품)
  - 기존 표 6개에 칼럼 추가 — 모두 NULL 허용이거나 기본값이 있다
    (설비 계층·상세, PM 사용량 기준, 작업지시 정비원·외주·코드, 작업 기록 정비원,
     예비품 WMS 품목·단가, 부품 사용 단가 스냅샷)
  - 바뀌는 제약은 제자리 교체 (설비 종류·출처 확장, PM 주기 NULL 허용 등)

제약·관계는 **배열 끝에 붙인다**. 이미 적용한 마이그레이션이 `c{번호}_check` 같은 이름을
순번에서 만들기 때문에, 중간에 끼워 넣으면 기존 DB의 제약 이름과 어긋난다.
교체하는 제약만 제자리에서 바꾸고, 마이그레이션이 옛 이름을 지우고 새로 만든다.
CMMS도 표·칼럼이 1:1로 맞아떨어져 특례 없이 범용 규칙만으로 교체된다.

마이그레이션은 tools/build_migration.py --previous 가 이 결과로 만든다. 멱등(두 번 돌려도 같다).
"""


from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
VERSION = "0.30.0"
TASK = "CMMS-1a"
DATE = "2026-10-20"
SCHEMA = "cmms"
CHANGE = (
    "CMMS 보강: 새 표 6개(점검 항목·결과, 정비원, 외주 업체, 고장 코드, 설비별 예비품)와 "
    "기존 6표 칼럼 추가(설비 계층·상세, PM 사용량 기준, 작업지시 정비원·외주·고장 코드, "
    "작업 기록 정비원, 예비품 WMS 품목·단가, 부품 사용 단가). 목표 설계 DSN-21에서 그대로 옮김"
)
STATUS = "마이그레이션 cmms1 적용 대상"


def key(c: dict[str, Any]) -> tuple:
    return (
        c["table"],
        c["kind"],
        tuple(c.get("columns") or []),
        c.get("expression", ""),
    )


def relation_key(r: dict[str, Any]) -> tuple:
    return (r["source"], tuple(r["columns"]), r["target"], tuple(r["target_columns"]))


def apply(current: dict, target: dict) -> bool:
    """current를 제자리에서 바꾸고, 바뀌었으면 True."""
    before = json.dumps(current, ensure_ascii=False, sort_keys=True)
    have = {t["name"]: t for t in current["tables"]}
    wanted = [t for t in target["tables"] if t["name"].startswith(f"{SCHEMA}.")]

    # 1) 새 표는 통째로, 기존 표는 빠진 칼럼만 목표 순서대로 붙인다.
    for table in wanted:
        mine = have.get(table["name"])
        if mine is None:
            current["tables"].append(json.loads(json.dumps(table)))
            continue
        existing = {c["name"] for c in mine["columns"]}
        for column in table["columns"]:
            if column["name"] not in existing:
                mine["columns"].append(json.loads(json.dumps(column)))

    names = {t["name"] for t in wanted}
    mine_keys = {key(c) for c in current["constraints"]}
    fresh = [
        c
        for c in target["constraints"]
        if c["table"] in names and key(c) not in mine_keys
    ]

    # 2) 없어지는 제약은 같은 표·같은 칼럼의 새 제약으로 **제자리에서** 바꾼다.
    #    순번이 곧 DB의 제약 이름이라, 끼워 넣거나 지우면 기존 DB와 어긋난다.
    target_keys = {key(c) for c in target["constraints"] if c["table"] in names}
    for index, old in enumerate(current["constraints"]):
        if old["table"] not in names or key(old) in target_keys:
            continue
        same = [
            c
            for c in fresh
            if c["table"] == old["table"] and c["columns"] == old["columns"]
        ]
        if len(same) == 1:
            current["constraints"][index] = json.loads(json.dumps(same[0]))
            fresh.remove(same[0])
        else:
            raise SystemExit(
                f"교체 대상이 하나가 아니다: {old['table']} {old['columns']} → {len(same)}건"
            )

    # 3) 남은 새 제약·관계는 배열 끝에 붙인다.
    current["constraints"].extend(json.loads(json.dumps(c)) for c in fresh)
    mine_relations = {relation_key(r) for r in current["relations"]}
    current["relations"].extend(
        json.loads(json.dumps(r))
        for r in target["relations"]
        if r["source"] in names and relation_key(r) not in mine_relations
    )

    if json.dumps(current, ensure_ascii=False, sort_keys=True) == before:
        return False
    current["version"] = VERSION
    current["task"] = TASK
    current["date"] = DATE
    current["change_log"].append(
        {
            "version": VERSION,
            "task": TASK,
            "date": DATE,
            "change": CHANGE,
            "status": STATUS,
        }
    )
    target["base_task"] = TASK
    return True


def main() -> None:
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(current, target)
    if changed:
        CURRENT.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        TARGET.write_text(
            json.dumps(target, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    tables = sum(1 for t in current["tables"] if t["name"].startswith(f"{SCHEMA}."))
    print(
        json.dumps(
            {
                "changed": changed,
                "version": current["version"],
                "cmms_tables": tables,
                "tables": len(current["tables"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
