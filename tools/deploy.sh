#!/usr/bin/env bash
# W0-3 배포 스크립트 (DSN-01 E). 맥북에서 한 번 실행하면 운영까지 끝난다.
#
#   tools/deploy.sh              # 배포
#   tools/deploy.sh --dry-run    # 서버를 바꾸지 않고 사전 점검만(서버 조회는 한다)
#   tools/deploy.sh --skip-ci-check   # CI 결과를 직접 확인했을 때만
#   tools/deploy.sh --help
#
# 순서: 사전 점검(로컬) → 프런트 빌드(로컬) → 서버 코드·마이그레이션 → (필요 시)시드 템플릿
#       → API 재시작 → 프런트 업로드 → 확인. 하나라도 실패하면 멈춘다.
#
# 손으로 하던 단계를 없애 2026-10-04의 "프런트 업로드 누락" 같은 실수를 막는다.
# 서버 접속(ssh)은 사용자 계정으로만 된다 — Claude는 이 스크립트를 실행하지 않는다.
set -euo pipefail

HOST="${FS_DEPLOY_HOST:-root@158.247.236.136}"
APP_DIR="${FS_DEPLOY_APP_DIR:-/srv/factory-studio/app}"
SITE="${FS_DEPLOY_SITE:-eip.hugh-d.com}"
SERVICE="${FS_DEPLOY_SERVICE:-factory-studio-api}"
APP_USER="${FS_DEPLOY_APP_USER:-factory}"
UV="${FS_DEPLOY_UV:-/usr/local/bin/uv}"
BRANCH="${FS_DEPLOY_BRANCH:-main}"
WORKFLOW="${FS_DEPLOY_WORKFLOW:-FS-009 runtime and schema}"
BUILD_DIR="${FS_DEPLOY_BUILD_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/fs-build}"

DRY_RUN=0
SKIP_CI=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) DRY_RUN=1 ;;
    --skip-ci-check) SKIP_CI=1 ;;  # CI가 아직 돌고 있을 때만. 통과를 확인했다는 뜻이 아니다.
    --help | -h)
      sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
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
remote() { ssh -o BatchMode=yes "$HOST" "$@"; }
remote_app() { remote "cd '$APP_DIR' && $1"; }
# 서버에서 앱 계정으로 uv 실행(.env는 서버 것)
remote_uv() { remote_app "sudo -u $APP_USER -H $UV run --frozen --project backend --env-file .env $1"; }

# ── 1. 사전 점검 (로컬, 아무것도 바꾸지 않는다) ────────────────────────────────
step "사전 점검"
command -v git >/dev/null || fail "git이 없습니다."
command -v npm >/dev/null || fail "npm이 없습니다(Node 24)."
command -v rsync >/dev/null || fail "rsync가 없습니다."

current_branch="$(git rev-parse --abbrev-ref HEAD)"
[ "$current_branch" = "$BRANCH" ] || fail "현재 브랜치가 $current_branch 입니다. $BRANCH 에서 배포합니다."

# 추적 중인 파일에 커밋하지 않은 변경이 있으면 서버와 달라진다. work/·.env 등 미추적 파일은 상관없다.
git diff --quiet && git diff --cached --quiet || fail "커밋하지 않은 변경이 있습니다. 커밋하거나 되돌린 뒤 다시 실행하세요."

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

remote true 2>/dev/null || fail "서버에 접속할 수 없습니다($HOST). ssh 키·네트워크를 확인하세요."
server_commit="$(remote_app "sudo -u $APP_USER -H git rev-parse HEAD")"
echo "서버 현재 커밋: ${server_commit:0:7}"
if [ "$server_commit" = "$COMMIT" ]; then
  echo "서버가 이미 같은 커밋입니다. 프런트·마이그레이션은 다시 맞춥니다."
fi
if remote_app "sudo -u $APP_USER -H git status --porcelain" | grep -q .; then
  fail "서버 저장소에 변경된 파일이 있습니다. 서버에서 먼저 정리하세요."
fi

# ── 2. 프런트 빌드 (로컬, 서버와 같은 커밋) ──────────────────────────────────
step "프런트 빌드 (별도 worktree, 작업 중인 폴더는 건드리지 않음)"
if [ -e "$BUILD_DIR" ]; then
  git worktree remove --force "$BUILD_DIR" 2>/dev/null || fail "빌드 폴더가 남아 있습니다: $BUILD_DIR"
fi
git worktree add --detach --quiet "$BUILD_DIR" "$COMMIT"
cleanup() { git worktree remove --force "$BUILD_DIR" 2>/dev/null || true; }
trap cleanup EXIT
(
  cd "$BUILD_DIR"
  npm --prefix frontend ci --silent
  npm --prefix frontend run build --silent
)
[ -f "$BUILD_DIR/frontend/dist/index.html" ] || fail "빌드 결과가 없습니다."
PRIVATE_DIR="$BUILD_DIR/backend/private-assets/soap-poc"
PRIVATE_FILES=(soap-poc.html research-notebook.html soap-poc/assembly-v3.json soap-poc/research-history.json soap-poc/soap-poc-03.zip soap-poc/drawer-v3.stl)
for asset in "${PRIVATE_FILES[@]}"; do
  [ -s "$PRIVATE_DIR/$asset" ] || fail "관리자 비누 자산이 없습니다: $asset"
done
echo "빌드 완료: $(du -sh "$BUILD_DIR/frontend/dist" | cut -f1)"

