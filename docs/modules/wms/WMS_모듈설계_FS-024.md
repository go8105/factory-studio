# FS-024 WMS 모듈 설계서

작성일: 2026-09-27 (Claude Code)
상태: **초안 — 사용자 승인 대기.** 승인 전에는 `schema.json`·마이그레이션·코드를 바꾸지 않는다(설계 후 개발 원칙). 승인 뒤 FS-024a(DB)·b(API·화면)·c(시드·도움말·흐름 맵) 순서로 구현한다.
전제: [FS-024 결정서](../../plan/WMS도입_재고원장_결정_FS-024.md)(D13~D17), [FS-023 D9 교차 조회](../../plan/QMS도입_교차조회_결정_FS-023.md), [FS-013](../../plan/독립솔루션_전환결정_FS-013.md)
화면: 화면 설계서는 이 설계 승인 뒤 `docs/ui/화면설계_WMS_FS-024.md`로 작성한다(9장은 요약).

---

## 1. 이 모듈은 무엇인가

**MES·ERP가 확정한 입출고를 읽어 와 재고 원장에 반영하고, 창고·위치별 현재고와 이동 이력을 관리하는 창고 관리 솔루션이다.**

```
ERP 매입 확정 ──┐                          ┌── MES 자재 투입(공정 실행 완료분)
                ▼ 반영(+)          반영(−) ▼
          [원자재 창고]  ── 재고 원장 ──  (원자재 차감)
MES 완제품 입고 ──▶ 반영(+) [완제품 창고] ──▶ 반영(−) ◀── ERP 출하 확정
                         조정(±) · 창고 간 이동 · 기초재고
현재고 = Σ 원장 수량(파생값, 저장하지 않음)   가용 = 현재고 − ERP 미출하 지시(D17)
```

MES·ERP를 꺼도 WMS만으로 "창고를 정하고, 기초재고를 넣고, 조정·이동으로 재고를 관리한다"가 성립해야 한다(D12).

평가자 3분 동선:

```
대시보드(품목별 현재고·음수 경고·미반영 건수)
  → 원천 반영(MES 입고 PL-0006·ERP 매입 PI-0004·ERP 출하 SH-0004가 "미반영"으로 보인다 — 교차 조회)
  → 반영 → 재고 현황에서 LOT별 수량 변화
  → 원장(전표 → 이동 줄 → 원천 번호)으로 추적
  → 조정(폐기·반품) · 창고 간 이동
```

## 2. 하위 모듈

| 하위 모듈 | 소유 테이블 | 교차 조회 |
|---|---|---|
| `wms_master` 기준정보 | 창고, 위치, 품목, 품목 단위 환산 | MES 품목(가져오기, 선택) |
| `ledger` 재고 원장 | 재고 전표, 재고 이동 | MES 입고·투입, ERP 출하·매입(반영 원천), ERP 미출하 지시(가용) |

소유 **6테이블**. 스키마 간 FK 0건. 원천은 **코드·번호·수량 스냅샷**으로만 들어온다(D11). 품목은 WMS가 따로 소유한다(FS-013 D1 — 코드는 MES·ERP와 같게 심는다).

## 3. 업무 규칙

