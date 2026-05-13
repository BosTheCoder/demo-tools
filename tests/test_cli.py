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
    spy.assert_called_once_with("nextjs", "my-demo", "demo")


def test_init_unknown_first_arg_does_not_call_scaffold(mocker):
    """An unknown stack name must NOT be intercepted as positional shorthand."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["unknown-stack", "name"])
    # Should fall through to Click's "no such command" path
    assert result.exit_code != 0
    spy.assert_not_called()


def test_init_adopt_subcommand_does_not_call_scaffold(mocker):
    """Invoking the adopt subcommand must not be intercepted as shorthand."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    adopt_spy = mocker.patch("demo_tools.cli._run_adopt")
    runner.invoke(init_app, ["adopt"])
    spy.assert_not_called()
    adopt_spy.assert_called_once_with("demo")


def test_init_explicit_scaffold_form_still_works(mocker):
    """The explicit form `demo-init scaffold <stack> <name>` must still route to _run_scaffold."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-demo"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-demo", "demo")


def test_scaffold_command_forwards_profile_default(mocker):
    """When --profile is omitted, _run_scaffold gets profile='demo'."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-app"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-app", "demo")


def test_scaffold_command_forwards_profile_service(mocker):
    """--profile service is forwarded to _run_scaffold."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-app", "--profile", "service"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-app", "service")


def test_positional_shorthand_supports_profile_flag(mocker):
    """`demo-init nextjs my-app --profile service` (shorthand) forwards profile."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["nextjs", "my-app", "--profile", "service"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-app", "service")


def test_adopt_command_forwards_profile_default(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("demo")


def test_adopt_command_forwards_profile_service(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt", "--profile", "service"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("service")
