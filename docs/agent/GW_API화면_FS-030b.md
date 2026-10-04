# FS-030b GW API·화면 완료 보고

작성: 2026-10-04 · 브랜치 `codex/fs-030-gw` · 기준 `origin/main` 8531c05.
구현 WIP: 2a80375. 최종 커밋은 이 문서를 포함한 `git log -1`에서 확인한다.

## 완료 범위

- G-01~07: 업무 현황, 담당자, 결재선, 기안함, 결재함, 문서함, 게시판. 기존 UI-02 패널·목록·모바일 패턴 적용.
- 초안 → 상신 → 순차 승인/반려 → 완료. 회수·재상신은 기존 이력을 보존하고, 재상신은 새 문서를 만든다. 1~3단계 결재선·자기 결재 방지·현재 차례 검증.
- 실제 로그인 주체와 합성 담당자 역할을 구분해 감사 기록. 공간/세대 격리, 변경 버전 검사, 멱등 재시도, 경합 시 단일 처리.
- 공지/자유 글의 초안·게시·정정·철회. 댓글·첨부 없음. 본문은 일반 텍스트이며 게시 후 내용은 고정한다.
- ERP 매입 전표 코드 스냅샷·금액/수량 문자열 정규화·digest. 상신 시 원문 변경/취소/모듈 중지 검사. E-11은 결재 상태를 읽기만 하며 ERP 확정에 영향을 주지 않는다.
- 런처·홈 타일·분야·아이콘·솔루션 전환·문서 진입·평가 모듈 등록. 저장 중 역할/대상 변경 방지와 미저장 입력 보호.

## 변경 파일

- 신규 `backend/src/fs/gw/{schema,service,router,interface}.py`, `__init__.py`, `backend/tests/test_gw.py`.
- `backend/src/fs/main.py`, `core/review.py`, `erp/{interface,purchases,router}.py`, ERP README 제공 조회 함수 표.
- 신규 `frontend/src/gw/` 화면·공통 요청/역할·스타일·단위 검사, ERP `GwApproval.tsx` 및 매입 상세 배지.
- 프런트 라우트·홈/진입/참고 문서·공통 표 ID·아이콘·솔루션 전환 링크, `content/systems.json`.
- GW/홈/포털/레이아웃 브라우저 검사, Vite/Playwright와 `tools/run_portal_smoke.py`의 전용 포트·DB 설정.
- API 계약서, GW 모듈/화면/README, 로드맵, 현황, 진행 기록, HANDOFF, 이 보고서.
- 이번 b는 DB 구조·마이그레이션·schema.json·Excel·ERD·시드를 바꾸지 않았다. main의 v0.17.0 / 118테이블·270FK / head `fs029b_cmms_module`, 템플릿 14,687행·복사 14,685행 유지.

## 실제 검증 결과

| 검증 | 결과 | exit code |
|---|---|---|
| GW API 회귀 | 20 passed; 순차/경합/멱등/원문/게시/권한/공간·세대/감사 | 0 |
| backend 전체 pytest | 839 passed, 1 failed, 2 warnings (41분 24초) | 1 |
| 위 실패 검사 단독 재실행 | `test_seed_copy_performance_benchmark` 1 passed | 0 |
| frontend 전체 Vitest | 62파일·518 passed | 0 |
| 마지막 ERP 배지 갱신 후 관련 Vitest | 2파일·11 passed | 0 |
| Chromium GW + 배치 검사 | 업무 4 + 데스크톱 6 + 모바일 7 = 17 passed | 0 |
| 마지막 GW 업무 재검사 | 미저장 보호 추가 및 ERP 중지 포함 5 passed (기존 4 중복) | 0 |
| 도구 unittest | 73 passed | 0 |
| Ruff check / format | 163파일 통과 | 0 |
| TypeScript / ESLint / Prettier / production build | 통과 | 0 |
| DB 설계 검증 / 격리 감사 R1~R6 / 실제 DDL 대조 | 오류 0 / 0 / 0 (118테이블·270FK) | 0 |

전체 pytest의 유일한 실패는 다른 검증을 동시에 실행하던 중 시드 복사 최대 3.426초가 기존 2초 기준을 넘은 것이다. 단독 재실행은 기준이나 코드를 바꾸지 않고 통과했다. 동시 실행 부하의 영향 가능성은 있으나 원인을 확정하지 않는다. 전체 suite를 다시 한 번 모두 통과시킨 것으로 표기하지 않는다. FastAPI/Starlette의 기존 deprecation 경고 2개와 기존 3D 번들 크기 경고가 남는다.

브라우저 추가 검사 최초 실행은 확인 창 닫기 후 포커스가 입력란 밖에 있어 Escape 기대가 실패했다. 입력란에 포커스를 준 상태로 수정 후 5개 모두 통과했다. 앞선 선택자/게스트 대기 조건 실패도 보정 후 재검증했다. 서로 다른 브라우저 검사 항목은 총 18개이며 재실행 횟수를 합산하지 않는다.

## 인수 기준과 남은 검증

- AC-220 DB 부분은 a에서 검증. b는 AC-221~236의 결재·게시·권한·ERP 경계를 API/UI로 검증했다.
- AC-237의 체험 시드 69행과 복사 후 실제 업무 체험, AC-239의 도움말/흐름맵 연계 및 전 솔루션 통합은 c에서 완료한다. AC-238의 업무일/실제 시각 분리·금액 정밀도는 API 검사에 포함했다.
- 미실행: Safari/실기기, 운영 부하 시험, 전체 솔루션 Playwright 재실행, c 신규 시드·도움말 검증, 운영 환경 검증.
- b는 빈 GW에서 담당자·결재선·문서를 직접 만드는 흐름까지 제공한다. 게스트에게 즉시 보이는 69행의 완성 체험과 도움말 본문은 아직 없다.
- 공유 개발/Claude/운영 DB는 사용하지 않았다. `factory_studio_codex_fs030b_test`, `_full_test`, `_browser_test`만 사용했다. 스모크는 8030/5230, Node 24 사용.

## 재현

비밀 값은 파일/로그에 출력하지 않고 전용 테스트 DB 접속 환경변수로 제공한다. `DATABASE_URL`과 `TEST_DATABASE_URL`이 Codex 전용 DB를 가리키는지 먼저 확인한다.

```sh
backend/.venv/bin/pytest backend/tests/test_gw.py
backend/.venv/bin/pytest backend/tests
backend/.venv/bin/pytest backend/tests/test_seed.py::test_seed_copy_performance_benchmark
npm --prefix frontend test -- --maxWorkers=2
npm --prefix frontend run build
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm run db:validate
python3 tools/audit_schema_isolation.py
```

실제 브라우저 재현은 전용 DB 접속 환경과 Node 24를 준비한 뒤 실행한다(전용 DB 데이터가 테스트로 교체됨).

```sh
FS_SMOKE_DB=factory_studio_codex_fs030b_browser_test FS_SMOKE_API_PORT=8030 FS_SMOKE_WEB_PORT=5230 backend/.venv/bin/python tools/run_portal_smoke.py e2e/gw.spec.ts e2e/portal.spec.ts e2e/layout.spec.ts --grep 'gw|GW'
```

## 다음 단계

사용자 b 확인 후 **FS-030c**: 승인 설계의 GW 업무 시드 69행·검증기·게스트 복사, g-01~07 도움말·사용자 참고 문서, 흐름 맵, 전체 통합 검증. 시작 시 최신 main의 CMMS 진행·시드 합계·head를 다시 확인한다. push·배포·main 병합은 하지 않았다.
