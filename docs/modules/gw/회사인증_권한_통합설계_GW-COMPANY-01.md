# GW 회사 인증·권한 통합 설계 · GW-COMPANY-01

2026-10-17 사용자 전체 설계 확인·구현 승인. 현재 **GW-COMPANY-02 기반 구현·로컬 검증 완료**이며 [검증 기록](../../agent/GW_회사인증_기반검증_GW-COMPANY-02.md)을 따른다. 아래 ‘확인 대상/01만 수행’은 문서 최초 작성 시점의 이력이다. 후속03~05와 실운영 인수 완료를 뜻하지 않는다.

2026-10-17. **현재 코드 대조·설계 개정 완료, 전체 설계 확인 대상. 제품 구현·DB 적용·실운영 완료가 아니다.** 기준 로컬 main `e02097d`(PWA-POLICY-01 포함). 사용자 지시로 PWA를 로컬 main에만 반영하고 다음 GW 작업을 진행한다. 원격 push·배포는 하지 않는다.

## 1. 목표와 제안 범위

동일 회사의 직원이 자기 계정으로 기안하고 다른 직원이 결재하며, 게시·일정·댓글·알림·채팅도 본인과 허용된 대상만 이용하게 한다. 개인/게스트 공간의 합성 담당자 체험은 그대로 둔다. 실제 회사 기능에 ‘담당자 선택’으로 다른 직원을 가장하는 기능은 두지 않는다.

기존 [GW-EXT-A](GW_공유협업_상세설계_GW-EXT-A.md)의 보안 원칙을 유지하되 회사/조직을 중복 생성하는 부분은 아래 개정안을 우선 적용하는 **제안**이다. 예전 문서를 자동 구현 승인으로 간주하지 않는다. [FS-013](../../plan/독립솔루션_전환결정_FS-013.md)의 인증·업무 소유권과 업무 간 FK 금지를 유지한다.

포함: 현재 회사 계정 재사용, GW 직원 연결·명시적 역할, 회사별 업무 범위, 일반 결재(GENERAL)의 순차/병렬·합의·참조·전결·위임, 조직 게시·댓글·일정·알림·기존 HTTP 채팅, 재배정/읽기 권한과 회수, 개인/게스트 회귀. 첫 회사 범위에서는 ERP/PLM 원천 선택·상세 및 연결 결재를 서버에서도 차단한다. 회사 기능은 아래 단계 전체가 통과할 때만 사용 가능으로 연다.

제외: 새 회원가입/초대 제품·별도 TEAM 구조·공통 세션 공간 전환, HR 권한의 자동 GW 승격, 외부/다른 회사 문서 공유, 첨부/PDF/메일/푸시/전자서명, 채팅 WebSocket·재입장·참여자 변경, ERP 확정 통제·미구현 원천 개발. 실제 운영 MFA/SSO·계정복구·보존/RPO/RTO는 [P0](../../operations/GW_실운영준비_상세설계_GW-EXT-P0.md) 인수 조건으로 남는다. 미충족 상태에서 실데이터 반입이나 운영 인증 완성을 주장하지 않는다.

## 2. 코드 대조 결과와 개정 이유

