from __future__ import annotations

import click
import typer
from typer.core import TyperGroup

VALID_STACKS = ("nextjs", "nextjs-fastapi", "fastapi", "streamlit", "static", "bare")


def _run_scaffold(stack: str, name: str) -> None:
    from pathlib import Path
    from .scaffold import scaffold_demo
    target = Path.cwd() / name
    if target.exists():
        typer.echo(f"Error: {target} already exists.", err=True)
        raise typer.Exit(1)
    scaffold_demo(stack, name, target)
    typer.echo(f"Scaffolded {name} at {target}")
    typer.echo(f"Next: cd {name} && just dev   (or 'just deploy' to ship)")


_ADOPT_DEFAULTS = {
    # stack -> (stateful, internal_port)
    "bare": (False, 3000),
    "nextjs": (False, 3000),
    "static": (False, 80),
    "fastapi": (True, 8000),
    "streamlit": (True, 8501),
    "nextjs-fastapi": (True, 3000),
}


def _run_adopt() -> None:
    from pathlib import Path
    from .adopt import detect_stack, overlay_infra

    repo = Path.cwd()
    if not (repo / "Dockerfile").exists():
        typer.echo("Error: no Dockerfile in current directory.", err=True)
        typer.echo("`demo-init adopt` is for existing dockerized repos.", err=True)
        typer.echo("To scaffold a new demo: demo-init <stack> <name>", err=True)
        raise typer.Exit(1)

    detected = detect_stack(repo)
    if detected:
        ans = typer.prompt(
            f"Detected stack: {detected}. Confirm? [Y/n]",
            default="Y",
            show_default=False,
        ).strip().lower()
        stack = detected if ans in {"", "y", "yes"} else _prompt_stack()
    else:
        typer.echo("Could not detect stack from package.json / requirements.txt.")
        stack = _prompt_stack()

    name = repo.name
    stateful, port = _ADOPT_DEFAULTS[stack]
    overlay_infra(repo, name=name, stack=stack, stateful=stateful, internal_port=port)
    typer.echo(f"Adopted {name}: infra files added (existing files preserved).")
    typer.echo("Next: review fly.toml, then `just deploy`.")


def _prompt_stack() -> str:
    return typer.prompt(
        f"Which stack? ({'|'.join(VALID_STACKS)})",
        default="nextjs",
    ).strip()


class _InitGroup(TyperGroup):
    """Routes bare ``demo-init <stack> <name>`` to the ``scaffold`` subcommand.

    Click resolves the subcommand before any callback runs, so we can't use a
    Typer callback + ``ctx.args`` to peek at unparsed positional args (the
    group's ``parse_args`` would have already failed). Instead we rewrite the
    arg list at ``resolve_command`` time when the first arg is a known stack.
    """

    def resolve_command(
        self, ctx: click.Context, args: list[str]
    ) -> tuple[str | None, click.Command | None, list[str]]:
        if args and args[0] in VALID_STACKS:
            args = ["scaffold", *args]
        return super().resolve_command(ctx, args)


init_app = typer.Typer(
    cls=_InitGroup,
    no_args_is_help=True,
    help="Scaffold a new demo or adopt an existing dockerized repo.",
)
demo_app = typer.Typer(
    no_args_is_help=True,
    help="Manage existing demos (list, prune).",
)


@init_app.command("scaffold")
def scaffold(stack: str = typer.Argument(...), name: str = typer.Argument(...)) -> None:
    """Explicit form: demo-init scaffold <stack> <name>."""
    _run_scaffold(stack, name)


@init_app.command("adopt")
def adopt() -> None:
    """Overlay infra onto an existing dockerized repo in the current directory."""
    _run_adopt()


@demo_app.command("list")
def list_demos() -> None:
    """List all Fly apps with status and URLs."""
    raise NotImplementedError("demo list is implemented in Task 6.1")


@demo_app.command("prune")
def prune(older_than: str = typer.Option("14d", "--older-than")) -> None:
    """Interactively destroy demos older than the given age."""
    raise NotImplementedError("demo prune is implemented in Task 6.2")
