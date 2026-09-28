# FS-025 BEMS 모듈 설계서

작성일: 2026-09-28 (Claude Code)
상태: **확정 — 사용자 승인 2026-09-28.** 13장 결정 4건은 권장안(환경 14일 · 진행 1~6시간·T+1일까지 · 설정값은 명령으로만 · 수동 명령은 다음 스케줄 경계까지)으로 확정. 전체 설계 확인 전에는 `schema.json`·마이그레이션·코드를 바꾸지 않는다.
전제: [FS-025 결정서](../../plan/BEMS도입_공용에너지_결정_FS-025.md)(D18~D23), [FS-023 D9 교차 조회](../../plan/QMS도입_교차조회_결정_FS-023.md), [FS-013](../../plan/독립솔루션_전환결정_FS-013.md)

---

## 1. 이 모듈은 무엇인가

**공용 설비(조명·공조·사무동)의 에너지와 실내 환경을 계측하고, 공조기를 스케줄·설정값·제어 명령으로 운전하며, 환경 경보를 관리하고, 사업장 전력을 제조·공용·잔여로 분해하는 건물 에너지 솔루션이다.**

```
FEMS 사업장 전력(수전) ──조회──┐
FEMS 제조 전력(설비 배분) ──조회──┤──▶ 분해: 전체 = 제조 + 공용(조명·공조·사무동) + 잔여(음수면 불일치)
BEMS 공용 계측 ───────────────┘
운전 스케줄 · 설정값 · 제어 명령 ─▶ 모의 공조기 ─▶ [1시간 진행] ─▶ 온도·습도·CO₂·공조 전력 관측 ─▶ 경보 규칙 평가
                                                                                     └▶ 경보 발생 → 확인 → 해제
```

평가자 3분 동선:

```
대시보드(분해 막대·활성 경보·구역 온도)
  → 에너지 분해(제조 288 · 공용 132 · 잔여 30 같은 일별 분해 — FEMS 조회)
  → 공조 운전: 사무동 냉방 설정 26 → 23℃, 1시간 진행 → 온도 하강·공조 전력 증가
  → 경보: CO₂ 상한 초과 발생 → 확인 → 환기(팬 운전) → 진행 → 해제
```

## 2. 하위 모듈

| 하위 모듈 | 소유 테이블 | 교차 조회 |
|---|---|---|
| `bems_master` 기준정보 | 구역, 공용 계측기, 환경 센서, 공조기 | — |
| `metering` 계측 | 공용 전력 관측, 환경 관측 | FEMS 사업장·제조 전력(분해) |
| `hvac` 공조 운전 | 운전 스케줄, 제어 명령 | — |
| `alarm` 경보 | 경보 규칙, 경보 | — |

소유 **10테이블**. 스키마 간 FK 0건. BEMS 구역은 FEMS 공간과 별개다(D19 — 코드가 겹칠 수 있을 뿐 연결되지 않는다).

## 3. 업무 규칙

