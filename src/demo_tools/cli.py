from __future__ import annotations

import typer

VALID_STACKS = ("nextjs", "nextjs-fastapi", "fastapi", "streamlit", "static", "bare")


def _run_scaffold(
    stack: str,
    name: str,
    profile: str,
    target: str = "fly",
    tailscale_path: str | None = None,
) -> None:
    from pathlib import Path
    from .scaffold import scaffold_demo
    if target == "local" and profile != "demo":
        typer.echo("Note: --profile only affects Fly; ignored for --target local.")
    dest = Path.cwd() / name
    if dest.exists():
        typer.echo(f"Error: {dest} already exists.", err=True)
        raise typer.Exit(1)
    scaffold_demo(
        stack, name, dest, profile=profile,
        deploy_target=target, tailscale_path=tailscale_path,
    )
    typer.echo(f"Scaffolded {name} at {dest}")
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


def _run_adopt(
    profile: str,
    stack: str | None = None,
    yes: bool = False,
    target: str = "fly",
    tailscale_path: str | None = None,
) -> None:
    from pathlib import Path
    from .adopt import detect_stack, overlay_infra

    if target == "local" and profile != "demo":
        typer.echo("Note: --profile only affects Fly; ignored for --target local.")

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
            f"Error: unknown stack '{stack}'. Valid: {', '.join(_ADOPT_DEFAULTS)}", err=True
        )
        raise typer.Exit(1)

    name = repo.name
    stateful, port = _ADOPT_DEFAULTS[stack]
    overlay_infra(repo, name=name, stack=stack, stateful=stateful,
                  internal_port=port, profile=profile,
                  deploy_target=target, tailscale_path=tailscale_path)
    typer.echo(f"Adopted {name}: infra files added (existing files preserved).")
    typer.echo("Next: review fly.toml, then `just deploy`.")


def _prompt_stack() -> str:
    return typer.prompt(
        f"Which stack? ({'|'.join(VALID_STACKS)})",
        default="nextjs",
    ).strip()


_INIT_HELP = """Scaffold a new demo or adopt an existing dockerized repo.

Stacks (used with the scaffold command: demo-init scaffold <stack> <name>):

  nextjs          Next.js + Tailwind, single Fly app
  nextjs-fastapi  Next.js web + FastAPI api, dual Fly app (api on .internal)
  fastapi         FastAPI starter, SQLite + Fly volume
  streamlit       Streamlit starter, SQLite + Fly volume
  static          Vite + nginx static site
  bare            Empty app/, bring your own Dockerfile

Examples:

  demo-init scaffold static my-site
  demo-init scaffold nextjs my-app
  demo-init adopt
"""

init_app = typer.Typer(
    no_args_is_help=True,
    help=_INIT_HELP,
)
demo_app = typer.Typer(
    no_args_is_help=True,
    help="Manage existing demos (list, prune).",
)


_PROFILE_OPTION = typer.Option(
    "demo",
    "--profile",
    help="demo (auto-stop, 0 min machines) | service (always-on, ≥1 machine)",
)


def _target_option() -> typer.Option:
    return typer.Option(
        "fly",
        "--target",
        help="fly (cloud) | local (always-on container exposed via Tailscale)",
    )


def _tailscale_path_option() -> typer.Option:
    return typer.Option(
        None,
        "--tailscale-path",
        help="URL path prefix under the shared Tailscale host (local target; defaults to /<name>).",
    )


@init_app.command("scaffold")
def scaffold(
    stack: str = typer.Argument(...),
    name: str = typer.Argument(...),
    profile: str = _PROFILE_OPTION,
    target: str = _target_option(),
    tailscale_path: str = _tailscale_path_option(),
) -> None:
    """Explicit form: demo-init scaffold <stack> <name>."""
    _run_scaffold(stack, name, profile, target, tailscale_path)


@init_app.command("adopt")
def adopt(
    profile: str = _PROFILE_OPTION,
    stack: str = typer.Option(None, "--stack", help="Skip detection; use this stack."),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip the detection-confirm prompt."
    ),
    target: str = _target_option(),
    tailscale_path: str = _tailscale_path_option(),
) -> None:
    """Overlay infra onto an existing dockerized repo in the current directory."""
    _run_adopt(profile, stack=stack, yes=yes, target=target,
               tailscale_path=tailscale_path)


@demo_app.command("list")
def list_demos() -> None:
    """List all Fly apps with status and URLs."""
    from rich.console import Console
    from rich.table import Table

    from .fleet import DOMAIN_BASE, list_apps, list_demos_only

    apps = list_demos_only(list_apps())
    table = Table(title="Demos")
    table.add_column("name")
    table.add_column("status")
    table.add_column("url")
    for a in apps:
        url = f"https://{a['name']}.{DOMAIN_BASE}"
        table.add_row(a["name"], a["status"], url)
    Console().print(table)


@demo_app.command("prune")
def prune(
    older_than: str = typer.Option("14d", "--older-than"),
    yes: bool = typer.Option(False, "--yes", "-y"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="List candidates without destroying anything."
    ),
) -> None:
    """Interactively destroy demos older than the given age."""
    import datetime as dt
    import json
    import subprocess as sp

    from .fleet import list_apps, list_demos_only, parse_duration

    cutoff = dt.datetime.now(dt.timezone.utc) - parse_duration(older_than)

    candidates = []
    for app in list_demos_only(list_apps()):
        try:
            r = sp.run(
                ["fly", "status", "--app", app["name"], "--json"],
                capture_output=True, text=True, check=True,
            )
            status = json.loads(r.stdout)
            created = status.get("App", {}).get("CreatedAt")
            if not created:
                continue
            created_dt = dt.datetime.fromisoformat(created.replace("Z", "+00:00"))
            if created_dt < cutoff:
                candidates.append((app["name"], created_dt, app.get("kind")))
        except sp.CalledProcessError:
            continue

    if not candidates:
        typer.echo(f"No demos older than {older_than}.")
        return

    typer.echo(f"Candidates older than {older_than}:")
    for name, created, _kind in candidates:
        typer.echo(f"  {name}  (created {created:%Y-%m-%d})")

    if dry_run:
        typer.echo("(dry run — nothing destroyed)")
        return

    for name, _created, kind in candidates:
        if not yes:
            ans = typer.prompt(f"Destroy {name}? [y/N]", default="N", show_default=False)
            if ans.strip().lower() not in {"y", "yes"}:
                typer.echo(f"  skipped {name}")
                continue
        targets = [name] if kind != "nextjs-fastapi" else [f"{name}-web", f"{name}-api"]
        for t in targets:
            sp.run(["fly", "apps", "destroy", "--yes", t], check=False)
        typer.echo(f"  destroyed {name}")
