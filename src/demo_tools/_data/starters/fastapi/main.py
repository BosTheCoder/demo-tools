import os

from fastapi import FastAPI

# ROOT_PATH is the base path the app is served under. It is empty on Fly and on
# `just dev` (served at "/"), and "/<name>" on the local Tailscale target, where
# Tailscale forwards the path WITHOUT stripping it. FastAPI/Starlette strips
# root_path from the incoming path for routing, so route decorators stay the
# same across targets — do NOT prefix them by hand.
#
# When you add links, redirects, HTMX attributes, or static mounts, build URLs
# from the base path so they resolve under "/<name>" on local and "/" on Fly:
#   - request.url_for(...) for named routes,
#   - request.scope["root_path"] as a prefix in templates
#     (e.g. hx-get="{{ request.scope.root_path }}/approve"),
#   - app.mount("/static", ...) + url_for("static", path=...) for assets.
# Never hard-code absolute paths like "/static/app.css" or hx-get="/approve" —
# those resolve to the tailnet host root and bypass the app on local.
app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))


@app.get("/")
def root() -> dict[str, str]:
    return {"hello": "world"}


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}
