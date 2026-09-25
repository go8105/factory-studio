# FS-020e 완료 보고 — M-06 자재 투입 · M-07 실적 확정

작성일: 2026-09-25 · 브랜치 `fs-020e-mes-material-result` (main `2a0717e` = FS-020d) · 작업자 Claude Code

## 범위

생산실행 마지막 두 화면. FS-020 진행 5/7(생산실행 M-04~M-07 완료).

## API — `/api/v1/mes` (구현: `mes/execution.py`)

| 경로 | 동작 |
|---|---|
| `GET /executions/{id}/bom-requirement` | 지시에 고정된 BOM의 기준 소요량. **BOM 없는 지시는 빈 배열**(FS-010 §9) |
| `GET /executions/{id}/material-issues` | 이 실행의 투입 기록 |
| `POST /executions/{id}/material-issues` `{materialItemId, materialLotId?, issuedQty, unit}` | 투입 기록 |
| `DELETE /executions/{id}/material-issues/{issueId}` | 투입 기록 삭제(정정용, 실적 확정 전만) |
| `GET /results` | 확정된 실적 전체(LOT·공정·설비·수량·사유) |

실적 확정은 FS-020d의 `POST /executions/{id}/result`를 그대로 쓴다(M-05·M-07 공통 폼 `ResultForm.tsx`).

## 규칙 (schema.json SERVICE 구현)

- **기준 소요 = LOT 계획 수량 × 1개당 소요량 × (1 + 손실률%)**, EA는 올림 정수·그 밖은 소수 3자리(시드 생성 규칙과 같음). **제안량 = 기준 소요 − 같은 LOT에서 이미 투입한 양**(0 미만이면 0). BOM 라인에 공정 구분이 없어(1단계 전개) 모든 자재를 보여 주고, 사출에서 수지를 넣었으면 조립 단계에서 수지 제안량은 0이 된다.
- **실적 확정 전 실행만** 투입 추가·삭제(409 `RESULT_CONFIRMED`). 잠금 순서 공간 → 지시 → LOT → 실행.
- **LOT 미지정(NULL) 중복 검사**: 같은 실행·자재·자재 LOT(NULL 포함, `IS NOT DISTINCT FROM`)이 있으면 409 `DUPLICATE_ISSUE`.
- 단위는 자재 기준 단위 또는 환산 단위(400 `fields.unit`), 수량 > 0.
- 자재 LOT은 **같은 품목으로 생산이 끝난 LOT**만(400 `fields.materialLotId`).
- `bom_version_id`는 BOM에 있는 자재일 때만 지시의 BOM 버전을 남긴다(이론 소요량 비교 근거), 아니면 NULL.
- **재고를 차감하지 않는다**(WMS 소유). 응답 플래그 없이 화면 고정 안내(FS-010 §9).

## 화면

- `Materials.tsx`(M-06): WMS 안내, 실행 중 공정 선택 → BOM 기준 소요량 표(기준·손실률·LOT 누적·제안, "제안량 채우기" / "투입 완료"), 이 공정 투입 기록(삭제 2단계), 투입 폼(자재·수량·단위(기준+환산)·자재 LOT 선택). BOM 없으면 직접 입력 안내.
- `Results.tsx`(M-07): QMS 제외 안내, 확정을 기다리는 공정 + `ResultForm`, 확정된 실적 표(전량 불량 배지, 불량률·사유, "불량이 있는 실적만" 필터).
- `ResultForm.tsx`: M-05에서 분리한 공통 실적 폼.
- 도움말 m-06(제안량 계산·중복·단위·자재 LOT), m-07(서버 투입, 확정 = 공정 완료, 전량 불량 종결) 보강.

## 테스트

- `backend/tests/test_mes_material_result.py` **12개**. 처음에는 시드의 실행 중 조립 공정에 투입 기록이 없다고 가정해 4건 실패 → 시드에는 수지·핀 투입이 이미 있어, 대기 LOT의 첫 공정을 새로 시작한 실행으로 테스트를 바꿨다.
- `frontend/src/mes/materials.test.tsx` **7개**. Playwright +1(새 공정 시작 → 수지 제안량 투입 → "투입 완료") + 360px 2화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 294 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 432 passed (7분 21초) |
| `tools/run_portal_smoke.py` | 67 passed |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020f M-08 패킹 · M-09 완제품 입고(TX-10·TX-11: BOX → PALLET, Σ포장 ≤ LOT 양품, 입고 후 구성 불변).
