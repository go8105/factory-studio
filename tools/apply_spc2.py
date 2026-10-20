#!/usr/bin/env python3
"""SPC-1c: SPC-1a가 빠뜨린 **기존 칼럼의 NULL 허용**을 목표 설계에서 옮긴다.

`apply_spc1.py`는 표·칼럼을 **더하기만** 한다. DSN-17 4-2가 요구한
`spc.subgroup.xbar`·`r`과 `spc.control_limit`의 X̄·R 칸 NULL 허용은 그래서 빠졌고,
이미 적용한 CHECK(계수형 부분군은 xbar가 NULL이어야 한다)가 만족될 수 없는 상태가 됐다.
계량형(X̄-R·I-MR)은 영향이 없지만 계수형(P·NP·C·U)은 행을 넣을 수 없다.

`spc1`은 이미 적용·병합했으므로 고치지 않고 새 revision(`spc2`)으로 처리한다.

NOT NULL을 **푸는 방향만** 허용한다. 반대로 조이는 것은 기존 행을 확인해야 하므로 거부한다.
멱등(두 번 돌려도 같다).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
VERSION = "0.29.0"
TASK = "SPC-1c"
DATE = "2026-10-20"
SCHEMA = "spc"
CHANGE = (
    "SPC-1a 보완: 기존 칼럼의 NULL 허용을 목표 설계와 맞춤 "
    "(spc.subgroup.xbar·r, spc.control_limit.xbar_cl·xbar_ucl·xbar_lcl·r_cl·r_ucl·r_lcl). "
    "계수형 관리도(P·NP·C·U) 부분군은 이 칸이 비어야 해서 지금 구조로는 넣을 수 없었다"
)
STATUS = "마이그레이션 spc2 적용 대상"


def apply(current: dict, target: dict) -> list[str]:
    """current를 제자리에서 바꾸고, 바꾼 칼럼 이름을 돌려준다."""
    wanted = {
        t["name"]: {c["name"]: c for c in t["columns"]}
        for t in target["tables"]
        if t["name"].startswith(f"{SCHEMA}.")
    }
    changed = []
    for table in current["tables"]:
        columns = wanted.get(table["name"])
        if columns is None:
            continue
        for column in table["columns"]:
            goal = columns.get(column["name"])
            if goal is None or goal["nullable"] == column["nullable"]:
                continue
            if not goal["nullable"]:
                raise SystemExit(
                    f"{table['name']}.{column['name']}: NOT NULL로 조이는 변경은 기존 행 확인이 필요하다"
                )
            column["nullable"] = True
            changed.append(f"{table['name']}.{column['name']}")
    if not changed:
        return []
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
    return changed


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
    print(
        json.dumps(
            {"changed": changed, "version": current["version"]}, ensure_ascii=False
        )
    )


if __name__ == "__main__":
    main()
