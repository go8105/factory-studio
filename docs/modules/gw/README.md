# GW — 전자결재·게시판

2026-10-18 **[GW-READY-02 실사용 구현 진행](../../agent/GW_실사용구현_GW-READY-02.md)**: 전체 설계 승인 후 MFA·기본 복구·세션 관리·회사 운영 정책과 정적 도움말 구현/합성 검증. 긴급 복구·SSO·백업/보관·최종 인수는 남아 있으며 main·원격·운영 미반영. 아래01 확인 대기는 당시 이력이다.

2026-10-18 **[GW-READY-01 실사용 보안·운영·UI 설계](../../agent/GW_실사용설계_UI검토_GW-READY-01.md)**: GitHub GW 비교·10인 기본안·MFA/복구/선택형 SSO·운영 기준·DB/API/제안 Excel·검토 화면 완료. 전체 설계 확인 대기이며 제품 미구현. 로컬 main 2be292e·현재 DB 유지, 원격/배포 없음.


2026-10-18 **[GW-COMPANY-05 WMS 통합·10인 인수 검증](../../agent/GW_WMS통합_인수검증_GW-COMPANY-05.md)**: schema0.27/210표·merge head·데이터 보존/폐쇄 복원·10인 HTTP·전체 회귀 확인. 로컬 main 반영, 원격/배포 없음. 실제 회사 인수는 MFA·복구/보존·담당자/환경 조건 미충족으로 미완료. 아래04의 WMS 미통합 안내는 당시 이력이다.

2026-10-17 **[GW-COMPANY-04 회사 화면·협업 권한](../../agent/GW_회사화면_협업권한_GW-COMPANY-04.md)**: 회사63경로·G-01~13·도움말 연결, 합성 Chrome 대표 업무와390px/연결회수 확인. 로컬 GW 브랜치 검증이며 main/WMS 통합·실운영 인수는05 후속, 원격/배포 없음. 아래03의 업무 미공개 안내는 당시 상태다.

2026-10-17 **[GW-COMPANY-03 직원 연결·업무 권한 완료](../../agent/GW_직원연결_업무권한_GW-COMPANY-03.md)**: 준비 관리 API/내부 결재·게시 서비스·권한회수/재배정, 관련147·최종3/도구139/공식ruff·DDL0. 회사 화면·전체63업무 공개는04 후속, 실운영 인수는05다. main/원격/배포 미반영. 병행 WMS main과의 스키마/head 통합은 별도 검증 필요.

2026-10-17 사용자 통합 설계 승인 → **GW-COMPANY-02 회사 인증 기반 구현·로컬 검증 완료**. 보안5표/회사·세션 게이트/본인 상태 조회, 회사 업무63경로는 후속ACL완료 전 차단. 관련API131/도구139·왕복DDL0/198원장hash보존. [검증](../../agent/GW_회사인증_기반검증_GW-COMPANY-02.md). 회사 GW 실운영·회사 UI 완료가 아니다. main/원격/배포 미반영.

2026-10-17 [회사 인증·권한 통합 설계 GW-COMPANY-01](회사인증_권한_통합설계_GW-COMPANY-01.md) 작성: 현행 core.company/HR/Flow 재사용, GW 직원 연결·역할·객체 ACL·협업63경로 대조. **최초 작성 당시 설계 확인 대상**이었으며 현재 구현 상태는 위02/03 기록이 우선한다. 기존 GW-EXT-A의 신규 TEAM/조직 가정과 달라 구현 전 이 개정안을 확인한다.

## 현재 도움말 기준 · 2026-10-12

현재 G-01~13은 합성 담당자 체험이다. 이전 G-14/15 프로젝트·내 업무는 Factory Flow로 독립 이관됐고 현행 /work-os를 사용한다. 공개 제품은 개인/게스트 담당자 체험이며, 회사 인증·권한은 전용 브랜치에서 단계별 구현 중이다. 회사 UI·전체 업무 공개 및 실운영 인수는 완료하지 않았다. Flow·내 근무 회사 기록과 구분한다. [제품 도움말 구현 대조](../../agent/제품도움말_구현대조_HELP-01.md).

