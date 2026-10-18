# 보안·운영 DB/API 계약 · GW-READY-01

2026-10-18 · **전체 설계 승인 후 GW-READY-02 구현 진행 중**. schema0.28/219표·새 revision gw_readiness를 격리 DB에 적용해 DDL 대조 오류0을 확인했다. 운영 DB·main에는 미적용이며 실제 서비스 연결 상태는 [구현 기록](../../agent/GW_실사용구현_GW-READY-02.md)을 따른다. 아래는 승인한 계약 원문이다. 상위 기준은 [통합 설계](실사용_보안운영_UI_통합설계_GW-READY-01.md). 새9표와 기존 core2표 확장을 제안한다. 승인 후 새 revision에서 명세/Excel/ERD와 함께 반영하며 현재210표를 새 표가 적용된 것으로 세지 않는다.

## 1. 공통 규칙

- 업무 범위 `S=(workspace_id,generation_id)`, bigint ID는 JSON 문자열. GW 업무 FK는 `(S,id)` 복합 참조, 삭제/변경 RESTRICT. core 사용자/인증은 기존 전역 사용자 모델을 따른다.
- core 표는 core만 참조. GW의 인증 user 식별자는 검증한 값으로 보관하되 core.app_user로 업무 FK를 추가하지 않는다. HR/Flow/ERP에 보안 표/FK를 중복하지 않는다.
- 시각은 timestamptz UTC, 화면은 한국 시간 표시. 기간 연·월·주차는 문자열, 월 단위 보관 계산은 정의한 기준일+달력 월로 수행하고30일 환산과 섞지 않는다.
- 쓰기: 회사/계정/세션/세대→명시 역할/객체 ACL→현재 버전/추가 인증→멱등 영수증→명령. 권한이 회수된 성공 응답을 재노출하지 않는다.
- 실패 횟수·잠금·코드 소비는 실제 TX로 보존한다. 예외로 전체 TX를 rollback해 실패 횟수가 지워지는 구현 금지. 오류 응답은 commit 후 밖에서 반환한다. 만료·계정 정지·세션 회수도 잠금 안에서 재확인.
- 민감 응답 `Cache-Control:no-store`, CSRF·Origin 정책, 로그 마스킹. 코드·비밀번호·TOTP seed·IdP token은 업무 receipt/감사/브라우저 영구 저장소에 넣지 않는다.
- 코드·키/서명은 검증 라이브러리 사용. 저장된 hash 비교는 상수 시간 비교, 암호화 키는 DB/백업 파일과 분리한 운영 비밀 설정에서 관리. 키 식별자는 manifest에 허용하지만 키 값은 금지.

## 2. core 제안 표5개

### core.mfa_factor

`id bigint PK`, `user_id bigint NOT NULL FK core.app_user`, `kind varchar(20) NOT NULL`(TOTP), `state varchar(12) NOT NULL`(PENDING/ACTIVE/REVOKED), `secret_ciphertext text NOT NULL`, `encryption_key_id varchar(60) NOT NULL`, `version integer NOT NULL default1`, `last_used_step bigint NULL`, `pending_expires_at timestamptz NULL`, `confirmed_at timestamptz NULL`, `revoked_at timestamptz NULL`, `created_at timestamptz NOT NULL`.

- UK(user_id,id); partial UK(user_id,kind) WHERE state=ACTIVE와 PENDING을 각각 둔다. version>0. PENDING은 만료, ACTIVE는 확인 시각, REVOKED는 회수 시각 필수.
- last_used_step은 사용한 구간보다 큰 값으로만 진행한다. 인증 확인과 갱신을 동일 잠금/TX에서 수행한다.
- 활성 TOTP 비밀 조회 API는 두지 않는다. 등록 QR/설정 키는 PENDING 발급 시에만 반환한다.

### core.authentication_challenge

`id bigint PK`, `user_id bigint NULL FK core.app_user`, `session_id bigint NULL`, `purpose varchar(24) NOT NULL`(LOGIN_MFA/STEP_UP/ENROLL/OIDC_LOGIN/OIDC_LINK/RECOVERY), `token_hash varchar(64) NOT NULL UK`, `state varchar(12) NOT NULL`(PENDING/CONSUMED/EXPIRED/LOCKED), `security_version integer NULL`, `provider_key varchar(60) NULL`, `protected_payload text NULL`, `encryption_key_id varchar(60) NULL`, `attempt_count integer NOT NULL default0`, `expires_at timestamptz NOT NULL`, `consumed_at timestamptz NULL`, `created_at timestamptz NOT NULL`.

