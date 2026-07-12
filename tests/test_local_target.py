"""Tests for the `local` deploy target (persistent container + Tailscale).

Covers Copier render output (infra/local scripts, compose overlay, justfile
dispatch), coexistence with Fly, the fastapi starter's ROOT_PATH base-path
awareness, and the CLI/scaffold/adopt threading of target + tailscale_path.
"""

from __future__ import annotations

import importlib.util
import os
import tempfile
from pathlib import Path

import pytest
from copier import run_copy
from typer.testing import CliRunner

from demo_tools._resources import STARTERS_DIR
from demo_tools._resources import TEMPLATE_DIR as TEMPLATE
from demo_tools.cli import init_app

runner = CliRunner()

LOCAL_VERBS = [
    "deploy", "stop", "start", "destroy", "logs",
    "ssh", "status", "open", "secret", "db-create",
]

# Words that would leak Fly vocabulary into local-target output (§4.2).
FLY_ISMS = ["fly ", "machines", "region", "billing", "postgres", "cert"]


def _render(stack: str = "fastapi", target: str = "local", **overrides) -> Path:
    tmp = Path(tempfile.mkdtemp())
    data = {
        "name": "tmp-demo",
        "stack": stack,
        "stateful": stack in {"fastapi", "nextjs-fastapi", "streamlit"},
        "internal_port": overrides.pop("internal_port", 8000),
        "domain_base": "demos.buildwithbos.com",
        "target": target,
    }
    data.update(overrides)
    run_copy(src_path=str(TEMPLATE), dst_path=str(tmp), data=data,
             defaults=True, unsafe=True, quiet=True)
    return tmp


# --- infra/local scripts -----------------------------------------------------

def test_local_renders_lib_and_all_verb_scripts():
    out = _render()
    local = out / "infra" / "local"
    assert (local / "_lib.sh").exists()
    for verb in LOCAL_VERBS:
        assert (local / f"{verb}.sh").exists(), f"missing {verb}.sh"


def test_local_lib_carries_host_path_and_port():
    lib = (_render() / "infra" / "local" / "_lib.sh").read_text()
    assert 'TS_HOST="bos-desktop.fish-grouper.ts.net"' in lib
    assert 'TS_PATH="/tmp-demo"' in lib
    assert 'INTERNAL_PORT="8000"' in lib
    # The reachable URL is composed from host + path.
    assert 'URL="https://${TS_HOST}${TS_PATH}"' in lib


def test_local_deploy_registers_tailscale_serve():
    deploy = (_render() / "infra" / "local" / "deploy.sh").read_text()
    assert "--set-path" in deploy
    assert "${TS_PATH}" in deploy
    assert "${INTERNAL_PORT}" in deploy
    assert "up -d --build" in deploy
    # Skips the admin-gated serve write when the path is already registered
    # (so everyday re-deploys need no UAC); elevates only on first registration.
    assert "already registered" in deploy
    assert "ts_serve_elevated" in deploy


def test_local_lib_defines_skip_and_elevation_helpers():
    lib = (_render() / "infra" / "local" / "_lib.sh").read_text()
    assert "serve_path_registered()" in lib
    assert "serve_path_conflict()" in lib
    assert "ts_serve_elevated()" in lib
    assert "RunAs" in lib  # elevation via Windows Start-Process


def test_local_destroy_unregisters_serve_and_keeps_data():
    destroy = (_render() / "infra" / "local" / "destroy.sh").read_text()
    assert "--set-path" in destroy
    assert "off" in destroy               # `serve --set-path <path> off`
    assert "ts_serve_elevated" in destroy  # deregister is also admin-gated
    assert "[y/N]" in destroy             # confirmation prompt
    assert "./data" in destroy            # data dir is KEPT


def test_local_db_create_is_friendly_na():
    db = (_render() / "infra" / "local" / "db-create.sh").read_text()
    assert "SQLite" in db
    assert "nothing to provision" in db


def test_local_scripts_have_no_fly_isms():
    for script in (_render() / "infra" / "local").glob("*.sh"):
        text = script.read_text().lower()
        for ism in FLY_ISMS:
            assert ism not in text, f"{script.name} leaks fly-ism {ism!r}"


# --- compose.local.yml overlay ----------------------------------------------

def test_local_compose_overlay_stateful_has_bind_mount():
    c = (_render("fastapi", internal_port=8000) / "compose.local.yml").read_text()
    assert "restart: unless-stopped" in c
    assert 'ROOT_PATH: "/tmp-demo"' in c
    assert "./data:/data" in c


