#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
#
# Point one or more hostnames at this Fly app's IPs by upserting A + AAAA
# records in Cloudflare. Idempotent — safe on every deploy.
#
#   usage: cloudflare_dns.sh APP HOST [HOST...]
#
# The zone is the last two labels of each hostname (foo.demos.example.com ->
# example.com). Set DEMO_DNS_ZONE to override, e.g. for a .co.uk domain.
#
# Two things it deliberately will not do, because a deploy has no business
# rearranging DNS somebody set up by hand:
#   - a hostname already served by a CNAME is left alone rather than replaced
#     with A/AAAA (Cloudflare would reject the clash anyway)
#   - an existing record keeps whatever proxy setting it has; only brand-new
#     records default to unproxied, since Fly terminates TLS itself
#
# Requires CLOUDFLARE_API_TOKEN (zone:dns:edit on the parent domain).
# When the token is unset, the script no-ops with a friendly hint, so
# deploys still work — they just need manual DNS setup at your registrar.

set -euo pipefail

APP="${1:-}"
shift || true
if [[ -z "$APP" || $# -eq 0 ]]; then
    echo "usage: cloudflare_dns.sh APP HOST [HOST...]" >&2
    exit 2
fi

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    echo "==> Cloudflare DNS automation skipped (CLOUDFLARE_API_TOKEN not set)"
    echo "    To enable per-app DNS automation, export a Cloudflare API token"
    echo "    with 'Edit zone DNS' permission and re-run \`just deploy\`."
    exit 0
fi

CF_API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json")

zone_for() {
    if [[ -n "${DEMO_DNS_ZONE:-}" ]]; then
        echo "$DEMO_DNS_ZONE"
        return
    fi
    awk -F. '{ print (NF >= 2) ? $(NF-1)"."$NF : $0 }' <<<"$1"
}

# Cache the zone ID across deploys (one round-trip becomes zero on re-runs).
zone_id_for() {
    local zone="$1" cache id
    cache="${HOME}/.cache/demo-tools/cf-zone-${zone}.id"
    mkdir -p "$(dirname "$cache")"

    if [[ -s "$cache" ]]; then
        cat "$cache"
        return
    fi

    id=$(curl -fsS "${AUTH[@]}" "$CF_API/zones?name=$zone" \
        | python3 -c "import sys,json; r=json.load(sys.stdin); print(r['result'][0]['id'] if r.get('result') else '')")
    if [[ -z "$id" ]]; then
        echo "ERROR: Cloudflare zone '$zone' not found." >&2
        echo "  - Confirm $zone is added to your Cloudflare account and active." >&2
        echo "  - Confirm the API token has Zone.DNS:Edit on $zone." >&2
        echo "  - If the hostname's zone isn't its last two labels, set DEMO_DNS_ZONE." >&2
        exit 1
    fi
    echo "$id" > "$cache"
    echo "$id"
}

# Pull v4 + v6 IPs from Fly. flyctl's --json shape uses a "Type" field with
# values like "v6", "shared_v4", "dedicated_v4". Match on suffix to be
# robust against shared/dedicated and any future variant.
FLY_IPS_JSON=$(fly ips list -a "$APP" --json)

extract_ip() {
    FLY_IPS_JSON="$FLY_IPS_JSON" python3 -c "
import json, os, sys
fam = sys.argv[1]
for ip in json.loads(os.environ['FLY_IPS_JSON']):
    if (ip.get('Type') or '').lower().endswith(fam):
        print(ip.get('Address') or '')
        break
" "$1"
}

V4=$(extract_ip v4)
V6=$(extract_ip v6)

if [[ -z "$V4" && -z "$V6" ]]; then
    echo "ERROR: Could not determine public IPs for app '$APP'." >&2
    exit 1
fi

# Reads the host's existing records once (RECORDS) so both A and AAAA can be
# resolved without another round-trip.
upsert_record() {
    local host="$1" zone_id="$2" records="$3" type="$4" content="$5"
    [[ -z "$content" ]] && return 0

    local existing payload
    existing=$(RECORDS="$records" python3 -c "
import json, os, sys
rs = json.loads(os.environ['RECORDS'])['result']
r = next((r for r in rs if r['type'] == sys.argv[1]), None)
print(f\"{r['id']} {str(r['proxied']).lower()}\" if r else '')
" "$type")

    payload=$(REC_PROXIED="${existing#* }" python3 -c "
import json, os, sys
print(json.dumps({'type': sys.argv[1], 'name': sys.argv[2], 'content': sys.argv[3],
                  'ttl': 1, 'proxied': os.environ['REC_PROXIED'] == 'true'}))
" "$type" "$host" "$content")

    if [[ -n "$existing" ]]; then
        echo "  update $type $host -> $content"
        curl -fsS -X PUT "${AUTH[@]}" \
            "$CF_API/zones/$zone_id/dns_records/${existing%% *}" \
            -d "$payload" >/dev/null
    else
        echo "  create $type $host -> $content"
        curl -fsS -X POST "${AUTH[@]}" \
            "$CF_API/zones/$zone_id/dns_records" \
            -d "$payload" >/dev/null
    fi
}

for HOST in "$@"; do
    ZONE=$(zone_for "$HOST")
    ZONE_ID=$(zone_id_for "$ZONE")

    RECORDS=$(curl -fsS "${AUTH[@]}" \
        "$CF_API/zones/$ZONE_ID/dns_records?name=$HOST&per_page=100")

    if RECORDS="$RECORDS" python3 -c "
import json, os, sys
rs = json.loads(os.environ['RECORDS'])['result']
sys.exit(0 if any(r['type'] == 'CNAME' for r in rs) else 1)
"; then
        echo "==> Skipping DNS for $HOST — a CNAME already points it somewhere"
        continue
    fi

    echo "==> Updating Cloudflare DNS for $HOST (zone $ZONE)"
    upsert_record "$HOST" "$ZONE_ID" "$RECORDS" A "$V4"
    upsert_record "$HOST" "$ZONE_ID" "$RECORDS" AAAA "$V6"
done