| 규칙 | 내용 |
|---|---|
| 원장이 원천 | 현재고는 **확정 전표의 이동 수량 합**이다. 잔량 테이블을 두지 않고 수량을 직접 고치지 않는다 |
| 전표 불변 | 확정(`posted`) 전표와 그 이동은 수정·삭제하지 않는다. 바로잡을 때는 **되돌림 전표**(부호 반대, `reverses_document_id`)를 남긴다. 작성 중(`draft`)은 조정·이동 전표만 있다 |
| 원천 반영 | 원천 1건 → 전표 1건, 반영과 동시에 확정. `source_key`가 같은 전표는 1건(부분 유니크). 두 번째 반영 요청은 409 `ALREADY_SYNCED`가 아니라 **기존 전표를 돌려준다**(멱등) |
| 반영 원천 4종 | ① MES 완제품 입고: 팔레트 1건 → 담긴 LOT마다 +, 완제품 기본 위치 ② MES 자재 투입: **완료된** 공정 실행 1건 → 투입 품목마다 −, 원자재 기본 위치(실행 중에는 MES에서 투입을 지울 수 있어 반영 대상이 아니다) ③ ERP 출하: 확정 출하 1건 → 줄마다 − ④ ERP 매입: 확정 매입 전표 1건 → 줄마다 +. 매입이 나중에 취소되면 "취소 반영"으로 되돌림 전표 |
| 출하 LOT 결정 | ERP 출하 줄의 `packing_no`가 WMS가 이미 반영한 **MES 입고 전표의 팔레트 번호**와 같으면 그 팔레트의 LOT별 수량으로 나눠 차감한다. 없거나 수량이 맞지 않으면 **LOT 미지정**(lot_no NULL)으로 품목 수량만 차감하고 현황에 "LOT 미지정 출고" 배지를 단다 |
| 단위 | 이동 수량은 **품목 기본 단위**로 저장한다. 원천 단위가 다르면 WMS 품목 단위 환산으로 바꾸고 원천 수량·단위를 스냅샷으로 남긴다(예: 핀 매입 10 BOX → 100,000 EA). 환산이 없으면 그 원천은 반영하지 않고 사유 "단위 환산 없음" |
| 미등록 품목 | 원천 품목 코드가 WMS 품목에 없으면 반영하지 않고 사유 "품목 미등록"을 보여 준다. W-07에서 MES 품목을 가져오거나 직접 등록한다 |
| 음수 재고 | 허용(D15). 전표 확정 때 잔량을 확인하지 않는다. 현재고 < 0인 품목·위치·LOT은 경고 배지 |
| 조정 | 사유 필수: `RETURN` 반품 입고 · `SCRAP` 폐기 · `COUNT` 실물 차이 · `OTHER` 기타(메모 필수). 한 전표에 +·− 줄을 섞을 수 있다 |
| 창고 간 이동 | 한 전표 안에서 같은 품목·LOT의 − 줄과 + 줄 합이 0이어야 확정된다(SERVICE). 같은 위치로의 이동은 막는다 |
| 기초재고 | 전표 유형 `OPENING`. 공간당 여러 건 가능(창고 추가 시). 원천 없음 |
| 기준 월 | 전표에 `document_month 'YYYY-MM'`(업무일 파생) — 대시보드 월별 입출고 집계 |

## 4. DB 차분 — `wms` 스키마 6테이블

공통 컬럼·제약은 QMS와 같다: `id bigint IDENTITY`·`workspace_id`·`generation_id`·`created_at`, PK·UK(S, id)·범위 앵커 FK → `core.data_generation`, 업무 FK는 `(S, 참조 id)` 복합·RESTRICT, scope `generation`, FK 열마다 INDEX. `S = (workspace_id, generation_id)`.

| 엔티티 | 하위 모듈 | 역할 |
|---|---|---|
| `wms.warehouse` | wms_master | 창고 |
| `wms.storage_location` | wms_master | 창고 안 보관 위치(1단계) |
| `wms.item` | wms_master | WMS 품목(재고 관리 대상) |
| `wms.item_unit_conversion` | wms_master | 품목별 단위 환산 |
| `wms.stock_document` | ledger | 재고 전표(원천 반영·기초·조정·이동·되돌림) |
| `wms.stock_move` | ledger | 재고 이동 줄 = 원장 |

### 4.1 `wms.warehouse`

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| code | varchar(20) | ○ | `[A-Z][A-Z0-9-]{1,19}`. UK(S, code) |
| name | varchar(100) | ○ | |
| purpose | varchar(10) | ○ | `RAW` / `FG` — 원천 반영이 들어갈 창고를 정한다 |
| is_active | boolean | ○ | default true |

- UK_PARTIAL (S, purpose) WHERE is_active — 용도별 활성 창고 1개(원천 반영 대상이 모호하지 않게).

### 4.2 `wms.storage_location`

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| warehouse_id | bigint | ○ | FK (S, warehouse_id) → warehouse |
| code | varchar(20) | ○ | UK(S, warehouse_id, code) |
| name | varchar(100) | ○ | |
| is_default | boolean | ○ | default false. UK_PARTIAL (S, warehouse_id) WHERE is_default — 창고당 기본 위치 1개(원천 반영 입고·차감 위치) |
| is_active | boolean | ○ | default true. 기본 위치는 사용 안 함으로 바꿀 수 없다(SERVICE) |

