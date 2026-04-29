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


@pytest.mark.parametrize("stack", ["bare", "nextjs", "static", "fastapi", "streamlit"])
def test_all_stacks_render_dockerfile(stack):
    """Single-app stacks render a top-level Dockerfile.

    nextjs-fastapi is excluded because its real Dockerfiles live in web/ and api/
    (written by the scaffolder); the top-level placeholder is removed by the
    Copier _tasks post-process step. See test_nextjs_fastapi_skips_top_level_*.
    """
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


def test_justfile_has_all_verbs():
    out = _render("bare", internal_port=3000)
    just = (out / "justfile").read_text()
    for verb in ["dev:", "build:", "deploy:", "stop:", "start:",
                 "destroy:", "logs:", "ssh:", "status:", "open:", "sync:"]:
        assert verb in just, f"missing verb: {verb}"


def test_readme_contains_demo_name_and_urls():
    out = _render("nextjs", internal_port=3000)
    readme = (out / "README.md").read_text()
    assert "tmp-demo" in readme
    assert "tmp-demo.fly.dev" in readme
    assert "tmp-demo.demos.buildwithbos.com" in readme


def test_copier_yml_does_not_leak_into_rendered_demo():
    """Regression: _exclude must include copier.yml or it ships in every demo."""
    out = _render("bare", internal_port=3000)
    assert not (out / "copier.yml").exists()
    assert not (out / "copier.yaml").exists()


def test_deploy_sh_renders_with_app_name():
    out = _render("nextjs", internal_port=3000)
    deploy = (out / "infra" / "fly" / "deploy.sh").read_text()
    assert "tmp-demo" in deploy
    assert "fly deploy" in deploy
    assert "fly certs add" in deploy
    assert "tmp-demo.demos.buildwithbos.com" in deploy


def test_all_infra_scripts_render():
    out = _render("nextjs", internal_port=3000)
    fly_dir = out / "infra" / "fly"
    for script in ["stop.sh", "start.sh", "destroy.sh", "logs.sh",
                   "ssh.sh", "status.sh", "open.sh"]:
        path = fly_dir / script
        assert path.exists(), f"missing {script}"
        if script != "open.sh":
            assert "tmp-demo" in path.read_text()


def test_destroy_sh_has_confirmation_prompt():
    out = _render("nextjs", internal_port=3000)
    destroy = (out / "infra" / "fly" / "destroy.sh").read_text()
    assert "[y/N]" in destroy


def test_secret_sh_takes_kv_arg():
    out = _render("nextjs", internal_port=3000)
    secret = (out / "infra" / "fly" / "secret.sh").read_text()
    assert "fly secrets set" in secret
    assert "${1" in secret  # accepts $1 with default substitution


def test_db_create_sh_only_works_for_stateful_stacks():
    nextjs_out = _render("nextjs")
    fastapi_out = _render("fastapi", internal_port=8000)
    nextjs_db = (nextjs_out / "infra" / "fly" / "db-create.sh").read_text()
    fastapi_db = (fastapi_out / "infra" / "fly" / "db-create.sh").read_text()
    assert "not applicable for stack 'nextjs'" in nextjs_db
    assert "fly postgres create" in fastapi_db


def test_nextjs_fastapi_skips_top_level_dockerfile_and_fly_toml():
    """For nextjs-fastapi, real Dockerfile/fly.toml live in web/ and api/.
    The top-level placeholders rendered by the template must be removed by
    Copier's _tasks post-process step."""
    out = _render("nextjs-fastapi", internal_port=3000)
    assert not (out / "Dockerfile").exists(), "top-level Dockerfile should be removed"
    assert not (out / "fly.toml").exists(), "top-level fly.toml should be removed"
    assert not (out / "compose.yml").exists(), "top-level compose.yml should be removed"
    # Infra scripts should still be there.
    assert (out / "infra" / "fly" / "deploy.sh").exists()
