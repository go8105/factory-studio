# GW-READY-02 78차 — main 통합 설계와 승격 검증 계약

작성일2026-11-05. `factory-studio-gw-company` / `codex/gw-company-01`, 시작 `4c898ac`/깨끗한 작업 트리. 사용자가77차 후속 진행을 승인했다. 이 문서는 통합 설계·충돌 해소·승격 검증 기준이며 실제 병합/DB 적용 결과가 아니다. 기존 GW 전체 설계/구현 승인은 유지한다. main checkout·병행 WMS·실계정/미리보기DB·원격push/배포는 변경하지 않았다.

## 1. 고정 입력과 선택

원격을 재조회한 main은 `783a2c1aa6e4f0053d055341f9738226a60dbdc7`, GW는 `4c898ac`, 공통 기준은 `2be292ee06778c26fadc1336aa6a12134f8846aa`다. 시작 시 GW88/main90커밋 분기다. 이후 ref/metadata 버전이 달라지면 재대조한다. 과거77차의 분할1600pass/1skip을 이번 실행이나 통합 후 결과로 표시하지 않는다.

선택은 **main의 현재 metadata 순서를 유지하고, GW 추가분을 뒤에 배치**하는 것이다. 공통210표 중 양쪽이 서로 다르게 동시에 수정한 표는0이다. main에서 변경한 기존 표는 main 정의, main이 유지하고 GW만 변경한 표는 GW 정의를 사용한다. GW 추가9표와 main 추가32표를 모두 보존한다. GW의 기준 제약 삭제/공통 표 동시 수정/새 표 충돌은 자동 선택하지 않고 설계 재검토로 중단한다.

정식 schema.json/schema-target.json·Excel·ERD·migration 파일은 이번에 수정하지 않았다. 구조 초안의 main 설명/이력 필드를 정식 문안으로 확정한 것도 아니다. 실제 통합의 change_log는 version만으로 중복 제거하지 않고 task/date/change/status와 입력 pin을 대조해 양쪽 사실을 보존한다. 후보 JSON은 소유 작업 폴더 `work/gw-readiness-02-phase78/`의 `review_only=true`, `migration_revision=null`인 설계 초안이다. 정식 검증기/실DDL 검증을 통과한 canonical schema로 간주하지 않는다. 재생성 가능한 이름 정규화 목록과 입력 SHA는 [설계 보고서](../../outputs/gw-readiness-02-phase78/integration-plan.json)에 둔다.

| 항목 | 통합 현재 설계 후보 | 목표 설계 후보 |
|---|---:|---:|
| 테이블 |251|390|
| 컬럼 |2833|4464|
| FK |617|950|
| 제약/인덱스/정책 레코드 |1845|2703|
| SERVICE/DB_POLICY |196|249|

정책 레코드는 DB 제약이 아니다. UK_PARTIAL은 조건부 유니크 인덱스다. 목표의 미래139표와 기존 표의 미래 컬럼18묶음은 이번 DB 승격 대상이 아니다. `bems.schedule_slot.hvac_unit_id`는 현재 NOT NULL/목표 nullable 차이를 유지한다. 미래 BEMS 변경을 GW 통합 migration에 넣지 않는다.

## 2. 새 revision과 이름 정규화

예정 ID는 `gw_main_ready02_merge`이며 현재 양쪽 이력에 같은 ID가 없음을 확인했다. **아직 migration 파일을 만들지 않았으므로 현재 실행할 revision이 아니다.** 예정 정의는 아래와 같다.

```python
revision = "gw_main_ready02_merge"
down_revision = ("gw_readiness", "fems1")
```

두 부모의 기존 DDL이 표/컬럼을 만든다. 새 연결 revision은 GW 제약·인덱스73개와 FK19개, 합계92개 이름만 정규화한다. main 쪽 metadata 기준 이름 변경은0이다. core.app_user/core.auth_session과 인증5표/GW운영4표, 총11표에 걸친다.