| 규칙 | 내용 |
|---|---|
| 관측 간격 | 1시간(D23). 관측값은 구간 `[period_start, period_start + 1h)`의 값(전력은 kWh, 환경은 구간 평균). 계측기·센서·구간당 1건 |
| 관측 출처 | `SEED`(합성 과거) / `SIMULATION`(1시간 진행으로 생성). 수동 입력·수정은 없다(1차). 관측값은 불변 |
| 분해(D20) | 일·월 단위. 잔여 = FEMS 사업장 전력 − FEMS 제조 전력 − Σ BEMS 공용 전력. 기간 안 FEMS·BEMS 관측이 모두 있는 시간만 셈한다. 잔여 < 0 → "불일치" 배지·원인 안내(공용 계측 과대·설비 배분 누락) |
| 설정값 | 구역별 냉방 온도·난방 온도·CO₂ 상한. **바꾸는 방법은 제어 명령(`SET_SETPOINT`)뿐**이며 현재 설정값 = 그 구역의 마지막 적용 명령. 범위 검증(냉방 20~30℃, 난방 16~24℃, 냉방 ≥ 난방 + 2, CO₂ 600~2000 ppm) |
| 공조기 상태 | `OFF` / `COOL` / `HEAT` / `FAN` + 운전 출처 `MANUAL`(수동 명령) / `SCHEDULE`. 수동 명령은 다음 스케줄 경계까지 유지하고, 경계에서 스케줄 모드로 돌아간다 |
| 운전 스케줄 | 공조기별 평일·주말 시간대(시작 시·종료 시·모드). 같은 공조기·요일 구분에서 시간대가 겹치면 거부 |
| 제어 명령 | `POWER_ON`·`POWER_OFF`·`SET_MODE`·`SET_SETPOINT`. 명령은 불변 이력이다. 적용 결과 `APPLIED`/`REJECTED`(사유: 범위 밖·이미 같은 상태·공조기 사용 안 함). 스케줄 경계 전환도 `SCHEDULE` 출처 명령으로 남긴다 |
| 1시간 진행(D21) | 시뮬레이션 시각 = 가장 늦은 관측 구간 + 1h. 스케줄·명령을 반영한 공조기 상태로 다음 1시간의 환경·공조 전력·조명·사무동 전력을 결정적 모델(5장)로 만들고 경보 규칙을 평가한다. **업무 기준일(T)의 다음 날을 넘지 않는다**(시드 시각 규칙 V10) |
| 경보 규칙 | 센서 항목(온도·습도·CO₂) · 비교(`HIGH`/`LOW`) · 한계값 · 지속 시간(연속 N시간) · 등급(`WARNING`/`CRITICAL`) · 대상 구역. 사용 안 함 가능 |
| 경보(D22) | 규칙 조건이 N시간 연속 참이면 `raised`, 사람이 `acknowledged`(메모 선택), 조건이 1시간 거짓이면 `cleared`(확인 전에 해제될 수도 있다). 규칙·센서당 해제되지 않은 경보 1건. 경보는 불변 이력(상태 전이만) |
| 독립 동작 | FEMS 꺼짐이면 분해만 계산 불가. 나머지는 동작 |

## 4. DB 차분 — `bems` 스키마 10테이블

공통 컬럼·제약은 QMS·WMS와 같다(`id`·`workspace_id`·`generation_id`·`created_at`, PK·UK(S, id)·범위 앵커 FK, 업무 FK `(S, 참조 id)` RESTRICT, FK 열 INDEX).

| 엔티티 | 하위 모듈 | 역할 |
|---|---|---|
| `bems.zone` | bems_master | 구역(사무동·생산동 공조 구역·유틸리티) |
| `bems.meter` | bems_master | 공용 전력 계측기(용도: 조명·공조·사무동·기타) |
| `bems.sensor` | bems_master | 환경 센서(온도·습도·CO₂) |
| `bems.hvac_unit` | bems_master | 공조기(모의 상태) |
| `bems.energy_reading` | metering | 공용 전력 관측(1시간) |
| `bems.environment_reading` | metering | 환경 관측(1시간) |
| `bems.schedule_slot` | hvac | 공조기 운전 스케줄 시간대 |
| `bems.control_command` | hvac | 제어 명령 이력(설정값 변경 포함) |
| `bems.alarm_rule` | alarm | 경보 규칙 |
| `bems.alarm` | alarm | 경보 발생·확인·해제 |

### 4.1 기준정보

