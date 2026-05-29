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
