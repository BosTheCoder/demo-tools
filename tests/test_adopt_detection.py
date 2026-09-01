import json
from pathlib import Path

from demo_tools.adopt import detect_stack


def _write_pkg(p: Path, deps: dict, dev_deps: dict | None = None):
    p.write_text(json.dumps({
        "name": "x",
        "dependencies": deps,
        "devDependencies": dev_deps or {},
    }))


def test_detects_nextjs(tmp_path):
    _write_pkg(tmp_path / "package.json", {"next": "^14.0.0", "react": "^18.0.0"})
    assert detect_stack(tmp_path) == "nextjs"


def test_detects_vite(tmp_path):
    _write_pkg(tmp_path / "package.json", {"react": "^18"}, {"vite": "^5"})
    assert detect_stack(tmp_path) == "vite"


def test_detects_fastapi(tmp_path):
    (tmp_path / "requirements.txt").write_text("fastapi>=0.100\nuvicorn>=0.30\n")
    assert detect_stack(tmp_path) == "fastapi"


def test_detects_streamlit(tmp_path):
    (tmp_path / "requirements.txt").write_text("streamlit>=1.30\npandas\n")
    assert detect_stack(tmp_path) == "streamlit"


def test_returns_none_on_ambiguous(tmp_path):
    # Just a Dockerfile, no other signals
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    assert detect_stack(tmp_path) is None


def test_adopt_on_pages_does_not_send_you_to_review_a_fly_toml(mocker, tmp_path, monkeypatch):
    """A pages project has no fly.toml. Pointing at one is how you learn the
    message was written for a different target."""
    from typer.testing import CliRunner
    from demo_tools.cli import init_app

    monkeypatch.chdir(tmp_path)
    mocker.patch("demo_tools.adopt.overlay_infra")
    result = CliRunner().invoke(
        init_app, ["adopt", "--stack", "html", "--target", "pages", "--yes"]
    )
    assert result.exit_code == 0, result.stdout
    assert "fly.toml" not in result.stdout
    assert "CNAME" in result.stdout
