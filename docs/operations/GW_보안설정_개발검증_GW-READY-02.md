# GW 보안 설정·개발 검증 · GW-READY-02

전체 구현 진행 중이다. 이 문서는 운영 담당자용이며 직원 안내는 [계정 보안 도움말](../../content/help/portal/account-security.md)을 따른다. 실제 회사 도입·운영 인수가 끝난 상태가 아니다.

## 환경 경계

- FS_SECURITY_MODE: PUBLIC_DEMO 기본, TEAM_TEST 합성 검증, COMPANY 운영 보안 강제. 브라우저가 모드를 변경하지 못한다.
- FS_SECURITY_KEYS: `{키식별자: Fernet키}` JSON 환경 비밀. FS_SECURITY_KEY_ID는 현재 암호화 키 식별자. SESSION_SECRET·DB 비밀번호와 다른 키를 쓴다. 값은 코드/로그/Git/도움말에 남기지 않는다. 이전 데이터 해독에 필요한 옛 키는 교체 기간 동안 별도 비밀 저장소에서 유지한다.
- FS_PUBLIC_ORIGIN: 브라우저 Origin과 같은 주소. COMPANY는 https origin, Secure 쿠키, 유효한 암호화 키가 없으면 거부한다. 비밀이 담긴 POST는 같은 Origin을 요구한다. COMPANY 인증 요청의 scheme도 https여야 한다. TLS 종료 proxy는 신뢰할 주소만 허용하고 임의 Forwarded 헤더를 신뢰하지 않는다.
- COOKIE_SECURE=false는 TEAM_TEST의 loopback HTTP 합성 검증에만 쓴다. COMPANY에서는 거부한다. 실제 도메인/TLS·시간 동기·키 보관·복구 담당 인수는 별도 검증이다.
- DB는 PostgreSQL18, Python3.14, 프런트 Node24. 이미 적용된 옛 migration을 수정하지 않고 `gw_readiness`를 추가한다. 보안/운영 표에 이력이 있으면 downgrade를 거부하므로 forward fix나 폐쇄 복원을 사용한다.

키를 새로 만들 때는 `cryptography.fernet.Fernet.generate_key()`를 사용해 별도 비밀 저장소에 보관한다. 운영 키를 테스트/회사 사이에 공유하지 않는다. 실회사 설정을 이번 개발에서 자동으로 생성·교체·배포하지 않았다.

## 재현과 실제 경계

비어 있는 전용 *_test DB에 `uv run --project backend alembic -c backend/alembic.ini upgrade head` 후 DATABASE_URL/TEST_DATABASE_URL·SESSION_SECRET·TEAM_TEST용 키/Origin을 테스트 프로세스 환경으로 전달한다. 공유 DB나 실제 계정으로 실행하지 않는다. pytest의 clean_database fixture는 대상 테스트 DB를 비운다.

- 보안: test_gw_security_crypto.py / test_gw_security_transactions.py / test_gw_security_http.py
- 운영 계약/정책: test_gw_operating_contract.py / test_gw_operations.py
- 현재 DB 대조: `uv run --project backend python tools/verify_ddl_matches_schema.py`
- 메타데이터/Excel/ERD: 저장소 표준 db:validate/db:build/build_erd 도구. 목표 파일은 --target, 실제 DB 명세와 구분한다.
- 제품 브라우저: frontend/e2e/gw-security-browser.mjs. GW_SECURITY_BROWSER_CREDENTIALS는 합성 login/password JSON의 비공개 경로, GW_SECURITY_BROWSER_ORIGIN은 loopback 주소, GW_SECURITY_BROWSER_OUTPUT은 캡처 경로다. company 숫자를 넣으면 실제 회사 정책 새 버전과 계속 편집 포커스도 검사한다. 비밀번호/설정 키/코드를 캡처나 결과에 출력하지 않는다. 합성 계정을 별도로 준비하며 완료 후 DB와 비공개 파일을 정리한다.

기존 회귀와 신규 경합/실패 검증을 구분한다. 모의 시간·DB에서 last_used_step을 조정하는 단위 검사는 실제 인증 앱 검증이 아니다. Chrome 제품 검사는 실제 다음 번호가 바뀌는 것을 기다리며, 실휴대폰을 대신하지 않는다.

긴급 복구·보관 검토·증거 등록과 서버용 암호화 백업/격리 복원·확인된 회수 제한 재적용까지 구현했다. 독립 회수 기록 자동 연속성·외부 저장소·실환경 인수/운영 게이트·SSO 어댑터·전체 10인 인수는 남아 있다. [백업·격리 복원 절차](GW_암호화백업_격리복원_GW-READY-02.md)를 따른다. Authlib는 해당 어댑터 구현 때 라이선스/버전을 확정하며 현재 런타임에는 미사용 의존성을 넣지 않는다.
