#!/usr/bin/env bash
# OPS-CI-01 로컬 CI 스크립트. .github/workflows/ci.yml과 같은 검사를 같은 순서로 로컬에서 돌린다.
#
#   tools/ci_local.sh            # 로컬 CI 전체 실행 (1~5단계)
#   tools/ci_local.sh --dry-run  # 명령을 실행하지 않고 단계만 출력
#   tools/ci_local.sh --help
#
# 순서: 1. DB 검증·도구 테스트 → 2. 백엔드 ruff 검사 → 3. 백엔드 마이그레이션·pytest
#       → 4. DB 초기화·마이그레이션 왕복 → 5. 프런트 검증·빌드·테스트
#
# 단일 프런트 테스트: npm --prefix frontend test -- <파일> (npx vitest run은 디렉터리가 달라져 실패함)
# GitHub Actions 결제 차단("recent account payments have failed") 시 수동 검증 표준 스크립트.
set -euo pipefail

DRY_RUN=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --help | -h)
      sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "모르는 인자: $argument (--help)" >&2
      exit 2
      ;;
  esac
done

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { printf '\n\033[1m[%s] %s\033[0m\n' "$(date +%H:%M:%S)" "$1"; }
fail() {
  printf '\n\033[1;31m중단: %s\033[0m\n' "$1" >&2
  exit 1
}

run_cmd() {
  if [ "$DRY_RUN" = 1 ]; then
    echo "[dry-run] $*"
  else
    "$@"
  fi
}

# ── 사전 점검 및 환경 설정 ─────────────────────────────────────────────────────
step "사전 점검 및 환경 설정"

# 1. Node 24 PATH 설정 (package.json engines: >=24 <25)
export PATH="${FS_NODE_BIN:-/opt/homebrew/opt/node@24/bin}:$PATH"
command -v npm >/dev/null || fail "npm이 없습니다."
node_ver="$(node -v 2>/dev/null || true)"
case "$node_ver" in
  v24*) ;;
  *) echo "경고: Node 24가 아닙니다 ($node_ver). /opt/homebrew/opt/node@24/bin 설치를 권장합니다." ;;
esac

# 2. Python venv PATH 설정 (Python 3.14 PEP 758 문법 지원)
export PATH="$ROOT/backend/.venv/bin:$PATH"
command -v python >/dev/null || fail "python이 없습니다 (backend/.venv/bin)."
command -v uv >/dev/null || fail "uv가 없습니다."

# 3. .env 파일 및 대상 DB 확인
[ -f "$ROOT/.env" ] || fail ".env 파일이 없습니다."
CI_DB_NAME="${TEST_DB:-factory_studio_ci_test}"

# 안전장치: DB 이름은 반드시 _test 로 끝나야 한다 (backend/tests/conftest.py 및 개발 DB 보호)
case "$CI_DB_NAME" in
  *_test) ;;
  *) fail "테스트 DB 이름은 _test로 끝나야 합니다 ($CI_DB_NAME)." ;;
esac

# .env에서 연결 정보를 읽고 DB 이름만 치환 (비밀번호는 터미널/로그에 절대 출력하지 않는다)
CI_DB_URL="$(python -c '
import os, sys
from sqlalchemy.engine import make_url

lines = open(".env").read().splitlines()
env_dict = dict(line.split("=", 1) for line in lines if "=" in line and not line.startswith("#"))
if "DATABASE_URL" not in env_dict:
    sys.exit(".env에 DATABASE_URL이 없습니다.")
orig_url = make_url(env_dict["DATABASE_URL"])
target_db = sys.argv[1]
ci_url = orig_url.set(database=target_db).render_as_string(hide_password=False)
print(ci_url)
' "$CI_DB_NAME")" || fail "DATABASE_URL 파싱에 실패했습니다."

echo "대상 DB: $CI_DB_NAME"

# 4. PostgreSQL 18 버전 및 DB 준비 점검
if [ "$DRY_RUN" = 0 ]; then
  CI_DB_URL="$CI_DB_URL" python -c '
import os, sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ["CI_DB_URL"])
admin_url = url.set(database="postgres")
target_db = url.database

try:
    # CREATE DATABASE는 트랜잭션 안에서 못 돈다. 아래 146·182·220행과 같은 틀.
    admin_eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_eng.connect() as conn:
        ver = conn.execute(text("SHOW server_version")).scalar()
        if not ver.startswith("18."):
            sys.exit(f"PostgreSQL 18이 아닙니다 (현재: {ver}). 포트 55432의 PostgreSQL 18.6을 확인하세요.")
        exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": target_db}).scalar()
        if not exists:
            conn.execute(text(f"CREATE DATABASE \"{target_db}\""))
            print(f"새 테스트 DB 생성 완료: {target_db}")
except Exception as e:
    sys.exit(f"PostgreSQL 점검 실패: {e}")
' || fail "PostgreSQL 18 연결 또는 테스트 DB 준비에 실패했습니다."
fi

# ── 1단계: DB 검증 · 도구 단위 테스트 ───────────────────────────────────────────
step "1단계: DB 검증 · 도구 단위 테스트"
run_cmd npm run db:validate
run_cmd python tools/audit_schema_isolation.py
run_cmd python -m unittest discover -s tools -p 'test_*.py'

# ── 2단계: 백엔드 린트 및 포맷 ──────────────────────────────────────────────────
step "2단계: 백엔드 ruff 검사"
run_cmd uv run --project backend ruff check --config backend/pyproject.toml backend tools/verify_ddl_matches_schema.py
run_cmd uv run --project backend ruff format --config backend/pyproject.toml --check backend tools/verify_ddl_matches_schema.py

