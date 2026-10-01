# FS-029 CMMS 모듈 설계서

작성일: 2026-10-01 (Claude Code)
상태: **13장 결정 5건 확정(2026-10-01, 하나씩 확정 — 4번만 권장과 다르게 유예 0일)** · 화면 설계와 함께 전체 설계 확인 대기. 전체 설계 확인 전에는 `schema.json`·마이그레이션·코드를 바꾸지 않는다.
전제: [FS-029 결정서](../../plan/CMMS도입_설비보전_결정_FS-029.md)(D45~D52, 2026-10-01 확정), [FS-023 D9 교차 조회](../../plan/QMS도입_교차조회_결정_FS-023.md), [FS-013](../../plan/독립솔루션_전환결정_FS-013.md), [새 솔루션 킷](../../plan/새솔루션_킷.md)
화면: [CMMS 화면 설계](../../ui/화면설계_CMMS_FS-029.md)

---

## 1. 이 모듈은 무엇인가

**설비 대장을 갖고, 예방보전(PM) 계획과 고장·신호에서 온 보전 작업지시를 접수 → 작업 → 완료까지 기록하며, 설비별 MTBF·MTTR·PM 준수율을 보여 주는 설비보전 솔루션이다.**

```
MES 설비 8대 ─가져오기─┐
BEMS 공조기 2대 ─가져오기─┤──▶ 설비 대장(스냅샷) ◀── 직접 등록(공용 압축기 등)
                         │
BEMS 경보(발생·확인) ──조회──┐
SPC 이상(설비 코드) ──조회──┼──▶ 전환 대기 신호 ─(사람이 전환)─▶ 고장(BM) 작업지시
수동 접수 ─────────────────┘                                     │
PM 계획(주기) ─(주기 도래, 사람이 생성)─▶ 예방(PM) 작업지시 ───────┤
                                                                 ▼
                         접수 → 진행(작업 기록·부품 사용) → 완료(원인·조치) / 취소
                                                                 │
                    진행 중 고장 작업지시 설비 ──조회──▶ MES "보전 중" 배지
                    완료 기록 ─▶ 지표 MTBF · MTTR · PM 준수율(조회할 때 계산)
```

평가자 3분 동선:

```
대시보드(진행 중 작업지시 · 전환 대기 신호 3 · 주기 도래 PM 1 · MTTR)
  → 전환 대기 신호: SPC 이상 LT-0017(INJ-02 사출 추세) → "INJ-02 냉각수 유량 점검" 고장 작업지시로 전환
  → 작업지시: 시작 → 작업 기록 40분 · 부품 "냉각수 호스" 1개 → 완료(원인 "설비 마모", 조치)
  → MES 공정 실행에서 INJ-02 "보전 중" 배지가 진행 중일 때 보이고, 완료 뒤 사라진다
  → 지표: INJ-02 MTTR·MTBF가 방금 기록으로 바뀐다
```

## 2. 하위 모듈

| 하위 모듈 | 소유 테이블 | 교차 조회 |
|---|---|---|
| `asset` 설비 대장 | 설비 | MES 설비 · BEMS 공조기(가져오기) |
| `plan` 예방보전 | PM 계획 | — |
| `work` 작업지시 | 작업지시, 작업 기록 | BEMS 경보 · SPC 이상(전환 대기) |
| `parts` 예비품 | 예비품, 부품 사용 | — |

소유 **6테이블**. 결정서 4장의 예상 7테이블 중 "신호 전환"은 별도 테이블 없이 작업지시의 출처(`source`·`source_ref`)와 부분 유니크 인덱스로 처리한다(13장 1). 스키마 간 FK 0건.

## 3. 업무 규칙

