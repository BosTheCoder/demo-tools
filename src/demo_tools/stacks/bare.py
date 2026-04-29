from __future__ import annotations

from pathlib import Path
from typing import Any


def scaffold(target: Path, name: str) -> dict[str, Any]:
    """Create an empty app/ directory. Claude fills in the actual app code."""
    app_dir = target / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / ".gitkeep").touch()
    return {"stack": "bare", "stateful": False, "internal_port": 3000}
