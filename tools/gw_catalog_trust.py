"""Explicit local trust-floor installation and irreversible revocation; no live env edits."""

import argparse
import json
import os

from cryptography.exceptions import InvalidSignature
from fs.gw import catalog_trust_store as floor
from fs.gw.evidence_trust import configured_environment


def main():
    parser = argparse.ArgumentParser(
        description="GW 목록 신뢰 이력 (로컬 보존, 운영 인수 승인 아님)"
    )
    parser.add_argument(
        "operation", choices=["initialize", "advance", "revoke", "status", "resume"]
    )
    parser.add_argument("--expected-digest")
    parser.add_argument("--workspace-id")
    parser.add_argument("--key-id")
    args = parser.parse_args()
    try:
        path = os.environ[floor.ENV]
        if args.operation == "status":
            if any((args.expected_digest, args.workspace_id, args.key_id)):
                raise ValueError("unexpected options")
            head, sha = floor.inspect(path)
        elif args.operation == "revoke":
            if not all((args.expected_digest, args.workspace_id, args.key_id)):
                raise ValueError("revocation identity and CAS required")
            head, sha = floor.revoke(
                path,
                workspace_id=args.workspace_id,
                key_id=args.key_id,
                expected_digest=args.expected_digest,
            )
        else:
            if args.workspace_id or args.key_id or not args.expected_digest:
                raise ValueError("CAS required")
            if args.operation == "resume":
                head, sha = floor.resume(path, expected_digest=args.expected_digest)
            else:
                head, sha = floor.commit(
                    path,
                    configured_environment(),
                    expected_digest=args.expected_digest,
                    initialize=args.operation == "initialize",
                )
        print(
            json.dumps(
                {
                    "revision": head.revision,
                    "digest": sha,
                    "revokedKeys": sum(a.state == "REVOKED" for a in head.authorities),
                    "ready": False,
                },
                sort_keys=True,
            )
        )
        return 2 if args.operation == "status" else 0
    except (OSError, ValueError, KeyError, TypeError, InvalidSignature, RecursionError):
        print(
            "목록 신뢰 이력 차단: 보존 경로·현재 지문/권한·원본과 회수 상태를 확인하세요. 과거 설정으로 초기화하지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
