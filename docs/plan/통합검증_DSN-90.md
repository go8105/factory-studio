# DSN-90 통합 검증 보고서

작성: 2026-10-05 (Claude Code) · 상태: **검증 완료 — GW 재검증 완료(7-2, DSN-31)**
방침: [ROADMAP-02](전체설계우선_전환_ROADMAP-02.md) 단계 3 — 교차 조회 계약 전체 표, 업무 흐름 시나리오, 시드 시나리오, 목표 DB 빈 DB 적용.
입력: 각 솔루션 설계 문서 6장(교차 조회)·"넘길 것" 18개 문서, 목표 DB `schema-target.json`(DSN-30까지 340테이블), 현재 코드 `backend/src/fs/*/interface.py`, Codex GW 설계(`codex/fs-030-gw` `08c91d9`).

---

## 0. 결론

| 항목 | 결과 |
|---|---|
| 교차 조회 계약 | 제공 함수 **109개**(현재 코드에 있는 19개 포함, 공통 4종 × 17 솔루션 별도)를 한 표로 정리(2장). 문서 사이 불일치 **9종 34건**을 찾아 이 표 기준으로 정리(3장) |
| 업무 흐름 | 시나리오 **8개 · 62단계**를 끝까지 추적(4장). 받는 쪽 원천 번호 칸이 없던 곳 **10곳** → 목표 DB 보정(`apply_dsn90`) |
| 시드 | 한 회사·한 코드 사전·기간 규칙·솔루션별 예산(5장) |
| 목표 DB | **340테이블 · FK 812 · 빈 DB 적용 대조 오류 0**, 격리 위반 0, 검증기 `validate_integration_dsn90` 추가(6장) |
| GW | Codex 설계는 목표 DB·기준표 형식이 아니라 대조 범위 밖. **HR과 사람·조직·근태·휴가가 겹친다** — 결정 4건(7장) |

**이 문서 2장이 교차 조회 계약의 기준본이다.** 각 솔루션 문서 6장은 설계 당시 초안이며, 다르면 이 표를 따른다.

## 1. 방법

1. 18개 설계 문서 6장의 "읽는 것·제공하는 것·넘길 것"을 모두 모아 제공자 기준으로 다시 묶었다.
2. 소비자가 요청한 함수가 제공자 표에 있는지, 이름·인자·뜻이 같은지 대조했다.
3. 업무 흐름 8개를 단계마다 "누가 무엇을 읽고 → 어느 표·칸에 남기나 → 두 번 가져오지 않는 키"로 추적하고, 목표 DB에서 칸·유일 키·원천 종류 값을 확인했다.
4. 확인 항목을 검증기 `validate_integration_dsn90`(흐름 칸 38 · 멱등 키 17 · 원천 종류 값 10 — DSN-31 뒤 41·21·12, 7-2)에 넣어 이후 설계 변경 때 다시 깨지지 않게 했다.

## 2. 교차 조회 계약 전체 표

규칙(FS-013·FS-023·DSN-01): 읽기 전용 `fs/<솔루션>/interface.py`만. 쓰기·스키마 간 FK·직접 SQL 금지. 값은 코드·수량 스냅샷. **제공 솔루션이 꺼져 있거나 그 시드가 아직 복사되지 않았으면 `None`**(화면은 "조회 불가", 0건과 구분).
표기: **있음** = 현재 코드에 있음 · ★ = 이번 검증에서 이름·소유·누락을 바로잡음.

### 2-1. 모든 솔루션 공통 4종

| 함수 | 돌려주는 것 | 쓰는 곳 | 제공 |
|---|---|---|---|
| `enabled()` | 이 공간에서 켜짐 여부 | 모든 소비자(조회 전 확인) | 17개 전부(ERP·MES·SPC·GW·FEMS 있음, ★QMS 등 나머지) |
| `monthly_summary(month)` | 지표 키 → 값(확정 자료 우선) | EIP KPI·보고서·대시보드 | 17개 전부. ★ERP는 `journal_summary`·`sales_summary`를 이 함수의 키로 흡수, SPC는 `capability_summary`와 별도로 둠 |
| `pending_tasks(hr_employee_code)` | 종류별 대기 건수·화면 경로 | EIP 내 할 일 | 사람 마스터가 있는 솔루션(없으면 빈 목록) |
| `lookup(code)` | 번호 → 대상 종류·화면 경로 | EIP 통합 검색 | 17개 전부 |

### 2-2. 솔루션별 제공 함수

