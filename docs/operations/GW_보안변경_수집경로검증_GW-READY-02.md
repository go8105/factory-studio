# 보안 변경 수집 경로 검증 · GW-READY-02

2026-10-19 19차 기준. 전체 수집 완전성이나 운영 전환 완료 선언이 아니다. [변경 기록 운영](GW_직원연결_역할변경기록_GW-READY-02.md), [격리 복원](GW_암호화백업_격리복원_GW-READY-02.md)을 함께 따른다.

## 이번에 확인·보완한 경로

| 경로 | 변경 직후 기록 | 검증 근거 |
|---|---|---|
| core.service.login_member | security.password_session.issued | 세션 발급 기록/비밀 미포함·저장 실패 시 발급 취소 |
| security.service.login_gate | security.login_challenge.issued | MFA 요청 생성 뒤 계정 기록 |
| security.service.verify_login 실패 | security.login_challenge.denied | 실패1~5회·LOCKED 상태와 시도 횟수 기록 |
| 같은 함수의 만료 | security.login_challenge.expired | 요청 EXPIRED 이후 기록·저장 실패 시 변경 취소 |
| security.emergency.fail_login | security.emergency_login.denied | 실제 갱신한 요청의 사용자만 기록·저장 실패 시 시도 횟수 취소 |
| security.emergency.approve의 문서 만료 | security.emergency_kit.expired | 만료 후 시스템 감사/암호화 기록과 DB 지문 확인 |

실제 PostgreSQL 합성 검사는 backend/tests/test_challenge_security_journal.py, 기존 회귀는 test_account_security_journal.py와 test_gw_security_transactions.py다. 요청 스냅샷에 attempt_count와 expires 시각만 추가했다. 코드/토큰/해시/비밀번호/IP를 추가하지 않았다. 같은 트랜잭션의 감사 표식과 암호화 지문을 대조하며, 기록 실패는 해당 DB 변경을 취소한다. 이미 LOCKED이거나 존재하지 않아 아무 변경도 하지 않은 요청에 허위 변경 기록을 만들지 않는다.

## 기존 수집과 검증 구분

MFA 등록/로그인·복구·코드 재발급·다른 세션 회수·로그아웃·HR 회사/직원 생성·역할/중지 변경은 기존 수집 경로이며 이번 관련 회귀에서도 확인한다. GW 직원 연결·역할/문서 ACL 변경은 앞선 회사 경로 검증 이력이 있고 이번에 해당 전체 테스트를 새로 실행한 것으로 표시하지 않는다. 기록을 파일에 남긴 것, DB에 반영된 것, 모든 경로의 누락이 없다는 것은 서로 다른 조건이다.

## 아직 전체 인수로 인정하지 않는 경로

- common/auth의 세션 유휴 만료 연장은 아래18차의 명시적 재생 제외 대상으로 판정했다. throttle의 초기0 새 창/최종 갱신 시각은 거부 횟수 증가와 구분한다. 모든 카운터 의미·부하·복구 인수는 별도다.
- core.service.create_member_account 및 HR 초기 회사/예제 계정 생성·중지·활성화는18차에서 계정 상태 수집을 연결했다. seed/나머지 운영 스크립트·실서버 도구 실행 인수는 별도이며 전체 자동 기록을 주장하지 않는다.
- 복원 도구의 계정/세션 제한 재적용은 원본 변경 수집과 구분한다. 복원 대상에 기록을 재생하는 행위를 원본 변경 기록으로 다시 수집하지 않는다.
- 직접 SQL/DB 소유자 작업, 배포/계정 초기 설정, 향후 SSO 변경은 별도 통제·인수 대상이다. 이번 파일 검색만으로 모든 쓰기 경로를 발견했다고 인정하지 않는다.
- 파일 삭제/변조·독립 최신성·거래 취소·외부 사본·격리 복원 검사는 각각의 기존 검증 범위를 따른다. 초기 설정이 없던 과거 변경을 소급 수집하지 않는다.

## 전체 회수 인수의 남은 기준

경로 목록의 책임자 검토, 누락 없는 실행 근거, 변경 이후 현재 원본과 checkpoint의 연결, 격리 복원 후 세션/미완료 인증 회수·회수 계정 거부, 관리자/직원 대표 업무를 함께 검증해야 한다. 이번 변경은 로그인 요청·거부 경로의 실제 누락을 보완한 단계다. completenessConfirmed/전체 revocationsReapplied/ready를 true로 바꾸지 않는다.

