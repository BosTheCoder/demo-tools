from __future__ import annotations

import json
import re
import subprocess
from datetime import timedelta
from typing import Any

DOMAIN_BASE = "demos.buildwithbos.com"


def list_apps() -> list[dict[str, Any]]:
    """Return all Fly apps for the current account, normalized."""
    r = subprocess.run(
        ["fly", "apps", "list", "--json"],
        capture_output=True, text=True, check=True,
    )
    raw = json.loads(r.stdout)
    return [
        {
            "name": a["Name"],
            "status": a.get("Status", "unknown"),
            "org": a.get("Organization", {}).get("Slug", ""),
            # `fly status --json` carries no App.CreatedAt, so age comes from the
            # last release here instead — which is the better staleness signal
            # anyway, and needs no extra call per app.
            "last_deployed": _release_timestamp(a),
        }
        for a in raw
    ]


_ZERO_TIME = "0001-01-01T00:00:00Z"


def _release_timestamp(app: dict[str, Any]) -> str | None:
    release = app.get("CurrentRelease") or {}
    created = release.get("CreatedAt")
    if not created or created == _ZERO_TIME:
        return None
    return created


def list_demos_only(apps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Filter to apps that look like demos.

    Heuristics:
    - Drop apps ending in '-db' (Fly Postgres clusters).
    - For nextjs-fastapi pairs (<base>-web + <base>-api), collapse to one entry
      named <base> with kind='nextjs-fastapi'. The -api app is hidden;
      the -web app is the canonical demo entry.
    """
    names = {a["name"] for a in apps}
    demos = []
    seen_bases = set()
    for app in apps:
        n = app["name"]
        if n.endswith("-db"):
            continue
        if n.endswith("-api"):
            base = n.removesuffix("-api")
            if f"{base}-web" in names:
                # paired with a -web app; skip (covered by the -web entry)
                continue
        if n.endswith("-web"):
            base = n.removesuffix("-web")
            if base in seen_bases:
                continue
            seen_bases.add(base)
            demos.append({**app, "name": base, "kind": "nextjs-fastapi"})
            continue
        demos.append(app)
    return demos


def fly_app_name(demo: dict[str, Any]) -> str:
    """Return a name that actually exists on Fly for a `list_demos_only` entry.

    A nextjs-fastapi pair is collapsed to a synthetic entry named <base>, which
    is not a real app — Fly lookups against it always 404. Use <base>-web.
    """
    if demo.get("kind") == "nextjs-fastapi":
        return f"{demo['name']}-web"
    return demo["name"]


def fetch_app_config(app_name: str) -> dict[str, Any] | None:
    """Return an app's deployed fly.toml as a dict, or None if unreadable."""
    try:
        r = subprocess.run(
            ["fly", "config", "show", "--app", app_name],
            capture_output=True, text=True, check=True,
        )
        return json.loads(r.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


# Fly treats a missing auto_stop_machines as "off" — the machine never stops.
_NEVER_STOPS = (False, "off")


def is_always_on(config: dict[str, Any] | None) -> bool:
    """True if the deployed config keeps at least one machine running 24/7.

    This is how a `service`-profile app is told apart from a `demo` one after
    deploy. The profile is a scaffold-time branch and is never recorded on Fly,
    but the autostop settings it produces are, so they stand in for it.

    Errs towards True: an unreadable or serviceless config counts as always-on
    so that prune keeps it rather than destroying something it cannot classify.
    """
    if config is None:
        return True

    blocks: list[dict[str, Any]] = []
    http = config.get("http_service")
    if isinstance(http, dict):
        blocks.append(http)
    services = config.get("services")
    if isinstance(services, list):
        blocks.extend(b for b in services if isinstance(b, dict))

    if not blocks:
        return True

    for b in blocks:
        if (b.get("min_machines_running") or 0) >= 1:
            return True
        if b.get("auto_stop_machines", "off") in _NEVER_STOPS:
            return True
    return False


def parse_duration(s: str) -> timedelta:
    """Parse strings like '14d', '6h', '30m' into a timedelta."""
    m = re.fullmatch(r"(\d+)([dhm])", s)
    if not m:
        raise ValueError(f"Invalid duration: {s!r}. Use forms like '14d', '6h', '30m'.")
    n, unit = int(m.group(1)), m.group(2)
    return {
        "d": timedelta(days=n),
        "h": timedelta(hours=n),
        "m": timedelta(minutes=n),
    }[unit]
