# Factory Flow 독립 시스템·업무일지 전체 설계

FLOW-01 / 2026-10-10 / 전체 확인 대상. 제품 코드·DB 미변경.

## 1. 기획 의도와 참조 코드 분석

Factory Studio의 열 번째 구현 솔루션으로 **Factory Flow**를 추가한다. 표시 설명은 **Work OS · 프로젝트 관리·협업**이다. GW는 전자결재·공지·일정·채팅을 계속 소유하고, 프로젝트·업무·업무일지는 Flow가 독립 소유한다. 물리적으로는 기존 PostgreSQL과 API 서버를 사용하며 별도 인증 서버나 새 사용자 계정을 만들지 않는다(FS-013).

제공된 폴더의 `src/App.tsx`는 React19/Tailwind4 기반 시제품이다. 독립 사이드바·상단 경로·요약 카드·밑줄 탭·색상 그룹·담당자 아바타·진행 바를 UI 기준으로 채택한다. 제품에 파일 전체를 덮어쓰거나 Tailwind를 새로 도입하지 않고 기존 CSS/아이콘 체계로 이식한다. 사용자 폴더는 읽기 전용으로 유지한다.

| 확인한 코드 | 제품 연결 시 보완 |
|---|---|
| 하위 행을 `child: boolean`로 표시 | 실제 parent_id 관계·접힘·부모 집계 유지 |
| 고정된 첫 보드가 선택 상태 | 실제 회사 보드 선택·주소·즐겨찾기 연결 |
| 담당자 이름 문자열/고정 본인 필터 | 실제 회사 계정 UUID·서버 권한·복수 담당자 |
| 상태 클릭 시 순환 | 명시적 상태 선택, 완료 체크는 완료/이전 미완료 복원 |
| 캘린더·간트 `EmptyView` | 기존 네 보기 기능 유지 |
| 일부 공유·필터·메뉴 버튼 무동작 | 실제 권한 설정·필터·행 메뉴 구현; 준비 버튼 노출 안 함 |
| 진행률 합계가 상위/하위를 같이 계산 | 최하위 업무만 집계, 취소 제외 |

첨부 분석의 업데이트 숫자는 보고서 수로 단정하지 않는다. Flow는 제출 일지 수·댓글 수·미작성 수를 각각 표시한다. 실제 참고 회사의 조직·이름·업무 내용은 제품 샘플이나 Git에 복사하지 않는다.

## 2. 첫 공개 범위와 경계

| 포함 | 구체 동작 |
|---|---|
| 독립 앱 진입 | 런처 카드·전체 솔루션·내 공간·즐겨찾기·도움말의 FLOW 구분 |
| 기존 보드 이전 | 회사/ID/관계/담당자/댓글/이력/개인 설정 보존 |
| UI | 한 개 독립 사이드바, 네 보기, 검색/필터, 요약, 우측 상세 패널 |
| 팀 업무일지 | 본부/실 → 팀·기간 → 팀원 → 날짜별 일지 |
| 설정 | 수동 조직 또는 HR 읽기 가져오기, 계정·사원 코드 명시적 연결 |
| 작성/검토 | 임시 저장·제출·철회·보완 요청·검토 완료·수정본 재제출 |
| 취합 | 기간/팀별 제출·미작성·보완 요청·검토 완료 현황 |
| 개인화 | 내 업무/내 일지, 보드 즐겨찾기·열·필터·순서·접힘 |
| 성능 | 부모/하위 행 커서 분리, 그룹 집계 서버 계산, 대량 행 가상화 |

**후속**: 첨부 업로드/다운로드, 자유 열·외부 공유·자동화·알림 발송·실시간 공동 편집·오프라인·의존 일정. 첨부는 별도 저장소·용량/보존/다운로드 권한 설계 후 FLOW-03에서 추가한다. 이번 첫 공개 UI에 무동작 파일 열이나 공유 링크를 두지 않는다. `공유` 버튼은 회사 내부 보드 권한 설정을 연다.

