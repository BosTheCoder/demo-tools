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

import yaml
from copier import run_update

from demo_tools._resources import TEMPLATE_DIR, TEMPLATE_GIT_URL, TEMPLATE_SUBDIR
from demo_tools.scaffold import scaffold_demo


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
