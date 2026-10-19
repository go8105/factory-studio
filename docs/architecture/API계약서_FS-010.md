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
| 401 | `INVALID_CREDENTIALS` | 회원 로그인 아이디·비밀번호 불일치(어느 쪽이 틀렸는지는 알리지 않음) |
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
| POST | `/guest-sessions` | P-01 | 게스트 공간 생성 + 세대 복사. 본문 `{nickname}` 필수(공백 제거 후 2~20자, 없으면 400 `fields.nickname`) — FS-027 |
| POST | `/sessions` | P-01 | 로그인 |
| DELETE | `/sessions/current` | — | 로그아웃 |
| GET | `/sessions/current` | 전역 | 사용자·공간·역할·만료 |
| GET | `/workspace` | P-02 P-06 | 공간 정보 |
| GET | `/workspace/modules` | P-02 | 앱 사용 여부 |
| PATCH | `/workspace/modules/{key}` | P-06 | 앱 on/off |
| POST | `/workspace/generations` | P-06 | 예시 데이터 초기화 |
| GET | `/admin/job-runs` | P-07 | ADMIN만 |
| GET | `/admin/audit-events` | P-07 | ADMIN만 |
| GET | `/admin/guest-visits` | P-07 | ADMIN만. 게스트 접속(`guest_session.created`) — `{id, createdAt, nickname(90일 뒤 null), workspaceNo, retired}` — FS-027 |

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
- `/energy-factors` (FS-018k): `factorKind`·`energySourceId` 필터. `factorUnit`은 서버가 유형(`TOE/`·`tCO2eq/`)과 에너지원 계측 단위로 정한다. 에너지원·유형은 수정 불가(PATCH는 연도·계수·출처). UTILITY 에너지원 400, 에너지원·유형·연도 중복 400 `fields.effectiveYear`, 계수 > 0. 참조 테이블이 없어 삭제는 자유이며 삭제된 연도는 계산에서 `FACTOR_MISSING`.
- `/meters` (FS-018l): `GET /meters`는 계측기 전체와 `channels`를 함께 준다(F-02·F-12 공용, 페이지 없음). 사업장은 공간에서 도출, 설비는 같은 공간·상위 계측기는 같은 사업장만, 부모 순환 400. 채널에 계측값·배분이 있으면 계측기의 공간·설비·상위 계측기 변경 409 `METER_IN_USE`, 채널의 에너지원·측정 종류·단위 변경 409 `CHANNEL_IN_USE`(+`fields`·`references`). 누적 채널 단위는 에너지원 계측 단위와 같아야 한다. 삭제는 409 `REFERENCED_BY_OTHERS`(하위 계측기·채널 / 계측값·배분 건수).
- `/sites` · `/locations` (FS-018m): 시간대는 IANA 이름만. 계측값·배분·생산 실적이 있는 사업장의 시간대 변경 409 `TIMEZONE_IN_USE`. 공간의 사업장은 수정 불가, 상위 공간은 같은 사업장·순환 금지. `GET /locations`에 `siteId`·`parentLocationId` 추가. 삭제 409 `REFERENCED_BY_OTHERS`(사업장 ← 공간·계측기·목표 / 공간 ← 하위 공간·설비·계측기).
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

### FS-019a 기준정보 구현 계약

- 공통: 세션에서 S를 결정하며 읽기는 `read_scope`, 쓰기는 `write_scope`의 공간 잠금·세대 재확인 뒤 실행한다. `X-CSRF-Token`·`Idempotency-Key` 필수, 성공 영수증 재전송 동일 결과. 다른 공간/이전 세대 ID는 404. ERP 사용 중단은 409 `MODULE_DISABLED`.
- 목록은 `data` + `page(offset,limit,total)`(기본 50, 최대 200). `sort=응답필드:asc|desc`, 결정적인 id 보조 정렬. 입력·페이지 오류는 400 `VALIDATION_FAILED` + `details.fields`.

| 경로 | 메서드 | 입력/응답 주요 필드 |
|---|---|---|
| `/partners`, `/partners/{id}` | GET·POST / GET·PATCH·DELETE | partnerCode, partnerName, partnerKind(CUSTOMER/SUPPLIER), paymentTermDays(nullable, 0 이상), isActive |
| `/items`, `/items/{id}` | GET·POST / GET·PATCH·DELETE | itemCode, name, baseUnit(EA/BOX/KG/M/L/SET), itemType(finished/semi_finished/raw/auxiliary), taxCategory(TAXABLE/ZERO/EXEMPT), isActive |
| `/items/{itemId}/conversions`, `…/{id}` | GET·POST / GET·PATCH·DELETE | fromUnit, factor(양수 문자열, 소수 6자리). itemId·toUnit은 서버 결정, 응답에 포함 |
| `/partner-prices`, `/partner-prices/{id}` | GET·POST / GET·PATCH·DELETE | partnerId, itemId, priceKind(기본 SALE), unitPrice(0 이상 문자열, 소수 4자리), currency(대문자 3자리, 기본 KRW), effectiveFrom, effectiveTo(nullable), isActive |
| `/accounts`, `/accounts/{id}` | GET | accountCode, accountName |
| `/posting-rules`, `/posting-rules/{id}` | GET | transactionKind, lineNo, entrySide, accountId, accountCode, amountBasis |

- POST 201, PATCH 200, DELETE 204. 계정·분개규칙에는 쓰기 라우트가 없다. `id`, `createdAt`은 응답 전용이다.
- 거래처·품목·단가 목록은 `active` 필터. 단가 목록은 `partnerId`·`itemId` 필터도 제공한다.
- 코드 중복, 환산 전 단위 중복, 명시적 null 금지 필드, 빈 PATCH는 400 + 필드 오류다. PATCH에서 결제조건·종료월만 null로 비울 수 있다.
- 환산 후 단위는 품목 기준 단위다. fromUnit은 기준 단위와 달라야 한다. 단위환산·전표 등이 참조 중이면 품목 기준 단위 변경은 409 `PRECONDITION_NOT_MET`, reason `UNIT_IN_USE` + references 건수.
- 참조 중인 거래처·품목 삭제는 409 `REFERENCED_BY_OTHERS`, 같은 reason + references(테이블·표시명·건수). 단위환산도 품목의 참조처로 센다. 사용 여부 변경은 별도 기능이다.
- 단가 적용 구간은 YYYY-MM, **양 끝 월 포함**, 종료월 null은 무기한. 종료월 < 시작월은 400. 같은 거래처·품목의 구간은 **단가 구분·통화·사용 여부와 무관하게** 겹침을 거부한다(화면 설계 §8 기준). 생성·수정 모두 409 `PERIOD_OVERLAP`, reason·references·conflicts(겹치는 id와 구간) 제공. 수정 대상 자신은 제외한다.
- 단가/환산 계수는 Decimal 문자열을 그대로 보존한다. 전표에 복사한 단가는 마스터 수정으로 소급 변경하지 않는다. 견적 자동 선택은 후속 FS-019b 범위다.
- E-16은 MES 품목과 독립임을 표시한다. E-18은 7계정·10규칙의 매핑 사유를 안내하는 읽기 전용이다.

