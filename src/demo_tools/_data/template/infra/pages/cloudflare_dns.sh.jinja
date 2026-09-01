#!/usr/bin/env bash
# MANAGED BY demo-tools — DO NOT EDIT. Run `just sync` to update.
#
# Point this site's custom domain at GitHub Pages by upserting a CNAME record
# in Cloudflare. Idempotent — safe on every deploy.
#
#   usage: cloudflare_dns.sh HOST TARGET
#     HOST    the hostname in CNAME, e.g. cc.example.com
#     TARGET  where Pages serves it, e.g. bosthecoder.github.io
#
# The zone is the last two labels of the hostname (cc.example.com ->
# example.com). Set DEMO_DNS_ZONE to override, e.g. for a .co.uk domain.
#
# Unlike the Fly equivalent, this one **forces proxied=false** on the record it
# manages rather than leaving an existing proxy setting alone. Proxying breaks
# GitHub's certificate issuance, and the symptom arrives an hour later as "http
# works, https does not" — far from the deploy that caused it. A record this
# script owns is a record that must be grey-clouded.
#
# An apex domain is refused: a CNAME cannot coexist with the zone's SOA/NS
# records, and Cloudflare's CNAME flattening would send Pages a host it has no
# certificate for. Apex Pages domains need A records, which this does not do.
#
# Requires CLOUDFLARE_API_TOKEN (zone:dns:edit on the parent domain).
# When the token is unset it prints the record you need and exits 0, so a
# deploy still succeeds — it just needs DNS set up by hand.

set -euo pipefail

HOST="${1:-}"
TARGET="${2:-}"
if [[ -z "$HOST" || -z "$TARGET" ]]; then
    echo "usage: cloudflare_dns.sh HOST TARGET" >&2
    exit 2
fi

zone_for() {
    if [[ -n "${DEMO_DNS_ZONE:-}" ]]; then
        echo "$DEMO_DNS_ZONE"
        return
    fi
    awk -F. '{ print (NF >= 2) ? $(NF-1)"."$NF : $0 }' <<<"$1"
}

ZONE="$(zone_for "$HOST")"

if [[ "$HOST" == "$ZONE" ]]; then
    echo "==> $HOST is the zone apex; Pages needs A records there, not a CNAME."
    echo "    Point it at GitHub's addresses by hand:"
    echo "      185.199.108.153  185.199.109.153  185.199.110.153  185.199.111.153"
    exit 0
fi

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
    echo "==> Cloudflare DNS automation skipped (CLOUDFLARE_API_TOKEN not set)"
    echo "    Add this record by hand, DNS-only (grey cloud — proxying breaks the cert):"
    echo "      CNAME ${HOST%%.*} -> ${TARGET}"
    exit 0
fi

CF_API="https://api.cloudflare.com/client/v4"
AUTH=(-H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" -H "Content-Type: application/json")

api() { curl -sS "${AUTH[@]}" "$@"; }

# Cache the zone ID across deploys (one round-trip becomes zero on re-runs).
zone_id_for() {
    local zone="$1" cache id
    cache="${HOME}/.cache/demo-tools/cf-zone-${zone}.id"
    mkdir -p "$(dirname "$cache")"
    if [[ -s "$cache" ]]; then
        cat "$cache"
        return
    fi
    id="$(api "$CF_API/zones?name=${zone}" | jq -r '.result[0].id // empty')"
    [[ -n "$id" ]] || return 1
    printf '%s' "$id" > "$cache"
    echo "$id"
}

ZONE_ID="$(zone_id_for "$ZONE" || true)"
if [[ -z "$ZONE_ID" ]]; then
    echo "ERROR: no Cloudflare zone '$ZONE' visible to this token." >&2
    echo "       The token needs Zone:DNS:Edit on it." >&2
    exit 1
fi

EXISTING="$(api "$CF_API/zones/$ZONE_ID/dns_records?name=${HOST}" | jq -c '.result[0] // empty')"
BODY="$(jq -nc --arg n "$HOST" --arg c "$TARGET" \
        '{type:"CNAME", name:$n, content:$c, proxied:false, ttl:1}')"

echo "==> DNS: ${HOST} CNAME ${TARGET} (DNS-only)"

if [[ -n "$EXISTING" ]]; then
    if [[ "$(jq -r '"\(.type)|\(.content)|\(.proxied)"' <<<"$EXISTING")" == "CNAME|${TARGET}|false" ]]; then
        echo "    already correct"
        exit 0
    fi
    jq -r '"    replacing: \(.type) -> \(.content), proxied=\(.proxied)"' <<<"$EXISTING"
    RESULT="$(api -X PUT "$CF_API/zones/$ZONE_ID/dns_records/$(jq -r .id <<<"$EXISTING")" --data "$BODY")"
else
    RESULT="$(api -X POST "$CF_API/zones/$ZONE_ID/dns_records" --data "$BODY")"
fi

if ! jq -e '.success' >/dev/null <<<"$RESULT"; then
    jq -r '.errors[]? | "    cloudflare: \(.message)"' <<<"$RESULT" >&2
    exit 1
fi
echo "    applied"
