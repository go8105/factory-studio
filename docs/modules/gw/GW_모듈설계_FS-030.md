# FS-030 GW 모듈 설계 revision 1

작성: 2026-10-01 · **사용자 “구현 진행해줘”로 전체 설계 승인. FS-030a DB·FS-030b API/화면 완료, c 시드·도움말 예정**.
근거: [승인 결정 D60~69](../../plan/GW도입_전자결재_결정_FS-030.md), [화면 설계](../../ui/화면설계_GW_FS-030.md), [현재 기준](README.md), [API 공통 규약](../../architecture/API계약서_FS-010.md). 결정서 권장안 4항목은 사용자 “진행해줘”로 승인됐다. 아래 상세는 2026-10-01 사용자 “구현 진행해줘”로 승인됐다.

## 1. 범위와 동작 원칙

`ERP 매입 조회 → GW 초안 → 상신본 고정 → 순차 결재 → 승인/반려 → ERP 읽기 전용 배지`와 `일반 기안`, `공지·자유 게시판`을 제공한다. 한 개인 공간에서 합성 담당자를 바꾸는 업무 체험이며 실제 직원들의 공동 결재가 아니다. 결재는 **상신 당시 문서 검토 기록**이다. ERP 원문 수정·확정·취소·재고 처리를 막거나 변경하지 않는다.

소유: gw 8테이블. 교차 쓰기/FK0, core 업무 테이블0. 공통 범위 `S=(workspace_id,generation_id)`. 읽기는 REPEATABLE READ에서 read_scope, 쓰기는 기존 write_scope의 공간 advisory lock 뒤 활성 세대를 다시 확정한다. 다른 업무 service import 금지. 금액·수량은 Decimal/문자열, 시각은 UTC ISO8601·화면 KST. GW 상태 순서는 사건 순번으로 판단하며 FS_TODAY와 실시간을 비교하지 않는다.

## 2. 인증·합성 역할·허용 행위

현재 core AuthContext는 GUEST/MEMBER와 개인 workspace를 제공한다. 기존 인증/CSRF/공간 접근 검증을 재사용하며, 새 core 권한 체계·계정 테이블을 만들지 않는다. 유효한 자기 공간 세션은 GW 체험 쓰기를 할 수 있다. 합성 역할은 core ADMIN 권한이 아니다.

| 행위 | 합성 담당자 검사 |
|---|---|
| 새 기안 | 같은 S의 활성 담당자. 그 담당자가 기안자가 됨 |
| 초안 수정·상신·회수·재상신 | 기안자와 선택한 담당자 일치 |
| 승인·반려 | 현재 대기 단계 담당자와 일치, 활성, 기안자와 다름 |
| 공지 생성/게시/철회/정정 | 활성 BOARD_ADMIN 직무 + 작성 담당자 일치(생성 시 작성자로 설정) |
| 자유 글 편집/게시/철회/정정 | 작성 담당자와 일치, 활성 |
| 담당자/결재선 관리 | 자기 공간의 인증 세션으로 관리. 합성 역할로 실권한 승격 없음 |
| 문서 조회 | 현재 S의 모든 문서 조회 가능. “내 기안/내 결재”는 업무 필터이며 비밀문서 ACL 아님 |

문서·게시글 변경 요청의 `actingPersonId`는 같은 S의 GW 담당자만 허용. 실제 인증 주체는 AuthContext에서만 기록하며 본문의 actorKey/actorKind/workspaceId/generationId는 400. 범위 밖 ID는 404. 담당자·결재선 마스터 관리는 actingPersonId 없이 실제 인증 주체로 core 감사에 기록한다(담당자0명 상태에서도 최초 등록 가능). 실제 세션 권한 실패는403, 올바른 공간의 다른 합성 역할/단계/비활성 충돌은409 reason으로 구분한다.

역할 선택은 탭의 메모리/sessionStorage에 S와 함께 저장하고 세대 변경 때 버린다. 쓰기마다 서버가 재검사한다. 비활성화는 진행 결재의 기안자/미처리 단계 담당자 또는 게시판/문서 초안 작성자면409. 그 외 비활성화 가능, 삭제 API 없음. 이름/직무 변경은 과거 스냅샷을 바꾸지 않는다. 공지 초안 작성자의 BOARD_ADMIN 직무 해제는 초안이 있는 동안 거부한다. BOARD_ADMIN 마지막 활성 담당자 비활성화/직무 해제는 거부하여 공지 관리가 막히지 않게 한다.

