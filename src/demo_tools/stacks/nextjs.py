from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npx", "--yes", "create-next-app@latest",
        str(app_dir),
        "--ts", "--app", "--tailwind", "--src-dir",
        "--use-npm", "--no-eslint", "--no-import-alias",
    ]
    subprocess.run(cmd, check=True)

    # Patch next.config to enable standalone output (required by our Dockerfile).
    cfg = app_dir / "next.config.mjs"
    cfg.write_text(
        "/** @type {import('next').NextConfig} */\n"
        "const nextConfig = { output: 'standalone' };\n"
        "export default nextConfig;\n"
    )

    return {"stack": "nextjs", "stateful": False, "internal_port": 3000}
