# CAD·CAM 공통 설계 · CAD-02

2026-10-05 사용자 지시: 완성된 CAD/CAM과 비누 POC를 Factory Studio에 넣고 로그인 후 앱 런처 오른쪽에 메뉴 배치.
이 지시를 기존 시제품 포털 연결 범위의 구현 승인으로 적용한다. ROADMAP-02의 다른 업무 솔루션 개발은 재개하지 않는다.

- 진입: 로그인 후 공통 헤더 `앱 런처 | CAD·CAM | 3D 공장`. `/cad-cam`은 기존 Private 경계.
- 화면: CAD·CAM 편집기 / 비누 POC 전환 링크, 하단 동일 출처 iframe. CSS/전역 이벤트 격리, 기존 편집 기능 유지.
- 빌드: frontend predev/prebuild에서 원본 prototypes/cad-cam을 Vite로 빌드하여 public/cad-cam-app 생성. 산출물은 Git 제외. 별도5241 서버 불필요.
- 경로: 모든 앱/다운로드 경로는 빌드 base를 따른다. iframe 안 이동도 공간 범위를 유지한다.
- 저장: 브라우저 localStorage, workspace_id+generation_id별 키. 인증 정보·쿠키를 iframe URL로 넘기지 않는다. 공유 PC/같은 공간 사용자는 브라우저 저장에 접근 가능, 서버 권한 저장소 아님. JSON 다운로드 지원.
- 권한: 포털 진입은 로그인 요구. 정적 도구/예제 파일 자체는 공개 정적 자산이며 기밀 데이터 없음. 서버 CAD API·업무 FK·DB 추가 없음.
- 제약: 기존 CAD-01의 2.5D 범위 유지, 비누 POC는 조립 검토. 실물 성능/출력·STEP/자유 조립·클라우드 저장 미지원.
- 검증: 로그인/비로그인 라우트, 메뉴 순서, 공간별 저장 키, 내장 정적 파일 빌드·기능 동작과 다운로드 확인. 로그인 브라우저 검증에 모의 세션을 쓰면 명시.

## 재현
Node24에서 `cd frontend && npm ci && npm run dev` 또는 `npm run build`.
원본 prototype npm 설치 없이도 frontend 의존성만으로 내장 앱을 빌드한다.
CAD 원본 수정 후에는 `npm run cad:build`로 내장 자산을 갱신한다.
운영에서는 기존 API 세션을 그대로 사용한다. DB 변경 없음.

DB 없이 브라우저 UI 검토: `node frontend/scripts/cad-preview-api.mjs`(8042),
다른 터미널에서 `cd frontend && FS_SMOKE_API_PORT=8042 npm run dev -- --host 127.0.0.1 --port 5242`.
이 fixture는 모의 게스트 로그인·홈만 제공하며 실제 인증/백엔드 검증이 아니다.