## 3. DB 명세 — FS-030a 구현 완료

모든 테이블 공통: `id bigint IDENTITY PK`, workspace_id/generation_id bigint NOT NULL, `created_at timestamptz NOT NULL DEFAULT clock_timestamp()`, UK(S,id), core workspace/data_generation 범위 앵커. 모든 업무 FK는 S를 포함하며 ON DELETE RESTRICT, FK 열 인덱스. 이름 표기의 `?`만 NULL 허용. UK/INDEX는 아래 열 앞에 S를 붙인다. 상태/직무 enum은 varchar+CHECK다. API의 길이·정밀도 제한은 DB와 같다.

### 3.1 담당자·결재선 (3테이블)

| 테이블 | 컬럼 | 제약/정책 |
|---|---|---|
| `gw.person` | code varchar(30), name varchar(80), job_role varchar(20): STAFF/MANAGER/EXECUTIVE/BOARD_ADMIN, is_active bool default true, version int default1 | UK(code), code 대문자 영숫자/하이픈 2~30자, 이름 trim 1~80. code 불변. version>0 |
| `gw.approval_route` | code varchar(30), name varchar(100), is_active bool default true, version int default1 | UK(code), code 불변. 이름1~100. version>0 |
| `gw.route_step` | route_id FK, seq smallint, person_id FK | UK(route_id,seq), UK(route_id,person_id), seq1~3. 서비스에서 빈 결재선 금지·연속1..N·활성 담당자 검사 |

템플릿 편집은 route의 version 증가와 단계 통째 교체를 한 TX에서 처리한다. 템플릿 단계 자체는 초안이며 삭제/재작성 가능, 문서 단계는 별도 복사본이다. 이미 선택한 문서의 결재선은 자동 갱신하지 않는다. 기안자 제외는 문서 생성/템플릿 재선택/상신 때 검사한다.

### 3.2 결재 문서·단계·사건 (3테이블)

| 테이블 | 컬럼 | 제약/정책 |
|---|---|---|
| `gw.approval_document` | serial bigint, document_no varchar(40), previous_document_id? self FK, round_no int default1, kind varchar(20): GENERAL/ERP_PURCHASE, title varchar(200), body text, drafter_id FK, drafter_code varchar(30), drafter_name varchar(80), drafter_job_role varchar(20), route_id FK, route_code varchar(30), route_name varchar(100), status varchar(20): DRAFT/IN_REVIEW/APPROVED/REJECTED/WITHDRAWN, version int default1, submission_order? bigint, current_step? smallint, submitted_at? timestamptz, closed_at? timestamptz, source_kind? varchar(30), source_no? varchar(40), source_snapshot? jsonb, source_digest? varchar(64), source_status? varchar(20), amount? numeric(18,2), currency? varchar(3) | UK(serial), UK(document_no), UK(previous_document_id) ※NULL 제외, UK(submission_order) ※NULL 제외. UK_PARTIAL(source_kind,source_no) WHERE status=IN_REVIEW AND kind=ERP_PURCHASE. 이전 문서≠자신, serial/round/version>0. 제목1~200·본문1~10000. JSON object/해시64hex/type별source값 일치 CHECK. GENERAL은 source 전부NULL, ERP는 모두필수. 금액≥0, amount/currency 함께NULL 또는 함께존재; 통화 A-Z3 |
| `gw.approval_step` | document_id FK, seq smallint, person_id FK, person_code varchar(30), person_name varchar(80), person_job_role varchar(20), status varchar(20): WAITING/APPROVED/REJECTED/SKIPPED, decision_reason? varchar(500), decided_at? timestamptz | UK(document_id,seq), UK(document_id,person_id), seq1~3. APPROVED는시각필수·의견선택, REJECTED는사유/시각필수, WAITING/SKIPPED는둘다NULL. 제출 전만 단계 교체, 이후 상태 단방향 전이 |
| `gw.approval_event` | document_id FK, event_seq int, event_type varchar(30): CREATED/DRAFT_SAVED/SOURCE_REFRESHED/ROUTE_SELECTED/SUBMITTED/APPROVED/REJECTED/WITHDRAWN/RESUBMISSION_CREATED, acting_person_id FK, person_code varchar(30), person_name varchar(80), person_job_role varchar(20), actor_kind varchar(10): GUEST/MEMBER/SEED, actor_key varchar(100), step_seq? smallint, reason? varchar(500), document_version int | UK(document_id,event_seq), seq/version>0, step_seq1~3. 승인/반려만 step_seq필수, 반려/회수 사유2~500. 나머지 NULL. 실제 사용자 FK 없음. 사건 payload에 세션 토큰·이메일·별칭·전체 본문 보관 금지 |