def test_local_compose_overlay_non_stateful_has_no_bind_mount():
    c = (_render("nextjs", internal_port=3000, stateful=False) / "compose.local.yml").read_text()
    assert "restart: unless-stopped" in c
    assert "ROOT_PATH:" in c
    assert "./data:/data" not in c


# --- justfile dispatch -------------------------------------------------------

def test_justfile_target_default_is_local_when_target_local():
    just = (_render(target="local", stack="bare", internal_port=3000) / "justfile").read_text()
    assert 'TARGET := env_var_or_default("DEMO_TARGET", "local")' in just
    assert "infra/{{TARGET}}/deploy.sh" in just  # Just interpolation preserved
    assert "PLATFORM" not in just                # old dispatch var is gone


def test_justfile_target_default_is_fly_when_target_fly():
    just = (_render(target="fly", stack="bare", internal_port=3000) / "justfile").read_text()
    assert 'TARGET := env_var_or_default("DEMO_TARGET", "fly")' in just


# --- coexistence + backward-compat ------------------------------------------

def test_local_target_still_renders_fly_infra():
    out = _render(target="local")
    assert (out / "infra" / "fly" / "deploy.sh").exists()
    assert (out / "fly.toml").exists()


def test_fly_target_still_renders_local_infra():
    out = _render(target="fly")
    assert (out / "infra" / "local" / "deploy.sh").exists()
    assert (out / "infra" / "local" / "_lib.sh").exists()


def test_fly_toml_never_sets_root_path():
    """The Fly deploy path serves at root — no ROOT_PATH is injected there."""
    out = _render(target="fly", stack="fastapi", internal_port=8000)
    assert "ROOT_PATH" not in (out / "fly.toml").read_text()


def test_gitignore_ignores_data_dir():
    assert "data/" in (_render() / ".gitignore").read_text()


def test_fly_workflow_pins_demo_target_fly():
    wf = (_render(target="local") / ".github" / "workflows" / "fly-deploy.yml").read_text()
    assert "DEMO_TARGET: fly" in wf


def test_generated_readme_local_shows_tailnet_url():
    r = (_render(target="local") / "README.md").read_text()
    assert "bos-desktop.fish-grouper.ts.net/tmp-demo" in r
    assert "Deploy target:** local" in r


def test_generated_readme_fly_shows_fly_urls():
    r = (_render(target="fly", stack="nextjs", internal_port=3000) / "README.md").read_text()
    assert "tmp-demo.fly.dev" in r
    assert "tmp-demo.demos.buildwithbos.com" in r


# --- fastapi starter base-path awareness ------------------------------------

def test_fastapi_starter_reads_root_path_env():
    main = (STARTERS_DIR / "fastapi" / "main.py").read_text()
    assert 'root_path=os.getenv("ROOT_PATH", "")' in main