`core.location`·`mes.location`(공정 구역)과 다른 개념이다(FS-005 ERD 메모). 이름을 `storage_location`으로 둔다.

### 4.3 `wms.item`

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| item_code | varchar(40) | ○ | UK(S, item_code). MES·ERP와 같은 코드(FK 없음) |
| name | varchar(100) | ○ | |
| base_unit | varchar(10) | ○ | 원장 수량 단위 |
| item_class | varchar(10) | ○ | `RAW` / `FG` |
| lot_tracked | boolean | ○ | `FG`면 true(D16). CHECK: item_class='RAW' → false |
| is_active | boolean | ○ | default true |

### 4.4 `wms.item_unit_conversion`

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| item_id | bigint | ○ | FK → item. UK(S, item_id, from_unit) |
| from_unit | varchar(10) | ○ | ≠ 품목 기본 단위(SERVICE) |
| factor | numeric(18,6) | ○ | > 0. 1 from_unit = factor 기본 단위 |

### 4.5 `wms.stock_document`

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| document_no | varchar(40) | ○ | 서버 발번 `WD-YYYYMMDD-NNN`. UK(S, document_no) |
| document_type | varchar(20) | ○ | `OPENING` · `MES_RECEIPT` · `MES_ISSUE` · `ERP_SHIPMENT` · `ERP_PURCHASE` · `ADJUSTMENT` · `TRANSFER` · `REVERSAL` |
| status | varchar(10) | ○ | `draft` / `posted`. 원천 반영·되돌림은 만들 때 `posted` |
| source_key | varchar(100) | | 원천 반영이면 NN (CHECK). 예 `MES:RECEIPT:PL-0006` · `MES:ISSUE:LT-0013:INJ` · `ERP:SHIPMENT:SH-0004` · `ERP:PURCHASE:PI-0004` |
| source_ref | varchar(40) | | 화면 표시용 원천 번호 스냅샷(PL-0006 등) |
| reverses_document_id | bigint | | 자기참조 FK. `REVERSAL` ↔ NN (CHECK) |
| reason_code | varchar(10) | | `ADJUSTMENT` ↔ NN: `RETURN`/`SCRAP`/`COUNT`/`OTHER` |
| document_on | date | ○ | 업무일(원천 시각의 서울 날짜) |
| document_month | varchar(7) | ○ | `'YYYY-MM'` CHECK. document_on에서 파생 |
| posted_at | timestamptz | | posted ↔ NN |
| note | varchar(300) | | `reason_code='OTHER'`이면 NN |

- **UK_PARTIAL** (S, source_key) WHERE document_type <> 'REVERSAL' — 원천 1건 = 반영 전표 1건(D14).
- **UK_PARTIAL** (S, reverses_document_id) WHERE reverses_document_id IS NOT NULL — 되돌림은 1번만.
- SERVICE: `posted`는 UPDATE/DELETE 금지(세대 정리만). `draft`는 조정·이동만, 삭제 가능.

### 4.6 `wms.stock_move` (원장)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| document_id | bigint | ○ | FK → stock_document. UK(S, document_id, line_no) |
| line_no | integer | ○ | ≥ 1 |
| item_id | bigint | ○ | FK → item |
| location_id | bigint | ○ | FK → storage_location |
| lot_no | varchar(50) | | 스냅샷. `lot_tracked` 품목에서 NULL이면 "LOT 미지정"(SERVICE: RAW 품목은 NULL만) |
| qty_delta | numeric(18,3) | ○ | ≠ 0 (CHECK). 기본 단위, 입고 +·출고 − |
| source_qty | numeric(18,3) | | 원천 수량 스냅샷 |
| source_unit | varchar(10) | | 원천 단위 스냅샷 |
| moved_at | timestamptz | ○ | 원천 시각(입고 시각·실행 종료·출하 시각·매입 확정) 또는 전표 확정 시각 |

- INDEX (S, item_id, location_id, lot_no) — 현재고 합계.
- SERVICE: 전표가 `posted`면 UPDATE/DELETE 금지. `TRANSFER` 전표는 품목·LOT별 합 0.

### 4.7 core 변경

