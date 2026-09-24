# FS-018h 완료 보고 — F-08 요금 산정

작성일: 2026-09-24 · 브랜치 `fs-018h-billing` (main `dc4071f`) · 작업자 Claude Code

## 범위

`GET /api/v1/fems/billing?from=YYYY-MM&to=YYYY-MM`. 조회 시 계산, 저장하지 않는다(G-04). FEMS 진행 9/14.

## 규칙

- **월 요금 = 기본요금 + 그 달 사용량 × 단가**(각각 원 단위 반올림). 시간대 가중치 없음(FS-008a F-08).
- 사용량: 최상위 계측기만, invalid 제외, 배수 적용(F-01·F-04와 같은 기준).
- **요금제는 월마다 고른다**(`effective_from ≤ 월 ≤ effective_to`, NULL = 계속). 요금제가 바뀌는 달에서 자연히 구간이 나뉘고 구간마다 적용 요금제를 보여 준다. 같은 에너지원 기간 겹침은 F-14가 막는다.
- 상태: `CALCULATED` / `TARIFF_MISSING`(요금제 없는 달이 있음 — 그 달을 뺀 부분 합계) / `NOT_BILLABLE`(`is_billable=false`, 합계 제외).
- 계측이 없는 달은 청구 구간을 만들지 않는다(기본요금만 붙는 빈 달 방지).
- 기간: 기본 전월 ~ 당월(요금제 개정이 바로 보인다). 최대 12개월. 당월은 최근 계측일까지 누계(`monthToDate`).
- **기본요금은 월 단위 전액**이다. 시드 8월은 계측이 08-25부터지만 기본요금 전액을 붙인다. 화면에 명시했다.

시드 결과(8~9월): 전력 8,907,797원(8월 TR-ELEC-01 120원, 9월 TR-ELEC-02 130원), 가스 1,710,000원, 용수 622,800원, 합계 11,240,597원.

## 구조 변경

- F-01 대시보드의 한 달 요금 계산(`_charges`, `tariffs_for_month`, `billable_sources`)을 **삭제하고 F-08의 `_billing`을 쓰게 했다.** 요금 계산 구현이 하나가 됐다. 대시보드 응답 형식은 그대로이며 대시보드 테스트 20개가 수정 없이 통과했다. 두 API 합계 일치를 테스트로 고정했다.
- AG-07(모바일 사이드바)과 충돌을 피하려고 `styles.css`를 수정하지 않았다(기존 클래스만 사용). `FemsLayout.tsx`는 `femsScreens` 한 줄만 추가했다.

## 테스트 (항목별 분리)

- `backend/tests/test_fems_billing.py` **16개**: 기본 기간 / 개정 월 구간 분할 / 구간 금액 공식(SQL 사용량) / 전월은 이전 단가 / 에너지원 합 = 구간 합 / 총합 = 에너지원 합 / 대시보드 요금 = 같은 달 산정 / 요금제 없는 달 / 그 달은 합계 제외 / 비부과 제외 / 계측 없는 달 미청구 / 문자열 / from만 400 / 역순 400 / 12개월 초과 400 / 모듈 꺼짐 409.
- `frontend/src/fems/billing.test.tsx` **11개**: 사이드바 요금 그룹 / 기간 채움 / 조회 월 전달 / 합계 원 표시 / 당월 누계 안내 / 구간별 요금제 / 사용량 × 단가 표시 / 요금제 없음 / 불완전 합계 알림 / 비부과 설명 / 빈 상태.
- Playwright +1(전력 TR-ELEC-01·02 구간) + 360px F-08.

## 실행 검증 (모두 exit 0)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build | 통과 |
| `npm --prefix frontend test` | 180 passed |
| ruff check / format --check | 통과 |
| backend 전체 pytest | 217 passed (8분 6초) |
| `tools/run_portal_smoke.py` | 35 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

360px 스크린샷 확인: 월·요금·요금제 코드가 먼저 보이고 가로 넘침 없음. schema.json·마이그레이션·content·conftest·test_common·test_seed·styles.css 변경 0.

## 남은 것

F-05 생산량 등록 → F-06 원단위 → F-13·F-12·F-09. backend 테스트가 8분을 넘었다 — 세션 범위 템플릿 fixture(conftest, Codex) 제안의 우선순위가 올라갔다.

## AG-07 통합 (같은 브랜치, rebase 후)

AG-07(antigravity/ag-07-sidebar `6f99461`) 위로 이 브랜치를 rebase했다(문서 2개 충돌만, 양쪽 기록 보존). 검토 중 실제 Chromium 153으로 확인한 결함 2건을 여기서 고쳤다.

1. **모바일에서 메뉴가 펼쳐진 채 시작**했다. `<details open>`이 좁은 화면에도 적용돼 원래 문제(본문이 화면 절반 아래)가 첫 진입에서 그대로였다. 링크를 누른 뒤에야 접혔다.
2. **넓은 화면에서 메뉴 링크를 한 번 누르면 사이드바 전체가 사라졌다.** 클릭 시 `details.open=false`가 되는데, 801px 이상에서는 summary를 숨기므로 다시 열 방법이 없었다. CSS의 `details:not([open]) > nav { display: grid }` 덮어쓰기는 브라우저의 닫힌 details 숨김을 이기지 못한다(Chromium에서 재현). jsdom은 레이아웃이 없어 AG-07 테스트가 잡지 못했다.

수정: `window.matchMedia("(max-width: 800px)")`(styles.css 미디어 쿼리와 같은 기준)일 때만 닫는다. 좁은 화면은 그리기 전(`useLayoutEffect`)에 닫힌 상태로 시작하고, 넓은 화면은 절대 닫지 않는다. matchMedia가 없으면 넓은 화면으로 본다. 효과 없는 CSS 덮어쓰기 규칙은 지웠다. 원래 프롬프트에서 제가 "JS 화면 크기 감지 금지 + `<details open>`"을 지시한 것이 원인의 일부다.

- `sidebar.test.tsx`: 닫힘 테스트 2개를 좁은 화면 조건으로 바꾸고, 좁은 화면 접힌 채 시작 / 넓은 화면 펼친 채 시작 / **넓은 화면 링크 클릭 후에도 열림**(회귀 방지) 3개 추가. 전체 frontend 194 passed.
- Playwright: 1280px 메뉴 링크 클릭 후 사이드바 유지, 360px 접힌 채 시작 → 펼쳐 이동 → 다시 접힘. 37 passed. 360px 스크린샷에서 메뉴 한 줄 아래로 본문이 바로 시작함을 확인.
- backend는 rebase 전 검증한 FS-018h와 바이트 동일(diff 0)이라 전체 pytest 217 결과를 유지한다.
