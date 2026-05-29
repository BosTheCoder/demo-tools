# demo-tools MCP server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose every `demo-tools` CLI command as an MCP tool automatically, so adding a new Typer command makes a matching tool appear with no MCP-layer code change.

**Architecture:** Ports-and-adapters. The core (`scaffold.py`, `adopt.py`, `fleet.py`) is untouched. `cli.py` stays the human adapter. A new reflection helper (`_reflect.py`) reads the existing Typer apps into tool specs; a new MCP adapter (`mcp_server.py`) serves them over stdio and executes each by shelling out to `sys.executable -m demo_tools …` (a new `__main__.py` router), so there is no dependency on console scripts being on `PATH`.

**Tech Stack:** Python 3.12+, Typer/Click, the MCP Python SDK (`mcp`), pytest + pytest-mock.

---

## Spec

Design doc: `docs/superpowers/specs/2026-05-30-mcp-server-design.md`.

## File structure

- Modify `src/demo_tools/cli.py` — add `--dry-run` to `prune`; add `--stack`/`--yes` to `adopt` (+ thread into `_run_adopt`).
- Create `src/demo_tools/__main__.py` — `python -m demo_tools <init|demo> …` router.
- Create `src/demo_tools/_reflect.py` — `reflect_tools()` and `build_argv()`.
- Create `src/demo_tools/mcp_server.py` — MCP `Server` with `list_tools`/`call_tool`, `run_tool()` helper, `main()`.
- Modify `pyproject.toml` — `demo-mcp` script + `[project.optional-dependencies] mcp`.
- Modify `README.md` — install + registration docs.
- Tests: `tests/test_cli.py` (update + extend), `tests/test_main_dispatch.py`, `tests/test_reflect.py`, `tests/test_mcp_server.py`.

**Confirmation model note:** Because we reflect the CLI, the prune tool's confirmation is expressed via the reflected `dry_run`/`yes` flags (not a synthetic `confirm` field). `mcp_server.run_tool` injects `--dry-run` for destructive tools unless the caller explicitly sets `dry_run`, so destruction requires an explicit `dry_run=false` + `yes=true`. This realizes the spec's "dry-run by default, destruction is deliberate" intent while keeping reflection generic.

---

### Task 1: `prune` gains `--dry-run`

**Files:**
- Modify: `src/demo_tools/cli.py` (the `prune` command, near end of file)
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_cli.py`:

```python
def test_prune_dry_run_lists_without_destroying(mocker):
    mocker.patch("demo_tools.fleet.list_apps", return_value=[{"name": "old"}])
    mocker.patch(
        "demo_tools.fleet.list_demos_only",
        return_value=[{"name": "old", "status": "stopped", "kind": "nextjs"}],
    )

    def fake_run(argv, *a, **k):
        if argv[:2] == ["fly", "status"]:
            return mocker.Mock(
                returncode=0,
                stdout='{"App":{"CreatedAt":"2020-01-01T00:00:00Z"}}',
            )
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py::test_prune_dry_run_lists_without_destroying -v`
Expected: FAIL — `prune` has no `--dry-run` option (Click usage error, non-zero exit).

- [ ] **Step 3: Add the option and early return**

In `src/demo_tools/cli.py`, change the `prune` signature to add `dry_run`:

```python
@demo_app.command("prune")
def prune(
    older_than: str = typer.Option("14d", "--older-than"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List candidates without destroying anything."
    ),
) -> None:
```

Then, immediately after the loop that echoes each candidate (the
`for name, created, _kind in candidates: typer.echo(...)` block) and **before**
the `for name, _created, kind in candidates:` destroy loop, insert:

```python
    if dry_run:
        typer.echo("(dry run — nothing destroyed)")
        return
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py::test_prune_dry_run_lists_without_destroying -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/cli.py tests/test_cli.py
git commit -m "feat(cli): add --dry-run to demo prune"
```

---

### Task 2: `adopt` gains `--stack` / `--yes` (non-interactive)

**Files:**
- Modify: `src/demo_tools/cli.py` (`_run_adopt` helper near top, `adopt` command near middle)
- Test: `tests/test_cli.py` (update 3 existing tests + add 1)

- [ ] **Step 1: Update existing tests + add the new one**

In `tests/test_cli.py`, update the three assertions that pin `_run_adopt`'s call
signature (they currently expect a single positional arg):

```python
# in test_init_adopt_subcommand_does_not_call_scaffold:
    adopt_spy.assert_called_once_with("demo", stack=None, yes=False)

# in test_adopt_command_forwards_profile_default:
    spy.assert_called_once_with("demo", stack=None, yes=False)

# in test_adopt_command_forwards_profile_service:
    spy.assert_called_once_with("service", stack=None, yes=False)
