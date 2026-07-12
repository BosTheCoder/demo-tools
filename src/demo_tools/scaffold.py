from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from copier import run_copy

from ._resources import (
    DEFAULT_DOMAIN,
    DEFAULT_TAILSCALE_HOST,
    TEMPLATE_DIR,
    TEMPLATE_GIT_URL,
    TEMPLATE_SUBDIR,
)
from .stacks import get_scaffolder


def scaffold_demo(
    stack: str,
    name: str,
    target: Path,
    profile: str = "demo",
    *,
    deploy_target: str = "fly",
    tailscale_path: str | None = None,
) -> None:
    """Scaffold app + overlay infra + git init + initial commit.

    ``deploy_target`` picks the default `just` dispatch target ("fly" or
    "local"); both ``infra/`` sets are always generated so graduation is a flip.
    ``tailscale_path`` overrides the local URL path prefix (defaults to /<name>).
    """
    target.mkdir(parents=True, exist_ok=True)

    scaffolder = get_scaffolder(stack)
    meta = scaffolder.scaffold(target, name)

    ts_host = DEFAULT_TAILSCALE_HOST
    ts_path = tailscale_path or f"/{name}"

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(target),
        data={
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "domain_base": DEFAULT_DOMAIN,
            "profile": profile,
            "target": deploy_target,
            "tailscale_host": ts_host,
            "tailscale_path": ts_path,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
        overwrite=True,
    )

    # Write the Copier answers file with the GitHub URL form so `just sync`
    # (which runs `copier update`) can fetch the latest template from a real
    # VCS source. Copier rejects bare local paths for update operations.
    # This requires the demo-tools repo to be published (Task 7.5); pre-publish,
    # `just sync` will fail with a clone error — that's acceptable for v0.1.
    answers_path = target / ".demo-template-version"
    if not answers_path.exists():
        answers_path.write_text(yaml.safe_dump({
            "_src_path": TEMPLATE_GIT_URL,
            "_subdirectory": TEMPLATE_SUBDIR,
            "_commit": "main",
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "domain_base": DEFAULT_DOMAIN,
            "profile": profile,
            "target": deploy_target,
            "tailscale_host": ts_host,
            "tailscale_path": ts_path,
        }))

    _git_init_and_commit(target)


def _git_init_and_commit(target: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
    subprocess.run(["git", "add", "."], cwd=target, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: initial scaffold via demo-tools"],
        cwd=target,
        check=True,
    )