serial은 공간 잠금 아래 `max(serial)+1`, 문서번호 `GW-000001`(6자리 최소, 초과는 자릿수 확대). 삭제가 없어 번호 재사용 없음. 재상신은 새 serial/번호, 이전문서+round_no+1. 일반 신규는 round1. ERP 같은 원천에 독립 신규 기안도 가능하므로 **최신 판단은 round_no가 아니라 상신 시 공간 전체 max(submission_order)+1**이다. 미상신 초안은 ERP 배지 대상이 아니다.

상태 CHECK: DRAFT는 submitted_at/closed_at/submission_order/current_step NULL. IN_REVIEW는 submitted_at/submission_order/current_step 필수·closed_at NULL. 종결은 submitted_at/submission_order/closed_at 필수·current_step NULL. 현재 단계와 실제 단계 수, 종결 상태/단계 일치, 순번 연속, 자기 결재 금지는 서비스 정책으로 명시하고 테스트한다. source_snapshot는 상신 전 명시적 갱신만 허용하며 상신 후 불변이다. 결재 이벤트는 append-only; 외부 변경/삭제 API가 없다. DB 운영자까지 막는 위변조 방지 시스템은 아니다.

### 3.3 게시판 (2테이블)

| 테이블 | 컬럼 | 제약/정책 |
|---|---|---|
| `gw.board_post` | serial bigint, post_no varchar(40), previous_post_id? self FK, board_kind varchar(10): NOTICE/FREE, author_id FK, author_code varchar(30), author_name varchar(80), author_job_role varchar(20), title varchar(200), body text, status varchar(20): DRAFT/PUBLISHED/WITHDRAWN, version int default1, published_at? timestamptz, withdrawn_at? timestamptz, withdraw_reason? varchar(500) | UK(serial), UK(post_no), UK(previous_post_id) NULL제외. 양수serial/version, 이전글≠자신. 제목1~200·본문1~10000. DRAFT는게시/철회칸NULL, PUBLISHED게시시각만, WITHDRAWN게시/철회시각/사유필수 |
| `gw.board_event` | post_id FK, event_seq int, event_type varchar(30): CREATED/DRAFT_SAVED/PUBLISHED/WITHDRAWN/CORRECTION_CREATED, acting_person_id FK, person_code varchar(30), person_name varchar(80), person_job_role varchar(20), actor_kind/actor_key(10/100), reason? varchar(500), post_version int | UK(post_id,event_seq), 양수seq/version. 철회사유2~500, 그 외 선택. 감사 주체 정책은 approval_event와 동일 |

게시번호 `GB-000001`. 게시글 원문 수정/물리삭제 API 없음. 초안만 수정, 게시 때 작성자 정보 재스냅샷. 정정 생성은 같은 작성자·게시판으로 새 초안/번호, previous_post_id로 연결; 한 글의 직접 후속은1건(중복 생성 시409+기존후속번호). 정정 초안은 원글을 가리지 않는다. 정정 게시 후 원글에도 후속 링크 표시하며 원글은 그대로 남는다. 철회 글은 목록에 철회 표시·사유·원문을 상세에서 열람 가능하다. 글은 plain text로 렌더링, HTML 실행/외부 콘텐츠 자동 로딩 없음.

조회 INDEX: 문서(status,submission_order), 문서(drafter_id,status,serial), 문서(source_kind,source_no,submission_order), 단계(person_id,status,document_id), 게시(board_kind,status,serial). FK 인덱스와 중복되면 통합. self FK는 생성 시 이미 존재하는 종결/게시 문서만 가리키므로 순환이 불가능하다(SERVICE).

