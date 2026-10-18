# GW·WMS 통합과 10인 인수 검증 · GW-COMPANY-05

2026-10-18. 사용자 ‘WMS main과 스키마 통합·실운영 인수 검증’ 승인, 추가 조건은 **회사1개·부서1개·총10명, 창업 전 준비용 최소 구성**이다. GW `7b41850`과 로컬 main `9f6cf36`을 `codex/gw-company-01`에서 통합했다. 최종 커밋은 `git log -1`로 확인한다.

**판정: 통합·합성 기술 검증 완료, 실제 회사 시범·운영 인수 미완료.** 검증 완료분은 기존 로컬 반영 요청에 따라 로컬 main에만 반영하며 origin push·배포·실회사 계정/정책 변경은 하지 않는다. 실제 인수 조건은 [10인 운영 준비서](../operations/GW_10인회사_인수_운영준비_GW-COMPANY-05.md)에 구분했다.

## 통합 결과

제품 코드의 자동 병합 결과를 보존하고 스키마·생성 문서를 합쳤다. WMS 품목/LOT·보류·해제 코드와 GW 회사 인증·협업 화면을 모두 포함한다. 다른 작업자가 사용 중인 원본 `factory-studio` checkout은 변경하지 않았다.

- WMS main의 메타데이터 순번을 기준으로 승인된 GW 보안5표를 추가했다. schema 버전을 중복된0.26에서 **0.27.0**으로 올리고 현재 task/head를 GW-COMPANY-05/`gw_wms_merge`로 기록했다. 최종 **210표·2295컬럼·524FK**다. 업무 교차 FK는 추가하지 않았다.
- 새 revision `20261018_gw_wms_merge.py`의 부모는 **`w2b1_wms`와 `gw_company_identity`**다. 이미 적용된 두 migration 파일은 원본과 byte 단위로 동일하며 수정·재생성하지 않았다.
- 새 통합 revision은 GW 분기의 추가 제약/인덱스 이름51개만 통합 명세의 순번으로 바꾼다. 기존 WMS 제약 이름은 보존한다. 업무 행·보안 이력을 덮어쓰거나 새 업무 표를 추가하지 않는다.
- 현재/목표 schema·검증 보고·Excel2종·모듈 ERD를 함께 재생성했다. 현재 Excel51시트/내부링크623, 목표83시트/링크1094, 파일의 오류 셀0. Artifact Tool로 변경 전후 렌더·오류 검사와 저장 파일 재읽기를 확인했다. 목표381표는 미래 설계이며 실제210표와 구분한다.
- WMS의 기존 도구 검사에서 task명이 W2b일 때만23표를 기대하던 분기를 GW-COMPANY-05에도 적용했다. 검사를 완화해 WMS 표 수 불일치를 숨기지 않는다.

## 데이터 보존·마이그레이션 경로

새 전용 PostgreSQL18.6 DB에서 다음3개 출발점을 각각 시험했다. 실제 회사 DB에 migration을 적용하지 않았다.

| 출발점 | 보존한 합성 자료와 확인 |
|---|---|
| `w2b1_wms` | 기존 전 모듈 원장·계정·회사와 추가 WMS LOT1건을 만든 뒤 통합. 기존 컬럼의 행 수/hash 일치 |
| `gw_company_identity` | 기존 전 모듈 원장·계정·회사와 GW 보안 설정 이력을 만든 뒤 통합. 기존 행 수/hash 일치 |
| 공통 `flow_board_custom` | 공통 스키마·원장·회사에서 양쪽 migration을 적용. 기존 행 수/hash 일치 |

각 경로에서 통합 후 DDL0·단일 head를 확인했다. 새 merge revision의 **이름 변경만 되돌렸다 재적용**해210표 행 지문 불변·DDL0을 다시 확인했다. 이는 부모 스키마를 삭제하는 운영 downgrade 시험이 아니다.

두 부모를 가진 지점의 `alembic downgrade -1`은 실제로 `Ambiguous walk`가 발생한다. 운영 복구에 사용하지 않는다. 특정 부모를 지정해 돌아가면 반대 분기의 표를 제거할 수 있고 GW 보안 이력이 있으면 기존 guard가 중단한다. 운영 대응은 원인별 forward fix 또는 폐쇄 백업 복원으로 정리했다.

## 10인 최소 구성과 동시성