| 규칙 | 내용 |
|---|---|
| 설비 대장(D46) | 코드·이름·종류(사출·조립·검사·공조·유틸리티·기타)·위치·출처(`MES`/`BEMS`/`CMMS`)·원천 코드. 가져오기는 원천 코드가 같은 설비가 이미 있으면 건너뛴다(같은 원천은 1건). 원천이 바뀌어도 대장은 그대로(스냅샷). 작업지시가 있는 설비는 삭제 대신 사용 안 함 |
| PM 계획(D49) | 설비·제목·점검 항목(텍스트)·주기(일, 1~365)·시작일·마지막 수행일. **다음 예정일 = (마지막 수행일 또는 시작일) + 주기**, 저장하지 않고 계산. 업무 기준일 ≥ 다음 예정일이면 "주기 도래". 사람이 "작업지시 생성"을 누르면 그 예정일로 PM 작업지시 1건(같은 계획·같은 예정일 중복 거부) |
| 작업지시 종류 | `BM`(고장·사후보전) · `PM`(예방보전). 출처 `MANUAL`·`BEMS_ALARM`·`SPC_SIGNAL`(BM) · `PM_PLAN`(PM). 번호는 서버 발번 `WO-YYYYMMDD-NNN`(업무 기준일) |
| 상태(D47) | `REQUESTED` → `IN_PROGRESS`(시작 시각) → `COMPLETED`(완료 시각, 원인 분류·조치 내용 필수) · `REQUESTED`/`IN_PROGRESS` → `CANCELLED`(사유 필수). 완료·취소 뒤 불변 |
| 고장 정지(D47) | BM은 **정지 시작**(고장 시각, 접수 때 입력, 기본 = 신호 발생 시각)과 **복구 시각**(완료 때 필수, 정지 시작 이후)을 남긴다. PM은 정지 기록이 없다(1차) |
| 신호 전환(D48) | 전환 대기 = BEMS 해제 전 경보 + SPC 이상(미조치이거나, 원인 "설비"로 조치 완료된 최근 30일) 중 **아직 전환하지 않은 것**. 전환하면 BM 작업지시를 만들고 원천 id·요약을 스냅샷으로 남긴다. 같은 신호는 취소되지 않은 작업지시 1건만(취소하면 다시 전환 가능). BEMS 경보는 구역 단위라 그 구역의 공조기 대장을 기본 설비로 고르고, 사람이 바꿀 수 있다(13장 2). **원천 상태는 바꾸지 않는다** |
| 작업 기록 | 진행 중에만 추가: 기록 시각·작업 시간(분, 1~1440)·내용. 추가만, 수정·삭제 없음 |
| 부품 사용(D50) | 진행 중에만 추가: 예비품·수량(> 0). 추가만. 예비품 "누적 사용"은 사용 기록 합. 안전 재고 미만 표시는 "안전 재고 − 최근 30일 사용" 참고값이며 재고가 아니다 |
| PM 완료 | PM 작업지시를 완료하면 그 계획의 마지막 수행일 = 완료 시각의 날짜(KST). 지연 완료면 다음 예정일도 밀린다(13장 5) |
| 지표(D51) | 기간·설비별, 조회할 때 계산: 고장 건수 = 기간 안 정지 시작인 완료 BM, **MTTR** = Σ(복구 − 정지 시작) ÷ 고장 건수, **MTBF** = (기간 시간 − Σ정지 시간) ÷ 고장 건수(0건이면 "고장 없음"), **PM 준수율** = 예정일이 기간 안인 PM 중 **예정일까지(당일 포함)** 완료한 비율(유예 0일, 13장 4). 정지 시간은 기간과 겹친 부분만 |
| 독립 동작 | MES·BEMS·SPC 중 꺼진 출처는 가져오기·전환 대기 목록에서만 빠진다. 작업지시·PM·지표는 그대로 |

## 4. DB 차분 — `cmms` 스키마 6테이블

공통 컬럼·제약은 다른 솔루션과 같다(`id`·`workspace_id`·`generation_id`·`created_at`, PK·UK(S, id)·범위 앵커 FK, 업무 FK `(S, 참조 id)` RESTRICT, FK 열 INDEX).

