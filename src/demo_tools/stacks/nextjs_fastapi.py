from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .._resources import STARTERS_DIR

STARTER = STARTERS_DIR / "nextjs-fastapi"


def scaffold(target: Path, name: str) -> dict[str, Any]:
    web_dir = target / "web"
    api_dir = target / "api"

    # API: copy starter as-is.
    shutil.copytree(STARTER / "api", api_dir)
    _render_fly_toml(api_dir, name, role="api")

    # WEB: scaffold via create-next-app, then overlay Dockerfile + fly.toml.
    cmd = [
        "npx", "--yes", "create-next-app@latest",
        str(web_dir),
        "--ts", "--app", "--tailwind", "--src-dir",
        "--use-npm", "--no-eslint", "--no-import-alias",
    ]
    subprocess.run(cmd, check=True)

    # When subprocess is mocked (in tests), web_dir won't be created. Make sure
    # it exists before writing into it. In production, create-next-app creates
    # web_dir; this mkdir(exist_ok=True) is a no-op then.
    web_dir.mkdir(parents=True, exist_ok=True)

    # Patch next.config for standalone output.
    (web_dir / "next.config.mjs").write_text(
        "/** @type {import('next').NextConfig} */\n"
        "const nextConfig = { output: 'standalone' };\n"
        "export default nextConfig;\n"
    )
    # Overlay our Dockerfile (Copier will not touch web/ or api/ subdirs).
    shutil.copy(STARTER / "web" / "Dockerfile", web_dir / "Dockerfile")
    _render_fly_toml(web_dir, name, role="web")

    return {"stack": "nextjs-fastapi", "stateful": True, "internal_port": 3000}


def _render_fly_toml(service_dir: Path, name: str, *, role: str) -> None:
    src = STARTER / role / "fly.toml.template"
    body = src.read_text()
    body = body.replace("__APP_WEB__", f"{name}-web")
    body = body.replace("__APP_API__", f"{name}-api")
    body = body.replace("__VOLUME_NAME__", f"{name.replace('-', '_')}_api_data")
    (service_dir / "fly.toml").write_text(body)
