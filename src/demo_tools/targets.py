"""Deploy-target rules: which stacks each target can serve, and how it publishes.

`fly` and `local` both build a Docker image and run a server, so they accept any
stack that ships a Dockerfile. `pages` serves files off a CDN — no server, no
container — so it accepts only stacks whose output is files.

Kept separate from `stacks/` because this is about the *pairing* of a stack and
a target, which neither owns on its own.
"""

from __future__ import annotations

VALID_TARGETS = ("fly", "local", "pages")

# Stacks that need a process running to answer a request. A CDN cannot host them.
SERVER_STACKS = frozenset({"fastapi", "streamlit", "nextjs-fastapi"})

# Stacks with no Dockerfile. fly and local both build an image, so these can
# only go to pages.
NO_DOCKERFILE_STACKS = frozenset({"html"})

# Stacks with a build step. Their output lands in a directory (dist/) that
# cannot be served from the repo root, so it is published to a branch.
BUILD_STACKS = frozenset({"vite", "nextjs"})


def check_target_stack(target: str, stack: str) -> None:
    """Raise ValueError if this stack cannot be deployed to this target.

    Called before any files are written, so a bad combination costs nothing.
    """
    if target not in VALID_TARGETS:
        raise ValueError(
            f"Unknown target '{target}'. Valid targets: {', '.join(VALID_TARGETS)}"
        )

    if target == "pages":
        if stack in SERVER_STACKS:
            raise ValueError(
                f"The 'pages' target serves static files only, but '{stack}' needs a "
                f"running server.\n\n"
                f"  static hosting : html, vite, bare\n"
                f"  needs a server : {', '.join(sorted(SERVER_STACKS))}\n\n"
                f"Use --target fly (cloud) or --target local (Tailscale container)."
            )
        if stack == "nextjs":
            # Technically possible via output: 'export', but that silently drops
            # SSR, API routes and image optimisation — breakage that shows up
            # long after scaffold time. Opt in explicitly or not at all.
            raise ValueError(
                "The 'pages' target does not support 'nextjs'.\n\n"
                "Next.js can target Pages via static export (output: 'export'), but "
                "that silently disables SSR, API routes and image optimisation.\n\n"
                "Use --target fly, or scaffold 'vite' if you want a static SPA."
            )
        return

    # fly / local
    if stack in NO_DOCKERFILE_STACKS:
        raise ValueError(
            f"The '{target}' target builds a Docker image, but the '{stack}' stack "
            f"has no Dockerfile — it is plain files with no build step.\n\n"
            f"Use --target pages, or scaffold 'vite' if you need a container."
        )


def publish_mode(stack: str) -> str:
    """How the pages target publishes this stack: 'root' or 'branch'.

    A stack with no build step has nothing to copy — the repo root is already
    the site, so Pages serves main directly. A stack that builds produces a
    dist/ that cannot sit at the repo root, so it is pushed to gh-pages.
    """
    return "root" if stack not in BUILD_STACKS and stack in NO_DOCKERFILE_STACKS else "branch"


def targets_for_stack(stack: str) -> tuple[str, ...]:
    """The targets this stack can actually deploy to."""
    return tuple(t for t in VALID_TARGETS if _ok(t, stack))


def _ok(target: str, stack: str) -> bool:
    try:
        check_target_stack(target, stack)
    except ValueError:
        return False
    return True
