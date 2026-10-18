#!/usr/bin/env bash
# Template runner only. Installation/activation belongs to the server operator.
set -euo pipefail
umask 077
: "${FS_GW_BACKUP_ROOT:?private backup root required}"
: "${FS_GW_BACKUP_COMPANY_ID:?company ID required}"
: "${FS_UV_BIN:=/usr/local/bin/uv}"
run_dir="${FS_GW_BACKUP_ROOT}/$(date -u +%Y%m%dT%H%M%SZ)-$$"
mkdir -m 700 -- "$run_dir"
trap 'printf "%s\n" "Backup failed; inspect private server diagnostics." > "$run_dir/FAILED"' ERR
"$FS_UV_BIN" run --project backend python tools/gw_backup.py backup \
  --company-id "$FS_GW_BACKUP_COMPANY_ID" \
  --output "$run_dir/database.fsbackup" --evidence "$run_dir/evidence.json"
printf '%s\n' 'Local encrypted artifact and evidence created.' > "$run_dir/SUCCESS"