| 테이블 | 컬럼(요약) | 규칙 |
|---|---|---|
| zone | code, name, kind(`OFFICE`/`PRODUCTION`/`UTILITY`), floor_area_m2 numeric(10,2) null, is_active | UK(S, code) |
| meter | zone_id FK, code, name, usage(`LIGHTING`/`HVAC`/`OFFICE`/`OTHER`), unit(`kWh` 고정 CHECK), is_active | UK(S, code) |
| sensor | zone_id FK, code, metric(`TEMP`/`HUMIDITY`/`CO2`), unit(℃·%·ppm, metric과 CHECK로 일치), is_active | UK(S, code), UK(S, zone_id, metric) — 구역·항목당 센서 1개(1차) |
| hvac_unit | zone_id FK, code, name, meter_id FK null(공조 전력 계측기), rated_kw numeric(8,2), state(`OFF`/`COOL`/`HEAT`/`FAN`), control_source(`SCHEDULE`/`MANUAL`), state_changed_at, is_active | UK(S, code). `meter_id`는 usage=`HVAC` 계측기만(SERVICE) |

### 4.2 관측

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| energy_reading | meter_id FK, period_start timestamptz, value numeric(12,3) ≥ 0, quality(`valid`/`invalid`), source(`SEED`/`SIMULATION`) | UK(S, meter_id, period_start). 불변 |
| environment_reading | sensor_id FK, period_start, value numeric(8,2), quality, source | UK(S, sensor_id, period_start). 불변 |

### 4.3 공조 운전

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| schedule_slot | hvac_unit_id FK, day_kind(`WEEKDAY`/`WEEKEND`), start_hour 0~23, end_hour 1~24(> start), mode(`COOL`/`HEAT`/`FAN`), is_active | 겹침 거부(SERVICE) |
| control_command | hvac_unit_id FK null(설정값은 구역 단위라 null 가능), zone_id FK, command(`POWER_ON`/`POWER_OFF`/`SET_MODE`/`SET_SETPOINT`), mode null, setpoint_kind(`COOL_TEMP`/`HEAT_TEMP`/`CO2_MAX`) null, value numeric(8,2) null, source(`MANUAL`/`SCHEDULE`/`SEED`), requested_at, result(`APPLIED`/`REJECTED`), reject_reason null, note | 명령별 필수 칸 CHECK. 불변. INDEX (S, zone_id, setpoint_kind, requested_at) — 현재 설정값 조회 |

### 4.4 경보

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| alarm_rule | zone_id FK, metric, comparator(`HIGH`/`LOW`), threshold numeric(8,2), duration_hours 1~24, severity(`WARNING`/`CRITICAL`), is_active | UK(S, zone_id, metric, comparator) |
| alarm | alarm_rule_id FK, sensor_id FK, status(`raised`/`acknowledged`/`cleared`), raised_at, peak_value, acknowledged_at null, ack_note null, cleared_at null | **UK_PARTIAL** (S, alarm_rule_id, sensor_id) WHERE status <> 'cleared'. 상태·시각 일치 CHECK. 해제 후 불변 |

### 4.5 core·규모

- `core.workspace_module` CHECK에 `'bems'`(새 revision), 모듈 행 데이터 마이그레이션.
- 업무 스키마 bems 10 → 전체 **93테이블**. 상태 목록 alarm 1개.

## 5. 1시간 진행 모델 (결정적, 외부 데이터 없음)

| 값 | 모델 |
|---|---|
| 외기 대리값 | 시각별 고정 곡선(최저 18℃ 05시 → 최고 29℃ 15시). 외부 날씨 데이터 없음 |
| 실내 온도 | `다음 = 현재 + 0.25 × (외기 − 현재) + 공조 효과`. COOL: 설정값보다 높으면 −1.2(설정값 아래로 내려가지 않음), HEAT: 반대, FAN·OFF: 0 |
| 습도 | COOL이면 −1.5%p, 그 외 외기 곡선 쪽으로 0.1배 이동. 30~70% 범위 |
| CO₂ | 재실 곡선(사무동 09~18시 +120 ppm/h, 그 외 −30 — FS-025c 보정: +10이면 밤새 쌓여 경보가 다시 떴다) − 환기(공조기가 켜져 있으면 −150). 하한 420 |
| 공조 전력 | OFF 0, FAN 0.25 × 정격, COOL·HEAT `정격 × min(1, 0.4 + 0.15 × |현재 − 설정값|)` |
| 조명·사무동 | 구역 운영 시간(평일 08~19시) 주간값, 그 외 야간값 — 시드와 같은 고정표 |