### 영업 (FS-019b): 견적·판매계획·수주

- 목록은 페이지 없이 전체(`data`만)이며 명세(`lines`)를 포함한다. 쓰기 공통 규칙은 FS-019a와 같다(CSRF·멱등, 400 `fields`, 409 `PRECONDITION_NOT_MET` + `reason`).
- `/quotations`: **최신 개정본만** 반환(`isLatest`·`revisionCount`·`salesOrderId`는 조회 시 파생). `GET /quotations/{id}/revisions`는 같은 견적번호의 전 차수(`lines`·`history`). POST(1차 draft + 이력), PATCH·`PUT /{id}/lines`는 최신 draft만(409 `QUOTATION_LOCKED`/`NOT_LATEST_REVISION`). `POST /{id}/status` `{status, reason}`: draft→confirmed→sent→accepted|rejected, 종결 전 cancelled(거절·취소 사유 필수, 빈 견적 확정 409 `EMPTY_QUOTATION`, 그 외 `INVALID_TRANSITION`). `POST /{id}/revise`(confirmed·sent·rejected, 라인 복사한 다음 차수 draft, 아니면 `REVISE_NOT_ALLOWED`). `POST /{id}/convert` `{orderNo, orderedOn, dueOn}`: sent·accepted만, 할인 반영 단가로 수주 생성, sent면 accepted로(`ALREADY_CONVERTED`). 삭제 없음(상태 이력 불변).
- 라인 `unitPrice`를 비우면 기준일(견적일·수주일)이 속한 달의 사용 중 SALE 거래처 단가를 복사한다. 없으면 400 `fields.lines`. 응답 `masterPrice`(현재 단가표 값)·`priceSource`(`partner_price`/`manual`, 비교로 파생)·`amount`(수량 × 단가 × (100 − 할인율)%, 원 반올림)·`totalAmount`.
- `/sales-plans`: POST·PATCH·`PUT /{id}/lines`(품목당 1행, 단위 = 품목 기준 단위)·`POST /{id}/confirm`(`confirmedAt`, 빈 계획 409 `EMPTY_PLAN`)·DELETE는 draft만(409 `PLAN_CONFIRMED`).
- `/sales-orders`: POST는 머리글 + `lines` 함께. 라인 `instructedQty`(취소 안 된 출하지시)·`shippedQty`(확정 출하), `shipmentOrderCount`, 근거 견적 `quoteNo`·`quoteRevisionNo`. PATCH(`lines`는 통째 교체)·`POST /{id}/cancel`은 open이고 유효 출하지시가 없을 때만(409 `ORDER_LOCKED`). 견적 전환 수주는 거래처 변경 400.
- 고객 거래처만(CUSTOMER·사용 중), 사용 중 품목만 선택할 수 있다. 같은 공간의 쓰기는 `write_scope` 공간 잠금으로 직렬화된다.

### 출하지시·출하 (FS-019c): TX-07·TX-08(+TX-09)

- `/shipment-orders`(목록에 `lines`·`orderNo`·`partnerId`·`shipmentNo`): POST `{shipOrderNo, salesOrderId, orderedOn, lines:[{salesOrderLineId, orderQty}]}`. 수주 → 수주 명세 잠금 뒤 Σ(취소 안 된 지시) + 신규 ≤ 수주수량, 초과 409 `ORDER_QTY_EXCEEDED`(+`lineNo`·`remainingQty`). 접수·출하 중 수주만(`ORDER_NOT_SHIPPABLE`). `POST /{id}/cancel` `{reason}`은 미출하만(`SHIPMENT_ORDER_NOT_OPEN`).
- `/shipments`(목록에 `lines`·매출 `salesRecordId`·`supplyAmount`·`taxAmount`·`totalAmount`): POST `{shipmentNo, shipmentOrderId, lines:[{shipmentOrderLineId, packingNo}]}`. 지시당 1건, 지시 전 명세를 지시 수량 그대로(서버 산출) 출하. 등록 = 확정(`status=confirmed`, 작성 단계 없음). 패킹번호는 선택 수기 코드, ERP 안 중복은 409 `PACKING_ALREADY_SHIPPED`(+`packingNos`).
- 출하 확정 트랜잭션 안에서 매출 1건 + 채권 1건 생성(TX-09, `erp/revenue.py`). 세액: 품목 과세구분 TAXABLE 10%·ZERO/EXEMPT 0%, 명세별 공급가액·세액 1원 사사오입 후 합산. 채권 원금 = 합계, 만기 = 인식일(Asia/Seoul) + 결제일수(조건 없으면 NULL). 실패 시 출하 전체 롤백.
- 수주 상태는 같은 트랜잭션에서 재계산: 유효 지시 없음 open / 있음 shipping / 전 명세 출하 완료 closed.

### 매출·세금계산서 (FS-019d)

- `GET /sales-records`: 공급가액·세액·합계·`recognizedAt`, `receivableId`·`dueDate`·`appliedAmount`(Σ소명), `taxInvoiceId`·`taxInvoiceStatus`, **`cancelBlockedReason`**(서버 파생: `ALREADY_CANCELLED` > `INVOICE_ISSUED` > `RECEIPT_APPLIED`, 없으면 null — 화면 툴팁용).
- `POST /sales-records/{id}/cancel` `{reason}`: 매출 → 세금계산서 → 채권 잠금 뒤 위 조건 재확인, 막히면 409 + 같은 `reason`. 발급대기 계산서는 같은 트랜잭션에서 물리 삭제, `cancelled_at`·`cancel_reason` 기록. 채권 원금은 유지(유효 집계 제외), 출하 물류는 그대로.
- `/tax-invoices`: POST `{salesRecordId}` → pending(매출당 1건 `INVOICE_EXISTS`, 취소 매출 `SALES_CANCELLED`, **0원 매출 `ZERO_AMOUNT_SALE` — E-G07 결정**). `POST /{id}/issue` `{approvalNo, issuedOn}`: pending만(`ALREADY_ISSUED`), 발급일 ≥ 매출일(KST) 400 `fields.issuedOn`, 승인번호 중복 400 `fields.approvalNo`. issued는 불변.

