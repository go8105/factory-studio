# FS-028 SPC 모듈 설계서

작성일: 2026-09-30 (Claude Code)
상태: **확정 — 사용자 승인 2026-09-30**(전체 설계 확인 완료, 13장 5건 모두 권장안). FS-028a DB 반영 완료(14장).
전제: [FS-028 결정서](../../plan/SPC도입_관리도_결정_FS-028.md)(D37~D44, 2026-09-30 승인), [FS-023 D9 교차 조회](../../plan/QMS도입_교차조회_결정_FS-023.md), [FS-013](../../plan/독립솔루션_전환결정_FS-013.md), [새 솔루션 킷](../../plan/새솔루션_킷.md)
화면: [SPC 화면 설계](../../ui/화면설계_SPC_FS-028.md)

---

## 1. 이 모듈은 무엇인가

**공정 중 측정값을 부분군으로 모아 X̄-R 관리도로 공정의 흔들림을 감시하고, 이상 신호를 조치까지 기록하며, 규격 대비 공정능력(Cp·Cpk)을 보여 주는 통계적 공정관리 솔루션이다.**

```
MES 공정 실행(LOT·공정·설비·기간) ──조회──▶ 측정 입력: 6시간마다 n=5 ─▶ 부분군(X̄, R)
                                                            │
관리 한계(버전, 처음 20 부분군으로 게시) ────────────────────▶ 이상 판정(규칙 1·2·3) ─▶ 이상 기록: 발생 → 조치 완료
                                                                                    └──조회──▶ QMS "SPC 이상" 배지
규격(LSL·USL) + 유효 부분군 ─▶ 공정능력 Cp·Cpk (조회할 때 계산)
```

평가자 3분 동선:

```
대시보드(특성 6개 · 미조치 이상 2 · Cpk 부족 1)
  → 관리도: FG-C200 사출 하우징 높이 — LT-0017에서 연속 상승(규칙 3) 뒤 UCL 초과(규칙 1)
  → QMS 검사 대기: 같은 LOT에 "SPC 이상" 배지 — 최종검사는 규격 안이라 합격할 LOT
  → 이상·조치: 원인 "설비(금형 온도)" · 조치 입력 → 조치 완료
  → 측정 입력: 진행 중 공정 실행을 골라 5개 값 입력 → 새 점이 관리도에 찍힌다
```

## 2. 하위 모듈

| 하위 모듈 | 소유 테이블 | 교차 조회 |
|---|---|---|
| `spc_master` 관리 특성 | 관리 특성, 관리 한계 | MES 품목(특성 등록 때 품목 선택) |
| `measure` 측정 | 부분군, 측정값 | MES 공정 실행(입력 때 선택·검사) |
| `signal` 이상 | 이상 기록 | — (QMS가 SPC를 조회) |

소유 **5테이블**. 스키마 간 FK 0건. 품목·LOT·공정·설비는 MES 코드 스냅샷이다(D38).

## 3. 업무 규칙