| 대상 | 변경 |
|---|---|
| `core.workspace_module` CHECK | `module_key`에 `'wms'` 추가 (새 revision, 기존 `fs023a_qms` 수정 금지) |
| 모듈 행 | 기존 공간에 `wms` 행 추가(데이터 마이그레이션, FS-023b와 같은 방식), 새 공간·시드 템플릿 6행 |

### 4.8 규모

| 구분 | 현재 | 변경 |
|---|---:|---:|
| 업무 스키마 | mes 21 · erp 27 · fems 13 · qms 6 | + **wms 6** |
| 전체 테이블 | 77 | **83** |
| 상태 목록 | — | stock_document 1개 추가 |

## 5. 상태 전이

| 대상 | 전이 | 조건 |
|---|---|---|
| stock_document(원천·되돌림) | (생성) `posted` | TX-W1·W3. 만들면서 확정 |
| stock_document(기초·조정·이동) | `draft → posted` | 줄 ≥ 1, 이동은 합 0, 조정은 사유 |
| | `draft` 삭제 | 작성자 누구나(공간 안) |
| posted 전표 | 되돌림 | `REVERSAL` 전표 1건(부호 반대 줄). 원천 반영 전표를 되돌리면 그 원천은 다시 "미반영"이 된다 — 1차는 **ERP 매입 취소 반영만** 되돌림을 만들고, 사용자가 임의로 원천 전표를 되돌리는 기능은 두지 않는다(13장 질문 3) |

## 6. 트랜잭션·잠금

기존 공간 우선 락 순서(FS-006a)를 따른다. WMS 트랜잭션은 **wms 스키마 행만 잠그고 MES·ERP는 읽기만** 한다(X5).

| TX | 내용 | 잠금 |
|---|---|---|
| TX-W1 원천 반영 | 인터페이스로 원천 1건 읽기 → 품목·단위 확인 → 전표(posted)+이동 INSERT | 공간 → (INSERT가 `source_key` 부분 유니크로 경합 판정, `ON CONFLICT DO NOTHING` 후 기존 전표 반환) |
| TX-W2 전표 확정 | 줄 검증(이동 합 0·사유) → posted | 공간 → 대상 전표 |
| TX-W3 매입 취소 반영 | ERP에서 취소된 매입의 반영 전표 확인 → 되돌림 전표 | 공간 → 원 전표 → (되돌림 부분 유니크) |

- 음수 허용(D15)이라 **잔량 행 잠금이 없다** — 원장 INSERT만 한다. 동시성 검증은 "같은 원천 동시 반영 → 전표 1건"과 "같은 전표 동시 확정 → 1번만" 두 가지.
- 멱등: 모든 변경 POST는 `Idempotency-Key`(core.request_receipt).
- 일괄 반영(여러 원천 선택)은 원천마다 따로 커밋한다 — 한 건 실패(품목 미등록)가 다른 건을 막지 않게.

## 7. 교차 조회 인터페이스 (D9·X1~X6)

### 7.1 MES 제공 — `fs/mes/interface.py` 추가

| 함수 | 반환 | 조건 |
|---|---|---|
| `finished_goods_receipts(scope)` | `[{packingNo, receivedAt, lines:[{lotNo, itemCode, qty, unit}]}]` | 확정 입고(팔레트). 줄은 팔레트 아래 BOX의 LOT별 합 |
| `completed_material_issues(scope)` | `[{sourceRef: 'LT-0013:INJ', endedAt, lines:[{itemCode, qty, unit}]}]` | **완료된** 공정 실행의 투입(품목별 합) |
| `items(scope, item_type=None)` | 기존 함수 확장 — `None`이면 전 품목 | W-07 품목 가져오기 |

### 7.2 ERP 제공 — `fs/erp/interface.py` (새 파일)

| 함수 | 반환 | 조건 |
|---|---|---|
| `confirmed_shipments(scope)` | `[{shipmentNo, shippedAt, lines:[{itemCode, qty, unit, packingNo}]}]` | 확정 출하 |
| `purchase_receipts(scope)` | `[{invoiceNo, confirmedAt, cancelledAt, lines:[{itemCode, qty, unit}]}]` | 확정·확정 후 취소 매입(초안 제외) |
| `open_shipment_qty(scope)` | `{itemCode: qty}` | 미출하 출하지시 수량(가용 계산, D17) |

