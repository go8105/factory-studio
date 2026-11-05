# GW-READY-02 79차 — 통합 구현·집중 검증 완료 / 전체 CI 시각 차단

2026-11-05. `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`. 시작d6a02c7, 고정 main783a2c1/GW4c898ac. merge/WIP5d3df3f·d24cfb0·a0cbb9f·364f529·117bd77. 마지막 커밋은 `git log -1`로 확인한다.

**통합 구현과 집중 승격 검증은 완료했지만 전체 CI는 미통과다.** 고정 소스 실행 중 실제 DB 시각 역전과 호스트 시각 불일치를 확인했다. 권한 대조의 오래된 시각 거부를 완화하지 않았고, 전체 회귀/빈 DB 전체 왕복·실환경 인수를 완료로 표시하지 않는다. 다른 ID를 시작하지 않는다.

## 적용한 범위

GW 브랜치 안에서 main783a2c1의 기존 업무 구현과 GW 인증/MFA/복구·운영 구현을 통합했다. shared main/다른 checkout·병행 WMS 개발·원격 push·운영 배포는 변경하지 않았다. main 기록은 접속 URL을 비공개 처리한 참조본으로 [인계](main_인계_783a2c1_통합참조.md)와 [진행 이력](../main_진행이력_783a2c1_통합참조.md)에 보존했다.

새 revision `gw_main_ready02_merge`의 부모는 `(gw_readiness,fems1)`이다. main 순서와 GW 추가분으로 current0.34.0/GW-READY-02-INTEGRATION, **251표/2833열/617FK**를 동기화했다. target은 target-0.22.0/390표/4464열/950FK, migration_revision=null이다. 미래139표·18컬럼묶음·BEMS nullable 차이는 실제 승격에 넣지 않았다. 기존 approval_step UK2개(c1335/c1546)는 유지했다. main의 공유 WMS migration 바이트는 그대로 수용했고, 기존 GW migration을 고치지 않았다.

연결 revision은 11표를 일정 순서로 잠그고 전체92객체의 옛 이름/종류·열/순서·CHECK/partial 식·FK/RESTRICT·유효 상태와 새 이름 점유를 먼저 대조한다. 인덱스 정렬·collation/opclass·NULL 옵션도 확인한다. 이름만 바꾸고 객체/소유 인덱스 OID를 다시 대조한다. DROP/재생성·데이터 변경·stamp로 충돌을 덮지 않는다. 역함수는 이 이름만 복구하며 보안 이력 보유 DB의 부모 전체 downgrade가 아니다.

Excel은 번들 artifact-tool로 current51/target83시트를 생성·재계산/오류 검사하고 다시 가져와 GW 시트를 렌더했다. native링크716/1113·오류셀0, 모든 표 식별자와 표/열/FK 행 수, ERD 해시/내장 명세의 원본 일치를 최종 파일로 확인했다. [정적 산출물 QA](../../outputs/gw-readiness-02-phase79/artifact-qa.json). 실제 Microsoft Excel 앱 검증은 아니다.

## 기존 도구 연결과 실행 안전성

`tools/gw_integration_check.py`는 전체 컨테이너ID/owner/running·단일127.0.0.1 포트/PG18을 확인한 뒤 새 UUID *_test DB만 만든다. 미리보기 DB를 템플릿이나 초기화 대상으로 쓰지 않는다. `--ci`가 생성한 URL을 `ci_local.sh --owned-url`에 명시 전달하고 자식도 소유/loopback을 확인한다. `.env`를 읽거나 덮어쓰지 않는다. 회귀 DB를 비우는 대신 `--empty-roundtrip`이 별도 새 빈DB에서 부모 전체 왕복을 검사하도록 연결했다(이번 전체 왕복은 시각 차단으로 미실행).

owned CI의 JUnit/basetemp는 private work에 둔다. 추적 코드·테스트·metadata·CI설정의 실행 전후 지문이 다르거나 새 DB가 남으면 통과로 반환하지 않는다. 전체 backend는 복원/전역 DB 목록 검사와 worker 경합을 피하려 `-n 0`으로 실행한다. 병렬 실행 검증 결과가 아니다. 고정 source pin 검사를 위해 CI checkout fetch-depth0을 명시했지만 실제 GitHub Actions 실행은 하지 않았다.

