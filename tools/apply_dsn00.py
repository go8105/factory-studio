"""DSN-00: 목표 DB(schema-target.json)의 출발점 = 지금 schema.json 복사 + 목표 머리 정보.

목표 파일 전체 재생성: python3 tools/apply_dsn00.py --rebuild && python3 tools/apply_dsn11.py (이후 DSN 스크립트를 순서대로)
목표 파일이 이미 있으면 --rebuild 없이는 덮어쓰지 않는다(쌓인 설계를 지우지 않게).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs/db/schema-metadata/schema.json"
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"


def base(current):
    head = dict(
        version="target-0.1.0",
        task="DSN-00",
        base_task=current["task"],
        target=True,
        date="2026-10-05",
        status="목표 설계(ROADMAP-02 D78) — 실제 DB 아님. 개발 때 schema.json과의 차이를 마이그레이션으로 옮긴다",
        migration_revision=None,
    )
    out = {**head, **{k: v for k, v in current.items() if k not in head}}
    out["change_log"] = current["change_log"] + [
        dict(
            version="target-0.1.0",
            task="DSN-00",
            date="2026-10-05",
            change=f"목표 설계 시작: schema.json {current['version']}/{current['task']} 복사({len(current['tables'])}테이블). 이후 DSN-11~ 보강·신규 설계를 여기에 쌓는다",
            status="설계 전용",
        )
    ]
    return out


def main():
    if TARGET.exists() and "--rebuild" not in sys.argv:
        raise SystemExit(
            "schema-target.json이 이미 있다. 전체 재생성이면 --rebuild 후 DSN 스크립트를 순서대로 다시 실행한다"
        )
    TARGET.write_text(
        json.dumps(
            base(json.loads(SOURCE.read_text(encoding="utf-8"))),
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("rebuilt", TARGET.relative_to(ROOT))


if __name__ == "__main__":
    main()
