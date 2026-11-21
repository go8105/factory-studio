# ERP — 판매·출하

## 현재 기준 (2026-09-30, ROADMAP-01)

- 상태: **보강 중(DSN-11)** — 19화면(E-01~19), 목표 41화면. **DB 반영 완료(ERP-1a, 2026-11-15, 마이그레이션 `erp1`, 27 → 63표)**, 1b 교차 조회·**1c 기초등록 완료(2026-11-21)**. 다음은 1d 영업·구매. 기능 추가는 [로드맵](../../plan/로드맵_17개시스템_ROADMAP-01.md)의 "살 붙이기" 단계에서만 한다. 다른 솔루션이 요청하는 **조회 함수 추가는 동결 중에도 허용**한다.
- 설계: [ERP 모듈 설계서](ERP_모듈설계_FS-005e.md) · **보강 설계: [DSN-11](ERP_보강설계_DSN-11.md)**(ROADMAP-02 — 72기능 중 58 범위, 27 → 63테이블, 화면 41. 설계 완료·**DB 반영 완료**. 단계: 1a DB / 1b 교차 조회 / 1c 기초등록 / 1d 영업·구매 / 1e 회계 전표 / 1f 장부·결산 / 1g 세무 / 1h 채권·채무·자금 / 1i 원가·예산·자산)
- 읽는 조회: GW `approvals` — E-11 상세 읽기 전용 배지(확정 통제 없음) · WMS `receipts(from,to)`·`stock_moves(month)`·`stock_on_hand()` · MES `production_results(month)`·`subcontract_results(month)` · HR `payroll_runs(month)`. **CMMS `part_requests()`는 CMMS에 요청 표가 없어 미구현**이다.

### 제공 조회 함수 (`backend/src/fs/erp/interface.py`)

| 함수 | 돌려주는 것 | 쓰는 곳 |
|---|---|---|
| `approval_documents()` / `approval_document()` | 코드·금액·명세 스냅샷/상태, 꺼짐 None | GW |
| `approval_source_digest(snapshot)` | 표시 날짜/상태를 제외한 정규화 SHA256(순수 함수) | GW·ERP 배지 |
| `enabled()` | 사용 여부 | — |
| `confirmed_shipments()` | 확정 출하 | WMS |
| `purchase_receipts()` | 확정(취소 포함) 매입 | WMS |
| `open_shipment_qty()` | 미출하 출하지시 수량(품목별) | WMS |
| `purchase_orders(open_only)` | 확정 발주 명세(입고 예정). **입고 진행은 주지 않는다** — WMS가 안다 | WMS |
| `journal_summary(month)` | 확정 전표의 계정별 차·대 합계(초안 제외) | EIP |
| `sales_summary(from,to)` | 기간 매출과 지금 남은 채권 미수(따로) | EIP·CRM |

모든 함수의 앞 두 인자는 `(connection, scoped)`이고, 이 솔루션이 꺼져 있으면 `None`을 돌려준다.

> 아래는 작성 당시 메모다. 위 "현재 기준"과 다르면 위가 우선한다.

- 업무 범위: 거래처, 판매계획, 수주, 출하지시·출하, 매출
- 이 폴더의 문서: 아키텍처_및_ERP_확장기획.md

## 메모

- 모듈 설계서 FS-005e와 보강 설계 DSN-11이 모두 있다. `아키텍처_및_ERP_확장기획.md`는 참고자료다.
- **ERP-1a에서 옮기지 않은 것**: `erp.approval_policy`·`erp.approval_evidence`(DSN-31 F44 확정 통제, W2b 배정)와 PLM·CRM·SCM 참조 칼럼. 그 작업에서 새 revision으로 넣는다.
- 새 표 36개 중 **5개(부서·담당자·프로젝트·단가 그룹·그룹 단가)는 1c에서 시드와 화면을 얻었다.** 나머지 31개는 그 화면을 만드는 단계에서 함께 넣는다.
- **단가 결정 순서(F06)**: 거래처별 단가(E-17) → 거래처의 판매 단가 그룹(적용 시작일 최신) → 품목 표준 판매가(E-16). 셋 다 없으면 단가를 만들지 않고 막는다.
- **거래처 구분 BOTH**는 수주·매입·수금·지급·`interface.partners(kind)` 다섯 곳이 함께 받아들인다. 새로 구분을 보는 코드를 쓸 때 BOTH를 빠뜨리지 않는다.
- **계정은 삭제하지 않는다**(사용 여부만 끈다). 쓰이는 계정의 분류·정상 잔액은 바꿀 수 없다.

## 규칙

이 폴더에 모듈 공통 설계서가 없으면 해당 모듈은 개발 착수 대상이 아니다.
설계를 먼저 확정하고 사용자 확인을 받은 뒤 구현에 들어간다.

공통 기준정보(품목·설비·작업장 등)는 core가 소유한다. 모듈별로 복제하지 않는다.

전체 현황은 [현재 기획과 진행 현황](../../plan/현재기획_진행현황.md)을 본다.
