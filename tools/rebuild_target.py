"""W2 이후에는 schema.json이 진화해 결과가 목표 파일과 달라진다. 설계 단계 재현용이다.
목표 DB(schema-target.json)를 schema.json에서 처음부터 다시 만든다: DSN-00 기준 복사 → DSN 스크립트를 순서대로.

새 DSN 스크립트를 만들면 STEPS 끝에 붙인다.
"""

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
    d = apply_dsn00.base(json.loads(apply_dsn00.SOURCE.read_text(encoding="utf-8")))
    for step in STEPS:
        step.apply(d)
    return d


if __name__ == "__main__":
    apply_dsn00.TARGET.write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("rebuilt", apply_dsn00.TARGET.name, [s.__name__ for s in STEPS])
