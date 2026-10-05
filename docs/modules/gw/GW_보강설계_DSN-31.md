# DSN-31 GW 그룹웨어 보강 설계

작성: 2026-10-05 (Claude Code — D82로 Codex 몫 인수) · 상태: **설계 완료(2026-10-05) — 사용자 확인 대기.** 1단계(기준표·Q1~Q7 확정) + 2단계(3장 규칙 · 4장 DB · 5장 화면 · 6장 교차 조회).
양식: [DSN-00](../../plan/기능기준표_DSN-00.md) · 방침: [ROADMAP-02](../../plan/전체설계우선_전환_ROADMAP-02.md) D81(사람·조직 원천 = HR)·D82 · [DSN-99](../../plan/개발계획_DSN-99.md) Q4(GW 실제 회사 도입은 별도 트랙, W5에는 체험 범위)
입력: [FS-030 결정 D60~69](../../plan/GW도입_전자결재_결정_FS-030.md)(운영 중 설계, `gw` 8테이블·G-01~07), [GW-EXT-01](../../plan/GW확장_협업플랫폼_결정초안_GW-EXT-01.md)·[GW-EXT-A](GW_공유협업_상세설계_GW-EXT-A.md)(실제 도입 설계), [DSN-90 2장](../../plan/통합검증_DSN-90.md)(GW 계약)

---

## 0. GW의 자리 — 두 겹

| 겹 | 범위 | 언제 |
|---|---|---|
| **체험 GW**(이 문서) | 전자결재·게시판·담당자(합성 역할) + 이번 보강 — 공개 전시, 합성 데이터, 개인·게스트 공간 | 일괄 개발 **W5** |
| **실제 도입 GW**(GW-EXT P0~F) | TEAM 공유 공간·실제 계정 권한·문서 열람 권한·외부 메일·전자서명·운영 환경 분리 | 회사 요구값이 정해질 때 별도 트랙(DSN-99 Q4) |

| 영역 | 소유 | GW와의 관계 |
|---|---|---|
| 사원·부서·근태·휴가 | **HR**(D81) | GW 담당자·조직은 HR에서 가져온 스냅샷 |
| 전사 공지 표시·집계 | **EIP**(DSN-28 Q1) | GW가 `published_notices` 제공 |
| ERP 문서 확정 | **ERP** | GW는 결재 근거만, 교차 쓰기 없음 |
| ELB 신청 승인 | **ELB 자체**(DSN-27 Q2) | GW 결재 대상 아님 |

## 1. 기준표

"지금" = 운영 중(FS-030b, `gw` 8테이블). ✓ 있음 · △ 일부 · ✗ 없음.

### 영역 01 — 전자결재

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F01 | 일반 기안(제목·본문·금액 선택) | 필수 | ✓ | ○ | D62 |
| GW-F02 | ERP 매입 전표 결재(상신본 고정·digest·원문 차이 표시) | 필수 | ✓ | ○ | D62·D65 |
| GW-F03 | 결재 대상 확장 — ERP 발주·지출결의, PLM ECO | 표준 | ✗ | ○ | PLM은 이미 `approvals(doc_ref)`를 읽는다(DSN-24) |
| GW-F04 | 순차 1~3단계·반려·회수·재상신(새 회차) | 필수 | ✓ | ○ | D63·D64 |
| GW-F05 | 결재선 템플릿 | 필수 | ✓ | ○ | |
| GW-F06 | 병렬·합의(필수/참고) | 표준 | ✗ | ○ | GW-EXT C |
| GW-F07 | 전결 규칙(문서 유형·금액별 단계 생략) | 표준 | ✗ | ○ | GW-EXT C |
| GW-F08 | 위임(부재 기간 대리 결재) | 표준 | ✗ | ○ | GW-EXT C |
| GW-F09 | 반복 기안 자동 생성·자동 승인 | 고급 | ✗ | ✕ | 제안 제외 |
| GW-F10 | 결재 문서 인쇄(상신본 + 결재 이력) | 표준 | ✗ | ○ | 브라우저 인쇄. 서버 PDF는 실제 도입 트랙 |