| 종류 | 수 | 예정 범위 |
|---|---:|---|
| PK/UK |9/13|ALTER TABLE RENAME CONSTRAINT; 소유 인덱스도 함께 대조 |
| CHECK |40|식/검증 상태를 바꾸지 않는 이름 변경 |
| 일반/조건부 유니크 인덱스 |6/5|ALTER INDEX RENAME |
| FK |19|참조 열·대상·RESTRICT·검증 상태 유지 |

제약/인덱스 번호는 `c1549..c1621`에서 `c1772..c1844`, FK는 `r524..r542`에서 `r598..r616`으로 이동한다. 이름 생성 규칙은 기존 tools/build_migration.py를 따른다. 새 이름을 맞추기 위해 DROP/재생성·데이터 수정·버전 stamp를 사용하지 않는다. PK/UK 소유 인덱스를 별도 대상으로 이중 rename하지 않는다.

실행 구현은 한 트랜잭션에서 대상92개와 새 이름 점유를 먼저 대조한다. metadata만으로 실제 DB 이름/정의를 확인했다고 처리하지 않는다. 옛 이름/정의·종류·열·순서·CHECK/partial 식·참조/RESTRICT·유효 상태가 기대값과 다르거나 새 이름이 다른 객체에 사용되면 변경 전에 차단한다. 성공 후에는 객체 OID/유효성·데이터 지문과 최종 DDL을 대조한다. 일부 성공을 수동 이름 변경이나 stamp로 완성하지 않는다.

기존 `gw.approval_step(workspace_id,generation_id,document_id,id)` UK는 `c1335_uk`/`c1546_uk` 두 개가 양쪽 부모에 모두 있다. 적용 이력/참조를 보존하며 이번에 하나로 축약하지 않는다. 설계 도구는 부모에 이미 있는 중복 수를 보존하되 새 중복 증가를 거부한다.

동일 `w2b1_wms`의 파일 바이트 차이는 main의 downgrade 위치 정리 DELETE1줄이다. upgrade 정의 차이는 아니다. main의 공유 파일을 새로 편집하거나 그 DELETE를 실행하지 않는다. 실제 통합 때 main의 기존 파일을 그대로 보존하고, 기존 GW/기존 main DB 승격은 새 revision으로 검증한다.

## 3. metadata·Excel·ERD 충돌 해소

정식 current 제안은 task=`GW-READY-02-INTEGRATION`, version=`0.34.0`, migration_revision=`gw_main_ready02_merge`다. 현재 main metadata의 migration_revision은 `gw_wms_merge`로 남아 있지만 실제 파일 head는 `fems1`이다. 이 오래된 표기를 새 current에 그대로 복사하지 않는다. target은 task=`DSN-90`, base_task=`GW-READY-02-INTEGRATION`, version=`target-0.22.0`, migration_revision=null/target=true로 재기준화한다. 실제 코드/DB 검증 이후의 정식 기록이며 이번에는 제안 값이다.

| 경로/영역 | 해소 기준 |
|---|---|
| schema.json/schema-target.json | 고정 입력3-way 대조, main 순서+GW 추가분, 현재/목표 경계 유지. 설명/이력과 구조 변경을 구분 |
| DB설계서.xlsx/DB설계서_목표.xlsx | binary 한쪽 선택 금지. 최종 current/target에서 기존 도구로 각각 재생성·행/시트/참조·렌더 확인 |
| erd/erd-target 전체·모듈·HTML·README | 각 metadata에서 재생성. 메타데이터 해시·표/FK 수 대조, SVG/HTML과 실제 관계의 차이 유지 |
| validation-report.json/검증 스크립트 | main의 신규 솔루션 기준과 GW 보안/운영 기준을 함께 보존하고 실제 실행 결과로 재생성 |
| backend/src/fs/main.py | GW 인증/MFA/복구·제한 세션 처리와 main 신규 라우터 모두 보존. 등록 순서와 권한 경계를 실행 검증 |
| frontend App/portal docs·content tests | 계정 보안/복구·회사 범위 동선과 main 모듈/도움말을 모두 보존. 키/경로 중복·도움말 누락 검사 |
| GW/WMS 병합 검사 | 고정 옛 head 문자열을 되살리지 않고 현재 head와 왕복 전후 유지·데이터 지문 비교를 보존 |
| 현황/progress/HANDOFF | 양쪽 사실/담당 범위를 보존해 재작성. 통합 검증 전 완료·배포로 승격 금지 |