구형10인 폐쇄복원의 이름 prefix guard는 기존 `gw_route_verify.validate_restore_container(strict=True)`의 전체ID/owner/loopback 계약으로 교체했다. 별도 복원기·수집기나 외부 공급자를 추가한 것이 아니다.

`gw_integration_sources.pinned_source`는 전체 SHA를 고정해 `git archive`로 backend/tools/metadata를 이 GW 저장소의 work에 내보내고 정리한다. `fs.__file__`도 해당 pin 소스인지 확인한다. 최신 seed를 옛 schema에 실행하지 않는다.

## 실제 통과한 검증

- **U0 초기**: 새 DB migration/실DDL251표·2833열·617FK, 스키마6pass/생성DB 제거. 이후 최종 단독9건 실행도 실제 migration/실DDL0으로 시작했다.
- **최종 단독 승격9pass/0skip**: GW/main pin의 유데이터 승격2, 이름 역/순1, 누락/점유/CHECK 변조/중간 중단/권한 부족/인덱스 옵션 변조6. source a0cbb9f, 추가DB잔존0/생성DB제거true.
- UG는 기존10인 API fixture와 실제 합성 MFA 등록/로그인·복구 코드·성공/실패 서명 원본·직원 거부를 남겼다. UM은 기존 seed/회사·실제 로그인 API 세션과 합성 CMMS설비/QMS계측기 행을 남겼다. 원래 컬럼/행 지문과 유데이터 이름 역/순 후 OID·head/DDL을 대조했다. UM 세션 PASSWORD 기본값/MFA 미생성도 확인했다.
- UF는 양쪽 부모까지 적용한 별도 빈DB에 주입했다. 권한 거부는 SQLSTATE42501, 중단은 실제 두번째 rename에서 발생했는지 확인했다. 모든 UG/UM 유데이터와 모든 실패 주입을 조합한 검증은 아니다. main 추가32표 전부에 업무 행을 넣거나 회수/보류 파일 원장의 복합 승격을 검증한 것도 아니다.
- **기존 선행3분기3pass**: 옛 WMS/GW/Flow branch의 seed도 고정GW pin으로 보정한 뒤 실DDL/보존·정리 확인.
- **최종 프런트822pass/0skip**, typecheck/lint/format/build 모두exit0. 실제 API 로그인 후 브라우저/1440·390 시각 회귀 검증은 아니다.
- **도구 전체144pass**(시각 보호5건 포함), backend/신규 실행기 Ruff·포맷430파일, bash 문법, 정적DB/R1~R6·문서/JSON/diff 확인. 기존 I00176건은 import 순서만 정리했고 GW전용70파일의 비import AST 보존과 main migration 바이트 일치를 확인했다.

## 전체 CI 미통과와 시각 사전검사

첫 전체CI는 최신 main의 RECEIVING seed를 옛 c781 제약에 넣어 선행분기2건이 실패했다. 제품 migration/제약을 낮추지 않고 fixture를 pin seed로 보정해3분기3pass 확인했다. 첫 실행은 정상중단했고 **2035pass/2fail/2skip/1deselected·53분19초**는 부분 기록이다. 중간 fixture import 누락 오류1은 보정했다.

고정 a0cbb9f 소스 전체CI는 **1510pass/1fail/1skip/1deselected·36분16초**에서 중단했다. `test_closed_restore_post_visibility[POST_ORG_SCOPE]`가 실제 도구의 ‘백업보다 오래된 권한 대조 기록’ 거부를 받았다. 해당 합성 backup 증거는 DB 시작보다 host 완료가 약0.19초 빠른 역전을 보였다. 실행 전후 추적 소스 지문은 `42d1108b9ed60d84641aae36e34c9ee215152e6432ff044ed711bab19bb644ac`로 동일했다. 추가DB잔존0/생성DB제거true. 같은 case의 별도 재검사는1pass/정리 확인했지만 전체CI 실패를 이 성공으로 대체하지 않는다.

