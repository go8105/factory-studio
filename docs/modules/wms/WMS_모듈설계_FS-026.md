# WMS 모듈 설계 revision 2 — FS-026

작성일: 2026-09-28. **전체 설계 승인 2026-09-28. FS-026a DB 구현, API·화면 미구현.** 결정서 D24~D32 및 Q1~Q6은 사용자의 “진행해줘”로 승인됐다.
기준: [FS-024 revision 1](WMS_모듈설계_FS-024.md), [FS-026 결정](../../plan/WMS확장_입고검수예약_결정_FS-026.md). 기존 6테이블/원장을 재사용하며 이 문서는 차분이다. 상충하는 범위·가용·입고 취소 정책은 승인된 FS-026을 따른다. 실제 DB/API는 아직 FS-024다.

## 1. 변경 범위와 불변식

- 기존 `warehouse`, `storage_location`, `item`, `item_unit_conversion`, `stock_document`, `stock_move` 유지. **새 테이블 5개 → WMS 총 11개**. 재고 잔량 테이블은 만들지 않는다.
- S=(workspace_id,generation_id), 새 테이블 공통: id bigint IDENTITY PK, workspace_id/generation_id bigint NOT NULL, created_at timestamptz NOT NULL default clock_timestamp(), UK(S,id), 기존과 같은 core 범위 앵커. 업무 FK는 모두 (S,id)·RESTRICT, FK 열 인덱스. 업무 스키마 간 FK 없음.
- 현재고=posted 전표의 stock_move 합. 정상 위치 현재고−활성 예약=예약 가능 수량. 격리 현재고는 별도 표시한다. 위치/품목/LOT별 음수를 숨기지 않는다.
- 수량 numeric(18,3), API 문자열·Decimal. 환산 factor numeric(18,6), 곱이 소수 3자리 또는 정밀도 한도를 넘으면 반올림하지 않고 거부한다. API ID는 기존 정수 규약, 시각 UTC ISO, 업무일 서울 날짜.
- 조회 값은 잔량/예약 부족/ERP 비교 결과를 저장하지 않는다. 확정 검수와 소진/해제 예약은 불변이다. 초안 물리 삭제 대신 취소/해제 이력을 보존한다.

## 2. 기존 테이블 차분

| 테이블 | 변경 / 제약 |
|---|---|
| storage_location | `location_type varchar(16) NOT NULL DEFAULT 'NORMAL'`, CHECK NORMAL/QUARANTINE. 기본 위치는 NORMAL이어야 함(CHECK). 기존 행 NORMAL로 이행 |
| stock_document | document_type에 `WMS_INSPECTION` 추가. 생성 시 posted, source_key 필수, reverses_document_id NULL. 현행 유형·source_key/posted CHECK를 새 revision에서 확장. source_key 부분 유니크 유지 |
| 나머지 4개 | 컬럼 변경 없음. 품목 단위·완제품 LOT 규칙 유지 |

WMS_INSPECTION은 ERP 연결 여부와 무관하게 `WMS:INSPECTION:<입고번호>`를 source_key로 쓴다. ERP 매입의 직접 반영 키와 다르므로 **아래 source_claim과 기존 stock_document를 함께 검사**해야 한다. key만 달리 발급해 중복을 회피하는 구현은 금지한다. 검수 후 조정은 기존 ADJUSTMENT/TRANSFER를 사용하고 note에 입고번호/사유를 필수로 남긴다. 원천 취소는 WMS_INSPECTION을 REVERSAL로 만들 수 없다.

SERVICE: 원장/진행 예정/활성 예약이 참조하는 위치의 유형 변경 금지. 유형 간 이동은 note 필수. 기본 위치의 비활성 금지는 유지하고, 추가로 진행 예정/활성 예약 참조 위치·품목·창고의 비활성화를 거부한다. 이미 비활성인 대상은 새 예정/예약/검수 확정의 대상으로 사용할 수 없다(해제·취소·읽기는 허용).

## 3. 새 테이블 명세

