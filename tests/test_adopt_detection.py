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


def test_detects_static_vite(tmp_path):
    _write_pkg(tmp_path / "package.json", {"react": "^18"}, {"vite": "^5"})
    assert detect_stack(tmp_path) == "static"


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
