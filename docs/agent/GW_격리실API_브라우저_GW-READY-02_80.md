# GW-READY-02 80차 — 격리 실제 API·브라우저 검증 (2026-11-07)

시작은 GW작업저장소 / codex/gw-company-01 / fcd69c5 / 깨끗한 작업트리다. 이 채팅의 마지막73차 이후 저장소가79차까지앞서있어 최신현황/HANDOFF/79차완료보고서를우선하고 이미있는74~76차본인동의를재구현하지않았다. 로컬main통합·전체로컬CI는79차의2026-11-06이력이며 이번에다시실행한것이아니다. 다른checkout/main은수정하지않았다.

이번범위는 고정통합소스의 실제API인증→회사선택→운영준비→선택문서권한거부→연결정지/재조회 복구다. 앱코드결함이발견되지않아 제품코드는변경하지않았다. 정적도움말/운영문서·무서명검증요약·화면9개와 재현fixture3개를추가했다. 이것은 인수PASS 증거발급기나 새GW/외부공급자수집기·복원기가아니다.

## 환경과 합성 준비

기존 Colima factory-studio프로필/API/Vite는중지상태였다. 기존프로필을기본명령으로기동했고 CPU/메모리·시각/서버보안정책을임의조정하지않았다. 기존 fs-gw-ready02-preview는계속중지상태로두었다. 새 owner=gw-ready-02-phase80 컨테이너전체ID/running/단일127.0.0.1:55480/PG18을확인하고 시각표본20회/250ms가드를통과한뒤 새UUID gw_browser_*_test만만들었다.

기존 migration/seed.create_template·hr.work_setup.create_company·실제GW/HR API로 합성회사1개/관리자admin·직원synthetic-staff/연결2명/예정10명·운영기준을준비했다. 새관리자이름은사용자기준admin이며기존계정이름변경은아니다. 회사표지가false여도실회사증명이아니며이회사는합성이다. 관리자/직원TOTP factor는새시험DB에직접삽입하고준비중운영기준검사에만합성세션assurance를사용했다. 준비세션은회수한뒤 실제브라우저의비밀번호202→MFA201을각1회거쳤다. 마지막읽기검사에서활성관리자제어/직원세션2개모두MFA임을확인했다. 실기기앱등록/복구·운영COMPANY/HTTPS모드는미검증이다.

API8380/웹5380은이번생성PID만사용했다. TEAM_TEST/loopback HTTP이며 요청가로채기/합성API응답으로바꾸지않았다. 비밀번호·OTP·키/쿠키·DB URL과전체로그는0700 work내부0600자료에만두고출력/Git제외했다.

## 실제 확인

- 관리자브라우저: 실제비밀번호/MFA→런처GW→개인체험에서회사선택→회사운영안내→운영준비. 회사명/보안관리자·연결2/예정10·앱2·기준1번째버전, 서버검증설정필요/실행증거0건을확인했다. GET재점검은백업/복원을실행하지않았다.
- 1440/390: 전환12조건펼치기와확인됨4/조치필요4/미확인4, 서버도움말해당절·뒤로·회사유지. 사이드바가펼친채모바일로전환되면닫기버튼으로닫고검사했으며임시viewport override는reset했다.
- 관리자양성대조: 실제로만든비공개초안본문을관리자가브라우저와API로읽었다. 직원은그기안자가아니며초안참여자는열람예외가아니다. 직원실제MFA로그인후관리화면주소로들어오면관리상세/등록UI대신계정보안안내만표시된다.
- 직원선택원문: 같은초안번호를넣은실제GET이404 NOT_FOUND로거부됐다(두뷰포트에서각1회). 원문/제목은표시하지않고open이제거되며회사ID는유지한다. 권한과연결다시확인을Enter로실행해현재회사목록으로복귀했다. 단일초안경계이며모든문서/쓰기/전체회수를검증한것은아니다.
- 연결경계: 별도실제MFA관리자API로이번시험직원연결을정지(version3)했다. 브라우저의기존조회주기에서직원연결정지/보안관리자문의가표시됐다. 직원의연결재조회는정지를해제하지않았다. 같은관리자API로재개(version4)후직원Enter재조회로같은회사목록이표시됐고옛open/본문을자동복구하지않았다. 실제회사/실계정연결은변경하지않았다.
- 최종실API읽기: ready=false/최종4UNVERIFIED·연결2명·관리자원문읽기true·직원연결ACTIVE를확인했다. 복원도구/실행증거등록/인수PASS는이번실행에없다.

## 검증과 실패 이력

브라우저가검사한소스지문은 e1548ad488e22bb83fd9bd5554567048598de59a71f28f5c41ec10472f2993ca 로79차고정소스와동일하다. 이지문은브라우저구간의제품/시험/정적도움말기준이며 이후추가한도움말설명은해당파일시험으로따로검사한다. 제품backend/frontend/tools·metadata/migration변경0이다.

초기실제제어helper가생성201을200으로기대해실패했다. 기대를200/201로수정했다. 이어자기자신을결재자로넣은합성fixture를제품이400으로거부해 직원결재선의관리자초안으로준비를고쳤다. 동의연결목록의rows오해도실제items계약으로고쳤다. 제품검사를약하게하거나실패를성공으로기록하지않았고, 최종API/브라우저근거만별도수록했다. 시스템Python3.9의UTC import실패는프로젝트Python으로재실행했다. 이실패로그는비공개work에보존한다.