```

Then add a new test:

```python
def test_adopt_stack_option_skips_detection(mocker):
    spy = mocker.patch("demo_tools.cli._run_adopt")
    result = runner.invoke(init_app, ["adopt", "--stack", "fastapi", "--yes"])
    assert result.exit_code == 0, result.stdout
    spy.assert_called_once_with("demo", stack="fastapi", yes=True)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -k adopt -v`
Expected: FAIL — `_run_adopt` still takes one positional arg / `adopt` has no `--stack`.

- [ ] **Step 3: Thread the new options through**

In `src/demo_tools/cli.py`, change the `adopt` command:

```python
@init_app.command("adopt")
def adopt(
    profile: str = _PROFILE_OPTION,
    stack: str = typer.Option(None, "--stack", help="Skip detection; use this stack."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the detection-confirm prompt."
    ),
) -> None:
    """Overlay infra onto an existing dockerized repo in the current directory."""
    _run_adopt(profile, stack=stack, yes=yes)
```

Change `_run_adopt`'s signature and stack-resolution block:

```python
def _run_adopt(profile: str, stack: str | None = None, yes: bool = False) -> None:
    from pathlib import Path
    from .adopt import detect_stack, overlay_infra

    repo = Path.cwd()
    if not (repo / "Dockerfile").exists():
        typer.echo("Error: no Dockerfile in current directory.", err=True)
        typer.echo("`demo-init adopt` is for existing dockerized repos.", err=True)
        typer.echo("To scaffold a new demo: demo-init <stack> <name>", err=True)
        raise typer.Exit(1)

    if stack is None:
        detected = detect_stack(repo)
        if detected:
            if yes:
                stack = detected
            else:
                ans = typer.prompt(
                    f"Detected stack: {detected}. Confirm? [Y/n]",
                    default="Y",
                    show_default=False,
                ).strip().lower()
                stack = detected if ans in {"", "y", "yes"} else _prompt_stack()
        else:
            typer.echo("Could not detect stack from package.json / requirements.txt.")
            stack = _prompt_stack()

    if stack not in _ADOPT_DEFAULTS:
        typer.echo(
            f"Error: unknown stack '{stack}'. Valid: {', '.join(VALID_STACKS)}", err=True
        )
        raise typer.Exit(1)

    name = repo.name
    stateful, port = _ADOPT_DEFAULTS[stack]
    overlay_infra(repo, name=name, stack=stack, stateful=stateful,
                  internal_port=port, profile=profile)
    typer.echo(f"Adopted {name}: infra files added (existing files preserved).")
    typer.echo("Next: review fly.toml, then `just deploy`.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -k adopt -v`
Expected: PASS (all adopt tests)

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/cli.py tests/test_cli.py
git commit -m "feat(cli): non-interactive adopt via --stack/--yes"
```

---

### Task 3: `python -m demo_tools` router

**Files:**
- Create: `src/demo_tools/__main__.py`
- Test: `tests/test_main_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_dispatch.py`:

```python
import subprocess
import sys


def _run(*args):
    return subprocess.run(
        [sys.executable, "-m", "demo_tools", *args],
        capture_output=True,
        text=True,
    )


def test_main_routes_demo_help():
    r = _run("demo", "--help")
    assert r.returncode == 0, r.stderr
    assert "prune" in r.stdout


def test_main_routes_init_help():
    r = _run("init", "--help")
    assert r.returncode == 0, r.stderr
    assert "adopt" in r.stdout


def test_main_no_args_errors():
    r = _run()
    assert r.returncode != 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_main_dispatch.py -v`
Expected: FAIL — `No module named demo_tools.__main__`.

- [ ] **Step 3: Write the router**

Create `src/demo_tools/__main__.py`:

```python
from __future__ import annotations

import sys

from typer.main import get_command

from .cli import demo_app, init_app

_GROUPS = {"init": init_app, "demo": demo_app}


def main() -> None:
    argv = sys.argv[1:]
    if not argv or argv[0] not in _GROUPS:
        sys.stderr.write("usage: python -m demo_tools <init|demo> ...\n")
        raise SystemExit(2)
    command = get_command(_GROUPS[argv[0]])
    command(args=argv[1:], prog_name=f"demo_tools {argv[0]}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_main_dispatch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/__main__.py tests/test_main_dispatch.py
git commit -m "feat: add python -m demo_tools dispatcher"
```

---

### Task 4: `_reflect.reflect_tools()` — CLI → tool specs

**Files:**
- Create: `src/demo_tools/_reflect.py`
- Test: `tests/test_reflect.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_reflect.py`:

```python
from demo_tools._reflect import reflect_tools


def _by_name():
    return {t["name"]: t for t in reflect_tools()}


def test_reflect_includes_all_current_commands():
    names = set(_by_name())
    assert {
        "demo_init.scaffold",
        "demo_init.adopt",
        "demo.list",
        "demo.prune",
    } <= names


def test_scaffold_requires_stack_and_name():
    schema = _by_name()["demo_init.scaffold"]["input_schema"]
    assert set(schema["required"]) == {"stack", "name"}
    assert schema["properties"]["stack"]["type"] == "string"


def test_prune_marked_destructive_list_is_not():
    tools = _by_name()
    assert tools["demo.prune"]["destructive"] is True
    assert tools["demo.list"]["destructive"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reflect.py -v`
Expected: FAIL — `No module named demo_tools._reflect`.

- [ ] **Step 3: Write the reflection**

Create `src/demo_tools/_reflect.py`:

```python
from __future__ import annotations

import sys

import click
import typer

from .cli import demo_app, init_app

# Commands that mutate/destroy remote state. The one manual touchpoint, and only
# for dangerous commands — normal commands need no entry here.
DESTRUCTIVE_COMMANDS = {"prune"}

# (router word for __main__, tool-name prefix, Typer app)
_APPS = [
    ("init", "demo_init", init_app),
    ("demo", "demo", demo_app),
]

_TYPE_MAP = {
    "text": "string",
    "integer": "integer",
    "boolean": "boolean",
    "float": "number",
}


def _long_opt(param: click.Option) -> str:
    return next((o for o in param.opts if o.startswith("--")), param.opts[0])


def _param_schema(param: click.Parameter) -> dict:
    if isinstance(param, click.Option) and param.is_flag:
        return {"type": "boolean"}
    type_name = getattr(param.type, "name", "text")
    return {"type": _TYPE_MAP.get(type_name, "string")}


def reflect_tools() -> list[dict]:
    """Introspect the Typer apps into MCP tool specs.

    Each spec: {name, description, input_schema, argv_prefix, params, destructive}.
    `params` is internal metadata used by build_argv().
    """
    tools: list[dict] = []
    for router_word, prefix, app in _APPS:
        group = typer.main.get_command(app)
        for cmd_name, command in group.commands.items():
            properties: dict = {}
            required: list[str] = []
            params: list[dict] = []
            for param in command.params:
                if param.name in (None, "help"):
                    continue
                schema = _param_schema(param)
                is_option = isinstance(param, click.Option)
                if is_option and param.help:
                    schema["description"] = param.help
                properties[param.name] = schema
                if param.required:
                    required.append(param.name)
                params.append(
                    {
                        "name": param.name,
                        "kind": "option" if is_option else "argument",
                        "opt": _long_opt(param) if is_option else None,
                        "is_flag": is_option and param.is_flag,
                    }
                )
            tools.append(
                {
                    "name": f"{prefix}.{cmd_name}",
                    "description": (command.help or "").strip(),
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                    "argv_prefix": [
                        sys.executable, "-m", "demo_tools", router_word, cmd_name
                    ],
                    "params": params,
                    "destructive": cmd_name in DESTRUCTIVE_COMMANDS,
                }
            )
    return tools
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reflect.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/_reflect.py tests/test_reflect.py
git commit -m "feat: reflect Typer CLI into MCP tool specs"
```

---

### Task 5: `_reflect.build_argv()` — spec + args → argv

**Files:**
- Modify: `src/demo_tools/_reflect.py`
- Test: `tests/test_reflect.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reflect.py`:

```python
from demo_tools._reflect import build_argv


def test_build_argv_scaffold_positionals_then_option():
    spec = _by_name()["demo_init.scaffold"]
    argv = build_argv(spec, {"stack": "nextjs", "name": "foo", "profile": "service"})
    assert argv[1:] == [
        "-m", "demo_tools", "init", "scaffold",
        "nextjs", "foo", "--profile", "service",
    ]


def test_build_argv_omits_false_flag():
    spec = _by_name()["demo.prune"]
    argv = build_argv(spec, {"dry_run": False})
    assert "--dry-run" not in argv


def test_build_argv_includes_true_flag():
    spec = _by_name()["demo.prune"]
    argv = build_argv(spec, {"dry_run": True})
    assert "--dry-run" in argv
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_reflect.py -k build_argv -v`
Expected: FAIL — `cannot import name 'build_argv'`.

- [ ] **Step 3: Implement build_argv**

Append to `src/demo_tools/_reflect.py`:

```python
def build_argv(spec: dict, arguments: dict) -> list[str]:
    """Turn a tool spec + arguments into an argv for `sys.executable -m demo_tools`."""
    argv = list(spec["argv_prefix"])
    args = arguments or {}
    # Positional arguments first, in declared order.
    for param in spec["params"]:
        if param["kind"] == "argument" and param["name"] in args:
            argv.append(str(args[param["name"]]))
    # Then options.
    for param in spec["params"]:
        if param["kind"] != "option" or param["name"] not in args:
            continue
        value = args[param["name"]]
        if param["is_flag"]:
            if value:
                argv.append(param["opt"])
        else:
            argv.extend([param["opt"], str(value)])
    return argv
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_reflect.py -v`
Expected: PASS (all reflect tests)

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/_reflect.py tests/test_reflect.py
git commit -m "feat: build CLI argv from tool spec + arguments"
```

---

### Task 6: `mcp_server.py` — server + `run_tool`

**Files:**
- Create: `src/demo_tools/mcp_server.py`
- Test: `tests/test_mcp_server.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mcp_server.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: FAIL — `No module named demo_tools.mcp_server` (or `mcp` not installed; if so, `uv sync --extra mcp` first — but Task 7 adds the extra. For local dev now run `uv add --optional mcp "mcp>=1.6"` or `uv pip install "mcp>=1.6"`).

- [ ] **Step 3: Write the server**

Create `src/demo_tools/mcp_server.py`:

```python
from __future__ import annotations

import subprocess

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from ._reflect import build_argv, reflect_tools

_SPECS = reflect_tools()
_SPECS_BY_NAME = {spec["name"]: spec for spec in _SPECS}

server = Server("demo-tools")


def run_tool(name: str, arguments: dict | None) -> str:
    """Execute one tool by shelling out to `sys.executable -m demo_tools …`."""
    spec = _SPECS_BY_NAME.get(name)
    if spec is None:
        raise ValueError(f"Unknown tool: {name}")

    args = dict(arguments or {})
    # Destructive tools are dry-run unless the caller explicitly opts out.
    if spec["destructive"] and "dry_run" not in args:
        args["dry_run"] = True

    argv = build_argv(spec, args)
    proc = subprocess.run(
        argv, capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    output = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode != 0:
        raise RuntimeError(output.strip() or f"exited with code {proc.returncode}")
    return output


@server.list_tools()
async def _list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name=spec["name"],
            description=spec["description"] or spec["name"],
            inputSchema=spec["input_schema"],
            annotations=types.ToolAnnotations(destructiveHint=spec["destructive"]),
        )
        for spec in _SPECS
    ]


@server.call_tool()
async def _call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    text = run_tool(name, arguments)
    return [types.TextContent(type="text", text=text or "(no output)")]


def main() -> None:
    import anyio

    async def _serve() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream, write_stream, server.create_initialization_options()
            )

    anyio.run(_serve)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp_server.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/demo_tools/mcp_server.py tests/test_mcp_server.py
git commit -m "feat: MCP server reflecting the demo-tools CLI"
```

---

### Task 7: Packaging + docs

**Files:**
- Modify: `pyproject.toml`
- Modify: `README.md`

- [ ] **Step 1: Add the script and optional dependency**

In `pyproject.toml`, under `[project.scripts]` add:

```toml
demo-mcp = "demo_tools.mcp_server:main"
```

And add a new table (place after `[project.scripts]`):

```toml
[project.optional-dependencies]
mcp = ["mcp>=1.6"]
```

- [ ] **Step 2: Sync and verify the server boots**

Run: `uv sync --extra mcp`
Then verify the full test suite passes:
Run: `uv run pytest -q`
Expected: all tests pass.

Smoke-check the server lists tools (Ctrl-C after it prints, or just confirm it starts without import error):
Run: `uv run --extra mcp python -c "from demo_tools.mcp_server import _SPECS; print(sorted(s['name'] for s in _SPECS))"`
Expected: `['demo.list', 'demo.prune', 'demo_init.adopt', 'demo_init.scaffold']`

- [ ] **Step 3: Document in README**

Add a section to `README.md` (after the Quick start) titled `## MCP server`:

````markdown
## MCP server

Expose every `demo-tools` command to an MCP client (e.g. Claude Code). New CLI
commands show up as tools automatically — no extra wiring.

```bash
# Install with MCP support
uv tool install --editable ".[mcp]"

# Register with Claude Code (stdio). Either form works:
claude mcp add demo-tools -- demo-mcp
# …or run straight from a clone, no install needed:
claude mcp add demo-tools -- uv run --directory /path/to/demo-tools demo-mcp
```

`demo.prune` is dry-run by default; destruction requires explicitly passing
`dry_run: false` and `yes: true`. It is flagged destructive so the client asks
before running.
````

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml README.md uv.lock
git commit -m "feat: package demo-mcp script + document MCP server"
```

---

## Final verification

- [ ] Run the whole suite: `uv run pytest -q` — expected: all pass.
- [ ] Confirm reflection covers all commands: the smoke-check in Task 7 Step 2 lists
  `demo.list`, `demo.prune`, `demo_init.adopt`, `demo_init.scaffold`.
- [ ] Confirm a *new* command would appear automatically: this is structural — any
  `@init_app.command` / `@demo_app.command` is picked up by `reflect_tools()` with no
  edit, except destructive ones, which need a name in `DESTRUCTIVE_COMMANDS`.