def _load_starter_app(root_path: str):
    """Import the shipped fastapi starter with ROOT_PATH set to `root_path`."""
    os.environ["ROOT_PATH"] = root_path
    try:
        mod_name = "starter_main_" + (root_path.strip("/").replace("/", "_") or "root")
        spec = importlib.util.spec_from_file_location(
            mod_name, STARTERS_DIR / "fastapi" / "main.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.app
    finally:
        os.environ.pop("ROOT_PATH", None)


def test_fastapi_root_path_routing_across_targets():
    """Empty ROOT_PATH serves at '/'; with ROOT_PATH="/<name>" the same route
    decorator still matches — both the realistic stripped-prefix request
    Tailscale actually sends ("/healthz") and a full-prefix request, because
    Starlette's get_route_path() only strips root_path from paths that carry
    it (see the design doc §5.4 correction, 2026-07-12)."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app_fly = _load_starter_app("")
    assert TestClient(app_fly).get("/healthz").status_code == 200

    app_local = _load_starter_app("/tmp-demo")
    # tailscale serve --set-path STRIPS the prefix, so the container really
    # only ever sees "/healthz" — routing must work with the bare path.
    assert TestClient(app_local).get("/healthz").status_code == 200
    # A full-prefix request also still routes correctly (belt and braces).
    assert TestClient(app_local).get("/tmp-demo/healthz").status_code == 200


def test_fastapi_starter_serves_static_via_route_not_mount():
    """The starter must serve /static via a route, not a StaticFiles Mount —
    a Mount only matches the full "/<name>/static/..." path and 404s once
    Tailscale strips the prefix (design doc §5.4 correction, 2026-07-12)."""
    main_src = (STARTERS_DIR / "fastapi" / "main.py").read_text()
    code_lines = [ln for ln in main_src.splitlines() if not ln.strip().startswith("#")]
    code_src = "\n".join(code_lines)
    assert "import StaticFiles" not in code_src
    assert "app.mount(" not in code_src

    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    app = _load_starter_app("/tmp-demo")
    static_dir = STARTERS_DIR / "fastapi" / "static"
    static_dir.mkdir(exist_ok=True)
    asset = static_dir / "app.css"
    asset.write_text("body{color:red}")
    try:
        client = TestClient(app)
        # Realistic stripped-prefix request (what Tailscale actually sends).
        resp = client.get("/static/app.css")
        assert resp.status_code == 200
        assert resp.text == "body{color:red}"
        # Path traversal outside STATIC_DIR must not be servable.
        assert client.get("/static/../main.py").status_code in (404, 400)
        # url_for still emits the correctly-prefixed URL for the browser.
        assert app.url_path_for("static", path="app.css") == "/static/app.css"
    finally:
        asset.unlink()
        static_dir.rmdir()


# --- scaffold / adopt / CLI threading ---------------------------------------

def test_scaffold_demo_local_writes_answers_and_justfile(tmp_path):
    from demo_tools.scaffold import scaffold_demo
    target = tmp_path / "loc"
    scaffold_demo("bare", "loc", target, deploy_target="local")
    just = (target / "justfile").read_text()
    assert 'env_var_or_default("DEMO_TARGET", "local")' in just
    answers = (target / ".demo-template-version").read_text()
    assert "target: local" in answers
    assert "tailscale_path: /loc" in answers
    assert "tailscale_host:" in answers


def test_scaffold_demo_tailscale_path_override(tmp_path):
    from demo_tools.scaffold import scaffold_demo
    target = tmp_path / "loc2"
    scaffold_demo("bare", "loc2", target, deploy_target="local", tailscale_path="/jobs")
    answers = (target / ".demo-template-version").read_text()
    assert "tailscale_path: /jobs" in answers
    lib = (target / "infra" / "local" / "_lib.sh").read_text()
    assert 'TS_PATH="/jobs"' in lib


def test_scaffold_demo_default_target_is_fly(tmp_path):
    from demo_tools.scaffold import scaffold_demo
    target = tmp_path / "flyloc"
    scaffold_demo("bare", "flyloc", target)  # no deploy_target kwarg
    answers = (target / ".demo-template-version").read_text()
    assert "target: fly" in answers


def test_adopt_overlay_local_target(tmp_path):
    from demo_tools.adopt import overlay_infra
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    overlay_infra(tmp_path, name="x", stack="bare", stateful=False,
                  internal_port=3000, deploy_target="local")
    answers = (tmp_path / ".demo-template-version").read_text()
    assert "target: local" in answers
    assert (tmp_path / "infra" / "local" / "deploy.sh").exists()


def test_scaffold_command_forwards_target_and_path(mocker):
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(
        init_app,
        ["scaffold", "fastapi", "job", "--target", "local", "--tailscale-path", "/jobs"],
    )
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("fastapi", "job", "demo", "local", "/jobs")


def test_adopt_command_forwards_target(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt", "--target", "local"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with(
        "demo", stack=None, yes=False, target="local", tailscale_path=None
    )


def test_local_service_profile_prints_ignored_notice(mocker, tmp_path, capsys):
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
    mocker.patch("demo_tools.scaffold.scaffold_demo")
    from demo_tools.cli import _run_scaffold
    _run_scaffold("bare", "n", "service", "local", None)
    assert "ignored for --target local" in capsys.readouterr().out


def test_local_demo_profile_prints_no_notice(mocker, tmp_path, capsys):
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
    mocker.patch("demo_tools.scaffold.scaffold_demo")
    from demo_tools.cli import _run_scaffold
    _run_scaffold("bare", "n", "demo", "local", None)
    assert "ignored" not in capsys.readouterr().out


def test_reflect_scaffold_exposes_target_options():
    from demo_tools._reflect import reflect_tools
    tool = {t["name"]: t for t in reflect_tools()}["demo_init.scaffold"]
    params = {p["name"]: p for p in tool["params"]}
    assert params["target"]["opt"] == "--target"
    assert params["tailscale_path"]["opt"] == "--tailscale-path"
