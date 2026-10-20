"""Inspect encrypted GW identity intents; never declares restore readiness."""

import argparse
import json
import os

from fs.core.backup import BackupError, private_file
from fs.core.security import journal_review
from fs.core.security.journal import verified_records, verify
from fs.core.security.transaction_proof import classify, summary
from fs.gw.journal_coverage import build as family_coverage
from fs.gw.security_journal import confirm_records, confirmed_digests
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--check-database", action="store_true")
    parser.add_argument("--classify-transactions", action="store_true")
    parser.add_argument(
        "--review-report", help="비공개 새 진단 JSON 파일. 거래 분류를 함께 수행합니다."
    )
    args = parser.parse_args()
    classify_transactions = args.classify_transactions or bool(args.review_report)
    try:
        directory = os.environ["FS_GW_IDENTITY_JOURNAL_DIR"]
        key = private_file(
            os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"], size=32
        ).read_bytes()
        if args.check_database or classify_transactions:
            result, records = verified_records(
                directory, key, args.expected_head, metadata_only=True
            )
            engine = create_engine(os.environ["DATABASE_URL"])
            try:
                with engine.execution_options(
                    isolation_level="REPEATABLE READ", postgresql_readonly=True
                ).begin() as c:
                    result.update(confirm_records(c, records))
                    if classify_transactions:
                        dispositions = classify(
                            c, records, confirmed_digests(c, records)
                        )
                        result.update(summary(dispositions))
                        result["recordingFamilies"] = family_coverage(
                            records, dispositions
                        )
                        if args.review_report:
                            journal_review.write(
                                args.review_report,
                                journal_review.build(result, records, dispositions)
                                | {"recordingFamilies": result["recordingFamilies"]},
                            )
            finally:
                engine.dispose()
        else:
            result = verify(directory, key, args.expected_head)
    except BackupError, OSError, KeyError, ValueError, TypeError, SQLAlchemyError:
        parser.exit(
            1, "기록을 확인하지 못했습니다. 설정·키·파일·별도 최신 지문을 확인하세요.\n"
        )
    print(json.dumps(result, ensure_ascii=False))
    if classify_transactions:
        if not result["allTransactionsSettled"]:
            raise SystemExit(3)
    elif args.check_database and not result["commitsConfirmed"]:
        raise SystemExit(3)


if __name__ == "__main__":
    main()
