"""Publish an encrypted snapshot then authenticate a separate delivery receipt."""

import argparse
import json
import os

from fs.core.backup import BackupError, private_file
from fs.core.security.journal_witness import latest, publish


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["publish", "check"])
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--expected-head")
    group.add_argument("--advance", action="store_true")
    parser.add_argument("--bundles")
    args = parser.parse_args()
    try:
        directory = os.environ["FS_GW_JOURNAL_WITNESS_DIR"]
        key = private_file(
            os.environ["FS_GW_JOURNAL_WITNESS_KEY_FILE"], size=32
        ).read_bytes()
        if args.action == "publish":
            if not (args.expected_head or args.advance) or not args.bundles:
                raise BackupError("독립 최신 지문과 사본 보관 폴더가 필요합니다.")
            result = publish(
                os.environ["FS_GW_IDENTITY_JOURNAL_DIR"],
                private_file(
                    os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"], size=32
                ).read_bytes(),
                args.expected_head,
                args.bundles,
                directory,
                key,
            )
        else:
            result = latest(
                directory,
                key,
                max_age=int(
                    os.environ.get("FS_GW_JOURNAL_WITNESS_MAX_AGE_SECONDS", "1800")
                ),
                minimum_sequence=int(
                    os.environ.get("FS_GW_JOURNAL_WITNESS_MIN_SEQUENCE", "1")
                ),
            )
        print(
            json.dumps(
                {
                    **result,
                    "externalDurabilityConfirmed": False,
                    "releaseAuthorized": False,
                },
                ensure_ascii=False,
            )
        )
    except (BackupError, OSError, ValueError, TypeError, KeyError):
        parser.exit(
            1, "전달 확인에 실패했습니다. 경로·별도 키·최신 지문·현재성을 확인하세요.\n"
        )


if __name__ == "__main__":
    main()
