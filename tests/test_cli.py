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


def test_init_positional_shorthand_routes_to_scaffold(mocker):
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["nextjs", "my-demo"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-demo")
