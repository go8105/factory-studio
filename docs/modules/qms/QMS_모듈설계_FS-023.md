# FS-023 QMS 모듈 설계서

작성일: 2026-09-27 (Claude Code)
상태: **확정 — 사용자 승인 2026-09-27.** 4장 테이블은 FS-023a에서 `schema.json` v0.10.0·마이그레이션 `fs023a_qms`로 반영. 13장 결정 3건은 권장안(서버 발번 · 서버가 정한 최근 월 · 패킹 여부와 무관하게 보류 생성)으로 확정.
전제: [FS-023 결정서](../../plan/QMS도입_교차조회_결정_FS-023.md)(D8~D12, 조회 인터페이스 X1~X6), [FS-013](../../plan/독립솔루션_전환결정_FS-013.md)
화면: [QMS 화면 설계 FS-023](../../ui/화면설계_QMS_FS-023.md)

---

## 1. 이 모듈은 무엇인가

**MES가 확정한 완제품 LOT이 출하해도 되는 품질인지 판정하고, 문제가 있는 LOT을 보류·처분하는 품질 관리 솔루션이다.**

```
MES 실적 확정(최종 공정 양품) ──조회──▶ QMS 검사 대기
                                        │  검사 기준(품목별·게시 버전)으로 측정값 입력
                                        ▼
                                   검사 확정 ── 합격 ──▶ (MES 패킹은 원래대로 진행)
                                        │
                                        └ 불합격 ──▶ 품질 보류 ──▶ 재검사 합격 / 특채 / 폐기 판정으로 해제
                                                        │
                                   MES 패킹 목록에 "QMS 보류" 배지(표시만, D10)
```

MES를 꺼도 QMS만으로 "기준을 정하고, LOT 코드를 입력해 검사하고, 불합격을 보류·처분한다"가 성립해야 한다(D12).

평가자 3분 동선:

```
대시보드(합격률·보류 LOT)
  → 검사 대기(MES에서 막 끝난 LOT이 보인다 — 교차 조회)
  → 검사 입력(기준 상·하한 대비 자동 판정)
  → 불합격 → 보류 → 재검사 / 특채 / 폐기
  → MES 패킹 화면에서 같은 LOT에 "QMS 보류" 배지
```

## 2. 하위 모듈

| 하위 모듈 | 소유 테이블 | 교차 조회 |
|---|---|---|
| `qms_master` 기준정보 | 불량 유형 | — |
| `spec` 검사 기준 | 검사 기준 버전, 검사 항목 | MES 품목(선택) |
| `inspection` 검사 | 검사, 검사 측정값 | MES 완료 LOT(선택) |
| `hold` 품질 보류 | 품질 보류 | — |

소유 **6테이블**. 스키마 간 FK 0건. MES 품목·LOT은 **값 스냅샷**으로만 들어온다(D11).

## 3. 업무 규칙

| 규칙 | 내용 |
|---|---|
| 검사 대상 | **LOT 단위 출하 전 최종검사.** MES LOT 중 상태 `completed`이고 최종 공정 양품 > 0인 LOT. 전량 불량 종결 LOT은 제외 |
| 검사 기준 버전 | 품목 코드별 버전. **게시한 버전은 불변.** 바꾸려면 개정(새 초안). 품목당 게시 버전은 1개 — 새 버전을 게시하면 이전 게시 버전은 `retired` |
| 기준 고정 | 검사를 만들 때 그 시점의 게시 기준 버전을 고정한다. 이후 기준이 개정돼도 진행 중·확정 검사는 영향받지 않는다(MES 경로 버전 고정과 같은 규칙) |
| 판정 방식 | 항목마다 `RANGE`(하한 ≤ 측정값 ≤ 상한, 한쪽만 있어도 된다) 또는 `PASS_FAIL`(작업자 합·부 선택) |
| 항목 판정 | 서버가 계산한다. 클라이언트 판정을 믿지 않는다 |
| 검사 판정 | 필수 항목이 모두 입력되어야 확정할 수 있다. **한 항목이라도 불합격이면 검사 불합격** |
| 불량 유형 | 불합격 항목에는 불량 유형을 1개 고른다(대시보드 사유 집계용) |
| 확정 불변 | 확정한 검사·측정값은 수정·삭제하지 않는다. 잘못 확정했으면 **재검사**(새 검사, `reinspection_of_id`)로 바로잡는다 |
| 보류 생성 | 불합격 확정과 **같은 트랜잭션**에서 그 LOT의 보류를 만든다(TX-Q2). LOT당 활성 보류는 1건 |
| 보류 해제 | 세 가지 처분 중 하나로만 해제한다 — `REINSPECTED`(해제 전 마지막 재검사가 합격이어야 함), `CONCESSION`(특채: 사유 필수), `SCRAP`(폐기 판정: 사유 필수). 해제 후 다시 보류하려면 새 검사가 불합격이어야 한다 |
| 수량 | QMS는 LOT 수량을 **바꾸지 않는다.** 폐기 판정도 기록일 뿐 MES 양품·재고를 차감하지 않는다(D10·WMS 경계) |
| 표본 | `sample_qty ≤ lot_qty`. 1차는 표본 크기 규칙(AQL)을 계산하지 않고 작업자가 입력한다 |

