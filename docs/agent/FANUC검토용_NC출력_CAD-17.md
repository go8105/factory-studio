# CAD-17 FANUC 검토용 NC 출력 결과 (2026-10-10)

사용자 ‘장비 미정으로 남은 작업 진행’ 승인. **검토용 출력 범위 완료**, 실제 장비 post 완료 아님. branch `codex/cad-17`, 기준main e137f61 / 이전기반738433d. [계약](../modules/cad-cam/NC출력_설계_CAD-17.md).

- `nc-controller.js`: FANUC 검토 프로필·O번호·G4 P밀리초를 기존 내부 초 단위 모델로 읽는 어댑터. 원본 행/원문을 표시하며 파일 프로필/초기 설정을 보존한다.
- `nc-post.js`: 원본 해시/다시 읽기·최신 품질 제안 재계산·FANUC 검토용 문법 생성·출력 재해석/행 대응/경로·모달·이벤트 의미 보존. 공구 보정/장비 이동을 추가하지 않는다.
- `nc-post-worker/review.js`: 30초·취소·stale 차단, 후보0/1~13·O번호·초기조건 확인·미리보기·NC/JSON 저장, 탭 비활성 취소. NC 화면 연결·프로필 선택·예제 프로필 복귀. 미리보기240px 제한으로 결과 패널 유지. 도움말 최신화.

## 실행한 검증

- CAD 전체153통과, 출력코어11개(기존7+FANUC4). 원본 bytes/CRLF/이모지 주석P·인치/상대/원호/F/S/T·모달 혼합·해시/품질변경·지원/종료·정수ms/범위·G+4/G004/G091.1 숫자 표기·재수출 확인.
- 프런트 도움말/포털/CAD 대상15통과. 전체 frontend build/공개비공개 자산 격리 통과, 기존 큰 번들 경고 유지. 범위 Prettier·diff 검증. 최초 diff-check가 NC의 의도된 CRLF를 trailing whitespace로 보고해 증거 폴더의 `.gitattributes`에 CRLF/원본 byte 보존 규칙을 지정하고 재검증 통과.
- 실제 Google Chrome(headless,1440×900/390×844), 합성 휴디 예제: NC→STEP→소재→에너지→품질3후보→파일 다운로드/JSON 수신. 원본600/300초→P600000/P300000, 후보3의10/10초→P10000/P10000. 저장 파일을 FANUC 프로필로 업로드·재해석·다시 출력해 동일 대기P 보존. 프로그램/프로필 변경 저장 차단·모바일가로넘침0·pageerror0.
- 최초 왕복검사에서 구분자/O번호의 비실행 헤더까지 블록 상태 비교해 실패했다. 실행 명령만 원본행과 비교하고 이동/전체이벤트·최종상태 검사는 유지하도록 수정, 해당 재수출/구분자 회귀 통과. 첫 browser STEP 대기중 Vite 최적화 페이지 reload로 DOM을 잃은 실행은 실패로 남기고 준비 후 전체 시퀀스 재실행 통과.

## Git에 보관한 합성 증거

- [원본 의미 출력](assets/cad-17/original.review.nc) / [후보3 출력](assets/cad-17/candidate-3.review.nc) / [검증 JSON](assets/cad-17/candidate-3.verification.json).
- [데스크톱](assets/cad-17/desktop.png) / [모바일](assets/cad-17/mobile.png).

고객 NC/비누 이미지 없음. 출력 주석 경고를 제거하지 않는다. 검증 JSON source는 합성 공정 근거다.

## 미실행 / 다음

실제 FANUC interpreter·특정 CNC 장비·H/D·홀더/지그·실측 품질/전력·실 음성·운영 서버/실제세션 검증·DB변경 없음. 본 파일을 실제 장비 실행 승인으로 취급하지 않는다. main 병합/push/배포 미실행. 사용자 결과 확인 후 반영 또는 실제 장비 모델/매뉴얼/보정 규칙을 확정하는 별도 작업. CAD-18/다른 솔루션 자동 착수 없음.

재현: Node24, `npm --prefix prototypes/cad-cam test`, `npm --prefix frontend test -- src/portal/docs.test.ts src/cad-cam/CadCam.test.tsx`, `npm --prefix frontend run build`. 원본 `npm --prefix prototypes/cad-cam run dev -- --port 5257`에서 nc-review.html, 도움말의 출력 순서 참조. 브라우저 다운로드는 실제 File chooser/file input과 save 버튼을 사용했다.
