# FS-020f 완료 보고 — M-08 패킹 · M-09 완제품 입고

작성일: 2026-09-25 · 브랜치 `fs-020f-mes-packing` (main `6bcbe1e` = FS-020e) · 작업자 Claude Code

## 범위

포장·입고(TX-10·TX-11, FS-006b §6). FS-020 진행 6/7 — 남은 것은 M-01 대시보드.

## API — `/api/v1/mes` (구현: `mes/packing.py`)

| 경로 | 동작 |
|---|---|
| `GET /packable-lots` | 정상 완료 LOT 중 담을 양품이 남은 것(`finalGoodQty`·`packedQty`·`remainingQty`) |
| `GET /packing-units` | 포장 전체 + `members`·`childIds`·`itemId`·`totalQty`·`displayStatus` |
| `POST /packing-units` `{packingKind}` · `DELETE /packing-units/{id}` | 열린 포장 생성(`BX-`/`PL-` 자동 번호) · 비어 있는 열린 포장만 삭제 |
| `PUT /packing-units/{id}/members` `{lotId, packedQty}` | 열린 BOX에 담기·수량 변경, 0이면 빼기 |
| `POST /packing-units/{id}/close` | BOX: 비어 있지 않을 때 / PALLET: BOX가 있고 모두 닫혔을 때 |
| `PUT /packing-units/{id}/parent` `{parentPackingUnitId}` | 닫힌 BOX를 열린 PALLET에 묶기, null이면 풀기 |
| `GET` · `POST /finished-goods-receipts` `{packingUnitId}` | TX-11 PALLET 입고 |

## 규칙

- **잠금**: 공간 → LOT → PALLET(id 순) → BOX(id 순). 담기는 **LOT을 먼저 잠가** 잔여 계산 근거를 고정한다(TX-10).
- **양품 한도(M-G08)**: LOT의 포장 합계(이 BOX 기존 수량 제외 후 재합산) ≤ 최종 양품 → 409 `EXCEEDS_GOOD_QTY` + `availableQty`. **동시성 테스트**: 같은 LOT을 두 BOX에 60%씩 동시 → 한 건만 성공.
- 정상 완료 LOT만(전량 불량·미완료 400 `fields.lotId`), EA 정수, LOT은 BOX에만(409 `NOT_A_BOX`), 한 BOX·PALLET에 같은 품목·단위만(409 `MIXED_ITEM`).
- 닫힌 BOX 내용·닫힌 PALLET 구성 변경 409 `UNIT_CLOSED`, 빈 포장 닫기 409 `UNIT_EMPTY`, 열린 BOX 편입 409 `BOX_NOT_CLOSED`, 열린 BOX가 있는 PALLET 닫기·입고 409 `BOX_OPEN`.
- **입고**: PALLET만(409 `NOT_A_PALLET`), 닫힌 것만(열림 409 `UNIT_OPEN`, 재입고 409 `ALREADY_RECEIVED`). PALLET closed → received + 입고 행. **하위 BOX는 closed로 두고** `displayStatus`로 부모 상태를 보여 준다(FS-006b). 입고 취소·해체는 첫 공개 범위 밖.
- 참고: 시드는 입고·출하 PALLET의 하위 BOX 상태를 received/shipped로 넣어 두었다(FS-006b와 다름). 시드는 바꾸지 않았고, 새로 입고하는 BOX는 설계대로 closed다. `displayStatus`로 두 경우 모두 같게 보인다.

## 화면

- `Packing.tsx`(M-08): 담을 수 있는 LOT 표, 포장 목록(종류 필터, 새 BOX·새 PALLET, 빈 포장 삭제), 구성 패널 — 열린 BOX: 구성·빼기·LOT 담기(같은 품목만, 비우면 잔여 전량)·닫기 / 닫힌 BOX: 열린 PALLET에 묶기·풀기 / PALLET: 하위 BOX·닫기. 드래그 없이 수량 입력(모바일).
- `Receipts.tsx`(M-09): 입고할 PALLET(입고), 입고 내역(번호 복사 버튼), ERP 수기 연결 안내.
- 도움말 m-08(닫힌 포장·빈 포장·수량 변경), m-09(입고 후 불변·ERP 수기) 보강.

## 테스트

- `backend/tests/test_mes_packing.py` **14개**(동시성 1개 포함).
- `frontend/src/mes/packing.test.tsx` **7개**. Playwright +1(새 PALLET·BOX → 담기 → 닫기 → 묶기 → PALLET 닫기 → 입고) + 360px 2화면.

## 실행 검증 (CI 환경 변수만, .env 미사용)

| 명령 | 결과 |
|---|---|
| frontend typecheck / lint / format:check / build / test | 301 passed |
| ruff check / format --check (CI 범위) | 통과 |
| backend 전체 pytest | 446 passed (7분 29초) |
| `tools/run_portal_smoke.py` | 70 passed (개발 서버 종료 후 실행) |
| tools unittest / db:validate / audit / git diff --check | 통과 |

schema.json·마이그레이션·conftest·test_common·test_seed 변경 0.

## 다음

FS-020g M-01 MES 대시보드(가동률 없음 M-G06 안내) — MES 15화면 마무리.
