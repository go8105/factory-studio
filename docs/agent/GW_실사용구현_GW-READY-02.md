# GW 실사용 보안·운영 구현 · GW-READY-02

2026-10-18 사용자 전체 설계 승인. **한 구현 ID의 A~E 진행 중이며 완료 보고가 아니다.** 내부 묶음마다 재승인하지 않는다. 로컬 main만 반영하는 기존 범위를 유지하며 원격/운영 배포는 하지 않는다.

2026-10-20 23차: 백업·복원 원본 서명 증거 쌍의 읽기 전용 수집기를 추가했다. 같은 현재 기준과 manifest·시각을 대조해도 PARTIAL이며 최종 인수 증거/운영 승인으로 사용하지 않는다. [실행 절차와 기존 GW UI 보완 항목](../operations/GW_실회사_인수절차_10인_GW-READY-02.md)을 따른다.

## 현재 구현과 검증

- A: 암호화 TOTP·중간 challenge·DB 실패 횟수·동일 번호 재사용 차단·키 문맥/교체·security_version·8시간 절대 만료. 앱 등록/확인·실제 로그인202→번호확인201·추가 본인 확인·복구 코드 재발급·다른 세션 종료 API/화면을 구현했다. 비밀번호 변경은 세션 버전도 올린다. COMPANY의 키/HTTPS origin/Secure 쿠키 누락은 거부하며 회사 업무는 MFA 세션을 요구한다.
- B 일부: 비밀번호+일회용 복구 코드→기존 앱/세션/코드 회수→업무 차단된 제한 세션→새 앱·코드→재로그인. 사전 긴급 문서+서버 운영자 승인+본인 비밀번호로 현재 GW 보안 관리자의 제한 재등록 경로를 추가했다. 긴급 복구 Chrome 최종 흐름도 확인했다. OIDC 선택 연결과 실환경 인수는 남아 있다.
- C 일부: 운영 정책 입력 계약·서명된 증거 검증 커널·회사 정책 새 버전/CAS/역할/최근 인증 API·운영 준비/기준 화면. 서명 증거 등록/조회 API·화면을 연결했다. 보관 검토·회사 보존 중지/개별 보류·이력/원문 ACL도 연결했다. 실제 실행 도구와 운영 전환은 남아 있다. 현재 ready=false이며 백업/복원·실환경 미완료를 표시한다.
- D 일부: 서버용 암호화 DB 백업/자체검사·현재성 검사·별도 암호화 권한 대조·새 DB 격리 복원/지문·FK·세션 회수/확인된 제한 재적용을 구현했다.30분 스케줄은 설치하지 않은 템플릿이다. 독립 회수 기록 자동 연속성·완전성,외부 저장소·실환경 인수는 미완료라 복원 증거는PARTIAL이고 전체 회수 확인=false다.
- E 진행: 상단 내 계정 보안, 로그인 본인 확인/복구, 회사 운영 안내→운영 준비와 정적 도움말을 연결했다. 전체 통합/10인 인수·최종 main 반영은 남아 있다.

격리 PostgreSQL18.6 신규 migration 적용·219표2409컬럼543FK 카탈로그 대조 오류0. 현재/목표 metadata·Excel2종·ERD를 갱신했다. 업무 데이터/인증 상태를 migration으로 임의 변경하지 않았다. 이력이 있으면 downgrade를 거부한다.

초기 보안/트랜잭션/HTTP/정책·서명 커널29건 통과. 동일 OTP/복구 코드 경합·실패 commit·제한 세션 업무 거부·만료/보안버전·재발급/다른 세션 회수 포함. 관련 인증/포털/HR 사용자/운영 정책39건 통과, 마지막 보안 집중30건 통과(서로 겹치는 검사). COMPANY HTTP·위조 Forwarded 헤더 거부도 포함했다. 첫 넓은 회귀에서 새 정책 부모에 created_at이 없는데 합성 시드 생성기가 그 열을 가정한 문제를 발견, 기존 시드 검사기처럼 부모 열이 있을 때만 시각 보정하도록 수정 후 관련39건 재검사에 통과했다.

Chrome 실제 제품에서 합성 계정의 등록→앱 로그인→코드 복구→재등록→도움말, 390px 가로 넘침0·페이지오류0 확인. 실제 휴대폰/IdP/실회사 검증이 아니다. 추가된 운영 화면도 실제 제품에서 정책1번째 버전 저장·계속 편집 포커스 복원·390px를 재검사했다. 코드 재발급/다른 세션 UI의 최종 브라우저 조작은 후속이며 해당 API는 경합/버전 검사로 확인했다. 초기 프런트 전체610통과/기존Flow7실패(617). 이후 전체 검사에서 운영 도움말 고아1건을 발견해 문서 트리에 연결했고 최종 전체614통과/기존Flow7실패(621)로 확인했다. 최신 집중28건은 문서 트리·보안·운영 입력·공통 패널·설치 PWA 로그인 이동을 포함해 통과했다. 타입/린트/포맷/빌드 통과(기존chunk 경고). 후속 변경 후 필요한 집중 검사를 반복한다. 전체CI성공이 아니다.

## 도움말

- [내 계정 보안·인증/분실 복구](../../content/help/portal/account-security.md)
- [회사 운영 준비·기준](../../content/help/gw/operations.md)
- [회사 시작·직원 권한](../../content/help/gw/company.md)

구현하지 않은 기능은 도움말에서 후속으로 명시한다. 코드·비밀번호·실제 개인정보·암호화 키를 도움말/Git에 넣지 않는다. 보안 키는 환경 비밀, 제품은 업무 본문/인증 비밀을 브라우저 영구 저장소에 저장하지 않는다.

## 다음과 환경

branch codex/gw-company-01 / 기준main2be292e. 실제 계정·공유DB·다른checkout·브라우저확장 변경 없음. 검증에는 소유 격리PG 컨테이너 fs-gw-ready02-test, loopback55438을 사용했다. 검토API8362/웹5362는 종료했고 소유PG의 ID/label 대조 후 컨테이너·익명볼륨을 삭제했다. 환경 비밀은 work만 사용했고 임시 JSON/env와 컨테이너 ID 파일을 제거했다. 최종 결과 전 실제 COMPANY 준비 완료/main 반영을 선언하지 않는다. [개발 환경과 운영 경계](../operations/GW_보안설정_개발검증_GW-READY-02.md)를 참고한다. WIP53b54c5 이후 검증 보강, 최종 커밋은 git log를 따른다.

재현: Python3.14/uv, Node24. 새 *_test PostgreSQL18 DB에 alembic upgrade head 후 TEST_DATABASE_URL 설정. `uv run --project backend pytest backend/tests/test_gw_security_crypto.py backend/tests/test_gw_security_transactions.py backend/tests/test_gw_security_http.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_operations.py -q`. 브라우저 재현은 frontend/e2e/gw-security-browser.mjs(합성 계정 JSON 경로·로컬 origin을 환경으로 제공; 비밀을 문서에 쓰지 않음). DB 정적검사/Excel/ERD는 저장소 표준 도구를 사용한다.


## 다음 구현 우선순위

1. P0: 직원 연결·역할의 암호화 의도 기록/체인 검사를 바탕으로 연결한 GW/공통 인증/HR 경로의 누락 감사·미확인 의도 최종 판정/제한 해제·보관 교체/독립 지문 전달, 외부 최신 지문/보관·실환경 복구 인수. 현재 CLI checkpoint는 명시 실행이며 부분 복원 결과를 완료로 올리지 않는다.
2. P0: 현재 정책/제품/DB·백업 나이·복원/회수/인수 증거의 서버 준비 판정과 운영 전환 게이트. 실제 조건 없이 ready나ACTIVE를 허용하지 않는다.
3. P1: 선택형 OIDC subject 명시 연결·공급자 장애/nonce/state/PKCE 검증, 모의 공급자와 실제 공급자를 구분. 기본 로컬 MFA는 유지한다.
4. P0 출시 전: 전체 공통 인증/회사 업무 회귀·10인 HTTP·코드 재발급/다른 세션 UI·실휴대폰/실환경 인수·문서 최종 대조와 로컬 main 반영. 실제 기기/사업 환경 미확인을 합성 검사로 대체하지 않는다.

위 항목은 이미 승인한 GW-READY-02 범위의 남은 구현이며 새 승인 질문을 요구하지 않는다. 다음 ID나 별도 시스템 고도화로 넘어가지 않는다.


## 2차 구현 결과와 남은 경계 (2026-10-18)

사전 본인 긴급 문서(365일·원문1회)→OS UID를 기록하는 서버 승인 CLI(0600·대상 회사/계정 대조·15분)→비밀번호 LOGIN_MFA+CSRF→현재 GW 보안 역할 재검사→제한 재등록을 구현했다. 정상 로그인20/10분·등록/긴급 문서 각각3/10분, COMPANY 회사/HR 관리 최근 MFA5분을 적용했다. 시각 혼용으로 즉시 추가 확인이 실패하는 문제를 발견해 DB 시계로 통일했다. 서버 승인 commit 불명확 시 이미 쓴 비밀 파일을 보존하도록 보완했다. 회사 범위→계정 shared/per-user 잠금 순서를 사용하고 다른 사용자 승인과 로그인 challenge를 혼용하지 않는다.

관련 backend38통과(4경고), 최종 보안/긴급14통과(2경고, 서로 겹침). 프런트 관련10통과 후 최신3파일8통과(겹침), 타입 포함 제품 build·전체 ESLint 통과. 이번 긴급 복구의 실제 브라우저 파일 선택→재등록, 실기기/실회사·전체 공통 회귀는 미완료다. 앞선 Chrome 결과를 새 긴급 복구 검사로 세지 않는다. 스키마는219표2409컬럼543FK 그대로라 migration/Excel/ERD 추가 변경 없음.

제품 진입은 회사 운영 안내→운영 준비의 본인 긴급 문서, 로그인 본인 확인의 분실 메뉴다. 사용자 도움말2개와 [운영자 절차](../operations/GW_긴급관리자복구_GW-READY-02.md), API 계약을 갱신했다. 나머지는 운영 증거/보관 정책 실행→암호화 백업/폐쇄 복원→선택 SSO→전체 회귀/10인·실환경 인수→로컬 main 반영 순이다. **전체02 미완료, 운영 ready=false 유지, 원격 push/배포 없음.**

마지막 보완 후 긴급 복구7통과(2경고, 위 검사와 겹침): CLI commit 결과 불명확 시 이미 쓴0600 승인 파일 보존까지 포함. 변경 Python Ruff·프런트 변경파일 Prettier·격리 감사 통과. 도움말 검사 최초 필터 src/help에는 테스트가 없어 미실행으로 종료했으며 실제 콘텐츠 검사 파일로 다시 실행한다.

콘텐츠 도움말 회귀18통과. 소유PG fs-gw-ready02-next-test는 ID/label 대조 후 컨테이너·볼륨 삭제했고 work 임시 env/ID를 제거했다. 검토 API/웹은 이번 증분에서 실행하지 않았다. 공유DB·실제 계정·다른 checkout 변경 없음.


## 3차 운영 증거 등록·긴급 복구 실제 Chrome (2026-10-18)

- 회사 운영 준비의 서명된 JSON 실행 증거 등록/목록을 구현했다. 현재 GW 보안 관리자+최근 MFA5분만 쓰기, 감사 역할 읽기, 일반 직원은 거부한다. 검증 키·제품 revision은 서버 설정, DB revision은 직접 읽는다. 서명/회사·세대/현재정책/제품·DB/기한/종류별 PASS 필수 실측값 확인 후 기존 operating_evidence에 불변 저장한다. 실패/일부 결과도 유지하며 runId 중복을 거부한다. 현재 정책과 다른 저장 기록은 이전 기준으로 표시한다. 파일 등록은 실행기가 아니며 ready=false다.
- API/서명/정책19통과(2경고). 초기2실패는 테스트 서명에 개인 공간 generation을 넣은 것이며 서버가 회사 범위 불일치를 거부했다. 실제 회사 정책의 generation으로 수정해 재검사 통과했다. 프런트 새 기록/기존 정책5통과. 전체 ESLint·타입 포함 build·R1~R6오류0, 기존 큰chunk 경고 유지. schema219표2409컬럼543FK 그대로, migration/Excel/ERD 변경 없음.
- 실제 Chrome 합성 회사: 인증 앱 등록→실제 다음번호 로그인→정책적용→서명된 합성 BACKUP FAIL 파일 선택/등록/목록→긴급 문서 다운로드→실제 서버 CLI 승인→로그인 승인파일 선택→제한 복구→새 앱 등록/코드 보관→도움말.390px 가로넘침0·pageerror0. 처음 스크립트의 화면 문구 불일치와 재시도 합성회사명 중복을 수정한 후 최종 통과했다. PASS 백업/실제 휴대폰/실회사 검증이 아니다.
- 재현 스크립트 frontend/e2e/gw-emergency-browser.mjs: 저장소 root에서 실행, 기존 GW_SECURITY_BROWSER_CREDENTIALS/ORIGIN/OUTPUT 환경 사용. 별도 합성 회사와 서버 인증 설정이 필요하다. 합성 FAIL 증거 포함 실행은 GW_EVIDENCE_SIGN_HELPER에 개인 테스트 서명 도구 경로를 제공한다. 출력은 work/gw-readiness-02-evidence만 사용하며 인증 비밀을 공개 결과에 복사하지 않는다.
- 도움말 두 문서와 [서버 설정·등록 계약](../operations/GW_운영증거등록_GW-READY-02.md)을 갱신했다. 현재는 기록 연결까지이며 보관 검토·보존 중지/원문ACL→암호화백업/폐쇄복원/회수재적용→선택SSO→전체회귀/10인·실환경 인수→로컬 main 반영이 남아 있다. 원격 push/배포 없음.

최종 설정 형식 보완 후 evidence API2통과(앞선19와 겹침), 프런트5파일28통과(앞선5와 겹침), Ruff/변경포맷 통과. API8362/웹5362 종료, 소유PG fs-gw-ready02-evidence-test ID/label 대조 후 컨테이너·볼륨 삭제, work의 env/계정JSON/긴급문서/승인/서명키/ID 제거. 공개 산출물에는 비밀 없는 합성 화면과 보고만 복사했다.


## 4차 보관 검토·보존 중지 (2026-10-18)

기존 retention_review/operating_settings를 활용해 기한 대상 갱신(최대200), 상태/숫자ID 검색·페이지, 검토 대기/보류/준비, 회사 전체 보존 중지/해제, 세대별 감사 이력 API·화면을 구현했다. GENERAL 종료 기안과 게시된 글만 한국 날짜+달력 월 기준으로 기한 계산, 원본 변경/삭제 없음. 보안 관리자는 비공개 자료의 식별자·기한·상태만 조회하고 기존 원문 ACL은 매 요청 검사한다. 준비는 현재 정책·원문 권한·회사/동일원문의 모든 정책 보류 없음이 필요하다. 감사 역할은 조회만 한다. 보관 완료/보관본 생성·내보내기/삭제는 미연결이다.