관리자1명(OWNER·HR ADMIN·GW 관리5역할 겸임)과 일반 직원9명을 동일 부서에 구성했다. 기존 공개 계정이나 비밀번호를 바꾸지 않고 매번 새 합성 계정과 무작위 임시 비밀번호를 생성했다. 실제 직원·담당자 실명은 미정이며 문서에 넣지 않는다.

1. HR 사용자 등록→GW HR 명시 가져오기→관리자 연결 요청→각 직원9명의 별도 로그인/본인 동의로10개의 ACTIVE 연결을 확인했다. 이름·직무 표시를 관리 권한으로 대신 사용하지 않았다.
2. ASGI/실제 DB 동시10 작업자: 대시보드100조회, 본인 게시 초안10개, 그룹 메시지10개와 같은키 재시도10건. 다른 계정의 초안10건은404, 메시지10건은 고유 순번10개로 보존됐다. 혼합 실행6.280초.110개 혼합 표본의 p50 102.32ms/p95 4250.22ms는100개의 조회와10개의 복합 쓰기 시나리오를 합친 값이며 단일 API 지연시간이 아니다.
3. **실제 로컬 HTTP 서버**에서도10계정·최대 동시10으로 대시보드100요청 성공. 전체0.943초, 조회 p50 88.32ms/p95 120.50ms/최대155.28ms. 그룹 메시지10건·같은키 재시도10건도 중복 없이 성공했다.
4. Chrome G-07 실제 화면에 관리자1명·직원9명이 표시되고 연결 완료10개임을 확인했다.

이 수치는 같은 Mac/로컬 DB에서 다른 회귀 검사도 진행하던 단발 시험 결과다. 운영 서버의 지속 부하·모바일 네트워크·최대 지원 용량·회사 응답시간 약속으로 확장하지 않는다. 쓰기가 회사 잠금을 통해 직렬화되는 조건도 운영 규모가 커지면 별도로 측정한다.

## 폐쇄 백업·복구 리허설

10개 본인 연결·역할·계정·세션과 전 모듈 합성 원장이 있는 DB를 `pg_dump -Fc`로 백업했다. **원본 백업 후 직원1명의 연결을 정지**해 백업 이후 권한 회수 조건을 만들었다.

1. 새 폐쇄 `_test` DB에 `pg_restore --exit-on-error`로 복원.210표 전체 행 수/hash가 백업 전과 일치했다.
2. 복원된 이전 인증 세션을 모두 무효화. 기존 로그인10개가401로 거부됐다.
3. 새 관리자 로그인으로 별도 보관한 연결 정지를 승인된 API에 다시 적용. 새로 로그인한 해당 직원의 문서 접근403, 관리자 대시보드200을 확인했다.
4. 백업0.443초·복원/대조/접근검사4.720초, dump1,160,877바이트. 실회사 RPO·RTO 목표는 미정이므로 달성 판정을 하지 않는다.

첨부/객체 저장소·키 관리·SSO/MFA 공급자·외부 worker/발송·실환경 장애 전환·대규모 원장 복원은 미검증이다. 단순 백업 성공 로그만으로 복구 인수로 표시하지 않았다. 테스트 DB·복원 DB는 매번 종료/삭제하고 덤프는 메모리에서만 사용했다.

## 실제 제품 화면

통합된 실제 backend/Vite와 Chrome의 별도 임시 프로필을 사용했다. 기존 브라우저 프로필/확장 설정은 바꾸지 않았다.

- 로그인 UI→회사 OWNER 최초 설정→명시 가져오기→직원 본인 동의→결재선 등록.
- 일반 기안 초안 비공개→상신→다른 로그인 승인→저장 댓글·사건 이력. 미저장 입력 취소/계속 편집/공간 이동, 개인 체험과 회사의 담당자 전환 구분.
- 일정 초대/참석→채팅 양방향→390px 전송→회사 도움말 연결. 회사 흐름의 pageerror0.
- 같은 통합 제품의 WMS 합성 게스트에서 LOT 등록→수동 보류/해제→QMS 출처로 수동 보류/해제→2건 이력 보존과390px 표시 확인. **실제 QMS 연계 호출이나 외부 품질 설비 검증을 뜻하지 않는다.**
- 추가10계정의 본인 동의/API 요청과 G-07 직원10명 화면을 확인했다.

화면은 합성 자료의 현재 제품이며 시제품이 아니다. 실휴대폰·실회사·운영 도메인·실데이터 검증은 미실행이다.

