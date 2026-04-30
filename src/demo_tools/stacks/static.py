from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npm", "create", "vite@latest", "--yes",
        app_dir.name, "--", "--template", "react-ts",
    ]
    # cwd=parent + relative path: create-vite v8 strips the leading slash from
    # absolute paths and joins onto cwd, so passing an absolute path scaffolds
    # into <cwd>/<abs-path-without-slash>. stdin=DEVNULL also suppresses the
    # "Install with npm and start now?" prompt that would otherwise hang.
    subprocess.run(cmd, check=True, cwd=app_dir.parent, stdin=subprocess.DEVNULL)
    subprocess.run(["npm", "install"], cwd=app_dir, check=True)

    return {"stack": "static", "stateful": False, "internal_port": 80}
