"""목표 DB(schema-target.json)를 schema.json에서 처음부터 다시 만든다: DSN-00 기준 복사 → DSN 스크립트를 순서대로.

새 DSN 스크립트를 만들면 STEPS 끝에 붙인다. test_dsn*.py가 "재생성 결과 = 커밋된 목표 파일"을 검사한다.
"""

import copy
import json

import apply_dsn00
import apply_dsn11
import apply_dsn12
import apply_dsn13
import apply_dsn14
import apply_dsn15
import apply_dsn16
import apply_dsn17
import apply_dsn21
import apply_dsn22
import apply_dsn23
import apply_dsn24
import apply_dsn25
import apply_dsn26
import apply_dsn27
import apply_dsn28
import apply_dsn29
import apply_dsn30
import apply_dsn31
import apply_dsn90

STEPS = [
    apply_dsn11,
    apply_dsn12,
    apply_dsn13,
    apply_dsn14,
    apply_dsn15,
    apply_dsn16,
    apply_dsn17,
    apply_dsn21,
    apply_dsn22,
    apply_dsn23,
    apply_dsn24,
    apply_dsn25,
    apply_dsn26,
    apply_dsn27,
    apply_dsn28,
    apply_dsn29,
    apply_dsn30,
    apply_dsn31,
    apply_dsn90,
]


def build():
    current = json.loads(apply_dsn00.SOURCE.read_text(encoding="utf-8"))
    d = apply_dsn00.base(current)
    for step in STEPS:
        step.apply(d)
    # The approved company contract supersedes DSN-31's unimplemented UUID
    # binding plan. Keep the other solutions' target design intact.
    company_tables = {
        t["name"] for t in current["tables"] if t.get("phase") == "GW-COMPANY-02"
    }
    if company_tables:
        d["tables"] = [
            t for t in d["tables"] if t["name"] not in company_tables
        ] + copy.deepcopy([t for t in current["tables"] if t["name"] in company_tables])
        for section, field in [("constraints", "table"), ("relations", "source")]:
            d[section] = [
                x for x in d[section] if x[field] not in company_tables
            ] + copy.deepcopy(
                [x for x in current[section] if x[field] in company_tables]
            )
        step_key = ["workspace_id", "generation_id", "document_id", "id"]
        if not any(
            x["table"] == "gw.approval_step"
            and x["kind"] == "UK"
            and x["columns"] == step_key
            for x in d["constraints"]
        ):
            d["constraints"].extend(
                copy.deepcopy(
                    [
                        x
                        for x in current["constraints"]
                        if x["table"] == "gw.approval_step"
                        and x["kind"] == "UK"
                        and x["columns"] == step_key
                    ]
                )
            )
    return d


if __name__ == "__main__":
    apply_dsn00.TARGET.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("rebuilt", apply_dsn00.TARGET.name, [s.__name__ for s in STEPS])
