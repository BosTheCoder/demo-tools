"""End-to-end scaffold tests across all six stacks.

Pure-Python stacks (bare, fastapi, streamlit) actually run their scaffolders.
Node-based stacks (nextjs, static, nextjs-fastapi) intercept npx/npm calls but
pass through everything else (git, Copier's rm in _tasks) to the real
subprocess.run. Without the passthrough, Copier's _tasks cleanup for
nextjs-fastapi (rm -f Dockerfile fly.toml compose.yml) wouldn't run.
"""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from demo_tools.scaffold import scaffold_demo

_REAL_RUN = subprocess.run


def _is_npm_or_npx(cmd) -> bool:
    if not cmd or not isinstance(cmd, (list, tuple)):
        return False
    first = str(cmd[0]) if cmd else ""
    return "npx" in first or first == "npm" or any("npx" in str(c) for c in cmd)


@pytest.mark.parametrize("stack", ["bare", "fastapi", "streamlit"])
def test_scaffold_pure_python_stacks(stack, tmp_path):
    target = tmp_path / "tmp-demo"
    scaffold_demo(stack, "tmp-demo", target)
    assert (target / "Dockerfile").exists()
    assert (target / "justfile").exists()
    assert (target / ".demo-template-version").exists()
    assert (target / ".git").is_dir()


@pytest.mark.parametrize("stack", ["nextjs", "static"])
def test_scaffold_node_stacks_mocks_npm(stack, tmp_path):
    target = tmp_path / "tmp-demo"

    def fake_run(cmd, **kwargs):
        if _is_npm_or_npx(cmd):
            app = target / "app"
            app.mkdir(parents=True, exist_ok=True)
            (app / "package.json").write_text('{"name":"x"}')
            if stack == "nextjs":
                (app / "next.config.mjs").write_text("export default {}")
            return MagicMock(returncode=0)
        return _REAL_RUN(cmd, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        scaffold_demo(stack, "tmp-demo", target)
    assert (target / "Dockerfile").exists()
    assert (target / "justfile").exists()


def test_scaffold_nextjs_fastapi_mocks_npm(tmp_path):
    target = tmp_path / "tmp-demo"

    def fake_run(cmd, **kwargs):
        if _is_npm_or_npx(cmd):
            web = target / "web"
            web.mkdir(parents=True, exist_ok=True)
            (web / "package.json").write_text('{"name":"x"}')
            return MagicMock(returncode=0)
        return _REAL_RUN(cmd, **kwargs)

    with patch("subprocess.run", side_effect=fake_run):
        scaffold_demo("nextjs-fastapi", "tmp-demo", target)
    # Both per-service fly.toml files written
    assert (target / "web" / "fly.toml").exists()
    assert (target / "api" / "fly.toml").exists()
    # Justfile/infra still produced at root
    assert (target / "justfile").exists()
    # Top-level Dockerfile/fly.toml/compose.yml removed by _tasks
    assert not (target / "Dockerfile").exists()
    assert not (target / "fly.toml").exists()
