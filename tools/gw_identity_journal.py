"""Inspect encrypted GW identity intents; never declares restore readiness."""

import argparse
import json
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.backup import BackupError, create_private, private_directory, private_file
from fs.core.security import journal_review
from fs.core.security.journal import verified_records, verify
from fs.core.security.journal_witness import expected_head
from fs.core.security.transaction_proof import classify, summary
from fs.gw.backup import policy_snapshot
from fs.gw.evidence_trust import from_environment
from fs.gw.journal_coverage import build as family_coverage
from fs.gw.journal_observation import observe, verify_current
from fs.gw.journal_routes import build as route_coverage
from fs.gw.operating_contract import canonical
from fs.gw.security_journal import confirm_records, confirmed_digests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def observation_command(args):
    engine = None
    try:
        if (
            args.company_id is None
            or args.company_id <= 0
            or args.check_database
            or args.classify_transactions
            or args.review_report
        ):
            raise ValueError()
        if expected_head() != args.expected_head:
            raise ValueError()
        if args.signed_observation:
            output = Path(args.signed_observation)
            private_directory(output.parent)
            if output.exists() or output.is_symlink():
                raise ValueError()
        keys = from_environment()
        url = make_url(os.environ["FS_GW_PREFLIGHT_DATABASE_URL"])
        if (
            url.drivername not in {"postgresql", "postgresql+psycopg"}
            or not url.host
            or not url.database
            or not url.username
        ):
            raise ValueError()
        engine = create_engine(
            url.set(drivername="postgresql+psycopg"),
            connect_args={"connect_timeout": 10},
        )
        args_context = {
            "company_id": args.company_id,
            "code_revision": os.environ["FS_CODE_REVISION"],
            "public_keys": keys,
        }
        if args.signed_observation:
            signer = Ed25519PrivateKey.from_private_bytes(
                private_file(os.environ["FS_GW_RUNNER_KEY_FILE"], size=32).read_bytes()
            )
            document = observe(
                engine,
                signer=signer,
                signer_id=os.environ["FS_GW_RUNNER_KEY_ID"],
                **args_context,
            )
            with create_private(output) as stream:
                stream.write(canonical(document))
                stream.flush()
                os.fsync(stream.fileno())
            result = document["envelope"]
        else:
            source = private_file(args.verify_observation)
            if source.stat().st_size > 16384:
                raise ValueError()
            result = verify_current(
                engine, json.loads(source.read_bytes()), **args_context
            ).model_dump(by_alias=True)
        print(
            json.dumps(
                {
                    "result": result["result"],
                    "ready": False,
                    "scopeRecords": result["scopeRecords"],
                }
            )
        )
        return 0 if result["result"] == "PARTIAL" else 2
    except (
        BackupError,
        ApiError,
        InvalidSignature,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        SQLAlchemyError,
    ):
        print(
            "회사 변경 기록 관측을 완료하지 못했습니다. 현재 기준·최신 지문·읽기 연결·관측 키와 파일 권한을 확인하세요."
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--check-database", action="store_true")
    parser.add_argument("--classify-transactions", action="store_true")
    parser.add_argument(
        "--review-report", help="비공개 새 진단 JSON 파일. 거래 분류를 함께 수행합니다."
    )
    parser.add_argument(
        "--company-id", type=int, help="현재 정책 회사의 GW 연결 7경로 진단"
    )
    observation = parser.add_mutually_exclusive_group()
    observation.add_argument(
        "--signed-observation",
        help="회사 범위 관측을 기록할 새0600 서명 파일 (인수 증거 아님)",
    )
    observation.add_argument(
        "--verify-observation", help="서명 관측을 현재 DB/기록과 다시 대조할0600 파일"
    )
    args = parser.parse_args()
    if args.signed_observation or args.verify_observation:
        return observation_command(args)
    if args.company_id is not None and (
        args.company_id <= 0 or not (args.classify_transactions or args.review_report)
    ):
        parser.error(
            "--company-id는 거래 분류/검토 보고와 함께 양의 정수로 지정하세요."
        )
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
                        if args.company_id is not None:
                            result["identityRoutes"] = route_coverage(
                                records,
                                dispositions,
                                scope=policy_snapshot(c, args.company_id),
                                code_revision=os.environ["FS_CODE_REVISION"],
                                db_revision=c.execute(
                                    text("SELECT version_num FROM alembic_version")
                                ).scalar_one(),
                                head=result["head"],
                            )
                        if args.review_report:
                            journal_review.write(
                                args.review_report,
                                journal_review.build(result, records, dispositions)
                                | {"recordingFamilies": result["recordingFamilies"]}
                                | (
                                    {"identityRoutes": result["identityRoutes"]}
                                    if "identityRoutes" in result
                                    else {}
                                ),
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
    raise SystemExit(main())