아래 `?`는 NULL 허용, 그 외는 NOT NULL. 모든 새 테이블에 1장의 공통 컬럼이 있다. CHECK는 단일 행 조건, SERVICE는 트랜잭션 안에서 검사하는 정책이다.

### 3.1 wms.inbound_notice — 입고 예정/검수 헤더

| 컬럼 | 타입·기본값 | 의미/제약 |
|---|---|---|
| notice_no | varchar(40) | UK(S,notice_no), 서버 IN-YYYYMMDD-NNN |
| business_key | varchar(100) | UK(S,business_key), 재요청과 별개 영구 중복 방지 번호 |
| warehouse_id | bigint | FK warehouse |
| status | varchar(16), PLANNED | PLANNED/ARRIVED/INSPECTED/CANCELLED |
| expected_on | date | 예정일 |
| vehicle_no | varchar(40)? | 합성 차량 식별 문자열 |
| partner_ref | varchar(100)? | 공급처 참고 코드, 타 스키마 FK 아님 |
| version | integer, 1 | >0, 변경마다 증가 |
| arrived_at | timestamptz? | 도착 서버 시각 |
| inspected_at | timestamptz? | 검수 확정 서버 시각 |
| cancelled_at | timestamptz? | 취소 서버 시각 |
| stock_document_id | bigint? | FK stock_document, UK_PARTIAL(S,stock_document_id) WHERE NOT NULL |
| reason | varchar(300)? | 취소·차이·격리 사유 |
| updated_at | timestamptz, clock_timestamp() | 마지막 변경 |

CHECK: INSPECTED ↔ inspected_at NN; CANCELLED ↔ cancelled_at NN; ARRIVED/INSPECTED이면 arrived_at NN; PLANNED이면 arrived_at NULL. stock_document_id NN이면 INSPECTED. CANCELLED이면 reason NN/공백 금지. SERVICE: INSPECTED 합계 수령량>0 ↔ stock_document_id NN, 전량 부족이면 NULL. 연결 전표는 WMS_INSPECTION이어야 한다. 취소는 도착 시각을 지우지 않는다.

### 3.2 wms.inbound_notice_line — 예정/검수 명세

| 컬럼 | 타입·기본값 | 의미/제약 |
|---|---|---|
| notice_id | bigint | FK inbound_notice, UK(S,notice_id,line_no) |
| line_no | integer | >0 |
| item_id | bigint | FK item |
| lot_no | varchar(50)? | 완제품 LOT 스냅샷, 원자재 NULL |
| expected_qty | numeric(18,3) | >0, 기본 단위 예정 |
| accepted_qty | numeric(18,3)? | 합격, >=0 |
| quarantined_qty | numeric(18,3)? | 격리, >=0 |
| shortage_qty | numeric(18,3)? | 부족, >=0 |
| normal_location_id | bigint | FK storage_location |
| quarantine_location_id | bigint? | FK storage_location |
| reason | varchar(300)? | 격리/부족 시 필수 |

CHECK: 세 검수 수량은 모두 NULL 또는 모두 NN이고 합=expected_qty. quarantined_qty>0이면 격리 위치 NN. SERVICE: 위치들은 헤더 창고와 동일, 정상/격리 유형 확인, 완제품 lot_no 필수·원자재 NULL. 같은 품목·LOT 중복 줄 금지(NULL 정규화 유니크 인덱스 S,notice_id,item_id,coalesce(lot_no,'')). 빈 LOT 문자열 금지. INSPECTED 전에는 세 검수 수량을 저장하지 않고 확인 요청에서 한 번에 기록한다. 초안 화면 편집값은 브라우저 폼이다.

### 3.3 wms.source_claim — ERP 매입 선점/대사 연결

