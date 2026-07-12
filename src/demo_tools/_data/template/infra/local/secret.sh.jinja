#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
KV="${1:-}"
if [[ -z "$KV" || "$KV" != *=* ]]; then
    echo "Usage: just secret KEY=VALUE" >&2
    exit 1
fi
KEY="${KV%%=*}"

# Upsert KEY=VALUE into a gitignored .env that the local overlay loads
# (compose.local.yml: env_file). Re-run 'just deploy' to apply.
ENV_FILE=".env"
touch "$ENV_FILE"
tmp="$(mktemp)"
grep -vE "^${KEY}=" "$ENV_FILE" > "$tmp" || true
mv "$tmp" "$ENV_FILE"
printf '%s\n' "$KV" >> "$ENV_FILE"
echo "Set ${KEY} in ./.env — re-run 'just deploy' to apply."