게스트는 회사 기록에 접근하지 않고 앱 안의 합성 예제만 읽기 전용으로 체험한다. 실제 회사는 기존 계정/회사 공동 공간을 사용한다. 출퇴근·휴가 기록 및 전자결재 원장은 Flow로 옮기지 않는다.

## 3. 메뉴·주소·전환

| 화면 | 주소 | 메뉴 |
|---|---|---|
| 내 업무 홈 | `/work-os` → `/work-os/my-tasks` | F-01 내 업무 |
| 보드 목록/선택 | `/work-os/boards?companyId=&boardId=` | F-02 프로젝트 보드 |
| 일지 작성 | `/work-os/work-logs?companyId=&periodId=&date=` | F-03 업무일지 |
| 일지 취합 | `/work-os/reports?companyId=&periodId=` | F-04 작성 현황 |
| 조직·계정 연결 | `/work-os/settings?companyId=` | F-05 조직·구성원 |

현재 포털 `/flow`는 전체 흐름 지도이므로 이름이 같아도 주소를 재사용하지 않는다. 기술 모듈 키·업무 스키마·백엔드 패키지는 `flow`, API는 `/api/v1/flow`이다.

기존 `/gw/projects`·`/gw/my-tasks`는 새 주소로 query를 유지해 replace redirect한다. 과거 도움말 G14/G15는 전환 안내로 유지한다. 새 GW 메뉴에는 두 화면을 넣지 않는다. 기존 메뉴 즐겨찾기 `gw:projects`→`flow:boards`, `gw:my-tasks`→`flow:my-tasks`를 순서 보존·중복 제거 후 이관한다. 전환 전 화면에서 오래 열린 요청은 기존 API alias로 동일 Flow 서비스·권한을 호출하도록 한 공개 주기 유지한다. 두 저장 원장을 병행하지 않는다.

## 4. 데이터 이전·독립 경계

기존 `gw.work_*` 10표를 새 revision에서 `flow` 스키마로 SET SCHEMA한다. 내부 ID·S·시퀀스·복합 FK·댓글·audit payload는 그대로 보존한다. 10표 이름은 유지한다. GW의 나머지19표는 유지한다. 적용된 gw_projects migration은 수정하지 않는다.

순서: 백업 → 쓰기 중지/전환 잠금 → 행수·ID·댓글/이력 digest 기준 기록 → flow 생성/10표 이동 → 8표 신설/부가 열 → COMPANY 활성 세대 flow 등록 → 메뉴 즐겨찾기 전환 → 경계/DDL/데이터 대조 → 새 앱 확인 → 쓰기 재개. 전체 DDL은 단일 트랜잭션, 짧은 점검 창 사용. core receipt/audit의 module_key=gw 과거 행은 수정하지 않고 새 요청부터 flow 기록. 기존 receipt를 alias 재시도에서 조회할 때 현재 Flow 권한 재검사하고 키 중복 실행을 막는 이행 adapter를 둔다.

기존 COMPANY GW모듈 enabled 값을 Flow에 복사한다. Flow 사용 중지·세대 준비 상태는 GW와 독립이다. 새 회사 생성·업무 모듈 목록·게스트 초기화/정리·검증·CLI·DB 메타데이터·실제/목표 Excel/ERD에 flow를 일관되게 등록한다. 합성 예제는 서버 원장 쓰기 없는 UI용 합성 데이터로 시작하고 회사 자료를 템플릿에 복사하지 않는다.

업무 FK는 모두 `(workspace_id,generation_id,참조id)` 복합 참조, RESTRICT. HR/GW로 향하는 업무 FK·직접 SQL·교차 쓰기는0건. 인증·회사 회원은 core의 읽기 계약, HR 조직/사원은 `hr.interface.departments/employees`만 사용한다. 다른 회사의 HR 스코프를 사용하지 않는다. 현재 HR 제공에는 app_user UUID 연결이 없으므로 이름 일치로 계정을 자동 연결하지 않는다. OWNER가 계정과 사원 코드를 확인해 연결하며, HR 미등록 회사도 Flow 수동 조직으로 독립 사용 가능하다.

