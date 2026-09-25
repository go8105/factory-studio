# Factory Studio 작업 인계

갱신: 2026-09-25 (FS-020 MES 15/15 완료, Claude Code). **다음 세션은 이 문서부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git·작업 위치

- 저장소(메인 폴더, Claude Code 전용): `/Users/hwang-kyoungho/projects/factory-studio`
- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/*`. 메인 폴더를 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- main·origin `cc8729d`(MES 6/7 + Codex FS-019a 통합), CI 통과.
- **Claude Code**: 브랜치 `fs-020g-mes-dashboard`(FS-020g, MES 15/15) push → CI → main ff.
- **Codex**: `../factory-studio-codex` · `codex/fs-019a-erp-master`(`4e2bc74`). 통합은 Claude Code가 새 브랜치로 진행했으므로 Codex는 다음 ID를 새 main에서 분기한다. 아래 **Codex — FS-019a** 절 참고.
- **MES·ERP 작업 계획과 프롬프트: `docs/agent/MES_ERP_작업계획_FS-019_020.md`** (분배·순서·병행 규칙·FEMS 함정·프롬프트 §9).
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list --branch <b>` / `gh run watch <id> --exit-status`.
- 정정: 예전 인계의 "`78e1206` CI도 날짜 때문에 실패했을 것"은 틀렸다(09-24에 돌아 성공).

## 끝난 것

- **FS-018 FEMS 14화면 완료**(018a~m). 마지막 018k F-13 · 018l F-12 · 018m F-09. 보고서 `docs/agent/FEMS_FS-018*.md`.
- **Codex 테스트 시간 단축**: 개선 전 312 passed 782.272초 → 개선 후 368.737초 / 308.066초(평균 56.7% 단축). 상세 [테스트 시간 단축](테스트시간단축.md).
  - `conftest.py`: 공유 `guest_template`은 세션당 1회, `guest_space`는 실제 guest API로 테스트마다 새 공간. `FS_TODAY=2026-09-24`·`GUEST_LIMIT=10000` 고정. 게스트만 자식 → 부모로 정리, 템플릿 불변·게스트 잔여 0을 세션 끝에 검사.
  - 전체 DB를 TRUNCATE하는 legacy 테스트를 먼저 실행. **한 테스트에서 `clean_database`와 `guest_space`를 섞으면 수집 오류.**
- F-09 테스트(`test_fems_sites.py`)도 통합 시 `guest_space`로 전환했다.

## 다음 할 일

1. Claude Code: FS-020g main ff. MES 완료 — 다음은 사용자와 정한다(ERP 분담 또는 FS-021 통합 검증 준비).
1-1. Codex: 새 main에서 `codex/fs-019b-...` 분기 → FS-019b. ERP 화면 관리 버튼(`link-button`)·등록 폼 select(`.field` 안 전체 폭) 모양을 FEMS·MES와 맞춘다. 스모크는 실행 전 사용자에게 묻는다.
2. Codex: FS-019a 진행 중. 먼저 끝난 쪽이 main ff, 나중 쪽이 rebase(공유 파일: main.py·App.tsx·Home.tsx·portal.spec.ts·styles.css).
3. 사용자 결정 대기: E-G07(0원 매출 세금계산서, FS-019d 전), 사용 중 채널 배수 변경 허용 유지(`FEMS_FS-018l.md`).
4. **스모크(`tools/run_portal_smoke.py`)는 8000·5173 포트와 `factory_studio_fs017_test`를 고정 사용** — Claude Code와 Codex가 동시에 실행하지 않는다.
4. **새 업무 테스트는 `guest_space` fixture를 쓴다**(FEMS 테스트 파일 참고: `def fems(guest_space): return guest_space[:2]`).

## 재현·주의점

- DB: Claude Code는 `factory_studio_fs016_test`(pytest)·`factory_studio_fs017_test`(스모크), Codex는 `factory_studio_codex_test`만. 같은 DB에 pytest를 동시에 돌리지 않는다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 테스트는 `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만.
- **ruff는 CI 범위로만**: `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `format --check`.
- schema.json·마이그레이션 변경 금지. `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 확정·게시 데이터 불변, 업무 쓰기는 `write_scope` 뒤, 결측(invalid)은 합계에서 제외.
- 30분마다 WIP 커밋, 종료 시 이 문서 갱신·커밋. `.env`·`work/`·`node_modules`는 스테이징하지 않는다. `git push --mirror` 금지.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# backend: CI 환경 변수 네 개만 전달 (접속 URL은 출력하지 않는다)
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$db_url" TEST_DATABASE_URL="$test_db_url" \
  uv run --project backend pytest backend/tests -q
uv run --project backend --env-file .env python tools/run_portal_smoke.py   # 8000·5173 비어 있어야 함
python -m unittest discover -s tools && npm run db:validate && python tools/audit_schema_isolation.py && git diff --check
```


## Codex — FS-019a (2026-09-25)

- 브랜치: `codex/fs-019a-erp-master`, 전용 `factory-studio-codex`만 사용.
- 마지막 커밋: `5ad511d WIP FS-019a`(보존 커밋 d47b8a4를 6bcbe1e 위로 rebase한 결과). 이 절과 최종 결과는 후속 `FS-019a: ERP 기준정보 구현 및 회귀 검증` 커밋에 포함한다. 최신 커밋은 `git log -1`로 확인한다.
- 끝난 것: ERP E-15~18 API·화면·도움말·API 계약, guest_space 기반 ERP 회귀 78개, 프론트 ERP 테스트 20개. MES/ERP 라우트를 모두 보존했고 Home은 세 솔루션 화면 진입으로 변경. Field children 제거, select 직접 렌더링, checkbox inline-check 적용.
- 검증: 최종 frontend 5종(314 tests), CI Ruff 2종, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 510 passed, 580.736초, exit 0(CI 환경 네 변수만, 전용 DB).
- 다음: 사용자 승인 후 공용 포트/DB 스모크 실행 및 ERP 360px 스크린샷 직접 확인. 아직 실행 승인이 없어 미실행. FS-019a 완료 판정은 이 검증 뒤이며 FS-019b 착수·push·main 병합은 사용자 확인 뒤.
- 주의: pytest DB는 `factory_studio_codex_test`, 스모크는 `factory_studio_fs017_test` + 8000/5173(Claude Code와 공유). 동시 실행 금지. schema.json·마이그레이션·test_common.py·test_seed.py·conftest 변경 없음. 새 의존성 없음.
- 보고서: `docs/agent/ERP_FS-019a.md`(명령·exit·런타임·남은 검증).

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# task_test_url은 factory_studio_codex_test 접속 URL. .env 없이 네 변수만 전달.
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" uv run --project backend pytest backend/tests -q --durations=15
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
npm run db:validate
uv run --project backend python tools/audit_schema_isolation.py
git diff --check
# 스모크는 사용자 승인 후 tools/run_portal_smoke.py 실행.
```


## Codex — P-02 런처 크기 조정 (2026-09-25)

- 브랜치 `codex/fs-019a-erp-master`, 기준 마지막 커밋 `4e2bc74`. 후속 `P-02: 솔루션 런처 아이콘 타일 크기 조정` 커밋에 이 인계 포함(`git log -1`로 확인).
- 끝난 것: 사용자 두 번째 이미지의 작은 아이콘 타일/하단 이름 배치 적용. Home.tsx·Home.css 변경, 기존 색상·동작 보존.
- 검증: Node 24.21.0, frontend typecheck/lint/format:check/build/test(314 passed) 및 diff --check 모두 exit 0.
- 다음: Claude Code가 새 main 통합 뒤 스모크·360px(ERP 및 런처 포함) 직접 검증. Codex는 사용자 지시로 스모크를 실행하지 않는다. 결과에 따른 수정 요청 대기. backend 검증 미실행(UI만 변경).
- 재현: 전용 factory-studio-codex에서 Node 24 PATH 지정 후 `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run build`, `npm --prefix frontend test`.
- 메인 폴더 미사용, push·main 병합 없음. .env·work/·node_modules 제외.

## Codex — 3D 공장 둘러보기 (2026-09-26, 진행 중)

- 브랜치 `codex/fs-019a-erp-master`, 기준 `f9eb879`. 현재 구현을 WIP로 보존한다.
- 사용자 승인: 조감도 + 3인칭 이동, 일반 조립/비전검사/포장 설비 3대·키오스크, 1층 현장사무실 1명·바코드 프린터, 2층 사무실 2명, 현장 순회 1명 + 사용자 캐릭터.
- 구현: frontend/src/factory 및 App의 `/factory`·상단 메뉴. 외부 모델/DB/API 없이 합성 시연. 키보드/터치, 계단·충돌·층 전환·일시정지·오류 대체 안내.
- 별도 5186 포트, 모의 API로 렌더링 사전 확인(공용 스모크 아님). 초기 frontend typecheck/lint exit 0, 선택 테스트 15/16 통과(부동소수점 비교 1건 수정, 재실행 대기). 브라우저 오류 0 및 360px 가로폭 확인. 최종 수정 후 전체 검증은 아직 미실행.
- 다음: `npm --prefix frontend run test:factory-browser`, 최종 프론트 5종, 스크린샷 확인, 문서/커밋. 공용 8000/5173·스모크 DB 및 backend 미사용. push/main 병합 금지.
- 실행은 Node 24 PATH 지정. 5186에 이전 preview Vite가 남았으면 본 세션 프로세스만 종료 후 테스트한다. 메인 폴더는 사용하지 않는다.