## 4. DB 차분 — `qms` 스키마 6테이블

공통 컬럼(모든 테이블): `id bigint GENERATED ALWAYS AS IDENTITY` · `workspace_id bigint NN` · `generation_id bigint NN` · `created_at timestamptz NN default now()`.
공통 제약: PK(id) · UK(workspace_id, generation_id, id) · 범위 앵커 FK `(workspace_id, generation_id) → core.data_generation(workspace_id, id)` · 업무 FK는 `(workspace_id, generation_id, 참조 id) → (workspace_id, generation_id, id)` 복합 참조, 삭제·변경 RESTRICT · scope `generation` · retention `세대 정리`. FK 열마다 조회 INDEX. 아래 표의 `S`는 `(workspace_id, generation_id)`.

엔티티 목록(검증기 `validate_db_design.py`가 읽는 기준 목록):

| 엔티티 | 하위 모듈 | 역할 |
|---|---|---|
| `qms.defect_type` | qms_master | 불량 유형 |
| `qms.inspection_spec` | spec | 품목별 검사 기준 버전. 게시 후 불변 |
| `qms.inspection_spec_item` | spec | 검사 항목(RANGE / PASS_FAIL) |
| `qms.inspection` | inspection | LOT 출하 전 최종검사 |
| `qms.inspection_value` | inspection | 항목별 측정값·판정 |
| `qms.quality_hold` | hold | 품질 보류와 처분 |

### 4.1 `qms.defect_type` 불량 유형 (`qms_master`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| code | varchar(30) | ○ | 대문자로 시작, `[A-Z][A-Z0-9_]{1,29}`. UK(S, code) |
| name | varchar(100) | ○ | |
| is_active | boolean | ○ | default true. 쓰인 유형은 삭제 대신 사용 안 함 |

시드 코드는 MES 불량 사유 코드와 같게 심는다(`MOLD_DAMAGE`·`SHORT_SHOT`·`PIN_MISALIGN`·`CONTACT_FAIL` + `APPEARANCE`·`DIMENSION`). **코드가 같을 뿐 FK는 없다.**

### 4.2 `qms.inspection_spec` 검사 기준 버전 (`spec`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| item_code | varchar(40) | ○ | 품목 코드 스냅샷(MES 조회 또는 직접 입력) |
| item_name | varchar(100) | ○ | 스냅샷 |
| version_no | integer | ○ | ≥ 1. UK(S, item_code, version_no) |
| status | varchar(20) | ○ | `draft` / `published` / `retired`, default `draft` |
| published_at | timestamptz | | `status <> 'draft'`이면 NN (CHECK) |
| note | varchar(300) | | |

- **UK_PARTIAL**: (S, item_code) WHERE status = 'published' — 품목당 게시 1건.
- SERVICE: 게시는 항목 ≥ 1. 게시·폐기된 버전과 그 항목은 UPDATE/DELETE 금지(`draft`만 수정·삭제). 검사에서 참조한 버전은 삭제 RESTRICT.

### 4.3 `qms.inspection_spec_item` 검사 항목 (`spec`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| spec_id | bigint | ○ | FK (S, spec_id) → inspection_spec. UK(S, spec_id, seq) |
| seq | integer | ○ | ≥ 1, 화면 순서 |
| name | varchar(100) | ○ | 예: 외관, 핀 피치, 절연 저항 |
| method | varchar(12) | ○ | `RANGE` / `PASS_FAIL` |
| lower_limit | numeric(15,4) | | |
| upper_limit | numeric(15,4) | | |
| unit | varchar(10) | | `RANGE`이면 NN |
| is_required | boolean | ○ | default true |

