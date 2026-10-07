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

## CAD-04 연구노트·고도화 분석 (2026-10-06)

사용자 확인: 관리자 웹 연구노트와 설계 파일 이력. 기존 MEMBER+ADMIN 보호 API/빌드 경계 적용. DB/역할 추가 없음.

- POC-01→02→03 회고: 이유·가정·검증/미실행·다음 방향·ZIP/STL/안내·SHA-256. 후속은 새 버전 추가.
- 신규 기록은 scope별 브라우저 저장. append·JSON export/import, 중복 병합·충돌시 원본 보존. 서버 동기화/사진 업로드/서명 없음, 공유 브라우저 한계는 기존 CAD와 같다.
- private/soap-poc/research-history.json·RESEARCH-NOTEBOOK.md, 보호 research-notebook.html. 공개 편집기에 넣지 않는다.
- [고도화 분석](편집기_고도화분석_CAD-04.md): 커널 실증→자유 스케치→피처/조립→제작→CAM. 전체 확인 전 고도화 구현 미착수.

## CAD-05 CNC 우선 E0 실증·기록 규칙

2026-10-06 사용자 전체 방향 확인 및 main push 승인. CNC 우선, 비누 심화는 후속 창업 단계. 사진 없이 설계 폴더/파일명·기록을 연결한다.

이번 범위는 기존 Manifold 후보의 자유 평면 윤곽 offset·가공 가능 영역 분리·독립 여유 검사 실증이다. Node 실증으로 브라우저/worker 성능이나 전체 CAM 완료를 주장하지 않는다. 다음은 결과 보고 후 자유 스케치 편집기 작업 ID.

설계 파일 위치는 연구 기록에 명시한다. 기존 POC-01~03 이름은 보존한다. 신규 비누 설계는 `private/soap-poc/revisions/POC-04/soap-grinder_POC-04_YYYY-MM-DD_<part>.stl` 같은 버전 폴더와 이름을 쓰며 덮어쓰지 않는다. 연구노트 기록의 폴더/파일명 입력은 참조 문자열이며 브라우저가 해당 디스크에 파일을 쓰거나 존재를 확인하는 기능은 아니다.

## CAD-06 E1 자유 스케치 구현 계약 (사용자 이어가기 승인)

- CNC 우선 E1만 구현한다. 선 연결의 닫힌 윤곽·3점 원호(마지막 직선으로 닫기)·회전 슬롯, 꼭짓점/원호 통과점 좌표 치수와 끝점/격자 스냅을 제공한다. 완전한 구속 해석기는 E1 범위가 아니다.
- JSON v2는 꼭짓점 ID·원래 좌표·원호 통과점을 보존한다. v1 사각형/원 파일은 v2로 읽고 동일 형상을 유지한다. 100KB·64꼭짓점·4096근사 경계점·32홈 상한. 미닫힘/교차/퇴화 윤곽은 적용을 거부한다. 원호 경계 현 오차 목표 0.01mm.
- 자유 홈은 E0의 Manifold 3.5.4 offset을 Worker에서 계산한다. 분리된 절삭 구간 사이에는 반드시 안전 높이 이동을 넣고 원래 경계의 공구 여유를 검증한다. 가공 불가능한 홈은 경로 생성을 거부한다.
- 기존 단일 돌출·상면 홈·STL·격자 소재 제거를 확장한다. 다중 돌출/조립/STEP/NC/실제 기계 충돌과 물성 검증은 이후 단계다. 비누 POC·사진 업로드를 확장하지 않는다.

CAD-06 E1 구현 완료: prototype37/frontend524/build·자산 분리, 실제 포털 및 1440/390폭 UI 검증 통과. 자유 스케치 예제 JSON은 `prototypes/cad-cam/examples/cnc_E1_2026-10-06_L-slot-arc.form.json`에 저장한다. 상세 검증과 미검증 항목은 [결과 보고](../../agent/자유스케치_편집기_CAD-06.md)에 기록했다. 다음 E2는 결과 확인 후 진행한다.

## CAD-07 E2 부품 설계 (2026-10-07 완료)

사용자 E2 진행 승인. 포털 `view=part`의 별도 3D 편집기로 다중 피처/평면/필렛/쉘을 제공한다. [구현 계약](부품설계_구현계약_CAD-07.md)과 [검증 보고](../../agent/부품설계_편집기_CAD-07.md)가 최신 E2 기준이다. E1 상면 CAM·관리자 비누 POC/연구노트의 권한과 범위는 유지한다. 설계 예제는 `prototypes/cad-cam/examples/cnc_E2_2026-10-06_<name>.part.json`에 보관한다. E2 원본 JSON v3는 별도 localStorage `form-studio-part-v3:<scope>`이며 E1 저장을 덮어쓰지 않는다. 조립은 E3, 측면/3D CAM은 E5 결과 확인 이후다.

## CAD-09 품질 우선 경로 제안 (2026-10-07 완료)

[CAD-08 계약](품질우선_경로제안_설계초안_CAD-08.md)을 사용자 승인으로 구현했다. E1 상면 포켓에서 절삭/방향/깊이/마무리·안전Z·동일 격자 결과를 보존하며 기존/가까운 방문 순서를 비교한다. 2후보·256래스터·30초 Worker 상한, 조회와 적용 분리·입력 무효화. 장비 미정은 비절삭 거리/시간만 비교하며 소비kWh/절감률은 산정 불가다. 실제 품질/전력 보증이 아니다. [검증 보고](../../agent/품질우선_경로제안_CAD-09.md).

## CAD-10 NC·소비 에너지·편집 고도화 분석 (2026-10-07)

[상세 분석 및 제안](NC에너지_편집고도화_분석_CAD-10.md). NC 경로와 CAD 이력의 분리·컨트롤러별 해석·소재/공구/좌표·장비 전력 입력 및 실측·품질 우선 제안 조건을 정리했다. E1/E2 공통 키보드/draft undo와 스케치/직접 편집 데이터 확장도 포함한다. CAD-10 당시 분석만 완료. 이후 사용자 권장안 승인으로 3축 밀링·G-code 우선 확정, CAD-11 구현 완료; CAD-12~17은 결과 확인 뒤 ID 하나씩 진행한다.

## CAD-11 편집 명령·실수 복구 (2026-10-07)

[설계 계약](편집명령_복구_설계_CAD-11.md) · [검증 결과](../../agent/편집명령_복구_CAD-11.md). E1/E2의 초안/확정 이력과 입력칸 기본 실행 취소를 분리하고 같은 단축키를 제공한다. NC 가져오기와 에너지 계산은 후속 CAD-12~15 범위다.