## 4. 상태 전이와 원문 검토

1. 초안 생성: 현재 역할을 기안자로 고정, 활성 결재선 1~3명 복사. 같은 역할 포함/중복 거부. GENERAL은 내용·선택금액, ERP_PURCHASE는 서버가 원문을 조회해 스냅샷/금액을 저장한다. 취소 원문은 신규 연결 불가.
2. 초안 수정: 제목/본문, 일반 금액/통화만 PATCH. 기안자·kind 불변. ERP 대상 변경은 별도 새 초안; 원천/금액을 PATCH로 바꾸지 못함. route-select와 refresh-source는 각각 명시적 변경/버전 증가/사건 기록.
3. 상신: 현재 버전·기안자·결재선 활성/자기결재/진행중중복 검사. ERP 원문을 동일 TX에서 다시 읽고 **저장된 초안 digest/status와 현재 값이 같아야** 한다. 다르면409 SOURCE_CHANGED, 입력은 보존; 사용자가 원문 갱신→차이 검토→상신한다. 원천 없음/취소/off는 상신 거부. 상태/상신시각/순번·현재단계1을 한 번 저장한다.
4. 승인: 현재 단계 WAITING만 APPROVED. 다음 단계가 있으면 current_step+1, 없으면 문서 APPROVED/closed_at. 단계 이름·직무는 상신 때 재스냅샷하고 이후 고정. 이름이 바뀌어도 동일 person_id 담당자는 처리할 수 있다.
5. 반려: 현재 단계 REJECTED, 뒤 WAITING은 SKIPPED, 문서 REJECTED. 회수: 어떤 단계도 승인되지 않은 IN_REVIEW만, 모든 WAITING은 SKIPPED, 문서 WITHDRAWN. 각각 사유 필수.
6. 재상신 생성: REJECTED/WITHDRAWN만, 원 기안자만 가능. 기존후속 있으면409. 새 초안에 본문/기존 결재선·원문 스냅샷을 복사하되 단계는WAITING, 제출정보NULL. ERP off여도 복사 가능하지만 새 상신은 원문 재검사. 완료 승인본 재상신은 불가; 별도 새 기안 가능.

상신 순간 이후 ERP 변경은 막지 않는다. GW가 읽은 TX 스냅샷 기준으로 상신하고 이후 조회에서 변경을 알린다. 승인/반려는 **현재 ERP 값을 조건으로 사용하지 않는다**. 순환 호출과 타솔루션 행 잠금 없음. 진행 중 ERP가 삭제/취소/off여도 고정 상신본에 대한 결재를 할 수 있으며 화면 확인 문구에 이 사실을 표시한다.

## 5. 원문 계약과 digest

ERP 제공 코드만 ERP 테이블을 읽는다. 기존 interface 계약은 유지한다. 새 함수는 b 단계 ERP README 표에 함께 추가한다.

| 함수 | 입력/반환 |
|---|---|
| `approval_documents(c, scoped, kind, *, search, offset=0, limit=50)` | kind PURCHASE_INVOICE만, offset≥0/limit1~100/search≤100. off=None; on={rows,total}. 목록은 번호/거래처/합계/통화/상태, invoice_no 정렬. 선택 후보는 draft/confirmed. 거래처/원문 ID 반환 안 함 |
| `approval_document(c, scoped, kind, document_no)` | off=None, on={found:false} 또는 {found:true,snapshot,digest,status}. 취소 문서도 조회되며 사라진 원문과 구분 |
| `approval_source_digest(snapshot)` | ERP 소유 순수 정규화 함수. DB/다른모듈 호출 없음. GW 저장·ERP 배지 비교 모두 동일 규칙 사용 |
| `gw.interface.approvals(c, scoped, document_refs)` | 최대100개의 (PURCHASE_INVOICE,번호), S내 IN_REVIEW 우선 또는 submission_order 최신 종결, DRAFT제외. off=None, on=요청키별 null/summary. summary: documentNo, status, submissionOrder, sourceDigest, sourceStatus. GW 저장값만 읽고 ERP를 호출하지 않음 |