| 엔티티 | 하위 모듈 | 역할 |
|---|---|---|
| `cmms.asset` | asset | 설비 대장 |
| `cmms.pm_plan` | plan | 예방보전 계획 |
| `cmms.work_order` | work | 작업지시(BM·PM, 신호 출처 스냅샷 포함) |
| `cmms.work_log` | work | 작업 기록(추가만) |
| `cmms.spare_part` | parts | 예비품 |
| `cmms.part_usage` | parts | 부품 사용(추가만) |

### 4.1 설비·계획

| 테이블 | 컬럼(요약) | 규칙 |
|---|---|---|
| asset | code, name, asset_type(`INJECTION`/`ASSEMBLY`/`INSPECTION`/`HVAC`/`UTILITY`/`OTHER`), location varchar(100) null, source(`MES`/`BEMS`/`CMMS`), source_code varchar(40) null, is_active | UK(S, code). **UK_PARTIAL** (S, source, source_code) WHERE source <> 'CMMS'. CHECK source = 'CMMS' ⇔ source_code IS NULL. 코드 형식 CHECK |
| pm_plan | asset_id FK, code, title, checklist varchar(500), interval_days int(1~365), start_on date, last_done_on date null, is_active | UK(S, code). CHECK last_done_on IS NULL OR last_done_on ≥ start_on |

### 4.2 작업

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| work_order | wo_no, asset_id FK, kind(`BM`/`PM`), source(`MANUAL`/`BEMS_ALARM`/`SPC_SIGNAL`/`PM_PLAN`), source_ref varchar(60) null, source_summary varchar(300) null, pm_plan_id FK null, due_on date null, title varchar(200), description varchar(1000) null, status(`REQUESTED`/`IN_PROGRESS`/`COMPLETED`/`CANCELLED`), requested_at, failure_at null, started_at null, completed_at null, restored_at null, cause_category(`WEAR`/`LUBRICATION`/`ELECTRICAL`/`SETTING`/`EXTERNAL`/`OTHER`) null, action varchar(500) null, cancelled_at null, cancel_reason varchar(300) null | UK(S, wo_no). **UK_PARTIAL** (S, source, source_ref) WHERE source IN ('BEMS_ALARM','SPC_SIGNAL') AND status <> 'CANCELLED' — 신호 1건당 작업지시 1건. **UK_PARTIAL** (S, pm_plan_id, due_on) WHERE kind='PM' AND status <> 'CANCELLED'. CHECK: kind·source 짝(PM ⇔ PM_PLAN), PM ⇔ pm_plan_id·due_on 있음, 신호 출처 ⇔ source_ref 있음, BM ⇔ failure_at 있음, 상태별 시각·필수 칸(완료 ⇔ completed_at·cause·action, BM 완료 ⇔ restored_at ≥ failure_at, 취소 ⇔ cancelled_at·사유), started_at ≥ requested_at, completed_at ≥ started_at |
| work_log | work_order_id FK, logged_at, minutes int(1~1440), note varchar(300) | 추가만(SERVICE) |

### 4.3 예비품

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| spare_part | code, name, unit varchar(10), safety_stock numeric(12,3) ≥ 0, is_active | UK(S, code) |
| part_usage | work_order_id FK, spare_part_id FK, qty numeric(12,3) > 0, used_at | 추가만(SERVICE). INDEX (S, spare_part_id, used_at) |

### 4.4 core·규모

- `core.workspace_module` CHECK에 `'cmms'`(새 revision), 모듈 행 데이터 마이그레이션(킷 a). `core.app_review` 모듈 키 CHECK에도 `'cmms'`(FS-040 평가 대상, GW와 같은 방식).
- 업무 스키마 cmms 6. 현재 main 112 → **118테이블**. 상태 목록 work_order 1개.
- 스키마 버전 v0.17.0. Codex FS-030b·c(GW)가 마이그레이션을 추가하면, 먼저 main에 들어간 쪽 뒤로 down_revision을 옮긴다.