## 18차 초기 설정 도구·재생 제외 기준

| 경로 | 기록/처리 | 검증 범위 |
|---|---|---|
| 운영자 회원 생성(create_member_account) | security.member_account.created, 시스템 행위자로 역할/활성 상태 기록 | 계정/역할 생성·비밀 미포함·저장 실패 시 계정/공간 생성 취소 |
| HR 초기 회사 생성 | hr.setup.company.created, 최종 회사 멤버십까지 계정 상태 기록 | 기존 HR 생성·권한 회귀에서 DB 반영 대조 |
| 예제 회사 생성 | hr.setup.example.created, 두 계정 회사 연결 뒤 기록 | 최종 멤버십/계정 상태 수집 |
| 예제 초기 비활성 준비 | hr.setup.example.disabled | 두 계정 중지 기록·저장 실패 시 전체 생성 취소 |
| 초기 비밀번호 설정 활성화 | hr.setup.example.activated | 두 계정 활성 상태·저장 실패 시 기존 중지 상태 유지 |
| 세션 유휴 만료 연장 | 매 요청별 별도 암호화 의도는 남기지 않음 | 절대 만료 상한·제한 재적용 뒤 이전 토큰 거부 |

추가 초기 설정 기록은 core 소유 계정/역할/회사 멤버십 상태다. HR 업무 원문이나 비밀번호를 복사하지 않는다. 평상시 HR 사용자 관리의 기존 HR 소유 스냅샷 수집을 대체하지 않는다. 원본/계정 상태 수집에 실패하면 같은 트랜잭션을 취소한다. 실제 계정 생성·비밀번호 설정·운영 도구 실행은 이번 개발에서 수행하지 않았고 소유 합성DB의 진입 함수만 검사했다.

세션 연장은 기존 미회수 세션의 유휴 만료를 절대 만료 안에서 조정한다. 복원은 모든 기존 세션을 회수하므로 이 연장을 원본 허용 상태로 재생하지 않는다. 매 HTTP 요청마다 계정 전체를 암호화해 기록하면 잠금/보관 부하가 크게 늘기 때문에 권한·발급/회수 변경과 구분한다. 이 제외가 모든 세션 경로 검증 완료나 전체 수집 완전성을 뜻하지는 않는다. 향후 세션 재사용/복원 정책을 바꾸면 이 판단도 다시 검증해야 한다.

throttle의 새 창 초기0과 updated_at 갱신은 실패/발급 횟수 증가와 구분한다. 현재 횟수 증가는 기존 기록·checkpoint 최댓값 재적용으로 다루며, 운영 환경의 모든 제한 창 의미/부하 검증은 남아 있다. 직접SQL·기타seed/관리도구·향후SSO·실환경 장애와 전체 권한 회수 인수까지 마치기 전에는 completeness/ready를 올리지 않는다.

## 19차 검증 대상 운영 경로 v1

이 목록은 이번 코드 버전에서 검증 대상으로 고정한 범위다. 운영 준비 전체의 통과 선언이나 직접 SQL 허용 목록이 아니다. 새 경로나 권한 부여 기능을 추가하면 이 목록·수집 경로·회수 검사를 함께 검토해야 한다.

| 범위 | 제품/운영 진입점 | 수집·회수 검증 |
|---|---|---|
| 비밀번호 세션/로그아웃 | core.service.login_member/logout | 발급·회수 기록, 복원 후 옛 토큰 거부 |
| MFA·복구·추가 인증·다른 세션 회수 | core.security.service 및 router | 허용된 상태 메타데이터 수집, OTP/복구코드 소비·세션 회수 검사 |
| 긴급 문서/운영자 승인/제한 복구 | core.security.emergency/GW emergency | 문서 교체·거부/만료·로그인 제한과 시스템 기록 |
| 평상시 회사 직원·계정 변경 | hr.users 및 GW identity/company action | HR 역할·계정 상태, GW 연결/권한/회사 범위 기록·제한 재적용 |
| 운영자/초기 설정 | create_member_account 및 HR work_setup의 회사/예제 설정 | 시스템 계정 상태 기록·실패 시 취소 |
| 암호화 백업·checkpoint·격리 restore | gw_backup.py, journal bundle/delivery 도구 | 기준 지문 연결·이후 의도/미확인 제한·새 격리 DB·외부 현재성 구분 |