snapshot v1: `schemaVersion=1`, kind, documentNo, partnerCode/partnerName, currency, supplyAmount/taxAmount/totalAmount, lines[{lineNo,itemCode,quantity,unit,unitPrice,currency,supplyAmount,taxAmount,totalAmount}], display{invoiceDate,dueDate,confirmedAt,cancelledAt}. 명세는 lineNo 오름차순, 최대200. 금액2/수량3/단가4자리 문자열, 빈 공간 trim·정규화된 코드, JSON keys정렬·고정UTF-8·구분자·SHA256 lowercase. digest 대상은 **display와 status를 제외한 모든 위 의미 필드**. snapshot에 조회시각을 넣지 않는다. ERP에서 계산된 저장 금액을 쓰고 GW가 계산하지 않는다.

display 날짜는 의도적으로 검토 동일성 판단에서 제외한다(D62). 따라서 금액·거래처·명세 승인을 의미하며 지급일 승인 통제가 아니다. 원문 상태는 source_status와 현재 status 별도 비교. GW GENERAL은 원천 digest가 없다.

읽기 응답 sourceComparison: availability=AVAILABLE/DISABLED/MISSING, contentChanged bool|null, statusChanged bool|null, currentStatus|null. 꺼짐/없음은 비교값null. 상태 변화 confirmed는 “원문 상태 변경·확정”, cancelled는 “원문 취소”, digest 불일치는 “원문 내용 변경”. 과거 승인+변경이면 반드시 “과거 상신본 승인”으로 표시한다.

E-11 상세는 ERP가 자기 현재 snapshot/digest를 만든 뒤 gw.interface를 읽는다. GET 배지를 얻느라 GW가 다시 ERP를 호출하지 않는다. 상세 화면 기존 id 조회는 ERP 안에서 번호로 변환한다. GW→ERP 링크는 코드 번호 검색 경로를 사용하고 임의 외부 URL을 저장하지 않는다. ERP 번호 수정/삭제 후 동일 번호 재사용은 코드 기반 계약의 한계이며 내부 행 식별 동일성을 보증하지 않는다; 이를 숨기기 위해 타업무 ID를 저장하지 않는다.

## 6. 트랜잭션·오류·감사

모든 변경은 공통 인증/CSRF→write_scope 공간잠금→멱등 영수증 확인→대상행 FOR UPDATE→expectedVersion/역할/상태 검사→GW 변경/이벤트/core 감사/영수증을 한 TX로 처리한다. 공간 잠금으로 결재선 편집/담당자 비활성화/초기화와도 직렬화한다. 원천 조회는 ERP 행 잠금 없이 수행. 이미 성공한 동일 키 요청은 버전 검사보다 먼저 저장 응답을 돌려준다. HTTP 상태/오류/본문까지 동일하며 사건 중복 없음.

| TX | 원자 작업/추가 검사 |
|---|---|
| TX-G1 초안 생성·수정·원문/결재선 갱신 | 문서/단계/이벤트. 신규는 공간잠금으로serial할당, 수정은 version+1 |
| TX-G2 상신 | ERP 재조회/비교·활성 단계 확인·원천 중복 검사, 부분UK 최종방어, submission_order할당·상신 이벤트 |
| TX-G3 승인·반려 | 문서→단계seq순 잠금, 현재단계·version 확인, 단계/문서/이벤트 동시 갱신 |
| TX-G4 회수·재상신 생성 | 원문서 잠금. 회수 최초승인0건, 재상신 이전종결·후속없음 검사. 재상신 시 원문서는 불변, 새 문서 첫 사건 RESUBMISSION_CREATED에 연결 |
| TX-G5 게시·철회·정정 | 글 잠금·작성자/공지역할/version 확인. 정정은 새 글 생성·후속유일성 |
| TX-G6 담당자·결재선 | 마스터잠금·사용중/마지막운영자 검사; 템플릿 단계 교체와 version 갱신 |

