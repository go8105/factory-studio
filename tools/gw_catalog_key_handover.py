"""Attest exact catalog history before planned retirement; never install trust settings."""

import argparse
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.gw import catalog_key_handover as handover
from fs.gw import catalog_store as store
from fs.gw.evidence_trust import from_environment


def private_key(variable):
    path = Path(os.environ[variable])
    with store.directory(path.parent) as root:
        return Ed25519PrivateKey.from_private_bytes(store.read_fd(root, path.name, 32))


def main():
    parser = argparse.ArgumentParser(
        description="GW 목록 키 정상 이관 근거 생성/현재 상태 (운영 인수 승인 아님)"
    )
    parser.add_argument("operation", choices=["issue", "extend", "inspect"])
    parser.add_argument("--context", required=True)
    parser.add_argument("--retiring-key-id", required=True)
    parser.add_argument("--directory")
    parser.add_argument("--expected-pin-digest")
    parser.add_argument("--output")
    parser.add_argument("--predecessor-key-id")
    parser.add_argument("--parent-file")
    parser.add_argument("--expected-parent-digest")
    parser.add_argument("--retiring-handover-file")
    parser.add_argument("--expected-retiring-handover-digest")
    args = parser.parse_args()
    continuation = (
        args.predecessor_key_id,
        args.parent_file,
        args.expected_parent_digest,
        args.retiring_handover_file,
        args.expected_retiring_handover_digest,
    )
    try:
        context = store.PublishContext.model_validate(store.load_private(args.context))
        public = from_environment()
        if args.operation == "inspect":
            if (
                any(
                    (
                        args.directory,
                        args.expected_pin_digest,
                        args.output,
                        *continuation,
                    )
                )
                or public.catalog_lifecycle is None
            ):
                raise ValueError("configured lifecycle required")
            record = public.catalog_lifecycle.records[
                str(context.workspace_id), args.retiring_key_id
            ]
            print(
                json.dumps(
                    {
                        "keyId": args.retiring_key_id,
                        "state": record.state,
                        "approvedDocuments": len(record.documents),
                        "ready": False,
                    },
                    sort_keys=True,
                )
            )
            return 2
        if (
            not all((args.directory, args.expected_pin_digest, args.output))
            or args.retiring_key_id != os.environ["FS_GW_CATALOG_KEY_ID"]
        ):
            raise ValueError("explicit source CAS and current retiring key required")
        output = Path(args.output)
        if output.parent.resolve() == Path(args.directory).resolve():
            raise ValueError("separate output required")
        extras = {}
        action = handover.issue
        if args.operation == "extend":
            from fs.gw.catalog_key_chain import extend

            if not all(continuation):
                raise ValueError("explicit pinned predecessor/own handover required")

            def read_approval(value):
                path = Path(value)
                with store.directory(path.parent) as root:
                    return store.read_fd(root, path.name, handover.MAX_BYTES)

            extras = {
                "parent_raw": read_approval(args.parent_file),
                "retiring_handover_raw": read_approval(args.retiring_handover_file),
                "predecessor_id": args.predecessor_key_id,
                "expected_parent_digest": args.expected_parent_digest,
                "expected_retiring_handover_digest": args.expected_retiring_handover_digest,
            }
            action = extend
        elif any(continuation):
            raise ValueError("continuation options require extend")
        raw, report = action(
            args.directory,
            context=context,
            public_keys=public,
            retiring_signer=private_key("FS_GW_CATALOG_KEY_FILE"),
            retiring_id=args.retiring_key_id,
            successor_signer=private_key("FS_GW_CATALOG_SUCCESSOR_KEY_FILE"),
            successor_id=os.environ["FS_GW_CATALOG_SUCCESSOR_KEY_ID"],
            now=datetime.now(UTC),
            expected_pin_digest=args.expected_pin_digest,
            **extras,
        )
        with store.directory(output.parent) as root:
            store.write_new(root, output.name, raw)
        print(json.dumps(report, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, RecursionError):
        print(
            "키 이관 차단: 현재 권한·두 발행 키·정확한 보존 원본/핀·정상 교체와 회수 상태를 확인하세요. 신뢰 설정을 자동 변경하지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