명시적 제외/별도 인수: 매 요청의 유휴 만료 연장은 허용 재생 제외, 카운터 초기0/updated_at는 실패 횟수와 구분한다. 직접SQL·임의 운영 스크립트·DB 소유자 변경·신뢰 실행기 자체의 위조·외부 저장소 장애·향후 SSO는 이 목록만으로 인수하지 않는다. 다른 솔루션의 업무 권한은 각 솔루션 소유다. 사용하지 않는 경로도 자동 통과로 바꾸지 않는다.

## 19차 격리 복원 접근 거부 시나리오

기존 test_backup_journal_restore.py의 실제 PostgreSQL dump/restore 두 경로(수동 지문, 폴더 교체+전달 확인 자동 지문)를 보강했다. 원본은 합성 관리자/직원 회사이며 실제 10인 회사 인수와 구분한다.

1. 백업 전 관리자/직원 세션과 합성 미완료 로그인 요청을 준비한다.
2. 백업 뒤 직원 연결 회수·재개, HR 역할 변경을 수행한다. 원본 직원의 기존 세션은 HR 역할 변경으로 이미 회수되는 것이 정상이다.
3. 최신 checkpoint와 독립 지문으로 새 접속 제한 DB를 복원한다.
4. 직원 계정/HR 계정 제한, GW 연결 정지·회사 보존 중지, 모든 기존 세션 회수, 미완료 요청 EXPIRED를 대조한다.
5. 제품의 실제 인증 판별 함수로 복원본의 옛 관리자/직원 토큰이 모두401 거부되는지 확인한다. 미완료 요청의 인증 확인도401이며 새 세션이 생기지 않아야 한다.
6. 검사 후에도 복원DB datconnlimit=0을 유지한다. 테스트 소유 superuser로 내부 검증할 뿐 직원 연결을 열지 않는다.
7. 원본의 관리자 토큰/운영 준비 HTTP 조회는 계속 사용 가능하고, 역할 변경으로 회수된 직원 토큰은 거부되며 계정 자체는 활성/직원 역할을 유지하는지 확인한다. 원본 미완료 요청도 임의로 만료시키지 않는다.

기존 checkpoint 검사는 OTP/복구코드 소비, 암호 변경, HR 역할 하향, 불확실 ACL/보존 중지를 각각 다룬다. 두 경로를 조합했더라도 모든 운영 쓰기의 무누락·실회사 장애/부하·운영 개방 승인을 의미하지 않는다. 서명 증거의 전체 revocationsReapplied/checkpointCompletenessConfirmed와 ready는 계속 false다.


## 29차 관측 기록계열 진단 · 개별 경로 완전성과 구분

기존 `tools/gw_identity_journal.py --expected-head <별도확인한지문> --classify-transactions --review-report <0700폴더의새파일>`은 검증한 기록/DB 감사/거래판정을 `recordingFamilies`로도 집계한다. 인증(core.security.intent.v1)·HR(hr.users.intent.v1)·GW(gw.company.intent.v2) 각각 MISSING(기록없음)/SETTLED(관측거래정리)/UNSETTLED(미확인포함)와6종 거래상태 건수를 제공한다. 계정·본문·operation원문은 출력하지 않는다.

하나라도 기록없음/미확인 또는 과거v1·미지원계열이 있으면 계열결과 BLOCKED다. 모두정리돼도 PARTIAL이며 모든 개별경로 실행·기록저장실패시롤백·최신지문/전체회수/원본유지·직접SQL/운영자경계는 별도 검증한다. 같은계열의 다른operation 기록을 특정경로의 실행근거로 인정하지 않는다. 없는계열을 과거형식으로 채우지 않는다.

기존CLI 종료코드는 거래상태 기준이다. 따라서 취소가확인된 인증기록1건만 있으면 exit0이어도 HR/GW는 MISSING·계열결과BLOCKED일수있다. exit0을 수집완전성이나 운영승인으로 사용하지 않는다. completenessConfirmed/revocationsReapplied/releaseAuthorized=false 유지. unsigned검토보고서는 제품 ACCEPTANCE 등록이나 checkpoint입력으로 쓰지 않는다.