400 VALIDATION_FAILED `details.fields.<경로>`: 타입·길이·수량·금액·단계1~3·동일담당자·알수없는키·페이지. 401/403/404/410 공통 그대로. 409 PRECONDITION_NOT_MET reason: VERSION_CONFLICT, WRONG_ACTOR, NOT_CURRENT_STEP, PERSON_INACTIVE, PERSON_IN_USE, LAST_BOARD_ADMIN, IMMUTABLE_DOCUMENT, SOURCE_CHANGED, SOURCE_MODULE_DISABLED, SOURCE_MISSING, SOURCE_CANCELLED, ACTIVE_APPROVAL_EXISTS, WITHDRAW_NOT_ALLOWED, SUCCESSOR_EXISTS, ROUTE_INACTIVE. 충돌은 현재 version/현재상태/안전한 동일S 후속번호를 제공. 422 IDEMPOTENCY_CONFLICT 전용. DB 유일성 충돌을500으로 노출하지 않는다.

감사 이벤트 actor_kind/key는 실제 인증에서만(GUEST UUID, MEMBER 식별자 문자열), synthetic person 필드는 별도. 토큰·비밀번호·별칭 저장 없음, core.app_user FK 없음. SEED는 고정 `seed` key, 화면 “합성 이력” 표시. 보존은 업무 세대 수명과 함께하며 기존 core.audit_event 보존/정리 정책을 변경하지 않는다. 재상신·이력 링크는 GW 문서 번호/동일S ID로만 연결한다. core 감사는 사건명/엔티티키/최소 상태 변경만 기록, 게시글·기안 전체 내용을 중복 저장하지 않는다.

## 7. API 계약

prefix `/api/v1/gw`. JSON camelCase, 공통 `{data}`/에러 포맷. 목록 `{data:{rows,total,offset,limit}}`, offset기본0/limit50 최대100, sort allowlist(serial/status/title)와 id tie-break. ID는 프런트 정밀도 손실 없는 문자열. 검색100자·상태/종류 allowlist, 소유권은 query로 바뀌지 않는다. 변경 POST/PATCH/PUT 모두 CSRF/Idempotency-Key, 기존대상은 expectedVersion 양수 필수, 생성은 불필요.

| 경로 | 내용 |
|---|---|
| GET `/dashboard?personId=` | 같은S 활성 역할의 기안초안/진행·현재단계대기·최근종결·게시물. 건수만, 통화합산 없음 |
| GET/POST `/people`; PATCH `/people/{id}` | 코드/이름/직무/활성 관리. 삭제없음 |
| GET/POST `/routes`; GET/PATCH `/routes/{id}` | 코드/이름/활성/steps[{personId}], 전체 명세교체; 코드불변 |
| GET `/sources?kind=&search=&offset=&limit=`; GET `/sources/{kind}/{documentNo}` | ERP 계약 래핑. off는200 `{enabled:false,...}`로 후보없음과 구분. 직접없는상세404 |
| GET `/documents?box=drafts|pending|archive|all&personId=&status=&kind=&search=&offset=&limit=` | drafts는내기안전체, pending은현재역할 현재단계 IN_REVIEW, archive는종결전체; 명칭은 UI필터로 설명. all은같은S전체 |
| POST `/documents` | actingPersonId,title,body,routeId,kind, ERP면sourceNo / 일반이면선택amount,currency. 입력 원천금액금지 |
| GET `/documents/{id}` | 본문·고정snapshot·단계·사건·이전/후속·sourceComparison·version·availableActions |
| PATCH `/documents/{id}` | actingPersonId,expectedVersion,title/body, GENERAL 선택금액. DRAFT만 |
| POST `/documents/{id}/select-route` | actingPersonId,expectedVersion,routeId. DRAFT만 |
| POST `/documents/{id}/refresh-source` | actingPersonId,expectedVersion. DRAFT ERP만; 서버값 교체·사건, 실패면기존값유지 |
| POST `/documents/{id}/submit` | actingPersonId,expectedVersion. 저장된초안과현재원문비교, 새 snapshot 본문입력없음 |
| POST `/documents/{id}/approve`, `/reject`, `/withdraw` | actingPersonId,expectedVersion,reason(반려/회수필수). 현재단계는 서버가 결정 |
| POST `/documents/{id}/resubmit` | actingPersonId,expectedVersion. 새 DRAFT 반환(자동상신없음) |
| GET/POST `/posts`; GET/PATCH `/posts/{id}` | boardKind/status/search/page, 작성역할/제목/본문, 수정DRAFT만 |
| POST `/posts/{id}/publish`, `/withdraw`, `/correct` | actingPersonId,expectedVersion; 철회사유필수; 정정은새DRAFT반환 |

