# Factory Studio

공통 포털에서 MES·ERP·FEMS를 각각 독립 솔루션으로 체험하는 제조 업무 포트폴리오입니다. 실제 회사·고객 데이터는 사용하지 않습니다.

## 기준 문서와 현재 상태

- [현재 기획과 진행 현황](docs/plan/현재기획_진행현황.md): 현재 상태 단일 기준본
- [FS-013 아키텍처](docs/plan/독립솔루션_전환결정_FS-013.md), [FS-011 개발 규약](docs/architecture/개발규약_FS-011.md)
- [FS-009 실행·검증 보고](docs/agent/실행기반_FS-009.md), [진행 기록](docs/progress.md)

전체 설계는 2026-09-23 승인됐습니다. FS-009는 실행 기반과 최초 마이그레이션까지 구현했습니다. 업무 API·제품 화면·시드 생성기는 아직 없습니다. 프론트엔드 빌드는 기반 검증용 라이브러리이며 방문 가능한 앱 화면이 아닙니다.

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

`.env`의 비밀번호를 임의의 로컬 값으로 바꾸고 `DATABASE_URL`에도 같은 값을 넣습니다. `.env`는 Git 제외 대상입니다. 기존 `.env`가 있으면 복사로 덮어쓰지 않습니다. DB는 `127.0.0.1:55432`에만 공개됩니다.

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
- `content/`: 도움말·설명 카드·흐름 맵 예정 경로
- `backend/seed/`: FS-015 생성기 예정 경로, 현재 구현 없음
- `docs/`, `tools/`: 설계·검증·문서 생성 도구
- `prototypes/`: 기존 시제품, 제품 UI와 분리

역할 분담은 AGENTS.md 8장을 따릅니다. 원격 push는 사용자 확인 후 수행하며 **`git push --mirror`는 금지**합니다.
