# FS-010 API 계약서

작성일: 2026-09-23
전제: 스키마 v0.9.1 / FS-008c (71테이블) · [FS-013 전환 결정](../plan/독립솔루션_전환결정_FS-013.md)
대상: [FS-008a 화면 설계](../ui/화면설계_포털_FS-008a.md) 54화면이 호출하는 HTTP 계약
성격: **구현 전 명세.** 실제 서버는 없으며 동작을 검증한 적이 없다.

---

## 1. 기본 구조

### 1-1. 네임스페이스

솔루션마다 경로를 나눈다. API 서버는 1개이며 라우터로만 분리한다(FS-013 D2).

```
/api/v1/core/...     포털 — 인증·공간·세대·운영
/api/v1/mes/...      MES
/api/v1/erp/...      ERP
/api/v1/fems/...     FEMS
```

**업무 네임스페이스끼리 서로를 호출하지 않는다.** ERP 핸들러가 MES 테이블을 읽지 않는 것과 같은 규칙이 API 계층에도 적용된다. 화면이 두 솔루션 데이터를 함께 보여줄 일이 없으므로 조인 엔드포인트도 없다.

`/api/v1/core`만 모든 솔루션이 공통으로 쓴다. 인증·공간 정보가 여기서 나온다.

### 1-2. 버전

경로에 `v1`을 박는다. 헤더 방식은 캐시·로그·디버깅이 모두 불편하다. 포트폴리오 범위에서 v2는 나오지 않는다.

---

## 2. 인증과 범위

### 2-1. 세션

| 항목 | 방식 |
|---|---|
| 자격 증명 | HttpOnly · Secure · SameSite=Lax 쿠키 |
| 저장 | 회원은 `core.auth_session.token_hash`, 게스트는 `core.workspace.guest_session_key` (모두 원문 미보관) |
| CSRF | 회원은 `csrf_token_hash`, 게스트는 서버 비밀과 세션 키의 HMAC 파생 토큰. 상태를 바꾸는 요청은 모두 `X-CSRF-Token` 헤더 필수 |
| 게스트 | 회원과 같은 쿠키 속성·검증 흐름. `workspace.guest_actor_key`로 주체를 식별 |

**게스트도 정식 세션을 받는다.** 회원과 게스트는 HttpOnly·Secure·SameSite=Lax 쿠키와 하나의 인증 해석기를 공유한다. 토큰의 `m_`/`g_` 접두어로 조회 저장소를 먼저 결정하며 두 저장소를 차례로 조회하지 않는다. 인증 해석 결과는 `{actor_kind, actor_key, workspace_id, user_id}` 단일 문맥이다. 업무 코드는 저장소 차이를 알지 못한다.

게스트 종료 시 `revoked_at` 대신 `guest_session_key`를 새 난수 해시로 교체해 기존 쿠키를 무효화한다. `expires_at`이 지난 요청은 거부하며 만료 공간을 신규 세션으로 재개하지 않는다. `request_receipt`와 `audit_event`의 `actor_key`는 회원은 사용자 식별 키, 게스트는 `workspace.guest_actor_key`를 사용한다. 토큰·쿠키·해시는 감사·요청 결과·요청 로그에 기록하지 않는다.

> **FS-016 정정 이력 (2026-09-24):** 이전 문구는 게스트도 `auth_session`에 저장되는 것으로 읽힐 수 있었다. FS-006b 정책 284·287의 GUEST 주체 계약, `workspace.guest_session_key` 부분 유니크(사유: 게스트 세션 식별), 계정 없는 게스트의 `actor_kind='GUEST'` + 공간 UUID `actor_key` 구조를 근거로 저장소를 위와 같이 명시했다. 스키마와 마이그레이션은 변경하지 않았다.

### 2-2. 범위 키는 클라이언트가 보내지 않는다

**이게 이 문서에서 가장 중요한 결정이다.**

`S = (workspace_id, generation_id)`는 **서버가 세션에서 파생한다.** 요청 본문이나 쿼리에 `workspace_id`를 받지 않는다.