- 관련 backend23통과(2경고): 윤년 기한,203건200+3 분할/중복0,ACL/감사역할,정책간보류/회사중지,최근인증·ACL회수 후 receipt거부,행CAS 경합·원본불변·사유/전후상태 이력. 초기 합성 부서 게시글을 FREE로 만든 검사는 기존 NOTICE/ORG 규칙에 맞춰 권한을 명시 부여해 수정했고, query helper가 sourceId를 덮어쓴 검사도 실제 query로 수정했다. 제품 권한을 완화하지 않았다.
- 프런트 집중6통과, 최종5파일29통과(겹침). 초기 화면 검사의 '적용 중'이 회사/개별 보류 두 곳에 일치해 실패한 선택자를 회사 상태로 특정했다. Ruff·타입 포함build·전체ESLint·변경포맷 검사, R1~R6 감사는 최종 결과를 아래 기록한다. 기존 큰chunk 경고 유지. schema219표2409컬럼543FK 유지로 migration/Excel/ERD 변경 없음.
- 실제 Chrome 합성 제품에서 MFA등록/다음번호로그인→정책적용→검토갱신→회사중지/해제→준비→개별보류/해제→사유이력→원문이동.390px 넘침0/pageerror0. 회사 중지 변경 후 부모 운영기준 버전 갱신을 보완하고 정책2차 연속 적용까지 최종 재검사 통과. 실제 회사/실자료 인수가 아니다.
- 제품 진입은 회사 운영 안내→운영 준비→보관 검토·보존 중지. 도움말의 시작/상태/원문권한/기한/취소/충돌/제한을 갱신했다. [API·운영 계약](../operations/GW_보관검토_보존중지_GW-READY-02.md), 재현 frontend/e2e/gw-retention-browser.mjs(저장소root,합성 GW_SECURITY_BROWSER_CREDENTIALS/ORIGIN/OUTPUT,기한이 지난 합성 게시글 필요).

다음은 실제 암호화 백업/폐쇄 복원/독립 회수 이력 재적용→운영 게이트·선택SSO→전체 회귀/10인·실환경 인수→로컬 main 반영이다. 전체 GW-READY-02 완료·운영 ready를 선언하지 않는다. main2be292e 유지, 원격 push/배포 없음.

최종 Ruff/포맷·격리감사 R1~R6 오류0 통과. 소유 API8362/웹5362 종료, PG fs-gw-ready02-retention-test의 ID/label 대조 후 컨테이너·볼륨 삭제, 임시env/계정JSON/ID 제거. 합성 화면/보고만 공개 outputs에 복사했다. 실제 계정·공유DB·다른 checkout 변경 없음.


## 5차 서버 암호화 백업·격리 복원 (2026-10-18)

- tools/gw_backup.py backup/check/checkpoint/restore 구현. 같은 REPEATABLE READ 스냅샷으로 PG customdump와 전 테이블 행 수/SHA256 지문·버전·키식별자·보안상태를 만들고, 서명명세까지 함께 스트리밍 AES256-GCM으로 암호화한다. 저장 후 복호화 인증/서명/dump지문 재확인→로컬 BACKUP PASS 증거. psql로 CLI/DB 연결이 같은 실제 대상을 가리키는지도 확인한다. 별도키·0600파일/0700폴더·새파일만허용·1GiB한도·private임시평문제거·비밀argv/출력금지.
- checkpoint는 백업과 다른 폴더에 명시 생성하는 암호화 현재 권한 대조 기록/서명head다. 별도 확인한 최신지문·백업실행/명세/원본DB/시각을 대조하고 누락·다른지문·오래됨을 거부한다. 모든 권한 변경의 자동 외부 기록/완전성은 아직 보장하지 않는다.
- restore는 자동 이름의 새 DB만 생성해 PUBLIC CONNECT회수/접속수0 유지. 행지문/FK/head 대조 후 세션/중간인증회수·OTPstep/코드소비/실패제한·계정/멤버십/GW연결·역할/열람자/HR계정 제한을 재적용한다. 인증정보변경 계정은 확인 전정지, 위임자동재개없음. 모호한 ACL·보존 변경은 범위 격리/회사중지. 실패대상은 ALLOW_CONNECTIONS=false 추가동결/보고보존. 원본 덮어쓰기/운영개방 없음. 보고/증거는PARTIAL,checkpointRestrictionsApplied=true/완전성·전체revocationsReapplied·twoAccountChecks=false다. 합성 테스트의 수동 계정 검사를 도구가 자동실시했다고 올리지 않는다.
- 운영 기록 UI에 로컬 백업통과/복원일부확인의 범위 안내를 추가, 기존 거짓 '도구미연결' 문구를 '준비판정/실저장소인수미연결'로 수정했다. 도움말은 증거JSON만등록/키·DB파일등록금지/회수완전성/일정템플릿과 실제설치 구분을 보완했다. [서버 절차·한계·재현](../operations/GW_암호화백업_격리복원_GW-READY-02.md).

검증: 소유PG18 실제 CLI백업→암호화/서명자체검사→별도 권한대조→새DB실복원→행/FK/세션회수→새로그인관리자200/정지직원403·옛세션401. 변조/다른키/기존파일보존·최신지문불일치·정책변경후현재성false·실패DB접속동결/보고·실제MFA코드소비/OTPstep·옛비밀번호/HR역할하향/회사보존중지 검사. 관련backend28통과(2경고), 최신집중9통과(겹침), 최종왕복 추가결과는 아래기록. 프런트23통과·lint/타입포함build통과·기존큰chunk경고. PythonRuff/포맷·R1~R6 결과도 마지막기록을 따른다. 전체CI/전체backend·실휴대폰/운영환경 인수는 이번증분미실행. product브라우저추가실행없음(이번변경은서버도구/범위안내).

초기검사에서 활성쿠키를 남긴 채 합성 재로그인해 기존멱등422를 받은 것을 cookie를비운 실제새로그인으로 수정했다. DB-실행자 시계차를0초기준으로 미래기록 거부한 문제는 명시30초허용/보고와 경과구간 여유로 보완했다. 기존 보관 도움말 강조표시의 괄호뒤 조사로 표시깨짐 회귀를 찾아 수정후23통과했다. 시스템 PG도구16.15를 확인하고 이 검증에는 소유컨테이너PG18 도구를 사용했다. schema219표2409컬럼543FK 유지로 migration/Excel/ERD추가변경없음. DB지문은 migration버전표도 포함한다.

