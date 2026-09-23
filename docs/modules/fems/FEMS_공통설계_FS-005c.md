# FS-005c FEMS 공통 설계 — 다중 에너지원 구조

작성일: 2026-09-20. 상태: **제안 · 미반영.** 논리 설계만 있으며 메타데이터 v0.3.0에 반영되지 않았다.

> **이 문서는 현재 기준이 아니다.** 기준본은 `schema.json` v0.3.0(FS-007b)이며 거기서 FEMS는 `energy_reading`·`energy_allocation` 2개로 사실상 전력 전용이다.
> 본 문서가 제안하는 다중 에너지원 구조(core +2 / fems +4, 54 → 60테이블)를 채택하려면
> 메타데이터·Excel·ERD·시드 정의를 함께 재생성해야 한다. 채택 여부 결정 대기 중이다.
기준: [FS-005 공통 ERD](../../architecture/공통ERD_데이터관계_FS-005.md) 5장, [FS-005a 차분 설계](../../architecture/차분설계_게스트_ERP_프로세스맵_FS-005a.md), [FS-005b 시드 정의](../../architecture/합성데이터_시드정의_FS-005b.md).
성격: FS-005의 FEMS/BEMS 연결 설계를 **다중 에너지원 구조로 확장**하는 순증 차분이다.

---

## 1. 무엇을 바꾸는가

FS-005의 FEMS 설계는 사실상 **전력 전용**이다. `core.meter`에 `measurement_kind`가 하나 붙고 `fems.energy_reading`이 kWh 값을 받는 구조라, 가스·유량·스팀을 넣을 자리가 없다.

표준 FEMS는 공장이 쓰는 **모든 에너지원**을 다룬다. 전력만 관리하는 시스템은 FEMS가 아니라 전력 관리 시스템이다. 이번 차분의 목적은 에너지원을 1급 축으로 올리는 것이다.

| 축 | 기존 | 변경 후 |
|---|---|---|
| 에너지원 | 없음 (전력 암묵) | `core.energy_source` — 전력·가스·용수·스팀·압축공기 |
| 측정 항목 | 계측기에 1개 고정 | `core.meter_channel` — 계측기 1대가 여러 항목 측정 |
| 단위 | kWh 암묵 | 에너지원별 고유 단위 (kWh / Nm³ / m³ / ton) |
| 합산 | 단순 더하기 | **1차에너지 환산 후 합산** |
| 배출계수 | 단일 | 에너지원별·연도별 |
| 요금제 | 없음 | 에너지원별 |

### 1.1 가장 중요한 결정 — 환산 없이는 합산할 수 없다

전력 12,000 kWh와 가스 800 Nm³를 더하면 12,800이 나오지만 **아무 의미가 없다.** 에너지원이 다르면 단위가 다르고, 단위가 다르면 총량도 원단위도 계산되지 않는다.

그래서 에너지원마다 **1차에너지 환산계수**(TOE 또는 kWh 등가)가 필요하고, 모든 합산·원단위·목표 비교는 환산값 기준으로 한다. 이 하나가 전력 전용 설계와 다중 에너지원 설계를 가르는 지점이다.

원본 값과 환산값을 함께 보여주고, 어떤 계수로 환산했는지 근거를 표시한다. 환산 근거를 숨긴 총량은 학습 자료로도 실무 자료로도 쓸 수 없다.

---

## 2. 소유 모듈 배치

FS-005의 원칙("계측 인프라는 core, 관측값은 소유 모듈")을 그대로 따른다.

| 대상 | 소유 | 이유 |
|---|---|---|
| 에너지원, 계측기, 계측 채널 | **core** | FEMS와 BEMS가 함께 참조한다. `core.meter`가 이미 core인 것과 같은 이유 |
| 관측값, 배분 | fems / bems | 기존 `owner_module` 분리 유지 |
| 배출계수, 요금제, 목표, 기준선 | **fems** | 에너지 분석 정책이며 BEMS가 쓰지 않는다 |

계측 채널을 fems에 두면 BEMS가 fems 테이블을 참조하게 되어 모듈 경계가 깨진다. core에 둔다.