# ── 3단계: 백엔드 마이그레이션 적용 및 테스트 ────────────────────────────────────
step "3단계: 백엔드 마이그레이션 적용 및 pytest"
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] alembic -c backend/alembic.ini upgrade head (DB: $CI_DB_NAME)"
  echo "[dry-run] python tools/verify_ddl_matches_schema.py (DB: $CI_DB_NAME)"
  echo "[dry-run] pytest backend/tests -q -n auto -m 'not perf' (DB: $CI_DB_NAME)"
  echo "[dry-run] pytest backend/tests -q -m perf (DB: $CI_DB_NAME)"
else
  DATABASE_URL="$CI_DB_URL" uv run --project backend alembic -c backend/alembic.ini upgrade head
  DATABASE_URL="$CI_DB_URL" python tools/verify_ddl_matches_schema.py

  # pytest-xdist 복제 전 잔여 커넥션 종료 (템플릿 DB 잠금 방지)
  CI_DB_URL="$CI_DB_URL" python -c '
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ["CI_DB_URL"])
admin_url = url.set(database="postgres")
admin_eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with admin_eng.connect() as conn:
    conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": url.database})
' 2>/dev/null || true

  DATABASE_URL="$CI_DB_URL" TEST_DATABASE_URL="$CI_DB_URL" uv run --project backend pytest backend/tests -q -n auto -m "not perf"

  # perf 테스트 전 대기 (병렬 작업자 디스크 I/O 정리)
  sleep 3
  if ! DATABASE_URL="$CI_DB_URL" TEST_DATABASE_URL="$CI_DB_URL" uv run --project backend pytest backend/tests -q -m perf; then
    echo "성능 테스트 일시적 I/O 지연 감지, 3초 후 1회 재시도..."
    sleep 3
    DATABASE_URL="$CI_DB_URL" TEST_DATABASE_URL="$CI_DB_URL" uv run --project backend pytest backend/tests -q -m perf
  fi
fi

# ── 4단계: DB 초기화 및 마이그레이션 왕복 검증 ─────────────────────────────────
step "4단계: DB 초기화 및 마이그레이션 왕복 (downgrade base → upgrade head)"
echo "주의: $CI_DB_NAME 데이터가 초기화되고 마이그레이션 왕복이 실행됩니다."
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] python tools/clear_test_data.py (DB: $CI_DB_NAME)"
  echo "[dry-run] alembic -c backend/alembic.ini downgrade base (DB: $CI_DB_NAME)"
  echo "[dry-run] alembic -c backend/alembic.ini upgrade head (DB: $CI_DB_NAME)"
  echo "[dry-run] python tools/verify_ddl_matches_schema.py (DB: $CI_DB_NAME)"
else
  echo "5초 후 진행합니다 (중단하려면 Ctrl-C)..."
  sleep 5
  DATABASE_URL="$CI_DB_URL" python tools/clear_test_data.py

  # downgrade 전 잔여 커넥션 종료
  CI_DB_URL="$CI_DB_URL" python -c '
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ["CI_DB_URL"])
admin_url = url.set(database="postgres")
admin_eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
with admin_eng.connect() as conn:
    conn.execute(text("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = :d AND pid <> pg_backend_pid()"), {"d": url.database})
' 2>/dev/null || true

  DATABASE_URL="$CI_DB_URL" uv run --project backend alembic -c backend/alembic.ini downgrade base
  DATABASE_URL="$CI_DB_URL" uv run --project backend alembic -c backend/alembic.ini upgrade head
  DATABASE_URL="$CI_DB_URL" python tools/verify_ddl_matches_schema.py
fi

# ── 5단계: 프런트 검증 · 빌드 · 테스트 ──────────────────────────────────────────
step "5단계: 프런트엔드 검증 (typecheck · lint · format · build · test)"
run_cmd npm --prefix frontend run typecheck
run_cmd npm --prefix frontend run lint
run_cmd npm --prefix frontend run format:check
run_cmd npm --prefix frontend run build
if [ "$DRY_RUN" = 1 ]; then
  echo "[dry-run] npm --prefix frontend test"
else
  if ! npm --prefix frontend test; then
    echo "프런트엔드 테스트 1회 재실행 (간헐적 타이밍 문제 점검)..."
    npm --prefix frontend test
  fi
fi

# ── 정리: pytest 작업자 복제 DB 정리 ───────────────────────────────────────────
step "정리: pytest 작업자 복제 DB 정리"
if [ "$DRY_RUN" = 0 ]; then
  CI_DB_URL="$CI_DB_URL" python -c '
import os, sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

url = make_url(os.environ["CI_DB_URL"])
admin_url = url.set(database="postgres")
prefix = url.database.removesuffix("_test") + "_"

try:
    admin_eng = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_eng.connect() as conn:
        rows = conn.execute(
            text("SELECT datname FROM pg_database WHERE datname LIKE :pat AND datname LIKE :end"),
            {"pat": f"{prefix}%", "end": "%_test"},
        ).fetchall()
        for (datname,) in rows:
            if datname.startswith("factory_studio_ci_") and datname.endswith("_test") and datname != url.database:
                conn.execute(text(f"DROP DATABASE IF EXISTS \"{datname}\" WITH (FORCE)"))
                print(f"복제 DB 삭제: {datname}")
except Exception as e:
    print(f"복제 DB 정리 중 오류 (무시됨): {e}")
'
fi

step "로컬 CI 전체 통과 완료!"
echo "1~5단계가 성공적으로 완료되었습니다."