받으면 어떤 일이 생기는가: 클라이언트가 남의 `workspace_id`를 넣어 보낼 수 있고, 모든 핸들러가 "이 사용자가 이 공간의 주인인가"를 매번 검사해야 한다. 한 군데만 빠뜨리면 다른 사용자의 데이터가 새어 나간다. 검사를 71개 테이블에 걸쳐 빠짐없이 하는 것보다, **애초에 받지 않는 쪽이 구조적으로 안전하다.**

```
요청 → 세션 조회 → workspace_id 확정 → generation_id = 활성 세대
     → 이후 모든 질의에 서버가 주입
```

세대 전환처럼 세대를 명시해야 하는 경우만 예외로 두고, 그때도 **해당 공간 소유 세대인지 서버가 검사한다.**

### 2-3. 권한

| 계층 | 담당 |
|---|---|
| 플랫폼 역할 | `core.role` — GUEST / OWNER / ADMIN. `/api/v1/core` 접근 제어 |
| 업무 권한 | 각 솔루션이 자체 보유. 메뉴·기능 단위 |

**플랫폼 역할이 업무 권한을 결정하지 않는다.** OWNER라고 ERP 매출 확정 권한이 자동으로 생기지 않는다. 1차 범위에서는 업무 권한을 "공간 소유자면 전부 허용"으로 두되, **계층은 분리해 둔다.** 나중에 세분화할 때 구조를 갈아엎지 않기 위해서다.

`/api/v1/core/admin/*`은 ADMIN만 접근한다. 게스트에게는 404를 준다(403이 아니다 — 존재 자체를 알릴 필요가 없다).

---

## 3. 공통 규약

### 3-1. 응답 형태

```jsonc
// 단건
{ "data": { ... } }

// 목록
{ "data": [ ... ], "page": { "offset": 0, "limit": 50, "total": 128 } }

// 오류
{ "error": { "code": "REFERENCED_BY_OTHERS", "message": "...", "details": { ... } } }
```

`data`로 한 번 감싼다. 최상위에 배열을 직접 두지 않는다.

### 3-2. 페이지네이션

**offset 방식을 쓴다.** 최대 데이터가 `fems.energy_reading` 약 6,480행이고 화면마다 필터가 걸린다. 이 규모에서 cursor 방식은 구현 비용만 늘린다.

- 기본 `limit=50`, 최대 200
- 정렬은 `sort=field:asc|desc`. 화이트리스트 밖 필드는 400

### 3-3. 오류 코드

HTTP 상태와 도메인 코드를 함께 준다. 화면이 분기해야 하는 것만 코드로 만든다.

| HTTP | 코드 | 상황 |
|---|---|---|
| 400 | `VALIDATION_FAILED` | 입력 형식 오류. `details.fields`에 필드별 사유 |
| 401 | `SESSION_EXPIRED` | 세션 없음·만료 |
| 403 | `FORBIDDEN` | 권한 없음 |
| 404 | `NOT_FOUND` | 대상 없음. 범위 밖 자원도 여기로 |
| 409 | `ALREADY_CONFIRMED` | 확정된 데이터 수정 시도 |
| 409 | `REFERENCED_BY_OTHERS` | RESTRICT 위반. **`details.references`에 참조처별 건수** |
| 409 | `LIMIT_EXCEEDED` | 소명 합계·배정 수량 초과. `details`에 한도와 현재값 |
| 409 | `PRECONDITION_NOT_MET` | 취소 조건 미충족 등. `details.reason` |
| 410 | `WORKSPACE_EXPIRED` | 게스트 공간 만료 |
| 422 | `IDEMPOTENCY_CONFLICT` | 같은 키에 다른 본문 |
| 429 | `RATE_LIMITED` | 게스트 생성 상한 등 |

**`REFERENCED_BY_OTHERS`의 `details.references`는 필수다.** FS-008a에서 "삭제할 수 없습니다만 띄우면 사용자가 다음 행동을 못 정한다"고 정했다. 그 화면 요구를 API가 받쳐야 한다.

### 3-4. 멱등키

`core.request_receipt`가 이미 그 구조를 갖고 있다.

- **상태를 바꾸는 모든 POST에 `Idempotency-Key` 헤더를 요구한다.** GET·목록 조회는 제외.
- 서버는 `(operation_key, request_key)`로 기존 처리를 찾고, `request_hash`(정규화 본문 SHA256)가 같으면 저장된 응답을 그대로 반환한다.
- 해시가 다르면 `422 IDEMPOTENCY_CONFLICT`. 같은 키로 다른 내용을 보내는 것은 클라이언트 버그다.

