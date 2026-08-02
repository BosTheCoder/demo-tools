"""The CLI rejects impossible stack/target pairings before writing any files."""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from demo_tools.cli import init_app

runner = CliRunner()


@pytest.mark.parametrize("stack", ["fastapi", "streamlit", "nextjs-fastapi"])
def test_server_stacks_are_refused_for_pages(tmp_path, monkeypatch, stack):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(init_app, ["scaffold", stack, "demo-x", "--target", "pages"])
    assert result.exit_code != 0
    assert stack in result.output
    assert "--target fly" in result.output
    # Nothing may be written when the pairing is impossible.
    assert not (tmp_path / "demo-x").exists()


def test_nextjs_is_refused_for_pages_with_the_export_caveat(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(init_app, ["scaffold", "nextjs", "demo-x", "--target", "pages"])
    assert result.exit_code != 0
    assert "export" in result.output.lower()
    assert not (tmp_path / "demo-x").exists()


@pytest.mark.parametrize("target", ["fly", "local"])
def test_html_is_refused_for_container_targets(tmp_path, monkeypatch, target):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(init_app, ["scaffold", "html", "demo-x", "--target", target])
    assert result.exit_code != 0
    assert "Dockerfile" in result.output
    assert "--target pages" in result.output
    assert not (tmp_path / "demo-x").exists()


def test_unknown_stack_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(init_app, ["scaffold", "rails", "demo-x"])
    assert result.exit_code != 0
    assert "rails" in result.output


def test_unknown_target_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(init_app, ["scaffold", "vite", "demo-x", "--target", "heroku"])
    assert result.exit_code != 0
    assert "heroku" in result.output
    assert not (tmp_path / "demo-x").exists()


def test_help_lists_the_pages_target_and_both_static_stacks():
    result = runner.invoke(init_app, ["--help"])
    out = result.output
    assert "pages" in out
    assert "html" in out
    assert "vite" in out


def test_static_is_gone_as_a_stack_name():
    # The word still appears in prose ("static files"); what must be gone is the
    # stack, so assert on the registry rather than the help text.
    from demo_tools.cli import VALID_STACKS, _ADOPT_DEFAULTS
    from demo_tools.stacks import get_scaffolder

    assert "static" not in VALID_STACKS
    assert "static" not in _ADOPT_DEFAULTS
    assert "vite" in VALID_STACKS and "html" in VALID_STACKS
    with pytest.raises(ValueError):
        get_scaffolder("static")