## 최종 검사

| 검사 | 결과 |
|---|---|
| backend 전체 기존 수집분 `pytest backend/tests -n4` | **1065 통과·1건 건너뜀**,583.90초, 경고35. native core 미빌드 조건1건 |
| 신규 통합3경로·10인 동시성·복구5검사 | **5 통과**,133.74초, 기존 라이브러리 경고11 |
| 도구 unittest | **138 통과**,16.808초 |
| backend 공식 ruff check/format | 통과·242파일 일치 |
| 현재/목표 정적 명세·R1~R6·실제 DDL | 오류0; DDL hash `99444a3c1c1cdf44e9e1a4e3ed6045546a5f152060f9e9430a427370afa7c1a6` |
| frontend 전체 `--maxWorkers=2` | **606 통과·기존 Flow7 실패**(613건·77파일) |
| frontend lint/format/production build | 통과, 기존 큰 chunk 경고 |
| Excel2종 | 렌더·저장 재읽기·오류 셀0·내부 링크/시트 확인 |
| Chrome·로컬 HTTP | 위 대표 업무·WMS 보류/해제·10계정 조회/메시지 통과 |

**전체 CI 성공/실운영 인수 성공으로 보고하지 않는다.** 새 테스트 작성 초기에 잘못된 fixture 가정(템플릿/반환키)과 merge의 `-1` 사용을 수정했다. 제품 코드에서 성공한 것으로 숨기지 않았으며 최종5건은 수정된 경로로 다시 실행했다. 최초 브라우저 스크립트는 로딩 전에 최초 설정 버튼의 가시성을 판단해 대기 실패했고, 화면 로드 대기와 이미 한국어로 바뀐 상태 문구를 맞춘 뒤 전체 흐름을 재실행해 통과했다.

## 남은 인수와 다음 작업

실운영의 MFA/SSO·추가 인증·계정 복구, 보존/삭제·감사 정책, 회사의 RPO/RTO·운영 담당/비상 복구·실기기/전용 서버 인수는 미완료다. `BUSINESS_READY`는 업무 구현 준비 상태이며 이 P0 운영 증거를 대신하지 않는다. 실제 회사 인수 전 실데이터 도입/운영 완료 표시를 하지 않는다.

인원 구성은 사용자 요청대로 정리했으며 실제 인수 담당자·연락처·보존 기간·인증 공급자를 임의로 확정하지 않았다. 후속 기능 개발은 별도 요청으로 진행한다. 전체 프런트 Flow7 실패와 공통 패널의 계속 편집 후 포커스 복원/회사 OpenAPI 계약·브라우저 종료를 가로지른 불명확 쓰기 복구는 기존 후속 과제로 유지한다.

## 재현 명령

Python3.14·Node24·PostgreSQL18, **새 전용 `_test` DB**를 준비한다. URL/비밀은 비공개 환경 변수로 전달한다. 기존 DB/운영 백업을 이 시험에 넣지 않는다. `PG_TEST_CONTAINER`는 자신이 만든 PostgreSQL18 컨테이너의 이름이며 복구 시험은 그 컨테이너에서 실행한다.

```sh
python -m alembic -c backend/alembic.ini upgrade head
python tools/verify_ddl_matches_schema.py
PYTHONPATH=backend/src:backend python -m pytest backend/tests -n 4 -q --tb=short
PG_TEST_CONTAINER="$GW_TEST_CONTAINER" GW_ACCEPTANCE_REPORT=work/gw-company-05/acceptance.json PYTHONPATH=backend/src:backend python -m pytest backend/tests/test_gw_wms_merge.py backend/tests/test_gw_company_acceptance.py -q --tb=short
python tools/validate_db_design.py
python tools/validate_db_design.py --schema docs/db/schema-metadata/schema-target.json --report docs/db/validation-report-target.json
python tools/audit_schema_isolation.py
python -m unittest discover -s tools -p 'test_*.py'
ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test -- --maxWorkers=2
```

도구 검사 중 로컬 CI dry-run은 임시 `.env`의 존재를 요구한다. 실제 연결 비밀 대신 합성 테스트 주소만 준비하고 반드시 제거한다. Excel은 저장소의 기존 `tools/build_db_design.mjs --artifact`/`--artifact --target`과 승인된 bundled runtime으로 재생성했다. 실제 화면은 위 순서와 제품 회사 도움말을 따라 재현한다.