**보존기간과 재시도 허용기간을 일치시킨다.** FS-014b가 남긴 제약이다. 소명을 물리 삭제한 뒤 옛 등록 요청이 재실행되면 UK만으로는 막을 수 없다.

- **둘 다 24시간으로 맞춘다.** 게스트 공간 수명과 같은 자릿수이고, 사용자가 24시간 뒤 같은 요청을 재전송하는 경우는 없다.
- 만료된 키로 온 요청은 **새 요청으로 처리하지 않고 `422`로 거부한다.** 조용히 중복 생성하는 것보다 낫다.

### 3-5. 날짜와 수치

- 연·월·주차는 **문자열**이다. `'2026-09'`, `'2026-W38'`. 정수로 받지 않는다(AGENTS §3).
- 금액·수량은 **문자열로 직렬화**한다. JSON number는 부동소수점이라 금액에서 오차가 난다. `"1200000.00"`.
- 시각은 ISO 8601 UTC. 표시 시간대는 `site.timezone`으로 클라이언트가 변환한다.

---

## 4. 포털 API (`/api/v1/core`)

| 메서드 | 경로 | 화면 | 비고 |
|---|---|---|---|
| POST | `/guest-sessions` | P-01 | 게스트 공간 생성 + 세대 복사 |
| POST | `/sessions` | P-01 | 로그인 |
| DELETE | `/sessions/current` | — | 로그아웃 |
| GET | `/sessions/current` | 전역 | 사용자·공간·역할·만료 |
| GET | `/workspace` | P-02 P-06 | 공간 정보 |
| GET | `/workspace/modules` | P-02 | 앱 사용 여부 |
| PATCH | `/workspace/modules/{key}` | P-06 | 앱 on/off |
| POST | `/workspace/generations` | P-06 | 예시 데이터 초기화 |
| GET | `/admin/job-runs` | P-07 | ADMIN만 |
| GET | `/admin/audit-events` | P-07 | ADMIN만 |

정적 콘텐츠(흐름 맵 P-03 · 설명 카드 P-04 · 도움말 P-05)는 **API가 아니다.** 빌드 산출물로 배포한다(FS-013 D6). 경로는 FS-011에서 정한다.

### 게스트 생성이 특별한 이유

`POST /guest-sessions`는 약 6,840행 복사를 동반한다. 화면에서 진행 표시가 필요하다고 FS-008a에서 정했다.

**동기 처리로 둔다.** 비동기 작업 큐를 만들면 폴링 엔드포인트·작업 상태 테이블·실패 재시도가 따라온다. 목표가 2초이고 실측 전이므로, 먼저 동기로 만들고 실측 후 판단한다. 지금 비동기로 설계하는 것은 근거 없는 복잡도다.

- 타임아웃 시 `504`. 부분 생성 없이 전량 롤백.
- 전역 상한 초과 시 `429 RATE_LIMITED`.

---

## 5. 세션 종료 판정

FS-008b가 "세션 생존 판정은 서비스 책임이며 상세는 FS-010"으로 미뤄둔 항목이다.

### 판정 규칙

세션이 **살아 있다**고 보는 조건:

```
revoked_at IS NULL
AND expires_at > now()
AND last_seen_at > now() - 30분
```

### 게스트 회수 조건

```
workspace.expires_at <= now()
AND 활성 세션 없음
AND 진행 중 요청 없음
```

만료 시각만으로 회수하지 않는다. 작업 중인 게스트를 끊으면 데모가 중단된다.

### 갭 — `last_seen_at`이 없다

`core.auth_session`에는 `expires_at`과 `revoked_at`만 있다. **마지막 활동 시각을 담을 컬럼이 없어서 위 판정을 구현할 수 없다.**

세 가지 처리안:

| 안 | 내용 | 비용 |
|---|---|---|
| A | `auth_session.last_seen_at` 컬럼 추가 | 컬럼 1개. 매 요청 UPDATE |
| B | 짧은 만료 + 갱신으로 대체 (`expires_at`을 30분으로 두고 요청마다 연장) | 컬럼 없음. `expires_at`이 두 의미를 겸함 |
| C | 세션 생존 판정을 포기하고 만료 시각만 사용 | 공짜. 작업 중 회수가 발생 |