모델 상수는 서비스 한 곳(`fs/bems/simulation.py`)에 둔다 — 조정 여지를 남긴다.

## 6. 트랜잭션·잠금

| TX | 내용 | 잠금 |
|---|---|---|
| TX-B1 제어 명령 | 검증 → 명령 INSERT → (APPLIED면) 공조기 상태 UPDATE | 공간 → 공조기 |
| TX-B2 1시간 진행 | 시각 결정 → 스케줄 경계 전환 명령 → 관측 INSERT → 경보 평가(발생·해제) | 공간(공간 잠금으로 동시 진행 직렬화). 관측 UK로 같은 시각 두 번 생성 방지 |
| TX-B3 경보 확인 | raised → acknowledged | 공간 → 경보 |

멱등: 변경 POST는 `Idempotency-Key`. 1시간 진행은 요청 멱등 + 관측 UK로 두 겹.

## 7. 교차 조회 인터페이스 — `fs/fems/interface.py` (새 파일)

| 함수 | 반환 | 조건 |
|---|---|---|
| `site_electricity(scope, start, end)` | `[{hour, kwh}]` 또는 `None` | 전력 에너지원·최상위 계측기(parent 없음)의 유효 관측 — F-01과 같은 기준 |
| `manufacturing_electricity(scope, start, end)` | `[{hour, kwh}]` 또는 `None` | 전력 `DIRECT_METER` 설비 배분(시간 합) |
| `enabled(scope)` | bool | |

## 8. API 계약 (`/api/v1/bems`)

| 메서드·경로 | 내용 |
|---|---|
| `GET /dashboard` | 오늘·어제 분해, 활성 경보 수(등급별), 구역별 현재 온도·CO₂·공조 상태, 시뮬레이션 시각 |
| `GET /breakdown?granularity=day\|month&from=&to=` | 기간별 전체·제조·공용(용도별)·잔여·불일치. FEMS 꺼짐 409 `SOURCE_MODULE_DISABLED` |
| `GET /environment?zoneId=&from=&to=` | 센서별 시간 관측 |
| `GET /energy?meterId=&from=&to=` | 계측기별 시간 관측 |
| `GET/POST/PATCH /zones·/meters·/sensors·/hvac-units` | 기준정보(쓰인 행 삭제 대신 사용 안 함) |
| `GET /hvac-units/{id}` | 상태·현재 설정값·최근 명령·스케줄 |
| `POST /commands` | TX-B1 `{hvacUnitId?, zoneId, command, mode?, setpointKind?, value?, note?}` → 명령 결과(REJECTED도 201로 기록하고 사유 반환) |
| `GET /commands?zoneId=&hvacUnitId=` | 명령 이력 |
| `GET/PUT /hvac-units/{id}/schedule` | 스케줄 시간대 전체 교체(겹침 400) |
| `POST /simulation/advance` | TX-B2 `{hours: 1}`(1~6) → 생성 관측·전환 명령·경보 변화 요약. T+1일 초과 409 `SIMULATION_LIMIT` |
| `GET /alarms?status=` · `POST /alarms/{id}/acknowledge` | TX-B3 |
| `GET/POST/PATCH /alarm-rules` | 규칙 |

## 9. 화면 (요약 — 상세는 [화면 설계서](../../ui/화면설계_BEMS_FS-025.md))

