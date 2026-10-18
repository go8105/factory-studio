# DSN-13 WMS 보강 설계

작성: 2026-10-05 (Claude Code) · 상태: **설계 완료(2026-10-05) — 사용자 확인 대기.** 1단계(기준표·Q1~Q7 확정) + 2단계(3장 기능 규칙 · 4장 DB 23테이블 · 5장 화면 20 · 6장 교차 조회).
양식: [DSN-00](../../plan/기능기준표_DSN-00.md) · 방침: [ROADMAP-02](../../plan/전체설계우선_전환_ROADMAP-02.md) · 기존 설계: [FS-024](WMS_모듈설계_FS-024.md) · [FS-026](WMS_모듈설계_FS-026.md)
넘겨받은 계약: ERP(DSN-11) 발주 입고·수불·재고 조회, MES(DSN-12) 비계획 입출고·외주 반영, 자재 LOT·라인 재고 제공.

---

## 0. 지금 WMS와 경계

**지금(11테이블·9화면)**: 창고(용도 RAW·FG **각 1개 고정**)·위치(일반·격리 2종)·품목(RAW/FG, **LOT은 완제품만**)·단위 → 재고 전표/원장(기초·MES 입고·MES 투입·ERP 출하·ERP 매입·검수·조정·이동·역전표) → 입고 예정·도착·검수(ERP 매입 선점) → 출고 예약·소진. 현재고 = 확정 원장 합계. 3D 공장에 트럭 도착.

| 영역 | 소유 | WMS와의 관계 |
|---|---|---|
| 재고 수량·위치·LOT | **WMS** (FS-024 D13, ERP Q1) | 모든 솔루션이 읽기만 |
| 발주·매입·반품 문서 | **ERP** | WMS는 발주를 읽어 입고 예정, ERP는 WMS 입고 확정을 읽어 매입(ERP Q4) |
| 생산 투입·비계획 입출고·완제품 입고·외주 | **MES** 기록 | WMS가 읽어 재고 반영(MES Q2) |
| 수입 검사 판정 | **QMS**(DSN-14) | 지금 WMS 검수는 수량 검수. 품질 판정 연계는 QMS 설계에서 |
| 현장 스캔 단말 | **POP**(Q1 확정) | 입고·적치·피킹·불출·실사 스캔은 POP, WMS는 가져와 재검증. POP = 생산 + 창고 현장 단말 |
| 운송·배차 | **TMS**(신규) | WMS는 출하 확정까지 |

## 1. 기준표

수준·지금·범위 표기는 DSN-00. 범위는 제안이고 질문으로 확정한다.

### 영역 01 — 창고·위치·품목 기준

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F01 | 창고 등록 | 필수 | △ | ○ | 용도 RAW·FG 각 1개 고정 → Q2 |
| WMS-F02 | 창고 용도 확장(원자재·반제품·완제품·상품·라인·외주·불량·반품) | 필수 | ✗ | ○ | Q2 |
| WMS-F03 | 위치 계층(구역·랙·단·칸)·위치 유형(일반·격리·라인·입고장·출고장·반품) | 필수 | △ | ○ | 지금 일반·격리 2종, 계층 없음 |
| WMS-F04 | 위치 용량·혼적 허용(품목·LOT 혼적) | 표준 | ✗ | ○ | 적치 추천(F14)의 기준 |
| WMS-F05 | 품목 기본·단위 환산 | 필수 | ✓ | ○ | W-07 |
| WMS-F06 | 품목 관리 속성(품목별 LOT 관리·유효기간·보관 조건·안전/최대 재고·ABC 등급) | 필수 | △ | ○ | LOT이 완제품 고정 → Q3 |
| WMS-F07 | 위치 라벨(바코드) 출력 | 표준 | ✗ | ○ | 스캔 적치·피킹의 대상 |

### 영역 11 — 입고

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F11 | 입고 예정·도착·검수(정상·격리·부족) | 필수 | ✓ | ○ | W-08 (FS-026) |
| WMS-F12 | 발주 기반 입고 예정(ERP 발주 확정 → 예정) | 필수 | ✗ | ○ | ERP Q4. 지금은 매입 전표 선점만 |
| WMS-F13 | 입고 LOT 부여·자재 LOT 라벨 출력 | 필수 | ✗ | ○ | MES Q4의 전제(자재 LOT 번호) |
| WMS-F14 | 적치(입고장 → 보관 위치, 위치 추천) | 표준 | ✗ | ○ | F04 |
| WMS-F15 | 반품 입고(판매 반품 실물, 검사 후 정상/불량) | 필수 | ✗ | ○ | ERP 판매 반품(F16) |
| WMS-F16 | MES 완제품 입고 반영 | 필수 | ✓ | ○ | W-03 |
| WMS-F17 | 외주 입고·출고 반영 | 표준 | ✗ | ○ | MES 외주(F82) |
| WMS-F18 | 수입 검사 연계(QMS 판정 → 격리 해제/불량) | 표준 | △ | Q | 지금 수량 검수만. DSN-14에서 확정 |