| 규칙 | 내용 |
|---|---|
| 관리 특성 | 품목 코드 · 공정 코드 · 특성명 · 단위 · LSL/USL(하나 이상, 둘 다면 LSL < USL) · 목표값(선택). 부분군 크기는 **5 고정**(D39, 13장 1). 품목·공정·특성명 조합은 하나 |
| 부분군 기록 | MES 공정 실행 1건(LOT×공정)을 고르고 측정 시각과 값 5개를 넣는다. 측정 시각은 그 실행의 시작~종료(진행 중이면 현재) 안이어야 하고, 실행의 품목·공정이 특성과 같아야 한다. X̄와 R은 기록할 때 계산해 함께 저장한다(불변) |
| 순서 | **측정 시각은 그 특성의 마지막 유효 부분군보다 늦어야 한다**(13장 2). 과거 시각 끼워 넣기를 막아 이상 판정을 다시 계산할 일이 없게 한다 |
| 간격 | 6시간은 시드 생성 규칙이다. 화면 입력은 간격을 강제하지 않는다(같은 실행·같은 시각 중복만 거부) |
| 관리 한계 | 기준 구간의 유효 부분군 **20개 이상**으로 산정: X̿ = 평균 X̄, R̄ = 평균 R, X̄ 관리도 CL = X̿·UCL/LCL = X̿ ± A2·R̄, R 관리도 CL = R̄·UCL = D4·R̄·LCL = D3·R̄ (n=5: A2 0.577, D3 0, D4 2.114). 게시하면 불변. 새 버전의 **적용 시작 = 게시 때 그 특성의 마지막 유효 부분군 측정 시각**(14장 — 벽시계와 무관). 직전 버전 뒤 새 부분군이 없으면 거부(409 `NO_NEW_SUBGROUP`). 게시 시각은 `created_at` |
| 판정 버전 | 부분군은 **측정 시각에 유효한 버전**(적용 시작 < 측정 시각인 최신 버전)으로 판정한다. 게시 전 부분군은 판정하지 않는다("한계 미게시") |
| 이상 규칙(D41) | 규칙 1: X̄ 또는 R이 한계 밖. 규칙 2: X̄가 CL 한쪽에 연속 9점. 규칙 3: X̄가 연속 6점 증가 또는 감소(같은 값은 끊김). **연속 판정은 같은 한계 버전 안의 유효 부분군만** 센다(13장 3). 한 부분군에서 여러 규칙이 동시에 참이면 규칙마다 1건 |
| 이상 조치(D42) | `open` → `resolved`. 조치 완료에는 원인 분류(`MACHINE` 설비 · `MATERIAL` 자재 · `MAN` 작업자 · `METHOD` 방법 · `MEASUREMENT` 측정 · `ENVIRONMENT` 환경)와 조치 내용(2~500자) 필수. 조치 완료 후 불변 |
| 부분군 무효(D42) | `valid` → `void`(사유 필수). 그 부분군에서 나온 이상 기록은 `void`가 된다(조치 완료된 것도). **뒤 부분군의 연속 판정 결과는 다시 계산하지 않는다**(불변 — 화면에 안내). 무효 부분군은 관리도에 흐린 점으로 보이고 계산에서 빠진다 |
| 공정능력(D43) | 선택 기간의 유효 부분군으로 μ = X̿, σ̂ = R̄/d2(2.326). Cp는 양쪽 규격일 때만. **유효 부분군 20개 미만이면 계산하지 않는다**("표본 부족"). 기간 안에 미조치 이상이 있으면 "관리 상태가 아니므로 해석에 주의" 안내 |
| 독립 동작 | MES 꺼짐이면 측정 입력(공정 실행 목록·기록)만 409. 관리도·공정능력·이상 조치는 저장된 스냅샷으로 동작 |

## 4. DB 차분 — `spc` 스키마 5테이블

공통 컬럼·제약은 QMS·WMS·BEMS와 같다(`id`·`workspace_id`·`generation_id`·`created_at`, PK·UK(S, id)·범위 앵커 FK, 업무 FK `(S, 참조 id)` RESTRICT, FK 열 INDEX).

| 엔티티 | 하위 모듈 | 역할 |
|---|---|---|
| `spc.characteristic` | spc_master | 관리 특성(품목·공정·특성·규격) |
| `spc.control_limit` | spc_master | 관리 한계 버전(불변) |
| `spc.subgroup` | measure | 부분군(MES 스냅샷·X̄·R·상태) |
| `spc.measurement` | measure | 부분군의 측정값 5개(불변) |
| `spc.signal` | signal | 이상 기록(발생·조치·무효) |

### 4.1 관리 특성·한계

