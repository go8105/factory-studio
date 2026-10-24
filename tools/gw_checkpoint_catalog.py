"""Publish an operator-owned signed checkpoint catalog; never approve acceptance."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.gw.catalog_store import (
    PENDING,
    PublishContext,
    current,
    digest,
    directory,
    inventory,
    load_private,
    publish,
    read_fd,
)
from fs.gw.evidence_trust import from_environment


def main():
    parser = argparse.ArgumentParser(
        description="GW 서명 목록 로컬 발행 (운영 인수 승인 아님)"
    )
    parser.add_argument(
        "operation", choices=["publish", "refresh", "recover-pending", "status"]
    )
    parser.add_argument(
        "--directory", required=True, help="회사/세대 전용 기존0700 절대 폴더"
    )
    parser.add_argument(
        "--context", required=True, help="0600 현재 회사/세대/정책/버전 JSON"
    )
    parser.add_argument(
        "--expected-pin-digest", help="status에서 별도로 확인한 핀 지문, 최초는 ABSENT"
    )
    parser.add_argument(
        "--initialize", action="store_true", help="빈 폴더의 최초 발행에만 명시"
    )
    parser.add_argument("--head", help="기존 도구의0600 서명 HEAD")
    parser.add_argument("--checkpoint", help="HEAD에 대응하는0600 암호화 대조 파일")
    args = parser.parse_args()
    try:
        context = PublishContext.model_validate(load_private(args.context))
        keys = from_environment()
        if args.operation == "status":
            if any(
                (args.initialize, args.head, args.checkpoint, args.expected_pin_digest)
            ):
                raise ValueError()
            with directory(args.directory) as root:
                catalog, pin, highest = current(
                    root,
                    args.directory,
                    public_keys=keys,
                    workspace_id=context.workspace_id,
                    healthy=False,
                )
                from fs.gw.catalog_store import check_scope

                check_scope(catalog, context)
                names, _ = inventory(root)
                pending = PENDING in names
                catalog_digest = None
                if catalog is not None:
                    raw_pin = read_fd(root, "current-pin.json", 8192)
                    if digest(raw_pin) != pin:
                        raise ValueError("pin changed during status")
                    catalog_digest = json.loads(raw_pin)["digest"]
                report = {
                    "catalogId": catalog.catalog_id if catalog else None,
                    "revision": catalog.revision if catalog else None,
                    "highestStoredRevision": highest,
                    "pinDigest": pin,
                    "catalogDigest": catalog_digest,
                    "pending": pending,
                    "ready": False,
                }
                # A pending file must at least remain a private regular bounded file.
                if pending:
                    read_fd(root, PENDING, 8192)
                print(json.dumps(report, sort_keys=True))
                return (
                    2
                    if pending or highest != (catalog.revision if catalog else 0)
                    else 0
                )
        if (
            not args.expected_pin_digest
            or (args.operation == "publish" and not all((args.head, args.checkpoint)))
            or (
                args.operation != "publish"
                and any((args.initialize, args.head, args.checkpoint))
            )
        ):
            raise ValueError()
        key_path = Path(os.environ["FS_GW_CATALOG_KEY_FILE"])
        with directory(key_path.parent) as root:
            raw = read_fd(root, key_path.name, 32)
        signer = Ed25519PrivateKey.from_private_bytes(raw)
        report = publish(
            args.directory,
            context=context,
            public_keys=keys,
            signer=signer,
            signer_id=os.environ["FS_GW_CATALOG_KEY_ID"],
            now=datetime.now(UTC),
            expected_pin_digest=args.expected_pin_digest,
            operation=args.operation,
            head_path=args.head,
            checkpoint_path=args.checkpoint,
            initialize=args.initialize,
        )
        print(json.dumps(report, sort_keys=True))
        return 0 if report["result"] == "PASS" else 2
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, RecursionError):
        print(
            "목록 처리 차단: 설정·회사/키 권한·예상 핀·보류 발행을 확인하세요. status 확인 전 재시도하지 마세요."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