## 5. 업무일지 모델과 날짜

일지 보드 템플릿의 그룹은 본부/실, 상위 업무는 팀·기준 기간, 하위 업무는 팀원이다. 트리 깊이는 기존1단계 하위 업무를 유지한다. 날짜별 일지는 별도 work_log 레코드로 개인 행에 연결한다. 일반 업무의 제목/진행률을 보고서 본문으로 재사용하지 않는다.

기간은 일간 또는 주간. `week_key`는 ISO 주차 문자열 YYYY-Www이며 시작/종료는 date. ISO 연말 경계는 서비스에서 실제 날짜로 검증한다. 주차 형식 CHECK만으로 실재 주차를 보장한다고 표현하지 않는다. 기간 생성자는 작성 대상 날짜를 명시한다(기본 월~금, 생성 화면 수정 가능). 주말·휴가·출장을 임의로 미작성에 포함하거나 HR근태를 변경하지 않는다. 작성 대상 날짜/대상자 변경은 제출 이력이 있는 셀을 삭제하지 않고 이후 적용 날짜를 가진 새 대상 정의로 추가한다.

한 기간·계정당 assignment1행, 대상자·일자당 log1행. 개인 행은 지정 계정1명, 일반 업무는 기존 복수 담당자를 유지한다. 기본 명단 생성과 재시도는 단일 TX/멱등키로 중복되지 않는다. 다음 기간 복제는 조직/대상자/검토자 구성만 복사하고 일지 본문·댓글·완료 상태는 복사하지 않는다.

회사 timezone으로 오늘·제출 시각을 표시한다. 미래 날짜 제출은 차단, 과거 대상일 작성 허용. 미작성은 대상일 중 오늘 이하이며 draft나제출 기록이 없는 셀, 임시 저장은 별도 수치다. 제출률=SUBMITTED/REVIEWED 셀 수÷대상 셀 수, 분모0은 대상 없음. 보완 요청은 현재 제출률에서 제외한다. 일반 업무 진행률은 기존 leaf 집계이며 일지 제출률과 섞지 않는다.

## 6. 상태·권한·불변 기록

일지 상태: `DRAFT` → `SUBMITTED` → `REVIEWED`, 또는 `SUBMITTED`→`CHANGES_REQUESTED`→`SUBMITTED`. 작성자는 검토 전 SUBMITTED를 철회하여 DRAFT로 돌릴 수 있다. 제출 시 수행 업무는 필수, 예정 업무·이슈는 선택, 각 필드 최대10000자. 검토 완료본은 본문을 덮어쓰지 않고 작성자가 수정본을 시작하여 재제출한다. 기존 제출 revision·검토 판단은 영구 유지하고 append-only history로 조회한다. 재제출마다 revision 증가, 동일 version 변경 충돌은409.

| 주체 | 일반 보드 | 일지 본문 | 검토 |
|---|---|---|---|
| 회사 일반 회원 | 기본 VIEWER, 회사 공유 보드 읽기 | 제출본 읽기, 본인 assignment만 임시본 읽기/쓰기 | 불가 |
| EDITOR | 기존 업무 수정 | 타인 임시본 열람/대필 불가 | 별도 검토자 지정 필요 |
| 기간 REVIEWER | 보드 VIEWER 이상 필요 | 해당 기간 제출본 | 다른 사람 일지 검토·보완 요청 |
| 보드 OWNER | 보드/대상자/검토자 설정 | 타인 임시본 대필 불가 | 검토자 지정된 경우만 가능 |
| 회사 OWNER | 보드 소유자 복구/생성 정책 | 기본 권한을 넘는 일지 임시본 접근 없음 | 지정 필요 |
| 플랫폼 ADMIN/HR ADMIN | 회사 회원/Flow 역할 자동 획득 없음 | 없음 | 없음 |