### 영역 21 — 출고

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F21 | 출고 예약(출하지시 기준)·소진 | 필수 | ✓ | ○ | W-09 |
| WMS-F22 | 피킹 지시(위치 순서 피킹 리스트) | 필수 | ✗ | ○ | Q4 |
| WMS-F23 | 피킹 확정·출하 검수(수량·LOT 확인) | 필수 | ✗ | ○ | Q4 |
| WMS-F24 | ERP 출하 반영 | 필수 | ✓ | ○ | |
| WMS-F25 | 생산 불출(작업지시 소요 → 라인 위치 이동) | 필수 | ✗ | ○ | Q4. MES 투입은 라인 재고에서 차감 |
| WMS-F26 | 구매 반품 출고 | 필수 | ✗ | ○ | ERP 구매 반품(F25) |
| WMS-F27 | 선입선출·유효기간 우선(FEFO) 피킹 | 표준 | ✗ | ○ | Q5 |
| WMS-F28 | 웨이브·배치 피킹 | 고급 | ✗ | ✕ | |

### 영역 31 — 재고 관리

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F31 | 현재고(품목·위치·LOT) | 필수 | ✓ | ○ | W-02 |
| WMS-F32 | 재고 원장 | 필수 | ✓ | ○ | W-05 |
| WMS-F33 | 재고 조정(사유) | 필수 | ✓ | ○ | W-04 |
| WMS-F34 | 재고 이동(창고·위치 간) | 필수 | ✓ | ○ | W-04 |
| WMS-F35 | 재고 실사(실사 지시 → 카운트 → 차이 조정, 전수·순환) | 필수 | △ | ○ | 지금 조정 사유 COUNT만 |
| WMS-F36 | 유효기간 관리(만료 임박·만료 재고 보류) | 표준 | ✗ | ○ | Q5 |
| WMS-F37 | 안전재고 부족·최대재고 초과 경고 | 표준 | ✗ | ○ | F06 |
| WMS-F38 | 재고 보류(QMS 보류·수동 보류 → 출고 불가) | 필수 | △ | ○ | 격리 위치만 있음 |
| WMS-F39 | 재고 월 마감(마감 월 전표 금지, ERP 원가의 기준) | 필수 | ✗ | ○ | ERP F35 재고자산 평가 |

### 영역 41 — 연계 반영 (다른 솔루션 기록 → 재고)

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F41 | MES 자재 투입 반영 | 필수 | ✓ | ○ | 라인 위치에서 차감으로 변경(F25) |
| WMS-F42 | MES 비계획 입출고·폐기 반영 | 필수 | ✗ | ○ | MES Q2 |
| WMS-F43 | ERP 발주 입고 → 매입 원천 제공 | 필수 | ✗ | ○ | ERP Q4 `receipts` |
| WMS-F44 | 원천 반영 현황(미반영·실패·재시도) | 표준 | ✓ | ○ | W-03 |

### 영역 51 — 현황·분석

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| WMS-F51 | 대시보드 | 필수 | ✓ | ○ | W-01 |
| WMS-F52 | 재고 수불부(기간 기초·입고·출고·기말, 품목·창고별) | 필수 | △ | ○ | 원장은 있으나 기간 집계 화면 없음. ERP F35 입력 |
| WMS-F53 | LOT 이력(입고 → 이동 → 투입·출하) | 필수 | △ | ○ | MES LOT 추적과 연결 |
| WMS-F54 | 재고 회전율·장기 체화 재고 | 표준 | ✗ | ○ | |
| WMS-F55 | 위치 점유 현황 | 표준 | ✗ | ○ | F04 |
| WMS-F56 | 3D 창고 위치 시각화 | 고급 | △ | ✕ | 3D 공장 트럭은 유지, 위치 3D는 제외 |

## 2. 갭 요약

| 영역 | 기능 | ✓ | △ | ✗ | 범위 ○ (제안) | Q | ✕ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01 창고·위치·품목 | 7 | 1 | 3 | 3 | 7 | 0 | 0 |
| 11 입고 | 8 | 2 | 1 | 5 | 7 | 1 | 0 |
| 21 출고 | 8 | 2 | 0 | 6 | 7 | 0 | 1 |
| 31 재고 관리 | 9 | 4 | 2 | 3 | 9 | 0 | 0 |
| 41 연계 반영 | 4 | 2 | 0 | 2 | 4 | 0 | 0 |
| 51 현황·분석 | 6 | 1 | 3 | 2 | 5 | 0 | 1 |
| **합계** | **42** | **12** | **9** | **21** | **39** | **1** | **2** |

**요지**: 입고 검수·예약 같은 "문서 흐름"은 FS-026으로 생겼지만, **창고 구조(다창고·위치 계층)·원자재 LOT·피킹·생산 불출·실사·마감**이 없다. 특히 원자재 LOT과 라인 위치가 없으면 MES 오투입 방지·역추적(DSN-12 Q4)과 ERP 원가(DSN-11 F35)가 성립하지 않는다. 확정 범위 39, 테이블 11 → **23**(4장).