**B를 제안한다.** 컬럼을 늘리지 않고, "만료 시각"과 "마지막 활동 + 30분"이 사실상 같은 값이 된다. 매 요청 UPDATE는 A도 마찬가지다. C는 FS-008b에서 이미 배제한 방향이다.

B를 택하면 **스키마 변경 없이 해소된다.** 다만 `expires_at`이 "절대 만료"와 "유휴 만료"를 겸하게 되므로 그 사실을 문서에 명시해야 한다.

---

## 6. 업무 API 패턴

기준정보 24화면(FEMS 6 · ERP 4 · MES 6 + 목록형)은 동일 패턴이다.

```
GET    /{resource}          목록. 필터·정렬·페이지
POST   /{resource}          등록
GET    /{resource}/{id}     단건
PATCH  /{resource}/{id}     수정
DELETE /{resource}/{id}     삭제 → RESTRICT 시 409 + references
```

**확정·게시된 자원은 PATCH·DELETE가 409를 반환한다.** 재산정은 새 버전 생성이다(AGENTS §3).

업무 실행 엔드포인트는 **명사 대신 동작으로 쓴다.** 상태 전이가 단순 수정이 아니기 때문이다.

```
POST /work-orders/{id}/release       발행
POST /executions/{id}/start          시작
POST /sales-records/{id}/cancel      취소
```

---

## 7. FEMS API (`/api/v1/fems`)

| 메서드 | 경로 | 화면 |
|---|---|---|
| GET | `/dashboard` | F-01 |
| GET | `/readings` | F-02 |
| GET | `/allocations` | F-03 |
| GET | `/emissions` | F-04 |
| GET·POST | `/production-records` | F-05 |
| GET | `/intensity` | F-06 |
| GET | `/targets/performance` | F-07 |
| GET | `/billing` | F-08 |
| — | `/sites` `/locations` `/equipments` `/energy-sources` `/meters` `/meters/{id}/channels` `/energy-factors` `/tariffs` | F-09~14 |

### FS-018a에서 확정한 업무 API 공통 규칙

