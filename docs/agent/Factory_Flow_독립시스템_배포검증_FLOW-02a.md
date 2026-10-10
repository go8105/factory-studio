# Factory Flow 독립 시스템·UI 배포 검증 — FLOW-02a

완료: 2026-10-10 21:03 KST. 제품 커밋 `31623b066419358ea8d896d8a8d938e37a17c08f`, 이전 운영 `98402d9`. 사용자 승인에 따라 main 병합·origin/main push·실서버 배포를 완료했다. 후속 문서 기록 커밋은 배포 제품 커밋과 구분한다.

## 진입과 반영 범위

앱 런처의 **Factory Flow** → `/work-os` → `/work-os/boards`. 내 업무는 `/work-os/my-tasks`. [실서버 진입](https://eip.hugh-d.com/work-os). GW 사이드바 밖에서 독립 헤더·보드 메뉴로 동작한다. 내 공간 메뉴 카탈로그·즐겨찾기·도움말·후기에도 Flow를 등록했다. 기존 GW 프로젝트/내 업무 URL은 회사·보드 query 및 hash를 보존해 새 주소로 이동한다.

API 패키지 `fs.flow`, `/api/v1/flow` 및 flow 모듈 별도 사용 여부. 기존 `/api/v1/gw/projects` alias는 동일 서비스/원장을 사용하고 `gw.projects.*` 멱등 operation namespace를 유지하여 과거 요청 재시도 중복을 방지한다. 보드·멤버·그룹·업무·담당자·댓글·사건·보드 즐겨찾기·보기·설정 10표를 `gw`에서 `flow`로 SET SCHEMA 이관했다. ID/시퀀스/FK/댓글/변경 이력과 메뉴 즐겨찾기 순서를 보존한다.

참조 폴더의 React/CSS를 분석하고 Factory Flow에 백자 `#F7F7F6`, 흰 카드 `#FFFFFF`, 한지 테두리 `#E8E8E6`, 먹색 `#1A1C1E`, 보조 텍스트 `#5D6166`, 쪽빛 `#1F2D3D`, 청자 `#2D4442`, 프로필 `#E2E3E5`, 그림자 0/2/6/4%를 적용했다. 상태 배지·주요 버튼·아바타·진행바를 정리하고 별표만 금색으로 표시한다. 참조 원본은 수정하지 않았다.

기존 네 보기/하위 업무/복수 담당자/댓글/회사·보드 권한을 유지한다. **날짜별 업무일지 8표 및 대규모 가상화는 FLOW-02b 후속이며 이번 배포에 구현되지 않았다.** 전체 설계 JSON/Excel과 실제 schema를 혼동하지 않는다. 실제 schema0.24.1/head `flow_split`: 191표2074컬럼464FK, flow10/gw19. 목표379표918FK·메타데이터/Excel/ERD 동기화.

## 검증

정확한 제품 HEAD의 [CI 38048961871](https://github.com/go8105/factory-studio/actions/runs/38048961871) success: backend **1006 passed/1 skipped**, 별도 perf **1 passed**, frontend **75파일588 passed**, tools **133 tests OK**. 타입/lint/서식/빌드·DB 설계·격리·migration 왕복/DDL 대조도 통과했다. 초기 CI는 새 Flow 모듈 때문에 기존 게스트/시드 개수 상수가 맞지 않아 실패했다. MODULE_KEYS 기준으로 보정 후 전체 CI를 다시 통과했으며 CI를 우회하지 않았다.

전용 DB 프로젝트9검사: 구/신 API 영수증 멱등 공유, GW off와 Flow off 분리, populated10표 downgrade/upgrade hash 보존, 즐겨찾기 왕복 순서 확인. 로컬 실제 DB도 백업 후 이관·10표 hash/DDL0 확인. 추가 게스트/시드 기능16검사와 단독 perf1 통과. 동시 부하 중 성능 실패는 단독 재측정 및 최종 CI perf 통과와 구분해 기록한다.

Chrome 실제 제품 화면에 합성 API 응답을 주입해 런처→Flow·구주소 선택 유지·정확한 색상 계산값·390px 가로 넘침0 확인. 사용자 outputs의 `Factory_Flow_독립_구현_UI.png`, `Factory_Flow_모바일_구현.png`는 합성 검증 이미지다. 운영 실제 회사 계정으로 업무 쓰기는 실행하지 않았다.

## 운영 반영

배포 사전 점검 `tools/deploy.sh --dry-run` 통과 후 서버 전용 `/srv/factory-studio/backups/20261010-flow-31623b0`에 DB dump/프런트·비공개 자산/이전 커밋/10표 digest를 저장했다. 디렉터리700·파일600, pg_restore 목록 및 gzip 검사 성공. SSH 표준 입력으로 실행하는 초기 백업 명령에서 Docker가 후속 스크립트 입력을 소비해 DB dump까지만 수행된 것을 확인했다. Docker 읽기 명령에 `/dev/null` 입력을 지정해 즉시 재실행하고 전체 백업을 검증한 뒤 배포했다. 이 준비 중 API는 중지 상태였으며 데이터 이관 전 백업 완료를 확인했다.

실제 `FS_DEPLOY_BUILD_DIR=work/deploy-build-31623b0 tools/deploy.sh`는 별도 빌드 checkout을 사용해 exit0 완료. 서버 git31623b0, alembicflow_split(head), APIactive. 코드/활성 템플릿 시드가 모두 `sv-20261009-gw1`이라 기존 템플릿을 유지했다. 실제 회사/사용자/비밀번호 생성·변경 또는 DB 초기화는 하지 않았다.

이관 전후 10표 **모든 행 수와 digest 일치**. 실제 운영 DDL오류0, 공개·원점200, 재시작 후 최근2분5xx0. 공개 `/`, `/work-os`, `/work-os/boards`, `/work-os/my-tasks`, `/gw/projects`, `/hr/users`와 index JS/CSS200. 미로그인 세션 및 구/신 Flow 회사 API401으로 인증 보호 확인. SPA200은 실제 계정 업무 쓰기 검증을 대신하지 않는다.

## 로컬 admin 클릭 차단 추가 조사

사용자 기존 Chrome 탭에서 메뉴 링크 클릭/Enter가 이동하지 않는 현상을 재현했다. 직접 URL로 관리자 화면은 로드되고, 메뉴 잠금 aria-busy=false·비활성 버튼 없음·DOM 가림/inert 없음. 같은 Chrome 프로필/기존 admin 세션으로 새 탭에서 사용자 관리→앱 런처→MES 반복 이동 정상, 사용자도 “새 탭은 정상 동작”이라고 직접 확인했다. 정상 비교 탭은 유지했다. 기존 탭 새로고침만으로는 차단이 해제되지 않았다.

스크린샷의 sessions/current401은 로그인 전 세션 확인에서도 발생할 수 있으며 그 기록만으로 로그인 이후 인증 실패를 단정하지 않는다. 정상 비교 탭에도 확장 오류가 있어 403 콘솔 오류를 클릭 차단의 원인으로 단정하지 않는다. 확장403 출처는 chrome-extension(Monica), MetaMask 경고도 별도다. 기존 탭 내부 입력 차단의 정확한 원인은 미확정; 계정/서버 권한 변경이나 앱에 확장 우회 코드를 추가하지 않았다. 확장 설정·계정·비밀번호 유지. 사용자 로컬8000/5173 서버를 종료하지 않았다.

다음 작업: FLOW-02b 날짜별 업무일지/가상화 및 권한 고도화는 별도 범위 확인 후 진행. 운영 실제 회사 쓰기·휴대폰 설치 검증은 미실행 상태를 유지한다.
