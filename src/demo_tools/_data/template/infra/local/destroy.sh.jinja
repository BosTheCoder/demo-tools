#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
read -r -p "Destroy ${APP}? Removes the container and unregisters ${TS_PATH}. [y/N] " ans
case "$ans" in
    [yY]|[yY][eE][sS]) ;;
    *) echo "Aborted."; exit 0 ;;
esac
resolve_ts
# Unregister the serve path only if it's actually mapped (an admin-gated write).
if serve_status | grep -qE "(^|[[:space:]])${TS_PATH}[[:space:]]"; then
  echo "==> Unregistering ${TS_PATH} — approve the Windows UAC prompt."
  ts_serve_elevated --set-path "${TS_PATH}" off || true
fi
"${COMPOSE[@]}" down || true
echo "Done. Your data dir ./data was KEPT (SQLite lives there). Delete it manually with: rm -rf ./data"
