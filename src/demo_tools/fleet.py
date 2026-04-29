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
        }
        for a in raw
    ]


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
