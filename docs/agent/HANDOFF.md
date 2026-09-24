# Factory Studio 작업 인계 — FS-017c 완료

갱신: 2026-09-24. 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## 현재 Git 상태

- 저장소: `/Users/hwang-kyoungho/projects/factory-studio` 메인 폴더만 사용.
- 브랜치: **fs-017-portal**. FS-017a/b/c 전체 완료, 사용자 보고 후 정지.
- 마지막 구현·검증 완료 커밋: **2e7889b19c3528eec9bdcd620896bb865cda53b6** (`FS-017c: 내 공간·운영 기록 확정과 rebase 후 전체 검증 완료`). 이 해시를 기록하는 인계 커밋이 그 다음 HEAD다.
- 구현 보존 WIP: **4f5cea9** (rebase 전 **88f69b1**). 최신 완료·인계 커밋은 `git log -2 --oneline`으로 확인한다.
- 착수 HEAD **cbcd5c5**에서 시작했고, **main 2cece7bac99fd08998746f70da1a21896901e089로 rebase를 한 번 완료**했다. 다시 rebase할 필요 없다.
- a/b의 현재 커밋: **425fc61** / **730671a**. 옛 보고서의 8f16d52/cbcd5c5 등은 rebase 전 이력이다.
- **main 병합·push 미실행**. 사용자 승인 전 수행하지 않는다. `../factory-studio-ag`, `antigravity/*` 브랜치 조작 금지.

## 끝난 것

- FS-017a: 세션 조회 CSRF 복구·만료 HttpOnly 쿠키 삭제, 독립 backend 회귀, 공통 레이아웃·표·폼·오류·빈 상태·로딩·만료 안내, P-01/P-02.
- FS-017b: P-03 흐름 17노드/19연결·JSON 계약, P-04 기존 카드·SCM 제목만, P-05 도움말 허브/맥락 문서·잘못된 키 404.
- FS-017c: P-06 초기화 확인/중복/이동 차단, 토글 실패 상태 유지, 불확실 요청 동일 키 재확인, POST 성공 후 GET 실패의 조회만 재시도, KST 고정 만료/남은 시간. P-07 ADMIN 경계·GUEST/OWNER 404, offset 페이지·읽기 전용·인라인 재시도.
- README 로컬/IntelliJ 실행 안내와 프론트 공통 패턴 확정. 초안 상태 해제.
- 실제 브라우저 항목별 16개, 신규 c 화면 테스트 21개. `tools/run_portal_smoke.py`로 테스트 DB·시드·테스트 서버 시작/종료 재현.
- 현황/progress 문서 충돌을 풀어 AG-03/04와 FS-017 이력을 함께 보존했다. **AG-04 test_common 11개·AG-03 test_seed 16개 분리를 main과 바이트 동일하게 유지**했다.

보고서: `docs/agent/포털_FS-017c.md`. 앞 조각 이력: 포털_FS-017a.md/포털_FS-017b.md.

## 다음 할 일

**이번 작업의 남은 구현 없음. 사용자 결과 확인을 기다린다.** main 병합이나 후속 FS-018(FEMS)을 자동으로 시작하지 않는다. 후속 반복 화면은 `docs/architecture/프론트엔드_공통패턴_FS-017.md`를 따른다.

## 주의점

- schema.json·마이그레이션·content/는 이번 c 착수 시점과 변경 0. test_common.py·test_seed.py는 main 그대로, conftest.py도 변경 없음.
- **30분마다 WIP 커밋, 세션 종료 시 HANDOFF 갱신·커밋.** `.env`·work/를 스테이징에서 제외한다.
- 업무 API·업무 화면은 후속 범위. 사용자 승인에 따라 활성 솔루션/업무 노드는 기존 도움말로 연결한다. 비활성 앱은 내 공간으로 이동한다. SCM 새 문안 추가 금지.
- 게스트 만료는 생성일 다음 날 00:00 KST, 요청 시 연장되지 않는다. 회원 유휴 만료와 구분한다.
- `busy`는 요청 중 조작·이동 잠금, `navigationBlocked`는 초기화 결과 불확실 동안 이동 잠금 유지다. 동일 키 재시도는 가능하다. 키 보존 범위는 현재 화면 인스턴스이며 새로고침 후 변경 요청을 자동 재전송하지 않는다.
- 브라우저 뒤로가기/프로그램 이동 동안 잠긴 라우트를 계속 렌더링하며 잠금 해제 뒤 요청된 경로로 이동한다. 강제 탭 종료·별도 탭까지 클라이언트 잠금이 보장하지는 않는다.
- 표 정렬/CSV는 현재 페이지 기준. 관리자 API는 서버 id 내림차순 offset 페이지다.
- `.env`에 DATABASE_URL과 32자 이상 SESSION_SECRET이 필요하다. 실제 비밀을 Git·로그에 넣지 않는다. 테스트 실행기는 임의 세션 비밀을 프로세스에만 주입한다.
- 테스트용 Uvicorn/Vite는 종료됐다. PostgreSQL과 테스트 DB는 유지한다.

## rebase 후 실제 검증

Python **3.14.7** / Node **24.21.0** / PostgreSQL **18.6**.

- frontend typecheck/lint/format:check/build/test: 각각 exit 0, **72 passed**.
- Playwright: exit 0, **16 passed**. 실제 API, 게스트→런처·탐색·새로고침 후 변경·게스트 404·360px 7종.
- backend 전체: exit 0, **40 passed** (main 36 + FS-017a 4).
- tools unittest: exit 0, **44 passed**. db:validate·R1~R5·git diff --check도 각각 exit 0.
- 새 runner Ruff lint/format: 각각 exit 0. 새 의존성 없음.
- backend pytest DB **factory_studio_fs016_test**, 브라우저 DB **factory_studio_fs017_test**. 반드시 순차 실행.
- Vite 약 529KB 단일 번들 크기 경고와 기존 backend upstream 경고 2건은 비실패 메시지다.
- 미실행: Firefox/WebKit·공개 배포·IntelliJ GUI에서 실행 구성 직접 생성·실제 관리자/OWNER 브라우저 로그인. 권한은 화면 테스트와 backend 전체 테스트로 검증했다.

## 재현 명령

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
npm --prefix frontend test
```

기존 마이그레이션이 적용된 별도 `_test` DB로 백엔드를 검증한다. 접속 URL은 출력하지 않는다.

```sh
uv run --project backend --env-file .env python - <<'PY'
import os, subprocess
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL']).set(database='factory_studio_fs016_test')
assert url.database.endswith('_test')
os.environ['TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
subprocess.run(['uv', 'run', '--project', 'backend', 'pytest', 'backend/tests', '-q'], check=True)
PY
python -m unittest discover -s tools -v
npm run db:validate
python tools/audit_schema_isolation.py
npm --prefix frontend exec -- playwright install chromium
uv run --project backend --env-file .env python tools/run_portal_smoke.py
git diff --check
```

브라우저 runner는 **factory_studio_fs017_test만 매 실행 초기화**한 뒤 템플릿 7,469행과 테스트 서버를 준비한다. 제품 DB는 변경하지 않는다. 8000/5173에 기존 서버가 있으면 먼저 사용자가 종료해야 하며, runner는 기존 프로세스를 종료하지 않는다. PostgreSQL/새 테스트 DB 준비와 IntelliJ 작업 디렉터리·환경변수는 README 참조. 검증 원문은 work/fs017c/post-rebase-verification.json에 있으나 Git 제외이며 위 명령으로 재현 가능하다.
