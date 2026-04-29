from pathlib import Path
from unittest.mock import patch, MagicMock

from demo_tools.stacks import nextjs


def test_nextjs_scaffold_invokes_create_next_app(tmp_path):
    with patch("demo_tools.stacks.nextjs.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        meta = nextjs.scaffold(tmp_path, "tmp-demo")
        run.assert_called_once()
        cmd = run.call_args.args[0]
        assert "npx" in cmd[0] or "create-next-app" in " ".join(cmd)
        assert "--ts" in cmd
        assert "--app" in cmd
        assert "--tailwind" in cmd
        assert "--src-dir" in cmd
        # Output dir is target/app
        assert str(tmp_path / "app") in cmd
    assert meta["internal_port"] == 3000
    assert meta["stateful"] is False


def test_nextjs_scaffold_writes_standalone_config(tmp_path):
    """next.config.mjs must include `output: 'standalone'` for the Dockerfile to work."""
    (tmp_path / "app").mkdir()
    with patch("demo_tools.stacks.nextjs.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        nextjs.scaffold(tmp_path, "tmp-demo")
    cfg = tmp_path / "app" / "next.config.mjs"
    assert cfg.exists()
    assert "standalone" in cfg.read_text()
