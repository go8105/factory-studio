# CAD-02 · Factory Studio 포털 통합

2026-10-05. 사용자 명시 요청: 완성 후 CAD/CAM부터 Factory Studio에 넣고 로그인 후 앱 런처 오른쪽에 메뉴.
해당 연결 범위만 구현 승인으로 반영했다. [공통 설계](../modules/cad-cam/README.md).

- 로그인 후 상단 `앱 런처 → CAD·CAM → 3D 공장`. 기존 Private 라우트 안 `/cad-cam`.
- 편집기/비누 POC 전환, 동일 출처 iframe. 로컬 별도 CAD 서버 없이 frontend 빌드에 포함.
- predev/prebuild 자동 생성, 정적 자산은 `/cad-cam-app/`. 원본은 prototypes/cad-cam.
- 상대 다운로드/모델 경로와 내장 부모 이동 지원. 브라우저 설계 저장 키는 공간+세대별 분리.
- CAD 데이터 서버 전송/DB 변경 없음. 공개 정적 시제품 자체를 서버 인증으로 보호하는 기능은 추가하지 않았다.

## 실제 확인한 결과
- frontend 전체521 통과; 탭 표시 수정 후 관련3 재통과. prototype13 통과.
- frontend build(내장 앱 포함)/typecheck/lint/format 성공. Three/CNC 공통569KB·기존 Factory947KB 청크 경고는 남는다.
- 로컬 브라우저: 모의 게스트 로그인 → 홈 메뉴 → CAD 모델 → 공구 경로 → 소재 제거100%, POC 전환 → STL다운로드 → 편집기로 돌아와 설계 유지.
- 390px 홈 메뉴·내장 편집기 가로 넘침 없음, 오류로그0. POC 탭 active 상태 하나만 표시 확인.
- 실제 다운로드 `plate-A.stl` 확인. 화면 증거 `assets/cad-02-integrated.png`, `assets/cad-02-soap.png`.
- 검증에 사용한8042 API는 합성 fixture. 실제 인증 서버/운영 DB/운영 도메인·Safari/실기기·프린터·슬라이서·분쇄 물리는 미검증.

## 재현과 남은 일
Node24, frontend에서 `npm ci && npm run build`. CAD-02는 제품 메뉴 통합까지, 실물은 미제작.
모의 검토 서버는 공통 설계 README 명령. 포트5242/8042를 사용하고 실제 업무 API는 제공하지 않는다.
다음은 사용자 확인 후 실제 환경 배포와 FDM 출력 실험. 원격 push·배포는 실행하지 않았다.
