# Antigravity 작업 지시서 — UI-02 공통 패턴 반복 적용

작성: 2026-09-27 (Claude Code)
읽을 것(순서대로): [공통 UI 규약](../ui/공통UI규약_UI-02.md) → [전체 메뉴 적용표](../ui/메뉴적용표_UI-02.md) → 기준 화면 코드 3개(`frontend/src/fems/Dashboard.tsx`·`Readings.tsx`·`Production.tsx`)

> 이 문서는 사용자가 Antigravity에게 작업을 맡길 때 전달하는 지시서다. Claude는 Antigravity에게 직접 메시지를 보내거나 작업을 시작시키지 않는다.

## 1. 시작 조건

- **기준 커밋: `0875482`** (`UI-02: 공통 앱 레이아웃·목록 채움·FormPanel 확정…`). 사용자 검토 후 main에 병합된 다음 시작한다. `git merge-base --is-ancestor 0875482 main`이 참인지 먼저 확인한다.
- 작업 위치: `/Users/hwang-kyoungho/projects/factory-studio-ag`(antigravity worktree). 메인 폴더와 `factory-studio-codex`는 열지 않는다.
- 브랜치: 묶음마다 새 main에서 `antigravity/ui02-<묶음 번호>`로 만든다. 예: `git switch -c antigravity/ui02-a1 main`
- 원격 push·main 병합은 하지 않는다. 묶음이 끝나면 커밋하고 사용자 리뷰를 기다린다(AGENTS.md 8장).

## 2. 모든 묶음에 공통인 규칙

### 수정할 수 있는 파일

- 적용표에서 그 묶음에 적힌 **화면 파일**과 **그 화면의 테스트 파일**(`*.test.tsx`)
- `frontend/e2e/layout.spec.ts`에 그 화면의 레이아웃 검사를 **추가**하는 것
- 문서: `docs/ui/메뉴적용표_UI-02.md`의 상태 열, `docs/progress.md`, `docs/agent/HANDOFF.md`

### 수정하면 안 되는 파일

- `frontend/src/shared/styles.css`, `components.tsx`, `SolutionLayout.tsx`, `hooks.tsx`, `app/App.tsx` — **공통 구현은 Claude 담당**
- 기준 화면 3개(`fems/Dashboard.tsx`·`Readings.tsx`·`Production.tsx`)
- backend 전체, 마이그레이션, `schema.json`, `test_common.py`·`test_seed.py`·`conftest.py`

### 해야 할 것

- 공통 컴포넌트와 공통 클래스만 쓴다: `PageTitle(actions)`, `.page-fill`, `.fill`, `.filter-bar`, `DataTable(leading)`, `split-view`, `FormPanel`, `useDiscardGuard`, `DateRange`, `.field-row`, `EmptyState(onAction)`, `ErrorNotice`, `Badge`.
- 화면에 `style={{…}}`·새 CSS 파일·새 클래스·`!important`를 추가하지 않는다. 기준 화면 코드를 복사해 따로 관리하지 않는다(구조만 따른다).
- **공통 컴포넌트에 기능이 모자라면 화면에서 우회하지 말고 멈춘다.** 필요한 확장(무엇이, 어느 화면에서, 왜)을 HANDOFF에 적고 그 화면은 "Claude 선행"으로 바꾼다.

### 보존할 것 (바꾸면 결함)

- API 경로·요청 본문·쿼리 파라미터, 멱등 키·CSRF 처리(`useApiSend`·`MutationKeys`)
- 입력 검증(`required`·`pattern`·`maxLength`)과 서버 오류 표시(필드 오류는 입력 아래)
- 확정·게시 불변, 정정=새 버전, 삭제 2단계(삭제 → 삭제 확정), 권한에 따른 버튼 표시
- 테스트가 찾는 접근성 이름(버튼 글자·라벨·`aria-label`). 이름이 바뀌어야 하면 테스트를 함께 고치고 이유를 커밋에 적는다.

### master-grid → FormPanel 옮기는 순서 (S 패턴)

1. 루트 `<>…</>`를 `<div className="page-fill">…</div>`로 바꾼다.
2. 폼의 제목(`<h2>` "○○ 등록")에 있던 행동을 `PageTitle`의 `actions` 버튼으로 옮긴다. 버튼 글자는 기존 제목과 같게("○○ 등록").
3. `<div className="master-grid">` → `<div className="split-view fill">`, 목록 `<section>` → `<section className="fill">`.
4. 항상 보이던 `<form className="panel">`을 `{panel && <FormPanel …>}`로 바꾼다. 상태: `panel`(닫힘/새 등록/수정 행), `initial`(열 때 값), `dirty`, `useDiscardGuard(dirty)`.
5. 행의 "수정" 버튼은 `guard.guard(() => openPanel(row))`. 저장 성공 시 패널을 닫고 `role="status"`로 결과를 알린다.
6. `RevealAnchor`는 지운다(패널이 대신한다).
7. 폼 안 저장·취소 버튼은 `FormPanel`의 `actions`로 옮긴다. 저장 오류는 패널 안 `ErrorNotice`.
8. 짧은 두 입력(시작일·종료일, 수량·단위, 코드·이름)은 `.field-row`로 한 줄에 둔다.

