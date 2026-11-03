# GW-READY-02 77차 — 현재 GW 회귀와 main 통합 전 차이

2026-11-03. 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`. 시작 `fceb68f`/깨끗한 작업 트리. 사용자 다음 진행 승인으로 회귀와 읽기 검토를 수행했다. 이번 단계에서 다른 checkout·병행 WMS·main 코드/DB를 수정하거나 병합·push·배포하지 않는다.

## 비교 기준

`git fetch origin main`으로 조회한 원격 main은 `783a2c1`이다. 공통 기준은 `2be292ee06778c26fadc1336aa6a12134f8846aa`, 시작 GW 전용85커밋/main 전용90커밋이다. 이 숫자는77차 결과 커밋 이전 스냅샷이다. `git merge-tree --trivial-merge <base> HEAD origin/main`으로 작업 트리·index·브랜치를 바꾸지 않고 차이와 충돌 위치만 확인했다. 통합 소스 생성/실행이나 충돌 해소 완료를 뜻하지 않는다.

| 항목 | 현재 GW | 조회한 main | 통합 전에 확인할 것 |
|---|---|---|---|
| migration head | gw_readiness | fems1 | 단순 파일 합치기로는2heads. 적용 이력을 보존하는 새 연결 revision/승격 경로 설계 필요 |
| metadata |219표·GW28표 |242표·GW24표 | 양쪽 업무/인증 구조를 보존하고 current/target·Excel·ERD를 같은 작업에서 재생성/대조 |
| 변경 경로 | 시작292개 |239개 | 시작 양쪽15경로,77차 보정 후16경로. 자동 병합 가능과 동작 정합을 구분 |
| 텍스트 충돌 | 시작8파일·14구간,현재9파일·15구간 | 동일 | 메타데이터/ERD/검증 보고서·진행/인계 문서는 현재 사실을 보존해 재작성 |
| binary 충돌 |DB설계서.xlsx | 동일 | 한쪽 파일 선택으로 끝내지 않고 통합 metadata로 재생성/검증 |

시작 텍스트 충돌 파일은 HANDOFF, ERD HTML/README/all.mmd, schema.json/schema-target.json, validation-report.json, progress.md다. 시작 경로/구간 수는 [초기 읽기 보고서](../../outputs/gw-readiness-02-phase77/main-review.json)에 고정했다.77차의 test_gw_wms_merge.py 보정도 main과 겹쳐 현재는16경로, 텍스트9파일15구간/Excel1충돌이다. [현재 작업 소스 재대조](../../outputs/gw-readiness-02-phase77/current-merge-review.json)는 원본/기준/main의 work 복사본을 git merge-file -p로 확인했다. 실제 소스/index/브랜치는 병합하지 않았다. 나머지 공통 변경 파일인 API 등록/App 라우팅·문서 등록/현황·검증 스크립트도 자동 병합 결과만으로 완료 처리하지 않는다.

GW에만 있는9표는 core의 authentication_challenge/authentication_throttle/mfa_factor/recovery_code/sso_identity와 GW의 operating_evidence/operating_policy_revision/operating_settings/retention_review다. main에만 있는32표는 CMMS6·FEMS12·QMS9·SPC5표다. 테이블 이름의 단순 합집합은 통합 설계나 실제 DDL 일치를 확정하지 않는다. 공통 표의 열/제약·인덱스·코드/상태/권한과 제약명·downgrade 참조도 대조해야 한다.

동일 revision `w2b1_wms`의 파일 바이트가 다르다. 차이는 main의 downgrade 목록에 추가된 `NORMAL/QUARANTINE` 이외 위치 삭제 SQL 한 줄이다. upgrade 차이로 보고하지 않는다. 이번에 이 downgrade를 실행하거나 WMS 파일을 수정하지 않았다. 기존 적용/공유 revision 불변 원칙과 main의 승인 이력을 통합 단계에서 확인하고, 이번 검토를 이유로 과거 revision을 다시 쓰지 않는다.

## 다음 통합 설계에서 고정할 검증 경로

1. 빈 전용 DB에 양쪽 이력을 적용한 경로와, GW head까지 적용한 합성 DB를 승격한 경로, main head까지 적용한 합성 DB를 승격한 경로를 각각 검증한다. 기존 실제 main/미리보기 DB에서 시험하지 않는다.
2. 두 head를 연결하는 새 revision과 통합 metadata를 기준으로 실제 DDL·S 복합 참조·RESTRICT·정책/부분 유니크·제약명/downgrade 참조를 대조한다. 과거 적용 migration을 고쳐 맞추지 않는다.
3. 각 승격 전후 합성 업무 행·회사/계정·서명 증거/권한 상태를 지문으로 대조하고, 확정 데이터 보존·과거 성공 대체 금지·PASS 차단을 확인한다. 인증/CSRF·제한 세션·회사 범위와 API 등록/App 라우팅은 양쪽 변경을 함께 검증한다.
4. current/target metadata·Excel·모듈/전체 ERD와 검증 스크립트 경로를 함께 갱신한다. 통합 소스에서 전체 CI 또는 승인된 ci:local 대체 검증을 수행한다. 롤백/배포 결정과 원격 push는 별도다.

이는 아직 실행하지 않은 다음 단계의 검증안이다. 이번 회귀 성공으로 위 경로를 통과 처리하지 않는다.

## 안전한 회귀 실행

`tools/gw_integration_check.py`는 인자로 받은 전체 컨테이너 ID 파일·owner 라벨·running·단일 IPv4 loopback 포트·PG18을 확인한 뒤 새 `gw_integration_<UUID>_test` DB를 만든다. 프리뷰 접속 자료/DB를 읽어 테스트 대상으로 복제하지 않으며 컨테이너 소유 PostgreSQL 접속값은 내부에서만 사용한다. URL/비밀번호/전체 pytest 로그는 출력하지 않는다. 마이그레이션→실제 DDL 대조→GW80파일 회귀를 순차 실행하고 생성 DB만 정리한다. 예상 밖 새 DB가 남으면 자동 삭제하지 않고 실패로 남긴다.

실행 대상은 저장된 전체 ID `f992fe7e3c8dab0c4ac0b13e6bddd0ea9ba14be0d02e84fb63ac5a0b47cfa7f3`, owner `gw-ready-02-preview`, 단일 `127.0.0.1:55439`의 `fs-gw-ready02-preview`다. 이는 조회 시점 자원 기록이며 다른 컨테이너/ID로 자동 대체할 수 없다. 실제 실행 환경이 달라지면 소유부터 새로 확인한다. 잘못된 owner 인자는 DB 연결/생성 전에 종료1로 거부되는 것을 별도로 실행했다.

재현(이 GW 저장소 루트):

```sh
backend/.venv/bin/python tools/gw_integration_check.py \
  --container fs-gw-ready02-preview \
  --expected-id-file work/gw-readiness-02-preview/container-id \
  --owner gw-ready-02-preview --port 55439 \
  --private-output work/gw-readiness-02-phase77/reproduce
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx src/shared/api.test.ts src/portal/account-security.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run build
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm run db:validate
backend/.venv/bin/python tools/audit_schema_isolation.py
backend/.venv/bin/ruff check --config backend/pyproject.toml tools/gw_integration_check.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check tools/gw_integration_check.py
git diff --check
```

예상 ID 파일이 없는 다음 세션은 위 기록의 전체 ID와 실제 소유 자원을 먼저 대조한다. 확인한 ID를 소유자 전용 `work/` 파일에 기록해 `--expected-id-file`로 전달할 수 있다. 새로 inspect한 ID를 확인 없이 신뢰값으로 자동 채우지 않는다. 비공개 preview.json/server.env나 Codex 전용 상태에 의존할 필요가 없다.

## 결과와 한계

[고유 case 분할 집계](../../outputs/gw-readiness-02-phase77/segmented-review.json) · [초기 중단](../../outputs/gw-readiness-02-phase77/initial-run.json) · [전체 재실행 중단](../../outputs/gw-readiness-02-phase77/full-rerun.json) · [잔여 실행](../../outputs/gw-readiness-02-phase77/remaining-run.json) · [자원 정리](../../outputs/gw-readiness-02-phase77/resources.json). 반복 실행 수를 합산하지 않는다. 초기 실패 두 건은 각 보정 뒤 통과했지만, 전체 순서/단일 프로세스 검증이나 main 통합 후 전체 CI를 대신하지 않는다. 생성 원본DB4개와 각 실행의 추가 DB가 남지 않았음을 확인했고, preview DB 존재만 메타데이터로 확인했다(업무 행 미조회).

초기 전체 선택은949통과/1실패/1skip에서 fail-fast로 중단했다(잔여 미실행). 실패는 기존 Flow 왕복 검사가 최신 GW 보안 이력을 포함한 전체 체인을 내려가려 해 이력 보호가 정상 거부한 것이다. 마이그레이션은 고치지 않았다. 검사에 전체 체인 거부/이력 지문 보존을 명시하고, Flow 함수만 폐기 DB에서 직접 역/순이관해 업무·즐겨찾기와 보안 이력/Alembic head 보존을 확인하도록 보정했다. 보정 집중1건 통과, 각 생성 DB 삭제/예상 밖 새DB0. 전체80파일 재실행은1494통과/1실패/1skip에서 중단했다. 추가 실패는 GW/WMS 정규화 검사의 고정 옛 head(`gw_wms_merge`) 기대값이었다. 현재 ScriptDirectory head를 확인하고 정규화 왕복 전후 head 유지로 검사를 보정했다. 제품/적용 migration 파일은 바꾸지 않았다. 이전 통과1494건의 고유 node ID와 전체1601건을 대조해 수정 모듈·실패/미실행·skip107건을 새DB에서 분할 실행했고106통과/1skip으로 종료했다. 현재 수집 목록과 다시 대조한 고유 case 결과는1600통과/1skip·누락0이며, 단일 전체 실행 통과로 보고하지 않는다. 수집 분류는 DB fixture300건/DB fixture 없는1301건이며, DB 중46건은 소유 백업 fixture를 포함한다(중복 범주). 실행 대조는 DB fixture299통과/1skip·DB fixture 없는1301통과이며, 소유 백업fixture46건은 모두 통과했다(중복 범주).

초기skip은 구형10인 폐쇄복원 검사의 PG_TEST_CONTAINER/전용 이름 규칙 미설정이다. 최신 GW 백업/복원 검사에 쓰는 검증된 GW_BACKUP_TEST_CONTAINER와 다른 계약이며, 이름 검사를 임의 완화하지 않았다. skip을 실행 통과로 세지 않는다.

프런트 GW·계정 보안·도움말·공통 API153건/14파일 통과(15.47초). 전체 프런트 build/typecheck도 통과했다. 기존 대용량 청크 및 CAD 의존성의 node:module 외부화 경고는 유지한다. 정적 DB/R1~R6·신규 DB 실제 DDL219표/2409열/543FK 대조 오류0. 시스템 Python3.9의 격리 감사는 구문 분석 오류로 중단됐고, 프로젝트 Python3.14.7로 다시 실행해 통과했다. 재현 명령도 프로젝트 Python을 명시한다. 신규 실행기 작성 중 Ruff3건도 수정 후 재검사 통과했으며, 보정 집중 검사와 전체 재실행은 수정된 실행기로 수행했다.

이번 결과는 현재 GW 브랜치의 합성/격리 검증이다. 통합 main 소스·기존 main DB 승격·전체 backend/frontend/CI·실 API 브라우저/실계정/실10인·외부 공급자 독립성/전체 회수·최종 인수 통과로 세지 않는다. ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL/ACCEPTANCE PASS 거부를 유지한다.

다음은 두 migration head/동일 revision 차이와 metadata·ERD·Excel 충돌을 다룰 통합 설계/해소안을 먼저 확정하는 단계다. 실제 통합·main/운영 반영은 별도 범위이며 이번에는 하지 않았다. GPT-6 Astra + High를 추천한다.
