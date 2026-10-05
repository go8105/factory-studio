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

## CAD-03 / POC-03 · 2026-10-05 사용자 수정 (위 CAD-02 공개 POC 정책 대체)

이번 요청에 한해 Codex가 CAD/비누 시제품을 수정한다. D82의 다른 업무 솔루션 역할 변경은 유지한다.
- 일반 CAD·CAM은 기존 사용자에게 유지. 비누 탭은 MEMBER+ADMIN만 렌더링하고 일반 사용자의 view=soap은 무시한다.
- 모든 비누 HTML/JS/CSS/STL/ZIP은 공개 빌드에서 제외하고 backend/private-assets에 빌드. 기존 resolve_auth 후 매 요청 MEMBER+ADMIN 검사, no-store, 경로 이탈 차단.
- 관리자 역할의 새 부여/변경, 업무DB/마이그레이션 없음. 공개 웹 경로에 private-assets를 매핑하지 않는다. 배포 상세는 FS-022 마지막 절.
- 사용자 사진 기반 접이식 설계를 만들고, 후속 '고무 같은 케이스' 요구에 따라 POC-03으로 대체. 유연 외피/커버/하단 스킨 + 단단한 마찰판/가이드 + 완전 분리 서랍.
- 위 케이스와 상부 마찰판이 누름/소각 비틀림, 아래 마찰판은 핀으로 고정해 상대 운동한다. 외피0~10 mm·±12° 표시는 탄성 계산이 아닌 동작 설명.
- 최신 파일은 private/soap-poc/*-v3.stl(9개), DESIGN-v3.md, assembly-v3.json, soap-poc-03.zip. v2는 이전 가정이며 웹 기본에서 제외.
- 외피 경도/힘·복원·피로·접합 유지·잠금/래치·방수·마모는 미검증. 실물 완성품/양산 도면으로 표시하지 않는다.

재생성: prototype에서 `npm run poc:flex && python3 tools/package-soap-flex.py` → frontend `npm run build`.
권한 시험: backend `uv run pytest tests/test_cad_private_assets.py -q`, frontend `npm test -- src/cad-cam/CadCam.test.tsx`.
로컬 모의 세션+실제 파일권한 라우터: backend `uv run uvicorn tests.cad_private_preview:app --host 127.0.0.1 --port 8043`; frontend `FS_SMOKE_API_PORT=8043 npm run dev -- --host 127.0.0.1 --port 5243`.
모의 관리자 아이디 admin-preview, 비밀번호는 임의 시험문자. 이 fixture는 실제 로그인/실DB 검증이 아니다. 운영에서는 반드시 fs.main:app.