### 영역 11 — 게시판

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F11 | 공지·자유 게시, 게시 후 불변·정정·철회 | 필수 | ✓ | ○ | D67 |
| GW-F12 | EIP 공지 제공 `published_notices(limit)` | 필수 | ✗ | ○ | DSN-28 Q1 |
| GW-F13 | 댓글(수정은 이력, 삭제는 표시) | 표준 | ✗ | ○ | |
| GW-F14 | 첨부 파일 | 표준 | ✗ | ✕ | 파일 저장소 없음(CMMS F05·RWS F04와 같은 기준). 실제 도입 트랙 B |

### 영역 21 — 사람·조직

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F21 | 담당자(합성 체험 역할) 선택 | 필수 | ✓ | ○ | D61 |
| GW-F22 | HR에서 가져오기 — 사원 → 담당자, 부서 → 조직 스냅샷 | 필수 | △ | ○ | D81. `gw.person.hr_employee_code`는 목표 DB에 있음 |
| GW-F23 | 조직도 보기(HR 부서 계층 조회) | 표준 | ✗ | ○ | 조회만 |

### 영역 31 — 협업

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F31 | 일정(개인·부서, 참석자) | 표준 | ✗ | ○ | |
| GW-F32 | 내부 알림함(결재 도착·반려·회수·공지, 읽음 표시) | 표준 | ✗ | ○ | 외부 메일·푸시는 실제 도입 트랙 F |
| GW-F33 | 채팅·메시지 | 표준 | ✗ | ○ | 실시간 연결·부하 |

### 영역 41 — 연계·현황

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F41 | ERP·PLM 결재 배지 `approvals(doc_ref)` | 필수 | ✓ | ○ | D66 |
| GW-F42 | GW 업무 현황(G-01) | 필수 | ✓ | ○ | |
| GW-F43 | 공통 4종 `enabled`·`monthly_summary`·`pending_tasks(hr_employee_code)`·`lookup` | 필수 | △ | ○ | DSN-90 2-1 |
| GW-F44 | ERP 확정 통제(ERP 문서 종류별 "GW 승인 필수" 정책, ERP 소유) | 고급 | ✗ | ○ | GW-EXT GX-07 |

### 영역 51 — 실제 회사 도입(별도 트랙)

| ID | 기능 | 수준 | 지금 | 범위 | 비고 |
|---|---|---|---|---|---|
| GW-F51 | TEAM 공유 공간·멤버십·초대(core) | 고급 | ✗ | ○ | GW-EXT A |
| GW-F52 | 실제 계정 ↔ 직원 연결·업무 권한·문서 열람 권한 | 고급 | ✗ | ○ | GW-EXT A |
| GW-F53 | 외부 메일·알림 공급자 연동 | 고급 | ✗ | ✕ | GW-EXT F(별도 트랙) |
| GW-F54 | 전자서명·위변조 방지 증빙 | 고급 | ✗ | ✕ | GW-EXT F(별도 트랙) |

## 2. 범위 요약

| 영역 | 기능 | 필수 | 표준 | 고급 | 범위 ○ | Q | ✕ |
|---|---:|---:|---:|---:|---:|---:|---:|
| 01 전자결재 | 10 | 4 | 5 | 1 | 9 | 0 | 1 |
| 11 게시판 | 4 | 2 | 2 | 0 | 3 | 0 | 1 |
| 21 사람·조직 | 3 | 2 | 1 | 0 | 3 | 0 | 0 |
| 31 협업 | 3 | 0 | 3 | 0 | 3 | 0 | 0 |
| 41 연계·현황 | 4 | 3 | 0 | 1 | 4 | 0 | 0 |
| 51 실제 도입 | 4 | 0 | 0 | 4 | 2 | 0 | 2 |
| **합계** | **28** | **11** | **11** | **6** | **24** | **0** | **4** |

## 3. 기능 규칙 (범위 24)

공통: **GW는 결재·게시·협업의 주인이고 사람·조직은 HR, 공지 집계는 EIP, 문서 확정은 ERP·PLM이 주인이다.** 교차 쓰기 없음. 체험(SIMULATION)은 합성 담당자 역할 선택(D61), 실제 도입(IDENTITY)은 서버 인증 주체 → 직원 연결로만 담당자 결정.

