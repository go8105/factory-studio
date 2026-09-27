# Factory Studio 작업 인계

갱신: 2026-09-27 (UI-02 A4 FEMS 기준정보 S 패턴 전환 완료, Antigravity). **다음 세션은 이 문서부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git·작업 위치

- 저장소(메인 폴더, Claude Code 전용): `/Users/hwang-kyoungho/projects/factory-studio`
- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/*`. 메인 폴더를 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- main·origin: `0addc2e`(FS-019b) 이후 ERP 하위 ID를 순서대로 ff. 매출·채권 생성은 `erp/revenue.py`(019c)에 있고 019d~e가 이어 쓴다.
- Codex의 `codex/fs-019a-erp-master`에는 **이미 main에 통합된 커밋만** 남아 있다(FS-019a는 `5da9019`·`945a78a`, 런처·3D는 `a0f71ae`·`7c83bc7`·`c3f3213`으로 통합). **Codex는 다음 작업을 새 main에서 새 브랜치로 시작**한다.
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list --branch <b>` / `gh run watch <id> --exit-status`.

## 현재 진행

| 영역 | 상태 |
|---|---|
| 포털 | 7/7 + 3D 공장(`/factory`, 건물 외관·내부·생산라인 고도화 통합) + 런처 아이콘 타일 |
| FEMS | 14/14 (FS-018a~m) |
| MES | 15/15 (FS-020a~g) — `docs/agent/MES_FS-020*.md` |
| ERP | 18/18 (019a 기준정보 E-15~18, 019b 영업 E-02~04, 019c 출하 E-05~06 + 매출·채권 생성, 019d 매출·세금계산서 E-07~08, 019e 채권·수금·소명 E-09~10, 019f 매입·채무·지급 E-11~13, 019g 분개 미리보기 E-14, 019h 대시보드 E-01) — **FS-019 종료** — 계획 `docs/agent/MES_ERP_작업계획_FS-019_020.md` §3, 보고 `docs/agent/ERP_FS-019*.md` |
| FS-021 | 완료 `docs/agent/통합검증_FS-021.md` — 정책 7건 통과, AC-35~80 검증 33·부분 5·미구현 4·폐기 4(나머지는 1차 범위 밖), AC-63 결함 수정, 로컬 실측(동시 생성 지연은 현행 유지) |
| FS-022 | **완료 — https://eip.hugh-d.com**. 이지스 서버 공존(Nginx 443 이름 기반, uvicorn 127.0.0.1:8021, PG18 Docker 55432, Cloudflare 프록시 + Origin CA). 절차·업데이트·걷어내기 `docs/deploy/배포절차_FS-022.md`. 서버 접속: 맥북 `ssh root@158.247.236.136`(키) |
| UI-01 | 완료 `docs/ui/디자인시스템_UI-01.md` — main 통합·서버 배포(2026-09-26). 공통 토큰·`SolutionLayout`(접기·서랍)·넓은 업무 화면·3D 캔버스 확보. 393·10·107 통과 |
| 운영 | 443은 Cloudflare IP만, 이지스는 https://aegis.hugh-d.com(Cloudflare Access)·:8000 외부 차단, 운영자 계정은 `tools/create_member.py`(서버에서 실행), DB는 SSH 터널(§12-5) |
| UI-02 | **진행 중(A1~A4 완료)** `docs/ui/공통UI규약_UI-02.md` — A1 대시보드(M-01, E-01), A2 조회 목록(M-09, E-07, E-14, P-07), A3 보고서형 조회(F-03, F-04, F-06, F-07, F-08, E-09·12), A4 FEMS 기준정보(F-09, F-10, F-11, F-13, F-14) 완료, vitest 402 통과, 다음 A5 MES 기준정보 대기 |
| 다음 | Antigravity A4 사용자 리뷰/확인 → A5(MES 기준정보 M-02,03,06,08,10~13) 진행 |

## 다음 할 일

1. ERP 분담 확정(2026-09-26): **FS-019b~h 전부 Claude Code**(메인 폴더, `fs-019<x>-*`). Codex는 ERP를 하지 않는다.
2. E-G07 결정(2026-09-26): **0원 매출 세금계산서 발급 금지** — 019d에서 구현(409 `ZERO_AMOUNT_SALE`, 발급 대상 목록에서 제외).
0. **UI-02(2026-09-27)**: 브랜치 `ui-02-common-patterns` — 코드 `0875482` 뒤에 문서 커밋, main 통합(OPS `88d584f` 위 rebase). 화면은 대시보드(F-01)·조회 목록(F-02)·목록+패널(F-05) 세 패턴 중 하나로 만든다. `master-grid`는 레거시. Antigravity 작업은 `docs/agent/Antigravity_작업지시_UI-02.md`(기준 커밋 `0875482`이 main에 있어야 시작). 예외 8화면(F-12·M-04·M-05·M-07·M-14·M-15·E-02·E-04)은 Claude가 UI-03에서 대표 구현을 먼저 확정한다. 로컬 검증 스크립트(`work/ui02/*.mjs`, Git 제외)는 5173·8000 개발 서버와 `work/ui02/state.json` 게스트 세션을 쓴다 — 공식 검증은 `e2e/layout.spec.ts`.
3. **UI는 `shared/styles.css` 토큰·공통 클래스만 쓴다(UI-01).** 솔루션 메뉴는 `*Screens` 배열만 고친다. ERP 화면 모양을 FEMS·MES와 맞춘다: 관리 버튼 `link-button`, 등록 폼 select는 `.field` 안 전체 폭. 019b부터 ERP 화면은 `erp/common.tsx`(shared/hooks 위 ERP 접두사)와 `SalesOrders.tsx`의 `LineEditor`를 재사용한다.
4. 후속: (UI-01에서 360px 상단 메뉴 해소) 인라인 폼 미저장 변경 보호. 사용 중 채널 배수 변경 허용 유지 여부(FEMS_FS-018l).
5. **새 업무 테스트는 `guest_space` fixture**, 스모크는 8000·5173·`factory_studio_fs017_test`를 고정 사용하므로 **동시에 한 명만** 돌린다. 사용자가 개발 서버(8000·5173)를 켜 두면 스모크가 멈춘다 — 종료를 요청한다.
6. 판단 기록: MES `/work-orders/{id}/lot` 추가(020c), `/executions/{id}/finish`를 `/result`로 통합(020d), MES 업무 시각 `clock_timestamp()`(020g).

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

## Codex — 3D 공장 둘러보기 (2026-09-26)

- 브랜치 `codex/fs-019a-erp-master`, 마지막 보존 커밋 `5593693 WIP: 3D 공장 둘러보기 구현 보존`(기준 f9eb879). 이 인계·최종 수정은 후속 `3D 공장: 조감도와 3인칭 현장 둘러보기` 커밋에 포함한다. 최종 해시는 `git log -1`.
- 끝난 것: 사용자 승인한 조감도·3인칭 이동, 일반 조립/비전검사/포장 설비 3대·키오스크, 1층 현장사무실 1명·바코드 프린터, 2층 사무실 2명, 현장 순회 1명 + 사용자 캐릭터. `/factory`, 상단 앱 런처 오른쪽 메뉴. 상세 `docs/agent/3D공장_구현.md`.
- Node 24.21.0. 최종 frontend typecheck/lint/format:check/build/test(330 passed) 및 독립 브라우저 7개(20.0초), diff --check 각각 exit 0. 스크린샷 직접 확인. backend·DB·공용 스모크 미실행.
- 새 의존성은 package-lock에 고정. 통합 시 `npm --prefix frontend ci`. three/Fiber/Drei와 @types/three. 공장 화면에만 lazy load. 코드 생성 모델로 외부 모델 자산 없음.
- 재현: 전용 폴더에서 Node 24 PATH를 지정한 후 `npm --prefix frontend run test:factory-browser`. 전용 5186을 시작/종료하며 API는 모두 모의 응답한다. 공용 8000·5173·스모크 DB를 사용하지 않는다.
- 다음: Claude Code가 새 main 통합 뒤 전체 스모크·360px 실행. 사용자는 Codex의 공용 스모크 실행을 금지했으므로 실행하지 않는다. 통합 시 ERP(4e2bc74)·런처(f9eb879)·3D(WIP+후속)의 범위를 구분한다. 수정 요청 대기.
- 메인 폴더·antigravity 미사용. push/main 병합 없음. .env·work/·node_modules 제외. 별도 테스트 서버는 종료한다.


## 2026-09-26 Blender 비전검사 설비 (Codex)

- 사용자 "참고자료 없이 바로 진행" 승인. `codex/factory-vision-blender`에서 기존 공장의 비전검사 1대를 Blender 원본/GLB로 교체.
- 카메라·링 조명·컨베이어·경광등, 6초 검사 주기·5번째 불합격, 상태/수량 패널·가까이 보기·이상 정지/해제·MES 대시보드 진입. 합성 시연이며 업무 데이터에 저장하지 않음.
- Node 24.21.0: frontend typecheck/lint/format:check/build/test(345 passed), 독립 Chromium 브라우저 8개 통과(exit 0). 360px/데스크톱 직접 확인. Blender 5.2.2 GLB 생성 성공.
- DB/API 변경·새 의존성 없음. backend/DB/공용 통합 스모크 미실행. main 병합·push 없음.
- 원본 `assets/blender/vision-cell.blend`, 재생성 `tools/blender/build_vision.py`, 상세 보고 `docs/agent/3D공장_Blender_비전검사.md`.
- 다음: 시각 피드백·통합 담당자 main 통합. MES 실제 레코드 연결 및 FEMS는 후속 설계.


## 2026-09-26 3D 공장 공간 고도화 (Codex, 완료)

- 브랜치 `codex/factory-building`, 기준 `b352514`(비전검사). 사용자 우선순위 진행 및 이어서 진행 승인.
- Blender 건물 외관/내부 전환, 지붕·패널·창문·하역장·공조기·철골·덕트·천장 조명. 조립·포장 설비도 Blender 모델로 교체하고 프레스·실링바 시연.
- 바닥 질감·환경 반사·그림자, 자재 선반/공구대/소방함 및 충돌. MES/ERP/FEMS 기존 화면 진입 카드. 업무 API/DB·실제 데이터 연동 없음.
- Node 24.21.0: typecheck/lint/format:check/build exit 0. 전체 테스트는 자원 경합을 줄인 `npm --prefix frontend test -- --maxWorkers=2`로 346개 통과. 독립 Chromium 브라우저 10개 통과(2.1분, exit 0). 외관/내부/모바일 스크린샷 직접 확인.
- Blender 5.2.2 LTS. 생성 스크립트와 .blend/GLB를 저장. 새 npm 의존성 없음. 상세 `docs/agent/3D공장_공간고도화.md`.
- backend/DB/공용 통합 스모크·Safari/실기기 성능은 미실행. main 병합·push 없음. 다음: 사용자 시각 피드백 및 통합 담당자 main 통합. 최종 커밋은 이 인계를 포함한 `3D 공장: 건물·재질·생산라인 공간 고도화`이며 `git log -1`로 확인.

## Antigravity — UI-02 A1 (2026-09-27)
- 브랜치: `antigravity/ui02-a1` / 기준 커밋: `ed9f438cbbd1f2aacec67a3029304020e3d7865e` (main) / 마지막 커밋: `ce731ab`
- 옮긴 화면: M-01(`frontend/src/mes/Dashboard.tsx`), E-01(`frontend/src/erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 이동
  - 카드 순서·내용 및 2×2 유지, 쿼리 파라미터 및 KPI 보존
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01 조회 월 위치 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A2 (2026-09-27)
- 브랜치: `antigravity/ui02-a2` / 기준 커밋: `ce731ab` (`antigravity/ui02-a1`) / 마지막 커밋: `26e9ab3`
- 옮긴 화면: M-09(`frontend/src/mes/Receipts.tsx`), E-07(`frontend/src/erp/SalesRecords.tsx`), E-14(`frontend/src/erp/Journal.tsx`), P-07(`frontend/src/portal/Records.tsx`)
- 내용:
  - 각 화면 루트에 `.page-fill` 적용
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면 구조 준수)
  - 안내문 `<p className="muted" role="note">` 규약 정비 및 `Loading delay={300}` 적용
  - P-07의 ADMIN 권한 분기 및 API 계약 보존
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A3 (2026-09-27)
- 브랜치: `antigravity/ui02-a3` / 기준 커밋: `26e9ab3` (`antigravity/ui02-a2`) / 마지막 커밋: `ad54b6c`
- 대상 화면: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill`을 쓰지 않고 자연스러운 문서 스크롤 유지 (합계·근거·표 복합 구조)
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 적용 (F-04 배출량·소비량, F-06 원단위·생산량, F-07 달성률·목표·실적, F-08 요금, E-09/12 채권·채무 원금·소명액·잔액)
  - 합계 계산 표시, 계산 근거 펼침(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들(.page-fill 미사용) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 후 A4 진행 대기
