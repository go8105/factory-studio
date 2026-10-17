# 회사 GW 인증 기반 · GW-COMPANY-02

2026-10-17. 사용자 GW-COMPANY-01 전체 설계 확인 및 “구현 진행해줘” 승인에 따른 첫 구현 단계. 브랜치 `codex/gw-company-01`, 기준 `06e4a70`, 로컬 main의 PWA `e02097d`/기록`0a45562` 보존. 원격 push·실서버 배포 및 실제 회사 데이터 변경은 하지 않는다.

## 구현 범위

- 신규 revision `gw_company_identity` → 기존 head `flow_board_custom` 뒤. 회사 GW 보안5표(settings/binding/role/reader/step assignment), 기존 approval_step의 문서 포함 복합UK. 사건 enum과 auth_mode는 이미 있어 중복 변경하지 않았다. 기존 테이블/제약 순번을 유지하고 추가만 한다.
- schema.json 0.26.0, **198표·2,151컬럼·488FK**. 현재/목표 Excel·GW/전체 ERD를 동시 갱신했다. Excel 목차의 고정 요약 행이 늘어난 모듈 목록을 덮던 문제도 동적 위치로 보정하고 전체 모듈이 보존되는지 재읽기로 확인했다. 목표 명세는 실제 적용 GW5표를 과거 UUID 바인딩 계획보다 우선하도록 재생성하며 다른 솔루션 목표 계약은 보존한다. 목표 DB를 제품 DB에 일괄 적용한 것이 아니다.
- core.company 읽기 계약에 계정 관리 잠금/실제 세션 재검사를 추가했다. GW 회사 TX는 회사공간16→계정관리→세션행 순서로 잠그고 READ COMMITTED에서 계정/회사/모듈/활성세대를 다시 확인한다. HR 사용자관리도 영수증 전·잠금 후 권한을 확인한다. 기존 로그아웃 UPDATE가 세션행 잠금과 직렬화된다.
- HR work_identity는 활성 계정 연결의 사원코드/이름/부서 최소값을 읽기만 한다. GW가 HR 원장을 직접 변경하거나 HR ADMIN을 GW 역할로 자동 승격하지 않는다.
- `/api/v1/gw/companies`, `/api/v1/gw/me?companyId`는 본인 회사와 본인 준비 상태만 제공한다. ACTIVE GW 바인딩/명시 역할 판정 및 객체 authorize 후에만 receipt를 반환하는 명령 기반 함수를 추가했다.
- 기존 GW **63경로**는 companyId가 있으면 현재 단계에서 409 `GW_COMPANY_NOT_READY`로 막는다. 회사 요청의 personId/actingPersonId는400. 개인/게스트의 기존 입력·시드는 유지한다. `/api/v1/gw/projects`는 Flow 호환 라우터로 별개다.
- 현재 me의 businessReady=false/capabilities=[]는 의도한 상태다. bootstrap/연결 요청·동의·권한 변경·문서/협업 ACL·회사 선택 화면은03/04 후속이며 공개 쓰기 API를 부분적으로 열지 않는다. 내부 명령 기반 함수를 업무 구현 완료로 표현하지 않는다.
- 회사의 시드 복사/세대 초기화를 거부하고 보안5표는 템플릿 복사에서 제외한다. 기존 보안 이력이 있으면 downgrade를 거부해 파괴적 롤백을 막는다.

## 검증 기록

