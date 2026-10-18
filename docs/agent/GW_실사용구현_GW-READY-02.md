# GW 실사용 보안·운영 구현 · GW-READY-02

2026-10-18 사용자 전체 설계 승인. **한 구현 ID의 A~E 진행 중이며 완료 보고가 아니다.** 내부 묶음마다 재승인하지 않는다. 로컬 main만 반영하는 기존 범위를 유지하며 원격/운영 배포는 하지 않는다.

## 현재 구현과 검증

- A: 암호화 TOTP·중간 challenge·DB 실패 횟수·동일 번호 재사용 차단·키 문맥/교체·security_version·8시간 절대 만료. 앱 등록/확인·실제 로그인202→번호확인201·추가 본인 확인·복구 코드 재발급·다른 세션 종료 API/화면을 구현했다. 비밀번호 변경은 세션 버전도 올린다. COMPANY의 키/HTTPS origin/Secure 쿠키 누락은 거부하며 회사 업무는 MFA 세션을 요구한다.
- B 일부: 비밀번호+일회용 복구 코드→기존 앱/세션/코드 회수→업무 차단된 제한 세션→새 앱·코드→재로그인. 모든 수단을 잃은 유일 관리자 긴급 복구와 OIDC 선택 연결은 남아 있다.
- C 일부: 운영 정책 입력 계약·서명된 증거 검증 커널·회사 정책 새 버전/CAS/역할/최근 인증 API·운영 준비/기준 화면. 증거 등록/실제 검사 연결·보관 검토·보존 중지·운영 전환은 남아 있다. 현재 ready=false이며 백업/복원·실환경 미완료를 표시한다.
- D: 암호화 백업 실행/스케줄·폐쇄 복원·독립 회수 기록 재적용 미구현. 증거 검증 커널만으로 실제 백업 기능을 완료 처리하지 않는다.
- E 진행: 상단 내 계정 보안, 로그인 본인 확인/복구, 회사 운영 안내→운영 준비와 정적 도움말을 연결했다. 전체 통합/10인 인수·최종 main 반영은 남아 있다.

격리 PostgreSQL18.6 신규 migration 적용·219표2409컬럼543FK 카탈로그 대조 오류0. 현재/목표 metadata·Excel2종·ERD를 갱신했다. 업무 데이터/인증 상태를 migration으로 임의 변경하지 않았다. 이력이 있으면 downgrade를 거부한다.

초기 보안/트랜잭션/HTTP/정책·서명 커널29건 통과. 동일 OTP/복구 코드 경합·실패 commit·제한 세션 업무 거부·만료/보안버전·재발급/다른 세션 회수 포함. 최신 관련 회귀 결과는 계속 기록한다. 첫 넓은 회귀에서 새 정책 부모에 created_at이 없는데 합성 시드 생성기가 그 열을 가정한 문제를 발견, 기존 시드 검사기처럼 부모 열이 있을 때만 시각 보정하도록 수정 후 재검사 중이다.

Chrome 실제 제품에서 합성 계정의 등록→앱 로그인→코드 복구→재등록→도움말, 390px 가로 넘침0·페이지오류0 확인. 실제 휴대폰/IdP/실회사 검증이 아니다. 코드 재발급/운영 화면은 추가 변경 후 브라우저 재검사 대상이다. 프런트 전체610통과/기존Flow7실패(617), 새 보안/로그인11통과·타입/린트/빌드 통과(기존chunk 경고). 후속 변경 후 필요한 집중 검사를 반복한다. 전체CI성공이 아니다.

## 도움말

- [내 계정 보안·인증/분실 복구](../../content/help/portal/account-security.md)
- [회사 운영 준비·기준](../../content/help/gw/operations.md)
- [회사 시작·직원 권한](../../content/help/gw/company.md)

구현하지 않은 기능은 도움말에서 후속으로 명시한다. 코드·비밀번호·실제 개인정보·암호화 키를 도움말/Git에 넣지 않는다. 보안 키는 환경 비밀, 제품은 업무 본문/인증 비밀을 브라우저 영구 저장소에 저장하지 않는다.

## 다음과 환경

branch codex/gw-company-01 / 기준main2be292e. 실제 계정·공유DB·다른checkout·브라우저확장 변경 없음. 소유 격리PG 컨테이너 fs-gw-ready02-test, loopback55438; 정리 시 work/gw-readiness-02/container-id와 label factory-studio.owner=gw-ready-02 대조 후 이 컨테이너/익명볼륨만 삭제한다. 검토API8362/웹5362는 종료했다. 환경 비밀은 work만 사용하며 Git 제외. 최종 결과 전 실제 COMPANY 준비 완료/main 반영을 선언하지 않는다.

재현: Python3.14/uv, Node24. 새 *_test PostgreSQL18 DB에 alembic upgrade head 후 TEST_DATABASE_URL 설정. `uv run --project backend pytest backend/tests/test_gw_security_crypto.py backend/tests/test_gw_security_transactions.py backend/tests/test_gw_security_http.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_operations.py -q`. 브라우저 재현은 frontend/e2e/gw-security-browser.mjs(합성 계정 JSON 경로·로컬 origin을 환경으로 제공; 비밀을 문서에 쓰지 않음). DB 정적검사/Excel/ERD는 저장소 표준 도구를 사용한다.