| ID | 화면 | 패턴 |
|---|---|---|
| B-01 | 건물 대시보드 | D — 분해 막대(제조·공용·잔여)·활성 경보·구역 카드 |
| B-02 | 에너지 분해 | L — 일·월 분해 표·용도별 공용·불일치 배지 **(FEMS 교차 조회 시연)** |
| B-03 | 환경 모니터링 | D/L — 구역별 온도·습도·CO₂ 추이, 설정값 선 |
| B-04 | 공조 운전 | V + FormPanel — 공조기 상태·현재 설정값·제어 명령·"1시간 진행" **(제어 시연)** |
| B-05 | 운전 스케줄 | W — 공조기별 평일·주말 시간대 행 편집 |
| B-06 | 경보 | L + DetailPanel — 발생·확인·해제, 규칙 편집 |
| B-07 | 기준정보 | P — 구역 → 계측기·센서·공조기 |

## 10. 합성 데이터 (약 5,300행)

| 대상 | 행 | 내용 |
|---|---:|---|
| zone | 3 | Z-OFF 사무동(OFFICE), Z-PRD 생산동 공조 구역(PRODUCTION), Z-UTL 유틸리티(UTILITY) |
| meter | 3 | BM-LGT 조명(전 구역 합), BM-HVAC 공조, BM-OFF 사무동 콘센트 |
| energy_reading | 2,160 | 3 × 24 × 30일(T−30~T−1, FEMS와 같은 기간). **합이 FEMS 수전에 숨긴 공용 부하(주간 25·야간 15 kWh/h)보다 작게** — 예: 조명 8/2, 공조 10/6, 사무동 4/3 → 잔여 주간 3·야간 4 kWh/h(음수 없음) |
| sensor | 6 | 사무동·생산동 × 온도·습도·CO₂ |
| environment_reading | 2,016 | 6 × 24 × 14일 |
| hvac_unit | 2 | AHU-OFF 사무동, AHU-PRD 생산동 |
| schedule_slot | 4 | 공조기별 평일 08~19 COOL, 주말 10~16 FAN |
| control_command | 약 20 | 과거 설정값 변경·수동 전원·스케줄 전환 이력 |
| alarm_rule | 4 | 사무동 CO₂ 1,000 ppm 2시간(WARNING), 온도 28℃ 2시간(WARNING), 생산동 온도 30℃ 1시간(CRITICAL), 습도 70% 3시간 |
| alarm | 약 4 | 해제된 과거 경보 3 + **확인 대기 1(사무동 CO₂ — 시연용)** |

- 복사: 시각 컬럼은 기존 규칙으로 일수 이동. 달력 문자열 컬럼 없음.
- 템플릿 7,691 → 약 **13,000행**. 게스트 복사 시간 증가(현재 0.47초)를 FS-025c에서 실측하고, 1초를 넘으면 환경 관측 기간을 줄인다.

## 11. 수용 기준 (AC-125~138)

| AC | 기준 |
|---|---|
| 125 | 분해 합: 전체 = 제조 + 공용 + 잔여(표시 반올림 전 값 기준) |
| 126 | 잔여 < 0인 기간은 불일치로 보이고 숨기지 않는다 |
| 127 | FEMS를 끄면 분해만 409 `SOURCE_MODULE_DISABLED`, 나머지 BEMS 기능은 동작. BEMS를 꺼도 FEMS는 그대로 |
| 128 | 설정값은 명령으로만 바뀌고, 범위 밖 설정은 REJECTED로 기록되며 현재 설정값은 그대로다 |
| 129 | 수동 명령은 다음 스케줄 경계에서 스케줄 모드로 돌아가고 전환이 SCHEDULE 명령으로 남는다 |
| 130 | 1시간 진행은 같은 요청을 다시 보내도 관측이 한 번만 생긴다(멱등·UK) |
| 131 | 냉방 설정값을 낮추고 진행하면 다음 시간 실내 온도는 내려가고 공조 전력은 늘어난다 |
| 132 | 조건이 지속 시간 동안 참이면 경보가 1건만 발생하고, 조건이 풀리면 해제된다 |
| 133 | 경보 확인은 사람만 하며, 해제된 경보는 바꿀 수 없다 |
| 134 | 스케줄 시간대 겹침은 거부된다 |
| 135 | 시뮬레이션은 업무 기준일 다음 날을 넘지 않는다 |
| 136 | 관측값·명령 이력은 수정·삭제할 수 없다 |
| 137 | 다른 공간·세대의 관측·경보는 보이지 않는다(X3) |
| 138 | BEMS는 FEMS 테이블을 직접 조회하지 않는다(R6: `fs.fems.interface`만 import) |

