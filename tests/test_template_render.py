from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from copier import run_copy

REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = REPO_ROOT / "template"


def _render(stack: str, **overrides) -> Path:
    tmp = Path(tempfile.mkdtemp())
    data = {
        "name": "tmp-demo",
        "stack": stack,
        "stateful": stack in {"fastapi", "nextjs-fastapi", "streamlit"},
        "internal_port": overrides.get("internal_port", 3000),
        "domain_base": "demos.buildwithbos.com",
    }
    data.update(overrides)
    run_copy(src_path=str(TEMPLATE), dst_path=str(tmp), data=data,
             defaults=True, unsafe=True, quiet=True)
    return tmp


def test_bare_renders_dockerfile():
    out = _render("bare", internal_port=3000)
    dockerfile = out / "Dockerfile"
    assert dockerfile.exists()
    content = dockerfile.read_text()
    assert "TODO" in content  # bare stack ships with a placeholder


@pytest.mark.parametrize("stack", ["bare", "nextjs", "static", "fastapi", "streamlit", "nextjs-fastapi"])
def test_all_stacks_render_dockerfile(stack):
    out = _render(stack)
    dockerfile = out / "Dockerfile"
    assert dockerfile.exists()
    assert dockerfile.read_text().strip() != ""


def test_bare_renders_fly_toml_with_correct_port():
    out = _render("bare", internal_port=3000)
    fly_toml = out / "fly.toml"
    assert fly_toml.exists()
    content = fly_toml.read_text()
    assert 'app = "tmp-demo"' in content
    assert "internal_port = 3000" in content
    assert "auto_stop_machines" in content


def test_stateful_stack_includes_volume_mount():
    out = _render("fastapi", internal_port=8000)
    fly_toml = (out / "fly.toml").read_text()
    assert "[mounts]" in fly_toml
    assert 'destination = "/data"' in fly_toml


def test_compose_yml_exposes_internal_port():
    out = _render("nextjs", internal_port=3000)
    compose = (out / "compose.yml").read_text()
    assert '"3000:3000"' in compose
    assert "build: ." in compose
