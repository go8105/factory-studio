# GW-PROJECT-01 — 프로젝트·업무 보드 설계 초안

2026-10-10 / 상태: 분석·설계 제안, 제품 개발·DB 적용 전 사용자 전체 설계 확인 대상

## 1. 분석과 제안

첨부 화면에서 편리한 부분은 업무를 그룹으로 묶고, 담당자·상태·일정을 표 안에서 바꾸며, 같은 업무를 여러 보기로 확인하는 흐름이다. GW에 **프로젝트·업무 보드**를 추가해 프로젝트 WBS, 팀 업무, 이슈, 회의 후속 업무를 한 방식으로 관리한다. 회사 공동 사용을 기본으로 제안한다.

monday 공식 문서에서도 보드를 그룹·열·항목·하위 항목으로 구성한다. 기능 구조를 참고하고 Factory Studio의 기존 백자/쪽빛 화면과 메뉴 체계를 사용한다. 첨부된 회사의 실제 프로젝트·업무 내용은 샘플이나 Git에 복사하지 않는다.

공식 참고: [보드 구성](https://support.monday.com/hc/en-us/articles/115005317249-The-basics-of-a-board), [하위 항목](https://support.monday.com/hc/en-us/articles/360011905480-All-about-subitems), [간트 보기](https://support.monday.com/hc/en-us/articles/360015643840-The-Gantt-Chart-View-and-Widget).

## 2. 첫 공개 범위

| 영역 | 첫 공개 동작 |
|---|---|
| 보드 | 생성·이름/설명 편집·보관/복구, 프로젝트/팀 업무/이슈/회의 후속 템플릿 |
| 그룹 | 이름·색상·접기·순서 변경, 업무가 남은 그룹 삭제 차단 |
| 업무 | 제목·설명·복수 담당자·상태·중요도·시작/종료일·진행률 |
| 하위 업무 | 1단계 하위 업무, 상위 업무 아래 펼치기/접기 |
| 메인 테이블 | 셀 바로 편집, 검색·담당자/상태/기한 필터·정렬, 기본 열 숨김/순서 설정 |
| 칸반 | 상태별 카드, 상태 이동으로 동일 업무 상태 변경 |
| 캘린더 | 월 보기, 기간 업무/마감 표시, 날짜 미지정 업무 별도 목록 |
| 간트 | 계획 시작/종료 막대·오늘선·확대, 상세 창에서 일정 변경 |
| 협업 | 업무 상세 오른쪽 패널, 댓글·참고 링크·변경 이력 |
| 내 업무 | 참여한 모든 보드의 내 담당 업무, 지연/오늘/예정 필터 |
| 현황 | 미완료·지연·완료 수, 그룹별 상태/진행률 요약 |
| 개인화 | 보드 즐겨찾기, 마지막 보기/필터 저장, 좁은 화면 대응 |

네 보기는 한 업무 원장을 사용한다. 테이블에서 수정하면 칸반·캘린더·간트도 같은 값을 표시한다. 간트의 선후행 의존 관계, 자동 일정 이동, 임계 경로는 첫 공개에 포함하지 않는다.

자유로운 사용자 정의 열, 파일 업로드, 외부 협력사 초대, monday 데이터 자동 가져오기, 이메일/푸시/규칙 자동화, AI, 실시간 동시 편집 표시, 오프라인 수정은 후속 범위다. 날짜·담당자 필터와 내 업무 현황으로 먼저 확인한다. 댓글과 변경 기록은 화면에서 갱신하며 실시간 알림으로 오해하게 표시하지 않는다.

## 3. 화면과 사용 흐름

GW 새 메뉴 **프로젝트·업무**, **내 업무**. `/gw/projects`에서 회사 선택 → 보드 목록 → 보드 만들기 → 그룹/업무 추가 → 담당자/상태/일정 편집 → 상세 댓글 → 보기 전환.

기존 공지·자유 게시판의 `/gw/board`와 구분한다. 전체 솔루션 즐겨찾기 사이드바는 유지하고, 프로젝트 화면 안에 보드 목록/보드 즐겨찾기를 둔다. 사이드바가 접히면 아이콘과 툴팁을 표시하고 긴 명칭은 말줄임한다. 선택한 별만 노란색이며 주변 배경은 기존 색을 유지한다. 보드 상세 즐겨찾기는 프로젝트 내부 목록에 저장하고 정적 메뉴 즐겨찾기와 구분한다.

데스크톱은 표와 오른쪽 상세 패널, 모바일은 카드 목록과 전체 화면 상세를 사용한다. 표의 제목 열은 고정하고 나머지는 가로 스크롤한다. 조회 실패는 해당 영역에 재시도를 표시하며 전체 메뉴 클릭을 막지 않는다. 편집 중 Enter 저장/Escape 취소, 드래그 외 순서 변경 버튼도 제공한다.

검토용 HTML은 합성 예시로 테이블/칸반/캘린더/간트 전환과 상태 변경·검색을 보여준다. 제품 화면이나 실제 저장 기능은 아니다.

## 4. 상태·진행률 규칙

- 상태: 대기 / 진행 중 / 보류 / 완료 / 취소. 중요도: 낮음 / 보통 / 높음 / 긴급.
- 하위 업무 없는 업무의 진행률은 0~100. 완료로 바꾸면 100, 미완료는 최대 99. 완료에서 다시 진행 중으로 열면 99로 조정하고 이력에 남긴다.
- 하위 업무 있는 상위 업무의 진행률/기간은 자식으로 계산한다. 취소 제외 자식 진행률의 동일 가중 평균, 기간은 자식 날짜의 최솟값/최댓값. 날짜 없는 자식 수를 따로 표시한다.
- 모든 자식 완료이면 상위 완료, 모두 취소이면 취소, 나머지는 진행률/보류 여부를 반영해 자동 상태 표시한다. 완료+취소만 남으면 완료. 모든 유효 자식 대기이면 대기, 미완료 자식이 전부 보류이면 보류, 그 외 진행 중.
- 자식이 있는 상위의 진행률/일정/상태는 직접 수정하지 않는다. 제목·설명·담당자·중요도는 편집할 수 있다. 첫 자식 생성 시 기존 부모 상태/일정 대신 집계가 적용됨을 확인한다.
- 그룹 요약은 최하위 업무만 집계하여 상위/하위 이중 계산을 피한다. 취소만 있는 그룹은 진행률 ‘대상 없음’ 표시.
- 지연은 회사 시간대 기준 종료일이 지났고 상태가 완료/취소가 아닌 최하위 업무. 날짜는 회사 달력 날짜, 이력 시각은 UTC 저장 후 회사 시간대로 표시.
- 시작일 ≤ 종료일. 마감만 입력하면 캘린더에 마감 이벤트, 간트는 날짜 미정 목록으로 표시. 상위·하위 업무의 그룹/보드는 일치해야 한다.
- 첨부 화면의 두 상태 열은 처음에 ‘업무 상태’와 ‘진행률’로 정리한다. 별도 검토/승인 단계가 필요하면 후속으로 구분하며 전자결재 완료와 업무 완료를 동일시하지 않는다.

## 5. 회사·계정·권한

실제 보드는 현재 COMPANY 공간/활성 세대에 저장한다. 게스트는 별도 합성 체험만 가능하며 회사 원장 접근은 불가하다. 개인 체험용 GW 담당자 선택으로 회사 업무를 처리할 수 없다.

회사 멤버십과 보드 권한을 매 요청 서버에서 확인한다. 회사에서 제외되거나 계정이 정지되면 과거 보드 역할/즐겨찾기/멱등 재요청이 있어도 접근을 거부한다. URL의 회사/보드/업무 ID만 바꿔 다른 회사 데이터를 읽지 못한다.

첫 공개는 **회사 전체 공유 보드**: 활성 회사 회원은 기본 VIEWER, 보드 OWNER가 EDITOR/OWNER를 지정한다. 생성자는 OWNER가 된다. 회사 회원의 보드 생성은 허용하되 회사 OWNER/ADMIN이 생성 권한을 회수할 수 있게 설정한다. 마지막 유효 OWNER의 제거/탈퇴는 소유권 이관 또는 회사 관리자 복구 절차가 필요하다. 회사 OWNER/ADMIN은 소유권 복구·보관을 할 수 있고 복구 이력을 남긴다. 비공개 보드/외부 공유는 후속이다.

| 역할 | 가능 작업 |
|---|---|
| VIEWER | 목록/상세/댓글/이력 조회, 개인 즐겨찾기/보기 설정 |
| EDITOR | 업무·그룹·담당자 편집, 댓글 작성/자신 댓글 수정·삭제 |
| OWNER | EDITOR 기능 + 보드 설정·역할 관리·보관/복구 |

업무는 우선 보관/복구하며 영구 삭제는 첫 공개에서 제공하지 않는다. 댓글 수정/삭제는 이전 내용의 감사 기록을 보존하고 화면에 변경 표시한다. 담당자가 퇴사하면 기존 이력/담당 표시는 유지하되 ‘비활성’ 표시, 새 배정은 차단한다.

HR 근무 ADMIN이 자동으로 GW OWNER가 되지 않는다. 플랫폼 admin도 모든 회사 업무를 자동으로 조회하지 않는다. 사용자는 기존 사용자 관리에서 계정을 만들고 회사 가입 후 보드 역할을 받는다. HR 사원/부서 원천은 기존 읽기 계약으로만 사용하며, 실제 로그인 계정 연결 여부를 별도로 검증한다. GW의 합성 담당자를 실제 사용자로 자동 연결하지 않는다.

## 6. 기존 구현과 차이

현재 GW 19개 테이블의 결재·공지·댓글·일정·채팅은 체험/개인 공간 기능이다. 프로젝트 보드/업무 원장은 없다. 과거 GW-EXT의 TEAM·담당자 바인딩 설계는 현재 core COMPANY 구현에 그대로 적용할 수 없다.

새 회사용 프로젝트 라우터는 기존 체험 `seed_ready('gw')`와 담당자 전환 경로에서 분리한다. `core.company.resolve_company` 계약으로 공간을 결정하고 요청의 실제 user_id를 사용한다. 기존 GW 결재·채팅을 회사용으로 동시에 전환하는 작업은 이번 범위가 아니다. 알림/파일도 현재 체험 구현이 회사용으로 이미 작동한다고 가정하지 않는다.

## 7. 데이터·API 초안

모든 업무 테이블은 S=(workspace_id,generation_id), id 및 생성/수정 시각을 가진다. 범위 앵커 외 타 스키마 FK 없음. GW 내부 참조는 S를 포함한 복합 FK와 RESTRICT. 실제 계정 ID는 식별자 값으로 보관하고 core 제공 회사 멤버십 계약으로 검증한다.

| 신규 GW 테이블 후보 | 주요 값/제약 |
|---|---|
| work_board | 이름·설명·템플릿·보관시각·version |
| work_board_member | board_id·user_id·OWNER/EDITOR, (S,board,user) 유일 |
| work_group | board_id·이름·허용 색상·순번·version |
| work_task | board_id·group_id·parent_id·제목·설명·상태·중요도·날짜·진행률·순번·보관시각·version |
| work_task_assignee | task_id·user_id·선택적 HR 사원 코드/표시 이름 스냅샷, 배정 유일 |
| work_task_comment | task_id·작성자·본문·수정/삭제시각·version |
| work_task_event | task_id·실제 행위자·변경 전/후·행위 시각, 추가만 허용 |
| work_board_favorite | board_id·user_id·순번, 사용자별 유일 |
| work_view_preference | board_id·user_id·보기·검증된 필터/열 설정, 사용자별 유일 |
| work_project_settings | 회사 공간별 생성 허용 정책·version, S 유일 |

위 10개는 설계 후보이며 현재 181테이블의 적용 스키마에 추가하지 않았다. 자기 참조 부모는 동일 보드/그룹, 순환/2단계 이상 깊이는 DB+서비스 검증. 상위의 집계 값은 API 계산으로 노출하여 별도 수동 값과 충돌하지 않게 한다.

API 초안: 회사 목록은 core 제공 계약, `/api/v1/gw/projects?companyId=...`, 보드 상세/그룹/업무/하위 업무/댓글/멤버/즐겨찾기/보기 설정, `/my-tasks`. 경로는 기존 GW 라우터와 충돌 없이 등록한다. 목록 커서·필터·정렬은 서버 처리, 보드 요약과 화면에 열린 그룹의 업무를 분리 조회한다. 이력/댓글도 페이지 조회한다.

쓰기 요청은 공통 action 엔진의 멱등키·동일 트랜잭션·fresh authorize를 사용한다. version 일치 조건으로 수정하여 충돌은409와 최신 값, UI는 실패 시 낙관 갱신을 되돌린다. 순서 변경·부모/자식 이동은 보드 단위 잠금 아래 함께 처리한다. 댓글 본문은 텍스트로 렌더링하고 링크는 http/https만 허용한다. 보기 설정은 허용 열/필터만 검증한다.

## 8. 개발 순서와 완료 기준

1. GW-PROJECT-01 전체 설계 확인 후 GW-PROJECT-02에서 상세 DB/API/권한 명세 확정 및 마이그레이션·메타데이터·DB Excel·ERD 동시 갱신.
2. 회사 권한·보드/그룹/업무·하위 업무·버전/멱등 API와 메인 테이블.
3. 같은 원장의 칸반·캘린더·간트, 내 업무·개인화·댓글/이력.
4. 통합 검증·도움말·합성 체험, main 병합/push. 운영 배포 시 기존 배포 절차와 DB 백업/마이그레이션 검증.

필수 검증: 회사 A/B 격리·게스트 차단·퇴사/정지 즉시 차단·역할 변경 후 멱등 재시도·마지막 OWNER 보호·부모 순환/범위 이동 차단·동시 수정409·재시도 중복 생성 방지·그룹/부모 집계·회사 시간대 지연 판정·네 보기 값 일치·조회 실패 시 메뉴 사용·긴 제목/접힌 사이드바/모바일 키보드 편집. 별도 합성 DB로 검증한다.

## 9. 확인할 결정

**추천: 회사 공동 공유 보드, 기본 열 중심, 테이블·칸반·캘린더·기본 간트 네 보기까지 첫 공개.** 프로젝트/팀 업무/회의 후속 템플릿으로 시작한다. 파일·자유 열·외부 공유·자동화는 후속.

확인 대상은 이 전체 범위와 회사 회원 기본 VIEWER/OWNER가 편집 권한 부여하는 정책이다. 현재 사용자에게 추천 범위 확인을 요청하며 제품 구현은 아직 시작하지 않았다.

## 승인 후 상세 DB 명세 (2026-10-10)

사용자 “그대로 진행해줘”로 전체 첫 공개 범위 승인. COMPANY 소유자 역할은 현재 core 계약의 OWNER만 존재하므로 OWNER가 복구/정책 설정을 맡는다. 아래 열·제약은 구현 메타데이터와 함께 관리한다.

| `gw.work_board` | id bigint, workspace_id bigint, generation_id bigint, name varchar(120), description text, template varchar(20), version integer, archived_at timestamptz, created_at timestamptz |
| `gw.work_board_member` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, user_id bigint, role varchar(10), created_at timestamptz |
| `gw.work_group` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, name varchar(120), color varchar(7), position integer, version integer, created_at timestamptz |
| `gw.work_task` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, group_id bigint, parent_id bigint, title varchar(250), description text, status varchar(12), priority varchar(10), starts_on date, ends_on date, progress integer, position integer, version integer, archived_at timestamptz, created_at timestamptz |
| `gw.work_task_assignee` | id bigint, workspace_id bigint, generation_id bigint, task_id bigint, user_id bigint, display_name varchar(120), created_at timestamptz |
| `gw.work_task_comment` | id bigint, workspace_id bigint, generation_id bigint, task_id bigint, user_id bigint, body text, updated_at timestamptz, deleted_at timestamptz, version integer, created_at timestamptz |
| `gw.work_task_event` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, task_id bigint, user_id bigint, action varchar(40), details jsonb, created_at timestamptz |
| `gw.work_board_favorite` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, user_id bigint, position integer, created_at timestamptz |
| `gw.work_view_preference` | id bigint, workspace_id bigint, generation_id bigint, board_id bigint, user_id bigint, settings jsonb, created_at timestamptz |
| `gw.work_project_settings` | id bigint, workspace_id bigint, generation_id bigint, allow_create boolean, version integer, created_at timestamptz |
