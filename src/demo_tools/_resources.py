"""Resolved paths to bundled package data (template + starters).

These resolve correctly under both dev install (`uv sync` from a clone) and
end-user install (`uv tool install ...`). The package data is under
`src/demo_tools/_data/` and is shipped via hatchling's `force-include` config
in `pyproject.toml`.
"""

from __future__ import annotations

from pathlib import Path

_PKG_ROOT = Path(__file__).resolve().parent

TEMPLATE_DIR = _PKG_ROOT / "_data" / "template"
STARTERS_DIR = _PKG_ROOT / "_data" / "starters"
DEFAULT_DOMAIN = "demos.buildwithbos.com"

# Default deploy target and the local (Tailscale) target's host. The tailscale
# path defaults to "/<name>" (computed per-project). These mirror the Copier
# question defaults so the CLI can write concrete values into the answers file.
DEFAULT_TARGET = "fly"
DEFAULT_TAILSCALE_HOST = "bos-desktop.fish-grouper.ts.net"

# Git URL that `copier update` (invoked by `just sync` from a demo) will fetch
# from. Initial scaffold uses TEMPLATE_DIR (bundled package data, no network).
# Updates need a VCS-tracked source — Copier rejects plain local paths for
# update operations.
TEMPLATE_GIT_URL = "https://github.com/BosTheCoder/demo-tools"
TEMPLATE_SUBDIR = "src/demo_tools/_data/template"


def template_commit() -> str:
    """The template revision to record in a demo's `.demo-template-version`.

    This used to be the literal string "main", which quietly made `just sync` a
    no-op forever: `copier update` diffs the recorded ref against the new one,
    and main->main is no diff, so it printed "Keeping template version" and
    changed nothing. Recording a real SHA gives copier something to diff from.

    Resolution order:
      1. HEAD of the demo-tools checkout we're running from — the actual source
         of the bundled template, and on a dev machine it matches the pushed
         remote. Skipped if the checkout is dirty, since that HEAD wouldn't
         describe what was really rendered.
      2. `git ls-remote` of the published URL, for installs with no checkout
         (uvx / uv tool install).
      3. "main" — no worse than the old behaviour when offline.
    """
    import subprocess

    def _git(*args: str, cwd: Path | None = None) -> str | None:
        try:
            r = subprocess.run(["git", *args], cwd=cwd, capture_output=True,
                               text=True, timeout=15)
        except (OSError, subprocess.SubprocessError):
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    repo = _PKG_ROOT.parent.parent  # src/demo_tools -> src -> repo root
    if (repo / ".git").exists():
        # A dirty tree means the rendered template isn't what that SHA holds.
        dirty = _git("status", "--porcelain", "--", str(TEMPLATE_DIR), cwd=repo)
        if not dirty:
            head = _git("rev-parse", "HEAD", cwd=repo)
            if head:
                return head

    remote = _git("ls-remote", TEMPLATE_GIT_URL, "main")
    if remote:
        return remote.split()[0]

    return "main"
