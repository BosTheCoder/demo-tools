from __future__ import annotations

import sys

import click
import typer

from .cli import demo_app, init_app

# Commands that mutate/destroy remote state. The one manual touchpoint, and only
# for dangerous commands — normal commands need no entry here.
DESTRUCTIVE_COMMANDS = {"prune"}

# Commands that only read state — safe for clients to call without confirmation.
READONLY_COMMANDS = {"list"}

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
    if param.param_type_name == "option" and param.is_flag:
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
                is_option = param.param_type_name == "option"
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
                    "readonly": cmd_name in READONLY_COMMANDS,
                }
            )
    return tools


def build_argv(spec: dict, arguments: dict) -> list[str]:
    """Turn a tool spec + arguments into an argv for `sys.executable -m demo_tools`."""
    argv = list(spec["argv_prefix"])
    args = arguments or {}
    # Positional arguments first, in declared order.
    for param in spec["params"]:
        if param["kind"] == "argument" and args.get(param["name"]) is not None:
            argv.append(str(args[param["name"]]))
    # Then options.
    for param in spec["params"]:
        if (
            param["kind"] != "option"
            or param["name"] not in args
            or args[param["name"]] is None
        ):
            continue
        value = args[param["name"]]
        if param["is_flag"]:
            if value:
                argv.append(param["opt"])
        else:
            argv.extend([param["opt"], str(value)])
    return argv
