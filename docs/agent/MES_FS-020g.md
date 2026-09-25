# FS-020g 완료 보고 — M-01 MES 대시보드 (MES 15/15)

작성일: 2026-09-25 · 브랜치 `fs-020g-mes-dashboard` (Codex FS-019a 통합 브랜치 위) · 작업자 Claude Code

## 범위

MES 마지막 화면. **FS-020 MES 15화면 완료.** MES 진입(`/mes`)을 대시보드로 바꿨다.

## API — `GET /api/v1/mes/dashboard?month=YYYY-MM` (구현: `mes/dashboard.py`)

기본 월은 업무 기준일(`FS_TODAY`, 없으면 오늘 KST)이 속한 달. 월 경계는 Asia/Seoul. 저장하지 않고 조회 시 계산.

| 항목 | 정의 |
|---|---|
| `openOrders` | 발행·진행 지시 수(월 무관) |
| `producedQty` | 그 달 확정된 **마지막 공정** 양품 합계 — 공정별 양품을 합산하지 않는다(FS-006b §5) |
| `goodRate` | 그 달 확정 실적 Σ양품 ÷ Σ산출 × 100(소수 1자리, 전 공정, FS-008a M-01). 실적 없으면 null |
| `receivedPallets` | 그 달 입고 PALLET 수 |
| `pipeline` | 공정별 완료 안 된 LOT의 `running`(실행 중)·`waiting`(다음 시작 대기) |
| `defectReasons` | 그 달 불량 사유별 불량 수 상위 5 |
| `planVsActual` | 그 달 확정 생산계획의 품목별 계획·지시 배정(취소 제외)·최종 양품(완료 LOT) |
| `pending` | 미확정 실적(실행 중 공정) 수, 미패킹 LOT(담을 양품이 남은 LOT) 수 |

설비 가동률은 설비 상태 컬럼이 없어 계산하지 않는다(M-G06 보류) — 화면에 사유를 적었다.

## 화면 — `frontend/src/mes/Dashboard.tsx`

조회 월, 지표 타일 4개, 공정별 진행 현황(가동률 미제공 안내, 공정 실행 링크), 불량 사유 상위(실적 링크), 계획 대비 실적(생산계획 링크), 처리 대기(M-07·M-08 바로가기). FEMS 대시보드의 공통 스타일(`kpi-grid`·`stat-tile`·`dashboard-grid`·`rank-list`)을 그대로 썼다. 도움말 m-01에 지표 정의·가동률 없음·조회 월 추가.

## 테스트

- `backend/tests/test_mes_dashboard.py` **8개** — 대시보드 숫자를 지시·실적·LOT·입고·계획 API로 따로 계산한 값과 맞춘다. 처음 계획 수량을 4주로 가정해 1건 실패 → 시드는 3주라 생산계획 API 합계와 비교하도록 고쳤다.
- `frontend/src/mes/dashboard.test.tsx` **5개**, `master.test.tsx` 진입 화면 갱신. Playwright MES 진입 e2e 갱신(양품률·파이프라인) + 360px.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 326 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 531 passed (9분 35초, `clock_timestamp` 수정 후) · 파이프라인 순서 수정 후 대시보드 8개 재실행 통과 |
| `tools/run_portal_smoke.py` | 76 passed × 3회(수정 후 연속 2회 + 순서 수정 후 1회), 서버 로그 오류 0 |
| tools unittest / db:validate / audit / git diff --check | 통과 |

첫 스모크에서 기존 e2e 1건이 **서버 500**으로 실패했다(지난 스모크 3회는 통과). 원인: `operation_execution` CHECK `ended_at >= started_at` 위반 — 실패 행의 `started_at` 14:05:36.5, `ended_at` 14:05:34.8. PostgreSQL `now()`는 트랜잭션 시작 시각이라, 완료 트랜잭션이 먼저 열리고 공간 잠금을 기다린 뒤 실행되면 종료가 시작보다 앞설 수 있다. **MES 업무 시각을 모두 `clock_timestamp()`(잠금 뒤 실제 시각)로 바꿨다**(실행 시작·종료, 실적 확정, 지시 발행·시작·완료, 버전 게시·폐기, 입고, 자재 투입). 작업지시 `completed_at >= started_at` CHECK도 같은 위험이었다. 재현 테스트는 타이밍 의존이라 두지 않았고, 수정 후 스모크를 연속 2회 돌려 확인했다.

360px 스크린샷에서 공정별 진행이 "조립 → 사출 → 검사"(공정 코드 순)로 보여, 경로 안 가장 앞 순번으로 정렬하도록 고쳤다(테스트 추가).

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## FS-020 MES 종료 요약

| 하위 ID | 화면 | 핵심 |
|---|---|---|
| 020a | M-10~13 기준정보 | 표 명세 공통 CRUD, 품목 기준 단위 잠금, 공간 순환 방지, 공정 허용 설비 |
| 020b | M-14 공정 경로 · M-15 BOM | 초안 → 게시 → 폐기 버전, 게시 불변·개정 |
| 020c | M-02 생산계획 · M-03 작업지시 | 계획 라인 잠금 배정 한도(동시성), 발행 시 LOT |
| 020d | M-04 LOT 현황 · M-05 공정 실행 | TX-01·02, 설비 점유 거부(동시성), all_defective 종결 |
| 020e | M-06 자재 투입 · M-07 실적 확정 | BOM 제안량, 확정 후 투입 금지, NULL LOT 중복 검사 |
| 020f | M-08 패킹 · M-09 완제품 입고 | LOT 먼저 잠금 양품 한도(동시성), PALLET 입고 |
| 020g | M-01 대시보드 | 조회 시 계산 지표·파이프라인 |

남은 사용자 결정·후속: 없음(MES). 판단 기록 — `/work-orders/{id}/lot` 추가(020c), `/finish`를 `/result`로 통합(020d). 다음은 FS-019 ERP 나머지(Codex)와 FS-021 통합 검증.
