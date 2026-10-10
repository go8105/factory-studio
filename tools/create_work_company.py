"""hugh-D Company 관리자1/직원1 생성. 비밀번호를 파일·로그·인자로 받지 않는다.
uv run --project backend --env-file .env python tools/create_work_company.py
동일 아이디가 있으면 기존 계정/회사/비밀번호를 덮어쓰지 않고 중단한다.
"""

import argparse
import getpass

from fs.common.db import get_engine
from fs.hr.work_setup import (
    activate_example_company,
    create_example_company,
    prepare_example_company,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--prepare-only",
        action="store_true",
        help="로그인 불가 상태의 예제 계정/회사만 준비",
    )
    group.add_argument(
        "--activate", action="store_true", help="준비한 계정의 최초 비밀번호 설정"
    )
    args = parser.parse_args()
    if args.prepare_only:
        with get_engine().begin() as c:
            result = prepare_example_company(c)
        print(
            f"회사 준비 완료: {result['company']} / hugh-admin, hugh-staff (최초 비밀번호 설정 전 로그인 불가)"
        )
        return
    values = []
    for label in ("hugh-admin 관리자", "hugh-staff 직원"):
        password = getpass.getpass(label + " 비밀번호(10자 이상): ")
        if len(password) < 10 or password != getpass.getpass("확인: "):
            raise SystemExit("10자 이상이고 두 입력이 일치해야 합니다.")
        values.append(password)
    with get_engine().begin() as c:
        result = (
            activate_example_company(c, *values)
            if args.activate
            else create_example_company(c, *values)
        )
    print(
        f"생성 완료: {result['company']} (회사 {result['companyId']}) / hugh-admin, hugh-staff"
    )


if __name__ == "__main__":
    try:
        main()
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
