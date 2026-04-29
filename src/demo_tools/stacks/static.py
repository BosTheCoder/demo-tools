from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npm", "create", "vite@latest", "--yes",
        str(app_dir), "--", "--template", "react-ts",
    ]
    subprocess.run(cmd, check=True)
    subprocess.run(["npm", "install"], cwd=app_dir, check=True)

    return {"stack": "static", "stateful": False, "internal_port": 80}