---

## 3. 신규 테이블 (6개)

### core.energy_source — 에너지원 기준정보

| 속성 | 내용 |
|---|---|
| S, source_code | ELEC / GAS / WATER / STEAM / AIR. (S,code) UNIQUE |
| source_name | 표시명 |
| source_kind | `ELECTRIC` / `FUEL` / `HEAT` / `UTILITY` |
| measure_unit | 계측 단위. kWh / Nm³ / m³ / ton |
| is_billable | 요금 부과 대상 여부. 압축공기처럼 사내 생산 유틸리티는 false |
| is_active | 사용 여부 |

환산계수를 여기 컬럼으로 두지 않는다. 계수는 연도별로 개정되므로 아래 `fems.energy_factor`에서 관리한다.

### core.meter_channel — 계측 채널

계측기 1대가 여러 항목을 동시에 측정하는 현실을 반영한다. 전력량계 한 대가 유효전력량·순시전력·역률을 함께 낸다.

| 속성 | 내용 |
|---|---|
| S, meter_id, channel_code | (S, meter, channel_code) UNIQUE |
| energy_source_id | 이 채널이 재는 에너지원 |
| measurement_kind | `CUMULATIVE`(누적) / `INSTANT`(순시) |
| unit | 채널 단위. 에너지원 단위와 다를 수 있다 (kW vs kWh) |
| multiplier | 계기 배수. numeric, > 0 |
| owner_module | `fems` / `bems`. `core.meter`의 소유 모듈과 일치해야 한다 |
| is_active | 사용 여부 |

**합산 대상은 `CUMULATIVE` 채널만이다.** 순시값을 기간 합계에 더하지 않는다. 이 구분이 없으면 kW와 kWh를 섞어 더하는 흔한 오류가 그대로 들어온다.

### fems.energy_factor — 환산·배출 계수

환산계수와 배출계수를 한 테이블로 둔다. 둘 다 "에너지원 × 적용연도 × 계수값 × 출처" 구조가 같고, 분리하면 같은 관리 화면을 두 벌 만들게 된다.

| 속성 | 내용 |
|---|---|
| S, energy_source_id, factor_kind, effective_year | (S, source, kind, year) UNIQUE |
| factor_kind | `PRIMARY`(1차에너지 환산) / `EMISSION`(탄소 배출) |
| factor_value | numeric. > 0 |
| factor_unit | TOE/단위, tCO₂eq/단위 |
| source_note | 계수 출처 |

`effective_year`는 `varchar(4)` + CHECK. 연도는 정수가 아닌 텍스트로 다룬다.

탄소 배출량은 **총 에너지 소비량 × 배출계수**로 산출한다. 에너지원이 여러 개면 원별로 계산해 합산하며, 환산값에 배출계수를 곱하지 않는다. 환산은 에너지 총량용, 배출계수는 원별 배출량용이다. 이 둘을 섞는 것이 다중 에너지원 FEMS에서 가장 흔한 계산 오류다.

### fems.tariff — 요금제 기준정보

| 속성 | 내용 |
|---|---|
| S, energy_source_id, tariff_code | (S, source, tariff_code) UNIQUE |
| tariff_name, contract_type | 표시명, 계약 종별 |
| basic_charge | 기본요금 단가. numeric |
| usage_rate | 사용량 단가. numeric |
| effective_from, effective_to | `varchar(7)` `'YYYY-MM'`. to는 nullable |
| currency | 통화 코드 |

**시간대별 차등 단가를 두지 않는다.** 단일요금제 전제이므로 요금 계산에 시간대 가중치를 적용하지 않는다. 시간대 요금제가 필요해지면 `fems.tariff_period` 자식 테이블을 추가하는 확장 지점만 남긴다. 지금 만들지 않는다.

가스·용수도 같은 구조를 쓴다. 기본요금 + 사용량 단가 형태는 에너지원을 가리지 않는다.

### fems.energy_target — 기간별 목표