- 업무 모듈 API는 요청마다 같은 트랜잭션에서 활성 세대와 `workspace_module.enabled`를 다시 읽는다(`fs/common/scope.py`). 꺼진 모듈은 조회·쓰기 모두 409 `PRECONDITION_NOT_MET`, `details.reason = "MODULE_DISABLED"`.
- 변경 요청(POST·PATCH·DELETE)은 CSRF와 `Idempotency-Key`를 모두 요구한다.
- 요청 본문의 모르는 필드는 400. 범위 키를 본문으로 받지 않는다는 2-2 규칙의 구현이다.
- 코드 중복은 400 `VALIDATION_FAILED` + `details.fields.<필드>`로 준다(화면 인라인 오류).
- `details.references`는 `[{ "table", "label", "count" }]` 배열이다.
- 참조 중인 에너지원의 계측 단위 변경은 409 `PRECONDITION_NOT_MET`, `reason = "UNIT_IN_USE"`.
- 계측기가 연결된 설비의 공간 변경은 409 `PRECONDITION_NOT_MET`, `reason = "LOCATION_IN_USE"` (AG-05).
- `GET /readings` (FS-018b): 날짜 `D`는 사업장 시간대의 `(D 00:00, D+1 00:00]`. 기간을 생략하면 최근 계측일까지 7일, 응답 `range`로 알린다. 최대 31일. **`quality = invalid` 행의 `value`는 `null`**(0 합산 방지).
- `GET /allocations` (FS-018c): 구간 `[D 00:00, D+1 00:00)`. 같은 설비·채널·구간에서 `input_revision`, `method_version`이 가장 큰 행이 현재 결과(`isLatest`). 기본은 현재 결과만, `includeSuperseded=true`로 이전 결과 포함. 필터는 현재 판정 뒤에 적용. `summary`는 현재 결과·invalid 제외·설비×단위별 합계.
- 요금제(F-14): 같은 에너지원에서 적용 기간 `[effective_from, effective_to]`(NULL = 계속 적용)이 겹치는 등록·수정은 409 `PRECONDITION_NOT_MET`, `reason = "PERIOD_OVERLAP"` (사용자 승인 2026-09-24).
- `GET /emissions` (FS-018d): 최상위 계측기(`parent_meter_id IS NULL`)만 합산, invalid 제외, 배수 적용, 계측 연도별 EMISSION 계수. 상태 `CALCULATED`/`NOT_APPLICABLE`(UTILITY)/`FACTOR_MISSING`/`UNIT_MISMATCH`. 총량은 계산된 에너지원만, 계산 불가가 있으면 `complete=false`. 기본 당월 누계, 최대 366일.
- `GET /dashboard?month=YYYY-MM` (FS-018f): 총 소비 TOE(PRIMARY, 환산 후 합산, UTILITY 제외), 사업장 TOE 목표 달성률(실적÷목표, 목표 없으면 UNSET), 예상 요금(부과 대상별 기본요금 + 누계 사용량 × 그 달 요금제 단가, 원 단위), 배출량(F-04와 동일), 일자별 TOE, 설비 상위 5(kWh), 품질 이상(valid 아님, 전체 채널). 기본은 최근 계측월 누계.
- `GET /targets/performance?month=YYYY-MM` (FS-018g): `site`(에너지원별 + TOE)와 `equipment`(kWh) 섹션을 나눠 합산하지 않는다. 상태 `WITHIN`/`EXCEEDED`/`UNSET`/`NOT_CALCULABLE`(실적 없음 또는 목표·실적 단위 불일치). 당월은 `monthToDate=true`(최근 계측일까지 누계).
- `GET /billing?from=YYYY-MM&to=YYYY-MM` (FS-018h): 월 요금 = 기본요금 + 사용량 × 단가(원 단위), 요금제는 월마다 선택(개정 월에서 구간 분할). 상태 `CALCULATED`/`TARIFF_MISSING`/`NOT_BILLABLE`. 계측 없는 달은 미청구. 기본 전월~당월, 최대 12개월. 대시보드 요금은 같은 계산을 쓴다.
- `/production-records` (FS-018i): 초안 등록(`MAN-YYYYMMDD-NNN`)·수정·삭제, `POST /{id}/confirm`, `POST /{id}/revise`(다음 버전 초안). 확정 불변 409 `ALREADY_CONFIRMED`, 정정 제약 409 `DRAFT_EXISTS`/`NOT_LATEST`/`REVISION_FIELDS_FIXED`, 확정 시 같은 설비·품목·단위 구간 겹침 409 `PERIOD_OVERLAP`(+`conflicts`). 날짜 입력은 사업장 시간대 `[시작 00:00, 종료+1 00:00)`.
- `GET /intensity` (FS-018j): 기본 최근 계측일까지 31일, 최대 92일. 기록별 = 생산 구간에 완전히 포함된 설비 일별 배분(현재 결과, invalid 제외) ÷ 생산량, 단위별로 따로, TOE/EA는 PRIMARY 환산(용수 제외). 상태 `NO_PRODUCTION`(생산량 0)/`NO_ENERGY`. 품목별 = 검사(INS)까지 끝나고 모든 공정이 기간 안인 MES LOT만, LOT 전 공정 전력 ÷ 검사 양품. MAN- 기록은 품목에서 제외. 확정 기준선 대비 증감률.
- 업무 기준일 (FS-018j): 게스트 복사·세대 초기화의 "오늘"은 `FS_TODAY`(테스트·스모크 전용) 또는 실제 KST 날짜. 게스트 만료는 항상 실제 생성일 다음 날 00:00 KST. `COOKIE_SECURE=false`면 세션 쿠키에서 Secure를 뺀다(로컬 HTTP 전용, 기본 true).

### 계산 결과를 저장하지 않는 엔드포인트

`/emissions` · `/billing` · `/intensity`는 **조회 시 계산**한다. 결과를 담는 테이블이 없다(FS-008a G-04).

응답에 **계산 근거를 함께 싣는다.** 화면의 "계산 근거 패널"이 이 데이터를 쓴다.

```jsonc
{ "data": { "amount": "...", "basis": {
    "factor": { "kind": "EMISSION", "year": "2026", "value": "...", "source": "..." },
    "consumption": { "quantity": "...", "unit": "kWh" } } } }
```

