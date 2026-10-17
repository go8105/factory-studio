# GW 직원 연결·업무 권한 · GW-COMPANY-03

2026-10-17. 사용자 “다음 진행해줘”로 승인된 03 단계. 기준 `824c4de`, 브랜치 `codex/gw-company-01`, WIP `e35eaa3`. **준비 관리 API·내부 업무 서비스 구현 및 로컬 검증 완료.** 최종 커밋은 `git log -1`로 확인한다.

## 구현 범위와 공개 경계

회사 OWNER가 빈 GW를 최초 설정하고, 조직 관리자가 HR 직원을 명시적으로 가져온 뒤 연결 요청을 만든다. 대상 직원은 자기 로그인으로 사번·이름·조직을 확인하고 동의한다. HR 사번이 일치하더라도 자동 연결하지 않는다. 설정·연결·역할 준비 API와 결재·게시 내부 업무 서비스를 구현했다.

**제품의 회사 선택 화면과 기존 63개 회사 업무 경로는 아직 열지 않는다.** `businessReady=false`, `capabilities=[]`를 유지한다. 결재·게시 대표 흐름은 실제 DB를 사용하는 내부 서비스 검증이며, 공개 HTTP 업무 API나 실제 브라우저의 회사 업무 완료를 뜻하지 않는다. 기존 개인/게스트 체험은 별도 회귀 대상이다.

DB 구조는 02의 `gw_company_identity`/schema0.26.0(198표·2151컬럼·488FK)을 그대로 사용한다. 신규 표·마이그레이션·Excel·ERD 변경은 없다. 사용자 계정·정책·실제 회사 원장은 변경하지 않는다.

## 직원 연결·역할

- 최초 설정은 현재 활성 회사 OWNER 본인과 HR 직원 연결이 있는 빈 회사 GW에서 한 번만 실행한다. 본인 1명을 ACTIVE로 연결하고 명시적 관리 역할 5개를 부여한다. AUDITOR는 자동 부여하지 않는다. 같은 멱등 키의 동시 재시도도 중복 생성하지 않는다.
- HR 가져오기는 기존 스냅샷 가져오기 함수를 같은 회사 트랜잭션 안에서 재사용한다. HR에 쓰지 않고, 역할/계정 연결을 자동 생성하지 않는다. HR 퇴사 표시만으로 기존 GW 접근을 자동 회수하는 정책은 아니다. core 계정/회사 소속 정지 또는 GW 직원/연결 정지를 구분해 처리한다. 미리보기 digest가 바뀌면 다시 확인한다.
- ORG_ADMIN이 같은 회사의 활성 계정과 동일 HR 사번의 GW 직원을 선택해 PENDING 요청을 만든다. 본인만 expectedVersion을 확인하고 수락한다. 미수락 요청은 취소 후 새 요청 가능하다.
- 활성화된 직원·계정 쌍은 바꿀 수 없다. SECURITY_ADMIN은 같은 쌍의 정지/복귀만 처리한다. CANCELLED 이력은 보존한다.
- GW 역할은 ORG_ADMIN/ROUTE_ADMIN/POLICY_ADMIN/BOARD_PUBLISHER/SECURITY_ADMIN/AUDITOR다. 역할 변경은 personVersion CAS로 처리하고 보안 감사와 authzVersion을 기록한다. HR 관리자·회사 OWNER·직무 표시 BOARD_ADMIN은 업무 본문 권한을 대신하지 않는다.
- 마지막 활성 SECURITY_ADMIN의 역할 제거·연결 정지는 409다. 두 관리자가 동시에 마지막 권한을 제거하려 해도 회사 잠금으로 직렬화한다. core 긴급 정지·실운영 복구 인수는 이 보호로 대체하지 않는다.

## 결재·게시 내부 서비스

