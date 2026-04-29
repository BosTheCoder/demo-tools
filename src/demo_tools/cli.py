from __future__ import annotations

import typer

init_app = typer.Typer(
    no_args_is_help=True,
    help="Scaffold a new demo or adopt an existing dockerized repo.",
)
demo_app = typer.Typer(
    no_args_is_help=True,
    help="Manage existing demos (list, prune).",
)

VALID_STACKS = ("nextjs", "nextjs-fastapi", "fastapi", "streamlit", "static", "bare")


@init_app.command("scaffold")
def scaffold(stack: str = typer.Argument(...), name: str = typer.Argument(...)) -> None:
    """Scaffold a new demo: demo-init scaffold <stack> <name>."""
    raise NotImplementedError


@init_app.command("adopt")
def adopt() -> None:
    """Overlay infra onto an existing dockerized repo in the current directory."""
    raise NotImplementedError


@demo_app.command("list")
def list_demos() -> None:
    """List all Fly apps with status and URLs."""
    raise NotImplementedError


@demo_app.command("prune")
def prune(older_than: str = typer.Option("14d", "--older-than")) -> None:
    """Interactively destroy demos older than the given age."""
    raise NotImplementedError