| 묶음 | 기능 ID | 규칙 |
|---|---|---|
| 결재 대상 (Q2) | F01~F03 | 일반 기안 · ERP 매입 전표 · **ERP 발주·지출결의 · PLM ECO**. 원천은 상신 때 스냅샷·digest로 고정(D62·D65), 원천당 진행 1건. ERP는 `approval_documents(kind)`·`approval_document(kind, no)`, PLM은 `eco_for_approval(eco_no)` 제공(신규) |
| 결재 정책 v2 (Q3) | F04~F08 | 같은 단계 APPROVER 전원 승인 시 다음 단계, 한 명 반려면 종결 · CONSENT 반대는 반려, REFERENCE는 의견만 · **전결**: 상신 때 (유형·통화·금액·월) 규칙을 고정, 최종 단계 뒤 SKIPPED · **위임**: 처리 순간 유효 재검사, 연쇄·자기 결재·기안자 우회 금지, 원 담당자와 수행자 모두 기록. v1 문서는 그대로 |
| 인쇄 | F10 | 상신본 + 결재 이력(브라우저 인쇄). "전자서명 아님" 표시 |
| 게시판 (Q4) | F11~F13 | 게시 후 불변·정정·철회(D67) · 부서 대상 공지(ORG) · EIP에 `published_notices(limit)` · **댓글**: 원문 승인 범위를 바꾸지 않음, 수정은 revision, 삭제는 표시 |
| 사람·조직 (D81) | F21~F23 | "HR에서 가져오기": HR 사원 → 담당자(`hr_employee_code`), HR 부서 → 조직 단위(코드 = HR 부서 코드). 조직도는 조회. 상신 때 조직 스냅샷(이후 이동으로 덮지 않음) |
| 협업 (Q5) | F31~F33 | **일정**: 개인·부서, 참석 응답 · **알림함**: 업무 변경 트랜잭션 안에서 (받는 사람, 사건 키) 1건, 읽음 · **채팅**: 대화방 순번(대화방 잠금)·재전송 키로 중복 0, 나간 뒤 수신 차단. 저장은 HTTP, 실시간 전송은 개발 때 선택 |
| 연계 (Q6) | F41~F44 | `approvals(doc_ref)` 배지(ERP·PLM) · 공통 4종 · **ERP 확정 통제**: ERP 정책 REQUIRED면 모든 확정 경로에서 GW 최종 승인·digest 일치를 확인하고 증빙 저장, 아니면 거부(GW 꺼짐도 거부). 기본 OFF, 소급 없음 |
| 실제 도입 A (Q1) | F51·F52 | TEAM 공간(core) · 멤버십(마지막 OWNER 보호)·초대(해시 토큰·1회·만료) · 직원 계정 연결 · 업무 권한(직무 ≠ 권한) · 문서 열람 권한(관리자도 본문 ACL 우회 없음) · 재배정. **목표 DB에만 반영, 개발은 별도 트랙(DSN-99 Q4)** |

## 4. DB

목표 파일 `schema-target.json`(`tools/apply_dsn31.py`, apply_dsn30 다음·apply_dsn90 앞, 멱등). GW 8 → **24테이블**(체험 10 + 조직 1 + 실제 도입 A 5), core 3, ERP 2 → 목표 **361테이블**. 업무 스키마 간 FK 0, GW → core 사용자 FK 0(계정은 `subject_key` 문자열).

### 4-1. 새 테이블 — 체험 GW·조직

