"""목표 DB(schema-target.json)를 schema.json에서 처음부터 다시 만든다: DSN-00 기준 복사 → DSN 스크립트를 순서대로.

새 DSN 스크립트를 만들면 STEPS 끝에 붙인다. test_dsn*.py가 "재생성 결과 = 커밋된 목표 파일"을 검사한다.
"""

import json

import apply_dsn00
import apply_dsn11
import apply_dsn12
import apply_dsn13
import apply_dsn14
import apply_dsn15
import apply_dsn16

STEPS = [apply_dsn11, apply_dsn12, apply_dsn13, apply_dsn14, apply_dsn15, apply_dsn16]


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