if [ "$DRY_RUN" = 1 ]; then
  step "시험 실행(--dry-run) — 서버를 바꾸지 않고 끝냅니다"
  echo "다음 단계였을 것: 서버 ${server_commit:0:7} → ${COMMIT:0:7}, 마이그레이션, 시드 확인, 비공개 비누 파일 업로드/읽기 확인, $SERVICE 재시작, 프런트 업로드, 확인"
  exit 0
fi

# ── 3. 서버 코드·마이그레이션 ────────────────────────────────────────────────
step "서버 코드 받기 · 의존성 · 마이그레이션"
remote_app "sudo -u $APP_USER -H git fetch --quiet origin $BRANCH && sudo -u $APP_USER -H git merge --ff-only $COMMIT"
deployed="$(remote_app "sudo -u $APP_USER -H git rev-parse HEAD")"
[ "$deployed" = "$COMMIT" ] || fail "서버 커밋이 다릅니다(${deployed:0:7} ≠ ${COMMIT:0:7})."
remote_app "sudo -u $APP_USER -H $UV sync --project backend --frozen --no-dev"
remote_uv "alembic -c backend/alembic.ini upgrade head"

# ── 4. 시드 템플릿 (시드 버전이 바뀐 배포에서만) ──────────────────────────────
step "시드 템플릿 확인"
code_seed="$(remote_uv "python -c 'from seed.common import SEED_VERSION; print(SEED_VERSION)'" | tr -d '\r')"
db_seed="$(remote_app "docker compose --env-file .env exec -T db psql -U factory_studio -d factory_studio -Atc \"SELECT g.seed_version FROM core.data_generation g JOIN core.workspace w ON w.id=g.workspace_id WHERE w.workspace_kind='TEMPLATE' AND w.active_generation_id=g.id AND g.status='active' ORDER BY g.created_at DESC, g.id DESC LIMIT 1\"" | tr -d '\r')"
echo "코드 $code_seed · 템플릿 $db_seed"
if [ -z "$db_seed" ]; then
  fail "활성 템플릿이 없습니다. 배포 절차 4-3을 먼저 수행하세요."
elif [ "$code_seed" != "$db_seed" ]; then
  echo "시드 버전이 달라 템플릿을 다시 만듭니다."
  remote_uv "python -m seed.cli template --date \$(TZ=Asia/Seoul date +%F)" | tail -1
else
  echo "시드 그대로 — 템플릿 유지"
fi

# 관리자 비누 파일은 Git/공개 dist에 없다. 코드와 같은 빌드의 비공개 자산을 먼저 올린다.
step "관리자 비누 자산 업로드 (웹 루트 밖)"
remote "mkdir -p '$APP_DIR/backend/private-assets/soap-poc'"
rsync -az --delete "$PRIVATE_DIR/" "$HOST:$APP_DIR/backend/private-assets/soap-poc/"
remote "chown -R $APP_USER:$APP_USER '$APP_DIR/backend/private-assets/soap-poc' && find '$APP_DIR/backend/private-assets/soap-poc' -type d -exec chmod 750 {} + && find '$APP_DIR/backend/private-assets/soap-poc' -type f -exec chmod 640 {} +"
for asset in "${PRIVATE_FILES[@]}"; do
  remote "sudo -u $APP_USER test -s '$APP_DIR/backend/private-assets/soap-poc/$asset'" || fail "서버 관리자 비누 자산이 없습니다/읽을 수 없습니다: $asset"
done

# ── 5. API 재시작 ────────────────────────────────────────────────────────────
step "API 재시작"
remote "systemctl restart $SERVICE"
for _ in $(seq 1 30); do
  sleep 1
  if remote "systemctl is-active --quiet $SERVICE"; then break; fi
done
remote "systemctl is-active --quiet $SERVICE" || fail "$SERVICE 가 올라오지 않았습니다: journalctl -u $SERVICE -n 50"

# ── 6. 프런트 업로드 (건너뛰면 2026-10-04 같은 사고가 난다) ───────────────────
step "프런트 업로드"
rsync -az --delete "$BUILD_DIR/frontend/dist/" "$HOST:$APP_DIR/frontend/dist/"
remote "chown -R $APP_USER:$APP_USER $APP_DIR/frontend/dist"

# ── 7. 확인 ─────────────────────────────────────────────────────────────────
step "확인"
origin_status="$(remote "curl -sk -o /dev/null -w '%{http_code}' --resolve $SITE:443:127.0.0.1 https://$SITE/")"
[ "$origin_status" = "200" ] || fail "원점 https 응답이 $origin_status 입니다."
public_status="$(curl -s -o /dev/null -w '%{http_code}' "https://$SITE/")"
[ "$public_status" = "200" ] || fail "공개 주소 응답이 $public_status 입니다(Cloudflare)."

# DB가 설계(schema.json)와 같은지 — 마이그레이션 누락을 잡는다
ddl_errors="$(remote_uv "python tools/verify_ddl_matches_schema.py" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["errors"]))' 2>/dev/null || echo "?")"
[ "$ddl_errors" = "0" ] || fail "서버 DB가 설계와 다릅니다(오류 $ddl_errors건)."

api_errors="$(remote "journalctl -u $SERVICE --since '-2 min' --no-pager | grep -c ' 5[0-9][0-9] ' || true")"
echo "원점 200 · 공개 200 · DDL 대조 0 · 최근 2분 5xx ${api_errors}건"
[ "${api_errors:-0}" = "0" ] || echo "경고: 5xx가 있습니다 — journalctl -u $SERVICE -n 50"

step "배포 완료: ${COMMIT:0:7}"
echo "운영 https://$SITE · 기록: docs/progress.md 와 docs/agent/HANDOFF.md 에 커밋을 남기세요."