상세 availableActions는 UI편의이며 서버 권한검사를 대체하지 않는다. GET상세 personId가 없으면 액션 판정을 생략하고, 있으면 같은S 역할로 계산한다. 변경 성공은 최신 상세(원문 비교 조회는 선택), 생성201/그 외200. 목록갱신을 기다리기 전에 성공응답 version을 즉시 적용한다. 네트워크오류/5xx는 같은 멱등키로재시도; 입력 변경이면새키. 응답유실 후 GET 서버조회 제공.

## 8. 시드·복사·초기화 계획

기준 읽기에서 ERP invoice_no는 `_column_expression`의 날짜 이동 대상이 아니며 PI-0001 형태를 유지한다. GW 문서/게시번호도 날짜를 넣지 않아 복사 시 유지한다. 같은S UK이므로 다른공간 중복번호는 정상이다. ERP 원천 번호를 임의 재작성하지 않는다.

기본 제안 **업무69행 + gw모듈행1개**. a에서 +1, c에서 +69. main의 SPC/CMMS 시드가 달라지므로 절대합계는 각 단계 실제기준에 더해 보고한다.

| 테이블 | 행 | 예시 |
|---|---:|---|
| person | 4 | 구매담당·팀장·임원·게시판운영 |
| approval_route / route_step | 2 / 3 | 팀장1단계, 팀장→임원2단계 |
| approval_document / approval_step | 8 / 16 | 초안2·진행2(0승인/1승인)·승인2(재상신1포함)·반려1·회수1. 시드문서는2단계 사용 |
| approval_event | 21 | 초안각1, 진행2/3, 승인각4, 반려3, 회수3. 새회차 CREATED 대신 RESUBMISSION_CREATED |
| board_post / board_event | 5 / 10 | 초안1, 게시3(원글/정정 포함), 철회1; 생성/게시/철회 사건 |

ERP 사례는 같은 공간의 실제 시드 매입 원문에서 snapshot을 만든다. 진행2건은 서로 다른 원천. ERP 시드를 수정하지 않으며 최소 후보수/상태를 검증한다. 재상신/반려 이야기는 일반 기안으로 독립시연도 보장한다. 네 담당자는 합성이며 실사용자 승인으로 표현하지 않는다.

복사: gw를SCHEMAS/초기화목록에추가, 부모→자식 복사·역순삭제, self FK 매핑도기존매핑테이블로수행. document/step/event/post 실제시각은 일수이동, snapshot.display의 invoiceDate/dueDate/confirmedAt/cancelledAt는 같은간격으로명시이동. source_digest/ERP번호/의미값/상태/submission_order/회차는 유지. SEED actor_key는seed그대로, 템플릿은SEED이벤트만허용하고 사용자이벤트를다른공간복사하지않는다. 일반초기화도 seed템플릿에서새세대를만들므로 과거실사용자이벤트를새사용자로치환하지않는다. 신세대쓰기중옛ID는404, 이미commit된멱등영수증의구세대재응답은기존core세대계약에맞춰차단검증한다.

## 9. 인수 기준·검증 매핑

