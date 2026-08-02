import subprocess as sp

from typer.testing import CliRunner

from demo_tools.cli import init_app, demo_app

runner = CliRunner()

# Deployed fly.toml shapes, as `fly config show` returns them.
_DEMO_CONFIG = (
    '{"http_service":{"auto_stop_machines":"stop","min_machines_running":0}}'
)
_SERVICE_CONFIG = (
    '{"http_service":{"auto_stop_machines":false,"min_machines_running":1}}'
)


def test_init_app_help_lists_subcommands():
    result = runner.invoke(init_app, ["--help"])
    assert result.exit_code == 0
    assert "adopt" in result.stdout


def test_demo_app_help_lists_list_and_prune():
    result = runner.invoke(demo_app, ["--help"])
    assert result.exit_code == 0
    assert "list" in result.stdout
    assert "prune" in result.stdout


def test_init_bare_stack_name_is_not_a_command(mocker):
    """A bare stack name is not a subcommand; scaffold requires the explicit word."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["nextjs", "my-demo"])
    assert result.exit_code != 0
    spy.assert_not_called()


def test_init_adopt_subcommand_does_not_call_scaffold(mocker):
    """Invoking the adopt subcommand must not be intercepted as shorthand."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    adopt_spy = mocker.patch("demo_tools.cli._run_adopt")
    runner.invoke(init_app, ["adopt"])
    spy.assert_not_called()
    adopt_spy.assert_called_once_with(
        "demo", stack=None, yes=False, target="fly", tailscale_path=None
    )


def test_init_explicit_scaffold_form_still_works(mocker):
    """The explicit form `demo-init scaffold <stack> <name>` must still route to _run_scaffold."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-demo"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-demo", "demo", "fly", None)


def test_scaffold_command_forwards_profile_default(mocker):
    """When --profile is omitted, _run_scaffold gets profile='demo'."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-app"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-app", "demo", "fly", None)