> **2026-10-09 GW-a~e 체험 보강 완료**(Codex, D83). 외부 원문 제공 의존성과 인쇄 미검증은 아래 최신 항목 참고. **2026-10-05 DSN-31 보강 설계**(Claude, D82) — [GW_보강설계_DSN-31.md](GW_보강설계_DSN-31.md). 체험 GW(일괄 개발 W5)와 실제 도입 GW(GW-EXT, 별도 트랙)를 나눈다. 사람·조직 원천은 HR(D81).

## 이전 기준 (2026-10-04, FS-030b)

- 상태: **FS-030b API·G-01~07·ERP 배지 구현 완료, c 시작 확인 대기**. 로컬 미배포; 업무 시드/도움말은 c에서 추가.
- 기준 브랜치 `codex/fs-030-gw`, main `8531c05`(a 병합·SPC 시드·CMMS DB)까지 fast-forward. “진행해줘”로 결정서, “구현 진행해줘”로 전체 설계 승인을 기록했다.
- [결정 D60~D69](../../plan/GW도입_전자결재_결정_FS-030.md) · [모듈 설계](GW_모듈설계_FS-030.md) · [화면 G-01~07](../../ui/화면설계_GW_FS-030.md).
- 범위: 일반 기안/ERP 매입 스냅샷의 순차 결재, 합성 담당자 역할 체험, 공지·자유 글. 실제 직원 계정·전자서명·ERP 확정 통제 제외.
- DB 완료: gw 8테이블, 현재 전체 head `fs029b_cmms_module`(스키마 v0.17.0), b는 migration 변경 없음. [검증 보고](../../agent/GW_DB_FS-030a.md). 구현: API `/api/v1/gw`, UI `/gw/*`; 도움말 `gw/g-01~07`은 c 예정. [b 보고](../../agent/GW_API화면_FS-030b.md).

### 제공 조회 함수 — 구현됨

| 함수 | 반환 | 소비 |
|---|---|---|
| `enabled(connection, scoped)` | bool | ERP/EIP |
| `approvals(connection, scoped, document_refs)` | 원천 종류·번호별 진행 중 우선/최신 종결 결재, 비교용 상신 digest·상태. 꺼짐 None, 기록 없음 null | ERP E-11 상세 배지 |

### 읽는 조회 함수 — ERP 제공 구현됨

`fs.erp.interface.approval_documents` / `approval_document` / `approval_source_digest`. 원문 조회·정규화 계약은 ERP가 소유한다. 기존 WMS용 함수는 바꾸지 않는다. ERP README 제공 표는 **구현과 같은 커밋**에서 갱신한다. interface 사이 재귀 호출·교차 쓰기·교차 FK 없음.

### 다음 단계

FS-030b 결과 확인 → FS-030c 업무69행 시드/도움말/흐름맵/통합 검증. 각 단계 보고 후 확인 대기. Codex 전용 DB만 사용하며 push·운영 반영은 제외한다.

### 확장 설계 검토 (2026-10-05)

실제 회사 도입 목표의 [GW-EXT-01 결정 초안](../../plan/GW확장_협업플랫폼_결정초안_GW-EXT-01.md)을 작성했다. 공유 공간/권한·고급 결재·파일/PDF·인사/협업·ERP 통제/EIP 계약·외부 연동과 운영 준비를 단계화했다. 사용자 “상세 설계 진행해줘”로 범위/순서 승인. [P0/A 상세 설계 묶음](../../plan/GW확장_상세설계검증_GW-EXT-A.md)을 작성했고 전체 설계 확인 대상이다. 현재 구현 범위는 FS-030b 그대로이며 c도 아직 미착수다.

## GW-b 정책 v2 (2026-10-09)

신규 문서는 서버에서 `policy_version=2`로 생성한다. 기존 v1은 전결·위임을 적용하지 않고 순차 결재를 유지한다. 상세 정책·검증·제약은 [GW-b 결과](../../agent/GW_결재확장_GW-b.md).