### 매출채권·수금·소명 (FS-019e)

- `GET /receivables?partnerId=&status=OPEN|PARTIAL|CLOSED`: **유효 채권만**(취소 매출 제외). `amount`·`appliedAmount`·`balance`·`status`는 조회 파생(원금 0은 CLOSED), `dueDate`(null = 미설정), `applications`(수금번호·금액·시각). 구현 `erp/receipts.py`의 `open_items(RECEIVABLE)` 하나 — 019h 대시보드도 재사용한다.
- `/receipts`(목록에 `appliedAmount`·`unappliedAmount`·`applications`): POST·PATCH·DELETE는 draft만(409 `RECEIPT_CONFIRMED`), `POST /{id}/confirm`.
- `POST /receipts/{id}/applications` `{lines:[{receivableId, amount}]}`: 확정 수금만(`RECEIPT_NOT_CONFIRMED`). 매출 → 채권(id 오름차순) → 수금 잠금 뒤 최신 합계로 채권·수금 양쪽 한도, 초과 시 전체 롤백 409 `LIMIT_EXCEEDED` + `limit`(`RECEIVABLE`·`RECEIPT`)·`receivableId`/`shipmentNo` 또는 `receiptId`·`availableAmount`. 같은 거래처가 아니면 400, 취소 매출 채권 409 `SALES_CANCELLED`. `apply_key`는 수금·요청 키·행 번호의 해시.
- `DELETE /receipts/{id}/applications/{applyId}`: 채권 → 수금 → 소명 잠금, 물리 삭제 + `core.audit_event`(`erp.receipt_apply.delete`, summary에 세대·양쪽 부모·소명 id·apply_key·금액·통화·사유) 같은 트랜잭션. 응답은 갱신된 수금.
- `GET /receipts/{id}/fifo-suggestion`: 미소명 잔여를 매출일이 오래된 유효 채권부터 채운 `[{receivableId, amount}]`. 저장하지 않는다.

### 매입·채무·지급 (FS-019f)

- `/purchase-invoices`(목록에 `lines`·`payableId`·`appliedAmount`·`cancelBlockedReason`): POST·PATCH(`dueDate` null 허용)·`PUT /{id}/lines` `{lines:[{itemId, quantity, unit, unitPrice}]}`·DELETE는 draft만(409 `INVOICE_LOCKED`). 원재료(raw) 품목만, 단위는 기준 단위 또는 단위환산 원 단위(400 `fields.lines`). 명세 공급가액·세액은 서버가 `revenue.line_amounts`로 계산, 머리글 합계 = 명세 합계.
- `POST /{id}/confirm`: SUPPLIER·명세 1개 이상(`EMPTY_INVOICE`), 확정 순간 과세구분으로 재계산, 만기 = 입력 우선 → 매입일 + 결제일수 → NULL, 같은 트랜잭션에서 채무 1건. `POST /{id}/cancel` `{reason}`: draft는 바로, 확정은 지급 소명 0행만(`PAYMENT_APPLIED`, `ALREADY_CANCELLED`). 매입(6) → 채무(7) 잠금.
- `/payables`·`/payments`는 `/receivables`·`/receipts`와 **같은 규칙·같은 경로 구조**(`receipts.Side` 한 벌): 키만 `payableId`·`paymentId`·`paymentNo`·`paidOn`·`invoiceNo`·`invoiceDate`, 409 `PAYMENT_CONFIRMED`·`PAYMENT_NOT_CONFIRMED`·`PURCHASE_CANCELLED`, `LIMIT_EXCEEDED`의 `limit`은 `PAYABLE`·`PAYMENT`. 소명 취소 감사 action `erp.payment_apply.delete`.

### 대시보드 (FS-019h)

- `GET /dashboard?month=YYYY-MM`(기본: 업무 기준일의 달, 잘못된 월 400): `salesSupply`·`salesTotal`·`salesCount`(그 달 KST 인식 유효 매출), `receivableBalance`·`payableBalance`(`receipts.open_items` 잔액 합, 월 무관), `orderBacklog`(취소 안 된 수주 (수주 − 출하) × 단가, 원 반올림), `monthlySales`(조회 월까지 6개월 공급가액), `topReceivables`(거래처별 잔액 상위 5), `receivableByDue`(`overdue`·`notDue`·`unset` — 만기 NULL은 연체로 분류하지 않음), `planVsActual`(그 달 확정 판매계획 수량 vs 유효 매출 출하 수량, 품목별), `pending`(`uninvoicedSales`·`unappliedReceipts`). 저장 없음, 구현 `erp/dashboard.py`.

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
- (FS-019g 구현) 응답 `{kind, id, doc, lines:[{lineNo, entrySide, accountCode, accountName, amountBasis, amount}], debitTotal, creditTotal, balanced, unapplied}`. 금액 기준 TOTAL·SUPPLY·TAX는 매출·매입 금액, APPLY는 소명 1행 금액. SALES·PURCHASE는 `sourceId`, RECEIPT·PAYMENT는 `applyId` 필수(없으면 400 `fields`). 취소 매출·작성/취소 매입은 409 `NOT_POSTABLE`. `unapplied`는 수금·지급의 미소명 잔여(매출·매입은 null). 구현 `erp/journal.py`.

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

### 기준정보 (FS-020a)

- `/sites` `/locations` `/equipments` `/items` `/processes`: 목록은 페이지 없이 전체(`data`만). 삭제 409 `REFERENCED_BY_OTHERS` + 건수.
- 공간의 사업장 수정 불가, 상위 공간 같은 사업장·순환 금지. 품목 기준 단위는 단위 환산·작업지시가 있으면 409 `UNIT_IN_USE`.
- `/items` 목록에 `conversions`, `/items/{id}/conversions` 등록·수정·삭제(결과 단위 = 기준 단위, 서버 결정).
- `/processes` 목록·응답에 `equipmentIds`. 본문 `equipmentIds`는 허용 설비 목록 전체 교체.