- 실제 API 테스트는 합성 회사·계정과 **전용 PostgreSQL18 컨테이너의 factory_studio_gw_company_test**만 사용한다. 공유 개발 DB·실제 계정/비밀번호·회사 정책/운영 서버는 변경하지 않는다.
- 최초 별도 `_test` DB(공유 개발 컨테이너)에서 회귀 중 PostgreSQL `out of shared memory / max_locks_per_transaction` 발생. 공용 설정을 바꾸지 않고 해당 검사를 중단하고 전용 컨테이너로 재실행한다. 중단 결과를 통과로 계산하지 않는다.
- 처음3개 신규 테스트는 fixture SQL의 state 매개변수 varchar/text 추론 충돌로 실패해 명시 CAST로 보정했다. 도구 검사도 목표 기준/GW 부분 이관 가드가 과거19표를 가정해 실패하여 현재 승인5표와 목표 재현성을 보존하도록 갱신했다. CI dry-run의 Python/환경파일 요구는 새 작업 폴더에 합성 설정과 실행 PATH를 제공해 검사했다.
- 정적 DB 검증/스키마 격리 R1~R6 오류0, 새 격리 DB head 적용/DDL 대조 오류0. Excel artifact-tool로 생성·재읽기·신규5표 렌더 확인, 수식 오류 검색0.
- 공식 CI 방식 ruff check/format 검사 통과. 일부 선행 PWA 테스트의 import 정렬도 같은 공식 설정에 맞췄다.
- 전용 PostgreSQL18에서 **관련 API 131 passed / 기존 경고6**(6분20초). 신규 기반13개 + HR work/users·기존 GW 결재/전결·위임/조직/협업·독립 Flow/자유컬럼 회귀를 포함한다. 회사 소속·두 회사 격리·실제 게스트403, 기존63경로 차단/역할 가장400, HR관리자와 GW역할 분리, 바인딩 상태/중복·복합FK, 세션 회수와 계정 정지 경합, 영수증 재노출 차단, 복사/초기화 및 이력있는downgrade 거부를 확인했다.
- 최종 **도구 단위검사139 OK**, 공식 ruff check/format(230파일) 통과. 현재/목표 정적 명세와 R1~R6 오류0. Excel 수식 오류0, 현재12/목표20 모듈 목차 보존과 요약행 분리 확인.
- **head → flow_board_custom → head** 왕복: 이전/현재 DDL 대조 각각 오류0, **198개 테스트 원장의 행 수·내용 해시 모두 일치**. 회사 보안 이력이 있으면 되돌리기를 거부하는 별도 테스트도 통과했다. 실제 운영 DB의 복원/회수 인수로 해석하지 않는다.
- 프런트/실브라우저/실휴대폰/실운영 회사 인수는 이번 기반 단계 검사 대상이 아니다. 기존 프런트 Flow7실패는 그대로 미해결이다. 전체 제품 CI를 통과했다고 주장하지 않는다.
- 구현 및 검사 결과는 로컬 브랜치에 커밋했다(중간35be30e, 최종 기록은 `git log -1`). main 병합·원격 push·운영 배포는 미실행. 검증 전용 컨테이너와 임시 자격증명은 검사 종료 후 제거했다. 공용 PostgreSQL 설정과 실제 업무 DB는 변경하지 않았다.

## 재현 및 다음 단계

Python3.14/Node24를 사용한다. 신규 `_test` 전용 DB에 `alembic -c backend/alembic.ini upgrade head`, `python tools/verify_ddl_matches_schema.py` 후 `pytest backend/tests/test_gw_company.py` 및 HR work/users·GW 기존 기능·Flow 관련 API를 검사한다. 같은 DB에서 검사를 동시에 실행하지 않는다. 코드·정적 명세 검사는 `npm run db:validate`, `python tools/audit_schema_isolation.py`, `python -m unittest discover -s tools -p 'test_*.py'`. 공식 ruff는 `--config backend/pyproject.toml`을 지정한다. Excel은 `tools/build_db_design.mjs --artifact`/`--target`, ERD는 `tools/build_erd.py`/`--target`로 재생성한다. DB URL/비밀번호는 명령 기록·문서·Git에 넣지 않는다.

다음 GW-COMPANY-03은 최초 설정/본인 연결 동의/역할/결재·게시 객체 ACL·읽기/재배정이다. 04 협업/화면,05 통합·P0 실제 운영 인증/복구/보존 인수 전에는 회사 실운영 완료가 아니다. 저장소 AGENTS.md의 ID별 결과 확인 규칙을 유지한다.
