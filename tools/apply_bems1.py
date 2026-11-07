#!/usr/bin/env python3
"""BEMS-1a: 승인된 목표 설계(schema-target.json)의 BEMS 보강을 제품 설계(schema.json)로 옮긴다.

BEMS는 FS-025로 구역·계측·센서·공조·경보까지 돌고 있다. 이 단계는 그 DB를 목표 설계(DSN-16)까지 올린다.
  - 새 표 11개 (건물, 조명 회로, 피크 감축안·단계, 쾌적 기준, 설비 경보 규칙·경보,
    건물 에너지 목표, 공용 비용 배분 실행·배분, 월간 건물 보고서)
  - 기존 표 변경 (구역 건물·층·부서, 공조기 감축 우선순위, 스케줄·제어 명령의 조명 회로,
    센서 지표 3 → 6, 스케줄 요일 HOLIDAY·모드 ON, 제어 출처 PEAK) — 제약 제자리 교체
  - `core.holiday`는 이미 있다(FEMS-1c가 날짜로 읽는다). 이 단계에서 바꾸지 않는다.

본보기는 `apply_fems1.py`다(`sync_nullable()` 포함). 제약·관계는 **배열 끝에 붙이고**, 교체하는
제약만 제자리에서 바꾼다(순번이 곧 DB 제약 이름이라 끼워 넣으면 기존 DB와 어긋난다).

마이그레이션은 tools/build_migration.py --previous 가 이 결과로 만든다. 멱등(두 번 돌려도 같다).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
VERSION = "0.35.0"
TASK = "BEMS-1a"
DATE = "2026-11-07"
SCHEMA = "bems"
CHANGE = (
    "BEMS 보강: 새 표 11개(건물, 조명 회로, 피크 감축안·단계, 쾌적 기준, 설비 경보 규칙·경보, "
    "건물 에너지 목표, 공용 비용 배분 실행·배분, 월간 건물 보고서)와 기존 표 변경(구역 건물·층·부서, "
    "공조기 감축 우선순위, 스케줄·제어 명령의 조명 회로, 센서 지표 6종, 스케줄 요일 HOLIDAY·모드 ON, "
    "제어 출처 PEAK). 목표 설계 DSN-16에서 그대로 옮김"
)
STATUS = "마이그레이션 bems1 적용 대상"
# 칼럼이 늘어 제자리 교체 대상을 칼럼으로 찾을 수 없는 제약(QMS-1a의 특례). FEMS에는 없다.
WIDENED: set[tuple[str, str]] = set()


def key(c: dict[str, Any]) -> tuple:
    return (
        c["table"],
        c["kind"],
        tuple(c.get("columns") or []),
        c.get("expression", ""),
    )


def relation_key(r: dict[str, Any]) -> tuple:
    return (r["source"], tuple(r["columns"]), r["target"], tuple(r["target_columns"]))


def sync_nullable(current: dict, wanted: list[dict]) -> list[str]:
    """기존 칼럼의 NULL 허용을 목표와 맞춘다. 푸는 방향만 허용한다.

    `spc2`·`cmms2`가 이것을 빠뜨려 따로 생겼다. NOT NULL로 조이는 변경은 기존 행이
    비어 있지 않은지 확인해야 하므로 여기서 하지 않고 멈춘다.
    """
    goals = {t["name"]: {c["name"]: c for c in t["columns"]} for t in wanted}
    loosened = []
    for table in current["tables"]:
        columns = goals.get(table["name"])
        if columns is None:
            continue
        for column in table["columns"]:
            goal = columns.get(column["name"])
            if goal is None or goal["nullable"] == column["nullable"]:
                continue
            if not goal["nullable"]:
                raise SystemExit(
                    f"{table['name']}.{column['name']}: "
                    "NOT NULL로 조이는 변경은 기존 행 확인이 필요하다"
                )
            column["nullable"] = True
            loosened.append(f"{table['name']}.{column['name']}")
    return loosened


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

    sync_nullable(current, wanted)

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
        if not same and (old["table"], old["kind"]) in WIDENED:
            # 칸이 늘어난 제약은 칼럼으로 못 잡는다. 표·종류가 하나뿐일 때만 짝지어 제자리에 둔다.
            same = [
                c
                for c in fresh
                if c["table"] == old["table"] and c["kind"] == old["kind"]
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
                "bems_tables": tables,
                "tables": len(current["tables"]),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
