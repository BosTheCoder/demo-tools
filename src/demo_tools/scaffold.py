from __future__ import annotations

import subprocess
from pathlib import Path

import yaml
from copier import run_copy

from ._resources import DEFAULT_DOMAIN, TEMPLATE_DIR
from .stacks import get_scaffolder


def scaffold_demo(stack: str, name: str, target: Path) -> None:
    """Scaffold app + overlay infra + git init + initial commit."""
    target.mkdir(parents=True, exist_ok=True)

    scaffolder = get_scaffolder(stack)
    meta = scaffolder.scaffold(target, name)

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(target),
        data={
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "domain_base": DEFAULT_DOMAIN,
        },
        defaults=True,
        unsafe=True,
        quiet=True,
        overwrite=True,
    )

    answers_path = target / ".demo-template-version"
    if not answers_path.exists():
        answers_path.write_text(yaml.safe_dump({
            "_src_path": str(TEMPLATE_DIR),
            "_commit": "HEAD",
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "domain_base": DEFAULT_DOMAIN,
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
