# FS-020c 완료 보고 — M-02 생산계획 · M-03 작업지시

작성일: 2026-09-25 · 브랜치 `fs-020c-mes-plan-order` (main `0f68b53`) · 작업자 Claude Code

## 범위

MES 첫 트랜잭션 화면. 계획 → 지시 → LOT. FS-020 진행 3/7. MES 진입(`/mes`)을 생산계획으로 바꿨다(M-01 대시보드 전까지).

## API — `/api/v1/mes` (구현: `mes/planning.py`)

| 경로 | 동작 |
|---|---|
| `GET /production-plans` | 계획 + 라인. 라인마다 `allocatedQty`(취소 아닌 지시 합계, draft 포함)·`remainingQty` |
| `POST` · `PATCH /{id}` · `DELETE /{id}` | 계획 헤더(초안만 수정·삭제). `salesPlanCode`는 선택 문자열, 빈 값은 NULL |
| `PUT /production-plans/{id}/lines` `{lines}` | 초안 라인 통째 교체. 단위는 품목 기준 단위(서버) |
| `POST /production-plans/{id}/confirm` | draft → confirmed, 라인 없으면 409 `EMPTY_PLAN` |
| `GET /work-orders` | 지시 + LOT(`lotId`·`lotNo`·`lotStatus`) |
| `POST /work-orders` | 확정 계획 라인에서 draft 지시. 번호 `WO-NNNN` 자동 |
| `PATCH /work-orders/{id}` | draft만. 경로·BOM·수량·기간(계획 라인·품목은 고정) |
| `POST /work-orders/{id}/release` | draft → released + **LOT 생성**(`LT-NNNN`, ready) 같은 트랜잭션 |
| `POST /work-orders/{id}/cancel` `{cancelReason}` | draft만, 사유 필수 |
| `POST /work-orders/{id}/lot` | **추가**: 발행됐지만 LOT이 없는 지시의 LOT 생성(아래 판단) |

## 규칙 (schema.json SERVICE · FS-006/006b 구현)

- **배정 한도**: 공간 잠금 → **계획 라인 `FOR UPDATE`** → 취소 아닌 지시 합계(수정 시 자신 제외) + 요청 수량 ≤ 계획 수량. 넘으면 409 `PLAN_QTY_EXCEEDED` + `planQty`·`allocatedQty`·`remainingQty`. **동시 요청 테스트**: 잔여 60%씩 두 건 동시 → 한 건 201, 한 건 409.
- 확정 계획 라인에서만 지시(400 `fields.productionPlanLineId`). 확정 계획은 헤더·라인·삭제 모두 409 `PLAN_CONFIRMED`.
- 경로·BOM은 **지시 품목의 게시 버전만**(400). 발행 때 다시 확인해 그사이 폐기됐으면 409 `VERSION_NOT_PUBLISHED`. BOM은 선택(M-G05), 발행 시점 버전이 지시에 고정된다.
- 수량 > 0, EA는 정수, 종료일 ≥ 시작일. 계획 라인도 같은 품목·주차 중복 금지, EA 정수.
- 발행 이후 수정·취소·재발행 409 `ORDER_RELEASED`(FS-006: released 이후 취소 미지원). 초안 삭제는 두지 않았다 — 취소는 사유와 이력을 남긴다(FS-006).
- 1지시 : 1LOT(UK, M-G04). 진행·완료 전이는 FS-020d 공정 실행.
- 판매계획 확정 여부는 검사하지 않는다(FS-014: ERP 판매계획은 선택 코드, 독립 솔루션). FS-006a §3의 `confirmed_at`은 스키마에 컬럼이 없어 기록하지 않는다.
- audit_event는 FEMS와 같이 남기지 않는다(FS-021 판단).

## 판단이 필요할 수 있는 것

- **`POST /work-orders/{id}/lot` 추가.** FS-008a M-03은 "발행 시 LOT 생성", FS-010 표에는 release·cancel만 있다. 그런데 시드에 발행됐지만 LOT이 없는 지시 3건(N01~N03)이 있고, FS-006은 "발행 후 LOT 생성 전도 미종결 업무"로 이 상태를 인정한다. 이 지시들은 LOT 없이는 공정을 시작할 수 없어 막히므로, 그 상태에서만 LOT을 만드는 작업을 추가했다. 새 발행은 여전히 발행과 동시에 LOT을 만든다.

## 화면

- `Plans.tsx`(M-02): 계획 목록(라인·확정·삭제), 새 계획(판매계획 코드 선택·수기 안내), 확정 계획 라인 표(계획·지시 배정·잔여·"지시 만들기" 링크 `/mes/work-orders?line=`), 초안 라인 편집.
- `Orders.tsx`(M-03): 상태 필터, 지시 목록(상태별 발행·수정·취소 / LOT 생성), 등록·수정 폼(잔여 있는 확정 라인, 게시 경로·BOM만, 링크로 온 라인과 잔여 수량 기본값), 취소 사유 폼.
- 도움말 m-02(중복·정수·빈 계획), m-03(발행 후 잠금·폐기 재확인·LOT 생성) 보강.

## 테스트

- `backend/tests/test_mes_plan_order.py` **20개**(동시성 1개 포함).
- `frontend/src/mes/planning.test.tsx` **8개**, `master.test.tsx` 진입 화면 갱신. Playwright +1(계획 라인 → 지시 등록 → 발행 → LT-0027) + 360px 2화면, MES 진입 e2e 갱신.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test (2회) | 282 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 404 passed (6분 47초) |
| `tools/run_portal_smoke.py` | 61 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

첫 실행에서 테스트 선택자 2건 실패 → 수정 후 통과: e2e 제목 선택(사이드바 그룹 "생산계획" h2와 겹침 → `level: 1`), 단위 테스트 1건이 목록 로드 전 폼을 찾음(→ `findByRole`).

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020d M-04 LOT 현황 · M-05 공정 실행(TX-01 시작 / TX-02 완료, 같은 설비 미종료 실행 거부 M-G07, 선행 양품·경로 순서).