| 테이블 | 한글명 | 영역 | 목적·규칙 |
|---|---|---|---|
| `gw.authority_rule` | 전결 규칙 | 결재 | F07(Q3). 문서 유형·금액·통화별로 생략할 단계. 상신 때 문서에 규칙 id를 고정(이후 규칙이 바뀌어도 그대로) |
| `gw.delegation` | 위임 | 결재 | F08(Q3). 부재 기간 대리 결재. 연쇄 위임·자기 결재·기안자 우회 금지(SERVICE). 원 담당자와 실제 수행자를 사건에 함께 남긴다 |
| `gw.comment` | 댓글 | 게시판 | F13(Q4). 게시글·결재 문서의 댓글. 원문 승인 범위를 바꾸지 않는다. 수정은 revision, 삭제는 표시 |
| `gw.comment_revision` | 댓글 수정 이력 | 게시판 | F13. 수정 전 내용(추가만) |
| `gw.calendar_event` | 일정 | 협업 | F31(Q5). 개인·부서 일정. 부서 일정의 부서는 조직 단위(HR 부서 스냅샷) |
| `gw.event_attendee` | 일정 참석자 | 협업 | F31. 참석 응답 |
| `gw.notification` | 알림 | 협업 | F32(Q5). 내부 알림함. 업무 변경 트랜잭션 안에서 생성(사건 키로 중복 0). 외부 메일·푸시는 실제 도입 트랙 F |
| `gw.chat_channel` | 대화방 | 협업 | F33(Q5). 1:1·그룹 대화. 저장은 HTTP(추가만), 실시간 전송 수단은 개발 때 부하 확인 후 선택 |
| `gw.chat_member` | 대화방 참여자 | 협업 | F33. 참여·나감·읽음 커서. 나간 뒤 새 메시지 수신 차단 |
| `gw.chat_message` | 메시지 | 협업 | F33. 대화방별 순번(재연결·중복 제거 기준). 추가만, 정정은 새 메시지 |
| `gw.organization_unit` | 조직 단위 | 조직(D81) | F22·F23(D81). HR 부서를 'HR에서 가져오기'한 스냅샷(코드 = HR 부서 코드). 문서 권한·부서 일정·게시 대상 판정용. 순환 금지(SERVICE) |

### 4-2. 새 테이블 — 실제 도입 A(설계만, 개발은 별도 트랙 — Q1)

| 테이블 | 한글명 | 영역 | 목적·규칙 |
|---|---|---|---|
| `gw.collaboration_settings` | 협업 설정 | 실제 도입 A | F51(Q1, 실제 도입). TEAM 공간 GW 초기화 1회·권한 버전(권한이 바뀌면 +1, 캐시 무효화) |
| `gw.person_identity_binding` | 직원 계정 연결 | 실제 도입 A | F52(Q1). 실제 계정(subject) ↔ GW 담당자. 활성 후 subject·person 변경 금지, 같은 직원을 다른 계정에 다시 연결 금지 |
| `gw.role_grant` | 업무 권한 | 실제 도입 A | F52(Q1). TEAM 업무 권한 원천(직무 표시값은 권한 아님) |
| `gw.document_reader` | 문서 열람 권한 | 실제 도입 A | F52(Q1). 기밀 결재 문서의 추가 열람자. 읽기만, 결재 권한 아님 |
| `gw.step_assignment` | 결재 재배정 | 실제 도입 A | F52(Q1). 퇴사·장기 부재 시 단계 담당자 재배정 사건. 원 단계 person_id는 바꾸지 않고 최신 회차를 읽는다 |
| `core.workspace_membership` | 공간 멤버십 | 실제 도입 A | F51(Q1, 실제 도입). TEAM 공간 회원·역할. 세대 복사 대상 아님. 마지막 OWNER 제거 금지(SERVICE) |
| `core.workspace_invitation` | 공간 초대 | 실제 도입 A | F51(Q1). 기존 계정 대상 초대. token은 해시만 저장, 1회·만료·철회·재발급 |
| `core.team_creation_receipt` | TEAM 생성 영수증 | 실제 도입 A | F51(Q1). TEAM 생성 멱등(아직 S가 없어 계정 기준). 개인 공간 초기화와 무관하게 유지 |

### 4-3. 새 테이블 — ERP 확정 통제(ERP 소유, Q6)

| 테이블 | 한글명 | 영역 | 목적·규칙 |
|---|---|---|---|
| `erp.approval_policy` | 결재 확정 통제 | ERP 확정 통제 | F44(Q6). ERP 문서 종류별 GW 승인 필수 정책(ERP 소유). 기본 OFF, 적용일 이후 새 확정만, 과거 확정본 소급 없음 |
| `erp.approval_evidence` | 결재 확정 증빙 | ERP 확정 통제 | F44(Q6). REQUIRED 정책으로 확정할 때 ERP가 GW 승인을 읽어 검사한 결과(ERP 트랜잭션 안에서 저장). GW에는 쓰지 않는다 |