기존 도구에 확인된 생성 명령은 `npm run db:build`, `node tools/build_db_design.mjs --target`, 프로젝트 Python의 `tools/build_erd.py`와 `--target`이다. 이번에는 실행하지 않았다. 실제 통합 작업에서 current/target·양쪽 Excel·양쪽 ERD를 같은 변경으로 갱신하고 수정 경로 링크를 검증한다. 표 이름 합집합만으로 DB 설계 완료를 판단하지 않는다.

## 4. 승격 검증 행렬

모든 경로는 소유 컨테이너의 전체ID/owner/running·loopback/PG18을 확인하고 새UUID *_test DB를 만든다. 기존 main/미리보기 DB를 템플릿이나 초기화 대상으로 사용하지 않는다. 각 기준 pin의 코드/seed로 합성 스냅샷을 만든다. 통합 후 최신 seed를 옛 schema에 곧바로 실행하지 않는다. 필요하면 기준 소스를 이 GW 저장소의 work에 내보내 별도 프로세스로 실행하며 다른 checkout을 변경하지 않는다.

| ID | 시작 상태 | 승격/검사 | 필수 보존·차단 |
|---|---|---|---|
| U0 | 빈DB | 양쪽 기존 이력+연결revision 적용 | 단일새head·251표/2833열/617FK,92이름,중복UK2개,목표139표 미생성 |
| UG | GW pin/gw_readiness | 합성1회사·1부서·10인/업무·인증·운영 이력 후 main 분기+연결 | 기존 열/행·S·ACL/거부·MFA/복구·키상태·서명 원본/보류/회수 지문 보존 |
| UM | main pin/fems1 | 합성 솔루션 업무/회사·세션 후 GW 분기+연결 | main의 신규32표/업무 행 보존. 기존 세션은 PASSWORD 기본값이며 MFA로 자동 승격하지 않음 |
| UF | 위3경로 각각 | 이름 점유/누락·정의 변조·권한 부족/중단을 합성 주입 | 변경 전 차단/트랜잭션 롤백,기존 행·이름·버전 유지,과거 성공 fallback 금지 |
| UR | 통합 폐기DB | 연결revision의 이름 정규화 역/순 함수만 직접 실행 | 행·보안 이력·head 보존. 부모 보안 이력을 삭제하는 전체 downgrade는 거부 |

UG/UM 비교는 기존 컬럼만을 고정한 지문과 새 컬럼의 예상 기본값을 따로 대조한다. 새 표/컬럼 때문에 전체JSON 지문이 달라진 것을 원본 행 손실로 오인하지 않는다. user/platform ADMIN과 GW SECURITY_ADMIN/AUDITOR를 혼용하지 않고, migration에서 계정·연결·MFA·역할을 자동 생성/초기화하지 않는다. 업무/인증/증거 원문을 로그에 출력하지 않는다.

코드/DB 버전이 바뀌면 옛 증거는 데이터로 보존하되 현재 인수 근거로 재분류하지 않는다. 옛 정책/버전·최신 FAIL/PARTIAL·원본 유실/변조·키 회수·신뢰 보류는 재검증 후 차단을 유지한다. 새 실행도 실제 복원 PARTIAL·최종4UNVERIFIED/ready=false/ACCEPTANCE PASS거부를 유지한다. 외부 공급자나 독립 최신성/전체 권한 회수를 이 승격으로 확인하지 않는다.

## 5. 전체 회귀·CI와 되돌림

