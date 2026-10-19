#!/usr/bin/env bash
# Opt-in template. Bootstrap with an independent pin before scheduling this runner.
set -euo pipefail
umask 077
: "${FS_GW_JOURNAL_BUNDLE_ROOT:?private delivery bundle root required}"
: "${FS_UV_BIN:=/usr/local/bin/uv}"
PYTHONPATH=backend/src "$FS_UV_BIN" run --project backend python tools/gw_journal_delivery.py \
  publish --advance --bundles "$FS_GW_JOURNAL_BUNDLE_ROOT"