- 회사 요청의 처리자는 서버의 활성 본인 연결에서 결정한다. actingPersonId가 있는 요청은 거부한다. 회사 준비 API의 personId 조회 매개변수도 거부한다. 상대방 personId는 같은 회사의 활성 연결 직원인지 따로 확인한다.
- GENERAL만 생성/열람한다. 외부 ERP/PLM 원천 선택·갱신을 차단한다. 일반 결재는 기존 순차/병렬·합의·참조·전결 처리 함수를 재사용하며, 회사 처리자와 활성 계정 검사를 추가한다.
- 초안은 기안자만 읽는다. 상신 후에는 기안자·유효 배정 참여자·실제 처리자·명시적 열람자만 읽는다. 현재 유효한 위임자는 원 담당자의 계정/연결도 활성일 때 현재 대리 업무를 읽고 처리한다. 위임이 만료·회수되면 새 접근을 막고 실제 처리 이력은 보존한다.
- 문서 ACL을 SQL WHERE에 적용한 뒤 검색·건수·페이지를 계산한다. 열람 불가한 이전/후속 문서 링크는 응답에서 숨긴다. 재상신 초안은 이전 결재자에게 노출하지 않는다.
- 기안자가 상신 문서의 읽기 권한을 부여/회수한다. documentVersion CAS와 사건을 기록한다. 열람 권한은 결재 권한을 만들지 않는다.
- 비활성 계정/직원 때문에 막힌 WAITING 단계만 재배정한다. 원 approval_step/상신 스냅샷은 수정하지 않고 step_assignment를 추가한다. 자기 자신·기안자·이미 다른 단계에 배정된 사람으로는 바꿀 수 없다. 재배정된 담당자만 유효 배정을 사용하고, 이전 담당자는 별도 권한/실제 처리 이력이 없으면 복귀 후에도 읽지 못한다.
- 막힌 결재 목록에는 문서/단계/담당 식별자·순서·참여구분·문서 버전만 제공한다. SECURITY_ADMIN에게 제목·본문·금액을 자동 공개하지 않는다.
- 게시 초안은 작성자만, 게시된 회사 글은 활성 연결 직원, 조직 글은 현재 직접 소속/작성자만 읽는다. 공지는 명시적 BOARD_PUBLISHER가 필요하다. 작성자의 수정·정정·철회도 현재 권한을 재검사한다. 직무 표시 문자열을 보안 역할로 바꾸지 않는다.
- 회사 변경·조회는 02의 회사→계정→세션 잠금을 사용한다. 변경은 현재 역할/객체 접근 권한을 성공 영수증보다 먼저 확인한다. 연결/역할/문서 읽기 권한 회수 후 저장된 원문 응답을 재노출하지 않는다. 권한 부여 당시 이미 전달한 응답까지 회수한다는 의미는 아니다.

## 준비 API

모든 경로는 `/api/v1/gw` 아래다. `/companies` 외에는 companyId가 필수다. 변경은 CSRF/Idempotency-Key, 기존 행은 expectedVersion이 필수이며 알 수 없는 입력은 400이다. 관리 변경 사유는 공백을 제외한 2~500자다. 본인 연결 동의는 별도 사유 입력을 요구하지 않는다.

| 경로 | 사용 범위 |
|---|---|
| GET /companies, /me | 활성 소속/본인 연결·역할·준비 상태 |
| GET/POST /company-setup | OWNER 본인 HR 확인/빈 GW 최초 설정 |
| GET /identity-candidates | ORG_ADMIN의 활성 회사 계정 이름·식별자 검색/페이지 |
| GET /company-hr-preview, POST /company-hr-import | ORG_ADMIN 명시적 HR 스냅샷 준비 경로. 기존 /hr-preview·/import-hr의 회사 모드는 04 전체 경로 통합 때 연결 |
| GET/POST /identity-bindings | ORG_ADMIN 요청 생성, ORG_ADMIN/SECURITY_ADMIN 최소 연결 상태 목록 |
| GET /me/binding, POST /me/binding/accept | 본인 요청 확인/동의 |
| POST /identity-bindings/{id}/cancel | ORG_ADMIN의 미수락 요청 취소 |
| POST /identity-bindings/{id}/suspend, /resume | SECURITY_ADMIN의 동일 쌍 정지/복귀 |
| GET/PATCH /people/{id}/roles | SECURITY_ADMIN 명시적 역할/직원 버전 관리 |
| GET/POST /documents/{id}/readers, PATCH /documents/{id}/readers/{personId} | 기안자의 열람자 목록/부여/회수 |
| GET /blocked-assignments, POST /documents/{id}/reassign-step | SECURITY_ADMIN 최소 목록/막힌 단계 재배정 |
| GET /security-events | SECURITY_ADMIN/AUDITOR의 최소 사건 메타데이터, 본문 없음 |

## 검증 결과