본인 일지는 자가 검토할 수 없다. 검토자 부재 시 검토 대기로 남기며 완료 처리하지 않는다. 회사 회원 정지/탈퇴 시 읽기·쓰기·receipt replay 즉시 차단한다. 과거 명단·이력은 이름 snapshot으로 보존하며 비활성 표시한다. reviewer 명단 변경·보드 보관도 fresh authorize 적용. 회사 공유 제출본이라는 정책을 작성 화면에 표시하고 임시본·미제출 본문은 타인에게 반환하지 않는다.

댓글은 제출본/검토 가능한 스레드에서 작성한다. 본인 댓글 수정·삭제만 허용하고 이전 본문은 감사 이력에 보존한다. work_log의 변경 이력은 본인 임시본 비공개 내용을 타인에게 우회 공개하지 않는다. 링크는 http/https만 클릭 가능, 본문은 텍스트 렌더링한다.

수정본 작성 중에도 과거 제출본은 제출 당시 내용으로 열람할 수 있다. GET 응답은 작성자에게 현재 임시본, 타인에게 공개 가능한 제출 revision만 반환하며 현재 draft 필드는 포함하지 않는다. 철회는 현재 제출 집계에서 제외하되 이미 공유한 제출 기록을 삭제하지 않는다. 이 차이를 패널의 날짜·revision·철회 배지로 표시한다. 기간/대상자 보관은 표시 숨김이며 일지 원문·revision을 지우지 않는다.

## 7. DB 명세

[flow-design.json](flow-design.json)은 이관10표와 신설8표의 열/키/제약/관계 명세다. 실제 schema.json을 승인 전 변경하지 않는다. 공통 열: S bigint NOT NULL, id bigint identity, PK(id), UK(S,id), created_at timestamptz now, version int default1 CHECK>0. 신규 전역 설정 대신 기존 work_project_settings 사용.

| 신설 표 | 용도·주요 규칙 |
|---|---|
| flow.organization_unit | 본부/팀의 자체 조직, parent 복합FK, 순환 서비스 차단, UK(S,code) |
| flow.person_link | 실제 계정 UUID와 선택 HR코드 snapshot, UK(S,user_id), HR교차FK 없음 |
| flow.log_period | 팀 상위 업무·기간·주차·대상일, UK(S,team_task_id), dates 유효·대상일 범위 확인 |
| flow.log_assignment | 개인 행·계정·적용 날짜·대상일, UK(S,period,user), UK(S,personal_task_id) |
| flow.log_reviewer | 기간별 검토자, UK(S,period,user), 활성 회사 회원 SERVICE |
| flow.work_log | 날짜별 현재 draft/state/current_revision/version, UK(S,assignment,log_date) |
| flow.work_log_revision | 제출본·검토·철회 등 불변 snapshot, UK(S,log,revision), REVIEWED 수정 금지 |
| flow.log_comment | log별 댓글·제출 revision 연결, deleted_at/version·감사 기록 |

기존 work_board에 board_kind=TASK/WORK_LOG 기본TASK 추가. work_group에 organization_code snapshot nullable 추가. 일지 개인 행의 assignees/부모 이동은 assignment 소유 서비스가 통제한다. 이미 일지가 있는 행은 일반 업무로 변환하거나 다른 기간으로 이동할 수 없다. 이관 포함18표, 전체 표수는 현재191에서 신설8로199 예상이다. FK/컬럼 수는 승인 후 실제 metadata 생성 시 산출하며 추정 수치를 확정값으로 쓰지 않는다.

