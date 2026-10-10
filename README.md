# Factory Studio

공통 포털에서 MES·ERP·FEMS를 각각 독립 솔루션으로 체험하는 제조 업무 포트폴리오입니다. 실제 회사·고객 데이터는 사용하지 않습니다.

## 기준 문서와 현재 상태

- [현재 기획과 진행 현황](docs/plan/현재기획_진행현황.md): 현재 상태 단일 기준본
- [FS-013 아키텍처](docs/plan/독립솔루션_전환결정_FS-013.md), [FS-011 개발 규약](docs/architecture/개발규약_FS-011.md)
- [FS-009 실행·검증 보고](docs/agent/실행기반_FS-009.md), [진행 기록](docs/progress.md)

전체 설계는 2026-09-23 승인됐습니다. 현재 포털 7화면과 **3D 공장 둘러보기**, **FEMS 14/14**, **MES 15/15**, **ERP 4/18**(기준정보)을 구현했습니다. 앱 런처에서 세 솔루션 모두 화면으로 들어갑니다. 남은 것은 ERP 나머지 화면, 통합 검증(FS-021), 배포(FS-022)이며 최신 상태는 [현재 기획과 진행 현황](docs/plan/현재기획_진행현황.md)과 [작업 인계](docs/agent/HANDOFF.md)를 봅니다.

## 런타임과 설치

Python **3.14**, Node **24 LTS**, PostgreSQL **18**. `.python-version`, `.nvmrc`, 패키지 engines/requires-python, Compose 이미지로 고정합니다. Python 의존성은 `backend/uv.lock`, Node 의존성은 각 `package-lock.json`으로 고정합니다.

Node 24를 PATH에 둔 뒤 저장소 루트에서 실행합니다. macOS 이번 검증에서는 `/opt/homebrew/opt/node@24/bin`을 사용했습니다.

```sh
uv sync --project backend --python 3.14 --locked
. backend/.venv/bin/activate
npm ci
npm --prefix frontend ci
test -f .env || cp .env.example .env
```

`.env`의 비밀번호를 임의의 로컬 값으로 바꾸고 `DATABASE_URL`에도 같은 값을 넣습니다. `SESSION_SECRET`에는 32자 이상의 임의 값을 설정합니다 (`uv run --project backend python -c "import secrets; print(secrets.token_urlsafe(48))"`로 로컬 생성 가능). `.env`는 Git 제외 대상입니다. 기존 `.env`가 있으면 복사로 덮어쓰지 않습니다. DB는 `127.0.0.1:55432`에만 공개됩니다.

```sh
docker compose up -d --wait
uv run --project backend --env-file .env alembic -c backend/alembic.ini upgrade head
uv run --project backend --env-file .env python tools/verify_ddl_matches_schema.py
```

macOS에서 이번 작업이 만든 Colima 프로필을 사용할 경우:

```sh
colima start --profile factory-studio --cpu 2 --memory 4 --disk 20 --vm-type vz --runtime docker
mkdir -p work/docker-config
printf '{"cliPluginsExtraDirs":["/opt/homebrew/lib/docker/cli-plugins"]}\n' > work/docker-config/config.json
export DOCKER_CONFIG="$PWD/work/docker-config"
export DOCKER_HOST="unix://$HOME/.colima/factory-studio/docker.sock"
```

Docker Desktop/Linux의 정상 Compose 환경에서는 위 Colima 설정이 필요 없습니다. 서버 검사·덤프는 호스트 PostgreSQL 16 도구 대신 컨테이너 도구를 사용합니다.

```sh
docker compose exec -T db psql -U factory_studio -d factory_studio -c 'SHOW server_version'
docker compose exec -T db pg_dump -U factory_studio -d factory_studio --schema-only > work/schema.sql
```

## 검증

Python 가상환경과 Node 24가 활성화된 상태에서 실행합니다.

```sh
npm run db:validate
python tools/audit_schema_isolation.py
python -m unittest discover -s tools -p 'test_fs0*.py' -v
uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run build
```