`approvals()`는 PURCHASE_INVOICE·PURCHASE_ORDER·EXPENSE_CLAIM·ECO를 지원한다. 한 종류의 배치는 기존처럼 번호 키를 유지하며 혼합 종류의 배치는 `종류:번호` 키를 사용한다(같은 번호의 원천 충돌 방지). 저장된 GW 증빙만 읽고 외부 솔루션을 재조회하지 않는다.

원문 소비 계약: ERP `APPROVAL_KINDS`에 구현한 종류를 선언하면 해당 종류의 `approval_documents()`·`approval_document()`를 사용한다. 선언이 없으면 기존 PURCHASE_INVOICE만 연결한다. PLM `eco_for_approval(c, scoped, no)`가 있으면 ECO 번호 직접 입력으로 조회한다. 모두 꺼짐=None, 없음={found:false}, 있음={found:true,snapshot,digest,status}로 구분한다. snapshot 금액은 totalAmount/currency 쌍(금액 없는 ECO는 모두 없음)이며 결재 증빙은 동일 digest 계약을 따른다. 현재 저장소의 ERP 발주·경비와 PLM 제공은 미구현이며 GW 소비 측 계약 테스트에서만 mock으로 검증했다. ERP 확정 통제는 ERP 소유 작업이다.

## GW-c 조직·HR 연계 (2026-10-09)

G-07 담당자는 공통 MasterScreen으로 관리하고 `GET /hr-preview`에서 HR 사원·부서 및 GW 스냅샷을 확인한 뒤 `POST /import-hr`로 선택한 재직 사원을 가져온다. `previewDigest`·`employeeCodes`를 보내며 미리보기 이후 원천/담당자 변경은409 재확인한다. 부서는 전체 반영, 담당자는 HR 사원 코드로 같은 ID를 갱신한다. 신규 STAFF·기존 직무/활성 보존, 자동 퇴직 비활성화/자동 동기화 없음. 일반 목록은 페이지 조회, 역할 선택은 `/people-options` 전체 조회를 사용한다.

G-10은 현재 HR 계층과 마지막 GW 조직을 읽기 전용으로 비교한다. HR 꺼짐/미개방은0건과 구분하고 마지막 값을 유지한다. HR `employees(status=None)`·`departments()`만 소비하며 직접 HR SQL·교차쓰기·FK는 없다. 상신 조직 기록은 이동 이후에도 불변이다. 결과·검증·제약은 [GW-c 결과](../../agent/GW_조직HR연계_GW-c.md). 다음은 사용자 확인 후 GW-d 협업이다.

## GW-d 협업 계약 (2026-10-09)