제공 솔루션이 꺼져 있으면 `None`(X4). ERP가 공개하는 첫 인터페이스다.

### 7.3 "미반영" 계산

인터페이스 결과의 원천마다 `source_key`를 만들어 WMS 전표에 없는 것을 **미반영**으로, 매입 중 `cancelledAt`이 있고 반영 전표는 있으나 되돌림이 없는 것을 **취소 미반영**으로 본다. 계산 결과를 저장하지 않는다. 반영할 수 없는 원천은 사유(품목 미등록·단위 환산 없음)와 함께 보여 준다.

## 8. API 계약 (`/api/v1/wms`, FS-010 3장 공통 규약)

| 메서드·경로 | 내용 |
|---|---|
| `GET /dashboard?month=` | 품목별 현재고·음수 경고 수·미반영 원천 수(원천별)·월 입출고 합 |
| `GET/POST /warehouses`, `PATCH /warehouses/{id}` | 창고. 쓰인 창고는 삭제 대신 사용 안 함 |
| `GET/POST /warehouses/{id}/locations`, `PATCH/DELETE /locations/{id}` | 위치. 이동이 있는 위치는 삭제 409 `REFERENCED_BY_OTHERS` |
| `GET/POST /items`, `PATCH /items/{id}`, `POST /items/import` | 품목, MES 품목 가져오기(MES 꺼짐 409 `SOURCE_MODULE_DISABLED`) |
| `GET/POST/DELETE /items/{id}/conversions` | 단위 환산 |
| `GET /stock?itemCode=&warehouseId=&lotNo=&negativeOnly=` | 현재고(품목·위치·LOT), 완제품은 가용 수량(ERP 꺼짐이면 `available: null`) |
| `GET /sources?kind=MES_RECEIPT\|MES_ISSUE\|ERP_SHIPMENT\|ERP_PURCHASE&state=pending` | 7.3 미반영·취소 미반영·반영됨 목록. 원천 솔루션 꺼짐이면 그 종류만 `disabled` |
| `POST /sources/sync` | `{kind, sourceKeys:[...]}` — TX-W1/W3, 원천별 결과 `{sourceKey, documentId?, reason?}` |
| `GET /documents?type=&status=&month=` · `GET /documents/{id}` | 전표·줄 |
| `POST /documents` · `PATCH /documents/{id}` · `DELETE /documents/{id}` | 기초·조정·이동 초안(줄 전체 교체) |
| `POST /documents/{id}/post` | TX-W2 |
| `GET /moves?itemCode=&lotNo=&from=&to=` | 원장 조회(전표 번호·원천 번호 포함) |

MES·ERP API는 바꾸지 않는다.

## 9. 화면 (요약 — 상세는 승인 뒤 화면 설계서)

| ID | 화면 | UI 패턴(UI-02·03) |
|---|---|---|
| W-01 | 재고 대시보드 | D |
| W-02 | 재고 현황 | L — 품목·위치·LOT, 음수·LOT 미지정 배지, 가용 |
| W-03 | 원천 반영 | L + 선택 반영 — 원천 4종 탭, 미반영 사유 **(교차 조회 시연 화면)** |
| W-04 | 재고 전표 | W(E-04) — 조정·이동·기초 작성·확정, 원천 전표 읽기 |
| W-05 | 재고 원장 | L — 이동 줄 조회, 전표·원천 번호로 추적 |
| W-06 | 창고·위치 | P(F-12) — 창고 → 위치 |
| W-07 | 품목·단위 | S(F-05) + MES 가져오기 |

## 10. 합성 데이터 (FS-005g 확장, 약 110행)

| 대상 | 행 | 내용 |
|---|---:|---|
| warehouse | 2 | `WH-RAW` 원자재 창고, `WH-FG` 완제품 창고 |
| storage_location | 4 | 창고마다 기본 위치 1 + 예비 위치 1 |
| item | 5 | RM-PBT·RM-PIN(RAW), FG-C100·C200·T300(FG). SF-H100(반제품)은 넣지 않는다(공정 내부) |
| item_unit_conversion | 1 | RM-PIN BOX → 10,000 EA(MES·ERP와 같은 값) |
| stock_document | 약 40 | 기초 1(T−91) · ERP 매입 PI-0001~0003·0006 + PI-0006 취소 되돌림 · MES 입고 PL-0001~0005 · ERP 출하 SH-0001~0003 · MES 투입(E 계열 LOT의 사출·조립 실행) · 조정 1(SCRAP) · 이동 초안 1 |
| stock_move | 약 55 | 전표 줄 |

