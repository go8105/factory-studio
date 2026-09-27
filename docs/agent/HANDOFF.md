# Factory Studio 작업 인계

갱신: 2026-09-27 (UI-03 B1·3D 1인칭 비전검사 통합, 스모크 169 통과. 남은 UI: E-02(UI-03 B2, Antigravity), Claude Code). **다음 세션은 이 문서부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

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
| UI-02 | **완료(A1~A6 전체 37화면 완료)** `docs/ui/공통UI규약_UI-02.md` — A1 대시보드(M-01, E-01), A2 조회 목록(M-09, E-07, E-14, P-07), A3 보고서형 조회(F-03, F-04, F-06, F-07, F-08, E-09·12), A4 FEMS 기준정보(F-09, F-10, F-11, F-13, F-14), A5 MES 기준정보 및 계획(M-02, M-03, M-06, M-08, M-10, M-11, M-12, M-13), A6 ERP 계획·출하·전표·기준정보(E-03, E-05, E-06, E-08, E-10·13, E-11, E-15~18) 완료 (누적 완료 40, 대기 0, Claude 선행 8, 유지 7 = 55), vitest 402 통과 |
| UI-02 검토 | Claude 검토·수정 후 main 통합(`86e729f` 이후 문서 커밋). 회귀 5건 수정·e2e 11건 갱신, 스모크 159 passed |
| 다음 | (UI-02 push·배포 완료 `0378bf6`) → Claude UI-03 예외 8화면(F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) |

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
- 남은 문제: 없음

## Antigravity — UI-02 A4 (2026-09-27)
- 브랜치: `antigravity/ui02-a4` / 기준 커밋: `ad54b6c` (`antigravity/ui02-a3`) / 마지막 커밋: `e6c9fd9`
- 대상 화면: F-09(`fems/Sites.tsx`), F-10(`fems/Equipments.tsx`), F-11(`fems/EnergySources.tsx`), F-13(`fems/Factors.tsx`), F-14(`fems/Tariffs.tsx`)
- 내용:
  - 레거시 `master-grid` 제거 및 `.page-fill` + `.split-view` + `FormPanel` + `useDiscardGuard` 표준 S 패턴 전환
  - F-09: 사업장과 공간 2개 섹션 블록 및 공통 FormPanel 적용
  - F-13: DataTable leading 탭 구조 및 FormPanel 통합
  - `frontend/e2e/layout.spec.ts`에 A4 화면들(.page-fill) 및 에너지원 패널 열기/닫기 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A5 (2026-09-27)