def test_scaffold_command_forwards_profile_service(mocker):
    """--profile service is forwarded to _run_scaffold."""
    spy = mocker.patch("demo_tools.cli._run_scaffold")
    result = runner.invoke(init_app, ["scaffold", "nextjs", "my-app", "--profile", "service"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("nextjs", "my-app", "service", "fly", None)


def test_adopt_command_forwards_profile_default(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with(
        "demo", stack=None, yes=False, target="fly", tailscale_path=None
    )


def test_adopt_command_forwards_profile_service(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt", "--profile", "service"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with(
        "service", stack=None, yes=False, target="fly", tailscale_path=None
    )


def test_adopt_stack_option_skips_detection(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt", "--stack", "fastapi", "--yes"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with(
        "demo", stack="fastapi", yes=True, target="fly", tailscale_path=None
    )


def test_run_adopt_with_stack_skips_detection(tmp_path, mocker):
    """_run_adopt called directly: when stack is given, detect_stack is never called."""
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
    detect = mocker.patch("demo_tools.adopt.detect_stack")
    overlay = mocker.patch("demo_tools.adopt.overlay_infra")

    from demo_tools.cli import _run_adopt
    _run_adopt("demo", stack="fastapi", yes=True)

    detect.assert_not_called()
    assert overlay.call_args.kwargs["stack"] == "fastapi"


def test_run_adopt_unknown_stack_raises_exit(tmp_path, mocker):
    """_run_adopt called directly: an unknown stack raises typer.Exit and never calls overlay_infra."""
    import pytest
    import typer
    (tmp_path / "Dockerfile").write_text("FROM alpine\n")
    mocker.patch("pathlib.Path.cwd", return_value=tmp_path)
    overlay = mocker.patch("demo_tools.adopt.overlay_infra")

    from demo_tools.cli import _run_adopt
    with pytest.raises(typer.Exit):
        _run_adopt("demo", stack="bogus", yes=True)

    overlay.assert_not_called()


def test_prune_dry_run_lists_without_destroying(mocker):
    mocker.patch("demo_tools.fleet.list_apps", return_value=[{"name": "old"}])
    mocker.patch(
        "demo_tools.fleet.list_demos_only",
        return_value=[{"name": "old", "status": "stopped", "kind": "nextjs",
                       "last_deployed": "2020-01-01T00:00:00Z"}],
    )

    def fake_run(argv, *a, **k):
        if argv[:3] == ["fly", "config", "show"]:
            return mocker.Mock(returncode=0, stdout=_DEMO_CONFIG)
        return mocker.Mock(returncode=0, stdout="", stderr="")

    run = mocker.patch("subprocess.run", side_effect=fake_run)

    result = runner.invoke(demo_app, ["prune", "--dry-run"])

    assert result.exit_code == 0, result.stdout
    assert "old" in result.stdout
    destroy = [
        c for c in run.call_args_list
        if c.args and c.args[0][:3] == ["fly", "apps", "destroy"]
    ]
    assert destroy == []


def test_prune_skips_app_with_no_release_date_loudly(mocker):
    mocker.patch("demo_tools.fleet.list_apps", return_value=[{"name": "never"}])
    mocker.patch(
        "demo_tools.fleet.list_demos_only",
        return_value=[{"name": "never", "status": "pending", "last_deployed": None}],
    )
    run = mocker.patch("subprocess.run",
                       return_value=mocker.Mock(returncode=0, stdout="", stderr=""))

    result = runner.invoke(demo_app, ["prune", "--older-than", "1d", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "never" in result.stdout
    assert "skipped" in result.stdout
    destroy = [
        c for c in run.call_args_list
        if c.args and c.args[0][:3] == ["fly", "apps", "destroy"]
    ]
    assert destroy == []


def test_prune_never_destroys_an_always_on_service(mocker):
    """The buildwithbos case: a production app must survive `prune --yes`.

    The service/demo profile is not recorded on Fly, so prune infers it from the
    deployed autostop config. Without this guard, `--yes` skips the per-app
    prompt and takes the live site with it.
    """
    mocker.patch("demo_tools.fleet.list_apps", return_value=[{"name": "buildwithbos"}])
    mocker.patch(
        "demo_tools.fleet.list_demos_only",
        return_value=[{"name": "buildwithbos", "status": "deployed", "kind": "nextjs",
                       "last_deployed": "2020-01-01T00:00:00Z"}],
    )

    def fake_run(argv, *a, **k):
        if argv[:3] == ["fly", "config", "show"]:
            return mocker.Mock(returncode=0, stdout=_SERVICE_CONFIG)
        return mocker.Mock(returncode=0, stdout="", stderr="")

    run = mocker.patch("subprocess.run", side_effect=fake_run)

    result = runner.invoke(demo_app, ["prune", "--older-than", "1d", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "Protected" in result.stdout
    assert "buildwithbos" in result.stdout
    destroy = [
        c for c in run.call_args_list
        if c.args and c.args[0][:3] == ["fly", "apps", "destroy"]
    ]
    assert destroy == []


def test_prune_finds_nextjs_fastapi_pair_via_the_web_app(mocker):
    """<base> is synthetic. The config lookup behind the guard must target
    <base>-web, or it 404s, the app reads as unclassifiable, and the pair is
    protected forever and can never be pruned."""
    mocker.patch("demo_tools.fleet.list_apps", return_value=[{"name": "chord-web"}])
    mocker.patch(
        "demo_tools.fleet.list_demos_only",
        return_value=[{"name": "chord", "status": "deployed", "kind": "nextjs-fastapi",
                       "last_deployed": "2020-01-01T00:00:00Z"}],
    )

    def fake_run(argv, *a, **k):
        if argv[:3] == ["fly", "config", "show"]:
            # Only the real -web app resolves; the synthetic base 404s.
            if argv[-1] != "chord-web":
                raise sp.CalledProcessError(1, argv)
            return mocker.Mock(returncode=0, stdout=_DEMO_CONFIG)
        return mocker.Mock(returncode=0, stdout="", stderr="")

    run = mocker.patch("subprocess.run", side_effect=fake_run)

    result = runner.invoke(demo_app, ["prune", "--older-than", "1d", "--yes"])

    assert result.exit_code == 0, result.stdout
    assert "Protected" not in result.stdout
    destroyed = [
        c.args[0][-1] for c in run.call_args_list
        if c.args and c.args[0][:3] == ["fly", "apps", "destroy"]
    ]
    assert destroyed == ["chord-web", "chord-api"]