| 테이블 | 컬럼(요약) | 규칙 |
|---|---|---|
| characteristic | code, item_code, item_name(스냅샷), process_code, name, unit, lsl numeric(12,4) null, usl numeric(12,4) null, target numeric(12,4) null, subgroup_size smallint(=5 CHECK), decimals smallint(0~4), is_active | UK(S, code), UK(S, item_code, process_code, name). CHECK lsl·usl 중 하나 이상, 둘 다면 lsl < usl. 규격·품목·공정은 부분군이 생긴 뒤 바꾸지 않는다(SERVICE, 409) |
| control_limit | characteristic_id FK, version int ≥ 1, effective_at timestamptz, basis_from·basis_to timestamptz, basis_count int ≥ 20, xbar_cl·xbar_ucl·xbar_lcl numeric(14,6), r_cl·r_ucl·r_lcl numeric(14,6), reason varchar(200) | UK(S, characteristic_id, version), UK(S, characteristic_id, effective_at). CHECK lcl < cl < ucl(두 관리도), basis_from ≤ basis_to. 불변 |

### 4.2 측정

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| subgroup | characteristic_id FK, lot_no, item_code, process_code, equipment_code(MES 스냅샷), run_started_at·run_ended_at null(스냅샷), measured_at timestamptz, xbar·r numeric(14,6), status(`valid`/`void`), void_reason null, voided_at null, source(`SEED`/`MANUAL`), note null | UK(S, characteristic_id, lot_no, measured_at). CHECK r ≥ 0, 상태·무효 칸 일치. INDEX (S, characteristic_id, measured_at). 값 불변(상태만 전이) |
| measurement | subgroup_id FK, seq 1~5, value numeric(12,4) | UK(S, subgroup_id, seq). 불변 |

### 4.3 이상

| 테이블 | 컬럼 | 규칙 |
|---|---|---|
| signal | subgroup_id FK, characteristic_id FK, control_limit_id FK, lot_no(스냅샷 — QMS 조회용), chart(`XBAR`/`R`), rule smallint(1~3), value numeric(14,6), detected_at, status(`open`/`resolved`/`void`), cause_category null, action varchar(500) null, resolved_at null, voided_at null | UK(S, subgroup_id, chart, rule). CHECK 규칙 2·3은 chart=`XBAR`, 상태별 칸 일치(resolved ⇔ 원인·조치·시각). INDEX (S, status, lot_no) — QMS 배지 조회 |

### 4.4 core·규모

- `core.workspace_module` CHECK에 `'spc'`(새 revision), 모듈 행 데이터 마이그레이션(DB 단계에서 함께 — 킷 a).
- 업무 스키마 spc 5. 현재 main 93 → **98테이블**(FS-026a가 먼저 병합되면 103). 상태 목록 subgroup·signal 2개.
- 스키마 버전은 FS-026a(v0.13.0) 병합 뒤 v0.14.0으로 정한다(병합 전 착수하면 v0.13.0을 쓰고 Codex와 조율).

## 5. 계산 (서비스 한 곳 — `fs/spc/stats.py`)

| 값 | 식 |
|---|---|
| X̄, R | 부분군 5값의 평균, 최대−최소. 저장은 numeric(14,6), 화면은 특성 `decimals`+1자리 |
| 관리 한계 | 3장 식. 상수표 `{5: A2 0.577, D3 0, D4 2.114, d2 2.326}` — n을 늘릴 때 표만 늘린다 |
| 규칙 1~3 | 부분군 기록 때 같은 버전의 이전 유효 부분군을 측정 시각 순으로 읽어 판정 |
| Cp·Cpk | 3장 식. 판정: ≥ 1.33 충분 · 1.00~1.33 주의 · < 1.00 부족 |
| 반올림 | 저장 전 `ROUND_HALF_UP`(시드 `round_half_up`와 같은 함수) |

Python `decimal`로 계산한다(부동소수 오차로 한계 경계값 판정이 흔들리지 않게).

## 6. 트랜잭션·잠금

| TX | 내용 | 잠금 |
|---|---|---|
| TX-S1 부분군 기록 | MES 공정 실행 조회·검사 → 순서 검사 → subgroup·measurement INSERT → 규칙 판정 → signal INSERT | 공간 → 특성(FOR UPDATE — 같은 특성 기록 직렬화) |
| TX-S2 한계 게시 | 기준 구간 유효 부분군 ≥ 20 검사 → 계산 → control_limit INSERT(version+1) | 공간 → 특성 |
| TX-S3 이상 조치 | open → resolved | 공간 → 이상 기록 |
| TX-S4 부분군 무효 | valid → void, 그 부분군의 이상 기록 → void | 공간 → 특성 → 부분군 |

