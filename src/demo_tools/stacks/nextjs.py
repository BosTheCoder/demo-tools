from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def scaffold(target: Path, name: str) -> dict[str, Any]:
    app_dir = target / "app"
    app_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "npx", "--yes", "create-next-app@latest",
        app_dir.name,
        "--ts", "--app", "--tailwind", "--src-dir",
        "--use-npm", "--no-eslint", "--no-import-alias",
    ]
    # Relative path + cwd=parent (some upstream scaffolders mishandle absolute
    # paths). stdin=DEVNULL keeps the run non-interactive.
    subprocess.run(cmd, check=True, cwd=app_dir.parent, stdin=subprocess.DEVNULL)

    # Patch next.config to enable standalone output (required by our Dockerfile).
    # create-next-app v16+ emits next.config.ts; older versions emit .mjs/.js.
    # Remove any variant the upstream wrote so our single .mjs is authoritative.
    for ext in ("ts", "js", "mjs"):
        (app_dir / f"next.config.{ext}").unlink(missing_ok=True)
    (app_dir / "next.config.mjs").write_text(
        "/** @type {import('next').NextConfig} */\n"
        "const nextConfig = { output: 'standalone' };\n"
        "export default nextConfig;\n"
    )

    return {"stack": "nextjs", "stateful": False, "internal_port": 3000}
