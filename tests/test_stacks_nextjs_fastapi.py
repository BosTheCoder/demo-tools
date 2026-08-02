from unittest.mock import patch, MagicMock

from demo_tools.stacks import nextjs_fastapi


def test_api_fly_toml_sets_autostop(tmp_path):
    """Fly defaults auto_stop_machines to "off" when absent, which billed the
    api machine 24/7 for the life of the app. The keys must be explicit."""
    with patch("demo_tools.stacks.nextjs_fastapi.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        nextjs_fastapi.scaffold(tmp_path, "tmp-demo")
    api_toml = (tmp_path / "api" / "fly.toml").read_text()
    assert 'auto_stop_machines = "stop"' in api_toml
    assert "auto_start_machines = true" in api_toml
    assert "min_machines_running = 0" in api_toml


def test_nextjs_fastapi_creates_web_and_api_dirs(tmp_path):
    with patch("demo_tools.stacks.nextjs_fastapi.subprocess.run") as run:
        run.return_value = MagicMock(returncode=0)
        meta = nextjs_fastapi.scaffold(tmp_path, "tmp-demo")
    # web/ comes from create-next-app + standalone config
    # api/ comes from copying our starter
    assert (tmp_path / "api" / "main.py").exists()
    assert (tmp_path / "api" / "requirements.txt").exists()
    assert (tmp_path / "api" / "Dockerfile").exists()
    assert (tmp_path / "web" / "Dockerfile").exists()
    assert meta["stack"] == "nextjs-fastapi"
    assert meta["stateful"] is True
    # internal_port is web's port (3000); api's port is 8000 implicitly
    assert meta["internal_port"] == 3000