| 기존 설계/가정 | 현재 코드 근거 | 이번 제안 |
|---|---|---|
| core TEAM/membership/invitation/creation receipt 신규 | `core.company`, `company_member`와 `core.company.resolve_company/members`가 HR·Flow에서 사용 중 | COMPANY·기존 로그인 재사용. 신규 TEAM/초대/세션 선택 테이블 없음 |
| 세션 active_workspace/context_version 전체 변경 | `common.auth._resolve_member`는 개인 MEMBER 공간을 반환, HR·Flow가 요청의 companyId로 검증된 범위를 별도 결정 | GW에서도 요청마다 명시 companyId, 세션 공간 변경 없음. 기존 타 솔루션 요청 의미 보존 |
| GW 조직 신규 및 person_assignment 신규 | `gw.organization_unit`, `person.organization_unit_id`, `hr_employee_code`가 이미 존재 | 기존 조직/HR 가져오기 스냅샷 재사용. 조직 변경은 기존 공통 감사에 남김. 이력 원장 중복 신설 안 함 |
| auth_mode/조직 스냅샷/게시 audience 신규 | 문서 auth_mode·기안/단계 조직 스냅샷, board_post visibility/audience_org_id 이미 존재 | 실제 데이터 타입/상태 제약 확인 후 재사용, 같은 컬럼 추가 migration 금지 |
| 담당자 ID가 실제 사용자 | `service.actor`는 활성 GW person만 확인, `GwLayout`은 sessionStorage에서 선택 | 서버 로그인 user_id와 GW person 바인딩으로 결정. 회사에서 역할 선택 금지 |
| 화면만 회사 선택하면 충분 | GW router **63개 경로**에 personId·actingPersonId/직접 master 호출이 흩어짐 | 모든 경로를 동일 회사/주체/객체 게이트로 감사. 일부만 옮겨 놓고 회사 모드 공개 금지 |
| 기존 action 재사용만 하면 안전 | `engine.action`은 authorize 후 receipt를 확인하지만 GW 문서 mutate는 authorize 미전달, read는 REPEATABLE READ | 회사 권한·객체 ACL은 receipt 전에 재검사, 조회도 잠금 후 READ COMMITTED에서 권한 확인 |
| 회사 계정 정지와 GW가 자동 직렬화 | HR users는 공간16 잠금 뒤 전역 user-management 잠금·계정 변경, 세션 resolve는 별도 TX | 같은 잠금 순서 정합 및 세션 재검증을 설계/검사. ‘즉시 회수’는 커밋 순서로 검증 |

현재 실제 코드를 실행해 회사 GW를 검증한 결과가 아니다. 위 근거는 소스·schema 메타데이터·라우트 AST의 정적 대조다. [63경로 감사표](../../agent/GW_회사인증_경로감사_GW-COMPANY-01.md).

## 3. 사용자와 권한

공통 전제는 활성 로그인 세션 + 활성 계정 + 회사 활성 구성원 + GW 모듈 활성 + ACTIVE 바인딩 + 활성 GW 직원이다. 플랫폼 ADMIN도 회사 가입/바인딩/객체 ACL을 건너뛰지 않는다. 회사 OWNER·HR ADMIN·Flow OWNER/EDITOR는 GW 업무 역할과 별개다.

| 주체/역할 | 허용 | 자동 허용하지 않는 것 |
|---|---|---|
| 게스트/개인 MEMBER | 기존 합성 담당자 체험 | companyId 접근, 회사 본문/인명 목록 |
| 활성 회사 구성원·미연결 | 회사 목록, 본인 연결 안내/동의 | 결재·게시·채팅 원문 |
| 연결 직원 | 본인 기안/결재/게시·참여 업무 | 타인 명의 행위·회사 전체 비공개 문서 |
| ORG_ADMIN | HR 미리보기/명시적 가져오기·GW 직원/조직 관리·연결 요청 | 직원 연결 수락 대행·본문 전체 열람 |
| ROUTE_ADMIN | 결재선 관리 | 결재 대신 처리 |
| POLICY_ADMIN | 전결 규칙 관리 | 규칙을 근거로 타인 명의 결재 |
| BOARD_PUBLISHER | 회사/소속 공지 게시 | 다른 작성자 초안 수정 |
| SECURITY_ADMIN | 명시적 GW 역할·연결 정지/복귀·막힌 결재 관리 | 감사 역할만으로 본문 열람·강제 승인 |
| 회사 OWNER | 빈 GW 최초 설정, 감사된 복구 신청 | 설정 완료 뒤 모든 업무 권한/비공개 본문 자동 획득 |

AUDITOR는 보안 사건 최소값 열람 역할이다. 문서 본문은 별도의 읽기 권한이 있어야 한다. STAFF/MANAGER/EXECUTIVE/BOARD_ADMIN이라는 기존 job_role 문자열을 회사 권한으로 쓰지 않는다.