- **미반영으로 남기는 원천(시연용):** MES 입고 PL-0006, ERP 매입 PI-0004, ERP 출하 SH-0004, W 계열 LOT의 완료된 공정 실행 투입. 게스트는 W-03에서 바로 반영해 볼 수 있다.
- 기초재고는 원자재만(PBT 200 KG, 핀 50,000 EA) — 시드 매입이 T−55부터라 초기 투입이 음수가 되지 않게 한다. 반영 순서 끝의 현재고가 모두 0 이상인지 시드 검증(V)으로 확인한다.
- 복사: `document_month` 재계산, `WD-` 번호 속 날짜 이동(QMS와 같은 방식). `source_key`는 날짜가 없는 원천 번호라 그대로 둔다.

## 11. 수용 기준 (AC-111~124)

| AC | 기준 |
|---|---|
| 111 | 같은 원천을 두 번 반영해도(동시 포함) 전표는 1건이고 두 번째 응답은 같은 전표다 |
| 112 | 현재고는 확정 전표 이동 합과 항상 같다(잔량 저장 없음) |
| 113 | 확정 전표·이동은 수정·삭제할 수 없다 |
| 114 | 출하 반영 시 반영된 팔레트 번호가 있으면 LOT별로, 없으면 LOT 미지정으로 차감한다 |
| 115 | 원천 단위가 다르면 환산해 기본 단위로 저장하고 원천 수량·단위를 남긴다. 환산이 없으면 반영되지 않고 사유가 보인다 |
| 116 | WMS 품목에 없는 코드의 원천은 반영되지 않고 사유가 보인다. 다른 원천 반영은 영향받지 않는다 |
| 117 | 재고가 부족해도 반영·확정되고 음수 경고가 보인다(D15) |
| 118 | 확정 후 취소된 ERP 매입은 "취소 미반영"으로 보이고, 반영하면 되돌림 전표 1건이 생긴다 |
| 119 | 이동 전표는 품목·LOT별 합이 0이 아니면 확정되지 않는다 |
| 120 | 조정 전표는 사유 없이 확정되지 않는다 |
| 121 | 실행 중인 공정 실행의 투입은 반영 대상에 나오지 않는다 |
| 122 | MES·ERP를 끄면 해당 원천만 "꺼짐"이고 WMS 수동 전표는 동작한다. WMS를 꺼도 MES·ERP 화면·API는 그대로다 |
| 123 | 가용 수량 = 현재고 − ERP 미출하 지시. ERP 꺼짐이면 `null` |
| 124 | 다른 공간·이전 세대의 원천·전표는 보이지 않는다(X3) |

격리 검사: R1(wms 포함) · R5 · R6.

## 12. 하지 않는 것 / 후속

- 결정서 5장 전부(차단, 예약, 피킹, 실사, 구매발주·입고검수, 원가, 원자재 LOT, MES 패킹 상태 갱신, QMS 자동 반영).
- 반제품(SF-H100) 재고. MES 공정 내부 흐름으로 본다.
- 바코드·모바일 스캔, 위치 용량.

## 13. 결정이 필요한 것 (승인 시 함께 확인)

1. **전표 번호** `WD-YYYYMMDD-NNN` 서버 발번(QMS와 같은 방식)으로 하는 것.
2. **원천 반영 단위**: MES 투입은 공정 실행 1건 = 전표 1건(품목별 줄). 권장: 그대로 — LOT·공정으로 추적이 된다.
3. **원천 반영 전표 되돌림**: 1차는 ERP 매입 취소 반영만 되돌림을 만든다. 사용자가 원천 반영 전표를 직접 되돌리는 기능은 두지 않는다(잘못된 수량은 조정 전표로). 권장: 그대로.
4. **완제품 창고 이동 시 LOT**: 이동 전표는 LOT을 지정해야 한다(LOT 미지정 재고는 이동 불가, 조정으로만 정리). 권장: 그대로.
