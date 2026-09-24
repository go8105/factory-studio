# Factory Studio

공통 포털에서 MES·ERP·FEMS를 각각 독립 솔루션으로 체험하는 제조 업무 포트폴리오입니다. 실제 회사·고객 데이터는 사용하지 않습니다.

## 기준 문서와 현재 상태

- [현재 기획과 진행 현황](docs/plan/현재기획_진행현황.md): 현재 상태 단일 기준본
- [FS-013 아키텍처](docs/plan/독립솔루션_전환결정_FS-013.md), [FS-011 개발 규약](docs/architecture/개발규약_FS-011.md)
- [FS-009 실행·검증 보고](docs/agent/실행기반_FS-009.md), [진행 기록](docs/progress.md)

전체 설계는 2026-09-23 승인됐습니다. FS-009 실행 기반, FS-015 시드, FS-016 공통 API에 이어 FS-017 포털 P-01~P-07을 구현했습니다. 업무 API·MES/ERP/FEMS 업무 화면은 후속 범위이며, 현재 앱 런처의 솔루션 선택은 해당 솔루션 도움말로 연결됩니다.

## 런타임과 설치

Python **3.14**, Node **24 LTS**, PostgreSQL **18**. `.python-version`, `.nvmrc`, 패키지 engines/requires-python, Compose 이미지로 고정합니다. Python 의존성은 `backend/uv.lock`, Node 의존성은 각 `package-lock.json`으로 고정합니다.

Node 24를 PATH에 둔 뒤 저장소 루트에서 실행합니다. macOS 이번 검증에서는 `/opt/homebrew/opt/node@24/bin`을 사용했습니다.

```sh
uv sync --project backend --python 3.14 --locked
. backend/.venv/bin/activate
npm ci
npm --prefix frontend ci
cp .env.example .env
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

DB는 core 10 / mes 21 / erp 27 / fems 13, 총 **71테이블**입니다. `public.alembic_version`은 별도 이력 관리 테이블입니다. `schema.json`은 v0.9.1 원본을 그대로 유지하며 SERVICE/DB_POLICY 80개는 아직 구현하지 않았습니다. `validation-report.json`은 정적 검사 결과이고 실제 DB 대사는 `docs/db/ddl-verification-report.json`을 봅니다.

## 디렉터리와 협업

- `backend/src/fs/`: FastAPI 조립 자리와 common/core/mes/erp/fems 경계
- `backend/alembic/`: 최초 마이그레이션. 기존 `backend/migrations/`는 과거 빈 자리
- `frontend/src/`: app/shared/portal/mes/erp/fems 뼈대
- `content/`: 도움말·설명 카드 Markdown, 흐름 맵 JSON/JSON Schema
- `backend/seed/`: FS-015 결정적 템플릿·게스트 복사 생성기
- `docs/`, `tools/`: 설계·검증·문서 생성 도구
- `prototypes/`: 기존 시제품, 제품 UI와 분리

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
uv run --project backend --env-file .env uvicorn fs.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend/src

# 터미널 2 — 저장소 루트
npm --prefix frontend run dev
```

### IntelliJ 실행 구성

`<repo>`는 `/Users/hwang-kyoungho/projects/factory-studio`다. Shell Script 또는 npm 실행 구성을 사용한다. `.env`는 uv의 `--env-file`에서 읽으며 실제 비밀 값을 공유 실행 구성 파일에 저장하지 않는다.

| 구성 | 작업 디렉터리 | 명령 | 필요한 환경변수 |
|---|---|---|---|
| 백엔드 개발 | `<repo>` | `uv run --project backend --env-file .env uvicorn fs.main:app --host 127.0.0.1 --port 8000 --reload --reload-dir backend/src` | `.env`: `DATABASE_URL`, 32자 이상 `SESSION_SECRET`; `PATH`에 uv/Python 3.14 |
| 프론트 개발 | `<repo>/frontend` | `npm run dev` | `PATH=/opt/homebrew/opt/node@24/bin:기존PATH`; 별도 VITE 환경변수 없음 |
| DB 기동 | `<repo>` | `docker compose up -d --wait` | `.env`: `POSTGRES_PASSWORD`, 선택 `POSTGRES_PORT=55432`; Colima 사용 시 위 Docker 환경 설정 |
| 프론트 단위/화면 | `<repo>/frontend` | `npm test` | Node 24 PATH |
| 브라우저 스모크 | `<repo>/frontend` | `npm run test:e2e` | Node 24 PATH; 8000에 전용 `*_test` DB를 사용하는 백엔드 실행 |

### 브라우저·컴포넌트 검증

```sh
npm --prefix frontend test
npm --prefix frontend exec -- playwright install chromium
npm --prefix frontend run test:e2e
```

Playwright는 5173의 Vite 서버를 직접 시작·종료한다. 이미 개발 프론트가 켜져 있으면 종료한 뒤 실행한다. 브라우저 테스트는 실제 API로 게스트 공간을 생성하므로 반드시 전용 테스트 DB를 사용한다. `DATABASE_URL`을 해당 `*_test` DB로 지정하고 마이그레이션·시드 템플릿을 적용한 뒤 위 백엔드 명령을 실행한다. 세션 비밀도 테스트용 임의 값을 주입한다. 테스트를 반복해 게스트 20개 상한에 도달하면 테스트 DB에서만 만료 시간을 경과시키거나 전용 DB를 재구성한다. 제품 DB를 테스트에 연결하지 않는다.

전체 백엔드 테스트는 별도 `TEST_DATABASE_URL`의 테이블을 정리한다. **브라우저 서버 DB와 전체 pytest DB를 공유해 동시에 실행하지 않는다.** 이번 검증은 브라우저 `factory_studio_fs017_test`, 전체 pytest `factory_studio_fs016_test`를 사용했다.

컴포넌트 사용법은 [FS-017 공통 패턴](docs/architecture/프론트엔드_공통패턴_FS-017.md)을 따른다.