### 공정 경로·BOM 버전 (FS-020b)

- `/routes` · `/boms`: 목록에 `steps`/`lines`. 생성은 초안, `POST /{id}/revise`(BOM은 `bomCode` 필수)·`/publish`·`/retire`, `PUT /routes/{id}/steps` `{processIds}`·`PUT /boms/{id}/lines` `{lines}`는 초안만 통째 교체, `DELETE`는 초안만.
- 409 `reason`: `VERSION_LOCKED`·`IS_DRAFT`·`DRAFT_EXISTS`·`INVALID_TRANSITION`·`EMPTY_VERSION`. BOM 자재 오류는 400 `fields.lines`.

### 생산계획·작업지시 (FS-020c)

- `/production-plans`: 라인에 `allocatedQty`·`remainingQty`. `PUT /{id}/lines` 초안 통째 교체, `POST /{id}/confirm`. 확정 후 409 `PLAN_CONFIRMED`, 빈 계획 확정 409 `EMPTY_PLAN`.
- `/work-orders`: 확정 계획 라인에서 생성(번호 자동), 배정 초과 409 `PLAN_QTY_EXCEEDED`(+잔여). `release`는 LOT을 같은 트랜잭션에서 생성, 경로·BOM 게시 재확인 409 `VERSION_NOT_PUBLISHED`. 발행 후 변경 409 `ORDER_RELEASED`.
- `POST /work-orders/{id}/lot`(추가): 발행됐지만 LOT이 없는 지시의 LOT 생성. 그 외 409 `LOT_NOT_ALLOWED`.

### 공정 실행 (FS-020d)

- 시작은 `POST /lots/{id}/executions` `{routeStepId, equipmentId}`, 완료는 `POST /executions/{id}/result`(실적 확정 = 완료). 결과 없는 종료는 스키마상 없으므로 `/finish`는 두지 않는다.
- 409 `reason`: `LOT_NOT_STARTABLE`·`STEP_RUNNING`·`OUT_OF_ORDER`·`PROCESS_INACTIVE`·`EQUIPMENT_BUSY`(+`lotNo`)·`ALREADY_COMPLETED`. 투입은 서버가 정하고 양품 + 불량 = 투입.

### 패킹·완제품 입고 (FS-020f)

- `/packable-lots`, `/packing-units`(`members`·`childIds`·`displayStatus`), `PUT /packing-units/{id}/members`(0이면 빼기), `/close`, `PUT /packing-units/{id}/parent`, `/finished-goods-receipts`.
- 409 `reason`: `EXCEEDS_GOOD_QTY`(+`availableQty`)·`NOT_A_BOX`·`MIXED_ITEM`·`UNIT_CLOSED`·`UNIT_EMPTY`·`BOX_NOT_CLOSED`·`BOX_OPEN`·`NOT_A_PALLET`·`UNIT_OPEN`·`ALREADY_RECEIVED`·`UNIT_NOT_EMPTY`. 입고 시 하위 BOX는 closed 유지, `displayStatus`는 부모 상태.

### LOT 상세가 핵심 응답이다

`GET /lots/{id}`는 추적성을 보여주는 화면(M-04)을 받친다. 공정 실행 · 투입 자재 · 실적을 **한 번에 반환한다.** 화면이 세 번 호출하게 두지 않는다.

### 자재 투입

`GET /bom-requirement`가 BOM 기준 소요량(로스율 반영)을 반환하고 화면이 기본값으로 채운다.

- **BOM이 없는 지시면 빈 배열을 반환한다.** 404가 아니다. BOM 없는 지시는 정상 경로다(FS-008b D-2).
- 투입은 기록일 뿐 재고를 차감하지 않는다. 응답에 그 사실을 표시하는 플래그를 두지 않는다 — **화면의 고정 안내로 처리한다.**

- (FS-020e) 제안량 = 기준 소요(LOT 계획 × 소요량 × (1+손실률)) − 같은 LOT 누적 투입. 투입은 실적 확정 전만(409 `RESULT_CONFIRMED`), 같은 실행·자재·자재 LOT(NULL 포함) 중복 409 `DUPLICATE_ISSUE`, `DELETE /executions/{id}/material-issues/{issueId}`로 정정. `GET /results`는 확정 실적 목록.

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

---

## 14. QMS API (`/api/v1/qms`, FS-023b)

설계: [QMS 모듈 설계서](../modules/qms/QMS_모듈설계_FS-023.md) 8장 · 결정: [FS-023](../plan/QMS도입_교차조회_결정_FS-023.md). 공통 규약(3장)을 그대로 따른다 — 세션에서 S 결정, 쓰기는 `write_scope` 공간 잠금 뒤, 변경 요청은 `X-CSRF-Token`·`Idempotency-Key`, QMS 사용 중단은 409 `MODULE_DISABLED`.

