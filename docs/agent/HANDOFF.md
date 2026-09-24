# Factory Studio 작업 인계

갱신: 2026-09-24 (FS-017b 완료, Claude Code). 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git 상태

- 저장소: `/Users/hwang-kyoungho/projects/factory-studio` **메인 폴더만 사용**.
- 브랜치: **`fs-017-portal`**.
- FS-017b 구현·인계는 커밋 `FS-017b: 흐름·카드·도움말 계약 검토와 도움말 키 결함 수정` 하나에 담겼다. `git log -1 --oneline`으로 확인한다.
- FS-017a 구현 커밋: `8f16d52db63608536cd65c5ba414a9a242b35c62`.
- WIP 보존: `9244801`, `WIP FS-017a: 중단 시점 보존`.
- 이 파일은 구현 커밋 다음의 별도 인계 커밋에 담긴다. 인계 커밋을 포함한 최종 HEAD는 `git log -1 --oneline`으로 확인한다.
- FS-016 main fast-forward 완료 기준: `e08f5d8ef3cc09477263d3e29d566cc4fd5f781a`.
- 마지막 확인 main: **`2cece7bac99fd08998746f70da1a21896901e089`**. 별도 AG 작업으로 전진했지만 **rebase하지 않았다**. FS-017c 끝에 한 번만 최신 main으로 rebase한다. main 병합·push 금지.
- `../factory-studio-ag` 및 `antigravity/*` 브랜치는 열거나 조작하지 않는다.

## FS-017b 완료 (최신)

- P-03/P-04/P-05와 `content/flow-map*.json` 초안을 FS-005a §3·§4, FS-008a, FS-011과 대조했다. 노드 17·연결 19 문구까지 일치. 결과: `docs/agent/포털_FS-017b.md`.
- 결함 수정 1건: `ContentPages.tsx` Help의 키 조회 `help[key]` → `Object.hasOwn(help, key)` (`/help/constructor`가 404를 통과해 렌더 예외).
- 신규 `frontend/src/portal/content-pages.test.tsx` 12개. frontend 51개 통과, typecheck/lint/format/build exit 0. backend·schema 변경 없음.
- **b 초안 파일은 이제 완료로 취급한다.** c 초안(아래 목록의 FS-017c)은 여전히 검토 대상이다.

## FS-017a에서 끝난 것

1. FS-016 기존 현재 세션 API에 CSRF 토큰 복구를 추가했다. 만료·종료 세션 오류 응답이 HttpOnly 쿠키를 삭제해 재진입을 허용한다.
2. 별도 회귀 파일 `backend/tests/test_portal_session.py`: CSRF 복구 / 복구 후 변경 / 만료 쿠키 삭제 / 만료 후 새 공간, 4개 독립 테스트.
3. `frontend/src/shared/`: API 클라이언트·멱등 키, 표·폼·오류 봉투·빈 상태·지연 로딩·세션 만료 안내·디자인 토큰. `src/app/`: 포털 레이아웃·라우팅·세션 경계.
4. P-01 게스트/로그인, 복사 진행·실패 재시도·만료 안내. P-02 실제 공간/세대·모듈 설정과 앱 런처. roles 없는 게스트 생성 응답 처리, 로그인 폼이 열린 상태의 게스트 재시도 보정.
5. AGENTS.md에 **30분마다 WIP, 세션 종료 시 이 인계 문서 갱신·커밋**을 상시 규칙으로 기록했다.

결과와 FS-016 staged stat 원문: `docs/agent/포털_FS-017a.md`. 현재 기획 문서와 progress.md도 갱신했다.

## 이미 있는 b/c 초안: 완료로 취급하지 말 것

처음에는 FS-017 전체를 수행하라는 지시였으므로 분할 지시가 도착하기 전에 다음 파일이 작성됐다. 사용자 지시대로 즉시 WIP에 보존했으며 삭제하지 않았다. **다음 작업은 처음부터 다시 만드는 대신 초안을 읽고 리뷰·보완·재검증한다.**

- **FS-017b**: `portal/ContentPages.tsx`, `shared/content.tsx`, `content/flow-map.json`, `content/flow-map.schema.json`, `portal/flow.test.ts`. P-03 흐름 / P-04 카드 / P-05 도움말 및 JSON 계약.
- **FS-017c**: `portal/Workspace.tsx`, `portal/Records.tsx`, `frontend/e2e/portal.spec.ts`, `playwright.config.ts`, README의 실행 안내, `docs/architecture/프론트엔드_공통패턴_FS-017.md`. P-06/P-07, 브라우저·360px, 문서 최종 확정, main rebase.
- `portal/screens.test.tsx`는 a/b/c 화면 테스트를 항목별로 포함한다. a에 추가한 테스트는 `portal/entry-home.test.tsx`로 분리돼 있다.
- 초안 경로는 현재 앱 라우터에서 열리지만 이것을 b/c 완료로 해석하지 않는다. 기능·권한·오류·동시 조작 검토가 후속 완료 조건이다.

### 다음 순서

1. AGENTS.md → 현재기획_진행현황.md → 이 문서 → 포털_FS-017a.md를 읽는다.
2. ~~FS-017b~~ 완료.
3. 사용자 승인 후 FS-017c에서 P-06/P-07과 브라우저·360px·README·패턴을 최종 점검한다. **c 끝에 최신 main으로 한 번만 rebase**한다. AG-04 등 후속 테스트 보강을 보존한다.

