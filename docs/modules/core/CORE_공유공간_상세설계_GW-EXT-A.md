# GW-EXT-A — CORE 공유 공간 상세 설계 r1

2026-10-05 · **전체 설계 확인 대상, 코드/DB 미적용**. 기준 40caa5e / schema0.17.0, headfs029b_cmms_module. 공식 FS/D/AC 번호는 구현 전 최신 main과 조율. [P0 운영](../../operations/GW_실운영준비_상세설계_GW-EXT-P0.md) · [GW 업무](../gw/GW_공유협업_상세설계_GW-EXT-A.md) · [화면](../../ui/화면설계_공유공간_GW-EXT-A.md).

## 1. 범위·소유권

core는 로그인·플랫폼 역할·공간/세대·멤버십/초대·세션 공간 선택·감사를 소유한다. 조직/직원/문서 ACL은 GW 소유. 다른 업무 스키마 FK/쓰기 금지. TEAM 초기 허용 모듈은 core/gw만. ERP 포함 다른 업무 API는 TEAM에서 명시적 allowlist로 거부한다. 플랫폼 SUPERADMIN도 GW 문서를 자동 열람하지 않는다.

현행 `_resolve_member`와 로그인은 owner_user_id로 MEMBER 공간을 고른다. 이를 세션의 active_workspace_id 기반 선택으로 바꾼다. MEMBER 개인 공간의 소유권 경로와 GUEST 동작은 유지한다. TEAM은 `owner_user_id=NULL`, 멤버십 OWNER가 관리한다. 따라서 기존 owner_user_id 유일성 제약을 제거할 필요가 없다.

## 2. 논리 DB 명세

아래는 설계용 명세이며 schema.json/실제 DDL이 아니다. PK bigint identity, 시각 timestamptz, created_at 기본 clock_timestamp(). 문자열 enum은 varchar+CHECK. 모든 FK RESTRICT. `?`는 NULL 허용, 그 외 필수. 양수 version은 기본1. assurance_level은 PASSWORD/VERIFIED_MFA/MOCK_MFA CHECK. 상태별 시각 정합은 CHECK, 권한/마지막OWNER/활성공간 등 교차 행 규칙은 SERVICE로 구분한다.

| 대상 | 추가/변경 컬럼 | 제약·인덱스 |
|---|---|---|
| core.app_user 기존 | subject_key uuid (서버 생성, 불변) | UNIQUE NOT NULL. 기존 행 UUID backfill. 과거 actor_key 숫자는 유지, 신규 GW 바인딩에 subject_key 사용 |
| core.workspace 기존 | workspace_kind에 TEAM 추가; name varchar(100)?; access_version bigint=1 | TEAM: owner/guest_session/expires/guest_actor 모두NULL, name1~100필수. 기존3종 CHECK 유지. access_version>0 |
| core.auth_session 기존 | active_workspace_id bigint?; context_version bigint=1; assurance_level varchar(20)=PASSWORD; assurance_provider varchar(80)?; assurance_verified_at?, assurance_expires_at? | workspace FK RESTRICT; context_version>0. 추가 인증 시각은 둘 다NULL 또는 expires>verified. VERIFIED_MFA 또는 MOCK_MFA일 때 provider/시각필수. MEMBER 기존공간으로 backfill |
| core.workspace_membership 신규 | id, workspace_id FK, user_id FK, platform_role varchar(10), status varchar(12), version int=1, joined_at, changed_at, ended_at? | UK(workspace_id,user_id), UK(workspace_id,id); role OWNER/ADMIN/MEMBER; status ACTIVE/SUSPENDED/LEFT. LEFT만 ended_at필수. workspace_id/status/role 및 user_id/status 인덱스 |
| core.workspace_invitation 신규 | id, workspace_id FK, target_user_id FK, invited_by_user_id FK, accepted_by_user_id? FK, token_hash varchar(64), state varchar(12), version int=1, created_at, expires_at, closed_at? | UK token_hash; 부분UK(workspace_id,target_user_id) WHERE state=PENDING; state PENDING/ACCEPTED/REVOKED/EXPIRED, expires>created. PENDING은 closedNULL, 종결은closed필수; ACCEPTED만 accepted_by필수이고 target와같음 |

신규 core.team_creation_receipt의 필드/UK/FK는 §5에 명시한다. workspace/session/user는 기존 테이블 확장이며 신규 개수에 포함하지 않는다.