멱등: 변경 POST는 `Idempotency-Key`. 부분군 기록은 요청 멱등 + UK(특성, LOT, 측정 시각) 두 겹.

## 7. 교차 조회 인터페이스

| 제공 | 함수 | 반환 |
|---|---|---|
| MES `fs/mes/interface.py` **(추가)** | `operation_runs(connection, scoped, date_from, date_to)` | `[{lotNo, itemCode, processCode, equipmentCode, startedAt, endedAt}]` — 시작된 공정 실행(진행 중은 `endedAt=None`), 시작 시각순. MES 꺼짐 `None` |
| MES (기존) | `items(connection, scoped)` | 특성 등록 때 완제품 선택 |
| SPC `fs/spc/interface.py` **(신규)** | `enabled(connection, scoped)` · `open_signal_lot_nos(connection, scoped, lot_nos)` | 미조치(`open`) 이상이 있는 LOT 번호 집합. SPC 꺼짐 `None` |

QMS는 Q-03·Q-04 목록 응답에 `spcSignal: true/false/null`을 붙인다(null = SPC 꺼짐, D44). 판정·보류 로직은 바꾸지 않는다.

## 8. API 계약 (`/api/v1/spc`)

| 메서드·경로 | 내용 |
|---|---|
| `GET /dashboard` | KPI(특성 수·미조치 이상·Cpk 판정별 수·최근 7일 부분군), 특성별 최근 20점 X̄·Cpk·미조치 수 |
| `GET/POST/PATCH /characteristics` | 관리 특성(부분군이 있으면 규격·품목·공정 변경 409 `CHARACTERISTIC_IN_USE`, 사용 안 함은 가능) |
| `GET /characteristics/{id}/chart?from=&to=` | 부분군 점(X̄·R·상태·LOT·설비), 구간별 한계 버전, 이상 표시 |
| `GET /characteristics/{id}/capability?from=&to=` | μ·σ̂·Cp·Cpk·판정·히스토그램 구간(10칸)·부분군 수. 20 미만 `insufficient: true` |
| `GET /characteristics/{id}/limits` · `GET …/limits/preview?basisFrom=&basisTo=` · `POST …/limits` | 한계 버전 목록 · 게시 전 미리 계산 · TX-S2 `{basisFrom, basisTo, reason}`(20 미만 400) |
| `GET /runs?characteristicId=` | MES 공정 실행(해당 품목·공정, 최근 30일) + 실행별 기록된 부분군 수. MES 꺼짐 409 `SOURCE_MODULE_DISABLED` |
| `POST /subgroups` | TX-S1 `{characteristicId, lotNo, measuredAt, values[5], note?}` → 부분군 + 생긴 이상 기록. 시각 창 밖·순서 위반 400(`fields.measuredAt`) |
| `GET /subgroups?characteristicId=&lotNo=&status=` · `POST /subgroups/{id}/void` | 목록 · TX-S4 `{reason}` |
| `GET /signals?status=&characteristicId=` · `POST /signals/{id}/resolve` | 목록 · TX-S3 `{causeCategory, action}` |

## 9. 화면 (요약 — 상세는 [화면 설계서](../../ui/화면설계_SPC_FS-028.md))

| ID | 화면 | 패턴 |
|---|---|---|
| S-01 | 대시보드 | D — KPI 4·특성 카드(작은 X̄ 추이·Cpk 배지) |
| S-02 | 관리도 | D — X̄·R 관리도 두 장 + 값 표 **(SPC 시연)** |
| S-03 | 공정능력 | D — Cp·Cpk·히스토그램(LSL·USL 선) |
| S-04 | 측정 입력 | V + FormPanel — MES 공정 실행 선택 → 5값 입력 **(MES 교차 조회 시연)** |
| S-05 | 이상·조치 | L + DetailPanel — 규칙 설명·주변 점·조치 입력 |
| S-06 | 부분군 기록 | L — 검색·무효 처리 |
| S-07 | 관리 특성·한계 | P — 특성 → 한계 버전 → 게시(미리 계산) |

