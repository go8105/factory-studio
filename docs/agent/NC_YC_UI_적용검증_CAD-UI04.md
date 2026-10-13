# CAD-UI04 NC·YC 제품 UI 적용·검증 (2026-10-13)

사용자 Figma CAD-UI03 결과 이후 이어가기 요청으로 제품 적용 승인. branch codex/cad-ui04, 기준 main ee9555a+UI03 설계b60a2a4. 기존업무/DB/권한/CAD E1·E2 변경 없음. factory-impeccable/figma-design-to-code 지침을 적용했다. Figma get_design_context6:733은 Starter도구한도로거절, 보관한시안PNG/노드ledger/작성script/설계서로대체했다. 미조회최종Figma와pixel-perfect일치라주장하지않는다.

## 구현

- 좌220px 준비단계/중앙유연뷰포트/우300px 실제속성·YC/하단재생 구조. Figma280px 우패널은 실제긴폼/숫자접근성을위해300px로조정. 기존입력/이벤트/뷰어/Worker객체를이동하여유지.
- 단계선택→우측해당폼만표시, aria-controls/current/expanded·확인완료/필요표시. 원본NC/선택행은중앙하단details로보존. 결과근거/출력은우측details.
- 최초파일미선택중앙안내/파일열기/YC예제실제버튼. NC·소재·에너지미완료시제안버튼차단, 음성요청은기존검증으로차단. 잘못된입력/변경은완료표시와결과를무효화.
- 제안은모달에서중앙section으로전환: 실제정지뷰어캡처·시간/kWh/변경근거/차단표시. 번호선택→다른카드숨김·기존뷰어이동/재생, YC는오른쪽유지, 재생패널은하단유지. 같은렌더러하나, Figma도식을제품이미지로붙이지않음.
- 제안중에는긴설정폼숨김으로YC접근. 전체보기는정지/3카드복귀, 닫기/Esc/단계선택은정지·뷰어원래위치/설정복귀. 기존일반최대13후보·TTS30초창·취소/무효화는유지.
- PC전체높이에헤더/중앙/하단맞춤, 각폼/뷰포트내스크롤. 950px이하세로배치/단계2열, 선택설정으로이동/작업화면복귀버튼. 실제조건입력은Figma도식/가짜수치와구분.

## 검증

- CAD154/154, 대상frontend33/3파일, 전체build/공개비공개자산격리·prototypeformat·diff검사통과. nc-layout기존회귀에단계전환/참조·입력/클릭보존/aria·완료무효화검증추가. 별도단순UI복제테스트추가없음.
- 실제GoogleChromeheadless 정적제품빌드1440×900/390×844, 실제NC/STEP/소재/에너지/post Worker. YC예제→자동준비→Step4계산시팝업없음→모의final발화YC/파일최적안→중앙3카드→3번발화선택/canvas1/진행률>0→정지/전체3→Esc/원래뷰포트→FANUC출력확인/미리보기→390가로넘침0→준비중입력변경중단/새입력유지→재시도성공→소재치수수정/제안비활성/완료표시해제→원본NC펼침/지원도움말열기닫기. pageerror0.
- 첫시각검토에서긴품질폼아래YC가가려지고상단스크롤발생을확인했다. 제안중설정폼숨김/전체높이제약으로보정후동일흐름재검증통과. 최종empty/comparison/selected/mobile 캡처보관. 최초상태검사는이벤트직후대기전사진일부완료표시갱신전이었다. 최종품질complete=true확인.
- 실제음성은미검증. SpeechRecognition/TTS모의가실제이벤트핸들러를통과한검증이며마이크성공이라고표시하지않음. 실제장비/전력정확도/FANUC기종호환·백엔드전체/DB왕복·운영새UI검증미실행. 기존큰번들경고유지.

## 재현·반영

Node24 prototype npm ci/test/format:check, frontend npm ci/build 및대상help/docs/CadCam검사. frontend/dist 정적서버5263→node docs/agent/assets/cad-ui04/workspace-check.mjs (Chrome필요, CAD_TEST_URL선택). 모의인식/합성예제사용. 테스트전용서버는종료한다. 계정/비밀번호/원장/병행antigravity변경없음.
사용자기존main/push승인범위로통합하며원격CI/배포결과는후속기록을참조한다. GitHub결제차단과Figma호출한도는별개, CI우회/새운영배포없음. 다음사용자결과확인/실발화·운영검증, CAD/CAM다른모드확장은자동착수없음.
