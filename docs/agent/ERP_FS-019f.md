# FS-019f 완료 보고 — E-11 매입 전표 · E-12 매입채무 · E-13 지급·소명 (ERP 16/18)

작성일: 2026-09-26 · 브랜치 `fs-019f-erp-purchase` (main `55c39c1` FS-019e 위) · 작업자 Claude Code

## 대칭 구조를 코드로도 한 벌로

- **백엔드**: 019e `erp/receipts.py`를 `Side` 설정(RECEIVABLE·PAYABLE)으로 일반화했다. 테이블·키·원천 조인·유효 조건·라벨만 다르고 잠금 순서·양쪽 한도·전체 롤백·물리 삭제+감사·FIFO는 한 코드다. 라우트도 `_settlement_routes` 한 함수로 `/receivables`·`/receipts`와 `/payables`·`/payments`를 등록한다. 019e 테스트 12개가 일반화 뒤에도 그대로 통과했다.
- **프론트**: `erp/settlement.ts`가 두 쪽 API 필드를 공통 모양으로 바꾸고, `Receivables.tsx`·`Receipts.tsx`가 `side` 속성으로 E-09/E-12, E-10/E-13을 함께 그린다. 019e 화면 테스트 8개도 그대로 통과.
- 세액 정책: `revenue.line_amounts`(명세 1줄)로 뽑아 매출(TX-09)과 매입 명세가 같은 함수를 쓴다.

## E-11 매입 전표 (`erp/purchases.py`)

| 항목 | 규칙 (FS-014b·FS-008b) |
|---|---|
| 등록 | 구매발주·입고검수 없이 직접(WMS 범위, 화면 안내). SUPPLIER만, 원재료(raw) 품목만, 단위는 기준 단위 또는 단위환산 원 단위 |
| 금액 | 명세 공급가액·세액은 서버 계산(과세 10%·영세/면세 0%, 명세별 1원 사사오입), 머리글 = 명세 합계 |
| 확정 | 명세 1개 이상, 확정 순간 과세구분으로 재계산. 만기 = 입력 우선 → 매입일 + 결제일수 → NULL. 같은 트랜잭션에서 채무 1건(원금 = 합계, 만기 복사) |
| 취소 | draft는 바로, 확정은 지급 소명 0행만. 세금계산서와 무관. 채무 원금 유지·유효 집계 제외. 막힘 이유는 서버 파생(`cancelBlockedReason`) → 버튼 비활성 + 툴팁 |

## 테스트

- backend `test_erp_purchases.py` **13개**: 시드 상태(취소 매입 채무 제외), 서버 금액 계산, 원재료·단위 검증, 고객 거래처 거부, 확정 → 채무·만기(결제조건 30일), 입력 만기 우선, 빈 전표 확정 거부, 취소 규칙 3종, 작성 중 지급 소명 거부, 채무 한도(전표번호 명시), **동시성 주입**(두 지급 병렬 → 201·409), 취소 매입 채무 소명 거부, FIFO·소명 취소 감사.
- frontend `erp/purchases.test.tsx` **6개**. Playwright: 매입 전표 작성 → 확정 → 매입채무 생성 흐름 + 360px 3화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 통과, **381 passed** |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | **607 passed** (10분 32초) |
| `tools/run_portal_smoke.py` | **100 passed** (3.7분) |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 통과 |

360px 스크린샷(E-11·E-12·E-13) 직접 확인. schema.json·마이그레이션·conftest·test_common·test_seed 변경 0. 새 의존성 0.

## 다음

FS-019g E-14 분개 미리보기(4거래 유형·7계정·10규칙, 소명 1행당 1세트, 저장 금지, 미소명 잔여는 표 밖) → FS-019h E-01 대시보드.