최초 설정: 회사 OWNER 본인 한 명만 최초 GW 직원과 연결한다. settings가 없는 빈 회사 GW에서 원자 처리하며 ORG_ADMIN/ROUTE_ADMIN/POLICY_ADMIN/BOARD_PUBLISHER/SECURITY_ADMIN을 부여한 사실을 감사한다. HR 직원 코드는 미리보기로 확인한 값만 선택한다. HR 직원 연결이 없으면 임의 이름으로 대신 생성하지 않고 준비 안내를 표시한다. 직원 가져오기는 바인딩/역할을 자동 생성하지 않는다.

다른 직원: ORG_ADMIN이 활성 회사 계정+GW 직원을 지정해 PENDING 연결 요청 → 대상 본인이 사번/표시명/조직을 확인하고 동의 → ACTIVE. 이미 활성화된 계정/직원 쌍의 교체는 금지한다. 잘못된 미수락 요청은 취소 후 같은 직원의 새 미수락 연결을 만들 수 있다. 활성 연결을 다른 사람으로 바꾸는 복구는 제공하지 않는다.

## 4. 회사 범위와 API 계약

기존 `/api/v1/gw` 경로는 유지하고 모든 GW 경로에서 선택적 `companyId`를 받는다. **없으면 개인/게스트 체험, 있으면 회사 모드**다. 서버는 core 읽기 계약으로 해당 회사·활성 멤버십을 검증하고 회사 workspace/활성 generation을 결정한다. 브라우저가 mode/workspaceId/generationId를 보내 권한을 바꾸지 못한다. 회사 ID를 잘못 보낸 경우 개인 체험으로 자동 폴백하지 않는다.

`GET /companies`는 로그인 회원의 활성 소속만 반환한다. `GET /me?companyId`는 company/person/roles/capabilities/bindingStatus/setupRequired 및 GW authzVersion을 반환한다. 미연결 본인에게만 연결 안내를 제공한다. 미소속은403, 알 수 없거나 접근 불가 업무 객체는404로 통일한다.

회사 GET의 personId와 쓰기의 actingPersonId는 **필드가 존재하면400**(본인 ID라도 거부). 서버가 로그인 바인딩에서 정한 person만 업무 함수에 전달한다. 개인 모드에서는 기존 필수 입력과 오류를 유지한다. 기존 Pydantic 모델을 단순 optional로 바꿔 개인 입력 검사를 잃지 않도록 모드별 검증한다. 상대방 personId(결재선·수신인·채팅 참여자)는 별개 필드이며 같은 회사의 활성 연결 여부를 검증한다.

쓰기 공통: CSRF/Idempotency-Key 필수, 기존 행은 expectedVersion CAS, 알 수 없는 필드400. 충돌409, 멱등 본문 충돌422. ID는 기존 GW wire처럼 문자열, companyId는 기존 HR/Flow query처럼 양의 정수로 받는다. 목록 offset≥0/limit1~100/search≤100, 권한 WHERE 후 검색·count·page 수행. 최대목록 무제한 people-options 대신 회사 모드에는 페이지 검색/선택한 ID 상세 조회를 제공한다.

추가 API 제안(모두 companyId 필수, 회사 관리 작업은 reason2~500자):

| 경로 | 용도와 검사 |
|---|---|
| GET /companies, GET /me | 소속/본인 연결·역할·가능 기능 |
| POST /company-setup | OWNER 최초 설정, 빈 GW+본인 HR 연결, 성공 재시도는 생성 중복0 |
| GET/POST /identity-bindings | ORG_ADMIN 연결 요청·상태 목록. 후보 계정은 같은 회사 최소 이름/식별자만 |
| POST /identity-bindings/{id}/cancel | 미수락 PENDING만, ORG_ADMIN |
| POST /me/binding/accept | 대상 본인만, 버전 확인 |
| POST /identity-bindings/{id}/suspend, /resume | SECURITY_ADMIN, 활성화된 동일 쌍만 |
| GET/PATCH /people/{id}/roles | SECURITY_ADMIN, personVersion CAS, 마지막 관리자 보호 |
| GET/POST /documents/{id}/readers; PATCH /documents/{id}/readers/{personId} | 기안자, 읽기만 부여, documentVersion CAS |
| GET /blocked-assignments; POST /documents/{id}/reassign-step | SECURITY_ADMIN, 비활성 담당 미처리 단계만, 제목/본문/금액 없는 목록 |
| GET /security-events | SECURITY_ADMIN/AUDITOR, 해당 회사 GW 사건 최소값·읽기 전용 |