## 주의점·승인된 결정

- 사용자가 FS-011 누락 규약을 승인했다: 백엔드 8000, 프론트 5173(API 프록시), Vitest·Testing Library·Playwright. FS-011 §14에 기록했다.
- 업무 화면은 후속 FS-018~020 대상. 사용자는 현재 런처·흐름 맵 업무 노드를 **기존 솔루션 도움말**로 연결하도록 승인했다. 업무 API를 만들지 않는다.
- SCM 문안 미확정: 제목/카드 존재만 유지. qms/wms/bems는 기존 Markdown 그대로 표시한다.
- schema.json·마이그레이션 변경 금지. `backend/tests/test_common.py`와 `test_seed.py`는 antigravity 대상이므로 수정 금지. FS-016 분기점 대비 바이트 불변 확인했다.
- FS-016 집계 대사: 업무 7,463+workspace_module 4=7,467. workspace 1+data_generation 1을 포함하면 7,469. 실제 전체 71테이블 대사 누락 0. `공통계층_FS-016.md`의 테이블별 정의 참조.
- 게스트 실제 만료는 생성일 다음 날 00:00 Asia/Seoul이다. 현재 게스트 API는 요청마다 만료를 연장하지 않는다. 회원 유휴 만료와 혼동하지 않는다.
- 표의 정렬/CSV는 현재 페이지 기준. FS-016 관리자 API는 전역 sort 인자를 지원하지 않는다.
- `MutationKeys`의 키 보존은 화면 인스턴스 범위다. 새로고침 후 변경 요청을 자동 재전송하지 않는다. 인증·CSRF·비밀번호 영속 저장 없음.
- Vite는 frontend와 content 경로만 읽도록 fs.allow를 설정했다. Markdown raw HTML은 렌더링하지 않는다.
- `.env`에 SESSION_SECRET이 없거나 32자보다 짧으면 실제 서버는 500을 반환한다. 테스트 서버에서는 프로세스에 임의 값을 생성·주입했다. 사용자 `.env`를 임의 변경하거나 비밀을 로그로 출력하지 않았다.
- 이번에 띄운 Uvicorn은 종료했다. Playwright Vite도 종료됐다. PostgreSQL 컨테이너와 테스트 DB는 남아 있다.

## 실제 검증 이력

Python **3.14.7**, Node **24.21.0**, PostgreSQL **18.6**.

- backend 전체 15개 통과(exit 0), DB `factory_studio_fs016_test`. 실행 뒤 백엔드 코드 변경 없음.
- 프론트 typecheck/lint/format/build 모두 최종 exit 0. 전체 테스트 39개(b/c 초안 포함), a 대상 별도 19개 통과.
- 도구 회귀 44개, db:validate, R1~R5 모두 exit 0.
- 분할 지시 전 실제 Playwright 5개 통과(exit 0), DB `factory_studio_fs017_test`. **c에서 다시 실행해야 한다.** 360px과 게스트 탐색/새로고침 후 변경을 포함한다.
- 실패 이력: Vite content 접근 설정 누락 → 수정, 실제 서버 SESSION_SECRET 누락 → 테스트 프로세스 주입, 새 Testing Library 테스트의 불필요한 exact 옵션으로 typecheck/build exit 2 → 제거 후 exit 0.
- 로컬 실행 원문은 work/fs017/*.json에 있으나 Git 제외다. 다른 작업자는 아래 명령만으로 검증을 재현할 수 있다.

## 재현 명령

저장소 루트에서 실행한다. 새 설치면 먼저 uv sync와 npm ci를 수행한다.

```sh
cd /Users/hwang-kyoungho/projects/factory-studio
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
uv sync --project backend --python 3.14 --locked
npm --prefix frontend ci
python --version
node --version
npm --prefix frontend run typecheck
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
npm --prefix frontend test -- src/shared src/portal/entry-home.test.tsx
npm --prefix frontend test
```

기존 별도 테스트 DB로 backend 전체를 실행한다. 테스트는 이 DB의 데이터를 정리하므로 반드시 `_test` DB여야 한다. 아래는 .env의 접속 자격은 유지하고 DB 이름만 바꾸며 비밀을 출력하지 않는다.

```sh
uv run --project backend --env-file .env python - <<'PY'
import os, subprocess
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL']).set(database='factory_studio_fs016_test')
assert url.database.endswith('_test')
os.environ['TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
subprocess.run(['uv', 'run', '--project', 'backend', 'pytest', 'backend/tests', '-q'], check=True)
PY
python -m unittest discover -s tools -p 'test_fs0*.py' -v
npm run db:validate
python tools/audit_schema_isolation.py
git diff --check
```

DB 컨테이너 실행 방법은 README 참조. 다른 머신에서 테스트 DB가 없으면 별도 `_test` DB를 만들고 `DATABASE_URL`을 해당 DB로 지정해 기존 Alembic head를 적용한 후 실행한다. 브라우저 검증에는 별도 `factory_studio_fs017_test`를 사용하며 템플릿이 필요하다. **전체 pytest와 브라우저 서버가 같은 DB를 공유한 채 동시에 실행하지 않는다.** 로컬 브라우저·IntelliJ 명령은 README 초안에 있으며 FS-017c에서 최종 확정한다.
