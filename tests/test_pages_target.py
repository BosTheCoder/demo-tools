"""The GitHub Pages target: what renders, what refuses, and how it publishes."""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest
from copier import run_copy

from demo_tools._resources import TEMPLATE_DIR as TEMPLATE
from demo_tools.scaffold import _target_flags

VERBS = [
    "deploy", "status", "logs", "open", "destroy",
    "stop", "start", "ssh", "db-create", "secret",
]


def _render(stack: str, target: str = "pages", **overrides) -> Path:
    tmp = Path(tempfile.mkdtemp())
    data = {
        "name": "tmp-demo",
        "stack": stack,
        "stateful": False,
        "internal_port": overrides.get("internal_port", 8000),
        "domain_base": "demos.buildwithbos.com",
        "target": target,
        **_target_flags(stack),
    }
    data.update(overrides)
    run_copy(src_path=str(TEMPLATE), dst_path=str(tmp), data=data,
             defaults=True, unsafe=True, quiet=True)
    return tmp


def _run(script: Path, *args: str):
    return subprocess.run(
        ["bash", str(script), *args],
        capture_output=True, text=True, cwd=script.parent.parent.parent,
    )


# --- what renders ------------------------------------------------------------

@pytest.mark.parametrize("stack", ["html", "vite", "bare"])
def test_pages_infra_renders_for_static_capable_stacks(stack):
    out = _render(stack)
    for verb in VERBS:
        assert (out / "infra" / "pages" / f"{verb}.sh").is_file(), verb


@pytest.mark.parametrize("stack", ["html", "vite", "bare"])
def test_every_pages_script_is_valid_bash(stack):
    out = _render(stack)
    for verb in VERBS:
        script = out / "infra" / "pages" / f"{verb}.sh"
        r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
        assert r.returncode == 0, f"{verb}: {r.stderr}"


@pytest.mark.parametrize("stack", ["fastapi", "streamlit", "nextjs-fastapi", "nextjs"])
def test_server_backed_stacks_get_no_pages_infra(stack):
    # A directory of scripts that can never run reads as a supported path.
    out = _render(stack, target="fly")
    assert not (out / "infra" / "pages").exists()


def test_html_ships_no_container_infra():
    out = _render("html")
    for path in ("Dockerfile", "compose.yml", "compose.local.yml", "fly.toml",
                 ".dockerignore", "infra/fly", "infra/local", ".github"):
        assert not (out / path).exists(), path


def test_vite_keeps_every_target_it_can_use():
    # vite runs in a container too, so switching target stays a flip.
    out = _render("vite", internal_port=80)
    for path in ("infra/fly", "infra/local", "infra/pages", "Dockerfile"):
        assert (out / path).exists(), path


# --- how it publishes --------------------------------------------------------

def test_html_publishes_by_serving_the_repo_root():
    out = _render("html")
    lib = (out / "infra" / "pages" / "_lib.sh").read_text()
    assert 'PUBLISH_MODE="root"' in lib


def test_vite_publishes_the_build_output_to_a_branch():
    out = _render("vite", internal_port=80)
    lib = (out / "infra" / "pages" / "_lib.sh").read_text()
    assert 'PUBLISH_MODE="branch"' in lib


def test_deploy_handles_both_publish_modes():
    out = _render("vite", internal_port=80)
    deploy = (out / "infra" / "pages" / "deploy.sh").read_text()
    assert 'PUBLISH_MODE" == "root"' in deploy
    assert "npm run build" in deploy
    # The branch name is defined once in _lib.sh, not repeated in each verb.
    assert "$PAGES_BRANCH" in deploy
    assert 'PAGES_BRANCH="gh-pages"' in (out / "infra" / "pages" / "_lib.sh").read_text()


def test_deploy_refuses_a_dirty_tree():
    # Pages publishes what is committed; deploying dirty would ship stale files.
    deploy = (_render("html") / "infra" / "pages" / "deploy.sh").read_text()
    assert "git status --porcelain" in deploy


# --- the verbs that refuse ---------------------------------------------------

def test_secret_refuses_and_writes_nothing():
    out = _render("html")
    r = _run(out / "infra" / "pages" / "secret.sh", "API_KEY=hunter2")
    assert r.returncode != 0
    assert not (out / ".env").exists(), "a refused secret must not leave a .env behind"