- CHECK: `method = 'PASS_FAIL'` → 하한·상한·단위 모두 NULL. `method = 'RANGE'` → 하한·상한 중 1개 이상, 둘 다 있으면 `lower_limit ≤ upper_limit`.

### 4.4 `qms.inspection` 검사 (`inspection`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| inspection_no | varchar(40) | ○ | 서버 발번 `QI-YYYYMMDD-NNN`. UK(S, inspection_no) |
| source | varchar(10) | ○ | `MES`(조회로 만든 검사) / `MANUAL`(직접 입력) |
| lot_no | varchar(50) | ○ | LOT 번호 스냅샷 |
| item_code | varchar(40) | ○ | 스냅샷 |
| item_name | varchar(100) | ○ | 스냅샷 |
| lot_qty | numeric(15,3) | ○ | > 0. 검사 대상 수량(MES 최종 양품 스냅샷 또는 입력) |
| unit | varchar(10) | ○ | |
| sample_qty | numeric(15,3) | ○ | > 0, ≤ lot_qty (CHECK) |
| spec_id | bigint | ○ | FK (S, spec_id) → inspection_spec. 만들 때 게시 버전 고정 |
| reinspection_of_id | bigint | | 자기참조 FK (S, id). 재검사면 원 검사 |
| status | varchar(20) | ○ | `draft` / `confirmed`, default `draft` |
| result | varchar(10) | | `PASS` / `FAIL`. `status = 'confirmed'` ↔ NN (CHECK) |
| inspected_on | date | ○ | 검사일(업무 날짜) |
| inspection_month | varchar(7) | ○ | `'YYYY-MM'` CHECK 형식. inspected_on에서 파생(대시보드 월 집계) |
| confirmed_at | timestamptz | | confirmed ↔ NN |
| note | varchar(300) | | |

- **UK_PARTIAL**: (S, lot_no) WHERE status = 'draft' — LOT당 작성 중 검사 1건.
- SERVICE: `confirmed`는 UPDATE/DELETE 금지(세대 정리만 허용). `draft`만 삭제.

### 4.5 `qms.inspection_value` 검사 측정값 (`inspection`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| inspection_id | bigint | ○ | FK (S, inspection_id) → inspection. UK(S, inspection_id, spec_item_id) |
| spec_item_id | bigint | ○ | FK (S, spec_item_id) → inspection_spec_item. **검사의 spec_id에 속한 항목이어야 함(SERVICE)** |
| measured_value | numeric(15,4) | | RANGE 항목 |
| pass_value | boolean | | PASS_FAIL 항목 |
| judgement | varchar(4) | | `PASS` / `FAIL`. 서버가 계산. 값이 없으면 NULL |
| defect_type_id | bigint | | FK (S, defect_type_id) → defect_type. `judgement = 'FAIL'`이면 NN (SERVICE — 확정 시 검사) |

- CHECK: measured_value와 pass_value는 동시에 값이 있을 수 없다.
- 확정된 검사의 측정값은 UPDATE/DELETE 금지.

### 4.6 `qms.quality_hold` 품질 보류 (`hold`)

| 컬럼 | 타입 | NN | 규칙 |
|---|---|:-:|---|
| hold_no | varchar(40) | ○ | 서버 발번 `QH-YYYYMMDD-NNN`. UK(S, hold_no) |
| lot_no | varchar(50) | ○ | 스냅샷(검사에서 복사) |
| item_code | varchar(40) | ○ | 스냅샷 |
| inspection_id | bigint | ○ | FK (S, inspection_id) → inspection. 보류를 만든 불합격 검사 |
| status | varchar(20) | ○ | `held` / `released`, default `held` |
| held_at | timestamptz | ○ | |
| disposition | varchar(12) | | `REINSPECTED` / `CONCESSION` / `SCRAP`. released ↔ NN (CHECK) |
| release_inspection_id | bigint | | FK (S, id) → inspection. disposition = REINSPECTED ↔ NN |
| release_reason | varchar(300) | | CONCESSION·SCRAP이면 NN (CHECK) |
| released_at | timestamptz | | released ↔ NN |

