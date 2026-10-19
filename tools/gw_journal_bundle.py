"""Export/verify an encrypted journal snapshot without resetting the live chain."""

import argparse
import json
import os

from fs.core.backup import BackupError, private_file
from fs.core.security.journal_bundle import export, inspect


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["export", "verify"])
    parser.add_argument("--expected-head", required=True)
    parser.add_argument("--bundle", required=True)
    args = parser.parse_args()
    try:
        key = private_file(
            os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"], size=32
        ).read_bytes()
        if args.action == "export":
            state = export(
                os.environ["FS_GW_IDENTITY_JOURNAL_DIR"],
                key,
                args.expected_head,
                args.bundle,
            )
        else:
            state = inspect(args.bundle, key, args.expected_head)
    except (BackupError, OSError, KeyError, ValueError, TypeError):
        parser.exit(
            1,
            "기록 묶음을 확인하지 못했습니다. 비공개 경로·키·독립 최신 지문을 확인하세요.\n",
        )
    print(
        json.dumps(
            {
                **state,
                "bundleVerified": True,
                "sourceRotated": False,
                "externalDurabilityConfirmed": False,
                "releaseAuthorized": False,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