## 5. 계산 (서비스 한 곳 — `fs/cmms/metrics.py`)

| 값 | 식 |
|---|---|
| 다음 예정일 | (last_done_on ?? start_on) + interval_days |
| 정지 시간 | min(restored_at, 기간 끝) − max(failure_at, 기간 시작), 음수면 0 |
| MTTR | Σ(restored_at − failure_at) ÷ 완료 BM 수(시간, 소수 1자리) |
| MTBF | (기간 시간 − Σ정지 시간) ÷ 완료 BM 수. 0건이면 null("고장 없음") |
| PM 준수율 | 완료일(KST) ≤ due_on인 PM ÷ 예정일이 기간 안인 PM(취소 제외). 분모 0이면 null |

## 6. 트랜잭션·잠금

| TX | 내용 | 잠금 |
|---|---|---|
| TX-C1 작업지시 생성 | 수동 · 신호 전환(원천 조회로 존재·미전환 확인) · PM 생성(주기 도래 확인) → 번호 발번 → INSERT | 공간(번호 발번·중복 전환 직렬화) + 부분 유니크 두 겹 |
| TX-C2 시작 | REQUESTED → IN_PROGRESS | 공간 → 작업지시 |
| TX-C3 작업 기록·부품 사용 | 진행 중 확인 → INSERT | 공간 → 작업지시 |
| TX-C4 완료 | IN_PROGRESS → COMPLETED(+BM 복구 시각), PM이면 계획 마지막 수행일 UPDATE | 공간 → 작업지시 → PM 계획 |
| TX-C5 취소 | REQUESTED/IN_PROGRESS → CANCELLED | 공간 → 작업지시 |
| TX-C6 가져오기 | MES·BEMS 조회 → 없는 원천 코드만 INSERT | 공간 |

멱등: 변경 POST는 `Idempotency-Key`. 처리 시각은 DB `clock_timestamp()`(시계를 섞어 비교하지 않는다 — SPC 교훈).

## 7. 교차 조회 인터페이스

| 제공 | 함수 | 반환 |
|---|---|---|
| MES `fs/mes/interface.py` **(추가)** | `equipment(connection, scoped)` | `[{equipmentCode, name, equipmentType, locationCode, isActive}]`. MES 꺼짐 `None` |
| BEMS `fs/bems/interface.py` **(신규)** | `enabled` · `hvac_units` → `[{code, name, zoneCode}]` · `active_alarms` → `[{alarmId, zoneCode, metric, severity, status, raisedAt, peakValue, threshold}]`(해제 전) | 꺼짐 `None` |
| SPC `fs/spc/interface.py` **(추가)** | `equipment_signals(connection, scoped)` → `[{signalId, equipmentCode, lotNo, characteristicCode, characteristicName, rule, status, causeCategory, detectedAt}]`(미조치 + 원인 MACHINE 조치 완료 최근 30일) | 꺼짐 `None` |
| CMMS `fs/cmms/interface.py` **(신규)** | `enabled` · `equipment_in_maintenance(connection, scoped, codes)` → 진행 중(`REQUESTED`·`IN_PROGRESS`) BM이 있는 MES 출처 설비의 원천 코드 집합 | 꺼짐 `None` |

MES는 공정 실행 목록·상세와 설비 목록 응답에 `maintenance: true/false/null`을 붙인다(D52). 실행 로직은 바꾸지 않는다.

## 8. API 계약 (`/api/v1/cmms`)