## 10. 합성 데이터 (약 2,350행)

| 대상 | 행 | 내용 |
|---|---:|---|
| characteristic | 6 | 품목 3 × {사출(INJ) 치수, 조립(ASM) 치수·토크}. 규격은 QMS 검사 기준과 같은 수치(복사가 아니라 SPC 자체 값 — D38): FG-C100 사출 하우징 높이 8.90~9.10 · 조립 핀 피치 2.49~2.59 mm, FG-C200 사출 하우징 높이 11.90~12.10 · 조립 핀 피치 2.49~2.59 mm, FG-T300 사출 단자 간격 4.95~5.05 mm · 조립 조임 토크 0.40~0.60 N·m |
| subgroup | 약 390 | 완료·진행 중 공정 실행마다 시작 1시간 뒤부터 6시간 간격(사출 약 62시간 → 약 10개, 조립 약 38시간 → 약 6개) |
| measurement | 약 1,950 | 부분군 × 5. 결정적 의사난수(시드 고정) + 특성별 평균·표준편차 |
| control_limit | 7 | 특성마다 v1(처음 20 부분군) + FG-C100 조립 핀 피치 v2(조치 후 재게시) |
| signal | 약 4 | FG-C100 조립 과거 규칙 1 **조치 완료**(설비 — 지그 마모, 지그 교체) · **FG-C200 사출 LT-0017(INJ-02)에서 규칙 3 → 규칙 1, 미조치 2건**(QMS 검사 대기 LOT — 배지 시연). 뒤 LOT(LT-0023·LT-0020)는 정상 범위(조정은 했지만 조치 기록이 빠진 이야기) |

- 공정능력 결과: 충분 4 · 주의 1(FG-C200 사출 — 이동 때문에) · 부족 1(FG-T300 조임 토크 — 분산이 큼).
- **의도하지 않은 이상이 생기지 않게** 생성 후 규칙 1~3을 다시 돌려 이상 기록이 위 목록과 정확히 같은지 `seed/validate.py`에서 검사한다(V 규칙 추가).
- 복사: 시각 컬럼은 기존 규칙으로 일수 이동. 달력 문자열 컬럼 없음. LOT 번호는 MES 복사와 같은 값을 쓴다.
- 템플릿 11,910 → 약 **14,260행**. 게스트 복사 시간(현재 중앙값 0.509초)을 FS-028c에서 재고, 1초를 넘으면 간격을 8시간으로 늘린다.

## 11. 수용 기준 (AC-170~184)

| AC | 기준 |
|---|---|
| 170 | 게시한 한계는 3장 식과 소수 6자리까지 같다(n=5 상수) |
| 171 | 유효 부분군 20개 미만으로는 한계를 게시할 수 없다(400) |
| 172 | 부분군은 측정 시각에 유효한 한계 버전으로 판정된다. 게시 전 부분군은 판정하지 않는다 |
| 173 | 한계 밖 1점은 규칙 1, 한쪽 연속 9점은 규칙 2, 연속 6점 증가·감소는 규칙 3 이상 기록을 1건씩 만든다 |
| 174 | 연속 판정은 한계 버전이 바뀌면 처음부터 센다 |
| 175 | 측정 시각이 공정 실행 기간 밖이거나 특성의 마지막 부분군보다 이르면 400이다 |
| 176 | 같은 요청을 다시 보내도 부분군이 한 번만 생긴다(멱등·UK) |
| 177 | 조치 완료에는 원인 분류와 조치 내용이 필요하고, 조치 완료 뒤에는 바꿀 수 없다 |
| 178 | 부분군을 무효 처리하면 그 부분군의 이상 기록이 무효가 되고 관리도·공정능력 계산에서 빠진다 |
| 179 | 부분군이 있는 특성의 규격·품목·공정은 바꿀 수 없다(409) |
| 180 | 유효 부분군 20개 미만이면 공정능력을 계산하지 않고 "표본 부족"을 돌려준다 |
| 181 | MES를 끄면 측정 입력만 409 `SOURCE_MODULE_DISABLED`, 나머지 SPC 기능은 동작한다 |
| 182 | SPC를 끄면 QMS 배지 값은 null이고 QMS 판정·보류는 그대로다. 미조치 이상 LOT에만 배지가 true다 |
| 183 | 다른 공간·세대의 특성·부분군·이상은 보이지 않는다(X3) |
| 184 | SPC는 MES 테이블을 직접 조회하지 않는다(R6: `fs.mes.interface`만 import). QMS는 `fs.spc.interface`만 import |

