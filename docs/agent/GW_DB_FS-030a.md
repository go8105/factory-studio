# FS-030a GW DB 완료 보고

2026-10-01 · 브랜치 `codex/fs-030-gw` · 기준 main `6350697` · 구현 WIP `15f9398`, 최종 커밋은 `git log -1`.
사용자 “구현 진행해줘”로 전체 모듈·화면 설계 승인. 이번 완료 범위는 a DB이며 b API·화면은 사용자 확인 후 시작한다.

## 변경

- 신규 `gw.person`·`approval_route`·`route_step`·`approval_document`·`approval_step`·`approval_event`·`board_post`·`board_event` 8테이블. 범위 복합 FK, RESTRICT, 순서1~3, 현재 진행 중인 동일 ERP 원천의 중복 상신 방지 인덱스, 상태/사유/스냅샷 CHECK. 업무 스키마 간 FK 없음.
- `tools/apply_fs030a.py`·`test_fs030a.py`·`validate_fs030a.py` 추가, 기존 검증 작업/버전 집합 확장. 기존 메타데이터 유지·부분 적용 거부·재실행 멱등 검증.
- 신규 revision `fs040_app_review → fs030a_gw → fs030b_gw_module`. 고정 DDL 사용, 적용된 기존 migration 변경 없음. 기존 공간에 gw 기본 활성화, 다른 모듈의 꺼짐 유지. GW 데이터/평가가 있으면 downgrade 거부.
- core의 기존 모듈 CHECK 두 곳(workspace_module/app_review)에 gw 허용. 업무 테이블을 core에 추가하지 않음. 평가 API의 GW 허용/런처 연결은 b에서 함께 구현.
- schema.json·DB설계서.xlsx·전체/모듈 ERD 동시 갱신. 임시버전0.15.0-gw, 112테이블·1,225컬럼·258FK·제약/정책978. main 병합 시 최종 버전 조정 필요.
- 스키마 목록: audit/DDL/Excel/ERD/validator, seed generate/copy/validate, core 새 공간·초기화, seed/common 테스트. 모듈행1개 추가로 템플릿11,934/게스트11,932. GW 업무69행은 c에서 추가한다.
- 게스트 복사는 내부 FK/자기 참조를 새 ID로 연결하고 source_snapshot.display의 날짜만 이동한다. 원천 digest는 그대로 보존. GW 신규 처리 시각은 DB clock_timestamp, FS_TODAY와 비교하지 않음.

## 실행 검증

| 검증 | 실제 결과 |
|---|---|
| 전용 PG DB, GW 제약·seed·common·schema_verifier pytest | **45 passed**, 기존 의존성 경고2, 100.95초, exit0 |
| tools/test_fs0*.py 전체 | **69 passed**, exit0(ABORT 문구3건은 의도한 실패 주입 테스트) |
| CI ruff check / format | check 통과·154파일 형식 통과, exit0 |
| db:validate / 격리 R1~R6 | 각각 오류0, exit0 |
| 실제 PostgreSQL DDL–메타데이터 대조 | 오류0, exit0; SERVICE 정책133개는 DB 제약과 구분 |
| 빈 전용 DB upgrade head → downgrade base → upgrade head | 통과, exit0 |
| 기존 FS-040 공간에서 upgrade, ERP off 유지·GW true | 통과, exit0 |
| GW 데이터 존재 상태 downgrade | 예상대로 거부; head·모듈행·업무행 모두 보존 확인, 검사 스크립트 exit0 |
| Excel 재생성·렌더 | 39시트, inspect 오류0; GW4시트 미리보기 확인, exit0 |
| ERD 재생성 / git diff --check | 통과, exit0 |

DB는 `factory_studio_codex_fs030_test` 및 `factory_studio_codex_fs030_roundtrip_test`만 사용했다. 공유 개발·Claude·운영 DB에는 적용하지 않았다. 빈 DB 왕복 후 기존 공간 시나리오를 별도 구성했다.

검증 중 보정: 최초 도구 테스트에서 WMS 테이블 수의 FS-030a 분기 누락1건을 수정 후69개 통과. 최초 왕복 검사의 합성 게스트 fixture에 guest_actor_key를 빠뜨려 실패했으며 fixture 보정 후 통과. 최초 format 검사2파일을 정리 후154개 통과. 제품 제약을 완화하지 않았다.

## 재현

전용 DB 접속 문자열을 환경 DATABASE_URL/TEST_DATABASE_URL에 주입한다(자격증명은 문서/로그에 적지 않음). 이름은 반드시 Codex 전용 *_test 사용.

```sh
python3 -m unittest discover -s tools -p 'test_fs0*.py'
npm run db:validate
python3 tools/audit_schema_isolation.py
backend/.venv/bin/ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
backend/.venv/bin/pytest backend/tests/test_gw_schema.py backend/tests/test_seed.py backend/tests/test_common.py backend/tests/test_schema_verifier.py -q --tb=short
backend/.venv/bin/python tools/verify_ddl_matches_schema.py
python3 tools/build_erd.py
```

Alembic은 backend에서 `../backend/.venv/bin/alembic -c alembic.ini upgrade head`로 실행한다. 빈 **별도 전용 DB**에서만 downgrade base 왕복을 수행한다. 기존 공간 검증은 FS-040에 합성 GUEST 공간(UUID guest_actor_key 포함)과 ERP enabled=false를 넣고 upgrade 뒤 GW true/ERP false를 확인한다. GW person1행 추가 후 downgrade fs040_app_review 실패 및 revision/모듈행/업무행 보존을 확인한다. GW 행이 있는 DB를 강제로 삭제하지 않는다.

## 미실행·남은 일

- 전체 backend pytest, vitest, 실제 API/브라우저 스모크, 프런트 typecheck/lint/build, 네이티브 Excel 앱 검증은 이번 단계 미실행. GW 서비스가 없으므로 결재 동시성/권한/불변/추가전용 이력 및 AC220~239 전체를 완료로 간주하지 않는다.
- **b:** GW API·트랜잭션/SERVICE 정책·ERP 읽기 interface와 README·G01~07·E11 배지·런처/평가/전환/문서 연결·e2e. 완료 보고 후 사용자 확인.
- **c:** 합성 업무69행·시드 검증·도움말/참고 문서·흐름맵·전체 통합 검증. 완료 보고 후 사용자 확인.
- push·main 병합·운영 배포 없음. .env/work 스테이징 없음. 다른 작업자의 진행 내용은 유지했다.