| 제공 | 함수 | 돌려주는 것 | 쓰는 곳 |
|---|---|---|---|
| **core** | ★`holidays(from, to)` | 공통 휴일 달력 | BEMS·FEMS TOU·MES 근무조·SCM·HR 근태 |
| **HR** | `employees(status?)` | 사원 코드·이름·부서·직위·재직 | 사람 마스터를 가진 솔루션 모두 "HR에서 가져오기", EIP 사람 연결 |
| | ★`departments()` | 부서 코드·이름·상위·부서장 | **부서 코드의 원천**(HR Q1): ERP 부서·ELB 승인자·FEMS·BEMS |
| | `payroll_runs(month)` | 확정 급여의 부서·항목별 합계 | ERP F94 급여 전표 |
| **ERP** | 있음 `confirmed_shipments`·`purchase_receipts`·`open_shipment_qty`·`shipment_orders`·`approval_source_digest`·`approval_documents`·`approval_document`(DSN-31: 종류 PURCHASE_ORDER·EXPENSE_CLAIM 추가) | 그대로 | WMS·GW·★TMS(배차 대상은 `shipment_orders` — TMS 문서의 `open_shipment_orders`를 이 이름으로) |
| | ★`partners(kind?)` | 거래처 코드·이름·구분 | MES·QMS·CMMS·SCM·TMS·ELB |
| | `purchase_orders(open)` | 발주 명세(`open=True` 입고 예정, `False` 이력) | WMS·TMS·SCM |
| | ★`returns(kind)` | 확정 판매·구매 반품 | QMS 반품 검사·WMS 반품 입고 |
| | `shipments_monthly(from, to)` | 품목·월 출하 | SCM 수요 이력 |
| | `crm_imports()` · `sales_orders_for_crm(since)` · `partner_summary(codes)` | 가져간 고객사·견적 / 수주 / 거래 요약 | CRM |
| | `budget_status(dept, account, month)` · `elb_request_status(nos)` · `card_transactions(open)` · `purchase_prices(items)` | 예산·진행·카드·단가 | ELB |
| | `standard_costs(items)` · `plm_imports()` | 표준 원가 / PLM 가져간 현황 | PLM |
| **MES** | 있음 `inspectable_lots`·`lot_snapshot`·`items`(★단위 중량 포함)·`finished_goods_receipts`·`completed_material_issues`·`operation_runs` | 그대로 | QMS·WMS·SPC·TMS·CMMS·FEMS |
| | `pop_context(barcode)` · `released_work_orders()` · `pop_results(entry_nos)` | 스캔 대상 / 발행 지시 / 반영 결과 | POP |
| | `production_results(month)` · `subcontract_results()` | 생산 양품 / 외주 입고 | ERP 원가·외주비, FEMS 원단위, SPC, WMS |
| | `material_adjustments()` · ★`material_shortages()` | 비계획 입출고 / 자재 부족 | WMS / **ERP 구매 요청(출처 MES)** |
| | `molds()` · ★`equipment()` | 금형·누적 타수 / 설비 | CMMS 대장 가져오기 |
| | ★`defects(month)` · ★`process_inspections(month)` · ★`lot_trace(lot_no)` | 공정 불량 / 공정 검사 / LOT 계보 | QMS 집계·역추적, SPC 계수형 |
| | `capacity(month)` · `production_plan(month)` · `open_work_orders_by_item(items)` · `plm_imports()` | 능력 / 계획 / 진행 지시 / PLM 가져간 현황 | SCM / PLM |
| **WMS** | `receipts(period)` · `stock_moves(month)` · `stock_on_hand(items)` · `lots(item)` · `line_stock(location)` | 입고·수불·재고·LOT·라인 재고 | ERP·MES·SCM·CMMS·QMS |
| | `pop_context(barcode)` · `pop_results(entry_nos)` · ★`pop_tasks(location)` | 스캔 대상 / 반영 결과 / **창고 작업 대기**(공통 `pending_tasks`와 이름 충돌 → 개명) | POP |
| | `picked_shipments()` · `inbound_notices(open)` · `inbound_status(items, refs)` · ★`inbound_lots_to_inspect()` · `plm_imports()` | 피킹 완료 / 입고 예정 / 입고 상태 / 검사 대상 LOT | TMS / ELB / QMS / PLM |
| **QMS** | 있음 `held_lot_nos`·`latest_results` | 보류 LOT·최근 판정 | MES·WMS |
| | `incoming_results(since)` · `return_results(since)` | 수입·반품 검사 판정 | WMS 격리 해제·반품 처리 |
| | `claims(customer_code)` · `supplier_grades(month)` · ★`gauges()` · `ncr(no)` · `plm_imports()` | 클레임 / 공급처 등급 / 계측기 / 부적합 | CRM / ERP·SCM / SPC / RWS / PLM |
| **SPC** | 있음 `open_signal_lot_nos` · 설계됨 `equipment_signals()` · `spec_violations(since)` · `capability_summary(month)` | 이상 LOT / 설비 신호 / 규격 이탈 / Cpk | QMS 배지·NCR 후보, CMMS 신호, EIP |
| **FEMS** | 있음 `site_electricity`·`manufacturing_electricity` · `energy_costs(month)` · `open_alarms()` · ★`tariff_rates(period)` | 전력 / 비용 배분 / 에너지 경보 / TOU 요율 | BEMS / ERP 원가 참고 / BEMS 피크 / BEMS 비용 |
| **BEMS** | `hvac_units()` · `active_alarms()` | 공조기 / **환경 경보만** | CMMS 대장·신호 |
| **CMMS** | `equipment_in_maintenance(codes)` · `part_requests()` · `part_usages(since)` · `work_order(no)` · `failure_codes()` · ★`assets()` | 보전 중 / 예비품 부족 / 부품 사용 / 작업지시 / 고장 코드 / 설비 대장 | MES 배지 / ERP 구매 요청 / **WMS 출고(CMMS_ISSUE)** / RWS |
| **POP** | `confirmed_entries(target_solution, since)` · `open_calls()` | 확정 입력(입력 번호 = 멱등 키) / 진행 호출 | MES·WMS 지연 가져오기 / EIP |
| **TMS** | `loaded_shipments(since)` · `deliveries(since)` · `inbound_arrivals(since)` · `carrier_settlements(month)` | 상차 / 배송 결과 / 조달 도착 / 운송사 정산 | ERP 출하 확정 / ERP·CRM / WMS / **ERP 매입(FREIGHT)** |
| **PLM** | `released_parts(since)` · `released_bom(part_no, rev)` · `eco_releases(since)` | 배포 리비전 / E-BOM / 배포 ECO | MES·ERP·WMS·QMS 품목 / MES BOM / QMS 4M |
| **CRM** | `accounts(ready_for_erp?)` · `quote_requests(since)` · `quality_inquiries(since)` · `pipeline_summary(month)` | 고객사 / 견적 요청 / 품질 문의 / 파이프라인 | ERP·RWS / ERP / QMS / SCM |
| **SCM** | `demand_forecast(month)` · `sop_plan(month)` · `inventory_policies()` · `supplier_scores(month)` | 확정 예측 / S&OP / 재고 정책 / 공급처 점수 | ERP 판매계획 / MES / WMS / ERP·QMS 참고 |
| **ELB** | `approved_requests(since)` · `receipts(since)` · `emergency_requests(since)` | 승인 신청 / 비재고 수령 / 긴급 구매 | **ERP 구매 요청(출처 ELB)** / **ERP 매입(INDIRECT)** / ERP 카드 비용 |
| **RWS** | `field_visit_requests()` | 현장 출동 필요 완료 요청 | CMMS 작업지시(RWS_REQUEST) |
| **GW** | 있음 `approvals(doc_ref)`(DSN-31: 발주·지출결의·ECO 확장) · `published_notices(limit)` | 결재 상태 / 게시 공지(권한 필터) | ERP·PLM 배지·**ERP 확정 통제** / EIP 공지(Q1) |
| **PLM**(DSN-31) | ★`eco_for_approval(eco_no)` | ECO 결재 원문 스냅샷 | GW 기안(PLM_ECO) |
| **core**(DSN-31, 실제 도입) | `membership(subject_key)`·`members()`·`security_events()` | TEAM 멤버십·권한 확인 | GW(TEAM) |
| **EIP** | `my_employee_code(actor)` | 로그인 사용자 ↔ 사원 코드 | HR 본인 조회 |