| 속성 | 내용 |
|---|---|
| S, target_scope, site_id, equipment_id, energy_source_id, target_month | (S, scope, site, equipment, source, month) UNIQUE |
| target_scope | `SITE` / `EQUIPMENT` |
| site_id / equipment_id | scope에 따라 하나만 NOT NULL |
| energy_source_id | NULL이면 **환산 기준 전체 에너지 목표** |
| target_value, unit | 목표값과 단위 |
| target_month | `varchar(7)` `'YYYY-MM'` |

### fems.energy_baseline — 원단위 기준선

| 속성 | 내용 |
|---|---|
| S, baseline_scope, item_id, equipment_id, energy_source_id, baseline_code | (S, code) UNIQUE |
| baseline_scope | `ITEM`(품목 원단위) / `EQUIPMENT`(설비 원단위) |
| baseline_value, unit | 생산 단위당 에너지. kWh/EA 등 |
| period_from, period_to | 산정 기간. `varchar(7)` |
| status | `draft` / `confirmed`. 확정 후 변경 금지 |

---

## 4. 기존 테이블 변경

| 테이블 | 변경 |
|---|---|
| `core.meter` | `measurement_kind`, `unit` **제거** → `core.meter_channel`로 이동. 계측기는 물리 장치, 채널은 측정 항목 |
| `fems.energy_reading` | `meter_id` → **`meter_channel_id`** 참조로 변경. UNIQUE는 (S, channel, source_key) |
| `bems.energy_reading` | 동일하게 채널 참조로 변경 |
| `fems.energy_allocation` | `meter_id` → `meter_channel_id`. UNIQUE에 channel 반영 |

**이것은 되돌리기 비싼 변경이다.** 물리 DDL 전인 지금이 마지막으로 싸게 바꿀 시점이다. FS-009에서 마이그레이션을 만든 뒤에는 데이터 이관이 따라붙는다.

---

## 5. 정합성 계약

- 채널의 `owner_module`은 소속 계측기의 `owner_module`과 같아야 한다. 같은 계측기의 채널이 두 모듈로 갈리지 않는다.
- 관측값이 있는 채널의 에너지원·측정 종류·소유 모듈 변경을 금지한다. 변경이 필요하면 새 채널을 만든다.
- 기간 합계는 `measurement_kind = 'CUMULATIVE'` 채널만 대상으로 한다.
- 서로 다른 에너지원의 값을 원단위 그대로 합산하지 않는다. `factor_kind = 'PRIMARY'` 계수로 환산한 뒤 합산한다.
- 적용 연도의 계수가 없으면 계산을 **추정으로 대체하지 않고 계산 불가로 표시**한다.
- 부모 계량기와 하위 채널을 함께 더하지 않는다. 기존 중복 합산 방지 규칙을 채널 단위로 확장한다.
- 원단위 = 환산 에너지 ÷ 생산량. 생산량이 0이면 계산 불가로 표시한다.
- 탄소 배출량은 에너지원별로 `소비량 × 배출계수`를 계산한 뒤 합산한다.

---

## 6. 시드 영향

FS-005b의 계측 행 수 산정이 바뀐다. **에너지원별로 현실적인 검침 주기를 다르게 잡는다.**

| 에너지원 | 계측 채널 | 주기 | 30일 행 수 |
|---|---|---|---|
| 전력 | 설비 8 + 사업장 전체 1 | 1시간 | 6,480 |
| 가스 | 사업장 1 | **1일** | 30 |
| 용수 | 사업장 1 | **1일** | 30 |
| **합계** | **11 채널** | | **6,540** |

가스·용수를 전력과 같은 1시간 주기로 두면 근거 없이 행 수만 늘어난다. 실제 현장도 가스·용수는 일 단위 검침이 일반적이다. **결과적으로 총 규모는 6,840행에서 6,540행으로 오히려 줄어든다.** 게스트 진입 예산에 영향이 없다.

에너지원 3종을 넣으면 "전력만 보는 게 FEMS가 아니다"라는 점과 환산 합산 문제를 시드 데이터만으로 보여줄 수 있다. 다중 에너지원 구조를 도입하는 실질적 이유다.