- FK(user_id,session_id)→core.auth_session(user_id,id), 기존 session에 UK(user_id,id)를 추가한다. purpose별 필수값 CHECK. 로그인 전 OIDC는 user_id NULL 허용, STEP_UP은 user/session 필수, OIDC_LINK는 현재 사용자/세션과 최근 추가 인증 결합. payload는 nonce/PKCE 등 필요한 임시값만 암호화. 비밀번호를 넣지 않음.
- attempt_count>=0, expires_at>created_at, CONSUMED면 소비 시각 필수. 토큰은 고엔트로피 opaque 값, hash만 저장. 종류별 수명5분, ENROLL10분·운영 복구 요청15분 초기값.
- 사용/실패 증가/만료/회수는 원자적. 이미 사용한 challenge로 새 세션을 다시 발급하지 않음. 단순 로그인 재시도에 업무 권한이 붙지 않음.

### core.recovery_code

`id bigint PK`, `user_id bigint NOT NULL`, `factor_id bigint NOT NULL`, `factor_version integer NOT NULL`, `code_hash text NOT NULL`, `used_at timestamptz NULL`, `revoked_at timestamptz NULL`, `created_at timestamptz NOT NULL`.

- FK(user_id,factor_id)→core.mfa_factor(user_id,id); version>0; UK(user_id,code_hash). 서버의 안전한 난수8개, 코드당 충분한 엔트로피, 기존 scrypt/검증 라이브러리로 hash. 응답/로그/DB에는 평문 재조회 없음.
- 검증과 used_at 갱신은 동일 TX로1회만 성공. 새 발급은 이전 미사용 코드를 모두 회수하고 security_version을 올려 관련 세션을 무효화. 실패/재발급 경합 검증.
- 관리자 긴급 복구의 별도 수단은 이 직원용 코드와 구분해 오프라인 보관/만료형 challenge 발급 절차로 다룸. 플랫폼 관리자의 본문/계정 가장 권한을 추가하지 않음.

### core.sso_identity

`id bigint PK`, `user_id bigint NOT NULL FK core.app_user`, `provider_key varchar(60) NOT NULL`, `issuer varchar(500) NOT NULL`, `subject varchar(255) NOT NULL`, `state varchar(12) NOT NULL`(ACTIVE/REVOKED), `version integer NOT NULL default1`, `linked_at timestamptz NOT NULL`, `revoked_at timestamptz NULL`.

- UK(issuer,subject), partial UK(user_id,provider_key) WHERE state=ACTIVE, version>0. 메일·표시명 변경으로 subject를 바꾸거나 다른 직원에게 이관하지 않음.
- access/refresh token 영구 보관 없음. 명시 연결은 현재 본인의 최근 추가 인증+OIDC subject 검증을 함께 요구. 정지된 로컬 계정·회사 소속을 IdP 로그인으로 되살리지 않음.

### core.authentication_throttle

`id bigint PK`, `bucket_hash varchar(64) NOT NULL`, `window_started_at timestamptz NOT NULL`, `fail_count integer NOT NULL default0`, `locked_until timestamptz NULL`, `updated_at timestamptz NOT NULL`.

- UK(bucket_hash,window_started_at), fail_count>=0, 만료/잠금 조회 인덱스. 정규화 로그인 식별자와 관측한 네트워크 식별자는 HMAC bucket으로 구분해 원문 IP/로그인 실패 비밀번호를 보관하지 않음. 위조 가능한 Forwarded 헤더를 그대로 신뢰하지 않음.
- 로그인 식별자 실패10회/10분, 네트워크100회/10분, OTP challenge5회/5분 초기안. 존재하지 않는 계정도 같은 제한/메시지. 제한은 설정 범위 내 조정 가능하나 COMPANY에서0/무제한 불가. 정상10명 같은 사무실의 로그인은 계정당과 네트워크 제한을 구분해 검사.

### 기존 core 표 확장