## 3. 찾은 불일치와 처리

| # | 종류 | 내용 | 처리 |
|---|---|---|---|
| C1 | 원천 오기 | ERP 문서가 구매 요청 원천을 "CMMS·ELB `part_requests()`"로 적음. ELB는 `approved_requests`를 제공하고, MES `material_shortages`가 빠짐 | 원천 3개 = MES `material_shortages` · CMMS `part_requests` · ELB `approved_requests`. 목표 DB `erp.purchase_request.source`는 이미 MES·CMMS·ELB(확인) |
| C2 | 원천 충돌 | BEMS·FEMS·ELB가 ERP `departments()`를 읽음 ↔ HR Q1 "부서 코드는 HR 원천" | 부서는 **HR `departments()`**. ERP 부서는 HR 코드를 가져온 ERP 자체 마스터(같은 코드) |
| C3 | 공통 누락 | EIP가 모든 솔루션에 요구한 `monthly_summary`·`pending_tasks`·`lookup`이 MES·WMS·QMS·ERP 등 제공 표에 없음 | 2-1 공통 4종으로 정함 |
| C4 | 이름 충돌 | WMS `pending_tasks(location)`(POP용) ↔ 공통 `pending_tasks(hr_employee_code)` | WMS 쪽을 `pop_tasks(location)`로 개명 |
| C5 | 이름 불일치 | TMS가 ERP `open_shipment_orders()`를 요청. 현재 코드는 `shipment_orders` | 현재 이름 사용 |
| C6 | 제공 누락(12건) | ERP `partners`·`departments`·`returns`, MES `equipment`·`defects`·`process_inspections`·`lot_trace`, WMS `inbound_lots_to_inspect`, QMS `gauges`, FEMS `tariff_rates`, CMMS `assets`, core `holidays` — 소비자 문서에만 있고 제공자 표에 없음 | 2-2에 제공자로 등록 |
| C7 | 받는 쪽 누락(6건) | WMS가 QMS `incoming_results`·`return_results`·CMMS `part_usages`를, QMS가 SPC `spec_violations`를, ERP가 FEMS `energy_costs`·SCM `supplier_scores`를 읽는다는 기록이 받는 쪽 문서에 없음 | 2-2 "쓰는 곳"에 반영 |
| C8 | DB 빈칸(10곳) | "가져오기"를 받는 표에 원천 번호가 없어 멱등(두 번 가져오지 않기)과 원천의 `*_imports()`를 만들 수 없음 | `apply_dsn90` — 아래 표 |
| C9 | 동시성 | POP 지연 가져오기를 두 요청이 동시에 할 때(POP 문서의 DSN-90 요청) | `mes.pop_import`·`wms.pop_import`의 UK(입력 번호)로 하나만 성공. 다른 쪽은 UK 위반을 "이미 반영"으로 처리(SERVICE) — 목표 DB에 이미 있음(확인) |

