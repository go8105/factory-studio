"""Server operator approves a one-use recovery grant; never issues a business session.

Run only on the server with its DB credentials/key access and separately held kit.
The target still needs their password. No password/secret is printed or taken on argv.
"""

import argparse
import json
import os
import stat
from pathlib import Path

from fs.common.errors import ApiError
from fs.core.security.config import security_settings
from fs.core.security.emergency import EmergencyKit
from fs.gw.emergency import approve
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError


def run(kit_path, output_path, reason, *, company_id, user_id):
    if not 2 <= len(reason.strip()) <= 500:
        raise ValueError("복구 승인 사유를 2~500자로 입력하세요.")
    if not hasattr(os, "geteuid"):
        raise ValueError("서버 운영자 UID를 확인할 수 없습니다.")
    if kit_path.stat().st_size > 8192:
        raise ValueError("복구 문서 크기를 확인하세요.")
    settings = security_settings()
    if settings.box is None or settings.mode == "PUBLIC_DEMO":
        raise ValueError("회사 서버의 보안 모드와 별도 키가 필요합니다.")
    kit_stat = kit_path.lstat()
    if (
        not stat.S_ISREG(kit_stat.st_mode)
        or kit_stat.st_uid != os.geteuid()
        or kit_stat.st_mode & 0o077
    ):
        raise ValueError("복구 문서를 본인 전용 일반 파일(0600)로 보관하세요.")
    parent = Path(output_path).parent.stat()
    if parent.st_uid != os.geteuid() or parent.st_mode & 0o022:
        raise ValueError(
            "출력 폴더는 운영자 소유이며 다른 사용자가 쓸 수 없어야 합니다."
        )
    kit = EmergencyKit.model_validate(json.loads(kit_path.read_text()))
    if kit.company_id != str(company_id) or kit.user_id != str(user_id):
        raise ValueError("선택한 회사·관리자와 복구 문서가 일치하지 않습니다.")
    engine = create_engine(os.environ["DATABASE_URL"])
    descriptor = os.open(output_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    written = False
    try:
        with os.fdopen(descriptor, "w") as output, engine.begin() as c:
            data, error = approve(c, kit, os.geteuid(), reason.strip())
            if error is None:
                output.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
                output.flush()
                os.fsync(output.fileno())
                written = True
        if error:
            raise error
    except BaseException:
        if not written:
            Path(output_path).unlink(missing_ok=True)
        raise
    finally:
        engine.dispose()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--kit-file", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--reason", required=True)
    p.add_argument("--company-id", type=int, required=True)
    p.add_argument("--user-id", type=int, required=True)
    args = p.parse_args()
    try:
        run(
            args.kit_file,
            args.output,
            args.reason,
            company_id=args.company_id,
            user_id=args.user_id,
        )
    except (ApiError, ValidationError, ValueError, OSError, KeyError, SQLAlchemyError):
        p.exit(
            1,
            "승인하지 못했습니다. 문서·현재 권한·기한·서버 설정과 비공개 파일 경로를 확인하세요. 출력 파일이 남아 있으면 보존하고 상태를 확인하세요.\n",
        )
    print(
        "일회 승인 파일을 저장했습니다. 본인 비밀번호 확인 후 15분 안에 인증 앱을 다시 등록하세요."
    )


if __name__ == "__main__":
    main()
