# ABOUT 코덱스 인계 (2026-11-08)

자기소개(`/about`)와 기술 노트(`/notes`) 구현을 Codex에 맡긴다. 설계·Figma 시안은 Claude Code가 ABOUT-01에서 끝냈다.
아래 `---` 아래를 그대로 Codex에 붙여 넣는다.

---

Factory Studio 저장소에서 공개 자기소개 페이지 `/about`과 기술 노트 `/notes`를 구현한다.
`/Users/hwang-kyoungho/projects/factory-studio`

## 0. 먼저 읽는다 (추측 금지)

1. `AGENTS.md` — 작업 규칙 전부. 특히 §1(작업 ID 하나씩, 보고 후 확인), §5(미실행 검증을 완료로 적지 않음), §6(30분 WIP 커밋·HANDOFF), §7(UI 기준)
2. `docs/ui/자기소개_기술노트_설계_ABOUT-01.md` — **이번 작업의 설계서. 화면 문안은 4장 표가 기준본이다.**
3. `docs/agent/HANDOFF.md` 맨 위 항목 — 최근 함정(로컬 CI 백엔드 병렬 불안정 등)
4. `docs/ui/공통UI규약_UI-02.md`, `frontend/src/shared/styles.css` `:root` — 토큰

## 1. Figma 연결 — 시안이 구현 기준이다

Figma MCP 서버를 연결한다(공식 원격 서버 `https://mcp.figma.com/mcp`, 사용자 계정으로 OAuth). 연결이 안 되면 **추측으로 그리지 말고 멈춰서 보고한다.**

- 파일: `https://www.figma.com/design/v7bouCuBnFf2E7qpqqzRMX` · fileKey `v7bouCuBnFf2E7qpqqzRMX`
- **PC 1440 기준 설계다**(사용자 결정). 모바일 시안은 없다.

| 화면 | nodeId | 구현 ID |
|---|---|---|
| `/about` — PC 1440 | `7:309` | ABOUT-02·03 |
| `/about` — 프로젝트 카드 펼침 상태 | `8:436` | ABOUT-02 |
| `/notes` — PC 1440 | `8:695` | ABOUT-04 |
| `/notes/:slug` — PC 1440 | `8:761` | ABOUT-04 |
| Components(토큰·컴포넌트 8종) | `2:24` | 공통 |

화면마다 `get_design_context`(fileKey·nodeId)와 `get_screenshot`을 먼저 받는다. 스크린샷은 **눈으로 맞출 기준**이고 코드에 이미지로 넣지 않는다.

Figma ↔ 코드 대응:
- 변수 컬렉션 `EIP tokens` = `shared/styles.css` `:root`. `color/bg`→`--bg`, `color/surface`→`--surface`, `color/surface-2`→`--surface-2`, `color/ink`→`--ink`, `color/muted`→`--muted`, `color/border`→`--border`, `color/accent`→`--accent`, `color/accent-soft`→`--accent-soft`, `space/N`→`--s1~s6`(4·8·12·16·20·24, 32·48은 기존 규칙대로), `radius/sm·md·lg`→`--radius-sm`·`--radius`·`--radius-lg`. **hex를 새로 하드코딩하지 않는다.**
- 글꼴: 시안은 Noto Sans KR(계정에 Pretendard 없음). 코드는 `:root`의 Pretendard 순서를 그대로 쓴다.
- 컴포넌트 8종 → 코드: Chip, Button(Primary/Secondary), StatTile, SectionHeading, TimelineRow, ProjectCard(Collapsed/Expanded), NoteCard, Tab(Active/Inactive). **`frontend/src/shared/`에 같은 역할의 공통 컴포넌트가 이미 있으면 그것을 쓴다**(예: 배지·버튼·탭). 없을 때만 `portal/about/` 안에 만든다.
- 시안의 기술 노트 날짜·요약은 자리 표시용이다. 실제 값은 `content/notes/*.md`에서 온다.

## 2. 단계 (하나씩 끝내고 보고, 사용자 확인 전 다음 단계 금지)