| 컬럼 | 타입·기본값 | 의미/제약 |
|---|---|---|
| source_key | varchar(100) | `ERP:PURCHASE:<번호>`만 허용 |
| notice_id | bigint | FK inbound_notice |
| status | varchar(16), CLAIMED | CLAIMED/COMPLETED/RELEASED |
| source_snapshot | jsonb | 연결 당시 invoiceNo, confirmedAt, 품목별 baseQty와 원천 qty/unit/factor 배열. 객체 CHECK |
| source_digest | varchar(64) | 정렬한 의미 값의 SHA-256, 화면 순서/조회 시각 제외 |
| closed_at | timestamptz? | COMPLETED/RELEASED ↔ NN |
| release_reason | varchar(300)? | RELEASED 시 필수 |

UK_PARTIAL(S,source_key) WHERE status<>'RELEASED'; UK_PARTIAL(S,notice_id) WHERE status<>'RELEASED'. 여러 취소/재연결 이력은 남지만 유효 연결은 원천·예정당 하나다. 단순 FK로 기존 stock_document의 중복을 막을 수 없으므로 모든 원천 반영/연결 경로에서 공간 락 안 교차 존재 검사를 강제한다. 직접 반영은 claim을 새로 만들지 않는다.

CLAIMED는 검수 전 선점. COMPLETED는 검수 완료/수동 기입고 대사 완료로 영구 유지한다. 전량 부족도 COMPLETED다. COMPLETED는 해제 불가. CLAIMED 해제는 연결 해제/예정 취소일 때만 가능하며 사유 필수. snapshot과 digest는 생성 후 수정하지 않는다. 원천 변경 시 기존 CLAIMED를 해제하고 새 연결을 만든다.

### 3.4 wms.stock_reservation — 예약 묶음

| 컬럼 | 타입·기본값 | 의미/제약 |
|---|---|---|
| reservation_no | varchar(40) | UK(S,reservation_no), RSV-YYYYMMDD-NNN |
| business_key | varchar(100) | UK(S,business_key), 영구 중복 방지 |
| status | varchar(16), ACTIVE | ACTIVE/RELEASED/CONSUMED |
| shipment_order_ref | varchar(40)? | ERP 출하지시 번호 참고, FK 아님 |
| version | integer, 1 | >0 |
| reason | varchar(300)? | 등록 메모/해제 사유 |
| closed_at | timestamptz? | ACTIVE ↔ NULL |
| shipment_source_key | varchar(100)? | CONSUMED 시 ERP:SHIPMENT:<번호> |
| stock_document_id | bigint? | FK stock_document, CONSUMED 시 ERP_SHIPMENT 전표 |

CHECK: CONSUMED ↔ shipment_source_key/stock_document_id 모두 NN; RELEASED이면 reason 공백 아닌 NN. UK_PARTIAL(S,shipment_source_key) 및 (S,stock_document_id) WHERE NOT NULL. 한 ERP 출하/전표를 여러 묶음이 소진할 수 없다. 상세 참고 출하지시가 있으면 실제 출하의 shipmentOrderNo와 같아야 한다.

### 3.5 wms.stock_reservation_line — 위치·품목·LOT 배분

| 컬럼 | 타입 | 의미/제약 |
|---|---|---|
| reservation_id | bigint | FK stock_reservation, UK(S,reservation_id,line_no) |
| line_no | integer | >0 |
| item_id | bigint | FK item |
| location_id | bigint | FK storage_location |
| lot_no | varchar(50)? | 완제품 필수/원자재 NULL, 빈 문자열 금지 |
| quantity | numeric(18,3) | >0, 기본 단위 |

UK(S,reservation_id,item_id,location_id,coalesce(lot_no,'')), SERVICE: 정상·활성 위치, 활성 품목/창고, 각 재고 키마다 quantity<=현재고−기존 활성 예약. 서로 다른 단위는 합산하지 않는다. 전량 등록 원자성. 등록 후 줄 수정/삭제 금지, 해제 후 새 묶음으로 재등록한다. 원자재 예약은 등록/해제까지만 지원하며 ERP 고객 출하 소진은 완제품 묶음만 가능하다. 이를 UI와 도움말에 표시한다.

## 4. 상태와 원장 효과