### 4-4. 기존 표 변경

| 대상 | 변경 | 이유 |
|---|---|---|
| `gw.approval_document` | 문서 유형 + `ERP_PO`·`ERP_EXPENSE`·`PLM_ECO`(원천 종류 PURCHASE_ORDER·EXPENSE_CLAIM·ECO), 원천 상태 허용 값 자유화, 진행 중 1건 UK를 일반 기안 외 전체로 · `policy_version`(1/2)·`authority_rule_id`·`auth_mode`(SIMULATION/IDENTITY)·기안 당시 조직 스냅샷 | Q2·Q3·Q1 |
| `gw.route_step`·`gw.approval_step` | `participant_role`(APPROVER/CONSENT/REFERENCE) · **단계 순번 유일 키 제거**(같은 단계 여러 명, 사람 유일 키는 유지) · 단계에 조직 스냅샷 · `approval_step (S, document_id, id)` UK(재배정 복합 참조) | Q3 병렬·합의 |
| `gw.approval_event` | 사건 CONSENTED·OPPOSED·SKIPPED·STEP_REASSIGNED·READER_GRANTED·READER_REVOKED · `on_behalf_of_person_id`(위임)·`details` | Q3·Q1 |
| `gw.board_post` | `visibility`(WORKSPACE/ORG)·`audience_org_id` | 부서 공지 |
| `gw.person` | `organization_unit_id`(HR 부서 스냅샷) | D81 |
| `core.app_user` | `subject_key` uuid(서버 생성·불변, UK) | Q1 |
| `core.workspace` | 종류 + `TEAM`(이름 필수)·`name`·`access_version` | Q1 |
| `core.auth_session` | `active_workspace_id`·`context_version`·추가 인증(`assurance_*`) | Q1 |

GW-EXT A의 `person_assignment`(소속 이력)는 D81로 두지 않는다 — 소속 이력은 HR 발령이 원천이고, GW는 현재 조직 스냅샷과 상신 당시 조직 스냅샷만 가진다.

## 5. 화면 목록

기존 G-01~07 + 신규. 화면 접두어 **G**.

| 화면 | 이름 | 패턴 | 주 테이블 | 기능 ID | 범위 |
|---|---|---|---|---|---|
| G-01 | 업무 현황 | D | (조회) | F42 | 기존 |
| G-02 | 기안함 | L+FormPanel(유형: 일반·매입·발주·지출결의·ECO) | approval_document | F01~F03 | 기존 확장 |
| G-03 | 결재함 | L+DetailPanel(병렬·합의·위임 표시) | approval_step·approval_event | F04·F06·F08 | 기존 확장 |
| G-04 | 결재 문서함 | L+DetailPanel wide(인쇄·댓글) | approval_document·comment | F04·F10·F13 | 기존 확장 |
| G-05 | 게시판 | L+DetailPanel(부서 공지·댓글) | board_post·comment | F11~F13 | 기존 확장 |
| G-06 | 결재선 | S(참여 구분) | approval_route·route_step | F05·F06 | 기존 확장 |
| G-07 | 체험 담당자 | S(HR에서 가져오기) | person | F21·F22 | 기존 확장 |
| G-08 | 전결 규칙 | S | authority_rule | F07 | 신규 |
| G-09 | 위임 | L+FormPanel | delegation | F08 | 신규 |
| G-10 | 조직도 | V(트리, HR 부서) | organization_unit | F23 | 신규 |
| G-11 | 일정 | V(월·주 달력) | calendar_event·event_attendee | F31 | 신규 |
| G-12 | 알림함 | L | notification | F32 | 신규 |
| G-13 | 채팅 | 특수(대화 목록 + 대화창) | chat_channel·chat_member·chat_message | F33 | 신규 |
| E-xx | ERP 결재 확정 통제 | S(ERP 화면) | erp.approval_policy·approval_evidence | F44 | ERP 신규 |
| — | 실제 도입 A 화면 9개 | [GW-EXT A 화면 설계](../../ui/화면설계_공유공간_GW-EXT-A.md) | — | F51·F52 | 별도 트랙 |

