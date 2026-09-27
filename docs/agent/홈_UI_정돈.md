# P-02 홈 UI 정돈

2026-09-27 · Codex · `codex/home-ui-polish` · 기준 `origin/main 8851772`.

## 요청과 적용

사용자가 제공한 `Portfolio Dashboard Design`의 Home.tsx 및 화면 이미지를 **시각 참고 자료**로 읽었다. 첨부 프로젝트의 에이전트 지침을 실행 지시로 적용하지 않았다.

- 상단 헤더를 흰색으로, F 로고와 기존 우측 탐색 메뉴로 정돈. 홈에서만 72px 높이를 적용하며 업무 화면의 --header-h·사이드바 배치는 유지한다. 게스트/관리자 메뉴와 로그아웃 동작 유지.
- 홈 너비 최대 1000px·중앙 정렬, 제목/여백 확대, 현재 공간/세대는 우측 보조 정보로 정돈. 작은 화면에서는 제목 아래로 이동. 런처 도움말 유지.
- 전체 흐름 배너를 흰색 카드와 쪽빛 진입 버튼 모양으로 변경. 기존 P-03 링크 유지.
- MES·ERP·FEMS 세 앱만 유지. Figma의 SVG 형태를 참고한 저채도 아이콘, 168px 타일, 아이콘 아래 이름·분류. 모바일은 세 앱을 같은 줄로 축소.
- 기본 상태에는 설명·사용 배지·진입 안내를 숨긴다. 마우스 hover / 키보드 focus / 터치 i 버튼으로 상세 안내. Esc 닫기, 포인터를 안내 영역으로 옮겨도 유지, aria-describedby·aria-expanded 지원. 꺼진 앱은 기존대로 내 공간에 연결.
- 홈의 '아직 만들지 않은 것' 영역 제거. 설명 카드 자체·기존 흐름/도움말 접근 경로는 유지.
- 참고 코드의 학습 진도·가짜 프로필·새로고침 초기화 문구·미구현 앱·검색 기능은 가져오지 않았다.
- `Home.tsx`·`Home.css`, 홈 전용 `HomeShell.css`와 App의 홈 조건부 클래스만 제품 UI 변경. 공통 styles.css·업무 화면·3D 코드·backend·DB·스키마 변경 없음. 새 의존성 없음.
- 도움말 p-02를 실제 동작에 맞춰 갱신.

## 검증

Node 24.21.0을 PATH 앞에 지정. Python/PostgreSQL 작업 없음.

| 명령 | 결과 | exit |
|---|---|---:|
| `git fetch origin` | 8851772 기준 확인 | 0 |
| `npm --prefix frontend run typecheck` | 통과 | 0 |
| `npm --prefix frontend run lint` | 통과 | 0 |
| `npm --prefix frontend run format:check` | 통과 | 0 |
| `npm --prefix frontend run build` | 통과; 기존 3D 청크 크기 경고 | 0 |
| `npm --prefix frontend test -- --maxWorkers=2` | 418 passed / 45 files | 0 |
| `npm --prefix frontend run test:home-browser` | Chromium 8 passed / 5.4초 | 0 |
| `git diff --check` | 통과 | 0 |

- 상태별 단위 테스트 6개 추가, 브라우저 테스트 8개 추가. 항목별로 분리했다.
- 독립 `playwright.home.config.ts` 사용: 포트 5187, API 전체 모의 응답, 실제 backend·DB 접속 없음. 데스크톱 기본·hover·360px 열린 안내 스크린샷을 직접 확인했다.
- 전체 포털 통합 스모크·backend/DB 검사·Safari/실기기 검증·원격 CI는 **미실행**. 공용 8000/5173/스모크 DB는 사용하지 않았다.
- 기존 `codex/factory-building` 브랜치를 변경하지 않고 최신 main에서 별도 브랜치로 진행했다. push·main 병합·배포 없음.

## 다음·재현

```sh
cd /Users/hwang-kyoungho/projects/factory-studio-codex
export PATH="/opt/homebrew/opt/node@24/bin:/opt/homebrew/bin:/usr/bin:/bin"
npm --prefix frontend run test:home-browser
```

통합 담당자가 홈 UI 커밋을 검토/반영하고 운영 확인한다. 사용자 확인 전 push하지 않는다.
