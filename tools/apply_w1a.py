#!/usr/bin/env python3
"""W1a: 승인된 목표 설계(schema-target.json)의 HR과 공통 휴일 달력을 제품 설계(schema.json)로 옮긴다.

일괄 개발 W1(사람 원천)의 DB 단계. 목표 설계에서 **그대로** 복사하므로 설계와 제품이 갈라지지 않는다.
  - hr 19테이블 (DSN-30)
  - core.holiday (DSN-16 Q1 — HR 근태 자동 생성이 읽는다)
  - 모듈 키 'hr' (core.workspace_module · core.app_review)

마이그레이션은 tools/build_migration.py가 이 결과로 만든다. 멱등(두 번 돌려도 같다).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CURRENT = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
VERSION = "0.19.0"
TASK = "W1a"
NEW_TABLES = ("core.holiday",)
NEW_SCHEMAS = ("hr",)


def wanted(name: str) -> bool:
    return name in NEW_TABLES or name.split(".", 1)[0] in NEW_SCHEMAS


def apply(current: dict, target: dict) -> bool:
    """current를 제자리에서 바꾸고, 바뀌었으면 True."""
    have = {t["name"] for t in current["tables"]}
    add = [t for t in target["tables"] if wanted(t["name"]) and t["name"] not in have]
    if not add:
        return False
    names = {t["name"] for t in add}
    current["tables"].extend(add)
    current["constraints"].extend(
        c for c in target["constraints"] if c["table"] in names
    )
    current["relations"].extend(r for r in target["relations"] if r["source"] in names)
    current["states"].extend(s for s in target.get("states", []) if s["table"] in names)
    current["code_lists"].extend(
        c for c in target.get("code_lists", []) if c["target"] in names
    )
    # 모듈 키 'hr'만 더한다. 아직 만들지 않은 솔루션 키는 제품에 넣지 않는다.
    for table in ("core.workspace_module", "core.app_review"):
        for c in current["constraints"]:
            if (
                c["table"] == table
                and c["kind"] == "CHECK"
                and "module_key IN" in c["expression"]
                and "'hr'" not in c["expression"]
            ):
                c["expression"] = c["expression"].rstrip(")") + ", 'hr')"
        for code in current["code_lists"]:
            if (
                code["target"] == table
                and code["column"] == "module_key"
                and "hr" not in code["values"]
            ):
                code["values"] = [*code["values"], "hr"]
    current.update(version=VERSION, task=TASK, date="2026-10-06")
    current["change_log"].append(
        dict(
            version=VERSION,
            task=TASK,
            date="2026-10-06",
            change=(
                "HR 19테이블(조직·사원·발령·자격/교육·근태·마감·연차·휴가·급여 항목/기준/수당/상여/실행/명세·평가)과 "
                "core.holiday(공통 휴일 달력), 모듈 키 hr. 목표 설계 DSN-30·DSN-16에서 그대로 옮김"
            ),
            status="마이그레이션 w1a_hr 적용 대상",
        )
    )
    return True


def main() -> None:
    current = json.loads(CURRENT.read_text(encoding="utf-8"))
    target = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(current, target)
    if changed:
        CURRENT.write_text(
            json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            dict(
                changed=changed,
                version=current["version"],
                task=current["task"],
                tables=len(current["tables"]),
                hr=sum(t["name"].startswith("hr.") for t in current["tables"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
