"""Refresh the template-managed files in an existing demo.

`copier update` was the original mechanism for `just sync` and it does not
work here. Against buildwithbos.com it printed "Updating to template version
0.0.0.post87.dev0+72c2ff3" and then changed nothing at all — no diff, no
touched files, `_commit` left on the old SHA. That is the failure mode of
running `update` on a project copier did not generate: most of these repos
were `demo init adopt`-ed, so the template owns a dozen files and the app owns
the other few hundred, and copier's three-way merge has nothing to anchor to.

So sync does the narrow thing every managed file already promises in its own
first line: re-render the template with the project's own answers, and
overwrite exactly the files that carry the `MANAGED BY demo-tools` marker.
Everything else is the app's — Dockerfile, fly.toml, compose.yml, justfile,
README — and is never touched, no matter what the template says about it.
"""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from copier import run_copy

from ._resources import TEMPLATE_DIR, template_commit

ANSWERS_FILE = ".demo-template-version"

# The line every generated infra script opens with. A file is the template's to
# overwrite if and only if it says so itself.
MARKER = "MANAGED BY demo-tools"


@dataclass(frozen=True)
class Change:
    verb: str  # "create" | "update" | "orphan"
    path: str


def sync_demo(project: Path, *, dry_run: bool = False) -> list[Change]:
    """Bring `project`'s template-managed files up to date with this template.

    Returns the changes made (or that would be made, under `dry_run`).
    """
    answers_path = project / ANSWERS_FILE
    if not answers_path.exists():
        raise FileNotFoundError(
            f"{answers_path} not found — is this a demo-tools project? "
            "Run `demo-init adopt` first."
        )

    answers = yaml.safe_load(answers_path.read_text()) or {}
    data = {k: v for k, v in answers.items() if not k.startswith("_")}

    tmp = Path(tempfile.mkdtemp(prefix="demo-tools-sync-"))
    try:
        run_copy(
            src_path=str(TEMPLATE_DIR),
            dst_path=str(tmp),
            data=data,
            defaults=True,
            unsafe=True,
            quiet=True,
            overwrite=True,
        )
        changes = _copy_managed(tmp, project, dry_run=dry_run)
        if not dry_run:
            _write_answers(project, answers)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return changes


def _copy_managed(rendered_root: Path, project: Path, *, dry_run: bool) -> list[Change]:
    changes: list[Change] = []
    managed: set[Path] = set()

    for rendered in sorted(rendered_root.rglob("*")):
        if not rendered.is_file():
            continue
        try:
            text = rendered.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        if MARKER not in text:
            continue

        rel = rendered.relative_to(rendered_root)
        managed.add(rel)
        dest = project / rel

        if dest.exists() and dest.read_text() == text:
            continue

        changes.append(Change("update" if dest.exists() else "create", str(rel)))
        if dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
        shutil.copymode(rendered, dest)

    changes.extend(_orphans(project, managed))
    return changes


def _orphans(project: Path, managed: set[Path]) -> list[Change]:
    """Managed files in the project that the template no longer renders.

    Reported, never deleted. A stack that switched target leaves a whole infra
    directory behind, and quietly removing files someone might still be reading
    is a worse failure than telling them the files are dead.
    """
    orphans: list[Change] = []
    for existing in sorted(project.rglob("*")):
        if not existing.is_file():
            continue
        rel = existing.relative_to(project)
        if rel in managed:
            continue
        try:
            if MARKER not in existing.read_text():
                continue
        except (UnicodeDecodeError, OSError):
            continue
        orphans.append(Change("orphan", str(rel)))
    return orphans


def _write_answers(project: Path, previous: dict) -> None:
    """Write back the answers file with the template's newer questions filled in.

    Questions added since the project was created (`hostnames`, `host_port`)
    already get their defaults during the render — the demo syncs fine without
    this. Writing them down is what makes them *discoverable*: the next person
    who wants a different hostname finds the key sitting in the file instead of
    having to know it exists.
    """
    merged = dict(previous)
    for key, value in _template_defaults(merged).items():
        merged.setdefault(key, value)
    merged["_commit"] = template_commit()
    (project / ANSWERS_FILE).write_text(yaml.safe_dump(merged, sort_keys=True))


def _template_defaults(answers: dict) -> dict:
    """Default for every question the template asks, rendered against `answers`.

    Copier only writes an answers file when the source is a VCS checkout, and
    the bundled template is a plain directory — so the render can't hand these
    back and they're recomputed here. Questions whose `when` is false for this
    project (the Tailscale ones on a Fly app) are skipped.
    """
    from jinja2 import Environment

    spec = yaml.safe_load((TEMPLATE_DIR / "copier.yml").read_text()) or {}
    env = Environment(keep_trailing_newline=True)
    resolved: dict = {}

    for name, question in spec.items():
        if name.startswith("_") or not isinstance(question, dict):
            continue
        if "default" not in question:
            continue
        context = {**resolved, **answers}
        when = question.get("when")
        if isinstance(when, str) and not yaml.safe_load(
            env.from_string(when).render(context) or "false"
        ):
            continue

        default = question["default"]
        if isinstance(default, str):
            rendered = env.from_string(default).render(context)
            value = yaml.safe_load(rendered) if question.get("type") in {
                "yaml", "json", "int", "float", "bool"
            } else rendered
        else:
            value = default
        resolved[name] = value

    return resolved
