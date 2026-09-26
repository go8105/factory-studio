# FS-019g 완료 보고 — E-14 분개 미리보기 (ERP 17/18)

작성일: 2026-09-26 · 브랜치 `fs-019g-erp-journal` (FS-019f 브랜치 위, 019f CI 통과 후 main ff) · 작업자 Claude Code

## API — `GET /api/v1/erp/journal-preview` (구현 `erp/journal.py`)

- 4거래 유형 × 분개 규칙(E-18, 시드 7계정·10규칙)을 **조회 때마다 계산**한다. 결과·전표·원장 저장 없음, POST 없음(요청 결과 행도 늘지 않음을 테스트로 확인).
- SALES(매출 1건, `sourceId`) · PURCHASE(확정 매입 1건, `sourceId`) · RECEIPT/PAYMENT(**소명 1행 = 분개 1세트**, `applyId`).
- 금액 기준 TOTAL·SUPPLY·TAX = 원천 금액, APPLY = 소명액. 수금·지급 원액은 분개하지 않는다.
- 미소명 잔여는 `unapplied`로 따로 주고 분개 라인에 넣지 않는다(선수금·선급금 계정 없음).
- 취소 매출, 작성 중·취소 매입은 409 `NOT_POSTABLE`.

## 화면

- `Journal.tsx`: 독립 화면 E-14(거래 유형·대상 선택) + **공통 패널 `JournalPanel`**. E-07 매출(유효 매출), E-11 매입(확정), E-10 수금·E-13 지급(소명 행)의 "분개" 버튼이 같은 패널을 연다.
- 차변/대변 표, 차대 합계, 미소명 잔여 표 밖 안내, "전표 확정·총계정원장·결산은 1차 범위 제외" 안내.
- 도움말 e-14에 계산 기준·공통 패널 진입·막히는 경우 추가.

## 테스트

- backend `test_erp_journal.py` **7개**: 매출·매입·수금·지급 규칙별 금액을 원천 API 값과 대조, 수금 미소명 잔여가 표 밖, 작성 매입·취소 매출 거부, 필수 id·타 공간 404, 저장 없음.
- frontend `erp/journal.test.tsx` **3개**. Playwright: 매출 분개 보기 → 차대 합계 일치 + 360px.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 통과, **384 passed** |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | **614 passed** (10분 43초) |
| `tools/run_portal_smoke.py` | **102 passed** (3.8분) |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 통과 |

360px 스크린샷(E-14) 직접 확인. schema.json·마이그레이션·conftest·test_common·test_seed 변경 0. 새 의존성 0.

## 다음

FS-019h E-01 ERP 대시보드 — 앞 화면 계산 재사용(`receipts.open_items`, 매출·매입 목록), 만기 NULL은 "미설정" 그룹(E-G02), 다른 화면 값과 일치 테스트. ERP 18/18.
