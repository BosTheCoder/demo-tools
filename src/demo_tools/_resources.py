"""Resolved paths to bundled package data (template + starters).

These resolve correctly under both dev install (`uv sync` from a clone) and
end-user install (`uv tool install ...`). The package data is under
`src/demo_tools/_data/` and is shipped via hatchling's `force-include` config
in `pyproject.toml`.
"""

from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent

TEMPLATE_DIR = _PKG_ROOT / "_data" / "template"
STARTERS_DIR = _PKG_ROOT / "_data" / "starters"
DEFAULT_DOMAIN = "demos.buildwithbos.com"
