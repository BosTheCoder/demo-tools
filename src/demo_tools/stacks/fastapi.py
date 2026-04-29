from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
STARTER = REPO_ROOT / "starters" / "fastapi"


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    shutil.copytree(STARTER, app_dir)
    return {"stack": "fastapi", "stateful": True, "internal_port": 8000}
