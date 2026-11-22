#!/usr/bin/env bash
# 맥북 운영 배포 (HYUDO-04). 개발 폴더의 main을 운영 폴더(별도 worktree)에 반영한다.
#
#   tools/deploy.sh                   # 배포
#   tools/deploy.sh --dry-run         # 사전 점검·빌드 가능 여부만, 운영은 바꾸지 않음
#   tools/deploy.sh --skip-ci-check   # CI 결과를 직접 확인했을 때만
#   tools/deploy.sh --help
#
# 순서: 사전 점검 → DB 백업 → 운영 폴더 커밋 전환 → 빌드(EIP·명함) → 마이그레이션
#       → (필요 시)시드 템플릿 → API 재시작 → 확인. 하나라도 실패하면 멈춘다.
# 구성과 되돌리기: docs/deploy/맥북운영_HYUDO-02.md
set -euo pipefail

PROD_DIR="${FS_DEPLOY_PROD_DIR:-$HOME/projects/factory-studio-prod}"
DB_CONTAINER="${FS_DEPLOY_DB_CONTAINER:-factory-studio-prod-db-1}"
API_LABEL="${FS_DEPLOY_API_LABEL:-kr.hyudo.fs-api}"
API_LOG="${FS_DEPLOY_API_LOG:-$HOME/Library/Logs/factory-studio/kr.hyudo.fs-api.log}"
API_PORT="${FS_DEPLOY_API_PORT:-8021}"
SITE="${FS_DEPLOY_SITE:-eip.hyudo.kr}"
CARD_SITE="${FS_DEPLOY_CARD_SITE:-www.hyudo.kr}"
BACKUP_DIR="${FS_DEPLOY_BACKUP_DIR:-$HOME/fs-backups}"
BRANCH="${FS_DEPLOY_BRANCH:-main}"
WORKFLOW="${FS_DEPLOY_WORKFLOW:-FS-009 runtime and schema}"

DRY_RUN=0
SKIP_CI=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --skip-ci-check) SKIP_CI=1 ;; # 통과를 확인했다는 뜻이 아니다.
    --help | -h)
      sed -n '2,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
export PATH="${FS_DEPLOY_NODE_BIN:-/opt/homebrew/opt/node@24/bin}:$PATH"

step() { printf '\n\033[1m[%s] %s\033[0m\n' "$(date +%H:%M:%S)" "$1"; }
fail() {
  printf '\n\033[1;31m중단: %s\033[0m\n' "$1" >&2
  exit 1
}
prod() { (cd "$PROD_DIR" && "$@"); }
prod_uv() { prod uv run --frozen --project backend --env-file .env "$@"; }
psql_prod() { docker exec "$DB_CONTAINER" psql -U factory_studio -d factory_studio -Atc "$1" </dev/null; }
http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$@" || true; }

# ── 1. 사전 점검 (아무것도 바꾸지 않는다) ───────────────────────────────────
step "사전 점검"
for tool in git npm uv docker curl launchctl; do
  command -v "$tool" >/dev/null || fail "$tool 이 없습니다."
done

current_branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$current_branch" = "$BRANCH" ] || fail "현재 브랜치가 $current_branch 입니다. $BRANCH 에서 배포합니다."
git diff --quiet && git diff --cached --quiet || fail "커밋하지 않은 변경이 있습니다."

git fetch --quiet origin "$BRANCH"
COMMIT="$(git rev-parse HEAD)"
remote_head="$(git rev-parse "origin/$BRANCH")"
[ "$COMMIT" = "$remote_head" ] || fail "로컬 $BRANCH 와 origin/$BRANCH 가 다릅니다. 먼저 push 하세요(로컬 ${COMMIT:0:7} · 원격 ${remote_head:0:7})."
echo "배포할 커밋: ${COMMIT:0:7} $(git log -1 --pretty=%s | cut -c1-70)"

if [ "$SKIP_CI" = 0 ]; then
  command -v gh >/dev/null || fail "gh가 없습니다. CI 결과를 확인할 수 없습니다(확인했다면 --skip-ci-check)."
  ci_status="$(gh run list --branch "$BRANCH" --workflow "$WORKFLOW" --limit 20 \
    --json headSha,status,conclusion \
    --jq "[.[] | select(.headSha==\"$COMMIT\")][0] | select(.) | \"\(.status) \(.conclusion)\"" 2>/dev/null || true)"
  case "$ci_status" in
    "completed success") echo "CI 통과" ;;
    "") fail "이 커밋의 CI 기록이 없습니다. push 직후면 잠시 기다리세요." ;;
    *) fail "CI가 통과하지 않았습니다($ci_status)." ;;
  esac
else
  echo "CI 확인 건너뜀(--skip-ci-check)"
fi

[ -f "$PROD_DIR/.env" ] || fail "운영 폴더가 없습니다: $PROD_DIR (절차서 0장)"
prod git status --porcelain --untracked-files=no | grep -q . && fail "운영 폴더에 고친 파일이 있습니다. 먼저 정리하세요."
prod_commit="$(prod git rev-parse HEAD)"
echo "운영 현재 커밋: ${prod_commit:0:7}"
psql_prod "SELECT 1" >/dev/null || fail "운영 DB에 접속할 수 없습니다($DB_CONTAINER). Colima가 켜져 있는지 확인하세요."

if [ "$DRY_RUN" = 1 ]; then
  step "시험 실행(--dry-run) — 운영을 바꾸지 않고 끝냅니다"
  echo "다음 단계였을 것: 백업 → 운영 ${prod_commit:0:7} → ${COMMIT:0:7}, 빌드, 마이그레이션, 시드 확인, API 재시작, 확인"
  exit 0