- `core.app_user.security_version integer NOT NULL default1 CHECK>0`. 비밀번호/MFA/복구 변경 시 증가. 기존 계정 비밀번호·활성 상태·역할은 migration으로 임의 변경하지 않음.
- `core.auth_session`: `assurance varchar(20) NOT NULL default'PASSWORD'`(PASSWORD/MFA/RECOVERY_LIMITED/OIDC), `verified_at timestamptz NULL`, `security_version integer NOT NULL default1`, `auth_method varchar(20) NOT NULL default'PASSWORD'`, `absolute_expires_at timestamptz NULL`.
- 실제 COMPANY 신규 세션은 절대 수명8시간·idle30분 초기안. 기존 체험 호환과 migration 도중 구버전 서버의 동작을 분리해 시험. MFA 설정 계정의 이전 PASSWORD 세션은 회사 업무에 재사용 불가.
- `assurance=RECOVERY_LIMITED`는 인증 재등록/로그아웃에만 사용하며 기존 ‘로그인했다’ 체크만으로 업무 API가 허용하지 않도록 공통 검증. provider의 OIDC 토큰만으로 MFA로 승격하지 않음.

## 3. GW 제안 표4개

모든 표는 `id PK`, `S NOT NULL`, `UK(S,id)`·범위 인덱스, core.workspace/data_generation 앵커만 공통 참조한다.

### gw.operating_settings

`version integer NOT NULL default1`, `current_policy_revision_id bigint NULL`, `rollout_state varchar(12) NOT NULL`(DRAFT/PILOT/ACTIVE/PAUSED), `company_hold boolean NOT NULL defaultfalse`, `hold_reason varchar(500) NULL`, `updated_by_user_id bigint NOT NULL`, `updated_at timestamptz NOT NULL`.

- UK(S), FK(S,current_policy_revision_id)→gw.operating_policy_revision(S,id); version>0; hold=true면 사유2~500자. 설정은 CAS로 변경하고 기존 GW 보안 감사 기록에 변경 원인/주체/버전을 남김.
- READY는 UI 입력 상태가 아니라 서버가 계산한 준비 조건. ACTIVE 저장 시 현재 증거/연결/MFA/역할/회사 모드 검증을 같은 잠금 안에서 재검사한다. 준비 실패 시 자동 성공·관리자 우회 플래그 없음.

### gw.operating_policy_revision

`revision_no integer NOT NULL`, `expected_people integer NOT NULL default10`, `expected_departments integer NOT NULL default1`, `responsible_person_id bigint NOT NULL`, `backup_interval_minutes integer NOT NULL default30`, `rpo_minutes integer NOT NULL default60`, `rto_minutes integer NOT NULL default240`, `document_review_months integer NOT NULL default36`, `audit_review_months integer NOT NULL default12`, `backup_keep_days integer NOT NULL default30`, `reason varchar(500) NOT NULL`, `confirmed_by_user_id bigint NOT NULL`, `confirmed_at timestamptz NOT NULL`, `policy_digest varchar(64) NOT NULL`.

- UK(S,revision_no), FK(S,responsible_person_id)→gw.person(S,id). 책임자가 현재 활성 연결인지 서비스에서 확인. 실제 인원과 expected_people은 배포/용량 한도와 구분.
- UI 초기 범위: 인원1~10000, 부서1~1000, 백업 간격5~1440분·RPO1~1440분·RTO15~10080분, 문서/감사1~120개월·백업7~365일. 양의 정수·백업 간격<RPO, 정책 사유2~500자 CHECK. 저장 기간을 짧게 바꿔 기존 원본을 즉시 삭제하지 않음.
- 확정 revision은 불변. 현재 설정 버전(expectedVersion)과 최종값/영향 동의 후 append하고 current pointer 변경. 승인 기록을 덮어쓰지 않음.

### gw.operating_evidence

`run_id uuid NOT NULL`, `kind varchar(20) NOT NULL`(BACKUP/RESTORE/ACCEPTANCE/INCIDENT), `started_at/finished_at timestamptz NOT NULL`, `policy_revision_id bigint NOT NULL`, `code_revision varchar(64) NOT NULL`, `db_revision varchar(100) NOT NULL`, `manifest_digest varchar(64) NOT NULL`, `result varchar(12) NOT NULL`(PASS/FAIL/PARTIAL), `metrics jsonb NOT NULL`, `signer_key_id varchar(60) NOT NULL`, `signature text NOT NULL`, `recorded_by_user_id bigint NOT NULL`, `recorded_at timestamptz NOT NULL`.