체험 화면 수 **14**(GW 13 + ERP 1), 실제 도입 9(별도 트랙).

## 6. 교차 조회

| 방향 | 함수 | 용도 |
|---|---|---|
| GW 제공 | `approvals(doc_ref)`(있음, 유형 확장) · `published_notices(limit)` · 공통 4종 | ERP·PLM 배지·ERP 확정 통제 · EIP 공지 · EIP |
| GW 읽음 | ERP `approval_documents(kind)`·`approval_document(kind, no)`(있음, 종류 PURCHASE_ORDER·EXPENSE_CLAIM 추가) · **PLM `eco_for_approval(eco_no)`(신규)** · HR `employees`·`departments` | 결재 원천 스냅샷 · 사람·조직 |
| core 제공(실제 도입) | `membership(subject_key)`·`members()`·`security_events()`(GW-EXT A §7) | TEAM 권한 확인 |

> 넘길 것(DSN-90 7-2에 반영): **ERP** `approval_document`에 발주·지출결의 종류, 확정 통제 정책·증빙 화면 · **PLM** `eco_for_approval` 제공 · **HR** 변경 없음 · **EIP** 변경 없음(공지 표시 그대로).

## 7. 결정 질문 (하나씩)

| # | 질문 | 제안 |
|---|---|---|
| Q1 | **목표 DB 범위** — 실제 도입 A(TEAM 공간·멤버십·초대 core 3, 직원 연결·업무 권한·문서 열람·재배정 GW 7)를 (a) 지금 목표 DB에 넣지 않고 GW-EXT 문서로 둔다(별도 트랙 시작 때 반영) (b) 지금 목표 DB에 넣는다(개발은 별도 트랙) | **(a)** — 목표 DB = 일괄 개발 범위. (b)면 core `workspace`·`auth_session` 변경이 W0~W6 마이그레이션에 섞인다 |
| Q2 | **결재 대상 확장** — ERP 매입 + 일반 기안에 ERP 발주·지출결의, PLM ECO 추가(ELB는 자체 승인 유지) | 포함 |
| Q3 | **결재 확장(체험 범위)** — 병렬·합의, 전결 규칙, 위임 | 모두 포함(반복 자동 결재는 제외) |
| Q4 | **댓글** 포함(첨부는 제외) | 포함 |
| Q5 | **협업** — 일정, 내부 알림함, 채팅 | 일정·알림함 포함, 채팅 제외 |
| Q6 | **ERP 확정 통제** — ERP가 문서 종류별 정책(OFF/REQUIRED)을 갖고, REQUIRED면 GW 최종 승인(상신본 digest 일치) 없이는 확정 거부. 기본 OFF, 과거 확정본 소급 없음 | 포함(ERP 쪽 설정 표 1개) |
| Q7 | 범위 확정 — 포함 13 + Q 결과, 제외: 반복 자동 결재, 첨부, 외부 메일, 전자서명(+ Q1·Q5) | 제안대로 |

### 7-1. 결정 기록 (2026-10-05 사용자 확정)

| # | 결정 |
|---|---|
| Q1 | **실제 도입 A(TEAM 공간·멤버십·초대·직원 계정 연결·업무 권한·문서 열람·재배정)를 지금 목표 DB에 넣는다**(제안은 넣지 않음). 개발은 DSN-99 Q4대로 별도 트랙 |
| Q2 | 결재 대상 확장(ERP 발주·지출결의·PLM ECO) 포함 |
| Q3 | 병렬·합의·전결·위임 모두 포함 |
| Q4·Q5 | 댓글·일정·알림함 포함, **채팅도 포함**(제안은 제외) |
| Q6 | ERP 확정 통제 포함(ERP 소유) |
| Q7 | 범위 24/28(제외: 반복 자동 결재, 첨부, 외부 메일, 전자서명) |