## 3. 기능 규칙 (범위 39 중 신규·보강 27)

공통: **현재고는 확정 원장(stock_move) 합계** — 잔량 테이블을 두지 않는다(FS-024). 모든 재고 변동은 전표 1건 + 이동 행, 확정 후 불변, 정정은 역전표. **마감 월(Q6) 전표 금지.** 스캔 입력은 POP 확정분을 가져와 같은 규칙으로 재검증(Q1).

| 묶음 | 기능 ID | 규칙 |
|---|---|---|
| 창고 구조 (Q2) | F01~F04·F07 | 다창고(용도 8: 원자재·반제품·완제품·상품·라인·외주·불량·반품), 용도당 기본 창고 1개. 위치 계층 구역 > 랙 > 단 > 칸(전표는 칸에만), 유형 6(일반·격리·라인·입고장·출고장·반품), 용량·품목/LOT 혼적 여부. 위치 라벨(Code128) |
| 품목 (Q3·Q5) | F06 | LOT 관리는 품목별. 유효기간 일수·보관 조건·안전/최대 재고·ABC 등급 |
| 입고 (Q3) | F11~F13·F15·F17 | 입고 예정 종류 4(매입·**발주**·**판매 반품**·외주). 검수 때 LOT 관리 품목은 **WMS가 LOT 번호 부여**(LOT 마스터 생성: 입고일·유효기간 = 입고일 + 일수·공급처 LOT) + 자재 LOT 라벨. 수량은 입고장 위치로. 반품 입고는 검사 후 정상/불량 위치 |
| 적치 | F14 | 입고 전표마다 적치 작업. 추천 위치 = 같은 품목·LOT이 있는 칸 → 용량 남은 칸(혼적 규칙). 완료 = PUTAWAY 이동 전표(입고장 → 칸) |
| 출고 (Q4·Q5) | F21~F23·F27 | 예약 → **피킹 지시(예약당 1건, 위치 순서, LOT 배정 FEFO → FIFO, 보류·만료 LOT 제외)** → **피킹 확정(PICK: 칸 → 출고장)** → ERP 출하 반영은 출고장 재고에서 차감 |
| 생산 불출 (Q4) | F25·F41 | MES 작업지시 소요(코드 스냅샷) 또는 수동 → 불출 요청 → PRODUCTION_ISSUE(창고 → 라인 위치). **MES 자재 투입(MES_ISSUE)은 라인 위치 재고에서 차감**, 모자라면 반영 실패로 원천 반영 현황에 남음 |
| 반품 출고 | F26 | ERP 구매 반품 확정을 읽어 ERP_PURCHASE_RETURN 출고 |
| 실사 | F35 | 전수·순환. 시작 시 장부 수량 스냅샷, 진행 중 대상 위치 이동 금지(실사 잠금). 차이 행만 CYCLE_COUNT 조정 전표 |
| LOT·보류 (Q5) | F36·F38 | LOT 상태: 사용 가능·보류(활성 보류 1건: 수동·QMS 보류 조회·만료)·만료. 만료 임박(기본 30일) 경고. 보류·만료 LOT은 예약·피킹·불출 불가 |
| 경고 | F37 | 품목 합계 < 안전 재고 → 부족, > 최대 재고 → 초과(조회 계산) |
| 마감 (Q6) | F39 | 재고 월 마감 → ERP 원가 계산(마감 월 수불 기준) → ERP 회계 마감. 마감 후 차이는 다음 달 조정 |
| 연계 반영 | F42·F43 | MES 비계획 입출고·폐기·외주 출고/입고를 읽어 전표(MES_ADJUST·MES_SUBCONTRACT, 원천 1건당 1건). 발주 입고 검수 확정분을 `receipts()`로 ERP에 제공(ERP가 PO_RECEIPT 매입 생성) |
| 현황 | F52~F55 | 수불부(기간 기초·입고·출고·기말, 품목·창고·LOT별), LOT 이력(입고 → 이동 → 투입·출하, MES LOT 추적과 연결), 회전율·장기 체화(마지막 출고 후 90일), 위치 점유율(용량 대비) |

## 4. DB

목표 파일 `schema-target.json`(`tools/apply_dsn13.py`, apply_dsn12 다음, 멱등. 바꿀 기존 제약을 못 찾으면 실패). WMS 11 → **23테이블**. LOT·위치의 수량은 저장하지 않는다(원장 합계). 다른 업무 스키마로 FK 없음(MES 작업지시·QMS 보류는 코드 스냅샷).

### 4-1. 새 테이블 (12)