fi

# ── 2. DB 백업 (맥북 안에만 둔다) ───────────────────────────────────────────
step "운영 DB 백업"
mkdir -p "$BACKUP_DIR"
backup="$BACKUP_DIR/$(date +%Y%m%d-%H%M%S)-${COMMIT:0:7}.dump"
docker exec "$DB_CONTAINER" pg_dump -U factory_studio -Fc factory_studio </dev/null >"$backup"
[ -s "$backup" ] || fail "백업 파일이 비었습니다: $backup"
echo "백업: $backup"

# ── 3. 운영 폴더 전환 · 빌드 ────────────────────────────────────────────────
step "운영 폴더 ${prod_commit:0:7} → ${COMMIT:0:7}"
prod git checkout --quiet --detach "$COMMIT"
[ "$(prod git rev-parse HEAD)" = "$COMMIT" ] || fail "운영 폴더 커밋이 다릅니다."

step "빌드 (EIP · 명함)"
prod npm --prefix frontend ci --silent
prod npm --prefix frontend run build --silent
prod npm --prefix card ci --silent
prod npm --prefix card run build --silent
[ -f "$PROD_DIR/frontend/dist/index.html" ] || fail "EIP 빌드 결과가 없습니다."
[ -f "$PROD_DIR/card/dist/index.html" ] || fail "명함 빌드 결과가 없습니다."
# 관리자 비누 파일은 웹 루트 밖(backend/private-assets)에만 있어야 한다.
PRIVATE_FILES=(soap-poc.html research-notebook.html soap-poc/assembly-v3.json soap-poc/research-history.json soap-poc/soap-poc-03.zip soap-poc/drawer-v3.stl)
for asset in "${PRIVATE_FILES[@]}"; do
  [ -s "$PROD_DIR/backend/private-assets/soap-poc/$asset" ] || fail "관리자 비누 자산이 없습니다: $asset"
done
find "$PROD_DIR/frontend/dist" "$PROD_DIR/card/dist" -iname '*soap-poc*' | grep -q . && fail "비누 POC 파일이 공개 폴더에 있습니다."

# ── 4. 마이그레이션 · 시드 ──────────────────────────────────────────────────
step "의존성 · 마이그레이션"
prod uv sync --project backend --frozen --no-dev --quiet
prod_uv alembic -c backend/alembic.ini upgrade head

step "시드 템플릿 확인"
code_seed="$(prod_uv python -c 'from seed.common import SEED_VERSION; print(SEED_VERSION)' | tr -d '\r')"
db_seed="$(psql_prod "SELECT g.seed_version FROM core.data_generation g JOIN core.workspace w ON w.id=g.workspace_id WHERE w.workspace_kind='TEMPLATE' AND w.active_generation_id=g.id AND g.status='active' ORDER BY g.created_at DESC, g.id DESC LIMIT 1" | tr -d '\r')"
echo "코드 $code_seed · 템플릿 $db_seed"
if [ -z "$db_seed" ]; then
  fail "활성 템플릿이 없습니다. 절차서 0장대로 먼저 만드세요."
elif [ "$code_seed" != "$db_seed" ]; then
  echo "시드 버전이 달라 템플릿을 다시 만듭니다."
  (cd "$PROD_DIR/backend" && uv run --frozen --env-file ../.env python -m seed.cli template --date "$(TZ=Asia/Seoul date +%F)") | tail -1
else
  echo "시드 그대로 — 템플릿 유지"
fi

# ── 5. API 재시작 ───────────────────────────────────────────────────────────
step "API 재시작"
log_lines="$( (wc -l <"$API_LOG") 2>/dev/null | tr -d ' ' || echo 0)"
launchctl kickstart -k "gui/$(id -u)/$API_LABEL"
api_status=""
for _ in $(seq 1 40); do
  api_status="$(http_code "http://127.0.0.1:$API_PORT/api/v1/core/sessions/current")"
  [ "$api_status" = "401" ] && break
  sleep 1
done
[ "$api_status" = "401" ] || fail "API가 올라오지 않았습니다($api_status): tail -50 $API_LOG"

# ── 6. 확인 ─────────────────────────────────────────────────────────────────
step "확인"
eip_status="$(http_code "https://$SITE/")"
card_status="$(http_code "https://$CARD_SITE/")"
[ "$eip_status" = "200" ] || fail "https://$SITE 응답이 $eip_status 입니다."
[ "$card_status" = "200" ] || fail "https://$CARD_SITE 응답이 $card_status 입니다."

# DB가 설계(schema.json)와 같은지 — 마이그레이션 누락을 잡는다
ddl_errors="$(prod_uv python tools/verify_ddl_matches_schema.py | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["errors"]))' 2>/dev/null || echo "?")"
[ "$ddl_errors" = "0" ] || fail "운영 DB가 설계와 다릅니다(오류 $ddl_errors건)."

api_errors="$( (tail -n +"$((log_lines + 1))" "$API_LOG" 2>/dev/null || true) | grep -c '" 5[0-9][0-9]' || true)"
echo "eip 200 · www 200 · DDL 대조 0 · 재시작 뒤 5xx ${api_errors:-0}건"
[ "${api_errors:-0}" = "0" ] || echo "경고: 5xx가 있습니다 — tail -50 $API_LOG"

step "배포 완료: ${COMMIT:0:7}"
echo "되돌리기: 운영 폴더에서 git checkout --detach ${prod_commit:0:7} 후 다시 빌드, DB는 $backup"
echo "기록: docs/progress.md 와 docs/agent/HANDOFF.md 에 커밋을 남기세요."
