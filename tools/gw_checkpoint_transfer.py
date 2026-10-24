"""Offline catalog transfer; operators deliver trust fingerprints separately."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from fs.gw import catalog_store as store
from fs.gw.catalog_transfer import MAX_TRANSFER, export, install
from fs.gw.evidence_trust import from_environment


def main():
    parser = argparse.ArgumentParser(
        description="GW 서명 목록 오프라인 전달/수신 (외부 인수 승인 아님)"
    )
    sub = parser.add_subparsers(dest="operation", required=True)
    outgoing = sub.add_parser("export")
    incoming = sub.add_parser("install")
    for part in (outgoing, incoming):
        part.add_argument(
            "--directory", required=True, help="운영자 소유0700 절대 폴더"
        )
        part.add_argument(
            "--context", required=True, help="현재 회사/세대/정책/버전0600 JSON"
        )
    outgoing.add_argument("--from-revision", required=True, type=int)
    outgoing.add_argument("--from-catalog-digest", required=True)
    outgoing.add_argument(
        "--output", required=True, help="별도0700 폴더의 새0600 전달 파일"
    )
    incoming.add_argument("--transfer", required=True, help="별도로 전달받은0600 파일")
    incoming.add_argument(
        "--expected-transfer-digest",
        required=True,
        help="별도 경로로 확인한 전체 전달 파일 지문",
    )
    incoming.add_argument(
        "--expected-catalog-id", required=True, help="별도 경로로 확인한 목록 식별자"
    )
    incoming.add_argument(
        "--expected-pin-digest",
        required=True,
        help="수신 측 현재 핀 지문, 최초는 ABSENT",
    )
    incoming.add_argument("--initialize", action="store_true")
    incoming.add_argument(
        "--resume",
        action="store_true",
        help="같은 전달 파일의 보류/완료 응답 유실 재시도만 허용",
    )
    args = parser.parse_args()
    try:
        context = store.PublishContext.model_validate(store.load_private(args.context))
        keys = from_environment()
        now = datetime.now(UTC)
        if args.operation == "export":
            path = Path(args.output)
            if path.parent == Path(args.directory):
                raise ValueError()
            raw, report = export(
                args.directory,
                context=context,
                public_keys=keys,
                now=now,
                base_revision=args.from_revision,
                base_digest=args.from_catalog_digest,
            )
            with store.directory(path.parent) as root:
                store.write_new(root, path.name, raw)
            print(json.dumps(report, sort_keys=True))
            return 0
        path = Path(args.transfer)
        if path.parent == Path(args.directory):
            raise ValueError()
        try:
            with store.directory(path.parent) as root:
                raw = store.read_fd(root, path.name, MAX_TRANSFER)
        except (OSError, ValueError):
            # A confirmed new anchor with missing/unreadable bytes fences the old pin too.
            raw = b""
        report = install(
            args.directory,
            raw,
            context=context,
            public_keys=keys,
            now=now,
            expected_transfer_digest=args.expected_transfer_digest,
            expected_catalog_id=args.expected_catalog_id,
            expected_pin_digest=args.expected_pin_digest,
            initialize=args.initialize,
            resume=args.resume,
        )
        print(json.dumps(report, sort_keys=True))
        return (
            0
            if report["result"] == "PASS"
            and report["contextMatches"]
            and report["targetFresh"]
            else 2
        )
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, RecursionError):
        print(
            "목록 전달 차단: 별도 신뢰 지문·현재 수신 핀·중간 서명 이력·보류 상태를 확인하세요. 자동 초기화하지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