### 검증 명령 (묶음마다 전부 실행, 결과를 HANDOFF에 기록)

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-ag
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test
git diff --check
# 브라우저: 8000·5173이 비어 있을 때만(다른 작업자와 동시 실행 금지). 사용자 승인 후 실행.
uv run --project backend --env-file .env python tools/run_portal_smoke.py
```

### 완료 기준 (묶음마다)

- **공식 스모크를 반드시 실행한다**(UI-02 검토에서 단위 테스트만 통과한 묶음이 스모크 11건 실패). e2e 기본 뷰포트 1280px은 패널 겹침 모드 — 패널에 필요한 버튼·표가 가려지지 않는지 본다.

- 1440×900·1366×768에서 L/S 화면의 문서 높이 ≤ 뷰포트(내용이 더 크면 문서 스크롤로 넘쳐도 되지만 잘리면 안 됨). 표를 스크롤해도 조건·머리글·페이지 이동이 보인다.
- S 화면: 1440에서 패널이 겹쳐 열리고 Esc로 닫혀 연 버튼으로 포커스가 돌아온다. 1600에서 목록 옆에 붙는다. 390에서 전체 화면이고 저장 버튼이 보인다. 변경 후 닫으면 확인을 묻는다.
- 360px에서 가로 스크롤 없음(`e2e/portal.spec.ts`의 기존 검사).
- 기존 단위 테스트·e2e 통과, 새로 옮긴 화면마다 `layout.spec.ts`에 최소 1개 검사 추가.
- 적용표 상태를 "완료(antigravity, 커밋)"로 바꾸고 HANDOFF에 브랜치·커밋·검증 결과·남은 문제를 적는다.

## 3. 작업 묶음

순서대로 진행한다. 한 묶음이 리뷰를 통과한 뒤 다음 묶음을 시작한다.

### A1 — 대시보드 조회 월 위치 (작음, 패턴 익히기)

| 대상 | 파일 |
|---|---|
| M-01 생산 개요 | `frontend/src/mes/Dashboard.tsx`, `mes/dashboard.test.tsx`(있으면) |
| E-01 경영 개요 | `frontend/src/erp/Dashboard.tsx`, 해당 테스트 |

- 할 일: 별도 `filter-bar`의 조회 월을 `PageTitle`의 `actions`로 옮긴다(F-01과 같은 마크업). 하단은 이미 2×2다 — 카드 순서·내용은 그대로.
- 주요 차트가 있는 대시보드가 아니므로 `has-lead`를 쓰지 않는다.
- 보존: 조회 월 변경 시 요청 파라미터, KPI 문구.

### A2 — 조회 목록 (L)

| 대상 | 파일 |
|---|---|
| M-09 완제품 입고 | `mes/Receipts.tsx` |
| E-07 매출 | `erp/SalesRecords.tsx` |
| E-14 분개 미리보기 | `erp/Journal.tsx` |
| P-07 운영 기록 | `portal/Records.tsx` |

- 할 일: 루트 `.page-fill`, 조건은 `.filter-bar`, 탭(보기 전환)이 있으면 `DataTable`의 `leading`으로.
- P-07은 ADMIN 전용 — 권한 분기를 건드리지 않는다.

### A3 — 보고서형 조회 (R)

| 대상 | 파일 |
|---|---|
| F-03 설비별 배분 | `fems/Allocations.tsx` |
| F-04 배출량 현황 | `fems/Emissions.tsx` |
| F-06 원단위 분석 | `fems/Intensity.tsx` |
| F-07 목표 대비 실적 | `fems/Targets.tsx` |
| F-08 요금 산정 | `fems/Billing.tsx` |
| E-09·E-12 매출채권·매입채무 현황 | `erp/Receivables.tsx`(두 화면 공용) |

- 할 일: `.page-fill`을 쓰지 **않는다**(합계·근거·표가 함께 있어 문서 스크롤이 맞다). 제목 줄·조건 줄·숫자 열(`th/td.num`)·배지 글자·긴 설명(`wrap`)만 규약에 맞춘다. 기간 표시는 `DateRange`.
- 보존: 합계 계산 표시, 계산 근거 펼침(`basis-panel`), 결측 제외 문구.

### A4 — FEMS 기준정보 (S)

| 대상 | 파일 |
|---|---|
| F-09 사업장·공간 | `fems/Sites.tsx` — 두 목록. 목록마다 등록 버튼을 섹션 머리에 두고 같은 `FormPanel`을 연다(동시에 하나만) |
| F-10 설비 | `fems/Equipments.tsx` |
| F-11 에너지원 | `fems/EnergySources.tsx` — `e2e/fems.spec.ts` "에너지원 등록 후 목록에 표시"를 패널 흐름으로 고친다 |
| F-13 환산·배출계수 | `fems/Factors.tsx` — PRIMARY/EMISSION 탭 유지 |
| F-14 요금제 | `fems/Tariffs.tsx` |

### A5 — MES 기준정보·계획 (S)

| 대상 | 파일 |
|---|---|
| M-02 생산계획 | `mes/Plans.tsx` |
| M-03 작업지시 | `mes/Orders.tsx` — 발행·LOT 생성 행 버튼 유지 |
| M-06 자재 투입 | `mes/Materials.tsx` |
| M-08 패킹 | `mes/Packing.tsx` — 두 목록(담을 수 있는 LOT·포장 목록) |
| M-10 사업장·공간 | `mes/Sites.tsx` — F-09와 같은 방식 |
| M-11 설비 · M-12 품목 · M-13 공정 | `mes/Equipments.tsx`·`mes/Items.tsx`·`mes/Processes.tsx` |

- `e2e/mes.spec.ts`의 등록 흐름을 패널 흐름으로 고친다.

### A6 — ERP (S)

| 대상 | 파일 |
|---|---|
| E-15~18 거래처·품목·단가·계정 | `erp/Master.tsx`(네 화면 공용) — 먼저 한다 |
| E-03 판매계획 | `erp/SalesPlans.tsx` |
| E-05 출하지시 · E-06 출하 | `erp/ShipmentOrders.tsx`·`erp/Shipments.tsx` |
| E-08 세금계산서 | `erp/TaxInvoices.tsx` — 0원 매출 409 안내 유지 |
| E-10·E-13 수금·지급 등록·소명 | `erp/Receipts.tsx`(공용) — 소명 입력도 같은 패널 |
| E-11 매입 전표 | `erp/PurchaseInvoices.tsx` — 등록·취소 두 패널을 `FormPanel` 하나로(취소 사유 확인 유지) |

- `erp/common.tsx`는 ERP 전용 공통이다. 여기 바꿀 것이 생기면 멈추고 Claude에게 넘긴다.

## 3-2. UI-03 묶음 (예외 패턴 적용, 2026-09-27 추가)

기준 커밋: UI-03 main 통합 커밋(`git log --grep "UI-03:" -1`). 규약 8장과 기준 화면 코드를 먼저 읽는다. 완료 기준은 위와 같고 **공식 스모크 필수**.

### B1 — 부모-자식 상세 (F-12 `fems/Meters.tsx`를 따른다)

| 대상 | 파일 | 주의 |
|---|---|---|
| M-14 공정 경로 | `mes/Routes.tsx` | 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼. 게시한 버전은 수정·삭제 버튼 없음(개정=새 버전), '개정'·'게시' 동작 유지. `e2e/mes.spec.ts` "공정 경로를 개정해…" 흐름 갱신 |
| M-15 BOM | `mes/Boms.tsx` | BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼. `RevealAnchor` 제거 |

### B2 — 넓은 행 편집 (E-04 `erp/SalesOrders.tsx`를 따른다)

| 대상 | 파일 | 주의 |
|---|---|---|
| E-02 견적 | `erp/Quotations.tsx` | 등록 `FormPanel wide`('견적 만들기'), 상세 `DetailPanel wide`('견적 상세' 대신 `${견적번호} ${차수}차` 제목), 라인 편집·확정·제출·**수주 전환 폼은 상세 패널 안**(패널 자체는 폼이 아니므로 안에 `<form>`을 둘 수 있다). `e2e/portal.spec.ts` "ERP 견적 작성 → 확정 → 제출 → 수주 전환" 갱신 |

## 4. 이번 지시에 포함하지 않는 화면 (Claude 선행)

없음 — UI-03에서 F-12·M-04·M-05·M-07·E-04를 Claude가 완료했고, M-14·M-15·E-02는 위 3-2 묶음이다.

## 5. 인계 형식

묶음을 마치면 HANDOFF에 다음을 남긴다.

```
## Antigravity — UI-02 <묶음> (날짜)
- 브랜치 / 기준 커밋 / 마지막 커밋
- 옮긴 화면: F-xx …
- 검증: typecheck·lint·format·build·test(개수)·diff --check 결과, 스모크(실행 여부·결과)
- 공통 컴포넌트 확장 요청: (없음 / 내용)
- 남은 문제
```