기존 `people`/`people-master` 중복 경로와 master 직접 호출도 게이트를 공유한다. 권한 없는 alias가 우회 경로가 되면 실패다. `/api/v1/gw/projects`는 Flow 호환 경로로서 이번 GW companyId 게이트/권한을 적용하지 않는다.

## 5. 객체별 판정과 회수

| 객체 | 조회 | 변경·회수 |
|---|---|---|
| 결재 초안 | 기안자만 | 기안자만. 예정 결재자는 상신 전 읽기 불가 |
| 상신 문서 | 기안자·현재 유효 배정 참여자·실제 처리자·명시적 읽기 권한 | 현재 단계의 본인 역할에 맞게 승인/합의/참조. 열람자 승인 금지 |
| 전결·위임 | 본인에게 적용되는 규칙/위임 및 관리 역할의 최소 목록 | 전결은 POLICY_ADMIN. 위임은 본인의 활성 단계 권한에 한정, 기간·회수·연쇄/겹침 방지 유지 |
| 게시 | 초안은 작성자, 게시된 회사글은 연결 직원, 조직글은 현재 직접 소속/작성자 | 작성자 수정/정정/철회. 공지는 BOARD_PUBLISHER 검사. 하위 조직 자동 포함 없음 |
| 댓글 | 부모 문서/게시를 현재 읽을 수 있는 직원 | 본인 작성/수정/삭제만. 부모 권한 회수 뒤 댓글·영수증 재노출 차단 |
| 일정 | 회사 공개/본인 작성/명시 참여, 조직 범위는 현행 지원 필드만 | 작성자만 수정·취소, 본인 참석 응답만. 관리자 전체 일정 자동 열람 없음 |
| 알림 | 본인 수신+대상 객체 현재 권한 | 본인 읽음 표시만. 대상 권한 없으면 제목/미리보기/건수도 제외 |
| 채팅 | 활성 연결+해당 채널의 미탈퇴 참여자 | 본인 전송/읽음/탈퇴. 참여자 후보는 같은 회사 활성 연결, 회사 관리자가 채팅 전체를 읽지 못함 |

위임받은 사람은 실제 처리자와 원 담당자를 사건에 각각 보관한다. 위임 기간이 끝나거나 회수되면 새 접근은 차단하되 실제 처리자가 수행한 사건은 보존한다. 미결 열람/승인 허용은 매 요청 현재 위임 및 활성 양쪽 계정을 검사한다. 직접 읽기grant 없이 단지 과거 위임자였다는 이유로 영구 열람하지 않는다.

재배정은 비활성 직원/멤버십/계정 때문에 막힌 WAITING 단계만. 원 approval_step.person_id·결정 이력은 바꾸지 않고 새 배정 사건을 추가한다. 자기 자신/기안자/다른 중복 단계 인원으로 재배정 금지. 완료 단계 변경·서비스 자동 승인 없음. 이전 배정자는 처리 이력/별도 권한이 없으면 이후 읽기 불가. 병렬 참여자별 재배정도 단계/참여역할을 보존한다.

마지막 SECURITY_ADMIN의 GW 역할 제거/연결 정지는409. core의 계정 긴급 정지는 막지 않는다. 마지막 관리자가 core에서 정지되면 자동 승격·플랫폼 관리자 본문 접근을 만들지 않고 P0 복구 인수 전 회사 기능 출시를 막는다. 복구 절차가 없는데 마지막 관리자 보호만으로 운영 준비 완료라 하지 않는다.

