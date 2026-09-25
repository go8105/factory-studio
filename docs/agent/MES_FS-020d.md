# FS-020d 완료 보고 — M-04 LOT 현황 · M-05 공정 실행

작성일: 2026-09-25 · 브랜치 `fs-020d-mes-lot-execution` (main `83c745d`) · 작업자 Claude Code

## 범위

LOT 추적과 공정 시작·완료 트랜잭션(TX-01 시작 / TX-02 완료). FS-020 진행 4/7.

## API — `/api/v1/mes` (구현: `mes/execution.py`)

| 경로 | 동작 |
|---|---|
| `GET /lots` | LOT + 지시·경로 요약, `completedSteps/stepCount`, `finalGoodQty`, `running`(투입 포함), `nextStep`(투입 포함) |
| `GET /lots/{id}` | **추적성 한 응답**: 단계별 실행·설비·시각·실적(투입·양품·불량·사유)·투입 자재 |
| `GET /executions` | 실행 중 공정 |
| `POST /lots/{id}/executions` `{routeStepId, equipmentId}` | TX-01 공정 시작 |
| `POST /executions/{id}/result` `{goodQty, defectQty, defectReason}` | TX-02 공정 완료 = 실적 확정 |

**FS-010의 `/executions/{id}/finish`는 따로 두지 않았다.** 스키마상 실행이 completed가 되려면 확정 실적 1건과 종료 시각이 함께 있어야 한다(CHECK·FS-006 "running→completed: 확정 result 1개와 종료시각 생성"). 결과 없는 종료는 표현할 수 없어 `/result` 하나가 완료다. 시작 경로는 LOT 아래(`/lots/{id}/executions`)에 두었다.

## 규칙 (schema.json SERVICE · FS-006 구현)

- **잠금 순서**: 공간 → 작업지시 → LOT(`FOR UPDATE OF o, t`) → 실행.
- **시작**: 발행·진행 지시의 미완료 LOT만(409 `LOT_NOT_STARTABLE`), 진행 중 단계가 있으면 409 `STEP_RUNNING`, **다음 단계만**(409 `OUT_OF_ORDER` + `nextRouteStepId`), 공정 사용 여부(409 `PROCESS_INACTIVE`), **허용 설비·활성 설비만**(400 `fields.equipmentId`), **같은 설비 미종료 실행 있으면 409 `EQUIPMENT_BUSY` + `lotNo`**(M-G07). 첫 공정이면 지시 released → in_progress(`started_at`), LOT ready → in_progress를 같은 트랜잭션에서.
- **완료**: 투입은 서버가 정한다(첫 공정 = 지시 수량, 이후 = 직전 양품). 양품 + 불량 = 투입, EA 정수, 불량 > 0이면 사유 필수(400). 실적 INSERT + 실행 completed(`ended_at`). **마지막 공정이면 normal, 양품 0이면 후행 공정 없이 all_defective**로 LOT·지시 completed(`completed_at`, `completion_reason`). 이미 완료한 실행 409 `ALREADY_COMPLETED`, 같은 키 재전송은 기존 결과(TX-02 순서: 요청 키 먼저).
- 시각은 서버 `now()`만. 실적은 확정 후 수정·삭제 없음.
- **동시성 테스트**: 같은 설비로 서로 다른 LOT 2건 동시 시작 → 201 한 건, 409 한 건.

## 화면

- `Lots.tsx`(M-04): 상태 필터, LOT 목록(대기·진행·완료·**전량 불량 종결** 배지, 진행 n/m, 최종 양품), 이력 패널(단계별 공정·상태·설비·투입·양품·불량·사유·투입 자재, 전량 불량 뒤 단계는 "투입 없음으로 미실행").
- `Executions.tsx`(M-05): 실행 중 표(실적 확정) + 시작 가능 LOT 표(다음 공정·투입 예정). 시작 폼은 허용·사용 중 설비만, 다른 LOT이 쓰는 설비는 "(사용 중: LT-…)"로 비활성. 실적 폼은 서버 투입·QMS 제외 안내.
- 도움말 m-04(전량 불량 종결 표시), m-05(서버 시각, 실적 확정 = 완료, 허용·활성 설비, 수량 등식) 보강.

## 테스트

- `backend/tests/test_mes_execution.py` **16개**(동시성 1개 포함).
- `frontend/src/mes/execution.test.tsx` **5개**. Playwright +1(대기 LOT 첫 공정 시작 → 실적 확정 → LOT 이력에 불량 사유) + 360px 2화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 287 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 420 passed (7분 8초) |
| `tools/run_portal_smoke.py` | 64 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

첫 스모크에서 새 e2e 1건 실패 → 수정 후 통과("확정" 버튼 선택이 표의 "실적 확정"에도 걸림 → 폼 범위·exact).

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020e M-06 자재 투입 · M-07 실적 확정 화면(BOM 기준 소요량 제안, 재고 차감 없음 안내, LOT 미지정 중복 투입 검사, 확정된 실행에는 투입 추가 금지).