스케줄 파일 deploy/gw-backup/*.service,*.timer와 tools/run_gw_backup.sh는30분 템플릿만제공/bash문법검사이며 Linux systemd실기동·사용자OS/실서버예약설정 변경없음. 다음은 자동회수기록/누락검증·외부보관/실환경복구인수·운영게이트·선택SSO·최종회귀/10인·로컬main. main2be292e 유지·원격push/배포없음. 전체02완료/운영ready 아님.

최종 PG도구/실DB 물리지문 대조·실패접속동결·30초시계허용 후 집중9통과, 경과구간여유 보완 후 실제왕복1건 추가통과(위검사와겹침). 제품스키마219+버전표1=220표 지문대조, 실제PG18.6 확인. 최종도움말18통과(프런트23에포함), Ruff/변경포맷·R1~R6오류0, bash문법통과. 검토API/웹미실행. 소유PG fs-gw-ready02-backup-test ID/label대조 후 컨테이너/익명볼륨 삭제,work임시env/ID제거. 실제공유DB/계정·스케줄·다른checkout 변경없음. 공개outputs에는 비밀없는 verification-summary.json만 저장했다.


## 6차 직원 연결·역할 변경 의도 기록 (2026-10-18)

- 별도 환경을 설정한 `company_identity.execute`에 공간/세대별 직원·연결·역할 상태 자동 기록을 연결했다. 현재 권한/최근 인증/멱등 재조회 뒤 실제 변경만 기록하며 키·원문·이름·사번·처리 사유는 담지 않는다. DB 확정 전에 파일/fsync를 완료하고 기록 실패는503/DB 변경·영수증 취소다. 미설정은 기존 동작 유지/검증 인정 없음, 일부 설정은 거부한다.
- AES256-GCM 봉투·연속 번호/이전SHA256·0600/0700·flock, 기존 체인 매번 검사/부분 파일 보존·4MiB/10,000건 제한. 별도 최신 지문 필수 CLI로 누락/변조/끝 삭제를 대조한다. 외부 지문 자동 전달·전체 저장소 롤백 독자 탐지·다중 호스트/대규모 검증은 없다.
- 기록 저장 후 DB 확정 실패 시 의도만 남는다. 이를 성공이나 권한 부여/복원 명령으로 사용하지 않는다. 전체 수집/확정 증명·복원 재생은 후속이며 기존 restore PARTIAL/전체회수확인false/readyfalse를 유지한다. 공통 인증·HR·다른 GW ACL/보존 경로는 이번 자동 수집 대상이 아니다.
- 실제 소유 PostgreSQL18 합성 회사 HTTP 최초 설정→연결 요청/수락→연결 정지, 저장소 오류503에서 상태/버전 보존→같은 키 재시도 성공→중복 기록 없음. 관련24통과(98.45초), 보강한 최종집중8통과(0.37초, 겹침): 20동시 쓰기·중간/끝 삭제/변조/키·부분 파일·CLI 최신지문·SQLite rollback/확정실패 의도잔존/다른회사 제외. 기존 Starlette/httpx 경고2.
- 기존 도움말 경로에 저장 실패 행동/한계를 추가하고 [운영 절차](../operations/GW_직원연결_역할변경기록_GW-READY-02.md)를 문서 지도/백업 절차에 연결했다. 새 UI·DB표·마이그레이션 없음. 실제 브라우저 새 검증·실회사/실기기·외부 저장소·전원 차단 미실행.

이번은 같은 GW-READY-02의 진행분이다. 원격push/배포·main 병합은 하지 않는다. WMS 자료는 사용자가 잘못 올린 내용으로 철회했으며 해당 저장소/브랜치는 변경하지 않았다. 다음은 전경로 수집·확정/누락 대조와 복원 제한 재적용 연결이다.

종료 시 별도 로컬 main은 다른 작업의 WMS 병합으로843036f임을 읽기 확인했다. 위 과거 main2be292e는 당시 기준이며 이번 GW 브랜치는 아직 main에 통합하지 않았다. 이 세션에서 별도 checkout은 변경하지 않았다.


## 7차 회사 업무 공통 기록·DB 반영 대조 (2026-10-18)

- `company.action`에도 자동 기록을 연결했다. 회사 직원·조직·문서/열람자·결재선/전결/위임·게시글/댓글·채팅/일정·운영 기준/보관 검토 경로의 실제 변경을 기록한다. 회사 범위 조건을 적용한 `gw.backup.capture(scope=...)`로 상태/지문을 읽고 다른 회사의 상태를 기록하지 않는다. 백업용 전역 capture 기본 동작은 유지한다.
- 새 의도 형식은 `gw.company.intent.v2`다. 파일/fsync 뒤 같은 트랜잭션의 기존 core.audit_event에 봉투지문·세대·작업 종류를 기록한다. DB 작업·영수증과 함께 확정/취소된다. 암호화 파일만 남으면 자동 성공 처리하지 않는다. 새 DB표·마이그레이션·웹 API/UI 재설계는 없다.
- 운영 CLI `--expected-head ... --check-database` 추가. 읽기 전용 REPEATABLE READ에서 지문/공간/세대/작업 종류를 모두 대조한다. 모든 비어 있지 않은 v2 기록 일치 시 commitsConfirmed=true/종료0, v1·빈 체인·불일치·확인 불가 기록은 종료3, 체인/DB 오류는 종료1. commitsConfirmed는 전체 회수 수집·최신성·현재 권한·복원 완료를 보장하지 않는다. completenessConfirmed=false/복원PARTIAL/readyfalse 유지.
- 관련 회사 업무·HTTP·실제 백업/격리복원·암호화 회귀38통과218.04초. 보강한 최종집중11통과12.91초(겹침): 일반 기안 작성/상신/승인 기록·회사 범위·DB 감사 세대 불일치·DB rollback 의도잔존·CLI일치0/미확인3·구형/빈 기록 미확인. 첫 추가 검사의 회사ID 비교 형식만 보정한 뒤 재통과했다. 기존 Starlette/httpx 경고2, 도움말18통과2.75초·Ruff/포맷/정적DB·격리오류0. 전체CI/실회사/실기기/새 실제브라우저/외부 저장소/전원차단 인수는 미실행이다.

### 지금까지 구현한 부분과 남은 일

| 구분 | 현재 상태 | 다음 해야 할 일 |
|---|---|---|
| 회사 GW 업무·권한 | 회사별 업무 흐름·연결/역할·현 권한 재검사·대표 합성 검증 구현 | 최신 main 통합 뒤 최종 전체 회귀/10인 인수 |
| 계정 보안·복구 | TOTP·추가 본인 확인·복구 코드·긴급 관리자 제한 복구 구현 | 실제 휴대폰·회사 환경 인수, 선택형 OIDC 연결 |
| 운영 기준·증거·보존 | 버전 정책·서명 증거 등록·검토/보류/이력 구현 | 실제 증거 기반 운영 전환 게이트·별도 보관 완료/실인수 |
| 백업·격리 복원 | 암호화 백업·자체검사·새 DB 복원·세션 회수/확인된 제한 재적용 | 외부 보관·원본/첨부/키 포함 실환경 복구 인수 |
| 변경 기록 | GW 두 공통 쓰기 경로·암호화 체인/최신지문·DB 감사 지문 대조 | 공통 인증/HR 수집·미확인 후속 대조·백업/복원 연결·최신지문 외부 신뢰 |
| 출시·반영 | 개발 브랜치 검증, 도움말/문서 유지 | 전체 수집/운영게이트·SSO/실환경 인수 후 로컬 main 최종 통합 |

추천 실행 순서: 공통 인증/HR 수집 → 미확인 대조·백업/복원 연결 → 외부 보관/운영 전환 게이트 → 선택 SSO → 전체 회귀·10인·실기기/실환경 인수 → 로컬 main 반영. 실제 미확인 환경은 합성 검사로 완료 처리하지 않는다. 원격 push·배포는 하지 않는다.

종료 정리: 소유 PG 컨테이너 fs-gw-ready02-journal-test/55438을 저장 ID와 소유 label 확인 후 볼륨까지 삭제했다. work/gw-readiness-02-journal의postgres.env/server.env/container-id 제거, 앱/웹서버·스케줄 설정 없음. 별도 main843036f는 읽기만 확인했으며 이번 GW 브랜치는 미통합이다. 최종 커밋은 git log를 따른다.


## 8차 공통 인증·HR 계정 변경 수집 (2026-10-18)

- 인증 소유 core.security.recording/HR 소유 hr.security_journal 추가. 기존 두환경설정이 모두없으면 미수집/기존동작유지, 일부설정·키/파일/체인오류는503/해당TX취소. 실제서버에는설정하지않았다. 인증비밀/해시·아이디문자열/IP·원문·사유를복사하지않고상태/버전/식별자만수집한다.
- core 보안감사에 연결: MFA 대기등록/확정·로그인번호/복구코드소비·추가인증·코드재발급·다른세션회수, 정상/제한복구로그아웃·긴급문서/승인감사. 변경된실패/발급카운터도기록한다. HR 회사/직원계정생성·비밀번호/아이디·역할·중지에 회사/세대계정상태+인증소유상태를연결하고멱등재조회중복을막는다.
- 형식 core.security.intent.v1/hr.users.intent.v1, 같은TX core.audit_event의새action/entity표식에봉투지문/허용된subject만기록한다. 기존CLI가GW와새형식을함께대조한다. 모든비어있지않은기록일치만commitsConfirmed=true, 전체완전성/readyfalse·restorePARTIAL유지. core는HR/GW업무를조회하지않고HR은인증소유함수만호출한다. 새표/마이그레이션/UI/API없음.
- 주요 경로 연결을 확인한 것이며 직접SQL/다른프로세스·오프라인시드/복원재적용·미구현SSO연결·임의글로벌역할/회사세대변경의전수수집은선언하지않는다. 카운터추가로기존10,000건한도/전체체인검사비용에더빨리도달할수있다. 보관묶음교체·최신지문외부신뢰·미확인의도판정·백업/복원연결이남는다.
- 관련 인증/HR/긴급복구/기존GW기록37통과138.68초(경고4: Starlette/httpx·anyio·Pydantic). 최초추가검사에서긴급기록접두어를실제security.emergency_kit명칭에맞게수정한뒤재통과했다. 계정/회사생성·로그아웃·실제백업복원/제한재적용을포함한최종25통과119.28초(겹침/경고4). 도움말18통과2.88초·Ruff/포맷·정적DB/격리오류0. 전체CI·새실제브라우저/실기기/실회사/외부보관/전원차단검사는미실행이다.

다음: 미수집경로감사·미확인의도대조/백업복원연결 → 최신지문/백업외부보관·운영전환게이트 → 선택SSO → 전체회귀/10인·실기기/실환경인수 → 최신로컬main통합. schema219/2409/543불변, 이번개발은GW브랜치만반영하며원격push/배포없음.

종료정리: 본인PG fs-gw-ready02-journal-test/55438 ID와 factory-studio.owner=gw-ready-02-journal label을확인하고컨테이너/익명볼륨삭제, work/gw-readiness-02-journal의server.env/postgres.env/container-id제거. 앱/웹서버/예약작업설치없음·실계정/공유DB/다른checkout변경없음. 포털 계정보안 도움말에도 기록실패 행동/운영도움말링크추가, 최종 도움말검사를따른다. 별도main843036f읽기확인/미통합, 기준fe47e1b/최종gitlog.


## 9차 백업 기준·미확인/후속 기록의 격리 제한 연결 (2026-10-18)

- 새 backup_journal: 원본 DB 스냅샷 전에 독립 FS_GW_JOURNAL_EXPECTED_HEAD와 체인 검증→같은 백업 DB 스냅샷에 반영된 감사 지문 집합/기준 저장. checkpoint는 같은 앞부분인지 대조해 기준 미확인/이후 기록을 후보로 만들고 현재 DB 미확인 수·제한할 계정/회사 범위만 서명·암호화 파일에 저장한다. 파일이 백업 전 저장됐으나 DB는 백업 후 확정된 경우도 빠뜨리지 않는다.
- restore는 기존백업/대조 파일연결과 독립 최신기록지문을 대상DB 생성전에대조한다. 현재 상태 checkpoint 재적용 뒤 core/HR 사용자 중지·GW 연결 정지/회사 보존 중지/권한 버전 갱신을 추가 적용한다. 복원에 없는 계정은 만들지 않고 취소한 연결을 재개 가능하게 바꾸지 않는다. 원본 수정/권한 허용/접속 개방없음, 미확인을 실패나 회수완료로 단정하지 않는다. report에 journal제한처리·후보/미확인/카운터/계정/범위수 추가, 콘솔요약/기존서명증거계약은유지한다. PARTIAL/전체회수확인false/완전성false/readyfalse다.
- 확인지문 조회를core/GW 묶음set으로공용화, 백업 연결은 복호화된snapshot본문 대신metadata만남겨메모리중복을줄인다. 키를백업출력폴더에두지못하게검사한다. 기록기준없는과거백업+새기록설정은새백업을요구하며, 미설정의과거경로는부분검증으로유지/기록연결인정없다. schema219/2409/543불변·새DB표/마이그레이션/UI/API없음.
- 집중14통과11.16초 후 최종관련30통과84.90초(겹침/경고4: Starlette/httpx·anyio·Pydantic). 실제 소유PG18에서 DB TX 미확정상태로 백업→그뒤확정·기준이전 미확인1건·연결회수후재개·HR역할왕복→대조→새DB복원. 후보6/미확인1/계정제한1/GW범위1·관리자계정active/직원disabled/회사hold/활성연결0/접속제한0·원본직원active/연결ACTIVE/역할STAFF불변 확인. 잘못된독립지문거부·누락/다른기준/metadata-only/기존백업복원·인증회귀포함. 초기추가검사의요약반환값/상세보고필드구분오류를보고파일대조로보정후재통과했다.
- 도움말18통과2.38초·Ruff/포맷/정적DB·격리R1~R6오류0. 전체CI/새실제브라우저/실기기/실회사/외부저장소/전원차단 인수미실행. 원본/공유DB·실계정/다른checkout·브라우저설정변경없음. 본인PG ID/label대조후컨테이너/내부폐쇄복원DB/익명볼륨삭제·work env/ID제거, 앱/웹/일정설치없음.

다음: 미확인 의도 최종 판정·안전한 제한 해제 절차, 기록 보관 묶음 교체·독립 최신 지문 전달/외부 보관 → 전경로 완전성/운영 전환 게이트 → 선택 SSO → 전체 회귀/10인·실기기/실환경 인수 → 최신 로컬 main 통합. 독립지문은수동제공이며기존30분템플릿만으로갱신되지않는다. 전체02미완료·재승인반복없음. 별도main843036f읽기확인/이번GW미통합·원격push/배포없음. WIP e01435f,최종gitlog.

## 10차 완료: 거래 취소 판정·새 격리 복원

선택 원본/타임라인/거래 근거와 6종 상태 판정, CLI 집계, 전체 취소 건만 새 checkpoint에서 제외하는 경로를 구현했다. 이전 복원 제한을 직접 해제하지 않는다. 실제 PG18 합성 검증 포함 관련 backend29 통과. 전체 운영 판정은 PARTIAL/ready=false를 유지한다. 다음은 과거 미확인 수동 인수 기준·보관 묶음 교체/독립 지문 전달/외부 보관, 전경로 완전성/운영 전환 게이트, 선택 SSO, 전체 회귀·10인 실환경 인수와 main 통합이다.

## 11차 완료: 과거 미확인 기록 인수 기준

최신 지문에 묶인 비공개 진단 보고 CLI와 한국어 판정별 조치/운영 점검 목록을 추가했다. 과거 미확인을 검토 완료만으로 제외하지 않으며 권한 해제·운영 승인 입력은 없다. 보고는 서명 증거나 checkpoint 입력과 구분한다. 다음은 보관 묶음 교체·독립 지문 전달/외부 보관, 전경로 완전성/운영 전환 게이트, 선택 SSO와 전체·10인 실환경 인수다.

## 12차 완료분: 암호화 기록 사본·오프라인 인증

원본 잠금/지문 인증→새 비공개 묶음 복사→복사본 재인증→완료 명세 기록과 DB 없는 오프라인 검증 CLI를 추가했다. 원본은 계속 기록하며 과거 사본은 고정된다. 실패·누락·변조·다른 키/지문·덮어쓰기를 거부한다. 이번 단계는 사본 생성/검증 기반이며 원본 한도 초기화나 실제 보관 묶음 교체는 아니다. 다중 묶음 백업/복원 연결, 독립 지문 자동 전달·네트워크 전송/외부 내구성 인수는 계속 남아 있다.

## 13차 완료분: 보존 기록 연결과 활성 기록 교체

과거 ciphertext/전역번호/지문을 유지한 새 보존 폴더 생성과 활성 접미 기록, 전환 전 원본/후속 지문 점검을 추가했다. 기존 백업의 prefix 기준과 교체 후 권한 대조를 연결한다. 활성10,000/전체100,000건이며 전체 체인 인증 비용은 남는다. 실서버 설정 전환·독립 최신지문 자동 전달/외부 전송·장기 보관 성능/장애 인수는 아직 수행하지 않았다.

## 14차 완료분: 전달 확인 기록·백업 자동 지문 입력

새 사본 재인증 후 별도 키 HMAC/순번/이전지문 확인 기록을 남기고, bootstrap 이후 접두 연속성을 대조하며 반복 전달한다. 선택 설정 시 백업/checkpoint/restore가 현재성/최소 순번을 검사한 지문을 자동 입력한다. 실행 템플릿만 추가했고 실제 외부 저장소·예약 실행은 설정하지 않았다. 외부 내구성/전체 저장소 복귀 방지·장기 성능·전경로 완전성/운영게이트/실환경 인수는 남는다.

## 15차 완료분: 운영 전환 차단 근거 표시

운영 준비에 종류별 최신 증거 진단을 연결했다. 기준/버전/실행자 키/시각/필수 검사 항목을 대조하고 최신 실패를 과거 성공으로 숨기지 않는다. 제품에 한국어 조치 안내를 표시하고 새 증거 등록 후 다시 조회한다. 원본 서명 재검증과 전체 회수 완전성/외부 보관·실환경 인수가 남아 있어 ready=false를 유지한다. 다음은 원본 증거 보존/재검증 계약과 전경로 회수 인수, 실제 외부 저장소·10인 실환경 인수다.

## 16차 완료분: 새 증거 원본 보존·서명 재검증

새 등록분부터 기존 JSONB 내부 예약 필드에 검증한 원본 서명 대상 값을 보존하고 현재 키로 재검증·DB 행 대조를 수행한다. 원본 없는 과거 기록은 소급 작성하지 않고 재검증 불가로 표시한다. 키 교체/원본·검사값·범위·실행 불일치를 거부한다. 전체 운영 준비는 계속 false다. 다음은 전경로 수집 완전성/회수 인수와 운영 전환 최종 조건, 외부 저장소·10인 실환경 인수다.

## 17차 완료분: 로그인 요청·거부 수집 누락 보완

실제 쓰기 경로를 대조해 비밀번호 세션 발급/MFA 요청 생성·실패·만료/긴급 로그인 실패·문서 만료의 기록을 보완했다. 시도 횟수/만료 시각과 저장 실패 rollback을 검증한다. 별도 수집 경로 검증 문서에 확인한 범위와 세션 연장/초기 설정·운영 도구/직접 SQL 등 미인수 경로를 구분했다. 전체 완전성/회수/ready는 계속 false이며 나머지 경로·실환경 인수가 후속이다.

## 18차 완료분: 초기 설정 도구 기록·세션 재생 제외

운영자 회원 및 HR 초기 회사/예제 계정의 최종 생성·중지·활성 상태를 기록하고 실패 시 취소한다. 세션 유휴 연장은 모든 세션 회수 정책에 따라 허용 재생에서 제외하며 상한/이전 토큰 거부를 검증했다. 실제 도구/계정/환경 변경은 하지 않았다. 남은 직접SQL/기타운영도구·카운터 의미/부하·전체 회수/실환경 인수는 별도다.

## 19차 완료분: 운영 경로 v1·복원 후 실제 인증 거부 검사

정상 운영/도구 경로와 재생 제외·직접 SQL/외부 인수 경계를 v1로 문서화했다. 실제 dump/restore의 수동 지문/교체·전달 확인 경로에서 과거 관리자·직원 토큰, 미완료 요청을 인증 판별 함수로 거부하는지 확인한다. 원본 관리자 HTTP 사용과 직원 역할 변경에 따른 기존 세션 회수는 유지한다. 제품 기능/DB/접속 개방 변경은 없으며 전체 무누락·실환경/10인 인수·최종 운영 전환은 계속 후속이다.

## 20차 완료분: 최종 운영 조건과 미확인 근거 분리

구조화된12조건을 확인됨/조치필요/미확인으로 표시하고 다음 행동을 연결했다. 현재 책임자 활성연결/조직/인원/MFA·현재 서명 증거는 실측 조회로, 미연결 외부복구/전체수집회수/실회사/최종전환은 미확인으로 판정한다. 로컬조건이모두맞아도ready=false. 책임자연결회수시재판정·직원접근제한·화면상태구분을 검증한다. 실제 외부·10인 회사 인수와 최종 전환 증거 계약/실행은 후속이다.

## 21차 완료분: 필요한 인수 근거·10인 도입 절차

미확인4조건의 검증 환경·필요 근거를 제품에서 펼쳐 보도록 연결했다. 정책의 예정 인원에 맞춰 안내하며, 안내만으로 상태나ready를 바꾸지 않는다. 10인 실회사 인수 문서에 현재까지의 완료/합성검증, 남은 증거 어댑터·최신main대조/전체회귀·외부장애/실회사인수·최종전환을 분리했다. 실제계정/외부저장소/배포는 이번에 적용하지 않았다.


## 2026-10-20 GW-READY-02 26차 암호화 사본 전체 읽기 어댑터

브랜치 codex/gw-company-01, 시작 커밋7ac3914. 작업 트리 깨끗함 확인 후 진행. acceptance_artifact.inspect_copy와 기존 수집기 --storage-copy를 추가했다. 현재 회사/세대·정책·코드/DB·서명·기한·RPO를 통과한 BACKUP PASS의 artifactDigest를 실제 사본 전체 SHA256과 대조한다. 열린 descriptor의 소유자/비공개 권한/일반파일/1GiB 한도·전후 크기/mtime/ctime을 검사하며 최종 심볼릭 링크·빈 파일·읽는 중 변경을 거부한다. 원본 백업 경로/복호화키/DB 연결 없이 지정 사본만 읽는다. 결과는 경로·원문 없이 지문/읽은 크기/백업실행 번호와 MATCH/MISMATCH. MISMATCH는 기존 쌍 일치에도 BLOCKED/exit2. 입력/서명 오류exit1·새0600 출력만 허용. MATCH는 저장소 독립성·내구성·복호화·복원 증거가 아니며 미확인4/ready=false 유지. 기존 파일쌍 모드 호환, 제품 API/UI·스키마 변경 없음.

검증: 관련 단위86 통과0.16초(기존 경고2). 실제 임시 파일 읽기/변조/권한/링크/빈파일·서명/옛버전 및 CLI 사본불일치/종료2/출력0600/readyfalse 확인. Ruff check/format 통과, db:validate219표2409컬럼543FK 오류0, Python3.14 R1–R6 오류0. 기본 python3 감사는 기존 최신 구문 파싱 오류로 실패해 uv Python으로 재실행 통과했다. 전체CI/실외부 저장소/PG 복원/브라우저/10인 인수는 이번 미실행. DB스키마 불변으로 Excel/ERD 재생성 미실행.

API94777:8362/Vite89508:5362 포트와 PG fs-gw-ready02-preview 소유라벨 대조, 서비스/미리보기DB 변경 없음. 비밀/work 스테이징 없음·다른checkout/main/원격push/배포 변경 없음. 전체02 진행 중. 다음: 외부 사본의 실제 장애영역/복호화·격리복원 연결, 전체 변경 수집/권한회수 계약과 실행 어댑터, 최종 ACCEPTANCE 계약/게이트, 기존GW UI 구성 보완, 최신main/전체회귀·10인 실인수. 전체 권한회수와 UI 보완은 이번 미구현.

재현: `uv run --project backend pytest backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (86). `npm run db:validate`; `uv run --project backend python tools/audit_schema_isolation.py`. 마지막 커밋은 git log -1 참조.

## 2026-10-20 GW-READY-02 27차 사본 복호화·명세/dump 검증

codex/gw-company-01, 시작b1ed206. 기존 gw_backup.py에 verify-copy 명령/verify_storage_copy 어댑터 추가. 원본DB 접속 없이 비공개 사본을 최대1GiB로 새 임시파일에 복사하고 현재 서명 BACKUP PASS/회사·세대·정책·제품/DB/RPO와 사본 지문을 대조한다. 같은 임시사본을 기존 AES-GCM/unpack 경로로 복호화해 내부 명세 서명·dump지문·증거 manifestDigest/runId를 확인한다. 입력은 백업 복호화키/키ID·신뢰 공개키만 필요하고 서명 개인키/인증키/DB URL 불필요. 임시 암호문/평문을 성공·실패 모두 정리한 뒤 새0600 최소보고서만 작성한다. 결과 PARTIAL/readyfalse·storageIndependenceConfirmed/databaseRestoreConfirmed=false. 오류exit1/기존출력 보존. unsigned보고서는 ACCEPTANCE 증거/제품등록용이 아니다. 사본의 실제PG 복원·외부장애영역/내구성은 미확인이다.

검증: 관련93 통과0.19초(기존 경고2), 실제 합성 AES-GCM/tar 서명/dump7경로와 CLI DB/서명개인키 없는 실행 포함. 잘못된키/명세불일치/dump변조/증거서명변조/암호문변조/기존보고서 보존·임시폴더정리·원본불변 확인. Ruff check/format·db:validate219/2409/543·R1–R6 오류0. 이번PG복원/실외부/브라우저/UI/전체CI/10인인수 미실행. schema불변·Excel/ERD재생성 미실행. 미리보기DB/서비스·실계정·다른checkout/main/원격push/배포 변경없음. 작업 트리 시작 깨끗함·비밀/work 스테이징없음.

전체GW-READY-02 진행 중. 다음: 이번 사본 검사와 실제 격리PG복원 증거의 연결·실제dump 기반 회귀 → 전체 변경 수집/권한회수 계약/어댑터 → 최종 ACCEPTANCE 계약·운영게이트 → 기존GW UI 구성 보완 → 최신main/전체회귀·10인실인수. 실제저장소/회사인수는 사용자 실환경에서 별도 확인하며 현재 readyfalse/미확인4 유지.

재현: `uv run --project backend pytest backend/tests/test_gw_storage_copy.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (93). `npm run db:validate`; `uv run --project backend python tools/audit_schema_isolation.py`. 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 28차 실제PG 사본 검사·격리복원 연결

codex/gw-company-01, 시작2b11be2·작업트리깨끗함 확인. 실제 백업 회귀를 보강했다. 실제 pg_dump/암호화 결과를 별도 로컬 비공개 사본으로 복사 → DB/인증키/서명개인키/PG컨테이너 환경을 제거한 subprocess의 verify-copy → 내부서명/dump/manifest 연결 확인 → checkpoint 뒤 테스트 원본 백업파일 제거 → 같은 사본으로 새 접속제한PG 복원 → 서명복원 증거와 사본검사 manifestDigest 대조/API전달·행/FK·세션회수·직원403·관리자200/원본 상태 유지까지 검사. 실제 다른 저장소 장애영역을 준비한 것은 아니다. 사본보고서 PARTIAL/databaseRestoreConfirmed=false는 파일검사 범위를 유지하며 별도 복원 증거도 PARTIAL/readyfalse다. 수동 합성업무 검사를 도구의 twoAccountChecks=true로 올리지 않았다.

실통합에서 DB 종료시각이 호스트보다 약1.6초 앞서 사본 검사가 실패했다. 사본 finishedAt 허용을 기존 verify_evidence와 같은30초로 정렬했다. snapshot/RPO 현재성 규칙은 변경없음·31초초과 거부 검사 추가. 이후 기존 권한회수 CHECK에 DB시각역전1회, 별도 재실행의 기존 백업증거 등록400도 관찰했다. 시계/호스트/컨테이너 설정은 변경하지 않았다. 첫3실행은 각각1실패2통과·2실패1통과·1실패2통과이며 성공으로 세지 않는다. 최종 새 소유DB에서3통과44.35초(기존 경고2). 시각역전 원인·장기안정성/실운영 시간동기 인수는 미확인으로 남긴다.

검증: 단위95통과0.20초(기존 경고2), 위 실제PG3통과, Ruff check/format·diff·정적DB219/2409/543·R1–R6 오류0. 소유preview컨테이너ID/owner라벨/loopback55439 대조 후 매실행 UUID *_test 생성/alembic head·시험DB정리; preview DB/서비스 유지. 이번브라우저/UI/전체CI/실외부/실기기/10인인수 미실행. schema불변·Excel/ERD재생성 없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포 변경없음.

전체02진행중. 다음: 전체 변경 수집/권한회수의 경로별 증거계약·실행어댑터와 미확인 처리 → 최종 ACCEPTANCE/운영게이트 연결 → 기존GW UI 맥락·긴정보/다음조치/모바일 보완 → 최신main/전체회귀·10인인수. 실제외부저장소/시간동기·회사인수는 별도 실환경 검증. 현재 readyfalse/미확인4 유지.

재현: 별도 소유PG18 *_test에 alembic head 적용·TEST_DATABASE_URL/GW_BACKUP_TEST_CONTAINER 주입 후 `uv run --project backend pytest backend/tests/test_gw_backup.py::test_actual_backup_replay_restore_and_business_denial backend/tests/test_backup_journal_restore.py -q --tb=short` (3). 단위는27차 명령에 같은파일 그대로(95). 미리보기DB를 TEST_DATABASE_URL로 사용하지 않는다. 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 29차 관측 기록계열 진단

codex/gw-company-01, 시작b494178·작업트리깨끗함. gw.journal_coverage 추가: 이미 암호화 체인/별도head·DB 감사·거래상태로 검증한 기록을 core.security.intent.v1/hr.users.intent.v1/gw.company.intent.v2 계열별 MISSING/SETTLED/UNSETTLED와6종 거래판정 건수로 집계한다. 과거v1/알수없는계열은 unsupportedRecords로 차단·계열대체없음. 누락/추가/중복지문/임의APPROVED 판정 거부. 모든계열 거래정리도 PARTIAL일뿐 completeness/revocations/release=false·경로실행/롤백·독립최신head·복원거부/원본유지/운영자경계5범위는 별도다. 기존 gw_identity_journal --classify-transactions 및 --review-report에 recordingFamilies 연결. snapshot/계정/operation원문 출력없음. 기존CLI 종료코드는 거래판정 기준을 유지하므로 exit0과 계열BLOCKED가 함께 있을수있다. 이 진단을 ACCEPTANCE/운영완료/전체경로계약으로 사용하지 않는다. 제품API/UI·DB스키마/권한변경 없음.

검증: 관련단위110통과0.18초(기존경고2). 소유preview컨테이너ID/라벨/55439 대조·새UUID *_test/alembic head에서 실제PG 거래취소/진행/저장점/다른원본 판정 및 CLI 두경로3통과1.52초(기존경고2). 취소확인exit0이어도 HR/GW MISSING·계열BLOCKED, 근거없는UNKNOWN exit3·보고/표준출력일치·비밀미노출 확인. 시험DB정리/previewDB·서비스 유지. Ruff check/format·CLI help·정적DB219/2409/543·R1–R6/diff 오류0. 전체CI/실외부/사본복원/브라우저/UI/10인실인수 이번미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

다음: 개별 변경 경로별 예상실행/롤백·회수 검증 근거를 현재범위/버전에 묶는 계약·실행어댑터(이번계열집계와 구분) → 최종 ACCEPTANCE/게이트 → 기존GW UI 보완 → main/전체회귀·10인실인수. readyfalse/미확인4 유지·전체02진행중.

사용자추가지침: 매작업 종료시 완료내용/검증/제약/다음작업을 한국어로 알리고 다음작업 난이도에 따라 모델·추론수준 추천. 모델변경은 사용자가 선택하며 자동변경하지 않는다. 다음 개별경로/권한회수 연결은 높음: 현재앱 선택지 기준 GPT-6.1 Sol + High 추천, 최종 무누락/경계감사는 GPT-6 Astra + High 대안. 공식 OpenAI reasoning 가이드는 복잡성에 따른 effort 선택의 일반근거이며 이프로젝트 추천은 작업판단이다(https://developers.openai.com/api/docs/guides/reasoning).

재현: `uv run --project backend pytest backend/tests/test_gw_journal_coverage.py backend/tests/test_journal_review.py backend/tests/test_gw_acceptance_artifact.py backend/tests/test_gw_acceptance_collection.py backend/tests/test_gw_operating_contract.py backend/tests/test_gw_readiness.py backend/tests/test_gw_launch_gate.py -q --tb=short` (110). 별도소유PG18 *_test/alembic head·TEST_DATABASE_URL 후 `uv run --project backend pytest backend/tests/test_journal_transaction_proof.py -q --tb=short` (3). 마지막커밋 git log -1.

## 2026-10-20 GW-READY-02 30차 GW 연결·역할 7경로 진단

codex/gw-company-01, 시작1b1c4b3·작업트리깨끗함. journal_routes/GW_IDENTITY_ROUTES_V1 및 기존CLI --company-id 추가. 현재 활성회사정책/세대·FS_CODE_REVISION·DBhead/별도확인head에 진단을 묶는다. 최초설정·연결요청/수락/취소/중지/재개·역할변경7개를 정확operation 패턴으로 분리한다. 다른회사/세대/bool범위 제외, 과거형식/잘못된ID/알수없는operation은 해당범위미지원 처리. 같은계열 다른operation으로 채우지 않는다. 모든기록 집계로 이후미확인에 과거성공 fallback없음. MISSING/ABORT_ONLY/UNSETTLED/COMMIT_OBSERVED 및 거래6종건수. 과거기록에 실행코드버전이 없으므로 assessment버전만 기록·executionRevisionVerified=false. 저장실패롤백/복원거부UNVERIFIED·모두관측도PARTIAL/전체회수·완전성·전환승인false 유지. 계정/대상ID/원문operation 출력없음. CLI exit0과경로BLOCKED 공존가능. 인증/HR/문서ACL 전체계약은후속이다.

검증: 단위121통과0.22초(기존경고2). 소유preview컨테이너ID/owner라벨/55439 대조·별도UUID *_test/alembic head에서 GW변경3+거래판정3 총6통과24.64초(기존경고2). 새실HTTP저장실패503→연결ACTIVE/버전불변→재시도중지200/직원posts403, 실제CLI 현재정책지문/head/제품버전·표준출력/보고일치·suspend관측1/cancel·resume미기록BLOCKED/readyfalse 확인. 이전ACL/미확인의도·감사범위변조 및 거래취소/진행/저장점/원본불일치 재검증. 테스트DB정리·previewDB/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/실외부/사본복원/브라우저/UI/10인실인수 미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4. 다음: 실행버전/실행번호·경로별저장실패롤백/권한회수 결과를묶는실제수집어댑터, 인증/HR/ACL경로목록 확대·실검증 → ACCEPTANCE/게이트 → GW UI보완 → main/전체회귀/10인인수. 다음난이도높음·GPT-6.1 Sol + High 추천, 최종경계감사는GPT-6 Astra + High 대안. 사용자선택전모델자동변경없음.

재현:29차단위명령에 backend/tests/test_gw_journal_routes.py 추가(121). 별도소유PG18 *_test/alembic head·TEST_DATABASE_URL 후 `uv run --project backend pytest backend/tests/test_gw_identity_journal.py backend/tests/test_journal_transaction_proof.py -q --tb=short` (6). 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 31차 합성 경로검증 실행 수집기

codex/gw-company-01, 시작e396c1c·작업트리깨끗함. tools/gw_route_verify.py 추가: 로컬 소유PG의 postgres 관리연결(FS_GW_ROUTE_VERIFY_ADMIN_URL)로 UUID 새 *_test DB만 생성→alembic head→고정된 실제HTTP직원연결중지 저장실패롤백/직원403 및 거래취소/진행/저장점/원본불일치2시나리오를 pytest로 직접실행→JUnit 정확모듈/이름·종료코드/누락/중복/실패/건너뜀검사→생성DB만정리→새0600 보고서. 외부 XML/체크값/임의명령 입력없음. runId/시작종료시각/DBhead·기준커밋+backend/tools실코드지문·전후동일여부와시나리오결과 기록. 지문은커밋되지않은코드도포함하며 기준커밋과실코드를혼동하지않는다. DB URL/계정/본문/로그/임시경로는보고서/표준출력미포함. private임시로그/JUnit폴더정리, 기존보고서덮어쓰기금지·미리보기DB직접대상/비로컬관리연결거부. migration120초/검증300초제한.

성공도 SYNTHETIC_GW_ROUTE_EXECUTION/PARTIAL·readyfalse·실회사인수/전체권한회수/완전성false·복원권한거부UNVERIFIED. 실패/누락/건너뜀/소스변경은BLOCKED/exit2; 환경/예외는exit1·실행오류보고서가항상생성되는것은아님. unsigned합성보고서를 ACCEPTANCE/현재회사운영증거로등록하지않는다. 회사/정책은테스트내생성범위이며 미리보기회사3의인수근거아님.

검증: 관련단위132통과0.20초(기존경고2). 소유preview컨테이너ID/owner/55439대조후 수집기 실제CLI 실행: 새DB마이그레이션/고정2시나리오PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·잔여수집DB0 확인. 첫실행은JUnit모듈명이tests.접두인것을짧은이름만비교해MISSING/BLOCKED/exit2, DB정리는성공. 모듈명정확허용2형식으로보정후재실행통과, 첫보고서는보존/덮어쓰지않음. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. UI/브라우저/전체CI/실외부/복원/10인실인수 이번미실행. 스키마불변·Excel/ERD재생성없음. 소유시험DB정리·previewDB/서비스유지, 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4 유지. 다음: 고정실행시나리오를 인증·HR·ACL 및나머지GW경로의저장실패롤백/거부로확대하고 복원후검사와연결 → 최종서명 ACCEPTANCE/게이트 → GW UI보완 → main/전체회귀/10인실인수. 다음난이도높음·GPT-6.1 Sol + High 추천, 최종경계감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:30차단위명령에 backend/tests/test_gw_route_verify.py 추가(132). 소유로확인한로컬PG postgres 관리연결을FS_GW_ROUTE_VERIFY_ADMIN_URL에비공개주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정2실행). 기존TEST_DATABASE_URL을초기화하지않으며새DB만소유/정리한다. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 32차 인증·HR·ACL/실복원 실행수집 확대

codex/gw-company-01, 시작95f7e48·작업트리깨끗함. 고정수집카탈로그 GW_SYNTHETIC_ROUTE_PROBES_V2를2→8시나리오로확대: 기존GW중지롤백/403·거래판정에 MFA등록실패롤백·로그인요청issued실패롤백·비밀번호세션발급실패롤백·HR비밀번호/역할/로그인ID/중지/재시도·문서ACL저장실패롤백/기록·실제PG격리복원후옛세션/미완료인증/회수권한거부/원본유지를추가. 문서submit의journal503시 approval_document 상태/버전·기록수불변과 재시도submit/approve를 실제검사하도록보강(S회사/활성세대제한). 전체인증/HR/ACL경로수집완전성이아니라지정시나리오범위다.

GW_BACKUP_TEST_CONTAINER 설정시 FS_GW_ROUTE_VERIFY_OWNER와 docker inspect 소유라벨/실행상태/PG5432→관리URL의동일loopback포트매핑을사전대조·불일치거부. 미설정복원검사는SKIPPED→BLOCKED이며자동생략통과없음. 정확parametrized JUnit이름포함 고정검사. 전체8PASSED/정상종료/소스불변시에만 restoredAccessDenial=SYNTHETIC_SCENARIO_PASSED. 실제회사/전체revocations/completeness/ready는false·서명ACCEPTANCE아님. 복원도구/DB접속제한PARTIAL은그대로다.

검증: 단위139통과0.22초(기존경고2). 소유컨테이너ID/라벨/55439확인후 새소유DB의실수집CLI 최종8PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. 첫실행은새문서조회테이블명오류로ACL FAILED·실행중수정sourceUnchanged=false→BLOCKED/exit2·복원거부UNVERIFIED를유지했다. approval_document와활성세대로수정후소스고정재실행통과·첫보고서보존. 최종소유PG읽기조회 collectorDB0/closedRestoreDB0/preview존재true확인. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부·실회사/기기/10인인수 미실행. 스키마불변·Excel/ERD재생성없음. previewDB/서비스유지·비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4유지. 다음: GW연결취소/재개/역할변경의저장실패롤백·허용/거부실행시나리오를추가해7경로진단과대조, 인증실패/복구·HR/ACL나머지분기확대 → 최종서명ACCEPTANCE/게이트 → 기존GW UI구성보완 → main/전체회귀/10인실인수. 다음난이도높음·GPT-6.1 Sol + High 추천(상태전이·권한·DB회귀), 최종경계감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:31차단위명령그대로(139). 소유확인로컬PG postgres관리연결을FS_GW_ROUTE_VERIFY_ADMIN_URL, 컨테이너를GW_BACKUP_TEST_CONTAINER, 소유라벨값을FS_GW_ROUTE_VERIFY_OWNER에비공개주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정8실행). 복원컨테이너/DB연결일치와생성자원정리필수·preview를초기화하지않는다. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 33차 연결 취소·재개·역할 부여/회수 롤백 검증

codex/gw-company-01, 시작b74d593·작업트리깨끗함. test_gw_identity_route_probes 실제PG/HTTP4시나리오추가·수집카탈로그GW_SYNTHETIC_ROUTE_PROBES_V3 8→12. 연결취소(PENDING→CANCELLED)/재개(SUSPENDED→ACTIVE), SECURITY_ADMIN부여/회수를분리. journal저장503에서 S범위연결상태/버전·person버전/역할행·authz_version·core.request_receipt불변/기록수불변·기존업무접근유지 확인. 같은request key 재시도성공→기록정확히1증가→중복요청결과/DB/기록수불변, 새key/옛버전409불변 확인. 비권한직원변경403, 취소뒤수락403/업무403·재개뒤업무200, 역할부여뒤보안이력200/회수뒤403와재변경403, 마지막보안관리자제거409불변. 새기록과원본감사확정대조. 전체회수/인수완료로승격하지않음.

source_identity가고정검증파일을git ls-files외에도명시포함하도록보강해 새미추적probe도실코드지문에포함한다. 미추적고정probe수정시커밋이같아도지문변경 단위검사추가. 실행버전/카탈로그/원본범위와합성구분유지·readyfalse/미확인4그대로.

검증: 관련단위140통과0.22초(기존경고2). 소유preview컨테이너ID/owner/55439대조·새소유DB의실수집CLI12PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. 새4시나리오와기존인증HR/ACL·실dump복원포함. 종료후collectorDB0/closedRestoreDB0확인·preview/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부/실회사·기기/10인인수 미실행. DB스키마불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중. 다음: 인증실패/만료/긴급복구·코드복구/세션회수 분기의고정실행수집확대와미검증경계대조 → 최종서명ACCEPTANCE/게이트연결 → 기존GW UI구성보완 → 최신main/전체회귀·10인실인수. 실제저장소/현재회사인수·전체수집무누락은여전히미확인. 다음난이도높음·GPT-6.1 Sol + High 추천(인증상태·일회성/세션·거래실패경계), 최종감사GPT-6 Astra + High 대안. 모델자동변경없음.

재현:32차단위명령그대로(140). 소유로컬PG postgres관리연결FS_GW_ROUTE_VERIFY_ADMIN_URL·GW_BACKUP_TEST_CONTAINER·FS_GW_ROUTE_VERIFY_OWNER 주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정12). 새DB만생성/정리·preview초기화금지. 마지막커밋git log -1.

## 2026-10-20 GW-READY-02 34차 인증 실패·만료·긴급/코드 복구 실행수집

codex/gw-company-01, 시작6bd67f0·작업트리깨끗함. 고정카탈로그 GW_SYNTHETIC_ROUTE_PROBES_V4 12→23. 기존실검사에서 OTP5회실패/잠금·새요청제한유지/기록, 요청만료/인증버전변경거부/기록, denied·expired·emergency3분기기록실패롤백, 복구코드경합/제한세션/재등록/옛코드거부, 타세션회수/코드재발급·옛세션거부, 긴급문서만료/기록, 로그아웃401/기록을연결했다. 긴급HTTP복구와역할/만료재확인에journal wrapper2개를추가해 실제승인경합/CSRF·Origin거부/업무접속차단/recoveryOnly/재등록/승인재사용401·현재권한403/만료401과DB감사확정/암호화기록을대조한다. 승인/재사용거부에필요한새기록존재·복구미실행시redeemed없음·비밀필드없음확인. 직접SQL로만든만료/역할회수준비는테스트주입일뿐자동전체수집/실인수근거가아니다.

파라미터명이달라진실행결과는해당검사를채우지못하도록JUnit wrong-param 거부단위추가. 성공도합성PARTIAL/readyfalse·실회사인수/전체revocations/completeness=false. unsigned보고서는제품ACCEPTANCE등록용아님. 실행범위/소스지문/DB버전/소유자원/실행기신뢰경계는이전과동일하다.

검증: 단위141통과0.32초(기존경고2). 소유컨테이너ID/owner/55439대조후새소유DB의실수집CLI23PASSED·PARTIAL/exit0·sourceUnchanged/databaseCleaned=true·합성복원거부통과. collectorDB0/closedRestoreDB0확인·previewDB/서비스유지. Ruffcheck/format·정적DB219/2409/543·R1–R6/diff오류0. 전체CI/브라우저/UI/실외부/실회사·기기/10인인수 미실행. schema불변·Excel/ERD재생성없음. 비밀/work/전체로그 스테이징없음·다른checkout/main/원격push/배포변경없음.

전체02진행중·readyfalse/미확인4유지. 다음: 최종서명인수증거계약/현재회사·세대·정책·제품/DB·실행번호/최신원본대조를연결하되 합성보고서를실회사PASS로승격하지않는경계구현 → 기존GW UI구성보완 → 최신main/전체회귀·10인실인수/실외부저장소·최종전환. 나머지HR/ACL조합·직접SQL/운영자통제·장기성능/시간동기/전경로무누락은여전히미확인. 다음난이도매우높음·GPT-6 Astra + High 추천(서명/최신성/인수범위·완료판정의신뢰경계), GPT-6.1 Sol + High 대안. 모델자동변경없음.

재현:33차단위명령그대로(141). 소유로컬PG postgres관리연결FS_GW_ROUTE_VERIFY_ADMIN_URL·GW_BACKUP_TEST_CONTAINER·FS_GW_ROUTE_VERIFY_OWNER 주입후 `uv run --project backend python tools/gw_route_verify.py --report <0700폴더의새파일.json>` (고정23). 새DB만생성/정리·preview초기화금지. 마지막커밋git log -1.

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


## 44차 — 기존 격리 복원본 재관측과 인수 진단v4 (2026-10-23)

- 기존 복원 도구에 읽기 전용 `recheck-restore`를 추가했다. 원본 암호화 백업/권한 대조/서명 HEAD/RESTORE 관측을 대조하고, 새 READ ONLY/REPEATABLE READ 거래에서 같은 물리 복원본의 제한·세션·인증 요청·공개 접속/접속수 제한을 다시 읽는다. 다른 물리 DB·다른 명세/지문은 거부한다. 새 DB 생성·제한 변경·연결 개방·일반 DATABASE_URL 대체는 없다.
- 명시적 회사/RESTORE_RECHECK 용도의 키로 새 관측을 서명한다. 최대15분/미래30초, 원본 전체 지문·백업/권한 대조 실행과 대상 물리 식별을 묶는다. 측정 불가는 measurement=null/targetMeasured=false/BLOCKED이며 0건으로 추정하지 않는다. 제한 위반은 BLOCKED, 제한 대조가 명확해도 PARTIAL이다. 상태 지문 불일치와 제한 위반을 구분한다. 회사 전체 회수·실회사·최종 전환/ready는 false다.
- 현재 DB 수집기 `--restore-recheck`가 관측을 기존 ACCEPTANCE 진단v4에 연결한다. 변경 기록 관측도 함께 보존할 수 있다. 별도 ACCEPTANCE 발급 키와 최신 BACKUP/RESTORE 원본/현재 정책·버전을 다시 대조한다. 서버는 관측 서명/현재 원본을 검증하며 복원본 자격정보를 보유하거나 직접/연속 조회하지 않는다. 단독 재관측 문서는 API400이다. 성공 부분은 PARTIAL, 위반/측정 불가는 FAIL이며 PASS는 여전히 거부한다.
- 새 등록에서는 기존 관측 유형을 생략할 수 없다. 실패/다른 정책/원본 없는 이력까지 조회하며 최신 ACCEPTANCE 등록 이후 관측만 받는다. 시계 허용 범위에서 같은 관측을 반복 등록하지 못하도록 두 관측 유형 모두 실행 번호 재사용도 거부한다. 미등록 파일 전체의 최신성을 보증하지 않는다. 백업 DB 시각과 복원 실행자 시각 비교는 기존 복원 계약과 같은30초로 제한했고31초 거부 경계를 추가했다.
- 기존 운영 준비의 실행 증거 영역에 최근 복원본 관측 시각·잔여 항목·격리 제한·측정 불가·지문 변화/다음 조치를 펼쳐 보도록 보완했다. 기존 업무/회사/관리 맥락과 정적 도움말을 유지한다. UI 전체 완성이나 실제 브라우저 인수로 표현하지 않는다. `admin` 로그인 이름만으로 GW 보안/발급 권한을 부여하지 않는다.
- 검증 결과와 재현 명령은 같은 날짜 `docs/progress.md`·`docs/agent/HANDOFF.md` 최신 기록을 따른다. 스키마/마이그레이션/Excel/ERD 변경 없음. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED 유지. 외부 공급자/외부 장애복구·최신 권한 대조 이후 미수집 변경의 완전성/전체 회수·실회사10인/최종 운영 전환·main/전체회귀는 남아 있다.
- 다음: 원래 복원에 사용한 권한 대조 이후의 새 변경을 감지하는 현재 원본/최신 체크포인트 대조 계약을 구현한다. 이후 외부 공급자 선정과 나머지 최종 인수 증거·통합/전체회귀·실회사10인 인수로 진행한다. 난이도 매우 높음, GPT-6 Astra + High 추천. 모델 자동 변경 없음.


## 45차 — 현재 원본과 복원 당시 권한 대조 비교 (2026-10-23)

- 기존 `recheck-restore --check-current-source`에 전용 원본 읽기 접속을 연결했다. 물리 원본을 먼저 확인하고 단일 READ ONLY/REPEATABLE READ 거래에서 회사/세대/정책·DB head와 기존 core/GW/HR 수집 항목을 다시 읽어 정규화 지문/변경 묶음을 비교한다. 같은 백업의 다른 공간 변경도 포함할 수 있다. raw 계정/권한/자격 원문은 요약에 넣지 않는다.
- RESTORE_RECHECK v2는 원본 관측과 기존 복원본 제한 관측을 같은 서명에 담고 기존 ACCEPTANCE 진단v4에 연결한다. 원본 수집 항목/현재 기준이 달라지거나 측정 불가이면 복원본이 정상이어도 BLOCKED→FAIL이다. null을0으로 추정하지 않는다. 일치도 PARTIAL이며 ready/전체 회수/실회사/최종 전환은 false다. 15분/미래30초·관측 간30초·물리 원본/대상·원본/파일 지문·기존 키 용도 분리를 유지한다.
- 원본 비교를 등록한 S에서는 새 인수에 원본 비교를 생략하거나 이전 관측 형식으로 되돌릴 수 없다. 최신 등록 이후 원본 관측·기존 실행 재사용/유형 생략 금지를 서버에서도 검사한다. 새 체크포인트를 옛 복원 증거와 섞지 않는다. 새로운 체크포인트/복원/재관측으로 원인을 해결하는 흐름 보완은 다음 작업이다.
- 기존 운영 준비의 재관측 펼침에 현재 원본 시각/변경 묶음/측정 불가/다음 조치를 추가하고 도움말·실회사 절차 §19를 갱신했다. 중간 변경 후 원복·미수집 경로/전체 회수 완전성·외부 HEAD의 독립 최신성·실행 바이너리·연속 감시를 증명하지 않는다. admin 이름으로 권한을 부여하지 않는다. UI 전체 완성 주장은 하지 않는다.
- 단위431·화면/정적 도움말37·타입/수정 린트·포맷·정적DB/R1–R6 통과. 새 소유 PostgreSQL 기존 관련15통과·새 실제 복원/원본 비교·API/CLI/읽기 쓰기 거부 시나리오 최종1통과18.50초. 제품 React+합성 API1440/390 본문/키보드/넘침0 확인. 상세 실패/보정·미실행·재현은 최신 progress/HANDOFF를 따른다. 전체CI/전체회귀·실외부/실회사10인 인수는 아니다. 새 스키마/마이그레이션/Excel/ERD 없음. ready=false/실제 복원PARTIAL/최종4조건 미확인 유지. main/push/배포 없음.


## 46차 — 원본 변경 실패 이후 새 대조·격리 복원·후속 인수 (2026-10-23)

- 기존 원본 변경 FAIL 이력을 기준으로 새 PARTIAL 인수의 복구 조건을 연결했다. 역사 인수/내부 재관측 서명·현재 회사/용도 권한과 등록 원본/집계/메타데이터를 대조한다. 원문/관측이 없거나 변조/키 회수이면 새 백업부터 요구하며 과거 실패를 현재 정책/버전/관측 통과로 쓰지 않는다.
- 실패 등록 이후 다른 RESTORE 실행/물리 대상과 다른 checkpoint 실행/파일 지문을 요구한다. 원본 상태를 되돌리거나 같은 대조로 새 대상만 만든 결과로 과거 실패를 숨길 수 없다. 최신 서명 원본/현재 기준·새 원본 MATCH/복원본 관측·기존 유형 유지/실행 재사용 금지는 그대로다. 수집기·잠금 안의 API 등록·준비 재조회에서 적용하며 반복 FAIL은 기록하고 새 PARTIAL만 제한한다. 새 스키마/서명 종류·수동 완료 체크는 없다.
- 기존 화면에 원본 변경 후 재점검4상태/조치/기준 실패 시각/접힌 순서·도움말을 연결했다. 조건 불충족은 OPERATING_RECOVERY_REQUIRED/400과 안전한 조치를 보여 주고 수집기는 종료1/새 출력 없음이다. 이전 실패 행은 유지하며 후속 일부 확인도 ready=false/전체 회수/실회사/최종 전환 미확인을 유지한다. 직관성·유효성·학습성·유연성과 기존 회사/업무 관리 맥락을 따른다. UI 전체 완성은 아니다.
- 단위448·화면/도움말41·타입/수정 린트/포맷·정적DB/R1–R6 통과. 새 소유 PostgreSQL의 실제 복원/복구2+기존 원본 비교1, 최종3통과74.50초. 원문 정상/없음·원복/대상/대조 재사용·수집기/API/실CLI·새 대조/새 복원/재관측→PARTIAL·실패 보존·이후 최신 복원 FAIL 선택을 확인했다(마지막 FAIL은 합성 서명 자료이며 실제 도구의 실패 측정 실행은 아님). 제품 React+합성 API1440/390 본문·PC 키보드/44px·넘침0 확인. 실제 API 브라우저/실회사10인·전체CI/전체회귀는 아니다. 상세 실패/보정·미실행/자원·재현은 최신 progress/HANDOFF를 따른다.
- 다음은 체크포인트 생성 시각·최신 HEAD 독립 증거 연결이다. 현재 대조는 다른 대조 실행/파일과 실패 이후 새 복원 시작이며 생성 시각/별도 최신 목록·실행 바이너리/연속 관측 증명은 아니다. 외부 공급자 미정/외부 장애복구·전체 수집/회수·최종 인수 계약·main/전체회귀·실회사10인/최종전환은 후속이다. 실제 복원PARTIAL/ready=false/최종4조건 UNVERIFIED 유지. 스키마/Excel/ERD·실계정/미리보기 데이터·main/push/배포 변경 없음.


## 47차 — 권한 대조 생성 시각·서명 HEAD의 인수 연결 (2026-10-24)

- 기존 `recheck-restore --check-current-source`가 RESTORE_RECHECK v3에 원본 서명 CHECKPOINT_HEAD를 포함한다. 현재 회사/CHECKPOINT 용도와 기존 명세 서명 문맥, 회사/세대/정책·백업/대조 실행·암호화 파일 지문·복원 시작/RPO와 생성 시각을 대조한다. 별도 RESTORE_RECHECK/ACCEPTANCE 권한 대조도 유지한다. 새 서명 종류/DB 테이블 없이 기존 진단v4에 연결한다. 원본 비교 없는 실행은 v1이며 구형 v1/v2·RESTORE 원본의 바이트/지문을 바꾸지 않는다.
- 원본 변경 실패 이후 새 PARTIAL에는 서명된 대조 생성 시각도 실패 등록보다 엄격히 뒤여야 한다. 실패 전 다른 대조를 새 물리 대상에 복원해도 수집기/회사 잠금 안 등록/준비 재조회가 거부한다. v3 등록 이력 뒤 HEAD 생략/구형 형식 역행도 모든 정책/실패/원문 없는 이력을 포함해 거부한다. 현재 HEAD 키의 CHECKPOINT 용도 회수는 기존 인수도 INVALID로 만든다. 실패와 PARTIAL·최신 원본 선택은 과거 성공으로 대체하지 않는다.
- 기존 재관측 펼침 안의 **복원 권한 대조 생성 근거**에서 검증한 생성 시각과 독립 최신 목록 미확인을 구분했다. 기존 회사/업무 동선·44px/키보드·모바일과 정적 도움말을 유지하며 UI 전체 완성은 아니다. admin 아이디는 회사 연결/보안/발급 권한을 대신하지 않는다. 운영 절차는 §21을 따른다.
- 검증의 최종 건수/실패·보정·미실행/자원과 표준 재현 명령은 최신 progress/HANDOFF를 따른다. 생성 시각은 허가된 실행자의 서명 주장과 특정 파일의 연결이다. 공인 시각/별도 운영자·장애 영역·불변 최신 목록/삭제 탐지·연속 관측·실행 바이너리 증명은 아니다. 외부 공급자는 미정이며 독립 최신 HEAD 목록 대조 어댑터가 다음 작업이다.
- ready=false/실제 복원 PARTIAL/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부를 유지한다. 전체 변경 수집/회수·최종 인수 계약·공급자 선정 후 외부 장애복구·최신main/전체회귀·실회사10인/최종전환은 남아 있다. 스키마/마이그레이션/Excel/ERD·실계정/미리보기 데이터·main/push/배포 변경 없음.


## 48차 — 별도 서명 목록의 현재 HEAD 읽기 대조 (2026-10-24)

- 운영자 설정의 `SIGNED_SNAPSHOT_FILE`을 읽는 공통 어댑터를 추가했다. 공급자는 미정이며 외부 연결을 임의 선정하지 않았다. 별도 CHECKPOINT_CATALOG 전용 키/회사 권한, 고정 목록 식별자/파일 SHA-256·0600/0700/소유자·링크/중복 JSON/크기/서명/15분·미래30초를 검사한다. 이 키는 다른 용도/같은 공개키 별칭을 혼용할 수 없다. 경로/신뢰 핀은 업로드 문서나 선택 HEAD가 결정하지 않는다. 발행·불변 교체/원격 전달 도구는 후속이다.
- 기존 `recheck-restore --check-current-source --check-checkpoint-catalog`는 원본/복원 관측과 HEAD·목록 대조를 RESTORE_RECHECK v4에 담고 기존 ACCEPTANCE 진단v4에 연결한다. 설정이 있으면 대조를 생략할 수 없다. 회사/세대의 최신 번호를 모든 결과/기준/원문 유무에서 선택하며 실패/일부/누락/옛 기준/HEAD 불일치는 BLOCKED→FAIL이다. 일치도 PARTIAL, 파일/서명/핀 오류는 새 출력 없이 오류다. 전체 목록/다른 회사·경로/비밀을 인수 증거에 넣지 않는다.
- 수집기·잠금 안 등록·준비 재조회에서 현재 목록을 다시 읽는다. 등록 이력의 식별자/버전/기록 번호·HEAD/생성 시각 바닥값으로 목록 리셋·후퇴/동일 번호 변경·형식 생략을 거부한다. 실패/옛 정책/원문 없는 이력도 포함한다. 등록된 목록 대조 미통과 이후에는 실패 등록 이후 생성한 새 대조·격리 복원을 요구하며 번호만 높인 옛 성공으로 복구할 수 없다. 기록 자체 손상은 차단하고 초기화로 우회하지 않는다.
- 기존 재관측 펼침에 별도 서명 목록의 관측/버전/최신 번호·7개 결과/조치와 실제 외부 보관 미확인을 표시했다. 현재 대조가 무효이면 상세를 숨긴다. 기존 회사·업무 관리 맥락/정적 도움말을 유지하며 admin 이름은 회사/보안/서명 권한을 대신하지 않는다. UI 전체 완성은 아니다.
- 최종 검사·실패/보정·자원·재현은 최신 progress/HANDOFF를 따른다. 목록 자료는 별도 시험 키의 합성 서명이며 실제 백업/dump/암호화/격리복원과 구분한다. 이 공통 어댑터만으로 외부 최신성/발행자의 누락·물리 독립성/전체 이력을 증명하지 않는다. 외부 보관/전체 회수/실회사/최종전환4조건 UNVERIFIED·실제 복원 PARTIAL·ready=false/ACCEPTANCE PASS 거부 유지. 새 스키마/마이그레이션/Excel/ERD·실계정/미리보기 DB/정책·main/push/배포 변경 없음. 다음은 목록 발행·불변 교체/신뢰 핀 전달 도구와 그 실패 검증이며 이후 최종 인수 계약·공급자별 외부 장애복구·main/전체회귀·실회사10인이다.

## 49차 — 로컬 목록 발행·원자 핀 교체와 중단 차단 (2026-10-24)

- 기존 v1 목록/RESTORE_RECHECK v4·인수 계약에 `catalog_store`와 `gw_checkpoint_catalog.py publish/refresh/status/recover-pending`를 연결했다. 회사/세대 전용0700 폴더·별도 회사/CHECKPOINT_CATALOG 키, 현재 정책/버전 문맥, 서명 HEAD와 실제 암호화 파일 전체 지문을 검사한다. 입력 대조 통과만 목록 PASS이며 원본 검증 실패는 새 FAIL·원문 null이다. ACCEPTANCE PASS/운영 승인이 아니다.
- O_EXCL0600 새 지문 파일/fsync·지속 잠금/예상 핀 CAS·보류 의도 선기록·원자 핀 교체/폴더 fsync를 사용한다. 과거 파일/실패/불완전 스냅샷을 덮거나 지우지 않는다. 현재 스냅샷은 최신 기록 하나이며 이전 스냅샷은 보존한다. 갱신은 항목 번호/시각/결과/기준을 그대로 유지한다. 중단 복구는 높은 새 버전의 PARTIAL·원문 null이며 미완료 PASS를 활성화하지 않는다. 실패/PARTIAL 이후 옛 HEAD 재발행은 새 FAIL이다.
- `FS_GW_CHECKPOINT_CATALOG_PIN_FILE`은 고정 current-pin.json과 같은 폴더 스냅샷을 읽는다. 기존 JSON 모드와 양립 불가·빈 값/권한·링크/하드링크·현재 서명/기한·보류/최고 저장 버전·읽기 중 핀 교체를 검사한다. 현재 목록 변경은 기존 인수 상세를 INVALID로 만든다. 개인키/접속 정보/전체 문서는 출력하지 않는다. status는 핀/보류 진단이며 운영 준비나 신선도 승인이 아니다.
- 실회사 절차 §23/정적 도움말에 담당자 준비·지문 구별/종료 코드·중단 복구/현재 기준 재점검을 설명했다. 기존 GW UI 구조/권한은 그대로다. 직관성(이전 성공 대신 현재 차단), 유효성(실제 파일/원본 재대조), 학습성(FAIL/PARTIAL/인수 경계), 유연성(기존 정적 모드와 명시적 관리 모드)을 고려했다. 화면 전체 완성은 아니다.
- 별도 수신 계정/원격 전달·신뢰 기준점 전달/순차 설치·누락 버전 따라잡기, 외부 공급자/물리 독립성·발행자의 누락/악의·전 경로 회수/최종 인수는 후속이다. 스키마/마이그레이션·metadata/Excel/ERD 변경 없음. 미리보기/실계정·다른 checkout/WMS·main/push/배포 변경 없음. 실제 복원 PARTIAL/ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 최종 검증/실패 보정·재현은 최신 progress/HANDOFF를 따른다.

## 50차 — 별도 수신 기준점·연속 버전 전달/보류 재시도 (2026-10-24)

- `catalog_transfer`와 `gw_checkpoint_transfer.py export/install`을 기존 v1 목록/관리 핀에 연결했다. 발행자 현재 핀과 수신자 revision/catalogDigest 기준점 사이의 보존 스냅샷 전부를 전달한다. 원본 서명/개행/전체 바이트를 유지하며 별도로 확인한 catalogId/묶음 전체 지문과 현재 회사별 서명 권한을 함께 검증한다. 수신에는 발행 개인키가 필요 없다. 새 운영 증거/스키마/서명 종류·자동 서버 설정은 없다.
- 수신자 전용 식별자/회사·세대/최초 지문·현재 핀 CAS와 발행/수신 역할을 구분한다. 연속 revision/기록번호, 갱신 시 전체 기록 동일성, 시각/HEAD 비후퇴, 실패 이후 새 생성 시각, 같은 버전의 다른 바이트/과거 이력 충돌을 검사한다. FAIL/PARTIAL/옛 기준을 그대로 보존한다. status에 catalogDigest도 제공해 pinDigest와 구별한다.
- 확인된 새 전달 지문과 현재 기준점을 본문 검증 전 보류 기록으로 fsync한다. 파일 누락/변조·서명/중간 이력/기한/기준점 오류에도 이전 성공 읽기를 차단한다. 완성 임시 파일/fsync→배타적 링크로 각 스냅샷 게시→최종 핀 한 번 원자 교체/fsync→보류 제거 순서다. 같은 원본만 명시 재시도하며 완료 응답 유실도 동일 바이트를 재대조한다. 보류 원본 만료 시 같은 유효 원본의 이력 완료만 허용하고 targetFresh=false/종료2·현재 읽기 차단을 유지한 채 새 전달을 요구한다. 자체 링크 직후 중단/부분 임시 쓰기·잘못된 재시도/경합을 검사한다. 불완전 파일/실패/옛 원문을 덮거나 지우지 않는다. 다른 묶음이나 서명 PARTIAL로 수신 보류를 임의 초기화하지 않는다.
- 1회256스냅샷/8MiB 안에서 보존된 미수신 버전을 따라잡는 범위다. 발행 중단으로 생긴 예약 번호 공백·발행 원본 유실/손상·과거 키 회수는 자동으로 건너뛰지 않는다. 공백 복구 근거/키 이관·큰 이력 분할/장기 보관은 후속이다. 각 서명/연속 번호 대조이며 기존 v1을 과거 해시가 연결된 서명 체인으로 바꾼 것이 아니다. OS/장애 영역·사람의 독립성/원격 전송·연속 관측은 증명하지 않는다.
- 실회사 절차 §24/정적 도움말에 지문/종료 코드·미수신 따라잡기·보류/재시도·원본 유실 경계를 설명했다. 직관성(확인된 새 전달 실패 시 이전 상세 숨김), 유효성(모든 원본/현재 권한 대조), 학습성(전달/인수 경계), 유연성(기존 읽기/수집·오프라인 공개키 수신)을 고려했다. 기존 제품 UI 코드는 수정하지 않았으며 UI 전체 완성이라고 표현하지 않는다. admin 이름은 발행/회사 보안 권한을 대신하지 않는다.
- 최종 검사·재현·실패/보정은 최신 progress/HANDOFF를 따른다. 실제 복원 PARTIAL·ready=false·최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 새 스키마/metadata·Excel/ERD·실계정/브라우저/미리보기·다른 checkout/WMS·main/push/배포 변경 없음. 공급자는 미정이며 실제 외부 저장소/실회사10인·최종 인수는 미완료다.

## 51차 — 발행 공백의 서명 복구 근거·수신 기준점 연결 (2026-10-24)

- 기존 recover-pending이 서명 recoveryProof를 포함한 CHECKPOINT_CATALOG v2를 발행한다. 일반 v1/기존 서명 바이트와 핀 형식은 유지한다. 별도 복구 서명 문맥·현재 회사/CHECKPOINT_CATALOG 단독 용도, 직전 목록 전체 지문/버전·번호, 원래 보류 intent/예약 관계, 새 PARTIAL 기록 전체 지문/시각, 공백마다 실제 남은 파일의 기대/실제 지문·크기 또는 원본 없음 상태를 함께 묶는다. 새 스키마/운영 증거 종류·발급 권한은 없다. 새 복구도 PARTIAL/head=null이며 refresh가 근거/기록을 바꾸지 않는다.
- 전달 묶음 v2의 artifacts는 공백에 남은 0바이트/잘린/미활성 완성 원본을 실제 바이트 그대로 보존한다. snapshots로 추정/재분류하지 않는다. 실제 직전 수신 지문/버전/번호가 복구 base에 맞을 때만 연결하고, 원본 누락/변조/등장·추가/중복·같은 버전 분기/형식 낮춤·공백 안 기준점은 거부한다. 재복구 중단/핀 교체 후 중단·같은 원본 수신 재시도도 기존 보류/원자 교체 흐름을 유지한다. 기존의 일반 공백은 서명 근거 없이 허용하지 않는다.
- 실제PG에서 실제 dump/암호화/폐쇄 복원→발행 중단/8바이트 원본→서명 복구·수신 PARTIAL→기존 인수 INVALID/새 ACCEPTANCE FAIL→실패 후 새 대조·새 폐쇄 복원→현재 관측/후속 PARTIAL, 이전 실패/원본 보존을 확인했다. 최신 실패/누락/변조/옛 기준을 과거 성공으로 대신하지 않는다. 실제 복원은 계속 PARTIAL/ready=false·최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부다.
- 실회사 절차 §25/정적 도움말은 공백의 의미·새 대조/격리 복원·남은 제한을 설명한다. 직관성(현재 일부/미통과 유지), 유효성(실제 기준점/원본 대조), 학습성(서명 복구와 인수의 경계), 유연성(기존 명령/일반v1·복구v2/재시도)을 고려했다. UI 제품 코드/전체 화면 완성은 이번 범위가 아니다. admin 로그인 이름은 회사/보안/서명 권한을 대신하지 않는다.
- 복구256슬롯/각2MiB·전달256스냅샷/256원본·총8MiB로 제한한다. 큰 이력 분할/키 이관·이미 잃은 과거 v1 보류/손상 기준점/근거 없는 유실 복구는 후속이며 자동 리셋하지 않는다. 서명은 발행자가 확인한 완료 불명 근거이고 물리 미공개/공인 시각/전체 무누락/사람·장애 영역 독립성 증명이 아니다. 실제 외부 공급자는 미정이다. 최종 검사/실패 보정/재현은 최신 progress/HANDOFF를 따른다. 스키마/metadata·Excel/ERD·실계정/브라우저/미리보기·다른 checkout/WMS·main/push/배포 변경 없음.

## 52차 — 큰 목록 이력의 분할 전달·수신 진행점 복구 (2026-10-25)

- `catalog_segments`와 `gw_checkpoint_segments.py export/receive/status`를 추가했다. 기존256개/8MiB 단일 묶음 형식은 유지한다. 분할은 각 실제 원본 최대2MiB·8192개/manifest2MiB 중 먼저 도달하는 제한이며 원본 전체를 메모리에 합치지 않는다. 새 인수 서명/스키마 없이 별도 확인한 manifest 전체 지문·목록 ID가 최종 목록/기준점·순서·정상/불완전 원본의 기대/실제 지문·크기를 묶는다. 각 기존 회사/용도 서명은 현재 키 권한으로 다시 검사한다.
- 본문 검증 전에 CAS/회사·기존 수신 역할을 확인하고 보류를 선기록한다. 조각은 완성 임시 파일/배타적 링크로만 보존하며 중간 단계는 RECEIVING/ready=false다. 저장 파일의 형태/이름/크기에서 진행점을 복구하되 저장 수를 전체 검증 수로 보지 않는다. 최종에 모든 실제 바이트/서명·현재 권한·정확한 연속 이력/복구 근거·실제 기준점을 재검증한 뒤에만 한 번 원자 핀 교체/보류 해제를 한다. 그전에는 기존 API도 과거 성공을 읽지 못한다. status는 읽기 전용이며 핀 교체 전 완료 대기는 AWAITING_FINALIZE/sourceResult다. 같은 보존 명세·원본/현재 핀의 재시도만 허용한다.
- 실패/일부·옛 정책/버전/원문 없음·변조/공백/회수된 키를 과거 성공으로 대체하지 않는다. 보류 중 만료된 같은 원본은 이력만 마치고 targetFresh=false/종료2이며 현재 읽기는 STALE다. 미래30초 초과는 계속 차단한다. 일반 PASS도 현재 기준 일치/신선도 없으면 종료0이 아니며 모든 결과는 ready=false다. admin 이름은 키/회사 권한을 대신하지 않는다. 절차 §26·정적 도움말을 갱신했으며 UI 제품 코드/브라우저 전체 완성 작업은 아니다.
- 다음은 과거 서명 키의 안전한 이관 계약/실행·현재 권한 회수 경계다. 공급자 선정 후 실제 외부 장애 복구, 최종 인수 계약/전체 변경 수집·회수, 최신main/전체회귀·실회사10인/최종전환은 남는다. 실제 복원 PARTIAL·최종4조건 UNVERIFIED·ready=false/ACCEPTANCE PASS 거부를 유지한다. 최대8192개/최대 용량 성능·장기 보관과 실제 원격 전송/독립성은 미검증이다.
- 검증: 관련 단위703(새41)·화면/정적 도움말48·타입/Ruff/정적DB219/2409/543·R1–R6 오류0, 별도 소유 PostgreSQL 실제 dump/암호화/폐쇄 복원·분할 수신/보류/API 인수 재조회 포함7통과124.70초. 상세 실패 보정·경계/재현은 최신 progress/HANDOFF를 따른다. 시험 자원0/미리보기 DB보존. 실환경 인수/전체CI·회귀/브라우저 재검증·main/push/배포는 미실행이다.

## 53차 — 목록 키 정상 교체의 정확한 과거 원본 허용·현재 회수 우선 (2026-10-25)

- `catalog_key_handover`/`gw_catalog_key_handover.py issue/inspect`를 추가했다. 기존·새 회사별 CHECKPOINT_CATALOG 단독 활성 키가 전체 보존 원본/복구 구간을 대조하고 역할별 이중 서명으로 정확한 원본 목록/복구 근거 지문·현재 캡처 메타데이터를 묶는다. 기존 목록/복구 원본 바이트·서명 문맥/단일·분할 전달 형식은 유지한다. 운영자가 별도 확인한 파일/전체 지문·원래 공개키/회사와 RETIRED/REVOKED 상태는 서버 소유 FS_GW_CATALOG_KEY_LIFECYCLE 설정으로만 받는다. 자동 신뢰 설치/키 생성·삭제/배포는 없다.
- 정상 RETIRED는 같은 회사/세대·목록 ID의 정확한 과거 바이트·버전/캡처 기록번호·지문과 안쪽 복구 근거만 허용한다. 현재 바깥 서명·새 발행/이관은 계속 활성 키를 요구한다. 수신의 실제 옛 기준점/중간 이력만 제한적으로 검증하고 최종은 활성 키여야 한다. 새/소급 서명·같은 버전 분기·다른 범위/추가 원본·메타데이터 불일치와 현재 REVOKED는 차단한다. 남은 활성 공개키·옛 이관 자료로 회수를 우회하지 않는다. HEAD/백업·복원/재관측·인수 키의 기존 권한은 확장하지 않는다.
- 현재 이관 파일/서명·핀/권한 오류는 안전한 구성 오류로 처리해 화면 CONFIG_REQUIRED/ready=false를 유지한다. 키 회수/현재 목록 대조 실패는 INVALID/차단이며 과거 성공을 대신하지 않는다. 기존 실패 이후 새 권한 대조·폐쇄 복원/현재 인수 규칙과 PARTIAL/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부를 유지한다. admin 이름은 회사/서명 권한을 대신하지 않는다. 실회사 절차 §27·정적 도움말을 갱신했으며 제품 UI 전체 완성 작업은 아니다.
- 범위는 **활성 새 키가 직접 확인하는 최초 한 단계 목록 키 교체**다. 여러 차례 이관/더 오래된 개인키 없이 재승인하는 연결은 후속이다. 승인자가 회수/재은퇴하면 자동 연쇄 신뢰 없이 차단한다. 현재 회수 우선 검증은 서버 설정 자체의 악의/롤백을 막는 독립 영구 회수 원장/WORM 증명이 아니다. REVOKED를 RETIRED로 되돌리는 복구 도구/절차는 제공하지 않는다. 실환경 설치·외부 저장소/독립성·키 삭제/최대 성능·최신main/전체회귀·10인 인수는 미실행이다.
- 검증: 관련 단위761(신규58)·화면/정적 도움말48·타입/Ruff/정적DB219/2409/543·R1–R6 오류0, 별도 소유 PostgreSQL 실제 dump/암호화/폐쇄 복원·이관/옛 키 제거/분할 수신·인수 재조회 포함8통과144.45초, 최종 보강 변형 별도1통과25.20초(중복 합산 없음). 상세 실패 보정·재현은 최신 progress/HANDOFF를 따른다. 생성 시험 자원0/미리보기 DB보존. 전체CI·회귀/실환경 인수·브라우저 재검증·main/push/배포는 미실행이다.

## 54차 — 여러 차례 목록 키 교체의 정확한 이관 연결 (2026-10-25)

- `catalog_key_chain`과 기존 `gw_catalog_key_handover.py extend`를 추가했다. 현재 운영자 설정에 고정된 은퇴 키 승인 파일을 원래 바이트/전체 지문 그대로 포함하고, 현재 키/다음 키가 별도 문맥·역할로 서명한다. 원래 허용한 목록/복구 원본·시각은 넓히지 않는다. 더 오래된 개인키는 필요 없으며 현재/다음 개인키로만 연결을 만든다. 한 단계 원래 자료/설정v1·목록/복구·전달 형식과 admin 이름/회사 권한은 유지한다.
- 중간 키의 현재 RETIRED/공개키는 서버 소유 설정에서만 읽고 마지막 키는 현재 회사의 단독 활성 권한을 요구한다. 모든 역할 서명/부모 지문/최초 이관·회사/세대·목록, 증가하는 캡처 버전/후퇴하지 않는 번호·시각/같은 번호의 기록 지문, 중간 키 자신의 원래 이관 전체 지문·직접 다음 키·실제 캡처를 교차 대조한다. 원본 목록/복구 지문도 현재 발행자가 서명한 전체 보존 원본과 정확히 같아야 한다. 회수/누락/분기·순환·옛 승인자 재생·미승인 부모·소급/누락/추가 원본을 거부한다.
- 단일/분할 수신·보류·현재 바깥 활성 키/최종 전체 재검증과 실제 인수 실패 이후 새 대조/폐쇄 복원 규칙은 유지한다. 잘못된 연결/현재 회수는 CONFIG_REQUIRED/INVALID·ready=false이며 과거 성공으로 대신하지 않는다. 실회사 절차 §28·정적 도움말을 갱신했다. 실제 복원 PARTIAL/최종4조건 UNVERIFIED/ACCEPTANCE PASS 거부를 유지하며 제품 UI 전체 완성 작업은 아니다.
- 최초 이관 포함8연결·각 파일2MiB/펼친 누적8MiB와 기존 승인20파일/설정·원본 한도 중 먼저 도달한 제한에서 차단한다. 최대8 이후 압축/새 신뢰 기준 전환과 최대 용량/장기 성능은 별도다. 독립 영구 회수 원장/설정 자체 롤백 방지·외부 독립 인수/실환경 키 삭제·최신main/전체회귀·실회사10인/최종전환은 미완료다. 실제 환경/키/계정/브라우저·다른 checkout/WMS·main/push/배포를 변경하지 않았다.
- 검증: 관련 단위823(신규62)·화면/정적 도움말48·타입/Ruff/정적DB219/2409/543·R1–R6 오류0, 별도 소유 PostgreSQL 실제 dump/암호화/폐쇄 복원·두 번째 이관/옛 시험 키 파일 제거·분할 수신/인수 재조회 포함9통과170.90초, 보강 변형 별도1통과26.36초(중복 합산 없음). 최종 화면 worker 시작시간초과는 작업자1 재실행48통과로 확인했다. 상세/재현은 최신 progress/HANDOFF를 따른다. 생성 시험 자원0/미리보기DB 보존. 전체CI·회귀/실환경 인수·브라우저 재검증·main/push/배포는 미실행이다.

## 55차 — 목록 신뢰 상태의 로컬 영구 이력·설정 후퇴 차단 (2026-10-25)

- `catalog_trust_store`/`gw_catalog_trust.py initialize/advance/revoke/status/resume`을 추가했다. 별도 운영자 소유 보존 폴더에 회사별 ACTIVE/RETIRED/REVOKED·키 ID/공개키 지문·정확한 승인 원본부터 현재까지 지문 경로, 원장 UUID/연속 버전/직전 파일 지문을 새 파일로 보존한다. 현재 기준점과 모든 보존 원본을 읽을 때 다시 검사한다. 목록/복구/이관·전달의 기존 서명 형식과 업무 DB 스키마는 바꾸지 않는다.
- 목록 권한/수명 상태가 있는 환경 로더는 보존 경로/현재 이력을 필수로 요구한다. 경로 제거/비어 있는 폴더·누락/변조/옛 설정·같은 최초 이관의 분기/옛 승인·권한 삭제/재활성화·ID/공개키 별칭/목적 전용은 CONFIG_REQUIRED/명령 차단·ready=false다. 다른 키 종류의 기존 권한을 넓히지 않는다. admin 로그인 이름도 회사/OS/서명 권한을 대신하지 않는다.
- 회수는 명시 revoke로 먼저 보존하며 과거 현재 설정도 즉시 불일치로 차단한다. 개인키나 정상인 현재 연결 없이 이미 보존한 정확한 회사/키를 회수할 수 있다. REVOKED→RETIRED/ACTIVE·원장 삭제/초기화 도구는 없다. 변경은 CAS·배타 잠금, 새 원본/fsync→보류 기준점/fsync→원자 교체/fsync 순서다. 중단 시 이전 성공을 읽지 않고 완성 원본의 별도 확인 지문/정확한 직전 기준점으로만 resume한다. 잘린/없는 원본은 재생성하지 않는다.
- 최대4096기록/각256KiB·2100회사-키와 기존 설정/승인 한도를 적용한다. 같은 OS 계정의 **로컬 보존 어댑터**이며 경로 자체를 새 원장으로 바꾸거나 원본/현재 기준점·설정을 모두 함께 롤백하는 공격·전체 유실을 독립 탐지하지 못한다. 외부 독립 최신 지문/원장·장애 영역/WORM·정확한 유실 원본 복구·최대 용량/장기 성능은 후속이다. 서버 환경/실계정·미리보기·실키는 설치/변경하지 않았다.
- 실회사 절차 §29/정적 도움말을 갱신했다. 직관성(보존 불일치 시 점검 보류), 유효성(현재 기준점/모든 원본·단조 상태/연결 대조), 학습성(정상 교체와 먼저 기록하는 회수 순서), 유연성(기존 공개키 도구/다중 교체·완성 중단 재개)을 고려했다. UI 제품 코드/실브라우저 전체 완성은 이번 범위가 아니다. 실제 복원 PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지. 최종 검사/실패 보정·재현은 최신 progress/HANDOFF에 기록한다.
- 최종 검증: 관련 단위864(신규41)·화면/도움말48·타입/Ruff/정적DB219/2409/543·R1–R6 오류0, 별도 소유 실제PG9통과178.40초. 초기 중단 재개 참조 오류/기존 구성 차단 기대값 보정 뒤 재실행했다. 시험 생성DB/폐쇄 복원DB0·미리보기 DB보존. 다음은 이력 내보내기/별도 최신 지문 고정 수신·원본 복구다. 전체CI·회귀/실외부·10인/브라우저 재검증/main/push/배포는 미실행이다.

## 56차 — 신뢰 이력 내보내기·별도 최신 지문에 고정한 원본 복구 (2026-10-25)

- `catalog_trust_transfer`/`gw_catalog_trust_transfer.py export/receive`를 추가했다. 별도 확인한 원장 UUID/최신 버전/원본 전체 지문과 manifest 전체 지문을 입력받아 모든 원래 바이트/연속 전이를 검증한다. 원본4096개/각256KiB·manifest2MiB 제한, 파일 단위 처리다. 패키지 안의 키·경로/자기 지문을 현재 권한으로 자동 신뢰하지 않는다. 기존 목록/이관·신뢰 원본 형식/서명·업무 DB 스키마는 유지한다. 신뢰 상태 원본 재구성이며 실제 DB 복원/인수 PASS가 아니다.
- 기존 손상 폴더를 잠가 모든 남은 원본/현재·보류 기준점·이전 영수증 지문을 고정하고 그대로 보존한다. 더 최신 버전·다른 원장/같은 버전 분기·중복/알 수 없는 기준점 버전은 거부한다. 새 환경은 명시 new-host가 필요하며 기존 더 최신 상태를 우회하는 용도가 아니다. 새 복구 폴더에 확인 지문/기존 원본 상태를 입력 해석 전 수신 보류로 기록하고 전체 원본/전이·기존 원본 불변 재검증 후에만 영수증/현재 기준점을 원자 활성화한다. 일반 조회는 수신 중 차단하며 이후 영수증의 최소 원본도 검사한다.
- 동일 계획/원본의 명시 resume만 허용한다. 완성 파일은 같은 실제 바이트로만 재사용하고 잘린 파일/영수증·보류 기준점은 자동 덮어쓰기/삭제하지 않는다. 기존 원본/실패 폴더를 보존하고 같은 별도 최신 기준으로 새 빈 폴더에 재구성해야 한다. 완료 응답 유실은 저장한 원본/영수증으로 확인하며 현재 더 전진한 이력을 과거 완료로 대신하지 않는다. 신뢰 환경/공개키·회사/수명 상태·이관 원본을 자동 설치하지 않으며 admin 이름/회사·서명 권한은 확장하지 않는다.
- 실회사 절차 §30/정적 도움말을 갱신했다. 직관성(신뢰 복구 완료와 운영 준비 구분), 유효성(별도 최신 기준/모든 원본·기존 더 최신 상태/단조 전이), 학습성(손상 원본 보존·재개/수동 경로 전환), 유연성(기존 환경/명시 새 환경·개인키 없는 원본 전달)을 고려했다. 제품 UI 코드/브라우저 전체 완성 작업은 아니다. 실제 복원 PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지.
- 같은 OS 계정의 로컬 어댑터이며 별도 최신 기준의 독립성/실제 외부 공급자·자동 최신 기준 갱신/키·승인 원본 설치·최대 성능/전체 복제본 유실은 별도다. 이전 손상/복구 진단 폴더 전체를 패키지에 포함한 것은 아니므로 별도 보존한다. 최종 검사/실패 보정·재현은 최신 progress/HANDOFF에 기록한다. 다음은 운영 준비에서 보존/복구 차단 원인을 비밀정보 없이 구분하고 현재 회사·관리 동선/다음 조치에 연결하는 UI 보완과 실제 브라우저/모바일 점검이다.
- 최종 검증: 관련 단위921(신규57)·화면/정적 도움말48·타입/Ruff/정적DB219/2409/543·R1–R6 오류0. 별도 소유 실제PG9통과175.95초, 최종 복구 연결 변형 별도1통과29.92초(중복 합산 없음). 보강 중 시험 변수/DB 시각 경계 실패를 보정해 재실행했다. 시험 생성DB/폐쇄 복원DB0·미리보기 DB보존. 상세 실패/재현은 최신 progress/HANDOFF를 따른다. 전체CI·회귀/실외부·실회사10인/브라우저/UI 전체 완성/main/push/배포는 미완료다.


## 57차 — 서버 차단 안내·담당자별 다음 조치와 모바일 (2026-10-25)

- 기존 운영 준비 API가 검증 설정/키 수명·이관/보존 설정·원본/설정 불일치·기준점 반영/수신 중단을7개 허용 코드로 구분한다. 고정 문구·서버 담당자/다음 조치만 반환하고 경로·키·예외 전문은 노출하지 않는다. SECURITY_ADMIN/AUDITOR만 진단을 조회하고 직원은 본인 보안 안내를 유지한다. 기존 검증/최신 회수·실패 원본/PARTIAL 계약은 완화하지 않는다.
- 현재 회사·연결1명/예정10명·역할과 최근 실행 요약을 유지하고 담당자별 다음 조치→상세12조건→실행 기록/기준으로 읽도록 보완했다. 회사별 업무 복귀/직원·조직 링크·정적 도움말을 연결하고 긴 조건은 펼쳐 본다. GET 재점검·초점 복원/오류 시 과거 결과 숨김, 기준·보관 검토·선택 파일/긴급 복구 입력 보호를 추가했다. admin 로그인 이름과 회사/서버 권한은 구분한다.
- 직관성(상단 차단/담당자), 유효성(허용 진단/현재 재조회·이전 성공 대체 금지), 학습성(담당자별 행동/도움말·12조건 펼침), 유연성(감사 조회/회사별 동선/390px)을 고려했다. 별도 합성 API 화면을 표시해 실제 브라우저1440/390·키보드/조회 전용·회사 유지/편집 보호를 검사했다. 실제5362 로그인은 별도 합성 계정이며 admin 부재·저장 정보 일치를 읽기로 확인했고 계정/비밀번호를 변경하지 않았다. 실제 API 로그인 후 브라우저 전체 흐름·UI 전체 완성을 주장하지 않는다.
- 최종 검사/실제PG/자원 정리는 최신 progress/HANDOFF를 따른다. 업무 스키마/마이그레이션·metadata/Excel/ERD 변경 없다. ready=false/최종4조건 UNVERIFIED·실제 복원 PARTIAL과 실외부/전체회귀/10인/최종PASS·최신main/원격push/배포 미완료는 유지한다.

57차 도움말 연결 보정: 지연 렌더링된 GW 문서는 요청한 제목이 DOM에 나타난 뒤 절로 이동한다. 다른 솔루션 문서의 동작은 바꾸지 않았다. 최종 화면/도움말61·타입/수정 린트와 실제 합성 브라우저의 절 위치를 재검사했다.


## 58차 — 자동 검증·실환경 인수의 공통 계약/실행 어댑터 (2026-10-30)

- `acceptance_contract` v1은 기존12조건의 현재DB/현재 서명 원본/실환경 인수, 도구 범위·남은 근거·선행 조건을 정의한다. 마지막4조건은 NOT_EXECUTED/UNVERIFIED이고 공통 실행 경계는 BLOCKED/PARTIAL만 반환한다. ACCEPTANCE PASS 계약이나 새 서명/업로드 형식이 아니다. 실제 복원PARTIAL·ready=false와 최종PASS 거부 유지.
- `acceptance_execution.execute`는 기존 회사 트랜잭션의 서버 기준을 받아 최신 등록을 먼저 선택하고 기존 수집기·준비 검증기를 호출한다. 정책/버전/결과로 성공만 선별하지 않고 원본 누락/변조·최신 실패/PARTIAL·회수를 과거 성공으로 대신하지 않는다. 회사/세대 혼합은 거부한다. 기존 연결 관측/신뢰 복구 기능을 중복 구현하지 않았다.
- 기존 운영 준비의12조건에 자동 확인·실환경 인수 구분을 접어 연결하고 정적 도움말과 [실회사 절차 §32](../operations/GW_실회사_인수절차_10인_GW-READY-02.md)에 도구/남은 근거를 대조했다. 도구 목록은 이 GET에서 실환경 검사를 실행했다는 뜻이 아니다. 기존 최소 예정 수 검사와 정확히10인·1부서/역할 구성 사전점검의 차이도 명시했다. 작은 설명 추가이며 전체 UI 완성은 아니다.
- 이번 관련 단위960(신규20)·화면/도움말61·타입/수정ESLint·Prettier·Ruff·정적DB219표2409열543FK/R1–R6 오류0. Docker소켓 부재·API8362/웹5362 미실행을 재확인했으며 임의 재기동하지 않았다. 이번 실제PG/브라우저·실회사/실기기10인/전체CI·회귀는 미실행이다. 과거PG/화면 결과를 이번 통과로 합산하지 않는다.
- 스키마/마이그레이션·Excel/ERD/계정·비밀번호·OTP·키/미리보기DB·다른checkout/WMS/main/push/배포 변경 없다. 다음은 기존10인 사전점검과 최신 원본의 공통 계약 보고 연결 및 전체 권한 거부의 누락 대조다. 외부 공급자 선정·독립성/전경로 무누락·전체 회수/최종PASS·실회사10인/최신main 통합은 남는다. 상세 재현/제약은 최신 HANDOFF/progress를 따른다.


## 59차 — 동일 읽기 스냅샷 실행 보고와 권한 거부 미연결 대조 (2026-10-30)

- 기존 `gw_acceptance_preflight.py --execution-report`는 동일 REPEATABLE READ·READ ONLY 거래에서 기존10인 구성 검사/현재 정책과 종류별 최신 원본 검증·12조건을 연결한다. unsigned GW_ACCEPTANCE_EXECUTION_REPORT v1이며 새로운 인수 서명/수집기·복원 도구가 아니다. 기본 사전점검 옵션/출력은 유지한다. 사전점검 BLOCKED와 전환 조건 차단을 따로 집계하고 어느 쪽이든 미충족이면 전체 BLOCKED다. 운영자 코드 버전값을 실행 바이너리 검증으로 표현하지 않는다.
- 권한 거부8영역은 선택된 검토 목록이다. 기존 인증 함수401/원본 HTTP 거부/제한 상태·격리와 복원본 새 인증 후 업무 권한 거부의 미연결을 분리한다. 기존 시험 참조는 실행 결과가 아니고 모든 행 NOT_EXECUTED·coverageComplete/revocationsComplete=false다. 직접SQL·전결/위임·게시/채팅/일정·향후SSO/독립 최신성·전경로 인수는 미완료다.
- [실회사 절차 §33](../operations/GW_실회사_인수절차_10인_GW-READY-02.md)·수집 경계·운영 준비의 기존 구분 안내/정적 도움말로 연결했다. CLI가 계정/비밀번호·권한을 자동 수정하지 않는다. 작은 설명/보고서 연결이며 전체 UI 완성 작업이 아니다. 실제 복원PARTIAL·ready=false/최종4조건 UNVERIFIED·ACCEPTANCE PASS 거부 유지.
- 검증: 관련 단위971(신규11)·화면/도움말61·별도 소유PG8(신규보고3+운영API3+실제dump/격리복원2)·수정Ruff check/format·정적DB219표2409열543FK/R1–R6 오류0. 같은 읽기 거래/쓰기거부25006·회사 상태불변/기본admin 부재·최신FAIL/원본유실·연결된서명PARTIAL 재검증을 확인했다. 새 UUID *_test DB와 새 owner라벨/loopback 컨테이너만 만들고 정리했으며 병행 DB/기존 미리보기는 접속/변경하지 않았다. 새 시험 환경 초기화의 임시socket 준비 상태를 TCP 준비 검사로 보정한 뒤 신규연결1건을 통과했다. 상세/재현/제약은 최신HANDOFF/progress를 따른다.
- 다음: 복원본에서 새 인증 뒤 권한 거부를 확인할 공통 검사 계약/제한 실행기부터 진행한다. 제한된 합성 대상·허용 경로와 실제 회수/실환경 인수를 구분하고 새 시험이 끝나도 전체 회수/인수PASS를 올리지 않는다. 실제10인/실기기·브라우저/전체CI·회귀·공급자/독립 최신 기준·최신main 통합/최종 전환은 남는다. 스키마/마이그레이션/metadata·Excel/ERD·실계정/OTP/키·다른checkout/WMS/main/push/배포 변경 없음.