## 6. 논리 DB 변경 제안

**이 문서의 명세는 미적용 설계다. schema.json/Excel/실DB는 변경하지 않았다.** 신규5표만 제안하며 기존 조직/컬럼은 재사용한다. 공통 컬럼 id bigint identity PK, workspace_id/generation_id NOT NULL, UK(S,id), 범위 앵커 FK RESTRICT, created_at timestamptz 기본clock_timestamp. 업무 FK는 반드시 S를 포함한다.

| 신규 GW 표 | 필수 필드·제약 |
|---|---|
| collaboration_settings | UK(S), authz_version bigint 기본1 CHECK>0, initialized_by_user_id bigint(인증값·FK 없음), initialized_at timestamptz. 설정 시 한 번만 생성 |
| person_identity_binding | person_id 복합FK, user_id bigint(인증 식별자·core FK 없음), state PENDING/ACTIVE/SUSPENDED/CANCELLED, version int기본1>0, requested_by_user_id, activated_at?/closed_at?, reason varchar500?. 부분UK(S,person_id)/UK(S,user_id) WHERE state<>'CANCELLED'. 활성화된 연결은취소/쌍변경금지. PENDING은양시각NULL/ACTIVE활성시각필수종료NULL/SUSPENDED양시각필수/CANCELLED활성NULL종료필수 |
| role_grant | person_id 복합FK, role_key varchar30(ORG_ADMIN/ROUTE_ADMIN/POLICY_ADMIN/BOARD_PUBLISHER/SECURITY_ADMIN/AUDITOR CHECK), is_active bool기본true, version int기본1>0, changed_by_user_id bigint, reason varchar500. UK(S,person_id,role_key). person.version CAS와 함께 변경 |
| document_reader | document_id/person_id 복합FK, is_active bool기본true, version int기본1>0, granted_by_user_id bigint, reason varchar500. UK(S,document_id,person_id), person/is_active 검색인덱스 |
| step_assignment | document_id/step_id/person_id, assignment_seq int>0, reason varchar500, assigned_by_user_id bigint. UK(S,step_id,assignment_seq), (S,document_id,step_id)→approval_step(S,document_id,id) FK. approval_step에 해당 복합UK 추가 |

승인 사건 enum에 STEP_REASSIGNED/READER_GRANTED/READER_REVOKED 추가(기존 details 재사용). auth_mode=IDENTITY 허용 제약이 실제 있는지 확인하고 부족한 CHECK만 신규 revision으로 확장한다. 조직·기안/단계 스냅샷 컬럼 재추가 금지. 회원 물리 삭제/ID 재사용을 이번에 만들지 않으며, 회사복구는 core 계정 ID와 GW binding을 같은 백업으로 복원·검증한다. UUID subject/SSO 공급자 연결은 이번 내부계정 ID를 대체하는 자동 이행으로 처리하지 않고 후속 설계한다.

binding/user_id는 표시명·아이디 문자열과 달리 계정명 변경 후에도 같은 내부 식별자를 유지한다. HR 사원 코드가 같다고 자동 바인딩하지 않는다. HR 읽기 인터페이스에서 명시적 연결 후보를 제공하되 hr.work_account를 GW가 직접 SQL 조회/쓰기하지 않는다. 계정·회사 후보는 core.company 읽기 계약을 통해 얻고 비밀번호·세션 해시를 GW에 반환하지 않는다.

## 7. 트랜잭션·회수·동시성

회사 쓰기/권한 조회 공통 순서 제안:

