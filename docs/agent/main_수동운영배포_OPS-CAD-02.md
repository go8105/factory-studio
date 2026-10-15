# OPS-CAD-02 main 수동 운영 배포 (2026-10-15)

사용자 로컬main 수동실서버반영 요청. 별도 main 체크아웃 factory-studio-help-main, 배포제품 c0f118e2c22b5eaa56c78deb0fd2c0f50f594ac5. 기존운영3a6019f→c0f118e, CAD-V03 자동발표준비/와이씨·CAD-UI04 중앙제안/단계별속성·고정재생·도움말 반영. 진행중 antigravity/ops-ci-01·ERP/W2b 작업은 병합하지 않았다.

## 배포 전 검증

- origin/main=로컬main=c0f118e, 추적변경없음. GitHub 해당커밋 CI38403477081/check115316846714의 recent account payments have failed or spending limit needs to be increased annotation 재확인. CI는 실행 전 차단 상태다.
- 정확한 main에서 frontend npm ci 후 전체601/75파일, typecheck/lint/format/build 통과. CAD154/154·prototypeformat·db:validate 오류0. 빌드의 기존큰번들경고 유지.
- 운영3a6019f와 main 사이 backend/lock·DB메타데이터·tools/deploy.sh diff0. 새백엔드/마이그레이션/시드 변경없음. 따라서 이번 backend전체/DDL왕복검사는 재실행하지 않았다. 전체 CI1~5를 돌렸다고 표시하지 않는다. 아직main에없는 OPS-CI-01 스크립트를 임의로 병합/실행하지 않았다.

## 보호 백업·표준 배포

- API 잠시중지→DB custom dump/복원목록읽기·이전frontend/비공개자산tar·gzip검사·회사원장/계정범위fingerprint→표준 tools/deploy.sh --skip-ci-check. **GitHub CI gate를 사용자수동배포요청과 위수동검증으로 대체했다. CI 성공/우회없음으로 표시하면 안 된다.**
- 유효백업 /srv/factory-studio/backups/20261015-cad-c0f118e-r2. 디렉터리700/파일600, DB·보호파일은서버에만보관. 이전커밋/DBdump/자산압축/restore-list/backup.sha256/company-before·after JSON 포함. 로컬/Git로원장·계정·환경정보다운로드없음.
- 최초 fingerprint SQL별칭 r이 spc.subgroup의 numeric r컬럼과충돌해 row_to_json(numeric) 오류. 배포시작전중단·trap으로API복구, 원본백업폴더보존. 별칭을고유이름으로보정하고 r2 새백업으로전체재실행. 프로덕션데이터/스키마 수정없음. 실패시API재시작trap유지.
- 코드/마이그레이션head flow_board_custom 유지, 시드 sv-20261009-gw1 일치로템플릿재생성없음. 관리자비누파일은웹루트밖업로드/앱소유자읽기확인. API재시작·프런트업로드·표준검증성공, 12:00 KST 완료.

## 배포 후 실제 확인

- 서버HEAD c0f118e/APIactive·원점/공개200·DDL대조0·배포직후최근2분5xx0. 회사범위업무/고정계정정보191표 건수·행hash 완전동일. 비교JSON은보호백업안에만있고실제데이터출력없음.
- 공개 /cad-cam200, 비로그인 /api/v1/cad/admin/soap-poc/soap-poc.html401. 공개NC의 JS(nc-CPTKQ6jy)/OrbitControls/CSS(nc-Ckz5c0en)가정확한main로컬build와SHA일치.
- 공개운영URL https://eip.hugh-d.com/cad-cam-app/nc-review.html 을 실제GoogleChromeheadless로실행: YC합성예제자동준비/실NC·STEP·소재·에너지Worker→Step4계산자동팝업없음→모의인식final이벤트헤이와이씨/파일최적안→중앙3정지카드→3번선택/canvas1/실진행률>0→정지/전체3→Esc/뷰포트복귀→FANUC검토용원본출력검증미리보기→390가로넘침0→준비도중NC변경중단/새입력유지→재시도→소재수정/제안비활성/완료무효화→원본NC/도움말열기닫기. pageerror0.
- 운영Chrome화면은 assets/ops-cad-02/public-comparison.png/public-selected.png/public-mobile.png. 실제원장/계정/설계파일입력없음, 공개합성예제와브라우저메모리수정만했다.

## 제한·인계

실제마이크발화/TTS·장비동작/실측품질·전력/FANUC기종호환 미검증. 모의음성이벤트가실제웹핸들러를통과한검증을 실음성성공으로표현하지않는다. 운영로그인계정으로쓰기/관리자비누200은미실행, 비로그인401만확인. 원장/계정/비밀번호/DB초기화없음.

재현: Node24 frontend npm ci/test/typecheck/lint/format:check/build, prototype npm ci/test/format:check, npm run db:validate. CAD_TEST_URL=https://eip.hugh-d.com/cad-cam-app/nc-review.html node docs/agent/assets/cad-ui04/workspace-check.mjs. SSH 앱소유자로서버HEAD/API상태확인, 회사fingerprint비교·백업파일은서버보호경로. 배포결과기록커밋은문서만이며운영제품c0f118e와구분한다. 다음사용자결과확인/맥북Chrome실발화리허설, 다른ID자동착수없음.