인덱스: 부모/하위 조회(S,board,group,parent,position,id), 제출 취합(S,period)/assignment경유(S,assignment,log_date,state), 로그 revision(S,log,revision DESC), 댓글(S,log,id). 대량 조회의 COUNT/집계는 본문 없이 서버 계산한다. 보고 기간 정책·인적 연결·본문·검토 변경은 공통 audit 및 Flow event에 남긴다.

## 8. API·트랜잭션·성능

`/api/v1/flow` 이하 회사ID 필수, 모든 요청 fresh 회사 확인. 회사 목록은 core 계약. overview는 부모50행 cursor, children는 펼친 부모별50행 cursor; 전체 보드 합계는 별도 aggregate SQL로 계산하여 로드된 페이지 합계와 혼동하지 않는다. 검색은 제목/활성·과거 담당자 snapshot, 리터럴 부분 검색, 결과에 ancestor 경로 포함. 상태/담당자/date filters 서버 처리. leaf만 칸반, 달력/간트는 기간 범위 서버 조회하고 큰 범위에서 화면 안내+월 이동을 제공한다. 우측 패널은 task 또는 log별 lazy detail 및 revision/comments50행.

| API | 역할·응답 |
|---|---|
| GET /companies, /boards, /boards/{id}/groups, /boards/{id}/tasks, /tasks/{id}/children | 회사 공유 읽기, 커서·집계 |
| POST /boards, /groups, /tasks 및 기존 operation 이행 | OWNER/EDITOR·version·CSRF·receipt |
| GET /my-tasks, /organizations, /people-links | 본인 담당 목록/조직·계정 연결 공개 정보 |
| POST /organizations/import-preview, /import-confirm, /people-links | OWNER, HR읽기 계약, 확인 snapshot/digest재검사 |
| POST /log-periods, /log-periods/{id}/assignments, /reviewers, /clone | OWNER, 명단 중복·날짜·역할검증·단일TX |
| GET /log-periods/{id}/summary, /assignments, /work-logs?date= | 모든 조회 회사/보드 범위, draft비공개·작성 현황 |
| POST /work-logs/save, /submit, /withdraw, /start-revision | 본인, version·날짜·상태검증 |
| POST /work-logs/review, /request-changes | 지정 REVIEWER, self-review차단·현재제출revision확인 |
| GET /work-logs/{id}, /revisions, /comments | 상태/작성자에 따른 공개 projection |
| POST /log-comments, /log-comments/update | 본인 댓글, 전본audit |

쓰기 순서: workspace/company 잠금 → Flow활성scope → 현재 권한 → receipt replay인가 → board → period → assignment → log행 잠금 → version 확인 → revision/event/집계에 필요한 행 갱신 → 공통 receipt/audit → commit. 동일 키 다른body409, 같은본문 재시도같은결과, 수신 실패 재시도중복제출0. parent잠금 순서는기존업무와통일하여데드락 회피.

프런트는 기존 React/Vite/CSS 사용, 가상화는 고정56px행+overscan의 프로젝트 전용 컴포넌트로 시작하여 별도표라이브러리 강제 도입 없음. 1000부모/3000자식 합성데이터로 접힘첫화면·스크롤·검색·집계검증. 네트워크/API DB쿼리수·응답시간·렌더표시행을 측정하고 실제수치로 완료 보고한다. 성능기준: 최초 목록 최대50부모, 자식 펼칠때만조회, DOM행은viewport+overscan 범위, 브라우저별체감측정은 별도 기록. 가상화 접근성은 logical rowcount/index 및 키보드 행 이동 제공.

## 9. 화면 설계·실패 흐름

참조 화면처럼 폭256px 사이드바 한 개에 브랜드/내업무/전체솔루션/즐겨찾기/회사보드 배치, 목록 안의 중복 업무보드 aside 제거. 접으면64px 아이콘·툴팁, 긴 이름ellipsis/fulltitle; 보드표시는 그룹색원·공간고유아이콘. 오른쪽 헤더는 회사선택·경로·회사내권한 설정. 전역포털 이동·로그아웃·도움말은 상단 또는사이드바하단으로 접근가능하게 유지.

