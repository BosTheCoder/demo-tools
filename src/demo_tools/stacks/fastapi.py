from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .. import pwa
from .._resources import STARTERS_DIR

STARTER = STARTERS_DIR / "fastapi"


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    shutil.copytree(STARTER, app_dir)

    # Scope and icon paths are left as {{ROOT_PATH}} for main.py to substitute
    # per request: one image serves both "/" on Fly and "/<name>" locally, so
    # the prefix cannot be baked in at scaffold time.
    pwa.write_assets(
        app_dir / "static",
        name,
        scope="{{ROOT_PATH}}/",
        assets="{{ROOT_PATH}}/static",
    )
    return {"stack": "fastapi", "stateful": True, "internal_port": 8000}
