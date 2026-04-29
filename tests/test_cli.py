from typer.testing import CliRunner

from demo_tools.cli import init_app, demo_app

runner = CliRunner()


def test_init_app_help_lists_subcommands():
    result = runner.invoke(init_app, ["--help"])
    assert result.exit_code == 0
    assert "adopt" in result.stdout


def test_demo_app_help_lists_list_and_prune():
    result = runner.invoke(demo_app, ["--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "prune" in result.stdout
