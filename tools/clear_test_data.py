"""CI 마이그레이션 왕복(downgrade base → upgrade head) 전에 테스트 DB의 업무 데이터를 비운다.

FS-026a downgrade는 입고·예약·격리 데이터가 있으면 운영 데이터를 지키려고 거부한다. pytest가 남긴
시드·게스트 데이터 때문에 CI 왕복이 멈추지 않게, 왕복 직전에만 이 도구로 비운다(2026-10-01).
모든 업무 행은 core.data_generation을 범위 앵커로 참조하므로 core를 CASCADE로 비우면 함께 비워진다.
안전장치: DB 이름이 `_test`로 끝나지 않으면 아무것도 하지 않고 실패한다(운영·개발 DB 보호).
"""

import os
import sys

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main() -> int:
    url = make_url(os.environ["DATABASE_URL"])
    if not (url.database or "").endswith("_test"):
        print(
            f"거부: 테스트 DB가 아닙니다({url.database}). 이름이 _test로 끝나야 합니다.",
            file=sys.stderr,
        )
        return 1
    engine = create_engine(url)
    with engine.begin() as connection:
        tables = [
            f'"core"."{table}"'
            for table in inspect(connection).get_table_names(schema="core")
            if table != "alembic_version"
        ]
        connection.execute(
            text(f"TRUNCATE {','.join(tables)} RESTART IDENTITY CASCADE")
        )
    print(
        f"{url.database}: core {len(tables)}개 테이블과 참조하는 업무 데이터를 비웠다."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