- **UK_PARTIAL**: (S, lot_no) WHERE status = 'held' — LOT당 활성 보류 1건.
- SERVICE: `released`는 UPDATE/DELETE 금지. REINSPECTED의 해제 검사는 같은 lot_no, `confirmed`, `result = 'PASS'`, 보류보다 나중에 확정된 검사여야 한다.

### 4.7 core 변경

| 대상 | 변경 |
|---|---|
| `core.workspace_module` CHECK | `module_key IN ('core','mes','erp','fems','qms')` |
| 모듈 사용 여부 기본값 | 게스트·회원 공간 생성 시 `qms` 행 `enabled = true` 추가 |

### 4.8 규모

| 구분 | 현재 | 변경 |
|---|---:|---:|
| 업무 스키마 | mes 21 · erp 27 · fems 13 | + **qms 6** |
| 전체 테이블(schema.json 기준) | 71 | **77** |
| 상태 목록 | — | inspection_spec · inspection · quality_hold 3개 추가 |

## 5. 상태 전이

| 대상 | 전이 | 조건 |
|---|---|---|
| inspection_spec | `draft → published` | 항목 ≥ 1. 같은 품목의 기존 published → retired(같은 트랜잭션) |
| | `published → retired` | 사용자 폐기. 폐기해도 과거 검사는 그 버전을 계속 가리킨다 |
| | 개정 | published/retired 버전을 복사한 새 `draft`(version_no + 1) |
| inspection | `draft → confirmed` | 필수 항목 모두 값, 불합격 항목 모두 불량 유형. result 서버 계산 |
| quality_hold | (생성) `held` | 불합격 확정 시 자동(TX-Q2). 이미 활성 보류가 있으면 새로 만들지 않고 기존 보류를 유지 |
| | `held → released` | 처분 3종 중 하나(3장) |

## 6. 트랜잭션·잠금

기존 공간 우선 락 순서(FS-006 / FS-006a)를 따른다. QMS 트랜잭션은 **qms 스키마 행만 잠근다.** MES 조회는 잠그지 않는다(X5).

| TX | 내용 | 잠금 순서 |
|---|---|---|
| TX-Q1 기준 게시 | 새 버전 게시 + 이전 게시 버전 retired | 공간 → 같은 item_code의 spec 행(published → 대상) |
| TX-Q2 검사 확정 | 측정값 판정 → 검사 확정 → (불합격이면) 보류 생성 | 공간 → inspection → 같은 lot_no의 held 보류 |
| TX-Q3 보류 해제 | 처분 검증 → released | 공간 → quality_hold → (REINSPECTED면) 해제 검사 읽기 |

- 멱등: 모든 변경 POST는 `Idempotency-Key`(기존 core.request_receipt).
- 동시 확정: 같은 LOT의 두 검사가 동시에 불합격 확정되면 UK_PARTIAL(held 1건)로 두 번째 보류 생성이 막힌다. 서비스는 이 경우 **기존 보류를 유지하고 확정은 성공**시킨다(보류는 LOT 단위).

## 7. 교차 조회 인터페이스 (D9·X1~X6)

### 7.1 MES가 제공 — `fs/mes/interface.py`

| 함수 | 반환(값) | 용도 |
|---|---|---|
| `inspectable_lots(scope, completed_since=None)` | `[{lotNo, itemCode, itemName, finalGoodQty, unit, completedAt}]` — status completed · 최종 양품 > 0 | Q-03 검사 대기 |
| `lot_snapshot(scope, lot_no)` | 위 항목 1건 또는 `None` | 검사 생성 시 값 복사 |
| `items(scope, item_type='FG')` | `[{itemCode, name, baseUnit}]` | Q-02 기준 품목 선택 |

MES가 꺼져 있으면 모두 `None`(X4).

### 7.2 QMS가 제공 — `fs/qms/interface.py`

| 함수 | 반환 | 용도 |
|---|---|---|
| `held_lot_nos(scope)` | `set[str]` 또는 `None` | MES M-08 패킹·M-04 LOT 목록의 "QMS 보류" 배지 |
| `latest_results(scope, lot_nos)` | `{lotNo: 'PASS' \| 'FAIL'}` 또는 `None` | M-04 LOT 상세의 품질 판정 표시 |