**C8 목표 DB 보정(`tools/apply_dsn90.py`, target-0.19.0)**

| 표 | 추가 | 유일 키·제약 | 흐름 |
|---|---|---|---|
| `erp.partner` | `crm_account_code` | CRM 고객사당 거래처 1건 | S1 CRM → ERP 거래처 |
| `erp.quotation` | `crm_quote_request_no` | 요청당 견적 1건(1차 개정 기준) | S1 견적 요청 → 견적 초안 |
| `erp.sales_plan` | `scm_forecast_ref` | (추적용) | S1 SCM 예측 → 판매계획 |
| `erp.item`·`mes.item`·`wms.item` | `plm_part_no`·`plm_revision` | 둘 다 있거나 둘 다 없음 | S8 PLM 품목 가져오기 |
| `mes.bom_version` | `plm_bom_ref` | — | S8 E-BOM → 제조 BOM |
| `qms.claim` | `crm_inquiry_no` | 문의당 클레임 1건 | S4 CRM 품질 문의 |
| `qms.change_notice` | `plm_eco_no` | ECO·품목당 진행 4M 1건 | S4·S8 ECO → 4M |
| `qms.ncr` | (기존 `source_ref`) | 원천당 NCR 1건 | S4 SPC 이탈 → NCR |
| `erp.purchase_invoice` | 매입 종류 `FREIGHT`·`INDIRECT` | 기존 (종류, 원천 번호) 유일 | S1 TMS 운송비 · S5 ELB 비재고 — 둘 다 DIRECT에 넣으면 원천 번호가 섞임 |
| `wms.stock_document` | 문서 종류 `CMMS_ISSUE` | 기존 원천 키 유일 | S3 정비 부품 출고 |

## 4. 업무 흐름 시나리오

각 단계는 **"읽는 함수 → 받는 표·칸 → 멱등 키"**. 화살표는 데이터 방향이고, 실제 동작은 항상 받는 쪽이 읽어 자기 표에 쓴다(교차 쓰기 없음). 받는 칸·키는 `validate_integration_dsn90`이 검사한다.

### S1 수주 → 생산 → 출하 → 매출 (14단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | CRM 고객사 → ERP 거래처 | CRM `accounts(ready_for_erp)` | `erp.partner.crm_account_code` ★ | 고객사당 1건 |
| 2 | CRM이 연결된 거래처 코드 표시 | ERP `crm_imports()` | `crm.account.erp_partner_code` | — |
| 3 | 견적 요청 → ERP 견적 초안 | CRM `quote_requests` | `erp.quotation.crm_quote_request_no` ★ | 요청당 1건 |
| 4 | SCM 확정 예측 → ERP 판매계획 초안 | SCM `demand_forecast` | `erp.sales_plan.scm_forecast_ref` ★ | 월 확정 1건(기존) |
| 5 | 판매계획 → MES 생산계획 | ERP 판매계획 조회(기존) | `mes.production_plan.sales_plan_code` | — |
| 6 | MES 작업지시 발행 → POP 내 작업 | MES `released_work_orders` | (POP 화면 조회) | — |
| 7 | POP 스캔 확정 → MES 실적 | POP `confirmed_entries` | `mes.pop_import.pop_entry_ref` | 입력 번호 UK |
| 8 | MES 완제품 입고 → WMS 재고 | MES `finished_goods_receipts` | `wms.stock_document.source_key`(MES_RECEIPT) | 원천 키 UK |
| 9 | ERP 출하지시 → WMS 피킹 | ERP `shipment_orders` | `wms.stock_reservation.shipment_source_key` | 원천 키 UK |
| 10 | 피킹 완료 → TMS 배차 | WMS `picked_shipments` | `tms.dispatch_stop.shipment_order_no` | — |
| 11 | 상차 → ERP 출하 확정 | TMS `loaded_shipments` | `erp.shipment` | 출하지시당(기존) |
| 12 | 배송 결과 → ERP 납품·반품 후보, CRM 고객 360 | TMS `deliveries` | (조회) | — |
| 13 | 운송사 정산 → ERP 매입 | TMS `carrier_settlements` | `erp.purchase_invoice`(FREIGHT ★, `source_ref`) | (종류, 원천) UK |
| 14 | 매출·채권 → EIP | ERP `monthly_summary` | `eip.report_line`(확정 보고서 스냅샷) | 월 확정 1건 |