| 테이블 | 한글명 | 영역 | 목적·규칙 |
|---|---|---|---|
| `wms.lot` | LOT | LOT | F13·F36·F53(Q3·Q5). 품목·LOT 속성(입고일·유효기간·공급처 LOT). 수량은 원장 합계(저장 안 함) |
| `wms.lot_hold` | LOT 보류 | LOT | F36·F38. 보류·해제 이력. QMS 보류는 조회로 받아 기록, 만료는 자동 |
| `wms.putaway_task` | 적치 작업 | 입고 | F14. 입고장 → 보관 위치. 추천 위치는 용량·혼적 기준, 실제 위치는 POP 스캔 또는 수동 |
| `wms.pick_order` | 피킹 지시 | 출고 | F22·F23(Q4). 출고 예약 1건당 피킹 1건. 확정 시 출고장 위치로 이동(PICK) |
| `wms.pick_line` | 피킹 명세 | 출고 | F22·F27. 위치 순서·FEFO→FIFO로 LOT 배정, 피킹 수량은 POP 스캔 또는 수동 |
| `wms.issue_request` | 생산 불출 요청 | 출고 | F25(Q4). MES 작업지시 소요(코드 스냅샷) → 라인 위치로 이동(PRODUCTION_ISSUE). MES 투입은 라인 재고에서 차감 |
| `wms.issue_request_line` | 생산 불출 명세 | 출고 | F25 |
| `wms.count_order` | 재고 실사 | 실사 | F35. 전수·순환. 시작 시 장부 수량 스냅샷, 차이는 CYCLE_COUNT 조정 전표 |
| `wms.count_line` | 실사 명세 | 실사 | F35. 차이 = 실사 − 장부(저장 안 함) |
| `wms.stock_period` | 재고 기간 | 마감 | F39(Q6). 마감 월 재고 전표 금지. ERP 원가는 마감 월 수불을 기준 |
| `wms.pop_import` | POP 가져오기 | POP 연계 | Q1. POP 창고 스캔 확정 입력 1건당 1행(멱등). 적용 또는 거부 |
| `wms.label_print` | 라벨 출력 | 라벨 | F07·F13. 위치 라벨·자재 LOT 라벨(Code128, 브라우저 인쇄 — MES Q3와 같음) |

### 4-2. 기존 테이블 변경 (6)

| 테이블 | 변경 | 이유 |
|---|---|---|
| wms.warehouse | + is_default. 용도 RAW·FG → 8종, "용도당 활성 1개" → "용도당 기본 1개" | Q2 다창고 |
| wms.storage_location | + parent_location_id, level_kind, capacity_qty, mix_items, mix_lots. 유형 2 → 6 | F03·F04 위치 계층·용량·혼적 |
| wms.item | + shelf_life_days, storage_condition, safety_stock, max_stock, abc_class. 구분 RAW·FG → 5종, **"LOT = 완제품" CHECK 삭제** | Q3·Q5·F06 |
| wms.inbound_notice | + notice_kind(매입·발주·판매 반품·외주) | F12·F15·F17 |
| wms.stock_document | 종류 9 → 17(MES 비계획·외주, ERP 판매/구매 반품, 생산 불출, 적치, 피킹, 실사) | F15·F25·F26·F35·F42 |
| wms.source_claim | 원천 키 `ERP:PURCHASE:` → `ERP:(PURCHASE\|PO\|SALES_RETURN):` | ERP Q4 발주 입고·판매 반품 |

## 5. 화면 목록

패턴 D·L·S·W. 기존 W-01~09 유지, W-10부터. 스캔 화면은 POP(Q1). 특수 화면 없음(3D 트럭은 기존 3D 공장 화면).

| 화면 | 이름 | 패턴 | 주 테이블 | 기능 ID | 지금 |
|---|---|---|---|---|---|
| W-01 | 대시보드 | D | (조회) | F51 | 있음 → 만료 임박·안전재고·피킹 대기 카드 |
| W-02 | 재고 현황 | L | (원장 합계)·lot | F31·F37 | 보강: LOT 상태·유효기간·안전재고 표시 |
| W-03 | 원천 반영 | L | stock_document | F16·F24·F41~F44 | 보강: MES 비계획·외주, ERP 반품 |
| W-04 | 재고 전표 | L+FormPanel wide | stock_document·stock_move | F33·F34 | 있음 |
| W-05 | 재고 원장 | L | stock_move | F32 | 있음 |
| W-06 | 창고·위치 | S(트리) | warehouse·storage_location | F01~F04 | 보강: 다창고·계층·용량 |
| W-07 | 품목·단위 | S | item | F05·F06 | 보강: LOT·유효기간·안전재고 |
| W-08 | 입고 예정·검수 | L+DetailPanel wide | inbound_notice | F11~F13·F15·F17 | 보강: 발주·반품·외주 종류, LOT 부여 |
| W-09 | 출고 예약 | L+DetailPanel | stock_reservation | F21 | 보강: 피킹 지시 연결 |
| W-10 | LOT·보류 | L+DetailPanel | lot·lot_hold | F36·F38·F53 | 신규(LOT 이력 포함) |
| W-11 | 적치 | L+FormPanel | putaway_task | F14 | 신규 |
| W-12 | 피킹 | L+DetailPanel wide | pick_order·pick_line | F22·F23·F27 | 신규(피킹 리스트 인쇄) |
| W-13 | 생산 불출 | L+DetailPanel | issue_request·issue_request_line | F25 | 신규 |
| W-14 | 재고 실사 | L+DetailPanel wide | count_order·count_line | F35 | 신규 |
| W-15 | 재고 마감 | L+FormPanel | stock_period | F39 | 신규 |
| W-16 | POP 가져오기 현황 | L | pop_import | Q1 | 신규 |
| W-17 | 라벨 출력 | L+FormPanel | label_print | F07·F13 | 신규 |
| W-18 | 재고 수불부 | L(조회) | (조회) | F52 | 신규 |
| W-19 | 재고 분석(회전율·체화·안전재고) | L(조회) | (조회) | F37·F54 | 신규 |
| W-20 | 위치 점유 | L(조회) | (조회) | F55 | 신규 |

