# Factory Studio 작업 인계

갱신: 2026-09-24 (FS-018a 완료, Claude Code). 다음 작업자는 Codex 또는 Claude Code일 수 있다.

## Git 상태

- 저장소: `/Users/hwang-kyoungho/projects/factory-studio` **메인 폴더만 사용**.
- 브랜치: **`fs-018-fems`**, main `a82670f`(FS-017 완료, origin push 완료)에서 분기.
- 구현·인계 커밋: `FS-018a: FEMS 레이아웃과 F-11 에너지원 기준정보 패턴`. WIP `b86e6bc` 포함. 최종 HEAD는 `git log -1 --oneline`.
- main 병합·push는 사용자만 한다(`git fetch . fs-018-fems:main`, ff만).
- `../factory-studio-ag`는 main `2cece7b` 기준이다. antigravity 작업 전 최신 main에서 새 `antigravity/*` 브랜치를 만들어야 한다.

## FS-018a에서 끝난 것

- FEMS 레이아웃(좌측 사이드바, `femsScreens`에 구현 화면만) + F-11 에너지원 CRUD. 런처 FEMS 카드 → `/fems`.
- `backend/src/fs/common/scope.py`: 업무 API의 세대·모듈 재확인과 공간 잠금. **ERP·MES도 이것을 쓴다.**
- `backend/src/fs/fems/`: router/schema/service/repository. 규칙은 FS-010 §7 "FS-018a에서 확정한 업무 API 공통 규칙".
- 공통 컴포넌트: `PageTitle help`, `ErrorNotice` 참조 건수 목록, `DataTable empty`. `api()`는 `/api/`로 시작하는 경로를 그대로 호출.
- FEMS·도움말 lazy 로딩(번들 경고 해소).
- 상세·antigravity 복제 가이드: `docs/agent/FEMS_FS-018a.md`.

## 다음 할 일

1. 사용자 승인 후 **FS-018b**: F-02 계측 조회(조회형 패턴 첫 구현). 기간 필터, 1시간 해상도 고정, **결측 구간은 "결측" 행으로 표시**, 품질 이상 저채도 배지, 표/선 그래프 전환(기본 표). REPEATABLE READ 조회, offset 페이지.
2. antigravity 병행 가능: F-09 사업장·공간, F-10 설비, F-14 요금제(복제 가이드 참조). F-12·F-13은 구조가 달라 Claude Code/Codex.
3. 계산 화면 F-01·F-03~F-08은 FS-018b 이후. F-07은 목표=실적×95% 문제를 화면에서 보고 사용자 판단.

## 주의점

- schema.json·마이그레이션 변경 금지. `test_common.py`·`test_seed.py`는 antigravity 소유, `conftest.py`는 Codex 소유.
- 업무 쓰기는 반드시 `write_scope` 뒤에 한다. 세션의 generation_id를 그대로 쓰지 않는다(초기화 경합).
- 마스터 CRUD는 audit_event를 남기지 않는다(결정 보류, FS-021).
- 흐름 맵 `energy_master` 노드는 아직 도움말 연결. content 계약 변경은 FEMS 화면이 더 생긴 뒤.
- `.env`에 SESSION_SECRET(32자 이상)이 필요하다. 테스트는 프로세스에 합성 값을 주입한다.

## 실제 검증 (FS-018a 최종 코드)

Python 3.14.7 / Node 24.21.0 / PostgreSQL 18.6. 모두 exit 0: frontend typecheck/lint/format/build/test(84), ruff check/format, backend 전체 pytest 62(`factory_studio_fs016_test`), `tools/run_portal_smoke.py` Playwright 20(`factory_studio_fs017_test`), tools unittest 44, db:validate, audit_schema_isolation, git diff --check. pytest와 브라우저는 순차 실행.

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
