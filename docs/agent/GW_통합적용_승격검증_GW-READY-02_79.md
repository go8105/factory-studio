# GW-READY-02 79차 — GW 브랜치 통합 적용·승격 검증

작성일 2026-11-05. 저장소 `factory-studio-gw-company`, 브랜치 `codex/gw-company-01`. 시작 d6a02c7, 고정 main783a2c1, GW 기준4c898ac. 중간 merge/WIP5d3df3f. 최종 결과 확정 전 작성 중인 기록이다.

## 범위와 보존

78차 설계를 GW 브랜치 안에 실제 적용했다. main의 업무 구현과 GW 인증/MFA/복구·운영 구현을 함께 보존하며 shared main/다른 checkout/WMS 개발·원격 push·운영 배포는 변경하지 않았다. main 원문 기록은 [인계](main_인계_783a2c1_통합참조.md)와 [진행 이력](../main_진행이력_783a2c1_통합참조.md)에 보존했다.

새 `gw_main_ready02_merge`의 부모는 `(gw_readiness,fems1)`이다. main 순서와 GW 추가분으로 정식 current를 0.34.0/GW-READY-02-INTEGRATION, 251표/2833열/617FK로 동기화했다. target은 target-0.22.0/390표/4464열/950FK이며 migration_revision=null이다. 목표의 미래139표·18컬럼묶음·BEMS nullable 차이는 실제 승격 대상이 아니다. 기존 approval_step UK2개(c1335/c1546)는 그대로 유지한다. main에서 가져온 공유 WMS migration 파일은 main 바이트 그대로이며 기존 GW migration은 고치지 않았다.

연결 revision은 11표를 일정 순서로 잠그고 전체92객체의 옛 이름/종류·열·CHECK/partial 식·FK/RESTRICT·유효 상태와 새 이름 점유를 먼저 대조한다. 인덱스의 정렬·collation/opclass·NULL 옵션도 확인한다. 이름만 바꾸고 각 객체/소유 인덱스 OID를 다시 대조한다. DROP/재생성·데이터 변경·stamp로 충돌을 덮지 않는다. 역함수는 이 이름만 복구한다. 보안 이력이 있는 DB에 부모 전체 downgrade를 실행하는 기능이 아니다.

## 검증 방법

`tools/gw_integration_check.py`가 전체 컨테이너ID/owner/running·단일127.0.0.1 포트/PG18을 확인한 뒤 새 UUID *_test DB를 만든다. 미리보기DB를 템플릿이나 초기화 대상으로 쓰지 않는다. 검사별 생성DB만 정리한다. `--ci`는 생성한 URL을 `ci_local.sh --owned-url`에 명시 전달하며 `.env`를 읽거나 덮어쓰지 않는다. 자식도 ID/owner/loopback을 재확인한다. CI의 회귀 DB를 비우는 대신 `--empty-roundtrip`이 별도 새 빈DB에서 downgrade base→upgrade head/실DDL을 검사한다. 기존 경로의 기본 동작은 유지하며 dry-run은 접속정보 없이 실행한다.

전체 backend는 `-n 0`으로 실행한다. 복원검사의 전역 DB 목록 대조와 생성/정리가 다른 worker와 경합하지 않도록 한 선택이다. worker 병렬성/성능 용량 검증 결과로 해석하지 않는다. 구형10인 폐쇄복원의 이름 prefix guard는 제거만 한 것이 아니라 기존 `gw_route_verify.validate_restore_container(strict=True)`의 전체ID/owner/loopback 계약으로 교체했다.

UG/UM은 `git archive`로 고정 pin의 backend/tools/metadata를 GW 저장소의 무시되는 work에 내보내 별도 프로세스에서 실행한다. `fs.__file__`이 해당 pin 소스인지 검사한다. 최신 seed를 옛 schema에 실행하지 않는다. UG는 기존 10인 API fixture와 실제 합성 MFA 등록/로그인·복구 코드, 성공/실패 서명 원본, 직원 거부를 남긴다. UM은 기존 seed·회사/실제 로그인 API 세션과 명시적인 합성 CMMS설비/QMS계측기 행을 남긴다. main 추가32표 전부에 업무 데이터를 넣은 것은 아니다. 승격 전 원래 컬럼/행 지문, 이름 역/순 후 지문·객체 OID/유효성, 현재 DDL을 대조한다. UM 세션은 PASSWORD 기본값이며 MFA 표는 비어 있어야 한다. 실제 계정/키/회사 데이터는 사용하지 않는다.