화면 수: 9 → **20**(신규 11).

## 6. 교차 조회

**WMS가 읽는 것**

| 제공 | 함수 | WMS 용도 |
|---|---|---|
| POP | `confirmed_entries(since)` 창고 입력(입고·적치·피킹·불출·실사·이동) | Q1 가져오기 |
| ERP | `purchase_orders(open=True)` (DSN-11) · 기존 `purchase_receipts`·`confirmed_shipments`·`open_shipment_qty` · 판매/구매 반품 확정 `returns()` | F12 발주 입고 예정, F15·F26 반품 |
| MES | `material_adjustments()`·`subcontract_results()`·`material_shortages()`(DSN-12) · 기존 `finished_goods_receipts`·`completed_material_issues` | F42 반영, F25 불출 요청 원천 |
| QMS | `held_lot_nos()` (있음) | F38 보류 |

**WMS가 제공하는 것** (DSN-11·12에서 요청받은 계약 확정)

| 함수 | 돌려주는 것 | 쓰는 곳 |
|---|---|---|
| `receipts(period)` | 확정 입고 명세(발주 번호·품목·LOT·수량·검수일) | ERP PO_RECEIPT 매입(Q4) |
| `stock_moves(month)` | **마감 월** 수불(품목별 기초·입고·출고, 출처 구분) | ERP 재고자산 평가(F35) |
| `stock_on_hand(items)` | 품목별 가용 재고(보류·만료 제외) | ERP 재고 현황(F31), MES 소요 계산(F23) |
| `lots(item)` | LOT·입고일·유효기간·상태 | MES 선입선출 경고(F47), 오투입 검증 |
| `line_stock(location)` | 라인 위치 재고 | MES 라인 재고(F46) |
| `pop_context(barcode)` | 위치·LOT 바코드의 대상과 허용 동작 | POP 창고 스캔 |

> 넘길 것: **POP(신규)** 창고 스캔 원장·`confirmed_entries` 창고 종류 · **QMS(DSN-14)** 수입 검사 판정 → 격리 해제/불량(F18) · **TMS(신규)** 출고장 피킹 완료 → 배차.

> POP DSN-22 반영(2026-10-05): 가져오기 종류에 CANCEL 추가, WMS는 `pop_results(entry_nos)`·`pending_tasks(location)`도 제공한다.

> TMS DSN-23 반영(2026-10-05): 조달 운송은 TMS 소관 — 입고 예정의 차량·도착은 TMS `inbound_arrivals`를 읽어 채운다(수동 유지). WMS는 `picked_shipments`·`inbound_notices(open=True)`를 제공한다.

> PLM DSN-24 반영(2026-10-05): WMS 품목은 "PLM에서 가져오기" 가능. `plm_imports`를 제공한다.

> SCM DSN-26 반영(2026-10-05): WMS는 SCM `inventory_policies()`를 가져와 품목 안전재고에 반영한다(제안 → 사람이 반영).

> ELB DSN-27 반영(2026-10-05): ELB 재고 품목의 입고 상태를 위해 `inbound_status(item_codes, refs)`를 제공한다.

## 7. 결정 질문 (하나씩)

| # | 질문 | 제안 |
|---|---|---|
| Q1 | **창고 스캔(입고·적치·피킹·실사)을 어디에 두는가** — (a) POP(MES와 같이 현장 단말 한곳) (b) WMS 안 휴대 단말 화면 | **(a) POP** — MES Q1과 같은 원칙(스캔 원장은 POP, WMS는 가져와 재검증). POP 설계 범위가 "생산 + 창고 현장 단말"이 된다 |
| Q2 | **창고 구조** — 용도별 1개 고정을 풀고 다창고·용도 8종·위치 계층(구역·랙·단·칸) | 푼다. 용도당 기본 창고 1개만 유지 |
| Q3 | **LOT 관리를 품목별 설정**으로(원자재도 LOT, 입고 때 WMS가 부여) | 그렇게 한다(MES Q4 전제) |
| Q4 | **출고 단계** — 예약 → **피킹 지시 → 피킹 확정** → 출하, **생산 불출**(작업지시 소요 → 라인 위치) 추가 | 추가 |
| Q5 | **유효기간·선입선출** — 품목별 유효기간, 만료 임박 경고, 만료 자동 보류, 피킹은 FEFO(유효기간) → FIFO(입고일) | 그렇게 한다 |
| Q6 | **재고 월 마감** — 마감 월에는 재고 전표 금지, ERP 원가 계산은 마감 월 수불을 기준 | 그렇게 한다 |
| Q7 | 범위 확정 — 포함 39 + Q 1(수입 검사, DSN-14로 넘김), 제외 2(웨이브 피킹·위치 3D) | 제안대로 |

