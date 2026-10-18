# GW-READY-01 제안 ERD

2026-10-18 · **제품 DB에 미적용**. 기존210표의 ERD와 분리한 검토용이다. 신규9표·기존2표 확장·제안FK19개다. 컬럼/NULL/기본값/상태/부분유니크/서비스 정책은 [상세 계약](../보안운영_DB_API_GW-READY-01.md), [검토 Excel](GW-READY-01_제안DB.xlsx), [기계 판독 제안](schema-proposal.json)을 함께 본다. diagram의 식별자는 `.`을 `_`로 표기했다.

## 인증 소유: core

```mermaid
erDiagram
  core_app_user ||--o{ core_auth_session : "기존 사용자 세션"
  core_app_user ||--o{ core_mfa_factor : "인증 수단"
  core_app_user |o--o{ core_authentication_challenge : "선택 사용자"
  core_auth_session |o--o{ core_authentication_challenge : "user_id와 session_id 복합 소유"
  core_mfa_factor ||--o{ core_recovery_code : "user_id와 factor_id 복합 소유"
  core_app_user ||--o{ core_sso_identity : "명시 subject 연결"
  core_app_user {
    bigint id PK
    integer security_version "추가 제안"
  }
  core_auth_session {
    bigint id PK
    bigint user_id FK
    varchar assurance "PASSWORD MFA RECOVERY_LIMITED OIDC"
    timestamptz verified_at "NULL 허용"
    integer security_version
    varchar auth_method
    timestamptz absolute_expires_at "NULL 허용"
  }
  core_mfa_factor {
    bigint id PK
    bigint user_id FK
    varchar kind
    varchar state
    text secret_ciphertext
    bigint last_used_step "NULL 허용"
    integer version
  }
  core_authentication_challenge {
    bigint id PK
    bigint user_id FK "NULL 허용"
    bigint session_id FK "NULL 허용"
    varchar token_hash UK
    varchar purpose
    varchar state
    integer attempt_count
    timestamptz expires_at
  }
  core_recovery_code {
    bigint id PK
    bigint user_id FK
    bigint factor_id FK
    text code_hash
    timestamptz used_at "NULL 허용"
  }
  core_sso_identity {
    bigint id PK
    bigint user_id FK
    varchar issuer
    varchar subject
    varchar state
  }
  core_authentication_throttle {
    bigint id PK
    varchar bucket_hash
    timestamptz window_started_at
    integer fail_count
    timestamptz locked_until "NULL 허용"
  }
```

`authentication_throttle`은 HMAC 버킷을 사용해 사용자 존재 여부와 무관하게 제한하며 core/GW 업무 표로의 FK는 없다. 기존 auth_session 사용자 FK를 제외한 제안 FK는5개다. subject나 인증 수단을 GW 직원으로 직접 FK 연결하지 않는다.

## 업무 소유: GW

```mermaid
erDiagram
  core_workspace ||--o{ gw_operating_settings : "공간 앵커"
  core_workspace ||--o{ gw_operating_policy_revision : "공간 앵커"
  core_workspace ||--o{ gw_operating_evidence : "공간 앵커"
  core_workspace ||--o{ gw_retention_review : "공간 앵커"
  core_data_generation ||--o{ gw_operating_settings : "S 앵커"
  core_data_generation ||--o{ gw_operating_policy_revision : "S 앵커"
  core_data_generation ||--o{ gw_operating_evidence : "S 앵커"
  core_data_generation ||--o{ gw_retention_review : "S 앵커"
  gw_operating_policy_revision |o--o| gw_operating_settings : "S와 현재 정책"
  gw_person ||--o{ gw_operating_policy_revision : "S와 책임자"
  gw_operating_policy_revision ||--o{ gw_operating_evidence : "S와 검증 정책"
  gw_operating_policy_revision ||--o{ gw_retention_review : "S와 검토 정책"
  gw_approval_document |o--o{ gw_retention_review : "S와 문서 XOR 게시"
  gw_board_post |o--o{ gw_retention_review : "S와 게시 XOR 문서"
  gw_operating_settings {
    bigint id PK
    bigint workspace_id FK
    bigint generation_id FK
    bigint current_policy_revision_id FK "NULL 허용"
    varchar rollout_state
    boolean company_hold
    integer version
  }
  gw_operating_policy_revision {
    bigint id PK
    bigint workspace_id FK
    bigint generation_id FK
    bigint responsible_person_id FK
    integer revision_no
    integer expected_people
    integer backup_interval_minutes
    integer rpo_minutes
    integer rto_minutes
    integer document_review_months
    integer audit_review_months
    integer backup_keep_days
  }
  gw_operating_evidence {
    bigint id PK
    bigint workspace_id FK
    bigint generation_id FK
    bigint policy_revision_id FK
    uuid run_id
    varchar result
    jsonb metrics
    text signature
  }
  gw_retention_review {
    bigint id PK
    bigint workspace_id FK
    bigint generation_id FK
    bigint document_id FK "NULL 허용"
    bigint post_id FK "NULL 허용"
    bigint policy_revision_id FK
    date review_due_on
    varchar state
    integer version
  }
```

GW 제안 FK14개는 core의 공간/세대 앵커8개와 GW 내부6개다. 모든 GW 내부 참조는 S 복합키이고 삭제/변경 RESTRICT다. `retention_review`는 document/post 중 정확히1개를 참조한다. 사용자별 보안 주체 식별자는 감사 값으로 검증/보관하되 core로 업무 FK를 추가하지 않는다.