| AC | 구현 증거/필수 테스트 |
|---|---|
| 220 | a의8테이블/C22/모듈행/격리·메타데이터·DDL왕복 |
| 221 | 인증없음·CSRF실패·가짜actor키·담당자역할 검사, 합성/실제주체 구분 |
| 222 | ERP interface만 import, 금액변조400, 반환원문스냅샷일치 |
| 223 | 초안후ERP수정→상신409→명시갱신→상신성공 |
| 224 | 제출본문/결재선/source 수정409, 템플릿/담당자명변경과거영향0 |
| 225 | 0/4단계·중복·기안자포함400, 다른역할/뒤단계409 |
| 226 | 같은승인동시2요청·승인/반려경합 한전이, 마지막승인완료1회 |
| 227 | 반려사유필수·새회차·이전불변·중복후속409 |
| 228 | 승인전회수/승인후거부, 승인과회수경합 |
| 229 | 같은ERP원천상신동시2개중1건, UK예외를409변환 |
| 230 | 키/본문/버전·응답유실 재시도, 사건/문서중복0 |
| 231 | 진행중ERP변경·취소·삭제 안내, GW처리로ERP값불변 |
| 232 | ERPoff 신규상신거부, 일반기안/기존결재/게시정상 |
| 233 | E-11 진행우선·최신상신순·원문변경·상태변경·없음·GWoff, 기존ERP회귀 |
| 234 | 공지직무·작성역할·비활성·타공간접근, plain text/XSS |
| 235 | 게시후수정거부·정정원문유지·철회사유/이력 |
| 236 | 다른공간/구세대의문서/담당자/결재선/글ID차단 |
| 237 | 초기화/게스트복사FK·번호·날짜·digest·SEED주체, 실제69행검증 |
| 238 | FS_TODAY와DB날짜차이에도상태동작, Decimal정확성·다통화미합산 |
| 239 | G01~07/ERP배지 실제API브라우저·360px·키보드/오류/미저장·도움말·전체회귀 |

a: 멱등적용도구/test_fs030a·validate_gw·기존검증ID집합·db:validate/build/ERD·R1~6·DDL대조·Codex전용DB왕복. b/c: 전체pytest, vitest, ruff check/format, typecheck/lint/format/build, 전용포트실API스모크(기존포트동시사용금지), seed행수/복사시간. DB/백엔드/프런트미실행검증을완료라고표시하지않는다.

## 10. 실행 순서·승인할 상세

1. **본 모듈·화면 전체 설계 확인** 후에만 FS-030a. 승인 대상은8테이블, 단계1~3/문서상태·source비교계약, 서버단역할검사/감사, 게시정정/철회,69행시드 계획이다.
2. a 착수 시 origin/main 최신head·SPC/CMMS합계·공통파일을재확인. 임시버전 v0.15.0-gw, revision fs030a_gw→fs030b_gw_module. 적용된migration을수정하지않고충돌시통합담당자에게새연결방식인계. 착수 기준 main6350697(FS-040) 104테이블에8개를추가해112테이블. down_revision=fs040_app_review. core.app_review 모듈CHECK도gw허용으로확장하며평가API/런처등록은b에서반영한다.
3. a 보고·승인→b 보고·승인→c 보고·승인. 각단계 현황≤200줄·progress·HANDOFF/README갱신. 업무/DB코드가없는이번설계단계는정적문서검증만한다.
4. 담당자계정관리·조직도·ERP확정통제·위임/병렬결재·파일/댓글·전사대시보드·배포는제외. GW담당자가추가솔루션을착수하지않는다.

### FS-030a 적용 결과

메타데이터 v0.15.0-gw: 112테이블·1,225컬럼·258FK·제약/정책978. 신규 GW8테이블의 DB제약·게스트 복사·모듈 행을 구현했다. 상신 불변/추가 전용 사건/권한/결재 순서 등 SERVICE 정책은 b에서 구현하므로 DB 완료와 구분한다. a 시드 합계는 GW 모듈행1개만 증가(템플릿11,934/게스트11,932), 업무69행은c예정. [실행 검증 보고](../../agent/GW_DB_FS-030a.md).

### FS-030b 구현 반영 (2026-10-04)

main8531c05 기준 headfs029b_cmms_module·v0.17.0·118테이블/270FK 유지. GW API·TX-G1~6·코드 스냅샷/순차결재/게시 불변/역할·멱등/감사, G01~07·ERP E11 읽기 배지·포털 진입/평가 연결을 구현했다. GET people/{id}도 편집·재조회용으로 제공한다. ERP 배지는 별도 GET purchase-invoices/{id}/gw-approval에서 조회하고 선택 전표가 변경되면 새로 읽는다. 상세 events에는 실제 actorKey를 노출하지 않는다.

업무 시드69행·도움말/흐름맵은 c. 현재 새 공간 GW 업무 데이터는 비어 있으며 G07 담당자→G06 결재선→G02 기안을 직접 등록할 수 있다. [검증·AC 근거](../../agent/GW_API화면_FS-030b.md). 상단 설계와 a 적용 결과는 해당 단계의 기록이다.