- UK(S,run_id), FK(S,policy_revision_id)는 같은 S의 policy를 참조한다. 시각 순서·필수 metrics 키/타입/범위를 확인한다. 본문·이름·비밀번호·비밀 키·DB URL을 metrics에 넣지 않는다.
- 운영 실행 측 Ed25519 비밀 키와 앱 측 검증 공개 키를 분리한다. 서명/범위/head/실행ID/기한/시계 차이를 확인한다. 브라우저는 PASS를 지정할 수 없다. 실패 증거를 지우고 마지막 성공만 보여 주지 않는다. 서명은 실행 주체와 변조 여부를 확인하는 수단이며 실행자/키 자체의 침해를 해결하지는 않는다. 실제 검사 도구가 판정해 발행하고 운영 담당자가 환경/manifest와 대조한다.
- RESTORE는 행 수/hash/FK/세션 무효화/회수 재적용/2계정/손실 구간/실측 시간이 모두 있어야 PASS를 판정한다. 증거가 오래됐거나 현재 policy와 다르면 준비 조건을 만족하지 않는다.

### gw.retention_review

`document_id bigint NULL`, `post_id bigint NULL`, `policy_revision_id bigint NOT NULL`, `review_due_on date NOT NULL`, `state varchar(20) NOT NULL`(DUE/HELD/ARCHIVE_PREPARED/ARCHIVED), `archive_digest varchar(64) NULL`, `archive_reference varchar(200) NULL`, `reason varchar(500) NOT NULL`, `version integer NOT NULL default1`, `reviewed_by_user_id bigint NULL`, `reviewed_at timestamptz NULL`, `created_at timestamptz NOT NULL`.

- document/post 중 하나만 NOT NULL. 각 FK는 S 복합 참조, policy도 같은 범위. UK_PARTIAL(S,document_id,policy_revision_id), post도 동일. version>0, reason2~500자.
- ARCHIVED는 검증된 보관본 digest/reference/담당자/시각이 필요하다. 참조는 비밀이 붙은 URL 대신 보관소 식별자를 쓴다. HELD와 회사 hold는 처리를 멈추며 해제는 새 감사 이력을 남긴다.
- 행 생성·상태 변경은 원문 삭제/편집을 뜻하지 않는다. 열람 ACL은 원래 document/post에 매번 적용한다. 건수/검색/페이지/CSV/이전후속 링크에서도 비공개 본문을 추측하지 못하게 한다.

## 4. API 계약(제안)

기존 개인 로그인·회사 GW63경로를 깨지 않도록 새 계약을 명시하고 기존 회귀를 유지한다. 아래는 **미구현 경로 제안**이다. 제품 도움말에 현재 가능한 기능으로 적지 않는다.

| 경로 | 주체/조건 | 결과/보안 |
|---|---|---|
| POST core/sessions | 기존 아이디/비밀번호 | MFA 필요 시202+짧은 challenge cookie, 업무 세션 없음. 일반 체험은 기존201 호환 |
| POST core/security/login/verify | challenge+OTP 또는 일회용 코드 | 한번 검증 후 새 세션. 복구 코드는 제한 세션만 |
| GET core/security/me | 현재 회원 본인 | 등록/코드 잔여 수/세션 요약. 비밀 없음 |
| POST core/security/enrollment/start·confirm | 현재 본인·CSRF·비밀번호/현재인증 | pending QR/키는 발급 때만; 유효 코드 확인 후 활성화. 응답 분실 시 평문 재조회하지 않음 |
| POST core/security/step-up | 본인 현재 인증 수단 | 실제 검증 시각을 서버에 기록, 브라우저가 시각/assurance 지정 불가 |
| POST core/security/recovery-codes/rotate | 본인 최근 추가 인증 | 새 코드8개1회 응답·구코드 회수. 로그/receipt 평문 금지 |
| POST core/security/recovery/start·complete | 비밀번호/미사용 코드 또는 승인된 복구 요청 | 제한된 재등록, 성공 시 모든 이전 세션/비밀 무효화·감사 |
| GET/POST core/security/oidc/start·callback·link | 고정 공급자/현재본인 명시연결 | nonce/state/PKCE/issuer/sub 검증. email 자동 가입 없음 |
| GET gw/operations?companyId | SEC_ADMIN/AUDITOR는 최소운영정보, 직원은 본인할일만 | 서버 계산 준비 상태/차단 사유. 회사OWNER라는 이유만으로 원문 자동 접근 없음 |
| GET/POST gw/operating-policies | SEC_ADMIN, 쓰기시최근인증·CAS·사유 | 새 revision과 현재 pointer, 불변확정이력 |
| GET/POST gw/operating-evidence | 권한 있는 담당자·서명 검증 | 원문 없는 엄격한 proof envelope. 사용자 자체성공표시 없음 |
| POST gw/rollout-transition | SEC_ADMIN·최근추가인증·CAS·현증거 | DRAFT→PILOT→ACTIVE 또는 PAUSED, 현재조건재평가·감사 |
| GET/POST gw/retention-reviews | 운영역할+대상원문 ACL 구분 | 기한·hold·보관상태; 별도직접DB삭제API 없음 |

