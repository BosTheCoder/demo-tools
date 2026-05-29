import pytest


def _ok(mocker):
    return mocker.Mock(returncode=0, stdout="ok", stderr="")


def test_run_tool_builds_scaffold_argv(mocker):
    from demo_tools import mcp_server

    run = mocker.patch("demo_tools.mcp_server.subprocess.run", return_value=_ok(mocker))
    mcp_server.run_tool("demo_init.scaffold", {"stack": "nextjs", "name": "foo"})

    argv = run.call_args.args[0]
    assert argv[1:5] == ["-m", "demo_tools", "init", "scaffold"]
    assert argv[5:7] == ["nextjs", "foo"]


def test_run_tool_prune_defaults_to_dry_run(mocker):
    from demo_tools import mcp_server

    run = mocker.patch("demo_tools.mcp_server.subprocess.run", return_value=_ok(mocker))
    mcp_server.run_tool("demo.prune", {})

    argv = run.call_args.args[0]
    assert "--dry-run" in argv
    assert "--yes" not in argv


def test_run_tool_prune_destroys_only_when_explicit(mocker):
    from demo_tools import mcp_server

    run = mocker.patch("demo_tools.mcp_server.subprocess.run", return_value=_ok(mocker))
    mcp_server.run_tool("demo.prune", {"dry_run": False, "yes": True})

    argv = run.call_args.args[0]
    assert "--dry-run" not in argv
    assert "--yes" in argv


def test_run_tool_unknown_raises(mocker):
    from demo_tools import mcp_server

    with pytest.raises(ValueError):
        mcp_server.run_tool("demo.nope", {})


def test_run_tool_nonzero_exit_raises(mocker):
    from demo_tools import mcp_server

    mocker.patch(
        "demo_tools.mcp_server.subprocess.run",
        return_value=mocker.Mock(returncode=1, stdout="", stderr="boom"),
    )
    with pytest.raises(RuntimeError, match="boom"):
        mcp_server.run_tool("demo.list", {})
