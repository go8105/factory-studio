# CAD-V03 YC 음성 요청 흐름 검증 (2026-10-13)

branch codex/cad-v03, 기준 main65aaea5. 사용자가 Step4 자동 팝업/기존 휴디 표시를 지적하고 예제→음성→제안→번호 재생 보정을 요청했다. 공통 CAD 설계·기존 전체 승인 범위 안의 시연 흐름 수정. factory-impeccable 지침 적용. antigravity/MES 체크아웃 변경 없음.

## 변경

Step4 품질 조건과 소비 비교는 report만 계산, 음성/NC에너지제안 요청만 카드 표시. YC 예제 버튼은 마이크 시작을 먼저 요청한 뒤 합성 NC·STEP·소재·장비·품질 조건 순차 준비. 준비 완료 후 와이씨 호출→파일최적안요청→3정지카드→번호요청/선택확대/실제NC뷰어재생. 실업로드 파일의 조건을 합성으로 덮지 않으며 일반후보 수는 기존계산 유지. 재시도·준비 실패/입력변경/탭숨김 중단·stale 순서 차단. 음성API 미지원/권한거절은 기존 버튼/텍스트 경로 유지. 화면 기본 YC와 호출 대기는 와이씨, 내부파일ID와 이전호출별칭은 유지.

공유 실행 브랜치 antigravity/w2a-1b2-rest에는 예전휴디 코드가 있으므로 해당 브랜치 실행과 최신 main 빌드를 혼동하지 않는다.

## 실제 검증

- CAD154·대상 frontend33/3파일 통과, 전체frontend build/공개비공개자산격리 통과. 도움말 갱신 후 대상33검사 재통과. 전체prototypeformat/diff 통과.
- 실제GoogleChrome headless 정적제품빌드 NC/STEP/소재/에너지 Worker를 실제 실행. 단일 YC 버튼 자동준비→정지 팝업0→Step4비교 후팝업0→SpeechRecognition 모의 final이벤트 ‘헤이와이씨’/‘업로드한파일최적안제안해줘’→팝업/정지→‘3번실행해줘’→보이는카드1/3번/canvas/진행률>0→정지/전체3카드/닫기. 390px 가로넘침0. 준비 도중 사용자NC입력변경→중단/새입력유지→예제 재시도 성공/팝업0. pageerror0.
- 처음 모의환경은 Chrome의 표준SpeechRecognition과 읽기전용speechSynthesis가 stub보다 우선하여 실패했다. 테스트에서 두API명과 speechSynthesis descriptor를 명시적으로 모의한 뒤 전체 흐름 통과. 앱의 실제 마이크 성공으로 표현하지 않는다.
- 이미지 assets/cad-v03/selected-3.png, 재현스크립트 assets/cad-v03/voice-flow-check.mjs. 실제NC/STEP는 합성 예제만. 원본 사용자 파일·계정/권한·DB 변경 없음.

## 한계·재현

실마이크 발화/TTS/권한 및 실장비·품질전력 정확도, 운영 새흐름 검증은 미실행. 가짜 인식 이벤트가 실제 음성 핸들러를 통과한 검증이다. 서버배포는 이전GitHub계정결제 차단 상태와 구분해야 하며 이번작업에서 CI를 우회하지 않는다.

Node24 npm --prefix frontend ci/build, npm --prefix prototypes/cad-cam ci/test. frontend/dist 정적서버5260 실행 후 node docs/agent/assets/cad-v03/voice-flow-check.mjs (Chrome 설치 필요; URL은 CAD_TEST_URL). 제품 커밋과 최종인계는 git log -1로 확인.

제품c0efb5b main/origin 반영 완료. 해당 check115285673525도 runner시작전 결제/한도차단. 새운영배포미실행·CI우회없음.