def test_secret_explains_public_config_versus_real_credentials():
    out = _render("html")
    r = _run(out / "infra" / "pages" / "secret.sh", "API_KEY=hunter2")
    msg = r.stderr
    assert "API_KEY" in msg
    assert "public" in msg.lower() and "credential" in msg.lower()
    assert "DEMO_TARGET=fly" in msg


def test_secret_never_echoes_the_value():
    # The message quotes KEY=VALUE for the fly command, but must not print the
    # bare secret anywhere else.
    out = _render("html")
    r = _run(out / "infra" / "pages" / "secret.sh", "API_KEY=hunter2")
    assert r.stdout == ""


@pytest.mark.parametrize("verb", ["ssh", "db-create"])
def test_verbs_with_no_analogue_fail_loudly(verb):
    out = _render("html")
    r = _run(out / "infra" / "pages" / f"{verb}.sh")
    assert r.returncode != 0
    assert "fly" in r.stderr


@pytest.mark.parametrize("verb", ["stop", "start"])
def test_always_on_verbs_succeed_with_a_note(verb):
    # Nothing to stop is not an error — it is the reason to pick this target.
    out = _render("html")
    r = _run(out / "infra" / "pages" / f"{verb}.sh")
    assert r.returncode == 0
    assert "GitHub Pages" in r.stdout


# --- justfile ----------------------------------------------------------------

def test_html_dev_serves_files_without_docker():
    just = (_render("html") / "justfile").read_text()
    assert "http.server" in just
    assert "docker compose up" not in just


def test_dockerised_stacks_keep_the_compose_dev_loop():
    just = (_render("vite", internal_port=80) / "justfile").read_text()
    assert "docker compose up" in just
    assert "http.server" not in just


def test_justfile_dispatches_every_verb_to_the_target():
    just = (_render("html") / "justfile").read_text()
    for verb in ("deploy", "stop", "start", "destroy", "logs", "ssh", "status", "open"):
        assert f"infra/{{{{TARGET}}}}/{verb}.sh" in just, verb


# --- .nojekyll and DNS, added after cclink deployed without either ------------

@pytest.mark.parametrize("stack", ["html", "vite", "bare"])
def test_dns_script_renders_and_is_managed(stack):
    """Managed, because that is the only way `just sync` reaches an existing
    demo. A helper the template renders but does not mark is a helper nobody
    already deployed will ever receive."""
    script = _render(stack) / "infra" / "pages" / "cloudflare_dns.sh"
    assert script.is_file()
    assert "MANAGED BY demo-tools" in script.read_text()


def test_deploy_applies_dns_rather_than_only_printing_it():
    deploy = (_render("html") / "infra" / "pages" / "deploy.sh").read_text()
    assert "cloudflare_dns.sh" in deploy


def test_dns_refuses_the_zone_apex():
    """A CNAME cannot sit at the apex beside SOA/NS, and Cloudflare's flattening
    would hand Pages a host it has no certificate for."""
    script = _render("html") / "infra" / "pages" / "cloudflare_dns.sh"
    r = subprocess.run(["bash", str(script), "example.com", "user.github.io"],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode == 0
    assert "apex" in r.stdout.lower()
    assert "185.199" in r.stdout


def test_dns_without_a_token_prints_the_record_and_succeeds():
    """A missing token must not fail the deploy — it degrades to the manual
    instruction the target shipped with before this existed."""
    script = _render("html") / "infra" / "pages" / "cloudflare_dns.sh"
    r = subprocess.run(["bash", str(script), "cc.example.com", "user.github.io"],
                       capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"})
    assert r.returncode == 0
    assert "CNAME cc -> user.github.io" in r.stdout
    assert "grey cloud" in r.stdout


def test_root_publish_commits_a_nojekyll():
    """Without it GitHub runs the repo through Jekyll, which hides _-prefixed
    files. The branch path writes one into its build output; the root path has
    to commit one, because there the repo is the artifact."""
    deploy = (_render("html") / "infra" / "pages" / "deploy.sh").read_text()
    root_half = deploy.split('PUBLISH_MODE" == "root"')[1].split("else")[0]
    assert ".nojekyll" in root_half
    assert "git commit" in root_half