### S2 구매 → 조달 운송 → 입고 → 수입 검사 → 매입 (9단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | MES 자재 부족 → 구매 요청 | MES `material_shortages` | `erp.purchase_request.source='MES'`·`source_ref` | (출처, 원천) UK |
| 2 | 구매 요청 → 발주 확정 | (ERP 내부) | `erp.purchase_order` | — |
| 3 | 발주 → WMS 입고 예정 | ERP `purchase_orders(open)` | `wms.inbound_notice`·`source_claim.source_key` | 원천 키 UK |
| 4 | 조달 운송 배차 | ERP `purchase_orders` · WMS `inbound_notices` | `tms.dispatch_stop.po_no`·`inbound_notice_no` | — |
| 5 | 게이트 도착 → WMS 차량·도착 | TMS `inbound_arrivals` | `wms.inbound_notice.vehicle_no`·`arrived_at` | — |
| 6 | 검수 완료 LOT → QMS 수입 검사 | WMS `inbound_lots_to_inspect` ★ | `qms.inspection.source='WMS'`·`source_ref` | — |
| 7 | 판정 → WMS 격리 해제·불량 | QMS `incoming_results` | `wms.lot_hold.source='QMS'`·`source_ref` | — |
| 8 | 입고 확정 → ERP 매입 | WMS `receipts` | `erp.purchase_invoice`(PO_RECEIPT) | (종류, 원천) UK |
| 9 | 공급처 성과 | QMS `supplier_grades` · ERP `purchase_orders(open=False)` | `scm.supplier_score` | 월 확정 1건(기존) |

### S3 설비 이상 → 원격 지원 → 보전 → 부품 (8단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | 설비 대장 가져오기 | MES `equipment`·`molds` · BEMS `hvac_units` | `cmms.asset.source`·`source_code` | (출처, 코드) UK |
| 2 | SPC 설비 신호·BEMS 환경 경보 → 작업지시 | SPC `equipment_signals` · BEMS `active_alarms` | `cmms.work_order.source`·`source_ref` | 신호당 진행 1건 |
| 3 | 작업지시 → RWS 원격 지원 요청 | CMMS `work_order(no)` | `rws.request.source_kind='CMMS_WO'`·`source_ref` | 출처당 진행 1건 |
| 4 | 원격 해결 실패 → 현장 출동 작업지시 | RWS `field_visit_requests` | `cmms.work_order.source='RWS_REQUEST'` | 요청당 진행 1건 |
| 5 | MES 보전 중 배지 | CMMS `equipment_in_maintenance` | (조회) | — |
| 6 | 부품 사용 → WMS 출고 | CMMS `part_usages` | `wms.stock_document`(CMMS_ISSUE ★) | 원천 키 UK |
| 7 | 예비품 부족 → 구매 요청 | CMMS `part_requests` | `erp.purchase_request.source='CMMS'` | (출처, 원천) UK |
| 8 | MTBF·MTTR → EIP | CMMS `monthly_summary` | `eip.report_line` | 월 확정 1건 |

### S4 품질 (7단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | SPC 규격 이탈 → NCR 후보 | SPC `spec_violations` | `qms.ncr.source_ref` | 원천당 1건 ★ |
| 2 | SPC 이상 LOT 배지 | SPC `open_signal_lot_nos` | (조회) | — |
| 3 | CRM 품질 문의 → 클레임 | CRM `quality_inquiries` | `qms.claim.crm_inquiry_no` ★ | 문의당 1건 |
| 4 | 클레임 → CRM 고객 이력 | QMS `claims` | (조회) | — |
| 5 | NCR → RWS 원격 지원 | QMS `ncr(no)` | `rws.request.source_kind='QMS_NCR'` | 출처당 진행 1건 |
| 6 | 보류 LOT → MES 입고·패킹 거부, WMS 보류 | QMS `held_lot_nos` | (조회) | — |
| 7 | 공정 불량·LOT 역추적 | MES `defects`·`lot_trace` | (조회 집계) | — |

### S5 간접 구매 ELB (6단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | 신청 → 부서장 승인(승인자 지정) | HR `departments` | `elb.approver.hr_employee_code` | 부서당 활성 1명 |
| 2 | 예산 확인 | ERP `budget_status` | (조회·경고) | — |
| 3 | 승인 신청 → 구매 요청 | ELB `approved_requests` | `erp.purchase_request.source='ELB'` | (출처, 원천) UK |
| 4 | 재고 품목 → 발주 → WMS 입고 | (S2 3~8과 같음) · ELB는 WMS `inbound_status` 조회 | — | — |
| 5 | 비재고 수령 → ERP 매입 | ELB `receipts` | `erp.purchase_invoice`(INDIRECT ★) | (종류, 원천) UK |
| 6 | 긴급 구매 ↔ 법인카드 | ERP `card_transactions` → ELB, ELB `emergency_requests` → ERP | `elb.request.card_txn_ref` | 카드 내역당 1건 |