쓰기의 바깥 actor/personId 입력·타회사 식별자·알 수 없는 필드를 거부한다. OTP·코드·비밀번호가 포함된 입력은 일반 request_digest/영수증 원문 기록 경로와 분리한다. 불명확 응답 재확인용 상태 조회는 본인의 opaque operation ID와 최소 결과만 반환하며 인증 비밀을 재발급하지 않는다.

## 5. 잠금·실패·배포 인수

- COMPANY의 업무 접근은 공통 core 회사 세션 assurance 검증과 GW의 S/연결/역할/객체 ACL을 모두 통과해야 한다. HR/Flow 등 공통 세션을 쓰는 기존 제품 회귀도 포함한다.
- TOTP/복구 코드 동시 요청2개는 하나만 성공. 실패 수 commit·재발급과 사용 경합·session version 변경·logout/정지 경합 검증. 요청 오류 본문/접근로그에 민감값 출력 금지.
- 쿠키 HttpOnly/Secure/SameSite, CSRF/Origin·짧은중간세션·절대만료·TLS·서버시간오차·키누락/교체·IdP중단을 검사. 외부 QR생성서비스 호출 금지.
- 신규 migration은 additive로 시작. 운영 COMPANY의 미설정 인증/키/게이트는 fail-closed. 과거 사용자 상태/실제 비밀번호를 migration으로 바꾸지 않음. 이미쓴인증·복구·정책/증거이력이 있으면자동downgrade하지않음.
- 자동 청소는 만료 challenge/제한 bucket 등 기술 레코드만 명시 allowlist·dry-run·기존 참조 RESTRICT로 처리. 원장·확정문서·회사감사/연결이력·보존중지대상은 자동삭제대상에 넣지 않음. 실제 사용자 데이터 삭제/익명화는 별도 정책·설계 확인 대상.

## 6. 중간 인증과 오류 응답

로그인202는 기존 Session 타입과 구분한 LoginChallenge 응답이다. 짧은 opaque challenge cookie(HttpOnly/Secure/SameSite)와 별도 challenge CSRF 토큰을 사용하며 full session 쿠키를 발급하지 않는다. OTP·복구 검증 POST는 cookie+CSRF+허용 Origin을 확인한다. 외부 Origin과 위조 Forwarded 헤더로 우회하지 못하게 한다.

성공201의 업무 세션 응답은 기존 소비자를 유지하고 필요한 인증 요약만 추가한다. 중간 challenge 동안 `/sessions/current`는 업무 로그인으로 취급하지 않는다. 응답이 유실되면 먼저 현재 세션을 확인하고, 이미 소비한 challenge로 세션을 재발급하지 않는다. 쿠키까지 유실됐으면 새 로그인/다음 인증 번호로 진행하며 사용한 번호를 되살리지 않는다.

| 상황 | HTTP/코드와 화면 행동 |
|---|---|
| 입력 형식/범위/필수 누락 | 400 VALIDATION_FAILED, 입력 옆 오류/요약과 값 유지 |
| 로그인/중간 인증 실패 | 401 AUTHENTICATION_FAILED, 계정 존재 노출 없는 설명 |
| 제한 초과 | 429 AUTHENTICATION_THROTTLED, 재시도 가능 시각 안내 |
| 최근 인증 필요 | 403 STEP_UP_REQUIRED, 현재 화면 복귀 정보만 유지하고 추가 인증 |
| 복구 전용 세션의 업무 접근 | 403 RECOVERY_ONLY, 재등록/로그아웃 안내 |
| 버전/단계 충돌 | 409 STATE_CHANGED, 현재 서버 상태와 비교/새 검토 |
| 운영 증거/설정 미충족 | 409 OPERATING_PREREQUISITE_REQUIRED, 남은 실제 조건과 행동 |
| 실제 키/어댑터/저장소 사용 불가 | 503 SECURITY_CONFIGURATION_UNAVAILABLE, 성공/우회 표시 없음 |

