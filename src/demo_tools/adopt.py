from __future__ import annotations

import json
from pathlib import Path


def detect_stack(repo: Path) -> str | None:
    """Best-effort stack detection. Returns None if ambiguous."""
    pkg = repo / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "next" in deps:
            return "nextjs"
        if "vite" in deps or "@vitejs/plugin-react" in deps:
            return "static"
        if "astro" in deps:
            return "static"
        # Plain React/Svelte without Vite — treat as static still
        if "react" in deps or "svelte" in deps or "vue" in deps:
            return "static"

    requirements = repo / "requirements.txt"
    pyproject = repo / "pyproject.toml"
    text = ""
    if requirements.exists():
        text += requirements.read_text().lower()
    if pyproject.exists():
        text += pyproject.read_text().lower()
    if text:
        if "streamlit" in text:
            return "streamlit"
        if "fastapi" in text:
            return "fastapi"

    return None