순시(`INSTANT`) 채널은 시드에 넣지 않는다. 구조는 지원하되 데이터는 누적 채널만 채우고, 순시 채널이 합계에서 제외된다는 규칙은 설명으로 다룬다.

---

## 7. 반영 결과

### 7.1 신규 엔티티 목록

검증기가 읽는 기준 목록이다. 표기를 바꾸면 정적 검증이 깨진다.

| 엔티티 | 소유 | 역할 |
|---|---|---|
| `core.energy_source` | core | 에너지원 기준정보 |
| `core.meter_channel` | core | 계측 채널 |
| `fems.energy_factor` | fems | 환산·배출 계수 |
| `fems.tariff` | fems | 요금제 기준정보 |
| `fems.energy_target` | fems | 기간별 목표 |
| `fems.energy_baseline` | fems | 원단위 기준선 |

### 7.2 규모 변화

| 구분 | 수 |
|---|---|
| FS-007a 기준 | 54 |
| core 신규 (`energy_source`, `meter_channel`) | 2 |
| fems 신규 (`energy_factor`, `tariff`, `energy_target`, `energy_baseline`) | 4 |
| **합계** | **60** |

컬럼·참조가 바뀌는 테이블: `core.meter`, `fems.energy_reading`, `fems.energy_allocation`, `bems.energy_reading`.

---

## 8. 참조 명세에서 가져오지 않은 것

실제 운영 FEMS 명세서를 참조했으나 아래는 의도적으로 제외했다. 제외 사유를 남겨 두어야 나중에 "왜 없냐"는 질문에 답할 수 있다.

| 제외 대상 | 사유 |
|---|---|
| 전력회사 API 연동 (고객정보·청구정보·호출이력) | 특정 국가 특정 사업자에 종속. 일반화 불가 |
| KPI 증빙 스냅샷 (피크 감소율·시스템 활용도·유효데이터 확보율) | 특정 과제의 성과 증빙용이지 FEMS 일반 기능이 아니다 |
| MES 연동 설정·일별 생산실적·작업지시 복제 | 실제 FEMS는 MES가 외부 시스템이라 복제가 필요했다. 여기는 단일 DB라 `mes.operation_result`를 직접 조인한다. 복제하면 생산실적이 두 벌이 된다 |
| 도면 파싱·3D 에셋·설비 좌표 | 시각화 범위. 기준정보·조회 범위 밖 |
| 외부 연동 API 클라이언트·감사 로그 | 대외 개방 기능. 범위 밖 |
| 리포트 발행 스냅샷 | 후속 |
| AI 채팅 세션·대화 이력 | 범위 밖 |
| 시스템 코드·메뉴·회사·토큰 관리 | FS-005에서 코드 명시 목록 정책으로 대체 결정 |
| 피크 임계치·초과 집계 | **단일요금제 전제**라 피크 절감 동기가 성립하지 않는다. 요금 로직과 앞뒤가 맞지 않아 제외 |
| 기간 집계 테이블 (15분·일·월 롤업) | 시드가 6,540행이라 조회 시 합산으로 충분하다. 실제 운영은 15분 × 수년치라 필요했던 것이다. FEMS 노드 설명 카드에 "언제 집계 테이블이 필요해지는가"로 다룬다 |

참조 명세의 테이블명·컬럼 구성은 사용하지 않았다. 업로드 파일도 저장소에 포함하지 않는다.

---

## 9. 미확정 / 후속

- 컬럼별 타입·NULL·기본값·CHECK 확정은 메타데이터 반영 작업에서 한다.
- 시간대별 요금제는 `fems.tariff_period` 확장 지점만 남기고 구현하지 않는다.
- 집계 테이블은 실제 데이터량이 커질 때 재판단한다.
- BEMS 채널 구조는 정의만 해두고 데이터는 채우지 않는다. BEMS는 준비 중이다.
- FEMS 학습 과정(C4)의 단계·검증 조건에 다중 에너지원 환산을 반영해야 한다. FS-004 개정 범위다.