| 메서드·경로 | 내용 |
|---|---|
| `GET /dashboard` | KPI(진행 중 작업지시·전환 대기 신호·주기 도래 PM·최근 30일 MTTR), 진행 중 작업지시 목록, 주기 도래 PM 목록 |
| `GET/POST/PATCH /assets` · `POST /assets/import {source: MES\|BEMS}` | 설비 대장 · TX-C6(추가 수·건너뜀 수) |
| `GET/POST/PATCH /pm-plans` · `POST /pm-plans/{id}/work-orders` | PM 계획(다음 예정일·주기 도래 포함) · TX-C1 PM 생성(주기 도래 아니면 409 `NOT_DUE`, 중복 409 `DUPLICATE`) |
| `GET /signals` | 전환 대기 신호(BEMS·SPC, 출처별 꺼짐이면 그 출처 `null`) + 이미 전환된 신호의 작업지시 번호 |
| `POST /work-orders {kind:BM, assetId, title, description?, failureAt, source?, sourceRef?}` | TX-C1 수동·신호 전환(원천 없음 404, 이미 전환 409 `ALREADY_CONVERTED`, 출처 꺼짐 409 `SOURCE_MODULE_DISABLED`) |
| `GET /work-orders?status=&kind=&assetId=` · `GET /work-orders/{id}` | 목록 · 상세(작업 기록·부품 사용 포함) |
| `POST /work-orders/{id}/start` · `/logs {minutes, note}` · `/parts {sparePartId, qty}` · `/complete {causeCategory, action, restoredAt?}` · `/cancel {reason}` | TX-C2~C5. 상태가 맞지 않으면 409 `INVALID_STATUS` |
| `GET/POST/PATCH /spare-parts` | 예비품(누적·최근 30일 사용, 안전 재고 참고 표시) |
| `GET /metrics?from=&to=` | 설비별 고장 건수·정지 시간·MTTR·MTBF, 전체 PM 준수율 |

## 9. 화면 (요약 — 상세는 [화면 설계서](../../ui/화면설계_CMMS_FS-029.md))

| ID | 화면 | 패턴 |
|---|---|---|
| C-01 | 대시보드 | D — KPI 4 · 진행 중 작업지시 · 주기 도래 PM |
| C-02 | 전환 대기 신호 | L + FormPanel — BEMS 경보·SPC 이상 → 고장 작업지시 전환 **(교차 조회 시연)** |
| C-03 | 작업지시 | L + DetailPanel wide — 시작·작업 기록·부품·완료·취소 **(CMMS 시연)** |
| C-04 | 예방보전 계획 | L + FormPanel — 다음 예정일·주기 도래·작업지시 생성 |
| C-05 | 설비 대장 | S — 목록·등록·MES/BEMS 가져오기 |
| C-06 | 예비품 | S — 목록·누적 사용·안전 재고 참고 |
| C-07 | 보전 지표 | D — 설비별 MTBF·MTTR·정지 시간 막대, PM 준수율 |

## 10. 합성 데이터 (약 150행)

| 대상 | 행 | 내용 |
|---|---:|---|
| asset | 11 | MES 8(가져오기 출처) + BEMS 공조기 2 + 직접 등록 1(UT-AIR 공용 압축기) |
| pm_plan | 12 | 사출 3·조립 3(주 1회 7일), 검사 2(14일), 공조 2(30일), 압축기 1(14일), INJ-02 금형 냉각 점검(7일). **1건은 업무 기준일에 주기 도래**(시연) |
| work_order | 약 40 | 최근 60일. PM 완료 약 30(기한 안 대부분, 2건 지연), BM 완료 7(INJ-02 2건 — 냉각수·히터, ASM-01 지그, ASM-03 공압, INS-01 센서, AHU-PRD 필터, UT-AIR 누설), **BM 진행 중 1(ASM-03 — 진행 중 실행 LT-0023, MES "보전 중" 배지 시연)**, 취소 1 |
| work_log | 약 55 | 작업지시당 1~3건 |
| spare_part | 8 | 냉각수 호스·히터 밴드·조립 지그 핀·공압 실린더 실·근접 센서·공조 필터·압축기 오링·그리스 |
| part_usage | 약 25 | |