- 브랜치: `antigravity/ui02-a5` / 기준 커밋: `e6c9fd9` (`antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02 생산계획: `frontend/src/mes/Plans.tsx` (FormPanel 적용, RevealAnchor 제거)
  - M-03 작업지시: `frontend/src/mes/Orders.tsx` (FormPanel 적용, ?line= 프리셋 패널 자동 열림)
  - M-06 자재 투입: `frontend/src/mes/Materials.tsx` (FormPanel title="자재 투입 등록", inner form 제거)
  - M-08 패킹: `frontend/src/mes/Packing.tsx` (FormPanel 적용, inner form 제거)
  - M-10 사업장·공간: `frontend/src/mes/Sites.tsx` (2개 섹션 블록 + FormPanel S 패턴)
  - M-11 설비: `frontend/src/mes/Equipments.tsx` (FormPanel S 패턴)
  - M-12 품목: `frontend/src/mes/Items.tsx` (FormPanel S 패턴, RevealAnchor 제거)
  - M-13 공정: `frontend/src/mes/Processes.tsx` (FormPanel S 패턴)
- 내용:
  - 모든 컴포넌트에서 React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 무조건 호출하도록 구조 정리
  - `FormPanel` 내 중첩 `<form>` 제거로 브라우저 경고 및 파싱 오류 방지
  - `planning.test.tsx`, `master.test.tsx`에서 패널 오픈 버튼 클릭 후 폼 조회하도록 단위 테스트 동기화
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 패널 열기/닫기 E2E 테스트 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. A6(ERP 계획·출하·전표·기준정보 화면)으로 이어짐

## Antigravity — UI-02 A6 (2026-09-27)
- 브랜치: `antigravity/ui02-a6` / 기준 커밋: `cd0c1d7` (`antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18 기준정보: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03 판매계획: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05 출하지시: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06 출하: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08 세금계산서: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13 수금·지급 등록·소명: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11 매입 전표: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강 (`Prices.test.tsx`, `Partners.test.tsx`, `Items.test.tsx`, `shipping.test.tsx`, `revenue.test.tsx`, `purchases.test.tsx`)
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 및 Claude 선행 8개 화면(UI-03: F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기

## Claude Code — UI-02 검토·main 통합 (2026-09-27)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- 주의(다음 Antigravity 지시에 반영): 묶음마다 **공식 스모크(`tools/run_portal_smoke.py`)** 를 돌려야 한다. 단위 테스트는 패널 뒤 목록이 가려지는 문제를 잡지 못한다. 기본 e2e 뷰포트 1280px은 패널 겹침 모드다.
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## Antigravity — UI-03 B1 (2026-09-27)

- 브랜치: `antigravity/ui03-b1` / 기준 커밋: `24179d1`
- 대상 화면 (2개):
  - M-14 공정 경로: `frontend/src/mes/Routes.tsx` (F-12 부모-자식 패턴 적용: 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`, 게시한 버전 불변, '개정'·'게시' 동작 유지, `RevealAnchor` 제거)
  - M-15 BOM: `frontend/src/mes/Boms.tsx` (BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`, 게시한 버전 불변, 개정 새 코드 `FormPanel`, `RevealAnchor` 제거)
- 테스트 갱신 및 추가:
  - `src/mes/versions.test.tsx`: BOM 라인 폼 전환에 따른 라벨·버튼 접근자 갱신 (8 tests passed)
  - `e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시)
  - `e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가
- 검증:
  - `npm --prefix frontend run typecheck`: exit 0
  - `npm --prefix frontend run lint`: exit 0
  - `npm --prefix frontend run format:check`: exit 0
  - `npm --prefix frontend run build`: exit 0
  - `npm --prefix frontend test`: 44개 파일 410개 테스트 통과 (exit 0)
  - `git diff --check`: exit 0
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py`: 공식 스모크 **166 passed** (8.0분, exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행 대기

## 2026-09-27 1인칭 비전검사 체험 (FS-3D-FP01, Codex 완료)

- 브랜치 `codex/factory-building`, 기준 `d3eaf31`. 사용자 승인한 웹 1인칭 검사 구역 데모 구현.
- `/factory`의 1인칭 체험 진입, 눈높이 이동·드래그 시선·충돌, 직접 클릭/탭·E 선택, 데스크톱 옆 패널/모바일 아래 패널. 작업자 1명·태블릿·안전 구획·조명 보강.
- 상태·판정·검사/합격/불합격 수량·링 조명·시연 설정값. 합성 시뮬레이션이며 실제 업무 API/계측/DB 연결 없음. 실사 품질 인물·재질은 후속 개선 대상.
- Node 24: typecheck/lint/format:check/build exit 0. Vitest 348개/36파일 통과. 기존 Chromium 회귀 10개 통과, 새 1인칭 3개는 최종 분리 실행에서 모두 통과(1.9분). 처음 한 테스트에 선택·이동·스크린샷을 묶어 60초 제한을 초과한 것은 테스트를 분리해 해소. 화면 직접 확인.
- 5186·모의 API만 사용, backend/DB/공용 스모크·실기기 FPS·Safari/WebXR 미검증. main 병합·push·운영 배포 없음.
- 보고서 `docs/agent/3D공장_1인칭_비전검사.md`. 다음: 통합 담당자가 현재 main/UI 변경과 대조해 3D 커밋 반영 여부 확인 후 사용자 체험. 실제 데이터 매핑과 실사 자산은 별도 후속 범위.
- 통합(2026-09-27, Claude Code): Antigravity UI-03 B1(`2cda062`, M-14 공정 경로·M-15 BOM 부모-자식 패턴) fast-forward + Codex 1인칭 비전검사 체험(`2a739c2` → cherry-pick `941a50d`). Codex 브랜치는 UI-01 이전 코드 기준이라 `Factory.tsx`·`Factory.css` 충돌 — main 파일을 기준으로 Codex 변경 13가지(체험 상태·진입/나가기·포커스 가둠·툴바·조준점·E 선택·이동 패드·설비 상태/설정 패널 등)를 다시 적용하고 CSS 블록은 원본과 동일함을 확인. 보정 `bf8c8e9`: 1인칭에서 설비 상세가 UI-01 겹침 규칙 때문에 장면과 6px 겹치던 것 → 옆 칸 배치.
  - 검증: typecheck·lint·format·build, vitest 412, 3D 브라우저 13 passed(1인칭 신규 3 포함), 1인칭 1440·390 설비 선택·상세·Esc 해제 직접 확인, M-14·M-15 넓은 패널 1440 한 화면, 공식 스모크 **169 passed**(9.6분, exit 0).
  - 참고: DOC-02는 직전 배포(`a35e895`)에 포함되어 이미 운영에 반영됨(작성 세션의 현황 기록은 '배포 보류'였음).
- 배포(2026-09-27): push `24179d1..ad199c1`, 서버 pull(백엔드 변경 없음, API 재시작 없음) → 프런트 빌드·rsync. 확인: 새 번들 해시 일치·API 5xx 0, 운영 게스트 M-14·M-15 넓은 패널 1440 한 화면, 1인칭 체험 설비 상세 열림, 오류 0(첫 방문은 3D 모델 내려받기 대기 필요).


## 2026-09-27 비전검사 AI 설명·세 시나리오 (FS-3D-AI01, 로컬 구현)

- 브랜치 `codex/vision-ai`, 기준 `origin/main 8851772`. 기존 `codex/home-ui-polish` 작업은 보존하고 통합된 1인칭 코드에서 시작했다.
- 정상/불합격 증가/정지 전환, 상태등·판정 주기·검사 정지 연동, AI 설명 버튼 구현. 확인된 사실 / 원인 가능성 / 다음 확인 항목을 구분한다. 활성 시나리오 재선택은 누계를 보존한다.
- 고정 합성 비교 자료: 정상 2%→2%, 증가 2%→20%(+18%p), 정지 처리량 100→50개. 실시간 애니메이션 누계·실제 검사 이미지·업무 센서값과 구분한다.
- 인증·CSRF가 필요한 읽기 전용 설명 API, 서버 전용 OpenAI Responses 어댑터, 성공 캐시·동시 호출 제한·실패 대기 구현. 키 미설정/공급자 오류는 출처가 표시된 데모 설명으로 대체한다. DB·스키마·업무 데이터 변경 없음.
- 프런트 420개/46파일, typecheck/lint/format/build 통과. 서버 DB 없는 모의 공급자 테스트 13개, Ruff 검사/포맷 통과. 배포 wheel의 시나리오 JSON 포함 확인.
- 실제 OPENAI_API_KEY가 없어 실제 Astra 호출·응답 품질·계정 접근은 미검증. 공용 DB 스모크·Safari·실기기 성능은 미실행. main 병합·push·운영 배포 없음.
- 남은 통합 작업: 커밋 반영 검토 → 공식 스모크 → 백엔드 재시작·프런트 재빌드. 실제 AI를 활성화할 경우 서버 비밀 설정에 키를 추가하고 세 시나리오 응답 확인. 운영 반영 여부와 무관하게 키 없이 데모 체험 가능.
- 설계 `docs/modules/factory/README.md`, 상세 인계·재현 명령 `docs/agent/3D공장_AI설명_FS-3D-AI01.md`. 이번 범위 구현 완료, 운영 통합과 실제 모델 검증은 남음.


### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.


## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.