백업의 RPO 나이는 ‘백업 완료’가 아닌 보수적인 스냅샷 시작 기준으로 계산하고 저장소 반영 지연을 포함한다. 실제 손실 구간을 단정할 자료가 없으면 범위/미확인으로 기록한다.

## 승인된 표 목록

2026-10-18 사용자 전체 설계 승인. 아래는 GW-READY-02 구현 명세의 추가 대상이며 적용·검증 상태는 최신 인계 기록을 따른다.

| 표 | 소유 |
|---|---|
| `core.mfa_factor` | core |
| `core.authentication_challenge` | core |
| `core.recovery_code` | core |
| `core.sso_identity` | core |
| `core.authentication_throttle` | core |
| `gw.operating_settings` | gw |
| `gw.operating_policy_revision` | gw |
| `gw.operating_evidence` | gw |
| `gw.retention_review` | gw |
| `core.app_user` | core |
| `core.auth_session` | core |


## GW-READY-02 긴급 복구 구현 계약 (2026-10-18)

스키마 변경 없이 `authentication_challenge.purpose=RECOVERY`를 재사용한다. 긴급 문서는 `provider_key=gw-kit:<companyId>:<operationKey SHA256 앞32자>`, 암호화 문맥 `emergency-kit`, subtype EMERGENCY_KIT이며 회사·세대·직원·사용자·보안 버전과 전체 operation hash를 결합한다. 365일·원문 1회 응답, 새 문서는 이전 문서/미사용 승인을 만료시킨다. 비밀은 해시 및 암호화 payload로만 보관한다.

서버 CLI의 승인은 `gw-grant:<companyId>`/암호화 문맥 `emergency-grant`이며 15분·일회성이다. 실제 OS UID와 사유를 감사에 남긴다. 승인 시점과 사용 시점에 GW가 현재 회사/세대/직원 연결/SECURITY_ADMIN 역할을 검사한다. core는 자격증명 검증/소비·계정 보안 버전·제한 세션을 소유하며 GW 업무 FK를 추가하지 않는다.

- POST `/api/v1/gw/emergency-kit?companyId=...`: 본인 활성 GW 보안 관리자, 최근 MFA5분, CSRF/Origin/멱등키, 사유2~500자. 같은 발급 요청 원문 재응답은409 ONE_TIME_RESPONSE_UNAVAILABLE.
- POST `/api/v1/core/security/login/emergency`: 비밀번호 검증된 LOGIN_MFA 쿠키+challenge CSRF와 grantToken. GW 조합 라우터를 main에서 연결하며 core→GW import는 없다. 같은 사용자 요청만 소비하고 RECOVERY_LIMITED 세션을 발급한다.
- 정상 비밀번호 로그인 발급20/10분, 등록 seed3/10분, 긴급 문서3/10분. 잘못된 문서5회 잠금·승인 사용 실패5/5분. DB 영속 throttle, DB 시계로 만료/최근 인증을 판정한다.
- COMPANY 회사/HR 관리 변경은 권한 검사 후 최근 인증을 확인하고 기존 receipt를 조회한다. 권한/인증이 만료된 재전송으로 과거 성공 결과를 재사용하지 않는다.

[운영자 절차](../../operations/GW_긴급관리자복구_GW-READY-02.md). 실회사 인수·SSO·백업/보관 실행은 미완료다.

## GW-READY-02 운영 증거 등록 연결 (2026-10-18)

GET/POST `gw/operating-evidence`를 기존 표에 연결했다. 현재 GW 역할·회사 범위·최근 MFA5분(등록)→멱등 응답→현재 정책/코드/DB/서명/시각/실측 계약→runId 중복 검사→불변 이력/감사 순이다. 서명 공개 키는 FS_GW_EVIDENCE_PUBLIC_KEYS, 제품 버전은 FS_CODE_REVISION, DB 버전은 alembic_version이다. PASS/FAIL/PARTIAL 목록에 이전 정책 여부를 표시한다. 자동백업·운영 ready 판정은 미연결이며 false 유지. [상세](../../operations/GW_운영증거등록_GW-READY-02.md).
