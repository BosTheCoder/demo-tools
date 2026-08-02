#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
preflight

INFO="$(pages_api || true)"
if [[ -z "$INFO" ]]; then
  echo "Pages:      not enabled for ${SLUG}"
  echo "Run 'just deploy' to publish."
  exit 0
fi

jq_get() { echo "$INFO" | python3 -c "import sys,json;d=json.load(sys.stdin);v=d$1;print('-' if v in (None,'') else v)" 2>/dev/null || echo "-"; }

echo "Repo:       ${SLUG}"
echo "Pages:      $(jq_get "['status']")"
echo "Source:     $(jq_get "['source']['branch']") $(jq_get "['source']['path']")"
echo "URL:        $(jq_get "['html_url']")"
echo "Domain:     $(jq_get "['cname']")"
# Absent until GitHub issues the Let's Encrypt cert — the usual reason a fresh
# custom domain serves fine over http but not https.
echo "HTTPS cert: $(echo "$INFO" | python3 -c "import sys,json;d=json.load(sys.stdin);c=d.get('https_certificate');print(c.get('state') if c else 'not issued yet')" 2>/dev/null || echo '-')"
echo "Enforced:   $(jq_get "['https_enforced']")"