1. companyId로 회사 후보 범위를 확인한다. 이 사전 조회만으로 최종 권한을 결정하지 않는다.
2. READ COMMITTED TX에서 기존 workspace advisory namespace16의 해당 회사 잠금을 획득한다(조회 shared, 변경 exclusive). 다음에 기존 `fs.company.user-management` 전역 잠금을 shared(업무)/exclusive(계정 관리)로 획득한다. 기존 HR 사용자 관리의 회사→전역 순서와 일치시킨다. 개인계정 정지/로그아웃의 세션 행 경합은 아래 규약을 추가한다.
3. 잠금을 얻은 다음 문장에서 계정/세션 만료·revoked_at/회사 멤버십·활성 세대·GW enabled를 재조회한다. 세션행 FOR SHARE(업무), 로그아웃은 해당 세션 FOR UPDATE 후 폐기한다. 여러 회사 잠금은 회사 ID 오름차순이며 전역 잠금 뒤 새 회사 잠금을 얻지 않는다.
4. GW 바인딩/역할·객체 ACL을 확인한 뒤 멱등 영수증을 확인한다. 기존 성공 receipt는 현재 권한이 있으면 전이 조건을 다시 요구하지 않고 반환, 권한 회수 시 본문을 반환하지 않는다.
5. 대상 행·approval step은 ID 순으로 잠그고 CAS/업무 상태 검사→변경·사건·감사·receipt를 한 TX로 처리한다. 권한 변경은 settings.authz_version 증가. 조회는 결과 구성까지 shared 잠금을 유지하되 외부 통신은 잠금 밖에서 한다.

기존 HR 사용자 관리의 **authorize가 전역 잠금 전 실행되는 지점**도 잠금 후 재확인을 추가해야 한다. 변경 범위는 계정 회수 경합 보호에 한정하고 HR 업무 정책/실제 계정 데이터는 바꾸지 않는다. core 전역 정지/로그아웃을 포함한 모든 회수 경로를 조사하고 같은 순서로 맞춘 뒤 병렬 barrier 테스트를 한다. 감사·원문/ERP 외부 조회를 잠금 안의 장기 네트워크 호출로 만들지 않는다.

권한 회수 커밋 전에 허가되어 만들어진 응답은 철회할 수 없다. 회수 커밋 뒤 시작하거나 잠금 대기에서 풀려난 요청은 차단해야 한다. 브라우저가 이미 받은 본문까지 회수했다고 표현하지 않는다. 회사 응답은 no-store, 회사 본문 localStorage 캐시 금지.

## 8. 화면과 업무 흐름

GW 화면 위에 ‘개인 체험 / 회사명’ 선택을 둔다. 회사 목록은 본인 소속만, 회사 모드에는 로그인에 연결된 직원명과 연결/권한 상태만 표시한다. 회사 변경 시 미저장·전송중·응답불명 재시도는 기존 보호로 막고 확인 후 변경한다. URL query companyId를 명시해 새로고침 시 회사를 유지한다. 개인/회사 UI 입력과 요청 키를 서로 재사용하지 않는다.

`useGet` cache key 및 `useSend` 멱등 operation key에는 companyId/선택 revision을 포함한다. 회사 변경/권한 변경 응답 전에 시작된 조회는 AbortController와 요청 키로 폐기한다. 다른 탭의 회사 선택은 세션을 바꾸지 않으며, 각 탭 URL의 회사로만 요청한다. 권한 회수·401은 해당 화면 원문/선택 상태를 비우고 재연결 안내한다.

대표 흐름: 기존 회사 관리에서 계정 준비 → OWNER GW 최초 설정 → HR 조직/직원 미리보기·명시적 가져오기 → 동료 계정 연결 요청 → 동료 본인 동의 → 결재선 등록 → 직원 기안·상신 → 다른 계정 순차/병렬 결재·합의·참조 → 사건/완료본 재조회. 이어 조직공지/댓글, 일정 초대·응답, 참여자 채팅과 탈퇴, 계정 회수 후 직접URL/API/알림/receipt 접근 차단을 확인한다.

기존 G-01~13을 사용하고 직원/조직/권한·연결/막힌결재는 기존 FormPanel/DetailPanel/DataTable 패턴으로 확장한다. Factory Flow는 독립 메뉴와 권한을 유지한다. 새 학습·진도·채점/광범위 UI 재설계는 없다. 도움말은 회사 모드가 실제 통과한 뒤 체험과 분리해 갱신한다.

## 9. 이행·게스트·보호

