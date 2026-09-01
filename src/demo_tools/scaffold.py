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
    template_commit,
)
from .stacks import get_scaffolder
from .targets import NO_DOCKERFILE_STACKS, check_target_stack, publish_mode


def scaffold_demo(
    stack: str,
    name: str,
    target: Path,
    profile: str = "demo",
    *,
    deploy_target: str = "fly",
    tailscale_path: str | None = None,
    host_port: int | None = None,
    pwa_assets: bool = True,
) -> None:
    """Scaffold app + overlay infra + git init + initial commit.

    ``deploy_target`` picks the default `just` dispatch target ("fly", "local"
    or "pages"). Every ``infra/`` set the stack can actually use is generated,
    so graduating between compatible targets is a flip; sets the stack can never
    use are dropped (see copier.yml's _tasks) rather than shipped dead.
    ``tailscale_path`` overrides the local URL path prefix (defaults to /<name>).
    ``host_port`` overrides the host side of the local target's port mapping;
    it defaults to the container port and only needs setting when another
    local app already publishes that port.
    ``pwa_assets`` generates the manifest, service worker and icons that make a
    demo installable. Pass False for a page that is not an app — a redirect or
    a single-field converter, where an offline shell can only serve a stale
    copy of the thing the page exists to do.
    """
    check_target_stack(deploy_target, stack)

    target.mkdir(parents=True, exist_ok=True)

    scaffolder = get_scaffolder(stack)
    meta = scaffolder.scaffold(target, name, pwa_assets=pwa_assets)

    ts_host = DEFAULT_TAILSCALE_HOST
    ts_path = tailscale_path or f"/{name}"
    host_p = host_port or meta["internal_port"]
    derived = _target_flags(stack)

    run_copy(
        src_path=str(TEMPLATE_DIR),
        dst_path=str(target),
        data={
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "host_port": host_p,
            "domain_base": DEFAULT_DOMAIN,
            "hostnames": [f"{name}.{DEFAULT_DOMAIN}"],
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
            "_commit": template_commit(),
            "name": name,
            "stack": stack,
            "stateful": meta["stateful"],
            "internal_port": meta["internal_port"],
            "host_port": host_p,
            "domain_base": DEFAULT_DOMAIN,
            "hostnames": [f"{name}.{DEFAULT_DOMAIN}"],
            "profile": profile,
            "target": deploy_target,
            "tailscale_host": ts_host,
            "tailscale_path": ts_path,
            **derived,
        }))

    _git_init_and_commit(target)


def _target_flags(stack: str) -> dict[str, object]:
    """Template variables derived from the stack, so copier.yml never has to
    restate the compatibility rules that live in targets.py."""
    return {
        "dockerised": stack not in NO_DOCKERFILE_STACKS,
        "pages_ok": _pages_ok(stack),
        "publish_mode": publish_mode(stack),
    }


def _pages_ok(stack: str) -> bool:
    try:
        check_target_stack("pages", stack)
    except ValueError:
        return False
    return True


def _git_init_and_commit(target: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=target, check=True)
    subprocess.run(["git", "add", "."], cwd=target, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "chore: initial scaffold via demo-tools"],
        cwd=target,
        check=True,
    )
