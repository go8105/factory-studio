# FS-019h 완료 보고 — E-01 ERP 대시보드 · **ERP 18/18 (FS-019 종료)**

작성일: 2026-09-26 · 브랜치 `fs-019h-erp-dashboard` (main `49a291d` FS-019g 위) · 작업자 Claude Code

## API — `GET /api/v1/erp/dashboard?month=YYYY-MM` (구현 `erp/dashboard.py`)

앞 화면의 계산을 **다시 구현하지 않고 가져다 쓴다**: 미수금·미지급 = `receipts.open_items`(E-09·E-12), 수주잔 = `sales._orders`의 진행률(E-04), 미소명 수금 = `receipts._monies`(E-10).

| 항목 | 정의 |
|---|---|
| 당월 매출 | 그 달(Asia/Seoul) 인식된 유효 매출의 공급가액·합계·건수 |
| 미수금·미지급 | 유효 채권·채무 잔액 합(월 무관) |
| 수주잔 | 취소 안 된 수주 명세 (수주 − 출하) × 단가, 원 반올림 |
| 월별 매출 | 조회 월까지 6개월 공급가액 |
| 미수 상위 | 거래처별 잔액 상위 5 |
| 만기별 미수 | 연체 / 미도래 / **미설정(만기 NULL, 연체로 보지 않음 — E-G02)** |
| 계획 대비 실적 | 그 달 확정 판매계획 수량 vs 그 달 유효 매출의 출하 수량(품목별) |
| 처리 대기 | 발급완료가 아닌 매출(0원 제외) 수, 미소명 잔여가 있는 확정 수금 수 |

## 화면

- `Dashboard.tsx`: 조회 월, 지표 타일 4개, 월별 매출(네이티브 `<meter>` 막대), 미수 상위·만기별, 계획 대비 실적, 처리 대기(E-08·E-10 링크). FEMS·MES 대시보드 스타일(`kpi-grid`·`stat-tile`·`dashboard-grid`·`rank-list`) 그대로.
- ERP 진입 `/erp` → `/erp/dashboard`, 사이드바 "개요" 그룹. 도움말 e-01에 지표 정의 반영.

## 테스트

- backend `test_erp_dashboard.py` **8개** — 대시보드 숫자를 채권·채무·매출·수주·판매계획·수금 API로 따로 계산한 값과 맞춘다(만기 그룹 합 = 미수금, 미설정 그룹 = 만기 없는 채권 잔액 합 등).
- frontend `erp/dashboard.test.tsx` **5개**. Playwright: ERP 진입 → 대시보드 → 처리 대기에서 세금계산서 이동 + 360px.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 통과, **389 passed** |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | **622 passed** (11분 40초) |
| `tools/run_portal_smoke.py` | 1차 1 failed(새 e2e 선택자 중복) → 수정 → 2차 1 failed(기존 FEMS e2e 타이밍) → 수정 → **3차 104 passed** |
| tools unittest / db:validate / audit_schema_isolation / git diff --check | 통과 |

- 1차: 새 대시보드 e2e의 `region "미수금"`이 "거래처별 미수금 상위"와 겹쳐 strict 위반 → `exact: true`.
- 2차: `fems.spec.ts` "결측 구간" 테스트가 첫 로드 전에 기간을 입력해 서버 기본 기간이 덮어씀(계획서 §7-8 함정, backend 테스트와 동시 실행 부하에서 드러남). 첫 로드(시작일 값)를 기다리도록 고쳤다.

360px 스크린샷(E-01) 직접 확인. schema.json·마이그레이션·conftest·test_common·test_seed 변경 0. 새 의존성 0.

## FS-019 ERP 종료 요약

| 하위 ID | 화면 | 핵심 |
|---|---|---|
| 019a | E-15~18 기준정보 | 거래처·품목·단가(구간 겹침 거부)·계정/분개규칙 읽기 (Codex) |
| 019b | E-02~04 견적·판매계획·수주 | 개정 이력(최신 파생), 거래처 단가 복사, 수주 전환, 출하지시 후 불변 |
| 019c | E-05~06 출하지시·출하 | TX-07 배정 한도(동시성), TX-08 전량 출하 + TX-09 매출·채권 |
| 019d | E-07~08 매출·세금계산서 | 취소 막힘 이유 파생, 발급대기 삭제, **0원 발급 금지(E-G07)** |
| 019e | E-09~10 채권·수금 | 잔액 조회 파생, 7단계 잠금·양쪽 한도(동시성 2종), 소명 취소 감사 |
| 019f | E-11~13 매입·채무·지급 | 019e를 `Side`로 일반화해 대칭 재사용 |
| 019g | E-14 분개 미리보기 | 소명 1행 = 1세트, 저장 없음, 공통 패널 |
| 019h | E-01 대시보드 | 앞 화면 계산 재사용, 만기 미설정 그룹 |

## 다음

FS-021 통합 검증(SERVICE 정책 7건·동시성·AC 실행) → FS-022 배포.
