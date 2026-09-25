# Factory Studio 작업 인계

갱신: 2026-09-25 (FS-018k F-13 완료, Claude Code). **다음 세션은 이 문서부터 읽는다.**

## Git 상태

- 저장소: `/Users/hwang-kyoungho/projects/factory-studio`
- main·origin: `5bcc4d2`(FS-018j + COOKIE_SECURE 수정), CI 통과.
- 브랜치 **`fs-018k-f13`**: F-13 환산·배출계수 커밋. push·main 병합은 사용자 확인 뒤.
- `gh` CLI 로그인 완료(go8105). CI는 `gh run list` / `gh run watch <id> --exit-status`로 직접 확인한다.
- 정정: 이전 인계의 "`78e1206` CI도 날짜 때문에 실패했을 것"은 틀렸다. 그 실행은 09-24에 돌아 성공했다.

## 다음 작업

1. `fs-018k-f13` push → CI 확인 → main ff.
2. F-12 계측기·채널 → F-09 사업장·공간.
3. Codex는 main `5bcc4d2` 이후 conftest 단축 작업 가능. 병합 순서는 아래 규칙.

## 병행 운영 (2026-09-25 사용자 지시)

- **Claude Code**: 메인 폴더에서 FEMS 남은 화면을 순차 진행(F-06 마무리 → F-13 → F-12 → F-09).
- **Codex**: **메인 폴더를 쓰지 않는다.** 전용 worktree `../factory-studio-codex`, 브랜치 `codex/*`. 이번 쿠키 변경처럼 같은 폴더를 동시에 쓰면 서로의 미커밋 변경이 섞인다.
- Codex 첫 작업: backend 테스트 시간 단축(conftest). FEMS 테스트 fixture를 건드리므로 **F-06이 main에 들어간 뒤** 시작한다.
- 병합 순서: 먼저 끝난 쪽을 main에 ff, 나중 쪽이 rebase. rebase는 Claude Code가 맡는다.

## 주의점

- **ruff는 CI와 같은 범위로 돌린다**: `uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py` + 같은 범위 `ruff format --check`. `tools` 폴더 전체를 넣으면 CI 밖 파일 오류가 쏟아진다.
- **backend 테스트는 CI 환경으로**: DATABASE_URL·TEST_DATABASE_URL·PATH·HOME만. `.env`를 쓰면 SESSION_SECRET 등이 섞여 CI와 결과가 달라진다.
- **날짜에 의존하는 테스트를 만들지 않는다**: 게스트를 만드는 테스트는 `FS_TODAY`를 템플릿 날짜로 고정한다.
- schema.json·마이그레이션 변경 금지. `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 확정·게시 데이터 불변, 업무 쓰기는 `write_scope` 뒤, 결측(invalid)은 합계에서 제외.

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

브라우저 스모크(전용 DB 초기화·서버 시작/종료 포함, 8000·5173 포트가 비어 있어야 함):

```sh
uv run --project backend --env-file .env python tools/run_portal_smoke.py
```
