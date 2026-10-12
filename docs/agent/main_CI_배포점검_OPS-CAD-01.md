# OPS-CAD-01 main 재push·CI·배포 점검 (2026-10-12)

사용자 요청으로 별도 main 체크아웃에서 확인했다. 공유 antigravity의 진행 중 MES 변경은 제외했다.

- 서버 앱 소유자 factory로 조회한 HEAD는 41ca68d, API active, 추적 변경 없음. root Git 조회는 dubious ownership으로 실패하여 기존 앱 계정으로 재조회했다. safe.directory 설정 변경 없음.
- dd62845 재push의 [38258159540](https://github.com/go8105/factory-studio/actions/runs/38258159540), CAD17/V02 병합13f3a8e push의 [38258223617](https://github.com/go8105/factory-studio/actions/runs/38258223617)는 verify steps가 빈 목록이다. 공식 annotation은 “The job was not started because recent account payments have failed or your spending limit needs to be increased. Please check the 'Billing & plans' section in your settings”. 코드 검사가 시작되기 전 계정 차단이다. 결제 실패와 지출 한도 중 어느 항목인지는 계정 화면 확인이 필요하다.
- Claude 기록의 과거 실행38255924011/38256475377은 이번 조회에서404라 원본 재확인 불가. 새 실행으로 같은 차단을 확인했다. 모든 브랜치를 이번에 시험하지는 않았다.
- 빈 커밋41ca68d 제목 after billing fix는 복구 증거가 아니다. 당시 도움말 배포는 기록대로 CI를 우회했으며 CI 성공 배포로 표현하면 안 된다. D84와 별도 배포 요청 여부는 이 기록만으로 단정하지 않는다.
- 최신 CAD가 운영에 없었던 별도 이유는 main 미병합이다. CAD-17 검토용 FANUC 출력 및 CAD-V02 STEP/YC 카드를 이번 main에 통합하고 push했다. backend/API/DB/시드 변경 없음. 진행 중 MES는 통합하지 않았다.
- CAD154/154, frontend596/596(75파일), 전체build/공개비공개자산격리/prototypeformat/git diff 통과. 최초 CAD 의존성 미설치 실패는 npm ci 후 재통과. 최초 frontend에서 NC 도움말 굵게 닫힘 문법 및 MES 대기 실패 발생; MES 단독12개 통과, 도움말 문법 수정 후 전체596개 재통과. MES 제품 코드는 수정하지 않았다. 큰 번들 경고 유지.
- 이번 실제 브라우저/마이크/운영 STEP, backend전체/DDL왕복 검사는 미실행. 이전 CAD 브라우저 검증은 각 결과 보고서 참조.

최신 CAD 실서버 배포는 미실행이다. CI 우회 없이 기존41ca68d를 유지했다. 저장소 소유자가 Billing & plans의 결제 및 Actions 지출 한도를 확인해 차단을 해소한 뒤 정확한 main HEAD CI를 재실행하고, 성공 후 보호 백업·표준 tools/deploy.sh·운영 STEP/YC 검증을 진행한다. 빈 커밋 반복push는 결제 해결책이 아니다. 계정/원장/비밀번호/결제 설정 변경, force/mirror push 없음.

재현: Node24 prototype npm ci/test, frontend npm test/build, gh run view38258223617 및 check-run annotations. 정확 HEAD는 git log -1 --oneline과 origin/main을 대조한다.