MES 응답 필드: LOT 목록·패킹 대기 LOT에 `qualityHold: true | false | null`(null = QMS 꺼짐), LOT 상세에 `qualityResult`.

### 7.3 "검사 대기" 계산

`inspectable_lots` 결과에서 **확정 검사가 한 번도 없는 lot_no**를 대기로 본다(QMS 쪽에서 스냅샷 lot_no로 차집합). 검사가 draft로 있으면 "작성 중"으로 표시한다. 계산 결과를 저장하지 않는다.

## 8. API 계약 (`/api/v1/qms`, FS-010 3장 공통 규약)

| 메서드·경로 | 내용 |
|---|---|
| `GET /dashboard?month=YYYY-MM` | 검사 수·합격률·활성 보류 수·불량 유형 상위 5·최근 불합격 |
| `GET/POST /defect-types`, `PATCH/DELETE /defect-types/{id}` | 쓰인 유형 삭제는 409 `REFERENCED_BY_OTHERS`(참조처별 건수) |
| `GET /inspection-specs?itemCode=&status=` | 버전 목록(항목 수 포함) |
| `POST /inspection-specs` | 새 draft(품목 스냅샷). 같은 품목에 draft가 있으면 409 `DRAFT_EXISTS` |
| `GET/PATCH/DELETE /inspection-specs/{id}` | PATCH는 note + **항목 전체 교체**(draft만). 게시본은 409 `PUBLISHED_IMMUTABLE` |
| `POST /inspection-specs/{id}/publish` · `/retire` · `/revise` | TX-Q1 |
| `GET /lookups/mes-lots?pending=true` | 7.3 검사 대기. MES 꺼짐: 409 `PRECONDITION_NOT_MET`, `reason = "SOURCE_MODULE_DISABLED"` → 화면은 직접 입력으로 전환 |
| `GET /lookups/mes-items` | 7.1 items |
| `GET /inspections?status=&result=&month=&lotNo=` | 목록 |
| `POST /inspections` | `{source:'MES', lotNo}` 또는 `{source:'MANUAL', lotNo, itemCode, itemName, lotQty, unit}` + `sampleQty`, `inspectedOn`. 품목의 게시 기준이 없으면 409 `NO_PUBLISHED_SPEC` |
| `GET /inspections/{id}` | 기준 항목 + 측정값 + 항목 판정(미리 계산) |
| `PATCH /inspections/{id}` | 측정값·불량 유형·표본·메모(draft만) |
| `POST /inspections/{id}/confirm` | TX-Q2. 미입력 필수 항목은 400 `VALIDATION_FAILED` `details.fields.values.<seq>` |
| `POST /inspections/{id}/reinspect` | 같은 LOT의 새 draft(현재 게시 기준, `reinspection_of_id`) |
| `DELETE /inspections/{id}` | draft만 |
| `GET /holds?status=held` · `GET /holds/{id}` | 보류 목록·상세(원인 검사·재검사 이력) |
| `POST /holds/{id}/release` | `{disposition, releaseInspectionId?, reason?}` — TX-Q3. 조건 미충족 409 `RELEASE_NOT_ALLOWED` |

MES API 변경(읽기만): `GET /api/v1/mes/lots`·패킹 대기 LOT 응답에 `qualityHold`, `GET /api/v1/mes/lots/{id}`에 `qualityResult`.

## 9. 화면 (요약 — 상세는 화면 설계서)

| ID | 화면 | UI 패턴(UI-02·03) |
|---|---|---|
| Q-01 | 품질 대시보드 | D |
| Q-02 | 검사 기준 | P(F-12) — 버전 목록 → 항목 상세 → 항목 편집 |
| Q-03 | 검사 대기 | L(F-02) — MES 조회 목록 · "검사 시작" |
| Q-04 | 검사 | W(E-04) — 검사 목록 + 넓은 측정값 입력 패널 |
| Q-05 | 품질 보류 | V(M-04) + FormPanel — 보류 상세 · 해제 처분 |
| Q-06 | 불량 유형 | S(F-05) |

MES 변경 화면: M-08 패킹·M-04 LOT에 "QMS 보류" 배지(읽기만).

## 10. 합성 데이터 (FS-005g 확장)