| 대상/동작 | 상태 | 원장 효과 |
|---|---|---|
| 예정 생성/수정 | PLANNED | 0 |
| 도착(3D/수동 동일) | PLANNED→ARRIVED | 0 |
| 검수 확정 | ARRIVED→INSPECTED | 합격 정상 +, 격리 +; 부족/0 줄 없음 |
| 예정 취소 | PLANNED/ARRIVED→CANCELLED | 0, CLAIMED 해제 |
| 사전 연결 | 미연결 예정→CLAIMED | 0, 예정 수량과 ERP 환산 합 일치 |
| 사후 대사 | 미연결 INSPECTED→COMPLETED | 0, 실수령 아닌 예정 수량과 ERP 합 일치 |
| 예약 등록 | 생성 ACTIVE | 0, 가용 감소 |
| 예약 해제 | ACTIVE→RELEASED | 0, 가용 복원 |
| 연결 출하 반영 | ACTIVE→CONSUMED | ERP 출하 −와 같은 TX |
| 격리 이동/해제 | 기존 TRANSFER posted | 동일 품목/LOT −/+ 합 0 |

ARRIVED 이후 예정 줄/창고/차량 수정 불가. 잘못된 예정은 취소 후 재등록한다. 다만 원천 연결/해제는 검수 전 PLANNED/ARRIVED에서 가능하다. 확정 시점에 유효 선점을 다시 확인한다. 검수 확정은 요청 줄 ID 집합이 저장된 모든 줄과 같아야 한다.

## 5. 원천 라우팅·중복 방지

ERP PURCHASE 반영은 기존 전표와 유효 claim을 함께 조회한다.

| 조건 | W-03 결과/쓰기 |
|---|---|
| 직접 반영 전표만 있음 | 기존 멱등 응답; ERP 취소면 기존 REVERSAL 1건 |
| CLAIMED | inspection_pending, 검수 안내, 원장 생성 안 함 |
| COMPLETED | inspected, noticeId/documentId(전량 부족 NULL) 반환, 새 원장 0 |
| COMPLETED + ERP 취소 | inspected_cancelled, 회계 취소 경고, 새 원장 0 |
| 둘 다 없음 | 기존 직접 반영 허용 |
| 양쪽 모두 존재(불변식 위반) | SOURCE_ROUTE_CONFLICT, 중단·진단; 자동 정정 금지 |

완료 claim은 원천 조회 결과가 사라져도 삭제하지 않는다. ERP가 꺼지면 연결된 검수 확정/대사/예약 소진은 SOURCE_MODULE_DISABLED. 수동 미연결 예정·검수·예약/해제는 동작한다. 원천 취소·삭제·단위/수량 변경·환산 변경으로 snapshot digest가 달라지면 SOURCE_CHANGED로 검수를 보류한다. 재연결이 필요하다.

원천 연결 전에 이미 직접 반영된 전표(되돌림 포함 이력)가 있으면 SOURCE_ALREADY_POSTED. 연결 해제와 직접 반영의 경합도 공간 락으로 직렬화한다. 별도 요청 키나 다른 사용자가 호출해도 같은 결과다. 사후 대사는 INSPECTED의 예정 품목/수량과 ERP를 대조하며 전량 부족도 허용한다. 한쪽에 다른 유효 연결이 있으면 거부한다.

## 6. 예약 소진과 가용 조회

`consume-shipment`은 원천 ERP 출하가 confirmed·미반영인지 확인한다. 예약의 품목별 합과 출하의 환산 합 전량 일치, 모두 FG, 참고 출하지시가 있다면 번호 일치가 필요하다. packingNo가 있는 출하 줄은 기존 MES 입고 원장 LOT 배분과 대응해야 한다. 품목·LOT별 수량까지 비교하고, 출하 줄의 packingNo 일부만 있는 혼합/모호한 배분은 연결 불가로 처리한다. 예약 위치는 현재 예약 배분 위치를 사용하므로 과거 팔레트 입고 위치와 같을 필요는 없다.