### 7-1. 결정 기록 (2026-10-05 사용자 확정, 하나씩)

| # | 결정 |
|---|---|
| Q1 | **창고 스캔은 POP**(MES와 같은 원칙). WMS는 POP 확정 입력을 가져와 재검증 |
| Q2 | **다창고·용도 8종·위치 계층(구역·랙·단·칸)·유형 6종**, 용도당 기본 창고 1개 |
| Q3 | **LOT 관리 품목별**, 원자재도 입고 검수 때 WMS가 LOT 부여 + 자재 LOT 라벨 |
| Q4 | **예약 → 피킹 지시 → 피킹 확정 → 출하, 생산 불출(라인 위치) 추가** |
| Q5 | **FEFO → FIFO, 만료 임박 경고·만료 자동 보류** |
| Q6 | **재고 월 마감**(마감 월 전표 금지, ERP 원가의 기준) |
| Q7 | **범위 제안대로**(포함 39, 수입 검사 연계는 DSN-14, 제외 2) |

## 8. 구현 및 스키마 반영 메모 (W2b-1a / WMS-FIX)

- **설계 재현 스크립트(`apply_dsn90.py`) 재적용 제약**: `apply_dsn90.py`는 재적용하면 `CMMS_ISSUE`가 중복된다(문자열 치환이 멱등하지 않다). 설계 단계 스크립트라 지금은 영향이 없지만, 다시 돌릴 일이 생기면 먼저 고친다.
- **기존 WMS 3표 칼럼 순서**: `apply_w2b1.py` 적용 시 기존 WMS 3표(`wms.warehouse`, `wms.item`, `wms.inbound_notice`)의 확장 칼럼이 `created_at` 뒤에 추가되어 `schema-target.json`과 칼럼 배열 순서 차이가 있으나, DDL 대조 0건이므로 기능 및 스키마 무결성에 영향이 없다.
- **적치 위치 흐름 및 검증 완화 (W2b-1c / C-3a)**: 설계는 입고장 경유((a) 입고 예정 정상 위치 = 입고장 `RECEIVING` → 검수 확정 → 적치 작업 `PUTAWAY` → 보관 위치 `NORMAL`)이나, 기존 데이터(60건) 및 테스트를 보호하기 위해 `_validate_lines` 검증을 교체하지 않고 `location_type IN ('NORMAL', 'RECEIVING')`으로 완화했다. 기존 60건은 `NORMAL` 직입고로 남으며, 신규 등록 시 창고의 `RECEIVING` 입고장 위치가 기본 선택된다.
- **적치 작업 생성 및 동적 위치 추천 (W2b-1c / C-3)**:
  - 검수 확정 시 합격 수량(`accepted_qty > 0`)이 있는 명세마다 `wms.putaway_task`를 `status = 'OPEN'`, `suggested_location_id = NULL`로 자동 생성한다(검수 트랜잭션의 무거운 용량·혼적 계산 방지 및 멱등성 유지).
  - 추천 위치는 W-11 적치 목록 조회 시(`GET /api/v1/wms/putaway-tasks`) CTE 쿼리를 통해 실시간 동적으로 산출한다.
  - 후보 위치 필터: 동일 창고 · `is_active` · `location_type = 'NORMAL'` · `level_kind = 'BIN'` (출발 칸 제외).
  - 제외 조건: 용량 초과(`현재고 + 적치수량 > capacity_qty`), 다른 품목 혼적 불가(`mix_items = false`), 다른 LOT 혼적 불가(`mix_lots = false`).
  - 우선순위: 1순위(동일 품목+동일 LOT) → 2순위(동일 품목) → 3순위(빈 칸) → 4순위(혼적 허용 칸) → 없으면 추천 없음(NULL).
  - 화면: W-11 적치 목록 화면(`frontend/src/wms/Putaways.tsx`) 신규 연결, 상태 배지(대기/완료/취소) 및 상세 패널 표시.
