"""Inspect encrypted GW identity intents; never declares restore readiness."""

import argparse
import json
import os

from fs.core.backup import BackupError, private_file
from fs.core.security.journal import verified_records, verify
from fs.gw.security_journal import confirm_records
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--check-database", action="store_true")
    args = parser.parse_args()
    try:
        directory = os.environ["FS_GW_IDENTITY_JOURNAL_DIR"]
        key = private_file(
            os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"], size=32
        ).read_bytes()
        if args.check_database:
            result, records = verified_records(directory, key, args.expected_head)
            engine = create_engine(os.environ["DATABASE_URL"])
            try:
                with engine.execution_options(
                    isolation_level="REPEATABLE READ", postgresql_readonly=True
                ).begin() as c:
                    result.update(confirm_records(c, records))
            finally:
                engine.dispose()
        else:
            result = verify(directory, key, args.expected_head)
    except (BackupError, OSError, KeyError, ValueError, TypeError, SQLAlchemyError):
        parser.exit(
            1, "기록을 확인하지 못했습니다. 설정·키·파일·별도 최신 지문을 확인하세요.\n"
        )
    print(json.dumps(result, ensure_ascii=False))
    if args.check_database and not result["commitsConfirmed"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
