# demo-tools MCP server — design

**Date:** 2026-05-30
**Status:** Approved (pre-implementation)

## Goal

Expose the `demo-tools` CLI to MCP clients (Claude Code) so an agent can scaffold,
adopt, list, and prune demos. The exposure must be **automatic**: adding a new
command to the Typer CLI should make a corresponding MCP tool appear with no extra
code, honoring the project's existing "add functionality once" ethos.

Scope is **everything** — including the destructive `prune` — but destruction is made
deliberate via dry-run-by-default + explicit confirmation.

## Non-goals

- No changes to the core logic modules (`scaffold.py`, `adopt.py`, `fleet.py`).
- No remote/HTTP transport. stdio only.
- No re-implementation of command logic in the MCP layer; it reuses the installed CLI.

## Architecture

Ports-and-adapters. The existing core stays untouched; the CLI stays the human-facing
adapter; a new MCP adapter is added. A reflection helper is the single source of truth
that both adapters' metadata flows from.

```
        core: scaffold() · adopt() · list_apps() · prune-logic
                          ▲
            ┌─────────────┴──────────────┐
        cli.py                      mcp_server.py   (new)
     (Typer apps)                   (MCP adapter)
            │                             │
            └──────── _reflect.py ────────┘   (new)
```

New files:
- `src/demo_tools/_reflect.py` — introspects the Typer apps into tool specs.
- `src/demo_tools/mcp_server.py` — the MCP server (named `mcp_server` to avoid
  clashing with the `mcp` package import).

## Components

### `_reflect.py` — CLI introspection (single source of truth)

Typer wraps Click. Use `typer.main.get_command(app)` to obtain the underlying Click
group for each of `init_app` and `demo_app`. For each command in `group.commands`,
read its `.params` (Click Options/Arguments) to extract: name, type, default,
required-ness, and help text.

Produces a list of tool specs. Each spec carries:
- `name` — `<app>.<command>` flattened, e.g. `demo_init.scaffold`, `demo.list`.
- `description` — the command's help/docstring.
- `input_schema` — JSON Schema derived from params:
  - Click `str` → `string`, `bool` → `boolean`, `int` → `integer`.
  - Required Click arguments → required schema fields.
  - Param help → field `description`.
- `argv_prefix` — the base argv for the command, e.g. `["demo-init", "scaffold"]`.
- `destructive` — bool, from a small explicit set (see below).

`DESTRUCTIVE_COMMANDS = {"prune"}` lives here. It is the one manual touchpoint, and
only for dangerous commands. Adding a normal command requires no edit here.

### `mcp_server.py` — the MCP adapter

Built on the MCP Python SDK's **low-level `Server`** (`mcp.server.Server`), because the
tool set is generated dynamically. Implements two handlers:

- `list_tools()` — returns one MCP `Tool` per reflected spec. Destructive specs get the
  `destructiveHint` annotation so the client (Claude Code) prompts before running.
- `call_tool(name, arguments)` — looks up the spec, builds an argv from
  `argv_prefix` + the supplied arguments, runs the installed console script as a
  **subprocess with stdin closed**, and returns stdout/stderr/exit code as the tool
  result (non-zero exit surfaced as an error result).

`main()` runs the server over stdio. Wired as a console script.

### Argv builder

Maps tool arguments to CLI flags/positionals using the reflected param metadata:
positional Click arguments become positional argv entries; options become
`--name value` (or bare `--flag` for booleans). Lives in `_reflect.py` (it needs the
same metadata) and is unit-tested independently.

## Destructive / interactive handling

The MCP transport has no stdin, so commands that prompt must be made
non-interactive-capable. Small CLI refactor (also improves the CLI for humans):

- **`prune`** gains a `--dry-run` flag: list candidates, destroy nothing. The `prune`
  MCP tool **defaults to dry-run**; it only passes `--yes` (destroy) when called with
  `confirm: true`.
- **`adopt`** gains `--stack` and `--yes` options so its stack-detection confirmation
  can be answered non-interactively.

Safety net: subprocess runs with stdin closed, so any unconverted prompt aborts with an
error rather than hanging.

The real human-in-the-loop gate remains the client: `destructiveHint` causes Claude Code
to ask for approval before running `prune`.

## Packaging & running

- `pyproject.toml`:
  - New console script: `demo-mcp = "demo_tools.mcp_server:main"`.
  - New optional dependency group: `[project.optional-dependencies] mcp = ["mcp>=1.2"]`
    so the base CLI install stays lean.
- Install with MCP support: `uv tool install --editable ".[mcp]"`.
- Register with Claude Code: `claude mcp add demo-tools -- demo-mcp` (stdio).
- README section documenting install + registration.

## Testing

- **Reflection** (`_reflect.py`): given the real Typer apps, assert the generated tool
  list contains every current command (`demo_init.scaffold`, `demo_init.adopt`,
  `demo.list`, `demo.prune`) with correct required fields — e.g. `scaffold` requires
  `stack` and `name`.
- **Argv builder**: tool name + arguments → expected argv (positionals + options).
- **`call_tool`**: with the subprocess call stubbed (pytest-mock), assert the correct
  argv is built, and that the `prune` tool **omits `--yes` unless `confirm: true`** (and
  passes `--dry-run` by default).
- **Smoke**: `list_tools()` returns a non-empty list and every spec has a valid schema.

## Done criteria

- `demo-mcp` starts over stdio and lists a tool per current CLI command.
- New CLI commands appear as tools with no MCP-layer code change.
- `prune` is non-destructive unless `confirm: true`; flagged `destructiveHint`.
- Tests above pass.