**1차에너지 환산 값에는 항상 환산 여부를 표기한다.** 단위가 다른 에너지원을 합산한 값은 환산 후에만 의미가 있다.

---

## 8. ERP API (`/api/v1/erp`)

| 메서드 | 경로 | 화면 |
|---|---|---|
| GET | `/dashboard` | E-01 |
| — | `/quotations` `/quotations/{id}/revisions` | E-02 |
| — | `/sales-plans` | E-03 |
| — | `/sales-orders` | E-04 |
| — | `/shipment-orders` `/shipments` | E-05 E-06 |
| GET | `/sales-records` | E-07 |
| POST | `/sales-records/{id}/cancel` | E-07 |
| — | `/tax-invoices` | E-08 |
| POST | `/tax-invoices/{id}/issue` | E-08 |
| GET | `/receivables` | E-09 |
| GET·POST | `/receipts` | E-10 |
| POST | `/receipts/{id}/applications` | E-10 |
| DELETE | `/receipts/{id}/applications/{applyId}` | E-10 |
| GET | `/receipts/{id}/fifo-suggestion` | E-10 |
| — | `/purchase-invoices` `/payables` `/payments` `/payments/{id}/applications` | E-11~13 |
| GET | `/journal-preview` | E-14 |
| — | `/partners` `/items` `/partner-prices` `/accounts` `/posting-rules` | E-15~18 |

### 소명 계약

- **`POST /receipts/{id}/applications`는 수금 확정 후에도 호출 가능하다.** 확정되는 것은 금액이지 배분이 아니다(FS-014b).
- **`DELETE`는 물리 삭제다.** `core.audit_event`에 이력이 남는다.
- 한도 초과 시 `409 LIMIT_EXCEEDED` + `details`에 초과한 채권 식별자.
- `GET /fifo-suggestion`은 **제안만 반환하고 저장하지 않는다.** 화면의 "FIFO로 채우기" 버튼이 쓴다.

### 잔액과 상태는 서버가 계산한다

`receivable` 응답에 `balance`와 `status`를 포함한다. **컬럼이 아니라 조회 시 산출한 값이다.** 클라이언트가 원금에서 소명액을 빼는 계산을 하지 않는다. 계산이 두 곳에 있으면 언젠가 어긋난다.

### 분개 미리보기

```
GET /journal-preview?kind=SALES&sourceId=...
GET /journal-preview?kind=RECEIPT&applyId=...
```

- `kind`는 `SALES` · `RECEIPT` · `PURCHASE` · `PAYMENT` 4종.
- 수금·지급은 **소명 행 단위**다. `applyId`를 받는다.
- 응답에 미소명 잔여를 `unapplied`로 별도 표기한다. **분개 라인에 섞지 않는다.**
- 저장하지 않으므로 POST가 없다.

---

## 9. MES API (`/api/v1/mes`)

| 메서드 | 경로 | 화면 |
|---|---|---|
| GET | `/dashboard` | M-01 |
| — | `/production-plans` | M-02 |
| — | `/work-orders` | M-03 |
| POST | `/work-orders/{id}/release` | M-03 |
| POST | `/work-orders/{id}/cancel` | M-03 |
| GET | `/lots` `/lots/{id}` | M-04 |
| GET·POST | `/executions` | M-05 |
| POST | `/executions/{id}/finish` | M-05 |
| GET·POST | `/executions/{id}/material-issues` | M-06 |
| GET | `/executions/{id}/bom-requirement` | M-06 |
| POST | `/executions/{id}/result` | M-07 |
| — | `/packing-units` `/packing-units/{id}/members` | M-08 |
| — | `/finished-goods-receipts` | M-09 |
| — | `/sites` `/locations` `/equipments` `/items` `/processes` `/routes` `/boms` | M-10~15 |

### LOT 상세가 핵심 응답이다

`GET /lots/{id}`는 추적성을 보여주는 화면(M-04)을 받친다. 공정 실행 · 투입 자재 · 실적을 **한 번에 반환한다.** 화면이 세 번 호출하게 두지 않는다.

### 자재 투입

`GET /bom-requirement`가 BOM 기준 소요량(로스율 반영)을 반환하고 화면이 기본값으로 채운다.