- 전용 합성 PostgreSQL18 `factory_studio_gw_company_test`, 로컬 55437만 사용한다. 공유 개발 DB/운영 DB에 적용하지 않는다.
- 새 회사 시나리오16개 + 기존 GW·HR·Flow131개, **관련 검사 합계147개 통과**. 146개 묶음은 6분41초/기존 경고6, 추가 회사 병렬·합의·참조·전결1개는6초/기존 경고2다. HTTP 관리 API와 내부 업무 서비스 검증을 구분한다. 회사 전결 규칙·위임의 테스트 준비는 합성 SQL로 생성했고, 해당 관리 HTTP 경로는04 대상이다.
- 마지막 보완에 대해3개 집중 재검사도 통과(17초/기존 경고2)했다. SECURITY_ADMIN의 최소 연결 상태 목록, 막힌 결재의 문서 버전, 실제 advisory lock 대기를 확인한 뒤 읽기 권한 회수 커밋 후404를 검사했다. 반복 검사를147개에 중복 합산하지 않는다.
- **도구139 OK**, 공식 ruff check/format233파일 통과, db:validate/FS-013 R1~R6 오류0, 전용 DB head/DDL198표·2151컬럼·488FK 대조 오류0. schema 변경이 없어 이번에 Excel/ERD를 재생성하지 않았다. 격리 감사는 프로젝트 Python3.14로 실행했다.
- 본인 생성 전용 컨테이너/볼륨과 임시 자격증명을 제거했다. 실제 계정·공유 DB·운영 서버·main·원격은 변경하지 않았다.
- 최초 문서 검증에서 기존 결재선 정규화 결과가 person_id가 아니라 id를 반환하는 차이를 발견해 회사 검사를 수정했다. 실패 실행을 통과로 합산하지 않는다.
- UI/실브라우저/실휴대폰/실제 회사/MFA·복구·백업 인수, 전체 제품 CI는 실행하지 않는다. 기존 Flow 프런트7실패를 해결했다고 주장하지 않는다.

## 재현·다음 단계

Python3.14 환경과 PostgreSQL18의 **전용 합성 `_test` DB**를 준비하고 DATABASE_URL/TEST_DATABASE_URL을 해당 테스트 DB로만 지정한다. PYTHONPATH는 이 checkout의 `backend/src:backend`로 지정한다. 다른 checkout의 editable install을 암묵적으로 사용하지 않는다. 최초 DB는 `python -m alembic -c backend/alembic.ini upgrade head`와 `python tools/verify_ddl_matches_schema.py`로 준비한다.

```sh
python -m pytest backend/tests/test_gw_company_work.py backend/tests/test_gw_company.py backend/tests/test_hr_work.py backend/tests/test_hr_users.py backend/tests/test_gw.py backend/tests/test_gw_policy.py backend/tests/test_gw_collaboration.py backend/tests/test_gw_organization.py backend/tests/test_gw_projects.py backend/tests/test_flow_custom.py -q
ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
python -m unittest discover -s tools -p 'test_*.py'
```

도구 중 CI dry-run 검사는 합성 `.env`와 Node24/Python 실행 PATH가 필요하다. 실제 DB 자격증명을 문서나 로그에 넣지 않는다. 검증 컨테이너/임시 자격증명은 본인 생성분만 종료·제거한다.

다음 **GW-COMPANY-04**는 기존 63개 업무 경로와 회사 선택/연결/역할·기안 화면, 전결·위임 관리·댓글·일정·알림·채팅 전체 ACL/회수 및 도움말을 통합한다. 내부 업무 함수의 회사 모드 인자를 빠뜨리지 않도록 기존 라우트를 대조하고 UI 캐시·늦은 응답 폐기를 함께 확인한다. 04 완료 전 회사 업무 공개를 열지 않는다. 05의 실제 운영 인수·P0 결정은 별도다. 원격 push·배포·main 병합은 이번에 하지 않는다.

병행 작업으로 로컬 main은 `9f6cf36`(WMS W2b-1a/1b, PWA e02097d 포함)까지 전진했다. 이 작업은 main을 수정하지 않았다. main의 schema0.26.0/205표·`w2b1_wms`와 GW 브랜치의 schema0.26.0/198표·`gw_company_identity`가 같은 `flow_board_custom`에서 갈라졌다. 통합 전 양쪽 스키마·명세 버전과 migration head를 대조해 안전한 병합 revision/재검증이 필요하다. 기존 적용 migration을 고치거나 한쪽 테이블을 덮어쓰면 안 된다. 이번 관련147개 검증은 GW 브랜치 기준이며 최신 WMS main 통합 회귀가 아니다.
