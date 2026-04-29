import tempfile
from pathlib import Path

from demo_tools.stacks import bare


def test_bare_scaffold_creates_empty_app_dir():
    tmp = Path(tempfile.mkdtemp())
    bare.scaffold(tmp, "tmp-demo")
    assert (tmp / "app").is_dir()
    assert (tmp / "app" / ".gitkeep").exists()


def test_bare_scaffold_returns_metadata():
    tmp = Path(tempfile.mkdtemp())
    meta = bare.scaffold(tmp, "tmp-demo")
    assert meta["stack"] == "bare"
    assert meta["stateful"] is False
    assert meta["internal_port"] == 3000
