from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .. import pwa


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

    # Vite copies public/ to the root of the build, so these land beside the
    # page and the worker's scope covers the whole app.
    pwa.write_assets(app_dir / "public", name)
    _make_installable(app_dir / "index.html")

    return {"stack": "vite", "stateful": False, "internal_port": 80}


def _make_installable(index_html: Path) -> None:
    """Add the manifest links and worker registration to Vite's index.html."""
    if not index_html.is_file():
        return
    html = index_html.read_text(encoding="utf-8")
    if "manifest.webmanifest" in html:
        return
    html = html.replace("</head>", f"{pwa.head_tags()}\n  </head>", 1)
    html = html.replace("</body>", f"{_REGISTER}\n  </body>", 1)
    index_html.write_text(html, encoding="utf-8")


_REGISTER = """  <script>
      // Non-fatal by design: without the worker the app still runs, it just
      // loses its offline fallback.
      if ("serviceWorker" in navigator) {
        window.addEventListener("load", function () {
          navigator.serviceWorker.register("/sw.js").catch(function () {});
        });
      }
    </script>"""
