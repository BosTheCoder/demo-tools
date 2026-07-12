import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

# ROOT_PATH is the base path the app is served under. It is empty on Fly and on
# `just dev` (served at "/"), and "/<name>" on the local Tailscale target.
#
# IMPORTANT: `tailscale serve --set-path /<name> <port>` STRIPS the "/<name>"
# prefix before proxying — the container only ever sees "/approve",
# "/static/app.css", etc, never "/<name>/approve". root_path is still needed
# for URL *generation* (request.url_for, redirects) so the browser gets links
# with the prefix restored — that's a one-way concern; don't assume incoming
# requests carry the prefix.
#
# When you add links, redirects, HTMX attributes, or static assets, build URLs
# from the base path so they resolve under "/<name>" on local and "/" on Fly:
#   - request.url_for(...) for named routes,
#   - request.scope["root_path"] as a prefix in templates
#     (e.g. hx-get="{{ request.scope.root_path }}/approve"),
#   - a route-based static handler (see `static_file` below), NOT
#     `app.mount("/static", StaticFiles(...))` — a Mount only matches the full
#     "/<name>/static/..." path, so the stripped "/static/..." request 404s.
# Never hard-code absolute paths like "/static/app.css" or hx-get="/approve" —
# those resolve to the tailnet host root and bypass the app on local.
#
# uvicorn must also run with --proxy-headers (see the Dockerfile CMD) so it
# trusts Tailscale's X-Forwarded-Proto: https header. Without it, url_for()
# emits http:// URLs on an https:// page, which browsers block as mixed
# content.
app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))

STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
def root() -> dict[str, str]:
    return {"hello": "world"}


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/static/{path:path}", name="static")
def static_file(path: str) -> FileResponse:
    """Serve static assets via a route rather than a StaticFiles Mount.

    A Mount only matches the full "/<name>/static/..." path; Tailscale's
    `--set-path` strips the "/<name>" prefix, so the container sees a bare
    "/static/..." request that a Mount would 404 on. A route matches either
    way, and url_for("static", path=...) still emits the prefixed URL.
    """
    candidate = (STATIC_DIR / path).resolve()
    if STATIC_DIR.resolve() not in candidate.parents or not candidate.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(candidate)