- **BOM이 없는 지시면 빈 배열을 반환한다.** 404가 아니다. BOM 없는 지시는 정상 경로다(FS-008b D-2).
- 투입은 기록일 뿐 재고를 차감하지 않는다. 응답에 그 사실을 표시하는 플래그를 두지 않는다 — **화면의 고정 안내로 처리한다.**

### 실적 확정

`POST /executions/{id}/result`는 `양품 + 불량 = 산출` 등식을 서버가 검증한다. 불량이 있는데 사유가 없으면 `400 VALIDATION_FAILED`.

---

## 10. SERVICE 정책과 API의 관계

DB 제약으로 표현할 수 없어 서비스가 지켜야 하는 규칙들이다. **전부 API 계층에서 강제한다.**

| 정책 | 적용 엔드포인트 | 위반 응답 |
|---|---|---|
| Σ소명액 ≤ 수금액·채권 원금 | `POST /receipts/{id}/applications` | 409 `LIMIT_EXCEEDED` |
| 배정 합계 ≤ 계획·수주 수량 | `POST /work-orders` `POST /shipment-orders` | 409 `LIMIT_EXCEEDED` |
| 패킹 수량 ≤ LOT 양품 | `POST /packing-units/{id}/members` | 409 `LIMIT_EXCEEDED` |
| 설비 동시 점유 금지 | `POST /executions` | 409 `PRECONDITION_NOT_MET` |
| 매출 취소 조건 | `POST /sales-records/{id}/cancel` | 409 `PRECONDITION_NOT_MET` |
| 선발행 금지 | `POST /tax-invoices` | 409 `PRECONDITION_NOT_MET` |
| 게스트 전역 상한 | `POST /guest-sessions` | 429 `RATE_LIMITED` |

**전부 트랜잭션 안에서 부모 행을 잠근 뒤 재계산해 검사한다.** 클라이언트 검증은 편의일 뿐이며 서버 검사가 최종이다. 잠금 순서는 FS-006a 8단계를 따른다.

---

## 11. 하지 않은 결정

| # | 항목 | 사유 |
|---|---|---|
| 1 | 요청·응답 스키마의 필드 단위 정의 | 71테이블 × 평균 10컬럼. 구현 단계에서 스키마 메타데이터로 생성하는 편이 정확하다 |
| 2 | 실시간 갱신(WebSocket·SSE) | 단일 사용자 체험 환경이라 필요 없다 |
| 3 | 파일 업로드 | 1차 범위에 첨부 기능이 없다 |
| 4 | 레이트 리밋 세부 수치 | 게스트 생성 외에는 실측 후 |
| 5 | OpenAPI 문서 생성 | FS-011 개발 규약에서 도구를 정한 뒤 |
| 6 | 캐시 헤더 전략 | 동적 데이터 위주. 정적 콘텐츠만 FS-011에서 |

---

## 12. 결정이 필요한 것

| # | 항목 | 제안 |
|---|---|---|
| **A-1** | 세션 생존 판정 (5장) | **B안** — `expires_at`을 유휴 만료로 겸용, 요청마다 연장. 스키마 변경 없음 |
| **A-2** | 멱등키 보존·재시도 기간 | **24시간 일치.** 만료 키는 422 거부 |
| **A-3** | 게스트 생성 동기·비동기 | **동기.** 실측 후 재판단 |
| **A-4** | 페이지네이션 | **offset.** cursor는 과설계 |
| **A-5** | 금액 직렬화 | **문자열.** JSON number 금지 |

A-1만 스키마와 관련이 있고 나머지는 구현 방침이다. **A-1을 B로 정하면 FS-010은 스키마 변경 없이 닫힌다.**

---

## 13. 이번 작업에서 하지 않은 것

- **스키마 변경 없음.** 5장의 `last_seen_at` 갭은 B안으로 회피 가능하다.
- 실제 서버·엔드포인트 구현. 전부 명세다.
- 요청·응답 본문의 필드 단위 정의(11장 1번).
- 성능·동시성·부하 검증. 게스트 생성 2초 목표는 여전히 미실측이다.
- 보안 검토. 세션·CSRF 방식은 일반적 구성을 따랐을 뿐 위협 모델링을 하지 않았다.
- OpenAPI·클라이언트 SDK 생성.
