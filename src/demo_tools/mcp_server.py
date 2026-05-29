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
    """Execute one tool by shelling out to `sys.executable -m demo_tools ...`."""
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