UF는 양쪽 부모까지 적용한 별도 빈 합성DB에 누락·새 이름 점유·CHECK 변조·중간 예외·권한 부족·인덱스 옵션 변조를 주입한다. 실패 시 이름/객체 OID·행 지문·head가 그대로인지 확인한다. 이 부정 주입을 모든 UG/UM 유데이터 스냅샷 조합에 반복한 것은 아니다. UR은 빈DB와 UG/UM 유데이터에서 이름 역/순 후 원래 컬럼/행·OID·head/DDL을 확인한다.

## 현재 실행 기록과 한계

- U0 초기 실행: migration/실DDL251표·2833열·617FK, 스키마6pass, 생성DB 제거.
- 집중 초기7pass: UG/UM·UR·누락/점유/정의/중단. 이후 권한부족·인덱스 옵션 검사와 유데이터 역/순 확인을 보강한 최종9건은 pytest 통과했다. 다만 동시 CI 생성DB를 새 자원으로 감지해 실행기의 자원 검사가 종료1이므로 CI 종료 후 단독 재실행을 남겼다.
- 프런트 초기 전체822pass, type/lint/format/build 확인. 도움말 후속 문구의 최종검사는 전체CI에서 다시 실행한다.
- 도구 초기138건 중4failure/1error: .env 의존dry-run·옛 GW표개수 기대·목표 재생성의 미지원 운영4표. 문안/기대만 낮추지 않고 4표/관계/제약/상태 원문 보존 검사를 추가해138pass 확인.
- 전체 backend Ruff의 기존 I001 76건은 import 순서만 정리했다. 초기 main 증인은 비어 있는 CMMS/QMS seed를 잘못 기대해 실패했고 기준 pin에서 합성 행을 명시 추가해 통과했다. 인덱스 검사 SQL의 예약어 alias 오류는 실제 빈DB 적용에서 확인해 수정했고 재검증 중이다. 실패를 과거 성공으로 대체하지 않는다.
- Excel은 번들 artifact-tool로 재생성·재계산/오류 검사 후 다시 가져와 GW 시트를 렌더 확인했다. current51시트/native링크716, target83시트/링크1113, 셀오류0. 실제 Microsoft Excel 앱 검증은 아니다. ERD current/target도 각각 재생성했다.
- 전체CI/최종9건은 실행 중이다. 최종 검증 결과를 확정하기 전 완료로 표시하지 않는다.

ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL·ACCEPTANCE PASS 거부는 유지한다. 보존한 옛 정책/버전·최신 실패/회수/보류·원본 없는 기록을 현재 성공으로 재분류하거나 재서명하지 않는다. 외부 공급자·독립 최신성·전체 권한 회수·실회사10인 인수/실API 브라우저·운영전환은 이 합성 승격/회귀로 확인하지 않는다. 작은 도움말 보완을 UI 전체 완성으로 보고하지 않는다.

## 재현

모든 명령은 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`에서 실행한다. ID 파일은 현재 소유 컨테이너의 전체ID와 대조하며 다른 컨테이너로 무단 교체하지 않는다. private-output은 새 work 경로를 사용한다. 원문 로그·접속값·키는 출력하거나 Git에 넣지 않는다.

```sh
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase79/reproduce-upgrade --test-node backend/tests/test_gw_main_integration.py
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase79/reproduce-ci --ci
backend/.venv/bin/python tools/validate_db_design.py
backend/.venv/bin/python tools/audit_schema_isolation.py
backend/.venv/bin/ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py
git diff --check
```

공급자 연결을 임의 가정하지 않는다. 다음 작업은 이번 최종 결과를 바탕으로 결정하며 다른 ID를 자동 시작하지 않는다. 인증/보존·운영 전환 경계의 후속 검증은 GPT-6 Astra + High를 제안한다.
