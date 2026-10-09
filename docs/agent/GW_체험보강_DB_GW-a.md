# GW-a 체험 그룹웨어 DB 보강 결과

2026-10-09 · 브랜치 `codex/gw-dsn31` · 시작 `af10726` · DB 단계 완료, 새 기능/API/화면은 미구현.

## 범위 판단

사용자 “최종 판단하고 진행” 및 AGENTS D83을 기준으로 DSN-31 체험 보강을 착수했다. 첨부 P0/A는 실제 회사 도입 설계이며 이번 체험 기능의 구현 승인이 아니다. 저장소 현황에는 전체 DSN 설계 승인(2026-10-05)이 기록되어 있다.

Claude 인계의 “16테이블 생성”은 “실제 도입 A 개발 제외”와 충돌한다. DSN-31 §4-1의 체험·조직 11표만 제품 DB로 이관하고, §4-2의 A 전용 5표는 목표 DB에 남겼다. CORE TEAM·ERP 통제도 제외한다. GW 목표 24표는 두 트랙의 합계이고 이번 제품은 19표다.

## 변경

- 신규 11표: 전결·위임·조직, 댓글/수정이력, 일정/참석자, 알림, 대화방/참여자/메시지.
- 기존 6표 15칼럼: person 2, route_step 1, approval_document 5, approval_step 3, approval_event 2, board_post 2. 기존 행 추가값은 NULL 허용 또는 기본값 사용. 결재 정책 기본값 1, 참여 구분 APPROVER, 인증 방식 SIMULATION, 게시 범위 WORKSPACE로 기존 기능 유지.
- `tools/apply_gw_a.py`는 목표 설계에서 복사한다. 멱등이며 GW 외 업무 메타데이터는 그대로다. 새 GW 상태 목록도 함께 가져온다.
- 제거되는 단계 순번 UK 2개는 배열 슬롯을 SERVICE/DB_POLICY로 보존하고 DB에서는 제거한다. source_status CHECK는 목표의 서비스 정책으로 제자리 교체, 나머지 변경 제약도 제자리 교체한다. 이후 제약·FK는 끝에 추가한다.
- 기존 migration은 수정하지 않았다. 새 revision `gw_a_dsn31`, 부모 `w2a1_mes`, 생성 SQL 131문. 공통 생성기 downgrade는 새 FK/제약→칼럼→표→기존 제약 복원 순서로 수정했다. 기존 표에서 새 표를 참조하는 FK와 self-FK 때문에 필요한 변경이다.
- 검사기는 GW 단계도 점진적 제품 DB로 판단하고, TEAM·ERP 전체 요구는 목표 또는 해당 트랙 도입 시 검사한다. 목표에서 요구를 누락시키면 실패하는 회귀 검사를 추가했다.
- schema 0.21.0: 전체 173표·1,916칼럼·412FK, GW 19표. schema.json/제품 Excel 47시트/GW·전체 ERD/오프라인 탐색기 재생성. 목표의 base_task만 GW-a로 갱신했다.

## 검증

- 제품/목표 메타데이터 오류 0. 업무 간 FK 위반 0, GW 외 tables/constraints/relations/states/code_lists 변경 없음.
- `factory_studio_gw_a_test`는 CI DB에서 복제한 독립 로컬 테스트 DB. 공유 개발 DB·기존 CI DB·운영 DB에 이번 migration을 적용하지 않았다.
- 실제 DDL 대조: 173표·1,916칼럼·412FK, 오류 0. [대조 기록](assets/gw-a/ddl-comparison.json).
- 기존 API로 합성 결재 승인 문서를 만든 뒤 Alembic downgrade→이전 명세 대조→upgrade→새 명세 대조. 기존 8표의 모든 기존 칼럼 값 보존, 양쪽 대조 오류 0. 신규 기본값 policy_version=1 유지. [왕복 기록](assets/gw-a/migration-roundtrip.json).
- 실제 DB 신규 3개: 병렬 단계 허용/동일 담당자 중복 거부, 다른 공간 참조 거부/알림 재전송 중복 거부, 데이터가 있는 조직 self-FK·담당자 소속 복사 및 게스트 정리. 도구 단위 검사 4개 통과(범위·멱등·안전한 칼럼·rollback 순서·목표 게이트).
- 전체 backend perf 제외: **900개 통과·1개 건너뜀**, 330.21초. 신규 DB 검사 3개 포함. 기존 의존성/SQLAlchemy 경고 25건, 실패 0건.
- 기존 GW frontend 5개 통과, 전체 tsc/eslint 통과. 프런트 제품 변경 없음; 프런트 전체 테스트/build는 미실행.
- backend 전체 ruff check/format 통과. 새 도구 check 통과. `git diff --check` 통과.
- 실제 Chrome: 로컬 5273/8073, 독립 DB의 게스트 생성→GW 현황→G-07 담당자 등록→목록 반영 확인. [화면](assets/gw-a/people-registration.png). 새 기능 UI·모바일·실제 회사 권한 검증은 이번 DB 단계 대상이 아니다.

## 다음 단계와 제한

GW-a DB 단계만 완료. 사용자 결과 확인 후 GW-b 결재 정책 v2·전결·위임 API/화면을 진행한다. 기존 v1은 계속 순차 결재다. 체험 11표를 만들었다는 사실이 병렬결재·위임·채팅 업무 구현 완료를 뜻하지 않는다. 실제 도입 A·실제 인증·외부 전송·ERP 통제·운영 배포·원격 push는 미실행.

GW-b에서 ERP 발주/지출결의 및 PLM ECO 제공 인터페이스 구현 시점을 확인해야 한다. 미구현 제공자의 결과를 정상 빈 데이터로 처리하면 안 된다. 조직 self-FK 자체는 정리/복사 실DB 검사를 통과했고, nullable 고리를 새로 만드는 경우 별도 검사한다.

재현: Node24 PATH 적용 후 `python3 tools/test_gw_a.py`, `npm run db:validate`, `python3 tools/validate_db_design.py --schema docs/db/schema-metadata/schema-target.json --report docs/db/validation-report-target.json`, `npm run db:build`, `python3 tools/build_erd.py`. 별도 PG18 테스트 DB에 `alembic -c backend/alembic.ini upgrade head` 후 `DATABASE_URL=... python tools/verify_ddl_matches_schema.py`; backend에서 `TEST_DATABASE_URL=... PYTHONPATH=src:. python -m pytest tests/ -q -m "not perf" -n 4`. 새 DB는 반드시 `_test` 접미사 사용. DB 연결값은 환경에서 제공하고 로그·Git에 넣지 않는다.
