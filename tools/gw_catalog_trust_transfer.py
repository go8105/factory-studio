"""Export/reconstruct trust originals with operator-confirmed latest pins; no env install."""

import argparse
import json

from fs.gw import catalog_trust_transfer as transfer


def main():
    parser = argparse.ArgumentParser(
        description="GW 신뢰 이력 전달/별도 폴더 복구 (운영 인수 승인 아님)"
    )
    parser.add_argument("operation", choices=["export", "receive"])
    parser.add_argument("--directory", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--expected-ledger-id", required=True)
    parser.add_argument("--expected-revision", required=True, type=int)
    parser.add_argument("--expected-digest", required=True)
    parser.add_argument("--expected-manifest-digest")
    parser.add_argument("--existing-directory")
    parser.add_argument("--new-host", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    try:
        anchor = transfer.Anchor(
            version=1,
            ledgerId=args.expected_ledger_id,
            revision=args.expected_revision,
            digest=args.expected_digest,
        )
        if args.operation == "export":
            if any(
                (
                    args.expected_manifest_digest,
                    args.existing_directory,
                    args.new_host,
                    args.resume,
                )
            ):
                raise ValueError("unexpected export options")
            result = transfer.export(args.directory, args.output, anchor=anchor)
        else:
            if not args.expected_manifest_digest:
                raise ValueError("confirmed manifest pin required")
            result = transfer.receive(
                args.directory,
                args.output,
                anchor=anchor,
                expected_manifest_digest=args.expected_manifest_digest,
                origin=args.existing_directory,
                new_host=args.new_host,
                resume=args.resume,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        print(
            "신뢰 이력 전달/복구 차단: 별도 확인한 최신 원장·버전/지문, 모든 원본과 기존 보존 상태를 확인하세요. 손상 원본과 서버 사용 경로를 자동 변경하지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