| 메서드·경로 | 요약 | 주요 오류 `reason` |
|---|---|---|
| `GET /dashboard?month=` | 검사 수·합격률(없으면 null)·활성 보류·검사 대기(MES 꺼짐이면 null)·일자별·불량 유형 상위 5·최근 불합격·활성 보류 목록. 월 생략 시 확정 검사가 있는 마지막 월 | — |
| `GET/POST /defect-types` · `PATCH/DELETE /defect-types/{id}` | 코드는 등록 뒤 바꾸지 않는다 | 400 `fields.code`(중복), 409 `REFERENCED_BY_OTHERS`(참조처별 건수) |
| `GET /inspection-specs?itemCode=&status=` · `POST` · `GET/PATCH/DELETE /{id}` | PATCH는 note와 **항목 전체 교체**(draft만) | 409 `DRAFT_EXISTS`·`PUBLISHED_IMMUTABLE`, 400 `fields.items.<i>.<field>` |
| `POST /inspection-specs/{id}/publish·retire·revise` | TX-Q1: 게시 시 같은 품목의 기존 게시 → retired | 409 `NO_ITEMS`·`NOT_PUBLISHED`·`ALREADY_DRAFT`·`DRAFT_EXISTS` |
| `GET /lookups/mes-lots?pending=true` | MES 정상 완료 LOT(최종 양품 > 0) + QMS 상태(`pending`/`drafting`/`inspected`, `hasSpec`) | 409 `SOURCE_MODULE_DISABLED` |
| `GET /lookups/mes-items` | MES 사용 중 완제품 품목 | 409 `SOURCE_MODULE_DISABLED` |
| `GET /inspections?status=&result=&month=&lotNo=` · `POST` · `GET/PATCH/DELETE /{id}` | POST `{source:'MES', lotNo, sampleQty}` 또는 `{source:'MANUAL', …, itemCode, itemName, lotQty, unit}`. 만들 때 기준 항목마다 빈 측정값 행을 만든다. PATCH `values[]`는 항목 판정을 서버가 계산 | 409 `LOT_NOT_INSPECTABLE`·`NO_PUBLISHED_SPEC`·`DRAFT_EXISTS`·`CONFIRMED_IMMUTABLE`·`SOURCE_MODULE_DISABLED`, 400 `fields.sampleQty`·`fields.values.<seq>` |
| `POST /inspections/{id}/confirm` | TX-Q2: 필수 누락·불합격 불량 유형 누락은 400. FAIL이면 같은 트랜잭션에서 보류(`ON CONFLICT … WHERE status='held' DO NOTHING`) | 400 `fields.values.<seq>`·`fields.values.<seq>.defectTypeId` |
| `POST /inspections/{id}/reinspect` | 같은 LOT 새 draft(현재 게시 기준, `reinspectionOfId`) | 409 `NOT_CONFIRMED`·`DRAFT_EXISTS`·`NO_PUBLISHED_SPEC` |
| `GET /holds?status=` · `GET /holds/{id}` | 상세에 원인 불합격 항목·보류 이후 확정 검사(해제 후보) | — |
| `POST /holds/{id}/release` | TX-Q3 `{disposition, releaseInspectionId?, reason?}` | 400 `fields.reason`·`fields.releaseInspectionId`, 409 `RELEASE_NOT_ALLOWED`·`ALREADY_RELEASED` |

**MES 응답 추가(읽기만, D10):** `GET /api/v1/mes/lots`·`/packable-lots`에 `qualityHold`(true/false, QMS 꺼짐이면 null), `GET /api/v1/mes/lots/{id}`에 `qualityHold`·`qualityResult`(PASS/FAIL/null).

**조회 인터페이스(코드, HTTP 아님):** `fs/mes/interface.py` — `inspectable_lots`·`lot_snapshot`·`items`·`enabled`; `fs/qms/interface.py` — `held_lot_nos`·`latest_results`. 제공 모듈이 꺼져 있으면 `None`. 격리 검사 R6이 다른 import를 막는다.

## 15. WMS API (`/api/v1/wms`, FS-024b)

설계: [WMS 모듈 설계서](../modules/wms/WMS_모듈설계_FS-024.md) 8장 · 결정: [FS-024](../plan/WMS도입_재고원장_결정_FS-024.md). 공통 규약(3장)을 그대로 따른다 — 세션에서 S 결정, 쓰기는 `write_scope` 공간 잠금 뒤, 변경 요청은 `X-CSRF-Token`·`Idempotency-Key`, WMS 사용 중단은 409 `MODULE_DISABLED`. 수량은 문자열(소수 3자리), 원장 단위는 품목 기본 단위.

| 메서드·경로 | 요약 | 주요 오류 `reason` |
|---|---|---|
| `GET /dashboard?month=` | 원자재 품목 수·완제품 LOT 수·음수 재고 수·미반영 원천 수(원천별, 꺼진 원천은 null)·품목별 현재고·가용·월 입출고(이동 제외). 월 생략 시 확정 전표가 있는 마지막 월 | — |
| `GET/POST /warehouses` · `PATCH /warehouses/{id}` | 용도(`RAW`/`FG`)별 활성 창고 1개 | 400 `fields.code`·`fields.purpose`·`fields.isActive` |
| `GET/POST /warehouses/{id}/locations` · `PATCH/DELETE /locations/{id}` | 창고의 첫 위치는 기본 위치. 기본 지정은 다른 위치를 기본으로 바꿔서만 푼다 | 400 `fields.isDefault`·`fields.isActive`, 409 `DEFAULT_LOCATION`·`REFERENCED_BY_OTHERS` |
| `GET/POST /items` · `PATCH /items/{id}` | 분류 `RAW`/`FG`(FG만 LOT 추적). 쓰인 품목은 사용 안 함으로 | 400 `fields.itemCode` |
| `GET /lookups/mes-items` · `POST /items/import {itemCodes}` | MES 원자재·완제품 중 WMS에 없는 것 → 스냅샷으로 등록 | 409 `SOURCE_MODULE_DISABLED`, 400 `fields.itemCodes` |
| `POST /items/{id}/conversions {fromUnit, factor}` · `DELETE /items/{id}/conversions/{cid}` | 1 fromUnit = factor 기본 단위 | 400 `fields.fromUnit`·`fields.factor` |
| `GET /stock?itemCode=&warehouseId=&lotNo=&negativeOnly=&unassignedOnly=` | `{rows:[창고·위치·품목·LOT·onHand·negative·lotUnassigned], totals:[FG 품목 onHand·openShipmentQty·available]}` — 0인 행 숨김, ERP 꺼짐이면 available null | — |
| `GET /moves?itemCode=&lotNo=&warehouseId=&type=&from=&to=` | 확정 이동 줄(전표·원천 번호). `itemCode`를 주면 품목·LOT별 누계 `running` | — |
| `GET /sources?kind=MES_RECEIPT\|MES_ISSUE\|ERP_SHIPMENT\|ERP_PURCHASE&state=pending\|synced\|all` | 원천 행 `state`: `pending`·`blocked`(사유 `ITEM_NOT_REGISTERED`·`UNIT_CONVERSION_MISSING`·`NO_WAREHOUSE`)·`synced`·`cancel_pending`·`reversed`·`cancelled`. 원천 솔루션 꺼짐이면 `{disabled:true, sourceModule}` | — |
| `POST /sources/sync {kind, sourceKeys[]}` | TX-W1·W3. 원천마다 따로 커밋, 결과 `{results:[{sourceKey, state, documentId?, reason?}], synced, blocked}`. 같은 원천은 기존 전표를 돌려준다(멱등) | 409 `SOURCE_MODULE_DISABLED`; 원천별 `reason.code` `SOURCE_NOT_FOUND`·`SOURCE_CANCELLED` 등 |
| `GET /documents?type=&status=&month=` · `GET /documents/{id}` | 전표·이동 줄(`moves`) | — |
| `POST /documents` · `PATCH/DELETE /documents/{id}` | 기초·조정·이동 초안. `lines[]` 전체 교체. 이동 줄 `{itemId, lotNo, fromLocationId, toLocationId, qty}` → 저장 시 −/+ 두 줄 | 400 `fields.lines.<i>.<field>`·`fields.reasonCode`·`fields.note`, 409 `POSTED_IMMUTABLE` |
| `POST /documents/{id}/post` | TX-W2. 잔량 확인 없음(음수 허용 D15) — 응답 `negative[]`에 음수가 된 품목·위치·LOT | 409 `NO_LINES`·`TRANSFER_UNBALANCED`·`POSTED_IMMUTABLE` |

