# FS-019a ERP 기준정보

2026-09-25 · Codex · `codex/fs-019a-erp-master` · 작업 폴더 `../factory-studio-codex`.

## Git·범위

- `9d896fd`에서 분기한 작업을 요청에 따라 `WIP FS-019a`(`d47b8a4`)로 보존한 뒤 `origin/main 6bcbe1e`(MES FS-020a~e)로 rebase했다. rebase 후 WIP 해시는 `5ad511d`.
- main.py·App.tsx·Home.tsx 충돌은 MES와 ERP를 모두 보존했다. 포털 360px 목록도 MES 항목을 유지하고 ERP만 추가했다. Home 안내는 “세 솔루션 모두 화면으로 연결됩니다”.
- E-15 거래처, E-16 품목·단위환산, E-17 거래처별 단가, E-18 계정과목·분개규칙 읽기 전용. ERP 진입은 `/erp` → `/erp/partners`.
- backend `fs/erp/{router,service,repository,schema}.py`, frontend `erp/` 레이아웃·화면·ERP 내부 Master 패턴. 기존 shared 컴포넌트·스타일과 FEMS/MES 업무 코드는 수정하지 않았다.

## 구현 규칙

- 모든 업무 질의는 S=(workspace_id,generation_id). 읽기 `read_scope`, 쓰기 `write_scope` 잠금·세대/모듈 재확인 뒤 멱등 영수증 처리. 입력 400 + fields, 정책 409 + reason/references, 참조 삭제 `REFERENCED_BY_OTHERS` + 건수.
- 거래처: 코드·이름·CUSTOMER/SUPPLIER·nullable 결제조건 일수·사용 여부. 품목: ERP 독립 안내, 기준 단위·품목 구분·과세 구분·사용 여부.
- 단위환산: 품목 하위 경로. toUnit은 품목 기준 단위로 서버 결정. fromUnit 중복/기준 단위 동일, 계수 0 이하 차단. 참조 중인 품목 기준 단위 변경과 삭제는 건수와 함께 차단.
- 단가: 연월 양 끝 포함, 종료월 null 무기한. 같은 거래처·품목의 겹침은 구분·통화·사용 여부와 무관하게 거부. 생성/수정 둘 다 검사하며 실패는 트랜잭션 롤백. 기존 전표 금액 소급 변경 없음.
- E-18은 7계정·10규칙과 매핑 이유를 표시하며 쓰기 라우트/버튼 없음.
- 목록 offset 페이지, 상세·쓰기의 타 공간/이전 세대 ID 격리. 코드/필드 오류·비활성 모듈·세션 만료 안내. 삭제 확인, 저장 중 중복 요청 차단, 불확실 응답의 동일 멱등 키 재사용.
- 일반 입력만 `Field` 사용. select는 직접 `.field` + label/select, checkbox는 `.inline-check`. fieldset은 기존 `.field`로 min-width:0 적용. 관리 열은 식별 열 바로 뒤.
- 도움말 E-15~17은 실제 필드/정책에 맞췄다. E-18은 기존 읽기 전용 설명이 구현과 같아 유지했다. 견적 자동 단가 연동은 후속임을 명시했다.
- 새 의존성 없음. schema.json·마이그레이션·conftest·test_common.py·test_seed.py 변경 없음.

## 검증 (스모크 승인 대기)

런타임 Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend는 `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만, 두 URL 모두 `factory_studio_codex_test`.

| 명령 | 결과 | exit |
|---|---|---:|
| `git fetch origin` | 완료 | 0 |
| `git rebase origin/main` | 최초 충돌 exit 1, MES·ERP 보존 후 continue 완료 | 0 |
| `npm --prefix frontend run typecheck` | 통과 | 0 |
| `npm --prefix frontend run lint` | 통과 | 0 |
| `npm --prefix frontend run format:check` | 통과 | 0 |
| `npm --prefix frontend run build` | 통과 | 0 |
| `npm --prefix frontend test` | 314 passed(ERP 20 포함) | 0 |
| `uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` | 통과 | 0 |
| `uv run --project backend ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py` | 73 files | 0 |
| backend ERP 선택 pytest | 초기 68 passed, 이후 격리·페이지/롤백 10개 추가 | 0 |
| `uv run --project backend pytest backend/tests -q --durations=15` | 510 passed, 2 warnings; pytest 576.92초 / 전체 경과 580.736초 | 0 |
| `npm run db:validate` | 71테이블·712컬럼·161 FK, 오류 0 | 0 |
| `uv run --project backend python tools/audit_schema_isolation.py` | R1~R5 오류 0 | 0 |
| `git diff --check` | 통과 | 0 |
| `uv run --project backend python tools/run_portal_smoke.py` | 사용자 실행 승인 대기, 미실행 | — |

- backend 기존 432 + ERP 78 = 510개 모두 통과. 경고 2개는 기존 Starlette/httpx·AnyIO 사용 중단 예고다. CI 원격 실행은 push 전이므로 미실행.
- 새 backend 테스트는 guest_space만 사용한다. 검증 항목별 테스트 분리, ERP 본문/가격/단위환산 파일 분리.
- Playwright에 ERP 거래처 등록→수정→삭제 흐름 1개와 네 화면 360px 검증을 추가했다. 스모크 runner는 공용 8000·5173 및 factory_studio_fs017_test를 사용하므로 사용자 승인 전 실행하지 않는다. 스크린샷 직접 확인도 아직 미실행.
- 초기 프론트 검사에서 Testing Library의 지원하지 않는 `exact` 옵션을 제거했다(typecheck exit 2 → 0). Prettier를 잘못된 실행 디렉터리에서 호출한 exit 2는 frontend 폴더에서 재실행해 해결했다. 공통 Field에 children을 넘기던 초안을 수정했다.

## 재현·다음

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"
# task_test_url에 전용 factory_studio_codex_test 접속 URL 지정. 출력/커밋하지 않는다.
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" \
  uv run --project backend pytest backend/tests -q --durations=15
```

backend 전체는 통과했다. 스모크 승인/실행과 ERP 360px 스크린샷 직접 확인이 남아 있어 FS-019a 완료 판정은 보류한다. 다음 업무 ID는 사용자 확인 뒤 FS-019b이며 이번 작업에서 착수하지 않는다. main 병합·push는 사용자 확인 뒤다.
