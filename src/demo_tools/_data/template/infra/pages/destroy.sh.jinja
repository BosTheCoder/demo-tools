#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
preflight

echo "This will DISABLE GitHub Pages for ${SLUG}."
echo "The repository and its code are left alone; only publishing stops."
read -r -p "Type the repo name to confirm (${SLUG}): " ans
[[ "$ans" == "$SLUG" ]] || { echo "Aborted."; exit 1; }

gh api -X DELETE "repos/${SLUG}/pages" >/dev/null
echo "Pages disabled. Re-publish any time with 'just deploy'."