- **적치 완료·취소 및 `PUTAWAY` 전표 반영 (W2b-1c / C-4)**:
  - 적치 완료(`POST /api/v1/wms/putaway-tasks/{id}/complete`): `FOR UPDATE` 행 잠금 후 `status != 'OPEN'`이면 409(`INVALID_STATE`)로 차단한다. 목적지 위치가 같은 창고의 활성 `NORMAL` 칸(출발 칸 제외)인지 검증(위반 시 400)한 뒤, 단일 트랜잭션(`base._action`) 안에서 `PUTAWAY` 재고 전표(`wms.stock_document`, `status = 'posted'`, `source_key = NULL`[`c624_check`], `source_ref = task_no`)와 이동 2줄(`from_location_id` `-qty`, `to_location_id` `+qty`)을 생성하고, `c1480_check`(`(status = 'DONE') = (done_at IS NOT NULL AND to_location_id IS NOT NULL)`)를 만족하도록 한 `UPDATE` 문에서 `status = 'DONE'`, `to_location_id`, `done_at`, `stock_document_id`를 갱신한다.
  - 적치 취소(`POST /api/v1/wms/putaway-tasks/{id}/cancel`): `FOR UPDATE` 잠금 후 `status != 'OPEN'`이면 409로 차단하고, 한 `UPDATE` 문에서 `status = 'CANCELLED'`, `to_location_id = NULL`, `done_at = NULL`, `stock_document_id = NULL`로 갱신한다(재고 전표 미생성).
  - 대시보드 집계(`service.py::dashboard`): 월별 입출고 흐름 집계에서 내부 위치 이동인 `'PUTAWAY'`와 `'PICK'`을 `'TRANSFER'`와 함께 제외(`d.document_type NOT IN ('TRANSFER', 'PUTAWAY', 'PICK')`)한다.
- **피킹 지시 생성 및 FEFO/FIFO LOT 배정 (W2b-1d / D-1)**:
  - 출고 예약(`wms.stock_reservation`, `ACTIVE`) 1건당 피킹 지시(`wms.pick_order`) 1건을 생성(`POST /api/v1/wms/pick-orders`, 발번 `PK-YYYYMMDD-NNN`)한다.
  - `c1482`(`UNIQUE (workspace_id, generation_id, reservation_id)`)가 조건부 인덱스가 아닌 무조건부 UNIQUE 제약이므로, 취소(`CANCELLED`)된 피킹 지시가 있는 예약에서 재생성할 때는 기존 `pick_order` 행을 `OPEN`으로 재개(`picked_at = NULL, stock_document_id = NULL, cancel_reason = NULL`)하고 `wms.pick_line`을 다시 구성한다.
  - LOT 배정(`c1486`): `wms.stock_move` 잔량 집계에 `wms.lot`을 `LEFT JOIN`하여 마스터 행이 없는 시드 LOT(`LT-0001`~`LT-0012`)도 누락 없이 포함하고, 보류(`wms.lot_hold` 활성·`qms.held_lot_nos`·`wms.lot.status = 'HOLD'`) 및 만료(`expiry_date < business_today()`·`status = 'EXPIRED'`) LOT을 배정에서 제외한다.
  - 예약 줄(`wms.stock_reservation_line`)에 LOT이 지정되어 있고 가용하면 그대로 존중하며, 보류·만료로 사용할 수 없거나 가용 수량이 부족할 때만 `expiry_date ASC NULLS LAST → received_on ASC NULLS LAST → lot_no ASC NULLS LAST → loc.code ASC`(FEFO → FIFO) 순으로 배정하고 대체 사유(`lotSubstitutions`)를 반환한다. 가용 재고 합계가 부족하면 `409 INSUFFICIENT_AVAILABLE`로 거절한다.
  - 배정된 명세는 위치 코드(`storage_location.code ASC`) 순으로 `sequence_no = 1..N`을 부여하며, `inventory.py`에서 `SHIPPING`(출고장) 위치 재고도 `normalOnHand`로 인정한다.
- **W-12 피킹 목록·상세 화면 및 동선 명세 (W2b-1d / D-2)**:
  - 화면: W-12 피킹 화면(`frontend/src/wms/Picks.tsx`) 신규 생성 및 WMS 라우트(`picks`) 연결.
  - 메뉴: `backend/src/fs/core/menu_catalog.json`에 `W-12` 피킹 등록(`group: "입출고"`, 전체 메뉴 116개).
  - 목록: 서버 필터(`status`, `warehouseId`, `reservationId`, `itemCode`) 및 페이지네이션(`pageSize = 50`), 상태 배지(`대기`, `피킹 완료`, `취소`), `LOT 대체 N건` 배지 표시.
  - 상세 패널:
    - 피킹 동선 명세: `sequenceNo` 오름차순(위치 코드 순) 정렬하여 동선 순서(`#1`, `#2`), 위치 코드·이름, 품목, LOT·유효기간, 지시 수량을 `.table-scroll` 테이블에 렌더링(390px 모바일 화면 가로 오버플로 없음).
    - LOT 대체 안내: `lotSubstitutions`가 있을 때 대체 사유(`HOLD`, `QMS_HOLD`, `EXPIRED`, `SHORTAGE`), 요청 LOT 및 위치, 배정된 대체 LOT 목록과 사유 메시지 표시.
    - 도착 위치 선택(W-11 패턴): 상세 진입 시 해당 창고의 위치를 1회 조회하여 `SHIPPING`(출고장)과 `NORMAL`(보관) 칸으로 분리. `SHIPPING` 칸이 있으면 첫 번째 출고장 칸을 기본 선택(`toLocationId`)하고, 없으면 빈 선택값과 함께 `"출고장 칸이 없어 보관 칸으로 이동합니다. W-06에서 출고장을 만들 수 있습니다."` 안내 문구 표시.