| 대상 | 행 | 내용 |
|---|---:|---|
| defect_type | 6 | 4.1 |
| inspection_spec | 4 | FG-C100·FG-C200·FG-T300 게시 각 1 + FG-C100 v2 draft 1 |
| inspection_spec_item | 약 16 | 품목당 외관(PASS_FAIL)·치수 2~3(RANGE)·절연 저항(RANGE) |
| inspection | 약 18 | 시드의 완료 LOT 중 15건 확정(합격 13·불합격 2), 재검사 1, draft 1 |
| inspection_value | 약 80 | 항목 × 검사 |
| quality_hold | 2 | 1건 `held`(현재 보류 — MES 패킹에 배지 시연), 1건 `released` CONCESSION |

- 시드의 lot_no·item_code는 MES 시드와 **같은 문자열**로 심는다(D11). FK는 없다.
- 합계 약 **126행** 추가 → 게스트 복사 약 7,590행. 복사 시간 영향은 FS-023c에서 실측한다.
- `inspection_month`는 복사 시 `inspected_on` 일수 이동 뒤 다시 계산하는 **달력 파생 컬럼 목록에 추가**한다(기존 9종 → 10종).

## 11. 수용 기준 (AC-97~110)

AC-81~96은 FS-013에서 폐기된 번호라 **97부터** 쓴다.

| AC | 기준 |
|---|---|
| 97 | 게시한 검사 기준의 항목을 바꾸면 409이고 값은 그대로다 |
| 98 | 새 버전을 게시하면 같은 품목의 이전 게시 버전이 retired가 되고, 게시 버전은 항상 1개다 |
| 99 | 기준을 개정해도 이미 만든 검사의 기준·판정은 바뀌지 않는다 |
| 100 | RANGE 항목은 서버가 판정한다(클라이언트가 PASS를 보내도 상한 초과면 FAIL) |
| 101 | 필수 항목 누락 확정은 400이고 필드별 사유가 있다 |
| 102 | 불합격 확정과 보류 생성이 한 트랜잭션이다(보류 생성 실패 시 확정도 롤백) |
| 103 | 같은 LOT 불합격 두 건이 동시에 확정돼도 활성 보류는 1건이다 |
| 104 | 확정 검사·해제 보류는 수정·삭제할 수 없다 |
| 105 | REINSPECTED 해제는 보류 이후 확정된 같은 LOT 합격 검사가 없으면 409 |
| 106 | CONCESSION·SCRAP은 사유 없이 해제할 수 없다 |
| 107 | MES를 끄면 검사 대기 조회는 `SOURCE_MODULE_DISABLED`이고, 직접 입력으로 검사·확정이 된다 |
| 108 | QMS를 끄면 MES 화면·API는 그대로 동작하고 `qualityHold`는 null이다 |
| 109 | 보류 중인 LOT도 MES 패킹은 허용된다(D10). 패킹 대기 목록에 배지만 보인다 |
| 110 | 다른 공간·이전 세대의 LOT은 조회 인터페이스로 보이지 않는다(X3) |

격리 검사: R1(qms 포함) · R5 · **R6(interface import만 허용)** 통과.

## 12. 하지 않는 것 / 후속

- 수입검사(구매 자재 LOT)·공정 중 검사: 검사 `inspection_type` 컬럼은 두지 않는다(필요해지면 확장).
- 표본 크기 자동 계산(AQL)·SPC 관리도·Cpk.
- 측정기·검교정, 고객 클레임, CAPA, 8D.
- 보류에 의한 패킹·출하 차단(D10), 폐기 수량의 MES·재고 반영(WMS 경계).
- 도면·사진 첨부.

## 13. 결정이 필요한 것 (승인 시 함께 확인)

1. 검사 번호·보류 번호를 서버 발번(`QI-`/`QH-` + 일자 + 순번)으로 하는 것 — MES LOT 번호처럼 사용자 입력으로 할지.
2. 대시보드 기본 월: 서버가 정한 "시드 기준 최근 월"(F-01과 같은 방식)으로 하는 것.
3. 불합격 LOT이 이미 패킹된 경우에도 보류를 만드는 것(패킹 여부와 무관하게 LOT 단위 기록) — 권장: 만든다.

## 14. 구현 기록 (FS-023b, 2026-09-27)

