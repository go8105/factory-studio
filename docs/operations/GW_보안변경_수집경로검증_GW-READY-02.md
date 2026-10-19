# 보안 변경 수집 경로 검증 · GW-READY-02

2026-10-19 17차 기준. 전체 수집 완전성이나 운영 전환 완료 선언이 아니다. [변경 기록 운영](GW_직원연결_역할변경기록_GW-READY-02.md), [격리 복원](GW_암호화백업_격리복원_GW-READY-02.md)을 함께 따른다.

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

- common/auth의 세션 유휴 만료 연장, throttle의 새 시간 창 생성/최종 갱신 시각 등 모든 보안 쓰기의 의미와 수집 필요성을 별도로 판정해야 한다.
- core.service.create_member_account 운영 도구, HR 초기 예제 계정 설정/전환 도구와 seed/운영 스크립트는 평상시 회사 사용자 관리와 구분해 감사해야 한다. 현재 전체 자동 기록을 주장하지 않는다.
- 복원 도구의 계정/세션 제한 재적용은 원본 변경 수집과 구분한다. 복원 대상에 기록을 재생하는 행위를 원본 변경 기록으로 다시 수집하지 않는다.
- 직접 SQL/DB 소유자 작업, 배포/계정 초기 설정, 향후 SSO 변경은 별도 통제·인수 대상이다. 이번 파일 검색만으로 모든 쓰기 경로를 발견했다고 인정하지 않는다.
- 파일 삭제/변조·독립 최신성·거래 취소·외부 사본·격리 복원 검사는 각각의 기존 검증 범위를 따른다. 초기 설정이 없던 과거 변경을 소급 수집하지 않는다.

## 전체 회수 인수의 남은 기준

경로 목록의 책임자 검토, 누락 없는 실행 근거, 변경 이후 현재 원본과 checkpoint의 연결, 격리 복원 후 세션/미완료 인증 회수·회수 계정 거부, 관리자/직원 대표 업무를 함께 검증해야 한다. 이번 변경은 로그인 요청·거부 경로의 실제 누락을 보완한 단계다. completenessConfirmed/전체 revocationsReapplied/ready를 true로 바꾸지 않는다.