| ID | 내용 | 파일 |
|---|---|---|
| ABOUT-02 | `/about` 라우트·화면. 상단 바 · 좌측 섹션 목차(스크롤 위치에 따라 현재 항목 강조, 앵커 이동) · Hero 2단 · 경력 2열 · 프로젝트 탭(FEMS/MES/개인)+카드 2열(펼침/접힘) · 기술 스택 · 수상/교육 2열 · 기술 노트 최신 3편 · 연락 띠 | `frontend/src/app/App.tsx`(`<Route path="/about">`를 `"/"` 옆에, **`Layout`·`Private` 밖**) · `frontend/src/portal/About.tsx` · `About.css` |
| ABOUT-03 | 자기소개 콘텐츠를 데이터로 분리 | `content/about/profile.json` — 설계서 4장 표 그대로. 화면은 이 파일만 읽는다(문안 하드코딩 금지) |
| ABOUT-04 | 기술 노트 목록·본문 | `frontend/src/shared/content.tsx`에 `content/notes/*.md` glob 추가(기존 help·cards와 같은 방식) · `portal/Notes.tsx` · 없는 slug는 기존 `NotFound`. 규칙: 1행 `# 제목`, 2행 `> YYYY-MM-DD · 카테고리 · 태그, 태그`, 파일명 `YYYY-MM-DD-slug.md`, 날짜 역순. **노트 0편이면 `/about`의 기술 노트 섹션을 숨긴다.** 예시 노트는 1편만 넣고 첫 줄에 `<!-- 예시: 사용자가 다시 쓴 글로 교체 -->` |
| ABOUT-05 | 로그인 화면 링크 | `frontend/src/portal/Entry.tsx` `entry-footer`에 "만든 사람 →" `/about` 링크 1개 |
| ABOUT-06 | 링크 미리보기 | `frontend/about.html`(index.html 복제 + `og:title`·`og:description`, 같은 SPA 번들) · `vite.config.ts` 다중 입력. **Nginx 설정은 레포 밖(운영 서버)이다** — 필요한 블록(`location = /about { try_files /about.html =404; }`)을 보고에 적고 직접 배포하지 않는다 |
| ABOUT-07 | 공개용 이력서 PDF 버튼 | 버튼과 경로(`/resume/hwang-kyoungho.pdf`)만 만든다. **PDF 파일은 사용자가 공개본을 줄 때까지 넣지 않는다**(파일 없으면 버튼 숨김) |

## 3. 반드시 지킬 것

### 브랜치
- `codex/about-02` 같은 별도 브랜치. **`docs/about-01`에서 분기한다**(설계서가 여기 있다). main·`ui-redesign-01`에 직접 커밋·푸시하지 않는다.
- `docs/about-01`은 `ui-redesign-01`(미병합 UI 재구성) 위에 있다. 공통 CSS(`shared/styles.css`)를 바꿔야 하면 먼저 보고한다.

### 공개 콘텐츠 (설계서 5장)
- **넣지 않는다:** 휴대폰 번호 · 주소 · 생년 · 병역 · 연봉 · 이직 사유 · 특정 회사 지원 동기 · 논문(학회 포스터) · 고객사·거래처 실명. 연락은 이메일·GitHub만.
- 원천 자료(이력서 .docx, 경력기술서 .pdf, Notion)는 레포에 넣지 않는다. 문안은 설계서 4장에서만 가져온다.

### 범위 밖
- 백엔드·DB·API 변경 없음. 로그인·세션 로직을 건드리지 않는다.
- 모바일 전용 디자인 없음. **폭이 좁으면 1열로 떨어지는 최소 처리만**(목차 숨김, 그리드 1열).
- Notion API 연동 없음. 기술 노트 본문 작성은 사용자 몫.
- GW(`gw/*`)는 별도 Codex 트랙 소유. 건드리지 않는다.

### 검증 (실행한 것만 통과로 적는다)
- `npm --prefix frontend run typecheck` · `lint` · `format:check` · `test` · `build`
- 테스트 추가 `frontend/src/portal/about.test.tsx`: 비로그인으로 `/about`·`/notes`·`/notes/:slug` 열림 · Hero 이름·숫자 렌더 · 프로젝트 탭 전환 · 카드 펼침/접힘 · 노트 0편이면 섹션 없음 · 없는 slug는 NotFound · 화면에 전화번호 패턴(`010-`)이 없음
- 브라우저 1440×900에서 Figma 스크린샷과 나란히 비교. 좁은 폭(390)은 깨짐 여부만.
- 끝나면 `docs/progress.md`·`docs/plan/현재기획_진행현황.md`·`docs/agent/HANDOFF.md` 갱신(AGENTS.md §0·§6).

## 4. 보고 형식

작업 ID마다: 바꾼 파일 · Figma와 다른 곳(이유) · 실행한 검증과 결과 · 실행하지 못한 검증 · 다음 ID.