본문: 제목/노란별(별만금색)·설명·상태요약/진행률 → 아이콘밑줄4탭 → 새업무/검색/내업무만/필터/열설정 → 그룹카드. 행은완료체크/제목/담당자initial아바타/텍스트상태/일정/진행바/스레드숫자/행메뉴. 일반업무에 검토라는 새상태를 임의추가하지 않고 기존대기/진행중/보류/완료/취소 유지; 업무일지검토요청은 별도 상태다.

우측패널폭480~560px: 업무정보/일지/댓글/이력 탭, 날짜선택, 수행/예정/이슈입력, 임시저장/제출·검토버튼. Esc닫기·포커스복귀, 미저장입력이면닫기전버리기/계속작성선택. 모바일은메뉴drawer·한열카드·전체화면상세, 버튼최소44px. 390px/768px/1280px 확인. 모달·drawer는열린동안만배경interaction제어,조회/저장실패로전역navigation잠그지않는다. 409는현재값재로드/입력유지·수동다시적용,타회사/계정정지403은본문숨김/회사선택복귀. 브라우저확장설정·실제비밀번호변경없음.

UI 검토 시제품은 합성 회사/업무로만 동작하며 실제저장/API연결이없음을명시한다. 현재제품의완료상태로표시하지 않는다.

## 10. 개발·검증·전환 완료 조건

FLOW-01 전체확인후 FLOW-02 한 작업으로 독립이관+UI+일지첫공개를구현한다. 단계별작업순서: 새metadata/migration/Excel/ERD → core모듈등록/기존데이터이관/alias/favorites → Flow권한/일지/API →독립UI/가상화/네보기 → 도움말/합성예제/검증 →로컬백업·적용·mainpush. FLOW-03 첨부는별도전체설계후.

검증표: 회사A/B모든신규경로격리,타임존·ISO연말·미래일·분모0,본인draft비공개,타인대필불가/자가검토불가,revokedmembership시receipt재시도차단,lastOWNER복구,reviewer변경시옛권한차단,save/submit/review동시수정409,중복assignment/일지재시도0,검토완료본불변/수정revision이력,댓글수/제출수정확,본인filter祖先표시,일지소유task이동차단,기존보드ID/관계/이력/개인설정100%보존,old/newURL/alias같은원장,FK교차0/DDL왕복0,모듈off독립,회사신규생성/세대정리,키보드/긴명칭/390px/대량페이지네보기. 관련검사후전체frontend/backend/tools및빌드,새실패만재검사.

첫반영은 로컬DB백업후main/originmain. 운영배포는현재요청에없으므로별도지시까지미실행. downgrade로신규일지데이터를삭제하지않으며,운영복구는백업/이전제품/확인된forwardfix 절차를사용한다. 빈테스트DB에서는DDL왕복검사,데이터있는DB에서는역이관보존검사(신규일지가있으면명시거부)를분리한다.

## 11. 확인할 결정

확인 묶음: **Factory Flow 독립 앱·flow 데이터 소유권, 기존기록/즐겨찾기/주소보존, 제공UI이식, 회사공유제출본·본인전용임시본·지정검토자, 날짜별일지첫공개, 첨부후속**. 표시이름은변경가능하며데이터/API경계는이명세를기준으로한다.

저장소 AGENTS.md §2: “사용자의 전체 설계 확인 후 제품 개발을 시작한다.” 연결문서도 “승인 후 범위/데이터 책임/업무 규칙이 크게 바뀌면 해당 설계를 먼저 갱신해 확인받고 영향을 받는 개발을 진행한다.”라고 규정한다. 이번독립소유권·새일지권한이그변경에해당하므로구체설계/시제품/DB명세를완성한후전체확인을받는다. 기존GW-PROJECT승인은이번미정의일지권한/새스키마설계의승인으로대체하지않는다.
