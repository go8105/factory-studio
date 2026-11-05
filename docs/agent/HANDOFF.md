## 79차 WIP2 — 전체 CI 진행·최종 단독 검증 대기 (2026-11-05)

- merge/WIP5d3df3f 이후 전체CI가 실행 중이며 약50%를 진행했다. 완료 결과가 아니다. 원문 로그는 work에만 둔다. 현재명세 상태 문구는 격리 시험 적용·운영 미적용으로 동기화했고 Excel/ERD를 다시 생성/확인했다.
- 최종 보강9건 pytest는 모두 통과했지만 동시 CI 생성DB를 새 자원으로 감지해 실행기 전체 종료1이다. 외부 자원을 삭제하거나 안전검사를 무시하지 않았다. CI 종료 후 단독9건 실행에서 자원 정리까지 다시 확인해야 한다. 이후 UM의 실제 pin 로그인 API 세션, 권한오류42501/두번째rename 중단 검사도 보강했으므로 이 최종 소스로 다시 실행한다.
- 새 연결revision은 인덱스 정렬/collation/opclass·NULL 옵션과 search_path 독립 FK 대조를 추가했다. 예약어alias 오류는 실제 U0에서 확인/수정했다. 기존공유migration은 고정main바이트와 동일하다. GW전용파일70개 비import AST 보존 확인. 신뢰/인수 PASS 조건은 완화하지 않았다.
- CI 접속가드 부정3경로를 추가해 도구전체139pass. CI 시작때의도구138건/백엔드8개 승격case 수집과 이후보강결과를 구분한다. 최종9건단독과전체CI결과확정·생성자원확인·최종인계/커밋이 남는다. 미리보기PID는읽기재확인API47906/Vite47907이며DB/계정변경없다.
- [상세보고](GW_통합적용_승격검증_GW-READY-02_79.md), [공개근거](../../outputs/gw-readiness-02-phase79/README.md). progress에서상대경로는docs/agent하위보고를참조한다. 공유main/다른checkout·push/배포없음,실회사인수미완료.

## 79차 WIP — GW 브랜치 통합 적용·승격 검증 중 (2026-11-05)

- GW 저장소/브랜치 안에서 고정 main783a2c1을 통합 중이다. 공유 main checkout·다른 WMS checkout·원격 push·배포는 변경하지 않는다. 시작 d6a02c7. 최종 완료 기록 전까지 이번 작업을 완료로 보지 않는다.
- 새 gw_main_ready02_merge(parents gw_readiness/fems1)는 92개 이름을 정의/점유 선검사 후 변경하며 OID를 보존한다. metadata 현재0.34.0/251표·2833열·617FK, 목표390표·4464열·950FK로 동기화. Excel51/83시트·native링크716/1113·셀오류0·GW렌더, ERD양쪽 재생성 확인.
- 실행한 U0는 migration/실DDL/스키마6pass. 고정 GW/main 코드에서 각각 합성 데이터를 만든 UG/UM·이름 역/순·실패롤백 집중7pass. 이후 권한부족/보존 검사를 보강해 전체 CI에서 다시 검증 중이다. 프런트 전체822pass, type/lint/format/build 확인. 초기 main 증인은 빈 CMMS/QMS 시드를 잘못 기대해 실패했고 합성 행을 명시 추가한 뒤 통과했다.
- 소유 실행기에 명시URL CI 경로/별도 빈DB 왕복을 연결하고, 구형10인복원은 기존 전체ID/owner/loopback 검증을 재사용한다. CI 초기 도구검사4failure/1error는 .env 의존 dry-run·옛 GW표개수/목표재생성 계약 때문. 보정 뒤 도구138pass, backend Ruff/포맷 확인. 전체CI는 아직 실행 중이며 통과로 기록하지 않는다.
- 전체 Ruff의 기존 I001 76건은 import 순서만 정리했다. 공개된 기존 migration은 새로 수정하지 않았다(main의 공유 WMS 파일을 그대로 수용). main 인계/진행 원문은 main_인계_783a2c1_통합참조.md와 ../main_진행이력_783a2c1_통합참조.md로 보존했다.
- ready=false/최종4UNVERIFIED·실제복원PARTIAL·ACCEPTANCE PASS거부 유지. 실회사10인/실 API브라우저·실외부공급자/전체회수·운영전환은 미검증이다. 남은 일: 전체CI/8개승격보강 결과 확인·자원정리·최종문서/커밋. 이 기록의 커밋은 WIP이며 실제 main 통합/배포 승인이 아니다.

## 78차 — 두 head 연결·metadata 충돌 해소·승격 검증 설계 (2026-11-05)

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작4c898ac/깨끗한 작업 트리. 최신77차 인계 후속을 사용자 승인으로 진행했다. main재조회783a2c1 동일, 공통2be292e·GW88/main90커밋 분기. 최종 커밋은 git log -1로 확인한다.
- 통합 설계를 작성했다: main metadata 순서+GW 추가분 보존, 신규예정revision gw_main_ready02_merge/parents(gw_readiness,fems1). 실제 migration 파일/병합은 아직 없다. 공통 표 동시변경0, 설계 후보 현재251표/2833열/617FK·목표390표/4464열/950FK. 현재1845레코드 중196SERVICE/DB_POLICY는 DB제약이 아니다.
- main 이름 변경0, GW 제약·인덱스73+FK19=92개 정규화 계획을 실제 metadata 순번으로 계산했다. 기존객체 정의/이름 점유·트랜잭션/실패·OID·지문 대조 후 이름만 변경하는 기준이며 실제DB 이름을 검증한 것은 아니다. 기존approval_step UK2개(c1335/c1546)는 양쪽 적용 이력으로 보존하고 신규 중복 증가만 거부한다.
- current헤더 제안0.34.0/GW-READY-02-INTEGRATION/새revision, target제안target-0.22.0/base_task재기준화/migration_revision=null. main의 오래된migration_revision=gw_wms_merge와 실제head=fems1 차이를 그대로 복사하지 않는다. 목표 미래139표·컬럼18묶음/BEMS nullable차이1곳은 실제승격에 섞지 않는다.
- 파일별metadata·Excel양쪽·ERD양쪽/검증기·API/App·도움말/검사·진행/인계 해소 기준과 U0빈DB/UG기존GW/UM기존main/UF실패/UR역순이름정규화 검증 행렬을 작성했다. 기존 세션 PASSWORD기본값을 MFA로 자동승격하지 않으며, 코드/DB버전 변경 뒤 옛 증거를 재분류/재서명하지 않는다. same-revision WMS차이는 main공유본 보존·기존적용재실행/다운그레이드 없음 기준으로 기록했다.
- 현재 ci_local은 .env강제읽기/-n auto/데이터삭제후downgrade base여서 소유검증실행기와 자동연결된 것이 아니다. 다음 구현에서 소유확인URL 명시주입/CI동등실행·복원병렬성/구형skip의 ID·라벨·loopback 계약을 마련해야 한다. 기존이력DB의전체downgrade는거부하며 폐기빈DB왕복과분리한다.
- 실행: tools/plan_gw_main_integration.py의 고정Git입력 계산·구조참조/RESTRICT·교차업무FK/중복FK점검, 동일입력결과파일cmp결정성, 기준제약삭제/동시표수정/CASCADE/신규중복FK·물리중복거부5건과 기존UK2개보존 확인. Ruff/포맷·문서링크/JSON·diff·현황200줄 제한 검사. 초기구조검사의기존UK중복오인·부정검사의잘못된삭제대상을보정한뒤확인했다. 77차1600pass/1skip은이번검증으로합산하지않는다.
- 새 도구는읽기Git/설계계산이며제품수집기/복원기아니다. 후보JSON은work의review_only/migration_revision=null 초안이고정식metadata아니다. 공개출력은 outputs/gw-readiness-02-phase78/의계획/거부검사, 상세 docs/agent/GW_통합설계_승격검증_GW-READY-02_78.md. DB접속·실DDL/rename·canonical검증기·Excel/ERD재생성·브라우저/제품단위·통합/전체CI는이번미실행이다.
- 제품/적용migration·정식schema/Excel/ERD·실계정/권한/MFA/비밀번호·미리보기DB/브라우저설정·다른checkout/병행WMS/main·push/배포변경없음. ready=false/최종4UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부유지. 78차는설계완료한정이며승격/실회사10인인수완료가아니다.
- 다음79차: GW브랜치안의통합구현·신규이름정규화revision/정식metadata·Excel·ERD동기화와U0/UG/UM합성승격검증. 공유main/다른checkout·운영DB/push/배포제외. 외부공급자·독립최신성/전체회수·구형skip/통합후전체회귀·실10인/최종전환은남는다. GPT-6 Astra + High추천, 모델자동변경/다음ID자동착수없음.

재현(이 GW 저장소 루트, DB 접속 없음):
```sh
backend/.venv/bin/python tools/plan_gw_main_integration.py --gw-ref 4c898ac --main-ref 783a2c1 --output work/gw-readiness-02-phase78/reproduce-plan.json --draft-directory work/gw-readiness-02-phase78/reproduce-drafts
cmp outputs/gw-readiness-02-phase78/integration-plan.json work/gw-readiness-02-phase78/reproduce-plan.json
backend/.venv/bin/ruff check --config backend/pyproject.toml tools/plan_gw_main_integration.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check tools/plan_gw_main_integration.py
git diff --check
```

## 77차 — GW 분할 회귀·보호 검사 보정·main 통합 전 차이 확인 (2026-11-03)

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작fceb68f/깨끗한 작업 트리. 사용자 다음 진행 승인 범위. WIP3591a64/1a90d02로 실행 중 상태를 보존했고 최종 커밋은 git log -1로 확인한다. 이번 제품 소스/적용 migration 변경 없음.
- GW80파일1601개 고유 case를 대조한 분할 결과는 **1600pass/1skip, 누락0**. DB fixture299pass/1skip, DB fixture 없는1301pass. 소유 백업 fixture46pass는 DB 범주 안의 중복이다. **보정 후 단일 전체 실행 통과가 아니다.** 전체 CI/전체 backend/frontend·main 통합 소스의 회귀와 구분한다.
- 초기 전체 선택949pass/1fail/1skip 중단: Flow 왕복 검사가 GW 보안 이력까지 전체 체인을 내려가려 해 정상 보호로 거부됨. 적용 migration/보호를 바꾸지 않고 전체 체인 거부·보안 이력 지문 보존을 검사하고 Flow 함수만 폐기 DB에서 직접 왕복하도록 보정, 집중1pass. 재실행1494pass/1fail/1skip 중단: GW/WMS 정규화 검사의 고정 옛 head 기대값. 현재 ScriptDirectory head와 정규화 왕복 전후 head 유지로 보정했다.
- 제품 소스가 시작fceb68f 이후 바뀌지 않았음을 확인하고, 재실행의1494pass와 수정 모듈/실패·미실행·skip107건을 현재 수집 node ID로 대조했다. 후속107건은106pass/1skip. 실패한 두 case는 보정 뒤 각각 통과했고 미해결 실패0이나, 전체 순서/단일 프로세스 검증 완료로 승격하지 않는다. 초기/집중/반복의 pass를 합산하지 않는다.
- skip1은 구형10인 폐쇄복원의 PG_TEST_CONTAINER/컨테이너 이름 계약 미설정. 이름/소유 보호를 임의 완화하지 않았다. 최신 소유 백업 fixture 통과나 과거 성공으로 이skip을 대신하지 않는다. 실회사10인 인수/실 API 브라우저·실 TOTP/전경로·전체 회수 확인이 아니다.
- `tools/gw_integration_check.py`는 전체ID/owner/running·단일127.0.0.1:55439/PG18 확인 후 새UUID *_test DB를 생성해 migration→실DDL→GW pytest를 수행한다. 새 실행기/검사파일2개 Ruff·포맷 통과. 잘못된 owner는 DB 연결 전에 종료1로 거부했다. 원문 로그/JUnit/접속값은 work에만 보존하며 출력/Git 제외한다. 수집/사전점검/복원기·신규 공급자를 중복 구현한 것이 아니다.
- 생성 원본DB4개 모두 삭제, 각 실행의 예상 밖 새 DB0, 종료 후 전체ID/라벨/loopback·4DB 부재/preview DB 존재 재확인. preview 업무 행을 조회/변경하지 않았다. 실제 계정·비밀번호/MFA·권한·업무자료/증거등록·브라우저 설정·다른 checkout/WMS/main·push/배포 변경 없음.
- 신규 DB 실DDL219표/2409열/543FK와정적DB/R1~R6 오류0. 시스템Python3.9의 감사 AST 구문 오류는 프로젝트Python3.14.7 재실행으로 통과했고 명령을 명시했다. 작성 중 실행기 Ruff3건은 수정 후 통과했다. 프런트 GW/계정보안/도움말/API153건/14파일(15.47초), 전체 frontend build/typecheck 통과. 기존 청크/의존성 외부화 경고 유지. 스키마/metadata/Excel/ERD 변경 없어 db:build/ERD 재생성 없음.
- origin/main783a2c1 재조회 동일. 시작 기준 GW85/main90커밋 분기, 양쪽 변경15경로. 시작 시 읽기3-way 모의는 텍스트8파일14구간/Excel1충돌.77차 검사 보정 후 복사본 재대조는 양쪽16경로, 텍스트9파일15구간/Excel1충돌이다. 새 충돌은 GW/WMS 검사 파일이다. 합친 migration은 gw_readiness/fems1 두head이며 동일w2b1_wms 바이트 차이는 main downgrade 정리SQL1줄이다(이번 미실행/미수정). 한쪽 metadata/Excel을 선택해 덮으면 GW인증/운영9표 또는 main32표가 누락된다.
- 상세·재현·남은검증: docs/agent/GW_통합회귀_main차이_GW-READY-02_77.md, unsigned 집계/실패·분할/자원 근거 outputs/gw-readiness-02-phase77/. ready=false/최종4UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부 유지. 현재 단계는 회귀/통합 경계 확인 한정 완료이며 전체UI/최종인수 완료가 아니다.
- 다음: 두head 연결의 새revision·metadata/Excel/ERD 충돌 해소안, 빈DB/기존GW head/기존main head 합성승격 보존 검증 계획을 확정한다. 실제 통합·병행WMS 수정·main/push/배포는 별도 범위다. 구형 폐쇄복원skip의 소유자검증 계약도 별도 정리한다. 외부공급자/독립최신성·전체회수/통합후전체회귀·실회사10인·최종전환은 남는다. GPT-6 Astra + High 추천, 모델 자동변경/다음ID 자동착수 없음.

재현(이 GW 저장소 루트; 전체 명령의 보정 후 단일 실행은 아직 남음):
```sh
backend/.venv/bin/python tools/gw_integration_check.py --container fs-gw-ready02-preview --expected-id-file work/gw-readiness-02-preview/container-id --owner gw-ready-02-preview --port 55439 --private-output work/gw-readiness-02-phase77/reproduce
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx src/shared/api.test.ts src/portal/account-security.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run build
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm run db:validate
backend/.venv/bin/python tools/audit_schema_isolation.py
backend/.venv/bin/ruff check --config backend/pyproject.toml tools/gw_integration_check.py backend/tests/test_gw_projects.py backend/tests/test_gw_wms_merge.py
backend/.venv/bin/ruff format --config backend/pyproject.toml --check tools/gw_integration_check.py backend/tests/test_gw_projects.py backend/tests/test_gw_wms_merge.py
git diff --check
```
예상ID 파일이 없으면 상세 문서의 전체ID·소유자/loopback 기록과 실제 자원을 먼저 대조한 뒤 소유자 전용 work 파일로 전달한다. 새로 inspect한 값을 확인 없이 예상ID로 자동 채우지 않는다. 실제미리보기 DB를 시험 대상으로 지정하지 않는다.

## 76차 — 본인 동의 합성 브라우저·모바일/키보드 검증과 체크 배치 보정 (2026-11-03)

- 시작: `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, `dd1cd69`/깨끗한 작업 트리. 최신75차 인계의 다음 범위를 사용자 승인으로 진행했다. 최종 커밋은 `git log -1 --oneline`으로 확인한다. factory-impeccable의 오류 복구·회사 맥락/가독성 기준을 적용했다.
- `frontend/e2e/gw-consent-synthetic-browser.mjs`는 전용5365 Vite/새 headless Chrome 컨텍스트를 생성하고, 모든 API를 허용 목록의 합성 응답으로 가로챈다. 예상 밖 API와 외부 요청은 차단/실패시킨다. 서비스워커는 새 컨텍스트에서만 차단하며 실제 사용자 브라우저 설정/프로필을 변경하지 않는다. API 프록시는 비업무 포트9를 가리켜 기존 실제API/미리보기DB에 연결하지 않는다. 기존 리스너가 있으면 재사용/종료하지 않는다. 생성한 Vite·격리 Chrome만 정리한다.
- 실제 제품 SessionProvider/App/GwLayout/CompanyStart/AccountSecurity·CSS로 1440×1000/390×844의 두 시나리오를 실행했다.409 체크 무효화/재조회·네트워크 미확인·GET실패 후 재시도·새 요청 동의 차단·원래 본문/멱등 키 유지·회사 선택/처리 중 입력 차단·별도 탭의 합성 추가 인증/원래 화면 복귀·새 요청 PENDING 유지·취소 뒤 동의 숨김을 확인했다. 과거 명령 성공 재생이 더 최신 요청을 ACTIVE로 바꾸지 않도록 합성 응답도 상태 변경과 분리했다. 초기 Tab/Shift+Tab 순서와 Space/Enter 활성화·나머지 명시 키보드 조작을 검사했다.
- 캡처에서 체크박스가 공통 입력 스타일로 중앙에 떨어져 보이는 문제를 발견해 CompanyStart에만20px 체크박스/텍스트 행·16px 간격·동작 버튼 배치를 적용했다. 추가 인증 링크에는 밑줄을 적용했다. 다른 화면/공통 입력 CSS는 변경하지 않았다. 최종 캡처를 직접 열어 데스크톱·모바일 가독성을 확인했다. 실제 마우스/터치·실기기/보조공학 전체 접근성 검증은 아니다.
- 검증: 위 두 브라우저 시나리오 최종 통과, 가로 넘침/페이지 오류/예상 밖 요청0. 캡처10장과 unsigned UI검토 report를 `outputs/gw-readiness-02-phase76/`에 보존했다. GW/도움말·공통 API150건/13파일 통과(16.95초), 도움말 갱신 후 집중19건 통과(2.39초, 기존 회귀와 중복). 타입·수정 TSX/MJS ESLint·수정3파일 Prettier·diff 검사 통과. 처음 스크립트 ESLint에서 clearTimeout 전역 선언 누락2건을 발견해 보정한 뒤 통과했다. 브라우저 기능 시나리오 실패는 없었다. 반복 통과를 중복 합산하지 않는다.
- 별도 탭은 실제 Chrome에서 제품 계정 보안 화면/추가 확인 POST와 복귀까지 실행했으나 API응답은 모두 합성이다. 실제 TOTP/로그인·쿠키/서버 세션 갱신·서버 멱등 거래/권한 회수 검증이 아니다. 보고서의 ready=false 등은 검토 범위 선언이며 현재 실제 서버의12조건을 실행/대조한 결과가 아니다. 실제 미리보기 계정/연결/권한/비밀번호/MFA·DB·업무자료/증거등록·브라우저 설정을 변경하지 않았다. 전체 UI완성/실회사10인 인수로 세지 않는다.
- ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL/ACCEPTANCE PASS 거부 유지. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. DB/백엔드/복원·전체 CI/전체 회귀/전체 build·실 API/실 인증·실회사10인은 이번 미실행이다. 다른 checkout/WMS/main/push/배포 변경 없음. 최종5365 리스너 없음 확인, 생성 Chrome 정리, work/.env/실제 비밀 Git 제외.
- 다음: GW 관련 백엔드/프런트 통합 회귀와 최신main 대비 차이의 읽기 검토로 통합 전 남은 검증 범위를 확정한다. DB검사는 기존 소유컨테이너 ID/라벨/loopback 재확인 후 새UUID *_test DB만 사용하고 생성 자원만 정리한다. 병합/push/배포는 하지 않는다. 외부 공급자·독립 최신성/전경로·전체 회수·최신main 통합/전체 회귀·실회사10인/최종 전환은 남는다. GPT-6 Astra + High 추천, 모델 자동 변경/다음 ID 자동 착수 없음.

재현(이 GW 저장소 루트,5365 비어 있어야 함):
```sh
/opt/homebrew/opt/node@24/bin/node frontend/e2e/gw-consent-synthetic-browser.mjs
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx src/shared/api.test.ts --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/Company.tsx frontend/e2e/gw-consent-synthetic-browser.mjs
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/Company.tsx frontend/src/gw/gw.css frontend/e2e/gw-consent-synthetic-browser.mjs
git diff --check
```

## 75차 — 본인 동의 충돌·추가 인증·불명확 응답의 명시 재확인 (2026-11-03)

- 시작: `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, `25b5392`/깨끗한 작업 트리. 최신74차 인계 후속을 사용자 승인으로 수행했다. 최종 커밋은 `git log -1 --oneline`으로 확인한다. factory-impeccable의 오류 복구·회사 맥락 기준을 적용했다.
- CompanyStart는 미확인 본인 동의의 bindingId/expectedVersion을 현재 화면 메모리에 보존한다. 네트워크·서버5xx·성공 응답 형식 오류는 **같은 동의 요청 결과 확인**으로 기존 useSend/MutationKeys의 동일 URL·본문·멱등 키를 명시 재사용한다. 새 수집기/영속 큐·새 키 발급 도구를 만들지 않았다. 응답 불명확 상태의 GET 재조회는 체크를 해제하고 최신 요청을 보여주지만 이전 결과 확인을 대신하거나 새 요청 동의를 허용하지 않는다. 조회 실패도 이전 요청 오류와 별도로 표시하며 원래 명시 재확인은 유지한다.
- 409는 현재 체크/동의를 무효화하고 본인 요청 GET 재조회/재동의를 요구한다. STEP_UP_REQUIRED는 입력·회사 맥락을 유지하고 내 계정 보안의 추가 확인을 안내한다. 일반403/404는 기존 권한 무효화/원문 제거,401/410은 기존 session.fail을 유지한다. 미확인 요청 재시도 중 STEP_UP_REQUIRED는 결과 확정이 아니므로 기존 useSend에서 원래 키/미확인 상태를 유지하고 새 요청을 차단한다. 미확인 재시도의 추가 인증은 이 화면을 유지하고 다른 탭에서 기존 내 계정 보안을 여는 링크를 제공한다. 링크 대상/새 탭 속성은 합성 검사이며 실제 탭 간 재인증 완료는 미검증이다. 처음부터 추가 인증이 필요했던 요청은 기존 입력 유지 동작이다. 추가 인증 자체를 이번 모의시험으로 완료했다고 세지 않는다. 실제 서버는 재시도에도 현재 권한을 확인하며 취소/정지 후 성공 재생을 보장하지 않는다.
- 동의 처리 중 체크·중복 제출·요청 재조회·회사 링크를 차단한다. SpaceChoice의 기존 onClick 차단이 Link의 이동보다 늦어 불명확 응답 뒤 변경 버리기로 회사를 바꿀 수 있던 결함을 onClickCapture로 수정했다. 최초 집중40건 중1건 실패로 발견했으며 보정40건과 추가 경계 포함 최종46건을 검사했다. 전체 로그/비밀을 Git에 넣지 않는다.
- 보존 범위는 현재 마운트된 화면 메모리다. 강제 주소 이동·회사/권한 epoch 변경·새로고침/탭 종료 후 멱등 키 복구를 구현한 것이 아니며 서버 거래 취소/전체 권한 회수·성공을 뜻하지 않는다. 읽기로 확인된 현재 상태와 과거 명령 결과를 구분한다. 실제 계정/연결·권한/비밀번호/MFA·브라우저 설정·미리보기DB/스키마 변경 없음. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. 다른 checkout/WMS/main/push/배포 변경 없음.
- 검증: 실제 GwLayout/CompanyStart/공통 HTTP 훅과 모의 세션·HTTP/셸 합성 신규14건 포함 집중46건 통과(3.38초), GW화면/정적도움말145건과 공통API5건 총13파일150건 통과(최종17.02초). 같은 본문/멱등 키·명시 재시도,409 뒤 새 요청/새 키,STEP_UP 입력 유지,500/네트워크/잘린 응답,불명확 재시도 반복/권한 거부,조회 실패,처리 중 중복/회사 링크를 검사한다. 타입·수정4파일ESLint/Prettier·diff 검사 통과. 반복 검사는 중복 합산하지 않는다. 실 API/실 브라우저/기기·실제 추가 인증/서버 멱등 거래·백엔드/DB/복원·전체 CI/전체 회귀/전체 build·실회사10인 인수는 이번 미실행이다.
- ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL/ACCEPTANCE PASS 거부 유지. 전체 UI 완성이나 실회사 인수 근거로 승격하지 않는다.
- 다음: 별도 합성 API의 브라우저에서 본인 동의 충돌·응답 불명확→재조회/같은 요청 확인·회사 선택 보호를1440/390·키보드로 대조한다. 실제 미리보기 계정/연결을 임의 변경하지 않는다. 외부 공급자·독립 최신성/전경로·전체 회수·최신main/전체 회귀·실회사10인/최종 전환은 남는다. GPT-6 Astra + High 추천, 자동 모델 변경/다음 ID 자동 착수 없음.

재현(이 GW 저장소 루트):
```sh
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/authorization-recovery.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx src/shared/api.test.ts --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/Company.tsx frontend/src/gw/GwLayout.tsx frontend/src/gw/common.tsx frontend/src/gw/authorization-recovery.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/Company.tsx frontend/src/gw/GwLayout.tsx frontend/src/gw/common.tsx frontend/src/gw/authorization-recovery.test.tsx
git diff --check
```

## 74차 — PENDING 본인 연결 동의의 재조회·취소·회사 전환 (2026-11-03)

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 커밋 `5c52729`, 시작 작업 트리 깨끗함. 최종 커밋은 `git log -1 --oneline`으로 확인한다. 요청의58차는 실제9308a92에 완료돼 최신73차 인계 후속을 사용자 승인받아 진행했다. factory-impeccable의 오류 복구·회사 맥락 기준 적용.

본인 연결 동의는 현재 회사 연결 상태와 별도 요청 상태가 모두 PENDING일 때만 표시한다. 회사 연결 상태가 바뀌면 CompanyStart를 새로 구성하고, 본인 확인 체크는 조회한 요청 ID·버전에만 대응한다. **본인 연결 요청 다시 확인**은 회사 연결과 요청을 GET으로 다시 읽고 체크를 해제한다. 동의 성공 후에도 체크를 비우고 현재 상태를 재조회한다. 새 계정·연결 생성이나 요청 취소 API를 실행하지 않는다.

취소/정지 관측 뒤 옛 PENDING 응답이 도착해도 동의 화면을 복구하지 않는다. 기존 회사 경계와 useGet의 abort/useSend의 mounted 검사를 재사용한다. 다른 회사로 이동할 때 체크한 입력은 기존 변경 버리기/계속 편집 보호를 따른다. 변경 버리기는 로컬 입력 정리이며 서버 연결 요청 취소가 아니다. 처리 중 링크 차단은 유지한다. 주소 변경 등으로 회사가 전환되면 옛 동의 응답으로 이전 회사 재조회를 실행하지 않는다. 서버에서 이미 처리된 거래의 취소/롤백이나 즉시 전체 회수를 뜻하지 않는다.

검증: 실제 GwLayout/CompanyStart와 모의 HTTP·세션/셸의 합성 통합시험 신규9건 포함 총32건, GW 화면/도움말12파일131건 통과(도움말 갱신 후 최종 실행14.45초, 반복 중복 합산 없음). 요청 ID/버전 변경 뒤 재동의·정확한 POST 대상, 같은 권한 버전 취소/정지, 지연 요청/동의 응답, 조회 오류 후 재시도, 회사 링크의 입력 보호를 검사했다. 최초 추가 시험1건은 회사 선택 링크의 dashboard 경로를 시험 라우터에 누락해 실패했고 경로 추가 후 최종131건 통과했다. 타입·수정3파일 ESLint/Prettier·diff 검사 통과. 실 API/브라우저·실기기·DB/백엔드/복원·전체 CI/전체 회귀/전체 build·실회사10인 인수는 이번 미실행이다.

ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL/ACCEPTANCE PASS 거부 유지. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. 미리보기 계정/연결/권한·비밀번호/MFA·DB 초기화·다른 checkout/WMS/main/push/배포 변경 없음. 전체 UI 완성으로 세지 않는다.

다음: 본인 동의 POST의 충돌·추가 인증·네트워크 응답 불명확 상태에서 기존 멱등 요청/재조회/회사 전환 보호를 합성 검증한다. 실제 계정 연결은 임의 변경하지 않는다. 외부 공급자·독립 최신성/전경로·전체 회수·최신 main/전체 회귀·실회사10인/최종 전환은 남는다. GPT-6 Astra + High 추천, 모델 자동 변경/다음 ID 자동 착수 없음.

재현(이 GW 저장소 루트):
```sh
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/authorization-recovery.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/Company.tsx frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/Company.tsx frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
git diff --check
```

## 2026-11-01 GW-READY-02 73차 — 회사 연결 실패·정지/취소 후 원문 제거·재조회

- 저장소 /Users/hwang-kyoungho/projects/factory-studio-gw-company, codex/gw-company-01, 시작4c38841/깨끗한 작업트리 확인. AGENTS·현황/FS-013/문서지도/progress/HANDOFF와72차구현·CompanyStart·backend me응답을대조했다. 최종커밋은 git log -1로 확인한다.
- 결함: /me실패·연결정지/취소가원문을숨겨도URL open은남았고 같은권한버전으로복구되면옛원문을자동재선택할수있었다. CompanySpace의unavailable조건(/meerror 또는직원/연결비활성·초기설정필요·업무미준비)에서 기존clearSelection을호출한다. 오류재시도로CompanyRoot를계속새로만들지않아 무한재조회가없으며 실패중과거선택주소재방문도query변경을감지해선택을비운다. 회사/경로/목록필터는유지한다.
- 연결오류에원문/입력숨김·재조회/자동재선택없음안내를추가했다. SUSPENDED/CANCELLED/UNBOUND·직원비활성은기존CompanyStart의정지/조직관리자문의안내를유지하며 회사연결다시확인(GET)을제공한다. 이버튼은연결재개/새계정·권한부여가아니다. 업무미준비에도재조회할수있다. 초기설정/본인동의의기존변경요청동작은유지한다.
- 미완료쓰기와함께연결실패가나면숨겨진컴포넌트의busy/uncertain표시가새업무까지막을수있어 unavailable에서참여자검색과함께초기화했다. 옛쓰기응답은기존mounted검사로무시한다. 이는실제서버거래취소/롤백이아니므로복구후현재기록을확인하라는안내를추가했다. 미완료요청을자동재전송하지않는다.
- authorization-recovery.test.tsx에신규15건/총23건: /me403/404/500/네트워크오류, 같은버전SUSPENDED/CANCELLED/UNBOUND·직원비활성/업무미준비각5, 지연승인결과무시·응답전연결복구후목록inert해제, 최초403업무요청없음, 지연상세abort/비표시,401/410기존session.fail호출, 실패중과거선택주소재방문을검사한다. 정상복구뒤허용목록에같은문서제목이보여도본문/처리입력과open은자동복구하지않는다. 재확인요청에새POST없음·회사/필터유지·정지/비활성/관리자문의문구를검사한다.
- 실제GwLayout/CompanyRoot·CompanyStart/Documents/공통훅을사용하지만HTTP/세션·SolutionLayout셸은모의다.401/410은mock fail호출과원문비표시만확인하며실앱로그아웃/재로그인은미검증이다. 기존주기/포커스재조회경로를사용하며실15초경과·모바일/실브라우저타이머·실제PG권한/계정회수검증이아니다. 실제미리보기/실계정연결·권한·MFA/업무자료/정책·증거등록을변경하지않았다.
- 초기신규9건은정상복구뒤목록을빈목록으로기대해실패했다. 서버가현재허용한목록의문서제목은보여도원문을자동열지않아야하므로목록행존재/본문비표시·선택없음으로수정했다. 수정22건/추가주소재방문과busy복구포함최종집중23건통과. 최초실패기록은work/gw-readiness-02-phase73에보존하고전체로그Git제외한다. 과거통과로실패를대신하지않는다.
- factory-impeccable의오류복구·회사맥락/유효성기준을적용했다. 정적도움말·실회사절차§47/수집경계·구현문서/문서지도·현황200줄이하/progress/HANDOFF갱신한다. 전체UI완성·실회사10인인수/전체권한회수/외부독립성완료로세지않는다.
- ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부유지. 스키마/마이그레이션·metadata/Excel/ERD변경없음. DB초기화/실계정/비밀번호/MFA/키·브라우저설정·다른checkout/WMS/main/push/배포변경없음.work/.env·비밀Git제외. 백엔드/별도PG·복원/전체CI·전체회귀/전체build/실API실브라우저·실회사10인/실기기는이번미실행이다.
- 다음: PENDING 본인연결동의의재조회·취소/다른회사전환과오래된응답처리를기존CompanyStart/회사경계와합성검증한다. 실제미리보기연결·권한을임의변경하지않는다. 외부공급자/독립최신성·전경로/전체회수·최신main/전체회귀·실회사10인/최종전환은남는다. GPT-6 Astra + High추천(본인동의·회사경계/지연응답정합), 모델자동변경없음/다음ID자동착수없음.

- 최종검증: GW화면/도움말12파일122건/17.09초, 집중연결복구23건/2.63초 통과(신규15·반복중복합산없음). 타입·수정2파일ESLint/Prettier·diff오류0. 초기신규9건의허용목록기대오류보정과지연쓰기응답전busy초기화까지최종소스로검사했다. 실제API/실브라우저·계정회수·DB복원/전체CI/실회사인수결과는아니다.

재현(이GW작업저장소루트):
```sh
git status --short
git branch --show-current
git log -1 --oneline
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/authorization-recovery.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
git diff --check
```

## 2026-11-01 GW-READY-02 72차 — 권한 변경 시 원문·선택 제거와 합성 재조회 복구

- 저장소 /Users/hwang-kyoungho/projects/factory-studio-gw-company, codex/gw-company-01, 시작8c8c4d7/깨끗한 작업트리 확인. AGENTS·현황/FS-013/문서지도/progress/HANDOFF와 기존CompanyRoot/invalidate·GET/POST를 대조했다. 최종커밋은 git log -1로 확인한다.
- 결함: 업무403/404에서 원문을 숨기고컴포넌트를새로만들어도 URL open은남아 재확인시같은문서를다시열었다. CompanyRoot의기존invalidate에 현재URL open제거/replace를추가했고 회사·경로/필터·hash·location.state는유지한다. 실제원문/기록삭제나 권한재부여가아니다.
- 기존 /me의authzVersion 변경을관측하면 새업무원문을먼저보이지않고 Loading→open제거/epoch갱신→새회사연결조회를한다. 기존15초/포커스조회는유지하고 같은버전은선택/입력을유지한다. epoch를통해 기존요청abort/오래된쓰기응답무시를재사용하며 별도수집기/폴링/권한회수도구를만들지않았다. 버전변경은권한추가등도포함할수있어 회수확정으로표현하지않는다. 서버응답전의즉시감지·전기기전체회수를보장하지않는다.
- 새 authorization-recovery.test.tsx8건은 실제GwLayout/CompanyRoot·Documents/공통훅을사용하고 세션/HTTP·SolutionLayout셸은모의다. GET403/404각각 원문숨김/URL선택제거/회사·필터유지/재확인후옛문서자동재선택없음을검사한다. POST403/404각각실제승인패널의합성처리사유/확정입력제거·다른메뉴회사유지를검사한다. 버전변경때 지연상세요청abort/옛원문비표시, 지연승인성공이selection을되살리지않음, STEP_UP_REQUIRED는권한거부와달리 원문/합성입력을유지함을검사한다. 기존15000ms콜백을합성호출한같은버전재조회는선택유지/새GET을검사하며 실제15초경과·실브라우저타이머시험은아니다.
- 기존사용중화면이 /me403/404/연결정지로전환될때의모든상태는이번8건범위가아니다. 실제PG권한정책/실제계정회수/인증기기·브라우저/모바일·감사자/일반직원실사용/복원은미실행이다. 미리보기DB/계정·권한·MFA설정/실제업무자료·정책·증거등록·브라우저설정변경없음. 이번HTTP는모의응답이며 API실로그인성공으로보고하지않는다.
- 초기통합시험4건은권한오류화면직후URL전환이완료되기전동기assert로실패했다. 원문이이미숨겨진뒤ReactRouter의URL반영완료를waitFor로검사하게보정했고7건통과, 정상주기/입력유지시험을더해최종8건으로확인했다. 임시로그는무시되는work/gw-readiness-02-phase72에두며전체로그Git제외. 검증결과는아래최종기록을따른다.
- factory-impeccable의기존회사맥락·오류상태/입력유효성기준을적용하고 정적도움말·실회사절차§46/수집경계·구현문서·현황200줄이하/문서지도/progress/HANDOFF갱신한다. 화면모의검증을제품전체UI완성으로세지않는다.
- ready=false/최종4 UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부유지. 백엔드·DB복원/전체CI/전체회귀·전체build/실API실브라우저·실회사10인인수는이번미실행이다. 스키마/마이그레이션·metadata/Excel/ERD변경없어DB생성·마이그레이션/정적DB재실행없음. 다른checkout/WMS/main/push/배포변경없음.work/.env/비밀Git제외.
- 다음: /me조회실패·회사연결정지/취소때원문제거/재연결안내와URL선택/입력복구를합성통합시험으로대조한다. 기존미리보기의실제연결·권한을임의회수하지않는다. 외부공급자/독립최신성·전경로/전체회수·최신main/전체회귀·실회사10인/최종전환은남는다. GPT-6 Astra + High추천(회사연결·오래된응답/오류복구정합), 모델자동변경없음/다음ID자동착수없음.

- 최종검증: GW화면/도움말12파일107건/11.66초 통과(신규통합8건, 집중8/1.50초와반복은중복합산없음). 타입·수정2파일ESLint/Prettier·diff오류0. 합성사유입력제거/STEP_UP입력유지까지최종확인했다. 실제API/브라우저·DB/계정회수·전체CI/실회사인수결과는아니다.

재현(이GW작업저장소루트):
```sh
git status --short
git branch --show-current
git log -1 --oneline
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/authorization-recovery.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/GwLayout.tsx frontend/src/gw/authorization-recovery.test.tsx
git diff --check
```

## 2026-11-01 GW-READY-02 71차 — GW 회사 복귀·검색/페이지 범위 보정

- 저장소 /Users/hwang-kyoungho/projects/factory-studio-gw-company, codex/gw-company-01, 시작992fc99/깨끗한 작업트리를 확인했다. AGENTS/현황/FS-013/문서지도/progress/HANDOFF와70차구현을 대조했다. 최종 커밋은 git log -1로 확인한다.
- 결재선 템플릿/게시판의 빈 DataTable은 공통 기본 앱런처 대신 기존 companyPath로 현재회사 GW업무현황 복귀를 제공한다. 누락 GW경로는 전용 MissingGwPage의 명확한 h1/회사복귀로 연결한다. 개인 체험은 개인 GW복귀이며 다른 솔루션의 공통EmptyState/NotFound는 변경하지 않았다.
- Masters 검색/페이지 이동이 setQuery의 새객체로 companyId를 버리는 결함을 보정했다. 기존URLSearchParams를 복사하고 검색만 변경/offset초기화, 페이지이동시 검색·회사/기타선택을 보존한다. 기존 ROUTE_ADMIN/등록·편집 검사는 그대로다. 새권한·계정/자동등록·공급자/수집기·복원기·인수PASS를 만들지 않았다.
- 정적 링크 대조: 문서함은70차회사경로, 역할체험NoRole은개인경로/내공간설정, 회사구성은 CompanySpace가 별도차단한다. 위임빈상태는같은화면등록, Authority 공통마스터는동일화면패널/모듈꺼짐시내공간안내, 조직·문서·공지·알림은기존GwLink, 운영준비오류는기존현재회사GwLink/GET재점검이다. 개인체험/다른회사선택·계정보안/도움말/HR·런처명시이동은 의도한 범위전환으로 유지한다. 모든동적경로/모든역할인수를완료했다는목록은아니다.
- 새 navigation.test.tsx 6건: 회사/개인 각각 결재선·게시판·누락화면 복귀, 검색시offset만초기화/다음페이지 검색·companyId·기타query 유지/API회사범위와GET만실행, 읽기역할 등록비활성, 개인담당자 안내를 확인한다. 회사모의값11/개인두범위의 URL/API를같이검사하며 실제PG권한시험으로 세지않는다.
- 실제자원: 기존 API47906/웹47907/listener8362/5362와 preview컨테이너의 저장fullID/owner=gw-ready-02-preview/running·단일127.0.0.1:55439를재검증했다. 읽기전용계정점검은 저장합성계정존재/비밀번호일치·admin없음이다. 기존MFA로 실제제품로그인후 회사3 결재선검색에 companyId유지·빈상태클릭복귀,390게시판빈상태/누락주소 Enter복귀와 회사명·연결직원유지를 확인했다. 기존데이터가0건이라 실제다중페이지는미검증/모의회귀로구분한다. 사이드바닫기/임시viewport원복, 비밀/OTP·키/전체로그출력없음.
- factory-impeccable 기준으로빈상태설명·회사맥락·제목/키보드·모바일을확인했고 화면근거 outputs/gw-readiness-02-phase71/를남겼다. 계정/역할/MFA설정·업무자료/정책·실행증거등록은요청하지않았다. 일반로그인인증/세션기록은발생하므로전체DB불변을주장하지않는다. 미리보기초기화·새DB/자원생성/스키마변경없음.
- 검증: 최종 GW전체화면/정적도움말11파일99건과타입/수정5파일ESLint·Prettier/diff검사를실행한다(최종수치는아래결과). 집중6/전체99·반복은합산하지않는다. 최초타입검사에서신규시험의TestingLibrary옵션exact지원외2건을발견해제거하고통과했다. 후속포맷경고1건은write로보정했다. 기능시험실패없음. 스키마/마이그레이션·metadata/Excel/ERD변경없어DB재생성/정적DB·백엔드/복원·전체build/전체CI/전체회귀는이번미실행이다.
- ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부유지. 보안관리자합성1명/예정10명이며 실제10인/감사자·일반직원브라우저/실기기·외부독립성/전체회수·전체UI완성은미검증이다. 실계정/admin/비밀번호·키/브라우저설정·다른checkout/WMS/main/push/배포변경없음.work/.env·비밀Git제외.
- 다음: 별도합성시험에서 회사권한회수후 프런트의원문/선택제거·재조회/다른메뉴복구를 기존CompanyRoot/invalidate와대조한다. 현재미리보기의계정/역할을임의회수하지않고 기존모의/별도소유시험을사용한다. 감사자/일반직원의실브라우저는기존승인계정자료없으면통과시키지않는다. 외부공급자/독립최신성·전경로/전체회수·최신main/전체회귀·실회사10인/최종전환은남는다. GPT-6 Astra + High추천(권한회수/비동기오래된응답·회사범위정합), 모델자동변경없음/다음ID자동착수없음.

- 최종검증 완료: GW화면/도움말11파일99건/10.57초, 도움말 최종문구 반영후 해당파일19건/2.17초 재통과(99건과중복합산없음). 타입·수정5파일ESLint/Prettier·diff오류0. 실제합성API 검색/빈목록/누락화면·390/Enter복귀를확인했고 페이지이동은모의범위다.

재현(이GW저장소루트):
```sh
git status --short
git branch --show-current
git log -1 --oneline
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/Board.tsx frontend/src/gw/Masters.tsx frontend/src/gw/ui.tsx frontend/src/gw/index.tsx frontend/src/gw/navigation.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/Board.tsx frontend/src/gw/Masters.tsx frontend/src/gw/ui.tsx frontend/src/gw/index.tsx frontend/src/gw/navigation.test.tsx
git diff --check
# 실제API: 소유ID/owner/running/loopback·기존합성credential 대조후에만.
# localhost:5362 기존login/MFA→회사3→결재선검색→빈상태 회사업무복귀.
# 게시판/없는GW화면도 같은회사로복귀. 페이지이동은모의시험만.
```

## 2026-10-31 GW-READY-02 70차 — 실제 API 로그인·운영 준비 동선 및 회사 복귀 링크 보정

- GW 저장소 / codex/gw-company-01 / 시작 fad7181 / 깨끗한 작업트리에서 수행했다. 다른 checkout·WMS/main/push/배포는 건드리지 않았다. 최종 커밋은 git log -1로 확인한다.
- 중지된 기존 미리보기의 저장된 full container ID·owner=gw-ready-02-preview·단일127.0.0.1:55439 바인딩을 대조한 뒤 기존 컨테이너를 시작했다. 기존 server.env의 DB는 gw_preview_test이며 초기화/마이그레이션/계정 변경 없이 기존 API8362·웹5362를 재기동했다. 현재 PID는 API47906/웹47907이나 다음 세션에서 재확인한다.
- 읽기 전용 계정 점검에서 저장된 합성 계정 존재/비밀번호 일치, admin 부재를 확인했다. admin을 생성/이름 변경/초기화하지 않았다. 기존 등록된 합성 MFA로 실제 브라우저 비밀번호 로그인→본인 확인→home 진입을 확인했다. 비밀번호/OTP/설정키는 출력·화면 근거·Git에 넣지 않았다. 일반 로그인에 따른 세션·인증 기록 쓰기는 발생하며 전체 DB 불변을 주장하지 않는다.
- 실제 제품/API에서 런처→GW 개인 체험→사용 공간 선택→회사3→회사 운영 안내→운영 준비를 확인했다. 현재 회사/연결 직원·보안 관리자, 연결1/예정10·인증앱1, 서버 검증 설정 필요, 확인됨4/조치필요4/미확인4를 표시한다. GET 재점검·12조건 펼치기·서버 점검 도움말 해당절→브라우저 뒤로→현재회사 운영준비→GW 업무/내 결재함 복귀를 확인했다. 인증 뒤 운영 준비가 자동 표시된다고 안내하지 않는다.
- 실제 빈 결재함의 결재선 관리 링크가 /gw/routes로 회사 선택을 잃는 결함을 발견했다. DocumentsSpace의 EmptyState에 기존 CompanyContext/companyPath를 적용했다. 기안함/결재함/결재기록 공통 빈 상태가 회사에서는 회사ID를 유지하고 개인 체험에서는 기존 개인 경로를 쓴다. 권한을 부여하거나 API 검사를 우회하지 않는다. 수정 뒤 실제390 화면의 링크 Enter로 /gw/routes?companyId=3와 연결직원·회사모드를 확인했다.
- factory-impeccable 스킬의 기존 제품 맥락/빈상태·모바일 기준을 적용했다. 기본359 및1440/390 뷰포트에서 운영준비·조건·도움말/회사복귀를 확인하고 임시 viewport override는 reset했다. 화면 근거는 outputs/gw-readiness-02-phase70/에 있다. 화면 크기 변경 시 기존 펼친 사이드바가 모바일 오버레이로 남아 닫기 버튼으로 닫았다. 기존 설정을 임의 변경하지 않았다.
- 실제 API 로그의 비공개 전문 대신 상태 집계를 확인했다: 로그인 시작202/기존MFA확인201, 로그인 전 GET401 두건과 로그인 후 GET200. 업무·정책·증거 등록/계정·MFA설정 변경은 요청하지 않았다. 로그에 비밀이 없다는 보증이나 모든 요청·모든 데이터의 불변 검증은 아니다.
- 검증: 최종 도움말 반영 후 관련 화면/도움말6파일75건 통과6.11초(신규3건은 각 문서함의 회사/개인 두범위 대조), frontend typecheck·수정2파일 ESLint 통과. 최초 신규3시험은 같은 Response 본문을 두번 읽는 시험fixture 오류로 실패해 매번 새 Response를 반환하도록 보정했고 최종75 통과했다. 첫 prettier 명령은 prefix의 cwd 차이로 파일을 못 찾아 실제 경로로 다시 실행했다. 제품 API의 기능 실패로 처리하지 않는다. 최종 포맷/문서·diff 검사는 아래 재현을 따른다.
- ready=false·최종4 UNVERIFIED, 실제복원 PARTIAL/ACCEPTANCE PASS 거부는 유지하며 이 화면검사로 승격하지 않는다. 현재 미리보기에는 실행 증거0건/검증설정 필요여서 실제 signed PARTIAL 등록 상세나 복구 도구를 이번에 실행한 결과가 아니다. 과거 합성API/시제품 화면을 실API 근거로 대신하지 않았다.
- 스키마/마이그레이션/metadata/Excel/ERD 변경 없음. 백엔드 단위/별도PG 복원/전체CI·전체회귀/전체build/실회사10인·실기기/감사자·일반직원 브라우저 동선은 이번 미실행이다. UI 전체완성/전체권한회수/외부독립성을 의미하지 않는다.
- 다음: GW 회사모드의 나머지 빈상태·오류 복구 링크를 기존 회사경로 함수와 대조하고 회사 선택을 잃는 경로를 보정한다. 감사자/일반직원 실브라우저 검증은 기존 승인된 계정·자료가 있을 때만 수행하고 계정/역할/MFA를 임의 준비하지 않는다. 외부공급자·독립최신성/전경로·전체회수/최신main·전체회귀/실회사10인·최종전환은 계속 남는다. 다음 난이도 중상, GPT-6 Astra + High 추천(회사범위/역할·오류복귀 정합), 모델 자동변경 없음. 한 단계 종료 후 다음 ID 자동착수 없음.

재현(이 GW 저장소 루트):
```sh
git status --short
git branch --show-current
git log -1 --oneline
# docker inspect로 저장된 fullID/owner/running/단일loopback을 먼저 검증한다.
# 기존 비공개 접속자료는 출력하지 않고 기존 계정/회사/MFA와 일치하는지만 읽기전용 확인한다.
# localhost:5362 실제 제품 로그인→기존MFA→GW→사용공간선택→회사→운영준비.
# 전환조건12/미확인4·도움말 절·뒤로·회사 업무/결재함·빈상태 결재선관리의 companyId 유지 확인.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/company.test.tsx src/gw/gw.test.tsx src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/eslint/bin/eslint.js frontend/src/gw/Documents.tsx frontend/src/gw/company.test.tsx
/opt/homebrew/opt/node@24/bin/node frontend/node_modules/prettier/bin/prettier.cjs --check frontend/src/gw/Documents.tsx frontend/src/gw/company.test.tsx
git diff --check
```

## 2026-10-31 GW-READY-02 69차 — 공통 카탈로그와 선택 권한검토맵 정합 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작 `1791667`/깨끗한 작업트리를 확인했다. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 새 denial_catalog.py의 불변9가족/28조건을 실행기와 진단맵이 함께 참조하게 했다. 모델Literal에서 관측버전/범위를 얻고 실제 매개변수시험 nodeid를 제공한다. 실행기의 중복 선택정의를 제거했으며 기존고정카탈로그V9/관측v1–v9/시험·수집기·복원기/엄격한검증은 유지했다. 새카탈로그는 커밋전에도 source_identity 지문에 포함하고 변경감지 회귀를 추가했다.
- revocationCoverage내부v2/12검토영역으로 갱신했다. 기존8영역을 유지/갱신하고 게시/채팅/일정/위임을 추가했다. 회사멤버십/다른회사 참조는 현재고정2조건으로 연결한다. FOREIGN_SCOPE를회사영역에만배치하고문서영역은DOCUMENT_READER만 배치해 고정28조건을중복없이연결한다. 위임은관측v6~v9의15조건으로 원본/복원하한·정책/HTTP·fixture를 구분한다. 구세션/미완료인증의 기존함수[False]2영역은legacy참조로유지하고28건에 합산하지않는다.
- 기존대표testReference와 전체testReferences·syntheticCases(case/probe/실제nodeid/모델관측버전·범위)를 제공하며 remainingScope에 영역별 실제회사/기기·전경로·동시성 등 미검증을 남긴다. 검토12영역과 운영전환12조건은 별개/코드집합비중복이며 1:1대응/완료수가아니다. 참조는저장소구현위치이지 설치서버에시험파일이있거나 현재회사에서실행됐다는증명이아니다.
- 보고서생성은 프로세스/시험실행·추가DB읽기·과거파일/환경PASS수입을 하지않는다. 전역/모든영역/조건은NOT_EXECUTED·currentCompanyVerified=false·result=UNVERIFIED/coverageComplete/revocationsComplete/syntheticExecutionImported=false를유지한다. 반환값PASS변조가 후속보고나 불변실행카탈로그로전파되지않음을 확인했다. 알수없는 참조는legacy시험으로바꾸지않고 거부한다.
- 동일읽기전용스냅샷·최신원본재검증/최신FAIL·PARTIAL/원본유실·변조·회수·옛정책/버전차단·사전점검은유지했다. 실행보고상위version1/내부맵v2를 구분한다. ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지. 새소유DB에서 별도CLI28조건을 실제실행해도 그합성결과를 현재회사보고서에자동수입하지 않는다.
- 실제검증: 관련단위1315통과25.55초(신규13/기존사용중단경고2), 최종도움말반영후화면/도움말61통과6.51초. 소유PG읽기전용진단3건18.32초통과: 회사2명/개발admin계정없음·4조건미확인/최신실패·원본유실·서명PARTIAL 유지, 실제읽기거래의쓰기25006차단·계정/세션/MFA·운영설정/증거5표지문불변을 확인했다. 집중단위375/전체1315·반복은합산하지않는다. 수정Python6개Ruff check/format·정적DB219표2409열543FK/R1–R6오류0. import/포맷보정, 실행시험실패없음. 스키마/마이그레이션·metadata/Excel/ERD변경없음.
- 최종고정CLI: 공통카탈로그를사용한최종소스28조건 PASSED/관측28·pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0·528.00초·상한840초. 실행선택공유의실제회귀를확인하려고 full64컨테이너ID/owner=gw-ready-02-phase69-test/running·단일127.0.0.1/TCP준비를확인한 새postgres:18/새UUID *_test DB에서 수행했다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨만정리하고 owner잔여0확인. 기존미리보기/병행DB접속·초기화없음.
- 실회사절차§43/수집경계·정적도움말/문서지도/구현문서·현황199줄/progress/HANDOFF갱신. 참조/실행·현재회사구분의직관성, 실제카탈로그/관측/읽기불변의유효성, 두12목록·선택범위학습안내와 공통카탈로그재사용을반영했다. 전체UI완성은아니다. 제품프런트미변경으로 타입/ESLint/build·실브라우저/모바일재실행없음. 전체CI/전체회귀·기존V5전체경로합성모드/실회사·실기기10인/최종전환은미실행·미완료다.
- unsigned진단/합성PARTIAL·실제복원PARTIAL과최종4조건미확인/PASS거부를 유지한다. 실계정/admin/비밀번호/OTP/키/브라우저·미리보기/다른checkout/WMS/main/push/배포변경없음.work/.env·비밀/전체로그Git제외.
- 다음:별도합성미리보기에서 실제API로그인후회사선택→운영안내→운영준비→도움말/업무복귀 동선을 검증한다. 기존URL http://localhost:5362/gw/operations?companyId=3 은실행상태를재확인할과거기록이며 API8362/PG fs-gw-ready02-preview·owner=gw-ready-02-preview/loopback55439의현재ID·라벨·계정/접속자료/회사·역할을먼저확인한다. 개발admin계정은57차시점없었으므로 생성/이름변경/비밀번호초기화·DB/브라우저설정변경을임의로하지않는다. 비공개work/gw-readiness-02-preview 자료의비밀을출력/Git에넣지않고 계정불일치를합성API/옛시제품으로통과시키지않는다. 외부공급자/독립최신성·전경로/전체회수·최신main/전체회귀·실회사10인/최종전환은남는다. 난이도높음,GPT-6 Astra + High추천(실API/MFA·회사/역할맥락·브라우저상태와계정변경금지정합). 모델자동변경없음/사용자확인전다음단계자동착수없음.

재현(이 GW 저장소 루트; 비밀은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/denial_catalog.py backend/src/fs/gw/acceptance_report.py tools/gw_route_verify.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_acceptance_report_db.py
uv run --project backend ruff format --check backend/src/fs/gw/denial_catalog.py backend/src/fs/gw/acceptance_report.py tools/gw_route_verify.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_acceptance_report_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유postgres:18 fullID/owner/running·단일127.0.0.1/TCP준비확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그컨테이너postgres관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제라벨 비공개주입.
# 새0700폴더/새출력파일; 실행기가 새UUID *_test DB생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-69.json
# 읽기전용진단3건은 소유검증한 별도새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_acceptance_report_db.py -q --tb=short
```
관련단위1315의 같은35파일 재현:
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
```
전용고정카탈로그V9/28조건·관측v1–v9는유지한다. 진단revocationCoverage v2/12영역/28조건참조는모두NOT_EXECUTED·현재회사false/UNVERIFIED이고 운영전환12조건과별개다. 신규공통카탈로그를실행기/진단이공유하며untracked상태도코드지문에넣는다. 참조위치/관측범위와실행/서명·현재회사인수를구분한다. 진단생성은시험실행·과거JSON/환경PASS수입을하지않는다. 실제CLI별도실행도진단으로자동수입하지않는다. 읽기전용진단3건/고정28조건은다른검사이고중복합산/전체CI주장없음. work임시도구없이표준명령과절차§43으로재현하며중단자원은이번ID/owner로확인한생성분만정리한다.

## 2026-10-31 GW-READY-02 68차 — 저장 위임의 정책함수·회사ACL 런타임 대조 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작 `fedd5bd`/깨끗한 작업트리를 확인했다. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존 전용실행기 `GW_RESTORED_DENIAL_PROBES_V9`/28조건으로 확장했다. 이전v1다섯/v2~v6각둘/v7다섯/v8넷은 유지하고 새4조건만 StoredDelegationRuntimeObservation v9/`SYNTHETIC_STORED_FIXTURE_POLICY_ACL_AND_CLOSED_RESTORE_FLOOR`로 구분한다. 소유검증/새UUID DB·암호화백업/checkpoint/폐쇄restore·새MFA·현재실행/소스지문을 재사용한다. 기존식의 현재840초/일반300/마이그레이션120초·시간초과BLOCKED/부분JUnit미채택을 유지한다. 새공급자/복원기/임의대상·수동인수체크/PASS없음.
- 별도시험DB의 회사·세대범위 거래에서 gw.insert로 새합성 위임행을 넣는다. fixtureInserted=true/fixtureAcceptedViaApi=false와 실제담당자쌍/미회수행수/종류·대상GENERAL을 요구한다. API가 잘못된등록을 허용했다거나 마이그레이션/직접SQL운영권한/무누락수집을 확인한 결과가 아니다. 기존확정문서/제약/회수정책을 덮거나 해제하지 않는다.
- 합성4명으로 먼저 실제회사HTTP에서 GENERAL과종류미지정(null) 위임을 각각등록하고 별도GENERAL문서 열람/eligible1개/actionSteps·실제승인200·대리/원담당자이력을 확인한뒤 정상회수한다. 그뒤 STORED_KIND_MISMATCH(ERP_PURCHASE→GENERAL/1행), STORED_OUTGOING_CHAIN(원담당자→대리자→추가관계자/2행), STORED_INCOMING_CHAIN(추가관계자→원담당자→대리자/2행), STORED_DIRECT_ASSIGNMENT(원담당자1/대리자2단계/1행)의 현재상태를 검사한다. ERP_PURCHASE는GW코드매칭이며 실제ERP업무/스키마/인증연동은미검증이다.
- 각상태의 회사HTTP와 내부 policy.decision(company_mode=True)를 별도로대조한다. 비공개3조건은HTTP404/목록검색제외/빈eligible, 내부승인·반려각409/PRECONDITION_NOT_MET·reason=NOT_CURRENT_STEP다. 직접배정은합법열람/목록검색200을보존하되현재차례아닌HTTP·내부승인반려409/동일사유를요구한다. 내부정책호출은전체HTTP/버전·멱등/직접SQL운영경로검사가아니다. 거부예외는거래롤백을확인한다.
- 네조건모두 결함상태 뒤에도 별도현재직접단계담당자승인200/onBehalfOfPersonId=null을요구해 전체차단과구분한다. sourceHTTP·정책거부전후 문서/단계/이력/위임/영수증5개불변을 확인한다. 실제백업/checkpoint/폐쇄restore 뒤 companyHold=false/미회수위임0·새MFA2명·원담당자대상열람/별도승인·대리자의별도직접승인 뒤 HTTP/eligible/정책거부·5개불변을다시대조한다. 복원원인세조건ALL_DELEGATIONS_REVOKED/직접배정DIRECT_ASSIGNMENT_RETAINED를분리하며 복원전체회수로원본판정을대신하지않는다.
- v9는 준비방식/실제저장형태/두정상종류/원본·복원 각HTTP·정책·직접업무대조/불변을필수검증한다. 엄격한bool/int·실행UUID/코드/DB/시각/소스·누락/중복/skip/실패/지원외버전·JSON중복/8KiB/추가속성거부를유지한다. source는권한7+위5=선택12개, 거부불변각5개이며 인증/세션·감사/알림/전체DB/독립외부수집/전경로·실기기/실회사10인인수는아니다.
- 실제검증: 관련단위1302통과27.39초(신규59/기존사용중단경고2), 화면/도움말61통과6.60초. 소유PG 직접추가4조건65.20초통과. 집중단위351/전체1302·직접4/전용28·반복은합산하지않는다. 수정Python4개Ruff check/format·정적DB219표2409열543FK/R1–R6오류0. import정렬/중첩with린트보정, 기능시험실패없음. 최초문서생성명령의UTF8해석오류는파일쓰기전실패했고 ASCII이스케이프입력으로재생성한후도움말검사를재실행했다. 스키마/마이그레이션·metadata/Excel/ERD변경없음.
- 최종전용CLI: 최종소스28조건 PASSED/관측28(v1다섯/v2~v6각둘/v7다섯/v8~v9각넷), pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0·503.31초·상한840초. full64컨테이너ID/owner=gw-ready-02-phase68-test/running·단일127.0.0.1/TCP준비를확인한새postgres:18/새UUID *_test DB에서실행했다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨만정리하고owner잔여0확인. 기존미리보기/병행DB접속·초기화없음.
- 실회사절차§42/수집경계·정적도움말·문서지도/구현문서/현황199줄/progress/HANDOFF를갱신했다. API등록/저장런타임·HTTP/내부경계구분, 실제허용/거부·두종류/방향검사, 직접권한학습안내·기존실행기재사용을반영했으며 전체UI완성은아니다. 제품프런트미변경으로타입/ESLint/build·실브라우저/모바일재실행없음. 전체CI/전체회귀·기존V5전체경로합성모드/실회사·실기기10인/최종전환은미실행·미완료다.
- unsigned합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지.59차보고/제품12조건자동승격없음. 실계정/admin/비밀번호/OTP/키/브라우저·미리보기/다른checkout/WMS/main/push/배포변경없음. work/.env·비밀/전체로그Git제외.
- 다음:59차진단의선택권한검토맵을최신28조건의실제범위에대조하고오래된참조/미연결·미실행표시를갱신한다. 자동실행/결과수입·현재회사PASS로승격하지않는다. 동시성/직접SQL운영권한·외부공급자/독립최신성·전경로/전체회수·실API브라우저/최신main/전체회귀·실회사10인/최종전환은남는다. 난이도높음,GPT-6 Astra + High추천(선택범위/현재회사근거/실행과미실행·진단보고신뢰경계정합). 모델자동변경없음/사용자확인전다음단계자동착수없음.

재현(이 GW 저장소 루트; 비밀은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_stored_delegation_runtime_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_stored_delegation_runtime_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유postgres:18 fullID/owner/running·단일127.0.0.1/TCP준비확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그컨테이너postgres관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제라벨 비공개주입.
# 새0700폴더/새출력파일; 실행기가 새UUID *_test DB생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-68.json
# 직접4조건은 소유검증한 별도새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_stored_delegation_runtime_db.py -q --tb=short
```
관련단위1302의 같은35파일 재현:
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
```
전용V9는 기존24+새4=28조건이며 일반전체경로카탈로그V5와구분해 --restored-denial-only를명시한다. 현재상한840/최대1200초·일반300/마이그레이션120초와시간초과BLOCKED/부분JUnit미채택을유지한다. 이전관측v1–v8유지/새4만v9다. 합성행삽입은API등록·직접SQL운영권한/무누락수집 인수가아니다. 정상GENERAL/종류미지정의실제API대조뒤 저장행쌍/종류/행수와회사HTTP·내부정책승인/반려를구분한다. 내부409/PRECONDITION_NOT_MET·reason=NOT_CURRENT_STEP와HTTP404/직접배정200·409를각각검증한다. 잘못된상태와복원후에도별도현재직접단계승인200을확인한다. ERP코드는GW매칭이며실제ERP연동은별도다. 선택12소스/각5개거부불변·내부ASGI/합성MFA4명은 전체DB/실기기/실10인·독립외부수집/전체회수인수가아니다. work임시도구없이표준명령과절차§42로재현하며 중단자원은이번ID/owner로확인한생성분만정리한다.

## 2026-10-31 GW-READY-02 67차 — 위임 연쇄·직접배정/외화·금액 누락 경계 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작 `6adfeb8`/깨끗한 작업트리를 확인했다. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존 전용실행기 `GW_RESTORED_DENIAL_PROBES_V8`/24조건으로 확장했다. 이전v1다섯/v2~v6각둘/v7다섯은 보존하고 새4조건만 `RestoredDelegationRelationObservation` v8/`SYNTHETIC_SOURCE_RELATION_MONEY_AND_CLOSED_RESTORE_FLOOR`로 구분한다. 기존소유검증/새UUID DB·암호화백업/checkpoint/폐쇄restore·새MFA/실행/소스지문을 재사용한다. 현재상한은 기존식의720초, 일반300/마이그레이션120초·시간초과BLOCKED/부분JUnit미채택은 유지한다. 새공급자/복원기·임의대상/수동체크/PASS없음.
- 합성4명의 실제 회사HTTP 문서/결재선생성·상신·위임등록·승인으로 준비한다. 유효원담당자→대리자 위임으로KRW100대조열람/별도승인과actingPersonId·onBehalfOfPersonId를 먼저 확인한다. 원본의 회사·세대범위 유효위임1건/실제위임비회수·대조문서eligible1개를 요구한다. 전체DB에있는 다른합성범위 위임을 삭제하거나 회사범위1건을 전역집계로 바꾸지 않는다.
- DELEGATION_CHAIN_INPUT은 대리자가 별도직접현재단계도 가진상태에서 후보에게 재위임하면409/PRECONDITION_NOT_MET·details.reason=DELEGATION_OVERLAP_OR_CHAIN·실패5테이블불변/기존유효위임유지를 확인한다. 후보의대상조회/승인·반려404·eligible=[]·목록/검색제외를 요구한다. 실제연쇄등록차단이며 저장된불법연쇄의런타임차단 검사는아니다.
- DELEGATION_DIRECT_ASSIGNMENT는 원담당자1단계/대리자2단계직접배정 대상의 읽기·목록/검색200과 actionSteps/eligible빈값·승인/반려409/PRECONDITION_NOT_MET·reason=NOT_CURRENT_STEP를 구분한다. 별도현재직접단계의 실제승인200·onBehalfOfPersonId=null을 원본/복원양쪽에서 확인한다. 합법열람을 원문유출로 세거나 직접권한까지 위임회수로 숨기지 않는다.
- DELEGATION_FOREIGN_CURRENCY/DELEGATION_MISSING_AMOUNT는 실제생성응답의100/USD 또는amount/currency모두null과 maxAmount100을 확인하고 원본404/비노출/eligible=[]·같은위임KRW100허용을 대조한다. 입력값을 서로대신하거나 제한없는위임으로 통과시키지 않는다. v8이 실제금액/통화·한도/전송코드·사유를 별도필수검증한다.
- 폐쇄복원에서 companyHold=false/미회수위임0·새MFA2명과 원담당자 대상열람/별도직접승인, 직접배정조건의 본인현재단계승인을 확인한다. 이후 대상거부/합법열람의5테이블불변을 검사한다. 복원원인은 세조건ALL_DELEGATIONS_REVOKED/직접배정DIRECT_ASSIGNMENT_RETAINED로 분리한다. 복원전체회수만으로 원본관계/금액판정을대신하지않는다. source권한7+문서/단계/이력/위임/영수증5=12개·원본/대상각5개만 비교하며 인증/세션·감사/알림/전체DB불변·독립외부수집/전경로·실기기인수가 아니다.
- 실제검증: 관련단위1243통과23.92초(신규54/기존사용중단경고2), 화면/도움말61통과5.68초. 새소유PG 추가직접4조건57.48초통과 후 회사·세대범위쿼리를명시하고 최종CLI에서재확인했다. 집중단위292/전체1243·직접4/전용24·반복을합산하지않는다. 수정Python4개Ruff check/format·정적DB219표2409열543FK/R1–R6오류0. 스키마/마이그레이션·metadata/Excel/ERD변경없음.
- 최종전용CLI: 최종소스24조건 PASSED/관측24(v1다섯/v2~v6각둘/v7다섯/v8넷), pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0·320.80초·상한720초. full64컨테이너ID/owner=gw-ready-02-phase67-test/running·단일127.0.0.1/TCP준비를 확인한 새postgres:18/새UUID *_test DB에서 실행했다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨만 정리하고 owner잔여0확인. 기존미리보기/병행DB접속·초기화없음.
- 실패/보정: 초기직접PG4조건은34.47초실패했다. 내부사유를error.code로 기대했고 다른합성범위의위임까지 전역집계해1건으로기대했다. 실제기존계약인PRECONDITION_NOT_MET/개별details.reason을각각검증하고 회사·세대범위집계/실제위임비회수를확인하도록보정했다. 금액·통화/한도실측을관측계약에추가했다. 기존ACL/위임/전송/복원정책을바꾸지않았다. 실패로그는비공개보존/과거통과로대체없음. import정렬/미사용변수도보정했다.
- 실회사절차§41/수집경계·정적도움말·문서지도/구현문서/현황199줄/progress/HANDOFF갱신. 열람/처리·코드/사유의직관적구분·실제허용/거부의유효성·직접배정/통화학습안내·기존계약재사용을반영했으며 전체UI완성은아니다. 제품프런트미변경으로 타입/ESLint/build·실브라우저/모바일재실행없음. 전체CI/전체회귀·기존V5전체경로합성모드·실회사/실기기10인/최종전환은미실행·미완료다.
- unsigned합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지.59차보고/제품12조건자동승격없음. 실계정/admin/비밀번호/OTP/키/브라우저·미리보기/다른checkout/WMS/main/push/배포변경없음. work/.env·비밀/전체로그Git제외.
- 다음: 저장된위임의문서종류 런타임매칭·연쇄/직접배정차단을 합성서비스경계에대조하는고정검사. 실제ERP연동/불법연쇄허용·동시성/무누락/전체회수·외부공급자/독립최신성·실API브라우저/최신main/전체회귀/실회사10인/최종전환은남는다. 난이도높음, GPT-6 Astra + High추천(등록제한/저장행정책/회사ACL·현재단계/복원하한의정합). 모델자동변경없음/사용자확인전다음단계자동착수없음.

재현(이 GW 저장소 루트; 비밀은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_relations_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_relations_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유postgres:18 fullID/owner/running·단일127.0.0.1/TCP준비확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그컨테이너postgres관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제라벨 비공개주입.
# 새0700폴더/새출력파일; 실행기가 새UUID *_test DB생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-67.json
# 직접4조건은 소유검증한 별도새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_delegation_relations_db.py -q --tb=short
```
관련단위1243의 같은35파일 재현:
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
```
전용V8는 기존20+새4=24조건이며 일반전체경로카탈로그V5와구분해 --restored-denial-only를명시한다. 이전관측v1–v7유지/새4만v8이다. 현재상한720/최대1200초·일반300/마이그레이션120초와시간초과BLOCKED/부분JUnit미채택을유지한다. 전송코드PRECONDITION_NOT_MET와details.reason의NOT_CURRENT_STEP/DELEGATION_OVERLAP_OR_CHAIN을각각검사한다. 직접배정의합법열람200/현재차례아닌409와개별현재단계직접승인200을보존한다. 회사·세대유효위임1건/실제금액통화·한도를확인하고 복원위임전체회수와직접권한보존을구분한다. 연쇄는등록차단이며 저장된불법연쇄/타종류런타임·ERP연동은별도다. 선택12소스/원본·대상각5테이블과내부ASGI/합성MFA·4명은 전체DB/외부독립성·실기기/실10인인수가아니다. work임시도구없이표준명령과절차§41로재현하며 중단자원은이번ID/owner로확인한생성분만정리한다.

## 2026-10-31 GW-READY-02 66차 — 원본 위임 범위와 복원 전체회수 하한 분리 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작 `6d31351`과 깨끗한 작업트리를 확인했다. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존 전용실행기를 `GW_RESTORED_DENIAL_PROBES_V7`/20조건으로 확장했다. 앞선v1다섯/v2~v6각둘은 보존하고 새5조건만 `RestoredDelegationBoundaryObservation` v7/`SYNTHETIC_SOURCE_BOUNDS_AND_CLOSED_RESTORE_DELEGATION_FLOOR`로 구분한다. 기존 소유검증/새UUID DB·실제암호화백업/checkpoint/폐쇄restore/새MFA·현재실행/소스지문을 재사용했다. 새 공급자/복원기/임의대상·수동인수체크/PASS는 없다.
- 핵심: 복원도구가 모든위임을 회수하므로 그404만으로 기간/한도/단계판정을 통과시키지 않는다. 원본실제API의 상세/승인/반려404·목록/검색비노출·실제policy.eligible=[]·허용대조·거부5테이블불변을 먼저 검사하고, 복원후에는 restoredBoundaryCause=ALL_DELEGATIONS_REVOKED·미회수0건과 별도대조/거부를 요구한다. sourceWindow·sourceDenialStateUnchanged와 sourceUnchanged·복원거부를 분리한다.
- 새5조건: DELEGATION_NOT_STARTED는 DB현재시각보다1시간뒤 시작/FUTURE, DELEGATION_EXPIRED는1시간전 만료/EXPIRED다. 실제DB 정책함수에 정확한 startsAt/endsAt를 넘겨 시작포함/종료제외를 확인하되 HTTP가 그순간 실행됐다고 주장하지 않는다. DELEGATION_AMOUNT는 활성위임 KRW100한도에서101거부와100승인/현재대조열람을 확인한다. DELEGATION_KIND_INPUT은 ERP_PURCHASE 등록400/VALIDATION_FAILED와 잔존유효위임없는 대상404다. 회사는GENERAL등록만 허용하며 타종류저장행 런타임매칭/ERP업무는 검사하지 않았다. DELEGATION_CURRENT_STAGE는 원 담당자2단계/현재1단계에서 대리404, 실제앞단계담당자 승인뒤2단계조회/actionSteps·eligible1개로 허용을 확인한다.
- 합성4명의 기안자/원 담당자/대리자/앞단계담당자를 분리했다. 실제 회사API로 생성/상신·위임등록/회수·승인을 준비한다. 유효한위임의 별도문서 열람/승인과 실제처리자·원 담당자 이력을 먼저 확인한다. 확정문서/시계를 SQL로 덮지 않는다. 원본거부 불변 뒤의 허용단계진행은 분리한다. 그현재상태 백업/checkpoint 후 닫힌복원본에서 companyHold=false/미회수위임0·새MFA2명/원 담당자 대상읽기·별도직접승인200과 대리상세/승인·반려404/목록검색비노출·거부5테이블불변을 확인한다. 옛위임을 활성화하지 않는다.
- v7는 원본/복원 각측정과 조건별끝점/동액한도/정확한입력400/실제단계진행을 필수검증한다. bool/int/버전·실행UUID/코드/DB/시각/소스일치·누락/중복/skip/실패/지원외버전·JSON중복/8KiB/추가속성거부를 유지한다. source는 권한7+문서/단계/이력/위임/영수증5=선택12개, 원본거부/대상거부는각5개만 비교한다. 전체DB/독립외부수집/전경로무누락·실기기/실회사10인인수는 아니다.
- 실제검증: 관련단위1189통과26.88초(신규43/기존사용중단경고2), 화면/도움말61통과5.86초, 소유PG 직접추가5조건71.59초통과. 집중단위238/전체1189·직접5/전용20·반복은 합산하지 않는다. 수정Python5개 Ruff check/format·정적DB219표2409열543FK/R1–R6오류0. 초기import정렬2건을 보정했고 기능시험의실패없음. 최초전체CLI는기존300초상한으로보고서없이실패해생성전용컨테이너/볼륨을정리했다. 전용모드고정상한을조건수기반(현재600/최대1200초)으로하고일반모드300/마이그레이션120초는유지했다. 시간초과부분JUnit을읽지않고BLOCKED/EXECUTION_TIMEOUT·관측없음/UNVERIFIED/pytestExitCode=null보고·기본DB정리를검사하는자식TimeoutExpired/DB연결모의2모드회귀를추가했다(실제600초소진시험미실행). 최초실패를비공개보존하고새DB/새출력에서최종재실행했다. 스키마/마이그레이션·metadata/Excel/ERD변경없음.
- 최종 전용CLI: 최종소스의20조건 PASSED/관측20(v1다섯/v2~v6각둘/v7다섯), pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0·366.67초, executionTimeoutSeconds=600. full64컨테이너ID/owner=gw-ready-02-phase66-test/running·단일127.0.0.1/TCP준비를 확인한 새postgres:18/새UUID *_test DB에서 실행했다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨만 정리하고 owner잔여0을 확인했다. 기존미리보기/병행DB접속·초기화없음.
- 실회사절차§40/수집경계·정적도움말·문서지도/구현문서/현황199줄/progress/HANDOFF를 갱신했다. 원본판정/복원하한의 직관적구분, 실제거부/허용/정책의 유효성, 기간/한도/순서학습 안내, 기존계약/실행기재사용을 반영했다. 전체UI완성은 아니다. 제품프런트미변경으로 타입/ESLint/build·실브라우저/모바일재실행없음. 전체CI/전체회귀·기존V5전체경로합성모드/실회사·실기기10인/최종전환은 미실행·미완료다.
- unsigned 합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부 유지.59차보고서/제품12조건자동승격없음. 실계정/admin/비밀번호/OTP/키/브라우저·미리보기/다른checkout/WMS/main/push/배포변경없음. work/.env·비밀/전체로그Git제외.
- 다음: 위임연쇄/직접배정충돌과 외화·금액누락의 접근경계 고정검사. 타종류저장행의런타임매칭/동시성·일정/채팅guard정책·게시정정·직접SQL/운영도구/SSO·전경로/전체회수/외부공급자·독립최신성·실API브라우저/최신main/전체회귀·실회사10인/최종전환은 남는다. 난이도높음, GPT-6 Astra + High추천(ACL/처리정책의연쇄·통화/금액정합과복원하한구분). 모델자동변경없음/사용자확인전다음단계자동착수없음.

재현(이 GW 저장소 루트; 비밀은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_bounds_db.py backend/tests/test_gw_route_verify.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_bounds_db.py backend/tests/test_gw_route_verify.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유postgres:18 fullID/owner/running·단일127.0.0.1/TCP준비확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그컨테이너postgres관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제라벨 비공개주입.
# 새0700폴더/새출력파일; 실행기가 새UUID *_test DB생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-66.json
# 직접5조건은 소유검증한 별도새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_delegation_bounds_db.py -q --tb=short
```
관련단위1189의 같은35파일 재현:
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
```
전용V7는 기존15+새5=20조건이며 일반전체경로카탈로그V5와구분해 --restored-denial-only를명시한다. 이전관측v1–v6유지/새5만v7이다. 복원404만으로 원본기간/한도/단계를 검증했다고 세지 않는다. 시각끝점은 정책함수명시시각/HTTP는안정된구간으로구분하고, 종류는회사GENERAL등록제한/실제ERP런타임매칭과구분한다. 합성4명·내부ASGI/합성MFA·선택12소스/각5대상불변은 실10인/실기기·전체DB/외부독립성·전체회수증명이아니다. work임시도구없이 표준명령/절차§40으로재현하며 중단자원은이번ID/owner로확인한생성분만정리한다.

## 2026-10-31 GW-READY-02 65차 — 위임 회수·현재 결재권과 실제 대리 처리 이력 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `05b3c66`/깨끗한 작업트리를 확인했다. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존 전용실행기 `GW_RESTORED_DENIAL_PROBES_V6`/15조건으로 확장했다. 이전v1다섯/v2둘/v3둘/v4둘/v5둘은 유지하고 새위임2조건만 `RestoredDelegationDenialObservation` v6로 분리한다. 기존 소유검증/새UUID DB/실제 암호화백업·checkpoint·폐쇄restore/새MFA·실행UUID/코드/DB/시각·소스지문 검증을 재사용한다. 새 공급자/복원기·수동체크·임의대상·인수PASS는 없다.
- 합성3명의 기안자/원 담당자/대리자를 분리한다. 현재 원 담당자 단계에 실제 위임생성API로 유효한 GENERAL 위임을 만들고 대리열람/actionSteps의delegationId·별도문서 승인/actingPersonId·onBehalfOfPersonId/이벤트1개를 백업 전에 확인한다. 관리계정도 기안자 예외 없이 위임만으로 대상에 접근하게 했다. DELEGATION_REVOKED는 백업전 실제 회수API 뒤 미처리문서조회/승인·반려404, 목록/검색·원문비노출을 요구한다. 복원후 원 담당자 조회/actionSteps·별도 직접승인200과 실제대리처리자 과거문서열람200·원 담당자 이력을 보존한다.
- DELEGATION_GUARD는 백업뒤 실제회수API/최신checkpoint의delegation guard 불일치로 회사격리/활성GW연결0/companyHold=true를 확인한다. core 새MFA성공과 원 담당자/대리자의 현재/과거GW조회·처리·목록/검색/옛영수증재요청403/GW_IDENTITY_REQUIRED를 구분한다. 격리된GW 양성대조를true로 꾸미지 않는다. 기존 복원도구는 모든 활성위임을 보수적으로 회수한다. 양조건 모두 미회수0건/restoredDelegationsRevoked=true·delegationReplayed=false를 요구하며 옛활성행을 그대로 남긴다고 가정하지 않는다.
- 과거 완료문서의 실제승인영수증이 복원초기/재요청직전에 존재하고 문서ID가 맞아야 한다. 정상회수에서는 같은멱등키/expectedVersion/본문의 완료요청이 원래결과200으로 재전송되고 승인1개/문서·단계/이력·위임/영수증5테이블이 변하지 않아야 한다. 이 과거성공은 현재미처리대상 권한으로 세지 않는다. 격리에서는 영수증재전송도403이다. source는 기존권한7+앞선5=선택12개, 대상은5개를 비교한다. 정상허용쓰기뒤/모든격리GW요청전에 지문을 잡고 인증·세션/보안감사·알림/전체DB불변을 주장하지 않는다.
- v6는 현재승인/반려와 목록/검색·과거이력/완료재전송의 상태·오류/복원전후대조/격리·회수필수값을 분리한다. 정확한bool/int/실행문맥/지원버전과 누락/중복/skip·실패/JSON중복/8KiB/추가속성 거부를 유지한다. unsigned합성 PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부 유지,59차 보고서/제품12조건으로 자동승격하지 않는다.
- 실제검증: 최종 관련단위1146통과23.09초(신규31/기존사용중단경고2), 화면/도움말61통과5.18초. 소유PG 추가직접2조건26.66초통과. 집중단위194/이전1145·직접2/최종CLI15·반복을 독립건수로 합산하지 않는다. 수정Python4개Ruff check/format·정적DB219표2409열543FK/R1–R6오류0. 스키마/마이그레이션·metadata/Excel/ERD변경없음.
- 최종CLI: 15조건 PASSED/관측15(v1다섯/v2둘/v3둘/v4둘/v5둘/v6둘), pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0·171.70초. full64컨테이너ID/owner=gw-ready-02-phase65-test/running·단일loopback을 확인한 새postgres:18/새UUID *_test DB에서 실행했다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨만 정리했고 owner잔여0을 확인했다. 기존미리보기/병행DB에는 접속/초기화하지 않았다.
- 실패/보정: 초기 실제PG2조건은25.90초 실패했다. 정상문서 목록의 data가페이지객체인데 배열로 해석했고, 격리복원에서 기존전체위임회수를 무시해 옛활성행을 기대했다. rows를읽고 양조건미회수0건과필수관측을추가했다. 기존ACL/위임회수/격리·캐시정책은 수정하지 않았다. 초기실패로그는 비공개보존했고 과거통과로 대신하지 않았다.
- 실회사절차§39/수집경계·정적도움말·문서지도/구현문서/현황199줄·progress/HANDOFF를 갱신했다. 현재권한/과거이력·격리 구분/실제원본대조·회수/재전송안내·기존계약재사용을 반영했으며 전체UI완성은 아니다. 제품프런트미변경으로 타입/ESLint/build·실브라우저/모바일을 재실행하지 않았다. 전체CI/전체회귀·기존V5전체경로합성모드/실회사·실기기10인인수는 미실행/미완료다. 실제계정/admin/비밀번호/OTP/키/브라우저·미리보기/다른checkout/WMS/main/push/배포변경없음. work/.env·비밀/전체로그Git제외.
- 다음: 위임 유효기간/금액·문서종류 한도/현재단계의 접근경계 고정검사. 연쇄/배정변경·일정/채팅guard정책/동시성·게시정정·직접SQL/운영도구/SSO·전경로무누락/전체회수·외부공급자/독립최신성·실API브라우저/최신main/전체회귀·실회사10인/최종전환은 남는다. 난이도높음,GPT-6 Astra + High추천(실시간기간·SQL ACL/처리적격성·복원제한일치). 모델자동변경없음, 사용자확인전 다음단계자동착수없음.

재현(이 GW 저장소 루트; 비밀값은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1146은 아래64차1115와 같은35파일에 신규31건이 추가된 결과다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_delegation_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 fullID/owner/running·단일127.0.0.1/TCP준비 확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그 컨테이너 postgres관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제owner라벨 비공개주입.
# 새0700폴더/새출력파일 사용; 실행기가 새UUID *_test DB생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-65.json
# 직접재현은 소유검증한 별도 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입 후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_delegation_db.py -q --tb=short
```
전용V6는 기존13+위임2=15조건이다. 일반전체경로카탈로그V5와구분해 --restored-denial-only를명시한다. 이전관측v1–v5보존/새위임만v6이며 보고서단독으로 최종PASS를 만들지않는다. 명시적회수의두시점과 현재권한/실제과거처리이력·동일완료요청을구분한다. 기존복원은 전체위임회수이며 양조건미회수0건/guard불일치회사격리를검사한다. 목록data는페이지객체의rows를읽는다. 선택12소스/5대상불변·내부ASGI/합성MFA와 전체DB/실기기·외부독립성/전체회수를구분한다. work임시도구/비공개로그없이 위표준명령과실회사절차§39로재현한다. 중단자원은이번ID/owner로확인한생성분만정리한다.

## 2026-10-30 GW-READY-02 64차 — 일정 소유자·참석자/응답 영수증 복원 경계 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, `codex/gw-company-01`, 시작 커밋 `d776913`과 깨끗한 작업 트리를 확인했다. 이 checkout만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- 기존 전용 실행기를 `GW_RESTORED_DENIAL_PROBES_V5`/13조건으로 확장했다. 앞선 v1다섯/v2둘/v3둘/v4둘은 보존하고 일정2조건만 `RestoredCalendarDenialObservation` v5로 분리한다. 기존 소유 검증/새UUID DB·실제 암호화 백업/checkpoint/폐쇄restore·새MFA/실행 문맥·소스 지문 검증을 재사용했다. 새 수집기/복원기/공급자·임의 대상·수동 완료 체크·인수 PASS를 만들지 않았다.
- `CALENDAR_REMOVED_ATTENDEE`: 백업 전에 실제 소유자 수정API로 참석에서 제외한 일정의 상세/응답·보존된 응답 영수증의 같은 요청 재전송/수정/취소404·목록 제외/제목 미노출을 확인한다. 복원 후 소유자의 대상 조회/대조일정 수정과 남은 참석자의 대조일정 조회/DECLINED 응답200을 확인한다. 읽을 수 있는 참석자라도 소유자가 아니면 수정/취소404다. 불참 응답과 참석자 제외·편집권을 혼동하지 않는다.
- `CALENDAR_ATTENDEE_GUARD`: 백업 뒤 같은 실제 소유자 수정API로 참석자를 제외하고 최신 checkpoint를 만든다. calendar_event/event_attendee 전체guard 불일치로 활성GW연결0/companyHold=true·소유자/참석자의 모든 대상/대조업무·목록403/GW_IDENTITY_REQUIRED를 확인한다. core 새MFA 성공과 GW 양성 대조를 구분하고 복원 후 GW 대조를 true로 꾸미거나 옛 참석자 행을 임의 재생하지 않는다.
- 기존 응답 영수증의 일정ID를 복원 직후와 재요청 직전에 확인하고 원래 멱등키·expectedVersion/본문을 그대로 쓴다. 영수증 없는 새 요청/다른본문·버전충돌을 회수 검증으로 대신하지 않는다. source는 권한7+일정/참석자/영수증3=선택10개, 대상 거부 전후는3개를 비교한다. 정상 대조 쓰기 후/격리GW거부 전에 지문을 잡고 인증·세션/보안감사/알림 등 전체DB불변을 주장하지 않는다. 현재 guard에는 제목·일시/장소·응답시각 등도 포함되며 이번은 참석자 제외의 두 시점만 확인한 것이다.
- 실제 DB 검사 초기2조건은13.61초에 KeyError(all_day)로 실패했다. 회사 일정 PATCH에서 exclude_unset이 생략 가능한 allDay/location 기본값까지 제거하던 기존 제품 결함이었다. 일정 전체교체 경로만 개인GW처럼 모델 기본값을 전달하도록 보정하고, 생략 입력을 유지한 복원 정상 대조와 기존 회사HTTP 시험에 수정/기본값 검증을 추가했다. 다른 PATCH/DELETE 부분변경과 권한/격리는 유지했다. 수정한 기존 시험의 import 정렬 I001도 보정했다. 실패 로그는 비공개로 보존하고 과거 성공으로 대신하지 않았다.
- 실제 검증: 관련 단위1115 통과22.98초(신규33/기존 사용중단 경고2), 최종 도움말 반영 후 화면/도움말61 통과5.03초. 새 소유 PostgreSQL의 일정 직접2조건24.18초·회사HTTP 회귀10건67.44초 통과. 직접2/전용13·집중단위164/전체1115·반복 실행은 별개 건수로 합산하지 않는다. 수정Python6개 Ruff check/format, 정적DB219표2409열543FK·R1–R6 오류0. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음.
- 최종 전용CLI: 최종 소스에서13조건 PASSED/관측13(v1다섯/v2둘/v3둘/v4둘/v5둘)·pytest종료0·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0, 141.56초. import 정렬 전 실행도13조건 통과했으나 최종 소스 지문으로 새DB/새출력에서 재실행했다. 각 실행은 full64 컨테이너ID/owner=gw-ready-02-phase64-test/running·단일127.0.0.1 바인딩을 확인한 새 postgres:18과 새UUID *_test DB에서 수행했다. 생성 DB/폐쇄복원DB·컨테이너/볼륨만 정리하고 소유 라벨 잔여0을 확인했다. 기존 미리보기·병행DB에 접속/초기화하지 않았다.
- 실회사 절차§38/수집경계·정적 도움말/문서지도·구현문서/현황199줄·progress/HANDOFF를 갱신했다. 소유자/참석자·거부/격리 구분, 정확한 권한 경계·영수증, 응답/제외 학습 안내와 기존 계약 재사용을 반영했다. 전체 UI 완성은 아니다. 프런트제품 코드 미변경으로 타입/ESLint/build·브라우저/모바일 재실행 없음. 전체CI/전체회귀·기존V5 전체합성모드/실회사·실기기10인 인수는 미실행/미완료다.
- unsigned 합성 PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부 유지.59차 보고서/제품12조건으로 자동 승격하지 않는다. 실계정/admin 이름·비밀번호/OTP/키·브라우저/미리보기·다른checkout/WMS/main/push/배포 변경 없음. work/.env·비밀/전체로그 Git 제외.
- 다음: 결재 위임의 복원 후 접근 경계 고정검사를 같은 제한 실행기에 연결한다. 일정 소유자교체/부서공개·응답만의guard정책·채팅재가입/읽음순번·동시성/게시정정·직접SQL/운영도구/SSO·전경로무누락/전체회수·독립최신성/외부공급자·실API브라우저/최신main/전체회귀·실회사10인/최종전환은 남는다. 난이도 높음, GPT-6 Astra + High 추천(위임 유효기간·현재 주체/단계·회사격리 정합). 모델 자동변경/사용자 확인 전 다음단계 자동착수 없음.

재현(이 GW 저장소 루트; 비밀은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1115는 아래63차1082와 같은35파일에 새단위33건을 추가한 결과다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/company_http.py backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_company_http.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_calendar_db.py
uv run --project backend ruff format --check backend/src/fs/gw/company_http.py backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_company_http.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_calendar_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 fullID/owner/running·단일loopback/TCP준비 확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL=그 컨테이너 postgres 관리연결,
# GW_BACKUP_TEST_CONTAINER=전체ID, FS_GW_ROUTE_VERIFY_OWNER=실제 라벨을 비공개주입.
# 새0700 폴더/새 출력파일 사용; 실행기가 새UUID *_test DB 생성/마이그레이션/검사/정리.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-64.json
# 직접검사는 소유 검증한 별도 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_calendar_db.py backend/tests/test_gw_company_http.py -q --tb=short
```
전용V5는 앞선11+일정2=13조건이다. 일반 전체경로 카탈로그V5와 구분하고 --restored-denial-only를 명시한다. 이전 관측v1–v4를 바꾸지 않고 새일정만v5다. 소유자 편집/취소와 참석자 조회/응답·불참응답/명단제외를 구분한다. 원래 영수증/요청이 남은 재전송만 측정하며 정상 필터목록200/data와 실제404/403의 data금지를 구분한다. 일정/참석자 전체guard의 비권한 필드 변경 격리 제약을 숨기거나 자동해제하지 않는다. 내부ASGI·합성MFA준비는 실기기 인수가 아니며 선택10개소스/3개대상 비교는 전체DB불변·전체회수를 뜻하지 않는다. work 임시도구/비공개로그 없이 위 표준 명령/실회사 절차§38로 재현한다. 생성자원은 이번ID/owner로 확인한 생성분만 정리한다.

## 2026-10-30 GW-READY-02 63차 — 채팅 멤버십·메시지/영수증 복원 후 접근 경계 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `10a2d6b`/작업트리깨끗함 확인. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존전용실행기를 GW_RESTORED_DENIAL_PROBES_V4/11조건으로 확장했다. v1다섯/v2둘/v3둘은 보존하고 새CHAT_LEFT_MEMBER/CHAT_MEMBERSHIP_GUARD2조건만 RestoredChatDenialObservation v4로구분한다. 기존소유검증/새UUID DB/백업·checkpoint·폐쇄restore/새MFA/실행UUID·버전/시각·소스지문을 재사용한다. 새복원·수집기/임의대상·공급자/수동인수체크·PASS형식은없다.
- CHAT_LEFT_MEMBER: 백업전나간채널은조회/빈조회순번·신규전송·보존영수증의같은요청재전송·읽음처리404/NOT_FOUND, 목록제외/본문·채널명미노출을검사한다. 남은관리자의대상조회와직원의별도대조채널조회/전송/읽음200·새MFA로전부거부와구분한다. CHAT_MEMBERSHIP_GUARD: 백업뒤실제나가기API/최신checkpoint의chat_member변경은기존회사격리로GW활성연결0/companyHold=true·모든GW요청403/GW_IDENTITY_REQUIRED를확인한다. core새MFA성공과GW격리를구분하며복원후GW양성대조를true로꾸미지않고멤버십을임의재생하지않는다.
- 복원본초기와실제재요청직전 원래영수증이있고 메시지ID가일치하는지확인한다. 영수증없는새요청·만료/본문불일치422를재전송거부로대체하지않는다. 원본선택7권한+채팅3/request_receipt1=11테이블비교, 대상거부전후채팅/영수증4테이블불변과정확한상태/코드·비노출을필수검증한다. 정상200필터목록에는대조채널data를허용하되실제404/403응답은data가없어야한다. 정상대조쓰기뒤/격리GW거부전에지문을잡으며인증/세션유휴·보안감사처리를객체불변과혼동하지않는다.
- v4는조회/전송/영수증재전송/조회순번/읽음/목록·양성대조·격리·영수증보존을분리하고지원외버전/누락·중복/skip·실패/실행문맥·JSON/소스불일치차단을유지한다. chat_member전체guard에는읽음순번/가입시각도포함되며이번에는나가기시점2조건만확인했다. 성공도unsigned합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지. 전경로수집/외부독립성/전체회수인수는아니다.
- 최종검증: 관련단위1082통과22.61초(신규29/기존사용중단경고2), 화면/정적도움말61통과5.39초. 수정Python4파일Ruff check/format·정적DB219표2409열543FK/R1–R6 오류0. 프런트제품코드미변경으로이번타입/ESLint/build·실브라우저/모바일은재실행하지않았다. 전체CI/전체회귀·실회사/실기기10인/기존V5전체합성실행은미완료/미실행이다.
- 실제PG/CLI: 새owner=gw-ready-02-phase63-test·전체ID/running/단일loopback확인컨테이너와새UUID *_test DB에서추가2조건23.94초통과. 최종전용CLI는새출력파일에서11조건PASSED·관측11(v1다섯/v2둘/v3둘/v4둘)·pytest종료0/sourceUnchanged/databaseCleaned=true·PARTIAL/종료0/127.27초다. 직접2+CLI11/반복을다른13건으로합산하지않는다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨정리와owner잔여0확인. 기존미리보기/병행DB에는접속/초기화하지않았다.
- 실패/보정: 초기채널생성201을시험도우미가200으로기대해준비2건이12.89초실패했다. 생성만201로명시하고메시지/조회·읽음의기존200은유지했다. 초기전체CLI와진단실행은10통과/CHAT_LEFT_MEMBER1실패·BLOCKED였다. 정상필터목록200에대조채널data가있어야하는데거부응답의data금지검사를같이적용한것이원인이었다. 실제404/403응답에만data금지를적용하고정상목록의대상제외/대조노출과본문미노출·상태불변은유지했다. 재전송직전에도영수증을재확인해최종소스/새번호·새소유DB/새파일로전체CLI11을통과했다. 실패출력은덮거나과거통과로대신하지않았고import정렬I001도보정했다.
- 문서/범위: 실회사절차§37/수집경계/도움말/문서지도·구현문서/현황199줄/progress/HANDOFF갱신. 직관성(멤버십/격리구분)/유효성(보존영수증·정확한경계·불변)/학습성(나간채널/새인증·GW권한구분)/유연성(기존계약/실행기재사용)을반영했으며전체UI완성은아니다. 스키마/마이그레이션·metadata/Excel/ERD·실계정/admin/비밀번호/OTP/키/브라우저설정변경없음. work/.env·비밀/전체로그Git제외. 다른checkout/WMS/main/push/배포변경없음.
- 다음: 일정소유자/참석자의복원후접근경계고정검사를같은제한실행기에연결한다. 채팅멤버추가/재가입·읽음순번변경만의guard정책/동시성·정정/재게시/결재위임·직접SQL/운영도구/SSO·전경로무누락/전체회수·독립최신성/외부공급자·실API브라우저/최신main/전체회귀·실회사/기기10인/최종전환은남는다. 난이도높음,GPT-6 Astra + High 추천(객체참석권한·회사격리·복원원본정합),모델자동변경없음. 사용자확인전다음단계자동착수하지않는다.

재현(이 GW 저장소 루트; 비밀값은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1082는 아래62차1053의 같은35파일에 새단위29건이 추가된 결과다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_chat_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_chat_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 컨테이너 fullID/owner/running·단일loopback/TCP준비 확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL은 해당컨테이너 postgres관리연결, GW_BACKUP_TEST_CONTAINER는전체ID,
# FS_GW_ROUTE_VERIFY_OWNER는실제owner라벨을 비공개주입. 새0700폴더/새출력파일 사용.
# 실행기가 새UUID *_test DB를 생성/마이그레이션/검사/정리한다. 기존DB초기화없음.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-63.json
# 추가채팅2조건만 직접재현: 소유검증한 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입 후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_chat_db.py -q --tb=short
```
전용V4전체는v1다섯+v2둘+v3둘+v4둘=11조건이다. 반복/직접2를다른시나리오로합산하지않는다. 생성201/메시지·조회·읽음200과권한거부404/403을구분한다. 나간채널의404와chat_member불일치의회사격리403을혼동하지않고영수증이없는새요청을캐시재전송으로세지않는다. 정상200필터목록에는멤버대조채널data가있어야하며실제404/403은data가없어야한다. 선택11테이블(권한7+채팅3/영수증1)/내부ASGI·합성MFA준비와전체DB불변/실기기등록·전경로수집·전체회수를구분한다. chat_member전체guard의읽음순번/가입시각포함제약과멤버십임의재생금지/격리유지·ready=false/미확인4·실제복원PARTIAL/PASS거부유지. 중단자원은이번생성ID/owner로확인해생성분만정리한다. work도구/비공개로그없이위표준검사/실회사절차§37로재현한다.

## 2026-10-30 GW-READY-02 62차 — 게시물 조직 공개·공개 범위 guard 복원 검사 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `e9c1119`/작업트리깨끗함 확인. 이 checkout만 수정했다. 최종커밋은 `git log -1`로 확인한다.
- 기존전용실행기를 GW_RESTORED_DENIAL_PROBES_V3/9조건으로 확장했다. v1다섯/v2둘은 유지하고 새게시물2조건만 RestoredPostDenialObservation v3로 분리한다. 기존소유검증/새UUID DB/실제dump·암호화백업·checkpoint·폐쇄restore·새MFA/실행UUID·버전/시각/소스지문 검증을 재사용했다. 새수집기/공급자/임의대상·수동완료체크·인수PASS는없다.
- POST_ORG_SCOPE: 백업전후 소속조직밖 작성자본인글·같은조직공지·회사공개글 읽기200과 직원본인FREE초안수정200을 대조한다. 다른조직공지의 상세/수정404/NOT_FOUND·목록/검색미노출·게시물/이력·조직/소속4개테이블 불변을 확인한다. POST_VISIBILITY_GUARD: 백업뒤 전체공개→조직공개 변경만 합성SQL로주입하고 기존guard의 활성GW연결0/companyHold=true를 확인한다. 옛게시물의 전체공개값은자동재생하지 않으며 관리자/직원새MFA성공과 GW상세/수정·목록/검색/본인초안403/GW_IDENTITY_REQUIRED를 구분한다. 격리된GW의복원후양성대조를true로꾸미지 않는다.
- v3는 복원전후대조/격리/보존중지·정확한읽기/수정오류·목록/검색모드와본문미노출·상태불변을 필수로검증한다. FILTERED(정상조직ACL)와IDENTITY_DENIED(회사범위격리)를혼동하거나 범위를재생했다고주장하면거부한다. 원본비교는 선택7개권한+person/organization_unit/board_post/board_event=11개이며 문서v2의11개와구성이다르다. 인증/유휴세션·감사처리를 객체불변과혼동하지 않는다. 성공도unsigned합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지.
- 최종검증: 관련단위1053통과26.21초(신규22/기존사용중단경고2), 화면/정적도움말61통과6.36초. 수정Python4파일 Ruff check/format·정적DB219표2409열543FK/R1–R6 오류0. 프런트제품코드미변경으로 이번타입/ESLint/build·실브라우저/모바일은재실행하지 않았다. 전체CI/전체회귀·실회사/실기기10인/기존V5전체합성실행은미완료/미실행이다.
- 실제PG/CLI: 새owner=gw-ready-02-phase62-test·전체ID/단일loopback 확인 컨테이너와 새UUID *_test DB에서 추가2조건33.20초통과. 거부요청전후지문/미노출범위를보강한 최종전용CLI는9조건PASSED·관측9개(v1다섯/v2둘/v3둘)·pytest종료0/sourceUnchanged/databaseCleaned=true·PARTIAL/종료0/141.77초다. 직접2+CLI9를 다른11건으로합산하지 않는다. 생성기본DB/폐쇄복원DB·컨테이너/볼륨정리와owner잔여0확인. 기존미리보기/병행DB에는접속/초기화하지 않았다.
- 실패/보정: 초기합성준비에서 FREE게시물에ORG공개를주어 기존NOTICE한정규칙으로2건400/VALIDATION_FAILED·17.14초실패했다. 공지로준비하고 기존게시권한/조직/격리규칙은유지했다. import정렬I001을보정했다. 최종검사에서는 격리경로의모든GW거부요청 전에 지문을잡고 정상허용수정은지문전에마쳐 부작용범위를구분했다. 실패를과거통과로대신하거나 미실행을통과로세지 않았다.
- 문서/범위: 실회사절차§36/수집경계/도움말/문서지도·구현문서/현황199줄/progress/HANDOFF갱신. 직관성(필터/격리구분)/유효성(실제게시/양성대조·정확한거부)/학습성(새인증과GW격리구분)/유연성(기존계약·실행기재사용)을반영했으며 전체UI완성은아니다. 스키마/마이그레이션·metadata/Excel/ERD·실계정/admin/비밀번호/OTP/키·브라우저설정변경없음. work/.env·비밀/전체로그Git제외. 다른checkout/WMS/main/push/배포변경없음.
- 다음: 채팅멤버십/메시지의 복원후접근경계 고정검사를 같은제한실행기에 연결한다. 정정/재게시·결재/위임·일정·직접SQL/운영도구/SSO·전경로무누락/전체회수·독립최신성/외부공급자·실API브라우저/최신main/전체회귀·실회사/기기10인/최종전환은남는다. 난이도높음, GPT-6 Astra + High 추천(객체멤버십·회사격리·복원원본정합), 모델자동변경없음. 사용자확인전 다음단계 자동착수하지 않는다.

재현(이 GW 저장소 루트; 비밀값은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1053은 아래61차1031의 같은35파일에 새단위22건이 추가된 결과다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_post_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_post_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 컨테이너 fullID/owner/running·단일loopback/TCP준비 확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL은 해당컨테이너 postgres관리연결, GW_BACKUP_TEST_CONTAINER는전체ID,
# FS_GW_ROUTE_VERIFY_OWNER는실제owner라벨을 비공개주입. 새0700폴더/새출력파일 사용.
# 실행기가 새UUID *_test DB를 생성/마이그레이션/검사/정리한다. 기존DB초기화없음.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-62.json
# 추가게시물2조건만 직접재현: 소유검증한 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입 후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_post_db.py -q --tb=short
```
전용V3전체는v1다섯+v2둘+v3둘=9조건이다. 반복실행/직접2를다른시나리오로합산하지않는다. 조직공개는NOTICE공지에서만허용한다. 공개범위guard불일치는회사GW격리이며 공개범위재생/필터성공으로꾸미지않는다. 새MFA성공후에도GW403일수있고격리조건의복원후업무양성대조는false다. 선택11테이블(권한7+게시/조직4)비교/내부ASGI·합성MFA준비와 전체DB불변/실기기등록/전경로수집·실회사인수를구분한다. 원본게시물내용/접속제한을임의수정하지않고ready=false/미확인4·실제복원PARTIAL/PASS거부유지. 중단자원은이번생성ID/owner로확인해생성분만정리한다. work도구/비공개로그없이위표준검사/실회사절차§36으로재현한다.

## 2026-10-30 GW-READY-02 61차 — 문서 ACL·다른 회사 문서의 복원 후 허용/거부 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `22689b1`/작업트리 깨끗함 확인. 이 checkout만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- 기존 전용실행기를 GW_RESTORED_DENIAL_PROBES_V2/7조건으로 확장했다. 앞선5조건의 RestoredDenialObservation v1은 보존하고 DOCUMENT_READER/FOREIGN_SCOPE 새2조건만 RestoredObjectDenialObservation v2로 구분한다. 기존백업/checkpoint/폐쇄restore·새MFA/소유검증/실행UUID·버전/시각/소스지문 검증을 재사용하며 새수집기·임의대상·공급자연결은 없다. v1에새조건을 끼우거나 옛5조건 결과로 새7조건을 통과시키지 않는다.
- DOCUMENT_READER: 백업전 참조자읽기200·다른결재열람경로SKIPPED 합성준비 뒤 최신checkpoint의 참조자회수를 복원본 상세404/NOT_FOUND·목록/검색미노출·수정404와 객체불변으로 검사한다. 대상은회수문서라편집권회수검사가 아니며 양성수정은 별도소유초안200으로 확인한다. FOREIGN_SCOPE: 실제두번째합성회사/그소유문서·별도활성결재자를 준비하고 소유자 새MFA/읽기·수정200을 확인한다. 대상직원은 그회사에 미가입이며 타회사ID 상세/수정403/COMPANY_ACCESS_DENIED, 자기회사ID+타문서ID404/NOT_FOUND·목록/검색미노출을 검사한다. 존재하지않는 회사번호 추정으로대체하지 않는다.
- 거부전후 문서/참조자/결재단계/이력4테이블지문과 원본선택11테이블불변·접속제한0/PUBLIC CONNECT 회수를 확인한다. 허용된수정은 거부직전지문 전에 마친다. 객체불변을 인증·세션유휴시각/보안감사 처리와 혼동하지 않는다. v2는 읽기/수정정확한상태·오류코드/양성대조/목록/불변/타회사번호조합을필수로검증한다. JSON비객체/중복키·8KiB초과/지원외버전·추가관측속성/실패·skip/다른실행문맥은BLOCKED다. 자동인수등록/수동완료체크는없고 성공도unsigned합성PARTIAL·ready=false/최종4조건UNVERIFIED·실제복원PARTIAL/PASS거부유지.
- 최종검증: 관련단위1031통과27.18초(신규22, 기존사용중단경고2), 화면/정적도움말61통과6.24초. 수정Python4파일 Ruff check/format·정적DB219표2409열543FK/R1–R6 오류0. 제품프런트코드 미변경으로 이번타입/ESLint/build·실브라우저/모바일은 재실행하지 않았다. 전체CI/전체회귀·실회사/실기기10인·기존V5전체합성카탈로그 실행은 미완료/미실행이다.
- 실제PG/CLI: 새owner=gw-ready-02-phase61-test·전체ID/단일loopback 확인 컨테이너/새UUID *_test DB에서 추가2조건33.31초 통과. 최종전용CLI는 새출력파일에서7조건PASSED·관측7개(v1다섯/v2둘)·pytest종료0/sourceUnchanged/databaseCleaned=true·PARTIAL/종료0/85.28초다. 직접2+반복CLI7을 다른9건으로 합산하지 않는다. 최종원본변경후 다시CLI전체를 실행했다. 생성기본DB/폐쇄복원DB와 컨테이너/볼륨 정리, owner잔여0 확인. 기존병행/미리보기DB에는 접속/초기화하지 않았다.
- 실패/보정: 초기합성기안에 기안자자신을결재자로 지정해2건준비검사가400/VALIDATION_FAILED로실패했다. 기존기안자제외규칙에맞춰 별도활성결재자를 준비했고 제품규칙은완화하지 않았다. 불필요owner변수/F841·예외스타일TRY004를 보정했다. TRY004는 비객체JSON을 지원외버전으로거부하는 같은ValueError경계로 정리했고 중복/크기검사·정확한거부·양성대조는유지했다. 정리전7조건CLI통과뒤 최종소스에서도 전체1031/CLI7을 재검증했으며 실패출력을덮거나 미실행을통과로세지 않았다.
- 문서/범위: 실회사절차§35·수집경계·정적도움말/문서지도·구현문서/현황199줄/progress/HANDOFF갱신. 직관성(문서/회사거부구분)/유효성(실재객체·양성대조·정확한404/403)/학습성(편집권회수와참조자읽기구분)/유연성(기존계약보존·실행기확장)을반영했으며 전체UI완성은아니다. 스키마/마이그레이션·metadata/Excel/ERD·실계정/admin개명/비밀번호/OTP·키/브라우저설정 변경없음. work/.env·비밀/전체로그Git제외. 다른checkout/WMS/main/push/배포변경없음.
- 다음: 게시물 공개범위의 복원후 실제허용/거부 고정검사를 같은 제한실행기에 연결한다. 문서전체생명주기/다중참조·전결/위임·채팅/일정·직접SQL/운영도구/SSO·전경로무누락/독립최신성·외부공급자/장애복구·실API브라우저/최신main/전체회귀·실회사10인/최종전환은 남는다. 난이도높음, GPT-6 Astra + High 추천(공개범위·회수/격리·최신원본 정합), 모델자동변경없음. 사용자확인전 다음단계 자동착수하지 않는다.

재현(이 GW 저장소 루트; 비밀값은 환경주입하고 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1031은 아래60차1009의 같은35파일에 새단위22건이 추가된 결과다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_object_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_object_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 컨테이너 fullID/owner/running·단일loopback/TCP준비 확인.
# FS_GW_ROUTE_VERIFY_ADMIN_URL은 해당컨테이너 postgres관리연결, GW_BACKUP_TEST_CONTAINER는전체ID,
# FS_GW_ROUTE_VERIFY_OWNER는실제owner라벨을 비공개주입. 새0700폴더/새출력파일 사용.
# 실행기가 새UUID *_test DB를 생성/마이그레이션/검사/정리한다. 기존DB초기화없음.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-61.json
# 추가2조건만 직접재현: 소유검증한 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL주입 후:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_object_db.py -q --tb=short
```
전용V2전체는 기존v1다섯+새v2둘=7조건이다. 직접2/CLI반복을 다른시나리오로 합산하지 않는다. 소유초안 양성수정과 수정불가 참조자회수문서의 편집권회수는 구분한다. 실재두번째합성회사에서도 검사대상직원에게 그회사멤버십을 주지 않는다. 선택11테이블비교/내부ASGI/합성MFA준비이며 전체DB불변·실기기등록·전체권한인수증거가 아니다. 중단자원은이번생성ID/owner로확인하고 생성분만 정리한다. 이전실패/옛정책·키회수/원본유실을 과거통과로 대신하지 않고 ready=false/미확인4·실제복원PARTIAL/PASS거부 유지. work도구/비공개로그없이 위표준검사/실회사절차§35로 재현한다.

## 2026-10-30 GW-READY-02 60차 — 격리 복원본 새 인증·권한 거부 공통 계약/제한 실행 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `a15aa7f`/작업트리 깨끗함을 확인했다. 이 checkout만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- `RestoredDenialObservation` v1과 기존 `gw_route_verify.py --restored-denial-only`/GW_RESTORED_DENIAL_PROBES_V1을 추가했다. 새 소유 UUID *_test DB에서 기존 실제dump/암호화백업·checkpoint·격리restore를 재사용하고 계정회수 새로그인401/INVALID_CREDENTIALS, 새MFA 뒤 회사멤버십/GW연결·역할/HR권한403의 고정5조건을 확인한다. 관리자 새MFA/현재세션·감사조회 양성대조와 직원 새MFA/현재세션·필요GW me를 따로 요구한다. 임의401/403·인증실패·서버오류를 회수 성공으로 세지 않는다. MFA factor/회수 상태는 합성SQL 시험 준비여서 등록/실기기·회수 명령 수집 검증은 아니다.
- 전용모드는 full64자리 컨테이너ID/owner/running·단일loopback 매핑을 검증한다. 임의회사/계정/URL/경로·기존DB를 실행 대상으로 받지 않는다. 실제 이번 실행의 정확한 pytest이름/클래스·5개전체·단일속성·UUID/코드/DB/시각·기대상태/코드·격리/양성대조/선택원본불변을 확인한다. 누락/중복·skip/실패·옛문맥·변조·실행중소스변경은BLOCKED다. 관측은 unsigned합성결과이며 기존 인수에 자동수입/등록하지 않는다. 성공도PARTIAL/ready=false·전체회수/완전성/실회사인수=false, 마지막4조건UNVERIFIED·실제복원PARTIAL 유지.
- 원본불변 비교는 계정/세션/MFA/회사멤버십/GW연결·역할/HR계정 선택7개테이블 지문이다. 전체업무DB 불변이나 외부독립 원본보관 증명이 아니다. 닫힌 대상은 datconnlimit0/PUBLIC CONNECT 회수 유지, 소유시험superuser의 내부ASGI만 사용하며 직원 접속을 개방하지 않았다. 실제회사의 계정/admin·암호·OTP·키를 바꾸지 않는다.
- 최종검증: 관련 단위1009통과27.46초(신규38, 기존 사용중단경고2); 집중58통과0.67초는 중복 합산하지 않는다. 화면/정적도움말61통과5.30초. 수정Python4파일 Ruff check/format·정적DB219표2409열543FK/R1–R6 오류0. 프런트제품코드 미변경으로 이번타입/ESLint/build·실브라우저/모바일은 재실행하지 않았다. 전체CI/전체회귀·실회사10인/실기기 인수는 아니다.
- 실제PG/실CLI: 새 owner=gw-ready-02-phase60-test·전체ID/loopback 확인 컨테이너와 새UUID시험DB에서 직접5조건76.50초 통과 후 CLI통합을 확인했다. 최종 전용CLI는 pytest종료0/5조건PASSED·관측5개·sourceUnchanged/databaseCleaned=true·PARTIAL/종료0, 전체81.72초다. 직접5+CLI반복을 다른10건으로 합산하지 않는다. 각새MFA/HTTP거부·양성대조/원본선택지문·폐쇄유지와 정리를 확인했다. 기존V5 전체카탈로그 실행은 이번 재실행하지 않았다.
- 실패/보정: 새실행기 import정렬I001을 보정했다. 초기직접검사 뒤 계약작성 중 내부오류AUTHENTICATION_FAILED를 기대해 전용CLI2회에서 CORE_ACCOUNT1실패/나머지4통과·BLOCKED였다. 비공개진단에서 실제router가 외부401/INVALID_CREDENTIALS로 변환함을 확인해 계약만 HTTP코드로 보정했다. 인증/인수 차단·기대401/403/양성대조는 완화하지 않았다. 실패출력은 덮거나 과거통과로 대신하지 않았고 새번호/새소유DB/새파일의 최종CLI5조건과 전체1009를 재검증했다. 미통과 실행을 완료로 세지 않는다.
- 문서/자원: 실회사절차§34/보안수집경계·정적도움말/구현문서·현황199줄/progress/HANDOFF 갱신. 직관성(고정조건/전용모드)/유효성(새인증·양성대조·정확한오류코드)/학습성(제한범위/남은ACL)/유연성(기존도구재사용)을 반영했으며 전체UI완성은 아니다. 이번생성컨테이너/볼륨/기본DB·폐쇄복원DB를 정리했고 owner잔여0을 확인했다. 기존미리보기/병행DB 접속·초기화/다른checkout/WMS/main/push/배포 변경없음. 스키마/마이그레이션·metadata/Excel/ERD 변경없음. work/.env·비밀/전체로그 Git제외.
- 다음: 문서별ACL과 다른회사범위의 복원후 실제허용/거부 고정검사를 같은 실행계약으로 확장한다. 문서/게시/결재위임·채팅/일정/직접SQL/운영도구/SSO·전경로무누락/독립최신성·외부공급자/장애복구·실API브라우저/최신main/전체회귀·실회사10인/최종전환은 남는다. 다음 난이도높음, GPT-6 Astra + High 추천(객체ACL/회사격리·인증상태 정합), 자동모델변경 없음. 사용자확인 전 다음단계 자동착수하지 않는다.

재현(이 GW 저장소 루트; 비밀은 환경 주입하고 값을 출력하지 않는다):
```sh
uv run --project backend pytest backend/tests/test_gw_restored_denial.py backend/tests/test_gw_route_verify.py -q --tb=short
# 관련1009 전체는 아래59차971 목록에 test_gw_restored_denial.py를 추가한35파일이다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_denial_db.py
uv run --project backend ruff format --check backend/src/fs/gw/restored_denial.py tools/gw_route_verify.py backend/tests/test_gw_restored_denial.py backend/tests/test_gw_restored_denial_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 새소유 postgres:18 컨테이너 fullID/owner/단일loopback/TCP준비를 확인한다.
# FS_GW_ROUTE_VERIFY_ADMIN_URL은 그 컨테이너의 postgres관리연결만, GW_BACKUP_TEST_CONTAINER는fullID,
# FS_GW_ROUTE_VERIFY_OWNER는실제owner라벨. 값을stdout/문서에적지않는다.
# 새0700폴더 안의 새출력파일로 실행한다. 실행기가 자체UUID *_test DB를 생성/마이그레이션/정리한다.
uv run --project backend python tools/gw_route_verify.py --restored-denial-only --report work/acceptance/restored-denial-60.json
# 직접pytest재현은 위와같이 소유검증한 새UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL을 주입하고:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restored_denial_db.py -q --tb=short
```
CLI 성공도unsigned합성PARTIAL이며 기존실복원PARTIAL/ready=false·최종4조건미확인/ACCEPTANCE PASS거부 유지.5조건을 반복한 결과를 다른시나리오 건수로 합산하지 않는다. 직접SQL시험준비/내부ASGI·선택7테이블비교와 실MFA등록/실기기·운영회수명령수집·전경로/전체업무DB불변을 구분한다. 중단자원은 생성ID/owner를 재확인해 이번생성분만 정리한다. 원본서명파일/합성관측의지문만으로 독립보관/최종인수를 인정하지 않는다. work harness/비공개로그 없이 표준검사/운영절차§34로 재현한다.

## 2026-10-30 GW-READY-02 59차 — 동일 읽기 스냅샷 실행 보고·권한 거부 미연결 대조 완료

- 작업 위치 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `9308a92`, 작업 트리 깨끗함 확인. 이 checkout만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- 기존 사전점검 CLI `--execution-report` 선택 옵션과 `acceptance_report.collect` 추가. 같은 REPEATABLE READ·READ ONLY 거래에서 기존10인 구성/현재 기준을 읽고58차 어댑터의 최신 원본 검증·12조건을 연결한다. 모든 결과/정책/버전 중 최신 등록부터 선택하고 기존 수집·관측·목록/신뢰 복구 검증을 재사용한다. unsigned GW_ACCEPTANCE_EXECUTION_REPORT v1이며 서명 ACCEPTANCE 등록 대상/운영 승인이 아니다. 기본 옵션·출력/새0600 파일·덮어쓰기 금지는 유지한다. 사전점검 차단과12조건 차단을 분리하며 신뢰 오류를 사전점검 전용 결과로 자동 후퇴시키지 않는다.
- 권한 거부8영역의 SELECTED_REVOCATION_BOUNDARIES/기존 시험 참조·확인 범위/남은 미연결을 추가했다. 인증 함수401·원본HTTP 거부·제한 상태/replay·격리를 복원본 새 인증 후 업무 권한 거부와 구분한다. 보고서가 시험을 실행한 것처럼 표시하지 않는다. 모든 검토 행 NOT_EXECUTED·coverageComplete/revocationsComplete=false, 마지막4조건 UNVERIFIED·ready=false·실제복원PARTIAL/ACCEPTANCE PASS 거부 유지. 전체 쓰기/권한 전수 목록이 아니며 직접SQL·게시 대상/위임·채팅/일정·향후SSO/독립 최신 기준은 별도다.
- 직관성(동일시점 구성/원본)/유효성(최신원본/별도 사전점검 차단)/학습성(기존검사·미연결 구분)/유연성(기존 CLI 선택옵션)을 반영했다. 운영 준비 기존 자동/실환경 안내 카탈로그·정적 도움말과 실회사 절차§33/수집경계를 연결했다. UI 제품 코드/새 버튼/전체 UI 완성은 이번 범위가 아니다.
- 검증: 관련 단위971통과24.04초(신규11/기존 사용중단 경고2), 사전점검 독립 차단·PARTIAL 최대값 시험을 보강한 최종 신규11통과0.11초(971과 중복 합산 안 함). 화면/정적 도움말61통과5.33초. 수정 Python5파일 Ruff check/format·정적DB219표2409열543FK·R1–R6 오류0. 프런트 제품 코드 미변경으로 이번 타입/ESLint/build·실브라우저/모바일 재실행은 하지 않았다. 전체CI/전체회귀 통과로 표현하지 않는다.
- 실제PG: Docker는 다시 응답했으나 기존 GW전용 컨테이너는 없었다. postgres:18 로컬 이미지로 새 UUID 이름/owner=gw-ready-02-phase59-test·loopback 임의포트 컨테이너만 생성하고 정확한ID/라벨/loopback 확인 뒤 새 UUID *_test DB에 마이그레이션했다. 보고서2+기존운영API3+기존실제dump/격리복원2=7통과63.22초. 추가 연결된서명PARTIAL 보고서1통과7.64초(서로 다른 검사, 총8). 기본admin 부재/합성연결2명·엄격10인차단, 같은스냅샷·문맥지문/READ ONLY 쓰기거부SQLSTATE25006, 조회전후 계정/세션/MFA/설정/원본상태 불변, 최신FAIL/원본유실과 연결된PARTIAL 재검증을 확인했다. 이는 실제회사10인 인수나 새 인증 후 전체업무권한 거부 검사가 아니다.
- 실패/보정: 추가PG 검사 준비에서 pg_isready가 PostgreSQL 초기화 중 임시socket 서버를 준비완료로 관측해 createdb가 실패했다. 해당 생성 컨테이너/볼륨만 정리했고 테스트는 실행되지 않았다. TCP127.0.0.1 준비검사로 고쳐 새 소유 자원에서 마이그레이션/추가1건을 통과했다. 제품의 시각·신뢰·인수차단/검사 조건은 완화하지 않았다.
- 자원/범위: 생성한 모든 시험 컨테이너/볼륨/DB는 정리했다. 기존 병행컨테이너 factory-studio-db-1/55432는 목록만 읽고 접속/변경하지 않았다. 기존 미리보기DB·실계정/admin 개명·비밀번호/OTP·키/브라우저 설정 변경 없음. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. work/.env·비밀/전체로그 Git 제외. 현황199줄·구현문서/운영절차/도움말/progress/HANDOFF 갱신. 다른checkout/WMS/main/push/배포 변경 없음.
- 다음: 복원본에서 새 인증 후 권한 거부를 확인하는 공통 검사 계약/제한 실행기를 진행한다. 제한된 합성 대상/허용 경로와 실제 전체회수·실환경 인수의 경계를 유지한다. 이후 전경로/독립 최신기준·외부공급자/장애복구·실API 브라우저/최신main/전체회귀·실회사/실기기10인/최종 전환이 남는다. 난이도 높음, GPT-6 Astra + High 추천(인증/격리·권한회수 정합), 모델 자동 변경 없음. 사용자 확인 전 다음 단계를 시작하지 않는다.

재현(이 저장소 루트; 비밀값은 출력하지 않고 환경으로 주입):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 관련971 전체는 아래58차 관련960 목록에 test_gw_acceptance_report.py를 추가한34파일이다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
uv run --project backend ruff check backend/src/fs/gw/acceptance_report.py backend/src/fs/gw/acceptance_contract.py tools/gw_acceptance_preflight.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_report_db.py
uv run --project backend ruff format --check backend/src/fs/gw/acceptance_report.py backend/src/fs/gw/acceptance_contract.py tools/gw_acceptance_preflight.py backend/tests/test_gw_acceptance_report.py backend/tests/test_gw_acceptance_report_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
# 실제PG: 새 소유postgres:18 컨테이너의 ID/owner/loopback을 먼저 확인한다.
# pg_isready는 -h 127.0.0.1로 TCP준비를 확인해 초기화 임시socket을 제외한다.
# 새 UUID *_test DB를 만들고 DATABASE_URL/TEST_DATABASE_URL과 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test/병행 DB는 절대 초기화/시험 대상으로 쓰지 않는다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_acceptance_report_db.py backend/tests/test_gw_operations.py backend/tests/test_backup_journal_restore.py -q --tb=short
# 종료 후 생성DB/컨테이너/볼륨만 ID/owner를 재확인하여 정리한다.
```
위 PG8건은 첫 실행7건과 추가 연결 시험1건의 서로 다른 시나리오다. 최신 전체8건 단일 실행 시간으로 표현하지 않는다. work harness/비공개로그에만 의존하지 않고 위 표준 검사 파일과 운영절차§33으로 재현한다. 실제 외부 공급자 미정/독립 최신성·전체 권한거부/10인 인수·최종PASS 미완료, 제한 복원본 접속을 열거나 운영계정을 바꾸지 않는다.

## 2026-10-30 GW-READY-02 58차 — 자동 검증/실환경 인수 공통 계약·기존 검증 실행 어댑터 완료

- 저장소 `/Users/hwang-kyoungho/projects/factory-studio-gw-company`, 브랜치 `codex/gw-company-01`, 시작 `dfadc0b`, 작업 트리 깨끗함을 확인했다. 이 checkout만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- `acceptance_contract` v1: 운영12조건 각각의 mode/executionState/기존 도구/자동 확인 범위/남은 근거/선행 조건을 정의했다. 마지막4조건은 LIVE_ENVIRONMENT/NOT_EXECUTED/UNVERIFIED, 전체 실행 경계 BLOCKED/PARTIAL·passSupported/liveCompanyAcceptance/releaseAuthorized=false다. 인수 완료 상태를 붙이려 하면 거부한다. 새 ACCEPTANCE PASS·서명 형식/수동 완료 체크·외부 공급자 연결은 만들지 않았다.
- `acceptance_execution.execute`: 현재 회사 거래의 범위·정책·시각·버전·키로 종류별 최신 등록부터 선택하고 기존 collect_registered/readiness.assess를 호출한다. 같은 시각은 id로 결정하며 정렬/입력 순서에 영향받지 않는다. 최신 실패/PARTIAL·원본 없음/변조·옛 정책/제품·키 회수를 과거 성공으로 대신하지 않고 다른 회사/세대를 거부한다. 기존 연결 관측/신뢰 복구/원본 대조를 그대로 재사용했다. 새 쿼리/스키마/수집기·복원 실행 없음.
- 기존 운영 준비12조건에 접힌 자동 확인·실환경 인수 구분과 정적 도움말을 연결했다. GET에서 실환경 도구를 실행하지 않는다고 명시하고 최소 예정 수 검사와 정확히1부서·10인/관리자1+직원9 사전점검을 구분했다. 현재 회사/역할·업무 복귀와 기존 근거 목록은 유지한다. 직관성(범위 구분)/유효성(최신 원본)/학습성(남은 근거)/유연성(기존 도구 재사용)을 반영했으며 전체 UI 완성은 아니다.
- 실제 검증: 관련 단위960통과22.26초(신규20, 기존 사용중단 경고2). 화면/정적 도움말61통과4.97초, 최종 계약/게이트34통과0.06초(960과 중복 합산 안 함). 타입/수정ESLint·Prettier와 Ruff check/format 통과. 정적DB219표2409열543FK·R1–R6 오류0. 초기 프런트 포맷 명령의 상대경로가 맞지 않아 파일 없음 종료2였고 저장소 기준 경로로 보정해 최종 검사를 통과했다. 제품 실패를 숨기거나 검사 조건을 완화하지 않았다.
- 실행 환경 재확인: Docker API 소켓이 존재하지 않고 API8362/웹5362 LISTEN도 없다. 이전 PID/컨테이너 상태를 재사용하지 않았다. 임의 daemon/서버 재기동 없이 이번 실제PG·브라우저/모바일 재검증을 미실행으로 기록한다. 시험DB/컨테이너 생성·접속/초기화·계정/비밀번호/OTP·키/브라우저 설정 변경 없음. 실제API 로그인 후 전체 흐름·전체CI/회귀·실회사/기기10인·최종 전환은 미완료다.
- 현황199줄/구현문서·실회사 절차§32/보안 수집 경계·도움말/progress/HANDOFF 갱신. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. work/.env·비밀을 Git에서 제외한다. 다른checkout/WMS/main/원격push/배포 변경 없음. 실제 복원PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지.
- 다음: 기존10인 사전점검과 최신 원본의 공통 계약 실행 보고를 읽기 전용으로 연결하고 전체 권한 거부의 누락을 대조한다. 공급자 선정 전 독립성/전체 회수/실회사 인수를 확인한 것으로 올리지 않는다. 이후 공급자 선정·독립 최신 기준/외부 장애복구·전경로 무누락/전체 회수·실API 브라우저/최신main/전체회귀·실회사10인/최종전환이 남는다. 다음 단계 난이도 높음, GPT-6 Astra + High 추천(계약/회수 정합 판단, 자동 모델 변경 없음). 이번58차 뒤 자동으로 다음 단계를 시작하지 않는다.

재현(저장소 루트, 비밀정보 없이):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_execution.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 관련960 전체는 아래57차/56차의940 목록에 test_gw_acceptance_execution.py를 추가한33파일이다.
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
PATH=/opt/homebrew/opt/node@24/bin:$PATH frontend/node_modules/.bin/eslint frontend/src/gw/Operations.tsx frontend/src/gw/operations.test.tsx
PATH=/opt/homebrew/opt/node@24/bin:$PATH frontend/node_modules/.bin/prettier --check frontend/src/gw/Operations.tsx frontend/src/gw/operations.test.tsx
uv run --project backend ruff check backend/src/fs/gw/acceptance_contract.py backend/src/fs/gw/acceptance_execution.py backend/src/fs/gw/launch_gate.py backend/src/fs/gw/operations.py backend/tests/test_gw_acceptance_execution.py
uv run --project backend ruff format --check backend/src/fs/gw/acceptance_contract.py backend/src/fs/gw/acceptance_execution.py backend/src/fs/gw/launch_gate.py backend/src/fs/gw/operations.py backend/tests/test_gw_acceptance_execution.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
PG 재검증은 환경 복귀 후 아래57차의 소유ID/owner/loopback 확인과 새 UUID *_test DB 한정 절차를 따른다. 기존 gw_preview_test는 초기화하지 않는다.

## 2026-10-25 GW-READY-02 57차 — 운영 준비 차단 안내·담당자별 조치와 모바일 보완 완료

- 시작 `7a7309f`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 기존 승인 GW 범위의57차 UI/API 안내 하나를 진행했다. 최종 커밋은 `git log -1`로 확인한다. 이 checkout만 수정했다.
- 신뢰 검증 설정·키 수명/이관·보존 설정 누락/원본 읽기·대조/현재 설정 불일치·기준점 반영/수신 진행의7개 허용 진단 코드를 추가했다. 기존 ValueError 차단/일반 예외 메시지를 유지하며 API는 고정 문구/담당자/다음 조치만 반환한다. 경로·키·원본 예외 전문은 노출하지 않는다. 코드가 모르는 값이면 일반 안내로 처리하고 회사 SECURITY_ADMIN/AUDITOR만 진단을 조회한다. 직원 응답에는 서버 진단이 없다. 현재 검사 실패를 과거 성공으로 대신하지 않는다.
- 기존 GwLayout의 현재 회사·역할/연결1명·예정10명과 업무 복귀를 유지하고 최근 실행 요약→담당자별 다음 조치→펼치는12조건/기존 실행 기록을 연결했다. 서버 담당자/회사 보안 관리자/직원 본인의 행동과 정적 도움말을 구분한다. GET 재점검은 백업/복구·설정을 실행하지 않으며 완료 후 버튼 초점을 복원한다. 기준/보관 검토/선택 증거 파일·긴급 문서 입력 중에는 잠근다. 조회 실패 시 이전 결과를 숨기고 현재 회사/오류·재시도/업무 복귀를 표시한다. 작은 안내를 전체 UI 완성으로 표현하지 않는다.
- 검증: 관련 단위940통과24.01초(신규19/기존 경고2). 화면/정적 도움말61통과5.20초(기존48+관련 기존/새13), 타입/수정ESLint·Prettier/Ruff check·format/정적DB219표2409열543FK·R1–R6 오류0. 실제PG는 소유 컨테이너ID/owner/loopback 검증 후 새 UUID *_test DB에만 마이그레이션/검사해12통과208.67초(기존 실제 백업/폐쇄 복원 흐름9+운영API3).7종 진단 응답/관리자·감사·직원 범위와 구성 오류 해소 뒤 최신 INVALID/FAIL·후속 PARTIAL 유지를 확인했다. 새 진단 API 역할 검사는 시험 설정 실패를 주입했고 파일 단계 분류는 실제 합성 파일 단위 검사로 확인했다. 전체CI/전체회귀 통과로 표시하지 않는다.
- 브라우저: 실제5362 세션 만료/로그인 입력란 펼침을 확인했다. 로그인 후 실제API 전체 화면은 미검증이다. 별도 읽기 전용 합성 API+제품 자산5365에서1440×1000/390×844, 담당자 안내/12조건 Enter 펼침·재점검 초점/기준 편집 잠금·취소/감사 조회 전용/회사 유지 업무 복귀/정적 도움말 절을 확인했다. clientWidth=scrollWidth 데스크톱1425·모바일375, 가로 넘침 없음. 합성 배너/연결1명·예정10명으로 표시했다. 근거는 `outputs/gw-readiness-02-phase57/`이며 실제 실회사/실기기10인 인수가 아니다. 임시 viewport 초기화/생성 합성 탭·서버5365 정리. 사용자 로그인용 실제 탭은 유지했다.
- 사용자 로그인 문의: 비밀번호가 바뀐 것으로 추정하지 않고 별도 미리보기DB를 읽기 확인했다. admin 계정은 없고 기존 저장된 합성 로그인은 admin과 다르며 저장 정보가 DB와 일치했다. 이번 계정 생성/개명·비밀번호/OTP/키/브라우저 설정·미리보기 정책·DB 초기화는 없다. 개발자 관리자 로그인 ID admin 통일 기준과 회사 연결/SECURITY_ADMIN·AUDITOR/서버 OS·서명 권한을 구분한다. 비공개 접속 자료의 값은 출력/Git에 싣지 않았다.
- 실패 보정: 새 시험 코드의 루프 변수 바인딩/정렬 린트2건을 보정해 최종 수정 린트를 통과했다. 도움말의 지연 렌더링 후 절 이동을 GW 문서에 한정해 보정했다. 연결 교체 중 JSX 닫힘/새 시험의 잘못된 exact 옵션으로 변환1/타입1 오류를 탐지·수정한 뒤 최종61·타입을 재검사했다. 브라우저 상세 summary의 DOM 역할 선택을 실제 보이는 텍스트로 고쳐 Enter 펼침을 확인했다. 제품 동작·시각/회수/원본·인수 차단을 완화하지 않았다. 검사 누락이나 테스트 실패를 통과로 간주하지 않았다.
- 문서/사용성: 실회사 절차 §31·구현/보안 수집 경계/도움말/README/현황/progress/HANDOFF 갱신. 직관성(상단 원인/담당자), 유효성(허용된 진단/현재 재조회·이전 성공 대체 금지), 학습성(담당자별 행동/도움말·조건 펼침), 유연성(감사 조회/회사 동선/390px)을 반영했다. DB 스키마/마이그레이션·metadata/Excel/ERD 변경 없다.
- 자원/제약: 생성 시험DB/폐쇄 복원DB만 정리했다. 기존 gw_preview_test 보존. API8362 PID20713/Vite5362 PID20714 LISTEN을 읽기 확인했고 재시작/서버 신뢰 설치는 하지 않았다. work/.env·비밀/전체로그 Git 제외. 다른 checkout/WMS/main/원격push/배포 변경 없음. 실제 복원 PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 실제 외부 공급자 미정/독립 최신 기준·전체 수집/회수·실회사10인·최종 전환/최신main 통합·전체CI/회귀는 미완료.
- 다음: **최종 인수 PASS 계약의 남은 근거를 기존 도구/12조건과 대조하고 자동 검증 가능한 조건·실환경 전용 조건을 분리하는 공통 계약/실행 어댑터**부터 진행한다. 옛 정책/버전·최신 실패/PARTIAL·원본 유실/변조·회수 상태를 과거 성공으로 대체하지 않고 최종PASS는 근거가 갖춰지기 전 열지 않는다. 이후 공급자 선정/외부 독립 인수·실제API 로그인 후 화면/최신main/전체회귀·실회사10인·최종 전환이 남는다. 난이도 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천. OpenAI Docs 공식 모델 페이지의 복잡한 추론/코딩·High 지원을 확인했으며 이 계약/권한 회수 정합 난이도에 따른 판단이다. 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 전체 관련940 목록은 직전56차 기록의921 명령에 test_gw_trust_configuration.py를 추가한다.
# 소유 컨테이너 ID/owner/loopback 확인 후 새 UUID *_test DB에만 DATABASE_URL/TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. fixture가 만든 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py backend/tests/test_gw_operations.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/gw/emergency-kit.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/trust_configuration.py backend/src/fs/gw/evidence_trust.py backend/src/fs/gw/catalog_trust_store.py backend/src/fs/gw/operations.py backend/src/fs/gw/operating_evidence.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_operations.py
uv run --project backend ruff format --check backend/src/fs/gw/trust_configuration.py backend/src/fs/gw/evidence_trust.py backend/src/fs/gw/catalog_trust_store.py backend/src/fs/gw/operations.py backend/src/fs/gw/operating_evidence.py backend/tests/test_gw_trust_configuration.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_operations.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
상세 운영 절차는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §29–31, 도움말은 `content/help/gw/operations.md`를 따른다. 비공개 work harness/자격 증명에만 의존하지 않고 표준 시험 명령·화면 근거로 재현한다. 실제 계정·미리보기DB/다른 checkout/WMS를 변경하지 않는다.

## 2026-10-25 GW-READY-02 56차 — 신뢰 이력 내보내기·별도 최신 지문으로 원본 복구 완료

- 시작 `08d529f`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 승인된 기존 GW 범위에서 신뢰 원본 전달/복구 하나를 진행했다. 최종 커밋은 `git log -1`로 확인한다. 이 checkout만 수정했고 새 GW/업무 DB 스키마·수동 인수 완료 체크는 없다.
- `catalog_trust_transfer`/`gw_catalog_trust_transfer.py export/receive`: 별도 확인한 최신 ledgerId/revision/digest와 manifestDigest를 고정한다. CATALOG_TRUST_EXPORT v1은 각 연속 원본의 version/revision/전체 지문/실제 크기와 anchor를 묶으며 파일명은 고정 규칙으로 계산한다. 모든 실제 바이트/엄격 형식·연속 버전/원장·직전 지문/단조 키 상태·승인 연결을 다시 검사한다. 일관되게 새 해시를 계산해도 회수 복원/은퇴 후퇴·분기는 거부한다. 패키지의 키·경로/자기 지문을 현재 권한으로 자동 신뢰하지 않는다. 기존 신뢰 원본/목록·복구/이관 서명 형식과 업무 스키마는 유지한다.
- export는 확인한 현재 원장 전체/현재 기준점과 일치해야 하며 원래 바이트를 새 빈0700 출력에0600 새 파일로 보존하고 재대조 후에만 manifest를 쓴다. 개인키·현재 정상 승인 환경 없이 보존된 회수 상태도 내보낸다. trust status 출력에 ledgerId를 더했다. 중단 패키지는 새 빈 출력에서 다시 만들며 원본/패키지를 덮어쓰지 않는다.
- receive는 기존 폴더를 잠가 모든 남은 원본/현재·보류 기준점/이전 영수증의 실제 지문을 고정한 뒤 기존 폴더를 그대로 보존하고 **새 빈 복구 폴더**만 구성한다. 더 최신 버전/회수·다른 원장/같은 버전의 다른 지문/중복·알 수 없는 기준점 버전을 과거 패키지로 대신하지 않는다. 원본 유실/0바이트·잘림/바이트 손상은 확인된 같은 버전/지문 이름과 별도 최신 전체 이력으로만 재구성한다. 기존 폴더가 없는 새 환경은 명시 new-host가 필요하며 기존 더 최신 상태를 회피하는 용도가 아니다.
- 입력 해석 전 새 폴더에 고정 원장/최신·manifest 지문/기존 폴더·전체 바이트 지문을 수신 보류로 보존한다. 모든 새 파일/fsync·저장 원본/전이 전체·기존 원본 불변을 재대조한 뒤 복구 영수증→보류 현재 기준점/fsync→원자 교체/fsync→수신 보류 제거/fsync 순서로 활성화한다. 일반 조회/기존 resume은 수신 중 차단하며 영수증의 최소 원장/원본은 이후에도 대조한다. 새 폴더에 이미 더 최신/다른 현재 기준점이 있으면 덮지 않는다.
- 같은 원본/계획/기존 폴더 상태의 명시 receive --resume만 허용한다. 완성 파일만 정확한 같은 바이트로 재사용하고 잘린 기록/영수증·보류 기준점은 자동 삭제/덮어쓰기하지 않는다. 실패 폴더와 기존 손상 폴더를 보존하고 여전히 최신임을 별도 확인한 같은 기준으로 새 폴더를 준비해야 한다. 완료 응답 유실은 저장 원본/영수증으로 확인하되 원장이 더 전진했으면 과거 완료를 현재 결과로 반환하지 않는다. 서버 사용 경로/환경·공개키/회사 목적·수명 상태·승인 원본을 자동 설치하지 않는다. admin 이름도 OS/회사·서명 권한을 대신하지 않는다.
- 한도/신뢰 경계: 원본4096개/각256KiB·manifest2MiB와 기존 상태/승인 한도 중 먼저 도달한 제한이다. 파일 단위 처리이며 최대 약1GiB/최대 파일·장기 성능은 미검증이다. 신뢰 상태 원본 패키지이며 과거 손상/복구 진단 폴더 전체의 보관 사본은 아니므로 그 폴더는 별도 보존한다. 같은 OS 계정의 합성 폴더/별도 기준을 가정한 시험이며 실제 외부 공급자·독립 최신 지문/자동 갱신·계정/장애 영역/WORM/공인 시각·전체 무누락/모든 복제본 유실을 검증한 것이 아니다. 새 수신/영수증을 읽으려면56차 검증기가 필요하고 이전 환경은 구성 차단되며 도구가 바이너리를 자동 갱신하지 않는다.
- 검증: 최종 관련 단위921통과(기존 경고2, 신규57). 기존/새 환경·유실/빈/잘린/변조 원본·현재/보류 기준점, 최신 회수 보존/옛 설정/더 최신 로컬 원본·현재 기준점/다른 원장/분기·중복·미래 형식·파일 누락/추가/경로/크기/엄격 JSON·일관 재해시 회수 복원 거부를 검사했다. 기록/영수증/현재 기준점/보류 해제 전후 중단·완성 재개/부분 파일 보존·바뀐 계획/기존 원본·완료 뒤 전진/영수증 변조, 실제 개인키 없는 export/receive CLI·두 프로세스의 단일 최초 활성화를 확인했다. 화면/정적 도움말48통과·타입·수정 Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. 제품 UI 코드/브라우저·모바일/실제 API 브라우저는 이번 재검증하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원→발행 중단/서명 복구 PARTIAL/ACCEPTANCE FAIL→두 차례 키 교체·시험 옛 개인키 파일 제거/분할 전달·기존 실패 원본/새 대조/폐쇄 복원/후속 PARTIAL을 유지했다. 현재 신뢰 원장 CLI export→시험 원본8바이트 손상/API CONFIG_REQUIRED→기존 원본을 보존한 receive·도구 실행만으로 현재 API가 바뀌지 않음→시험 소유 경로만 수동 전환/현재 신뢰 재검증·최신 FAIL/INVALID 유지→실제 회수 CLI/옛 RETIRED advance와 더 오래된 패키지 복구 거부를 확인했다. 기존9시나리오 전체9통과175.95초, 최종 연결 변형 별도1통과29.92초(같은 시나리오로 합산하지 않음). 실제 복원은 계속 PARTIAL이다.
- 실패/보정: 검사 확장 중 미사용 변수 이름을 정리하다 기준 지문 초기값까지 바뀐 시험7실패/50통과를 탐지했고 해당 시험 변수를 바로잡아 신규57/관련921을 최종 재실행했다. 전체PG9통과 뒤 연결 변형 재확인에서 복구 직후 API의 STALE와 기대 INVALID 차이로1실패28.44초가 있었다. 기존 시험과 같은30초 미만 DB 실행 완료 시각 대기를 새 복구 직후 검사에도 적용하고 상세 사유를 확인하도록 보강해 최종1통과29.92초를 확인했다. 제품의 미래 시각·신선도/회수·원본/인수 차단 조건은 완화하지 않았다.
- 문서/사용성: 실회사 절차 §30·구현/보안 수집 경계/정적 도움말·README/현황/progress/HANDOFF를 갱신했다. 직관성(신뢰 원본 복구와 운영 준비 분리), 유효성(독립 확인 기준·모든 원본/기존 최신 상태·단조 전이), 학습성(손상 폴더 보존/동일 재개·사용 경로 별도 전환), 유연성(기존/명시 새 환경·개인키 없는 전달)을 고려했다. 작은 도움말 추가를 제품 UI 전체 완성이라고 표현하지 않는다.
- 자원/제약: 생성 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 gw_preview_test 보존을 읽기 확인했다. preview DB 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·서버 환경·실환경 키 변경 없음. API8362 PID20713·Vite5362 PID20714 LISTEN만 읽기 확인했으며 재시작/이번 코드의 실제 브라우저 반영 확인은 하지 않았다. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/원격push/배포 변경 없음. 실제 복원 PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사/기기/10인/최종전환·최신main 통합은 미실행/미완료.
- 다음: **운영 준비에서 신뢰 보존/복구 차단 원인을 비밀정보 없이 구분하고 현재 회사·관리 동선/담당자별 다음 조치에 연결하는 UI 보완**을 진행한다. 기존 GwLayout/업무 복귀·긴 정보/모바일 가독성과 실제 브라우저/모바일 점검을 포함하고 작은 안내를 전체 UI 완성으로 처리하지 않는다. 관리자 로그인 admin과 회사 SECURITY_ADMIN 권한을 구분한다. 이후 공급자 선정/외부 독립 인수, 최종 인수 계약·전체 변경/권한 회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 중상, [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) + High 추천(화면/API 상태 정합·반응형/실제 브라우저 검증). OpenAI Docs 공식 모델 페이지의 복잡한 코딩/컴퓨터 사용·High 지원을 확인했고 작업 난이도에 따른 판단이며 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 새 시험용 폴더/합성 설정은 검사 fixture가 준비하고 생성 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
# 최종 보강한 연결/복구 변형만 별도 재현하려면 같은 새 소유 시험DB에서 아래 선택을 사용한다.
uv run --project backend pytest 'backend/tests/test_gw_catalog_store_db.py::test_actual_checkpoint_cli_atomic_pin_fail_and_current_api[chain]' -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_trust_transfer.py backend/src/fs/gw/catalog_trust_store.py tools/gw_catalog_trust.py tools/gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_store_db.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_trust_transfer.py backend/src/fs/gw/catalog_trust_store.py tools/gw_catalog_trust.py tools/gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_trust_transfer.py backend/tests/test_gw_catalog_store_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
원본 내보내기/복구는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §30, 로컬 신뢰 설치/회수는 §29, 목록·이관/전달은 §23–28을 따른다. 비공개 work harness 없이 표준 명령/계약으로 재현할 수 있어야 한다. 실제 외부 저장소는 미정이며 담당자가 별도 최신 기준의 진위/신선도·기존 손상 폴더 보존과 실제 사용 경로 전환을 확인해야 한다. 도구가 서버 설정/회사·키 권한/실환경 키 삭제·배포를 자동 수행하지 않는다. 실계정/브라우저/다른 checkout/WMS를 변경하지 않는다.

## 2026-10-25 GW-READY-02 55차 — 목록 신뢰 상태의 로컬 영구 이력·설정 후퇴 차단 완료

- 시작 `d09674d`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 승인된 기존 GW 범위에서 회수 상태 보존/설정 후퇴 차단 하나를 진행했다. 최종 커밋은 `git log -1`로 확인한다. 이 checkout만 수정했으며 새 GW/업무 DB 스키마·수동 인수 완료 체크는 없다.
- `catalog_trust_store`/`gw_catalog_trust.py initialize/advance/revoke/status/resume`: 별도 운영자 소유0700 폴더·0600 단일 링크 원본에 CATALOG_TRUST_FLOOR v1 원장 UUID/연속 버전/직전 파일 전체 지문·회사별 키 ID/공개키 지문/ACTIVE·RETIRED·REVOKED·최초 승인부터 현재까지 정확한 지문 경로를 보존한다. 새로운 서명/인수 증거가 아니라 OS 권한으로 보호하는 로컬 상태 계약이다. 기존 목록/복구/이관/전달 원본·서명 형식과 단독 목적/회사 권한을 유지한다.
- 환경 로더에서 목록 권한/수명 상태가 있으면 FS_GW_CATALOG_TRUST_DIRECTORY/현재 이력을 필수로 요구한다. 보존 경로 항목 제거·빈 폴더/미설치·현재 설정 불일치/옛 수명 상태 항목 전체 제거·키 재활성화/ID·공개키 별칭/목적 전용, 은퇴 승인 경로의 후퇴/분기·원래 승인 추가/제거·원본 변경은 구성 오류로 차단한다. 목록 권한 삭제도 명시 은퇴/회수 상태가 있어야 한다. 현재 기준점과 보존 원본 전체의 실제 바이트/연속 버전·연결/단조 전이를 다시 검증한다. 누락·변조/옛 현재 기준점·권한/링크 오류/미완료는 CONFIG_REQUIRED/명령 차단·ready=false이며 이전 성공으로 대신하지 않는다.
- 모든 변경은 배타 잠금·현재 전체 지문 CAS다. 새 원본/fsync→보류 기준점/fsync→원자 교체/fsync 순서며 읽기는 한 호출의 로드한 신뢰 스냅샷을 사용한다. 완성 원본만 별도 확인한 정확한 새 지문과 같은 직전 기준점/이미 동일한 완료 기준점으로 명시 resume한다. 최초 완성 기록도 원본을 보존해 재개하며 재초기화하지 않는다. 잘린/없는 원본·보류 기준점은 삭제/재생성하지 않는다.
- 명시 revoke는 현재 연결/개인키 없이 이미 보존한 회사/키 공개 지문으로 먼저 회수를 남긴다. 그 직후 과거 유효한 설정/승인도 차단되고 과거 정상 은퇴로 advance할 수 없다. 중간 키 회수로 다른 연결이 깨져도 먼저 보존/완성 중단 재개가 가능하다. REVOKED→RETIRED/ACTIVE·원장 삭제/리셋 도구는 없다. 환경만 수정하고 영구 기록을 생략하면 회수 절차가 끝난 것이 아니다. 정상 변경은 새 활성 키 추가→advance→기존 이관/새 키 refresh→정확한 은퇴/연결 설정→advance다. 최초 설치/변경 전 유지보수/별도 확인이 필요하며 운영 환경을 자동 설치/재시작하지 않는다.
- 한도: 최대4096기록/각256KiB·2100회사-키와 기존 설정/승인 한도 중 먼저 도달한 제한이다. 최대 용량/장기 성능·압축/새 원장 전환은 미검증이다. 같은 OS 계정의 로컬 보존 어댑터이며 보존 경로를 새 원장으로 바꾸거나 원본/현재 기준점·환경을 모두 롤백하는 공격·호스트/모든 복제본 유실은 독립 탐지하지 못한다. 외부 독립 최신 지문 고정·정확한 유실 원본 복구/장애 영역·WORM/공인 시각·무누락 인수는 미완료다. 공급자는 미정이며 로컬 보호를 독립 영구 원장 인수로 표현하지 않는다.
- 검증: 관련 단위864통과(기존 경고2, 신규41). 세 차례 정상 교체·이전 유효 설정/옛 승인 차단, 회수 뒤 환경 항목 제거/빈 경로/재활성화·ID/공개키/목적 전용, 정확한 회사 회수와 다른 기존 회사 권한 유지, 원본/현재 기준점 삭제·후퇴/변조/링크/권한·엄격 형식, 초기/추가 기록·보류 기준점·원자 교체 전후 중단/정확한 재개·잘린 원본 거부, 잘못된 CAS/없는 회사·크기 제한 원본 불변, 두 실제 CLI 프로세스 경합/개인키·현재 환경 없는 회수 재개를 검사했다. 화면/정적 도움말48통과·타입·수정 Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. 제품 UI 코드/브라우저·모바일/실제 API 브라우저는 이번 재검증하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원·발행 중단/서명 복구 PARTIAL/ACCEPTANCE FAIL→두 차례 키 교체/옛 시험 개인키 파일 제거·승인 변조/분할 수신·기존 인수 INVALID/실패 뒤 새 대조·폐쇄 복원/후속 PARTIAL·이전 실패 원본 보존을 확인했다. 새 로컬 신뢰 설치/각 교체 advance를 거치고 보존 경로 항목 제거 시 API CONFIG_REQUIRED/정확한 설정 복구 시 최신 FAIL 유지, 실제 revoke CLI 후 과거 유효 설정도 CONFIG_REQUIRED·옛 RETIRED로 advance 거부를 확인했다. 최종 기존9시나리오 전체9통과178.40초(경고2). 실제 복원은 계속 PARTIAL이다.
- 실패/보정: 초기 새 중단 재개5실패/29통과는 인자 정리 후 남은 미정의 참조를 탐지해 제거했다. 최종 새41/관련864를 재실행했다. 첫 실제PG1실패/8통과172.13초는 목록 권한을 보존 기록 없이 삭제한 검사의 옛 INVALID 기대가 새 CONFIG_REQUIRED와 달랐기 때문이다. 더 이른 구성 차단을 기대하도록 수정하고 정확한 환경을 되돌리면 최신 FAILED가 유지되는 검사도 더해 전체9를 다시 통과했다. 회수/원본·PARTIAL/인수 차단 계약을 완화하지 않았다.
- 문서/사용성: 실회사 절차 §29·구현/보안 수집 경계·정적 도움말·README/현황/progress/HANDOFF를 갱신했다. 직관성(현재 보존 불일치 시 점검 보류), 유효성(모든 원본/기준점·단조 상태/연결 지문), 학습성(정상 교체/먼저 기록하는 회수·중단 재개), 유연성(기존 공개키 도구/다중 교체·회사별 회수)을 고려했다. 작은 도움말 추가를 UI 전체 완성으로 표현하지 않는다. 개발자 관리자 admin 이름은 회사/보안·OS 보존/서명 권한을 대신하지 않는다.
- 자원/제약: 생성 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 gw_preview_test 보존을 읽기 확인했다. 기존 preview DB 초기화/실계정·비밀번호/OTP·브라우저/미리보기 정책·서버 환경/실환경 키 변경 없음. 포트8362 API PID20713·5362 Vite PID20714 LISTEN만 읽기 확인했고 재시작/이번 코드의 실제 브라우저 반영 확인은 하지 않았다. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/원격push/배포 변경 없음. 실제 복원 PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사/기기/10인/최종전환·최신main 통합은 미실행/미완료.
- 다음: **신뢰 보존 이력의 내보내기·별도 확인한 최신 지문으로 수신/유실 원본을 복구하는 공통 계약·도구**를 진행한다. 공급자 미정 상태에서 오래된 원장/업로드한 자기 지문을 현재 기준으로 자동 신뢰하지 않고 회수 상태와 실패 원본을 보존해야 한다. 이후 외부 공급자 선정/독립 보존 인수, 최종 인수 계약/전체 변경·권한 회수, UI 구성 보완·최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(외부 기준점·동일 원본 복구/중단·회수 후퇴 경계). OpenAI Docs 공식 모델 페이지에서 복잡한 추론/코딩·High 지원을 확인했고 추천은 작업 난이도에 따른 판단이며 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_trust_store.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 새 시험용 신뢰 폴더/합성 설정은 검사 fixture가 준비하며 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_trust_store.py backend/src/fs/gw/catalog_key_handover.py backend/src/fs/gw/evidence_trust.py tools/gw_catalog_trust.py backend/tests/test_gw_catalog_trust_store.py backend/tests/gw_catalog_trust_helpers.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_trust_store.py backend/src/fs/gw/catalog_key_handover.py backend/src/fs/gw/evidence_trust.py tools/gw_catalog_trust.py backend/tests/test_gw_catalog_trust_store.py backend/tests/gw_catalog_trust_helpers.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
운영 설치/회수·중단 재개는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §29, 교체/목록·전달은 §23–28을 따른다. 비공개 work harness 없이 표준 명령/계약으로 재현할 수 있어야 한다. 현재 보존 이력 설치 전에는 기존 목록 환경의 API/CLI가 구성 오류로 차단되므로 실제 운영 설치는 별도 확인된 환경에서 진행한다. 도구가 서버 설정/실환경 키 생성·삭제·배포를 자동 수행하지 않는다. 실계정/브라우저·다른 checkout/WMS를 변경하지 않는다.

## 2026-10-25 GW-READY-02 54차 — 다중 목록 키 교체의 정확한 이관 연결 완료

- 시작 `478c794`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 중간 구현 WIP `c06afa2`; 최종 기록 커밋은 `git log -1`로 확인한다. 승인된 기존 GW 범위의 이관 연결 하나를 진행했다. 이 checkout만 수정했고 새 GW/DB 스키마·수동 인수 완료 체크는 없다.
- `catalog_key_chain`/기존 `gw_catalog_key_handover.py extend`: 현재 설정에 고정한 은퇴 키 승인 파일의 원래 바이트/전체 지문을 부모로 넣고 현재·다음 키가 별도 CONTINUATION 문맥/RETIRING·SUCCESSOR 역할로 서명한다. 더 오래된 개인키는 필요 없고 원래 목록/복구 지문과 허용 시각은 넓히지 않는다. 기존 한 단계 원래 자료/설정v1·목록/복구/단일·분할 전달 형식은 유지한다. 운영 신뢰 설정/키 생성·삭제/배포를 자동 수행하지 않는다.
- 모든 역할 서명·부모 지문/최초 이관/회사·세대·목록, 중복 키 ID/공개키/연결 ID·순환과 캡처 버전·번호/시각 후퇴/같은 번호의 기록 지문 변경을 거부한다. 중간 키는 현재 운영자 설정의 RETIRED/공개키가 있어야 하고 자기 원래 이관의 전체 지문·직접 다음 키·캡처 값을 별도로 교차 대조한다. 최종 키는 현재 회사의 단독 활성 발행 권한을 요구한다. 현재 회수·누락/목적 상실·옛 승인자 재생·분기를 과거 성공으로 대신하지 않는다. 현재 은퇴자 자신의 이관 자료도 전체 보존 원본/복구 지문과 정확히 같아야 하며 누락/추가·소급 자료를 거부한다.
- 실제 수신 기준점/중간 원본만 제한적으로 검증하고 현재 바깥 목록·최종 핀은 활성 키를 요구한다. 기존 보류 선기록·전체 바이트 재검증/원자 핀 교체·실패 이후 새 대조/폐쇄 복원 규칙을 유지한다. 잘못된 연결/회수는 CONFIG_REQUIRED/INVALID·ready=false이며 새 유효한 바깥 서명도 회수된 안쪽 근거/연결을 부활시키지 못한다. admin 이름/회사 권한·HEAD/백업/복원·재관측/인수 키 권한을 확장하지 않는다.
- 한도: 최초 이관 포함8연결·파일 하나2MiB/펼친 누적8MiB와 기존 설정64KiB/100회사-키·승인 전체20파일/원본 한도 중 먼저 도달한 제한이다. 8 이후 압축/새 신뢰 기준 전환·최대 파일/장기 성능은 미검증이다. 독립 영구 회수 원장/서버 설정 자체 악의적 롤백 방지는 미완료이며 REVOKED를 RETIRED로 되돌리는 복구 도구/절차는 없다. 서명은 정상 교체 진술이고 개인키 실제 삭제·공인 시각/독립 담당자·장애 영역/WORM·전체 무누락을 증명하지 않는다.
- 검증: 관련 단위823통과(기존 경고2, 신규62). 세 차례 교체의 PASS/FAIL/PARTIAL×단일/분할×신규/기존 수신12조합, 오래된 개인키 객체 제거 후 최신 개인키만 보유한 흐름과 원본/기존 실패 보존, 중간 회수·누락/자기 이관 분기·옛 부모 재생·현재 최종 키 권한 상실·순환·역할/부모/형식/범위·실제 캡처 후퇴/기록 불일치, 유효한 이중 서명에도 자기 원본 누락/추가/소급 거부, 엄격 JSON/크기·최대8 성공/9번째 원자 거부를 검사했다. 화면/정적 도움말48통과·타입·수정 Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드/브라우저·모바일·실제 API 브라우저는 이번 재실행하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원·발행 중단/복구 PARTIAL/ACCEPTANCE FAIL→첫 정상 교체→시험 생성 A 개인키 파일 제거→현재 B/C CLI issue/extend→두 번째 교체/시험 생성 B 개인키 파일 제거→연결 파일 변조 CONFIG_REQUIRED/동일 고정 원본 복구→분할 수신·최신 C/옛 안쪽 복구 대조/기존 인수 INVALID·새 FAIL→실패 후 새 권한 대조·새 폐쇄 복원/후속 인수 PARTIAL·실패 원본 보존을 확인했다. 중간 B 회수 시 현재 승인/옛 연결이 차단되어 CONFIG_REQUIRED임을 확인했다. 기존8+새 다중이관1 총9통과170.90초; 원본 정확한 목록 보강 후 다중이관 변형 별도1통과26.36초(같은 시나리오로 합산하지 않음). 실제 복원은 계속 PARTIAL이다.
- 실패/보정: 새 이관 단위/실제PG의 논리 실패는 없었다. 최종 화면 재실행에서 Vitest forks worker 시작 응답 시간초과로 18검사만 통과/오류1이 발생했다. 48완료로 간주하지 않고 작업자1개로 같은 두 파일을 재실행해 최종48통과3.04초를 확인했다. 중간 WIP는 최종검사 진행 상태로 현황/인계와 함께 보존했고 최종 대상823/정적 도움말을 재실행했다. 키/원본/회수·PARTIAL 계약은 완화하지 않았다.
- 문서/사용성: 실회사 절차 §28·구현/정적 도움말·README/현황/progress/HANDOFF 갱신. 직관성(현재/중간 키 역할과 교체 완료·인수 결과 구분), 유효성(고정 부모/원본·자기 이관/현재 회수 교차 대조), 학습성(다음 교체 순서·원래 허용 범위 유지), 유연성(기존 단일/분할과 여러 차례 교체)을 고려했다. 작은 도움말 추가를 UI 전체 완성으로 표현하지 않는다.
- 자원/제약: 생성 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. gw_preview_test 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·서버 환경·실환경 키 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/push/배포 변경 없음. 실제 외부 공급자는 미정이며 같은 OS 계정 합성 키/폴더 수신이다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사/기기/10인/최종전환·최신main 통합은 미실행/미완료.
- 다음: **회수 상태의 영구 기록과 이전 신뢰 설정으로 되돌리는 오류를 막는 공통 계약/실행 어댑터**를 진행한다. 현재 설정 아래 회수 우선 검증과 독립 영구 원장/물리 WORM은 구분하고 회수 키를 과거 승인으로 복구하지 않는다. 이후 공급자 선정 후 외부 장애 복구, 최종 인수 계약/전체 변경·권한 회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(지속되는 신뢰 기준·상태 롤백/키 회수·중단 경계). 공식 모델 페이지에서 복잡한 추론/코딩·High 지원을 확인했으며 작업 난이도에 따른 판단이고 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=1
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_key_chain.py backend/src/fs/gw/catalog_key_handover.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_store_db.py tools/gw_catalog_key_handover.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_key_chain.py backend/src/fs/gw/catalog_key_handover.py backend/tests/test_gw_catalog_key_chain.py backend/tests/test_gw_catalog_store_db.py tools/gw_catalog_key_handover.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
운영 표준 명령은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §28, 한 단계/전달/발행/복구는 §23–27을 따른다. 비공개 work harness 없이 표준 명령/계약으로 재현 가능해야 한다. 현재/다음 개인키는 발급 담당자에게만 있고 오래된 개인키/수신 개인키는 필요 없다. 도구가 서버 신뢰 설정/실환경 키 삭제·배포를 자동 수행하지 않는다. 실계정/브라우저/다른 checkout/WMS를 변경하지 않는다.

## 2026-10-25 GW-READY-02 54차 WIP — 다중 이관 연결 구현/최종 검사 진행

- 시작/직전 커밋 `478c794`, 브랜치 `codex/gw-company-01`. 여러 차례 목록 키 교체의 부모 원본/지문·현재 은퇴자 원래 이관과 실제 캡처 교차 대조, 역할별 서명/현재 최종 권한·중간 회수·순환·재생 차단과 기존 CLI extend를 구현했다. 오래된 개인키가 필요 없고 원래 승인 원본/시각은 넓히지 않는다. 실회사 절차 §28/구현/도움말 갱신 중이다.
- 현재까지: 관련 단위819통과 후 원본 정확한 누락/추가·소급 검사를 보강해 신규62통과. 별도 소유PG 기존8+다중이관1 총9통과170.90초, 보강 후 다중이관 변형 별도1통과26.36초(중복 합산 없음). 화면/도움말48·타입/Ruff/정적DB/R1–R6 통과. 최종 전체 대상 재실행/문서 현황 마무리와 최종 커밋이 남는다. 완료로 표시하지 않는다.
- 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 최대8연결/파일2MiB·펼친누적8MiB와 기존 한도. 독립 영구 회수 원장/설정 자체 롤백 방지·실외부/10인/전체회귀·main/push/배포는 미완료. 실제 키/계정/미리보기DB·다른 checkout/WMS 변경 없음. work/.env·비밀/전체로그 제외.
- 다음: 최종 관련 단위/정적 도움말 검사를 재실행하고 현황/progress/HANDOFF 최종 기록을 갱신·커밋한다. 재현 명령은 직전53차와 같은 대상에 backend/tests/test_gw_catalog_key_chain.py를 더하며 운영 명령은 실회사 절차 §28을 따른다. 기존 gw_preview_test를 시험 초기화하지 않고 새 UUID 소유 *_test DB만 사용/정리한다.

## 2026-10-25 GW-READY-02 53차 — 목록 키 한 단계 정상 교체·현재 회수 우선

- 시작 `00f8636`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 최신 현황/인계·실제52차와 기존 키/목록/복구 계약을 대조한 뒤 승인된 기존 GW 범위에서 목록 발행 키의 한 단계 정상 교체를 구현했다. 이 checkout만 수정했다. 이번 마지막 커밋은 `git log -1`로 확인한다. 새 GW/DB 스키마·수동 인수 완료 체크는 없다.
- `catalog_key_handover`/`gw_catalog_key_handover.py issue/inspect`: 기존/새 회사별 CHECKPOINT_CATALOG 단독 활성 키가 현재 정상 핀/CAS·15분/시계와 전체 보존 이력·서명 복구/불완전 원본을 대조한 뒤 역할별 이중 서명으로 정확한 과거 목록 버전/전체 바이트 지문·복구 문서 지문, 현재 캡처 번호/기록 전체 지문·키 ID/공개키 지문·회사/세대/목록 ID를 묶는다. 역할 문맥은 RETIRING/SUCCESSOR+0바이트·FS-GW-CATALOG-KEY-HANDOVER-v1+0바이트다. 자료 생성만 하며 기존 원본/핀·운영 신뢰 설정/키 생성·삭제/배포를 자동 변경하지 않는다. 기존 목록/복구 문맥·바이트·전달 형식은 유지한다.
- 서버/도구 소유 FS_GW_CATALOG_KEY_LIFECYCLE 설정에 별도 확인한 원래 공개키/회사·RETIRED/REVOKED와 이관 파일/전체 지문을 지정한다. 입력 증거/HEAD/묶음의 키나 설정을 자동 신뢰하지 않는다. 단독 목적/현재 새 키 권한·두 서명/고정 파일 권한·핀·엄격 형식/중복·키 ID 재사용/별칭을 대조한다. 설정64KiB/100회사-키 항목·승인 전체20개/각2MiB·파일당8192목록/8192복구 지문과 전체 이력8192원본 제한이며 먼저 도달한 제한에서 차단한다. 설정/자료 오류는 비공개 값 없는 안전한 구성 오류로 정규화한다.
- RETIRED는 같은 회사/세대·목록 ID와 정확한 과거 원본 지문·버전·캡처 기록번호/기록 지문, 정확한 안쪽 복구 문서만 허용한다. 시각만으로 허용하지 않는다. 현재 바깥 목록 서명·새 발행/이관은 계속 활성 키를 요구하며 남은 옛 활성 공개키도 RETIRED/REVOKED를 우회하지 못한다. 수신 도구의 실제 옛 기준점/중간 이력만 제한적으로 검증하고 최종은 활성 키여야 한다. 최신 FAIL/PARTIAL/원문 없음·옛 기준/같은 버전 분기·뒤늦은 소급 서명/추가 원본·다른 범위·메타데이터 불일치를 과거 성공으로 대신하지 않는다. 두 키가 서명한 캡처 메타데이터라도 실제 원본과 다르면 거부한다.
- 현재 REVOKED는 approvals=[]이며 과거 정상 이관/지문 일치/남은 활성 공개키와 관계없이 목록·복구 검증을 거부한다. REVOKED에 승인 자료를 남긴 모순된 설정도 거부한다. 새 활성 바깥 서명도 회수된 안쪽 복구 근거를 부활시키지 못한다. 이관 파일 누락/변조/서명·권한/형식 오류는 API 준비 조회에서 CONFIG_REQUIRED/ready=false, 현재 대조 실패는 INVALID/차단으로 남기고 이전 성공 상세를 대신하지 않는다. 각 명령/API 요청이 현재 설정/고정 파일을 다시 읽고 한 호출은 로드한 신뢰 스냅샷을 사용한다. BACKUP/RESTORE/CHECKPOINT_HEAD·재관측/인수 키 권한과 admin 로그인/회사 권한은 확장하지 않는다.
- 범위/남은 제약: 현재 활성 새 키가 직접 확인하는 **최초 한 단계 목록 키 교체**다. 새 승인자까지 재은퇴/회수하면 연쇄 추론 없이 차단한다. 여러 차례 이관·더 오래된 개인키 없이 재승인하는 연결/독립 영구 회수 원장·WORM/신뢰 설정 자체의 악의적 롤백 방지는 아직 없다. REVOKED를 RETIRED로 되돌리는 복구 도구/절차를 제공하지 않는다. 현재 회수 우선 검증과 설정 자체의 물리적 롤백 방지를 혼동하지 않는다. 정상 교체로 분류한 두 키의 진술이며 무침해/공인 시각/개인키 삭제·독립 담당자/장애 영역/전체 무누락을 증명하지 않는다. 최대 용량/장기 성능·실제 외부 공급자/운영 설치·실회사 인수는 미검증이다.
- 검증: 관련 단위761통과(기존 경고2, 새58검사). PASS/FAIL/PARTIAL×단일/분할×신규/기존 수신12조합, 옛 현재 핀 차단/활성 새 최종과 기존 실패·불완전 원본 보존, 같은 버전 분기/새 소급 서명/이관 뒤 미승인 원본·다른 회사/세대/목록·원래 캡처 버전/번호/기록 지문 불일치, 현재 회수/승인자 권한 제거·회수/별칭·두 역할 서명/지문/중복·형식/시계·파일 권한/링크/누락, 실제 발급 CLI·개인키 없는 inspect/설정 재조회·안전한 오류를 검사했다. 화면/정적 도움말48통과·타입·수정 Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드/브라우저·모바일·실제 API 브라우저는 이번 재실행하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원→발행 중단/복구 PARTIAL·기존 실패 등록→두 키 CLI 이관/새 키 refresh→옛 활성 키 제거·원래 키 정상 은퇴 설정→옛 수신 핀/이전 인수 INVALID→분할 전달/새 바깥·기존 안쪽 근거 대조/ACCEPTANCE FAIL→실패 후 새 권한 대조·새 폐쇄 복원·후속 인수 PARTIAL과 실패 원본 보존을 확인했다. 이관 파일 변조 시 API CONFIG_REQUIRED/ready=false·같은 고정 원본 복구, 최종 REVOKED 시 과거 전체 이력 export 차단/새 활성 최신 FAIL 보존도 검사했다. 기존7+새 이관1 총8통과144.45초(기존 경고2); 파일 오류 안내/캡처 메타데이터 대조 보강 후 이관 변형은 최종 코드로 별도1통과25.20초로 재확인했고 중복 시나리오라 합산하지 않는다. 실제 복원은 계속 PARTIAL이다.
- 실패/보정: 추가 안전한 구성 오류 시험1실패/54통과에서 깊은 배열 JSON이 재귀 예외 대신 Pydantic ValueError로 거부되어 기대 문구와 달랐다. 구성 ValueError도 안전한 일반 문구로 정규화하고 최종 신규58/관련761을 재실행했다. 서명/현재 권한·회수/현재 바깥 활성 키·부분 인수 계약은 느슨하게 하지 않았다. 실제PG는 최초8통과 후 보강한 새 변형을 재실행했으며 기존30초 미만 DB/실행자 시계 대기를 유지했다.
- 문서/사용성: 실회사 절차 §27·구현/정적 도움말·README/현황/progress/HANDOFF 갱신. 직관성(정상 교체/회수 구분·현재 목록은 활성 키), 유효성(정확한 원본·현재 권한·캡처 메타데이터), 학습성(옛 이관으로 회수 우회 불가·인수 경계), 유연성(기존 단일/분할 전달·읽기 전용 inspect)을 고려했다. 작은 도움말 추가를 UI 전체 완성으로 표현하지 않는다.
- 자원/제약: 생성 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. gw_preview_test 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·서버 환경 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/push/배포 변경 없음. 같은 OS 계정 합성 폴더/키 수신이며 실외부/사람·장애 영역 독립 인수가 아니다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사/기기/10인/최종전환·최신main 통합은 미실행/미완료.
- 다음: **여러 차례 목록 키 교체의 이관 연결·더 오래된 개인키 없이 정확한 원본을 재확인하는 계약/실행**을 진행한다. 회수 키/순환 위임·옛 이관 재생·현재 승인자 권한 상실을 새 성공으로 처리하지 않는다. 독립 영구 회수 원장/설정 롤백 방지는 후속으로 명확히 구분한다. 이후 공급자 선정 후 외부 장애 복구, 최종 인수 계약/전체 변경·권한 회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(다중 승인/현재 신뢰 기준·회수/재생·개인키 없는 원본 연결). 공식 모델 페이지의 복잡한 추론/코딩·High 지원을 확인했으며 작업 난이도에 따른 판단이고 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_key_handover.py backend/src/fs/gw/catalog_recovery.py backend/src/fs/gw/catalog_segments.py backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/src/fs/gw/checkpoint_catalog.py backend/src/fs/gw/evidence_trust.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_store_db.py tools/gw_catalog_key_handover.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_key_handover.py backend/src/fs/gw/catalog_recovery.py backend/src/fs/gw/catalog_segments.py backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/src/fs/gw/checkpoint_catalog.py backend/src/fs/gw/evidence_trust.py backend/tests/test_gw_catalog_key_handover.py backend/tests/test_gw_catalog_store_db.py tools/gw_catalog_key_handover.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
운영 표준 명령은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §27, 전달/발행/복구는 §23–26을 따른다. 비공개 work harness 없이도 표준 명령/계약으로 재현 가능해야 한다. 기존/새 개인키는 발급 담당자에게만 있고 수신/조회에 필요 없다. 도구가 정상 은퇴/회수 분류나 신뢰 설정·키 삭제/배포를 자동 수행하지 않는다. 실계정/브라우저/다른 checkout/WMS를 변경하지 않는다.

## 2026-10-25 GW-READY-02 52차 — 큰 이력 분할 전달·수신 진행점 복구

- 시작 `51fb6e1`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 최신 현황/인계·실제51차 코드 대조 후 승인된 기존 GW 범위에서 분할 수신을 구현했다. 이 checkout만 수정했다. 이번 마지막 커밋은 `git log -1`로 확인한다. 새 GW/DB 스키마·수동 인수 완료 체크는 없다.
- `catalog_segments`/`gw_checkpoint_segments.py export/receive/status`: 별도 확인한 manifest 전체 지문·목록 ID로 최종 목록 지문/버전·실제 수신 기준점과 조각 순서/정상·불완전 원본의 기대/실제 지문·크기를 묶는다. 기존 단일 묶음 v1/v2·256개/8MiB 계약은 유지한다. 분할은 각 실제 바이트 파일2MiB·8192개/manifest2MiB 중 먼저 도달하는 제한이며 전체 원본을 한 번에 메모리에 합치지 않는다. 패키지는 새 빈0700 폴더의0600 파일로 쓰고 검증/발행 핀 CAS 후에만 최종 manifest를 쓴다. 중단 출력은 새 빈 폴더에서 재생성한다.
- 회사/기존 목록·수신 역할/CAS 확인 뒤 본문 해석·검증 전에 보류를 선기록한다. 확인된 명세/조각 누락·변조/옛 정책·버전/공백도 이전 성공을 현재 근거로 읽지 못하게 한다. 완성 임시 파일/배타적 링크와 원래 바이트를 보존하며 저장 파일의 이름/형태·권한/크기에서 진행점을 복구한다. receivedParts는 저장 진행 수이고 최종 서명/바이트 검증 완료 수가 아니다. 중간은 RECEIVING/ready=false·종료2, 모든 파일이 있으나 핀 교체 전이면 읽기 전용 status가 AWAITING_FINALIZE/sourceResult를 표시하며 성공 판정하지 않는다.
- 최종 단계에 모든 실제 바이트/현재 회사별 키·용도/서명, 정확한 연속 버전·기록번호/시각·실패 이후 새 HEAD, 서명 복구 구간/실제 직전 기준과 불완전 원본 전체를 다시 대조한 뒤 한 번만 원자 핀 교체/보류 해제를 한다. 같은 보존 명세·원본/실제 현재 핀의 명시적 --resume만 허용한다. 같은 크기 변조/같은 버전 분기·추가/누락/순서·권한 회수도 최종 활성화 전에 차단한다. 완료 응답 유실/핀 교체 뒤 중단은 실제 현재 핀과 동일 최종 지문으로만 복구한다. 잘못 확인한 명세나 손상 기준점·근거 없는 유실을 다른 지문/과거 성공으로 자동 초기화하지 않는다.
- 기한이 지난 보류 원본은 명시적 같은 원본 재시도로 이력만 보존하고 targetFresh=false/종료2이며 현재 읽기는 STALE다. 미래30초 초과는 계속 거부한다. 완료 최신 PASS도 현재 정책/코드/DB 기준과 신선도가 맞아야 CLI 종료0이며 인수 완료가 아니다. 최신 FAIL/PARTIAL·원문 없음·옛 기준/권한을 이전 PASS로 대체하지 않는다. 현재 키 회수 시 과거 원본도 차단하며 정상 키 교체/침해·회수의 이관 계약은 아직 없다. admin 로그인 이름은 회사/서명 권한을 대신하지 않는다.
- 검증: 관련 단위703통과(기존 경고2, 새41검사). 실제258개 이력/최신 FAIL과8MiB 초과 중단 원본·0바이트/서명 복구 PARTIAL 보존, 정확한 최종 지문, 잘못된 CAS/명세/회사/세대·중복 JSON/재귀/크기/버전/중간 순서·같은 크기 변조/현재 키 회수, 저장/완성 링크/핀 교체 전후·보류 해제 중단/응답 유실 재시도, 읽기 전용 상태/완료 전 성공 부재, 두 실제 CLI 프로세스 경합과 수신 개인키 불필요·만료 이력/새 세션을 검사했다. 화면/정적 도움말48통과·타입·수정 Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드/브라우저·모바일·실제 API 브라우저는 이번 재실행하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원→분할 발행/개인키 없는 수신 중 관리 목록/API 차단→완료 후 관측, 발행 중단/서명 복구/불완전 원본→수신 PARTIAL/기존 인수 INVALID·새 ACCEPTANCE FAIL→실패 후 새 대조·새 폐쇄 복원·후속 인수 PARTIAL과 이전 실패 보존을 확인했다. 명세 변조 후 같은 원본 재시도/미수신 FAIL·refresh도 대조했다. 기존6+새 분할 변형1 총7통과124.70초(기존 경고2). 큰 용량/258개 검사는 합성 파일 단위 검사이며 실제PG에서 그 최대 부하를 실행했다는 뜻이 아니다. 실제 복원은 계속 PARTIAL이다.
- 실패/보정: 초기 새 단위2실패/25통과에서 만료 후 명시적 재시도와 새 세션 helper의 재시도 옵션 기대를 보정했다. 뒤의 경합 시험1실패/37통과는 마지막 조각 대신 첫 조각만 전달한 기대 오류였다. 첫 조각 저장 후 마지막 조각 경합으로 고쳐 최종703을 재실행했다. 만료/미래·서명/실패/보류 차단 계약은 완화하지 않았다. 최종화 전 status의 sourceResult와 실제 완료 result를 분리했다. 실제PG는 최초7통과이며 기존30초 미만 DB/실행자 시계 대기를 유지했다.
- 문서/사용성: 실회사 절차 §26·구현/정적 도움말·README/현황/progress/HANDOFF 갱신. 직관성(저장 진행과 인수 결과 구분), 유효성(전체 원본·최종 신뢰 지문/현재 권한), 학습성(중간 보류·같은 원본 재시도/만료 경계), 유연성(기존 단일 묶음과 분할/진행점 복구)을 고려했다. 작은 정적 도움말 추가를 UI 전체 완성으로 표현하지 않는다.
- 자원/제약: 생성 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. gw_preview_test 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·서버 환경 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/push/배포 변경 없음. 같은 OS 계정 합성 폴더 수신이며 실제 외부 공급자는 미정이다. 최대8192개/최대 용량 성능·장기 보관/독립 담당자·장애 영역/WORM/전체 무누락 증명은 없다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사/기기/10인/최종전환·최신main 통합은 미실행/미완료.
- 다음: **정상 키 교체와 침해·회수를 구분하는 과거 서명 검증/안전한 키 이관 계약·실행**을 진행한다. 현재 회수된 키 거부를 임의로 완화하지 않는다. 이후 공급자 선정 후 외부 장애 복구, 최종 인수 계약/전체 변경·권한 회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(신뢰 시점/현재 회수·기존 원본/이력 바닥값의 경계). OpenAI Docs 공식 모델 페이지를 확인했으며 추천은 작업 난이도에 따른 판단이고 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_segments.py backend/src/fs/gw/catalog_store.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_store_db.py tools/gw_checkpoint_segments.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_segments.py backend/src/fs/gw/catalog_store.py backend/tests/test_gw_catalog_segments.py backend/tests/test_gw_catalog_store_db.py tools/gw_checkpoint_segments.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
운영 표준 명령은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §26을 따른다. 단일 묶음/발행/복구는 §23–25다. 비공개 work harness 없이도 표준 명령/계약으로 재현 가능해야 한다. 수신자에게 발행 개인키를 전달하지 않으며 운영자 확인 명세/목록 ID·현재 핀을 입력 내용으로 자동 신뢰하지 않는다. 원격 전달/서버 설정 설치·실계정/브라우저 변경은 하지 않는다.

## 2026-10-24 GW-READY-02 51차 — 발행 공백의 서명 복구·실제 수신 기준점 연결

- 시작 `888f647`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 현황/인계·설계와 실제 코드 대조 후 승인된 기존 GW 범위에서 발행 공백의 근거를 수신 흐름에 연결했다. 별도 GW/수동 완료 체크·새 DB 스키마는 없다. 최종 커밋은 `git log -1`로 확인한다.
- `catalog_recovery`의 별도 FS-GW-CHECKPOINT-CATALOG-RECOVERY-v1 서명 문맥으로 실제 직전 목록의 전체 지문/버전·번호와 원래 보류 intent/예약 관계, 새 PARTIAL 기록 전체 지문/시각/기준, 공백별 파일 이름의 기대 지문·실제 바이트 지문/크기 또는 원본 없음 상태를 묶는다. 현재 회사/CHECKPOINT_CATALOG 단독 용도·안쪽/바깥 서명을 모두 검사한다. 예약이 직전 기준 바로 다음이면 원래 예상 핀도 실제 현재 핀과 같아야 하며 임의 큰 예약 번호·다른 회사/기준을 새 복구로 만들지 않는다. admin 이름은 권한을 대신하지 않는다.
- 기존 recover-pending은 recoveryProof를 포함한 CHECKPOINT_CATALOG v2를 발행한다. 일반 v1/과거 서명 바이트와 핀·RESTORE_RECHECK v4/인수 진단 형식은 그대로다. 바깥 서명은 기존 catalog canonical 문맥으로 version/proof까지 묶는다. 새 복구는 반드시 PARTIAL/head=null·복구 시각/기록 지문 일치이며 refresh는 최초 근거와 기록을 유지한다. 구형 v1 전용 읽기 환경은 새 v2를 사용할 수 없으며 운영 환경을 자동 설치/재시작하지 않는다.
- 전달 묶음 v2 artifacts는 0바이트/잘린 JSON·미활성 완성 원본을 실제 바이트 그대로 보존한다. 서명한 공백에 필요한 파일만 전달하고 정상 snapshots로 추정/재분류하지 않는다. 현재 목록부터 역으로 검증해 복구 원점에서만 명시된 직전 기준으로 연결한다. 실제 직전 수신 지문/버전/번호와 맞아야 하며 공백 안 기준점·일반 공백/형식 낮춤·누락/추가/중복·원본 변조/사라짐/나중 등장·같은 버전 분기를 거부한다. 기존 보류 선기록/완성 임시 파일/배타적 링크/최종 핀 원자 교체·같은 원본 재시도를 유지하며 불완전 파일/실패를 덮거나 지우지 않는다.
- 범위는 복구 최대256슬롯·파일2MiB, 전달256스냅샷/256원본·총8MiB다. 유효한 현재 보류 intent와 직전 핀이 있는 중단 복구이며, 근거 없는 일반 공백·이미 보류를 잃은 과거 v1 복구·손상 기준점·원래 확인한 수신 지문 오류·회수된 과거 키를 자동 재구성/리셋하지 않는다. 큰 이력 분할/키 이관은 후속이다. 서명은 발행자가 확인한 완료 불명 근거이며 한 번도 공개되지 않았다는 물리 증명·공인 시각·발행자 악의/누락·전체 무누락/독립 담당자·장애 영역/WORM 증명이 아니다. 공급자는 미정이고 실제 원격 전달을 설치하지 않았다.
- 검증: 관련 단위662통과(기존 경고2, 새44검사). 최초/기존 기준의 없음/0바이트/잘림/완성 중단, 두 번 복구 중단·핀 적용 뒤 중단/갱신의 같은 기록 번호, 실제 바이트 보존·0바이트 수신 링크 중단/재시도, 미활성 FAIL 보존·옛 HEAD 새 FAIL/새 생성 후 PASS, 복구/바깥 서명·현재 권한/회사/예약·정확한 원점/시각/기록 변경·가짜 성공/HEAD·과도한 구간, 원본 누락/추가·변조/나중 등장/정상 원본 위장·형식 낮춤·다른 실제 기준점을 검사했다. 최종 화면/정적 도움말48통과, 타입·수정 Python Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드/브라우저·모바일·실제 API 브라우저는 이번 재실행하지 않았다.
- 실제PG: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원→발행 중단/8바이트 원본→복구 서명 목록/수신 PARTIAL→기존 인수 INVALID/새 ACCEPTANCE FAIL→실패 후 새 대조·새 폐쇄 복원→현재 재관측/후속 PARTIAL과 이전 실패/원본 보존을 확인했다. 기존 발행/수신2변형+새 공백 복구1·기존 목록1/복구2 총6통과97.78초(기존 경고2). 복구 시나리오는 최종 코드로 별도1통과20.32초로 재확인했고 같은 시나리오라 합산하지 않는다. 실제 복원은 계속 PARTIAL이고, 목록 입력 FAIL/완료 불명과 실제 복원 도구가 측정한 실패를 혼동하지 않는다. 과거 최신 RESTORE FAIL 선택 검사는 합성 서명 자료다.
- 실패/보정: 초기 새 복구 Literal 표기/참조 오류를 lint와 단위6실패/137통과가 탐지해 실제 타입 선언을 수정했다. 최초 실제PG는 공백 복구/새 대조·복원/후속 인수까지 진행한 뒤 기존 시험의 고정 sequence=2 기대가 새 기록5와 달라1실패/5통과였다. 직전 기록 번호 기준의 상대 검사로 바꾸고 최종6을 재실행했다. 서명·회사/기준·PARTIAL/실패 계약을 느슨하게 하지 않았다. DB/실행자 시계 검사는 기존30초 미만 제한 대기를 유지하며 미래/실패 이후 생성·복원 조건을 완화하지 않았다.
- 문서/사용성: 실회사 절차 §25·구현/정적 도움말·README/현황/progress/HANDOFF 갱신. 직관성(새 복구도 현재 일부/미통과), 유효성(실제 수신 기준점·원본/서명), 학습성(공백 복구와 인수 경계), 유연성(기존 명령/일반v1·복구v2/재시도)을 고려했다. 작은 도움말 추가를 화면 전체 완성으로 표현하지 않는다.
- 자원/제약: 시험 생성 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. gw_preview_test 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·운영 서버 환경 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. 같은 OS 계정의 합성 폴더 수신이며 실외부/사람·장애 영역 독립 인수가 아니다. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/push/배포 변경 없음. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실회사/기기/10인/최종전환·최신main 통합 미실행/미완료.
- 다음: 256개/8MiB를 넘는 **큰 이력의 분할 전달과 수신 진행점 복구**를 구현한다. 중간 묶음을 현재 최신 성공으로 인정하지 않고 최종 신뢰 지문까지 연결하며 공백 복구 원본도 보존해야 한다. 이후 과거 키 이관/외부 공급자 선정 후 장애 복구, 나머지 최종 인수 계약/전체 변경·회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(여러 묶음/진행점·재생/누락/중단 경계). OpenAI Docs 공식 모델 페이지를 열어 확인했으며 작업 난이도에 따른 판단이고 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_recovery.py backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/src/fs/gw/checkpoint_catalog.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_store_db.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_recovery.py backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/src/fs/gw/checkpoint_catalog.py backend/tests/test_gw_catalog_recovery.py backend/tests/test_gw_catalog_store_db.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
발행/수신 계약은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §23–25를 따른다. 표준 명령과 계약은 비공개 work harness 없이 재현할 수 있어야 한다. 발행자 전용 개인키를 수신자에게 전달하지 않으며 서버 설정/원격 운영을 자동 변경하지 않는다. 비밀/전체 로그 출력·다른 checkout/WMS·실계정/브라우저 변경 금지.

## 2026-10-24 GW-READY-02 50차 — 수신 기준점·연속 이력 전달/보류 재시도

- 시작 `bd1e38f`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 현황/인계와 실제49차 코드 확인 후 승인된 GW 범위의 수신 단계를 구현했다. 이 작업 폴더만 수정했다. 최종 커밋은 `git log -1`로 확인한다.
- `catalog_transfer`/`gw_checkpoint_transfer.py export/install`: 발행자 현재 핀과 수신자 revision/catalogDigest 사이의 보존 원본 전부를 원래 서명/개행/파일 지문 그대로 전달한다. 목록 ID/묶음 전체 SHA-256은 별도 신뢰 경로로 확인해 지정하며 각 목록/HEAD의 현재 회사별 키·세대/서명·연속 버전/기록번호·갱신 기록 동일성/시각·실패 이후 새 생성/옛 HEAD·같은 버전 다른 바이트를 대조한다. 신규 묶음은 운영 증거나 새 서명 종류가 아니다. 수신에는 발행 개인키가 필요 없다. status의 catalogDigest/pinDigest를 구별한다.
- 별도 수신 식별자 파일에 회사/세대/목록 ID/최초 묶음 지문을 보존하고 발행/수신 폴더를 혼용하지 않는다. 예상 수신 핀 CAS와 기존 식별자를 확인한 뒤 본문 검증 전에 보류 기록/fsync를 만든다. 확인된 최신 지문에 해당하는 파일 누락/변조·서명/중간 이력/기한/기준점 오류가 있어도 이전 성공 읽기를 차단한다. 입력 내용으로 예상 핀/신뢰 ID를 자동 설정하지 않는다. 잘못된 현재 핀/기존 회사·목록은 변경 없이 거부한다. 잘못 확인한 원본/손상된 바닥값·보류를 자동 초기화하는 도구는 없다.
- 완성 임시 파일/fsync→배타적 링크/폴더 fsync로 원본 파일 게시→마지막 핀 한 번 원자 교체/fsync→보류 제거 순서다. 보존된 파일/실패/불완전 쓰기를 덮거나 지우지 않는다. 링크 직후 중단의 같은 바이트/소유자/자체 임시 별칭 하나만 정리한다. 같은 묶음의 명시 재시도와 완료 응답 유실 재확인만 허용한다. 같은 버전의 다른 원본·과거 이력 충돌·다른 묶음/옛 핀/더 최신 수신 이력을 우회하지 않는다. 같은 예상 핀 경합은 한 프로세스만 성공한다.
- 보류 원본이 만료되면 같은 지문의 유효 원본에 한해 --resume으로 이력 완료할 수 있다. 미래 시각/서명·전체 버전 검증은 유지하며 targetFresh=false/종료2, 관리 핀 읽기는 계속 기한 오류로 차단된다. 그 기준점부터 새 신선한 묶음을 수신해야 현재 재관측을 할 수 있다. 최초/일반 설치에는 이 예외가 없으며 만료된 PASS를 종료0이나 현재 성공으로 사용하지 않는다. contextMatches도 별도로 출력하며 최신 옛 기준/FAIL/PARTIAL은 그대로 보존·종료2다. ready=false이며 운영 승인과 무관하다.
- 범위/제약: 1회256개 스냅샷(기준 포함)/8MiB 안에서 **보존된 미수신 버전**을 따라잡는다. 발행 중단으로 예약만 된 버전/기록번호 공백·발행 원본 유실/손상·과거 키 회수는 자동 건너뛰지 않고 차단한다. 공백 복구 명세/키 이관·큰 이력 분할·장기 용량 관리는 후속이다. 기존 v1을 과거 해시가 연결된 서명 체인으로 바꾸지 않았다. 실제 네트워크 전송/다른 OS 계정·담당자/장애 영역·외부 공급자/연속 감시·미등록 이력 완전성은 증명하지 않는다. 별도 원격 전달/환경 설치를 자동 실행하지 않는다.
- 검증: 관련 단위618통과(기존 경고2, 신규39검사). 순서/번호/서명·변조/누락/옛 기준·실패/같은 시각 옛 HEAD·같은 버전 분기·보존 이력 충돌, 크기/개수/중복 JSON/깊은 중첩/키 회수, 자체 식별자/스냅샷의 부분 쓰기·링크 직후·핀 교체/동기화·보류 제거 중단7경계, 같은 원본 재시도/다른 원본 거부·완료 응답 유실, 실제 두 수신 CLI 프로세스 경합/발행 개인키 없음, 실제 CLI의 입력 없음/옛 핀 거부·만료된 보류 PASS 종료2를 확인했다. 최종 화면/정적 도움말48통과, 타입·수정 Python Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드/브라우저·모바일·실제 API 브라우저 검사는 이번 재실행하지 않았다.
- 실제 PostgreSQL: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 복원→발행 CLI→별도 수신 폴더/미수신 FAIL+갱신 따라잡기→재관측v4·수집/API·준비 조회까지, 발행 직접 읽기/수신 읽기2변형+기존 목록1/복구2 총5통과78.18초(기존 경고2). 수신 변형은 최종 코드에서 별도1통과16.19초로 재확인했으며 같은 시나리오라 합산하지 않는다(앞선5통과82.95초/수신1통과15.46초도 중복). 확인한 최신 묶음의 변조 뒤 보류/기존 인수 INVALID·같은 원본 재시도·최신 FAIL 수집/등록·개인키 없는 수신·ready=false/미확인4를 확인했다. 실제 복원은 계속 PARTIAL이며 입력 검증 FAIL과 실제 복원 도구의 실패 측정을 혼동하지 않는다. 과거 최신 RESTORE FAIL 선택 검사는 합성 서명 자료다.
- 실패/보정: 최초 신규 단위1건은 InvalidSignature를 검사가 ValueError만 기대해서 실패했으며 실제 암호 서명 거부 예외를 검사하도록 보정했다. 만료 재시도 보완 중 validate의 새 인자 연결 누락을 단위35실패/3통과가 탐지했고 실제 함수 선언/조건을 수정한 후 최종618 전체 선택 검사를 다시 통과했다. 미래 시각/서명/현재 기한 계약을 느슨하게 하지 않았고 만료 보류의 이력 완료와 현재 읽기 차단을 분리해 실CLI까지 검사했다. 실제PG5와 수신 재확인은 모두 통과했다.
- 문서/사용성: 실회사 절차 §24·구현/정적 도움말·README/현황/progress/HANDOFF 갱신. 직관성(확인된 새 전달 실패 때 과거 상세 차단), 유효성(모든 원본/현재 신뢰), 학습성(전달과 인수 경계), 유연성(기존 API/오프라인 공개키 수신·보류 만료 복구)을 고려했다. 새 업무 화면/체크로 운영 완료를 만들지 않았다. admin 이름은 회사/보안/발행 권한을 대신하지 않는다. UI 전체 완성은 아니다.
- 자원/제약: 시험 생성 자원만 정리, 최종 관측 시험DB0·폐쇄 복원DB0·기존 preview DB존재 확인. gw_preview_test 초기화/실계정 admin·비밀번호/OTP·브라우저/미리보기 정책·운영 서버 환경 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. 합성 수신은 같은 OS 계정의 별도0700 폴더이며 실제 외부/사람·장애 영역 독립 인수가 아니다. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 다른 checkout/WMS·main/push/배포 변경 없음. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사·기기/10인/최종전환·최신main 통합 미실행/미완료.
- 다음: 발행 중단의 예약 번호/원본 공백을 수신자가 임의로 건너뛰지 않도록 **서명 복구 근거와 수신 기준점을 연결하는 계약/도구**를 구현한다. 이후 키 이관/큰 이력 분할·외부 공급자 선정 후 장애 복구, 나머지 최종 인수 계약/전체 변경·회수, 최신main/전체회귀·실회사10인/최종전환이 남는다. 다음 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(서명 이력 공백·실패 보존/재생·여러 기준점의 복구 판정). 공식 모델 안내에 따른 기능 확인과 작업 난이도를 바탕으로 한 판단이며 자동 모델 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_transfer.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_catalog_transfer.py tools/gw_checkpoint_catalog.py tools/gw_checkpoint_transfer.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_store.py backend/src/fs/gw/catalog_transfer.py backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_catalog_transfer.py tools/gw_checkpoint_catalog.py tools/gw_checkpoint_transfer.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
발행/수신/별도 신뢰 지문·현재 기준점/재시도·보류 만료 이력 완료/제한은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §23–24를 따른다. 표준 명령과 계약은 비공개 work harness 없이 재현할 수 있어야 한다. 수신자에게 발행 개인키를 전달하거나 서버 설정·원격 운영을 자동 변경하지 않는다. 비밀/전체 로그 출력·다른 checkout/WMS·실계정/브라우저 변경 금지.

## 2026-10-24 GW-READY-02 49차 — 로컬 목록 발행·원자 핀 교체/중단 차단

- 시작 `44e5537`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 최신 인계/현재 상태와 실제 코드 확인 후 승인된 GW 작업의 로컬 발행 단계를 구현했다. 작업 폴더만 수정했으며 별도 GW/스키마나 수동 완료 체크를 추가하지 않았다. 최종 커밋은 `git log -1`로 확인한다.
- `catalog_store`와 `gw_checkpoint_catalog.py publish/refresh/status/recover-pending`를 추가했다. 회사/세대 전용0700 폴더, 별도 회사/CHECKPOINT_CATALOG 단독 용도·실제 개인키/공개키 일치, 현재 정책/버전 문맥, 기존 서명 HEAD/실제0600 암호화 대조 파일의 서명/범위/RPO·시계/형식/크기/전체 SHA-256·읽기 중 변경을 검사한다. 정상 파일 대조만 목록 PASS이며 ACCEPTANCE PASS/복호화·격리복원/전체 인수 통과가 아니다. 권한/CAS 확인 뒤 입력 검증 실패는 새 FAIL·원문 null/종료2, 설정/권한/기존 상태 오류는 종료1이다.
- 지속 잠금+예상 핀 지문 CAS, 원본 읽기 전 보류 의도0600/fsync, 새 지문 이름 스냅샷 O_EXCL/fsync, 임시 핀/fsync와 같은 폴더 원자 교체·폴더 fsync를 구현했다. 과거 스냅샷/실패/불완전 파일을 덮거나 지우지 않는다. 현재 스냅샷은 최신 항목 하나이며 과거 파일을 보존한다. 최대100,000폴더 항목/2MiB, 장기 이관/용량 관리 도구는 후속이다. refresh는 번호/기록 시각/결과/HEAD·기준을 바꾸지 않으며 실패를 숨기지 않는다. status는 공개키만 쓰는 제한된 진단이며 운영 준비/15분 신선도 승인이 아니다.
- 보류/더 높은 미완료 스냅샷이 있으면 관리 핀 읽기를 차단한다. recover-pending은 실제 현재 핀과 기존 회사/세대/식별자를 검증한 뒤 가장 높은 저장/예약 번호보다 높은 새 PARTIAL·원문 null을 남긴다. 미완료 PASS 활성화나 과거 핀 롤백은 없다. 실패/PARTIAL 이후 옛 HEAD 재발행은 새 FAIL이며 새 생성 시각이 필요하다. 현재 핀/보류 자체가 손상되면 자동 초기화하지 않는다. 같은 OS 소유자의 악의적 변경을 막는 WORM/외부 CAS라고 주장하지 않는다.
- `FS_GW_CHECKPOINT_CATALOG_PIN_FILE` 관리 모드는 기존 v1 핀 형식을 사용한다. 기존 JSON 설정과 동시 지정/빈 값, 경로/소유자/권한·링크/하드링크, 현재 서명/기한·보류/최고 저장 버전·읽기 중 핀 교체를 검사한다. 기존 모드/원본 서명 바이트는 유지한다. 수집기/API 등록/준비 조회에서 현재 관리 핀을 다시 읽어 변경 전 증거를 INVALID로 만들고 과거 성공으로 대신하지 않는다. 발행 개인키/URL/전체 문서/전체 로그를 출력하지 않는다. admin 로그인 이름은 회사/보안/발행 권한을 부여하지 않는다.
- 검증: 관련 단위579통과(기존 경고2, 새36검사 포함). 별도 두 CLI 프로세스의 동일 예상 핀에서 하나만 성공, 원본 읽기 중 종료·스냅샷/임시 핀/원자 교체/교체 직후 동기화 중단, 불완전 파일 보존·새 PARTIAL 복구, 초기 중단 식별자 유지/재초기화 거부, 옛 생성/서명/원본 없음/기한·권한/링크·키 회수/핀 후퇴·읽기 중 교체·과도한 JSON 중첩의 안전한 오류/새 FAIL을 확인했다. 최종 화면/정적 도움말48통과, 타입·수정 Python Ruff check/format·정적DB219표/2409열/543FK·R1–R6 오류0. UI 제품 코드는 수정하지 않았으며 브라우저/모바일·실제 API 브라우저는 이번 재실행하지 않았다.
- 실제 PostgreSQL: 새 UUID 소유 시험DB에서 실제 dump/암호화/폐쇄 격리 복원→새 발행 CLI→관리 핀→재관측v4/수집/API/준비 조회 신규1시나리오와 기존 목록1/복구2 최종4통과65.69초(기존 경고2). 새 발행 PASS/ready=false, 최신 입력 검증 FAIL 뒤 기존 인수 INVALID·새 ACCEPTANCE FAIL 등록, 갱신해도 FAIL 유지, 옛 예상 핀 거부·원본 바이트 보존을 확인했다. 앞선 실행은 새 시험이 기존 실행 설정에 없는 policy를 읽어 KeyError로1실패/기존3통과였다. 시험 문맥을 현재 operations API 정책으로 준비한 뒤 전부 재실행했다. 제품 계약/검증을 느슨하게 하지 않았다. 실제 복원은 계속 PARTIAL이며 새 FAIL은 발행 입력 검증 실패이지 실제 복원 실패 측정이 아니다. 기존 최신 RESTORE FAIL 선택 검사는 합성 서명 자료다.
- 문서: 실회사 절차 §23·구현/정적 도움말·문서 지도/현재 상태/progress/HANDOFF 갱신. 직관성(현재 차단/다음 점검), 유효성(실파일 대조/현재 재조회), 학습성(파일 PASS/인수 경계), 유연성(기존 정적·명시적 관리 모드)을 고려했다. 작은 도움말 추가를 UI 전체 완성으로 표현하지 않는다.
- 자원/제약: 시험 생성 자원만 정리, 최종 관측 시험DB0·폐쇄 복원DB0·기존 preview DB존재 읽기 확인. gw_preview_test 초기화/실계정 admin·비밀번호/OTP/브라우저·미리보기 정책/운영 서버 환경 변경 없음. API8362/Vite5362 상태 재검사/재시작 없음. work/.env·비밀/전체 로그 Git 제외. 스키마/마이그레이션/metadata·Excel/ERD 변경 없음. 외부 공급자 미정이며 임의 연결/설정하지 않았다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집/전체 실제DB·실외부/실회사·기기/10인/최종전환·최신main 통합/원격push/배포 미실행/미완료.
- 다음: 별도 수신 폴더의 신뢰 기준점 전달/검증·순차 설치/CAS·중단 재시도와 누락 버전 따라잡기 계약/도구를 구현한다. 로컬 핀 파일 교체만으로 원격 전달/수신자 독립성을 완료했다고 보지 않는다. 이후 공급자 선정 후 외부 장애 복구, 나머지 최종 인수 계약/전체 변경·회수, 최신main/전체회귀/실회사10인·최종전환이 남는다. 다음 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(복수 기준점·순서/재생/누락·중단 경계). OpenAI Docs 공식 모델 페이지를 열어 확인했으며 추천은 작업 난이도에 따른 판단이고 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_catalog_store.py backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_catalog_store_db.py backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
uv run --project backend ruff check backend/src/fs/gw/catalog_store.py backend/src/fs/gw/checkpoint_catalog.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_catalog_store_db.py tools/gw_checkpoint_catalog.py
uv run --project backend ruff format --check backend/src/fs/gw/catalog_store.py backend/src/fs/gw/checkpoint_catalog.py backend/tests/test_gw_catalog_store.py backend/tests/test_gw_catalog_store_db.py tools/gw_checkpoint_catalog.py
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
발행/갱신/상태·중단 복구/관리 핀 설정은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §23을 따른다. 표준 명령과 계약은 비공개 work harness 없이 재현할 수 있어야 한다. 읽기 어댑터에는 발행 개인키가 필요 없으며 수신자 전송/설정 설치·원격 운영은 자동화하지 않는다. 비밀/전체 로그 출력·다른 checkout/WMS·실계정/브라우저 변경 금지.

## 2026-10-24 GW-READY-02 48차 — 별도 서명 목록의 현재 HEAD 대조

- 시작 `eb29142`, 브랜치 `codex/gw-company-01`, 작업 트리 깨끗함. 사용자 다음 진행 승인 범위에서 기존 도구/인수 계약을 확장했다. 별도 GW/스키마·수동 인수 완료 체크 없이 공통 읽기 어댑터 하나를 진행했다. 최종 커밋은 `git log -1`로 확인한다.
- `checkpoint_catalog`에 서버/운영자 소유 FS_GW_CHECKPOINT_CATALOG 설정의 SIGNED_SNAPSHOT_FILE 읽기를 추가했다. 고정 catalogId/문서 전체 바이트 SHA-256, 0600 일반 파일/0700 직접 부모·소유자/링크·중복 JSON/2MiB/1000항목·서명/15분·미래30초를 검사한다. 새 CHECKPOINT_CATALOG 키는 명시적 회사와 단독 용도를 요구하며 기존 원본/재관측/인수 키와 공개키 바이트를 공유할 수 없다. 경로/신뢰 핀을 선택 HEAD나 업로드 문서가 정하지 않는다. 목록 발행·불변 교체/핀 전달 도구와 외부 공급자 연결은 아직 없다.
- 기존 recheck-restore의 --check-current-source --check-checkpoint-catalog가 RESTORE_RECHECK v4로 현재 원본/복원본·서명 HEAD와 별도 목록 관측을 연결한다. 설정이 있으면 목록 대조를 생략할 수 없다. 현재 설정의 목록 서명/핀·회사/세대의 최신 sequence를 모든 정책/버전/결과/원문 유무에서 선택한다. 최신 FAIL/PARTIAL·원문/범위 없음·옛 기준·다른 HEAD는 BLOCKED→ACCEPTANCE FAIL, 일치는 PARTIAL이다. 파일/서명/핀·기한/형식 오류는 새 출력 없는 오류다. 경로/URL/전체 목록·다른 회사 원문을 인수 증거에 넣지 않는다. 기존 인수 진단v4와 옛 v1~v3 바이트/지문을 유지한다.
- 수집기·회사 잠금 안 API 등록·준비 재조회에서 현재 목록을 다시 읽는다. 등록된 모든 기준/실패/원문 없는 이력의 catalogId/버전/최신 번호·HEAD 지문/생성 시각을 바닥값으로 써서 목록 리셋·후퇴·같은 버전의 다른 파일·같은 번호의 다른 결과/HEAD·새 번호로 옛 생성 시각/다른 HEAD를 제시하는 새 PARTIAL을 거부한다. 등록된 목록 대조 미통과 뒤에는 실패 등록 이후 생성한 새 대조·격리 복원을 요구한다. 현재 핀/키 회수·목록 변경은 이전 인수를 INVALID로 만들며 과거 성공을 찾지 않는다. 설정을 제거해도 이미 등록한 v4에서 구형 형식으로 되돌릴 수 없다. 바닥값 관측 자체가 손상되면 차단하며 초기화 도구는 없다.
- 기존 재관측 펼침 안에 별도 서명 목록의 시각/버전/최신 번호·7개 결과와 조치를 표시하고 현재 대조에 실패하면 상세를 숨긴다. 정적 도움말·실회사 절차 §22와 구현 문서를 갱신했다. 직관성(현재 증거 옆), 유효성(현재 원본/서명 재대조), 학습성(실패 원인/외부 인수 경계), 유연성(기존 접힘/키보드/모바일)을 고려했다. admin 이름은 회사/보안/목록 발행 권한을 대신하지 않으며 UI 전체 완성은 아니다.
- 검증: 관련 단위543통과(기존 경고2), 화면/정적 도움말48통과, 타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 새 UUID 소유 PostgreSQL에서 실제 dump/암호화/격리 복원·목록/API/실CLI1시나리오+기존 복구2시나리오 최종3통과60.89초(기존 경고2). 최신 실패/일부/원문 없음/옛 코드 기준·핀 후퇴·번호만 올린 옛 성공/우회 발급 등록 거부, 새 대조/새 격리복원 PARTIAL, 기존 실패 보존, 설정 제거/형식 생략·별도 발행 키 회수 시 INVALID, 단독 관측400, 두 CLI의 PARTIAL/FAIL 종료0/2·새0600 파일/미설정 종료1·자동 등록 없음까지 확인했다. 앞선3통과58.03초/59.90초는 같은 시나리오이며 합산하지 않는다. 목록은 별도 시험 키가 만든 합성 서명 자료로 실제 외부 목록 발행/저장소 인수가 아니다. 최신 RESTORE FAIL 선택 검사는 기존 합성 서명 FAIL 자료이며 실제 복원 도구가 그 실패를 측정했다고 표현하지 않는다.
- 실패/보정: 최초 목록 단위8개 미통과 조합에서 서명 발급의 결과 계산이 새 목록 BLOCKED를 반영하지 않아 엄격 계약이 발급을 거부했다. 발급 계산에 목록 결과를 포함하고 원본/복원본/목록의 정상·미통과/측정 불가12조합을 추가해 검사했다. 목록 미통과6이유별 생성 시각의 실패 등록 직전/동일/직후18경계도 검사했다. 계약/서명/미통과 기준을 느슨하게 하지 않았다. 새 실제 DB 검사는 최초3통과 후 CLI/추가 후퇴 검사 보강 최종3을 재실행했다. 기존 DB/실행자 시계 차이 시험 대기는 이전 차수와 같은30초 미만 제한이며 제품의 미래 시각 거부는 그대로다.
- 브라우저: 기존 제품 React+읽기 전용 합성 API에서1440/390px 목록 최신 실패/조치·외부 독립 인수 문구·PC Enter 펼침·44px·가로 넘침0을 확인했다. 모바일 메뉴 오버레이는 닫고 본문 위치를 확인했다. 실제 API 브라우저/실기기 인수나 메뉴 동작 수정/화면 전체 완성은 아니다. 임시 탭·뷰포트·소유5364 서버 정리. Vite5362 PID20714 listen만 재확인했고 API 실행 상태 재검사/재시작 없음.
- 자원/제약: 생성한 시험 자원만 정리했고 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. preview DB 초기화·실계정 admin/비밀번호/OTP·미리보기 정책/업무 변경 없음. 새 서버 목록 환경/키를 실미리보기에 설치하지 않았다. work/.env·비밀/전체 로그는 Git에 넣지 않는다. 스키마/마이그레이션/Excel/ERD 변경 없음. ready=false/실제 복원 PARTIAL/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·기존 전체 실제DB/고정24수집·실외부/실회사·기기/10인·최종전환·최신main 통합/원격push/배포 미실행/미완료. 다른 checkout/WMS는 건드리지 않았다.
- 다음: 이 계약을 따르는 목록 발행·불변 교체/신뢰 핀 전달 도구와 실패/경합 검증을 구현한다. 현재 설정한 서명 스냅샷을 읽은 결과로만 해석하며 아직 관측하지 못한 더 최신/누락 기록·발행자의 악의, 별도 사람/장애 영역·물리 독립 보관·전체 변경 수집/회수·공인 시각/바이너리·연속 감시는 증명하지 않는다. 외부 공급자는 미정이다. 이후 최종 인수 계약·공급자 선정 후 외부 장애복구·최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(발행 권한·파일 교체/신뢰 핀 경합과 재생 방지·부분/최종 경계). OpenAI Docs 공식 모델 페이지를 검색·열어 확인했으며 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_checkpoint_catalog.py backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_checkpoint_catalog_db.py backend/tests/test_gw_recovery_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
목록 설정/원본 서명·키/전용 URL·현재 읽기/새 복구 순서는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §18–22를 따른다. 이 표준 명령/계약은 비공개 work harness 없이 재현할 수 있어야 한다. 읽기 어댑터에 목록 발급 개인키는 필요 없으며 시험 자료 발행은 저장소의 합성 시험 helper로 한정했다. 외부 목록 발행자를 임의 설치하지 않는다. 비밀/전체 로그를 출력하거나 원격 운영·다른 checkout·실계정/브라우저 설정을 변경하지 않는다.

## 2026-10-24 GW-READY-02 47차 — 대조 생성 시각·서명 HEAD의 인수 연결

- 시작 `14a61b6`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 다음 진행 승인 범위에서 기존 도구/증거 계약 하나를 보완했다. 새 GW/스키마·서명 종류·수동 완료 체크는 없다. 최종 커밋은 `git log -1`로 확인한다.
- `recheck-restore --check-current-source`가 RESTORE_RECHECK v3에 원본 서명 CHECKPOINT_HEAD를 포함한다. HEAD 키의 현재 회사/CHECKPOINT 용도와 기존 명세 서명 문맥을 별도로 확인하며 회사/세대/정책·백업/대조 실행·암호화 파일 지문을 RESTORE 원본 관측에 대조한다. 대조 생성은 복원 시작보다30초 넘게 늦거나 RPO+30초보다 오래될 수 없다. 도구는 복호화한 대조 명세의 생성 시각도 HEAD와 대조한다. 원본 비교 없는 실행은 기존 v1이며 기존 v1/v2·RESTORE 서명 바이트/지문은 보존한다.
- 원본 변경 FAIL 이후 새 PARTIAL은 대조 생성 시각도 실패 등록보다 엄격히 뒤여야 한다. 이 순서에30초 유예를 적용하지 않는다. 다른 UUID/파일을 실패 전에 만들고 새 물리 대상에 복원해도 수집기/잠금 안 API/준비 재조회가 거부한다. 최신 실패/원문 없음/변조/옛 기준을 과거 성공으로 대체하지 않는다. HEAD 형식 도입 뒤 v2/v1으로 새 인수를 등록할 수 없고 모든 정책/실패/원문 없는 이력을 포함한다. HEAD 키의 CHECKPOINT 용도만 회수해도 기존 인수는 INVALID/요약 미표시다. 반복 실패 이력은 유지한다.
- 기존 재관측 펼침에 **복원 권한 대조 생성 근거**와 검증한 생성 시각/독립 최신 목록 미확인을 표시했다. 기존 회사/업무 관리 맥락·정적 도움말/실회사 절차 §21을 보완했다. 직관성(현재 증거 옆), 유효성(서버 재대조/미통과), 학습성(의미·미확인 범위), 유연성(접힘/키보드/모바일)을 고려했다. admin 이름만으로 회사·보안·서명 권한을 부여하지 않으며 UI 전체 완성은 아니다.
- 검증: 단위475통과(기존 경고2), 화면/정적 도움말41통과, 타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 별도 소유 PostgreSQL 최종6통과80.73초(기존 경고2). 새 UUID 소유 시험DB만 사용했고 실제 dump/암호화/폐쇄 복원·실패 전 다른 대조/같은 대조 거부·새 대조/복원/재관측 PARTIAL·실패 유지·구형 계약 수집기/우회 발급 API 거부·HEAD 용도 회수/현재 재조회·CLI/기존 재관측 회귀를 확인했다. 중간3통과는 최종 검사와 겹치므로 합산하지 않는다. 최신 RESTORE FAIL 선택 검사는 합성 서명 FAIL 자료이며 실제 도구의 실패 측정 실행이라고 표현하지 않는다.
- 실패/보정: 첫 실제3검사 중2건은 의도적 구형 발급 시험이 수집기의 직접 import 참조가 아닌 원래 모듈의 함수만 우회해 차단된 시험 준비 오류였다. 실제 수집기 참조를 시험 안에서만 우회하고 서버 등록 거부를 확인했다. 다음1건/확대2건은 실행자 완료 시각이 PostgreSQL 시계보다 앞서 준비 조회가 미래 시각/STALE로 차단한 것이다. 시험은 DB 시계와 완료 시각을 비교해30초 미만 차이에만 완료 시각 이후 조회를 기다리도록 보정했다. 제품의 미래 시각 거부/순서·권한/미통과 기준은 느슨하게 하지 않았다.
- 브라우저: 기존 제품 React+읽기 전용 합성 API에서1440/390px 생성 시각/독립 목록 미확인 문구, PC Enter 펼침·44px 조작·가로 넘침0을 확인했다. 모바일 본문 영역 위치도 확인했고 크기 전환의 기존 메뉴 오버레이는 닫았다. 실제 API 브라우저/실기기 인수가 아니며 메뉴 동작 수정/화면 전체 완성은 아니다. 임시 탭·뷰포트·소유5364 서버 정리. Vite5362 PID20714 listen만 재확인, API 상태 재검사/재시작 없음.
- 자원/제약: 생성한 시험 자원만 정리하며 preview DB 초기화·실계정 admin/비밀번호/OTP·미리보기 정책/업무 변경 없음. 최종 관측 시험DB0·폐쇄 복원DB0/기존 preview DB존재를 읽기 확인했다. work/.env·비밀/전체 로그는 Git에 넣지 않는다. 스키마/마이그레이션/Excel/ERD 변경 없음. ready=false/실제 복원 PARTIAL/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 전체CI/전체회귀·고정24수집·실외부/실회사·기기/10인·최종전환·최신main 통합/원격push/배포 미실행/미완료이며 다른 checkout/WMS는 건드리지 않았다.
- 다음: 특정 파일의 서명 생성 시각과 별개로, 운영자가 고른 옛 HEAD/기대 지문을 독립 최신 목록과 대조하는 공통 계약/읽기 어댑터를 구현한다. 별도 운영자/장애 영역·불변 목록/삭제 탐지·공인 시각/실행 바이너리·연속 관측은 이번 증명이 아니다. 외부 공급자 미정은 유지한다. 이후 최종 인수 계약·공급자 선정 후 외부 장애복구·통합/전체회귀·실회사10인/최종전환. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(독립 최신성/재생 공격·현재 키·복구 순서와 부분/최종 경계). OpenAI Docs 공식 페이지를 검색·열어 확인했으며 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_checkpoint_head.py backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 대조 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_recovery_db.py backend/tests/test_gw_source_checkpoint_db.py backend/tests/test_gw_restore_recheck_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
키/전용 URL·HEAD 계약/순서·종료값은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §18–21을 따른다. 이 표준 명령과 절차는 비공개 work harness 없이 재현 가능해야 한다. 비밀번호/OTP/키/전체 로그를 출력하지 않으며 원격 운영·다른 checkout·실계정/브라우저 설정을 변경하지 않는다.

## 2026-10-23 GW-READY-02 46차 — 원본 변경 실패 뒤 새 대조·격리 복원·후속 인수

- 시작 `5a2b040`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 “다음진행해줘”에 따라 기존 승인 범위의 후속 복구 흐름 하나를 보완했다. 새 GW/DB 테이블·서명 종류·수동 완료 체크를 만들지 않았다. 최종 커밋은 `git log -1`로 확인한다.
- 같은 회사/세대의 모든 정책·버전에서 최근 원본 변경(CHANGED) ACCEPTANCE FAIL을 복구 기준으로 선택한다. 역사 인수/내부 재관측 서명과 현재 키의 회사/용도, 등록 행/집계/메타데이터를 대조한다. 옛 관측의 서명 확인을 현재 정책/버전/15분 관측 통과로 간주하지 않는다. 원문 없음/변조·키 회수·복원 관측 없음은 과거 checkpoint 식별을 믿지 않고 실패 등록 이후 새 BACKUP을 요구한다.
- 새 PARTIAL 인수에는 실패 등록 이후 시작한 다른 RESTORE 실행·물리 대상·checkpoint runId/암호화 파일 지문과 현재 원본 MATCH/복원본 관측을 요구한다. 현재 백업/복원이 같은 백업 실행·명세를 가리키지 않으면 재복원 단계로 남긴다. 원본을 예전 상태로 되돌리거나 같은 checkpoint로 새 대상만 만든 결과도 등록을 거부한다. 검증 가능한 실패 원본/관측이 있으면 현재 유효한 기존 백업을 새 checkpoint와 함께 사용할 수 있다. 최신 각 종류 증거의 실패/원본 없음/옛 기준 선택은 기존 그대로이며 이전 성공으로 대체하지 않는다.
- 현재 DB 수집기·회사 잠금 안의 API 등록·준비 재조회에 같은 복구 조건을 연결했다. 반복 FAIL 기록은 보존하고 새 PARTIAL만 복구 조건으로 제한한다. 수집기를 우회한 발급도 서버가 OPERATING_RECOVERY_REQUIRED/400으로 거부하며, 수집기는 종료1/파일 없음과 새 백업 또는 새 격리 복원 조치를 출력한다. 키/URL/계정 원문을 오류에 출력하지 않는다. 등록된 실패를 수정·삭제하거나 자동 복원을 실행하지 않는다.
- 기존 실행 증거 영역에 **원본 변경 후 재점검**의 새 백업/새 대조·복원/새 관측·인수/후속 일부 확인4상태와 기준 실패 시각·조치·접힌 순서/정적 도움말을 연결했다. 직관성은 현재 조치/기존 회사 관리 영역, 유효성은 서버 재대조/차단, 학습성은 순서·범위/도움말, 유연성은 펼침·키보드/모바일을 고려했다. admin 로그인 이름은 회사/보안/발급 권한을 대신하지 않으며 UI 전체 완성은 아니다.
- 검증: 관련 단위448통과(기존 경고2), 화면/정적 도움말41통과, 타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 새 소유 PostgreSQL 실제 dump/암호화/복원·원본 변경/회수 후 복구2시나리오와 기존 원본 비교1시나리오, 최종3통과74.50초(기존 경고2). 역사 원문 정상/없는 경우, 원본 변경 원복·옛 대상 재관측·옛 checkpoint 새 대상의 수집기/API 거부, 실CLI 조치/종료1/새 출력 없음, 새 백업(필요시)/새 checkpoint/새 격리 복원/새 관측→PARTIAL·실패 행 유지, 이후 최신 RESTORE FAIL의 INVALID/재복원 요구를 확인했다. 마지막 최신 RESTORE FAIL 선택 검사는 합성 서명 FAIL 자료를 추가한 것으로, 그 실패를 실제 복원 도구가 측정했다고 주장하지 않는다. 실제 복원은 계속 PARTIAL이며 실회사10인 인수가 아니다.
- 실패/보정: 최초 실제3건 중 마지막 최신 실패 검사에서2건이400이었다. 합성 FAIL 증거의 unrevokedSessions=1과 sessionsInvalidated=true를 모순되게 만들었기 때문에 기존 계약이 정확히 거부했다. 시험 표지를 false로 보정했고 실제 복구3건을 통과시킨 뒤 CLI 조치 추가를 포함해 최종3건을 재실행했다. 제품 서명/권한·미통과 기준을 느슨하게 하지 않았다.
- 브라우저: 제품 React+읽기 전용 합성 API로1440/390px 재점검 본문·세 단계/미완료 범위·PC 키보드 펼침·44px 조작·가로 넘침0을 확인했다. 크기 전환 중 메뉴 오버레이는 닫고 실제 본문을 다시 확인했다. 실제 API 브라우저/실기기 인수가 아니다. 임시 탭·뷰포트·서버 정리. 기존 Vite5362 PID20714 listen만 재확인, API 실행 상태 재검사/재시작 없음.
- 자원/제약: 생성한 시험 자원만 정리했고 관측 시험DB0·폐쇄 복원DB0/preview DB존재를 읽기 확인했다. preview 초기화·실계정 admin/비밀번호/OTP·미리보기 정책/업무 변경 없음. 스키마/마이그레이션/Excel/ERD 변경 없음. ready=false/실제 복원 PARTIAL/최종4조건 UNVERIFIED 유지. 전체CI/전체회귀·기존 전체 실제DB 회귀·고정24수집·실외부/실회사·기기/10인·최종 전환은 미실행/미완료. 다른 checkout/main/원격push/배포 변경 없음. work/.env·전체 로그·비밀은 Git에 넣지 않는다.
- 다음: 권한 대조 생성 시각과 최신 HEAD의 독립 증거 연결을 보완한다. 이번 조건은 다른 대조 실행/파일과 실패 등록 이후 새 복원 시작을 확인하며 checkpoint 자체의 생성 시각·별도 최신 목록·실행 바이너리/연속 관측 증명은 아직 아니다. 이후 나머지 최종 인수 계약·공급자 선정 후 외부 장애복구·최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) + High 추천(시간/서명·독립 최신성·실패/부분/최종 판정 경계). 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_recovery.py backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_recovery_db.py backend/tests/test_gw_source_checkpoint_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
복구/CLI 순서와 키·전용 URL 전환, 새 대상 유지/격리·전체 인수 경계는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §20을 따른다. 이 문서와 표준 명령은 비공개 work 임시 harness 없이 재현 가능해야 한다. 원격 운영·타 checkout·실계정/브라우저 설정을 변경하지 않는다. 외부 공급자 미정이며 임의로 선정하지 않는다.

## 2026-10-23 GW-READY-02 45차 — 현재 원본과 복원 권한 대조 비교

- 시작 `65e4acd`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 “다음진행해줘”로 기존 GW 승인 범위의 다음 작업 하나를 수행했다. 새 GW/스키마·실계정 권한을 만들거나 바꾸지 않았다. 마지막 커밋은 `git log -1`로 확인한다.
- 기존 `recheck-restore --check-current-source`와 전용 비공개 `FS_GW_SOURCE_CHECKPOINT_DATABASE_URL`을 추가했다. 같은 물리 원본을 먼저 확인한 뒤 READ ONLY/REPEATABLE READ 거래에서 현재 정책/세대/DB head·기존 core/GW/HR 체크포인트 수집 항목을 다시 읽고 정규화 지문·변경 묶음을 대조한다. 다른 물리 원본은 수집/출력 없이 거부한다. 일반 DATABASE_URL 대체·접속 개방/권한 변경·자동 새 복원 없음.
- 기존 RESTORE_RECHECK v2가 현재 원본 관측과 복원본 제한 관측을 한 서명에 담고 기존 ACCEPTANCE 진단v4에 연결한다. 서명 키의 회사/용도·원본 RESTORE/백업/권한 대조 지문·물리 원본/대상·현재 정책/버전·15분 기한/미래30초·두 관측/발급 시각30초 범위를 검증한다. raw 계정/권한/자격 스냅샷은 내보내지 않는다. 원본 비교/변경 기록 관측을 함께 넣을 때 어느 한쪽의 미통과도 유지하는4개 조합을 추가 확인했다. 원본 관측의15분 기한도 별도로 검사한다.
- 복원본 제한이 정상이어도 원본 수집 항목/현재 기준이 다르면 BLOCKED→ACCEPTANCE FAIL이다. 원본 읽기 불가에는 sourceMeasured=false/지문·묶음·기준 null을 서명하며 변경 없음으로 추정하지 않는다. 일치도 PARTIAL이다. 원본 비교가 등록된 회사/세대의 이후 등록은 이전 v1/원본 비교 없는 관측으로 되돌릴 수 없고, 최신 인수 등록 이후의 원본 관측도 요구한다. 실패/옛 정책/원본 없는 이력을 포함하며 수집기를 우회한 발급도 API 등록에서 거부한다. 새 체크포인트와 옛 RESTORE를 섞지 않는다.
- 기존 운영 준비의 재관측 펼침 안에 원본 관측 시각·공통/GW/인사 변경 묶음·측정 불가·다음 조치를 추가했다. 정적 도움말·실회사 절차 §19를 갱신했다. 묶음은 권한/직원 건수가 아니며 전체 백업 보안 수집 범위라 다른 공간 변경도 포함할 수 있다. 두 시점만 비교하고 중간 변경 후 원복/미수집 경로·외부 HEAD의 독립 최신성·전체 수집/회수 완전성·실행 바이너리 증명/연속 감시는 하지 않는다. `admin` 이름은 회사/보안/발급 권한을 대신하지 않는다. UI 전체 완성 주장은 하지 않는다.
- 검증: 관련 단위431통과(기존 경고2), 화면/정적 도움말37통과, 프런트 타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 새 소유 PostgreSQL의 기존 재관측/변경 기록 회귀15건 통과, 새 실제 dump/암호화/격리복원→현재 원본 비교/인수 시나리오 최종1건18.50초 통과(기존 경고2). 새 시나리오에서 정상 PARTIAL·원본 core/GW/HR 변경→닫힌 복원본은 정상이어도 인수FAIL·원본/복원 물리 혼동·새 체크포인트/옛 복원 혼용·누락된 전용 URL/자동 대체 거부·연결 불가 null/종료2/0600·등록/재조회·형식 생략의 수집기/API 거부를 확인했다. 원본 READ ONLY 거래에서 실제 UPDATE 거부와 데이터 불변도 확인했다. 입력은 합성 회사이며 실회사10인 인수가 아니다.
- 실패/보정: 첫 혼합 실행은 기존15건 통과/새1건 API 요약 없음으로 실패했다(요약 추가 전 로드된 서버). 요약 반영 후 새 시나리오에서 시험 SQL이 관리자 GW 역할까지 회수해 후속 등록403이 발생했다. 관리자 권한을 우회하지 않고 합성 직원의 GW 활성/인사 계정으로 변경 범위를 좁혀 최종1건 전체를 다시 실행했다. 제품의 미통과/권한 경계는 유지했다.
- 브라우저: 제품 React+읽기 전용 합성 API 서버에서1440/390px 원본 비교 본문·다음 조치/두 시점 범위·키보드 펼침·44px 조작·가로 넘침0을 확인했다. 뷰포트 전환 중 메뉴 오버레이는 닫고 실제 본문을 다시 확인했다. 실제 API 브라우저/실기기 인수는 아니다. 임시 탭/뷰포트/서버는 정리했다. 기존 Vite5362 PID20714 listen만 재확인, API 상태 재검사/재시작 없음.
- 최종 자원 확인: 새 관측 시험 DB0·폐쇄 복원 DB0, 기존 preview DB존재를 읽기 확인했다. 생성한 시험 자원만 정리했으며 work/.env는 스테이징하지 않는다.
- 제약: 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED 유지. 외부 공급자 미정/외부 장애복구·전체 변경 수집/회수·실회사/기기/10인·최종 PASS/운영 전환·최신main 통합/전체CI·전체회귀·고정24수집 미완료/미실행이다. 스키마/마이그레이션/Excel/ERD 변경 없음. preview DB 초기화/실계정 admin·비밀번호/OTP·미리보기 정책/업무 변경 없음. 다른 checkout/main/원격push/배포 변경 없음.
- 다음: 변경 감지 뒤 새 체크포인트→새 격리 복원→신선한 원본/복원 관측→인수 재점검으로 이어지는 복구 흐름과 최신 실패 보존을 보완한다. 이후 최종 증거 계약·공급자 선정 후 외부 장애복구·통합/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(서명/최신성·실행 순서·부분/최종 판정 경계). [공식 모델 안내](https://developers.openai.com/api/docs/models/gpt-6-astra)를 확인했으며 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_source_checkpoint.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입:
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 생성한 자원만 정리한다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_source_checkpoint_db.py backend/tests/test_gw_restore_recheck_db.py backend/tests/test_gw_journal_acceptance_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
원본/복원 전용 URL·회사/용도별 키와 CLI 실행/종료값은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §19를 따른다. 명령과 절차는 비공개 work 임시 harness 없이 재현할 수 있어야 한다. 비밀·전체 로그·work/.env는 Git에 넣지 않는다. 실환경 공급자를 임의 선택하지 않는다.

## 2026-10-23 GW-READY-02 44차 — 기존 복원본 읽기 재관측·서명 인수 연결

- 브랜치 `codex/gw-company-01`, 시작 커밋 `1103353`. 사용자 “다음진행해줘”에 따라 기존 GW 승인 범위의 다음 작업 하나를 진행했다. 별도 GW/스키마를 만들지 않았다. 최종 커밋은 `git log -1`로 확인한다.
- 기존 복원 도구 `recheck-restore`에 전용 복원본 URL·물리 DB 식별 선대조·READ ONLY/REPEATABLE READ 제한 재관측을 추가했다. 백업/권한 대조 암호화 묶음과 서명 HEAD·RESTORE 원본 지문을 대조하며, 대상/명세 불일치는 거부한다. 새 DB/제한 재적용/연결 개방/일반 DATABASE_URL 대체 없음. 연결/권한/스키마 오류는 관측 없음/BLOCKED로 서명하며 측정값을 지어내지 않는다.
- 회사/RESTORE_RECHECK 키 범위·15분 유효 기한/미래30초·실행 번호·전체 원본/대상 식별/제한 집계를 서명한다. 수집기 `--restore-recheck`와 ACCEPTANCE 진단v4를 연결하고 변경 기록 관측도 함께 보존한다. 별도 인수 발급 키, 현재 정책/버전과 최신 등록 BACKUP/RESTORE를 다시 대조한다. 정상도 PARTIAL, 위반/측정 불가는 FAIL. 단독 재관측 API 등록400, 전체 인수 PASS는 거부한다.
- 새 인수 등록의 관측 유형 생략·최신 등록 이전 관측·동일 관측 실행 번호 재사용을 거부한다. 시계 허용으로 미래 관측을 허용해도 같은 관측을 반복할 수 없다. 실패/다른 정책/원본 없는 이력도 유형 판단에 포함하며 과거 성공으로 대체하지 않는다. 실제 백업/복원 연결에서 DB/실행자 시각 차이는 기존 복원 계약과 같은30초 이내만 허용하고31초 거부 단위를 추가했다.
- 기존 운영 준비의 실행 증거 영역에 최근 복원본 관측 시각·잔여 세션/인증 요청/제한·접속수/공개 접속 회수·측정 불가·지문 변화와 다음 조치를 표시했다. 관측 이후 연속 감시가 아님을 안내한다. 기존 정적 도움말·실회사 절차 §18을 갱신했다. `admin` 로그인 이름만으로 회사/보안/발급 권한을 부여하지 않는다. UI 전체 완성 주장은 하지 않는다.
- 검증: 관련 단위412통과(기존 경고2), 화면/정적 도움말34통과, 타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 새 소유 PostgreSQL의 백업/복원/변경 기록 확장 회귀22통과177.33초, 이후 관측 재사용/실CLI 보강 최종3통과42.74초(각 기존 경고2). 22건에는 보강 이전의 같은3건이 포함되므로 서로 다른25건으로 합산하지 않는다. 실제 dump/암호화/권한 대조/격리복원, 재관측 PARTIAL/잔여 세션 FAIL/연결 불가 null·격리 유지/다른 물리 대상 거부·0600 새 출력/덮어쓰기·URL 대체 거부, 현재 수집CLI(v4+선택적 변경 기록)·API/최신 실패 무효화를 확인했다.
- 실패/보정: 최초 단위의 BLOCKED 합성 관측에서 상태 지문 갱신을 빠뜨린 시험 준비를 보정했다. 최초 실제 연결2실패는 DB/실행자 시계 비교를 기존30초 계약으로 맞춰 해결했다. 후속 연결 불가1실패는 실행자 시각이 직전 DB 등록보다 앞선 상태였으며 재사용 방지 규칙은 유지하고 등록 시각 이후 새 관측으로 시험했다. 실CLI 보강 중 시험이 PARTIAL 종료값을2로 잘못 예상한2실패는 기존 수집기 성공0 계약대로 보정했고 최종3건을 재실행했다. 제품 권한/미통과 경계를 우회하지 않았다.
- 최종 자원 확인: 새 관측 시험 DB0·폐쇄 복원 DB0, 기존 preview DB존재를 읽기 확인했다. 이 실행에서 만든 시험 자원만 정리했다. 변경 기록 기존 회귀12건도 재사용 보강 코드에서 통과했다(혼합 실행은 시험 종료값 예상 오류2건으로 실패했고 해당2건 포함 최종3건을 다시 실행했다).
- 제약: 서버는 최신 서명/등록 원본을 재검증하며 복원 DB를 직접 조회하거나 연속 감시하지 않는다. 원래 복원 권한 대조 이후의 미수집 변경/최신성·전체 회수 완전성, 실외부 공급자/장애복구·실회사/기기/10인 인수·최종 전환은 아직 미확인이다. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED 유지. 이번 실제 API 브라우저/모바일 시각 검증·전체CI/전체회귀·고정24수집은 미실행이다. 스키마/마이그레이션/Excel/ERD 변경 없음. preview DB 초기화/실계정 admin·비밀번호/OTP·미리보기 데이터/정책 변경·API/Vite 재시작 없음. 다른 checkout/main/원격push/배포 변경 없음.
- 다음: 원래 복원에 사용한 권한 대조 이후 새 변경을 감지하는 현재 원본/최신 체크포인트 대조 계약·읽기 어댑터를 진행한다. 이후 최종 인수 계약·공급자 선정 후 외부 장애복구·최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(현재성/권한 회수·신뢰 범위/실패 유지 경계). 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_restore_recheck.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인 후 새 UUID *_test DB만 생성해 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER를 비공개 주입한다.
# 기존 gw_preview_test는 절대 초기화/시험하지 않는다. 예전 시험DB를 재사용하지 않는다.
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_restore_recheck_db.py backend/tests/test_gw_journal_acceptance_db.py backend/tests/test_gw_backup.py backend/tests/test_backup_journal_restore.py backend/tests/test_gw_restore_observation_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend run typecheck
python3 tools/validate_db_design.py
uv run --project backend python tools/audit_schema_isolation.py
```
운영 CLI의 전용 접속/키 용도 전환·일부/미통과 종료값과 다음 조치는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §18을 따른다. 시험은 새 소유 자원만 정리한다. 비밀·전체 로그·work/.env는 Git에 넣지 않는다. 이 인계는 비공개 임시 harness 없이도 위 명령과 운영 절차로 재현 가능해야 한다. 최종 자원 점검은 위 완료 기록을 따른다.

## 2026-10-23 GW-READY-02 43차 복원 직후 제한·세션 회수 관측과 서명 인수 연결

- 시작 `2260c79`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 기존 승인 범위에서 실제 복원 직후의 제한 재대조 어댑터를 추가했다. 기존 GW/암호화 백업·격리 복원 도구 확장이며 별도 GW/새 DB 스키마를 만들지 않았다. 외부 저장소 미정과 실회사10인/최종 PASS 미완료를 유지한다.
- core/GW/HR 소유 backup 어댑터에 읽기 비교를 추가했다. 백업 원본과 최신 권한 대조 모두에 허용된 활성 계정/역할·멤버십·직원/조직·연결/열람자·근무 계정만 허용하고 더 강한 비활성/회수는 인정한다. 공통 자격/보안 버전·MFA/OTP 단계·복구/SSO·시도 제한, GW guard 차이/변경 기록 격리의 연결 중지/보존 중지와 위임 회수도 대조한다. 복원 제한 적용 함수의 성공 표지를 그대로 서명하지 않고 커밋 뒤 별도 READ ONLY/REPEATABLE READ 거래에서 실제 세션/인증 요청과 잔여 권한을 읽는다. 문장15초/잠금3초, DB/운영자 시각 차이30초를 적용한다. 기존 복원/권한 재적용 정책·업무 경계는 바꾸지 않았다.
- 복원 진단v2/executionObservation/RESTORED_CHECKPOINT_RESTRICTIONS 추가. 백업/권한 대조 runId·명세/암호화 파일 지문·서로 다른 원본/복원 물리 식별·관측 시각/시계 허용 범위·상태 지문·PUBLIC CONNECT/접속수0·남은 세션/인증 요청/불일치 집계를 RESTORE 서명에 묶는다. 실제 자격 지문·계정·스냅샷·DB URL/이름을 제품 증거로 내보내지 않는다. 기존 v1은 유지하고 없는 관측을 추정하지 않는다. 새 증거는 쓰기 전에 계약을 자체 검증한다. 관측 PARTIAL도 revocationsComplete/currentTargetStateVerified/liveCompanyAcceptance/releaseAuthorized=false이며 RESTORE PASS로 승격할 수 없다.
- 기존 ACCEPTANCE가 최신 RESTORE 원본 전체를 지문으로 참조하므로 새 관측도 함께 연결된다. 관측 backupRunId와 실제 참조 BACKUP 실행 번호도 대조한다. 변조/다른 실행·최신 실패·원본 없음/옛 기준을 과거 성공으로 대체하지 않는다. 관측은 RESTORE 실행자 신뢰 아래 있고 인수 발급은 기존 별도 키 용도를 유지한다. 독립 관측자 증명은 아니다. 적용 뒤 실제 관측이 BLOCKED면 서명 RESTORE FAIL/비공개 FAIL 보고를 남기고 새 DB의 연결을 추가 차단한다. 관측 이전 오류/측정 불가능은 기존 격리 실패 보고만 남기며 측정값을 지어내 서명하지 않는다. 자동 등록은 하지 않는다.
- 기존 운영 준비의 최근 복원 검사 내용에 복원 직후 관측 시각·세션/인증 요청·제한 불일치와 범위 안내를 추가했다. 직관성은 기존 실행 영역, 유효성은 서명/현재 원본 대조, 학습성은 관측 시점·다음 점검 안내/정적 도움말, 유연성은 기존 펼침·키보드/모바일 구성을 따른다. factory-impeccable 기준을 유지했다. 실행 시점 관측이며 현재 복원본을 제품 API가 다시 조회한 것은 아니다. 이후 상태 변경의 신선한 재관측/격리 검증 어댑터는 다음 작업이다. 화면 전체 완성을 주장하지 않는다.
- 검증: 관련 단위387통과(기존 경고2), 화면/정적 도움말32·타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 별도 새 소유 PostgreSQL에서 실제 dump/암호화/사본/권한 대조/격리 복원과 API 인수 연결 최종7통과105.36초(기존 경고2). 실제 세션·GW 연결·HR 권한/공통 역할 재활성화, PUBLIC CONNECT/접속수 변경을 재관측해 BLOCKED, 읽기 거래의 UPDATE 거부와 제한 적용 함수의 잘못된 성공 표지 이후 서명 FAIL/연결 차단/최신 등록 FAILED를 확인했다. 기존 기록 이력/폴더 교체 복원2건과 실제 이전 세션/회수 업무 거부도 포함한다. 7건을 실회사10인 인수나 전체 CI로 표현하지 않는다.
- 실패와 보정: 최초5건 중1건은 새 관측의 DB/운영자 시각을 엄격히 같은 실행 구간으로 비교해 API400, 이후 진단 자체 검증에서 같은 오류를 재현했다. 기존 복원 시계 허용30초를 새 계약에 명시하고 경계 단위를 추가해 실제 복원1건13.36초 통과. 후속7건 중1건은 합성 DB에 공통 역할 행이 없는데 미부여 조합을 가정한 시험 준비 오류였다(나머지6통과). 새 복원본에 합성 역할을 만들고 시험 뒤 제거하도록 보정했으며 최종7건을 재실행했다. 제품 제약/계정을 우회하지 않았다. 실패 실행에서 남은 제한 복원본3개는 소유 컨테이너·이름/표식·접속수/연결 없음과 이 실행 생성 시각을 정확히 대조해 정리했다. 다른 DB를 정리하지 않았다.
- 브라우저: 실제 제품 React+읽기 전용 합성 API 서버(5364)로 1440px 키보드 펼침,390px 본문/범위 안내·가로 넘침0을 확인했다. 중간 크기 전환 뒤 비상호작용 제목 클릭이 다른 메뉴를 열어 그 화면은 증거로 쓰지 않았고, 새390px 탭에서 올바른 운영 준비 주소와 본문을 다시 확인했다. 실제 API 브라우저/실기기 인수가 아니다. 임시 서버·탭·뷰포트 정리. 새 시험DB/폐쇄 복원DB 남음0·preview DB존재를 읽기 확인했다. 기존 preview DB 초기화/실계정 admin·비밀번호/MFA·미리보기 정책/업무 변경 없음. API/Vite 재시작 없음. 스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·고정24수집/실외부 저장소/실회사·기기/10인 실인수 미실행. 다른 checkout/main/원격push/배포 변경 없음.
- 다음: 복원 관측 이후의 현재 복원본 상태/신선한 관측·격리 상태 재검증을 별도 읽기 어댑터로 연결한다. 그 뒤 나머지 최종 증거 계약·공급자 선정 후 외부 장애복구·최신main 통합/전체회귀·실회사10인/최종전환. ready=false·실제 복원 PARTIAL·최종4조건 UNVERIFIED는 그대로다. 난이도 매우 높음, GPT-6 Astra + High 추천(현재성/격리·물리 원본·실행자 신뢰/최신 실패·복원 접근 경계). 모델 자동변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_restore_restriction_comparison.py backend/tests/test_gw_restore_observation.py backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인·새 *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_backup.py backend/tests/test_backup_journal_restore.py backend/tests/test_gw_restore_observation_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
```
새로 만든 시험 DB만 정리하고 기존 gw_preview_test를 초기화하지 않는다. 운영 계약은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §17. 비밀번호/OTP/키/전체 로그/work를 Git에 넣지 않는다. 마지막 커밋은 `git log -1`.


## 2026-10-23 GW-READY-02 42차 서명 관측의 인수 수집·등록·현재 준비 조회 연결

- 시작 `49b9d57`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 기존 승인 범위에서 41차 서명 관측을 기존 ACCEPTANCE 흐름에 연결했다. 별도 GW/새 스키마·권한을 만들지 않았다. 외부 저장소 미정이며 실제 회사/기기/10인 인수와 최종 PASS는 미완료다.
- 진단v3/CURRENT_REGISTERED_SOURCES_AND_JOURNAL은 최신 BACKUP/RESTORE 원본 참조와 서명 관측 원본 전체를 인수 서명/명세 지문 안에 묶는다. 기존 v1/v2 지문·과거 조회를 유지한다. 중첩 관측의 회사·세대·정책/context·제품/DB·15분 시각·회사/용도별 관측 서명을 별도 검증하고 4개 runId 재사용/모르는 필드·PASS 승격을 거부한다. 관측 PARTIAL은 인수 PARTIAL, 관측 BLOCKED는 인수 FAIL로 보존하며 최종4조건 UNVERIFIED/실제 복원 PARTIAL/ready=false를 유지한다.
- 현재 DB 수집기에 --journal-observation 추가. 기존 전용 읽기 DB/새0600 출력·발급 키 분리를 사용하고 관측 개인키는 요구하지 않는다. 현재 DB 서명 수집에서만 허용하며 파일 쌍/사본과 혼용하지 않는다. PARTIAL/종료0, FAIL/종료2, 오류/종료1. 자동 등록/DB 변경은 없다. 일반 admin 이름은 권한·서명 신뢰를 대신하지 않으며 실제 계정/비밀번호/MFA를 변경하지 않았다.
- 등록과 준비 재조회는 현재 DB에서 관측 접두부의 물리 원본/타임라인·감사/거래 결과·집계를 재검증한다. 등록 자체의 기록으로 즉시 무효화되는 순환을 피하기 위해 이후 체인은 같은 회사/세대의 정확한 gw.operating_evidence.record·DB 감사 확인·물리 거래 근거가 모두 있는 등록 영수증만 허용한다. 다른 업무/회사/core 변경·취소/진행 중/근거 없는 등록·접두부 누락/변조/감사 삭제는 차단한다. 빈 관측은 FAIL이다. 수동 지문은 등록 영수증까지 검증한 뒤 운영자가 갱신해야 하며 오래된 핀을 자동 신뢰하지 않는다. 파일/DB의 무기한 원자성을 주장하지 않고 검증 도중 변경과 다음 조회의 현재성을 대조한다.
- 관측 원본과 실패를 기존 불변 운영 실행 이력에 보존한다. 새 관측은 결과/정책/버전/원본 유무로 필터하지 않은 마지막 ACCEPTANCE 등록보다 뒤여야 한다. 같은 S에 v3 이력이 있으면 새 v1/v2/관측 없는 인수 등록도 거부해 미통과를 숨기는 역행을 막는다. 최신 실패·원본 없는 기록·옛 기준/변조를 과거 성공으로 대체하지 않는다. 등록하지 않은 운영자 파일 전체의 실행 순서/실패 이력을 아는 별도 수집 원장은 아니다.
- factory-impeccable 지침으로 기존 실행 증거 영역 안에 현재 재대조된 관측의 펼침 상세(시각·대상/감사 확인/취소/미확인/거래 근거 없음·다음 조치)를 추가했다. 무효한 관측 집계는 정상 상세로 노출하지 않는다. 직관성은 기존 회사 업무 맥락/같은 영역, 유효성은 서버 현재 대조, 학습성은 범위/조치와 정적 도움말, 유연성은 접힘/키보드/모바일을 적용했다. 화면 전체 최종 완성을 주장하지 않는다.
- 검증: 관련 단위332통과(기존 경고2). 별도 새 소유 PostgreSQL/ASGI/실CLI 고유34개 검사 통과: 최초 연결/기존관측/원본대조32건198.91초, 빈체인 추가1건9.12초, 형식 역행 차단 보완 후 연결/원본21건182.22초 재실행·최종 CLI 정상/FAIL 2건23.08초(정상은 재실행). 중복 회귀를 별도 신규 건수로 합산하지 않는다. 새 등록/재조회·최근 미통과/원본 없음 우선·키 회수/변조·취소/진행 중 영수증·단독 관측400·옛 관측/옛 형식 재등록 거부·개인키 분리/0600/덮어쓰기 거부·0/2 종료 분기를 확인했다. 입력 백업/복원은 합성 서명 주장으로 실dump/복원이나 실회사 인수를 대신하지 않는다.
- 화면/정적 도움말31·타입·수정 ESLint/Prettier·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 실제 제품 React와 읽기 전용 합성 응답 서버(5364)에서 1440/390px 관측 펼침/키보드·44px 조작·가로 넘침0을 확인했다. 실제 API 브라우저 인수는 아니며 임시 서버/탭/뷰포트는 정리했다. 기존 Vite5362 PID20714의 listen만 재확인했고 API 실행 상태는 재검사/재시작하지 않았다. 새 시험DB만 정리하며 preview DB 초기화 없음. DB스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·고정24수집/실dump복원 재실행·실외부 저장소/실회사·기기/10인 실인수 미실행. 다른 checkout/main/원격push/배포 변경 없음.
- 다음: 접속 제한 복원본의 권한 제한 재적용·세션 회수 관측을 최신 원본/서명 인수에 연결하는 유형별 실행 어댑터를 이어간다. 전체 수집/PASS와 실환경 인수 경계는 유지한다. 이후 나머지 최종 증거 계약·공급자 선정 뒤 외부 장애복구·최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(복원/현재 권한·서명·최신 실패와 부분/최종 판정 경계). OpenAI 공식 모델 사양을 확인했으며 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_journal_acceptance.py backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인·새 *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_journal_acceptance_db.py backend/tests/test_gw_journal_observation_db.py backend/tests/test_gw_acceptance_sources_db.py -q --tb=short
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/gw/operations.test.tsx src/portal/content-pages.test.tsx --maxWorkers=2
```
새 시험 DB만 정리하며 기존 gw_preview_test를 초기화하지 않는다. 운영 절차/수동 지문 갱신은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §16. 비밀/전체로그/work를 Git에 넣지 않는다. 마지막 커밋은 `git log -1`.

## 2026-10-23 GW-READY-02 41차 회사 GW 변경 기록 서명 관측·현재 재검증

- 시작 `6261374`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 최신 실제 상태/인계와 기존 설계를 대조하고 외부 저장소 미정에서 자동 검증할 수 있는 현재 회사 변경 기록 관측 계약/실행 어댑터를 구현했다. 기존 GW/운영 도구 확장이며 별도 GW를 만들지 않았다.
- `journal_observation`의 JOURNAL_OBSERVATION/GW_COMPANY_JOURNAL_SCOPE_V1 계약 추가. 현재 회사/활성 세대·정책/기준 지문·실DB head·물리 DB·끝/선택 기록 지문·DB 관측 시각·집계를 서명한다. 기록은 메타데이터로만 읽고 gw.company.intent.v2 중 해당 S만 선택한다. 다른 회사/세대·HR/core/과거 계열과 수집되지 않은 변경은 전체 수집으로 인정하지 않는다. 출력에 원문/계정/처리자·DB URL/경로·키/다른 범위 집계를 넣지 않는다.
- 단일 READ ONLY/REPEATABLE READ DB 거래에서 실제 감사 지문·PostgreSQL 거래 결과를 대조한다. 같은 물리 원본/타임라인 근거가 없는 기록, 진행 중/감사 없는 커밋/미확인/대상 없음은 BLOCKED. 대상 전부가 감사 확인 또는 실제 롤백이고 거래 근거도 갖췄을 때만 PARTIAL이다. 관측 전후 최신 지문 변화는 오류다. 코드 버전은 운영자 입력이므로 executionRevisionVerified=false, 전체 수집/회수/실회사/전환/보관 독립성/ready는 항상 false다.
- 기존 gw_identity_journal CLI에 --signed-observation/--verify-observation 추가. 전용 비공개 FS_GW_PREFLIGHT_DATABASE_URL, 현재 설정과 일치하는 --expected-head, 명시적 회사/JOURNAL_OBSERVATION 키 용도가 필요하며 모든 모드에서 무범위 키를 거부한다. 발급은 새0600 파일, 재검증에는 발급 개인키 불필요. PARTIAL/종료0, BLOCKED/종료2, 오류/종료1. 기존 검사 옵션과 혼용을 거부하고 일반 DATABASE_URL을 자동 사용하지 않는다. 기존 검사 경로는 유지한다.
- 단순 verify는 서명/범위/제품/15분 기한만 확인한다. verify_current는 새 DB/암호화 기록/현재 키 권한/기준/집계까지 대조한다. 정책/물리DB/키/감사/거래 상태·끝 지문이 바뀌면 과거 파일을 검색해 대신 통과시키지 않는다. 관측 실행 이력의 최신 등록 저장/선택과 기존 ACCEPTANCE 수집/등록/재조회 연결은 다음 작업이다. 현재 파일은 제품 실행 증거 API가400으로 거부한다. 전체 인수 PASS·ready=false/최종4조건 미확인·실제 복원 PARTIAL은 그대로다.
- 검증: 관련 단위315통과(기존 경고2). 새 소유 PostgreSQL/ASGI·실CLI/기존 기록 회귀13통과113.72초, 회사/세대 제외·관측 도중 지문 변경 추가2통과17.45초(각 기존 경고2), 총15개 별도 검사. 실제 커밋/롤백/진행 중·감사 없는 커밋/삭제·거래 근거 없는 기록·정책/지문/변조·서명/현재 재검증·API 오등록400/최종4조건 유지·실CLI 비공개 새 출력/덮어쓰기 거부/개인키 없는 재검증·PostgreSQL 쓰기 거부·다른 범위 원문 비노출을 확인했다. 새 시험DB만 정리, 관측 시험DB0·preview DB존재 읽기 확인. 합성 회사의 실제 기록 검증이며 실회사/기기/10인 인수가 아니다.
- 도움말18·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·고정24실수집/실dump복원 재실행·브라우저/실외부 저장소/실회사·기기/10인 실인수 미실행. 실제 계정/admin·비밀번호/OTP/키·미리보기 정책/업무 데이터 변경 없음. 다른 checkout/main/원격push/배포 변경 없음.
- 다음: 서명 관측의 현재/최신 원본 대조를 기존 ACCEPTANCE PARTIAL 수집·등록·준비 재조회에 연결하되 전체 수집/PASS로 승격하지 않는다. 이후 나머지 유형별 실환경 어댑터/최종 인수 계약·공급자 선정 뒤 외부 장애복구·최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(서명/현재성·범위·부분/최종 판정 경계). 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_journal_observation.py backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인·새 *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_journal_observation_db.py backend/tests/test_gw_identity_journal.py -q --tb=short
```
새 시험 DB만 정리하며 기존 gw_preview_test를 초기화하지 않는다. 운영 절차는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §15. 비밀/전체로그/work를 Git에 넣지 않는다. 마지막 커밋은 `git log -1`.

## 2026-10-20 GW-READY-02 40차 회사·용도별 서명 신뢰와 인수 발급 키 분리

- 시작 `641eb00`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 다음 진행 승인 범위에서 기존 실행 증거의 서명자 권한을 회사/용도로 제한했다. 실환경 관측 어댑터나 최종 PASS를 완료했다고 표현하지 않는다.
- `evidence_trust`에 배포자 소유 FS_GW_EVIDENCE_KEY_SCOPES v1 도입. 공개키 이름과 정확히 같은 키 집합·명시적 회사ID 문자열/용도를 요구하며 와일드카드·중복 JSON/회사/용도·형식/모르는 필드·별칭 공개키를 거부한다. ACCEPTANCE_RECONCILIATION 발급 키는 다른 용도를 혼용하거나 원본 실행 키와 같은 공개키 바이트를 쓸 수 없다. PUBLIC_DEMO/TEAM_TEST에서만 미설정 기존 방식 호환, COMPANY는 미설정 오류이며 명시하면 모든 모드에서 적용한다. 실제 환경/계정/키를 자동 변경하지 않았다.
- 서버 증거 등록/준비 재조회·원본 대조, 수집기/현재DB 어댑터, 백업/복원/권한 대조/오프라인 사본 검사가 공통 신뢰 정책을 읽는다. 서명이 맞아도 다른 회사나 용도면 거부한다. 허용 용도는 BACKUP/RESTORE/CHECKPOINT/ACCEPTANCE_RECONCILIATION/INCIDENT이며 최종 PASS/미래 어댑터 권한을 문자열로 추가할 수 없다. 회사 모드 설정 부족/오류는 CONFIG_REQUIRED/503, 도구는 오류로 종료한다.
- 백업 내부 명세와 권한 대조/최신 지문에 회사 권한을 대조한다. 새 권한 대조/최신 지문은 회사·세대·정책 지문3필드만 보관하며 정책 원문/담당자를 추가하지 않는다. 엄격 모드에서 옛 무범위 권한 대조를 거부하고 백업과 다른 범위도 거부한다. 새 격리 DB 생성 전에 RESTORE 실행자 권한을 확인한다. 기존 파일을 수정/덮어쓰지 않는다.
- 서버가 현재 키/용도/회사 회수를 재평가해 이전 등록도 무효 처리하고 과거 통과로 대체하지 않는다. 기술적 키 분리는 별도 사람/장애 영역·실제 개인키 보관 분리/발급 당시 신뢰 이력 증명이 아니다. admin 로그인/GW 역할은 서명 권한과 별개이며 실제 키 분배·회수 인수는 남는다. ready=false·실제 복원 PARTIAL·최종4조건 미확인·ACCEPTANCE PASS 거부를 유지한다.
- 검증: 관련 단위287통과(기존 경고2), 도움말18·Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 별도 소유 PG에서 회사/용도·키 회수/별칭·실제CLI 및 실제 dump/암호화/사본/격리복원14통과91.22초. 권한 대조의 최소 범위/다른 세대 지문 거부 검사를 추가한 최종 백업·복원5건도51.54초 통과(기존 경고2). 최초14건 중 백업/복원5건을 보완 후 재실행한 것이며19개 별도 검사로 합산하지 않는다. 원본 사본 전체읽기·복호화·덤프/명세·옛 세션/회수 권한 거부·원본 유지·실패 복원 격리 유지와 다른 범위 거부 전후 새 격리 DB 미생성을 확인했다. 생성한 시험 자원만 정리·trust 시험DB0/폐쇄복원DB0·preview DB존재를 읽기 확인했다. 스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·고정24수집 재실행·브라우저/실외부 저장소/실회사·기기/10인 실인수 미실행.
- 다음: 유형별 실환경 관측 자료와 검증 어댑터·최신 원본/현재 신뢰 정책을 묶는 최종 인수 계약을 이어간다. 외부 공급자는 미정이며 선정 뒤 장애 영역/키 보관/복구를 실제 검증한다. 이후 최신main/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천. 모델 자동변경 없음. 다른 checkout/main/원격push/배포 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_evidence_trust.py backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 확인·새 *_test DB에만 동일 DATABASE_URL/TEST_DATABASE_URL과 소유 GW_BACKUP_TEST_CONTAINER 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_evidence_trust_db.py backend/tests/test_gw_backup.py backend/tests/test_backup_journal_restore.py -q --tb=short
```
새 시험 DB만 정리하며 preview DB 초기화/실제 계정·비밀번호/OTP/키 변경 없음. 운영 설정 계약: `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §14. 비밀/전체로그/work를 Git에 넣지 않는다. 마지막 커밋은 `git log -1`.

## 2026-10-20 GW-READY-02 39차 현재 DB 최신 원본 선택·서명 대조 계약v2

- 시작 `1cf68ee`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 다음 진행 승인 범위에서 현재 DB 원본 선택 어댑터를 구현했다. 최종 PASS/실환경 인수 완료를 구현했다고 표현하지 않는다.
- `acceptance_preflight`의 입력 검증/REPEATABLE READ·READ ONLY 거래를 재사용해 `acceptance_sources.sign_current`에서 같은 스냅샷의 현재 회사/세대·정책 원본·DB head와 최신 BACKUP/RESTORE 등록행을 조회한다. 최신순은 recorded_at/id이며 결과/정책/버전 성공 필터와 과거 성공 fallback이 없다. 원본 서명/등록행·현재성·동일 manifest를 대조한다. 최신 RESTORE PARTIAL을 PARTIAL로 참조하고 BACKUP PARTIAL/실패/원본 없는 행·변조/옛 기준은 거부한다.
- 기존 CLI에 `--current-company-id --signed-reconciliation` 경로와 전용 비공개 FS_GW_PREFLIGHT_DATABASE_URL·FS_CODE_REVISION 연결을 추가했다. 파일 선택/사본 옵션과 혼용·unsigned 현재DB 출력을 금지하고 기존 파일 방식을 유지한다. 출력 전 기존 파일/링크를 거부하며 키/URL/SQL 오류 세부를 출력하지 않는다. DB 변경·증거 자동등록 없음. 기본 admin은 읽기 조회 이름일 뿐 본인 확인/역할·10인 준비 통과를 뜻하지 않는다.
- ACCEPTANCE PARTIAL 진단v2/CURRENT_REGISTERED_SOURCES에 DB 관측 시각·현재 기준 contextDigest와 최신 원본 참조를 서명한다. 기존 진단v1 계약/지문을 유지한다. 원본 등록이 관측보다 늦거나 실행 시작과 관측 불일치·현재 기준 지문/회사/정책/버전 불일치·알 수 없는 필드·PASS/다른 종류 승격을 거부한다. 등록/준비 조회에서 실제 최신 원본 재대조. UI는 기존 일부 확인 설명에 DB 관측 대조임을 표시하며 도움말을 갱신했다. 화면 전체 구성 완성을 주장하지 않는다.
- 새 실패가 수집 도중 확정되는 경합은 읽기 스냅샷에서 과거 관측이 일관돼도 서버 등록/기존 기록 재조회에서 거부해야 한다. 출처는 신뢰하는 실행자/읽기 DB/서버 최신 원본 경계이며 DB 독립 감사 서명·배포 소스/실회사 증명은 아니다. ready=false·실제 복원 PARTIAL·최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부를 유지한다.
- 검증: 관련 단위258통과(기존 경고2)·도움말18통과·정적DB219/2409/543·R1–R6 오류0. 별도 새 소유 PostgreSQL/HTTP/실CLI 최종26통과139.84초(기존 경고2). 최신 실패/새PARTIAL/새PASS·원본 없음/변조·정책/버전·실CLI 새0600 출력/덮어쓰기 거부·PostgreSQL 자체 쓰기 거부와 기존v1/사전점검 회귀를 확인했다. 수집 도중 다른 거래가 실패 원본을 확정하면 기존 읽기 스냅샷은 일관되지만 실제 등록400·기존 대조INVALID·새 수집 거부가 됨을 확인했다. 처음25통과 뒤 경합 검사와 관측 시각/기준 지문 검증을 보완한 최종26을 재실행했다. source의 서명 입력은 합성 주장으로 실제 백업/복원·실회사 검증을 대신하지 않는다. 생성한 시험DB 정리·남은 sources 시험DB0/preview DB존재를 읽기 확인했고 미리보기 초기화/실계정·비밀번호·정책 변경 없음. DB스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·고정24실수집 재실행·브라우저·실외부 저장소·실회사/기기/10인 실인수 미실행.
- 다음: 최종 실환경 인수 자료의 유형별 실행 어댑터/관측 출처·서명자 신뢰 분리와 최종 PASS 계약을 이어간다. 외부 저장소 공급자는 미정이며 선정 뒤 연결/장애복구 검증. 이후 최신main 통합/전체회귀·실회사10인/최종전환. 난이도 매우 높음·GPT-6 Astra + High 추천, 모델 자동변경 없음. 다른 checkout/main/원격push/배포 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_sources.py backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 포트 대조·새 *_test DB 생성/동일 DATABASE_URL·TEST_DATABASE_URL 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_acceptance_sources_db.py backend/tests/test_gw_acceptance_evidence.py backend/tests/test_gw_acceptance_preflight_db.py -q --tb=short
```
시험 뒤 생성한 DB만 정리하며 gw_preview_test를 초기화하지 않는다. 운영자 실행은 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §13. 비밀번호/OTP/키/전체로그/work를 Git에 포함하지 않는다. 마지막 커밋은 `git log -1`.

## 2026-10-20 GW-READY-02 38차 사전점검·합성10인 MFA/대표 업무 실행 연결

- 시작 `bbd7fbf`, 브랜치 `codex/gw-company-01`, 시작 작업 트리 깨끗함. 사용자 다음 진행 승인에 따라 기존 수집기에 합성10인 실행 어댑터를 추가했다. 외부 저장소 미정은 유지한다. 실제 인수 PASS를 만들지 않는다.
- 기존 ten_people/새 소유 시험DB 준비를 재사용한 `test_gw_business_probe` 추가. 새 합성 관리자만 admin으로 맞춘다. 실제 등록/확인 API로10명 TOTP 등록·옛 세션401·비밀번호202 도전/다음 미사용 OTP201·정상 업무 연결·GW 보안관리자1/직원9를 확인한다. 키/계정/세션/시계 검증을 모의 통과시키지 않았다. 실제/미리보기 계정 변경 없음.
- 현재 사전점검 PARTIAL 뒤 직원9명 기안→관리자 승인·게시/다른 직원 조회·댓글·일정 참석·알림 읽음,10명 채팅/같은 키 재시도, 직원 관리기록403/타직원 초안404를 실행한다. 최종 사전점검 PARTIAL과 현재 기준 전후 지문 일치·제품 ready=false 확인. 실제 PostgreSQL과 in-process ASGI API이며 네트워크/TLS·브라우저/기기/실회사 사용·동시 부하 검증이 아니다.
- `SyntheticBusinessObservation`는 합성 범위·현재 runId·회사/세대/정책/contextDigest·코드/DB·실행 시각·고정 수를 제한한다. bool과 int/float를 같은 값으로 허용하지 않는다. 수집 카탈로그V5 고정24검사에 연결하고, 전체 성공 JUnit의 정확한 검사/속성1개만 읽는다. 누락/중복/실패/생략·옛 실행/버전·미래/역전/무시간대·모르는 필드·완료 표지 위조를 거부한다. 전후 소스 변경 시 관측 제외/BLOCKED. 기존 결과 재사용/덮어쓰기 없음. 새 계약 파일도 미추적 상태부터 실행 소스 지문에 포함한다.
- unsigned 합성 관측이며 제품 ACCEPTANCE 등록/서명 인수 자료가 아니다. 실제 복원 PARTIAL·ready/liveCompanyAcceptance=false·외부/전체수집/실회사/최종전환4조건 미확인·최종PASS 거부는 유지한다. 최종 실환경 어댑터/PASS 계약 개발은 아직 남는다.
- 검증: 관련 단위232통과(기존 경고2), 별도 새 소유DB의10인 MFA/업무 직접 실행1통과26.45초. 첫 실행은 생성 응답201을200만 기대해1실패 후 테스트 계약 보정. 관측 단위 첫 실행은 bool을정수1로 인정한1실패를 발견해 엄격 형식을 추가한 뒤 통과했다. 최종 고정24실수집 전부PASSED·PARTIAL/exit0·118.10초, sourceUnchanged/databaseCleaned=true·합성 복원 거부 통과. 현재 실행/커밋/DB와 합성10인 관측의 동일성·기준 전후 지문·정해진 작업 수를 결과 파일에서 다시 대조했다. 종료 후 collector/폐쇄복원/10인자식DB0·preview DB존재를 읽기 확인했다. 시험DB만 정리했으며 preview 초기화/실계정 변경 없음. 단독 실행의4경고와 단위의 기존2경고는 통과 수와 구분한다. Ruff check/format·정적DB219/2409/543·R1–R6 오류0. UI/도움말 변경·스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·실외부/실회사/기기/10인 실인수 미실행.
- 다음: 실제 인수 자료의 신뢰하는 실행/관측 출처·회사/세대/정책/제품/DB·최신 원본 연결과 최종 PASS 계약을 이어간다. 공급자 어댑터는 저장소 선정 뒤 진행. 이후 최신main 통합/전체회귀·실회사10인/최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(인수 판정·최신 실패 우선·합성/실환경 경계). 모델 자동 변경 없음. 다른 checkout/main/원격push/배포 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_business_observation.py backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 소유 컨테이너ID/owner/loopback 포트 대조 후 비공개 환경 주입, 새 보고서만 지정:
uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>
```
기존 gw_preview_test를 시험 초기화하지 않는다. 수집기 새DB와10인 fixture의 새 gw_merge_*_test만 생성/정리한다. 실제 계정/비밀번호/OTP/키/전체로그/work를 Git에 넣지 않는다. 상세 실행 범위: `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §12. 마지막 커밋은 `git log -1`.

## 2026-10-20 GW-READY-02 37차 공통 인수 사전점검·admin 권한 기준

- 시작 `bdd3e02`, 브랜치 `codex/gw-company-01`, 작업 트리 깨끗함. 사용자 질의에 운영 준비는 자동 팝업/미완료 때만 보이는 화면이 아니라 회사 GW의 상시 관리 화면이라고 설명했다. 활성 회사 소속·GW 직원 연결과 SECURITY_ADMIN/AUDITOR 역할로 메뉴를 표시하며 SECURITY_ADMIN만 변경, AUDITOR는 조회한다. 일반 직원의 직접 주소 접근은 본인 보안 안내만 제공한다. 플랫폼 ADMIN·회사 OWNER·로그인 이름 admin으로 GW 역할을 대체하지 않는다.
- 사용자 기준: 개발자 관리자 아이디 `admin`. 외부 저장소는 **미정이며 공통 사전점검을 먼저 진행**한다는 답변을 받았다. 기존 실제 계정 생성/이름 변경/권한 변경은 하지 않는다. 현재 회사3 합성 미리보기 DB에는 admin 계정이 없고 기존 합성 미리보기 계정만 회사 GW에 연결돼 있음을 읽기 전용으로 확인했다. 다른 환경의 admin 계정 유무/권한을 이 결과로 단정하지 않는다.
- `acceptance_preflight.collect`와 `tools/gw_acceptance_preflight.py` 추가. 전용 비공개 FS_GW_PREFLIGHT_DATABASE_URL을 사용하고 PostgreSQL REPEATABLE READ/READ ONLY 거래, 문장15초/잠금3초·연결10초 제한을 적용한다. 현재 활성 회사/GW 세대 준비/초기화·정책 원본 지문·DB head와 인원/부서/MFA/보안 역할/책임자를 동일 스냅샷에서 읽는다. 기본 admin 식별자는 조회 조건이며 이름으로 권한을 부여하지 않는다. 실제 업무 세션/최근 인증은 NOT_CHECKED다.
- 예정10/1부서·활성 소속/직원/연결10명·현재 활성 부서 배정·전원 MFA·활성 보안 관리자1명/그 외9명·책임자 연결·지정 관리자 GW 역할/MFA를 대조한다. 예제 표지는 DB 분류일 뿐 실제 회사임을 증명하지 않는다. 모든 사전조건이 맞아도 PARTIAL/exit0, 부족하면 BLOCKED/exit2, 오류는 exit1이다. 항상 ready/liveCompanyAcceptance/releaseAuthorized=false·대표 업무/기기·최종4조건 미확인이다. 제품/DB 실행 버전을 함께 증명한 것은 아니며 codeRevision은 운영자 환경에서 제공, executionRevisionVerified=false를 남긴다.
- 기존 수집기의5필드 현재 기준 파일과 원문/계정 식별자가 없는 집계 보고서를 서로 다른 새0600 파일로 출력하고 contextDigest로 묶는다. 정책 파일에는 담당자 식별자/사유가 포함되므로 비공개 보관한다. 기존 파일/경합 파일은 보존하고 새 파일 쌍 생성 실패 시 이 실행의 파일만 정리한다. 보고서는 unsigned이며 제품 ACCEPTANCE로 업로드하지 않는다. 서명/수동 체크/합성 결과로 최종 PASS를 발급하지 않는다.
- 검증: 관련 단위201통과(기존 경고2). 별도 새 소유 PostgreSQL의 DB/HTTP/실CLI17통과95.40초(기존 경고2). admin 이름+플랫폼ADMIN만으로 권한 승격 없음, GW역할 제거/감사 전환/회사 소속 회수·정지/미연결/비활성·옛 정책/모듈/타회사·현재 기준 갱신·실CLI 비공개 출력/덮어쓰기 거부와 PostgreSQL 자체 쓰기 거부를 확인했다. 합성 등록값으로10명/1부서/전원MFA/보안관리자1·그 외9명을 구성한 사전조건 일치도 PARTIAL/ready=false이며 실제 OTP/업무 세션·기기·실회사10인 사용을 검증한 것은 아니다. 새 시험DB를 정리했다. 처음 실검사는 상태 주입에 필요한 종료 시각 누락으로2실패, 보정 뒤 취소 상태의 활성 시각 잔존1실패였다. 실제 제품 CHECK를 바꾸지 않고 합성 준비 상태를 적법한 형태로 보정했다. 실패를 인수 통과로 대체하지 않는다. 실제 미리보기 읽기 CLI는 새 비공개 파일로 BLOCKED/exit2·연결1/MFA1/부서1/보안관리자1·지정 admin 없음 확인. 당시 checkout HEAD를 제품 기준으로 명시 주입했으며 배포/실행 버전 검증 완료는 아니다. 정책/계정/업무 데이터 쓰기 없음.
- Ruff check/format·정적DB219/2409/543·R1–R6 오류0. 도움말18통과. DB스키마/마이그레이션/Excel/ERD 변경 없음. 전체CI/전체회귀·실외부 저장소·실기기/실회사·10인 업무 인수는 미실행. 미리보기DB 초기화·다른 checkout/main 변경·원격 push·배포 없음. 비밀/전체로그/work를 Git에 포함하지 않는다.
- 다음: 현재 회사 사전점검 기준과10인 대표 업무의 실제 실행 결과를 결합하는 인수 어댑터·최종PASS 계약을 이어간다. 외부 공급자 연결은 저장소 선정 뒤 검증한다. 이후 최신main 통합/전체회귀·실회사10인 인수·최종전환. 난이도 매우 높음, GPT-6 Astra + High 추천(신뢰하는 실행/관측 범위·최신성·역할/완료 판정 경계), 일반 구현은 GPT-6.1 Sol + High 대안. 모델 자동 변경 없음.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_preflight.py backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 별도 소유 새 *_test DB를 준비하고 DATABASE_URL/TEST_DATABASE_URL을 동일하게 비공개 주입:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_acceptance_preflight_db.py backend/tests/test_gw_evidence.py backend/tests/test_gw_operations.py -q --tb=short
```
기존 `gw_preview_test`를 테스트 초기화에 사용하지 않는다. 소유 컨테이너ID/owner/127.0.0.1:55439를 대조한 새 `gw_preflight_*_test`만 생성/정리한다. 인수 도구의 실행/권한/출력 절차는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §11. 실제 계정이름·비밀번호/OTP·원문/전체로그 출력 금지. 마지막 커밋은 `git log -1`.

## 2026-10-20 GW-READY-02 36차 기존 GW 운영 준비 UI 구성 보완

- 브랜치 `codex/gw-company-01`, 시작 `6908c0f`, 시작 작업 트리 깨끗함. `factory-impeccable` 지침을 적용해 기존 GW 레이아웃 안에서 구성했다. 별도 GW/새 권한/DB를 만들지 않았다. 회사명·연결 직원은 기존 `/me` 응답에서 RoleContext로 전달하고 공간 선택은 펼침으로 표시한다. 회사 운영 안내의 현재 메뉴를 표시한다.
- 운영 준비 상단에 연결/예정 인원·MFA·관리/감사 역할과 첫 조치 항목을 두고, 회사 ID를 유지한 업무 복귀/결재함을 연결했다. 조건→실행 증거→보관·복구 기준→보관 검토→계정 복구 구획과 초점 가능한 바로가기를 추가했다. 조치 필요와 미확인을 먼저 표시하고 확인된 조건은 접어 둔다. 원본/부분 복원 진단·파일 등록·보관·정책 편집 기능을 유지한다. 긴급 복구는 필요할 때 펼치며 요청 거부 후에도 펼침/입력/오류를 유지하도록 보완했다. 감사는 조회 전용 안내·변경/복구 숨김을 유지한다.
- 직관성: 회사·GW 업무 복귀와 우선 조치. 유효성: 서버 조건/원본 판정과 기존 변경 보호 유지. 학습성: 긴 인수 근거/정적 도움말·실행 결과 설명. 유연성: 항목 이동·펼침·모바일 세로 구성을 적용했다. 백자/먹색/쪽빛 토큰·텍스트 상태를 사용하며 주요 링크/펼침44px, 본문 색 대비 최소5.56:1을 정적 계산했다.
- 검증: GW/정적 도움말 Vitest64건(10파일) 통과, 타입·수정 ESLint/Prettier·제품 빌드 통과(기존 CAD node:module 외부화/대형 chunk 경고 유지). 처음 집중 실행은 중복 안내 텍스트와 확인 조건 접힘에 대한 옛 기대값2건이 실패했으며 안내 중복 제거/펼침 기대 갱신 후 통과했다. 회사 범위 링크/이동 대상·감사 표시·복구 거부 후 오류/입력 유지 검사를 추가했다. 전체 CI·백엔드 회귀/DB 검사·전체 솔루션 브라우저 검사는 이번 미실행이다.
- 브라우저: 실제 제품 React를 쓰는 별도 읽기 전용 합성 API 응답 서버에서 1440/390 구성·가로 넘침0·부분 복원 확인/미충족/기록 없음·항목 이동을 확인했다. 이후 실제 로컬 API와 합성 계정의 기존 비밀번호/MFA 로그인으로 회사3 운영 준비를 확인했다. 실제 API에서 정책 패널 입력→취소→계속 편집의 값/초점 유지→변경 버리기, 회사 ID를 유지한 업무 현황 복귀, Enter로 확인 조건 펼침을 확인했다. 실제 API 모바일390의 본문 폭375/scrollWidth375로 넘침0, 최종 실제 화면 캡처를 보관했다. 실기기/실회사/10인 사용 검증은 아니다. 화면 의견의 최종 사용자 확인도 남아 있다.
- 환경: 세션 시작 때 이전 API94777/Vite89508은 종료돼 있었다. 기존 PG컨테이너ID/소유라벨/실행/55439 매핑을 대조하고 기존 비공개 server.env로 API `127.0.0.1:8362` PID20713·Vite `localhost:5362` PID20714를 재실행했다. 기존 합성 로그인만 사용했고 비밀번호/MFA 설정/회사 정책·업무 데이터를 변경하지 않았다. preview DB 초기화/스키마·마이그레이션·Excel/ERD 변경 없음. 실제 API의 증거 검증 키/버전 설정 미준비·예정10/연결1·ready=false/미확인4를 유지했다. 실제 외부 저장소·최종 인수·전체회귀·main 반영은 미완료, 원격 push/배포 없음.
- 다음: 실환경 인수 실행 어댑터와 최종 ACCEPTANCE PASS 계약의 남은 범위를 구현/검증한다. 독립 저장소·전체 변경/권한 회수·실회사·최종 전환의 실제 근거를 합성 결과/수동 체크로 대신하지 않는다. 이후 최신 main 통합·전체 회귀·실회사10인 인수/최종 전환. 다음 난이도 매우 높음, GPT-6 Astra + High 추천(실행자 신뢰/현재성/증거 범위와 완료 판정); UI 후속은 GPT-6.1 Sol + High. 자동 모델 변경 없음.

재현:
```sh
cd frontend
npm test -- src/gw src/portal/content-pages.test.tsx --maxWorkers=2
npm run typecheck
npx eslint src/gw/Operations.tsx src/gw/GwLayout.tsx src/gw/common.tsx src/gw/operations.test.tsx
npx prettier --check src/gw/Operations.tsx src/gw/Operations.css src/gw/GwLayout.tsx src/gw/common.tsx src/gw/gw.css src/gw/operations.test.tsx
npm run build
```
Node24 사용. 실제 미리보기 `http://localhost:5362/gw/operations?companyId=3`, 시제품 HTML과 구분한다. 계정/OTP/키/전체 로그는 출력·Git 포함 금지. 재현은 회사3의 기존 합성 계정으로 로그인하고 위 읽기/미저장 취소 동작만 수행한다. 실제 캡처는 무시되는 `work/gw-readiness-02-preview/screens-36/desktop-live.jpg`, `mobile-live.jpg`이며 문서/제품 소스가 구현 기준이다. 임시 합성 API 응답 서버5363은 검증 뒤 종료했다. 마지막 커밋 `git log -1`.

## 2026-10-20 GW-READY-02 35차 서명 인수 일부 확인·최신 원본 대조

- 브랜치 `codex/gw-company-01`, 시작 커밋 `21ff888`, 시작 작업 트리 깨끗함. 최종 인수 계약의 기반으로 `acceptanceDiagnostics` v1을 추가했다. 범위는 `BACKUP_RESTORE_RECONCILIATION`이며 백업·복원의 실행 번호와 원본 서명 문서 지문을 묶는다. 명세 지문도 대조하며 결과는 PARTIAL만 허용한다. 외부 저장소·전체 수집/회수·실회사·최종 전환은 UNVERIFIED 고정이다. 다른 검사값·임의 필드·PASS·합성 수집 보고서 대입을 거부한다.
- 기존 `gw_acceptance_collect.py --signed-reconciliation`은 현재 BACKUP PASS와 같은 manifest의 이후 RESTORE PASS/PARTIAL 원본 서명을 검증한 뒤 실행자 키로 일부 확인 기록을 발급한다. 기본 unsigned 수집 동작은 유지한다. 서명 옵션에만 기존 FS_GW_RUNNER_KEY_FILE/ID가 필요하며 현재 신뢰 공개 키와 불일치하면 출력하지 않는다. 사본 검사 옵션과 혼용하지 않는다. 새0600 출력만 허용한다.
- 등록은 현재 회사/운영 기준 잠금 안에서 종류별 최신 등록을 먼저 선택한 뒤 정책·제품/DB·범위·시각·원본 서명/등록행 전체·참조 실행 번호/지문을 다시 검증한다. 운영 준비 조회도 같은 대조를 수행한다. 최신 실패·다른 PARTIAL/성공·원본 누락·변조·옛 기준이 있으면 과거 원본으로 대신하지 않는다. 복원 PARTIAL 자체를 인수 일부 확인에서 참조할 수 있지만 기존 백업/복원 PASS 쌍이나 전체 준비 완료로 승격하지 않는다. 과거 진단 없는 PARTIAL/FAIL 형식은 기존 제한된 표시를 유지한다.
- 검증: 관련 단위178통과(기존 경고2), 별도 새 소유 PostgreSQL에서 실제 HTTP/DB11통과62.92초(새5시나리오 포함). 미등록 원본400, 직원403, 같은 요청 재전송, 새 실패/PARTIAL/성공·원본 누락/변조 뒤 조회 INVALID·옛 참조 신규등록400·등록행 불변·ready=false/미확인4를 확인했다. 이 API 검사는 합성 서명 주장으로 계약/등록을 검사하며 실제 dump/복원은 이번에 재실행하지 않았다. 소유 컨테이너ID/owner/55439대조 후 새 `gw_acceptance_*_test`만 생성·정리했다. API8362 PID94777/Vite5362 PID89508 실행 유지 확인.
- 기존 운영 화면/정적 도움말 관련 Vitest26통과(2파일). Ruff/포맷·정적DB219표2409열543FK·R1–R6·diff 검사 통과. schema 변경 없음, Excel/ERD 재생성 없음. 전체CI·실브라우저/UI외관·실외부·실회사/기기·10인 인수 미실행. preview DB 초기화·다른 checkout/main 변경·원격 push·배포 없음. 비밀/work/전체 로그를 Git에 포함하지 않는다.
- GW-READY-02 전체는 진행 중이다. 최종 ACCEPTANCE PASS 계약/실환경 실행 어댑터는 여전히 미완료다. 다음은 기존 GW 운영 준비 UI의 회사/업무/관리 맥락·업무 복귀·정보 우선순위/다음 조치·모바일 구성을 보완하고 실제 제품 브라우저에서 검증한다. 이후 실환경 어댑터·최신 main 통합/전체 회귀·실회사10인 인수와 최종 전환을 진행한다. UI 작업 난이도 높음, GPT-6.1 Sol + High 추천(모델 자동 변경 없음); 최종 증거/보안 경계 검토는 GPT-6 Astra + High 추천.

재현(저장소 루트):
```sh
uv run --project backend pytest backend/tests/test_gw_acceptance_reconciliation.py backend/tests/test_gw_route_verify.py backend/tests/test_gw_journal_routes.py backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short
# 별도 소유 새 *_test DB를 만들고 DATABASE_URL/TEST_DATABASE_URL에 동일하게 비공개 주입한 뒤:
uv run --project backend alembic -c backend/alembic.ini upgrade head
uv run --project backend pytest backend/tests/test_gw_acceptance_evidence.py backend/tests/test_gw_evidence.py backend/tests/test_gw_operations.py -q --tb=short
```
시험 뒤 생성한 DB만 정리한다. 미리보기 `gw_preview_test`는 위 명령의 대상이 아니다. 서명 발급 절차는 `docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md` §10 참조. 마지막 커밋은 `git log -1`로 확인한다.

## 2026-10-20 GW-READY-02 34차 인증 실패·만료·긴급/코드 복구 실행수집

codex/gw-company-01, 시작6bd67f0·작업트리깨끗함. 고정카탈로그 GW_SYNTHETIC_ROUTE_PROBES_V4 12→23. 기존실검사에서 OTP5회실패/잠금·새요청제한유지/기록, 요청만료/인증버전변경거부/기록, denied·expired·emergency3분기기록실패롤백, 복구코드경합/제한세션/재등록/옛코드거부, 타세션회수/코드재발급·옛세션거부, 긴급문서만료/기록, 로그아웃401/기록을연결했다. 긴급HTTP복구와역할/만료재확인에journal wrapper2개를추가해 실제승인경합/CSRF·Origin거부/업무접속차단/recoveryOnly/재등록/승인재사용401·현재권한403/만료401과DB감사확정/암호화기록을대조한다. 승인/재사용거부에필요한새기록존재·복구미실행시redeemed없음·비밀필드없음확인. 직접SQL로만든만료/역할회수준비는테스트주입일뿐자동전체수집/실인수근거가아니다.

파라미터명이달라진실행결과는해당검사를채우지못하도록JUnit wrong-param 거부단위추가. 성공도합성PARTIAL/readyfalse·실회사인수/전체revocations/completeness=false. unsigned보고서는제품ACCEPTANCE등록용아님. 실행범위/소스지문/DB버전/소유자원/실행기신뢰경계는이전과동일하다.

검증: 단위141통과0.32초(기존경고2). 소유컨테이너ID/owner/55439대조후새소유DB의실수집CLI23PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. collectorDB0/closedRestoreDB0확인·previewDB/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부/실회사·기기/10인인수 미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4유지. 다음: 최종서명인수증거계약/현재회사·세대·정책·제품/DB·실행번호/최신원본대조를연결하되 합성보고서를실회사PASS로승격하지않는경계구현 → 기존GW UI구성보완 → 최신main/전체회귀·10인실인수/실외부저장소·최종전환. 나머지HR/ACL조합·직접SQL/운영자통제·장기성능/시간동기/전경로무누락은여전히미확인. 다음난이도매우높음·GPT-6 Astra + High 추천(서명/최신성/인수범위·완료판정의신뢰경계), GPT-6.1 Sol + High 대안. 모델자동변경없음.

재현:33차단위명령그대로(141). 소유로컬PG postgres관리연결FS_GW_ROUTE_VERIFY_ADMIN_URL·GW_BACKUP_TEST_CONTAINER·FS_GW_ROUTE_VERIFY_OWNER 주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정23). 새DB만생성/정리·preview초기화금지. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 33차 연결 취소·재개·역할 부여/회수 롤백 검증

codex/gw-company-01, 시작b74d593·작업트리깨끗함. test_gw_identity_route_probes 실제PG/HTTP4시나리오추가·수집카탈로그GW_SYNTHETIC_ROUTE_PROBES_V3 8→12. 연결취소(PENDING→CANCELLED)/재개(SUSPENDED→ACTIVE), SECURITY_ADMIN부여/회수를분리. journal저장503에서 S범위연결상태/버전·person버전/역할행·authz_version·core.request_receipt불변/기록수불변·기존업무접근유지 확인. 같은request key 재시도성공→기록정확히1증가→중복요청결과/DB/기록수불변, 새key/옛버전409불변 확인. 비권한직원변경403, 취소뒤수락403/업무403·재개뒤업무200, 역할부여뒤보안이력200/회수뒤403와재변경403, 마지막보안관리자제거409불변. 새기록과원본감사확정대조. 전체회수/인수완료로승격하지않음.

source_identity가고정검증파일을git ls-files외에도명시포함하도록보강해 새미추적probe도실코드지문에포함한다. 미추적고정probe수정시커밋이같아도지문변경 단위검사추가. 실행버전/카탈로그/원본범위와합성구분유지·readyfalse/미확인4그대로.

검증: 관련단위140통과0.22초(기존경고2). 소유preview컨테이너ID/owner/55439대조·새소유DB의실수집CLI12PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. 새4시나리오와기존인증HR/ACL·실dump복원포함. 종료후collectorDB0/closedRestoreDB0확인·preview/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부/실회사·기기/10인인수 미실행. DB스키마불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중. 다음: 인증실패/만료/긴급복구·코드복구/세션회수 분기의고정실행수집확대와미검증경계대조 → 최종서명ACCEPTANCE/게이트연결 → 기존GW UI구성보완 → 최신main/전체회귀·10인실인수. 실제저장소/현재회사인수·전체수집무누락은여전히미확인. 다음난이도높음·GPT-6.1 Sol + High 추천(인증상태·일회성/세션·거래실패경계), 최종감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:32차단위명령그대로(140). 소유로컬PG postgres관리연결FS_GW_ROUTE_VERIFY_ADMIN_URL·GW_BACKUP_TEST_CONTAINER·FS_GW_ROUTE_VERIFY_OWNER 주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정12). 새DB만생성/정리·preview초기화금지. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 32차 인증·HR·ACL/실복원 실행수집 확대

codex/gw-company-01, 시작95f7e48·작업트리깨끗함. 고정수집카탈로그 GW_SYNTHETIC_ROUTE_PROBES_V2를2→8시나리오로확대: 기존GW중지롤백/403·거래판정에 MFA등록실패롤백·로그인요청issued실패롤백·비밀번호세션발급실패롤백·HR비밀번호/역할/로그인ID/중지/재시도·문서ACL저장실패롤백/기록·실제PG격리복원후옛세션/미완료인증/회수권한거부/원본유지를추가. 문서submit의journal503시 approval_document 상태/버전·기록수불변과 재시도submit/approve를 실제검사하도록보강(S회사/활성세대제한). 전체인증/HR/ACL경로수집완전성이아니라지정시나리오범위다.

GW_BACKUP_TEST_CONTAINER 설정시 FS_GW_ROUTE_VERIFY_OWNER와 docker inspect 소유라벨/실행상태/PG5432→관리URL의동일loopback포트매핑을사전대조·불일치거부. 미설정복원검사는SKIPPED→BLOCKED이며자동생략통과없음. 정확parametrized JUnit이름포함 고정검사. 전체8PASSED/정상종료/소스불변시에만 restoredAccessDenial=SYNTHETIC_SCENARIO_PASSED. 실제회사/전체revocations/completeness/ready는false·서명ACCEPTANCE아님. 복원도구/DB접속제한PARTIAL은그대로다.

검증: 단위139통과0.22초(기존경고2). 소유컨테이너ID/라벨/55439확인후 새소유DB의실수집CLI 최종8PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. 첫실행은새문서조회테이블명오류로ACL FAILED·실행중수정sourceUnchanged=false→BLOCKED/exit2·복원거부UNVERIFIED를유지했다. approval_document와활성세대로수정후소스고정재실행통과·첫보고서보존. 최종소유PG읽기조회 collectorDB0/closedRestoreDB0/preview존재true확인. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부·실회사/기기/10인인수 미실행. 스키마불변·Excel/ERD재생성없음. previewDB/서비스유지·비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4유지. 다음: GW연결취소/재개/역할변경의저장실패롤백·허용/거부실행시나리오를추가해7경로진단과대조, 인증실패/복구·HR/ACL나머지분기확대 → 최종서명ACCEPTANCE/게이트 → 기존GW UI구성보완 → main/전체회귀/10인실인수. 다음난이도높음·GPT-6.1 Sol + High 추천(상태전이·권한·DB회귀), 최종경계감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:31차단위명령그대로(139). 소유확인로컬PG postgres관리연결을FS_GW_ROUTE_VERIFY_ADMIN_URL, 컨테이너를GW_BACKUP_TEST_CONTAINER, 소유라벨값을FS_GW_ROUTE_VERIFY_OWNER에비공개주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정8실행). 복원컨테이너/DB연결일치와생성자원정리필수·preview를초기화하지않는다. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 31차 합성 경로검증 실행 수집기

codex/gw-company-01, 시작e396c1c·작업트리깨끗함. tools/gw_route_verify.py 추가: 로컬 소유PG의 postgres 관리연결(FS_GW_ROUTE_VERIFY_ADMIN_URL)로 UUID 새 *_test DB만 생성→alembic head→고정된 실제HTTP직원연결중지 저장실패롤백/직원403 및 거래취소/진행/저장점/원본불일치2시나리오를 pytest로 직접실행→JUnit 정확모듈/이름·종료코드/누락/중복/실패/건너뜀검사→생성DB만정리→새0600 보고서. 외부 XML/체크값/임의명령 입력없음. runId/시작종료시각/DBhead·기준커밋+backend/tools실코드지문·전후동일여부와시나리오결과 기록. 지문은커밋되지않은코드도포함하며 기준커밋과실코드를혼동하지않는다. DB URL/계정/본문/로그/임시경로는보고서/표준출력미포함. private임시로그/JUnit폴더정리, 기존보고서덮어쓰기금지·미리보기DB직접대상/비로컬관리연결거부. migration120초/검증300초제한.

성공도 SYNTHETIC_GW_ROUTE_EXECUTION/PARTIAL·readyfalse·실회사인수/전체권한회수/완전성false·복원권한거부UNVERIFIED. 실패/누락/건너뜀/소스변경은BLOCKED/exit2; 환경/예외는exit1·실행오류보고서가항상생성되는것은아님. unsigned합성보고서를 ACCEPTANCE/현재회사운영증거로등록하지않는다. 회사/정책은테스트내생성범위이며 미리보기회사3의인수근거아님.

검증: 관련단위132통과0.20초(기존경고2). 소유preview컨테이너ID/owner/55439대조후 수집기 실제CLI 실행: 새DB마이그레이션/고정2시나리오PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·잔여수집DB0 확인. 첫실행은JUnit모듈명이tests.접두인것을짧은이름만비교해MISSING/BLOCKED/exit2, DB정리는성공. 모듈명정확허용2형식으로보정후재실행통과, 첫보고서는보존/덮어쓰지않음. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. UI/브라우저/전체CI/실외부/복원/10인실인수 이번미실행. 스키마불변·Excel/ERD재생성없음. 소유시험DB정리·previewDB/서비스유지, 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4 유지. 다음: 고정실행시나리오를 인증·HR·ACL 및나머지GW경로의저장실패롤백/거부로확대하고 복원후검사와연결 → 최종서명 ACCEPTANCE/게이트 → GW UI보완 → main/전체회귀/10인실인수. 다음난이도높음·GPT-6.1 Sol + High 추천, 최종경계감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:30차단위명령에 backend/tests/test_gw_route_verify.py 추가(132). 소유로확인한로컬PG postgres 관리연결을FS_GW_ROUTE_VERIFY_ADMIN_URL에비공개주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정2실행). 기존TEST_DATABASE_URL을초기화하지않으며새DB만소유/정리한다. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 30차 GW 연결·역할 7경로 진단

codex/gw-company-01, 시작1b1c4b3·작업트리깨끗함. journal_routes/GW_IDENTITY_ROUTES_V1 및 기존CLI --company-id 추가. 현재 활성회사정책/세대·FS_CODE_REVISION·DBhead/별도확인head에 진단을 묶는다. 최초설정·연결요청/수락/취소/중지/재개·역할변경7개를 정확operation 패턴으로 분리한다. 다른회사/세대/bool범위 제외, 과거형식/잘못된ID/알수없는operation은 해당범위미지원 처리. 같은계열 다른operation으로 채우지 않는다. 모든기록 집계로 이후미확인에 과거성공 fallback없음. MISSING/ABORT_ONLY/UNSETTLED/COMMIT_OBSERVED 및 거래6종건수. 과거기록에 실행코드버전이 없으므로 assessment버전만 기록·executionRevisionVerified=false. 저장실패롤백/복원거부UNVERIFIED·모두관측도PARTIAL/전체회수·완전성·전환승인false 유지. 계정/대상ID/원문operation 출력없음. CLI exit0과경로BLOCKED 공존가능. 인증/HR/문서ACL 전체계약은후속이다.

검증: 단위121통과0.22초(기존경고2). 소유preview컨테이너ID/owner라벨/55439 대조·별도UUID *_test/alembic head에서 GW변경3+거래판정3 총6통과24.64초(기존경고2). 새실HTTP저장실패503→연결ACTIVE/버전불변→재시도중지200/직원posts403, 실제CLI 현재정책지문/head/제품버전·표준출력/보고일치·suspend관측1/cancel·resume미기록BLOCKED/readyfalse 확인. 이전ACL/미확인의도·감사범위변조 및 거래취소/진행/저장점/원본불일치 재검증. 테스트DB정리·previewDB/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/실외부/사본복원/브라우저/UI/10인실인수 미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4. 다음: 실행버전/실행번호·경로별저장실패롤백/권한회수 결과를묶는실제수집어댑터, 인증/HR/ACL경로목록 확대·실검증 → ACCEPTANCE/게이트 → GW UI보완 → main/전체회귀/10인인수. 다음난이도높음·GPT-6.1 Sol + High 추천, 최종경계감사는GPT-6 Astra + High 대안. 사용자선택전모델자동변경없음.

재현:29차단위명령에 backend/tests/test_gw_journal_routes.py 추가(121). 별도소유PG18 *_test/alembic head·TEST_DATABASE_URL 후 `uv run --project backend pytest backend/tests/test_gw_identity_journal.py backend/tests/test_journal_transaction_proof.py -q --tb=short` (6). 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 29차 관측 기록계열 진단

codex/gw-company-01, 시작b494178·작업트리깨끗함. gw.journal_coverage 추가: 이미 암호화 체인/별도head·DB 감사·거래상태로 검증한 기록을 core.security.intent.v1/hr.users.intent.v1/gw.company.intent.v2 계열별 MISSING/SETTLED/UNSETTLED와6종 거래판정 건수로 집계한다. 과거v1/알수없는계열은 unsupportedRecords로 차단·계열대체없음. 누락/추가/중복지문/임의APPROVED 판정 거부. 모든계열 거래정리도 PARTIAL일뿐 completeness/revocations/release=false·경로실행/롤백·독립최신head·복원거부/원본유지/운영자경계5범위는 별도다. 기존 gw_identity_journal --classify-transactions 및 --review-report에 recordingFamilies 연결. snapshot/계정/operation원문 출력없음. 기존CLI 종료코드는 거래판정 기준을 유지하므로 exit0과 계열BLOCKED가 함께 있을수있다. 이 진단을 ACCEPTANCE/운영완료/전체경로계약으로 사용하지 않는다. 제품API/UI·DB스키마/권한변경 없음.

검증: 관련단위110통과0.18초(기존경고2). 소유preview컨테이너ID/라벨/55439 대조·새UUID *_test/alembic head에서 실제PG 거래취소/진행/저장점/다른원본 판정 및 CLI 두경로3통과1.52초(기존경고2). 취소확인exit0이어도 HR/GW MISSING·계열BLOCKED, 근거없는UNKNOWN exit3·보고/표준출력일치·비밀미노출 확인. 시험DB정리/previewDB·서비스 유지. Ruff check/format·CLI help·정적DB219/2409/543·R1–R6/diff 오류0. 전체CI/실외부/사본복원/브라우저/UI/10인실인수 이번미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

다음: 개별 변경 경로별 예상실행/롤백·회수 검증 근거를 현재범위/버전에 묶는 계약·실행어댑터(이번계열집계와 구분) → 최종 ACCEPTANCE/게이트 → 기존GW UI 보완 → main/전체회귀·10인실인수. readyfalse/미확인4 유지·전체02진행중.

사용자추가지침: 매작업 종료시 완료내용/검증/제약/다음작업을 한국어로 알리고 다음작업 난이도에 따라 모델·추론수준 추천. 모델변경은 사용자가 선택하며 자동변경하지 않는다. 다음 개별경로/권한회수 연결은 높음: 현재앱 선택지 기준 GPT-6.1 Sol + High 추천, 최종 무누락/경계감사는 GPT-6 Astra + High 대안. 공식 OpenAI reasoning 가이드는 복잡성에 따른 effort 선택의 일반근거이며 이프로젝트 추천은 작업판단이다(https://developers.openai.com/api/docs/guides/reasoning).

재현: `uv run --project backend pytest backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (110). 별도소유PG18 *_test/alembic head·TEST_DATABASE_URL 후 `uv run --project backend pytest backend/tests/test_journal_transaction_proof.py -q --tb=short` (3). 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 28차 실제PG 사본 검사·격리복원 연결

codex/gw-company-01, 시작2b11be2·작업트리깨끗함 확인. 실제 백업 회귀를 보강했다. 실제 pg_dump/암호화 결과를 별도 로컬 비공개 사본으로 복사 → DB/인증키/서명개인키/PG컨테이너 환경을 제거한 subprocess의 verify-copy → 내부서명/dump/manifest 연결 확인 → checkpoint 뒤 테스트 원본 백업파일 제거 → 같은 사본으로 새 접속제한PG 복원 → 서명복원 증거와 사본검사 manifestDigest 대조/API전달·행/FK·세션회수·직원403·관리자200/원본 상태 유지까지 검사. 실제 다른 저장소 장애영역을 준비한 것은 아니다. 사본보고서 PARTIAL/databaseRestoreConfirmed=false는 파일검사 범위를 유지하며 별도 복원 증거도 PARTIAL/readyfalse다. 수동 합성업무 검사를 도구의 twoAccountChecks=true로 올리지 않았다.

실통합에서 DB 종료시각이 호스트보다 약1.6초 앞서 사본 검사가 실패했다. 사본 finishedAt 허용을 기존 verify_evidence와 같은30초로 정렬했다. snapshot/RPO 현재성 규칙은 변경없음·31초초과 거부 검사 추가. 이후 기존 권한회수 CHECK에 DB시각역전1회, 별도 재실행의 기존 백업증거 등록400도 관찰했다. 시계/호스트/컨테이너 설정은 변경하지 않았다. 첫3실행은 각각1실패2통과·2실패1통과·1실패2통과이며 성공으로 세지 않는다. 최종 새 소유DB에서3통과44.35초(기존 경고2). 시각역전 원인·장기안정성/실운영 시간동기 인수는 미확인으로 남긴다.

검증: 단위95통과0.20초(기존 경고2), 위 실제PG3통과, Ruff check/format·diff·정적DB219/2409/543·R1–R6 오류0. 소유preview컨테이너ID/owner라벨/loopback55439 대조 후 매실행 UUID *_test 생성/alembic head·시험DB정리; preview DB/서비스 유지. 이번브라우저/UI/전체CI/실외부/실기기/10인인수 미실행. schema불변·Excel/ERD재생성 없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포 변경없음.

전체02진행중. 다음: 전체 변경 수집/권한회수의 경로별 증거계약·실행어댑터와 미확인 처리 → 최종 ACCEPTANCE/운영게이트 연결 → 기존GW UI 맥락·긴정보/다음조치/모바일 보완 → 최신main/전체회귀·10인인수. 실제외부저장소/시간동기·회사인수는 별도 실환경 검증. 현재 readyfalse/미확인4 유지.

재현: 별도 소유PG18 *_test에 alembic head 적용·TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 주입 후 `uv run --project backend pytest backend/tests/test_gw_backup.py::test_actual_backup_replay_restore_and_business_denial backend/tests/test_backup_journal_restore.py -q --tb=short` (3). 단위는27차 명령에 같은파일 그대로(95). 미리보기DB를 TEST_DATABASE_URL로 사용하지 않는다. 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 27차 사본 복호화·명세/dump 검증

codex/gw-company-01, 시작b1ed206. 기존 gw_backup.py에 verify-copy 명령/verify_storage_copy 어댑터 추가. 원본DB 접속 없이 비공개 사본을 최대1GiB로 새 임시파일에 복사하고 현재 서명 BACKUP PASS/회사·세대·정책·제품/DB/RPO와 사본 지문을 대조한다. 같은 임시사본을 기존 AES-GCM/unpack 경로로 복호화해 내부 명세 서명·dump지문·증거 manifestDigest/runId를 확인한다. 입력은 백업 복호화키/키ID·신뢰 공개키만 필요하고 서명 개인키/인증키/DB URL 불필요. 임시 암호문/평문을 성공·실패 모두 정리한 뒤 새0600 최소보고서만 작성한다. 결과 PARTIAL/readyfalse·storageIndependenceConfirmed/databaseRestoreConfirmed=false. 오류exit1/기존출력 보존. unsigned보고서는 ACCEPTANCE 증거/제품등록용이 아니다. 사본의 실제PG 복원·외부장애영역/내구성은 미확인이다.

검증: 관련93 통과0.19초(기존 경고2), 실제 합성 AES-GCM/tar 서명/dump7경로와 CLI DB/서명개인키 없는 실행 포함. 잘못된키/명세불일치/dump변조/증거서명변조/암호문변조/기존보고서 보존·임시폴더정리·원본불변 확인. Ruff check/format·db:validate219/2409/543·R1–R6 오류0. 이번PG복원/실외부/브라우저/UI/전체CI/10인인수 미실행. schema불변·Excel/ERD재생성 미실행. 미리보기DB/서비스·실계정·다른checkout/main/원격push/배포 변경없음. 작업 트리 시작 깨끗함·비밀/work 스테이징없음.

전체GW-READY-02 진행 중. 다음: 이번 사본 검사와 실제 격리PG복원 증거의 연결·실제dump 기반 회귀 → 전체 변경 수집/권한회수 계약/어댑터 → 최종 ACCEPTANCE 계약·운영게이트 → 기존GW UI 구성 보완 → 최신main/전체회귀·10인실인수. 실제저장소/회사인수는 사용자 실환경에서 별도 확인하며 현재 readyfalse/미확인4 유지.

재현: `uv run --project backend pytest backend/tests/test_gw_storage_copy.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (93). `npm run db:validate`; `uv run --project backend python tools/audit_schema_isolation.py`. 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 26차 암호화 사본 전체 읽기 어댑터

브랜치 codex/gw-company-01, 시작 커밋7ac3914. 작업 트리 깨끗함 확인 후 진행. acceptance_artifact.inspect_copy와 기존 수집기 --storage-copy를 추가했다. 현재 회사/세대·정책·코드/DB·서명·기한·RPO를 통과한 BACKUP PASS의 artifactDigest를 실제 사본 전체 SHA256과 대조한다. 열린 descriptor의 소유자/비공개 권한/일반파일/1GiB 한도·전후 크기/mtime/ctime을 검사하며 최종 심볼릭 링크·빈 파일·읽는 중 변경을 거부한다. 원본 백업 경로/복호화키/DB 연결 없이 지정 사본만 읽는다. 결과는 경로·원문 없이 지문/읽은 크기/백업실행 번호와 MATCH/MISMATCH. MISMATCH는 기존 쌍 일치에도 BLOCKED/exit2. 입력/서명 오류exit1·새0600 출력만 허용. MATCH는 저장소 독립성·내구성·복호화·복원 증거가 아니며 미확인4/ready=false 유지. 기존 파일쌍 모드 호환, 제품 API/UI·스키마 변경 없음.

검증: 관련 단위86 통과0.16초(기존 경고2). 실제 임시 파일 읽기/변조/권한/링크/빈파일·서명/옛버전 및 CLI 사본불일치/종료2/출력0600/readyfalse 확인. Ruff check/format 통과, db:validate219표2409컬럼543FK 오류0, Python3.14 R1–R6 오류0. 기본 python3 감사는 기존 최신 구문 파싱 오류로 실패해 uv Python으로 재실행 통과했다. 전체CI/실외부 저장소/PG 복원/브라우저/10인 인수는 이번 미실행. DB스키마 불변으로 Excel/ERD 재생성 미실행.

API94777:8362/Vite89508:5362 포트와 PG fs-gw-ready02-preview 소유라벨 대조, 서비스/미리보기DB 변경 없음. 비밀/work 스테이징 없음·다른checkout/main/원격push/배포 변경 없음. 전체02 진행 중. 다음: 외부 사본의 실제 장애영역/복호화·격리복원 연결, 전체 변경 수집/권한회수 계약과 실행 어댑터, 최종 ACCEPTANCE 계약/게이트, 기존GW UI 구성 보완, 최신main/전체회귀·10인 실인수. 전체 권한회수와 UI 보완은 이번 미구현.

재현: `uv run --project backend pytest backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (86). `npm run db:validate`; `uv run --project backend python tools/audit_schema_isolation.py`. 마지막 커밋은 git log -1 참조.

## 2026-10-20 GW-READY-02 25차 실제 복원 부분 진단 전달

기준90e4889/branch codex/gw-company-01. 실제 복원 도구가 PARTIAL인 동안 세부 검사값을 수집기가 전달하지 않던 한계를 보완했다. metrics.restoreDiagnostics v1에 격리/DB버전/권한제한/완전성·변경대상/미확인/격리범위 건수만 서명한다. 복원 전용 엄격한 타입·허용필드/건수 범위·미확인<=대상 수를 검사하고 미확인 진단과 모순되는 PASS는 거부한다. 원본·저장행 재검증을 통과한 최근 PASS/PARTIAL 복원만 restoreMeasurements로 전달한다. 실패/옛정책/원본없음/변조는 숨기고 이전 성공 fallback없음. PARTIAL을 쌍 통과로 올리지 않으며 readyfalse/미확인4 유지. 실제 외부저장소·전체권한회수·회사 인수 완료 아님.

기존 GW 연결 점검에 기본 접힘 ‘최근 복원 검사 내용’ 추가. 지문/참조/이전세션과 전체권한회수/관리자·직원업무의 확인·미충족·기록없음을 구분하고 격리·완전성·미확인 건수를 안내한다. 이전 형식의 진단 누락과 현재검사없음도 구분. 기존 증거 호환/JSON저장 유지·DB스키마 변경없음. UI 전체 재설계는 후속이다. 도움말·인수절차 갱신.

검증: 최종 단위77 통과0.15초, 소유 임시PG에서 실제 dump/암호화/격리복원·원본권한회수/재등록/서명진단/API 전달·journal 복원2경로 총3 통과55.37초(각기존경고2). 소유preview 컨테이너 라벨·55439 대조 후 별도 UUID *_test 생성/alembic head·시험복원DB/시험DB 정리, preview DB유지. 화면/도움말29 통과3.58초, 도움말 수정후18 재검사3.17초(중복합산금지). 타입/수정ESLint/Prettier/Ruff·정적DB219/2409/543/R1–R6/diff 오류0. 실제 브라우저 회사3 기존세션/operations200·펼침/확인기록없음 표시와 캡처 outputs/gw-implementation-20261020/실제제품_복원검사펼침.jpg 확인. 합성 미리보기에 가짜 성공 증거를 넣지 않음. 전체CI/실회사/외부저장소/실기기/10인 부하 미실행.

API94063 명령대조후종료·8362에 PID94777/세션22876로재실행. Vite5362/세션3065 및 fs-gw-ready02-preview/55439 유지, 기존22차 소유ID/라벨/명령대조 정리원칙 유지. 비밀/work/전체로그 스테이징금지. 사용자계정·비밀번호/실서버/예약설정/main/다른checkout/원격push/배포변경없음.

다음 같은02: 실제외부저장소 검증·전체수집/회수/실회사/최종전환 증거계약/어댑터, 기존GW UI 보완, 최신main/전체회귀·10인인수. 현재 부분 검증을 운영 인수 완료로 표현하지 않는다. 재현: uv run --project backend pytest backend/tests/test_gw_operating_contract.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short (77). 별도 소유PG/alembic·TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 후 test_gw_backup.py::test_actual_backup_replay_restore_and_business_denial 및 test_backup_journal_restore.py (3).

## 2026-10-20 GW-READY-02 24차 최신 등록 증거와 수집기 연결

기준88d9e5b/branch codex/gw-company-01. 기존 operations 회사트랜잭션/종류별최근조회와 acceptance_collection을 연결했다. 최신행을 recorded_at/id로 선택해 현재policy revision/키/코드/DB·시각·원본서명/등록행 전체 대조 후 BACKUP/RESTORE쌍을 수집. 더최근FAIL/PARTIAL/변조/원본없음/옛정책/타범위가있으면 과거성공 fallback없음. API backupRestoreCollection과 기존운영화면의 읽기전용 ‘백업·복원 연결 점검’ 안내 추가, 일반직원응답엔미노출. 별도추가쿼리/쓰기/완료입력/스키마없음. 쌍일치여도PARTIAL/readyfalse·미확인4유지. 서버가 실제백업을 복호화/복원하거나 외부저장소/전체권한회수/실회사인수를 실행한 것은 아니다.

검증: 집중 단위backend69 통과0.13초, 별도 소유 임시PG DB에서 실제정책/증거HTTP/권한/최신실패/저장행변조 포함6 통과49.69초(각기존경고2). 새 PG DB는 소유preview컨테이너55439 안에 UUID *_test 이름으로 생성/alembic head적용 후 정확한생성DB만삭제·preview DB유지. 합성서명PASS는판정계약검사이며실제dump/restore증거가아님. 화면/도움말 최종28 통과3.32초·타입/수정ESLint/포맷/Ruff·정적DB219/2409/543/R1–R6/diff 오류0. 실제브라우저 회사3/로그인유지/operations200·새안내미확인표시 확인·캡처 outputs/gw-implementation-20261020/실제제품_최신증거연결점검.jpg. 미리보기검증키/증거미설정상태로 성공위장안함. 전체CI/실회사/실외부/실기기/10인부하는미실행.

실행미리보기유지: 기존API89447을명령대조후종료·새코드API PID94063/세션60209로같은8362재실행, Vite5362/세션3065와소유PG fs-gw-ready02-preview/55439는유지. 사용자계정/비밀번호/실회사/원격/배포/예약설정변경없음. private work 접속/전체로그 스테이징금지. 종료시22차 소유ID/label·명령대조원칙유지. 외부시제품탭변경없음. main/다른checkout변경없음.

남은같은02: 실제외부저장소와수집/회수·실회사·최종전환 증거계약/실행어댑터 → 기존GW UI 맥락/정보구성 보완 → 최신main통합/전체회귀·10인인수. 기존전체승인유효·이번운영인수완료아님. 재현: uv run --project backend pytest backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short (69). 별도 소유PG/alembic와비공개TEST_DATABASE_URL 후 test_gw_evidence.py/test_gw_operations.py (6). Node24 frontend npm test -- --run src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/portal/content-pages.test.tsx (28).

## 2026-10-20 GW-READY-02 23차 백업·복원 인수 자료 수집기

기준5666060/branch codex/gw-company-01. 기존 GW의 GwLayout 회사 운영 안내→operations 연결을 코드로 확인했다. 새 솔루션이 아닌 관리자 점검 화면이며 별도 GW처럼 보인다는 사용자 피드백을 10인 인수 절차에 UI 보완 항목(업무/관리 맥락·다음 행동·정보량·모바일·4대 UI 기준)으로 기록했다. 이번에 UI 재설계는 하지 않았다.

acceptance_collection 및 tools/gw_acceptance_collect.py 구현: 기존 gw_backup.py BACKUP/RESTORE 원본 서명을 현재 회사/세대/정책/제품/DB·신뢰키로 재검증, PASS/백업RPO 현재성·시각·서로 다른실행·동일manifest 대조. 원본을 재실행/복호화하는 도구가 아닌 서명 증거 쌍 대조다. 검증한 원본 지문·현재 기준/시각·최소 상태만 새0600 파일에 저장. 입력은 소유자0600·출력폴더0700/기존파일 덮어쓰기거부. 개인키/DB URL/DB 접근 없음. 일치해도PARTIAL/exit0, 불일치BLOCKED/exit2, 파일/설정오류exit1. unsigned 수집보고서로 ACCEPTANCE PASS 업로드/launchGate 완료를 허용하지 않는다. 담당자 제공 현재 기준과 파일쌍만 검사하며 DB최신실패·실외부저장소·전체권한회수·실회사·최종전환은 아직 검증하지 않는다. 네 조건UNVERIFIED/readyfalse 유지.

검증: 새 수집기14+기존 계약16+gate14=집중backend44 통과0.09초(기존경고2). 서명변조·타회사/정책/버전·서로다른manifest·시각겹침/미래·실행중복·기한초과·PARTIAL·누락/임의완료필드 차단, CLI 실제 파일 권한/덮어쓰기/최소출력 검사 포함. 도움말18 통과2.32초, Ruff/format·CLI help·정적DB219/2409/543 및R1–R6/diff 오류0. 새 PG/브라우저/실기기/실회사/전체CI/실외부저장소 검사 미실행. 이전22차 합성 미리보기(API8362/Vite5362/PG55439)는 별도 기록대로 유지하며 이번 새 서비스/예약 설치 없음. 비밀/work 스테이징금지. main/다른checkout/원격push/배포 변경 없음.

다음 같은02: 수집 결과의 최신등록/실측자료 연결·외부저장소/전체수집회수/실회사/최종전환의 최종 서명 인수 계약과 실행 어댑터 → 최신main통합/전체회귀·10인부하 → 실제회사 인수. UI 보완은 위 피드백을 기존 GW 맥락에서 반영한다. 운영 인수 완료 아님. 재현: uv run --project backend pytest backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_launch_gate.py -q --tb=short. 도구 사용법은 docs/operations/GW_실회사_인수절차_10인_GW-READY-02.md §2-1.

## 2026-10-20 GW-READY-02 22차 실제 제품 실행·시제품 구분

기준 601fb4b, branch codex/gw-company-01. 기존 file:// 검토용화면.html#retention은 설계 시제품이며 구현/배포 증거가 아님을 정리했다. 현재 React+FastAPI+전용 PostgreSQL18을 실행하고 실제 브라우저에서 합성 관리자 비밀번호 로그인 → MFA → 홈 → 회사 운영 준비를 확인했다. 합성 회사3/부서1/연결직원1/인증앱1, 예정인원10이며 실제 10인 인수가 아니다. 정책 저장값과 12조건(확인4/조치4/미확인4), 증거 등록·보관 검토/보존 중지 화면을 확인하고 실제 화면을 캡처했다. 보관 변경/증거 업로드/실외부 저장소 검사는 이번에 실행하지 않았다. 도움말에서 운영 준비 미완료와 제품 미구현을 구분하고 기존의 판정 미구현 표현을 수정했다. 새 제품 기능/증거 어댑터/스키마 변경 없음.

로컬 실제 제품: http://localhost:5362/gw/operations?companyId=3 (이번 합성 미리보기 전용). 화면 캡처는 채팅 outputs/gw-implementation-20261020에 보관. 이전 file 시제품은 변경하지 않았다. 사용자 확인을 위해 API8362(실행 세션59265), Vite5362(세션3065), 소유 PG fs-gw-ready02-preview/127.0.0.1:55439/gw_preview_test를 이번에는 유지했다. 임시 실행이므로 재시작/지속 가동을 보장하지 않는다. 비공개 초기화/접속 자료는 무시되는 work/gw-readiness-02-preview 아래0600, 디렉터리0700. 공개 문서에 비밀번호/OTP/키를 기록하지 않았다. 정리 시 저장된 container-id와 factory-studio.owner=gw-ready-02-preview 라벨이 일치할 때만 해당 컨테이너/볼륨을 삭제하고, API/Vite는 해당 작업 명령·포트 소유를 확인한 뒤 종료한다. 다른 DB/계정/브라우저 설정/서버/예약 작업 변경 없음.

남은 순서: 미확인4조건·ACCEPTANCE PASS 증거계약/수집·검증 어댑터 → 최신 main 통합/전체 회귀·10인 부하 → 실제 독립 저장소 장애복구/기기·회사 업무 인수 → 최종 운영 전환. 현재 ready=false, 개발 브랜치에 구현됨/main 미통합/원격 push·배포 없음. 이번 도움말 집중 검사18건 통과(2.47초), diff 검사 오류0. 이번 검사는 실제 브라우저 대표 흐름과 도움말 집중 검사이며 전체 CI/실기기/실회사 인수와 구분한다.

## 2026-10-19 GW-READY-02 21차 인수 근거 안내·현재/남은 작업

기준ddb7d78/branch codex/gw-company-01. acceptance_requirements의 정적 근거목록을 launchGate 미확인4조건에 acceptanceScope/requiredEvidence로 연결. 제품 운영전환조건에서 필요한인수근거를펼쳐검증환경·자료목록확인, 예정직원수는정책expectedPeople에따라안내. 이필드는증거/승인값아니며state/ready계산불변·업로드/수동완료/DB스키마없음. 10인실회사인수절차문서에1회사/1부서/관리자1+직원9 기본안·현재구현/합성검증·증거어댑터/최신main회귀/실외부/10인인수/최종전환 남은범위 명시. 총관리자admin과회사관리자구분·실계정/비밀미기록.

이번집중backend14 통과0.02초(정적기준/판정·인원안내/상태불변), 화면/도움말26 통과2.85초(펼침/접힘·안내가증거아님/기존응답호환), TypeScript/수정ESLint·Prettier/Ruff/정적DB219/2409/543·격리R1–R6/diff 오류0. 이번새PG/실브라우저/실기기/실회사/외부저장소/전체CI미실행,20차PG36은이력과구분. DB/앱/예약설치·실계정/비밀번호/외부저장소/서버설정변경없음·다른checkout/main/원격push/배포변경없음. 합성파일검사만사용·정리할신규서비스/인증파일없음. 도움말/API/현황/진행/HANDOFF/문서지도갱신.

현재: 회사인증/권한·MFA/제한/긴급복구·서명증거·암호화백업/격리복원·변경기록/교체/전달·원본재검증·12조건과인수안내구현. 남은개발: 미확인4조건/ACCEPTANCE PASS 증거계약·수집/검증어댑터·전체무누락/최종전환 연결. 남은통합: 최신main대조/전체회귀·CI/10인부하/장기성능. 남은실인수: 실제독립저장소장애·복구/COMPANY·TLS·기기·10인업무/담당자·최종전환. 선택SSO사용시실IdP인수별도. 아직사업운영인수완료아님/readyfalse. 다음같은02는증거계약/어댑터부터, 기존전체02승인유효. 재현: uv run --project backend pytest backend/tests/test_gw_launch_gate.py -q --tb=short (14, DB불필요). Node24 frontend npm test -- --run src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/portal/content-pages.test.tsx (26). 비밀/work/전체로그스테이징금지.

## 2026-10-19 GW-READY-02 20차 최종 조건·미확인 증거 구조화

기준2e38dd3/branch codex/gw-company-01. gw.launch_gate v1이 운영기준/현재담당자활성연결/조직/직원/MFA/서명증거3종과 외부저장소/전체수집회수/실회사/최종전환 총12조건을 CONFIRMED/BLOCKED/UNVERIFIED로분리. 운영준비응답 launchGate/집계/각설명·다음조치 추가, blockers는미충족조건에서생성. 책임자활성계정·회사멤버십·직원연결/활성조직은S범위묶음조회. 증거는RECORDED_PASS+signatureVerified=true필수. 미연결4조건은UNVERIFIED고정·ready는모두CONFIRMED일때만true로계산하여현버전false. 직원제한응답유지·새쓰기/승인입력/스키마/DB개방없음. UI운영전환조건에한국어상태/조치표시, 기존응답fallback유지.

실제소유PG18 회사HTTP·책임자회수후재판정/증거·진단 포함backend36 통과29.43초(기존경고2), 화면/도움말26 통과2.62초. 로컬8조건충족해도미확인4로차단·무정책/0인/인원·MFA·조직부족·중복/누락/서명미확인·부분증거거부. 타입검사/수정ESLint·Prettier/Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 새실브라우저/실기기/실회사/외부저장소/전체CI미실행. 실제계정/비밀번호/서버/예약설정변경없음·main/원격push/배포/다른checkout변경없음. 소유PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/볼륨·임시env/ID제거. 도움말/운영/API/현황/진행/HANDOFF갱신.

다음 같은02: 미연결조건의서명증거계약·책임경계/최종인수계획 → 실제외부저장소장애복구/전경로완전성·전체회수/장기성능·선택SSO/전체회귀·10인실환경인수/main. 체크리스트확인과외부실증을구분·임의완료입력금지. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL 후 uv run --project backend pytest backend/tests/test_gw_launch_gate.py backend/tests/test_gw_operations.py backend/tests/test_gw_evidence.py backend/tests/test_gw_readiness.py -q --tb=short (36). Node24 frontend npm test -- --run src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/portal/content-pages.test.tsx (26). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 19차 운영 경로v1·복원 인증 거부

기준af4ecce/branch codex/gw-company-01. 운영 경로 검증 문서에 core세션/MFA·복구·긴급/GW·HR권한/초기설정/백업·기록도구 범위v1과 제외·별도인수 경계를 고정했다. 기존 실제PG dump/restore 테스트 두경로(수동지문/폴더교체+전달확인자동지문)에 관리자/직원옛토큰 _resolve_member401·합성미완료요청 EXPIRED/verify_login401·미회수세션0·검사후datconnlimit0 검사를추가. 원본관리자토큰/운영준비HTTP200·직원역할변경에따른원래세션회수401/원본요청PENDING·계정/직원역할유지 확인. DB개방/새계정/제품코드/권한정책/스키마변경없음. 전체무누락·전체회수서명증거/readyfalse 유지, 실제외부/10인실환경인수와구분.

최종실제PG관련7 통과52.12초(기존경고2): 두dump/restore+OTP/복구소비·암호변경·HR하향·불확실ACL checkpoint4·취소후새격리복원1. 도움말18 통과2.84초·Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 최초2실패는 원본직원토큰이HR역할변경때이미회수된정상동작을테스트에서유효하다고기대한문제로, source직원401/admin유효로보정후재통과(제품수정없음). 복원DB는테스트소유superuser로내부함수검증, 직원DB연결/대상HTTP개방안함. 새브라우저/전체CI/실기기/실회사/실외부저장소·10인인수미실행. 소유PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/복원DB/볼륨·임시env/ID제거. 실제계정/비밀번호/서버설정/스케줄/다른checkout변경없음·main미통합/원격push/배포없음. 도움말/운영/현황/진행/HANDOFF갱신.

다음 같은02: 최종운영조건의기계검증/미확인항목과증거계약정리 → 전체운영인수/실제외부저장소장애복구·장기성능/선택SSO·전체회귀/10인실환경/main. 코드목록고정/합성거부검사를전체완전성/운영승인으로올리지않음. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 후 uv run --project backend pytest backend/tests/test_backup_journal_restore.py backend/tests/test_security_checkpoint.py backend/tests/test_aborted_journal_rebuild.py -q --tb=short (7). Node24 frontend npm test -- --run src/portal/content-pages.test.tsx (18). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 18차 초기 설정 도구 기록·세션 제외 판정

기준89acf6a/branch codex/gw-company-01. core.create_member_account 완료후 security.member_account.created 시스템기록, HR초기회사/예제최종연결·중지준비·비밀번호설정활성 뒤 hr.setup.company.created/example.created|disabled|activated를 core계정/역할/회사멤버십 상태로 수집. 기존선택환경/같은TX실패취소 규칙유지·비밀번호/이름원문제외. HR평상시사용자관리 스냅샷과 구분. common.auth 유휴만료연장은 복원시전체세션회수 대상으로판정해 허용재생/매요청암호화기록에서제외. 절대만료상한/제한재적용후이전토큰거부를실제로검사. throttle 초기0/updated_at는거부횟수변경과구분하고전체카운터의미/부하는남김. 새표/HTTP/UI/권한정책변경없음·전체완전성/회수/readyfalse 유지.

실제소유PG18 관련backend18 통과96.59초(기존경고4), 도움말18 통과2.91초. 운영자계정역할/기록·비밀미포함/저장실패생성취소, 초기예제두계정중지/활성기록·저장실패전체생성취소/활성화취소, 세션연장상한·복원제한후토큰거부, 기존HR/인증/긴급/운영자회원회귀. Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 실제CLI대화/실계정/실비밀번호설정/서버/스케줄변경없음. 새브라우저/실기기/실회사/외부저장소/전체CI 미검증. 소유PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/볼륨·임시env/ID제거. main/원격push/배포/다른checkout변경없음. 도움말/경로검증/운영/API/현황/진행/HANDOFF갱신.

다음 같은02: 지원할 운영경로 목록 확정·나머지 도구/직접SQL 경계 → 전체 권한회수 종단시나리오/운영전환 최종조건 → 실제외부저장소 장애복구/장기성능·선택SSO/전체회귀·10인실환경인수/main. 경로판정과실환경인수를혼동하지않음. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL 후 uv run --project backend pytest backend/tests/test_setup_security_journal.py backend/tests/test_account_security_journal.py backend/tests/test_member_account.py -q --tb=short (18). Node24 frontend npm test -- --run src/portal/content-pages.test.tsx (18). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 17차 로그인 요청·거부 기록 누락 보완

기준7e82882/branch codex/gw-company-01. 실제 보안 쓰기를 대조해 core.service.login_member 세션발급, security.login_gate 요청생성/verify_login 실패·만료, emergency.fail_login 실제갱신/approve 문서만료 직후 계정 암호화기록/동TX감사 연결. 작업명 password_session.issued/login_challenge.issued|denied|expired/emergency_login.denied/emergency_kit.expired. 요청snapshot에 attempt_count/expires시각만추가·토큰/코드/비밀번호제외. 저장실패시DB변경취소, 이미LOCKED/미존재로UPDATE안된긴급요청은기록중복없음. 새표/HTTP/UI/권한허용/로그인정책변경없음. 별도 GW_보안변경_수집경로검증_GW-READY-02.md에 확인범위와 초기설정도구/common.auth 유휴만료연장/throttle 새창·직접SQL 등 미인수범위를구분, 전체완전성/회수/readyfalse 유지.

실제소유PG18 최종관련27 통과59.04초(초기24/26과겹침, 기존경고4), 도움말18 통과2.28초. 실패1~5회LOCKED/만료/긴급문서만료·DB지문일치, issued/denied/expired/emergency 4경로 저장실패rollback, 기본비밀번호세션 발급기록/비밀미포함·저장실패취소, 긴급거부5회기록·잠금후중복없음·기존MFA경합/회수/HR/긴급/로그아웃 회귀. Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 전체CI/새브라우저/실기기/실회사/외부보관미검증. 소유PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/볼륨·임시env/ID제거. 실계정/실환경설정/스케줄/다른checkout변경없음·main미통합/원격push/배포없음. 도움말/운영/API/현황/진행/HANDOFF갱신.

다음 같은02: 남은 쓰기 경로의 수집 필요성/초기설정·운영도구 인수 → 전경로 회수·최종운영게이트 → 실제외부저장소 장애복구/장기성능·선택SSO/전체회귀·10인실환경인수/main. 경로검색만으로전체누락없음선언금지. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL 후 uv run --project backend pytest backend/tests/test_challenge_security_journal.py backend/tests/test_account_security_journal.py backend/tests/test_gw_security_transactions.py -q --tb=short (27). Node24 frontend npm test -- --run src/portal/content-pages.test.tsx (18). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 16차 원본 증거 보존·서명 재검증

기준94b4d11/branch codex/gw-company-01. 새 증거 등록 시 엄격 허용목록/서명 검증을 통과한 원본 envelope 값을 기존 metrics JSONB 내부 예약필드 _signedEnvelope에 보존한다. signature/정규화검사값 열 유지, 새표/열/마이그레이션 없음. 운영준비 조회는 현재키로 원본서명을 재검증하고 S/정책/버전/runId/종류/시간/manifest/결과/실행자/검사값을 DB행과 대조. timestamptz는 동일시점 비교. 과거 원본없는행은 수정/추정하지않고 LEGACY_UNVERIFIED, 변조/불일치는INVALID. 각 evidenceChecks.signatureVerified, 3종모두재검증시 evidenceIntegrityReverified=true. 서명확인과 PASS/전체운영준비는 별개로 ready=false 유지. 새증거 원본을 history응답에 노출하지 않음. 도움말/운영/API/현황/진행/HANDOFF갱신.

실제소유PG18 등록원본보존/조회재검증·원본/정규화검사값 변조/과거형식·정책/권한/계약 포함 최종backend38 통과28.30초(초기37·단위26과겹침, 기존Starlette경고2). 화면/도움말25 통과2.49초. 키동일ID교체/서명·범위·runId불일치/시간대표현/서명확인된PARTIAL상태유지 검사. Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 새브라우저/실기기/실회사/외부보관/전체CI 미검증. 실제계정/운영설정/스케줄/다른checkout변경없음, main통합/원격push/배포없음. 본인PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/볼륨·임시env/ID제거. 신뢰실행기정확성/DB소유자재작성방지/전경로회수·외부복구인수는별도.

다음 같은02: 전경로 수집 완전성·권한회수 인수/최종운영게이트 → 실제외부저장소 장애복구/장기성능·선택SSO/전체회귀·10인실환경인수/main. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL 후 uv run --project backend pytest backend/tests/test_gw_readiness.py backend/tests/test_gw_operations.py backend/tests/test_gw_evidence.py backend/tests/test_gw_operating_contract.py -q --tb=short (38). Node24 frontend npm test -- --run src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/portal/content-pages.test.tsx (25). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 15차 운영 준비 증거별 진단

기준ba6eade/branch codex/gw-company-01. gw.readiness가 현재 정책/제품/DB 버전·신뢰 실행자 키·필수 검사·시각과 BACKUP RPO를 대조한다. operations 조회는 S 범위 종류별 최신 recorded_at/id 한 건을 묶음조회, 최근실패/부분을 과거PASS로 대체하지 않는다. CONFIG_REQUIRED/POLICY_REQUIRED/MISSING/STALE/INVALID/FAILED/PARTIAL/RECORDED_PASS 진단을 evidenceChecks에추가. 관리자/감사만조회·직원제한유지, UI 실행증거확인/한국어조치·등록성공후상위재조회 연결. 기존DB는정규화metrics를저장하므로 원본JSON표현/서명재검증은 주장하지않고 evidenceIntegrityReverified=false/ready=false 유지. 외부장애복구·전경로완전성/전체회수·원본서명재검증/최종운영승인 차단근거표시. 새표/마이그레이션/권한부여/운영개방없음.

실제소유PG18 회사HTTP·서명등록→운영준비조회/최신실패·설정미비·권한과 계약/진단 관련backend29 통과18.81초(기존경고2). 화면/등록후갱신·도움말25 통과2.48초, TypeScript/수정파일ESLint·Prettier/Ruff·정적DB219/2409/543·격리R1–R6/diff 오류0. 새실브라우저/실기기/실회사/외부보관/전체CI 미검증. 본인PG fs-gw-ready02-journal-test/55438 ID+owner label대조후컨테이너/볼륨·임시env/ID제거. 실계정/실환경설정/스케줄/다른checkout변경없음·main통합/원격push/배포없음. 도움말/API/현황/진행/HANDOFF갱신.

다음 같은02: 원본 서명 증거 보존·재검증 계약/구현 → 전경로 수집 완전성·회수 인수/최종운영게이트 → 실제외부저장소 장애복구/장기성능·선택SSO/전체회귀·10인실환경인수/main. 등록된통과는현재조건진단일뿐운영승인아님. 기존전체02승인유효. 재현: 새소유PG18 *_test/alembic head·비공개 TEST_DATABASE_URL 후 uv run --project backend pytest backend/tests/test_gw_readiness.py backend/tests/test_gw_operations.py backend/tests/test_gw_evidence.py backend/tests/test_gw_operating_contract.py -q --tb=short (29). Node24 frontend npm test -- --run src/gw/operations.test.tsx src/gw/operating-evidence.test.tsx src/portal/content-pages.test.tsx (25). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 14차 전달 확인 기록·자동 지문 입력

기준81fc3d9/branch codex/gw-company-01. core.security.journal_witness와 gw_journal_delivery.py publish/check 추가. 원본/사본/확인 경로 분리·기록키와 다른32바이트 키로 HMAC/순번/이전지문 확인 기록을 인증하며 새 사본 재인증 뒤에만 작성한다. 첫 독립지문 bootstrap 필수, 이후 --advance는 확인된 접두에서 이어지는 원본만 전달한다. backup_journal의 backup/checkpoint/restore 지문 입력을 선택 WITNESS DIR/KEY_FILE의 최신 인증 확인 기록과 연결. MAX_AGE_SECONDS 기본1800(1~86400)/MIN_SEQUENCE 기본1·미래시각/인증/최소순번/수동지문 충돌/원본진행 불일치 거부. 실행 템플릿 run_gw_journal_delivery.sh만 추가·스케줄 미설치. 새표/HTTP/UI/권한허용 없음. PARTIAL/readyfalse/외부내구성false 유지.

실제 소유PG18 전달확인지문만으로 backup→기록폴더교체→회수후재개/역할변경→재전달→checkpoint→격리restore와 수동경로 포함 관련37 통과55.97초. 이후 --advance/초기무지문거부/실제CLI를 포함 최종단위35 통과1.82초(겹침), 도움말18 통과3.17초. 전달실패시확인지문불변·사본/확인저장실패·분기체인/후속폴더·오래됨/미래시각/최소순번/인증변조거부. Ruff/포맷/bash문법/diff·정적DB219/2409/543·격리R1–R6 오류0. 실외부저장소/네트워크단절/전원차단/대량성능/실기기/실회사/전체CI/새브라우저 미검증. HMAC키보유자재작성·허용시간내저장소전체복귀는 자체완전탐지 못함, 독립 최소순번/실저장소변경방지 인수필요. 확인기록10,000개한도·실패사본남음/새사본부모로재시도·부분확인기록은조사대상. 실제외부자격증명/서버설정/스케줄변경없음. 소유PG fs-gw-ready02-journal-test/55438 ID+owner label대조 후 컨테이너/복원DB/볼륨·임시env/ID제거. main/다른checkout/원격push/배포변경없음.

다음 같은02: 외부저장소·독립최소순번/장애복구/장기성능 인수 → 전경로 완전성·운영전환게이트 → 선택SSO/전체회귀·10인실환경인수/main. 외부설정이없는동안 구현할 다음대상은 운영전환게이트의 검증근거/차단조건이다. 기존 전체02 승인 유효. DB없는재현: uv run --project backend pytest backend/tests/test_journal_witness.py backend/tests/test_journal_rollover.py backend/tests/test_journal_bundle.py backend/tests/test_backup_journal.py -q --tb=short (35). PG는새소유 *_test/alembic head/비공개 TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 후 test_backup_journal_restore/test_aborted_journal_rebuild와 위검사(추가advance전37). 비밀/work/전체로그 스테이징금지.

## 2026-10-19 GW-READY-02 13차 완료

branch codex/gw-company-01, 구현 커밋 1e595d5. 기존 ciphertext/지문/전역번호를 유지한 .history 보존 접두와 활성 접미를 연결했다. rollover는 새 폴더 준비만 수행하고 원본을 유지한다. check-switch는 원본/새 폴더 동일 지문 점검이며 실제 설정 전환은 하지 않는다. 운영자는 모든 작성 경로를 멈추고 동일 키/새 버전으로 일괄 전환해야 한다. 새 기록 후 과거 원본 재활성 금지. 활성10,000/전체100,000건 한도, 전체 체인 인증 비용과 복사 용량/잠금 시간 제약 유지. 기존 백업 기준과 교체 후 checkpoint/격리 복원 연결, 교체 후 사본 export/verify도 구현. 새 DB표/HTTP/UI 없음, PARTIAL/ready=false 유지.

실제 소유 PG18 백업/교체 후 GW회수·재개/HR역할 변경/격리 복원 포함 관련37 통과36.83초, 최종 별도 교체25 통과0.97초(겹침), 도움말18 통과2.69초. Ruff/포맷/diff·정적DB219/2409/543·격리R1–R6 오류0. 누락/변조/번호누락/링크/중간복사실패/원본진행 차단과 축소한도 반복교체 검증. 전체CI/새브라우저/실기기/실회사/외부보관/대량성능/전원차단 미검증. 본인 PG fs-gw-ready02-journal-test/55438 ID+owner label 대조 후 컨테이너/복원DB/볼륨·임시env/ID 제거. 실환경설정/실계정/스케줄/다른checkout/main/원격/배포 변경없음. 최종 기록 갱신 스크립트의 stdin 인코딩 오류로 문서 반영이 빠져 별도 문서 커밋으로 보정했다.

다음 같은02: 독립 최신지문 자동전달/외부보관·장기성능/장애인수 → 전경로 완전성/운영전환 게이트 → 선택SSO/전체회귀·10인 실환경인수/main. 기존 전체02 승인 유효. DB 불필요 재현: uv run --project backend pytest backend/tests/test_journal_rollover.py backend/tests/test_journal_bundle.py backend/tests/test_backup_journal.py -q --tb=short (25). PG 재현은 새 소유 *_test에 alembic head 및 비공개 TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 후 test_backup_journal_restore/test_aborted_journal_rebuild/test_journal_transaction_proof/test_security_journal와 위 단위 검사 실행. 비밀/work/전체로그 스테이징 금지.

## 2026-10-19 GW-READY-02 12차 암호화 기록 사본·오프라인 인증

기준ee588ac/branch codex/gw-company-01. core.security.journal_bundle와 tools/gw_journal_bundle.py export|verify 추가. 독립 expected-head 대조 후 원본 flock 유지 상태에서 새 0700폴더/0600암호화파일 복사·fsync, 복사본 재인증 뒤 manifest를 마지막 기록한다. 기존경로/심볼릭링크 덮어쓰기 없음·실패폴더 보존/재사용거부·원본안쪽 경로거부. verify는 원본DB/폴더 없이 키+독립지문으로 인증. 출력은 건수/지문/기존완전성false와 bundleVerified/sourceRotatedfalse/externalDurabilityConfirmedfalse/releaseAuthorizedfalse. 복호화·키 출력없음. 기존 체인/백업 연속성을 보존하므로 원본삭제/한도초기화/새체인 교체 없음. 이번은 사본 생성/인증 기반까지이며 실제 다중묶음 교체·독립지문 자동전달/네트워크전송·외부내구성은 미완료다.

관련backend23 통과0.44초(초기21과 겹침/기존Starlette경고2), 도움말18 통과2.51초. 실제 암호화파일 export와 DB없는 CLI verify, 이후원본append/옛사본고정·최신지문거부, 동시append직렬화·누락/변조/오키/명세불일치/미완료/기존파일거부·빈묶음/권한 검사. Ruff/포맷/diff·정적DB219/2409/543/격리R1–R6 오류0. 새표/마이그레이션/HTTP/UI없음. DB/앱/스케줄 실행·실제계정/운영설정 변경없음. 전체CI/새브라우저/실기기/실회사/외부저장소/전원차단 미검증. 이번은 pytest 임시 합성파일만 사용, DB컨테이너 생성없음. main통합/원격push/배포없음.

다음 같은02: 다중묶음 체인·백업/복원 연결을 유지하는 실제 보관 교체 → 독립 최신지문 전달/외부보관 인수 → 전경로 완전성·운영전환 게이트 → 선택SSO/전체회귀·10인 실환경인수/main. 기존 전체02 승인 유효. 재현: uv run --project backend pytest backend/tests/test_journal_bundle.py backend/tests/test_journal_review.py backend/tests/test_backup_journal.py -q --tb=short (DB 불필요). 환경키·work·전체로그 스테이징 금지. 실제 외부 저장 장소가 없으므로 로컬 사본을 외부 복구 인수로 표시하지 않는다.

## 2026-10-19 GW-READY-02 11차 과거 미확인 기록 인수 진단

기준81162b3/branch codex/gw-company-01. CLI --review-report가 거래 분류를 함께 수행해 지정 최신지문·조회시각·기록 봉투지문별 6종 판정/한국어 조치·운영자 점검 목록을 새 비공개 JSON에 저장한다. core.security.journal_review는 payload/계정/원본DB지문/거래ID를 내보내지 않고 0700부모/0600신규파일·덮어쓰기/심볼릭링크거부·fsync를 적용한다. 보고는 진단 전용, 서명증거/checkpoint 입력/권한승인 아님. releaseAuthorized/checkpointInput/completenessConfirmed=false, 수동 ACCEPTED/미확인 제외 경로 없음. UNKNOWN은 확인 불가/제한 유지, PENDING 재조회, 원본/감사누락 조사·소급기록 금지·새 checkpoint/격리 복원과 별도 운영 인수 기준을 문서화. 새DB표/마이그레이션/UI/HTTP/권한허용 없음. PARTIAL/readyfalse 유지.

관련 backend22 통과2.62초(초기21과 겹침/기존Starlette경고2), 도움말18 통과3.19초. 실제 소유 PG18 CLI에서 근거 있는 취소는0/근거없는 과거 취소는3을 유지하면서 비공개 보고 생성 확인. 단위검사에서 6종/빈기록/수동판정·범위누락거부/비밀미포함/파일권한/기존파일·링크덮어쓰기거부 확인. Ruff/포맷/diff·정적DB219/2409/543/격리R1–R6 오류0. 스키마 불변. 전체CI/새브라우저/실기기/실회사/외부보관/실환경인수 미실행. 본인 PG fs-gw-ready02-journal-test/55438 ID+factory-studio.owner label대조 후 컨테이너/볼륨·work의임시env/ID제거. 실제계정/역할권한/운영설정/스케줄/다른checkout 변경없음. main통합/원격push/배포없음.

다음 같은02: 보관 묶음 교체·독립 최신지문 전달/외부보관 → 전경로 완전성·운영 전환 게이트 → 선택SSO → 전체회귀/10인 실환경 인수/main. 과거 근거를 되살리거나 검토 완료만으로 제한을 푸는 기능은 제공하지 않는다. 기존 전체02 승인 유효. 재현: 소유 PG18 *_test에 alembic head 후 비공개 TEST_DATABASE_URL 설정, uv run --project backend pytest backend/tests/test_journal_review.py backend/tests/test_journal_transaction_proof.py backend/tests/test_backup_journal.py backend/tests/test_security_journal.py -q --tb=short. 임시비밀/전체로그 스테이징·출력 금지.

## 2026-10-19 GW-READY-02 10차 거래 취소 판정·새 격리 복원

선택 FS_GW_JOURNAL_TX_PROOF(기본false)가 암호화 의도에 원본DB/타임라인/최상위거래 근거를 남긴다. 같은 원본의 전체 취소만 ABORT_CONFIRMED로 새 checkpoint 후보에서 제외하고, 진행 중/저장점 취소/감사 누락/원본 불일치/과거 불명은 제한 유지. CLI --classify-transactions는 6종 집계·allTransactionsSettled만 추가, 완전성false 유지. journalAbortedIntents 보고 추가. 기존 제한 복원본은 그대로 두고 새 접속 제한 DB로 다시 복원한다. 원본 변경/권한 부여/운영 개방/새 표·마이그레이션/UI 변경 없음. PARTIAL/전체회수false/readyfalse 유지.

관련 backend29 통과127.98초(집중15와 겹침/기존 경고4), 도움말18 통과2.96초. 실제 합성 PG18 전체취소·저장점취소·미확정·원본/타임라인불일치·미래ID와 이전 제한 복원본 유지/새 복원본 취소 제외 검증. 최초 pending 검사가 snapshot xmax로 UNKNOWN을 반환해 읽기전용 조회 거래 ID 상한으로 수정한 뒤 재통과. Ruff/포맷·정적DB219/2409/543·격리R1–R6 오류0. 시스템 python의 구버전 문법 분석 실패는 프로젝트 Python3.14로 재실행해 통과. 전체CI/새 브라우저/실기기/실회사/외부보관/전원차단 미검증. 본인 PG ID+owner label 확인 후 컨테이너/폐쇄복원DB/볼륨·임시env/ID 제거. 실제 역할 권한·운영환경 설정·스케줄 변경 없음. codex/gw-company-01만 변경, main 통합/원격push/배포 없음.

다음: 과거 미확인 수동 인수 기준·보관 묶음 교체/독립 지문 자동 전달/외부 보관 → 전경로 완전성·운영 전환 게이트 → 선택SSO → 전체 회귀/10인 실환경 인수/main. 기존 전체02 승인 유효. 재현은 새 소유 PG18 *_test에 alembic head 및 비공개 TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 설정 후 test_aborted_journal_rebuild/test_journal_transaction_proof/test_backup_journal_restore/test_backup_journal/test_gw_backup/test_security_journal/test_account_security_journal 실행. 비밀 파일/로그 전체 출력·스테이징 금지.

## 2026-10-18 GW-READY-02 9차 완료분: 변경 기록·백업/격리 제한 연결

branch codex/gw-company-01 / factory-studio-gw-company, 기준d9b40aa/WIP e01435f·최종gitlog. fs.gw.backup_journal이원본DBsnapshot전에독립 FS_GW_JOURNAL_EXPECTED_HEAD/체인검증, 같은백업DBsnapshot에확인된감사지문집합/체인기준을명세에저장. checkpoint는앞부분연속성검사·기준전미확인/이후의도를현재DB와대조해제한할계정/회사범위+건수만서명암호화. restore는독립최신기록지문을대상생성전에대조, 기존checkpoint재적용뒤core/HR계정중지·GW연결정지/보존중지/권한버전갱신. 취소연결재활성/새사용자생성/원본변경/운영개방없음. metadata-only와core/GW묶음지문조회, 새키백업폴더분리검사. report journalRestrictionsApplied/candidate/unconfirmed/counter/disabledAccounts/quarantinedScopes진단추가·콘솔기존요약유지/서명증거PARTIAL·완전성false/전체회수false/readyfalse. 과거미설정경로는부분검증유지/새설정은새백업부터. 새DB표/마이그레이션/UI/API없음219불변.

최종관련30통과84.90초/집중14와겹침, 도움말18/Ruff/포맷·정적DB/격리오류0. 실제PG18 TX미확정상태백업후확정·기준전미확인1·회수후재개/HR역할왕복→복원후후보6/미확인1/계정1/범위1제한·원본active/연결ACTIVE/STAFF불변·잘못된독립지문거부. 초기요약반환값에서상세필드찾던테스트를보고파일대조로보정후재통과. 경고4 Starlette/httpx/anyio/Pydantic. 전체CI/새브라우저/실기기/회사/외부저장소/전원차단미검증. 본인PG fs-gw-ready02-journal-test/55438 ID+label factory-studio.owner=gw-ready-02-journal 확인후컨테이너/내부폐쇄복원DB/익명볼륨삭제, work/gw-readiness-02-journal server.env/postgres.env/container-id제거. 앱/웹/스케줄설치없음·공유/실계정/다른checkout변경없음. 별도main843036f읽기확인/이번GW미통합·원격push/배포없음.

다음같은02: 미확인최종판정·안전한제한해제/보관묶음교체·독립지문자동전달/외부보관→전경로완전성·운영전환게이트→선택SSO→전체회귀/10인·실환경인수/main. 지문은현재수동제공, 기존30분템플릿만으로자동갱신안됨. docs/operations/GW_암호화백업_격리복원_GW-READY-02.md9차·GW_직원연결_역할변경기록_GW-READY-02.md연결. 전체02승인유효/내부재승인반복없음. 재현: 새소유PG18 *_test에alembic head 후TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER비공개설정, uv run --project backend pytest backend/tests/test_backup_journal_restore.py backend/tests/test_backup_journal.py backend/tests/test_gw_backup.py backend/tests/test_security_checkpoint.py backend/tests/test_security_journal.py backend/tests/test_account_security_journal.py -q --tb=short (30). 비밀출력/임시env커밋금지.

## 2026-10-18 GW-READY-02 9차 WIP 변경 기록·백업/복원 연결

branch codex/gw-company-01 기준d9b40aa. backup_journal 모듈이 원본DB스냅샷 전에 독립최신지문(FS_GW_JOURNAL_EXPECTED_HEAD)과암호화체인을확인하고, 백업DB에반영된지문목록을서명/암호화명세에저장한다. checkpoint는기준체인연속성을대조하고백업기준미확인/이후기록의계정·회사제한대상만저장, restore는독립최신지문재대조후core계정/HR계정중지·GW연결/보존중지재적용. 권한허용/복원완료선언없고PARTIAL/readyfalse유지. 새DB표/마이그레이션없음. 확인된지문set조회공용화, 메타데이터만수집하여스냅샷복호화내용을불필요하게보관하지않음.

집중14통과11.16초: 실제PG덤프/복원에서회수후재개·역할왕복·백업이전미확인기록도제한, 원본활성/직원역할불변. 첫추가테스트가요약반환값에서세부필드를찾던문제를보고파일대조로보정후통과. 마지막실제미확정DB트랜잭션을백업후확정하는경합검사와관련백업/인증회귀진행중,최종결과미선언. 소유PG fs-gw-ready02-journal-test/55438(label factory-studio.owner=gw-ready-02-journal)만사용. work/gw-readiness-02-journal의server.env/postgres.env/container-id비밀스테이징금지, 종료시ID/label대조컨테이너/볼륨삭제·env/ID제거필수. 첫실패테스트의폐쇄복원DB도본인컨테이너안이며외부접속없음,컨테이너최종정리에포함. API/웹/스케줄설치없음·공유/실계정/main/원격/배포변경없음. 다음운영/도움말·현황/진행최종갱신,최종검사결과확인/자원정리/커밋. 전체02승인유효.

## 2026-10-18 GW-READY-02 8차 공통 인증·HR 변경 기록

branch codex/gw-company-01 / factory-studio-gw-company, 기준fe47e1b·최종gitlog. core.security.recording(인증상태만)/hr.security_journal(회사계정+인증소유조회)추가. service.audit/MFA대기시작/record_failure(실패·발급counter)/정상·제한복구logout/emergency.system_audit/HR users회사·직원생성/비밀번호·아이디·역할·중지연결. 기존FS_GW_IDENTITY_JOURNAL_DIR/KEY_FILE둘다없으면기존동작/미수집, 일부설정·키/파일/체인실패503/해당TX취소. 실제서버설정없음. 새coverage core.security.intent.v1/hr.users.intent.v1·같은TX의기존core.audit_event(action security.journal.confirmation/entity security_journal/봉투지문/summary.subject 허용metadata). GW confirm_records가새종류를core confirmed_count로대조하여혼합체인확인. 암호화snapshot에비밀번호/해시·TOTP비밀/암호문·코드/토큰/해시·아이디/IP·원문/사유없음. 전체완전성/restore/ready자동승인없음(PARTIAL/false유지), 미수집감사/미확인대조·백업복원연결·보관교체/외부지문·운영게이트/선택SSO/전체회귀/10인실환경인수/main남음.

관련37통과138.68초·최종25통과119.28초(겹침/경고4 Starlette/httpx/anyio/Pydantic)·도움말18/Ruff/포맷/정적DB/격리오류0. 신규6에서긴급작업명조건을실제emergency_kit에맞게수정후통과, 추가계정/회사생성·로그아웃3과기존백업/격리복원재검사. 복구경합/재등록·OTPstep·세션회수·비밀미포함·저장실패rollback/같은키재시도/중복없음·DB대조. 전체CI/새브라우저/실기기/회사/외부저장소/전원차단미검증. 본인PG fs-gw-ready02-journal-test/55438 ID+label(factory-studio.owner=gw-ready-02-journal)확인후컨테이너·볼륨삭제, work/gw-readiness-02-journal server.env/postgres.env/container-id제거. API/웹/스케줄없음·실계정/공유DB/다른checkout변경없음. 별도main843036f읽기확인/이번GW미통합·원격배포없음. 포털계정보안/GW운영도움말·운영수집경로표/API계약/문서지도/현황/진행갱신.

재현: Python3.14/uv, 소유PostgreSQL18의새 *_test DB에alembic head, TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER를비공개설정후 uv run --project backend pytest backend/tests/test_account_security_journal.py backend/tests/test_security_journal.py backend/tests/test_backup_crypto.py backend/tests/test_gw_backup.py backend/tests/test_security_checkpoint.py -q --tb=short (최종25). 참고 docs/operations/GW_직원연결_역할변경기록_GW-READY-02.md 8차. work의임시비밀에의존하지말고test로그전체출력금지. 전체02승인유효·내부승인반복없음.

## 2026-10-18 GW-READY-02 7차 회사 업무 기록·DB 반영 대조

branch codex/gw-company-01 / factory-studio-gw-company, 기준1ce2a27·최종gitlog. 회사identity.execute에이어company.action도별도환경설정시암호화기록, gw.backup.capture(scope=(w,g)) 추가로회사별ACL상태/지문만수집(전역백업기본보존). v2봉투지문을동TX core.audit_event(action gw.security.journal-confirmation/entity gw.security_journal/summary generationId+operation)에저장. 새표/HTTP/UI없음. CLI --check-database는RR읽기전용으로지문/공간/세대/작업종류대조, 전체비어있지않은v2일치만 commitsConfirmed=true/0, 구형v1/빈/미확인3, DB/체인오류1. 원문/복호화payload출력없음. DBrollback후파일만남음→미확인이며실패/회수완료로단정안함. completenessfalse/restorePARTIAL/readyfalse유지, 전체경로/복원완료판정아님.

관련38통과218.04초·최종집중11통과12.91초(겹침)·도움말18/Ruff/포맷·정적DB/격리오류0. 회사작성/상신/승인·수집scope·DB표식일치/다른세대미확인·rollback의도잔존·CLI0/3·구형/빈기록확인. 초기추가테스트회사ID형비교수정후재통과, 기존Starlette/httpx경고2. 전체CI/새브라우저/실회사/기기/외부보관/전원차단미검증. 소유PG fs-gw-ready02-journal-test/55438 ID+label factory-studio.owner=gw-ready-02-journal 확인후컨테이너/볼륨삭제·work/gw-readiness-02-journal postgres.env/server.env/container-id제거. 앱/웹/스케줄없음·실계정/공유DB/다른checkout수정없음. 별도main843036f읽기확인/이번GW미통합·원격배포없음. docs/agent/GW_실사용구현_GW-READY-02.md에누적완료/남은일표·docs/operations/GW_직원연결_역할변경기록_GW-READY-02.md에DB대조의미/제약/절차. 다음공통인증/HR수집→미확인후속대조/백업복원연결→외부최신지문/보관·운영게이트→선택SSO→전체회귀/10인·실기기/실환경인수/main. 전체02승인유효·내부재승인반복없음.

재현: Python3.14/uv·새소유PostgreSQL18의 *_test DB·alembic head 후 TEST_DATABASE_URL, GW_BACKUP_TEST_CONTAINER 설정. uv run --project backend pytest backend/tests/test_gw_identity_journal.py backend/tests/test_gw_company_work.py backend/tests/test_gw_company_http.py backend/tests/test_gw_backup.py backend/tests/test_security_journal.py backend/tests/test_backup_crypto.py -q --tb=short (최종추가검사포함시개수는과거38과다름). 임시비밀을출력/커밋하지말고 work자격증명에의존하지말것.

## 2026-10-18 GW-READY-02 6차 직원 연결·역할 변경 의도 기록

branch codex/gw-company-01 / factory-studio-gw-company, 기준 c83aaf1·최종gitlog. 사용자 잘못 올린 WMS 내용 철회→GW 재개, WMS checkout변경없음. identity.execute 이후 암호화 의도 snapshot(그회사/세대 직원·연결·역할) before-commit/fsync·기록실패503/DB·영수증 rollback·멱등 중복없음. core/security/journal.py AESGCM/연속번호·이전지문/flock·기존체인검사·파일4MiB/폴더10,000 제한. tools/gw_identity_journal.py --expected-head 필수, 환경 FS_GW_IDENTITY_JOURNAL_DIR/KEY_FILE 둘다없으면 미수집·하나만있으면 거부. 키별도0600·폴더0700; 실제서버설정없음. 의도 저장후DB확정실패는 파일만잔존·완료사실아님. CLI는 commitsConfirmed/completenessConfirmed=false, restore재생미연결·PARTIAL/readyfalse유지. 전경로/DB확정·외부최신지문·외부보관/복원연결/게이트·SSO/전체인수/main남음.

검증: 소유격리PG18 관련24통과98.45초, 최종집중8통과0.39초(겹침), 도움말18·Ruff/포맷·정적DB/격리오류0. 실제HTTP 회수/저장실패rollback/같은키재시도·중복방지, 체인변조/중간·끝삭제/부분파일/20동시쓰기/CLI·SQLite확정실패/다른회사제외. 신규 실제브라우저/실회사/기기/외부저장/전원차단·전체CI 미실행. 처음 root에서vitest 실행한 document undefined는 frontend cwd로 수정후통과, 제품문제아님. schema219불변/별도main843036f(WMS병합) 확인·이번GW미반영·원격배포없음. 소유 fs-gw-ready02-journal-test/55438 ID+label(factory-studio.owner=gw-ready-02-journal) 확인후 컨테이너·볼륨삭제, work/gw-readiness-02-journal의server.env/postgres.env/container-id제거. API/웹·스케줄미실행. 로그는ignored work; 재현은커밋된test_security_journal/test_gw_identity_journal, TEST_DATABASE_URL=* _test (공백 없이) PG18·alembic head 후 uv run --project backend pytest backend/tests/test_gw_identity_journal.py backend/tests/test_gw_company_work.py backend/tests/test_security_journal.py backend/tests/test_backup_crypto.py -q --tb=short. 비밀환경/실제계정 변경금지. 전체02승인유효·내부승인반복없음. 운영절차 docs/operations/GW_직원연결_역할변경기록_GW-READY-02.md.

## 2026-10-18 GW-READY-02 5차 암호화 백업·격리 복원

서버CLI backup/check/checkpoint/restore·동일snapshot PGdump/행지문·서명명세 AES256-GCM·자체검사·별도권한대조/최신지문·자동새DB복원/접속제한/실패동결·세션회수/확인된제한재적용 구현. 실제PG18왕복·관리자200/정지직원403/옛세션401·변조/현재성/실패보고·OTP/코드소비/옛비밀번호/HR역할/보존중지검사. 관련backend28/최신집중9통과(겹침), 프런트23·lint/build통과. 자동회수기록 연속성/완전성·외부보관·실환경인수미완료→복원PARTIAL/전체회수확인false/readyfalse.30분템플릿만제공·설치없음. 도움말/서버절차/API계약갱신·schema219불변·main2be292e유지/원격배포없음. 상세 GW_실사용구현_GW-READY-02.md·서버절차 GW_암호화백업_격리복원_GW-READY-02.md. 다음자동기록/누락검증→실저장소/운영게이트→SSO/전체인수/main. WIP e2d5290,최종커밋gitlog. 최종집중9/왕복1·도움말18재검사통과(겹침),Ruff/포맷·격리0·bash통과. 소유PG ID/label대조삭제·work env/ID제거·API/웹미실행.

## 2026-10-18 GW-READY-02 5차 WIP 암호화 백업·격리 복원

사용자 다음진행 승인·같은02 범위. 암호화 AES256-GCM 묶음(DBdump+서명명세)·동일스냅샷 전표지문·서명증거·별도 암호화 권한대조/최신지문·새DB복원/행/FK/세션무효화/제한재적용 구현중. 실제PG18 왕복/2계정허용거부·변조/OTP소비/옛비밀번호/보존중지/HR역할제한8통과, 마지막실패경로·상태/문서/전체회귀추가중. 복원은PARTIAL/접속제한 유지, 독립기록자동수집/완전성·실환경인수/운영게이트·SSO남음. 스케줄템플릿만추가·실제설치없음. 소유PG fs-gw-ready02-backup-test/55438(label factory-studio.owner=gw-ready-02-backup), work/gw-readiness-02-backup의env/ID비밀은스테이징금지·종료시ID/label대조삭제. 제품API/웹미실행. PG16시스템도구대신소유PG18컨테이너도구사용. 재현: TEST_DATABASE_URL 및 GW_BACKUP_TEST_CONTAINER 설정 후 uv run --project backend pytest backend/tests/test_gw_backup.py backend/tests/test_security_checkpoint.py backend/tests/test_backup_crypto.py -q. main2be292e유지·원격/배포없음. WIP커밋이후검증계속.

## 2026-10-18 GW-READY-02 4차 보관 검토·보존 중지

현재 정책의 기한대상200건 갱신/상태·ID검색/페이지·준비/개별보류·회사중지/해제·세대별 사유이력 API/화면 구현. 달력월/한국날짜·과거정책보류유지·원문ACL 매번검사/비공개제목본문미반환·감사조회만·최근MFA/CAS/권한회수 후 receipt거부. 원본불변·보관본생성/보관완료/삭제미구현·ready=false. 관련backend23·최종프런트29통과(집중6과겹침)·lint/build통과. Chrome갱신/회사중지해제/준비/개별보류해제/이력/원문·중지변경후정책연속적용·390넘침0/pageerror0. schema219불변·도움말/운영계약갱신. 같은02 다음백업/폐쇄복원/회수재적용→운영게이트/선택SSO→전체회귀/10인·실환경인수/main반영. main2be292e유지·원격/배포없음. 상세 GW_실사용구현_GW-READY-02.md,최종커밋gitlog. Ruff/포맷·R1~R6오류0,소유API/웹종료·PG ID/label대조삭제·임시env/계정JSON/ID제거.

## 2026-10-18 GW-READY-02 3차 운영 증거 등록·복구 Chrome 확인

현재회사/최근MFA/서명·정책·코드·DB·시각 검증 후 운영 실행 증거 불변저장/목록 API·화면 구현. 실패이력유지·중복run거부·이전기준표시·일반직원차단, ready=false. API/계약19통과, 새화면/기존정책5통과, lint/build·격리오류0. Chrome합성FAIL파일등록→목록과 긴급문서다운로드→실제CLI승인→파일선택→제한복구→재등록→도움말,390넘침0/pageerror0. 실제백업/실기기/실회사아님. schema219불변. 도움말2·운영증거설정계약 갱신. 같은02 보관검토/보존중지→백업/폐쇄복원→선택SSO→전체회귀/10인·실환경 인수/main반영남음. main2be292e 유지·원격/배포없음. 상세 GW_실사용구현_GW-READY-02.md, 최종커밋gitlog. 최종프런트28·API2재검사통과(겹침)·Ruff/포맷통과, API/웹종료·소유PG ID/label대조삭제·임시비밀제거.

## 2026-10-18 GW-READY-02 2차 관리자 긴급 복구·발급량·최근 인증

현재 GW 보안 관리자 본인 긴급 문서(365일/1회응답)·서버 승인 CLI(대상회사/계정/실OSUID/0600/15분)·비밀번호 확인 후 제한 재등록 API/화면 구현. 로그인20/10분·등록/긴급문서 각각3/10분, COMPANY 회사/HR 관리 최근MFA5분. 시계혼용은DB시계로통일·commit불명확시쓴승인파일보존. 관련backend38·최종집중14통과(겹침), 프런트관련10/최신8통과(겹침)·build/ESLint통과. 새 긴급복구 실제브라우저/실기기·전체인수미완료. schema219불변. 도움말2/API계약/운영자절차 갱신. 같은02의 운영증거/보관→암호화백업/폐쇄복원→선택SSO→전체회귀/10인·실환경인수/main반영남음. main2be292e유지·원격/배포없음. 상세 docs/agent/GW_실사용구현_GW-READY-02.md. 최종커밋gitlog. 도움말콘텐츠18통과·R1~R6오류0·변경포맷통과. 소유PG ID/label대조삭제·임시env/ID제거.

## 2026-10-18 GW-READY-02 WIP 2차 긴급 관리자 복구·발급량·관리 추가 인증

사용자 다음구현+현재/남은범위설명요청. 같은02안에서 긴급문서(365일/보안버전연동/원문1회)→서버운영자CLI(UID/별도문서/DB키 접근,15분승인파일0600)→기존비밀번호LOGINchallenge+CSRF→현재GW보안관리자재검사→제한재등록 구조 구현중. 계정로그인발급20/10분·등록3/10분·긴급문서3/10분, COMPANY GW연결·역할/HR사용자관리 최근MFA확대. core는인증토큰/GW는현재권한소유, 새DB표없음219유지. 화면·API·회귀작성중이며통과미선언. 등록직후최근인증 판정에호스트/DB시각혼용발견해DB시각으로통일검사중. branch codex/gw-company-01/main2be292e보존·원격/배포없음. 소유PG fs-gw-ready02-next-test/55438(labelfactory-studio.owner=gw-ready-02-next)·ID/env는work/gw-readiness-02-next, 종료때ID/label대조삭제·임시비밀제거필수. 긴급복구 검증뒤운영증거/보관·백업/복원·선택SSO·전체인수남음·재승인질문없음.

## 2026-10-18 GW-READY-02 1차 구현·검증 기록 / 같은 ID 계속

전체설계승인유효·A~E완료아님·재승인질문없음. MFA/제한복구/재발급/세션관리·회사운영정책/API/화면·정적도움말 구현. 관련39통과+최종보안30통과(겹침), 제품Chrome등록/앱로그인/복구/정책새버전/포커스/390/도움말오류0, 프런트최종614통과/기존Flow7실패(621)·집중28·타입/린트/포맷/빌드통과. 시드부모created_at가정·도움말고아·PWA MFA후이동 수정. schema0.28/219표2409컬럼543FK 격리DDL0·현재목표Excel/ERD·이력downgrade차단확인. 실제휴대폰/실회사·SSO/긴급복구·증거/보관·백업/복원·전체인수미완료. branch codex/gw-company-01/WIP53b54c5,최종gitlog,main2be292e청결유지·원격/배포없음. 소유API8362/웹5362종료·PG55438 ID/label대조컨테이너/볼륨삭제·work임시비밀JSON/env/ID제거. 공유DB/다른checkout/실계정변경없음. 결과 docs/agent/GW_실사용구현_GW-READY-02.md·환경 docs/operations/GW_보안설정_개발검증_GW-READY-02.md·재현표준명령은결과참조. 다음은 결과의P0긴급복구/발급량제한/관리최근인증·운영증거/보관·백업/폐쇄복원·선택SSO·전체회귀,이미승인범위계속.

## 2026-10-18 GW-READY-02 WIP 전체 설계 승인·제품 구현 진행

사용자 전체설계승인+도움말문서화 요청. 같은 ID A~E 계속 진행·재승인 반복 없음. A MFA/단계인증/암호화키/DB시도제한/세션버전·기본복구/재등록/코드재발급/다른세션 API·화면, C일부 정책/서명커널/새버전 API·운영기준 UI·정적 도움말. 신규9표/기존2확장·schema0.28/219표2409컬럼543FK·현재목표Excel/ERD·소유PG18DDL오류0. 초기보안29통과·실제품Chrome390/등록·로그인·복구·도움말 오류0·프런트610통과/기존Flow7실패. 시드의부모created_at가정발견수정후관련회귀중. 긴급복구/SSO·증거/보관·백업/복원·전체인수/main반영미완료. 결과문서 GW_실사용구현_GW-READY-02.md 참조. branch codex/gw-company-01, 최종커밋gitlog·main2be292e 유지·원격/배포없음. 검토8362/5362종료, 소유PG fs-gw-ready02-test/55438만사용·종료시ID/label대조삭제 및work비밀제거필수. Python3.14/Node24사용(시스템python ast는3.14문법미지원). 다음ID착수없음·현재02계속.

## 2026-10-18 GW-READY-01 설계·검토 시제품 완료 / 전체 설계 확인 대기

신규 인증·복구·운영 범위는 AGENTS§2 전체 설계 확인 대상. 회사1/부서1/10인 기본안, GitHub EGroupware/Frappe/authentik/Nextcloud 등 비교·제안9표/기존2확장/FK19·DB/API/ERD/Excel9시트·정적 시제품 완료. Chrome11desktop/6mobile·입력 유지/포커스/키보드·오류0/외부요청0, 정적 도구 검사 통과. 실제 인증·복구·백업·정책 저장 미구현, 현재DB210표/main2be292e 불변. branch codex/gw-company-01, WIP32033db, 최종커밋gitlog 참조. 결과: [결과](GW_실사용설계_UI검토_GW-READY-01.md). 다음은 전체설계확인후 GW-READY-02 A~E 일괄 구현, 내부 단계 승인 반복 없음. 원격push/배포없음. 정적 서버8371은 검증 후 종료; 재현은 prototypes/gw-readiness/README.md. 임시 work 자료·자격증명 불필요. 실제계정/비밀번호/공유환경/다른checkout 변경없음.

## 2026-10-18 GW-READY-01 WIP 실사용 보안·운영·UI 설계 검토

사용자 GW-COMPANY-05 미완료를 GitHub GW기본으로 설계·제작, UI직관성/유효성/학습성/유연성 필수 요청. 기존01에서제외한신규인증/복구 범위라AGENTS§2전체설계확인대상. Frappe/authentik/Nextcloud/PyOTP/Authlib1차자료·commit핀대조, 10인기본안(TOTP/코드8/SSO선택·RPO60/RTO240/백업30분·문서36개월/감사12개월/백업30일)과신규9표/기존2표확장/제안FK19·DB/API/ERD/제안Excel9시트·독립시제품작성. Chrome시제품11desktop/6mobile·입력오류유지/닫기포커스/키보드/권한별검토메뉴/가로넘침0/pageerror0/외부요청0. 실제MFA/DB/운영기능미구현·현재schema210/main2be292e보존. 최종패키지·결과기록마무리중. 정적검토서버127.0.0.1:8371(소유)만실행, 실제계정/비밀번호/DB/설정/원격/배포변경없음.

## 2026-10-18 GW-COMPANY-05 WMS 통합·10인 합성 기술 검증 완료 / 실운영 인수 미완료

- 사용자05 승인·추가요청 회사1/부서1/총10명 최소 구성(창업 전 준비). GW7b41850+로컬main9f6cf36을 codex/gw-company-01에서 통합, 완료분 로컬main만반영·원격push/배포없음. [결과](GW_WMS통합_인수검증_GW-COMPANY-05.md), 운영 준비는결과연결문서. 최종commit은gitlog.
- 적용된w2b1_wms/gw_company_identity원본보존·새양부모gw_wms_merge로GW추가제약이름51개정규화. schema0.27/210표2295컬럼524FK·현재/목표명세/Excel2종/ERD동시갱신. WMS/GW/공통head3출발점기존행hash보존·DDL0·이름변경역적용/재적용보존. 두부모merge의downgrade -1은Ambiguous walk로운영복구금지,부모표삭제대신forwardfix/폐쇄복원.
- backend전체1065통과1skip(미빌드nativecore)·583.90초/경고35, 신규경로3+10인/복원2=5통과133.74초/경고11. 도구138·ruff242·정적/격리/DDL0. frontend전체606통과/기존Flow7실패·lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 관리자1+직원9 본인동의·10동시ASGI조회100/초안10/메시지10·같은키10/타인초안40410, 실제HTTP10동시조회100(p95 120.50ms)·메시지10/중복0. 로컬단발수치이며운영용량보장아님. Chrome회사전체대표흐름/10직원화면·WMS LOT보류해제2이력/390확인. 실제QMS연계/실휴대폰/실회사검증아님.
- 폐쇄pg_dump/restore210표hash동일·복원된세션10개401·백업후연결회수재적용403/관리자200. 백업0.443초·복원/검사4.720초. RPO/RTO목표미정·첨부/키/공급자/실장애미검증. MFA/SSO/추가인증·계정복구/보존·실운영담당/환경인수전출시미완료. 실제계정/정책임의변경없음.
- 검증서버8265/5265와소유PG18/55437만사용·종료후소유ID대조삭제/볼륨정리·임시자격증명/.env제거. 공유DB/원본다른작업checkout/브라우저프로필·확장변경없음. 재현은결과표준명령과커밋된test_gw_wms_merge/test_gw_company_acceptance,work비밀의존금지. 다음ID자동착수없음.

## 2026-10-17 GW-COMPANY-04 회사 화면·협업 권한 로컬 검증 완료

- 사용자 다음진행 승인. branch `codex/gw-company-01` / `factory-studio-gw-company`, 기준55a7500, WIP72735cf·11d1e51, 최종gitlog. [결과](GW_회사화면_협업권한_GW-COMPANY-04.md).
- 기존63경로 회사 입력/인증 분기·GENERAL업무·현재부모ACL/영수증전권한·전결/위임·댓글/일정/알림/채팅, 회사선택/최초설정/본인동의/G-01~13·정적회사도움말연결. BUSINESS_READY=true는설정/활성본인연결확인후만적용. 직무표시/활성·사유/CAS/마지막보안관리자보호, 늦은응답폐기·검색/페이지. 개인체험과Flow독립보존.
- PostgreSQL18.6 전용합성DB 관련156통과470.22초(기존경고6)+직원상태추가1통과4.84초(경고2), 도구139·ruff238·정적/격리/DDL오류0. 프런트전체603통과/기존Flow7실패(610건), 최초병렬ERP/MES시간초과2는집중53/전체maxWorkers2재검사통과. lint/format/build통과·기존chunk경고. 전체CI성공아님.
- 실제Chrome 로그인/최초설정/HR가져오기/직원본인동의/일반기안·승인·저장댓글/일정참석/채팅·공지390px/표시·전결/역할·연결정지시원문폐기·동일계정복귀/도움말확인,pageerror0. 합성화면10장. 실휴대폰/실회사·운영/물리인쇄미검증. 계속편집뒤포커스복원P2·회사OpenAPI표현/불명확요청의브라우저종료복구는후속.
- schema0.26/198표/headgw_company_identity변경없음·Excel/ERD재생성없음. WMS main9f6cf36/205표/headw2b1_wms와미통합. 다음05에서양쪽메타데이터/constraint충돌대조·새merge revision·기존자료보존/양쪽회귀·P0실운영인수필수. 적용migration수정금지. 다음ID는결과확인후.
- 본인컨테이너ID대조후종료·볼륨삭제, 로컬8265/5265서버종료·임시postgres.env/container-id/browser-private.json/.env제거. 실계정/비밀번호·공유DB/컨테이너·main·원격/배포변경없음. 재현은결과문서의표준명령/수동흐름,work자격증명에의존하지말것.

## 2026-10-17 GW-COMPANY-04 WIP 브라우저 검증 완료·최종 회귀 중

회사63경로/13화면·정적도움말 연결, BUSINESS_READY=true(활성본인연결·설정확인후). 합성Chrome에서최초설정/연결동의/결재승인·댓글/일정참석/채팅390px/공지/표시편집·전결/역할/연결회수시원문폐기·동일계정복귀확인. 최종백엔드관련156묶음진행중, 직원상태집중추가예정. 프런트전체601통과9실패(기존Flow7+ERP/MES시간초과2), ERP/MES포함집중53재통과·린트/포맷/빌드통과. 정적/격리0오류·ruff238. 최종도구/DDL·기록마무리중. main9f6cf36/WMS와미통합(05), main/원격/운영변경없음. 소유PG18/55437와합성계정만사용,완료후소유컨테이너/비공개자격증명정리필수.

## 2026-10-17 GW-COMPANY-04 WIP 기존 업무 API·회사 화면 연결

사용자 다음진행 승인. 기존63경로에 회사 전용 입력/인증 분기(개인 계약 보존), 전결/위임·댓글/일정/알림/채팅의 동TX 내부함수·현재부모ACL/receipt전권한, 회사 선택/최초설정/본인동의/직원·역할 화면 연결중. HTTP회사5+선행16=21 통과, 프런트typecheck/린트통과·관련UI회귀진행. BUSINESS_READY=false 유지, 실제브라우저/최종회귀·도움말은진행중. WMS main9f6cf36/205표와GW198표의schema0.26/head분기확인,05통합전양쪽대조·새merge revision필요. 신규schema변경/공유DB·계정·main·원격/배포없음. 소유합성PG18/55437만검증용. 다음: UI보완/전수권한·화면검증/도움말/최종기록,미실행 검증은 완료로 표시하지 않음.

## 2026-10-17 GW-COMPANY-03 로컬 검증 완료 — 회사 업무 공개 전

- 사용자 다음진행 승인, branch codex/gw-company-01 / factory-studio-gw-company. 기준824c4de, WIPe35eaa3, 최종gitlog. [결과](GW_직원연결_업무권한_GW-COMPANY-03.md).
- company_identity.py/company_work.py/company_router.py: OWNER bootstrap/HR snapshot·PENDING본인동의/취소·같은쌍정지복귀·명시역할/CAS/마지막보안관리자/보안사건, GENERAL결재·게시ACL/SQL목록필터·읽기권한·재배정. 기존organization.import_snapshot를동일TX재사용, 기존정책/문서함수는명시company_mode인자(개인기본false)로유효배정/활성회사계정확인. 직무문자열을역할로임시변조하지않음.
- 준비관리API만공개. 기존63개회사업무게이트/businessReady=false/capabilities=[] 유지. 실제HTTP는설정/연결/역할/관리 검증, 결재·게시전체흐름은DB내부서비스검증. UI/회사선택·협업전체ACL/도움말은04, 실운영P0/복구·MFA인수는05. 다음ID는결과확인후.
- 전용Postgres18/55437 관련147통과(146묶음401.63초·기존경고6+회사병렬/합의/참조/전결1개6.14초), 최종3집중재검사16.89초통과. 도구139/공식ruff233·dbvalidate/R1R6/DDL0. 새시나리오16개. 스키마변경/새migration없음(schema0.26/headgw_company_identity 유지), Excel/ERD재생성없음. 전체backend/frontend/브라우저/실기기/실운영미검증·기존Flow프런트7실패미해결.
- 테스트컨테이너 factory-studio-codex-gw-company-test 본인ID검증후종료·볼륨제거, 임시postgres.env/container-id/.env없음. 공유DB·실제계정·비밀번호·main·원격·운영변경없음. 표준재현명령은결과문서, work의비공개파일에의존하지말것.
- **통합주의**: 병행main은다른작업에서9f6cf36으로전진(PWA포함·WMS205표/schema0.26/w2b1_wms). 이GW는198표/schema0.26/gw_company_identity. 양쪽head가flow_board_custom에서분기. 04/통합전양쪽schema버전·추가표·제약/기존자료보존·새merge revision을대조/재검증하고 적용migration수정금지. 이번147은최신WMS main과통합된검증아님. 원본다른작업자checkout보존. 원격push/배포없음.

## 2026-10-17 GW-COMPANY-03 WIP 직원 연결·업무 권한

사용자 “다음 진행해줘” 승인. 회사 최초 설정/HR 명시적 스냅샷·PENDING 본인 동의/취소·동일쌍 정지복귀/명시 역할·마지막 보안관리자 보호, 일반 결재·게시 내부 ACL/읽기권한·재배정 구현중. 준비 관리 API만 추가하고 기존63개 업무 회사게이트/businessReady=false 유지. 최초9개 새 시나리오 통과 후 위임·조직·동시회수 및 기존회귀 진행중. schema/마이그레이션 변경없음. 전용 합성Postgres18/55437만 사용, 실제계정·공유DB·main·원격·운영변경없음. 다음: 현재 코드 전체회귀/기록 마무리, 04 UI/전체경로 통합은 이번ID 완료보고 뒤 확인.

## 2026-10-17 GW-COMPANY-02 기반 구현·로컬 검증 완료

- branch codex/gw-company-01 / factory-studio-gw-company. 기준06e4a70, WIP35be30e, 최종커밋gitlog. 사용자전체설계/구현승인. main은PWA e02097d/기록0a45562 그대로, 원격/운영미반영.
- 보안5표·새revision gw_company_identity(head flow_board_custom 뒤), schema0.26/198표2151컬럼488FK·현재/목표Excel/ERD. 회사잠금→계정잠금→세션행검증·principal/명시역할·receipt전authorize, HR읽기계약·관리회수재검증. /gw/companies,/me만상태조회·businessReady=false. 기존63업무회사요청은409,person가장400. 공개본인연결/역할/업무ACL/화면은03/04후속.
- 전용Postgres18 관련API131/기존경고6·도구139·공식ruff230파일·정적/격리/DDL0. 왕복 head→flow_board_custom→head와198테스트원장건수/hash동일. 이력있는downgrade거부·복합FK·회수경합·receipt재노출차단·시드/초기화보호 확인. [결과/재현](GW_회사인증_기반검증_GW-COMPANY-02.md). 실브라우저/실휴대폰/회사실운영/전체CI미실행, 기존Flow프런트7실패유지.
- 최초공유테스트컨테이너에서메모리부족으로중단한결과는성공아님. 별도컨테이너로131재검증완료. 검증전용컨테이너/임시자격증명은종료시제거,공용DB설정변경없음. 다음재현시새 `_test` DB/임시자격증명준비. work/env/node_modules스테이징금지.
- 다음은ID별결과확인후03(bootstrap/본인연결동의/명시역할/결재·게시/읽기·재배정ACL). 현재게이트를부분해제하지말것. P0 MFA/계정복구/보존/RPO·RTO는별도실인수미정. 원격push/실서버배포금지.

## 2026-10-17 GW-COMPANY-02 WIP 기반 구현

- 사용자 전체설계·구현 승인. branch codex/gw-company-01 / factory-studio-gw-company, 기준06e4a70, 마지막커밋gitlog. 실제DB/계정/원격/운영/main변경없음.
- 신규5표·revision gw_company_identity/명세198표2151컬럼488FK·현재/목표Excel/ERD. 회사TX/세션/권한/receipt기반, HR읽기계약, /gw/companies,/me 상태조회. 회사업무63경로는409로닫음(후속03/04), 본인대신person입력400. 시드복사/초기화·이력있는downgrade보호. [검증](GW_회사인증_기반검증_GW-COMPANY-02.md).
- 정적/DDL0·공식ruff/ExcelQA완료. 관련API/최종도구/왕복진행중. 최초공유Postgres _test 회귀는 out-of-shared-memory로중단(30통과/오류1·중단). 다른작업의공용설정변경없이 **소유컨테이너 factory-studio-codex-gw-company-test:55437** 새로생성, factory_studio_gw_company_test에서 재검사. 임시자격증명work/gw-company/postgres.env(비공개), 테스트runner/log는work/gw-company. 실제DB URL인계금지. 컨테이너정리는검증완료후본인생성분만.
- Node24/기존Python3.14 venv사용, repo임시.env는CI dry-run용합성주소(실제연결정보아님), work/db-design/node_modules는bundled artifact symlink. env/work/node_modules스테이징금지. 최종결과기록·커밋필수. 다음03은ID별결과확인후, P0인수·실기기·업무UI완료아님.

## 2026-10-17 GW-COMPANY-01 설계 대조 완료 · 제품 미착수

- branch codex/gw-company-01, folder factory-studio-gw-company, 기준PWA제품e02097d+main기록0a45562, 마지막커밋gitlog. main에는PWA만반영, 원격/운영없음. 원본antigravity보존.
- [통합설계](../modules/gw/회사인증_권한_통합설계_GW-COMPANY-01.md)/[63경로](GW_회사인증_경로감사_GW-COMPANY-01.md): 회사/조직중복없음, 신규GW5표·6권한·본인연결·GENERAL결재/협업ACL·회사query/늦은응답/receipt·회수잠금제안. 구GW-EXT-A/화면/CORE에개정안연결. 전체설계확인대상·제품/DB미적용.
- 정적검증: 기존router AST63경로와감사표63행일치, 재사용컬럼확인, 문서상대링크0오류·현황200줄·diff공백0.  제품테스트/브라우저/DB미실행. 기존PWA31/API12/전체597/604·Flow7baseline실패는이전검증이며GW검증으로재사용금지.
- 다음사용자전체설계확인→GW-COMPANY-02(DB설계/마이그레이션/게이트). spec §7 잠금순서회사16→전역user관리→세션행과계정/세션회수전수검사, 63경로+신규경로ACL·개인체험보존필수. P0실운영MFA/복구/보존미정은회사지시없이채우지않음. 원격push/운영배포금지(이번사용자범위는로컬main만).

## 2026-10-17 PWA-POLICY-01 로컬 main 반영 · GW 설계 대조 시작

사용자 지시로 PWA `e02097d`를 로컬 main에 ff 병합. 원격/실서버 변경 없음. main 폴더는 factory-studio-help-main, 새 GW 브랜치는 codex/gw-company-01 / factory-studio-gw-company. 다음은 기존 GW-EXT-A와 core.company/HR/Flow 인증·조직 재사용 대조이며 제품DB 적용 전 전체설계 확인 필요. 기존 Flow 회귀7실패 보존. 이전 아래 항목의 main 미반영 표시는 이 기록으로 갱신한다.

## 2026-10-17 PWA-POLICY-01 완료 · 당시 main/운영 미반영

- 브랜치 `codex/pwa-policy-01`, 폴더 `/Users/hwang-kyoungho/projects/factory-studio-pwa-policy`, 기준main `eaa01eb`. 마지막 커밋은 `git log -1 --oneline`. 원본 `antigravity/w2b-1b` 및 main 보존.
- 사용자 고도화 순서 승인. 첫 ID는 기존 승인 HR-TIME-01의 회사 정책 적용 보정: 요약/잔여 일 환산/연차·반차 제출/분 단위 선택. [검증](PWA_정책화면_일치_PWA-POLICY-01.md), [순서](../plan/시스템고도화_진행순서_UPGRADE-01.md). 시간대 Seoul·당일1휴게, 잘못된 정책/홀수 반차 차단. 새정책화면·DB·실제계정/정책/원장변경없음.
- 검증 관련31/31·격리근무API12/12·type/lint/format/build·Chrome모의API1440/390/4종제출JSON/pageerror0. 전체597/604·Flow기존7실패. main에서도해당7동일실패, ERP/MES재검사통과. 전체성공아님. main/push/운영/실기기미실행. `work/` 로그·스크린샷은임시, 보고서에재현절차/실패근거기록.
- 다음: AGENTS §1 ID별결과확인, 기존Flow회귀실패별도점검, GW-EXT-A는전체확인대기설계이고현재core.company와중복/차이있어최신대조먼저. 실제회사운영/실기기/장비조건을임의확정하지않음. 이전문서배포승인을새회사인증운영승인으로확대하지않음.
- 재현 Node24: `npm --prefix frontend test -- src/hr/Work.test.tsx src/hr/workPolicy.test.ts src/hr/Users.test.tsx src/portal/content-pages.test.tsx`. 격리 `_test` DB를 새로 준비하고Python3.14로head적용후 `pytest backend/tests/test_hr_work.py -q`. `.env`/비밀번호/`work`/node_modules스테이징금지.

## 2026-10-15 OPS-CAD-02 CAD·YC main 수동 운영 배포 완료

사용자수동배포요청으로 운영3a6019f→main제품c0f118e 반영(12:00KST). backend/DB/시드차이0, 정확main frontend601·CAD154/type/lint/format/build/격리/dbvalidate통과. GitHub결제차단은수동검증으로대체하여 --skip-ci-check 명시사용(CI성공아님). 보호백업r2검증·회사/계정191표건수/hash보존·APIactive/공개원점200/DDL0/최근5xx0·시드유지·공개NC JS/CSS SHA동일/비로그인비누401. 공개운영실Chrome합성NC/STEP/에너지/모의음성→3카드/3번재생/정지/복귀/출력미리보기/변경무효화/390/pageerror0통과. 실마이크/실장비/실측/운영계정쓰기미검증. 초기backup fingerprint별칭오류는배포전중단/API복구후보정·r2재검증,원장변경없음. [배포기록](main_수동운영배포_OPS-CAD-02.md). 다음사용자결과확인/실발화리허설,자동다음ID없음.

- branch main factory-studio-help-main. 운영제품c0f118e/기록커밋gitlog분리. 보호백업 /srv/factory-studio/backups/20261015-cad-c0f118e-r2. 공개검증script/명령/실행범위는배포기록참조. GitHub결제gate수동대체명시·계정/DB초기화없음·진행중antigravity미병합.

CAD-UI04 제품3818b38 main/origin 반영 완료. CI38403227492/check115315971025는 runner시작전 결제/지출한도 차단(annotation확인). 새운영UI 배포미실행·CI우회없음. 로컬검증용5263/Chrome 종료, 실제회사/계정/원장/병행브랜치변경없음.

## 2026-10-13 CAD-UI04 NC·YC 제품 화면 구조 적용 완료

사용자 UI03 Figma시안 이후 진행 승인. 좌준비단계/중앙실제뷰어/우속성YC/하단재생. 제안중앙비교→번호확대/뷰어1·YC접근·고정재생·닫기/Esc/단계복귀, 값/핸들러/원본행/출력/검증유지. CAD154/대상frontend33/build/격리/format/diff·실Chrome합성Worker/모의음성이벤트/3카드/3번진행/정지/복귀/변경무효화/원본행/FANUC미리보기/390넘침0/pageerror0통과. Figma신규조회한도로보관시안/script대체·완벽동일주장없음. 실마이크/운영새UI/실장비/DB검증미실행. branch codex/cad-ui04, 마지막커밋gitlog. [결과](NC_YC_UI_적용검증_CAD-UI04.md). 다음확인/운영·실발화검증, 다른ID자동착수없음.

- 기준main ee9555a+설계b60a2a4, 별도factory-studio-cad-ui04. 기존업무/DB/계정/원장/antigravity변경없음. 재현명령/script/PNG는결과참조. main승인범위로반영후CI확인, 우회없음. 마지막커밋 git log -1.

## 2026-10-13 CAD-UI03 NC·YC Figma 구조 시안

사용자 제안방향 확인 후 Figma Design Z9reC31WUdfLMhfC02VM2m 생성. NC우선5상태/7화면·공통5가족17variants/20변수/3텍스트스타일/113instances·클릭전환·중앙뷰포트/좌준비단계/우속성YC/하단재생. 7화면 최초구조넘침0/글꼴불일치0, 5상태캡처시각확인. 마지막진행/완료구분·초기제안차단 수정성공 뒤 Starter MCP호출한도로 캡처/최종구조재검증미실행. 이미지직전버전/시뮬레이션SVG도식/클릭은모의. 제품코드/DB/배포변경없음. 다음 사용자시안확인→최종보정검증/전체확인→별도제품UI적용. [설계기록](../modules/cad-cam/NC_YC_화면구조_CAD-UI03.md).

- branch codex/cad-ui03-design / factory-studio-cad-ui03, 기준main ee9555a. 마지막커밋 git log -1. Figma URL/node·작성script·ledger·PNG는기록폴더참조. 제품변경없음/원장계정보존. 마지막후캡처미검증을완료표시하지말것. 도구한도는Figma플랜/GitHubCI와구분.

# 2026-10-13 OPS-CI-01 로컬 CI 스크립트 개발 및 전 단계 검증 완료

- 브랜치: `antigravity/ops-ci-01`
- 마지막 커밋: `git log -1 --oneline`
- 끝난 것:
  - `tools/ci_local.sh`: `.github/workflows/ci.yml`과 동일한 순서의 1~5단계 로컬 CI 스크립트 작성.
  - `package.json`: `"ci:local": "bash tools/ci_local.sh"` 추가.
  - `tools/test_ci_local.py`: `--help`, `--dry-run`, 미지원 옵션, `_test` 접미사 검사 단위 테스트 작성 (4/4 passed).
  - 안전장치 구현:
    - Node 24 (`/opt/homebrew/opt/node@24/bin`) 및 Python 3.14 (`backend/.venv/bin`) PATH 우선 적용.
    - PostgreSQL 18.6 버전 검증 및 테스트 DB `_test` 접미사 강제.
    - 터미널/로그에 비밀번호 미노출 (DB명만 출력).
    - 4단계 DB 초기화 전 대상 안내 및 5초 취소 대기 시간 부여.
    - pytest 병렬 워커 임시 복제 DB(`factory_studio_ci_*_test`) 자동 정리.
    - 가상 환경 디스크/I/O 지연 대응: `pytest -m perf` 및 `npm test` 1회 재시도 보호.
  - 검증 완료:
    - `tools/ci_local.sh` 전체 실행: 1~5단계 전체 통과 (백엔드 1,020 passed/1 skipped, perf 1 passed, 도구 137 passed, 프런트 601/601 passed).
    - 의도적 실패 검증: 2단계 ruff format 미준수 주입 시 즉시 중단 확인.
    - `--help`, `--dry-run` 무해성 및 비밀번호 미노출 확인.
- 다음 할 일:
  - 사용자 최종 리뷰 후 `main` 병합.
  - GitHub Actions 결제 해결 전까지 배포 전 로컬 검증 표준으로 활용 (`npm run ci:local`).
- 주의점:
  - `tools/ci_local.sh` 실행 시 포트 55432의 PostgreSQL 18 컨테이너가 켜져 있어야 한다 (`uv run --project backend --env-file .env python tools/start_local.py db`).
  - 단일 프런트엔드 테스트 실행 시 반드시 `npm --prefix frontend test -- <파일>`을 사용한다 (`npx vitest run` 사용 금지).
- 재현 명령:
  - `npm run ci:local -- --help`
  - `npm run ci:local -- --dry-run`
  - `npm run ci:local`

# 2026-10-17 W2b-1b B-3 W-10 LOT 보류·해제 이력 및 QMS 연동 완료 (W2b-1b 전체 완료)

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (B-3 및 W2b-1b 전체)**:
  - W-10 LOT 보류·해제 백엔드 (`backend/src/fs/wms/`, `backend/src/fs/qms/`):
    - **DB 불변 및 이력 누적 원칙 준수**: `schema.json` 변경 없음. `wms.lot_hold`의 부분 고유 인덱스(`UNIQUE (workspace_id, generation_id, lot_id) WHERE (released_at IS NULL)`)를 기반으로, 보류 시 새 행 INSERT(`released_at=NULL`), 해제 시 UPDATE(`released_at=clock_timestamp()`), 재보류 시 새 행 INSERT로 다중 보류/해제 이력을 영구 보존.
    - 엔드포인트: `POST /lots/{id}/hold`, `POST /lots/{id}/release`.
    - 중복 및 유효성 방어: 보류 중인 LOT에 보류 시도 시 409 Conflict, 미보류 LOT 해제 시도 시 409 Conflict.
    - QMS 보류 조회 연동: `fs.qms.interface`의 `is_enabled`, `active_hold_details(conn, scoped, lot_no)`를 통해 QMS 검사 및 보류 상태를 읽기 전용으로 안전하게 조회 (`qmsHold: { active, holdNo, reason }`).
    - LOT 목록 및 상세 연동: `list_lots`에서 QMS 활성 보류 여부(`qmsHold: true/false`) 반환, `_lot_row`에서 활성 보류 정보, QMS 보류 상세, 최근 50건 보류 이력(`status: "HELD" | "RELEASED"`) 반환.
  - W-10 LOT 보류 프런트엔드 (`frontend/src/wms/Lots.tsx`):
    - 목록 테이블: LOT 상태 배지 옆에 QMS 보류 시 `<Badge tone="issue">QMS 보류</Badge>` 표시.
    - 상세 패널 현재 보류 카드: 활성 보류 중일 때 보류 사유, 출처, 일시 표시 및 "보류 해제" 버튼 제공. 미보류 시 "보류 설정" 버튼 제공.
    - 인라인 보류 등록 폼: 출처(MANUAL/QMS/EXPIRY), 원천코드, 보류 사유(2자 이상 필수) 입력 및 등록 처리.
    - QMS 품질 검사 상태 카드: QMS 모듈 활성화 여부 및 활성 보류 상세 표시, "QMS 보류 동기화" 버튼 연동.
    - 보류 이력 테이블: 최신 50건 상태(보류중/해제됨), 출처, 보류 사유, 보류일시, 해제일시, 해제사유 표시.
    - 모바일 390px 반응형 뷰포트 최적화.
  - 브라우저 실기동 자동화 검증 완료 (`frontend/scripts/verify-wms-hold-browser.mjs`):
    - 게스트 세션 시작 → LOT 등록 → 1차 수동 보류(MANUAL) → 1차 해제 → 2차 QMS 재보류 → 2차 해제 전 과정 통과 및 이력 2건 영구 보존 확인.
    - 스크린샷 5종 보존 (`wms-lots-initial.png`, `wms-lots-hold-active.png`, `wms-lots-hold-released.png`, `wms-lots-hold-second.png`, `wms-lots-mobile-390.png`).
  - A-2 검증 지표 실측치:
    - `verify_ddl_matches_schema.py` 오류 수: **0건** (205표, 2,246칼럼, PK 205, UK 425, CHECK 502, INDEX 165, UNIQUE_INDEX 46, FK 507 100% 일치).
    - 왕복 결과: `downgrade base` -> `upgrade head` 후 다시 **오류 0건**.
    - 적용 DB 목록: `factory_studio`, `factory_studio_test`, `factory_studio_ci_test` 모두 **`w2b1_wms (head)`** 상태.
    - **백엔드 pytest 요약 줄 전문**:
      - `1023 passed, 1 skipped, 47 warnings in 454.01s (0:07:34)` (not perf)
      - `1 passed, 1024 deselected, 5 warnings in 26.56s` (perf)
      - **총 1,024 passed, 1 skipped (실패 0건, 에러 0건, worker down 0건)**.
    - 도구 단위 테스트: `Ran 136 tests in 16.184s - OK`.
- **다음 할 일**: 사용자 확인 및 **W2b-1b 전체 승인** 대기 (승인 전 W2b-1c 임의 착수 금지).
- **주의점**:
  - `wms.lot`에 수량 및 만료 여부를 컬럼으로 저장하지 않는다 (원장 집계 및 실시간 판정 원칙).
  - `wms.lot_hold`는 부분 인덱스를 활용해 활성 1건만 유지하되 과거 해제 이력을 삭제하지 않고 유지한다.
- **재현 명령**:
  - `backend/.venv/bin/pytest backend/tests/test_wms.py -v`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`
  - `npm run ci:local`

# 2026-10-15 W2b-1b WMS-FIX 완료

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (WMS-FIX)**:
  - `tools/test_fs024a.py`: WMS 표 개수 가드 23으로 업데이트 (`W2b-1a` 및 `W2b*` 분기 추가, 이전 6/11 분기 유지).
  - `tools/test_dsn11.py`: `test_rebuild_from_schema_json_is_identical` 분리·제거(안 B 채택) 및 사유 주석 기록 (W2 단계마다 `schema.json`에 목표 표가 선반영되어 재생성 비교가 성립하지 않으며, 목표 설계 검증은 `test_contract_holds`, `test_rejects_regressions`, `validate_db_design.py --schema`가 전담).
  - `tools/rebuild_target.py`: docstring 상단에 "W2 이후에는 schema.json이 진화해 결과가 목표 파일과 달라진다. 설계 단계 재현용이다" 안내 추가.
  - `docs/modules/wms/WMS_보강설계_DSN-13.md`: 8절(구현 및 스키마 반영 메모) 추가하여 `apply_dsn90.py` 재적용 시 `CMMS_ISSUE` 중복 생성 제약 및 기존 WMS 3표 칼럼 순서(DDL 대조 0건으로 기능 영향 없음) 문서화.
  - `backend/alembic/versions/20261013_w2b1_wms.py`:
    - `downgrade()` 복원 시 `c831_check` -> `c781_check` (`storage_location`), `c818_check` -> `c768_check` (`source_claim`)로 pre-w2b1 원래 제약 이름 복원 (`alembic downgrade base` 전체 왕복 성공).
    - `MODULE_CHECKS = []` ruff 포맷 보정.
  - `backend/tests/test_wms.py`: ruff I001 import 정렬 보정.
  - `frontend/src/portal/favorites.test.tsx`: W-10 LOT 메뉴 추가에 따른 메뉴 카탈로그 개수 가드 113 -> 114 보정 (`menuCatalog` 114개 키·경로 고유성 100% 통과).
- **검증 결과**:
  - `python -m unittest discover -s tools -p 'test_*.py'`: **136 passed (OK)**.
  - `npm run ci:local`: **1~5단계 전체 통과 (SUCCESS)**.
    - 1단계: DB 정적 검증(`npm run db:validate`, 0 errors), 격리 감사(`audit_schema_isolation.py`, R1~R6 0 errors), 도구 단위 테스트 (136 passed).
    - 2단계: 백엔드 ruff check & ruff format check (227 files, 0 errors).
    - 3단계: 마이그레이션 적용 및 `verify_ddl_matches_schema.py` (0 errors), pytest (1,022 passed, 1 skipped, 1 perf passed).
    - 4단계: `clear_test_data.py` -> `downgrade base` -> `upgrade head` -> `verify_ddl_matches_schema.py` (0 errors, 완벽한 왕복).
    - 5단계: 프런트엔드 `typecheck`, `lint`, `format:check`, `build`, `test` (75 test files, 603 passed, 0 errors).
- **다음 할 일**: 사용자 확인 후 **B-3 (W-10 보류·해제 이력)** 착수.
- **주의점**:
  - `lot_hold`는 이력 표: 해제 시 UPDATE 금지, 행 새로 쌓기 (`status='HELD'` / `'RELEASED'`).
  - 현재 보류 여부는 최신 행으로 판정 (`active_holds` CTE 검증).
  - 브라우저에서 보류 걸기 → 해제 → 재보류 흐름 검증 필수.
  - QMS 보류 조회 연동(읽기 전용, `fs/qms/interface.py`).
- **재현 명령**:
  - `python -m unittest discover -s tools -p 'test_*.py'`
  - `npm run ci:local`

# 2026-10-15 W2b-1b B-2 W-10 LOT 조회·등록 완료

- **브랜치**: `antigravity/w2b-1b`
- **끝난 것 (B-2)**:
  - W-10 LOT 백엔드 (`backend/src/fs/wms/`):
    - `wms.lot` 조회/등록/수정 API (`GET /lots`, `GET /lots/{id}`, `POST /lots`, `PATCH /lots/{id}`).
    - **LOT 수량 DB 미저장 원칙 준수**: 단일 출처는 재고 이동 원장(`wms.stock_move`). N+1 방지를 위해 `WITH lot_stock AS (...)`, `active_holds AS (...)` 단일 질의로 현재고(`qty_on_hand`) 및 활성 보류 산출.
    - 만료 여부 DB 미저장: `business_today()` 기준 조회 시 실시간 판정 (`isExpired`).
    - 페이징: `fs/common/page.py` (`Page(offset, limit).checked()`) 표준 적용.
    - 품목별 `lot_tracked` 플래그 반영 전표 줄 검증(`_validate_lines`).
  - W-10 LOT 화면 (`frontend/src/wms/Lots.tsx`):
    - 목록: LOT 번호, 상태 배지(가용/보류/만료), 품목, 현재고(원장 합계), 입고일, 유효기간, 공급처 LOT, 출처, 관리(상세).
    - 필터: 품목 드롭다운, 상태 드롭다운, 키워드 검색, 만료만 보기 토글.
    - 등록 패널 (`FormPanel`): 품목 선택(선택 시 `shelfLifeDays`로 유효기간 자동 제안), LOT 번호, 입고일, 유효기간, 공급처 LOT, 출처.
    - 상세 패널 (`DetailPanel`, wide): 기본 정보, 원장 집계 총 재고 및 위치별 재고 분포(`locations`), 보류 상태/이력(`holds`), **B-3 보류 안내 문구** 명시.
    - 메뉴 및 라우트 등록: `menu_catalog.json` (W-10 LOT·보류), `WmsRoutes` (`/wms/lots`).
    - 표준 훅: `useSend` 훅으로 CSRF 토큰 및 멱등키 보장.
  - 검증 결과:
    - 백엔드 WMS 테스트: `pytest backend/tests/test_wms.py -v` (17 passed).
    - 프론트엔드 테스트: `npm --prefix frontend test -- src/wms/wms.test.tsx` (12 passed).
    - 프론트엔드 검사: `npm run lint` (0 errors), `npm run typecheck` (0 errors), `npm run format:check` (Prettier 통과), `npm run build` (tsc & vite) 통과.
    - 백엔드 린트: `ruff check backend/src/fs/wms/` & `ruff format --check` 통과.
    - **브라우저 실기동 및 기능 검증 (`verify-wms-browser.mjs`)**:
      - `/wms/items` (B-1 품목 보강 확인): 테이블 컬럼 및 등록 폼에 유효기간, ABC, 안전/최대재고, PLM 필드 노출 확인.
      - `/wms/lots` (B-2 LOT 등록): `LOT-20261015-LIVE` 등록, 목록 및 상세 패널 정상 확인.
      - **원장 수량 실시간 대조**: 기초재고 전표 750 EA 확정 후 LOT 목록 및 상세에서 현재고가 즉시 정확히 750 EA로 증가 일치 확인!
      - 390px 모바일 뷰포트 레이아웃 검증 완료.
    - **A-2 검증 지표 실측치**:
      - `verify_ddl_matches_schema.py` 오류 수 (적용 후): **0건**
      - 왕복 결과: `downgrade -1` -> `upgrade head` 후 다시 **오류 0건**
      - 적용 DB 목록: `factory_studio` 및 `factory_studio_test` 둘 다 **`w2b1_wms (head)`** 상태.
- **다음 할 일**: 사용자 확인 후 **B-3 (W-10 보류·해제 이력)** 착수.
- **주의점**:
  - B-3 사용자 확인 전 착수 금지.
  - DB 변경 없음 (W2b-1a 확정분 유지).
- **재현 명령**:
  - `TEST_DATABASE_URL="..." pytest backend/tests/test_wms.py -v`
  - `npm --prefix frontend test -- src/wms/wms.test.tsx`
  - `npm --prefix frontend run lint && npm --prefix frontend run typecheck && npm --prefix frontend run build`
  - `node frontend/scripts/verify-wms-browser.mjs`

# 2026-10-13 W2b-1b B-1 품목 보강 (W-07) 완료
CAD-V03 제품 c0efb5b main/origin push 완료. 운영 새흐름 배포 미실행. 최종 main CI도 runner 시작 전 결제/한도 차단 확인(check115285673525). 실마이크 미검증, 기존 MES 브랜치 보존.

## 2026-10-13 CAD-V03 YC 예제·음성 요청 흐름 보정 완료

YC 예제 클릭→마이크 요청/합성NC·STEP·소재·장비·품질 준비→헤이와이씨/파일최적안요청→정지카드3→번호확대재생. Step4는 계산만 하고 자동팝업 제거. 실제업로드는 기존조건검증 유지/후보수강제없음. CAD154/대상frontend33/build/격리/format·실Chrome모의인식이벤트 전체흐름/진행률·정지/복귀/390/입력중단/재시도/pageerror0. 실마이크/운영새흐름/실장비/DB검증미실행·CI우회없음. branch codex/cad-v03, 기준main65aaea5; main반영/push는 승인된 기존반영범위. [결과](YC_음성요청_흐름검증_CAD-V03.md). 공유MES변경없음, 이전antigravity로컬휴디코드와최신빌드구분. 다음결과확인/실발화·운영검증, 다음ID자동착수없음.

- 재현: Node24 prototype npm ci/test, frontend npm ci/build 및 대상33검사, 정적빌드5260+assets/cad-v03/voice-flow-check.mjs. 마지막커밋 git log -1. 실마이크는모의인식과구분. 계정/DB/원장/비밀번호변경없음.

# 2026-10-12 OPS-CAD-01 main push / CI billing blocker

CAD17/V02 merged into main (13f3a8e), NC help markup fixed. CAD154/frontend596/build/isolation/format passed. Runs38258159540/38258223617 failed before any step due to billing or spending limit. Server41ca68d/APIactive preserved; latest CAD deployment not executed. Next: owner resolves Billing & plans, rerun exact main HEAD CI, then backup/standard deployment. See docs/agent/main_CI_배포점검_OPS-CAD-01.md. Final commit: git log -1 --oneline. Shared MES changes untouched. Backend/DDL roundtrip and new browser/microphone checks not run.

## 2026-10-12 CAD-V02 STEP·YC 카드 완료 인계

- branch codex/cad-v02, `/Users/hwang-kyoungho/projects/factory-studio-cadv02`, 최신main3d850fc+CAD17f2a1052 통합aebce5d, 구현커밋8e47eb9, 최종인계커밋 `git log -1 --oneline`. [결과](YC_음성카드_STEP검증_CAD-V02.md)/[계약](../modules/cad-cam/음성카드_시연_설계_CAD-V02.md).
- 완료: 운영STEP30초초과재현→커널준비90/읽기30/진행/재시도·시제품기능안내, 기본호출헤이와이씨/YC+휴디별칭, 정지3D캡처후보카드→번호선택/나머지숨김/확대기존뷰어재생→전체/닫기/復元/무효화. 실제계산조건만표시, Ra가짜값없음. CAD154/프런트대상15/build/격리/포맷·Chrome정적빌드STEP재시도/32초지연·전체카드/3번진행/정지/반복/복귀/Esc/390통과.
- 다음사용자결과확인후main/push/배포/운영STEP재검증·맥북Chrome실발화리허설. 실마이크/실장비/품질전력/90초만료/DB/운영수정배포 미검증. 공유MES5파일·main보존, backend/secretary/계정변경없음. 다음ID자동착수없음.
- Node24 테스트/build·빌드정적NC화면 재현은 결과보고참조. 새검증서버5258/5259·headless Chrome 종료, dependency공유symlink제거·work/env스테이징제외. 원본첨부App.tsx는UI참고만하고실행하지않음.

## 2026-10-10 CAD-17 FANUC 검토용 완료 인계

- branch codex/cad-17, `/Users/hwang-kyoungho/projects/factory-studio-cad17`, 기준main e137f61/내부기반738433d, 구현커밋 dcf7a8f, 최종인계커밋 `git log -1 --oneline`. 사용자기종미정 검토용출력 승인. [결과](FANUC검토용_NC출력_CAD-17.md)/[계약](../modules/cad-cam/NC출력_설계_CAD-17.md).
- 완료: FANUC review profile/O1~7999/G4 P밀리초·기존 NC→출력/다시열기·재해석/원본행매핑/의미보존·품질후보재계산·UI다운로드/JSON·30초취소/무효화/도움말. 검토용100%, 실장비용아님. CAD153/프런트대상15/build/격리·Chrome 실제다운로드/재업로드/재출력/1440·390 통과. 합성 파일/캡처 docs/agent/assets/cad-17.
- 다음: 사용자 결과 확인 후 반영 또는 기종/매뉴얼확정 후 실제post/장비 검증. FANUC 실제 interpreter/H·D/실기계/실측/음성/운영/DB 미검증. main병합/push/배포 없음. 다른 작업자 사이드바 코드 보존.
- 재현: Node24에서 prototype test/frontend대상test/build, nc-review.html의 도움말/출력 순서. node_modules 공유 symlink는검증후제거; 필요시npm ci. 새 로컬Vite5257 검증종료, Chromeheadless닫음. work/env스테이징없음. 다음ID자동착수없음.

# 2026-10-12 HELP-01 다섯 시스템 도움말·운영 배포 완료

제품027505f main/origin/실서버 반영(21:58KST), 정확HEAD CI38249603910 SUCCESS: backend1010/skip1·perf1·frontend596·tools133·타입/lint/format/build/DDL왕복. 표준배포 성공·CI우회 없음·보호백업20261012-help-f14b75b 검증·회사59/회사+회원59원장/계정 전체hash보존·템플릿sv-20261009-gw1유지·APIactive/DDL0/공개원점200/5xx0·기존이지스active/office200·공개10주소200/JS해시일치·운영 도움말 렌더링/관련이동 확인. 배포 후 결과 기록 커밋은 제품과 구분한다. 상세 [구현 대조·검증](제품도움말_구현대조_HELP-01.md).

이번 작업 정적도움말·진입링크/문서경로·검사/기록30파일, 업무기능·DB/API/시드 변경 없음. HR H16~18·Flow사이드바/행편집/집계/보관복구/G14·15 현행연결·GW합성/실회사·CAD가정/실측·3D시연 구분. 격리API116·최종main 로컬frontend596·링크317/끊김0. 실제 합성 GW/Flow/근무직원신청→관리자승인/E1CAM/NC후보재생/CNC시연 확인. 실제 회사쓰기·계정/비밀번호/확장 설정 변경 없음. 실휴대폰·마이크·실가공/실설비 및 로컬WebGL불가 3D렌더링/걷기 미검증.

통합은 별도factory-studio-help-main의main에서 수행; 원래 체크아웃의 병행antigravity 브랜치·MES 미추적 도움말 보존. 검증 서버/탭 종료, 기존8000/5173 유지. 다음은 사용자 요청 후에만 P1근태정책-화면일치→실회사GW인증/권한→PWA실기기, P2Flow업무일지/규모→CAD실측/음성→3D실데이터. 재현: Node24 frontend npm test/typecheck/lint/format:check/build, db:validate, 프로젝트uv Python3.14 격리감사. pytest는 격리 *_test DB만 사용. 후속 개발 자동 착수 금지.

# 2026-10-12 ANTI-HELP-01 MES 화면 도움말 4편 작성 및 정리 완료

- **브랜치**: `antigravity/anti-help-01`
- **마지막 커밋**: `12162f3` (ANTI-HELP-01 완료 문서 갱신 커밋)
- **끝난 것**:
  - `content/help/mes/m-16.md` (M-16 불량·사유 코드)
  - `content/help/mes/m-17.md` (M-17 작업자·근무조)
  - `content/help/mes/m-19.md` (M-19 라벨 양식)
  - `content/help/mes/m-26.md` (M-26 공정 검사 기준)
  - `backend/src/fs/core/menu_catalog.json` 기준 미제공 화면(M-20, M-25, M-27, M-29) 링크 및 관련 화면 참조 정리
  - `frontend/src/portal/content-pages.test.tsx:50`의 `count("mes/m-")` 기댓값 15 → 19 갱신
  - HR 3편(H-16, H-17, H-18)은 main 커밋 `f14b75b`에서 이미 완료되어 있어 중복 작성하지 않고 ANTI-HELP-01은 종료
- **검증**:
  - `npx --prefix frontend vitest run src/portal/content-pages.test.tsx` (18/18 통과)
  - `npm --prefix frontend test -- src/mes/masters.test.tsx` (5/5 통과)
  - `npm --prefix frontend run build` (통과)
  - Playwright Chromium 브라우저에서 `/mes/codes`, `/mes/workers`, `/mes/labels`, `/mes/inspection-items`의 "? 도움말" 클릭 시 4개 문서 정상 로드 및 "이 화면 열기 →" 링크 동작 검증 완료
- **다음 할 일**: 사용자 확인 후 `antigravity/anti-help-01` 브랜치를 main에 병합 검토. 후속 W2a-1b2-rest 작업 착수는 사용자 지시 대기.
- **주의점**: 다른 antigravity 세션과의 충돌 방지를 위해 임의로 브랜치를 checkout하지 않고 `antigravity/anti-help-01` 브랜치에 그대로 두고 대기한다.
- **재현 명령**:
  - `npm --prefix frontend test -- src/portal/content-pages.test.tsx`
  - `npm --prefix frontend run build`

# 2026-10-12 W2a-1b2-rest MES 공정 경로(M-14)·BOM(M-15) R-1~R-5 전체 완료

- 브랜치: `antigravity/w2a-1b2-rest`
- 마지막 커밋: `d64a95f` (style(mes): format Routes.tsx and versions.test.tsx with prettier)
- 진행 상태: **R-1 ~ R-5 전체 완료 — 사용자 최종 확인 및 main 병합 대기**
- 작업 내용:
  - R-1: `mes.route_step` 컬럼 확장(표준 CT, 준비 분, 외주 여부, 외주처), `schema.RouteSteps` 객체 목록 변경, `validate_steps` 검증 및 정규화, 백엔드 테스트 통과.
  - R-2: `Routes.tsx` 단계별 4개 속성 편집 폼 및 목록 컬럼 추가, 외주 체크 해제 시 외주처 코드 비움/감춤, 빈 칸 null 정규화, `versions.test.tsx` 갱신 및 신규 속성 추가 테스트(9 passed), 전체 프론트엔드 597테스트/typecheck/lint/build 통과, Playwright 브라우저 실동작 검증 완료.
  - R-3: `bom_line.issue_process_id` 추가 (`repository.LINE` 컬럼, `schema.BomLineIn`, `service.validate_lines`에서 `mes.process` 검증). `PUT /boms/{id}/lines`를 `service.set_bom_lines`로 연결하여 `material_item_id` 키 기반 맞춤 저장(UPDATE/INSERT/DELETE) 구현. 기존 줄 UPDATE로 `bom_line.id` 보존 및 하위 대체 자재 유지. 삭제 대상에 대체 자재가 딸려 있으면 409 `REFERENCED_BY_OTHERS` 반환.
  - R-4: `mes.bom_substitute` 조회·편집 API (`GET /boms/{id}/lines/{lineId}/substitutes`, `PUT /boms/{id}/lines/{lineId}/substitutes`). 초안(`draft`)에서만 편집 가능 (`VERSION_LOCKED` 409). 완제품 자신/원래 구성 자재와 동일 품목/중복 등록/미존재 품목 차단. BOM 개정(`revise`) 시 새 버전의 구성 자재 라인 아래로 대체 자재 자동 복제.
  - BOM-FIX: 자재 순서 교체 시 `UK(workspace_id, generation_id, bom_version_id, line_no)` 위반 해결. `reconcile_bom_lines`에서 살아남는 줄의 `line_no`를 1단계에서 `-idx` 임시 음수로 일괄 업데이트 후 2단계에서 최종 순서 번호로 업데이트하여 충돌 방지. 자재 순서 교체 시 `bom_line.id` 및 하위 대체 자재 보존 테스트(`test_bom_lines_reordering_preserves_line_ids_and_substitutes`) 추가 및 34 passed 통과.
  - R-5: `Boms.tsx` 화면 보강:
    - 구성 자재 등록/수정 시 투입 공정(`issueProcessId`) 선택 드롭다운 (비우면 `null` 전송, "공정 지정 안 함").
    - 구성 자재 행별 대체 자재 펼치기/접기 토글 및 대체 자재 추가/삭제 기능 연동 (`PUT /boms/{id}/lines/{lineId}/substitutes`, `ratio` string 정규화).
    - 자재 순서 변경(↑/↓) 및 "순서 저장" 버튼.
    - 대체 자재가 딸린 구성 자재 삭제 시도 시 409 `REFERENCED_BY_OTHERS` 응답을 감지하여 해당 행 옆에 인라인 에러 안내(`대체 자재를 먼저 지우세요`) 표시.
    - 게시·폐기 버전에서는 대체 자재 추가/삭제/관리 버튼 비활성화/숨김.
    - 390px 반응형 뷰포트 지원.
  - 검증:
    - 백엔드: `backend/tests/test_mes_route_bom.py` 34 passed, 전체 MES 138 passed (전체 통과), `ruff check`/`ruff format` 통과.
    - 프론트엔드: `npm run typecheck`, `npm run lint`, `npm run build` 통과, `versions.test.tsx` 13 passed, 프론트엔드 전체 75파일 601 passed.
    - 브라우저 E2E 실동작 검증(Playwright): 포털 접속 -> 게스트 로그인 -> `/mes/boms` -> 신규 BOM 생성 -> 투입 공정 지정 자재 2건 추가 -> 대체 자재 추가 -> 순서 교체 및 저장(BOM-FIX 확인) -> 페이지 새로고침 후 순서 및 대체 자재 유지 확인 -> 대체 자재 있는 줄 삭제 시도 시 409 인라인 안내 표시 확인 -> 대체 자재 삭제 후 줄 삭제 -> 게시(게시 상태 잠금 전환) -> 390px 뷰포트 확인까지 전체 통과 확인.
- 주의: main 브랜치 병합은 수행하지 않고 사용자 확인을 기다린다.

---

# 2026-10-12 HELP-01 제품 도움말 구현 대조·로컬 검증 완료

사용자 다섯 시스템 문서화·main/origin·기존 실서버 배포 승인. 기준main3306777, 브랜치codex/product-help-20261012, 별도factory-studio-help 체크아웃. 제품 정적 도움말과 진입 링크만 변경; 공유main의 진행 중 MES 변경은 보존/제외. HR H-16~18 신설, Flow 행편집·부모집계·보관복구·권한·/work-os 이동 보정, GW 전체 합성 업무 안내, CAD 가정/실측·3D 시연 구분과 README 이력 표시. 상세 [구현 대조](제품도움말_구현대조_HELP-01.md).

로컬 검증: frontend596/75파일 전체 통과, 타입/lint/format/build 및 링크 보정 후 관련36통과. 프로젝트uv Python3.14 격리감사193표471FK오류0. 격리 *_help_api_test에서 근무/계정/Flow/GW116통과, *_help_browser_test+8046/5246은 실제API 합성UI 전용. 기존8000/5173·실제 회사/계정/비밀번호/브라우저확장 변경 없음. 다음: main/push→정확HEAD CI→기존백업/배포→운영검증. 아직 배포 완료 아님. 후속고도화 자동착수 금지.

# FLOW-03 행 편집·접힘 UX 운영 배포 완료

브랜치 main/origin main. FLOW-03 행 편집·접힘 UX 보정 운영 배포 완료(2026-10-11 18:41 KST): 제품2c30b42 main/origin/실서버 반영. 접힌 그룹68px 한 줄·업무/하위 업무 행 우측 삭제/복구·상세 편집 제목/설명2항목·담당자/상태/중요도/일정/진행률 행 편집. CI38128137226 SUCCESS(backend1010/skip1·perf1·frontend596·tools133), 실제 로컬 저장/새로고침/삭제/복구/390px 검증. 기존 Flow12원장전체hash보존·보호 백업·APIactive/DDL0/공개200/최근5xx0·공개JS/CSS SHA동일. 운영 로그인 UI는 기존 세션 만료로 미검증. FLOW-02b 후속.

보호 백업: /srv/factory-studio/backups/20261011-flow-row-2c30b42. 재현: frontend Node24 npm test / typecheck / lint / build / format:check. 상세 [행 편집 검증](Factory_Flow_행편집_검증_FLOW-03.md). 최종 문서 기록 커밋은 운영 제품과 구분, 다음 ID 자동 착수 없음.

# FLOW-03 행 편집·접힘 UX 보정 (2026-10-11)

브랜치 main. FLOW-03 행 편집・接힘 UX 보정 구현/로컬 검증 완료(2026-10-11): 접힌 그룹68px 한 줄·하위 업무 행 우측 삭제/복구·상세 편집은 제목/설명·참고 링크2항목·담당자/상태/중요도/일정/진행률 행 편집. 실제 로컬 합성 보드 저장/새로고침/삭제/복구·부모 집계 확인, 기존 업무 보존. DB/API 변경 없음. main push·정확HEAD CI·운영 배포 진행 예정. FLOW-02b 후속.

검증 명령: frontend에서 Node24 PATH로 npm run typecheck / npm run lint / npm test / npm run build / npm run format:check. 운영 배포는 기존 tools/deploy.sh의 정확 HEAD CI 성공 확인 후 보호 백업을 먼저 한다. 실제 계정/비밀번호/확장 설정 변경 없음. 운영 로그인 UI는 세션 만료로 미검증 상태를 유지한다. 상세: [행 편집 검증](Factory_Flow_행편집_검증_FLOW-03.md).

# 2026-10-11 FLOW-03 인라인 생성·작은 카드 운영 배포 완료

제품 b255c6c 로컬main/origin/main/실서버 반영(17:55 KST). 정확HEAD CI38124898787 SUCCESS: backend1010/skip1·perf1·frontend592/75파일·tools133·타입/lint/format/build/DDL왕복. 기존 Flow12원장 전체행 건수/hash보존·보호 백업20261011-flow-inline-b255c6c·APIactive·DDL0·원점/공개/Flow200·최근5xx0·공개JS/CSS의 로컬/서버SHA동일. 로컬 실제 합성 검증 보드에서 새 업무/하위업무 인라인 생성·이름 저장·새로고침 유지·새 그룹 이름 편집 확인 후 검증 보드 보관. 운영 기존 브라우저 탭은 세션 만료/401로 로그인된 UI 확인 미실행, 재로그인 필요. 운영 업무 쓰기·계정 생성·확장 변경 없음. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 최종 문서 기록 커밋은 제품과 구분, FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 실제 Figma 인라인 생성 보정

열린 Figma 직접 조작/카드 치수 측정 후 사용자 승인. 새 업무/하위 업무 모달 제거·서버 생성 직후 부모 아래 인라인 이름 편집·새 그룹 자동 이름 편집·중복 전송 잠금·실패 입력 유지/IME 처리. 3카드96×72/진행률160×72. 로컬 별도 합성 보드 저장/새로고침/그룹명 검증 및 보관·기존 보드 복귀. DB/API 변경 없음. 정확HEAD CI와 운영 배포 예정. 상세 docs/agent/Factory_Flow_인라인생성_실제품검증_FLOW-03.md. 다음: 검증 완료→main push→CI 성공→보호 백업/표준 배포→공개 UI/원장 보존 확인. FLOW-02b 자동 착수 없음.

# 2026-10-11 FLOW-03 승인 UI 제품 보정·운영 배포 완료

승인 시제품과 제품 daa1905의 실제 UI 차이를 확인하고 단독 셸·breadcrumb/공유·설정 메뉴·표 헤더·상태 배지·아이콘·간격·체크박스/하위업무 선을 보정했다. 회사 등록/API/DB 변경 없음. 회사 미등록 admin과 게스트의 공통 메뉴 유지 브라우저 검증 포함. 제품27a3db0 로컬main·origin/main·실서버 반영(10:53 KST).

정확HEAD CI38102155660 SUCCESS(backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/format/build/DDL왕복). 보호된 서버 백업20261011-flow-ui-27a3db0 검증·Flow12원장 건수/hash보존·APIactive·DDL0·공개/원점/메뉴/CSS200·미로그인API401·최근5xx0. 운영 빌드+합성응답으로 화면 캡처·진입/구주소/컬럼drawer/Escape/공유/390px 확인. 실제 운영 쓰기·계정 생성·확장 설정 변경 없음. 상세 docs/agent/Factory_Flow_승인UI_제품보정_배포검증_FLOW-03.md. 다음 FLOW-02b는 별도 범위, 자동 착수 없음. 최종 문서 커밋은 운영 제품과 구분.

# 2026-10-11 FLOW-03 UI 승인 이미지 차이 보정

사용자 승인 시제품과 실제 제품의 표 헤더·native 상태 선택·상시 설정·간격 차이를 확인해 수정. Flow 중복 플랫폼 헤더 제거, breadcrumb/공유·제목 즐겨찾기, 내보드+ 생성/설정 메뉴, SVG 탭·검색·필터·내업무, 상태 배지/키보드 select 유지, 날짜/프로필/체크박스·그룹 스트립/하위업무 선·부가 메뉴 정리. 회사 등록·보드 설정/권한·기존 업무 CRUD 유지. DB/API 변경 없음.

로컬 frontend590/75파일·타입/전체lint/build/범위format·실제품 브라우저 합성7업무/3그룹·39%·런처/구주소/컬럼drawer/Escape/공유 열기닫기·390px overflow0 통과. 출력 Factory_Flow_FLOW04_UI.png는 제품을 합성 데이터로 실행한 캡처이며 운영 데이터가 아니다. main push/정확HEAD CI/운영 배포 진행 예정. 운영 실제 회사/계정 생성 및 확장 설정 변경 없음.

# FLOW-03·HR-USERS-02 운영 배포 완료

2026-10-11 10:09 KST 제품 daa1905를 로컬 main·origin/main·실서버에 반영했다. Figma 보드 UI·자유 컬럼6종/셀·그룹 복제/보관/삭제/복구·총 관리자 회사/첫 회사 관리자 웹 등록 포함.

정확 HEAD CI38099879569 SUCCESS: backend1010/skip1·perf1·frontend590/75파일·tools133·타입/lint/build/DDL 왕복 통과. 로컬/운영 백업 후 flow_board_custom 적용, 기존10원장 건수/hash 보존. 운영 백업 /srv/factory-studio/backups/20261011-flow03 검증. tools/deploy.sh 성공·CI 우회 없음·서버 APIactive·DDL0·공개/원점200·최근2분5xx0. 보드/내업무/사용자관리 URL200, 미로그인 세션/관리역량/Flow API401.

실제193표2102열471FK·목표381표925FK 및 Excel/ERD 동기화. 시드 유지, 실제 운영 회사/계정/비밀번호 생성 없음. 앱 런처→Factory Flow; admin→사용자 관리→회사 등록. FLOW-02b 업무일지 트리/가상화 후속. 확장 설정 유지. 최종 기록 커밋은 문서만이며 운영 제품 daa1905와 구분한다.

# 2026-10-11 GW-FLOW-03 배포 진행

- 현재 작업 디렉터리 /Users/hwang-kyoungho/projects/factory-studio, branch main (사용자 main 반영·push·배포 승인). 이전 WIP 9f0baa8.
- 구현·검증은 docs/modules/flow/Factory_Flow_간결보드_FLOW-03.md 최신 기록. 새 head flow_board_custom, 로컬 적용/원장10표보존 완료.
- 다음: exact HEAD origin/main push → FS-009 CI 통과 → 서버 백업/기존 tools/deploy.sh → 공개/DDL/원장 hash/5xx 확인 → 배포 기록 커밋/push.
- 운영 실제 회사·계정·비밀번호 자동 생성 금지. 사용자 admin → 사용자 관리 → 회사 등록에서 입력.
- 재현: uv run --project backend --env-file .env python tools/verify_ddl_matches_schema.py; npm --prefix frontend run build/test; uv run --project backend python -m unittest discover -s tools -p 'test_*.py'. 테스트는 별도 *_test DB를 지정한다.

# 2026-10-11 진행 중 인계

- branch: codex/gw-flow-simple-design. 사용자 전체 구현/main/push/배포 승인.
- FLOW-03 자유 컬럼/셀+그룹 상태/복제, HR-USERS-02 웹 회사 등록, Figma UI 구현 중.
- 테스트 DB DDL 일치, 프런트 집중 8 통과. 전체 기능/CI 검증과 실제 배포 미완료.
- 다음: 테스트 수정/통과, Excel/ERD 동기화, 로컬 main 반영/CI/백업/배포.
- 실제 계정 비밀번호 생성 금지, 예제/운영 원장 초기화 금지.

## 2026-10-10 FLOW-02a 운영 배포 완료·로컬 admin 클릭 비교

Factory Flow 앱 런처 카드→/work-os/boards·/work-os/my-tasks 독립 진입, flow API/10표 이관, 구GW URL·즐겨찾기·멱등 요청 보존, 새 백자/먹색/쪽빛 UI를 운영 제품31623b0으로 배포 완료(21:03 KST). 정확한 HEAD CI38048961871 success: backend1006/skip1·perf1·frontend588/75파일·tools133 및 타입/lint/빌드/DDL왕복·격리 통과. 초기 모듈 개수 상수 실패는 MODULE_KEYS 기준 보정 후 전체 CI 재통과.

서버 백업20261010-flow-31623b0(DB/프런트·비공개/commit/10표digest) 목록·압축 검증 완료. 초기 SSHstdin을 Docker가 소비한 백업 준비를 입력/dev/null 지정으로 재실행·완전 검증 후 배포. tools/deploy.sh exit0/CI우회0, 서버git31623b0/alembicflow_split/APIactive·10표행수/hash보존·DDL0·공개/원점/JS/CSS200·최근5xx0·구/신API미로그인401. 템플릿 시드 버전 동일로 유지, 사용자/비밀번호/DB초기화 없음. 제품 스키마0.24.1·191표2074열464FK. 날짜별 업무일지8표/가상화 FLOW-02b는 후속 미구현.

추가 로컬 admin 조사: 기존Chrome탭 링크 클릭·Enter 이동 차단 재현/직접URL 관리자 정상. busy=false/disabled0/DOM가림·inert0. 동일 프로필·admin세션 새탭 사용자관리/런처/MES 이동 정상 및 사용자 직접 “새 탭은 정상 동작” 확인, 정상 비교탭 유지. 정상탭에도 확장오류가 있어 403과 클릭 차단 인과 단정 금지. 기존탭 입력 차단 원인미확정, 계정·서버권한/확장설정 변경 없음. 로컬8000/5173유지. 실제운영계정쓰기/휴대폰설치 미검증.

상세: [배포 검증](Factory_Flow_독립시스템_배포검증_FLOW-02a.md). 후속 기록은 문서만이며 운영 제품31623b0과 구분. 다음 FLOW-02b 별도 범위 확인.

재현: main 정확한 HEAD CI success→tools/deploy.sh 사전점검/실행, gh run view38048961871. 백업은 서버에만 유지하고 Git/outputs로 복사하지 않는다. 브랜치 codex/gw-flow-deploy-report의 후속 기록을 main ff병합/push; 마지막 커밋 git log -1. 제품 배포31623b0은 기록 커밋과 구분.

## 2026-10-10 FLOW-02a 독립 진입·보드 이관 인계

사용자 앱 런처 Factory Flow/독립 보드 분리 진행 및 기존 배포 승인 유지. 신규 참조 폴더의 src/App.tsx/index.css 읽기 분석, 백자#F7F7F6/먹색#1A1C1E/쪽빛#1F2D3D/한지#E8E8E6/청자#2D4442/프로필#E2E3E5·4% 그림자 적용. 참조 파일은 변경하지 않았다.

런처 열 번째 카드 Factory Flow → /work-os/boards, /work-os/my-tasks, 내 공간/메뉴/도움말/카탈로그 연결. 독립 UI에 기존 네 보기/권한/댓글 유지·아바타/진행바 추가. 기존 /gw/projects,/gw/my-tasks query/hash보존 redirect. API 패키지 fs.flow·/api/v1/flow, 구APIalias는 같은 원장 사용. gw.work_*10표 SET SCHEMA→flow, 기존ID/시퀀스/FK/댓글/감사이력 보존. Flow모듈 별도등록/off, 새회사/템플릿/복사정리 목록/후기허용 확장. 메뉴즐겨찾기 순서/중복보존 전환. 기존 gw.projects.* receipt namespace 유지로 재시도 중복0, 데이터엔티티는flow. 날짜별 업무일지8표/가상화 고도화는 이번 요청의 진입·분리와 구분하며 후속 FLOW-02b 미구현.

schema0.24.1/headflow_split·191표2074컬럼464FK, 목표379표918FK·Excel/ERD 동기화. 전용DB DDL0·프로젝트9검사(구API멱등/off독립/실제보드·댓글/10표역이관digest/즐겨찾기왕복 포함), 기존관련26검사, frontend588/타입/lint/format/build, tools133/격리0 통과. 초기 migration SQL 문법·신규테스트 operation명 오류 보정 후 재통과. 로컬 DB 백업 pg_restore검증 후 migration 적용·10표행수/digest보존/DDL0. Chrome 실제 제품UI+합성응답으로 런처진입/oldURL선택유지/색상계산값/390px가로넘침0 확인; 운영 실제계정쓰기 검증은 아니다. 사용자8000/5173·실제계정/비밀번호/확장 설정 유지. main push/CI/운영배포는 후속 확인 중이며 완료 후 이 문서와 인계 갱신.

다음: 정확한main제품커밋 CI success 확인→실서버DB/파일백업→API쓰기중지→기존배포스크립트→10표digest/DDL/publicassets검증. 데이터삭제/초기화 금지. 로컬8000/5173유지.

## 2026-10-10 FLOW-02a 독립 진입·보드 이관 WIP

사용자 앱 런처 Factory Flow·/work-os·기존 보드 분리 구현 및 배포 승인. codex/gw-flow-entry에서 작업 중. Flow 패키지/API와10표 SET SCHEMA·메뉴/즐겨찾기 이전 구현, 검증 진행 중. 날짜별 일지8표/FLOW-02b는 미구현으로 구분한다. 첫 마이그레이션 SQL 문법 검사 실패를 수정 중이며 운영/로컬 실DB에는 아직 미적용. 기존8000/5173 유지. 다음: 전용 테스트DB·역이관 보존/권한/alias·UI검증 후 main push, CI 통과 뒤 백업·쓰기 중지·운영배포. 제품 완료로 표시하지 않는다.

## 2026-10-10 GW-PROJECT·HR 운영 배포 완료

사용자 실서버 배포 요청으로 main/origin/main의 제품 커밋 `98402d978428a60bd070bda910f740fca234f765`를 기존 `tools/deploy.sh`로 실제 배포했다. 기존 운영 `31af096` → `98402d9`, DB `w0_fav_menu_shape` → `gw_projects`. GW 프로젝트 보드·내 업무, 회사 근무/PWA·관리자 사용자 관리 등 기존 main 변경 포함. Factory Flow 독립 Work OS/업무일지는 설계·검토용 시제품만이며 제품 구현/DB 이관은 아직 승인 대기다.

CI 차단 Ruff migration 서식과 HR 사용자 테스트 Prettier 서식만 보정했다(`71d140a`, `98402d9`). migration AST 비교로 실행 의미/SQL 불변 확인. 최종 CI [38044267825](https://github.com/go8105/factory-studio/actions/runs/38044267825) success: backend1004 passed/1 skipped, 성능1 passed, frontend75파일588검사, 타입/lint/서식/빌드, DB upgrade·downgrade 왕복/DDL·격리·설계 검증 및 도구 검사 통과.

운영 서버 전용 백업 `/srv/factory-studio/backups/20261010-projects-71d140a`에 DB dump/프런트·비공개 자산/이전 커밋을 저장, pg_restore 목록 및 gzip 무결성 검사 완료. 시드 버전 동일 `sv-20261009-gw1`로 기존 템플릿 유지. API active, 공개·원점200, 실제 운영 DDL오류0, 재시작 후 최근2분5xx0. 공개 `/gw/projects`, `/gw/my-tasks`, `/hr/users` 및 JS/CSS200; 미로그인 세션·프로젝트 회사 API401. Python urllib 기본 요청은 Cloudflare403이었으나 curl 공개/원점 검증은 정상; 앱500과 구분한다. 실제 회사 로그인·쓰기/휴대폰 설치는 미검증, 실제 계정/비밀번호/회사 생성 없음. 기존 로컬8000/5173·확장 설정 유지.

상세: [배포 보고서](GW_프로젝트_main_배포검증.md). 이 후속 기록 커밋은 문서만이며 운영 제품 커밋98402d9와 구분한다. 다음: FLOW-01 전체 설계 확인 후 FLOW-02 개발.

재현: main에서 `tools/deploy.sh`(정확한 HEAD CI success 필요), `gh run view 38044267825`, 공개 `https://eip.hugh-d.com`. 브랜치 codex/gw-deploy-report → main으로 문서 보고서만 병합/push. DB 초기화·실제 사용자 생성·비밀번호 설정은 하지 않는다. 백업은 서버에만 보관하고 Git/outputs로 복사하지 않는다.

## 2026-10-10 FLOW-01 독립 Work OS·업무일지 전체 설계

사용자가 GW 프로젝트 보드를 독립 시스템으로 분리·제공 UI 코드 이식·업무일지 고도화 요청 및 이어서 진행 지시. 방향 승인과 신규 전체 설계 확인을 구별한다. Factory Flow(Work OS·프로젝트 관리·협업), module/schema/package flow, 프런트 /work-os, API /api/v1/flow. 기존 포털 /flow 맵 유지. GW10표 SET SCHEMA로ID/S/댓글/이력 보존, 새 일지8표/총18표191컬럼 설계. 기존 제약42/FK31/상태 보존. 실제 schema0.24.0/headgw_projects·191표464FK 유지.

새 공통 설계: docs/modules/flow/README.md 및 Factory_Flow_독립시스템_업무일지_FLOW-01.md·flow-design.json·flow-design.mmd·별도설계Excel·ui-preview.html. 본부/실→팀기간→팀원→날짜별일지, 제출본회사공유/임시본본인만/지정검토자·자가검토금지/immutable revision. HR원천interface읽기·계정명자동연결금지/수동조직fallback. 구GW주소/메뉴즐겨찾기보존,계정/스키마독립모듈등록·멱등이행·세대정리·성능/가상화·검증명세 포함. 첨부는FLOW-03후속,첫공개는독립앱+UI+일지.

검증: 참조React코드분석(캘린더/간트EmptyView,고정명단/child boolean,일부무동작버튼),설계18표191컬럼/관계·앵커/문서링크/XLSX3시트통과. Spreadsheet artifact-tool 생성·3시트렌더확인. UI시제품JS문법/브라우저검색·일지트리·우측패널·가상제출·390px확인. 모두합성예제/탭내시제품으로 실제API저장 없음. 제품pytest/vitest/실제DDL/migration/부하/배포 미실행(제품변경없음). 사용자원본폴더/실제회사/계정/비밀번호/확장설정 변경없음. 기존5173/8000유지,검토8766서버는종료.

브랜치 codex/gw-flow-design, 설계 문서만 main 반영 대상. 사용자 전체 설계 확인 전 FLOW-02 제품구현/DB변경 시작금지(AGENTS §2 및 설계완료 승인기준). 다음: 설계확인후 새codex/gw-flow-implementation에서원장독립이관·UI·일지동일범위구현→검증→로컬백업적용→mainpush. 전체설계후데이터책임/권한변경이커서기존GW-PROJECT승인으로대체하지않는다. 최종커밋은git log -1. 검토화면/Excel은사용자 outputs와저장소모듈에보존하여work임시파일없이재개가능.

## 2026-10-10 GW-PROJECT 첫 공개 구현 완료

회사 공동 보드·그룹·1단계 하위 업무·복수 담당자·상태/중요도/기간/진행률·표/칸반/기간 캘린더/기본 간트·내 업무·댓글/변경 이력·보드 즐겨찾기/보기 설정 구현. GW G-14/G-15와 도움말 추가. 회사 회원 기본 VIEWER, 지정 EDITOR/OWNER만 업무 수정, 플랫폼 ADMIN/HR ADMIN 자동 권한 없음. 멤버십 fresh authorize·회사 격리·version409·멱등 재시도·마지막 OWNER 보호·자식 집계·보관 배치 복구 검증. 부모 기준 페이지 조회가 자식을 함께 반환한다.

schema0.24.0/headgw_projects: 실제191표2074열464FK, 목표379표918FK. migration/메타데이터/DB Excel/실제·목표 ERD 동시 반영. 기존 COMPANY에 GW 활성 세대 등록, 합성 체험 데이터 복사 없음. 실제 로컬 DB는 pg_dump 백업 후 적용, 카탈로그 대조0오류. 전용 테스트 DB에서 downgrade/upgrade 왕복 및 대조0오류.

검증: backend 전체 병렬1001통과·1skip·성능검사1실패(병렬 부하에서5.817초), 해당 성능검사 단독 재측정 통과. 최종 프로젝트 API7통과. frontend75파일588검사·lint·typecheck·build 통과, 도구133통과. 합성 전용 브라우저에서 네 보기·상태 저장/재조회 확인. 실제 회사/계정/비밀번호 및 확장 설정 변경 없음. 사용자 기존8000/5173 서버 유지. 운영 배포는 미실행. main 병합 및 origin/main push 대상이며 최종 커밋은 git log -1로 확인.

한계: 파일/자유 열/외부 공유/자동화/실시간 동시 편집/오프라인/의존 일정은 후속. 내 업무 최대1000건, 보드는 모든 부모 페이지를 읽어 네 보기에 표시하며 대규모 화면 렌더링 성능은 별도 부하 검증 전.

# GW-PROJECT-01 인계 — 2026-10-10

브랜치 codex/gw-project-design → main. 설계 문서만 반영하며 최종 커밋은 git log -1로 확인. 프로젝트 보드 신규 범위는 사용자 전체 설계 확인 전. 회사 공유·기본 VIEWER/지정 EDITOR·네 보기·10개 신규 테이블 후보. 기존 GW 체험 actor/seed_ready와 회사 프로젝트 경로를 분리한다. 실제 데이터/비밀번호 복사 금지. 상세 DB/API/권한 명세와 설계 Excel/ERD 후 개발 가능. HTML 시안 JS 문법 검사만 완료, 브라우저 file URL 정책 차단으로 렌더링 미검증. 기존 5173/8000 서버·확장 설정 유지.

## 2026-10-10 LOCAL-AUDIT 진입 오류·메뉴 클릭 전체 점검

사용자 기존 Chrome 탭에서 메뉴 클릭이 반응하지 않는 현상 재현. 서버는 점검 시작 시 중지되어 있어 공통 기동기로 DB 확인 후 backend/frontend 재실행, 현재 localhost:5173/8000 유지. 실제 Chrome의 기존 admin 세션으로 새 탭에서 MES/QMS/SPC/WMS/FEMS/BEMS/ERP/GW/HR 9개 대시보드 클릭·데이터 로딩·오류 알림 없음 확인. 내 공간·즐겨찾기 편집 창 열기/취소·사용자 관리 회사 조회·CAD iframe 로딩·3D 공장·전체 흐름·도움말도 확인. 콘솔 permission error는 Monica extension ofpnmcalabcbjgholdjcjblkibolbppb의 /writing/get_template_list, EventEmitter/ObjectMultiplex 경고는 MetaMask extension nkbihfbeogaeaoehlefnkodbefgpgknn에서 발생. 해당 확장 오류는 정상 새 탭에서도 발생하므로 클릭 차단 원인이라고 단정하지 않음.

기존 탭은 새로고침/문서 재진입/DevTools 종료 후에도 클릭 차단 재현, JS debugger는 Not paused, 앱 busy=false/내비게이션 버튼 활성/앱 dialog·고정 덮개 없음. 기존 탭의 정확한 차단 원인은 미확정. 사용자는 확장 설정 유지 선택; 확장/쿠키/계정/비밀번호 변경 없음. 정상 동작하는 새 Chrome 탭을 사용자 관리에 남김. 앱 코드 변경 없음·DB 스키마 변경 없음. 새 게스트 검증은 기존 로컬 게스트 상한 때문에 RATE_LIMITED였으며 데이터를 지우거나 상한을 변경하지 않음. 실제 증거는 사용자-facing outputs/로컬_메뉴_동작확인.png. 다음: 새 탭에서 사용, 기존 탭의 환경 문제는 추가 재현 정보 또는 사용자 별도 브라우저 비교가 필요. 점검 결과 문서만 main push.

- 최종 커밋은 git log -1. 점검용 서버 8000/5173을 현재 유지했다. IntelliJ에서 재기동하려면 기존 서버를 먼저 종료해야 하며 사용자 실행 서버와 구별할 것. 정상 새 탭과 기존 문제 탭을 혼동하지 말 것. 이전 LOCAL-START의 API500과 이번 extension403/클릭 차단은 별개다.

## 2026-10-10 LOCAL-START 로컬 500 및 IntelliJ 주소 통일

실제 로컬 DB/Colima가 중지된 상태에서 DB 연결 거부 재현. 기존 IntelliJ 전체 구성은 DB 기동 없이 front/backend만 실행했고 Compose 플러그인도 없었다. 공통 start_local.py가 기존 Colima 프로필/DB를 기동하고 실제 DB 연결 확인 후 서버를 실행한다. 동시 DB 준비 파일 잠금, Compose standalone fallback, 기존 데이터/볼륨 보존. 공유 .run Local - All 추가와 PC 기존 .idea 명령 보정. backend 표시/접속은 localhost:8000, front는 localhost:5173; Vite DNS verbatim 고정 및 프록시 IPv4 지정으로 표시 변동/IPv6 API 연결 실패 방지.

검증: 중지된 Colima/DB 실제 복구, backend/frontend 동시 기동, localhost front HTTP200, 만료/위조 쿠키 API401(500 없음), 기존 admin의 current_session 서비스 조회 성공. schema head hr_time_check 유지, 실제 계정/비밀번호 변경 없음. frontend584·타입/lint/build·기동스크립트 Ruff 통과. 사용자 main push 승인 유지. 검증용 앱 서버는 종료하고 DB 유지; IntelliJ Local - All로 실행. 운영 배포 없음.

- 브랜치 codex/local-startup → main fast-forward/push, 최종 커밋은 git log -1. 재현: uv run --project backend --env-file .env python tools/start_local.py backend 또는 frontend. 공유 .run 구성은 IntelliJ 프로젝트를 다시 로드하면 표시된다. 사용자 PC의 기존 .idea 구성도 보정했으며 .idea 자체는 Git 제외다.

## 2026-10-10 W1-HR-USERS 관리자 사용자 관리 완료

사용자 요청으로 터미널 최초 비밀번호 설정을 관리자 웹 화면으로 대체했다. 기존 활성 플랫폼 admin 로그인 → /hr/users → hugh-D Company 선택 → 각 계정 관리 → 비밀번호 설정·사용 재개. 새 사용자 아이디·비밀번호·사원 코드·이름·근무 권한·올해 연차를 함께 등록한다. 플랫폼 ADMIN은 회사 목록, 회사 ADMIN은 자기 회사만 관리하며 STAFF/게스트는 접근 불가. 비밀번호는 반환하지 않고 변경 시 기존 세션 종료. 자기 계정 변경·마지막 회사 관리자 제거·다중 회사 계정 변경 차단, 멱등 요청/동시성/감사 기록에서 비밀번호 제외. 로컬 두 예제 계정은 사용자 설정 전까지 비활성 유지.

검증: 관련 backend29개 및 새 사용자 API4개 재검증, frontend전체584개/새 화면4개 재검증, 타입·lint·format·build 통과. Chrome 별도 합성 테스트 DB에서 실제 회사 조회/계정 관리 폼 표시 확인(브라우저 비밀번호 제출은 사용자에게 맡김). 스키마 변경 없음: schema0.23.3/headhr_time_check·181표433FK. 사용자 main push 승인 유지; 운영 배포/실제 휴대폰 설치 미실행. 다음: 기존 admin에서 두 계정 비밀번호 설정 후 사용. 회사 정책 편집·다음 연도 연차 자동 부여는 후속.

- 브랜치 codex/hr-user-management → main fast-forward/push 반영, 마지막 커밋은 git log -1 참조. 이전 터미널 활성화 안내는 이번 사용자 요청으로 대체됨. 실제 비밀번호를 요청/기록하지 말 것. 재현: frontend에서 npm exec vitest -- run src/hr/Users.test.tsx, backend TEST_DATABASE_URL에 독립 테스트 DB 지정 후 pytest backend/tests/test_hr_users.py.

## 2026-10-10 W1-HR-TIME 구현 완료 / 최초 비밀번호 사용자 입력 대기

- 브랜치 codex/hr-time-company, WIP cd46db4 이후 최종 커밋은 git log -1. 사용자 main 즉시 push 지시 유지, 로컬 main·origin/main 반영. 운영 배포는 미실행.
- [검증/시작안내](회사근무_구현검증_W1-HR-TIME.md). 회사 멤버십+HR 사원 연결, 실제 원장은 기존 개인 AUTO 근태와 분리. 게스트 실제API403, 합성 체험만 허용. schema0.23.3/headhr_time_check. 회사 코드/정책/직원 2명은 로컬 DB에 생성됨. 계정 hugh-admin/hugh-staff는 disabled, 사용자 터미널 getpass 활성화 대기. 비밀번호를 요청하거나 문서에 기록하지 말 것.
- 활성화: 저장소에서 `uv run --project backend --env-file .env python tools/create_work_company.py --activate`. 예제회사 두 비활성 계정만 최초 활성화, 기존 활성 계정 비밀번호는 덮어쓰지 않음.
- 검증: 회사API9+활성화1, 도구133, 프런트580, 스키마9, DDL왕복오류0·Chrome 별도 테스트DB 실제직원 출퇴근/관리자 기록정정. 최초 전체backend991통과/1skip/DDL1실패는 후속 CHECK 재생성으로 고쳐 해당 스키마9 검사 재통과. 기존 적용 migration SQL 변경 없음.
- 다음: 사용자가 PC 터미널 비밀번호 입력→두 계정 실제 사용 확인. 운영 반영을 진행할 경우 현재 head CI 확인/정식 deploy.sh·서버 백업·운영 회사/계정 별도 준비 및 사용자 터미널 비밀번호 설정·HTTPS Android/iPhone 실제 설치검증. 로컬DB 계정 데이터를 운영에 복제하지 않음. 추가 직원 초대/다음 연도 연차 부여/정책 설정 UI는 별도 후속.
- 테스트 DB factory_studio_hr_time_test만 검증 데이터 초기화에 사용. 사용자 로컬 factory_studio는 백업 후 새 revision만 적용, 초기화하지 않음. 별도8001/5181/5182 검증 서버 정리, 사용자8000/5173 유지.

## 2026-10-10 HR-TIME-01 회사 공동 출퇴근 PWA 설계

사용자 회사공동/버튼출퇴근/1시간시간차 확정. [설계안](../plan/회사공동_출퇴근_PWA_HR-TIME-01.md) 작성: HR소유·GW바로가기, 회사멤버십/사원연결 선행, 실제회원/합성게스트체험 분리, 실제시각원장·휴가분단위·출장·PWA오프라인제출금지. 기존AUTO예정근태·반차승인clock초기화와 실제기록 충돌 확인. 구현/DB변경/회사활성화 없음. 다음: 전체설계확인 후 회사접근기반부터 구현.

## 2026-10-10 사이드바 긴 메뉴·별 배경 보정 / main 반영

사용자 main 즉시 push 승인. W0-FAV-2 전체 즐겨찾기·아이콘 접기와 이번 고정24px아이콘/긴이름줄바꿈/별주변투명배경을 함께 main에 병합한다. 관련23테스트·타입검사 통과, 실제Chrome 긴게시판명 overflow없음/아이콘24px/별버튼배경투명 확인. 운영배포는 이번요청범위에 포함하지 않음. 이후 같은 사이드바 작업은 검증 후 main push 승인 유지.

## 2026-10-10 W0-FAV-2 전체 즐겨찾기·아이콘 사이드바 완료

- 사용자 요청: 현재 솔루션 필터를 제거해 모든 솔루션 즐겨찾기를 저장한 순서로 표시. 라벨/접근성 이름에 솔루션을 표시해 중복 대시보드 구분.
- 넓은 화면 접기는 메뉴를 숨기지 않고 아이콘 레일로 전환. title/aria-label로 설명과 키보드 이동 제공. 좁은 화면 서랍은 기존 표시 유지.
- 등록 별: 채운 금색/노란 배경/진한 테두리. 미등록은 회색 윤곽.
- 검증: frontend575/72파일·typecheck/lint/build 통과. 회귀는 교차GW/WMS 링크·접기 유지·전체전환/추가저장 포함. 실제Chrome GW에서 전체6개 표시→접기→MES아이콘 이동 확인.
- 브랜치 codex/favorites-sidebar-all. 이번 변경은 로컬 개발 서버 반영, 운영 배포는 아직 하지 않음. DB 변경 없음.

## 2026-10-10 GW·즐겨찾기 main 병합·운영 배포 완료

제품31af096 로컬main/원격main 병합 후 CI전체통과 및 정식deploy.sh 완료. 운영HTTP200/DDL오류0/최근5xx0/API14검사 통과, 실제Chrome저장·새로고침·MES등록메뉴표시 확인. 로컬DB구버전500은 백업 후 head마이그레이션으로 복구·기존공간유지. [결과](GW_즐겨찾기_main_배포검증.md). 후속기록커밋은문서전용, 제품배포31af096.

# GW·즐겨찾기 main 병합/배포 진행 (2026-10-10)

- 사용자 로컬main병합/운영배포 명시승인, 원격push 포함. 기존CI실패2건 보정: 목표재생성 partial 구현 호환·목표361표866FK/전체미구현설계 보존, tools133통과. SPC 테스트 시계만 고정·정책무변경, SPC18통과. 실제schema0.22.1/headw0_fav_menu_shape 유지.
- 현재 codex/workspace-favorites, 최종커밋git log -1. 로컬mainaf10726·originmain3ff4cf5·운영f860e8b 모두조상/깨끗함. 다음 로컬mainfast-forward→origin/mainpush→해당headCI통과→운영백업/정식deploy.sh(우회옵션없음)→공개사이트실제메뉴저장/사이드바/API/DDL확인→최종문서. 아직배포완료아님.
- 서버 158.247.236.136 /srv/factory-studio/app, service factory-studio-api, 공개 https://eip.hugh-d.com. 다른서비스/secretary DB 미접촉·초기화없음. 서버.env 읽거나출력하지 않음.

# W0-FAV 즐겨찾기 완료 인계 (2026-10-10)

- 사용자 이미지2장·참고React 분석→실제9솔루션108메뉴 연결. codex/workspace-favorites, 시작GW검토bfae108/WIPca74aaa, 최종커밋git log -1. [검증과화면](내공간_즐겨찾기_검증_W0-FAV.md), [계약](../ui/내공간_즐겨찾기_W0-FAV.md).
- 내 공간 카드/3열선택·검색·순서·임시선택취소, 사이드바등록메뉴/전체전환·별버튼. 공간 서버저장·초기화보존·게스트격리·회원다른세션공유. 최근브라우저별. 미확인응답멱등재시도/실제GET·다른업무잠금보존.
- schema0.22.1/headw0_fav_menu_shape/core.workspace2컬럼3CHECK(173표1918컬럼412FK). 실제·목표Excel/ERD/base_task동기화. 독립 factory_studio_favorites_test만 적용, 최초revision적용후무변경·JSONnullCHECK새revision. 별도왕복DB4회DDL0·삭제완료.
- frontend575/72파일·최종lint/format/typecheck/build, Ruff/format206·설계격리0. backend신규8/전체982통과·기존SPC실패1/skip1·독립perf1. tools131통과·기존DSN목표재생성오류1. 두기존main실패근거는GW_main_병합검토.md. 전체CI통과아님.
- Chrome6카드/ERP추가/순서저장·새로고침유지/MES등록2메뉴만/최근메뉴, 390px가로넘침0·44px적용·Esc포커스/Tab순환 확인. 회원실기기간UI/실마우스드래그는미검증(두회원로그인API/버튼순서검증).
- 공유main af1072669d6441d3b70605ff01054bc294cca393 깨끗함. main병합/push/운영배포/공유DB적용없음. 다음 반영 시 기존CI차단 해결 후 최신main재검토, 두플랫폼마이그레이션과프런트함께배포. 새업무자동착수없음.
- 재현: 독립 *_test DB+PYTHONPATH=backend/src:backend, xdist원본복제중접속금지·동일DBpytest동시금지. 로컬검증서버/생성브라우저탭종료, node_modules공유symlink제거·work/env스테이징제외.

## 이전 GW 병합 검토 인계

# GW-main 병합 검토 완료 인계 (2026-10-09)

- codex/gw-dsn31, 제품17f0f18, 최종검토커밋은 `git log -1 --oneline`. main af10726 직접조상/충돌0·fast-forward 가능. 실제 main 병합/push/배포 없음. [검토](GW_main_병합검토.md).
- 수정: tools/apply_fs030a.py 초기8표 포함 검사로 후속19표 보존, test_fs030a.py 확장 무변경 회귀. 기본표 누락 거부 유지. 도구7+4통과.
- 검증: PG18 빈DB/main/GW/rollback/reupgrade 카탈로그4회0·frontend566/71파일·lint/format/typecheck/build·Ruff202파일·DB설계/격리0. backend974통과/기존main SPC실패1/skip1, 독립perf1통과. tools131통과/기존main DSN재생성오류1. 원본main에서 둘다재현. 처음loadscope실행은 공유템플릿 초기화순서파손으로 무효, 기본분배 재실행 결과가 최종.
- 다음: DSN목표재생성·SPC측정시각 테스트 CI차단 해결 후 최신main재대조/병합. 새시드 배포시새템플릿 필요. 실제회사A/ERP확정통제/신규원천/인쇄PDF는 기존제한 유지.
- 사용자 새 요청: 참고 React시제품·이미지 기반 내공간 메뉴 추가/순서편집 및 MES/ERP 등 즐겨찾기만 표시하는 사이드바. 다음 별도 codex 브랜치에서 구현. GW 검토를 제품 전체CI통과로 인계하지 않는다.
- 재현: 독립 PG18 `_test` DB 환경 주입, PYTHONPATH=backend/src:backend, `pytest backend/tests -q -n 4 -m 'not perf'`, 이후 `pytest backend/tests -q -m perf`; tools 전체unittest/프런트 명령은 검토문서 참조. 비밀 접속값 Git에 없음.

## 이전 GW-e 완료 인계

# GW-e 완료 인계 (2026-10-09)

- codex/gw-dsn31, 시작8216636/WIPd78e534, 마지막커밋 `git log -1 --oneline`. worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_시드도움말_GW-e.md).
- 완료: GW19표98행/sv-20261009-gw1(HR4부서10담당자·일반/ERP매입초안·병렬대기·전결/위임/기존순차이력·댓글/일정/알림/채팅). ERP공개조회 snapshot 연결, JSON SQL NULL구분·GW사건시각 보존. 복사 FK외 JSON단계/위임/전결ID·범위/월/시각 및 알림refId/eventKey변환, KST상신월재계산, 같은TX지도정리. 원본/digest/코드금액조직·채팅seq/clientKey/readCursor보존. V-GW검증, 도움말13+공통안내·정적흐름3노드3연결·DSN90실제계약.
- 검증: DB신규6통과. 전체backend974통과/1실패/1skip(379.71s), 다른새공간GW빈가정 조직격리1건 테스트만 보정→조직17전체 재통과(37.85s), 총975서로다른테스트확인(보정후전체재실행은안함). frontend566/71files·최종타입/build/전체ESLint·전체backendRuff/변경format/diff·DB설계/173표412FK격리0. rootRuff기존policy import1건보정. Chrome새guest11/gen13 시드10명·기안현황2/1/2, 실제위임→합의→종결, 알림링크→일정응답, 댓글revision/삭제, 채팅seq1/2→3,390px/도움말/흐름, 처리후V-GW통과. 증거 docs/agent/assets/gw-e.
- 다음: 사용자 결과 확인 후 **main과 병합 검토**. main공통엔진optional authorize·MasterScreen·MES테스트mock·seedversion·migrationparent/schemametadata·current/progress/HANDOFF충돌을 재대조할 것. 아직push/merge/배포 없음. 새시드배포는 새템플릿생성 필요(기존운영템플릿수정금지). 실제도입A/TEAM계정ACL·ERP F44 및 ERP발주/경비·PLMECO원천제공은 별도후속. 네이티브인쇄PDF/대량운영부하 미검증 유지.
- 재현: 전용 *_test DB만 사용, mainvenv재사용시 PYTHONPATH=backend/src:backend 필수. 같은DB의 독립pytest 동시실행금지; -n4 원본DB복제중preview접속금지, 끝난workerDB집중검증가능. API8073/Vite5273·검증탭 종료, viewport복원·node_modules 심볼릭링크 정리. 접속값은Git/문서/로그에 넣지 않았다.

## 이전 GW-d 기록

# GW-d 협업 인계 (2026-10-09)

- 브랜치 codex/gw-dsn31, 기준b39e274, WIP2a30415, 마지막커밋 git log -1 --oneline. worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_협업_GW-d.md). main/공유DB/push/merge/배포 없음.
- 완료: 댓글revision/삭제표시·부서공지/현재조직열람, 개인/부서 월/주 일정·응답/수정/취소, 알림 동일TX recipient/event_key중복0·읽음/현재열람, 채팅 1:1/그룹·HTTP저장/활성3초조회·seq/clientKey·탈퇴차단. G-04/05보강·G-11/12/13, 도움말4신규+G04보강. EIP전체공간공지·공통4종제공(None off/빈결과구분). commonengine optional authorize를 공간잠금후/멱등재사용전에 실행, 기존호출 기본None.
- 검증: 전체backend967/1skipped(마지막권한보정전), 최종공통/GW 103통과(협업23), frontend566/71파일, 최종타입/전체lint/build·범위Ruff/format·DB설계/격리0. 실제Chrome 일정/응답·알림/공지댓글/삭제·두탭자동채팅/읽음/탈퇴·390px/도움말 확인. 대량부하/네이티브인쇄PDF/실제회사권한/운영 미검증, 기존rootRuff GW import2건 유지.
- DB schema0.21.0/GW19·전체173/headgw_a_dsn31, 시드버전 변경없음. 실제도입A/CORE TEAM/ERP F44 제외. 신규ERP발주/경비·PLMECO 원천제공은 외부미구현, GW계약 유지.
- 다음: 사용자 결과 확인 후 GW-e 시드·도움말·통합 검증. 아직 착수안함. 전결rule/위임/approval_event.details/조직 및 협업 댓글revision·일정attendee·알림event_key·chatseq/clientKey/readCursor 유데이터의 세대 복사/날짜/내부ID·정리 검증. 일반/부서공지·결재알림대기·채팅·일정 체험시드와 공통도움말/DSN90 계약 정리.
- 재현은 결과문서 표준명령. 기존 main venv/node_modules/Node24 재사용 가능하나 PYTHONPATH=backend/src:backend 필수. 독립 *_test DB만, 같은DB 독립pytest 병렬금지; 전체 -n4 초기원본복제 동안 preview연결금지. 최종집중은 원본preview와 별도작업자DB사용. 서버8073/5273 종료, 의존성 심볼릭링크 최종정리. mac잠금native창은제어지연, 화면내확인으로검증완료. work/비밀정보스테이징금지.

## 이전 GW-c 기록

# GW-c 조직·HR 연계 인계 (2026-10-09)

- 완료: 사용자 후속 승인 범위 GW-c(G-07·G-10/F21~23). `codex/gw-dsn31`, 시작0dd6ef9/WIP1fe0642, 최종커밋 `git log -1 --oneline`. 격리 worktree `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. [결과](GW_조직HR연계_GW-c.md).
- G-07 공통 MasterScreen·HR 미리보기/선택/명시적 가져오기, G-10 현재 HR/마지막 조직 조회, 도움말2편. HR interface만 읽는다. 이름/부서만 갱신·동일 사원 ID 유지, 기존 GW 직무/활성·상신 조직/이력 보존. 퇴직/원천 없음/조회 불가 구분. 조직 순환·비활성 상위·누락·중복·코드 충돌·원천 변경·동시성·롤백 보호. 신규 STAFF·최대1,000명/회·부서만 가져오기 가능. 전체 역할 조회로100명 이후 누락 방지.
- 검증: 전체 backend944/1skipped(362.48초), 최종 GW66/신규17(107.36초), 감사 보정 후 신규17(46.13초). 전체 frontend559/70파일·최종집중134/16파일, 타입/빌드/전체frontend ESLint·GW Ruff·DB설계0. root 전체Ruff는 시작과 동일한 기존 test_gw.py·test_gw_policy.py import 정렬2건. import 분류는 실행 위치에 영향을 받으므로 결과문서의 명령/위치를 함께 재현한다.
- 실제 Chrome: HR 미개방→개방→부서4/사원10 가져오기, HR 명칭 변경 뒤 현재HR/마지막GW 차이, 신규0·갱신10 재가져오기,390px 본문 넘침0·표 내부 스크롤·도움말. 발령/조직 불변은 실제HR API+DB로 검증(브라우저 발령 재연 없음). 모바일 체크박스 공통 inline-check 보정. 기존 MES 진입 테스트의 빈 dashboard mock만 정상 합성 응답으로 수정해 전체 프런트 회귀 안정화; MES 제품 코드 변경 없음.
- 상태: DB/schema/시드 버전은 GW-a 그대로. main/공유DB/push/배포 없음. API8073/Vite5273·검증탭 종료, viewport복원, 의존성 symlink 제외/정리. 최종 브라우저는127.0.0.1(기본 localhost의 인증 쿠키와 분리). 접속값은 인계 문서/로그/Git에 넣지 않았다.
- 재현: 독립 `_test` DB에 TEST_DATABASE_URL, `PYTHONPATH=backend/src:backend`, main venv와Node24 사용 가능. 전체pytest `-m 'not perf' -n4`, GW파일3개 집중, 프런트 전체/build·결과문서 명령. 같은DB에서 독립pytest 동시 실행 금지. xdist 복제 중 원본 DB에 접속하지 않는다.
- 다음: 사용자 결과 확인 후 **GW-d 협업**(댓글/일정/알림/채팅). 미착수. 이후 GW-e 시드/도움말, 채워진 rule/delegation/event.details 복사·날짜·ID·증빙 검증 보강. EIP published_notices/공통4조회 실제 제공 상태도 후속 재대조. ERP F44/신규원천제공은 외부 담당자 소유, 실제 도입 A트랙은 제외. GW-b 인쇄 미리보기/PDF 미검증은 유지.

## 이전 GW-b 인계 기록

# GW-b 인계 (2026-10-09)

- 브랜치 `codex/gw-dsn31`, 시작GW-a `19e8f9e`, WIP `6ce757c`, 마지막 커밋 `git log -1 --oneline`. 격리 worktree: `/Users/hwang-kyoungho/Documents/Codex/2026-10-09/gw/work/factory-studio-gw`. main/공유DB/push/배포 없음. [결과](GW_결재확장_GW-b.md).
- 완료: 신규문서 정책2·병렬/합의/참고·상신전결고정·처리시점 위임조건/해제 재검사. G-02/03/04/06·G-08/09, 브라우저인쇄 코드·도움말6편. 기존policy1은 전결/위임 제외·순차 유지. 공통action/master사용, 버전/멱등/공간잠금/감사.
- 검증: 전체backend927/1skipped, 마지막보정 GW58, 전체frontend554·최종GW/콘텐츠26, tsc/전체frontendeslint/build/GWruff/DB검증0. Chrome결재선·전결·위임등록→상신→대리승인→합의→최종승인, 390px 넘침없음. 전체backendruff 기존core/service.py I001(기준본 재현), 인쇄 미리보기/PDF는 Mac잠금으로 미검증.
- 외부 의존: ERP PURCHASE_ORDER·EXPENSE_CLAIM 제공미구현, PLM eco_for_approval 없음. GW종류/소비/배지계약은 구현·mock검증. ERP는 APPROVAL_KINDS 선언, PLM은 ECO번호직접입력 지원. approvals 단일종류 번호키/혼합종류 `종류:번호` 키. 실제 회사 신원/공유공간/A트랙 및 F44 ERP 확정통제 제외.
- 다음: 사용자 결과 확인 후 GW-c 조직·HR 연계. 시작하지 않았다. GW-e 시드에서 rule/delegation/approval_event.details가 채워지면 날짜 이동·내부ID·증빙 스냅샷의 복사/정리 검증을 보강할 것.
- 재현: `TEST_DATABASE_URL`은 독립 `_test` DB, `PYTHONPATH=backend/src:backend`, 기존 backend venv/Node24 재사용 가능. 결과 문서 명령 참고. 동일DB에 여러 독립pytest를 동시 실행하지 않는다. 브라우저용8073/5273 프로세스 중지, 의존성심볼릭링크는제외/정리. `work/`에만 다음작업의 필수정보를 두지 않았다.
- DB는 GW-a schema0.21.0/headgw_a_dsn31/GW19·전체173 그대로. 병합 시 main MESmetadata·부모revision·제약순번/버전을 재대조할 것. GW-b schema migration 추가 없음.

## 이전 GW-a 인계 기록

## GW-a 체험 그룹웨어 DB (2026-10-09)

- branch `codex/gw-dsn31`, 시작 `af10726`, 마지막 커밋 `git log -1 --oneline`. 작업 경로는 `git worktree list`의 해당 브랜치. main/다른 세션 폴더는 수정하지 않았다. [결과](GW_체험보강_DB_GW-a.md).
- 완료: DSN-31 체험·조직11표 + 기존6표15칼럼, GW19/전체173, schema0.21.0/head`gw_a_dsn31`. 실제 도입A5표·CORE TEAM·ERP통제 제외. metadata/Excel/ERD/현황/progress 동시 갱신. `apply_gw_a.py` 멱등·제약순번보존; `build_migration.py` rollback FK/제약→칼럼→표→옛제약복원으로 보정. 이전 migration은 수정하지 않았다.
- 독립 `factory_studio_gw_a_test`에만 적용. 공유개발·CI원본·운영DB 미적용. 기존승인문서 왕복/DDL대조0, 도구4/실DB신규3·기존GWfrontend5/tsc/eslint/ruff/브라우저담당자등록 통과. 전체 backend900통과·1건너뜀(330.21초). 코드/API/신규화면은 미구현, 원격push/배포 없음.
- 당시 다음 단계: GW-b(사용자 승인 후 위 최신 기록처럼 구현 완료). 기존policy_version1 기본값으로 v1 순차결재 유지. ERP 발주/지출결의·PLM ECO 제공 인터페이스 존재 확인. A를 GW-a16표로 다시 넣지 않는다(인계프롬프트의 A 제외와 충돌).
- 재현: 결과문서의 명령. 새 DB는 PG18 및 `_test` 접미사. venv/node_modules는 main 것 재사용 가능하나 `PYTHONPATH=backend/src:backend`로 현재 worktree의 코드 사용. 테스트는 `EMPTY_MODULES=("gw",)`로 빈모듈 표시. 목표 `base_task`는 GW-a; main MES 진행과 병합할 때 schema/migration 부모/제약순번/버전을 다시 대조해야 한다. worktree branch의 단일 head는 w2a1_mes→gw_a_dsn31. 시드버전 변경 없음.

## UI-DESIGN-02 실제 UI 적용 (2026-10-09)

- branch main, 시작 기준66e3001, UI 구현 커밋 **0d34ec5**. 마지막 인계 커밋은 `git log -1 --oneline`. 사용자 전체 추천안 확인 후 구현100%. 로컬 커밋만, 원격 push/운영 배포 없음. 병행 MES/common/master·shared/master·MES 화면/테스트는 다른 작업자의 변경이며 보존/스테이징 제외.
- 끝난 것: Taste Entry.tsx+Entry.css/합성 NC 이미지, CAD 셸, E1/E2 공통 UI, nc-layout.js 기존 DOM 재배치/4준비단계·뷰포트/휴디·결과/접기, 공장 하단 시연·맥락 패널·초점. 현재 도움말/설계안/현황/progress 상태도 갱신. [결과와 캡처](UI개선_적용결과_UI-DESIGN-02.md).
- 검증: CAD142/frontend551(68파일)·최종 대상40·build/격리·대상 lint/format/diff. Chrome NC 전체 분석/3후보/텍스트3번재생정지, E2 체적24,000mm³, 랜딩 로그인·공장/1440·390. 공장 browser4종 통과: CNC1개 완료·정지·오류 복구·모바일 포함; 외관33.3초로 기존30초 초과, 60초 재검증 통과/테스트 제한 보정. 실제 음성 발화·운영/DB/실장비·계측은 미검증/미실행.
- 다음: 사용자 결과 확인. 다음 ID·운영 배포·원격 push 자동 진행 없음. NC 모델/품질 차단/후보revision/보호POC/iframe microphone 정책 유지. 스킬은 정적 프로젝트 지침이며 launcher/hook 사용하지 않는다.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; `npm --prefix prototypes/cad-cam test`; `npm --prefix frontend test -- --maxWorkers=2`; `npm --prefix frontend run build`; `npm --prefix frontend run test:factory-browser -- --grep '공장 장면은|건물|CNC'`. 3D 소프트웨어 렌더 캡처는 시간이 걸린다. 이 세션의 검토 Vite는5194, 기존 다른 포트/DB는 건드리지 않았다. 재실행은 `npm --prefix frontend run dev -- --host 127.0.0.1 --port 5194 --strictPort`; Git의 합성 예제·문서·캡처를 사용하고 work/tmp에 의존하지 않는다.

## W2a-1b MES 기준정보 화면 완료 (2026-10-09)

- branch main. M-16 불량·사유 코드, M-17 작업자·근무조, M-19 라벨 양식, M-26 공정 검사 기준. MES OpenAPI 경로 50 → 62.
- 새 파일 `backend/src/fs/mes/masters.py`, `backend/tests/test_mes_masters.py`, `frontend/src/mes/{Codes,Workers,Labels,InspectionItems}.tsx`, `frontend/src/mes/masters.test.tsx`. 수정: mes/{schema,router}.py, `fs/common/master.py`, `frontend/src/shared/master.tsx`, mes/{index,MesLayout}.tsx.
- 주의점: `MasterScreen`을 **탭으로 갈아끼울 때는 `key`를 준다** — 같은 컴포넌트라 목록·입력이 그대로 남는다. 공통 엔진의 중복 검사는 이제 `IS NOT DISTINCT FROM`이라 NULL 키 칸도 잡는다.
- MES 라우터는 `_values(payload, nullable, full=True)`가 등록용이다(기본값까지 보낸다). 기존 `_register`는 옛 `repository.Master`용이라 섞지 않는다.
- **남은 결함**: `mes.inspection_item`의 UK는 `item_id IS NULL`인 행끼리 DB가 막지 못한다. 서비스가 막지만 동시 등록이면 뚫린다. 목표 설계에 조건부 유니크를 더해야 한다.
- 재현: `cd backend && TEST_DATABASE_URL=... .venv/bin/python -m pytest tests/test_mes_masters.py -q`; `npx --prefix frontend vitest run src/mes`.
- 미실행: M-12~15 보강, 시드·도움말, 운영 배포(운영 `f860e8b`). 다음: W2a-1b2.

## UI-DESIGN-01 도움말·스킬·전체 UI 검토 (2026-10-09)

- branch main, 시작 기준 bb3b1bd, 구현/검토 자료 커밋 **fc7e3f1**. 인계 문서의 최종 커밋은 `git log -1 --oneline`로 확인한다. 로컬 커밋, 원격 push/운영 배포 없음. 병행 작업자의 common/master·MES backend/화면/테스트 파일은 건드리거나 스테이징하지 않는다.
- 완료: 공개 도움말5편·P-05·검색/목차/화면 경로·CAD/공장 직접 도움말. `.agents/skills/`의 factory-taste/factory-impeccable 고정 원본+프로젝트 파생 지침/라이선스/출처. CLI/hook/자동 다운로드/별도 agent 설정 미설치. 다음 턴부터 프로젝트 스킬 사용 가능.
- [전체 UI 검토안](../ui/UI개선_전체검토안_UI-DESIGN-01.md)·[구조 시제품](../ui/previews/UI-DESIGN-01.html)·PNG4장. 시제품은 배치·문구 검토용이며 실제 CAD/3D 엔진·분석·세션 생성 없음. 도움말 링크 외 제품 UI 재배치 미착수. 사용자 전체 확인 후 UI-DESIGN-02만 진행, 자동 다음 ID 착수 없음.
- 검증: frontend546/67파일·대상40, 전체build/자산 격리·대상 lint/format/diff, 스킬 frontmatter2개, Chrome3탭구성/1440·390폭/가로 넘침0·육안. 처음 도움말 Markdown 강조 오류는 수정 후 재검증. 시스템 YAML 미설치→임시 검증 venv, 제품 패키지 변경 없음. 기존 번들 경고 유지.
- 주의: 관리자 비누 POC를 공개 도움말/랜딩 이미지로 사용하지 않는다. NC 계산/품질/권한/파일 저장 동작과 3D 시연 안전 상태 유지. CAD-V01 실제 음성 리허설은 여전히 미검증. DB·장비·운영 배포 미실행.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; `npm --prefix frontend test -- --maxWorkers=2`; `npm --prefix frontend run build`. 시제품은 HTML을 Chrome에서 열어 상단 랜딩/CAD·CAM/3D공장 전환. 검토 자료와 스킬은 Git에 저장되며 work/tmp에 의존하지 않는다.

## W2a-1a MES 보강 DB 완료 (2026-10-08)

- branch main. mes 21 → 45테이블, 전체 162. 마이그레이션 **`w2a1_mes`**(head). schema.json 0.20.0 / W2a-1a.
- 새 파일 `tools/apply_w2a1.py`. `tools/build_migration.py`에 `--previous`(기존 표 변경) 추가.
- 주의점: 제약 이름은 **schema.json `constraints` 배열의 순번**이다. 새 제약은 반드시 **배열 끝에** 붙이고, 바꾸는 제약만 제자리에서 고친다 — 중간에 끼우면 운영 DB의 제약 이름과 어긋난다.
- `mes.work_order` ↔ `mes.lot`이 서로를 가리키는 **고리 FK**다. 게스트 정리(`fs/core/service.py::_cleanup_plan`)는 고리 안의 비울 수 있는 FK만 먼저 비우고, 시드 복사(`seed/copy.py::_table_order`)는 그 간선만 무시한다. **고리 밖 nullable FK를 비우면 안 된다**(fems.energy_target CHECK가 깨진다). 시드가 그 칼럼을 채우게 되면 복사 뒤 UPDATE 단계가 필요하다(`ponytail:` 주석).
- 재현: `backend/.venv/bin/python tools/apply_w2a1.py`; `... tools/build_migration.py --revision w2a1_mes --down w1a_hr_module --tables 'mes.*' --previous <git show HEAD:schema.json> --out ...`; `npm run db:validate`; `npm run db:build`; `python3 tools/build_erd.py`; `DATABASE_URL=... python tools/verify_ddl_matches_schema.py`.
- 미실행: 화면·API·시드, 운영 배포(운영은 `f860e8b`, 다른 세션 미커밋 문서 때문에 배포 보류 중). 다음: W2a-1b.

## CAD-V01 구현·로컬 검증 완료 (2026-10-08)

- branch main, 기준2241851·구현39204d3, origin/main push 성공(1ecd4f5→39204d3), 마지막 커밋 git log -1. 사용자 전체 흐름 구현 승인·최신 환경은 **맥북 Google Chrome/NC 에너지 제안**. 아래 Windows 설계 항목은 이전 이력이다. [계약](../modules/cad-cam/음성발표데모_제안_CAD-V01.md)·[검증/발표 준비](휴디_NC음성발표_CAD-V01.md).
- 끝난 것: 휴디 호출/한국어 명령/응답·후보 번호/ID/revision·G4 시간 모델 재생/정지/누적kWh·기존 품질 차단·입력 무효화·음성 실패 대안·합성 발표 예제. CAD141/frontend545·전체build/격리/포맷/대상 lint/diff·실 Chrome/모의 게스트 포털 iframe 흐름·390폭 확인. 실제 인증/DB 아닌 합성 세션이다.
- **남은 검증: 맥북 실제 마이크 발화·TTS 리허설**. 코드와 모의 음성 테스트 통과를 실제 음성 서비스 성공으로 소개하지 않는다. 발표자는 Chrome/macOS 마이크 권한과 인터넷을 확인한다. 운영 배포/실 CNC/실측 품질·절감 미실행/미검증. CAD-17 자동 착수 없음.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam ci/test/format:check; npm --prefix frontend test -- --maxWorkers=2; npm --prefix frontend run build. 핵심 파일·합성 NC·캡처는 리포지토리에 저장, work/tmp에만 의존하지 않는다.
- 로컬 검토: frontend/scripts/cad-preview-api.mjs(8042)와 FS_SMOKE_API_PORT=8042 frontend Vite(5244), 합성 게스트. 이 세션이 시작했던 별도 frontend5243·prototype5245 검토 서버는 종료했다. 실제 backend/공유 DB를 시작하지 않았다. 병행 작업자의 MES migration·schema·ERD·시드·service 변경은 그대로 보존하고 커밋에서 제외한다.

## CAD-V01 발표 대상 확정·설계 수정 (2026-10-08)

- branch main, 기준1ecd4f5. 마지막 커밋은 git log -1. 문서만 변경: [음성 발표 제안](../modules/cad-cam/음성발표데모_제안_CAD-V01.md), 현재 현황, 진행 기록. 타 작업자 파일 변경 없음.
- 사용자 확정: **Windows·Google Chrome 일반 브라우저·NC 에너지 제안**. Mac/E1 가정으로 구현하지 않는다. 발표 브라우저 Google Chrome 확정. NC 현재 코드는 후보 비교/행 선택뿐이고 자동 재생이 없으므로 번호/revision 선택+후보 G4 시간 모델의 경로/시간/kWh 재생을 음성과 함께 구현할 전체 제안으로 작성했다.
- 다음: 전체 수정 흐름 확인 후 CAD-V01 구현. Windows 실마이크/발화 검증 필요. 문서 검사만 수행했으며 음성/재생 제품 코드·테스트/build·DB/운영 배포 미실행. 기존 CAD-16 완료/main push1ecd4f5 유지; CAD-17 자동 착수 없음.
- 재현: NC 코드 `prototypes/cad-cam/src/{nc-review,nc-proposal-review,nc-proposals,nc-viewer}.js`와 CAD-15 계약 대조. 문서 상대 링크 검사와 git diff --check. work/tmp에만 의존하지 않는다.

## CAD-16 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준257871e·WIP12cf7d0·HR W1c b8b3405 보존 병합69737d6·포털72b253a 보존 병합c3b3ec2. 마지막 커밋 git log -1. 442482e까지 main fast-forward·origin/main push 성공(72b253a→442482e), 운영 배포 없음. 타 작업자 main 포털/UI 수정은 편집/스테이징하지 않는다.
- 끝난 것: E1/E2 공통 전문 스케치/섬 영역·국소 필렛/모따기/선택 면 기하 참조, 파일 상한/모달 키보드 격리. [계약](../modules/cad-cam/전문스케치_직접편집_설계_CAD-16.md)·[검증](전문스케치_직접편집_CAD-16.md). prototype134/frontend545·포맷/전체build/격리·실 UI/1440·390폭 통과. STEP 커널 왕복/STL 체적 통과, 브라우저 다운로드 수신은 시간 초과로 미확인. DB/실 CNC/운영 배포 미실행.
- 다음: 사용자 결과 확인 후 CAD-17 또는 **추가 요청 [CAD-V01 음성 발표 제안](../modules/cad-cam/음성발표데모_제안_CAD-V01.md)** 범위 확정. 최신 제안은 Windows Google Chrome/NC 에너지 대상 확정. 마이크·음성 구현 미착수. 자동으로 다음 ID를 시작하지 않는다.
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. localhost5243/8043은 모의 관리자 fixture. Git 예제 JSON/PNG/보고와 tests/{sketch-edit,direct-edit}.test.js를 사용한다. 임시 work/tmp 파일에 의존하지 않는다.

## W1c HR 시드·도움말 완료 (2026-10-08)

- branch main. 끝난 것: HR 합성 시드(`backend/seed/hr.py`), 공통 휴일 달력(`core.holiday` 16건 + 게스트 복사), 검증 규칙 V-HR, 도움말 15편(`content/help/hr/`), 전체 흐름 맵 HR 3노드.
- **시드 버전 `sv-20261001-1` → `sv-20261008-1`.** 다음 배포에서 시드 템플릿이 다시 만들어져 배포가 길어진다.
- 주의점: 시드는 기준일 T 기준으로 **지난달 = 마감·급여 확정 / 이번달 = 기준일까지 근태 + 마감 작성 중**이다. V-HR은 복사본에서도 통과하도록 **절대 월이 아니라 달 사이 관계**로 본다. 금액은 제품의 `fs.hr.payroll.slip_lines`를 그대로 쓴다 — 계산식을 고치면 시드도 같이 바뀐다. 공휴일은 복사할 때 **날짜를 밀지 않는다**(실제 달력).
- 행 수가 기준일에 따라 달라지는 `hr.attendance`·`hr.payslip_line`은 `seed.validate.DATE_VARYING`으로 빼고 규칙으로 본다. 고정 합계 **14,794**(검증기) / **14,811**(writer, core.holiday 포함) / **14,809**(복사본).
- 빈 공간을 전제하는 테스트는 모듈에 `EMPTY_MODULES = ("hr",)`를 선언한다. 선언하지 않으면 화면을 처음 열 때 지연 복사가 시드를 넣는다.
- 재현: `cd backend && DATABASE_URL=... PYTHONPATH=src .venv/bin/python -m seed.cli template --date $(TZ=Asia/Seoul date +%F)` 후 `... validate --date ... --workspace N --generation M`. 테스트는 `pytest -m "not perf" -n 4`.
- 미실행: 운영 배포. 다음: W2a.

## CAD-15 품질 우선 NC 검토 제안 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준f860e8b·구현5761608·운영 기록c769a42 보존 병합7aefb20, 최종 커밋 git log -1. 기존 main push 승인 유지. a3c1c6f까지 main fast-forward·origin/main push 성공(f860e8b→a3c1c6f)·이번 CAD-15 운영 배포 없음. HR/시드 등 main 타 작업자 수정은 소유자 작업이므로 스테이징/편집하지 않는다. [계약](../modules/cad-cam/품질우선_NC제안_설계_CAD-15.md)·[검증](품질우선_NC제안_CAD-15.md).
- `/cad-cam?view=nc`: 전체 에너지 분석 후 품질 우선 개선 제안 → 대기 목록/품질 기준·최소시간·목적/영향 확인 → 소비 비교. 단독 G4만, 품질 미달/근거 없음 차단·범위/여유 미정 우열 보류. 원본/경로/F/S/T 보존·NC 자동 적용/출력 없음. JSON 근거·200대기/12선택·입력 무효화. 합성 예제 버튼으로만 가정 입력.
- prototype117/frontend544·포맷/build/격리/diff·실제 후보/근거/과절삭 차단·행 선택/무효화/201페이지/상한·1440/390폭 통과. Node5만행 목록88.95/비교106.51ms, 동기 계산 느린 기기 지연 가능. 실측 품질/안전/절감·JSON재열기/Safari/실기기 대형 부하/DB/이번 운영 배포 미검증.
- 다음은 사용자 결과 확인 후 CAD-16 한 ID. Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-proposal-benchmark.mjs. localhost5243/8043 합성 관리자 fixture. Git 예제/보고/PNG/benchmark 사용, work/tmp 의존 없음.

## 운영 배포 (2026-10-08)

- 운영 https://eip.hugh-d.com = main **`f860e8b`** (이전 3474942). W1b-2·3·4 HR 전체 + CAD-12~14 포함. 마이그레이션 head `w1a_hr_module`, 시드 템플릿 변경 없음.
- 확인: 원점/공개 200 · DDL 대조 0 · 5xx 0건 · 운영 브라우저에서 H-01·H-10 표시 · `/api` 응답 `Cache-Control: no-store`.
- 배포는 `./tools/deploy.sh` 한 줄(먼저 `--dry-run`).

## CAD-14 시간·소비 모델 완료 (2026-10-08)

- branch codex/soap-cad-review, 기준e7c42cd·구현8e5b19e·HR b16e721 보존 병합854a3c8. 최종 커밋은 git log -1. 기존 사용자 main push 승인 유지. 92a2b84까지 main fast-forward·origin/main push 성공(e7c42cd→92a2b84), 운영 배포 없음. main 진행 중 HR 파일은 타 작업자 소유이며 건드리지 않는다. [계약](../modules/cad-cam/시간소비모델_설계_CAD-14.md)·[검증](시간소비모델_CAD-14.md).
- `/cad-cam?view=nc` 현재 NC/소재 → 상태표 → 장비 축 제한·전체 kW·이벤트 시간 → 시간/kWh. 빈칸 미정/알려진 소계, 출처/별도 비교 비보정, 합성 예제, 200구간/행 선택/JSON·Worker. 실제 CNC/계측/정확도·안전/부하 보정/DB/운영배포 미검증. CAD-15 자동 착수 금지, 사용자 결과 확인 뒤 한 ID.
- prototype104/frontend544(67파일; HR 병합 후 재검증)·포맷/build/격리/diff·실제 계산/미정/비교/행 선택/200페이지/1440·390폭 확인. Node5만행73.01ms(브라우저/peak 아님). 빌드 중 이전 Worker 자산 오류는 새로고침 후 통과; 실30초/브라우저취소 경합/stale주입/다운로드재열기 미검증.
- Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-energy-benchmark.mjs. localhost5243/8043은 합성 관리자 fixture. Git 보고/PNG/benchmark에 결과 저장, work/tmp 의존 없음.

## W1b-4 HR 평가·현황·본인 완료 (2026-10-08)

- branch main. 끝난 것: 자격·교육(H-05 인사카드), 인사 현황(H-01), 인사 평가(H-13), 인건비·근태 분석(H-14), 내 정보(H-15), EIP 공통 제공 `monthly_summary`·`pending_tasks`·`lookup`. **HR 15화면이 모두 구현됐다.** HR OpenAPI 경로 48개.
- 새 파일 backend/src/fs/hr/{review,analytics}.py, backend/tests/test_hr_review.py, frontend/src/hr/{Overview,Reviews,Cost,Me}.tsx, frontend/src/hr/review.test.tsx. 수정: hr/{schema,router,service,interface}.py, backend/src/fs/common/request_logging.py, frontend/src/hr/{Employees,index,HrLayout}.tsx.
- 주의점: 평가자는 코드 문자열(`reviewer_code`)이고 FK가 아니다. 확정은 `status='confirmed' = (confirmed_at IS NOT NULL AND grade IS NOT NULL)` CHECK를 지켜야 해서 한 UPDATE로 처리한다. 평가 기간을 닫으면 그 해 평가를 더 만들거나 고칠 수 없다(409 `CYCLE_CLOSED`). 인건비·`monthly_summary`의 인건비는 **확정 급여만** 센다. H-15는 EIP 연동 전까지 화면에서 사원 코드를 고른다.
- 라우터 `_values(payload, full=True)`가 등록용이다. 기본값이 있는 새 등록 본문을 만들면 **반드시 `full=True`**로 넘겨야 한다(DB 기본값이 없는 칸에서 NOT NULL 위반).
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_review.py -q`; `npx --prefix frontend vitest run src/hr`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173), uvicorn에 --reload가 없어 백엔드를 고치면 preview를 다시 띄운다.
- 로컬 게스트 공간은 생성 다음 날 00:00 KST에 만료된다. 만료된 공간으로 브라우저 검증을 이어가려면 새로 만들거나 `core.workspace.expires_at`을 미뤄야 한다(로컬 전용).
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1c HR 시드·도움말, 그 뒤 W2a.

## CAD-13 소재·공구·STEP 정합 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작83483dc·구현6fb5a96·STEP 정리0c34d32. 로컬 main fast-forward·origin/main push 성공(83483dc→0c34d32), 마지막 인계 커밋은 git log -1. 기존 사용자 main push 승인 유지·운영 배포 없음. main 진행 중 HR 파일은 타 작업자 소유이므로 스테이징/편집하지 않는다. [계약](../modules/cad-cam/소재공구_STEP정합_설계_CAD-13.md)·[검증](소재공구_STEP정합_CAD-13.md).
- `/cad-cam?view=nc` 소재/평엔드밀 T·H/D참조·단일 STEP→G54 정합/겹침·제거/잔삭/과절삭/급속 접촉 후보 행·숫자 공구표·예제. 비교는 수평/수직 면의 바닥부터 이어지는 상면만, 곡면/중공/언더컷·H/D보정·홀더/지그/기계 안전·전력은 미지원. 입력 변경은 정합/분석 무효화. 샘플 NC→해석→STEP예제→정합/상면 확인→소재 검토 실행.
- prototype88/frontend539·포맷·전체build/격리/diff·실제 NC/STEP/정합 차단/급속34행/입력 무효화/1440·390폭 확인. STEP취소 시도는 먼저 완료돼 미검증, 실제30초/stale강제주입·대형메모리/다운로드재열기·DB/실물/계측/운영 배포 미검증·미실행. 다음은 결과 확인 뒤 CAD-14 한 ID만, 이번에 시간/kWh 계산 없음.
- 재현 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. fixtures 생성: node prototypes/cad-cam/experiments/nc-cad13-fixtures.mjs. 작업 화면 localhost5243/8043은 worktree 합성 관리자 fixture, 운영 DB 아님. 화면/샘플은 Git 기록, work 임시 파일 의존 없음.

## CAD-12 NC 경로 검토 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작7861ed1·WIP24779cd·최종 구현/검증1f26837. 로컬 main fast-forward·origin/main push 성공(7861ed1→1f26837), 마지막 인계 commit은 git log -1. 기존 main push 승인 유지, 운영 배포 없음. [계약](../modules/cad-cam/NC해석_경로검토_설계_CAD-12.md)·[검증](NC경로검토_CAD-12.md). main의 진행 중 HR 변경은 별도 작업자 소유이며 스테이징하지 않는다.
- NC 메뉴 `/cad-cam?view=nc`, 3축 LinuxCNC 기반 제한 프로필·로컬 파일/붙여넣기·코드/경로 동기·이벤트/모달 전후 상태·첫 미지원 차단·200행페이지·원문/해시·Worker취소/상한. 초기좌표 확인 필요, G43/사이클/매크로/선반 미지원. M6/M30 기계 자동 동작 미정, 실제 장비 전체 재현 아님. 파일 메모리만·새로고침 소멸; DB/기존 E1/E2/비누 권한 정책 변경 없음.
- prototype77/frontend66파일539/포맷·전체build/자산격리·실제 파일/BOM/CRLF·행↔경로·5만행 취소/재실행·390/1440폭 통과. 기존 ERP 비동기시험1회실패→전체재실행통과(미수정). 파서Node5만626.79ms/heap+126.13MiB/RSS+182.73MiB, browser/GPU/peak 제외. 다운로드 이벤트만료·다운로드재열기/30초만료/stale강제주입/실장비/계측/DB/운영배포 미검증.
- 다음: 결과 확인 뒤 CAD-13 공구·소재·원점/목표 STEP 정합, CAD-14 시간/소비, CAD-15 품질우선제안. CAD-13~17 자동 착수 없음. 컨트롤러 실제 모델 미정, 현재부분집합을 실제 장비 호환으로 오인하지 않도록 유지한다.
- 재현: Node24 PATH 적용; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build; node --expose-gc prototypes/cad-cam/experiments/nc-benchmark.mjs. 예제 examples/cnc_CAD12_2026-10-07_milling.ngc, 검증 PNG/benchmarkJSON은 docs/agent/assets/cad-12. 로컬5243/8043 합성fixture, 운영 아님. work/tmp 파일에 의존하지 않는다.

## CAD-11 편집 복구 완료 (2026-10-07)

- branch codex/soap-cad-review, 구현6d4d8d3·HR 급여aaee3a3 보존 병합9a5c0a3. 문서2b6086c까지 로컬 main fast-forward·origin/main push 성공(b2390b7→2b6086c). 최종 인계 commit은 git log -1. 기존 사용자 main push 승인 유지, 운영 배포 없음. [계약](../modules/cad-cam/편집명령_복구_설계_CAD-11.md)·[검증](편집명령_복구_CAD-11.md).
- 3축 밀링/G-code 우선·선반 후속 사용자 확정. E1/E2 키·초안/확정/nativeundo 분리, 점/원호/닫기/드래그·치수 복구, Esc취소, 참조 목록·삭제 보호. 저장은 확정 모델만. E2 취소Worker인스턴스 방어. JSON/DB/비누권한 정책 변경 없음.
- 실제 prototype62/프런트66파일538/포맷/전체build·자산격리·웹키입력/드래그·형상체적/삭제 복구 통과. Windows/IME기기·30초만료/stale주입·저장재열기·전수도구·DB/NC/실물/계측/운영배포 미검증. 기본커널약23MB/chunk 경고 유지.
- 다음: 결과 확인 뒤 CAD-12 G-code 부분집합/모달상태/원본행/경로/미지원차단·취소상한. 컨트롤러 모델 미정, 전체 NC 분석/장비 실행 보장하지 않는다. CAD-13~17 자동 착수 금지. 다른 작업자 main HR schema 미커밋 수정은 보존한다.
- 재현: PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. 로컬5243/8043 합성 관리자 fixture, 실제 운영 아님. 증거 PNG는 docs/agent/assets/cad-11, work 임시파일에 의존하지 않는다.

## W1b-3 HR 급여 완료 (2026-10-07)

- branch main. 끝난 것: 급여 항목·사원 기준·고정 수당·상여 규칙(H-10), 계산 → 검토 → 확정(H-11), 급여대장·명세서·퇴직금 추계(H-12), ERP용 `payroll_runs(month)`. HR OpenAPI 경로 36개.
- 새 파일 backend/src/fs/hr/payroll.py, backend/tests/test_hr_payroll.py, frontend/src/hr/{PayStandards,Payroll,Payslips}.tsx, frontend/src/hr/payroll.test.tsx. 수정: hr/{schema,router,interface}.py, frontend/src/shared/hooks.tsx(`fieldErrors`가 `body.` 접두사 제거), hr/{index,HrLayout}.tsx.
- 주의점: 계산 입력은 그 달의 **확정 근태 마감**이다. 공제는 `calc_kind='RATE'`만이고 과세 지급 합계에만 건다(DB CHECK가 `item_kind='DEDUCTION' = (calc_kind='RATE')`). `rate`는 계산 방식에 따라 뜻이 다르다 — 연장·야간·휴일은 배수(1.5), 공제는 퍼센트(4.5). 작성 중 실행을 다시 계산하면 같은 버전을 **지우고 다시 만든다**(id가 바뀐다). 확정 후 재계산만 새 버전이다. 퇴직금 추계와 ERP 합계는 저장하지 않는 조회 계산이다.
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_payroll.py -q`; `npx --prefix frontend vitest run src/hr`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173) — uvicorn에 --reload가 없어서 백엔드를 고치면 preview를 다시 띄워야 한다.
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1b-4 평가·현황·본인(H-01·H-13~15) + `monthly_summary`·`pending_tasks`·`lookup`, 그 뒤 W1c 시드·도움말.

## CAD-10 NC·소비·편집 고도화 분석 (2026-10-07)

- branch codex/soap-cad-review, 시작9b54a29에 HR3596156 fast-forward 보존. 최종 commit은 git log -1. [상세 분석](../modules/cad-cam/NC에너지_편집고도화_분석_CAD-10.md), 이번은 문서만·제품 구현0%, 분석100%. main push 기존 승인 유지, 운영 배포 없음.
- NC=경로/기계 상태 명령, CAD 이력 원본과 분리. 초기 3축 밀링·한 컨트롤러 부분집합 제안, 미지원 의미 명령은 전체 시간/kWh/최적화 차단. 공구/소재/초기XYZ/원점·장비 전력/실측 필요, G1을 곧바로 접촉으로 취급하지 않는다. CAD-09 방문 재배열을 외부 NC에 적용하지 않는다.
- E1 확정 모델 CtrlZ는 있지만 그리는 중 점 이력 없음, E2 undo 버튼은 있지만 keydown 없음. 공통 명령·draft와 확정 undo·필드 native undo 분리부터 제안. STEP import API는 설치된 replicad에 있으나 제품 연결/실증 미착수.
- 검증은 공식 문서/코드 조사·문서 링크/표/diff 검사, 신규 기능 시험·계측/DB/배포 미실행. 다음: 컨트롤러 질문 답변과 전체 구현 계약 확인 후 CAD-11 한 ID. CAD-12~17 자동 착수 금지. 재현: rg -n 'keydown|undo|redo' prototypes/cad-cam/src/{main,part-editor}.js; 분석 문서 출처 직접 확인. 다른 작업자의 HR 진행은 보존한다.

## W1b-2 HR 근태·휴가 완료 (2026-10-07)

- branch main. 끝난 것: 근태 자동 생성·예외 수정(H-07), 월 마감 draft→확정→재마감 새 버전(H-08), 연차 발생·잔여 계산·신청·부서장 승인/반려/취소(H-09). 승인하면 마감하지 않은 달의 해당 날짜 근태가 LEAVE/HALF_LEAVE가 된다. HR OpenAPI 경로 23개.
- 새 파일 backend/src/fs/hr/{attendance,leave}.py, frontend/src/hr/{Attendance,AttendanceCloses,Leaves}.tsx, backend/tests/test_hr_attendance.py, frontend/src/hr/attendance.test.tsx. 수정: hr/{schema,router}.py, fs/core/service.py(게스트 정리에 core.holiday), backend/tests/conftest.py(같은 이유), hr/{index,HrLayout}.tsx.
- 주의점: 월 잠금 판정은 `hr.attendance_close`의 **월별 마지막 버전**만 본다(확정만 보면 재마감해도 안 열린다). 근태 수정은 항상 `source=MANUAL`로 바꾼다. 휴가 승인은 `is_head` 직책 재직 사원만, 본인 승인 불가, 잔여는 `FOR UPDATE`로 재확인. `core.holiday`는 등록 화면이 없어 W1c 시드 전에는 비어 있다(공휴일이 휴무로 안 잡힘).
- 재현: `set -a && . ./.env && set +a`; `cd backend && TEST_DATABASE_URL="postgresql+psycopg://factory_studio:$POSTGRES_PASSWORD@127.0.0.1:$POSTGRES_PORT/factory_studio_ci_test" .venv/bin/python -m pytest tests/test_hr_attendance.py tests/test_hr_master.py -q`; `npx --prefix frontend vitest run src/hr`; `ruff check --config backend/pyproject.toml backend`. 로컬 미리보기는 .claude/launch.json의 backend(8000)·frontend(5173).
- 미실행: 전체 pytest 일괄 실행, 운영 배포(운영은 아직 `3474942`). 다음: W1b-3 급여(H-10~12), 그 뒤 W1b-4·W1c.

## CAD-09 품질 우선 경로 제안 (2026-10-07 완료)

- branch codex/soap-cad-review, 구현b10d157·HR1136611 보존 병합6f91b4c. 최신 기록commit은 git log -1. 기존 사용자 main push 승인으로 e17fef8까지 로컬 main fast-forward·origin/main push 성공(1136611→e17fef8). 다음 HR 근태/휴가 미추적 파일 보존. 다른 작업자 변경은 스테이징하지 않는다.
- E1 상면 포켓 순서 후보2개·256래스터 상한, 절삭/방향/깊이/실제 마지막 마무리/경계·안전Z·같은격자 보존, 기존보다 개선되면 제안. 선택 적용만 경로 변경, 입력 변경 후보 무효화, Worker30초/수동취소·revision/종료 Worker 응답 방어. 장비 미정 kWh/전력절감% 없음. [검증 보고](품질우선_경로제안_CAD-09.md).
- 실제 prototype56/frontend530(64파일)/전체build·자산 분리·포맷·웹 적용/100%·기존진행률/무효화·상한·수동취소/복구 확인. 실제30초만료/stale강제주입·Ra/실물/전력·DB명령 미검증. 운영 배포 없음. 다음은 결과 확인 뒤 장비/목표품질 입력 설계. E3 자동 시작 안 함.
- 재현 PATH=/opt/homebrew/opt/node@24/bin:$PATH; npm --prefix prototypes/cad-cam test; npm --prefix prototypes/cad-cam run format:check; npm --prefix frontend test; npm --prefix frontend run build. 로컬5243/8043 합성 관리자 preview만 검증, 운영관리자200은 이전 CAD-08도 미검증. 보호 비누 파일은 빌드시 backend/private-assets/soap-poc에 생성하며 Git에 넣지 않는다.

## CAD-08 운영 비누 파일 복구·경로 제안 분석 (2026-10-07)

- branch codex/soap-cad-review, 시작8a10ea6. deploy.sh 비공개 업로드 누락 수정: 필수 로컬 자산/서버 실행계정 읽기 검사, 보호 폴더 전송·750/640, 공개경로 추가 없음. 가짜 도구 계약7·기존 보호 API13 통과, 전체 실배포 스크립트 미실행. 구현 ee5c499 로컬 main fast-forward 및 origin/main push 성공(8a10ea6→ee5c499). 최종 기록commit은 git log -1, main의 진행 중 HR 파일 보존.
- 운영은3474942. 같은 커밋의 별도 archive 빌드로 private38파일만 복구, 전체 경로/내용해시 일치·factory 읽기·비로그인401 확인. 관리자 브라우저200은 세션 없어 미검증. E2/코드/DB 배포·API 재시작 안 함. work/cad08-server-build는 재현 가능한 임시 빌드이며 인계 의존 대상 아님.
- 품질1·소비2 [설계초안](../modules/cad-cam/품질우선_경로제안_설계초안_CAD-08.md), 제품 구현 미착수. 재질/장비/목표품질 질문 답변 전 미정. 기존 E1의 절삭/방향/마무리·안전Z를 유지하며 래스터 방문만 조정하는 초기 제안. 장비 미정은 실제kWh/%를 표시하지 않음. 다음은 사용자 확인 뒤 경로 제안 구현, E3는 자동 시작 안 함.
- 재현: python3 tools/test_deploy.py; bash -n tools/deploy.sh; backend .venv/bin/python -m pytest tests/test_cad_private_assets.py -q. main 미추적 backend/src/fs/hr는 다른 작업자 진행 중이므로 건드리지 않는다.

## CAD-07 E2 완료 (2026-10-07)

- branch codex/soap-cad-review, 시작3f6b244. WIP0377787·포털/입력7ed2817, main W0-5 e135f79 보존 병합b7edf18. 최신 원격 d135d7f(HR/운영 기록)를384e206으로 병합 보존. 로컬 main fast-forward 및 origin/main push 성공(d135d7f→384e206), 최종 기록 commit은 git log -1. 기존 사용자 main push 승인, E2 운영 배포 없음. main prototype node_modules 없이 frontend 단독 의존성 설치/전체 build·자산 분리 재검증 통과, lock 변경 없음.
- E2 OCCT1.1.0 단일 부품·기준3평면·다중 돌출·측면 구멍·배열/미러·필렛/쉘·제한된 점/원호 구속. 포털 view=part. JSON v3 별도 scope 키, legacy base/cut 변환. 형상 실패에 마지막 정상 원본/표시 유지, 30초 종료/수동 취소. [보고](부품설계_편집기_CAD-07.md).
- prototype50/frontend525/API13·포맷·단독/전체 build·자산 분리, 실제 합성 관리자 브라우저 치수/구속/오류/undo/redo/복원/STEP 생성·1440/390폭 통과. DB/실물/NC/외부 STEP 읽기·브라우저 파일 다운로드/재열기·취소/타임아웃 실사용 미검증. E1 CAM 전용이며 E2를 평면 CAM으로 자동 변환하지 않음.
- 재현 Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; prototype npm ci && npm test && npm run build; frontend npm ci && npm run build && npm test; backend .venv/bin/python -m pytest tests/test_cad_private_assets.py -q. frontend 단독 설치 빌드 alias (?url regex) 유지. licenses를 public cad-cam-app/licenses로 복사. WASM22,980KB·gzip7316KB 별도 Worker 최초 진입만.
- 예제 prototypes/cad-cam/examples/cnc_E2_2026-10-06_{bracket,shell-fillet}.part.json. 기존 비누 연구노트·파일 참조 유지, 사진 업로드 없음. 5243/8043은 worktree 모의 세션 fixture(운영 아님). 기존 개발 의존성 source-map-js audit high1 별도 대응. 다음 E3는 사용자의 이번 결과 확인 후, 다른 솔루션 역할은 D82 유지.

## CAD-06 E1 완료 (2026-10-06)

- branch codex/soap-cad-review, 기준 c663114, 구현09286e4·W0-4 be91ce9 병합4c87b7c. 로컬 main fast-forward 및 origin/main push 성공(be91ce9→4c87b7c). WASM ?url 경로 alias 보정057100d, frontend 의존성만 설치된 main CAD 빌드/자산 분리 재검증 통과. 최종 기록 커밋은 git log -1. 기존 사용자 main push 승인, 다른 작업자 변경 보존, 운영 배포 없음.
- 선 연결·3점 원호(닫는 직선 포함)·회전 슬롯·좌표 치수·끝점/격자 스냅·JSON v2/v1 읽기·Manifold offset Worker·안전 높이 분리 이동. 단일 XY 영역/돌출·상면 포켓. 섬 편집/구속 해석/다중 돌출/필렛/STEP/NC 미구현.
- prototype37/frontend524/관리자 권한API13/build·공개/관리자 자산 분리 통과. 실제 브라우저 직접 윤곽·치수 편집·가공·되감기·오류 거부·390/1440폭 확인. 예제 JSON: prototypes/cad-cam/examples/cnc_E1_2026-10-06_L-slot-arc.form.json. [상세](자유스케치_편집기_CAD-06.md).
- 재현: Node24 PATH=/opt/homebrew/opt/node@24/bin:$PATH; prototypes/cad-cam에서 npm ci && npm test; frontend에서 npm ci && npm run build && npm test. frontend/prototype 각각 manifold3.5.4 런타임 의존성·빌드 alias 포함. 브라우저 WASM worker 실행 확인, node:module externalized 빌드 경고는 Node 분기용.
- CAD 로컬 서버는 worktree frontend5243/backend8043 합성 인증 fixture. DB·실물·NC 미검증. IAB Blob 다운로드 이벤트 timeout으로 실파일 다운로드/선택 재열기 검증 미완료(순수 JSON 왕복 통과). 기존 개발 source-map-js1.2.1 audit high1 별도 대응 필요.
- 다음: 사용자 이번 결과 확인 후 CAD-07/E2. 비누 심화는 창업 후속 때. 연구노트는 기존 관리자 기록/폴더·파일명만 유지, 사진 업로드 없음.

## CAD-05 CNC E0 완료 (2026-10-06)

- branch codex/soap-cad-review, 구현 ba00b69 로컬 main 병합 및 origin/main push 성공. 최종 기록 커밋 git log -1. 사용자 main push 승인, 운영 배포 없음. CNC 우선·비누 심화 후속·사진 없이 폴더/파일명 기록 확정.
- experiments/cnc-offset-e0.mjs: L자/섬/좁은목/과대공구 offset·영역 분리·독립 여유10908표본·안전Z·돌출 검사 통과. Node24 실증, 브라우저 커널 성능/전체 제거·NC·장비 미검증.
- 연구노트 폴더/파일명 입력/JSON 유지·구 백업 호환. 사용자 방향과 현재ZIP 경로를 합성 관리자 브라우저에 실제 기록. 파일 생성·존재 확인 기능 아님.
- prototype32/빌드·자산 분리 통과. 재현 prototype npm run cnc:experiment && npm test; frontend(Node24) npm run build. 재실증 출력 work/cnc-e0, 커밋 기준자료 docs/agent/assets/cnc-e0는 자동 덮어쓰기 금지.
- [보고](CNC_윤곽커널실증_CAD-05.md). 다음 CAD-06 자유 스케치·JSON v2·CNC worker 연결, AGENTS.md 작업ID별 결과 확인 후. 다른 솔루션 업무/DB 미변경.

## CAD-04 완료 (2026-10-06)

- branch codex/soap-cad-review, 구현 11131e8, 최신 main8df92c4(W0-2/CI) 병합 보존. 최종 커밋은 git log -1. 사용자 관리자 웹 연구노트 확인; 기존 보호 API 안에서 research-notebook.html과 research-history.json을 제공.
- POC01→03 회고/파일 해시·추가 노트 scope별 브라우저 저장·JSON 백업/복원. 미실행 값을 창작하지 않음. 기록은 전자서명/서버 동기화/사진 업로드 없음.
- 검증 prototype29/API13, frontend build·공개자산 분리, 실제 브라우저 저장/JSON 다운로드·복원과 HTTP401/403/200 통과. 실제 DB/실물/커널 후보 실증은 미실행.
- 재현: prototype npm test, frontend(Node24) npm run build, backend uv run pytest tests/test_cad_private_assets.py -q. 5243/8043 합성 로그인 검토 서버는 기존 실행 유지. 연구노트는 비누 POC 안 링크.
- 다음: docs/modules/cad-cam/편집기_고도화분석_CAD-04.md 전체 방향 확인 후 E0커널 실증. 고도화 제품 구현 미착수. 다른 작업자 W0-2/CI 변경을 병합하여 보존, 원격 push/배포 없음.

## CAD-03 완료 (2026-10-06)

- branch `codex/soap-cad-review`, WIP d11471e, main ec1b373 병합 8dce56d. 구현/검증 160b9b0 로컬 main 통합 완료. 최종 기록 커밋은 `git log -1`. 최신 POC-03(유연 외피9부품)이 v2를 대체한다. 사용자 이번 요청만 수행, D82 다른 업무 중단 유지.
- frontend524/prototype27/API13 및 빌드 통과. 실제 브라우저 관리자 모델/서랍 분리/다운로드 검증. [결과](CAD_CAM_관리자POC_CAD-03.md). 실물·탄성·실제 DB 인증·운영 배포 미검증.
- 재현: `cd frontend && npm run build` (Node24), `cd prototypes/cad-cam && npm run poc:flex && npm test`, `uv run --directory backend pytest tests/test_cad_private_assets.py`.
- 5243/8043은 합성 인증+실제 보호 라우터의 검토 환경. 실행법은 docs/modules/cad-cam/README.md. 테스트 fixture를 운영에 실행하지 않는다.
- 보호 자료 backend/private-assets는 빌드 생성물. 공개 정적 경로로 노출 금지, 운영 배포시 오래된 public soap 파일도 교체. 원격 push·배포 없음.
- main의 backend/pyproject.toml·seed/copy.py·tests/conftest.py·uv.lock은 다른 작업자의 진행 중 변경으로 보존. 다음은 사용자 검토 후 재료/결합 방식·실물 시험.


## Codex 최신 상태 — 2026-10-05 CAD-02 포털 통합 완료

- branch `codex/soap-cad-review`, worktree `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`. POC 커밋1a364f7, 최종 통합 커밋 `git log -1`; main의 DSN-29 기준표까지 병합 보존.
- 사용자 요청으로 앱 런처 바로 오른쪽 CAD·CAM, `/cad-cam` 로그인 경계, 편집기/POC 내장. [설계/실행](../modules/cad-cam/README.md) · [검증](CAD_CAM_포털통합_CAD-02.md).
- frontend521+최종 관련3, prototype13, build/lint/format 통과. 실제 브라우저 모의 게스트→CAM100%→POC STL→설계 복귀 확인. 실제 인증·운영·실물은 미검증.
- Node24 `cd frontend && npm ci && npm run build` 또는 `npm run dev`. prebuild/predev가 CAD 원본을 public/cad-cam-app에 생성하므로 별도5241 서버 불필요. CAD 소스 수정시 `npm run cad:build` 필요.
- 검토 중인5242 서버는8042 모의 API 연결이며 실제 업무 환경이 아니다. fixture 실행법은 공통 설계. 별도5241 POC 서버도 남아 있다.
- 다음: 사용자 검토 후 배포 또는 FDM 실험. 로컬 main 반영, 원격 push·배포 없음. ROADMAP-02 다른 솔루션 개발 재개 아님. 생성 public 자산·.env/work/원본 PDF는 커밋 제외.


## Codex 최신 상태 — 2026-10-05 POC-01 완료

- worktree `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, branch `codex/soap-cad-review`. 시작 ff5988d, 최종 커밋 `git log -1`.
- 일반 FDM 디지털 시험편: 판3종+트레이 STL, Manifold 생성기, soap-poc.html 검토 화면, ZIP/출력 안내/측정표. [보고](비누그라인더_POC-01.md).
- test13/build/format 통과, 실제 브라우저 조립/교체/ZIP 검증. 실물과 슬라이서 미실행. 웹에서 치수 변경은 아직 안 되며 생성 소스로 수정.
- 재현 `cd prototypes/cad-cam && npm ci && npm run poc:build && npm test && npm run build`; `npm run dev` localhost5241/soap-poc.html. 현재5241 서버 재사용. ZIP `python3 tools/package-soap-poc.py`.
- 다음: 사용자 검토 후 출력 프로파일 적용/실물 A/B/C 시험. 회전 본체·양산·포털 통합 미착수, ROADMAP-02 유지. PDF 원본/개인정보·.env/work 미포함. push 없음.


## Codex 최신 상태 — 2026-10-05 CAD-01 웹 CAD·CAM 시제품

- 위치 `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, 브랜치 `codex/soap-cad-review`. 시작 `a4baf30`, 검토 `ebfb787`, 구현 WIP `33c3f22`. 최종 문서/검증 커밋은 `git log -1 --oneline`로 확인한다.
- 사용자 의도: 직접 설계·가공하는 웹 프로그램. 아래 CAD-00의 제품 기구 선택 질문/답변 대기는 철회됐다. CAD-01 독립 검토 시제품을 제공한다.
- 구현 완료: `prototypes/cad-cam/` 스케치·돌출·파내기·치수/이력·JSON/STL·2.5D 공구 경로·worker 소재 제거. 상세 [검증 보고](CAD_CAM_편집기_CAD-01.md), 실행은 해당 폴더 README.
- 검증: 수학/형상/worker9 통과, 실제 브라우저 드래그·입력→3D→CAM·재생/되감기·과대 공구·JSON 왕복·STL 파일 확인. 화면1440/390 가로 넘침0. Safari/실기기/장비/정밀 CAD 호환/DB 명령 미실행.
- 재현: `cd prototypes/cad-cam && npm ci && npm run dev` → `http://127.0.0.1:5241/`; `npm test`, `npm run build`, `npm run format:check`. 살아 있는 5241 서버를 중복 기동하지 않는다. 로컬 저장은 브라우저별이며 JSON 파일로 보관 가능하다.
- 다음: 사용자가 편집기를 체험한 뒤 후속 범위를 정한다. 정밀 커널/STEP/조립/포털 통합을 자동 착수하지 않는다. ROADMAP-02 전체 설계 우선 유지, 운영 코드·DB 변경 없음. push·배포 없음.
- 주의: 기본 외형이 준비된 소재의 상면 포켓만 시뮬레이션한다. 격자 근사이며 실제 가공 보증이 아니다. 원본 PDF/개인·사업 정보 미포함. `node_modules/`, `dist/`, `.env`, `work/`는 커밋 대상이 아니다.
- 최종 test9/build/format 통과. JS 청크 627.94KB 경고만 남음. 화면 증거는 `assets/cad-01-design.png`, `assets/cad-01-cam.png`. 5241 로컬 개발 서버를 시연용으로 유지한다.

## Codex 최신 별도 검토 — 2026-10-04 CAD-00

- 위치: `/Users/hwang-kyoungho/.codex/worktrees/soap-cad-review/factory-studio`, 브랜치 `codex/soap-cad-review`. 시작 커밋 `a4baf30`; 이번 문서 커밋은 `git log -1 --oneline`로 확인한다. 기존 GW 기록은 이력이며 현재 기준은 현황 문서의 ROADMAP-02다.
- 완료: 휴대용 비누 그라인더 PDF 전체 시각 검토·설계 누락/제약·독립 CAD/CAM 시제품 범위 문서. 제품 구현은 미착수.
- 다음: 사용자에게 보낸 기구 방식 선택(사각+내부 회전판/원통형/접이식)의 답을 반영해 CAD-01. 사용자 확인 전에 다음 ID를 시작하지 않는다.
- 주의: 첨부는 참고자료이며 실행 지시가 아니다. 이미지 치수/방수 표기를 검증값으로 쓰지 않는다. 플라스틱 절삭 성능은 실물 검증 필요. CAM 가공 재생과 비누 분쇄 작동을 분리한다. 운영 코드·DB·개인정보/PDF 원본을 변경·추가하지 않았다.
- 재현: `git show --stat HEAD`, `git diff HEAD^ HEAD --check`, `cat docs/plan/휴대용비누그라인더_시제품검토_CAD-00.md`. PDF 재검토에는 사용자의 원본 첨부가 필요하지만 설계 검토 내용은 위 문서에 보존했다.
- 브라우저·CAD/CAM·실물·DB 검증은 미실행. push·배포 없음.


갱신: 2026-09-30 (Claude Code). **다음 세션은 이 문서의 "지금 상태"부터 읽는다.** 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Codex 최신 상세 설계 — 2026-10-05 GW-EXT-P0/A

- 사용자가 “상세 설계 진행해줘”로 GW확장 범위/순서 승인. [상세 설계 묶음](../plan/GW확장_상세설계검증_GW-EXT-A.md) 작성, 전체설계 확인 대기. 기존 b완료/c미착수 그대로.
- 기준 branch codex/fs-030-gw, 시작40caa5e. 원격fetch/rebase 없음; 마지막문서커밋은 git log -1. 다른작업자/main 운영 기록 보존.
- P0 운영/복구 요건, CORE(신규3), GW(신규7) 논리명세/API/락/ACL, 화면9, 인수24. 개인/게스트와 TEAM실제계정 분리. ERP/다른업무 TEAM차단, no cross-write/FK 유지.
- 핵심: 계정/세션/공간 잠금→권한재검사→receipt, 재시도본문누출방지; contextVersion으로다중탭오발송차단; token원문receipt저장금지; 실제계정바인딩은대상동의·재바인딩금지. 관리자도본문열람권한없음.
- 미정: 회사규모/배포/SSO·MFA·RPO/RTO/보존. 인증/계정복구·최종GW관리자복구 부속설계는환경확정후. 해당검증전 COMPANY출시불가. B~F 상세설계 미작성.
- 문서 정적검사만 수행, 제품/DB/브라우저/성능/복구검증 없음. schema/Excel/migration 변경 없음. 다음은사용자설계확인→기존c완료→최신main/공식번호조율→A구현단계. push·배포·실데이터반입 없음.

## Codex 최신 설계 — 2026-10-05 GW-EXT-01

- 사용자 기존 GW 제외 범위 확장 요청 및 **실제 회사 도입 목표** 확정. [결정 초안](../plan/GW확장_협업플랫폼_결정초안_GW-EXT-01.md) 작성; 기능 범위/구현은 아직 미승인. 이전 b완료/c미착수 상태 유지.
- 기준 codex/fs-030-gw / 1f96532. 이번 원격 fetch/rebase 없음, 문서만 변경. 마지막 문서 커밋은 git log -1. 기존 main/다른 작업자 기록 보존.
- P0 실제 운영 요건(규모/인증/보존/RPO/RTO/운영자 미정)→A 공유 공간/권한 우선. 전체 c→P0→A→B→C→D→E→F 순서 제안. 실회사 데이터는 별도 운영 환경에서 준비 완료 후만; 공개 체험 반입 금지.
- ERP 직접 교차쓰기 대신 ERP소유 확정 통제, EIP 집계 소유 유지. 공식 번호 충돌 방지 위해 GX01~10 로컬 제안. 전체 모듈/화면 설계 승인 전 schema/코드 변경 금지.
- 검증은 문서 정적검사만. 제품 pytest/Vitest/브라우저/DB/공급자 검증 없음. 사용자 범위 확인 후 상세 설계, 구현 전 최신main/CMMS/번호 조율. push·배포 없음.

## Codex 최신 상태 — 2026-10-04 FS-030b 완료

- 아래 main 운영/Claude 기록은 보존한다. GW의 이전 a/WIP 상태는 이 항목으로 대체한다.
- 위치 `/Users/hwang-kyoungho/projects/factory-studio-codex`, branch `codex/fs-030-gw`. main8531c05 fast-forward 후 구현 WIP2a80375, 구현/검증 160b9b0 로컬 main 통합 완료. 최종 기록 커밋은 `git log -1`. push·배포·main 병합 없음.
- G01~07/API·ERP 조회계약/E11 배지·런처/전환 구현 완료. DB v0.17.0/headfs029b_cmms_module·시드14,687 유지. 교차쓰기 없음.
- 검증: GW20·Vitest518(+마지막 관련11)·tools73·브라우저17 후 업무5 재검사(고유18)·Ruff163·빌드/타입/lint/format·설계/격리/DDL 오류0. 전체pytest839통과/성능1실패(3.426초>2초), 해당 검사 단독1통과. 기준 변경 없음. 실행 상세·미실행·재현: [FS-030b 보고](GW_API화면_FS-030b.md).
- 다음은 **사용자 b 확인 후 c**: GW69행·게스트복사 검증·g01~07 도움말·참고문서·흐름맵·통합. 최신main의 CMMS/시드/head 확인부터. c는 아직 시작하지 않았다.
- 전용DB factory_studio_codex_fs030b_test/full_test/browser_test, 포트8030/5230만 사용. `.env`/`work/` 스테이징 금지. Safari·운영·전체 솔루션 브라우저 미검증.

## 지금 상태 (2026-09-30)

- **운영** https://eip.hugh-d.com — **서버는 main `3474942`(2026-10-06 배포: `tools/deploy.sh` 첫 실행. W0-1 지연 복사 · W0-2 테스트 병렬 · W0-4·W0-5 공통 엔진 · W1a HR DB · CAD-03~06)**. head **`w1a_hr_module`**, schema 0.19.0 / 138테이블, 템플릿 14,688(모듈 행 hr 포함). 확인: 원점·공개 200, 서버 DDL 대조 0, 최근 5xx 0, 게스트 생성 201 → FEMS 에너지원 3건(지연 복사 + 공통 엔진)·MES·ERP 대시보드 200. 배포는 맥북에서 `tools/deploy.sh` 한 줄(사용자 실행 — Claude는 ssh 불가).
- **최근 완료**: FS-025 BEMS(API·화면·시드) · DOC-03/04 참고 문서 4구역(설계 8·따라하기 3·개념 19) · MAP-02 P-03 보기 3종 · 홈 제목 "제조 현장의 올인원 시스템" · FS-027 게스트 별칭 필수·P-07 "게스트 접속"(별칭 90일) · UI-04 앱 안 링크 이동 미저장 보호 · 새 로고·파비콘.
- **마지막 전체 검증**: pytest 727 passed · 1 skipped, vitest 492, 전체 스모크 231 passed(+재실행 167), db:validate·격리 R1~R6 0.
- **FS-026 WMS 확장 main 병합(2026-09-30, Claude)**: Codex `codex/vision-ai` `f65044b`(입고 예정·도착·검수 W-08, 예약·소진 W-09, 3D 트럭 도착, 시드 +22, 도움말)을 main에 병합. 순서 FS-028a(SPC) → FS-026a: schema **v0.14.0 / 103테이블**, 마이그레이션 `fs026a_wms_receiving_reservation`의 down_revision을 `fs028b_spc_module`로 옮김(제약 이름은 분기 때 번호 그대로 — DDL 대조는 구조 비교). 템플릿 11,933(WMS +22, spc 모듈 행 +1), 복사 11,931. `wms-extension.spec.ts`에 FS-027 별칭 입력 추가.
- **배포 방법**: Claude가 `ssh root@158.247.236.136`·`rsync`로 직접 할 수 있다(사용자 허락, 2026-09-29~30). 순서: 프런트 빌드(별도 worktree) → rsync·chown → 서버 `git pull` → 백엔드가 바뀌었으면 `uv sync`·`systemctl restart factory-studio-api` → 시드가 바뀌었으면 `seed.cli template`. 반영 후 외부 curl 확인은 권한 분류기가 막을 때가 있다.
- **주의**: 다른 Claude 세션("EIP 포토폴리오 개발_vN")이 같은 폴더·main을 쓴다 → `git add`는 파일 지정. 스모크는 8000·5173을 쓰며 다른 세션 개발 서버가 막을 수 있다. 스모크 도중 frontend 파일을 고치지 않는다. 로컬 개발 DB는 만료 게스트가 쌓여 `.claude/launch.json`이 `GUEST_LIMIT=1000`으로 띄운다.

### 사용자 결정 (2026-09-30) — 17개 시스템 전체 구현
- 카탈로그 17개를 **모두 구현**한다(제외였던 그룹웨어·RWS 포함). 그룹웨어는 **"GW"**로 표기. 깊이는 **모두 BEMS 수준**(결정서 → 모듈·화면 설계 승인 → a DB / b API·화면 6~7 / c 시드·도움말). 다 만든 뒤에는 기능을 계속 덧붙인다.
- 방식: 큰 틀(로드맵)을 고정하고, 끝난 솔루션은 동결, 남은 것을 **하나씩** 설계·개발한다. 매 세션은 로드맵 + 대상 솔루션 + 이웃 조회 계약만 읽는다.
- 순서(ROADMAP-01 확정): 1 SPC → 2 CMMS → 3 POP → 4 TMS(FS-026 뒤) → 5 PLM → 6 CRM → 7 SCM → 8 ELB/MRO → 9 EIP → 10 GW → 11 RWS.
- **ROADMAP-01 확정(2026-09-30, 제안대로)** — `docs/plan/로드맵_17개시스템_ROADMAP-01.md`·`docs/plan/새솔루션_킷.md`. **지금: FS-028 SPC** — 설계 확정, **FS-028a DB 완료**(v0.13.0, 로컬 head `fs028b_spc_module`, pytest 727). **FS-028b 진행 중**(API `/api/v1/spc`·`fs/spc/interface.py`·MES `operation_runs`·QMS 배지·S-01~07·홈 분야별 묶음). D 다음 D45, AC 다음 AC-185.
- **Codex에 전달**: FS-026은 main에 병합됐다. 다음 작업은 새 main에서 새 브랜치로 시작한다(`codex/vision-ai`는 병합 끝). 게스트 생성 테스트는 `json={"nickname": …}`, e2e는 별칭 입력 필수(FS-027).
- **FS-028 SPC a·b·c 완료(2026-10-01, 로컬 main)** — c: 시드 `_spc`(부분군 456·측정값 2,280·이상 3: LT-0017 미조치 2·LT-0010 지그 조치 1, 공정능력 충분4·주의1·부족1), `seed/validate.py` V13, 템플릿 14,685·복사 14,683(중앙값 0.813초), 도움말 s-01~07·개념 c-20·21, 흐름 맵 `process_control`(18·21), e2e QMS 배지. **남은 것: 운영 반영**(main에 다른 세션의 `cb3fba4 WIP FS-040` 런처 평가가 함께 있다 — 같이 배포할지 사용자 확인) → README "운영 · 동결" → 로드맵 2번 CMMS 결정서(D45·AC-185부터).
- **GW(로드맵 10번)는 Codex가 병행(FS-030, 2026-10-01 사용자 지시)** — 지시서 `docs/agent/Codex_작업지시_GW_FS-030.md`(브랜치 `codex/fs-030-gw`, 번호 범위 D60~69·AC-220~239·화면 G, 스키마 버전은 병합 때 Claude가 정한다). Claude 쪽 CMMS는 D45·AC-185부터.
- **FS-030a GW DB main 병합(2026-10-01, Claude)**: Codex `codex/fs-030-gw` `cd8b619`. 충돌 4곳(시드 합계·진행 기록)만 해결 — 템플릿 14,686·복사 14,684(SPC +2,752 + gw 모듈 행 +1). 임시 버전 `0.15.0-gw` → **v0.16.0**(FS-040이 0.15.0). 검증: db:validate 0·격리 0·tools 69·실제 DB base↔head·DDL 대조 0(112·FK 258)·pytest 관련 72(seed·common·spc·gw_schema·schema_verifier·reviews)·ruff. Codex 다음은 FS-030b(API·화면) — 새 main에서 rebase.
- **지금(Claude): ROADMAP-02 전체 설계 우선** — 개발 중지. 18개(HR 신설 D79) 설계 → DSN-90 → DSN-99 → 일괄 개발. DSN-00·01 완료. **기존 7개 보강 설계 완료(확인 대기): DSN-11 ERP · 12 MES · 13 WMS · 14 QMS · 15 FEMS · 16 BEMS · 17 SPC** — 목표 DB 228테이블. 바코드 스캔(생산·창고)은 POP, 휴일 달력은 core.holiday. 목표 DB 재생성 `python3 tools/rebuild_target.py`(새 DSN 스크립트는 STEPS에). **DSN-21 CMMS 재점검 완료(6→12, 신호 출처 확장 제외) · DSN-22 POP 신규 완료(7테이블, 지연 가져오기) · DSN-23 TMS 신규 완료(10테이블, 조달 운송 포함) · DSN-24 PLM 신규 완료(16테이블, 각 솔루션 가져오기) · DSN-25 CRM 신규 완료(13테이블) · DSN-26 SCM 신규 완료(9테이블, 계획·분석만) · DSN-27 ELB/MRO 신규 완료(11테이블, 발주는 ERP) · DSN-28 EIP 신규 완료(8테이블, 사람 연결은 HR 사원 코드, **포털 첫 화면 = EIP·모듈 키 없음 D80**) · DSN-29 RWS 신규 완료(12테이블, 현장 출동은 CMMS가 가져감) · DSN-30 HR 신규 완료(19테이블, 사람·부서 코드 원천)**. **Claude 신규 설계 끝 · DSN-90 통합 검증 완료**(`docs/plan/통합검증_DSN-90.md` 2장 = 교차 조회 계약 기준본, 목표 DB target-0.19.0). **GW-EXT 병합 완료, D81(사람·조직 원천 = HR), D82(Codex 중단 — 모든 역할 Claude). DSN-99 초안(`docs/plan/개발계획_DSN-99.md`, Q1~Q5 확정 — 단계별 revision·단계마다 배포·GW 실제 도입 별도·antigravity 병행). DSN-31 GW 보강 완료(목표 DB 361테이블, rebuild STEPS …dsn30 → dsn31 → dsn90), DSN-90 7-2 GW 재검증 완료. **설계 작업 끝 · 전체 설계 확인 완료 → 일괄 개발. W0-1 지연 복사 완료(head `w01_lazy_seed`, schema 0.18.0). W0-2 테스트 병렬 완료(`pytest -n auto -m "not perf"` 3분 + `-m perf`). W0-3 배포 스크립트 완료(`tools/deploy.sh` + `tools/test_deploy.py`, 실제 실행은 사용자). W0-4 백엔드 공통 엔진 완료(`fs/common/engine.py`·`master.py`). W0-5 프런트 공통 엔진 완료(`shared/master.tsx`). W1a HR DB 완료(schema 0.19.0/138테이블, head `w1a_hr_module`). W1b-1 HR 기준정보 완료(H-02~06, 화면 15개로 조정). 다음: W1b-2 근태·휴가**. 마이그레이션은 `tools/build_migration.py`로 설계에서 생성한다. 로컬 측정 스크립트 `work/w0/run_pytest*.sh`(DB `factory_studio_fs016_test`, 다른 테스트와 동시 실행 금지), GW는 Codex. 각 문서 6장 "넘길 것"이 입력.

- **FS-040 런처 평가 완료(2026-10-01, 로컬 main, push·배포 안 함)** — `core.app_review`·`/api/v1/core/reviews`·P-02 평점 줄+패널. schema **v0.15.0 / 104테이블**, head **`fs040_app_review`**(down `fs026a`). **FS-028c·GW(FS-030) 병합 때 주의**: 다음 schema 버전은 v0.16.0, 새 마이그레이션 down_revision은 `fs040_app_review`, 새 제약 번호는 C868·R237부터. `validate_db_design`의 작업 집합에 새 작업 ID를 FS-040과 함께 넣는다. 운영 반영 시 `alembic upgrade head`만(시드 변경 없음). 남은 것: p-02 도움말에 평가 안내, e2e.
- 재현: `python3 tools/apply_fs040.py` → `npm run db:validate` → (전용 DB) `alembic upgrade head` → `tools/verify_ddl_matches_schema.py` → `pytest backend/tests/test_reviews.py`.

### 다음 후보 (사용자 결정)
1. Codex FS-026b2 결과 검토 → W-08·W-09 화면·트럭·시드 → main 병합·배포.
2. 브라우저 뒤로·앞으로 가기 미저장 보호(UI-04 한계) — 데이터 라우터 전환이 필요해 비용이 큼.
3. Safari·실기기 확인, 운영 부하 시험(미실행).
4. FS-021 범위 밖 9건(구세대 정리·`statement_timeout` 등) — Codex 영역.


## Git·작업 위치

- 저장소(메인 폴더, Claude Code 전용): `/Users/hwang-kyoungho/projects/factory-studio`
- **Codex는 `/Users/hwang-kyoungho/projects/factory-studio-codex`만 사용**, 브랜치 `codex/*`. 메인 폴더를 열거나 수정하지 않는다. antigravity worktree·브랜치도 건드리지 않는다.
- main·origin: `0addc2e`(FS-019b) 이후 ERP 하위 ID를 순서대로 ff. 매출·채권 생성은 `erp/revenue.py`(019c)에 있고 019d~e가 이어 쓴다.
- Codex의 `codex/fs-019a-erp-master`에는 **이미 main에 통합된 커밋만** 남아 있다(FS-019a는 `5da9019`·`945a78a`, 런처·3D는 `a0f71ae`·`7c83bc7`·`c3f3213`으로 통합). **Codex는 다음 작업을 새 main에서 새 브랜치로 시작**한다.
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list --branch <b>` / `gh run watch <id> --exit-status`.

## 현재 진행

| 영역 | 상태 |
|---|---|
| 포털 | 7/7 + 3D 공장(`/factory`) + **P-02 홈 UI 정돈 통합(`d93b757`, Codex `086f4d7`): 흰 헤더·F 마크·4타일(QMS 포함)·호버/`i` 안내, 하단 WMS·BEMS·SCM 링크 유지** — 제목 "네 시스템", 운영 배포 |
| FEMS | 14/14 (FS-018a~m) |
| MES | 15/15 (FS-020a~g) — `docs/agent/MES_FS-020*.md` |
| ERP | 18/18 (019a 기준정보 E-15~18, 019b 영업 E-02~04, 019c 출하 E-05~06 + 매출·채권 생성, 019d 매출·세금계산서 E-07~08, 019e 채권·수금·소명 E-09~10, 019f 매입·채무·지급 E-11~13, 019g 분개 미리보기 E-14, 019h 대시보드 E-01) — **FS-019 종료** — 계획 `docs/agent/MES_ERP_작업계획_FS-019_020.md` §3, 보고 `docs/agent/ERP_FS-019*.md` |
| FS-021 | 완료 `docs/agent/통합검증_FS-021.md` — 정책 7건 통과, AC-35~80 검증 33·부분 5·미구현 4·폐기 4(나머지는 1차 범위 밖), AC-63 결함 수정, 로컬 실측(동시 생성 지연은 현행 유지) |
| FS-022 | **완료 — https://eip.hugh-d.com**. 이지스 서버 공존(Nginx 443 이름 기반, uvicorn 127.0.0.1:8021, PG18 Docker 55432, Cloudflare 프록시 + Origin CA). 절차·업데이트·걷어내기 `docs/deploy/배포절차_FS-022.md`. 서버 접속: 맥북 `ssh root@158.247.236.136`(키) |
| UI-01 | 완료 `docs/ui/디자인시스템_UI-01.md` — main 통합·서버 배포(2026-09-26). 공통 토큰·`SolutionLayout`(접기·서랍)·넓은 업무 화면·3D 캔버스 확보. 393·10·107 통과 |
| 운영 | 443은 Cloudflare IP만, 이지스는 https://aegis.hugh-d.com(Cloudflare Access)·:8000 외부 차단, 운영자 계정은 `tools/create_member.py`(서버에서 실행), DB는 SSH 터널(§12-5) |
| UI-02 | **완료(A1~A6 전체 37화면 완료)** `docs/ui/공통UI규약_UI-02.md` — A1 대시보드(M-01, E-01), A2 조회 목록(M-09, E-07, E-14, P-07), A3 보고서형 조회(F-03, F-04, F-06, F-07, F-08, E-09·12), A4 FEMS 기준정보(F-09, F-10, F-11, F-13, F-14), A5 MES 기준정보 및 계획(M-02, M-03, M-06, M-08, M-10, M-11, M-12, M-13), A6 ERP 계획·출하·전표·기준정보(E-03, E-05, E-06, E-08, E-10·13, E-11, E-15~18) 완료 (누적 완료 40, 대기 0, Claude 선행 8, 유지 7 = 55), vitest 402 통과 |
| UI-02 검토 | Claude 검토·수정 후 main 통합(`86e729f` 이후 문서 커밋). 회귀 5건 수정·e2e 11건 갱신, 스모크 159 passed |
| QMS | FS-023a DB·023b API·화면(운영 배포) + **FS-023c 시드 113행(`sv-20260927-1`, 템플릿 7,583)·복사 월/번호 재계산·도움말 Q-01~06·흐름 맵 업무 노드(로컬, 미배포)**. 시드 LOT: LT-0017 검사 대기, LT-0015 작성 중, LT-0016 보류 중(+재검사 초안), LT-0008 특채 해제. 교차 조회는 `fs/<솔루션>/interface.py`만(R6) |
| UI-03 | **8화면 전체 완료·운영 배포** — Claude F-12·M-04·M-05·M-07·E-04(`a35e895` 배포), Antigravity B1(M-14·M-15) + B2(E-02 견적) — 브랜치 `antigravity/ui03-b2`, 스모크 171/171 통과. E-02: `FormPanel wide`(등록)·`DetailPanel wide`(상세·라인편집·확정·제출·수주 전환 통합). main 병합 완료 |
| 다음 | **FS-027 게스트 별칭 필수·P-07 게스트 접속(운영 반영). 게스트를 만드는 테스트는 `json={"nickname": …}` 필수.** 운영 `653d438` 반영 완료(2026-09-29, 프런트 de1892c 빌드). 현황 문서 정비 완료. Codex FS-026b2 진행 중. 다른 세션과 같은 폴더를 쓰므로 `git add`는 파일 지정. Codex FS-026b1 검토 완료(충돌 없음) — b2 승인 여부 사용자 결정.** 운영: `6508599`·head `fs025b_bems_module`·템플릿 11,910행(2026-09-29 반영 완료). Codex FS-026a(`521ad76`) 검토 완료: 진행 가능, 조건 = 422→400 규약, digest 날짜 제외, 시드 전 rebase — 운영은 `fs025a_bems`·`fs025b_bems_module` 마이그레이션 + 템플릿 재생성(11,910행) 필요. **Codex FS-026(WMS 확장)** 결정서를 기다린다 — Codex 새 WMS 설계(`fad0c3a`)는 기존 WMS와 겹쳐 병합 금지. FS-025c 완료: 시드 `_bems`(모델과 같은 시뮬레이션), 도움말 b-01~07, 흐름 맵 업무 노드, BEMS 카드 삭제, `CO2_IDLE` −30. 로컬 개발 DB는 만료 게스트 291개로 상한 20에 걸린다(`GUEST_LIMIT`을 올려 띄우거나 만료 공간 정리 필요). FS-025b 완료: API(`/api/v1/bems`, `fs/fems/interface.py`, `fs/bems/simulation.py`, 계약서 16장) + 화면 `frontend/src/bems/` B-01~07·포털 6타일·"여섯 시스템"(화면 설계 6장). 도움말 링크는 아직 404. 수동 명령도 시뮬레이션 시계로 기록한다. 스모크는 `smoke.sh`처럼 Node 24 PATH + fs017 DB URL을 넘긴다. 설계 확정(결정서·모듈·화면 설계 FS-025). FS-025a 완료: schema.json v0.12.0(93테이블), 로컬 head `fs025b_bems_module`(운영 미적용), 로컬 개발 DB·템플릿 반영. 025b: `fs/fems/interface.py` 신규, `/api/v1/bems`, `fs/bems/simulation.py`(모델 상수 한 곳), B-01~07. **로컬 개발 DB도 새 마이그레이션·시드 때 함께 올린다.** Codex는 `codex/vision-ai`(공장 컨셉·CNC) — 마이그레이션 head 겹치지 않게 조율 |

## 다음 할 일

- **운영 반영 완료(2026-09-27, `be87546`)**. Claude Code의 운영 SSH(`ssh root@158.247.236.136`)는 자동 모드 권한 분류기에 막혀 서버 명령은 사용자가 실행했다. 다음 배포도 같은 순서(배포절차 8장 → 시드가 바뀌면 템플릿 → 6장): 서버 pull·API 재시작·프런트 빌드 → **`seed.cli template --date 오늘` 재실행**(배포절차 4-3 아래 "시드가 바뀐 배포"). 마이그레이션 변경 없음(head `fs023b_qms_module` 유지). 운영 게스트로 Q-03에 LT-0017, M-08에 LT-0016 "QMS 보류" 배지 확인.
- `test_qms.py`의 API 테스트는 `qms` fixture가 게스트 QMS 시드를 지우고 시작한다. 시드에 의존하는 검사는 `seeded` fixture를 쓴다.

1. ERP 분담 확정(2026-09-26): **FS-019b~h 전부 Claude Code**(메인 폴더, `fs-019<x>-*`). Codex는 ERP를 하지 않는다.
2. E-G07 결정(2026-09-26): **0원 매출 세금계산서 발급 금지** — 019d에서 구현(409 `ZERO_AMOUNT_SALE`, 발급 대상 목록에서 제외).
0. **UI-02(2026-09-27)**: 브랜치 `ui-02-common-patterns` — 코드 `0875482` 뒤에 문서 커밋, main 통합(OPS `88d584f` 위 rebase). 화면은 대시보드(F-01)·조회 목록(F-02)·목록+패널(F-05) 세 패턴 중 하나로 만든다. `master-grid`는 레거시. Antigravity 작업은 `docs/agent/Antigravity_작업지시_UI-02.md`(기준 커밋 `0875482`이 main에 있어야 시작). 예외 8화면(F-12·M-04·M-05·M-07·M-14·M-15·E-02·E-04)은 Claude가 UI-03에서 대표 구현을 먼저 확정한다. 로컬 검증 스크립트(`work/ui02/*.mjs`, Git 제외)는 5173·8000 개발 서버와 `work/ui02/state.json` 게스트 세션을 쓴다 — 공식 검증은 `e2e/layout.spec.ts`.
3. **UI는 `shared/styles.css` 토큰·공통 클래스만 쓴다(UI-01).** 솔루션 메뉴는 `*Screens` 배열만 고친다. ERP 화면 모양을 FEMS·MES와 맞춘다: 관리 버튼 `link-button`, 등록 폼 select는 `.field` 안 전체 폭. 019b부터 ERP 화면은 `erp/common.tsx`(shared/hooks 위 ERP 접두사)와 `SalesOrders.tsx`의 `LineEditor`를 재사용한다.
4. 후속: (UI-01에서 360px 상단 메뉴 해소) 인라인 폼 미저장 변경 보호. 사용 중 채널 배수 변경 허용 유지 여부(FEMS_FS-018l).
5. **새 업무 테스트는 `guest_space` fixture**, 스모크는 8000·5173·`factory_studio_fs017_test`를 고정 사용하므로 **동시에 한 명만** 돌린다. 사용자가 개발 서버(8000·5173)를 켜 두면 스모크가 멈춘다 — 종료를 요청한다.
6. 판단 기록: MES `/work-orders/{id}/lot` 추가(020c), `/executions/{id}/finish`를 `/result`로 통합(020d), MES 업무 시각 `clock_timestamp()`(020g).

## 재현·주의점

- DB: Claude Code는 `factory_studio_fs016_test`(pytest)·`factory_studio_fs017_test`(스모크), Codex는 `factory_studio_codex_test`만. 같은 DB에 pytest를 동시에 돌리지 않는다.
- Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. backend 테스트는 `.env` 없이 DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만.
- **ruff는 CI 범위로만**: `ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `format --check`.
- schema.json·마이그레이션은 작업 ID 범위에서만(이미 적용한 revision 수정 금지). pytest DB는 새 head가 생기면 `alembic upgrade head`를 먼저 돌린다(`test_schema_verifier` 기준선). `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 확정·게시 데이터 불변, 업무 쓰기는 `write_scope` 뒤, 결측(invalid)은 합계에서 제외.
- 30분마다 WIP 커밋, 종료 시 이 문서 갱신·커밋. `.env`·`work/`·`node_modules`는 스테이징하지 않는다. `git push --mirror` 금지.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# backend: CI 환경 변수 네 개만 전달 (접속 URL은 출력하지 않는다)
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$db_url" TEST_DATABASE_URL="$test_db_url" \
  uv run --project backend pytest backend/tests -q
uv run --project backend --env-file .env python tools/run_portal_smoke.py   # 8000·5173 비어 있어야 함
python -m unittest discover -s tools && npm run db:validate && python tools/audit_schema_isolation.py && git diff --check
```


## Codex — FS-019a (2026-09-25)

- 브랜치: `codex/fs-019a-erp-master`, 전용 `factory-studio-codex`만 사용.
- 마지막 커밋: `5ad511d WIP FS-019a`(보존 커밋 d47b8a4를 6bcbe1e 위로 rebase한 결과). 이 절과 최종 결과는 후속 `FS-019a: ERP 기준정보 구현 및 회귀 검증` 커밋에 포함한다. 최신 커밋은 `git log -1`로 확인한다.
- 끝난 것: ERP E-15~18 API·화면·도움말·API 계약, guest_space 기반 ERP 회귀 78개, 프론트 ERP 테스트 20개. MES/ERP 라우트를 모두 보존했고 Home은 세 솔루션 화면 진입으로 변경. Field children 제거, select 직접 렌더링, checkbox inline-check 적용.
- 검증: 최종 frontend 5종(314 tests), CI Ruff 2종, db:validate, audit_schema_isolation, diff --check exit 0. backend 전체 510 passed, 580.736초, exit 0(CI 환경 네 변수만, 전용 DB).
- 다음: 사용자 승인 후 공용 포트/DB 스모크 실행 및 ERP 360px 스크린샷 직접 확인. 아직 실행 승인이 없어 미실행. FS-019a 완료 판정은 이 검증 뒤이며 FS-019b 착수·push·main 병합은 사용자 확인 뒤.
- 주의: pytest DB는 `factory_studio_codex_test`, 스모크는 `factory_studio_fs017_test` + 8000/5173(Claude Code와 공유). 동시 실행 금지. schema.json·마이그레이션·test_common.py·test_seed.py·conftest 변경 없음. 새 의존성 없음.
- 보고서: `docs/agent/ERP_FS-019a.md`(명령·exit·런타임·남은 검증).

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:/opt/homebrew/bin:/usr/bin:/bin"
npm --prefix frontend run typecheck && npm --prefix frontend run lint && npm --prefix frontend run format:check
npm --prefix frontend run build && npm --prefix frontend test
# task_test_url은 factory_studio_codex_test 접속 URL. .env 없이 네 변수만 전달.
env -i HOME="$HOME" PATH="$PATH" DATABASE_URL="$task_test_url" TEST_DATABASE_URL="$task_test_url" uv run --project backend pytest backend/tests -q --durations=15
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
uv run --project backend ruff format --check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
npm run db:validate
uv run --project backend python tools/audit_schema_isolation.py
git diff --check
# 스모크는 사용자 승인 후 tools/run_portal_smoke.py 실행.
```


## Codex — P-02 런처 크기 조정 (2026-09-25)

- 브랜치 `codex/fs-019a-erp-master`, 기준 마지막 커밋 `4e2bc74`. 후속 `P-02: 솔루션 런처 아이콘 타일 크기 조정` 커밋에 이 인계 포함(`git log -1`로 확인).
- 끝난 것: 사용자 두 번째 이미지의 작은 아이콘 타일/하단 이름 배치 적용. Home.tsx·Home.css 변경, 기존 색상·동작 보존.
- 검증: Node 24.21.0, frontend typecheck/lint/format:check/build/test(314 passed) 및 diff --check 모두 exit 0.
- 다음: Claude Code가 새 main 통합 뒤 스모크·360px(ERP 및 런처 포함) 직접 검증. Codex는 사용자 지시로 스모크를 실행하지 않는다. 결과에 따른 수정 요청 대기. backend 검증 미실행(UI만 변경).
- 재현: 전용 factory-studio-codex에서 Node 24 PATH 지정 후 `npm --prefix frontend run typecheck`, `npm --prefix frontend run lint`, `npm --prefix frontend run format:check`, `npm --prefix frontend run build`, `npm --prefix frontend test`.
- 메인 폴더 미사용, push·main 병합 없음. .env·work/·node_modules 제외.

## Codex — 3D 공장 둘러보기 (2026-09-26)

- 브랜치 `codex/fs-019a-erp-master`, 마지막 보존 커밋 `5593693 WIP: 3D 공장 둘러보기 구현 보존`(기준 f9eb879). 이 인계·최종 수정은 후속 `3D 공장: 조감도와 3인칭 현장 둘러보기` 커밋에 포함한다. 최종 해시는 `git log -1`.
- 끝난 것: 사용자 승인한 조감도·3인칭 이동, 일반 조립/비전검사/포장 설비 3대·키오스크, 1층 현장사무실 1명·바코드 프린터, 2층 사무실 2명, 현장 순회 1명 + 사용자 캐릭터. `/factory`, 상단 앱 런처 오른쪽 메뉴. 상세 `docs/agent/3D공장_구현.md`.
- Node 24.21.0. 최종 frontend typecheck/lint/format:check/build/test(330 passed) 및 독립 브라우저 7개(20.0초), diff --check 각각 exit 0. 스크린샷 직접 확인. backend·DB·공용 스모크 미실행.
- 새 의존성은 package-lock에 고정. 통합 시 `npm --prefix frontend ci`. three/Fiber/Drei와 @types/three. 공장 화면에만 lazy load. 코드 생성 모델로 외부 모델 자산 없음.
- 재현: 전용 폴더에서 Node 24 PATH를 지정한 후 `npm --prefix frontend run test:factory-browser`. 전용 5186을 시작/종료하며 API는 모두 모의 응답한다. 공용 8000·5173·스모크 DB를 사용하지 않는다.
- 다음: Claude Code가 새 main 통합 뒤 전체 스모크·360px 실행. 사용자는 Codex의 공용 스모크 실행을 금지했으므로 실행하지 않는다. 통합 시 ERP(4e2bc74)·런처(f9eb879)·3D(WIP+후속)의 범위를 구분한다. 수정 요청 대기.
- 메인 폴더·antigravity 미사용. push/main 병합 없음. .env·work/·node_modules 제외. 별도 테스트 서버는 종료한다.


## 2026-09-26 Blender 비전검사 설비 (Codex)

- 사용자 "참고자료 없이 바로 진행" 승인. `codex/factory-vision-blender`에서 기존 공장의 비전검사 1대를 Blender 원본/GLB로 교체.
- 카메라·링 조명·컨베이어·경광등, 6초 검사 주기·5번째 불합격, 상태/수량 패널·가까이 보기·이상 정지/해제·MES 대시보드 진입. 합성 시연이며 업무 데이터에 저장하지 않음.
- Node 24.21.0: frontend typecheck/lint/format:check/build/test(345 passed), 독립 Chromium 브라우저 8개 통과(exit 0). 360px/데스크톱 직접 확인. Blender 5.2.2 GLB 생성 성공.
- DB/API 변경·새 의존성 없음. backend/DB/공용 통합 스모크 미실행. main 병합·push 없음.
- 원본 `assets/blender/vision-cell.blend`, 재생성 `tools/blender/build_vision.py`, 상세 보고 `docs/agent/3D공장_Blender_비전검사.md`.
- 다음: 시각 피드백·통합 담당자 main 통합. MES 실제 레코드 연결 및 FEMS는 후속 설계.


## 2026-09-26 3D 공장 공간 고도화 (Codex, 완료)

- 브랜치 `codex/factory-building`, 기준 `b352514`(비전검사). 사용자 우선순위 진행 및 이어서 진행 승인.
- Blender 건물 외관/내부 전환, 지붕·패널·창문·하역장·공조기·철골·덕트·천장 조명. 조립·포장 설비도 Blender 모델로 교체하고 프레스·실링바 시연.
- 바닥 질감·환경 반사·그림자, 자재 선반/공구대/소방함 및 충돌. MES/ERP/FEMS 기존 화면 진입 카드. 업무 API/DB·실제 데이터 연동 없음.
- Node 24.21.0: typecheck/lint/format:check/build exit 0. 전체 테스트는 자원 경합을 줄인 `npm --prefix frontend test -- --maxWorkers=2`로 346개 통과. 독립 Chromium 브라우저 10개 통과(2.1분, exit 0). 외관/내부/모바일 스크린샷 직접 확인.
- Blender 5.2.2 LTS. 생성 스크립트와 .blend/GLB를 저장. 새 npm 의존성 없음. 상세 `docs/agent/3D공장_공간고도화.md`.
- backend/DB/공용 통합 스모크·Safari/실기기 성능은 미실행. main 병합·push 없음. 다음: 사용자 시각 피드백 및 통합 담당자 main 통합. 최종 커밋은 이 인계를 포함한 `3D 공장: 건물·재질·생산라인 공간 고도화`이며 `git log -1`로 확인.

## Antigravity — UI-02 A1 (2026-09-27)
- 브랜치: `antigravity/ui02-a1` / 기준 커밋: `ed9f438cbbd1f2aacec67a3029304020e3d7865e` (main) / 마지막 커밋: `ce731ab`
- 옮긴 화면: M-01(`frontend/src/mes/Dashboard.tsx`), E-01(`frontend/src/erp/Dashboard.tsx`)
- 내용:
  - 별도 `filter-bar`의 조회 월 입력을 `PageTitle`의 `actions`로 이동
  - 카드 순서·내용 및 2×2 유지, 쿼리 파라미터 및 KPI 보존
  - `frontend/e2e/layout.spec.ts`에 M-01 및 E-01 조회 월 위치 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A2 (2026-09-27)
- 브랜치: `antigravity/ui02-a2` / 기준 커밋: `ce731ab` (`antigravity/ui02-a1`) / 마지막 커밋: `26e9ab3`
- 옮긴 화면: M-09(`frontend/src/mes/Receipts.tsx`), E-07(`frontend/src/erp/SalesRecords.tsx`), E-14(`frontend/src/erp/Journal.tsx`), P-07(`frontend/src/portal/Records.tsx`)
- 내용:
  - 각 화면 루트에 `.page-fill` 적용
  - P-07: 상단 탭을 `DataTable`의 `leading` prop으로 전달 (F-02 기준 화면 구조 준수)
  - 안내문 `<p className="muted" role="note">` 규약 정비 및 `Loading delay={300}` 적용
  - P-07의 ADMIN 권한 분기 및 API 계약 보존
  - `frontend/e2e/layout.spec.ts`에 A2 화면들(`.page-fill`) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A3 (2026-09-27)
- 브랜치: `antigravity/ui02-a3` / 기준 커밋: `26e9ab3` (`antigravity/ui02-a2`) / 마지막 커밋: `ad54b6c`
- 대상 화면: F-03(`fems/Allocations.tsx`), F-04(`fems/Emissions.tsx`), F-06(`fems/Intensity.tsx`), F-07(`fems/Targets.tsx`), F-08(`fems/Billing.tsx`), E-09·12(`erp/Receivables.tsx`)
- 내용:
  - `.page-fill`을 쓰지 않고 자연스러운 문서 스크롤 유지 (합계·근거·표 복합 구조)
  - 직접 쓴 표 숫자 열에 `th.num`, `td.num` 클래스 적용 (F-04 배출량·소비량, F-06 원단위·생산량, F-07 달성률·목표·실적, F-08 요금, E-09/12 채권·채무 원금·소명액·잔액)
  - 합계 계산 표시, 계산 근거 펼침(`basis-panel`), 결측 제외 문구, 목표 초과 배지 글자 보존
  - 안내문 `<p className="muted" role="note">` 및 `Loading delay={300}` 공통 규약 정비
  - `frontend/e2e/layout.spec.ts`에 R 패턴 화면들(.page-fill 미사용) 레이아웃 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A4 (2026-09-27)
- 브랜치: `antigravity/ui02-a4` / 기준 커밋: `ad54b6c` (`antigravity/ui02-a3`) / 마지막 커밋: `e6c9fd9`
- 대상 화면: F-09(`fems/Sites.tsx`), F-10(`fems/Equipments.tsx`), F-11(`fems/EnergySources.tsx`), F-13(`fems/Factors.tsx`), F-14(`fems/Tariffs.tsx`)
- 내용:
  - 레거시 `master-grid` 제거 및 `.page-fill` + `.split-view` + `FormPanel` + `useDiscardGuard` 표준 S 패턴 전환
  - F-09: 사업장과 공간 2개 섹션 블록 및 공통 FormPanel 적용
  - F-13: DataTable leading 탭 구조 및 FormPanel 통합
  - `frontend/e2e/layout.spec.ts`에 A4 화면들(.page-fill) 및 에너지원 패널 열기/닫기 검사 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음

## Antigravity — UI-02 A5 (2026-09-27)
- 브랜치: `antigravity/ui02-a5` / 기준 커밋: `e6c9fd9` (`antigravity/ui02-a4`)
- 대상 화면 8개:
  - M-02 생산계획: `frontend/src/mes/Plans.tsx` (FormPanel 적용, RevealAnchor 제거)
  - M-03 작업지시: `frontend/src/mes/Orders.tsx` (FormPanel 적용, ?line= 프리셋 패널 자동 열림)
  - M-06 자재 투입: `frontend/src/mes/Materials.tsx` (FormPanel title="자재 투입 등록", inner form 제거)
  - M-08 패킹: `frontend/src/mes/Packing.tsx` (FormPanel 적용, inner form 제거)
  - M-10 사업장·공간: `frontend/src/mes/Sites.tsx` (2개 섹션 블록 + FormPanel S 패턴)
  - M-11 설비: `frontend/src/mes/Equipments.tsx` (FormPanel S 패턴)
  - M-12 품목: `frontend/src/mes/Items.tsx` (FormPanel S 패턴, RevealAnchor 제거)
  - M-13 공정: `frontend/src/mes/Processes.tsx` (FormPanel S 패턴)
- 내용:
  - 모든 컴포넌트에서 React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 무조건 호출하도록 구조 정리
  - `FormPanel` 내 중첩 `<form>` 제거로 브라우저 경고 및 파싱 오류 방지
  - `planning.test.tsx`, `master.test.tsx`에서 패널 오픈 버튼 클릭 후 폼 조회하도록 단위 테스트 동기화
  - `frontend/e2e/layout.spec.ts`에 8개 MES 화면 `.page-fill` 검사 및 설비 패널 열기/닫기 E2E 테스트 추가
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. A6(ERP 계획·출하·전표·기준정보 화면)으로 이어짐

## Antigravity — UI-02 A6 (2026-09-27)
- 브랜치: `antigravity/ui02-a6` / 기준 커밋: `cd0c1d7` (`antigravity/ui02-a5`)
- 대상 화면 10개 (11개 메뉴):
  - E-15~18 기준정보: `frontend/src/erp/Master.tsx` (`Partners.tsx` E-15, `Items.tsx` E-16, `Prices.tsx` E-17, `Accounts.tsx` E-18 공용). `children` prop 지원, `FormPanel` 전환, `Accounts.tsx` split-view + 매핑 이유 aside 패널 결합.
  - E-03 판매계획: `frontend/src/erp/SalesPlans.tsx` (`master-grid` 및 `RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("판매계획 만들기")`).
  - E-05 출하지시: `frontend/src/erp/ShipmentOrders.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하지시 만들기")`, 미출하 취소 동작 유지).
  - E-06 출하: `frontend/src/erp/Shipments.tsx` (`RevealAnchor` 제거, `page-fill` + `split-view` + `FormPanel("출하 확정")`, 수기 패킹번호 동작 유지).
  - E-08 세금계산서: `frontend/src/erp/TaxInvoices.tsx` (등록·발급 두 폼을 `FormPanel` 모드 전환으로 S 패턴 통합, 0원 매출 발급 방지 및 409 안내 유지).
  - E-10·E-13 수금·지급 등록·소명: `frontend/src/erp/Receipts.tsx` (수금·지급 공용 컴포넌트, `master-grid` 및 `RevealAnchor` 제거, `FormPanel` 등록 전환, 409 LIMIT_EXCEEDED 오류 안내 유지).
  - E-11 매입 전표: `frontend/src/erp/PurchaseInvoices.tsx` (`master-grid` 및 `RevealAnchor` 제거, 등록·취소 두 패널을 `FormPanel` 모드 전환으로 통합).
- 내용:
  - React Rules of Hooks 준수: `useDiscardGuard`를 early return (`moduleOff`) 이전에 호출하여 조건부 훅 오류 원천 차단
  - E2E 및 단위 테스트 최신화: 패널 오픈 버튼 클릭 후 폼을 조회하도록 테스트 보강 (`Prices.test.tsx`, `Partners.test.tsx`, `Items.test.tsx`, `shipping.test.tsx`, `revenue.test.tsx`, `purchases.test.tsx`)
  - `frontend/e2e/layout.spec.ts`에 전체 ERP 화면 `.page-fill` 검사 및 ERP 거래처 등록 패널 열기/닫기 E2E 테스트 추가
  - **Antigravity UI-02 작업 묶음 A1~A6 (총 37개 화면) 전체 완료** (완료 40, 대기 0, Claude 선행 8, 유지 7 = 총 55개 화면).
- 검증: typecheck·lint·format:check·build·test(43개 파일 402개 테스트 통과)·diff --check 모두 통과(exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 및 Claude 선행 8개 화면(UI-03: F-12, M-04, M-05, M-07, M-14, M-15, E-02, E-04) 진행 대기

## Claude Code — UI-02 검토·main 통합 (2026-09-27)

- Claude 검토(2026-09-27): 공식 스모크를 처음 돌려 11건 실패를 찾았다(Antigravity 묶음 검증에는 스모크 없음). 실제 회귀 5건 수정 — M-06 BOM 제안량 표가 겹침 패널에 가려 채울 수 없음(→ 패널 안으로), M-12 '환산'이 등록 패널을 자동으로 열어 목록을 가림(→ 목록만, 등록은 버튼), E-05·E-06·E-10/13 저장 직후 새 행 선택이 미저장 보호에 막힘(→ 가드 없는 `choose()`), E-18 설명 패널이 표와 겹침(→ main 구조·R 패턴 복원), F-09 인라인 style·정의 없는 `section-block`(→ 공통 `.section-block` 추가). 나머지 6건은 e2e 흐름 갱신. 레이아웃 e2e를 '클래스 존재' → '1440×900 문서 높이'로 강화.
- 검증: typecheck·lint·format:check·build, vitest 402, 스모크 **159 passed**(7.6분, exit 0), 55경로 × 1440·1600·390 전후 비교(가로 넘침·오류 0), S 화면 24개 패널 열기·저장 버튼·Esc(행 선택형 M-06·M-08 포함).
- 통합: `antigravity/ui02-a6` + 검토 커밋(`e8b0d71`·`86e729f`)을 main에 fast-forward. push·서버 배포 전.
- 주의(다음 Antigravity 지시에 반영): 묶음마다 **공식 스모크(`tools/run_portal_smoke.py`)** 를 돌려야 한다. 단위 테스트는 패널 뒤 목록이 가려지는 문제를 잡지 못한다. 기본 e2e 뷰포트 1280px은 패널 겹침 모드다.
- 배포(2026-09-27): origin push `88d584f..0378bf6`, 서버 `git pull --ff-only`(백엔드·마이그레이션 변경 없음 → API 재시작 없음), 맥북 별도 worktree에서 `0378bf6` 프런트 빌드 → rsync. 확인: Cloudflare 경유 200·새 번들 해시 일치·API 5xx 0, 운영 게스트로 F-02·F-05·M-12·E-15 1440×900 문서 900px, F-01 1600 하단 2×2, F-05 패널 열림, 페이지 오류 0.
- UI-03 예외 패턴(2026-09-27, Claude Code): 공통 `DetailPanel`(폼 없는 패널)·`wide`(640px, 1920px 이상 붙음·이하 겹침)를 `SidePanel` 하나로 구현. 기준 화면 — 읽기 전용 상세 M-04, 부모-자식 F-12(채널 상세 ↔ 채널 폼), 넓은 행 편집 E-04(등록·상세·편집), 상태 전이 M-05·M-07(`ResultForm`을 패널로). 규약 8장·적용표(완료 45, Antigravity 대기 3: M-14·M-15·E-02 → 지시서 UI-03 B1·B2).
  - 검증: typecheck·lint·format·build, vitest 402, 대표 화면 5개 × 1920·1600·1440·390 패널 모드·문서 높이·가로 넘침 확인, e2e(layout·fems·mes·portal) 151 passed / 2 failed(F-03 배분 추정·F-01 전월 목표 초과 — 이번에 바꾸지 않은 화면, e2e를 여러 번 돌려 로컬 개발 DB가 바뀐 데이터 의존 실패로 판단). **공식 스모크는 미실행**: 같은 메인 폴더에서 다른 세션(DOC-01)이 동시에 작업 중이라 8000·5173을 점유하는 스모크를 돌리지 않았다.
  - 주의: 이 폴더에서 다른 세션이 동시에 커밋 중(DOC-01 `238a7a0`이 UI-03 WIP 사이에 있음). 스테이징은 경로를 지정한다. push·배포 전.
- UI-03 스모크·배포(2026-09-27): 공식 스모크 **164 passed**(7.7분, exit 0 — 로컬에서 실패하던 F-03·F-01도 통과, 데이터 의존 실패 확인). origin push `6e22e00..a35e895`(DOC-01·DOC-02 포함), 서버 pull(백엔드 변경 없음, API 재시작 없음) → `a35e895` 프런트 빌드·rsync. 확인: 새 번들 해시 일치·200·API 5xx 0, 운영 게스트 1920×1080에서 M-04·F-12·E-04 넓은 패널(640) 붙음, M-05·M-07 패널(380), 문서 1080px, 오류 0.

## Antigravity — UI-03 B1 (2026-09-27)

- 브랜치: `antigravity/ui03-b1` / 기준 커밋: `24179d1`
- 대상 화면 (2개):
  - M-14 공정 경로: `frontend/src/mes/Routes.tsx` (F-12 부모-자식 패턴 적용: 경로 버전 목록 → 단계 목록 `DetailPanel wide` → 단계 폼 `FormPanel`, 게시한 버전 불변, '개정'·'게시' 동작 유지, `RevealAnchor` 제거)
  - M-15 BOM: `frontend/src/mes/Boms.tsx` (BOM 목록 → 자재 라인 `DetailPanel wide` → 라인 폼 `FormPanel`, 게시한 버전 불변, 개정 새 코드 `FormPanel`, `RevealAnchor` 제거)
- 테스트 갱신 및 추가:
  - `src/mes/versions.test.tsx`: BOM 라인 폼 전환에 따른 라벨·버튼 접근자 갱신 (8 tests passed)
  - `e2e/mes.spec.ts`: 공정 경로 개정 흐름 갱신(패널 열림 확인 → 순서 편집 → 저장 → 패널 닫기 후 목록에서 게시)
  - `e2e/layout.spec.ts`: M-14 공정 경로 단계 패널 및 M-15 BOM 자재 패널 1440×900 문서 높이 ≤ 900 및 Esc 닫기 검사 추가
- 검증:
  - `npm --prefix frontend run typecheck`: exit 0
  - `npm --prefix frontend run lint`: exit 0
  - `npm --prefix frontend run format:check`: exit 0
  - `npm --prefix frontend run build`: exit 0
  - `npm --prefix frontend test`: 44개 파일 410개 테스트 통과 (exit 0)
  - `git diff --check`: exit 0
  - `uv run --project backend --env-file .env python tools/run_portal_smoke.py`: 공식 스모크 **166 passed** (8.0분, exit 0)
- 공통 컴포넌트 확장 요청: 없음
- 남은 문제: 없음. 사용자 확인 후 UI-03 B2 (E-02 견적 넓은 행 편집 화면) 진행 대기

## 2026-09-27 1인칭 비전검사 체험 (FS-3D-FP01, Codex 완료)

- 브랜치 `codex/factory-building`, 기준 `d3eaf31`. 사용자 승인한 웹 1인칭 검사 구역 데모 구현.
- `/factory`의 1인칭 체험 진입, 눈높이 이동·드래그 시선·충돌, 직접 클릭/탭·E 선택, 데스크톱 옆 패널/모바일 아래 패널. 작업자 1명·태블릿·안전 구획·조명 보강.
- 상태·판정·검사/합격/불합격 수량·링 조명·시연 설정값. 합성 시뮬레이션이며 실제 업무 API/계측/DB 연결 없음. 실사 품질 인물·재질은 후속 개선 대상.
- Node 24: typecheck/lint/format:check/build exit 0. Vitest 348개/36파일 통과. 기존 Chromium 회귀 10개 통과, 새 1인칭 3개는 최종 분리 실행에서 모두 통과(1.9분). 처음 한 테스트에 선택·이동·스크린샷을 묶어 60초 제한을 초과한 것은 테스트를 분리해 해소. 화면 직접 확인.
- 5186·모의 API만 사용, backend/DB/공용 스모크·실기기 FPS·Safari/WebXR 미검증. main 병합·push·운영 배포 없음.
- 보고서 `docs/agent/3D공장_1인칭_비전검사.md`. 다음: 통합 담당자가 현재 main/UI 변경과 대조해 3D 커밋 반영 여부 확인 후 사용자 체험. 실제 데이터 매핑과 실사 자산은 별도 후속 범위.
- 통합(2026-09-27, Claude Code): Antigravity UI-03 B1(`2cda062`, M-14 공정 경로·M-15 BOM 부모-자식 패턴) fast-forward + Codex 1인칭 비전검사 체험(`2a739c2` → cherry-pick `941a50d`). Codex 브랜치는 UI-01 이전 코드 기준이라 `Factory.tsx`·`Factory.css` 충돌 — main 파일을 기준으로 Codex 변경 13가지(체험 상태·진입/나가기·포커스 가둠·툴바·조준점·E 선택·이동 패드·설비 상태/설정 패널 등)를 다시 적용하고 CSS 블록은 원본과 동일함을 확인. 보정 `bf8c8e9`: 1인칭에서 설비 상세가 UI-01 겹침 규칙 때문에 장면과 6px 겹치던 것 → 옆 칸 배치.
  - 검증: typecheck·lint·format·build, vitest 412, 3D 브라우저 13 passed(1인칭 신규 3 포함), 1인칭 1440·390 설비 선택·상세·Esc 해제 직접 확인, M-14·M-15 넓은 패널 1440 한 화면, 공식 스모크 **169 passed**(9.6분, exit 0).
  - 참고: DOC-02는 직전 배포(`a35e895`)에 포함되어 이미 운영에 반영됨(작성 세션의 현황 기록은 '배포 보류'였음).
- 배포(2026-09-27): push `24179d1..ad199c1`, 서버 pull(백엔드 변경 없음, API 재시작 없음) → 프런트 빌드·rsync. 확인: 새 번들 해시 일치·API 5xx 0, 운영 게스트 M-14·M-15 넓은 패널 1440 한 화면, 1인칭 체험 설비 상세 열림, 오류 0(첫 방문은 3D 모델 내려받기 대기 필요).
- FS-023 QMS 설계(2026-09-27, Claude Code): 사용자 결정 "QMS 먼저, 읽기 전용 조회" 반영. 산출물 — 결정서 `docs/plan/QMS도입_교차조회_결정_FS-023.md`(D8 QMS 구현 편입·출하 전 최종검사, D9 읽기 전용 조회 인터페이스 X1~X6·격리 규칙 R6, D10 보류는 표시만, D11 스냅샷 보관, D12 독립 동작), 모듈 설계 `docs/modules/qms/QMS_모듈설계_FS-023.md`(qms 6테이블 컬럼·제약·UK_PARTIAL, 상태 전이, TX-Q1~Q3, 인터페이스 함수, API, 시드 약 126행, AC-97~110), 화면 설계 `docs/ui/화면설계_QMS_FS-023.md`(Q-01~06, 기존 D·L·S·P·V·W 패턴만 사용, MES M-08·M-04 배지). 문서 정리: 현황 5장 교체, QMS·WMS README의 'core 소유' 표현 정정.
  - 검증: 설계 문서 정적 대조만(schema.json 테이블 수 71 = mes 21·erp 27·fems 13·core 10 확인). schema.json·마이그레이션·Excel·ERD·코드 변경 없음(승인 후 FS-023a). `npm run db:validate` 미실행(메타데이터 미변경).
  - 다음: 사용자 승인(결정서 6장 3문항 + 모듈 설계 13장 3문항) → FS-023a.
- FS-023a QMS DB 반영(2026-09-27, Claude Code): 사용자 승인(D8~D12·범위·순서·발번·기본 월·패킹 무관 보류 모두 권장안). `schema.json` v0.10.0 — qms 6테이블(불량 유형·검사 기준·검사 항목·검사·측정값·품질 보류), `core.workspace_module` module_key에 qms. 적용 스크립트 `tools/apply_fs023a.py`(멱등, 새 제약·관계는 끝에 붙여 기존 C·R 번호 유지). 마이그레이션 `20260927_fs023a_qms_schema.py`(revision `fs023a_qms`, 실행 시 JSON 미참조 고정 SQL, 제약 이름 = C·R 번호). 검증 도구: `audit_schema_isolation.py` BUSINESS에 qms + **R6**(다른 솔루션은 `fs.<B>.interface`만 import, AST 검사), `validate_db_design.py` FS-023a 엔티티 목록(설계서 표)·`validate_qms`, `verify_ddl_matches_schema.py`·Excel·ERD 생성기에 qms. Excel 23시트·ERD `qms.mmd` 재생성.
  - 수치: 77테이블 · 785컬럼 · FK 175 · 제약/정책 587(DB 제약: PK 77·UK 178·CHECK 183·INDEX 46·UNIQUE_INDEX 11, SERVICE 정책 92).
  - 검증: `npm run db:validate` 오류 0, 격리 검사 R1~R6 오류 0, 도구 단위 테스트 49 OK(신규 `test_fs023a.py` 5), pytest DB에서 alembic upgrade head → verify_ddl 오류 0 → downgrade -1 → downgrade base → upgrade head → verify 오류 0, 로컬 개발 DB upgrade·verify 오류 0, backend pytest **648 passed**(13분 45초), ruff check·format 통과.
  - 미실행: 공식 스모크(프런트·API 변경 없음, 스모크는 실행 시 head를 자체 적용), 운영 서버 마이그레이션(배포 전).
  - 주의: 새 공간의 `qms` 모듈 행 생성·게스트 세대 복사/정리 순서에 qms 추가는 FS-023b·c. 현재 qms 테이블은 비어 있어 기존 복사·회수에 영향 없음(pytest로 확인).
  - 다음: FS-023b — `fs/mes/interface.py`·`fs/qms/interface.py`, `/api/v1/qms` API(TX-Q1~Q3), Q-01~06 화면, MES 배지.


## 2026-09-27 비전검사 AI 설명·세 시나리오 (FS-3D-AI01, 로컬 구현)

- 브랜치 `codex/vision-ai`, 기준 `origin/main 8851772`. 기존 `codex/home-ui-polish` 작업은 보존하고 통합된 1인칭 코드에서 시작했다.
- 정상/불합격 증가/정지 전환, 상태등·판정 주기·검사 정지 연동, AI 설명 버튼 구현. 확인된 사실 / 원인 가능성 / 다음 확인 항목을 구분한다. 활성 시나리오 재선택은 누계를 보존한다.
- 고정 합성 비교 자료: 정상 2%→2%, 증가 2%→20%(+18%p), 정지 처리량 100→50개. 실시간 애니메이션 누계·실제 검사 이미지·업무 센서값과 구분한다.
- 인증·CSRF가 필요한 읽기 전용 설명 API, 서버 전용 OpenAI Responses 어댑터, 성공 캐시·동시 호출 제한·실패 대기 구현. 키 미설정/공급자 오류는 출처가 표시된 데모 설명으로 대체한다. DB·스키마·업무 데이터 변경 없음.
- 프런트 420개/46파일, typecheck/lint/format/build 통과. 서버 DB 없는 모의 공급자 테스트 13개, Ruff 검사/포맷 통과. 배포 wheel의 시나리오 JSON 포함 확인.
- 실제 OPENAI_API_KEY가 없어 실제 Astra 호출·응답 품질·계정 접근은 미검증. 공용 DB 스모크·Safari·실기기 성능은 미실행. main 병합·push·운영 배포 없음.
- 남은 통합 작업: 커밋 반영 검토 → 공식 스모크 → 백엔드 재시작·프런트 재빌드. 실제 AI를 활성화할 경우 서버 비밀 설정에 키를 추가하고 세 시나리오 응답 확인. 운영 반영 여부와 무관하게 키 없이 데모 체험 가능.
- 설계 `docs/modules/factory/README.md`, 상세 인계·재현 명령 `docs/agent/3D공장_AI설명_FS-3D-AI01.md`. 이번 범위 구현 완료, 운영 통합과 실제 모델 검증은 남음.


### 최종 검증 (FS-3D-AI01)

- Node 24 typecheck/lint/format:check/build 통과, Vitest **420 passed / 46 files**.
- DB 없는 backend 설명 테스트 **13 passed**, Ruff check/format 통과. wheel에 `fs/factory/scenarios.json` 포함 확인.
- Chromium 기존 회귀 13개 통과. 신규 시나리오·모바일 2개는 최종 분리 실행 **2 passed**. 전체 실행에서는 한 테스트가 접힌 비교 자료의 중복 문구를 찾아 실패했으나, 보이는 설명 문구를 선택하도록 수정한 후 재검증했다. 총 15개 시나리오 검증, 최종 단일 전체 실행은 반복하지 않았다.
- 1440×900 1인칭 설명 화면과 390px 모바일 패널 캡처 직접 확인. 모바일 가로 넘침 없음. 빌드의 기존 3D 청크 크기 경고와 THREE.Clock 사용 중단 예정 경고는 남아 있다.
- 실제 모델 요청과 공용 DB 스모크는 실행하지 않았다. 작업 폴더 `factory-studio-codex`, 브랜치 `codex/vision-ai`. 결과물은 이번 완료 커밋에 포함되며 원격 push/배포는 하지 않았다.


## 2026-09-27 합성 이미지 검사실 (FS-VISION-LAB01)

- 사용자 승인 범위 구현: 정상/이물/조명 변화 샘플, 전체/중앙 ROI, 임계값·최소 연결 면적 조절, 원본/이진화 화면과 검출 영역, OK/NG 및 오검출·미검출·영역 밖 결함 픽셀 수. 레시피·결과 JSON 다운로드.
- `/factory/vision-lab`, 비전검사 설비 상세에서 진입. 브라우저 순수 함수의 요청/결과 v1 계약 분리. OpenCV·C++·C#·실장비·AI 분석은 연결하지 않음. 새 서버·DB·의존성 없음.
- `codex/vision-ai`, 기준 `0f16bb6`에 후속 구현. 프런트 425 tests / 47 files 통과, typecheck/lint/format/build 통과. 모의 API·5186에서 신규 Chromium 진입/조건 변경/JSON 다운로드/모바일 가로 넘침 검사 통과. 공용 DB 스모크·실장비·Safari 미검증.
- 상세 설계·후속 연결 계약·재현 명령: `docs/agent/합성이미지검사실_FS-VISION-LAB01.md`. 이번 합성 범위 완료. 다음은 통합 검토와 사용자 체험이며 C++/C# 엔진은 별도 후속 범위. 원격 push·운영 배포 없음.
- 통합·배포(2026-09-27, Claude Code): main에 FS-023b + UI-03 B2(`d194cb9`) + Codex 비전검사 AI 설명(`0f16bb6`)·합성 이미지 검사실(`da2f02a`) 병합(`2ef0578`). 검증: ruff·격리 R1~R6 0, vitest 435, 백엔드 설명 테스트 13, 공식 스모크 **187 passed**(11.8분). push `8851772..2ef0578`, 서버 pull·`alembic upgrade head`(→ `fs023b_qms_module`)·API 재시작, 프런트 빌드·rsync(번들 `index-aVsvqfGf.js` 일치). 운영 게스트 확인: QMS Q-01~06·MES 패킹·E-02 견적 패널·`/factory/vision-lab` 열림, 페이지 오류 0·5xx 0. OPENAI_API_KEY 미설정 → AI 설명은 데모 응답.


## 2026-09-27 P-02 홈 UI 정돈 (Codex)

- 작업 폴더 `factory-studio-codex`만 사용. 브랜치 `codex/home-ui-polish`, 기준/마지막 이전 커밋 `8851772`(origin/main). 이 인계는 `P-02: Figma 참고 홈 UI 정돈` 커밋에 포함하며 최종 해시는 `git log -1`로 확인한다. 기존 `codex/factory-building`은 그대로 보존.
- 끝난 것: 흰색 홈 헤더·로고, 중앙 본문/배너, 기본 아이콘·이름·분류만 노출, 설명/상태 호버·포커스·터치 안내, 미구현 영역 제거. 현재 공간·도움말·실제 진입·역할 메뉴 유지. 보고서 `docs/agent/홈_UI_정돈.md`.
- 검증: Node 24.21.0 PATH. typecheck/lint/format:check/build/test(418개/45파일) 및 독립 Chromium 8개, diff --check 각각 exit 0. 데스크톱/호버/360px 직접 확인. backend·DB·공용 포털 스모크 미실행.
- 재현: 전용 폴더에서 `export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin"`, `npm --prefix frontend run test:home-browser`. 5187 포트·모의 API만 사용, 테스트 서버 자동 종료. 공용 8000/5173과 DB는 사용하지 않는다.
- 새 의존성 없음. package.json은 검증 스크립트만 추가. 공통 CSS·업무/3D·스키마 변경 없음. .env/work/node_modules 제외.
- 다음: 사용자 시각 검토 후 통합 담당자가 main에 반영·운영 확인. Codex는 push/main 병합/배포 없이 멈춘다.


## 2026-09-27 연속 검사 모드 (FS-VISION-RUN01 완료)

- 사용자 확인한 연속 검사 범위 구현. `codex/vision-ai`, 기준 `da2f02a`. 기존 3종 20회 반복, 500/200ms, 시작/일시정지/재개/종료, 시작 시 레시피 고정.
- OK/NG/합격률/평균 알고리즘 시간, 샘플별 NG, 누적 오검출·미검출·ROI 밖 픽셀. NG 당시 원본/이진화·좌표·면적 조건 재조회, 실행 기록 JSON 다운로드.
- 비동기 어댑터 경계와 세대별 늦은 응답 폐기, 화면 이탈 정리. 설정 이동/탭 숨김 일시정지. 한 배치 20건 메모리 보관, 새 배치·화면 이탈 시 교체/소멸.
- Node 24: typecheck/lint/format/build 통과, Vitest 431 tests / 48 files. Chromium 기존 합성 검사실 1개 + 신규 배치·JSON/라이프사이클 2개 통과(최종 신규 2개 재실행 통과). 1440·390 캡처 직접 확인, 360·390 가로 넘침 없음.
- 실장비·PLC·C++/C#·backend/DB 스모크·Safari 미검증. 기존 3D 청크·Clock 경고 유지. push/운영 배포 없음.
- 다음: 사용자 체험·통합 검토, 이후 별도 작업으로 가상 PLC 상태 머신. 설계 `docs/modules/factory/README.md`, 상세 계약·재현 `docs/agent/연속검사모드_FS-VISION-RUN01.md`.


## 2026-09-27 가상 PLC 핸드셰이크 (FS-VISION-PLC01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `74a4ec2`. 연속 검사에 선택형 PLC 모드 추가, Ready/Trigger/Busy/Done/OK·NG/Interlock 신호, 요청 ID별 이벤트 로그.
- 300ms 검사 제한·1000ms 확인 제한, 1회 지연/확인 누락 주입, 수동 확인, 중복 트리거 차단, 결과 래치, 명시적 리셋·새 배치 복구. 타임아웃/취소 후 늦은 응답 무효화.
- PLC 수량은 확인까지 끝난 거래만 반영. 확인 실패 결과는 PLC 진단 스냅샷에 보존하고 NG 수량과 분리. 0건 실패 배치도 신호/알람/로그 JSON 다운로드 가능.
- Node 24 최종 typecheck(빌드 포함)/lint/format/build 통과. Vitest **443 tests / 49 files**. Chromium 관련 5개 통과, 로그 ID·알람 표시 보정 후 신규 PLC 2개 재실행 통과. 1440·390 캡처 직접 확인, 모바일 가로 넘침 없음.
- 브라우저 모의 프로토콜. Ready_Req ON 고정, Recipe_ID=RUN_SNAPSHOT. 실제 PLC·통신 SDK·C++/C#·MES·backend/DB 스모크·Safari 미검증. 기존 3D 청크/Clock 경고 유지. push·운영 배포 없음.
- 다음: 사용자 체험/통합 검토 후 C++ OpenCV 코어 분리 및 동일 입력의 결과 비교. 상세 `docs/agent/가상PLC_FS-VISION-PLC01.md`, 공통 설계 `docs/modules/factory/README.md`.


## 2026-09-27 C++ OpenCV 검사 코어 (FS-VISION-CORE01 완료)

- 사용자 후속 진행 승인. `codex/vision-ai`, 기준 `7ec4519`. `native/inspection_core`에 C++17 정적 라이브러리·CLI·CMake·예제·비교 테스트 구현.
- 기존 요청 v1과 검사실 {request,result} JSON 입력, stdin/파일/NDJSON 지원. 결과 source=synthetic-opencv-cpp-v1. 임계값 `<`, 연결 4/SAUF, 픽셀 면적 `>=`, ROI·영역 순서·정답 평가를 웹과 일치시킴.
- CTest 2개 프로그램 통과(8.72초). 원본 TS 엔진 직접 실행과 19,968개 입력 비교: 불일치 0. C++ 핵심 사례, 입력 타입·범위·JSON 오류, NDJSON 오류 후 복구, 파일 입력 검증 통과. 예제 이물 결과 80/36px²·NG 확인.
- 검증 환경: macOS arm64, Apple Clang 21, CMake 4.4.3(Homebrew로 이번 설치), Node24, OpenCV4.13.0·nlohmann-json3.12.0 소스 빌드. 제3자 소스/빌드/로그는 work/에만 보관. CMake4와 OpenCV 내부 정책 경고는 남으나 최종 빌드·테스트 성공.
- 웹/서버/PLC 패널은 기존 브라우저 엔진 유지. 실행 연결·실영상·C#·Windows/Linux·실장비·배포 미검증/미구현. 프런트 코드를 바꾸지 않아 기존 443개 테스트/브라우저 스모크는 이번에 재실행하지 않음. push·운영 배포 없음.
- 다음: 사용자 체험 후 C# 프로세스/통신 어댑터 또는 웹 서버의 네이티브 호출 연결 범위 확정. 요청 ID·취소·시간 제한·출력 검증 계약 필요.
- 재현: `cmake -S native/inspection_core -B work/inspection-core -DINSPECTION_FETCH_DEPS=ON -DCMAKE_BUILD_TYPE=Release -DNODE_EXECUTABLE=/opt/homebrew/opt/node@24/bin/node`; `cmake --build work/inspection-core --parallel 4`; `ctest --test-dir work/inspection-core --output-on-failure`.
- 상세: `native/inspection_core/README.md`, `docs/agent/C++검사코어_FS-VISION-CORE01.md`.


## 2026-09-27 C++ 웹 호출·사용자 참고 문서 (FS-VISION-CONNECT01 완료)

- 사용자 요청한 C++ 호출 연결과 도움말 반영 완료. `codex/vision-ai`, 기준 `848778b`. 운영 배포는 사용자가 직접 진행하며 이번에 push·main 통합·운영 접속/재시작/배포 없음.
- 인증/CSRF POST /api/v1/factory/vision/inspect, 서버 고정 절대경로 VISION_CORE_EXECUTABLE 실행. 2초·동시4개/프로세스·출력1MiB 제한, 요청/결과 모델 검증, 오류503/429/502/504, 브라우저 대체 없음. C++ --timed 추가(기본 CLI 출력 유지).
- 검사실 C++ 단건/JSON, 연속 검사 엔진 선택, PLC 선택 엔진 호출·취소. 엔진 출처·고정 레시피·요청 ID 연결, 순수 C++ 시간 표시. 클라이언트 취소/늦은 응답 폐기.
- 도움말 사용자 참고 문서/포털에 `portal/vision-lab` 추가, 전체 사용 흐름·설정·20회 배치·PLC 장애/복구·JSON·한계 집필. 검사실 왕복 링크·검색·모바일 확인.
- 최종 검증: 프런트 448 tests/50 files, 타입(빌드)/lint/format/build 통과. DB 없는 서버 27 tests(실제 C++·인증/CSRF·검증·미설정·출력오류/상한·시간제한·동시제한·취소) 통과, Ruff check/format 통과. CTest2개 통과, 웹 비교19,968개 불일치0.
- Chromium 관련6개 최종 단일 실행 통과(1.3분). 모의 인증·실제 API·실제 C++ 바이너리로 단건/20회/PLC20회 및 JSON·도움말 확인. 기존 모의 API 회귀 포함. 실제 화면 캡처 확인, 도움말390px 가로 넘침 없음.
- 공용 DB/운영인증/운영배포·Windows/Linux·실장비 미검증. 기존 3D 청크/Clock 경고와 Python 테스트 클라이언트 사용중단 경고 유지.
- 배포 인계: `docs/agent/C++웹연결_FS-VISION-CONNECT01.md`. 서버 OS에서 바이너리 빌드/검증 → 서비스 환경 VISION_CORE_EXECUTABLE 절대경로 설정 → 백엔드 반영·재시작 → 프런트 재빌드·반영 → 게스트C++/PLC/도움말 확인. tests/factory_native_preview.py는 모의 인증이므로 운영 사용 금지.


## 2026-09-29 Codex FS-026b1 진행 중 (main 내용 유지 후 추가)

- 작업 위치 factory-studio-codex, 브랜치 codex/vision-ai. origin/main `6508599`로 rebase 완료. 이전 HEAD `521ad76`은 `backup/vision-ai-before-fs026b1-20260929` 보존. rebase 직후 HEAD `df6014e`. main의 BEMS 시드 템플릿 11,910 / 복사 11,908행 유지.
- FS-026a 완료: migration head `fs026a_wms_receiving_reservation`, metadata v0.13.0 /98테이블·1022컬럼·225 FK. 기존 migration 변경 없음. 이전 상세 보고 docs/agent/WMS확장_DB_FS-026a.md.
- 현재 b1: receiving.py/receiving_schema.py, 입고 예정/도착/검수/원천 선점 API와 기존 sync 연계, NORMAL/QUARANTINE 마스터 보호, snapshot 날짜만 복사·digest 불변 구현 중. 입력400/멱등422, 신규 처리 시각 DB clock_timestamp 통일.
- 아직 검증 완료 아님. 신규 테스트 실패 수정 중이며 전체 pytest/ruff/격리 감사는 최종 실행 필요. 완료 후 보고를 갱신한다. 실행: 전용 *_test DB에 DATABASE_URL/TEST_DATABASE_URL 설정 후 `backend/.venv/bin/pytest backend/tests --tb=short -q`, `uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py`, `python3 tools/audit_schema_isolation.py`. 비밀값은 저장/출력하지 않는다.
- 사용자 지정 단계: b1(TX-W4~7/AC140~150) 보고 후 사용자 확인 대기. b2 예약·소진·가용(TX-W8~9/AC151~158)은 아직 시작 금지. 이후 화면/트럭/시드·도움말도 별도. push·배포 미승인.

### FS-026b1 검증 중간 갱신
- 입고 API23개 통과(별도 PG 연결 경합, 전량 부족, 취소/원천변경, 환산/복사/격리, 멱등, 줄 순서 오류 경로, 초안 삭제 뒤 발번 포함). 전량 부족 sync 영수증은 전표가 없으므로 inbound_notice ID로 저장한다.
- 기존 W-03 새 상태 및 검수 전표 이름의 최소 표시 호환 추가. WMS 프런트10개·typecheck·변경 ESLint 통과. 입고 전용 화면은 미구현.
- 전체 백엔드 pytest 재실행 중. ruff check/format134파일 통과, R1~R6 감사 오류0, db:validate 오류0. 최종 전체 결과 전에는 완료로 인계하지 않는다.


## 2026-09-29 FS-026b1 최종 완료 — 다음은 사용자 확인 후 b2

- 위 중간 WIP 상태를 이 항목으로 대체한다. 브랜치 codex/vision-ai, 기준 main6508599, 마지막 구현 a832fa8(16045ae 포함), 마지막 보고커밋은 git log -1. main 본문은 보존했다.
- 입고 예정·도착·검수·원천선점/해제/사후대사와 기존 ERP sync 단일 경로 완료. 400 필드오류/422 멱등, 날짜 제외 digest, 복사 confirmedAt 날짜만 이동·digest 불변, 신규 서버 시각 통일. 기존 W-03 새 상태/NULL 전표 호환 포함.
- 최종 검증: **backend 전체755 passed, 2 warnings, 1204.94초**; 신규 입고23 포함. tools58+subtests13, WMS 프런트10, typecheck·변경 ESLint, CI ruff check/format134파일, R1~R6 감사0, db:validate0. 자동 탐색 ruff의 기존18 I001 파일은 main과 동일하며 CI 명령은 통과했다.
- 전용 factory_studio_codex_fs026b1_final_test DB에서 실행. head fs026a_wms_receiving_reservation 유지. 공유 개발/운영DB·migration·schema/Excel/ERD·BEMS 시드11,910 기준 변경 없음. .env/work 스테이징 없음. push·배포 없음.
- b2 예약·소진·가용 조회(TX-W8~W9/AC151~158)는 **사용자 b1 확인 전 시작하지 않는다**. AC141의 예약가능95 조회도 b2에 남는다. 이후 입고 화면/3D 트럭/시드·도움말·브라우저 검증. 신규 입고 화면은 아직 없으며 프로젝트 전체 완료가 아니다.
- 상세 및 재현 명령: docs/agent/WMS확장_API_FS-026b1.md. 테스트에 필요한 전용 *_test DB 환경만 주입하면 표준 pytest 명령으로 재현되며 work 임시 도구에 의존하지 않는다.


## 2026-09-30 FS-026b2 WIP — 예약·소진·가용

- 사용자가 다음 진행 방향 1번(b2)을 승인했다. 브랜치 codex/vision-ai, 기준 3f5039c/main6508599. TX-W8~W9, AC151~158 구현. 예약 생성/해제, ERP 확정 출하 전량 소진, 원장·예약 경합 직렬화, 격리 제외/위치별 부족 보존, ERP off 가용 계산.
- ERP 조회는 interface.py만 사용. 신규 처리 시각 clock_timestamp, FS_TODAY 미사용. 게스트 예약 번호 날짜 이동/FK 재매핑. 기존 W-01/02 가용 표시 호환만 반영; W-08/09 미구현.
- 현재 관련 API60개(신규22 포함), WMS 프런트10개/typecheck/변경 ESLint 통과. CI ruff138파일, R1~R6 감사0, db:validate0. 전체 pytest 전용 factory_studio_codex_fs026b2_final_test에서 실행 중. 최종 결과 전 완료 아님.
- migration/schema/Excel/ERD 변경 없음. 템플릿11,910 유지. .env/work 스테이징 금지, push·배포 없음. b2 최종 보고 후 사용자 확인을 기다린다.
- 재현: 전용 *_test DB의 DATABASE_URL/TEST_DATABASE_URL을 환경으로 제공한 뒤 backend/.venv/bin/pytest backend/tests -q --tb=short. Ruff는 backend/pyproject.toml 명시(CI 명령). 상세 docs/agent/WMS확장_API_FS-026b2.md.


## 2026-09-30 FS-026b2 완료 — 다음은 사용자 확인 후 화면

- 위 b2 WIP 상태를 이 항목으로 대체한다. 사용자 후속 1번 승인에 따라 TX-W8~W9/AC151~158 완료. 브랜치 codex/vision-ai, 기준 main6508599/3f5039c, 구현 0d639b7. 최종 보고 커밋은 git log -1.
- 예약 생성·해제·ERP 확정 출하 전량 소진, 동일 원천 단일 전표, sync 경합, 정상 현재고−활성 예약, 격리 제외, 위치별 부족 보존, ERP off 가용 계산. AC141 예약가능95 조회도 검증 완료.
- 입력400/멱등422, clock_timestamp 처리 시각 통일, FS_TODAY 미사용. ERP interface 조회만 사용, 게스트 예약 날짜/FK 복사. 기존 W-01/02 화면·도움말 새 계산식 호환. 신규 W-08/09 화면은 아직 없음.
- 최종 검증: **backend 전체777 passed, 2 warnings, 1414.37초**(신규22 포함). 관련 WMS60, 프런트 전체490/56파일, 도구58+subtests13, typecheck/build/변경 ESLint 통과. CI ruff check/format138파일, R1~R6 감사98테이블/225FK 오류0, db:validate 오류0. 기존 사용중단 경고2와 프런트 청크 경고 유지.
- 전용 factory_studio_codex_fs026b2_final_test에서 실행. migration head fs026a_wms_receiving_reservation 유지; schema/Excel/ERD·시드 기준11,910/복사11,908 및 seed/validate.py·test_seed/test_common 변경 없음. 공유 개발/운영DB 변경·push·배포 없음, .env/work 스테이징 없음.
- 다음: **사용자 b2 확인 후** W-08 입고 예정/도착/검수와 W-09 예약 화면 및 브라우저 흐름 검증. 이후 3D 트럭 도착·체험 시드·종합 사용자 도움말·통합 점검. 신규 화면/브라우저/운영 검증은 이번에 하지 않았다.
- 상세 API/AC 근거 및 비밀값 없는 표준 재현 명령: docs/agent/WMS확장_API_FS-026b2.md. 전용 *_test DB 환경을 주입하고 pytest backend/tests 실행, Ruff는 backend/pyproject.toml 명시. main HANDOFF 본문은 보존했다.


## 2026-09-30 FS-026 후속 UI·트럭·시드·도움말 통합 WIP

- 사용자 b2 후속 전체 승인: 화면 → 3D 트럭 → 시드/도움말 → 통합 검증까지 중간 확인 대기 없이 진행. push·배포는 제외. 기준 9c66cf1, codex/vision-ai.
- W-08/09, 읽기 전용 출하 대조 미리보기·날짜/예약부족 필터, 기존 W-01~07 연결, 3D 도착 API, 정상/격리 위치, 포털 사용자 흐름 문서 구현 중.
- 새 템플릿 sv-20260930-1: WMS22행 추가, 총11,932/복사11,930. BEMS4,218행 그대로. 기존5품목, R-Q01/F-Q01, 예정/도착/95·3·2 검수/전량부족/취소, 활성/해제/소진 예약. 소진 시드는 기존 역사 출고 전표를 새 템플릿의 소진 예약 이력으로 연결하며 추가 차감하지 않는다. PI-0004/SH-0004 미반영 유지. 운영 기존 템플릿은 수정하지 않는다.
- 관련 backend76개 통과(새 preview/filter 테스트 추가 검증 중). 실 API 브라우저 트럭도착→원장0→검수95/3/2 및 새로고침 통과. 다른 브라우저 시나리오/전체 회귀는 진행 중이며 완료 아님.
- 로컬 전용 fs026_ui_test / fs026_browser_test 사용. 브라우저용 API localhost8000은 현재 실행 중(합성 시크릿, 로컬 쿠키). 테스트 종료 후 중지 예정. .env/work 스테이징 금지.
- 다음: 브라우저 실패 수정·모바일/3D 캡처 확인, 전체 pytest/프런트·ruff·격리 감사·도움말 링크·문서 갱신. 최종 커밋/인계 후 종료.

### 2026-09-30 FS-026 후속 최종 검증 중간 갱신

- W-08/09 저장 응답의 최신 version을 즉시 상세에 반영해 연속 조작 경합을 보완했다. 3D 외관·트럭 패널, W-01 수량 표시도 최종 정리.
- 실제 API Chromium 통합10개 전부 통과(1.2분). 프런트 전체491개(57파일, maxWorkers=2), 전체 ESLint/Prettier/typecheck/build 통과. Ruff139파일, R1~R6 오류0, DB 검증 오류0.
- 전체 백엔드는 깨끗한 별도 DB에서 실행 중이다. 최종 완료 항목 전까지 완료로 판단하지 않는다. 보고: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.

## 2026-09-30 FS-026 후속 통합 완료 — 입고·예약 화면 / 트럭 / 시드·도움말

- 앞선 후속 WIP 상태를 대체한다. 사용자의 후속 전체 승인 범위 완료. `codex/vision-ai`, main6508599 기준 유지, 구현 `cd41b04`, 연속 조작 보완 `0ad25ee`. 마지막 문서 커밋은 `git log -1`.
- W-08 입고 예정·도착·검수·원천 연결, W-09 예약·출하 대조·소진, 기존 W-01~07 정상/격리/예약/가용 표시·동선 확장. 저장 응답의 최신 version을 즉시 반영하여 빠른 다음 조작의 이전 버전 사용을 방지한다.
- 3D 트럭은 서버 도착 상태만 변경한다. 검수 때만 재고 증가, 예약 때 원장 불변, 소진 시 기존 출하 원천과 중복 차감 방지. 통신 실패/재시도/응답 유실 복구/미저장 보호 포함. CNC 수량·GPS/실차·실장비 연결 제외.
- 시드 sv-20260930-1: 템플릿11,932 / 게스트11,930, 기존 품목·BEMS4,218 유지. WMS22행 추가. 새 migration 없음(head fs026a_wms_receiving_reservation), metadata98테이블/1022컬럼/225FK 유지. 기존 템플릿·운영 DB 수정 없음.
- 최종 검증: 전체 backend **779 passed**(23분39초, 기존 경고2), frontend **491 passed /57파일**(maxWorkers=2), 실제 API Chromium **10 passed**(1.2분). 전체 typecheck/lint/format/build 통과, Ruff139파일 통과, R1~R6 격리 감사0·db:validate0, tools58+subtests13 통과. 기본 병렬 프런트 실행의 기존 ERP 테스트 일시 실패·재검증 및 경고는 통합 보고에 기록.
- 도움말 W-08/09, 기존 W-01~07, 사용자 참고 `/help/portal/wms-flow` 반영. 360px와 트럭 외관 캡처 확인. 보고·재현·AC 증거: `docs/agent/WMS확장_화면트럭통합_FS-026.md`.
- 검증용 API/Vite 종료. `.env`·work 스테이징 없음. **push·운영 배포 없음. 이번 승인 범위 남은 개발 없음.** 다음은 사용자의 통합/운영 반영: 백엔드·프런트를 함께 적용하고 새 템플릿 생성·검증 후 새 게스트에서 체험한다. 기존 기록을 소급 변경하지 않는다.

## 2026-10-01 FS-030 GW 결정서 — 승인 대기

- 사용자 GW 별도 담당 지시에 따라 fetch 후 최신 origin/main7a2d70f(67540be 후속)에서 `codex/fs-030-gw` 생성. 작업 폴더 factory-studio-codex만 사용, vision-ai에서 이어 개발하지 않음.
- `docs/plan/GW도입_전자결재_결정_FS-030.md` 작성. D60~D69, AC220~239 범위 유지. 합성 담당자/실제 인증 주체 구분, 순차 결재·회수·재상신 불변 이력, 원문 변경·off·최신 회차 배지, 글 포함/댓글·첨부 제외 해석을 승인안으로 보완.
- 권장: ERP 매입 전표 한 종류+일반 기안, E-11 읽기 전용 배지 포함. ERP 교차 쓰기/확정 통제 없음. 결정은 아직 승인되지 않음.
- 킷의 공용 개발 DB 적용 지시는 이번 전용 DB 지시로 제외. 적용 migration 불변과 병합 head 변경 충돌은 DB 착수 전 재확인 및 새 연결 방식 조율로 기록. 현재 head fs026a_wms_receiving_reservation, metadata v0.14.0/103테이블 유지.
- 검증: 문서 상대 링크5개·D번호10개·AC20개·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 제품 코드/스키마 변경이 없어 pytest·프런트·브라우저·migration·시드·격리 감사는 미실행. DB 접속/공용 서버 실행 없음.
- 다음: **사용자 결정서 승인 후** GW 모듈/README·G-01~07 화면 설계. 전체 설계 승인 전 schema.json·migration·제품 코드 작성 금지. 이후 a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1로 확인.

## 2026-10-01 FS-030 GW 전체 설계 작성 — 승인 대기

- 사용자 “진행해줘”를 결정서 권장안 4항목 승인으로 기록(D60~69). 브랜치 codex/fs-030-gw, main7a2d70f/선행 결정커밋 b873543.
- 새 문서: docs/modules/gw/GW_모듈설계_FS-030.md, 같은 폴더 README.md(현재 기준/조회 계약), docs/ui/화면설계_GW_FS-030.md. 결정서·로드맵·현황 갱신.
- gw8테이블, G01~07+E11 읽기 배지, TX-G1~6/API/권한/잠금/오류/불변 이력·재상신·원문 digest/복사·시드69행(+모듈행1 별도) 설계. AC220~239 연결. source digest는 ERP 소유 정규화 함수로 일원화; 제공 interface 사이 재귀 호출 금지.
- 검사: 문서4개 상대 링크17개·테이블8·화면7·AC20·시드합69·현황173/200줄 정적 검사 통과(exit0), git diff --check 통과(exit0). 최초 임시 검사 정규식이 interface 함수까지 테이블로 세어 실패했으며 식별자 패턴 보정 후 통과. 제품 검증 결과가 아님.
- 미실행: pytest·vitest·브라우저·DB migration·시드 생성·격리 감사. 문서만 작성했고 제품 코드/schema.json/Excel/ERD/migration 변경 및 DB 접속 없음.
- 다음: **사용자 모듈·화면 전체 설계 확인 후 FS-030a DB**. a 착수 전 최신 main/head/공통 파일·SPC/CMMS 시드 합계 재확인. 적용 migration 수정 금지, Codex 전용 DB/포트만 사용. a/b/c 각각 보고 후 대기. push·배포·main 병합 없음. 최종 문서 커밋은 git log -1.

## 2026-10-01 FS-030a DB WIP

- 사용자 “구현 진행해줘”로 모듈·화면 전체 설계 승인. origin/main6350697(FS-040 포함) 위 rebase 완료, codex/fs-030-gw. GW 8테이블·스키마 목록·복사·모듈 기본행 및 Excel/ERD 구현. head fs030b_gw_module, down fs040_app_review.
- 전용 factory_studio_codex_fs030_test: DB 제약·시드·공통 회귀45 passed, 도구69 passed, 실제 DDL 대조/설계 검증/격리 감사 오류0. 전체 backend/UI/browser 미실행. downgrade 왕복·기존 공간 backfill 검증과 최종 문서 정리 남음.
- FS-030b API/화면은 아직 시작하지 않음. a 최종 보고 후 사용자 확인 대기. push·배포·main 병합 없음. .env/work 스테이징 금지. 상세 표준 재현 명령은 최종 a 보고에 남긴다.

## 2026-10-01 FS-030a DB 완료 — 다음은 사용자 확인 후 b

- 앞선 GW WIP/승인대기 상태를 대체한다. 전체 설계 “구현 진행해줘” 승인. main6350697에 rebase한 codex/fs-030-gw, 구현15f9398·최종커밋 git log -1.
- 신규8테이블·복사/초기화·모듈행/평가모듈CHECK, schema/Excel/ERD 일치. 임시0.15.0-gw,112테이블·1,225컬럼·258FK, headfs030b_gw_module(fs040 뒤). 템플릿11,934/복사11,932. 적용 기존migration 변경 없음.
- 전용DB pytest45/도구69 통과, Ruff154파일·격리/DDL/정적 오류0, 빈DB 왕복·기존공간GW true/ERP false·유데이터 downgrade 거부/전체롤백 통과. Excel39시트/GW4미리보기 확인. 전체backend/UI/browser 미실행.
- 상세 변경파일·검증/미실행·재현은 docs/agent/GW_DB_FS-030a.md. SERVICE 정책/권한/결재 로직은 아직 b 미구현이며 DB 제약과 구분한다.
- b 사용자 확인 후 API·G01~07·ERP조회계약/E11배지·런처/평가 gw 허용·전환/문서/e2e. c69업무행/도움말/흐름맵/전체검증. push·배포·main 병합 없음. Codex전용DB만 적용, 공유DB/8000/5173 서버 사용 없음. .env/work 스테이징 없음.

## 2026-10-03 FS-030b API·화면 WIP

- 사용자 “이어서 진행해줘”로 b 승인. main8531c05까지 fast-forward(GW a 병합·SPC 시드·CMMS DB/운영 기록 유지), branch codex/fs-030-gw. 스키마 v0.17.0/headfs029b_cmms_module 그대로.
- GW 서비스/읽기 interface/ERP 조회계약, G01~07·ERP 배지·런처 연결 구현 중. 순차 결재·반려/재상신·회수·게시정정·역할 검사·멱등·스냅샷 불변. ERP 코드 조회만, 교차쓰기 없음.
- 첫 관련 API11개 통과 후 경합/ERP 배지/원문변경 등을 확장 검사 중. typecheck 통과. 전체pytest·frontend·실제브라우저는 아직 완료 아님. 전용 factory_studio_codex_fs030b_test만 사용.
- 다음: 추가 회귀·브라우저 검증/오류 보정·문서/최종보고. c업무69행/도움말은 사용자 b 확인 뒤. push·배포 없음. .env/work 스테이징 금지.