공개준비recipe는명시플래그없음/기존state덮어쓰기와work밖출력을거부했고, 준비/제어/정리3recipe의work밖경로거부를실제로확인했다. Ruff·포맷/구문검사결과와도움말시험최종수치는progress/HANDOFF를따른다. 이가드는운영권한회수·외부독립성증명이아니다.

## 정리와 남은 범위

생성API/Vite만PID명령과대조해SIGTERM으로종료했다. 전체ID/owner/단일loopback을재확인한컨테이너와그안의생성DB/익명볼륨1개를제거했고owner잔여0·3포트리스너0을확인했다. 기존미리보기컨테이너는저장ID와대조해중지상태임을확인했으며DB에접속하지않았다. 기존사용자탭은건드리지않고생성검증탭만닫았다. Colima런타임은기동상태로남겨두었다.

80차는선택된합성실API브라우저동선검증완료다. 전체CI/전체회귀/백엔드전체단위·복원·실기기·실회사10인인수를이번에실행하지않았다. 감사자/PENDING본인동의의실API브라우저·독립외부저장소/전체수집·회수·최종운영전환은남는다. ready=false/최종4UNVERIFIED·실제복원PARTIAL/ACCEPTANCE PASS거부는계속유지한다. 원격push/배포/main반영없음.

## 재현

GW작업저장소에서만실행한다. 이재현은새폐기합성fixture를준비하는실제DB쓰기이며미리보기/운영DB를지정할수없다. postgres:18로컬이미지/가동중Docker와프로젝트의존성이필요하다. 최초prepare가실패해도state가있으면소유확인뒤cleanup으로생성분만정리한다. 이미제거한state를덮어쓰지않으므로다음실행은새private경로를쓴다. 실행원문은work에저장하고공개하지않는다.

```sh
export GW_BROWSER_REVIEW_WORK=work/gw-readiness-02-phase80-reproduce
mkdir -m 700 "$GW_BROWSER_REVIEW_WORK"
PYTHONPATH=. backend/.venv/bin/python outputs/gw-readiness-02-phase80/prepare_fixture.py --prepare-owned-synthetic > "$GW_BROWSER_REVIEW_WORK/prepare.log" 2>&1
# credentials.json의새합성admin/직원과기존등록factor로localhost:5380에서실제로그인/MFA.
# 회사선택/운영준비·도움말/GET재점검과1440/390확인. 실제기기등록검증은아님.
backend/.venv/bin/python outputs/gw-readiness-02-phase80/control_fixture.py document > "$GW_BROWSER_REVIEW_WORK/document.log" 2>&1
# admin이원문양성대조후로그아웃,직원MFA로그인.관리주소/해당초안open거부와회사재조회를확인.
backend/.venv/bin/python outputs/gw-readiness-02-phase80/control_fixture.py suspend > "$GW_BROWSER_REVIEW_WORK/suspend.log" 2>&1
# 직원화면기존주기/정지안내·재조회로정지가유지되는지확인.
backend/.venv/bin/python outputs/gw-readiness-02-phase80/control_fixture.py resume > "$GW_BROWSER_REVIEW_WORK/resume.log" 2>&1
# 직원회사재조회/옛원문자동선택없음. audit은관리자API읽기이며현재화면인수를대신하지않음.
backend/.venv/bin/python outputs/gw-readiness-02-phase80/control_fixture.py audit > "$GW_BROWSER_REVIEW_WORK/audit.log" 2>&1
backend/.venv/bin/python outputs/gw-readiness-02-phase80/cleanup_fixture.py
backend/.venv/bin/ruff check outputs/gw-readiness-02-phase80/*_fixture.py
backend/.venv/bin/ruff format --check outputs/gw-readiness-02-phase80/*_fixture.py
PATH=/opt/homebrew/opt/node@24/bin:$PATH npm --prefix frontend test -- src/portal/content-pages.test.tsx --maxWorkers=1
git diff --check
```

제어관리자MFA는브라우저관리자와다른OTP시점에확인한다. 이미쓴OTP를다시사용하거나factor시각/재사용보호를바꿔통과시키지않는다. 정지는이fixture직원만대상이며재개역시동일연결의현재버전을조회해CAS로요청한다. 정리recipe는생성ID/owner·loopback/PID명령을다시대조하고다른자원을종료하지않는다.

다음제안은동일격리계약에서감사자의조회전용범위와PENDING본인동의의재조회/회사전환을실제API브라우저로검증하는것이다. GPT-6 Astra + High제안유지, 모델자동변경없음/다음ID자동착수없음.

80차최종검사: 실제격리API/브라우저 선택동선12항목·1440/390/Enter·관리자/직원로그인2회와별도제어MFA1회를확인했다. 단위시험건수로합산하지않는다. 도움말19건/3.79초·공개fixture3개Ruff/포맷·구문검사/JSON·로컬링크·diff·현황200줄제한통과. 명시플래그/기존state덮어쓰기·3recipe work밖경로거부5조건확인. 제품소스는검증구간79차와동일, 전체CI는이번재실행하지않음. 생성API/Vite·시험DB/컨테이너/볼륨정리·owner잔여0/3포트리스너0·기존preview중지유지.