DB 대조 테스트는 마이그레이션을 적용한 별도 `*_test` DB와 `TEST_DATABASE_URL`이 필요합니다. `pytest backend/tests -q`는 이 변수가 없으면 실패하며 검증을 조용히 생략하지 않습니다. 테스트는 카탈로그를 일시 변경한 뒤 롤백합니다. CI는 전용 테스트 DB에서 실행합니다.

다운그레이드는 이 리비전 소유 테이블과 데이터를 삭제하므로 검증용 DB에서만 실행합니다. 외부 객체를 연쇄 삭제하는 CASCADE는 사용하지 않습니다.

```sh
uv run --project backend --env-file .env alembic -c backend/alembic.ini downgrade base
uv run --project backend --env-file .env alembic -c backend/alembic.ini upgrade head
```

DB는 core 10 / mes 21 / erp 27 / fems 13, 총 **71테이블**입니다. `public.alembic_version`은 별도 이력 관리 테이블입니다. `schema.json`은 v0.9.1 원본을 그대로 유지하며 업무 SERVICE 정책은 후속 구현 범위입니다. `validation-report.json`은 정적 검사 결과이고 실제 DB 대사는 `docs/db/ddl-verification-report.json`을 봅니다.

## 저장소 구성

루트의 폴더·파일이 무엇인지 정리했습니다. **Git 제외** 항목은 각자 로컬에만 있고 저장소에 올라가지 않습니다.

| 경로 | 의미 |
|---|---|
| `.github/` | GitHub Actions CI(`workflows/ci.yml`): 마이그레이션·DDL 대사·backend 테스트·frontend 검사 |
| `.idea/` | IntelliJ 프로젝트 설정 (Git 제외) |
| `backend/` | API 서버(Python 3.14·FastAPI). `src/fs/`에 common(인증·세션·멱등·오류)과 core·fems·mes·erp 모듈, `alembic/` 마이그레이션, `seed/` 합성 시드 생성기, `tests/` pytest. `migrations/`는 과거에 비워 둔 자리 |
| `frontend/` | 웹 화면(React·Vite·TypeScript). `src/` 아래 app·shared·portal·fems·mes·erp·factory(3D 공장), `e2e/` Playwright 브라우저 테스트 |
| `content/` | 도움말·설명 카드 Markdown과 전체 흐름 맵 JSON (DB가 아닌 정적 파일, FS-013 D6) |
| `docs/` | 설계·결정·작업 보고 문서. 시작점은 [docs/README.md](docs/README.md). `docs/archive/prototypes/`는 설계 초기 HTML 시제품(참고용, 제품 UI 아님) |
| `tools/` | 설계·검증 도구: DB 설계서 검증·생성(`validate_db_design.py`, `build_db_design.mjs`), 스키마 격리 검사, DDL 대사, 브라우저 스모크 실행기(`run_portal_smoke.py`) |
| `node_modules/` | 루트 `package.json`의 도구 의존성(exceljs) 설치 폴더 (Git 제외). 제품 프론트 의존성은 `frontend/node_modules/` |
| `work/` | 검증 로그·스크린샷·임시 추출본 등 작업 산출물 (Git 제외). 예: `work/fs017c/` 스모크 결과, `work/fs005g-check2/` 스키마 덤프 |
| `.env` | 로컬 DB 비밀번호·`DATABASE_URL`·`SESSION_SECRET` (Git 제외, 절대 커밋하지 않음) |
| `.env.example` | `.env` 작성용 견본(비밀 값 없음) |
| `.gitignore` | Git 제외 목록 |
| `.nvmrc` | Node 버전 고정(24) |
| `.python-version` | Python 버전 고정(3.14) |
| `AGENTS.md` | AI 작업자(Claude Code·Codex·antigravity) 공통 작업 규칙 |
| `README.md` | 이 문서 |
| `docker-compose.yml` | 로컬 PostgreSQL 18 컨테이너(127.0.0.1:55432) |
| `package.json` · `package-lock.json` | **루트 도구 전용** Node 의존성(`npm run db:validate`, `npm run db:build`). 제품 프론트엔드는 `frontend/package.json` |

