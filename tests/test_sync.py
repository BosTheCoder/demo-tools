"""Tests for `just sync` / `copier update` flow.

We don't actually clone GitHub during tests — instead we verify:
1. The `.demo-template-version` answers file written by scaffold_demo has the
   right shape (GitHub URL src_path, subdirectory, commit ref).
2. `copier update` works end-to-end when given a properly git-tracked local
   source — proving the mechanism is sound even though our default ships the
   GitHub URL form.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml
from copier import run_update

from demo_tools._resources import TEMPLATE_DIR, TEMPLATE_GIT_URL, TEMPLATE_SUBDIR
from demo_tools.scaffold import scaffold_demo
from demo_tools.sync import sync_demo


def test_scaffolded_demo_answers_file_has_github_url(tmp_path):
    target = tmp_path / "demo"
    scaffold_demo("bare", "demo", target)
    answers = yaml.safe_load((target / ".demo-template-version").read_text())
    assert answers["_src_path"] == TEMPLATE_GIT_URL
    assert answers["_subdirectory"] == TEMPLATE_SUBDIR
    assert "_commit" in answers
    assert answers["stack"] == "bare"


def test_copier_update_works_against_local_git_template(tmp_path):
    """Mechanism check: with a real git source, `run_update` succeeds.

    We init a git repo at a copy of our template, scaffold a demo against it,
    add a new file to the template + commit, then run `copier update` and
    verify the new file appears in the demo. This proves the update flow is
    valid; production demos use TEMPLATE_GIT_URL which works the same way
    once the repo is published.
    """
    # 1. Make a git-tracked copy of the template.
    template_repo = tmp_path / "template-repo"
    shutil.copytree(TEMPLATE_DIR, template_repo)
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=template_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=template_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@x", "-c", "user.name=t",
         "commit", "-q", "-m", "initial"],
        cwd=template_repo, check=True,
    )

    # 2. Scaffold a demo and rewrite its answers file to point at the local
    #    git repo (simulating what the GitHub URL would resolve to in prod).
    target = tmp_path / "demo"
    scaffold_demo("bare", "demo", target)
    answers = yaml.safe_load((target / ".demo-template-version").read_text())
    answers["_src_path"] = str(template_repo)
    answers["_subdirectory"] = "."
    commit_sha = subprocess.run(
        ["git", "-C", str(template_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    answers["_commit"] = commit_sha
    (target / ".demo-template-version").write_text(yaml.safe_dump(answers))
    # Commit the answers-file rewrite — Copier requires a clean dest repo.
    subprocess.run(
        ["git", "-c", "user.email=t@x", "-c", "user.name=t",
         "-C", str(target), "commit", "-q", "-am", "rewire src_path"],
        check=True,
    )

    # 3. Add a new file to the template and commit.
    (template_repo / "NEWFILE.txt.jinja").write_text("hello {{ name }}")
    subprocess.run(["git", "add", "."], cwd=template_repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@x", "-c", "user.name=t",
         "commit", "-q", "-m", "add new file"],
        cwd=template_repo, check=True,
    )

    # 4. Run copier update and verify the new file landed.
    run_update(
        dst_path=str(target),
        answers_file=".demo-template-version",
        defaults=True, unsafe=True, quiet=True, overwrite=True,
    )
    assert (target / "NEWFILE.txt").exists()
    assert "hello demo" in (target / "NEWFILE.txt").read_text()


# --- `demo sync`: refresh the files stamped MANAGED BY demo-tools -----------
#
# The test above only proves copier can ADD a file. The case that actually
# matters — a managed file whose contents changed — is what silently no-opped
# against buildwithbos.com, so it gets its own coverage here.


def _demo(tmp_path: Path) -> Path:
    target = tmp_path / "demo"
    scaffold_demo("bare", "demo", target)
    return target


def test_sync_rewrites_a_stale_managed_file(tmp_path):
    target = _demo(tmp_path)
    deploy = target / "infra" / "fly" / "deploy.sh"
    deploy.write_text("# MANAGED BY demo-tools — DO NOT EDIT.\necho stale\n")

    changes = sync_demo(target)

    assert "echo stale" not in deploy.read_text()
    assert "fly deploy" in deploy.read_text()
    assert any(c.verb == "update" and c.path.endswith("deploy.sh") for c in changes)


def test_sync_does_not_touch_files_the_app_owns(tmp_path):
    """The template renders a Dockerfile, a README and a justfile. None of them
    carry the marker, so an app that has edited them keeps its edits."""
    target = _demo(tmp_path)
    for name, body in [
        ("Dockerfile", "FROM node:22\n# hand-written, not the bare placeholder\n"),
        ("README.md", "# My actual project\n"),
        ("fly.toml", 'app = "demo"\n# tuned by hand\n'),
    ]:
        (target / name).write_text(body)

    sync_demo(target)

    assert "hand-written" in (target / "Dockerfile").read_text()
    assert (target / "README.md").read_text() == "# My actual project\n"
    assert "tuned by hand" in (target / "fly.toml").read_text()


def test_sync_is_a_noop_on_an_untouched_demo(tmp_path):
    target = _demo(tmp_path)
    assert [c for c in sync_demo(target) if c.verb != "orphan"] == []


def test_sync_dry_run_writes_nothing(tmp_path):
    target = _demo(tmp_path)
    deploy = target / "infra" / "fly" / "deploy.sh"
    deploy.write_text("# MANAGED BY demo-tools — DO NOT EDIT.\necho stale\n")

    changes = sync_demo(target, dry_run=True)

    assert any(c.verb == "update" for c in changes)
    assert "echo stale" in deploy.read_text()


def test_sync_backfills_answers_added_since_the_demo_was_made(tmp_path):
    """A demo scaffolded before `hostnames` existed must still sync, and come
    out the other side with the key written down so it can be changed."""
    target = _demo(tmp_path)
    answers_path = target / ".demo-template-version"
    answers = yaml.safe_load(answers_path.read_text())
    del answers["hostnames"]
    answers["_commit"] = "stale-sha"
    answers_path.write_text(yaml.safe_dump(answers))

    sync_demo(target)

    updated = yaml.safe_load(answers_path.read_text())
    assert updated["hostnames"] == ["demo.demos.buildwithbos.com"]
    assert updated["_commit"] != "stale-sha"
    assert 'HOSTNAMES=("demo.demos.buildwithbos.com")' in (
        target / "infra" / "fly" / "deploy.sh"
    ).read_text()


def test_sync_honours_an_explicit_hostnames_answer(tmp_path):
    """The buildwithbos.com case end to end: declare the real domains, sync,
    and the demo subdomain the app never wanted is gone."""
    target = _demo(tmp_path)
    answers_path = target / ".demo-template-version"
    answers = yaml.safe_load(answers_path.read_text())
    answers["hostnames"] = ["example.com", "www.example.com"]
    answers_path.write_text(yaml.safe_dump(answers))

    sync_demo(target)

    deploy = (target / "infra" / "fly" / "deploy.sh").read_text()
    assert 'HOSTNAMES=("example.com" "www.example.com")' in deploy
    assert "demo.demos.buildwithbos.com" not in deploy


def test_sync_reports_orphans_without_deleting_them(tmp_path):
    target = _demo(tmp_path)
    stray = target / "infra" / "fly" / "gone.sh"
    stray.write_text("# MANAGED BY demo-tools — DO NOT EDIT.\n")

    changes = sync_demo(target)

    assert any(c.verb == "orphan" and c.path.endswith("gone.sh") for c in changes)
    assert stray.exists(), "orphans are reported, never deleted"


def test_sync_without_an_answers_file_is_an_error(tmp_path):
    (tmp_path / "not-a-demo").mkdir()
    with pytest.raises(FileNotFoundError):
        sync_demo(tmp_path / "not-a-demo")