- **전환 대기 신호는 시드로 만들지 않는다**: BEMS 시드의 확인 대기 CO₂ 경보 1건과 SPC 시드의 LT-0017 미조치 2건이 그대로 C-02에 보인다(시연 출발점).
- 지표가 설비별로 달라 보이게: INJ-02 MTTR 길고 고장 2건, ASM-03은 진행 중, 검사기는 고장 적음.
- 복사: 시각·날짜 컬럼은 기존 규칙으로 일수 이동. `wo_no`의 날짜 부분은 이동 후 날짜로 다시 계산한다(QMS 번호와 같은 방식). 달력 문자열 컬럼 없음.
- 템플릿 14,686 → 약 **14,840행**.

## 11. 수용 기준 (AC-185~200)

| AC | 기준 |
|---|---|
| 185 | MES·BEMS 가져오기는 같은 원천 코드를 두 번 만들지 않고, 원천이 바뀌어도 대장은 그대로다 |
| 186 | PM 다음 예정일 = (마지막 수행일 ?? 시작일) + 주기이고, 주기 도래가 아니면 PM 작업지시를 만들 수 없다(409) |
| 187 | 같은 PM 계획·예정일의 작업지시는 취소되지 않은 것 1건뿐이다 |
| 188 | 같은 BEMS 경보·SPC 이상은 취소되지 않은 작업지시 1건으로만 전환된다. 취소하면 다시 전환할 수 있다 |
| 189 | 전환해도 BEMS 경보·SPC 이상의 상태는 바뀌지 않는다 |
| 190 | 상태는 REQUESTED → IN_PROGRESS → COMPLETED / CANCELLED만 가능하고, 완료·취소 뒤 바꿀 수 없다(409) |
| 191 | 완료에는 원인 분류·조치 내용, BM은 복구 시각(정지 시작 이후)이 필요하다 |
| 192 | 작업 기록·부품 사용은 진행 중에만 추가되고 수정·삭제할 수 없다 |
| 193 | PM 완료는 계획의 마지막 수행일을 완료일로 바꾼다 |
| 194 | MTTR·MTBF·PM 준수율은 5장 식과 같다(기간 경계에 걸친 정지는 겹친 부분만) |
| 195 | 진행 중 BM이 있는 MES 설비는 MES 응답에서 `maintenance=true`, 완료 뒤 false, CMMS를 끄면 null이고 MES 실행은 그대로다 |
| 196 | MES·BEMS·SPC를 끄면 그 출처의 가져오기·전환만 막히고(409 / null) 나머지 CMMS는 동작한다 |
| 197 | 같은 요청을 다시 보내도 작업지시가 한 번만 생긴다(멱등·부분 유니크) |
| 198 | 다른 공간·세대의 설비·작업지시는 보이지 않는다(X3) |
| 199 | CMMS는 다른 스키마를 직접 조회하지 않는다(R6: `fs.mes`·`fs.bems`·`fs.spc`의 interface만). MES는 `fs.cmms.interface`만 import |
| 200 | 시드: 전환 대기 신호 = BEMS 확인 대기 경보 1 + SPC LT-0017 이상 2, 주기 도래 PM 1, 진행 중 BM 1(ASM-03 → MES 배지) |

## 12. 하지 않는 것 / 후속

결정서 5장 전부. 추가로: PM 정지 시간, 작업자 이름·배정, 작업지시 첨부·사진, 예비품 단가·비용, 설비 계층(부속 설비), 보전 캘린더 화면.

## 13. 결정 (2026-10-01 사용자 확정)

1. **신호 전환은 별도 테이블 없이 작업지시의 출처·원천 id + 부분 유니크**(6테이블) — 권장대로.
2. **BEMS 경보의 기본 설비 = 그 구역의 공조기 대장, 사람이 변경 가능** — 권장대로.
3. **작업 기록·부품 사용은 진행 중에만, 추가만** — 권장대로.
4. **PM 준수 유예 0일 — 예정일까지(당일 포함) 완료해야 준수.** 권장(3일)과 다르게 사용자가 정했다. 시드의 지연 PM은 준수율에 그대로 드러난다.
5. **PM 지연 완료 시 다음 예정일 = 완료일 + 주기** — 권장대로.
