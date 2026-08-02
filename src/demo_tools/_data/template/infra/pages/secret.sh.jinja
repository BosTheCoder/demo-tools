#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
set -euo pipefail

# Deliberately fails. On fly/local, `just secret` sets a server-side value the
# client never sees. GitHub Pages has no server: every byte it serves is public,
# so a "secret" here would be published to a CDN while looking like it was
# hidden. Writing a .env that silently does nothing is the dangerous outcome —
# it fails closed instead, and says which of the two cases you are in.

KV="${1:-}"
KEY="${KV%%=*}"

echo "Refusing to set a secret on the pages target." >&2
echo >&2
echo "GitHub Pages serves static files with no server, so anything the page can" >&2
echo "read, a visitor can read. There is nowhere to put a value that the browser" >&2
echo "can use but the public cannot." >&2
echo >&2
echo "If ${KEY:-this value} is PUBLIC config — an API base URL, a feature flag, a" >&2
echo "publishable key that is safe in client code — put it directly in the source." >&2
echo "It is going to be visible either way; committing it makes that honest." >&2
echo >&2
echo "If it is a REAL credential — an API key, a token, a signing secret — it" >&2
echo "cannot live in a static site at all. Either:" >&2
echo "  - call an API that holds the credential server-side, or" >&2
echo "  - move this app to a target that runs a server:" >&2
echo "      DEMO_TARGET=fly just deploy && DEMO_TARGET=fly just secret ${KV:-KEY=VALUE}" >&2
exit 1