**조회 인터페이스(코드, HTTP 아님):** `fs/mes/interface.py` 추가 — `finished_goods_receipts`·`completed_material_issues`·`items(item_type=None)`; `fs/erp/interface.py`(신규) — `confirmed_shipments`·`purchase_receipts`·`open_shipment_qty`·`enabled`. MES·ERP API는 바뀌지 않는다.

## 16. BEMS API (`/api/v1/bems`, FS-025b)

설계: [BEMS 모듈 설계서](../modules/bems/BEMS_모듈설계_FS-025.md) · 결정: [FS-025](../plan/BEMS도입_공용에너지_결정_FS-025.md). 공통 규약(3장)을 그대로 따른다. BEMS 사용 중단은 409 `MODULE_DISABLED`. 시각은 KST(`+09:00`) ISO 문자열, 값은 문자열(소수). 관측·명령 시각은 시뮬레이션 시계(마지막 관측 구간 + 1시간, 이력이 없으면 업무 기준일 00:00)를 따른다.

| 메서드·경로 | 요약 | 주요 오류 `reason` |
|---|---|---|
| `GET /dashboard` | 어제·최근 7일 분해(FEMS 꺼짐이면 null), 구역별 최신 환경·설정값·공조 상태, 미해제 경보, 시뮬레이션 시계 | — |
| `GET /breakdown?granularity=day\|month&from=&to=` | 행 `{period, site, manufacturing, common, commonByUsage, residual, mismatch, missingHours}`. 잔여 = FEMS 사업장 전력 − FEMS 설비 직접 배분 − BEMS 공용. 기본 T−30~T−1 | 409 `SOURCE_MODULE_DISABLED` |
| `GET /environment?zoneId=&from=&to=` · `GET /energy?meterId=&from=&to=` | 1시간 관측(환경은 구역 설정값 포함) | — |
| `GET/POST /zones·/meters·/sensors·/hvac-units` · `PATCH /…/{id}` | 기준정보. 센서 단위는 지표에서 정한다. 구역당 지표 1개. 공조 계측기는 같은 구역의 용도 HVAC만 | 400 `fields.code`·`fields.metric`·`fields.meterId` |
| `GET /hvac-overview` · `GET /hvac-units/{id}/detail` | 상태·제어 출처·설정값·최근 명령 20건·스케줄 | 404 |
| `PUT /hvac-units/{id}/schedule {slots[]}` | 평일/주말 시간대(시작 ≤ 시 < 끝) 전체 교체. 겹치면 거부 | 400 `fields.slots.<i>` |
| `GET /commands?zoneId=&hvacUnitId=` · `POST /commands` | TX-B1. `POWER_ON`·`POWER_OFF`·`SET_MODE`·`SET_SETPOINT`. 거부도 이력으로 남긴다(201, `result=REJECTED`, `rejectReason` `OUT_OF_RANGE`·`BAND_TOO_NARROW`·`UNIT_INACTIVE`·`ALREADY_ON`·`ALREADY_OFF`·`SAME_STATE`). 수동 운전은 다음 스케줄 경계까지 유지 | 400 `fields.zoneId`·`fields.mode`·`fields.value` |
| `GET /simulation/clock` | `{next, limit, canAdvance}` — 다음 진행 구간 시작·한도(B-01·B-04 진행 버튼, FS-025b 2부) | — |
| `POST /simulation/advance {hours:1~6}` | TX-B2. 스케줄 전환 → 환경·전력 관측 → 경보 판정. 결과 `{from, to, hours, readings, switches, raised, cleared}`. 한도 업무 기준일 다음 날 00:00 | 409 `SIMULATION_LIMIT` |
| `GET /alarms?status=` · `POST /alarms/{id}/acknowledge {note}` | TX-B3. 발생 중인 경보만 확인 | 409 `NOT_RAISED` |
| `GET/POST /alarm-rules` · `PATCH /alarm-rules/{id}` | 구역·지표·비교·임계·지속 시간·등급. 같은 구역·지표·비교는 1개 | 400 `fields.comparator` |

**조회 인터페이스(코드, HTTP 아님):** `fs/fems/interface.py`(신규) — `enabled`·`site_electricity`·`manufacturing_electricity`(일별 kWh). FEMS API는 바뀌지 않는다.

## 17. SPC API (`/api/v1/spc`, FS-028b)

설계: [SPC 모듈 설계서](../modules/spc/SPC_모듈설계_FS-028.md) · 결정: [FS-028](../plan/SPC도입_관리도_결정_FS-028.md). 공통 규약(3장)을 그대로 따른다. SPC 사용 중단은 409 `MODULE_DISABLED`. 시각은 시간대가 있는 ISO 문자열, 값은 문자열(소수). 조회 기간 `from`·`to`는 날짜(KST)이고, `to`가 없으면 끝을 열어 둔다(측정 시각은 실제 시각이라 업무 기준일보다 늦을 수 있다).