성공 시 예약 배분으로 ERP_SHIPMENT 전표·이동을 1회 생성하고 예약을 CONSUMED로 바꾼다. source_qty/source_unit은 예약 배분의 기본 단위로 기록하고 원 ERP 상세는 원천 인터페이스에서 조회한다(기존 LOT 배분 방식과 동일). 예약 후 부족해졌어도 D15에 따라 소진 출하는 반영하고 음수/부족 경고를 반환한다. 소진 직전 재고 부족으로 ERP 확정 사실을 누락시키지 않는다.

연결 검증 실패는 예약/원장 모두 변화 0. 사용자는 W-03에서 연결 없이 기존 반영을 선택할 수 있다. 이 경로는 기존 LOT 매칭 정책이며 예약은 남는다. 예약이 연결된 출하를 기존 sync가 먼저 반영하면 소진 요청은 SOURCE_ALREADY_POSTED(소급 소진 금지). 소진이 먼저 끝나면 sync는 기존 전표 반환. 성공한 동일 소진 재요청은 같은 전표 반환, 다른 출하 키로 재소진은 상태 오류다.

조회: W-01/W-02 `available`의 뜻을 예약 가능으로 변경한다. `normalOnHand`, `quarantinedOnHand`, `reservedQty`, `available`, `reservationShortage=max(0,-available)`를 위치/품목/LOT별 제공한다. 합계만으로 다른 위치의 부족을 숨기지 않는다. ERP `openShipmentQty`는 별도 참고, 꺼짐이면 이 값만 null. 기존 AC-123은 대체된다. 수량/위치 필터는 현재고와 예약 양쪽에 동일 적용, 현재고 0이어도 예약이 있으면 행을 표시한다. 대시보드 현재 재고·예약은 월 필터와 무관, 월 필터는 이동 실적만 적용한다.

## 7. TX·멱등·오류

모든 쓰기: 인증/CSRF → write_scope(공간 락·활성 세대·모듈 검사) → 기존 영수증 확인 → version/상태 검사 → WMS 행 잠금/정책 검사 → 변경+영수증 원자 커밋. 다른 솔루션 행은 잠그지 않는다. 입고 헤더→claim→전표, 예약 헤더→전표 순서; 여러 대상은 ID 오름차순이다. 기존 원천 반영/조정도 같은 공간 락을 사용하므로 예약 수량 검사와 경쟁하지 않는다.

| TX | 원자 단위 |
|---|---|
| TX-W4 | 예정 생성/수정 및 줄 검증; 수정은 expectedVersion 필수 |
| TX-W5 | 원천 선점/해제/사후 대사, notice version 증가 |
| TX-W6 | 도착/취소; 취소 시 선점 해제 포함 |
| TX-W7 | 검수 줄 기록+전표/이동+claim COMPLETED+상태 변경 |
| TX-W8 | 예약 전량 등록/해제 |
| TX-W9 | 출하 원천 검사+원장 1회 차감+예약 소진 |

Idempotency-Key는 기존 24시간 영수증 규칙(동일 키 다른 본문/만료 422)을 유지한다. 영수증 만료 이후도 business_key·source_claim·원천 전표 유니크·최종 상태가 중복 생성을 막는다. 새 키 재요청의 도착은 이미 ARRIVED/INSPECTED면 기존 도착 결과, 검수는 저장 결과와 동일 본문이면 기존 결과(상이하면409), 소진은 같은 출하라면 기존 결과. 최종 상태 재요청 판정을 version 오류보다 먼저 하되 내용 일치를 확인한다. 네트워크 시간 초과는 실패 확정이 아니므로 GET으로 서버 상태를 재조회한다.