저장소 밖 형제 폴더: `factory-studio-codex`(Codex 전용 worktree), `factory-studio-ag`(antigravity worktree), `factory-studio-backups`(V-1 외부 백업), `factory-studio-references`(원본 참고자료, 공개 제외).

역할 분담은 AGENTS.md 8장을 따릅니다. 원격 push는 사용자 확인 후 수행하며 **`git push --mirror`는 금지**합니다.

## 로컬 포털 실행 (FS-017)

규약 포트는 백엔드 **8000**, 프론트 **5173**, DB **55432**다. 셸이 Node 26을 선택하지 않도록 먼저 PATH를 설정한다.

```sh
export PATH="/opt/homebrew/opt/node@24/bin:$PWD/backend/.venv/bin:$PATH"
node --version
python --version
```

최초 DB에서만 시드 템플릿을 만든다. 이미 템플릿이 있는 DB에서는 반복 생성하지 않는다. 회원가입·관리자 계정 자동 생성은 없다. 게스트 버튼으로 이용할 수 있다.

```sh
uv run --project backend --env-file .env python -m seed.cli template --date 2026-09-24
```

서로 다른 터미널에서 다음 두 명령을 실행한다. 브라우저는 [Factory Studio 로컬 포털](http://localhost:5173/)을 연다. 프론트의 `/api` 요청은 Vite가 백엔드로 프록시하므로 CORS 설정이나 프론트 비밀 변수가 필요 없다. Secure·HttpOnly 쿠키를 유지하기 위해 로컬 URL도 `localhost`를 사용한다.

```sh
# 터미널 1 — 저장소 루트
uv run --project backend --env-file .env python tools/start_local.py backend

# 터미널 2 — 저장소 루트
uv run --project backend --env-file .env python tools/start_local.py frontend
```

### IntelliJ 실행 구성

공유 `.run/`의 **Local - All**을 선택하면 프런트와 백엔드를 함께 실행한다. 각 구성은 `tools/start_local.py`로 기존 DB를 먼저 기동·접속 확인한다. 현재 Docker context가 `colima-factory-studio`일 때만 해당 프로필을 자동 시작하며, 다른 Docker 환경은 사용자가 먼저 기동한다. Compose 플러그인이 없으면 `docker-compose`를 사용한다. 동시 실행은 파일 잠금으로 DB 준비를 직렬화하며 데이터/볼륨을 삭제하거나 마이그레이션하지 않는다. 기존 IntelliJ 로컬 실행 구성도 같은 명령을 쓰도록 수정했다.

브라우저는 항상 `http://localhost:5173/`, 백엔드 표시 주소는 `http://localhost:8000`을 사용한다. Vite의 Node DNS 순서를 `verbatim`으로 고정해 표시 주소 변동을 막고 API 프록시 연결만 IPv4로 지정한다. `localhost`와 `127.0.0.1`은 같은 PC의 loopback이지만 브라우저 쿠키 저장소는 다르므로 주소를 혼용하지 않는다. Uvicorn 접근 로그의 `127.0.0.1`은 접속자의 내부 IP로, 브라우저 URL 변경을 의미하지 않는다.

`<repo>`는 `/Users/hwang-kyoungho/projects/factory-studio`다. Shell Script 또는 npm 실행 구성을 사용한다. `.env`는 uv의 `--env-file`에서 읽으며 실제 비밀 값을 공유 실행 구성 파일에 저장하지 않는다.

| 구성 | 작업 디렉터리 | 명령 | 필요한 환경변수 |
|---|---|---|---|
| 백엔드 개발 | `<repo>` | `uv run --project backend --env-file .env python tools/start_local.py backend` | `.env`: `DATABASE_URL`, 32자 이상 `SESSION_SECRET`; `PATH`에 uv/Python 3.14 |
| 프론트 개발 | `<repo>` | `uv run --project backend --env-file .env python tools/start_local.py frontend` | `PATH=/opt/homebrew/opt/node@24/bin:기존PATH`; 별도 VITE 환경변수 없음 |
| DB 기동 | `<repo>` | `uv run --project backend --env-file .env python tools/start_local.py db` | `.env`: `POSTGRES_PASSWORD`, 선택 `POSTGRES_PORT=55432`; Colima 사용 시 위 Docker 환경 설정 |
| 프론트 단위/화면 | `<repo>/frontend` | `npm test` | Node 24 PATH |
| 브라우저 스모크 | `<repo>` | `uv run --project backend --env-file .env python tools/run_portal_smoke.py` | Node 24 PATH·.env의 DB 접속 정보. 8000·5173 포트가 비어 있어야 함 |

### 브라우저·컴포넌트 검증

저장소 루트, Node 24 PATH에서 실행한다.

```sh
npm --prefix frontend test
npm --prefix frontend exec -- playwright install chromium
uv run --project backend --env-file .env python tools/run_portal_smoke.py
```

`run_portal_smoke.py`는 .env의 DB 접속 자격을 사용하되 DB 이름을 **factory_studio_fs017_test**로 고정한다. 이 전용 DB가 없으면 생성하고 기존 Alembic head를 적용한다. **매 실행 전 이 테스트 DB의 core/mes/erp/fems 데이터를 정리하고 시드 템플릿을 다시 만든다.** 제품 DB는 변경하지 않는다. DB 계정에는 이 테스트 DB 생성·접속 권한이 필요하다.

이 명령은 임의 SESSION_SECRET을 테스트 프로세스에만 주입하고 8000의 백엔드를 시작한 뒤 `npm --prefix frontend run test:e2e`를 실행한다. Playwright는 5173의 프론트를 시작한다. 두 서버는 검증 종료 시 종료한다. 포트가 사용 중이면 기존 서버를 재사용하거나 종료하지 않고 실행을 거부한다. 먼저 개발 서버를 종료한 후 실행한다. 브라우저 테스트는 API 응답을 모킹하지 않는다. 결과·실패 로그와 스크린샷은 Git 제외된 `work/fs017c/` 및 `work/fs017/playwright-results/`에 남는다.

전체 pytest는 별도 `TEST_DATABASE_URL`의 테스트 데이터를 정리한다. **브라우저 검증과 backend 전체 pytest를 동시에 실행하지 않는다.** 전체 pytest DB는 `factory_studio_fs016_test`, 브라우저는 `factory_studio_fs017_test`를 사용한다. 새 머신에서는 `_test` DB를 생성하고 기존 마이그레이션을 적용해야 한다.

기존 로컬 테스트 DB로 backend 전체를 실행하는 예:

```sh
uv run --project backend --env-file .env python - <<'PYTEST'
import os, subprocess
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL']).set(database='factory_studio_fs016_test')
assert url.database.endswith('_test')
os.environ['TEST_DATABASE_URL'] = url.render_as_string(hide_password=False)
# W0-2: 병렬(작업자마다 <DB>_gwN_test 복제). 시간 측정 테스트는 따로.
subprocess.run(['uv', 'run', '--project', 'backend', 'pytest', 'backend/tests', '-q', '-n', 'auto', '-m', 'not perf'], check=True)
subprocess.run(['uv', 'run', '--project', 'backend', 'pytest', 'backend/tests', '-q', '-m', 'perf'], check=True)
PYTEST
```

P-07은 ADMIN만 접근한다. 게스트/OWNER에게 메뉴를 숨기고 직접 SPA 경로 접근은 404 화면으로 표시한다. 신규 관리자 생성 화면은 범위 밖이다. API는 독립된 서버 권한 검사를 유지한다.

컴포넌트 사용법은 [FS-017 공통 패턴](docs/architecture/프론트엔드_공통패턴_FS-017.md)을 따른다.
