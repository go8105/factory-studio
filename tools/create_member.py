"""운영자 회원 계정 만들기. 제품에는 회원가입이 없어 서버에서 이 도구로 만든다.

서버(저장소 루트)에서:
  sudo -u factory -H /usr/local/bin/uv run --frozen --project backend --env-file .env \
    python tools/create_member.py <아이디> --name "관리자" --admin

비밀번호는 화면에 보이지 않게 두 번 입력받는다(10자 이상). 해시만 저장하고 출력하지 않는다.
계정·회원 공간·템플릿 데이터 복사가 한 트랜잭션이라 중간에 실패하면 아무것도 남지 않는다.
"""

from __future__ import annotations

import argparse
import getpass
import sys

from fs.common.clock import business_today
from fs.common.db import get_engine
from fs.core.service import create_member_account


def main() -> None:
    parser = argparse.ArgumentParser(description="운영자 회원 계정 만들기")
    parser.add_argument("login_id")
    parser.add_argument("--name", default="관리자", help="화면에 보일 이름")
    parser.add_argument(
        "--admin", action="store_true", help="관리자 권한(운영 기록 조회)"
    )
    args = parser.parse_args()
    password = getpass.getpass("비밀번호(10자 이상): ")
    if password != getpass.getpass("비밀번호 확인: "):
        sys.exit("비밀번호가 서로 다릅니다.")
    try:
        with get_engine().begin() as connection:
            result = create_member_account(
                connection,
                args.login_id,
                args.name,
                password,
                business_today(),
                args.admin,
            )
    except ValueError as error:
        sys.exit(str(error))
    print(
        f"생성 완료: 아이디={result['loginId']} 관리자={result['admin']} "
        f"공간={result['workspaceId']} 복사 행={result['copiedRows']}"
    )


if __name__ == "__main__":
    main()
