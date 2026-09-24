# FS-018a 완료 보고 — FEMS 레이아웃 + F-11 에너지원

작성일: 2026-09-24 · 브랜치 `fs-018-fems` (main `a82670f`에서 분기) · 작업자 Claude Code

## 범위와 이유

FEMS 14화면 중 **기준정보 CRUD 패턴의 기준 구현 1개**만 만들었다. F-11 에너지원을 고른 이유: 선행 조건이 없고, 5개 테이블(계측 채널·환산/배출계수·요금제·목표·기준선)이 참조해 RESTRICT·참조 건수·코드 중복·비활성화를 모두 담는다. F-09/F-10/F-13/F-14는 이 파일을 복제하면 된다(아래 복제 가이드).

조회·계산 화면(F-01~F-08)은 이번 범위가 아니다.

## 구현

### 백엔드

| 파일 | 내용 |
|---|---|
| `fs/common/scope.py` | `read_scope`/`write_scope`. 같은 트랜잭션에서 활성 세대·모듈 사용 여부를 다시 읽는다. 쓰기는 core와 같은 공간 advisory lock(namespace 16)을 먼저 잡아 초기화 전환과 직렬화한다(FS-006 TX-01·TX-05) |
| `fs/fems/{router,schema,service,repository}.py` | FS-011 §3 계층. 트랜잭션 경계는 service. 조회는 REPEATABLE READ 읽기 전용 |
| `fs/main.py` | `/api/v1/fems` 등록 |

엔드포인트: `GET/POST /energy-sources`, `GET/PATCH/DELETE /energy-sources/{id}`. 변경 요청은 CSRF + `Idempotency-Key` 필수(core PATCH와 동일).

확정한 규칙:

- 범위 키는 서버가 결정한다. 본문에 `workspaceId` 같은 모르는 필드가 있으면 400(`extra="forbid"`).
- 모듈 비활성: 조회·쓰기 모두 409 `PRECONDITION_NOT_MET`, `details.reason="MODULE_DISABLED"`.
- 코드 중복: 400 `VALIDATION_FAILED`, `details.fields.sourceCode` → 화면 인라인 오류.
- 삭제 RESTRICT: 409 `REFERENCED_BY_OTHERS`, `details.references=[{table,label,count}]`.
- **참조 중인 에너지원의 계측 단위 변경 금지**: 409 `PRECONDITION_NOT_MET`, `reason="UNIT_IN_USE"`. 계측값·계수·요금 단가가 단위를 전제로 저장돼 있어 바꾸면 하위 계산이 조용히 틀린다. 이름·구분·사용 여부는 바꿀 수 있다.
- 정렬 화이트리스트 `sourceCode|name|createdAt : asc|desc`, 그 밖은 400.
- 마스터 CRUD는 audit_event를 남기지 않는다. 필요해지면 FS-021에서 판단한다.

### 프론트

| 파일 | 내용 |
|---|---|
| `src/fems/index.tsx` | FEMS 라우트 묶음. `App`에서 `lazy`로 불러 별도 청크(7.7kB) |
| `src/fems/FemsLayout.tsx` | 좌측 사이드바 + 포털 헤더. **구현된 화면만 메뉴에 둔다**(`femsScreens` 배열). 다른 앱은 업무 안내 링크 |
| `src/fems/EnergySources.tsx` | F-11. 목록(사용 중 필터·페이지) + 등록/수정 패널 + 행 삭제 2단계 확인. `MasterOrder`(등록 순서 안내) export |
| `shared/api.ts` | `/api/`로 시작하는 경로는 그대로 호출(솔루션 API) |
| `shared/components.tsx` | `PageTitle help` 키, `ErrorNotice` 참조처를 "라벨 N건"으로 표시, `DataTable empty` 슬롯 |
| `app/App.tsx` | FEMS·도움말 화면 lazy 로딩. **Vite 500kB 경고 해소**(529kB → 최대 282kB) |
| `portal/Home.tsx` | 런처 FEMS 카드 → `/fems`. MES·ERP는 기존 도움말 연결 유지 |

## 테스트 (항목별 분리)