신규 정책 오류는 기존 ApiError의 409 CONFLICT + details.reason: STALE_VERSION, INVALID_STATE, SOURCE_CLAIMED, SOURCE_ALREADY_POSTED, SOURCE_ROUTE_CONFLICT, SOURCE_CHANGED, SOURCE_CANCELLED, INSUFFICIENT_AVAILABLE, QUARANTINE_NOT_RESERVABLE, SHIPMENT_MISMATCH. SOURCE_MODULE_DISABLED는 기존 409 코드 유지. 필드/수량 오류 422, 공간 밖 ID는 404. DB 유니크 충돌은 원천 재조회 후 기존 결과 또는409로 변환한다. 500으로 노출하지 않는다.

## 8. 인터페이스와 API 계약

ERP만 수정할 공개 조회 계약:

- `purchase_receipts` 반환은 유지. WMS에서 기존 item_unit_conversion으로 Decimal 환산 후 snapshot 생성. ERP 직접 SQL 금지.
- `confirmed_shipments`에 `shipmentOrderNo`와 줄 `lineNo`를 추가(기존 필드 유지). ERP 내부 JOIN으로 값을 제공한다.
- 새 `shipment_orders(scope)` → `[{shipmentOrderNo,status,lines:[{itemCode,qty,unit}]}]`, open/shipped/cancelled 상태 및 번호별 수요 대조용. 기존 ERP 출하지시 상태를 그대로 반환한다. 꺼짐 None, 범위 S 필터, 잠금/쓰기 없음.
- MES interface 및 MES 제품 쓰기 계약은 변경하지 않는다. 예약 확인은 위 ERP 계약 또는 WMS 자신의 원장만 사용한다.

모든 경로 아래 `/api/v1/wms`, 기존 응답 envelope/인증/CSRF/Idempotency-Key 사용. 신규 경로는 **설계이며 아직 존재하지 않는다.**

| 메서드/경로 | 요청 → 결과 |
|---|---|
| GET/POST /inbound-notices | 필터 status/warehouseId, 또는 `{businessKey,warehouseId,expectedOn,vehicleNo?,partnerRef?,lines:[{itemId,lotNo?,expectedQty,normalLocationId,quarantineLocationId?}]}` → 헤더/줄 |
| GET/PATCH /inbound-notices/{id} | 수정 `{expectedVersion,...편집값,lines}` 전체 줄 교체; PLANNED만 |
| POST /inbound-notices/{id}/source-link | `{expectedVersion,sourceKey}` → PLANNED/ARRIVED 선점 또는 INSPECTED 사후 대사(원장0) |
| POST /inbound-notices/{id}/source-unlink | `{expectedVersion,reason}` → CLAIMED만 해제 |
| POST /inbound-notices/{id}/arrive | `{expectedVersion}` → ARRIVED, arrivedAt |
| POST /inbound-notices/{id}/cancel | `{expectedVersion,reason}` → CANCELLED |
| POST /inbound-notices/{id}/inspect | `{expectedVersion,lines:[{lineId,acceptedQty,quarantinedQty,shortageQty,reason?}]}` → notice/documentId?/totals |
| GET/POST /reservations | 필터 status/itemCode 또는 `{businessKey,shipmentOrderRef?,reason?,lines:[{itemId,locationId,lotNo?,quantity}]}` → 묶음/배분 |
| GET /reservations/{id} | 상세·현재 부족·참고 출하지시 대조(조회 불가 별도) |
| POST /reservations/{id}/release | `{expectedVersion,reason}` → RELEASED |
| POST /reservations/{id}/consume-shipment | `{expectedVersion,sourceKey}` → CONSUMED/documentId/negativeWarnings |
| GET /reservation-sources | ERP 출하지시·확정 미반영 출하 후보, enabled 상태 |

목록 기본50/최대100, page/total 응답. 예정 최대100줄, 예약 최대100줄. 합계 정밀도/허용 길이 검증, version 정수>0. 기존 W-03 API에 noticeId·inspectionState·sourceCancelled 추가, 기존 documentId는 검수 전량 부족일 때 null임을 프런트에서 처리한다. 일괄 sync 결과에 deferred(검수 대기)/inspected(이미 검수) 수를 추가하며 미반영 성공 수로 세지 않는다. stock/dashboard, 위치 생성/수정 요청은 유형/예약 필드 확장. 기존 전표 API의 격리 이동 note 검증도 보강한다.