- **W-12 피킹 확정·취소 API 및 유효 현재 위치 도출 (W2b-1d / D-3)**:
  - 피킹 확정 API (`POST /api/v1/wms/pick-orders/{id}/confirm`): `toLocationId` 및 명세별 `pickedQty`(기본값 지시 수량)를 받아 한 트랜잭션에서 `wms.pick_line.picked_qty` 기록, `PICK` 재고 이동 전표(`status='posted'`, `source_key=NULL`, `source_ref=pick_no`, 출발 -picked / 도착 +picked) 생성, `pick_order.status='PICKED'`, `picked_at=now`, `stock_document_id=doc_id` 갱신. 부분 피킹 허용(`picked_qty = 0`이면 전표 미생성, 1개 이상 양수 필수).
  - 피킹 취소 API (`POST /api/v1/wms/pick-orders/{id}/cancel`): `cancelReason`(1~300자) 입력 필수. `status='CANCELLED'`, `picked_at=NULL`, `stock_document_id=NULL`, `cancel_reason` 기록. 취소 후 동일 예약에서 재요청 시 `OPEN`으로 재개(c1482) 지원.
  - 유효 현재 위치 도출: `wms.stock_reservation_line`은 변경하지 않고, 피킹 전(미지시/OPEN/CANCELLED)에는 원래 `(location_id, lot_no, qty)`, 피킹 후(PICKED)에는 도착 칸 `(to_location_id, lot_no, picked_qty)` + 미피킹 잔량 `(location_id, lot_no, qty - picked_qty)`을 유효 현재 위치로 도출.
    - `inventory.py`: amounts CTE의 `reserved_qty` 집계에 적용하여 보관 칸 음수 재고 방지.
    - `reservations.py`: `consume`, `shipment_preview`, `_detail`, `list_reservations`에 적용하여 ERP 출하 소진 시 출고장 칸에서 차감(보관 칸 이중 차감 방지) 및 확정 후 W-09 예약 목록에 거짓 부족 경보(reservationShortage) 방지.
  - 화면 연계 (`frontend/src/wms/Picks.tsx`): OPEN 상세에서 명세별 피킹 수량 입력 필드 제공, 피킹 확정 및 피킹 취소(사유 필수) 폼 연계. PICKED 상세에서 도착 위치(`toLocationCode · toLocationName`), 확정 시각, 생성된 PICK 전표 링크 노출. CANCELLED 상세에서 취소 사유 노출. 390px 반응형 검증 통과.
- **W-09 출고 예약 피킹 상태 연계 및 완제품 예약 규칙 정규화 (W2b-1d / D-4)**:
  - **피킹 상태 연계 및 목록 N+1 방지**:
    - 예약 목록 조회(`GET /api/v1/wms/reservations`) 시 `wms.pick_order`를 `LEFT JOIN`하여 단일 쿼리로 `pickOrderId`, `pickOrderNo`, `pickOrderStatus`(`OPEN`='대기', `PICKED`='피킹 완료', `CANCELLED`='취소', 미지시=null)를 묶음 반환. N+1 쿼리 없음.
    - 예약 상세(`_detail`)에서도 해당 예약에 바인딩된 최신 피킹 지시 정보를 조회하여 반환.
  - **예약 상세에서 피킹 지시 생성 및 오류 상세 안내**:
    - `ACTIVE` 상태이면서 피킹 지시가 없거나(`미지시`) 취소(`CANCELLED`)된 예약 상세 화면에서 "피킹 지시 생성" 버튼 노출.
    - 이미 `OPEN` 또는 `PICKED` 상태인 피킹 지시가 존재하면 중복 지시 생성 버튼 숨김.
    - 지시 생성 성공 시 알림 및 W-12 화면 링크(`/wms/picks?open={id}`) 제공.
    - 피킹 지시 생성 실패(`409 INSUFFICIENT_AVAILABLE`) 시, 제외된 LOT(`excludedLots`: LOT 번호, 위치, 보류/만료 사유)과 부족 품목(`insufficientItems`: 품목 코드/명, 부족 수량)을 상세 패널 상단 알림(`role="alert"`)으로 명확히 안내.
  - **예약 등록 규칙 정규화 (C-2 일관성)**:
    - `backend/src/fs/wms/reservations.py`의 예약 생성 시 LOT 필수 여부 검증을 `bool(lot) != (item["itemClass"] == "FG")`에서 C-2(입고 검수)와 동일한 `bool(lot) != bool(item.get("lotTracked"))`로 수정하여 품목 마스터의 `lot_tracked` 플래그를 일관되게 적용.
  - **HOLD·EXPIRED LOT 예약 차단**:
    - 신규 예약 등록 시 `picks._lot_metadata` 및 `picks._lot_block_reason`, `qms.held_lot_nos`를 활용하여 WMS 활성 보류(`LOT_HOLD`), QMS 품질 보류(`LOT_QMS_HOLD`), 유효기간 만료(`LOT_EXPIRED`) 상태의 LOT 지정을 `409 Conflict`로 즉시 차단.