## 12. 하지 않는 것 / 후속

결정서 5장 전부. 추가로: 구역·항목당 센서 여러 개, 에너지 관측 수동 입력·보정, 공용 에너지 목표·원단위.

## 13. 결정이 필요한 것 (승인 시 함께 확인)

1. **환경 관측 기간**: 1시간 간격 **최근 14일**(약 2,000행) — 30일이면 약 4,300행. 권장: 14일(공용 전력은 FEMS에 맞춰 30일).
2. **1시간 진행 한도**: 한 번에 1~6시간, 업무 기준일 다음 날까지. 권장: 그대로.
3. **설정값을 명령으로만 바꾸는 것**(별도 설정값 테이블 없음 — 이력 = 명령). 권장: 그대로.
4. **수동 명령 유지 범위**: 다음 스케줄 경계까지(그 뒤 스케줄 복귀). 권장: 그대로.

## 14. 구현 기록 (FS-025a, 2026-09-28)

| 항목 | 구현 |
|---|---|
| 메타데이터 | `tools/apply_fs025a.py`(멱등) → `schema.json` **v0.12.0 / FS-025a / 93테이블**(bems 10), 954컬럼, FK 209, 제약·정책 726(bems C647~C725, R187~R208). 상태 목록에 `bems.alarm.status`·`bems.hvac_unit.state` |
| DB 제약으로 둔 규칙 | 명령별 필수 칸(공조기·모드·설정값 항목/값), 거부 ↔ 사유, 경보 상태 ↔ 시각, 센서 항목 ↔ 단위(℃·%·ppm), 스케줄 시간 범위. 정시 구간·스케줄 겹침·설정값 범위·계측기 용도 일치는 SERVICE |
| 마이그레이션 | `20260928_fs025a_bems_schema.py`(revision `fs025a_bems`, down `fs024b_wms_module`, 고정 SQL, 모듈 CHECK `c22_check`에 `'bems'`) + **`20260928_fs025b_bems_module_rows.py`(`fs025b_bems_module`, 기존 공간에 bems 행)** — WMS에서 모듈 행을 API 단계로 미뤘다가 로컬에서 "꺼짐"으로 보였던 일 때문에 DB 단계에 함께 둔다. 새 공간·시드 템플릿도 bems 행(7개), 시드 7,691 → 7,692 |
| 격리 | `audit_schema_isolation.py` FORBIDDEN에서 `bems` 제거(R4 해제), BUSINESS에 bems. `tools/test_fs014.py`의 R4 예시에서 bems 삭제 |
| 검증 도구 | `validate_db_design.py` FS-025a 엔티티 목록·`validate_bems`(관측 구간 유일, 규칙·센서당 활성 경보 1건, 설정값 테이블 없음, 교차 FK 없음, 모듈 키), `tools/test_fs025a.py` 3. `verify_ddl_matches_schema.py`에 bems + **`%` 이스케이프**(CHECK `unit = '%'`를 `exec_driver_sql`이 psycopg 자리표시자로 읽던 문제) |
| 산출물 | Excel 31시트·ERD `bems.mmd`, ERD 탐색기·Excel의 "후속 예약 설계" 표시 제거 |

## 15. 구현 기록 (FS-025b 1부 API, 2026-09-28)

