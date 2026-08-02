from __future__ import annotations

import json
from pathlib import Path

import yaml
from copier import run_copy

from .targets import NO_DOCKERFILE_STACKS, check_target_stack, publish_mode
from ._resources import (
    DEFAULT_DOMAIN,
    DEFAULT_TAILSCALE_HOST,
    TEMPLATE_DIR,
    TEMPLATE_GIT_URL,
    TEMPLATE_SUBDIR,
)


def detect_stack(repo: Path) -> str | None:
    """Best-effort stack detection. Returns None if ambiguous."""
    pkg = repo / "package.json"
    if pkg.exists():
        data = json.loads(pkg.read_text())
        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if "next" in deps:
            return "nextjs"
        if "vite" in deps or "@vitejs/plugin-react" in deps:
            return "vite"
        if "astro" in deps:
            return "vite"
        # Plain React/Svelte without Vite — still a bundled SPA
        if "react" in deps or "svelte" in deps or "vue" in deps:
            return "vite"

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


def overlay_infra(
    repo: Path,
    *,
    name: str,
    stack: str,
    stateful: bool,
    internal_port: int,
    profile: str = "demo",
    deploy_target: str = "fly",
    tailscale_path: str | None = None,
) -> None:
    """Apply the Copier infra overlay onto an existing dockerized repo.

    Skips files that already exist (existing Dockerfile, package.json, app code,
    etc. are preserved). Only adds the missing infra layer: justfile, fly.toml,
    infra/fly/*.sh, infra/local/*.sh, .demo-template-version, etc.

    ``deploy_target`` sets the default `just` dispatch target; ``tailscale_path``
    overrides the local URL path prefix (defaults to /<name>).
    """
    if deploy_target != "pages" and not (repo / "Dockerfile").exists():
        raise FileNotFoundError(
            f"No Dockerfile found in {repo}. "
            "`adopt` is for existing dockerized repos. "
            "Use `demo-init <stack> <name>` to scaffold a new demo."
        )

    ts_host = DEFAULT_TAILSCALE_HOST
    ts_path = tailscale_path or f"/{name}"
    derived = {
        "dockerised": stack not in NO_DOCKERFILE_STACKS,
        "pages_ok": _pages_ok(stack),
        "publish_mode": publish_mode(stack),
    }

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(repo),
        data={
            "name": name,
            "stack": stack,
            "stateful": stateful,
            "internal_port": internal_port,
            "domain_base": DEFAULT_DOMAIN,
            "profile": profile,
            "target": deploy_target,
            "tailscale_host": ts_host,
            "tailscale_path": ts_path,
            **derived,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
        overwrite=True,
        skip_if_exists=["**"],
    )

    answers_path = repo / ".demo-template-version"
    if not answers_path.exists():
        answers_path.write_text(yaml.safe_dump({
            "_src_path": TEMPLATE_GIT_URL,
            "_subdirectory": TEMPLATE_SUBDIR,
            "_commit": "main",
            "name": name,
            "stack": stack,
            "stateful": stateful,
            "internal_port": internal_port,
            "domain_base": DEFAULT_DOMAIN,
            "profile": profile,
            "target": deploy_target,
            "tailscale_host": ts_host,
            "tailscale_path": ts_path,
            **derived,
        }))


def _pages_ok(stack: str) -> bool:
    try:
        check_target_stack("pages", stack)
    except ValueError:
        return False
    return True