77차1600pass/1skip은 분할 결과다. 실제 통합 후에는 현재 source의 단일 전체 실행·전체 backend/frontend·DB/R1~R6/실DDL·help/type/lint/build를 수행하고 결과를 새로 기록한다. 구형10인 폐쇄복원 검사의 이름 prefix guard는 임의 제거하지 않고 전체ID/owner/loopback을 확인하는 계약으로 정리한 뒤 실행한다. 과거46개 백업 fixture 통과로 이skip을 대신하지 않는다.

현재 ci_local.sh는 .env의 접속값을 읽고 DB 이름만 바꾸며, pytest는 -n auto, 마지막은 데이터 삭제 후 downgrade base를 한다. 이 스크립트를 이번 GW 소유 실행기의 URL에 자동 연결된 것으로 가정하지 않는다. 실제 통합 구현에서 소유 확인된 URL을 명시 주입하는 실행 경로/CI parity를 마련해야 한다(아직 미구현). .env를 임의 덮어쓰지 않는다. 복원검사의 전역 DB 목록 확인과 worker clone 정리는 별도로 검증하고, 검증되지 않은 병렬 실행으로 완전성을 주장하지 않는다.

이력이 있는 승격DB에서 downgrade base/부모 역적용은 하지 않는다. 빈 폐기DB의 왕복과 보안 이력 보유 시 거부를 분리한다. 운영 되돌림은 인증 호환 빌드/접속 제한과 전진 수정·검증된 격리 복원 절차로 설계하며, 보안 버전/회수/검증된 이력을 낮추지 않는다. 실제 운영 변경/되돌림·외부 연결·main push/배포는 이번 범위 밖이다.

## 6. 이번에 실제 실행한 것과 다음

`tools/plan_gw_main_integration.py`로 고정 Git 입력의 설계 후보/정규화 목록을 계산했다. 표/열/제약 참조·중복FK/RESTRICT·업무 교차FK 금지 구조 확인과 동일 입력 재실행의 결정성을 확인했다. 기준 제약 삭제·동시 표 수정·CASCADE·새 중복FK·새 물리 중복의 거부5건과 기존UK2개 보존을 실행 확인했다. 초기 구조 검사에서 기존UK 중복을 새 오류로 오인해 중단했고, 양쪽 기존 multiplicity 보존/신규 증가 거부로 보정했다. 처음 부정 검사1건은 기준 대신 GW 신규 제약을 빼서 기대 거부가 나지 않았으므로 기준 제약 삭제로 고쳐 다시 확인했다.

DB 연결/적용·실제 객체 rename·canonical 검증기·Excel/ERD 재생성·제품 코드·브라우저/단위/통합/전체CI는 이번 미실행이다. 따라서 위251표/92개 이름은 계산된 설계이며 실제 통합 DB 검증 결과가 아니다. 정식 metadata/적용migration·미리보기/계정·다른checkout/WMS/main/push/배포는 변경하지 않았다.

재현(이 GW 저장소 루트):

```sh
backend/.venv/bin/python tools/plan_gw_main_integration.py --gw-ref 4c898ac --main-ref 783a2c1 --output work/gw-readiness-02-phase78/reproduce-plan.json --draft-directory work/gw-readiness-02-phase78/reproduce-drafts
cmp outputs/gw-readiness-02-phase78/integration-plan.json work/gw-readiness-02-phase78/reproduce-plan.json
backend/.venv/bin/ruff check --config backend/pyproject.toml tools/plan_gw_main_integration.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check tools/plan_gw_main_integration.py
git diff --check
```

다음79차는 이 설계를 기준으로 GW 브랜치 안의 통합 구현과 U0/UG/UM 합성 승격 검증을 수행하는 단계다. 공유 main/다른 checkout·운영 DB·push/배포는 포함하지 않는다. 한 작업 ID 결과를 확인하기 전 자동 착수하지 않는다. DB/인증·업무 보존과 병합 정합 작업이므로 GPT-6 Astra + High를 추천한다.