## 9. 도입·시드·수명주기

- migration 제안 revision `fs026a_wms_receiving_reservation`, 현재 down_revision `fs025b_bems_module`. 구현 직전 head를 재확인하고 다른 head가 생겼으면 조율한다. FS-024/025 migration 수정 금지.
- schema.json·DB설계서.xlsx·ERD·검증기 엔티티/정책/상태를 구현과 같은 작업에서 갱신한다. 이번 문서 단계에서는 실제 메타데이터와 산출물을 변경하지 않는다.
- 기존 운영 전표/위치/LOT/시드는 유지. 위치는 NORMAL 기본값, 신규 테이블은 빈 상태. 과거 전표를 검수 건으로 소급 변경하지 않는다.
- 새 템플릿에는 기존 5품목만 사용: R-Q01/F-Q01 격리 위치 각1개, 수동 PLANNED/ARRIVED/INSPECTED(95/3/2 KG 예시)/전량 부족/취소, 예약 ACTIVE/RELEASED/CONSUMED 예시. 기존 PI-0004/SH-0004 미반영 체험은 유지하고 이 원천을 사전 소진하지 않는다. 성공 소진 예시는 기존 다른 미반영 원천을 검증해 사용하거나 합성 ERP 원천을 해당 ERP 시드 소유 코드에서 추가한다. 알루미늄 품목 없음. 행 수는 생성 후 확정한다.
- 세대 복사: 부모 stock_document/마스터→notice→notice_line/source_claim→reservation→reservation_line 순으로 ID 매핑. 삭제는 역순, stock_document는 뒤에 삭제. 시간/expected_on·IN/RSV 번호 날짜를 기존 방식으로 이동하며 business_key/source_key 참조의 번호 치환도 함께 한다. 검수 source_key 내부 IN 번호 일치 필수. JSON snapshot confirmedAt도 동일 날짜 오프셋 적용 후 digest 재계산. 수량/단위 환산 값은 보존한다.
- 세대 초기화 후 이전 ID로 조회/쓰기는 거부한다. 모듈 끄기는 데이터 삭제 아님. 새로운 module_key나 workspace_module 행은 필요 없다.

## 10. 인수 기준 — AC-139~164 (설계, 미실행)

