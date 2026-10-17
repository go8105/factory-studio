# GW 회사 화면·협업 권한 · GW-COMPANY-04

2026-10-17. 사용자 ‘다음 진행해줘’로 승인된 04 단계. 기준 `55a7500`, 브랜치 `codex/gw-company-01`, 작업 폴더 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`. WIP `72735cf`·`11d1e51`. 최종 커밋은 `git log -1`로 확인한다.

회사 API·제품 화면·정적 도움말을 연결했다. 활성 회사 소속과 본인 GW 직원 연결·초기 설정을 확인한 경우 `businessReady=true`로 회사 업무를 연다. 개인/게스트 합성 담당자 체험은 별도 공간으로 유지한다. **로컬 합성 데이터 검증이며 실회사 도입·운영 배포 완료가 아니다.**

## 제품 진입과 화면별 결과

GW 상단 **사용 공간 → 회사명**을 선택한다. 회사 선택은 탭 URL의 `companyId`에 남으며 세션의 다른 솔루션 공간이나 다른 탭을 바꾸지 않는다. 즐겨찾기에 없는 메뉴는 **전체 메뉴**에서 연다. 회사 직원·연결 화면의 **? 도움말**과 G-01~13 도움말 상단에서 [회사 GW 시작과 권한 안내](../../content/help/gw/company.md)로 이동한다. 실제 제품 경로는 `/help/gw/company`다.

| 화면 | 회사에서 사용할 수 있는 범위 |
|---|---|
| G-01 업무 현황 | 현재 본인에게 허용된 기안·게시·처리 대상의 요약 |
| G-02 기안함 | 본인 일반 기안 초안·상신·회수·재상신 준비 |
| G-03 결재함 | 현재 유효 배정/위임과 단계에 맞는 승인·반려·합의·참고 의견 |
| G-04 결재 기록 | 허용된 기록·상신 당시 조직·처리 사건, 원 담당자와 유효 재배정 구분 |
| G-05 공지·자유 게시판 | 본인 초안, 회사/직접 소속 공지의 ACL, 공지 게시 역할 확인 |
| G-06 결재선 템플릿 | 활성 연결 직원 검색·선택, 결재선 관리 역할만 등록·편집 |
| G-07 회사 직원·연결·권한 | 최초 설정·HR 명시 가져오기·본인 동의·역할·연결 정지/복귀·직무 표시/활성·막힌 결재 재배정·최소 보안 사건 |
| G-08 전결 규칙 | 일반 기안 규칙, 전결 관리 역할과 버전 확인, 사용 규칙 변경 제한 |
| G-09 결재 위임 | 현재 미처리 배정이 있는 본인의 위임·회수, 활성 대상·기간/중첩/연쇄 제한 |
| G-10 조직도 | GW에 가져온 조직 조회, 조직 관리자만 HR 비교·갱신 |
| G-11 일정 | 본인 작성·참석/직접 부서 범위, 작성자 편집·취소·본인 참석 응답 |
| G-12 알림 | 본인 수신이면서 현재 부모 대상도 읽을 수 있는 알림 |
| G-13 채팅 | 현재 참여자만 전송·조회·읽음·탈퇴, 탈퇴 뒤 성공 영수증 재노출 차단 |

Factory Flow는 `/work-os`의 독립 시스템이다. GW의 회사 query를 Flow·ERP·HR 등의 요청에 전달하지 않는다. 회사 기안은 GENERAL만 열며 ERP·PLM 원천을 선택하지 않는다. 총 관리자 `admin`·회사 OWNER/HR 관리자·GW 명시 역할·직무 표시는 서로 다르다.

## 구현과 권한 경계

- 기존 GW 63경로에 `CompanyRoute`를 적용했다. `companyId`가 없는 기존 개인 입력 계약과 상태 코드는 유지한다. 회사 요청은 현재 로그인으로 주체를 결정하며 `personId` query와 `actingPersonId` 본문을 거부한다. 회사별 양의 ID, 중복/알 수 없는 query·본문·버전·CSRF·멱등 키를 확인한다.
- 모든 회사 서비스는 회사/계정/세션/세대 잠금을 포함한 자기 트랜잭션에서 권한을 다시 확인한다. 쓰기는 객체와 현재 권한을 성공 영수증보다 먼저 확인한다. 63경로 전체에 타 회사·주체 위조 거부 테스트를 적용했다. 이는 모든 유효 업무 조합을 브라우저로 전수 검증했다는 뜻은 아니다.
- 결재·게시 목록의 ACL은 SQL에서 건수·페이지보다 먼저 적용한다. 이전/후속 링크와 알림에도 현재 부모 열람 권한을 적용한다. 댓글 작성자·일정 작성자/참석자·채팅 현재 참여자를 구분한다. 읽기 회수 후 댓글·알림과 이전 성공 응답으로 원문을 되찾을 수 없다.
- HR는 `fs.hr.interface`로 읽는다. 가져오기는 명시적 선택·사유·미리보기 검증 후 GW 스냅샷만 갱신하며 계정/역할을 자동 부여하지 않는다. 직무 표시를 MANAGER로 바꿔도 관리 역할이 생기지 않는다. 직원 비활성은 업무 접근을 막으며 마지막 활성 보안 관리자는 보호한다.
- 회사 화면의 요청은 회사·권한 세대별로 구분한다. 회사 변경/화면 해제 뒤 늦은 조회·쓰기 응답은 폐기한다. 응답 불명확 시 같은 입력·멱등 키로 재확인하고 입력을 바꾼 재시도는 막는다. `/me`를 15초마다, 창 포커스 시 확인하며 회수/권한 오류에는 원문·선택 상태를 비운다. 이미 브라우저에 전달된 내용의 소급 삭제를 보장하지 않는다.
- 직원·후보 계정·연결·보안 사건·막힌 결재·읽기 허용 목록에 페이지 이동을 연결했다. 참여자 검색은 최대100명씩, 이미 선택한 직원은 개별 ID 조회로 확인한다. 이 변경은 대규모 부하 검증 결과가 아니다.
- DB 표·마이그레이션 변경은 없다. schema0.26/198표·2151컬럼·488FK, head `gw_company_identity`를 유지한다. Excel·ERD는 재생성하지 않았다.

## 실제 Chrome 검증

본 작업만의 PostgreSQL18 컨테이너(port55437)에 별도 브라우저 `_test` DB를 만들었다. 기존 사용자/비밀번호/공유 DB/브라우저 프로필·확장 설정은 바꾸지 않았다. 합성 회사·관리자·직원과 무작위 임시 비밀번호만 사용했으며 자격증명은 Git/보고서/스크린샷에 넣지 않는다.

1. 실제 로그인 화면 → OWNER 본인 최초 설정 → HR 직원 명시 가져오기 → 본인 연결 요청 → 다른 로그인 직원의 자기 확인·동의 → 결재선 등록.
2. 일반 기안 초안 → 예정 결재자의 초안 직접 접근404 → 상신 → 직원 승인 → 처리 기록·실제 저장 댓글 확인. 회사 화면에서 담당자 전환이 없고 개인 체험으로 전환하면 체험 선택기가 나타남을 확인.
3. 미저장 패널의 닫기 → 계속 편집/변경 버리기 → 공간 전환. 저장 전 입력을 버린 뒤 이동함을 확인.
4. 일정 작성·직원 초대 → 직원 참석 응답 → 양쪽 표시 확인.
5. 1:1 채팅 생성·전송·다른 로그인 수신 → 390px 화면에서 메뉴를 닫고 메시지 전송, 가로 넘침 없음.
6. 직원 직무 표시 편집 → API의 저장값 확인, 전결 규칙 화면 등록, 직접 부서 공지 게시 → 390px 직원 조회.
7. 보안 사건 조회 역할 부여 → 직원 채팅 원문이 열린 동안 관리자 연결 정지 → 직원의 원문/선택 폐기 확인 → 같은 계정 복귀 → 재확인 후 접근. 감사 역할의390px G-07 화면도 가로 넘침 없음.
8. 실제 G-07 도움말 버튼 → 회사 안내문 → 관련 정적 도움말 연결 확인. 각 성공 시나리오의 브라우저 pageerror는0.

산출 스크린샷은 합성 자료의 현재 제품 화면이며 설계 시제품이 아니다. 실제 휴대폰/다른 브라우저/OS 인쇄·PDF 저장/실회사·실운영은 검증하지 않았다.

## 자동 검사

| 검사 | 결과 |
|---|---|
| 백엔드 회사/HR/GW/Flow 관련 묶음 | 156 통과·470.22초, 기존 경고6 |
| 직원 직무·활성·사유·버전·마지막 관리자 추가 검사 | 1 통과·4.84초, 기존 경고2 |
| 도구 unittest | 139 통과 |
| 공식 backend ruff check/format | 통과 / 238파일 일치 |
| 설계 정적 검사·R1~R6 격리 | 오류0 / 198표·488FK |
| 실제 PostgreSQL18.6 DDL 대조 | 오류0 / 198표·2151컬럼·488FK, 명세hash `acefeb23…` |
| 프런트 GW/문서와 ERP·MES 집중 재검사 | 53 통과(7파일) |
| 프런트 전체 `--maxWorkers=2` | 603 통과·기존 Flow7 실패(610건·77파일) |
| frontend lint·format·production build | 통과, 기존 큰 chunk 경고 |
| 실제 Chrome | 위1~8 성공, pageerror0;390px는실기기아님 |

최초 프런트 전체 병렬 실행은601통과·9실패(Flow7+ERP/MES 시간 초과2)였다. ERP/MES를 포함한 집중53건은 통과했고, 동시 실행 수2로 재실행한 전체 검사에서는603통과·Flow7실패로 정리됐다. 앞선 실패를 숨기거나 전체 CI를 성공으로 표시하지 않는다. 새 회사 정적 도움말이 지도에서 누락되어 발견된 테스트 실패는 문서 지도에 연결해 해결했다.

전체 백엔드 CI·실운영 배포·실휴대폰·실회사 사용자 인수·물리 출력은 미실행이다. 스키마 변화가 없어 이번04에서 Excel/ERD 재생성이나 migration 왕복을 반복하지 않았다(02에서 수행).

## 후속 우선순위와 제약

1. **05 통합 전 필수:** 병행 로컬 main `9f6cf36`의 WMS205표와 GW198표가 schema0.26과 `flow_board_custom` 이후 migration head를 각각 추가했다. 양쪽 표/컬럼/제약·버전 충돌을 대조하고 새 merge revision·기존 자료 보존·양쪽 기능 회귀를 검증한다. 적용된 migration을 수정하거나 한쪽 schema를 덮어쓰지 않는다. 이번 검증은 최신 WMS main과 합친 결과가 아니다.
2. **05 실운영 P0 인수:** MFA/SSO·긴급 정지/계정 복구·보존/감사·백업/복구 RPO·RTO·실회사 권한 인수와 부하/회복 검증. 회사 화면이 열렸다는 이유만으로 도입 완료로 처리하지 않는다.
3. **기존 프런트 회귀:** Flow7 실패는 이번 범위에서 수정하지 않았다. 전체 CI 성공으로 보고하지 않는다. ERP/MES의 전체 병렬 실행 시간 초과는 집중 재실행과 구분해 기록한다.
4. **제품 문제 P2:** 미저장 확인에서 ‘계속 편집’ 뒤 포커스가 입력 밖에 남으면 다음 Escape가 패널을 닫지 않는다. 입력을 다시 포커스하면 기존 닫기 가드로 진행한다. 공통 패널 포커스 복원은 별도 후속으로 기록하며 이번에 범위 밖 UI 재설계를 하지 않는다.
5. **개발 계약 정리:** 자동 OpenAPI는 기존 개인 본문 계약을 표시한다. 회사 런타임은 위조 주체 필드가 없는 별도 모델을 검증한다. 회사별 OpenAPI 표현은 후속 문서 계약 과제다.

검증 종료 후 본인 생성 컨테이너의 ID를 대조하고 종료·볼륨 제거했다. 로컬8265/5265 검증 서버를 종료하고 임시 postgres.env/container-id/browser-private.json과 CI용 .env를 제거했다. 공유 컨테이너와 실제 계정은 변경하지 않았다.

이번 단계에서 main/원격 push/운영 배포는 하지 않았다. 다음 ID는 결과 확인 뒤 진행한다.

## 재현

Python3.14·Node24·PostgreSQL18, 새 전용 `_test` DB와 합성 계정을 사용한다. 실제 DB를 테스트 주소로 지정하지 않는다. 임시 `work/` 자격증명 파일은 재사용 전제가 아니다.

```sh
PYTHONPATH=backend/src:backend python -m pytest backend/tests/test_gw_company_http.py backend/tests/test_gw_company_work.py backend/tests/test_gw_company.py backend/tests/test_hr_work.py backend/tests/test_hr_users.py backend/tests/test_gw.py backend/tests/test_gw_policy.py backend/tests/test_gw_collaboration.py backend/tests/test_gw_organization.py backend/tests/test_gw_projects.py backend/tests/test_flow_custom.py -q --tb=short
python -m unittest discover -s tools -p 'test_*.py'
python tools/validate_db_design.py
python tools/audit_schema_isolation.py
ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
python tools/verify_ddl_matches_schema.py
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=2
```

pytest와 DDL 검사는 새 전용 `DATABASE_URL`/`TEST_DATABASE_URL`을 설정한다.도구의 로컬 CI dry-run 테스트는 `.env`의 존재를 요구한다. 테스트용 합성 주소만 임시 준비하고 검사 후 제거한다. 실제 화면 재현은 위1~8 순서를 따른다.
