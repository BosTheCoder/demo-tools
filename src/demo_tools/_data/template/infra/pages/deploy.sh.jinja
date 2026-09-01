#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
preflight

BRANCH="$(git rev-parse --abbrev-ref HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: working tree is dirty. Commit or stash first — a Pages deploy" >&2
  echo "publishes what is committed, so deploying now would ship stale files." >&2
  exit 1
fi

if [[ "$PUBLISH_MODE" == "root" ]]; then
  # Stop GitHub running the repo through Jekyll, which drops _-prefixed files
  # and directories. The branch path writes this into the build output; the
  # root path has to commit it, because here the repo *is* the artifact.
  if [[ ! -f .nojekyll ]]; then
    echo "==> Adding .nojekyll (Jekyll would hide _-prefixed files)"
    touch .nojekyll
    git add .nojekyll
    git commit -q -m "chore: .nojekyll — serve files as written" .nojekyll
  fi

  # No build step: the repo root IS the site. Push and point Pages at it.
  echo "==> Pushing ${BRANCH} (no build step — source is the artifact)"
  git push -u origin "$BRANCH"
  SOURCE_BRANCH="$BRANCH"
  SOURCE_PATH="/"
else
  echo "==> Building"
  if [[ -f package.json ]]; then
    npm ci 2>/dev/null || npm install
    npm run build
  else
    echo "ERROR: no package.json — nothing to build, but publish mode is 'branch'." >&2
    exit 1
  fi
  [[ -d "$BUILD_DIR" ]] || { echo "ERROR: build produced no ${BUILD_DIR}/" >&2; exit 1; }

  # A custom domain needs its CNAME inside the published tree, not just on main.
  [[ -f CNAME ]] && cp CNAME "$BUILD_DIR/CNAME"
  # Stop GitHub running the output through Jekyll (it drops _-prefixed files).
  touch "$BUILD_DIR/.nojekyll"

  echo "==> Publishing ${BUILD_DIR}/ -> ${PAGES_BRANCH}"
  # A detached worktree keeps the build output out of the working branch's
  # history and never touches the tree you are editing.
  TMP="$(mktemp -d)"
  git worktree add --detach "$TMP" >/dev/null
  (
    cd "$TMP"
    git checkout --orphan "$PAGES_BRANCH" >/dev/null 2>&1 || git checkout "$PAGES_BRANCH"
    git rm -rf . >/dev/null 2>&1 || true
    cp -r "$OLDPWD/$BUILD_DIR/." .
    git add -A
    git commit -q -m "deploy: $(cd "$OLDPWD" && git rev-parse --short HEAD)" || true
    git push -f origin "$PAGES_BRANCH"
  )
  git worktree remove --force "$TMP"
  SOURCE_BRANCH="$PAGES_BRANCH"
  SOURCE_PATH="/"
fi

echo "==> Ensuring Pages is enabled (source: ${SOURCE_BRANCH} ${SOURCE_PATH})"
if ! pages_api >/dev/null; then
  gh api -X POST "repos/${SLUG}/pages" \
    -f "source[branch]=${SOURCE_BRANCH}" -f "source[path]=${SOURCE_PATH}" >/dev/null
else
  gh api -X PUT "repos/${SLUG}/pages" \
    -f "source[branch]=${SOURCE_BRANCH}" -f "source[path]=${SOURCE_PATH}" >/dev/null || true
fi

if [[ -f CNAME ]]; then
  CUSTOM="$(tr -d '[:space:]' < CNAME)"
  echo "==> Custom domain: ${CUSTOM}"
  gh api -X PUT "repos/${SLUG}/pages" -f "cname=${CUSTOM}" >/dev/null 2>&1 || true
  bash "$HERE/cloudflare_dns.sh" "$CUSTOM" \
       "$(echo "$SLUG" | cut -d/ -f1 | tr 'A-Z' 'a-z').github.io"
fi

echo
echo "Deployed:"
echo "  $(pages_url)"
echo
echo "First deploy? The HTTPS certificate can take up to an hour to issue."
echo "Check with: just status"