## 12. 하지 않는 것 / 후속

결정서 5장 전부. 추가로: 부분군 크기 5 외, 측정값 수정(무효 후 다시 입력), 한계 게시 취소, 특성별 측정 간격 강제, 이상 담당자 배정·기한.

## 13. 결정이 필요한 것 (전체 설계 확인 때 함께)

1. **부분군 크기 5 고정**(CHECK). 권장: 고정 — 상수표만 늘리면 되도록 코드는 표로 둔다.
2. **측정 시각 순서 강제**(마지막 부분군보다 늦게만). 권장: 강제 — 과거 끼워 넣기를 허용하면 뒤 부분군 판정을 다시 계산해야 하고, 불변 원칙과 부딪힌다.
3. **연속 규칙은 한계 버전마다 새로 센다.** 권장: 그대로 — 조치 뒤 재게시한 한계에 옛 추세가 이어지지 않게.
4. **무효 처리 때 뒤 부분군의 판정을 다시 계산하지 않는다.** 권장: 그대로 — 화면에 "무효 처리 전 판정 결과는 그대로 남는다" 안내.
5. **공정능력 최소 20 부분군.** 권장: 그대로(한계 게시 기준과 같음).

## 14. 구현 기록 (FS-028a DB, 2026-09-30)

- `tools/apply_fs028a.py`(멱등) → `schema.json` **v0.13.0 / FS-028a**: 98테이블(spc 5) · 1,030컬럼 · FK 220 · 제약·정책 776. 모듈 키 CHECK(C22)에 `'spc'`.
- 설계서와 다른 점 2건.
  1. 한계 적용 시작 컬럼은 **`effective_at`**(설계 초안 `effective_from`). `effective_from`은 검증기가 달력 문자열 키로 보는 이름이라 timestamptz를 쓸 수 없다. 4.1 표를 고쳤다.
  2. **적용 시작 값은 게시 시각이 아니라 게시 때 마지막 유효 부분군의 측정 시각**이다(FS-028b 구현 중 발견). 게시 시각(DB 시계)과 측정 시각(화면 입력)은 서로 다른 시계라 몇 초만 어긋나도 게시 직후 기록이 새 한계 밖으로 빠졌고, 게스트 공간은 업무 날짜를 옮기므로 벽시계와 업무 시각이 다르다. 측정 순서를 이미 강제하므로 "게시 뒤 기록 = 적용 시작 뒤 측정"이 시계와 무관하게 성립한다. DB 구조는 같고 SERVICE 정책 문장만 바뀌었다(마이그레이션 SHA 주석 갱신).
- 마이그레이션 `fs028a_spc`(down `fs025b_bems_module`, C·R 번호 고정 텍스트) + `fs028b_spc_module`(기존 공간 모듈 행).
- 검증기: `validate_spc` 추가, 작업 ID 집합에 FS-028a(이전 `validate_bems`가 FS-025a 전용이어서 꺼질 뻔했다 → `LATER_THAN_025A`). 격리 검사 BUSINESS에 spc. Excel 35시트·ERD `spc.mmd` 재생성.
- 시드: 모듈 행 +1(템플릿 11,911 · 게스트 복사 11,909). SPC 업무 시드는 FS-028c.
- **Codex 조율 필요**: FS-026a(`codex/vision-ai`)도 v0.13.0이다. main 병합 전 rebase 때 FS-026a를 **v0.14.0**으로, 그 마이그레이션 `down_revision`을 **`fs028b_spc_module`**로, 모듈 키 목록에 `'spc'`를 유지하도록 옮긴다.