TEAM 생성은 workspace+빈 data_generation+core/gw 모듈행+최초 OWNER membership을 한 core TX로 생성. GW 테이블에 쓰지 않는다. 초기 세대는 템플릿 복사를 하지 않는다. 개발 모듈용 데이터도 GW 초기 설정 API로 등록한다. USER 계정 자동 가입/생성은 초대 API가 하지 않는다.

초대는 이미 존재하는 회사 계정을 대상으로 한다. 입력 loginId를 core 내부에서 user_id로 해결하며 공개 계정 검색 API는 제공하지 않는다. 부재/비활성 계정에 동일 일반 오류와 요청 제한. COMPANY 계정 프로비저닝/SSO는 P0 인증 부속 설계가 책임진다.

사용자당 개인 MEMBER 공간1개와 TEAM 여러 개를 허용한다. TEAM 회원 row는 재가입 시 같은 row를 ACTIVE로 전환, 과거 변경은 core.audit_event로 추가 기록. 개인/게스트에 membership을 강제로 만들지 않는다.

## 3. 세션·공간 전환 계약

로그인은 subject 인증→기본 MEMBER 선택→세션 생성. 선택 TEAM은 explicit switch로만 변경한다. `GET /sessions/current`는 subjectKey, workspaceId, generationId, workspaceKind, contextVersion, accessVersion, membershipRole, assurance 요약을 추가 반환한다. token/MFA 증명 원문은 반환하지 않는다.

모든 회원 업무 요청에 `X-Workspace-Id`, `X-Context-Version`을 보낸다. TEAM 요청은 누락400, 세션 선택값과 불일치409 CONTEXT_CHANGED. MEMBER도 갱신 클라이언트는 보낸다. 오래된 클라이언트는 기존 MEMBER만 허용하며 TEAM을 한 번이라도 선택해 context_version>1이면 헤더 없는 업무 요청을 거부한다. 로그인/현재세션/로그아웃/공간목록/초대수락/공간전환은 명시한 bootstrap 예외이다.

공간전환: 현재 session row 잠금→요청 contextVersion 확인→대상공간 멤버십/활성상태 확인→active_workspace_id 교체, context_version+1. 응답에는 새 context 전체를 반환한다. 전환은 세션 모든 탭에 적용되며 이전 탭은 헤더 불일치로 실패한다. 대상 선택 실패 시 기존 공간을 유지한다. 권한 회수된 공간을 개인 공간으로 조용히 바꿔 쓰기 요청을 처리하지 않는다.

전환 성공 직후 응답 유실 재시도는 목표공간이 현재와 같고 contextVersion이 정확히1 증가한 경우 같은 context를 반환할 수 있다. 그 외409로 현재 세션 재조회. 이 명령은 contextVersion 기반 CAS로 처리하며 업무 receipt를 만들지 않는다. 추가 전환을 한 번 더 적용하지 않는다.

## 4. 잠금·인증 재확인

TEAM 명령은 기존 세션 의존성 밖에서 인증을 한 번 읽는 것으로 끝내지 않는다. 실제 업무 TX에서 다시 확인한다.

1. 계정 shared advisory lock(신규 namespace 이름/정수는 구현 때 기존 목록과 충돌 검사).
2. 세션 row FOR SHARE(업무 요청) / FOR UPDATE(전환·로그아웃).
3. workspace advisory shared(TEAM 조회) / exclusive(변경). 여러 공간이면 ID 오름차순.
4. 멤버십/직원/ACL 재조회 → 대상 행 → 단계 순 잠금. 권한 변경은 같은 workspace exclusive.

TEAM은 READ COMMITTED에서 잠금을 얻은 **다음 문장**으로 활성 계정/세션/멤버십/세대/모듈을 읽는다. 잠금 대기 전 REPEATABLE READ 스냅샷으로 회수 전 권한을 계속 사용하는 구현 금지. 조회 동안 shared workspace lock을 유지해 결과 구성 전 권한 변경과 순서를 보장한다. 이미 회수 전에 허가된 응답/클라이언트에 전달한 내용까지 회수할 수 있다고 주장하지 않는다.

전역 계정 정지는 해당 계정 exclusive advisory lock 후 상태/세션 회수만 처리, GW를 쓰지 않는다. 멤버십 회수는 대상 사용자 session row를 잠그지 않고 workspace exclusive로 상태 변경하므로 역순 교착을 만들지 않는다. 모든 신규/기존 로그인·정지 경로에 account 잠금 규약을 맞추고 교착 회귀 테스트를 한다. 장기 외부 통신/파일 전송 중 DB 잠금을 유지하지 않는다.