| 메서드·경로 | 요약 | 주요 오류 `reason` |
|---|---|---|
| `GET /dashboard` | KPI(특성 수·미조치 이상·공정능력 판정별 수·최근 7일 부분군) + 특성 카드(최근 20점 X̄·최신 한계·Cpk). 미조치 많은 순 → Cpk 낮은 순 | — |
| `GET /lookups/items` | 특성 등록용 MES 완제품(`fs.mes.interface.items`) | 409 `SOURCE_MODULE_DISABLED` |
| `GET/POST /characteristics` · `GET/PATCH /characteristics/{id}` | 관리 특성. 품목은 MES 완제품만. 규격 하나 이상, 하한 < 상한, 목표값은 규격 안. 부분군이 있으면 규격·단위 변경 거부(이름·자릿수·사용은 가능) | 400 `fields.itemCode`·`fields.usl` · 409 `DUPLICATE`·`CHARACTERISTIC_IN_USE` |
| `GET /characteristics/{id}/chart?from=&to=` | 부분군 점(X̄·R·상태·LOT·설비·판정 버전·이상 표시) + 한계 버전 목록 | — |
| `GET /characteristics/{id}/capability?from=&to=` | μ·σ̂(R̄/d2)·Cp·Cpk·판정(`CAPABLE`/`MARGINAL`/`INCAPABLE`)·히스토그램 10칸·미조치 이상 수. 유효 부분군 20개 미만이면 `insufficient: true`만 | — |
| `GET /characteristics/{id}/limits` · `GET …/limits/preview?basisFrom=&basisTo=` · `POST …/limits {basisFrom, basisTo, reason}` | TX-S2. 기준 구간 유효 부분군 20개 이상으로 X̄·R 한계(n=5 상수) 게시. **적용 시작 = 게시 때 마지막 유효 부분군 측정 시각**(벽시계와 무관). 게시 시각은 `publishedAt` | 400 `fields.basisFrom` · 409 `NO_NEW_SUBGROUP` |
| `GET /runs?characteristicId=` | MES 공정 실행(해당 품목·공정, 최근 30일, `fs.mes.interface.operation_runs`) + 실행별 기록된 부분군 수 | 409 `SOURCE_MODULE_DISABLED` |
| `POST /subgroups {characteristicId, lotNo, measuredAt, values[5], note?}` | TX-S1. 측정 시각은 공정 실행 기간 안이고 그 특성의 마지막 유효 부분군보다 늦어야 한다. 기록과 함께 규칙 1~3 판정 → 결과에 `signals[]` | 400 `fields.measuredAt`·`fields.lotNo`·`fields.values.<n>` · 409 `SOURCE_MODULE_DISABLED`·`CHARACTERISTIC_INACTIVE` |
| `GET /subgroups?characteristicId=&lotNo=&status=` · `POST /subgroups/{id}/void {reason}` | TX-S4. 무효 처리하면 그 부분군의 이상 기록도 무효(`voidedSignals`). 뒤 부분군 판정은 다시 계산하지 않는다 | 409 `NOT_VALID` |
| `GET /signals?status=&characteristicId=` · `POST /signals/{id}/resolve {causeCategory, action}` | TX-S3. 미조치만 조치 완료. 원인 `MACHINE`·`MATERIAL`·`MAN`·`METHOD`·`MEASUREMENT`·`ENVIRONMENT` | 409 `NOT_OPEN` |

**조회 인터페이스(코드, HTTP 아님):** `fs/spc/interface.py`(신규) — `enabled`·`open_signal_lot_nos(lot_nos)`(미조치 이상 LOT). `fs/mes/interface.py`에 `operation_runs(date_from, date_to)` 추가. QMS `GET /lookups/mes-lots`·`GET /inspections` 행에 `spcSignal`(true/false, SPC 꺼짐이면 null)이 붙는다 — QMS 판정·보류는 바뀌지 않는다(D44).

## 18. 런처 평가 API (`/api/v1/core/reviews`, FS-040)

결정: [FS-040](../plan/런처평가_한줄평_FS-040.md). 회원·게스트 세션 모두 가능. 공간을 넘는 집계는 이 API만 한다(평가 행에는 업무 데이터가 없다).

| 메서드·경로 | 요약 | 주요 오류 |
|---|---|---|
| `GET /reviews/summary` | `[{moduleKey, average(소수 1자리), count, reviewed}]`. 평가 0건인 솔루션은 빠진다 | — |
| `GET /reviews?moduleKey=` | 최근 5건 `[{nickname, rating, comment, createdAt}]` | 400 `fields.moduleKey` |
| `POST /reviews {moduleKey, rating 1~5, comment 2~100자, nickname?}` | CSRF·Idempotency-Key. 회원은 표시 이름(앞 20자)을 쓰고 `nickname`은 무시, 게스트는 별칭 2~20자 필수. 201 | 400 `fields.comment`·`fields.nickname`·`fields.moduleKey` · 409 `ALREADY_REVIEWED`(같은 계정·같은 게스트 공간) · 409 `NICKNAME_TAKEN`(같은 솔루션에 같은 게스트 별칭) |


## 19. GW API (`/api/v1/gw`, FS-030b)

[GW 모듈 설계](../modules/gw/GW_모듈설계_FS-030.md) §6~7을 구현한다. 공간·세대는 인증에서 결정하며 변경은 CSRF·Idempotency-Key 필수. 기존 행 변경은 expectedVersion, 문서·게시글은 actingPersonId가 필요하다. ID/큰 순번은 문자열, 금액은 Decimal 문자열이다. 합성 역할은 실제 인증 권한이 아니다.

| 메서드·경로 | 의미 |
|---|---|
| `GET /dashboard?personId=` | 내 초안/진행/종결·현재 단계 대기·최근 기록, 금액 통화 합산 없음 |
| `GET/POST /people`, `GET/PATCH /people/{id}` | 합성 담당자, 마지막 게시판 운영·사용 중 역할 비활성 방지 |
| `GET/POST /routes`, `GET/PATCH /routes/{id}` | 활성 담당자 1~3명, 연속·중복 금지. 기존 문서에 템플릿 변경 자동 반영 없음 |
| `GET /sources`, `GET /sources/PURCHASE_INVOICE/{no}` | ERP 코드/의미 값 스냅샷. 꺼짐 `{enabled:false}`, 없음 상세404 |
| `GET/POST /documents`, `GET/PATCH /documents/{id}` | 목록 box=drafts/pending/archive/all, status/kind/search/offset/limit/sort. 상세 personId에 따른 availableActions |
| `POST /documents/{id}/select-route`, `/refresh-source`, `/submit` | 초안 결재선/원문 명시 갱신, 상신 직전 원문 digest·상태 재확인 |
| `POST /documents/{id}/approve`, `/reject`, `/withdraw`, `/resubmit` | 순차 결재, 사유 필수 반려/회수, 첫 승인 후 회수 거부, 재상신은 새 초안 |
| `GET/POST /posts`, `GET/PATCH /posts/{id}` | boardKind/status/mine/personId/search/page, 초안만 편집 |
| `POST /posts/{id}/publish`, `/withdraw`, `/correct` | 게시 불변, 철회사유, 새 정정 초안·원문 보존 |
| `GET /api/v1/erp/purchase-invoices/{id}/gw-approval` | E-11 상세 읽기 배지, 진행 우선/최신 상신, 원문 변경·GW off 구분. ERP 확정·취소와 무관 |