| 항목 | 구현 |
|---|---|
| 모듈 행 | 마이그레이션 `fs023b_qms_module`(데이터만): 기존 모든 공간에 `qms` 행 추가. 회원 생성·시드 템플릿도 `qms` 포함(템플릿 모듈 행 4 → 5). 범위 확인은 행이 없으면 꺼진 것으로 본다 |
| 품목 조회 | MES `item_type='finished'`(완제품)만 기준 대상으로 돌려준다 |
| 검사 대기 | `GET /lookups/mes-lots?pending=`로 검사 완료 LOT 포함 여부를 고른다. 화면은 기본 대기만 |
| 표본 기본값 | Q-03 "검사 시작"은 `min(최종 양품, 32)`로 만들고 Q-04에서 고친다(AQL 미계산, 3장) |
| 측정값 행 | 검사를 만들 때 기준 항목마다 빈 행을 만들고 PATCH는 행 단위 UPDATE |
| 동시 불합격 | 보류 INSERT는 부분 유니크 인덱스를 대상으로 `ON CONFLICT DO NOTHING` — 활성 보류 1건 유지(AC-103) |
| 공간 정리·시드 | `_business_table_order`·시드 복사·검증의 스키마 목록에 `qms` 추가. QMS 시드는 FS-023c |
| 화면 | Q-01~06(`frontend/src/qms/`), 런처·내 공간 스위치·다른 앱 링크·라인 아이콘, MES M-04·M-08 배지 |
| 검증 | backend `test_qms.py` 21(AC-97~110 대응, AC-103은 순차 경로), frontend `qms.test.tsx` 10, e2e `qms.spec.ts` 2 + layout 5 + 360px 6 |

## 15. 구현 기록 (FS-023c, 2026-09-27)

| 항목 | 구현 |
|---|---|
| 시드 | `backend/seed/generate.py` `_qms` — **113행**(설계 추정 약 126행보다 적다: 항목 4 × 검사 17). seed_version `sv-20260927-1`, 템플릿 7,470 → **7,583행**(게스트 복사 7,581) |
| 불량 유형 6 | `MOLD_DAMAGE`·`SHORT_SHOT`·`PIN_MISALIGN`·`CONTACT_FAIL`(MES 불량 사유와 같은 코드) + `APPEARANCE`·`DIMENSION` |
| 검사 기준 4 · 항목 16 | FG-C100·C200·T300 v1 게시(T−60) + FG-C100 v2 초안(핀 피치 2.50~2.58 검토). 품목당 외관(PASS_FAIL)·치수 2(RANGE)·절연 저항(RANGE, 하한만) |
| 검사 17 · 측정값 68 | 확정 15 = E01~E12·W01·W02·W04(LT-0001~0014·LT-0016), 합격 13 · 불합격 2(E08 LT-0008 핀 피치 2.61 → `PIN_MISALIGN`, W04 LT-0016 외관 → `APPEARANCE`). 작성 중 2 = W03 LT-0015(항목 2개만 입력), W04 재검사(빈 값). **W05 LT-0017은 검사 대기**로 남긴다. 검사일 = 최종 공정 완료 다음 날, 번호 `QI-검사일-순번` |
| 보류 2 | LT-0008 `released` CONCESSION(+2일), LT-0016 `held` — 패킹 대기 LOT이라 M-08에 "QMS 보류" 배지. 시드 재검사를 확정하면 REINSPECTED로 해제할 수 있다 |
| 게스트 복사 | `seed/copy.py`: `inspection_month` = 옮긴 `inspected_on`의 월(달력 파생 10종째). `inspection_no`·`hold_no` 속 `YYYYMMDD`도 같은 일수만큼 옮긴다(번호와 검사일 일치). 공간 정리·세대 정리는 FS-023b에서 qms 포함 |
| 시드 검증 | V1 행 수, V2에 검사 월·번호 날짜 = 검사일, V3에 검사 LOT·품목 스냅샷 = MES 완료 LOT(값 비교, FK 아님) |
| 도움말·흐름 맵 | `content/help/qms/q-01~06.md`, 공통 안내에 "솔루션 간 읽기 전용 조회". 흐름 맵 품질검사 노드 `solution`(도움말 `qms/q-03`) — 스키마에 qms 업무 노드 허용. 직결선은 "QMS를 끄면 이 경로"로 이름만 바꿨다(연결 종류가 solution/card 두 가지라 점선 구분은 하지 않음). 설명 카드는 WMS·BEMS·SCM만(`content/cards/qms.md` 삭제), P-05 참고 문서에 QMS 구역 |