TEAM 시간 판정(초대/세션/추가인증/멱등)은 DB clock_timestamp를 사용. FS_TODAY는 업무일 용도로만. 개인/게스트 기존 계약을 일괄 변경하지 않고 추가 회귀로 호환 확인한다.

## 5. 명령과 멱등 재시도

멤버십/초대 명령은 CSRF·권한·추가인증→workspace lock→현재 권한 재검사→receipt→버전/상태→변경/감사/receipt를 하나의 TX로 처리한다. 탈퇴 같은 권한을 없애는 명령의 성공 응답은 {operationId,status}의 비민감 정보만 저장하며, 동일 주체 재시도는 대상 식별자를 노출하지 않는 성공 영수증만 반환할 수 있다.

**기존 GW receipt는 상세 본문을 저장하므로 그대로 TEAM에 사용하지 않는다.** TEAM 문서 재시도는 현재 membership+직원+문서 읽기 권한을 먼저 검사한 뒤 저장 응답을 반환한다. 완료로 현재 차례가 바뀌었다는 이유로 성공 재시도를 거부하지 않는다. 현재 actor/객체 읽기권한은 필수, 최초 전이 조건은 재검사하지 않는다. 권한이 사라지면403/404이고 과거 본문을 반환하지 않는다. 개인/게스트 기존receipt는 호환 유지.

초대 token은 서버가 생성한 난수 비밀, DB에는 hash만. 만료 기본24시간(제안 설정), 수락/철회/만료 상태 전이는 DB 시각 기준. 만료 상태 materialize 후 같은 대상 재초대 가능. 재발급은 기존PENDING 철회+새행을 원자 처리. 초대 role은 MEMBER 고정, 수락 후 OWNER가 별도 역할 변경.

초대 생성 응답 원문 token은 최초 한번만 표시하고 일반 receipt에는 저장하지 않는다. 동일키 재시도는 invitationId/state/tokenAvailable=false 반환하는 **명시적 비밀 응답 예외**다. 응답 유실이면 기존 초대를 재발급하여 옛 token 무효화. 감사/요청 digest/오류/URL query에 평문 token을 저장하지 않는다. 초대 페이지 fragment에서 token을 읽은 뒤 주소를 지우고 POST body로 보낸다. 수락 receipt digest에는 token hash만 사용한다.

TEAM 생성은 아직 S가 없으므로 계정 잠금 아래 신규 **core.team_creation_receipt**를 사용한다: id bigint identity PK, user_id bigint FK(core.app_user), request_key varchar(100), request_hash varchar(64), team_workspace_id bigint FK(core.workspace), created_at timestamptz=clock_timestamp(), 모두 NOT NULL. UK(user_id,request_key), FK는RESTRICT. 응답은 team ID만 저장하고 현재 소유/멤버십 검사 후 반환한다. 세대 초기화와 무관하게 유지하므로 개인공간 reset 뒤 같은 키로 TEAM이 중복생성되지 않는다. 총 core 신규 테이블은3개다. 생성키 재사용은 본문일치 성공재현/본문상이422, 탈퇴후재시도403. 이 영수증의 보존은 공간 수명과 함께 관리하며 실제 삭제 정책은 P0에 따른다.

초대 수락은 계정/세션 확인→token_hash로 대상공간 식별→그공간잠금→target_user/토큰/기한/상태 재확인→receipt→membership ACTIVE/초대 ACCEPTED/감사/receipt 순서다. 아직멤버가아닌초대대상에한해서만 membership 사전검사를예외로한다. 동일수락키재시도는같은target 계정·token_hash와receipt 일치시비민감성공결과만반환, 이후정지된membership을재활성화하지않는다. 만료시각초과/철회는새수락실패, 이전성공receipt는처리이력으로만표시한다. 다른초대수락키로종결token재사용은409이다.

## 6. API (prefix /api/v1/core)

JSON camelCase, ID 문자열, {data}, 목록 {rows,total,offset,limit}; limit기본50/최대100, 검색100자. 변경 expectedVersion·Idempotency-Key 필수(새 생성 version제외). 세션전환은 위 CAS 예외. 업무 입력 오류400 VALIDATION_FAILED(details.fields.경로), 멱등키 충돌422, 상태409 PRECONDITION_NOT_MET(reason), 인증401, 권한403, 다른공간/없는객체404. 429에는 Retry-After.