| AC | 입력/행동 | 기대 결과 |
|---|---|---|
| 139 | 기존 FS-024 DB→새 revision | 기존 원장·현재고 보존, 위치 NORMAL, 신규5테이블, 업무간 FK0 |
| 140 | 100 KG 예정→도착2회/새로고침 | 도착시각1개, 원장0, 서버 상태 복원 |
| 141 | 100→95합격/3격리/2부족 확정 | 정상+95/격리+3, 현재고98, 예약가능95 |
| 142 | 100→전량부족 확정·ERP sync 재시도 | INSPECTED/COMPLETED, 전표NULL·move0, 추가입고0 |
| 143 | 합계불일치·음수·정밀도초과·누락/중복줄 | 422, 상태/원장/claim 변화0 |
| 144 | 같은 ERP 원천 직접sync와 선점/검수 동시 | 별도 DB 연결의 실제 경합으로 단일 경로만 성공, 중복 증가0 |
| 145 | 선점 원천 일괄sync | 검수대기 안내, 다른 정상 원천은 기존처럼 처리 |
| 146 | 이미 직접 반영/유효 선점된 원천 연결 | 거부; 취소 후 해제된 선점만 재연결 가능 |
| 147 | 수동 기입고 사후 ERP 대사 | 예정 수량 일치·미반영만 연결, 원장0, 이후sync0 |
| 148 | 검수 전 ERP 취소/원천수량·환산변경 | 확정 보류; 해제/재연결 필요, 원장0 |
| 149 | 검수 후 ERP 취소 vs 직접반영 후 취소 | 검수는 경고만, 직접반영은 기존 되돌림1회 |
| 150 | BOX→EA/소수KG 연결·확정 | 환산snapshot 보존, 환산누락/자리수초과 거부 |
| 151 | 정상95에서 예약40, ERP 미출하40 | 예약가능55, ERP 수요 중복 차감0 |
| 152 | 정상95에 별도 연결로60씩 동시예약 | 한 묶음만 성공, 두번째 부족409 |
| 153 | 격리위치·완제품LOT누락·원자재LOT 예약 | 거부, 모든 줄 원자성 |
| 154 | 예약40 후 미예약출하70(정상95기준) | 원천반영 허용, 정상25/예약40/가용−15, 신규예약 거부 |
| 155 | 예약 해제/다른키 재해제 | 원장0, 가용1회복원, 해제사유 보존 |
| 156 | ERP 출하 전량 연결 예약 소진·재시도 | 단일 ERP_SHIPMENT와 CONSUMED, 차감1회 |
| 157 | 다른 출하키/수량/LOT/참고지시 불일치 | 연결 거부·부분 소진0; 기존 무연결sync 가능 |
| 158 | 기존sync와 예약소진 동시 | 출하전표1개. sync선행이면 예약유지/연결거부, 소진선행이면 기존전표반환 |
| 159 | 격리해제3 이동·유형변경 시도 | 정상+3/격리−3 총량불변, 사용된 위치 유형변경 거부 |
| 160 | ERP/MES/WMS 각각 비활성 | 소유경계 유지, 수동 WMS는 ERP 없이 동작, 연결 검증은 조회불가 |
| 161 | 다른 공간/이전세대 ID·원천 | 조회/쓰기 차단, 교차 SQL/import R6 검사0 |
| 162 | 게스트복사·초기화 | FK/날짜/번호/snapshot digest 정합, 기존 세대 오염0 |
| 163 | 360px/키보드/도착 통신실패 | 넘침없음·상태문구·포커스복귀, 서버 확인 전 도착성공 표시0 |
| 164 | 검수중 stale version·응답유실·영수증만료 | 충돌/재조회 안내, 기존 결과 재확인, 원장 중복0 |

AC-111~124도 회귀 확인한다. 114는 무연결 출하에 적용, 118은 직접 반영 매입에 적용, **123은 151/160으로 대체**, 117은 원천/기존 수동 전표에 유지하되 신규 예약은152 예외다. 테스트 수를 AC 개수와 동일하다고 주장하지 않는다.

## 11. 전체 설계 확인 체크

확인 대상: 이 revision의 5개 신규 테이블·수명주기/제약, ERP 조회 반환 확장, 원천 선점·전량부족·사후대사, 예약 전량 소진/음수 정책, [화면 revision 2](../../ui/화면설계_WMS_FS-026.md), AC-139~164. 승인 후 FS-026a(DB/명세/검증)부터 구현하고 단계별 보고한다. 구현·배포 승인으로 자동 확대하지 않는다.

## 12. FS-026a 구현 차분

- metadata v0.13.0, WMS11테이블(전체98), 새 revision fs026a_wms_receiving_reservation. 기존6테이블/원장 유지.
- coalesce LOT 유니크 표현은 같은 의미의 부분 유니크 인덱스 두 개(NULL / NOT NULL)로 구현해 기존 메타데이터·DDL 검증기와 호환한다. 0/NULL 검수 혼합 차단과 차이 사유는 DB CHECK로도 강제한다. 위치/품목·원천 간 검증은 SERVICE 정책이며 후속 API 구현 대상이다.
- 기존 전표 CHECK c620/c624의 허용 유형만 확장하고 기존 C/R 번호를 보존했다. 새 자료가 있는 downgrade는 오류로 중단하여 이력을 삭제하지 않는다.
- 이번 단계는 전용 로컬 테스트 DB에서 검증한다. 공유 개발 DB·운영 DB는 변경하지 않았다. 신규 업무 시드는 API/화면 후속 작업에서 추가한다.
