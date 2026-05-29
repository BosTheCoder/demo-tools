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
