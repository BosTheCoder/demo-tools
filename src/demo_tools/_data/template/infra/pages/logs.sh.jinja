#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
preflight

# A CDN has no request logs to tail. The honest analogue is the build history:
# what was published, when, and whether it succeeded.
echo "Pages build history for ${SLUG} (a CDN has no request logs to tail):"
echo
gh api "repos/${SLUG}/pages/builds" \
  --jq '.[] | "\(.created_at)  \(.status)  \(.commit[0:7])  \(.error.message // "")"' \
  2>/dev/null | head -20 || echo "  (no builds yet)"
