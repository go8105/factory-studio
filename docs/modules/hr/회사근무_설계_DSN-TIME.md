# 회사 공동 근무 HR-TIME-01

사용자 2026-10-10 전체설계·예제hugh-D Company 관리자1/직원1 승인. HR 업무 소유, core 회사/소속만 소유. 계정 연결은 서비스 멤버십 조회로 검증하며 업무→인증 FK 금지 유지.

| 테이블 | 내용 |
|---|---|
| `core.company` | 회사 |
| `core.company_member` | 회사 구성원 |
| `hr.work_account` | 근무 계정 연결 |
| `hr.work_policy` | 회사 근무 기준 |
| `hr.clock_session` | 실제 출퇴근 원장 |
| `hr.work_request` | 휴가 시간차 출장 신청 |
| `hr.work_event` | 근무 변경 이력 |
| `hr.work_close` | 회사 근태 월 마감 |

상세: [승인설계](../../plan/회사공동_출퇴근_PWA_HR-TIME-01.md). 예제근무표09~18/휴게12~13/연차15일. 회사용원장은 기존체험AUTO근태와 분리. 시간차 정수분60배수, 직원본인/관리자승인·정정·월마감. 실제회사공간의 초기화/시드복사 금지. 계정비밀번호는 운영자가 터미널getpass로 설정한다.
