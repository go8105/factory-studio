# GW 운영 증거 등록 · GW-READY-02

개발 브랜치의 기록 저장·조회 계약이다. 실제 백업/복원 실행기와 실회사 인수는 미완료이며 ready=false를 유지한다. 서명은 실행 주체와 변조 여부를 확인하며 실행 내용의 진실성이나 키 침해를 해결하지 않는다. 이번 Chrome 검사는 별도 합성 실행자가 만든 FAIL 파일이며 실제 백업 성공 증거가 아니다.

## 서버 설정과 역할

- `FS_GW_EVIDENCE_PUBLIC_KEYS`: `{ "키식별자": "Ed25519 공개키 원시32바이트의 base64" }` JSON, 최대20개. 비밀 서명 키는 앱 환경에 넣지 않고 실행자 측에서 별도 보관한다.
- `FS_CODE_REVISION`: 현재 배포 제품의 Git revision(7~64자리 소문자16진). 앱은 DB의 alembic_version도 직접 읽어 대조한다. 운영 반영 시 실제 배포 버전으로 설정한다.
- 설정 미비 시503, 키를 화면에서 등록하거나 검증을 해제하는 API는 없다. COMPANY의 기존 HTTPS/쿠키/키 조건도 그대로 적용한다.
- 현재 GW 보안 관리자+최근 MFA5분만 등록, 감사 역할은 조회만 한다. 회사 소유자/총 관리자 이름으로 우회하지 않는다. 원문·계정 이름·DB URL·인증 비밀을 evidence에 넣지 않는다.

## API

`POST /api/v1/gw/operating-evidence?companyId=...`에 `{envelope, signature}`를 CSRF/Origin/멱등키와 함께 보낸다. envelope는 승인된 EvidenceEnvelope 계약이며 canonical JSON 전체에 Ed25519 서명을 적용한다. 종류별 PASS 필수 실측값, 회사/세대, 현재 정책 digest, 현재 코드/DB revision, 미래30초 허용/종료30일 이내를 검사한다. 임의 ACCEPTANCE/INCIDENT PASS 계약은 아직 허용하지 않는다. BACKUP PASS도 아직 실제 실행 도구가 발행하지 않는다.

같은 범위 runId는 한 번만 등록한다. 현재 권한·최근 인증 검사 후 멱등 응답을 조회하며, 위조·정책 변경·다른 범위의 신규 등록은 거부한다. 실패와 일부 결과도 삭제하지 않고 불변 이력에 저장한다. 보관·삭제 API를 추가하지 않는다.

`GET /api/v1/gw/operating-evidence?companyId=...&offset=0&limit=20`는 권한이 있는 회사 범위의 총건수와 최근 등록 순 최소 정보만 반환한다. limit1~100, offset0~100000. metrics/서명 원문을 목록에 재노출하지 않는다. 현재 정책과 다른 기록은 currentPolicy=false다. 목록 등록만으로 준비 상태를 통과시키지 않는다.

## 확인과 남은 구현

관련 API/서명/정책19통과, 프런트5통과. Chrome 합성 증거 FAIL 파일 선택→등록→실패 기록 표시, 긴급 문서 다운로드→실제 CLI 승인→파일 선택→제한 재등록,390px 넘침0/pageerror0. 초기 API 테스트가 개인 공간 세대를 잘못 서명해 회사 범위 검증으로 거부된 것을 확인, 회사 정책의 실제 세대로 검사 데이터를 수정한 뒤 통과했다. 실제 계정/공유DB를 수정하지 않았다.

다음은 보관 검토/보존 중지·원문 ACL, 실제 암호화 백업/폐쇄 복원/회수 재적용, 선택 SSO, 전체 회귀/10인·실환경 인수다. [사용자 도움말](../../content/help/gw/operations.md), [전체 구현 기록](../agent/GW_실사용구현_GW-READY-02.md).
