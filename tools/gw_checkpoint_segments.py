"""Offline bounded segment transfer; no issuer private key or intermediate activation."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from fs.gw import catalog_segments as segments
from fs.gw import catalog_store as store
from fs.gw.evidence_trust import from_environment


def private_bytes(path, limit, *, allow_empty=False):
    path = Path(path)
    with store.directory(path.parent) as root:
        return store.read_fd(root, path.name, limit, allow_empty=allow_empty)


def main():
    parser = argparse.ArgumentParser(
        description="GW 목록 분할 전달/수신 (운영 인수 승인 아님)"
    )
    sub = parser.add_subparsers(dest="operation", required=True)
    outgoing = sub.add_parser("export")
    incoming = sub.add_parser("receive")
    status = sub.add_parser("status")
    for part in (outgoing, incoming, status):
        part.add_argument("--directory", required=True)
        part.add_argument("--context", required=True)
    outgoing.add_argument(
        "--output-directory", required=True, help="새 빈0700 절대 폴더"
    )
    outgoing.add_argument("--from-revision", required=True, type=int)
    outgoing.add_argument("--from-catalog-digest", required=True)
    for part in (incoming, status):
        part.add_argument(
            "--manifest", required=True, help="별도0700 폴더의0600 manifest.json"
        )
        part.add_argument(
            "--expected-manifest-digest",
            required=True,
            help="별도 신뢰 경로로 확인한 최종 전달 명세 지문",
        )
        part.add_argument("--expected-catalog-id", required=True)
        part.add_argument("--expected-pin-digest", required=True)
    incoming.add_argument("--initialize", action="store_true")
    incoming.add_argument("--resume", action="store_true")
    incoming.add_argument("--part-number", type=int)
    incoming.add_argument("--part-file", help="nextPart에 해당하는0600 part-NNNNN.bin")
    args = parser.parse_args()
    try:
        context = store.PublishContext.model_validate(store.load_private(args.context))
        keys = from_environment()
        now = datetime.now(UTC)
        if args.operation == "export":
            report = segments.export(
                args.directory,
                args.output_directory,
                context=context,
                public_keys=keys,
                now=now,
                base_revision=args.from_revision,
                base_digest=args.from_catalog_digest,
            )
            print(json.dumps(report, sort_keys=True))
            return 0
        if Path(args.manifest).parent.resolve() == Path(args.directory).resolve():
            raise ValueError("separate package required")
        try:
            raw = private_bytes(args.manifest, segments.MAX_PLAN)
        except (OSError, ValueError):
            raw = b""  # The separately confirmed anchor still fences the old pin.
        part_raw = None
        if args.operation == "receive" and args.part_file:
            if Path(args.part_file).parent.resolve() == Path(args.directory).resolve():
                raise ValueError("separate part required")
            try:
                part_raw = private_bytes(
                    args.part_file, store.MAX_BYTES, allow_empty=True
                )
            except (OSError, ValueError):
                pass
        if args.operation == "receive" and bool(args.part_file) != (
            args.part_number is not None
        ):
            raise ValueError("part number and file required together")
        report = segments.receive(
            args.directory,
            raw,
            context=context,
            public_keys=keys,
            now=now,
            expected_manifest_digest=args.expected_manifest_digest,
            expected_catalog_id=args.expected_catalog_id,
            expected_pin_digest=args.expected_pin_digest,
            initialize=getattr(args, "initialize", False),
            resume=getattr(args, "resume", False),
            part_number=getattr(args, "part_number", None),
            part_raw=part_raw,
            status=args.operation == "status",
        )
        print(json.dumps(report, sort_keys=True))
        return (
            0
            if report["state"] == "COMPLETE"
            and report.get("result") == "PASS"
            and report["targetFresh"]
            and report["contextMatches"]
            else 2
        )
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, RecursionError):
        print(
            "분할 수신 차단: 별도 명세 지문·현재 핀·같은 원본과 보류 상태를 확인하세요. 자동 초기화하지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
