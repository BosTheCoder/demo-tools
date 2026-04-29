from unittest.mock import patch, MagicMock

from demo_tools.stacks import nextjs_fastapi


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