| 경로 | 요청 | 응답/권한 |
|---|---|---|
| GET /workspaces | search/offset/limit | 자기 MEMBER+ACTIVE TEAM만, id/name/kind/role |
| POST /workspaces | name | TEAM_TEST의 등록계정 또는 COMPANY의 플랫폼 ADMIN, 추가인증, 201 {id,name,kind,version} |
| POST /sessions/current/workspace | workspaceId,expectedContextVersion | 새 context; 추가인증은 대상 정책에 맞춤 |
| GET /workspace/members | status/search/page | OWNER/ADMIN, 회원id·표시명·role/status/version; token/전역권한 없음 |
| PATCH /workspace/members/{id} | expectedVersion,status?,role?,reason | OWNER 역할변경/소유권; ADMIN은 MEMBER 정지/복귀만. 자신/OWNER 정지는 별도명령 |
| POST /workspace/leave | expectedVersion,reason | 자신의 membership LEFT, 마지막OWNER409. 성공후 space선택 화면 |
| POST /workspace/transfer-owner | targetMembershipId,expectedVersion,reason | OWNER→대상 OWNER 승격+자신ADMIN, 한TX·추가인증. 최소OWNER1유지 |
| GET /workspace/invitations | state/page | OWNER/ADMIN; 평문token 없음 |
| POST /workspace/invitations | loginId | 201 invitationId/expiresAt/inviteUrl(최초만) |
| POST /workspace/invitations/{id}/revoke 또는 /reissue | expectedVersion,reason | 관리자; 재발급은 새id/token |
| POST /invitations/accept | token | 로그인 대상계정만, ACTIVE membership; 공간 자동전환 안 함 |
| GET /workspace/security-events | page | OWNER; 최소 core 관리 사건만 |

추가인증 실패403 STEP_UP_REQUIRED, 마지막소유자409 LAST_OWNER, 컨텍스트불일치409 CONTEXT_CHANGED, 비활성회원403 MEMBERSHIP_INACTIVE. 초대수락 부재/불일치/철회는 일반404 INVITATION_UNAVAILABLE로 상세 존재성 노출 억제. 자기 계정 대상 만료는409 INVITATION_EXPIRED 허용. 모든 기존 /workspace/modules·/generations·admin 조회·reviews도 TEAM allowlist/권한을 적용한다. TEAM 초기화 및 reviews(체험평가)는409 WORKSPACE_KIND_UNSUPPORTED.

## 7. 내부 읽기 계약과 감사

core.interface에 `security_events(c,scoped,module_key,page)`(허용된 관리자에게 현재공간 해당모듈의 관리사건만 반환), `membership(c, scoped, subject_key)` → {active,platformRole,accessVersion}|None, `members(c,scoped,subject_keys)`(최대100) → 제한된 표시명/활성 정보, `workspace_mode(c,scoped)`를 제공. GW는 core 업무 테이블을 직접 SQL 조회하지 않는다. 인증/권한 공통 서비스는 core 소유 데이터를 직접 다룰 수 있지만 GW 데이터를 import/쓰기하지 않는다. subject_key를 사용자 입력만으로 신뢰하지 않으며 조회권한 없는 계정 검색을 제공하지 않는다.

membership/초대/소유권 변경마다 workspace.access_version+1, core.audit_event 추가. 바인딩/ACL/조직 변경은 GW 자체 authz_version 증가(별도 명세). 요청마다 검증하고 버전은 클라이언트 캐시 무효화용이며 서버 검사를 대체하지 않는다.

## 8. 마이그레이션·개발 영향

새 revision: app_user subject backfill→workspace/session 확장→membership/invitation/team_creation_receipt 생성→기존 세션 active MEMBER backfill. 기존 데이터가 잘못되면 예외 행 보고 후 이행 중단, 임의 space 생성 금지. TEAM에만 새 규칙, 기존 GUEST 만료/복사 유지. 신규 FK/UK/INDEX와 metadata/Excel/ERD는 구현 단계에 함께 갱신. 유데이터 downgrade는 거부하거나 명시 복구 계획 요구.

영향 파일: common/auth.py·scope.py·idempotency.py, core/service.py·router.py·schema.py·신규interface, 계정 생성 CLI/세션/초기화/모듈/관리자/cleanup/review, seed copy allowlist, 모든 솔루션 공통 인증 회귀, frontend API wrapper/AuthContext/공간 전환/쿼리 cache. 기존 CORE README의 품목/설비 소유 설명은 FS-013과 충돌하므로 현재 기준을 정정한다.

검증: [A 인수표](../../plan/GW확장_상세설계검증_GW-EXT-A.md). 이번에는 문서만 작성, DB 적용/제품 테스트 없음.