- `backend/tests/test_fems_energy_source.py` **22개**: 자기 공간 목록 / 정렬 화이트리스트 / 세션 필요 / 다른 공간 404 / CSRF 필요 / 멱등 키 필요 / 등록 / 같은 키 재전송 동일 행 / 같은 키 다른 본문 422 / 코드 중복 필드 오류 / 구분 enum / 범위 필드 거부 / 이름 수정 / 참조 중 단위 변경 거부 / 미참조 단위 변경 허용 / 비활성화 필터 / 참조 삭제 건수 / 미참조 삭제 / 삭제 재전송 204 / 모듈 비활성 조회 차단 / 쓰기 차단 / 초기화 후 새 세대에 쓰기.
- `frontend/src/fems/energy-sources.test.tsx` **12개**: 런처 연결 / 진입 리다이렉트·목록 / 사이드바 구현 화면만 / 도움말 키 / 사용 중 필터 / 등록 헤더·대문자 코드 / 중복 인라인 오류 / 불확실 응답 같은 키 재시도 / 바뀐 항목만 PATCH / 삭제 확인 전 무요청 / 참조 건수 표시 / 모듈 비활성 안내.
- Playwright `frontend/e2e/fems.spec.ts` **3개**(런처→목록, 등록, 참조 삭제 거부) + 360px F-11 가로 넘침 없음 1개. 실제 API, 모킹 없음.

## 실행 검증

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend DB `factory_studio_fs016_test`, 브라우저 DB `factory_studio_fs017_test`, 순차 실행.

| 명령 | exit | 결과 |
|---|---:|---|
| `npm --prefix frontend run typecheck` | 0 | |
| `npm --prefix frontend run lint` | 0 | |
| `npm --prefix frontend run format:check` | 0 | |
| `npm --prefix frontend run build` | 0 | 청크 크기 경고 없음 |
| `npm --prefix frontend test` | 0 | 84 passed (기존 72 + 12) |
| `ruff check` / `ruff format --check` (backend/src, 신규 테스트) | 0 / 0 | |
| backend 전체 pytest | 0 | 62 passed (기존 40 + 22), upstream 폐기 경고 2 |
| `uv run --project backend --env-file .env python tools/run_portal_smoke.py` | 0 | Playwright 20 passed |
| `python -m unittest discover -s tools -p 'test_fs0*.py'` | 0 | 44 passed (`ABORT: injected replace failure`는 의도한 오류 주입) |
| `npm run db:validate` | 0 | |
| `python tools/audit_schema_isolation.py` | 0 | errors [] |
| `git diff --check` | 0 | |

schema.json·마이그레이션·content·conftest·test_common·test_seed는 main 대비 변경 0.

## antigravity 복제 가이드 (F-09·F-10·F-13·F-14)

1. 백엔드: `repository.py`에 `<RES>_COLUMNS`·`<RES>_SORT`·`<RES>_REFERENCES`와 5개 질의 함수를 추가하고, `service.py`의 에너지원 함수 5개를 복제한다. **모든 질의에 `workspace_id=:w AND generation_id=:g`**, 쓰기는 반드시 `write_scope` 뒤. 참조 테이블 목록은 `pg_constraint`의 `confrelid`로 확인한다.
2. 부모를 참조하는 자원(F-10 설비→공간, F-13·F-14→에너지원)은 등록·수정 시 **부모가 같은 S에 있는지 service에서 확인**하고 없으면 400 `fields.<parentId>`. DB 복합 FK가 최종 방어선이다.
3. 프론트: `EnergySources.tsx`를 복제하고 `femsScreens`에 한 줄 추가, `fems/index.tsx`에 라우트 한 줄. 선행 데이터가 없으면 `EmptyState`로 선행 화면 링크(FS-008a FEMS §2).
4. 테스트는 위 목록과 같은 단위로 **항목별 분리**. 한 테스트에 여러 검증을 묶지 않는다.
5. F-12(마스터-디테일)·F-13(PRIMARY/EMISSION 탭 분리)은 구조가 달라 Claude Code/Codex 대상으로 남긴다.

## 남은 것

- FS-018b: 조회형 패턴 첫 구현(F-02 계측 조회: 기간 필터·결측 행 표시·1시간 해상도). 그 뒤 F-01·F-03~F-08 계산 화면.
- F-07 목표=실적×95% 판단은 F-07 구현 시 화면을 보고 결정(사용자 확인 필요).
- 흐름 맵의 `energy_master` 노드는 여전히 도움말 연결(콘텐츠 계약 변경은 FS-018 화면이 더 생긴 뒤 한 번에).