목록 `{data:{rows,total,offset,limit}}`, limit 기본50/최대100. 모든 성공 `{data}`, 생성201/기존 대상 작업200(재상신·정정의 새 초안 반환도200). 400 VALIDATION_FAILED(details.fields), 역할·버전·상태409 PRECONDITION_NOT_MET, 422는 IDEMPOTENCY_CONFLICT 전용. 동일 성공 요청 재시도는 저장된 결과를 반환하고 이벤트를 추가하지 않는다. 업무 시각은 DB clock_timestamp; FS_TODAY를 상태 비교에 쓰지 않는다.

추가 조회 계약: `fs.erp.interface.approval_documents/approval_document/approval_source_digest`, `fs.gw.interface.enabled/approvals`. ERP→GW provider는 GW 값만 읽으며 ERP를 재호출하지 않는다. 원문 digest는 display 날짜/상태를 제외한 의미 값만 포함한다. GW가 ERP를 수정하는 경로는 없다.

## GW-READY-02 거래 판정 보완 (2026-10-19)

HTTP API·DB 스키마 변경 없음. 운영 CLI의 선택 `--classify-transactions`는 거래 상태별 집계와 `allTransactionsSettled`를 반환하며 전체 완전성을 인정하지 않는다. 비공개 격리 복원 보고에 `journalAbortedIntents`를 추가했다. 취소로 확인된 건만 새 계획에서 제외하고 기존 복원본을 변경하지 않는다. [운영 계약](../operations/GW_직원연결_역할변경기록_GW-READY-02.md).

## GW-READY-02 미확인 인수 진단 (2026-10-19)

HTTP/DB 변경 없음. `gw_identity_journal.py --review-report`는 거래 분류를 함께 실행하고 지정 지문/시각·봉투 지문별 판정·후속 점검을 새 비공개 JSON에 저장한다. 파일은 진단 전용이며 서명 증거/checkpoint 입력/권한 승인으로 소비하지 않는다. 수동 ACCEPTED 상태나 권한 해제 API를 추가하지 않았다. [운영 절차 11차](../operations/GW_직원연결_역할변경기록_GW-READY-02.md).

## GW-READY-02 암호화 기록 묶음 (2026-10-19)

HTTP/DB 변경 없음. `tools/gw_journal_bundle.py export|verify --expected-head --bundle`는 새 암호화 기록 사본 생성/독립 지문 인증만 제공한다. 0700/0600·신규 경로·완료 명세 마지막 쓰기, 원본 잠금·복사본 재인증을 적용한다. 성공0/오류1, bundleVerified와 sourceRotated/externalDurabilityConfirmed/releaseAuthorized=false를 구분한다. 키·복호화 내용을 출력하지 않는다. 원본 초기화·다중 체인 교체·독립 지문 자동 전달은 미구현이다. [운영 12차](../operations/GW_직원연결_역할변경기록_GW-READY-02.md).

## GW-READY-02 보존 접두 기록 교체 (2026-10-19)

HTTP/DB 변경 없음. 기록 reader/writer가 `.history/`+`.history.json` 보존 접두와 평면 활성 접미를 하나의 전역 번호/해시 체인으로 인증한다. 기존 ciphertext/digest/backup 기준은 유지한다. 활성10,000·전체100,000건 한도. CLI rollover는 새 보존 폴더 준비, check-switch는 원본/후속 동일지문 점검만 수행하며 환경 설정을 변경하지 않는다. 기존 백업 계획 건수 검증은 전체 한도로 확장한다. [운영 13차](../operations/GW_직원연결_역할변경기록_GW-READY-02.md).

## GW-READY-02 전달 확인 기록 (2026-10-19)

HTTP/DB 변경 없음. gw_journal_delivery.py publish/check와 bootstrap 이후 --advance를 추가했다. 재인증 사본 생성 뒤에만 별도키 HMAC/연속 순번 확인 기록을 저장한다. 선택 WITNESS 환경으로 backup/checkpoint/restore 지문을 자동 입력하며 수동 지문 충돌·오래됨·인증 실패를 거부한다. run_gw_journal_delivery.sh는 미설치 템플릿이다. 외부 내구성/운영 승인false와 전체 저장소 rollback 탐지 한계를 유지한다. [운영14차](../operations/GW_직원연결_역할변경기록_GW-READY-02.md).

## GW-READY-02 운영 준비 진단 보완 (2026-10-19)

GET 회사 operations의 기존 관리자/감사 응답에 evidenceChecks(kind/label/state/detail), evidenceIntegrityReverified=false를 추가한다. state는 CONFIG_REQUIRED/POLICY_REQUIRED/MISSING/STALE/INVALID/FAILED/PARTIAL/RECORDED_PASS다. 일반 직원 제한 응답은 유지한다. DB에서 S 범위 종류별 최신 recorded_at/id를 한 번에 조회하고 과거 통과로 fallback하지 않는다. ready=false를 유지한다. 원본 서명 재검증은 미완료이며 등록된 PASS와 운영 전환 승인을 구분한다. 새 API/테이블/마이그레이션 없음.

## GW-READY-02 원본 증거 재검증 (2026-10-19)

새 operating-evidence 등록은 허용목록/서명을 검증한 envelope를 metrics JSONB 내부 `_signedEnvelope`에 보존한다. 외부 EvidenceMetrics 입력에는 이 예약 필드를 허용하지 않는다. 조회에서 원본 서명·DB 행 필드를 재대조하고 evidenceChecks.signatureVerified 및 LEGACY_UNVERIFIED 상태를 추가했다. evidenceIntegrityReverified는3종 모두 재검증됐을 때만true이며 ready는false를 유지한다. 원본/서명/검사값은 기존 history 응답에 노출하지 않는다. 과거행 소급수정/새 DB구조/새 경로 없음. [운영16차](../operations/GW_암호화백업_격리복원_GW-READY-02.md).