| 항목 | 구현 |
|---|---|
| 모듈 | `backend/src/fs/bems/` — `simulation.py`(모델 상수·계산, `__main__` 자체 점검), `service.py`, `schema.py`, `router.py`, `main.py`에 `/api/v1/bems` 등록. 계약: [API 계약서 16장](../../architecture/API계약서_FS-010.md) |
| FEMS 조회 | `fs/fems/interface.py`(신규) — `enabled`·`site_electricity`(최상위 전력 계측기)·`manufacturing_electricity`(DIRECT_METER 배분). 분해는 이것만 읽는다(R6) |
| 시뮬레이션 시계 | 다음 구간 = 마지막 관측 + 1시간(KST), 이력이 없으면 업무 기준일 00:00. 한도 T+1 00:00. **수동 명령도 이 시계로 기록**해 스케줄 명령·관측과 같은 시간축에 둔다(실제 시각으로 두면 명령 이력 순서가 뒤집혔다) |
| 스케줄 경계 | 이번 구간과 앞 구간의 스케줄 모드가 다르면 경계. 수동 운전은 경계에서만 스케줄로 돌아가고 `source=SCHEDULE` 명령을 남긴다 |
| 테스트 | `backend/tests/test_bems.py` 12 — 모듈 행, 기준정보 규칙, 설정값 거부(AC-128), 스케줄 겹침(AC-134), 진행 멱등(AC-130), 냉방 인과(AC-131), 수동→스케줄(AC-129), 경보 발생·해제·확인(AC-132·133), 한도(AC-135), 분해·불일치(AC-125·126), FEMS 꺼짐(AC-127), 격리(AC-137) |

## 16. 구현 기록 (FS-025c 시드·도움말·흐름 맵, 2026-09-28)

| 항목 | 구현 |
|---|---|
| 시드 | `seed/generate.py` `_bems` — **1시간 진행과 같은 모델(`fs.bems.simulation`)을 30일 동안 시간 단위로 돌려** 공용 전력(3계측기 × 720시간 = 2,160)과 환경(6센서 × 14일 = 2,016)을 만든다. 공조기 AHU-OFF(12 kW, BM-HVAC 계측)·AHU-PRD(18 kW, 계측 없음 → 잔여), 스케줄 평일 08~19 냉방·주말 10~16 송풍. 명령 16(설정값 적용 3·거부 1, 수동 정지 4, 최근 2일 스케줄 전환 8). 경보 규칙 4(설계값), 경보 4 = 수동 정지일 CO₂ 경보(해제 3 + **T−1 확인 대기 1**, 시연용). 합 **4,218행**, 템플릿 7,692 → **11,910**, 복사 11,908 |
| 잔여 | 공용 최대 주간 24·야간 5 kWh/h < FEMS 숨긴 공용 부하 25·15 → 30일 모두 잔여 ≥ 0(불일치 없음). 불일치 시연은 테스트(AC-126)에서 만든다 |
| 모델 보정 | `CO2_IDLE` +10 → **−30 ppm/h**(비재실 자연 환기). +10이면 밤새 CO₂가 쌓여 해제 직후 같은 경보가 다시 떴다 |
| 설계와 다른 점 | 경보는 설계 "해제 3 + 확인 대기 1"과 같다. 행 수는 설계 추정 약 5,300이 아니라 4,218(추정에 관측 외 행을 넉넉히 잡았다). 스케줄 전환 명령은 시드 크기 때문에 최근 2일만 남긴다. 확인 대기 경보는 T−1이 평일일 때만 남는다(T−1이 주말이면 재실이 없어 경보가 생기지 않고 해제 4) |
| 복사 시간 | 중앙값 **0.509초**·최대 0.619초(10회, 이전 0.470초) — 1초 미만이라 환경 기간을 줄이지 않는다 |
| 도움말·흐름 맵 | `content/help/bems/b-01~07.md`, 공통 안내 "솔루션 간 읽기 전용 조회"에 BEMS 예시. 흐름 맵 `building_energy`를 업무 노드(`bems/b-02`)로, `energy_master → building_energy` "제조·공용·잔여로 분해한다(FEMS 조회)" 실선. 스키마의 업무 노드 모듈·도움말 패턴에 bems. `content/cards/bems.md` 삭제, P-04는 SCM만(P-02·P-03·P-04 도움말 갱신) |