### S6 사람·급여 (7단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | HR 사원·부서 → 각 솔루션 사람 마스터 | HR `employees`·`departments` | `mes.worker`·`pop.operator`·`cmms.technician`·`gw.person`·`crm.sales_rep`·`erp.employee`·`rws.expert`·`elb.approver`의 HR 사원 코드 | 솔루션별 사람 코드 UK(기존) |
| 2 | 휴일 달력 → 근태 자동 생성 | core `holidays` | `hr.attendance` | 사원·일 1건 |
| 3 | 월 근태 마감 → 급여 계산 | (HR 내부) | `hr.payroll_run.attendance_close_id` | 월 확정 1건 |
| 4 | 확정 급여 → ERP 급여 전표 | HR `payroll_runs` | `erp.journal_entry`(PAYROLL, `source_ref`) | (종류, 원천) UK |
| 5 | 로그인 사용자 ↔ 사원 | (EIP 관리) | `eip.person_link.hr_employee_code` | 사용자당 1건 |
| 6 | 사람별 할 일 | 각 솔루션 `pending_tasks(hr_employee_code)` | (조회) | — |
| 7 | HR 본인 조회 | EIP `my_employee_code` | (조회) | — |

### S7 에너지 (5단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | MES 생산량 → FEMS 원단위 | MES `production_results` | `fems.production_record.source='MES'`·`source_key` | (원천, 버전) UK |
| 2 | FEMS 전력 → BEMS 공용 분해 | FEMS `site_electricity`·`manufacturing_electricity` | (BEMS 계산) | — |
| 3 | FEMS 피크 경보 → BEMS 감축 계획 | FEMS `open_alarms` | `bems.demand_plan.fems_alarm_ref` | 경보당 1건 |
| 4 | TOU 요율 → BEMS 비용 | FEMS `tariff_rates` ★ | (BEMS 계산) | — |
| 5 | 에너지 비용 배분 → ERP 원가 참고 | FEMS `energy_costs` | (조회) | — |

### S8 설계 변경 (6단계)

| # | 단계 | 읽는 함수 | 받는 표·칸 | 멱등 |
|---|---|---|---|---|
| 1 | ECO 결재 배지 | GW `approvals` | (조회) | — |
| 2 | 배포 리비전 → 품목 가져오기 | PLM `released_parts` | `erp.item`·`mes.item`·`wms.item`의 `plm_part_no`·`plm_revision` ★ | 품목 코드 UK(기존) |
| 3 | E-BOM → 제조 BOM | PLM `released_bom` | `mes.bom_version.plm_bom_ref` ★ | 품목·버전 UK(기존) |
| 4 | 가져간 현황 | 각 솔루션 `plm_imports()` | (조회 — 위 칸으로 계산) | — |
| 5 | 배포 ECO → QMS 4M 후보 | PLM `eco_releases` | `qms.change_notice.plm_eco_no` ★ | ECO·품목당 1건 |
| 6 | 진행 지시 영향 | MES `open_work_orders_by_item` | (조회) | — |

## 5. 시드 시나리오

**한 회사**(소형 전자부품 양산, FS-005b) · 합성 데이터만 · 솔루션마다 자기 시드(지연 복사, DSN-01 S2).

| 항목 | 규칙 |
|---|---|
| 기간 | 기준 월 M: **M-3~M-1 확정**(마감·확정 보고서·급여·근태 마감·원가) + **M 진행 중**(작업지시·결재·신청이 열려 있음). 날짜는 시드 생성 시점 기준 상대값 |
| 코드 사전 | 같은 대상은 모든 솔루션 시드에서 **같은 코드**. 생성기는 하나의 사전을 공유한다: 사원·부서(HR 원천) · 품목(PLM 부품 번호 = 품목 코드) · 거래처(ERP 거래처 코드 = CRM `erp_partner_code`) · 설비(MES 설비 코드 = CMMS·FEMS 대상 코드) · 창고·위치(WMS) |
| 가져오기 흔적 | 흐름 표의 원천 번호 칸을 **이미 가져온 상태로** 채운다(예: ERP 거래처의 `crm_account_code`, CMMS 작업지시의 `RWS_REQUEST`). 가져오기 버튼을 누르면 "이미 반영"이 나오는 건과, 아직 안 가져온 건을 모두 둔다 |
| 흐름별 진행 상태 | S1~S8마다 **끝까지 간 건 1개 + 중간에 멈춘 건 1개 이상**(예: 상차는 됐지만 출하 확정 전, 원격 해결 실패 후 현장 출동 대기) |
| 사람 | 사원 약 30명·부서 8. 체험 사람 = EIP 사람 연결로 고르는 사원(생산 작업자·정비원·영업·구매·관리자·부서장) — 사람별 할 일이 비지 않게 |
| 예산 | 솔루션당 **약 3,000행 이하**(측정형 FEMS·BEMS는 별도 협의, DSN-01). 18개 합계 목표 50,000~80,000행 |
| 꺼짐·미복사 | 원천 솔루션이 꺼졌거나 그 시드가 아직 복사되지 않았으면 조회는 `None` → "조회 불가". 가져오기는 원천을 연 뒤 가능 |

