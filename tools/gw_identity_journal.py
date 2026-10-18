"""Inspect encrypted GW identity intents; never declares restore readiness."""

import argparse
import json
import os

from fs.core.backup import BackupError, private_file
from fs.core.security.journal import verify


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args()
    try:
        result = verify(
            os.environ["FS_GW_IDENTITY_JOURNAL_DIR"],
            private_file(
                os.environ["FS_GW_IDENTITY_JOURNAL_KEY_FILE"], size=32
            ).read_bytes(),
            args.expected_head,
        )
    except (BackupError, OSError, KeyError, ValueError, TypeError):
        parser.exit(
            1, "기록을 확인하지 못했습니다. 설정·키·파일·별도 최신 지문을 확인하세요.\n"
        )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
