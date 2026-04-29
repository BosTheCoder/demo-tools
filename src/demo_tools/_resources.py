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

# Git URL that `copier update` (invoked by `just sync` from a demo) will fetch
# from. Initial scaffold uses TEMPLATE_DIR (bundled package data, no network).
# Updates need a VCS-tracked source — Copier rejects plain local paths for
# update operations.
TEMPLATE_GIT_URL = "https://github.com/BosTheCoder/demo-tools"
TEMPLATE_SUBDIR = "src/demo_tools/_data/template"
