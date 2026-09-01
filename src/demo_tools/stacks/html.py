"""Plain HTML/JS/CSS — no bundler, no package.json, no Dockerfile.

For pages that don't need a toolchain: a redirect, a converter, a link tool, a
status board. The value isn't disk space (node_modules is gitignored either
way) — it's that there is nothing to rot. No Node version, no lockfile, no
bundler config, so the deploy path still works untouched years later.

Files land at the repo root because GitHub Pages can only be pointed at "/" or
"/docs" — never "app/" — and this stack publishes by serving main directly.

Cross into JSX, TypeScript, npm libraries or HMR and the answer is to scaffold
`vite`, not to grow this into a bundled app.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import pwa

_INDEX = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<link rel="stylesheet" href="app.css">
<link rel="icon" href="icon-192.png">
{head_tags}
</head>
<body>
<main>
  <h1>{name}</h1>
  <p>Plain HTML, JS and CSS. No build step — edit these files and reload.</p>
  <button id="ping" type="button">Say hello</button>
  <p id="out" aria-live="polite"></p>
</main>
<script type="module" src="app.js"></script>
{sw_script}</body>
</html>
"""

_SW_SCRIPT = """<script>
  // Non-fatal by design: without the worker the app still runs, it just loses
  // its offline fallback.
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("sw.js").catch(function () {});
    });
  }
</script>
"""

_APP_JS = """// No bundler: this is an ES module the browser loads directly.
// Imports of other local modules work as-is — use relative paths with the
// extension ("./thing.js"), since there is no resolver to guess them for you.

const out = document.getElementById("out");

document.getElementById("ping").addEventListener("click", () => {
  out.textContent = `hello at ${new Date().toLocaleTimeString()}`;
});
"""

_APP_CSS = """:root {
  --bg: #fbfbfd; --fg: #1c1c1e; --muted: #6b6b70; --accent: %(accent)s;
}
@media (prefers-color-scheme: dark) {
  :root { --bg: #16161a; --fg: #ececf1; --muted: #9b9ba3; }
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; display: grid; place-items: center; padding: 24px;
  background: var(--bg); color: var(--fg);
  font: 16px/1.5 ui-sans-serif, -apple-system, "Segoe UI", system-ui, sans-serif;
}
main { width: 100%%; max-width: 32rem; }
h1 { font-size: 1.25rem; letter-spacing: -.01em; margin: 0 0 4px; }
p { color: var(--muted); margin: 0 0 16px; }
button {
  padding: 10px 16px; border: 0; border-radius: 10px;
  background: var(--accent); color: #fff; font: inherit; font-weight: 600;
  cursor: pointer;
}
button:active { opacity: .85; }
"""


def scaffold(target: Path, name: str, *, pwa_assets: bool = True) -> dict[str, Any]:
    target.mkdir(parents=True, exist_ok=True)

    # Every path is relative, because this stack is served from two places: the
    # custom domain root (https://site/) and, before a domain is attached,
    # https://<user>.github.io/<repo>/. Absolute "/manifest.webmanifest" 404s in
    # the second case, and an absolute scope makes the browser refuse to install.
    # A page whose whole job is to redirect, or to render one field, has no
    # use for an installable shell — and a service worker in front of it can
    # serve a stale copy of the very thing it exists to bounce. --no-pwa is
    # for those.
    if pwa_assets:
        pwa.write_assets(target, name, scope="./")

    (target / "index.html").write_text(
        _INDEX.format(name=name, head_tags=pwa.head_tags(".") if pwa_assets else "",
                      sw_script=_SW_SCRIPT if pwa_assets else ""),
        encoding="utf-8",
    )
    (target / "app.js").write_text(_APP_JS, encoding="utf-8")
    (target / "app.css").write_text(_APP_CSS % {"accent": pwa.hex_accent(name)}, encoding="utf-8")

    # internal_port is only meaningful to targets that run a container; it is
    # carried so `just dev`'s local http.server has a port to bind.
    return {"stack": "html", "stateful": False, "internal_port": 8000}