시드 생성기 자체(사전 파일·결정적 난수·솔루션별 생성 함수)는 일괄 개발 첫 단계(DSN-01 S1 B 지연 복사)와 함께 만든다.

## 6. 목표 DB 검증

| 검사 | 결과 |
|---|---|
| `validate_db_design.py --schema schema-target.json` | 오류 0 (`validate_integration_dsn90` 포함) |
| `audit_schema_isolation.py --schema …` | 업무 스키마 간 FK 0 · 업무 → core FK는 공간·세대 앵커만 |
| `schema_ddl.py --apply`(빈 `factory_studio_target` DB) | **340테이블 · 컬럼 3,923 · UK 683 · CHECK 834 · INDEX 218 · UNIQUE_INDEX 99 · FK 812 · 대조 오류 0** |
| ERD·Excel(`--target`) | 재생성 |
| 테스트 | tools 73 + DSN 45 통과 · 현재 `schema.json` 검증 0 |

## 7. GW(Codex) 설계와의 대조 — 결정 대기

Codex는 `codex/fs-030-gw`(`08c91d9`, main `1f96532`에서 갈라짐)에 **GW 실제 회사 도입** 확장 설계를 냈다: GW-EXT-01(범위·단계 c→P0→A→B→C→D→E→F), P0 운영 준비, A 상세(공유 TEAM 공간·실제 계정·조직·문서 권한, core 3 + GW 7 논리 테이블, 화면 9, 인수 24).

**맞는 것**: 교차 쓰기·업무 FK 금지 유지(GX-07 ERP 확정 통제는 ERP 소유), EIP가 전사 집계 소유·GW는 권한 필터된 공지 제공(GX-08 = EIP Q1과 같음), 게스트·개인 체험 유지.

| # | 충돌·빈칸 | 내용 |
|---|---|---|
| G1 | **사람·조직 원천** | GW-EXT A의 `organization_unit`·`person_assignment`(GW 조직·소속)와 D단계 "인사 기초·근태·휴가 원장"이 **HR(DSN-30)의 부서·사원·발령·근태·휴가와 겹친다.** HR Q1은 "HR이 사원·부서 코드 원천" |
| G2 | 형식 | GW 설계는 기준표·목표 DB(`schema-target.json`) 반영이 없어 이번 계약·흐름 검사 대상 밖. 목표 DB의 GW는 현재 8테이블 + `hr_employee_code`뿐 |
| G3 | 범위 성격 | GW만 실제 회사 도입(별도 운영 환경·실데이터·TEAM 공간), 나머지 17개는 합성 데이터 포트폴리오. core에 TEAM 공간·멤버십·초대가 들어오면 모든 솔루션의 공통 스코프 검사가 바뀐다(GW-EXT는 "TEAM에서는 GW만 허용"으로 막음) |
| G4 | 브랜치 | `codex/fs-030-gw`가 main보다 많이 뒤처졌고, 같은 기준 문서(현재기획·progress·HANDOFF·FS-013·core README)를 고쳐 병합 충돌이 난다 |

### 7-1. 결정 기록 (2026-10-05 사용자 확정, ROADMAP-02 D81)

| # | 결정 |
|---|---|
| G1 | **HR 원천 유지** — GW 조직·소속은 HR 부서·사원을 가져온 스냅샷(문서 권한 판정용). GW-EXT D단계의 인사 기초·근태·휴가는 빼고 HR이 맡는다. GW는 일정·채팅만. 계정 ↔ 직원 연결·문서 권한은 GW |
| G2 | **Codex가 목표 DB에 반영** — GW 기준표(DSN-00 양식) + `tools/apply_dsn31.py`(core TEAM 공간 3 + GW 7, apply_dsn30 다음·apply_dsn90 앞) → GW 부분만 DSN-90 재검증 |
| G3 | (G1·G2로 정리) GW 실제 도입 트랙의 개발 순서는 DSN-99에서 정한다 |
| G4 | **지금 병합** — `codex/fs-030-gw` `08c91d9`를 main에 병합(설계 문서만, 충돌은 main 기준으로 정리). 배포 없음 |

### 7-2. GW 재검증 (DSN-31 반영 뒤, 2026-10-05)

[DSN-31](../modules/gw/GW_보강설계_DSN-31.md)로 GW가 같은 양식(기준표 28·범위 24, 목표 DB GW 24·core 3·ERP 2 → **361테이블**)이 되어 G2를 닫았다.