- `GET/POST /comments`, `PATCH /comments/{id}`, `POST /comments/{id}/delete`: POST/DOCUMENT 대상. 수정 전 revision 추가, 삭제 내용은 저장하되 API에서는 숨김. 작성자만 변경, 원문 버전 불변. 댓글·이력에 대상 공지의 현재 조직 열람 판정 적용.
- 게시글 `visibility=WORKSPACE|ORG`, `audienceOrgId`: NOTICE만 ORG, 활성 GW 조직 필요. 작성자/현재 소속 조회, 선택 역할 없는 조회는 WORKSPACE만. 정정 초안에도 공개 범위 유지.
- `GET/POST /calendar`, `GET/PATCH /calendar/{id}`, `POST .../cancel|respond`: 개인/부서, 참석 응답. 기간 교차 `[start,end)`, 조회 최대93일, 등록자 편집·취소, 이벤트 version 확인. 수정은 참석자/응답 재설정, 취소는 이력 보존. 부서 ID는 생성 때 고정, 같은 부서 범위 편집 시 소속 이동으로 재배정하지 않음. 종일 한국 자정 경계.
- `GET /notifications`, `POST /notifications/{id}/read`: 사람별/50개 페이지. 현재 공지·일정 열람을 페이지 처리 전에 재검사. 업무와 동일 TX 안 `recipient,event_key` ON CONFLICT 중복 제거. 읽음 시각 최초 값 유지. 결재 상신/단계 전환·종결, 공지 게시, 댓글 등록, 일정 생성/수정/취소.
- `GET/POST /channels`, `GET/POST /channels/{id}/messages`, `POST .../read|leave`: 1:1/그룹, 고정 명단2~100명. 메시지 채널행 FOR UPDATE, 증가 seq, (channel,author,clientKey) 유일 + 내용 동일 재전송 확인. 공간 잠금·CSRF·멱등 영수증/감사 공통 action. 나간 후 전체 메시지 읽기·전송 차단. HTTP 저장 + 화면 활성 때3초 조회, 순번 cursor/100개 chunk, 오류 때 수동 재연결. 읽음 수동 단조 증가.
- 제공 interface: `published_notices(connection,scoped,limit=10)`은 선택 역할 없는 EIP에 전체 공간 공지만, `monthly_summary(...,month)` KST 상신월 통계, `pending_tasks(...,hr_employee_code)` 현재 본인/위임 결재 대기, `lookup(...,code)` 문서/전체 게시 공지. 비활성 GW는 모두 None, 조회 가능 빈 결과와 구분. 제공 측은 타 업무 interface 호출 안 함.
- common action의 선택 `authorize` 훅으로 영수증 재사용 전에도 현재 열람/멤버십을 재검사한다. 탈퇴 후 과거 전송 캐시 및 부서 이동 후 알림 읽음 캐시는 차단하며, 나가기 확인 재시도는 유지한다.
- 실제 회사 계정/TEAM ACL·외부 메일/푸시·첨부·WebSocket/SSE·참여자 재초대는 미구현/범위 밖. GW-e에서 체험 시드와 유데이터 세대 복사·정리를 추가 검증한다. DB/schema0.21.0/headgw_a_dsn31 유지.

## GW-e 시드·도움말 (2026-10-09)

GW-a~e 체험 범위를 현재 GW 19개 표에서 구현했다. 과거 FS-030c의 69행 계획은 DSN-31 확장을 반영한 **98행** 시드로 대체한다. `sv-20261009-gw1`, 조직 4·HR 연결 담당자 10, 결재 초안/병렬 대기/전결·위임/기존 순차 이력, ERP 매입 snapshot, 전체·부서 공지, 댓글 수정·삭제 표시, 일정·응답·알림·채팅을 포함한다. G-01~13 도움말과 공통 안내, HR → GW 조직 → 결재 → 협업 흐름을 정적 파일로 제공한다. [개발 결과](../../agent/GW_시드도움말_GW-e.md), [현재 통합 계약](../../plan/통합검증_DSN-90.md#9-gw-체험-구현-계약-gw-e-2026-10-09).

새 템플릿을 만들어야 새 게스트 체험에 적용된다. 기존 운영 템플릿이나 종결 이력을 수정하지 않는다. 실제 도입 A/TEAM·계정 권한, ERP F44와 신규 ERP·PLM 원천 제공은 후속 단계다.

## GW-PROJECT-01 프로젝트·업무 보드 (2026-10-10)

[전체 범위 설계 초안](GW_프로젝트업무보드_설계초안_GW-PROJECT-01.md): 회사 공동 보드·그룹/하위 업무·담당자/상태/일정·테이블/칸반/캘린더/기본 간트·내 업무·댓글/이력 제안. 기존 공지 게시판/체험 담당자와 분리. 사용자 전체 승인 후 첫 공개 구현 완료. G-14 `/gw/projects`, G-15 `/gw/my-tasks`, 회사 API `/api/v1/gw/projects`. 실제 회원의 회사 공유 원장이며 게스트는 합성 안내만 본다. schema0.24.0/headgw_projects·GW29표(프로젝트10표 포함), DB Excel/ERD 동시 반영. 회사 기본 VIEWER·지정 EDITOR/OWNER 정책 및 상세 제약은 설계 명세 참조.
