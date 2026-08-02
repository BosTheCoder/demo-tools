import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse

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
def root(request: Request) -> HTMLResponse:
    """The app shell.

    Served from a route (not a redirect to a file) so {{ROOT_PATH}} can be
    substituted per request — the prefix is only known from the incoming
    request's root_path, and the same file has to work on Fly at "/" too.
    """
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html.replace("{{ROOT_PATH}}", request.scope.get("root_path", "")))


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


# The manifest and the service worker are served from the app root rather than
# from /static, and that placement is load-bearing: a service worker can only
# control URLs at or below the path it was served from, so one under /static/
# could never intercept the pages it exists to cache.
@app.get("/manifest.webmanifest", name="manifest")
def manifest(request: Request) -> Response:
    raw = (STATIC_DIR / "manifest.webmanifest").read_text(encoding="utf-8")
    root_path = request.scope.get("root_path", "")
    return Response(
        raw.replace("{{ROOT_PATH}}", root_path),
        media_type="application/manifest+json",
    )


@app.get("/sw.js", name="sw")
def service_worker() -> FileResponse:
    return FileResponse(
        STATIC_DIR / "sw.js",
        media_type="text/javascript",
        # A cached service worker is how an app gets stuck on an old version.
        headers={"Cache-Control": "no-cache"},
    )


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