| 확인 | 결과 |
|---|---|
| 사람·조직(D81) | GW 조직 단위 = HR 부서 스냅샷, `gw.person.organization_unit_id`. GW에 소속 이력·근태·휴가 표 없음(`validate_gw_dsn31`) |
| 계약 | GW 제공 `approvals`(유형 확장)·`published_notices`·공통 4종 / 읽음 ERP `approval_document`(종류 확장)·**PLM `eco_for_approval`(신규 — 2장에 추가)**·HR `employees`·`departments` / core(실제 도입) `membership`·`members` |
| 흐름 **S9 결재 → 확정 통제** | ① 기안: ERP·PLM 원문 조회 → `gw.approval_document.source_no`·`source_digest`(원천당 진행 1건 UK) ② 병렬·합의·전결·위임 결재 ③ 알림: `gw.notification`(받는 사람, 사건 키) UK ④ ERP·PLM 배지: GW `approvals` ⑤ ERP 확정(정책 REQUIRED): GW `approvals` 읽고 digest 일치 → `erp.approval_evidence`(문서·GW 회차) UK, 불일치·GW 꺼짐은 거부 |
| 검증기 | `validate_integration_dsn90` 흐름 칸 41 · 멱등 키 21 · 원천 종류 12(GW 추가분 포함), `validate_gw_dsn31` |
| 빈 DB 적용 | 361테이블 · FK 866 · 대조 오류 0 · 격리 위반 0 |

## 8. DSN-99로 넘길 것

- 2장 계약 표 = 일괄 개발의 interface 목록(신규 90개 + 공통 4종). 함수 시그니처·반환 필드는 개발 첫 구현 때 확정하고 이 표에 적는다.
- 시드 생성기·코드 사전(5장), 지연 복사와 "시드 없음 = None" 계약.
- 운영 DB를 새로 만들지(배포절차 4-3) — 목표 DB가 현재 DB와 크게 달라 마이그레이션 수가 많다.
- 7장 GW 결정 결과에 따라 GW 트랙의 순서(포트폴리오 일괄 개발과 GW 실제 도입 P0~F)를 정한다.

## 9. GW 체험 구현 계약 (GW-e, 2026-10-09)

DSN-31 체험 범위는 GW-a~e에서 현재 DB의 GW 19개 표로 구현했다. 목표 DB의 실제 도입 A·CORE TEAM과 ERP 확정 통제 F44는 별도 소유·단계다.

| 제공·조회 | 실제 동작과 경계 |
|---|---|
| GW `approvals` | 매입·발주·지출결의·ECO 참조를 100개까지 조회. 미상신 초안 제외, 진행 회차 우선. 단일 종류는 번호 키, 여러 종류는 `종류:번호` 키. GW 꺼짐·미복사면 `None`, 열린 뒤 대상 없으면 번호별 `None` |
| GW `published_notices` | 전체 공간에 게시된 공지만 제공. 담당자 없는 EIP 조회에 부서 공지 제목·내용은 노출하지 않음 |
| GW 공통 4종 | `enabled`·`monthly_summary`(KST 상신 월)·`pending_tasks`(HR 사원 코드, 위임 포함)·`lookup`(문서 번호 또는 전체 공간 게시글 번호). 꺼짐·미복사는 조회 불가와 빈 결과를 구분 |
| HR → GW | `employees`·`departments` 읽기 전용. 선택 가져오기 후 현재 GW 조직을 갱신하고, 상신 조직·종결 이력은 보존 |
| ERP → GW | `approval_document(PURCHASE_INVOICE, no)`로 실제 매입 snapshot·digest 연결. 발주·지출결의 제공은 아직 미구현. GW는 지원되지 않는 종류를 합성 원문으로 대체하지 않음 |
| PLM → GW | `eco_for_approval` 소비 계약 준비. 원천 제공이 없으면 조회 불가. 실제 제공 구현은 PLM 단계 |
| S9 결재 → ERP 확정 | GW 병렬·합의·전결·위임·내부 알림은 구현. ERP REQUIRED 정책 및 `approval_evidence`는 W2b에서 ERP 담당자가 구현·검증할 것 |

시드 `sv-20261009-gw1`은 HR 합성 코드 기반 조직 4·담당자 10, 일반·ERP 매입 초안, 병렬 대기, 전결·위임 완료 및 기존 순차 이력, 전체/부서 공지·댓글 이력, 개인/부서 일정과 참석 응답, 읽음/미읽음 알림, 1:1/그룹 채팅을 포함한다. GW 19개 표 98행. 기존 템플릿 수정 없이 새 템플릿을 생성하며 배포 시 재생성이 필요하다.

복사 시 관계 FK와 결재 사건 JSON의 내부 ID·전결 월/시각·상신 적용 월, 알림의 대상 ID·사건 키를 새 범위로 옮긴다. 원문 digest·코드/금액·조직 이름 스냅샷, 채팅 seq/clientKey/readCursor는 보존한다. GW 개방은 HR·ERP를 자동 개방하지 않는다. 초기화와 만료 공간 정리는 댓글 수정 이력·일정 참석·알림·채팅 자식을 포함한다. 실제 PostgreSQL 검증 결과는 [GW-e 결과](../agent/GW_시드도움말_GW-e.md)에 기록한다.