읽기 전용10회 DB 시각 관측에서 역전1회를 확인했다. 개선된20회 사전검사는 SQL 왕복의 host before/after 범위를 사용해 쿼리 지연을 시각 오차로 오인하지 않으며, DB가 그 범위를 **2027.257ms** 벗어난 것을 관측했다. host/image 모두 ARM64, privileged=false, 시각 강제변수 없음. 정확한 VM/호스트 동기화 원인은 아직 확정하지 않았다. 서버·Docker·OS 시각 설정/재시작이나 CPU 설정은 변경하지 않았다.

시험 실행기에만 DB 생성 전 시각 사전검사를 추가했다. DB/host 역전 또는 host 관측 범위 밖250ms 초과는 **CLI 전용 `GW_TEST_CLOCK_UNSTABLE`**로 거부한다. 실제 실행에서 databaseCreated=false/검사 stages빈목록/시각거부를 확인했다. 250ms는 로컬 시험 하네스 기준이며 운영 백업의 허용 시각 정책·12개 전환 조건·최종4조건·화면의 허용7코드를 바꾸지 않는다. 20회 표본 통과는 연속 안정성이나 인수 통과의 증거가 아니다.

시각보호5건은 일치/DB역전/host역전/쿼리지연/host범위밖을 구분해 통과했다. `--clock-check-only`는 시험DB를 만들지 않고 표본만 읽는다. 시각이 불안정한 동안 장시간 전체 CI를 반복하거나 보호를 낮추지 않는다. source a0의 단독 승격과 이후 하네스 시각보호 변경의 검증 범위를 구분한다. 남은 전체backend/성능1건·빈DB 부모 전체왕복과 단일 전체CI는 완료하지 않았다. 별도 프런트 통과도 전체CI 완료가 아니다.

## 자원·운영 상태와 다음 작업

생성 rootDB와 pin 임시폴더의 잔존0을 읽기 확인했다. 소유/loopback 확인 후 생성한 자원만 삭제했고 미리보기DB/실계정·MFA/비밀번호·브라우저 설정은 바꾸지 않았다. 마지막 수신 확인은 API127.0.0.1:8362/PID47906, Vite127.0.0.1:5362/PID47907이다. PID는 다음 실행에서 다시 확인한다.

ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL·ACCEPTANCE PASS 거부는 유지한다. 보존한 옛 정책/버전·최신 실패/회수/보류·원본 없는 기록을 현재 성공으로 재분류/재서명하지 않는다. 외부 공급자·독립 최신성·전체 권한 회수·실회사10인 인수/실API 브라우저·운영전환은 미완료다. 작은 도움말 보완을 UI 전체 완성으로 보고하지 않는다.

**다음은79차 잔여 작업**이다. 병행WMS/미리보기에 영향 없는 방식으로 host/Docker/PG 시각 안정성 원인을 확인하고 안정된 소유 검증 환경에서 전체CI를 재실행한다. 공유 Docker/서버 설정·재시작은 이번 저장소와 새 시험DB 범위를 넘어가므로 임의 실행하지 않는다. 전체CI가 끝난 뒤 실제 API/브라우저와 실회사 인수를 별도로 진행한다. 다른 ID를 자동 시작하지 않는다. 환경 시각·증거 현재성·인증/복원 경계가 함께 얽혀 있어 기존 GPT-6 Astra + High 제안을 유지한다.

## 재현

모든 명령은 이 GW 저장소에서 실행한다. 현재 전체ID/owner/loopback을 대조하며 private-output은 새 work 경로를 쓴다. 비밀번호·OTP·키·원문 로그는 출력하거나 Git에 넣지 않는다.

```sh
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase79/reproduce-clock --clock-check-only
backend/.venv/bin/python -m unittest discover -s tools -p 'test_*.py'
backend/.venv/bin/ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py tools/gw_integration_check.py tools/test_gw_integration_clock.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py tools/gw_integration_check.py tools/test_gw_integration_clock.py
git diff --check
```

안정된 환경에서만 아래를 각각 단독 실행한다. 짧은 clock 표본 통과만으로 장시간 안정성을 확인했다고 간주하지 않는다.

```sh
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase79/reproduce-upgrade --test-node backend/tests/test_gw_main_integration.py
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase79/reproduce-ci --ci
```