기존 개인/게스트 본문·이벤트·템플릿은 수정하지 않는다. 신규 보안 표는 회사 범위만 사용하고 공개 템플릿은0행이다. 현재 COMPANY의 GW enabled/seeded_generation_id 표시는 제품 인증 완료가 아니다. 기존 회사에 문서가 있거나 임의 person/바인딩 흔적이 있으면 bootstrap을 중단하고 보고한다. 기존 회사를 자동 스캔해 관리자/직원/권한을 생성하지 않는다.

main의 `seed_ready("gw")`는 개인 context에서 실행된다. GW 회사 요청에는 회사전용 준비 게이트를 두어 회사 데이터에 copy_module_seed를 호출하지 않는다. 회사 권한 목록/초기 설정 외 진입은 settings 및 기능 완료 상태를 확인한다. reset/게스트 복사/cleanup에 신규 표가 잘못 포함되지 않도록 명시적 제외와 회사거부를 검사한다. Flow `/gw/projects` 호환 include 순서도 별도 회귀한다.

실제 DB 변경 시 새 revision·schema.json·DB설계서.xlsx·GW ERD를 같은 작업에서 반영하고 격리 DB에서 upgrade/downgrade/upgrade·DDL0을 확인한다. 적용 전 실제 head/목표schema 차이를 다시 확인한다. 기존 revision 수정 금지. 테스트 계정은 임시 난수 자격증명으로 격리 DB에만 생성한다.

## 10. 실행 단계와 인수 기준

| ID | 산출물 | 완료 판정 |
|---|---|---|
| GW-COMPANY-01 | 현재 코드 대조·통합 설계·63경로 감사표 | 이번 문서. 제품/DB 미적용, 사용자 전체 설계 확인 |
| GW-COMPANY-02 | 승인 명세의5표/제약·core 읽기/HR연결 인터페이스·잠금/인증게이트 | DB 문서 동시반영/왕복/DDL0·게스트/HR/Flow 회귀. 회사 업무는 아직 공개하지 않음 |
| GW-COMPANY-03 | bootstrap/바인딩/역할·결재·게시/읽기/재배정 ACL | 직원2명 별도 세션 대표업무, 타회사/역할가장/회수/receipt/경합 통과 |
| GW-COMPANY-04 | 기존 협업13화면 회사연결·전결/위임·댓글/일정/알림/채팅·도움말 | 63기존경로+신규경로 전수권한·브라우저1440/390·개인체험 회귀 |
| GW-COMPANY-05 | 통합 및 회사 시범 인수 | 전체 검사·부하/복구 및 P0 실제운영조건. 미충족은 회사 시범/운영 미완료로 표시 |

각 ID는 결과 보고 뒤 사용자 확인 원칙을 따른다. 이번에는01만 수행하며02 제품/마이그레이션은 시작하지 않는다. 현재 요청은 로컬 main만 반영 범위이며 원격 push/실서버 배포는 하지 않는다.

필수 검사(실행 결과 아님): C01 게스트/미소속403; C02 회사A/B 본문·목록·건수·검색·이전후속 링크 격리; C03 personId/actingPersonId 위조400·alias우회0; C04 자기 연결만 수락·재바인딩 금지; C05 회사OWNER/HRADMIN/플랫폼ADMIN 비공개본문 자동열람0; C06 휴가권한과GW권한 독립; C07 직접/병렬/합의/참조/전결/위임 실계정처리 및 스냅샷 보존; C08 초안 비공개·읽기grant/조직이동 회수; C09 댓글/일정/알림/채팅·탈퇴 뒤 재시도; C10 계정정지/멤버십회수/로그아웃/권한변경과 업무 경합; C11 receipt replay 시 본문 재노출0; C12 마지막관리자·막힌결재·완료이력보존; C13 회사전환·늦은응답·재시도키 분리; C14 시드/복사/초기화 유출0; C15 migration/DDL/격리·전체검사; C16 두계정 실제API 브라우저/키보드/모바일폭; C17 실운영 MFA/복구/보존·회사 시범 인수.
