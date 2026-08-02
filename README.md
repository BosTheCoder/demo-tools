<div align="center">

# demo-tools

**Spin up a demo. Ship it. Forget it.**

A CLI + [Copier](https://copier.readthedocs.io/) template for scaffolding throwaway web apps and shipping them to [Fly.io](https://fly.io) with sane defaults — auto-stop billing, free TLS on a custom subdomain, and one `just` recipe per operation.

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-3776ab.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Built for Fly.io](https://img.shields.io/badge/deploys-Fly.io-7B3FE4?logo=docker&logoColor=white)](https://fly.io)
[![Powered by uv](https://img.shields.io/badge/installed%20via-uv-DE5FE9)](https://github.com/astral-sh/uv)
[![Built on Copier](https://img.shields.io/badge/scaffolded%20with-Copier-2ea44f)](https://copier.readthedocs.io/)
[![Status: alpha](https://img.shields.io/badge/status-alpha-orange)]()

```bash
demo-init scaffold nextjs chord-detector
cd chord-detector && just deploy
# → https://chord-detector.fly.dev
# → https://chord-detector.demos.buildwithbos.com
```

</div>

---

## Why this exists

Throwaway demos shouldn't take an afternoon to host. With `demo-tools`:

- **Zero config out of the box.** Pick a stack, get an app + Dockerfile + `fly.toml` + a working `just deploy`.
- **Costs nothing when idle.** Machines auto-stop on no traffic; auto-start on the next request (~5s warm-up).
- **Free TLS on a real subdomain.** `<name>.demos.buildwithbos.com` is wired up via wildcard DNS — set it up once, every future demo just works.
- **Adoptable.** Got an existing Dockerfile? `demo-init adopt` overlays the infra without touching your app.
- **Updatable.** `just sync` pulls template improvements into existing demos via three-way merge.

---

## Quick start

```bash
# Prerequisites: uv (https://astral.sh/uv) + flyctl (https://fly.io/install)

# Local clone — editable, reflects your edits live (recommended if you tweak it):
git clone https://github.com/BosTheCoder/demo-tools && cd demo-tools
uv tool install --editable .

# …or the published version, if you just want to use it:
uv tool install git+https://github.com/BosTheCoder/demo-tools

# Then, from anywhere:
demo-init scaffold <stack> <name>
cd <name>
just dev          # local docker compose
just deploy       # ship to Fly + ensure cert
```

Run `demo-init` with no arguments to see the six stacks listed below, with example invocations.

> Want to run without a global install? See [Running a local copy](#running-a-local-copy) for the `uv run` and snapshot options, plus editable-install caveats.

---

## Stack reference

| Stack            | Port      | Storage                    | Generator                                            |
| ---------------- | --------- | -------------------------- | ---------------------------------------------------- |
| `nextjs`         | 3000      | none (opt-in Postgres)     | `create-next-app` + Tailwind, single Fly app         |
| `nextjs-fastapi` | 3000/8000 | SQLite + volume on api     | `create-next-app` (web) + FastAPI starter (api)      |
| `fastapi`        | 8000      | SQLite + volume            | Minimal FastAPI starter, uvicorn entrypoint          |
| `streamlit`      | 8501      | SQLite + volume            | Minimal Streamlit starter                            |
| `static`         | 80        | none                       | `create-vite` (React + TS) → multi-stage nginx       |
| `bare`           | any       | none                       | Empty `app/`, you (or Claude) write the Dockerfile   |

`nextjs-fastapi` deploys as two apps: `<name>-web` (public, Next.js) and `<name>-api` (`.internal` only, FastAPI). The web app gets the public hostname; the api is reachable from web at `http://<name>-api.internal:8000`.

---

## Installable on a phone (PWA)

Every scaffolded demo is installable by default — open it on a phone, **Add to Home Screen**, and it launches full-screen with its own icon. A demo you can only reach by pasting a URL is a demo you don't open.

Scaffolding writes a manifest, a service worker, and a set of icons. Icons are **generated**, not shipped: a monogram of the app's first letter on a colour derived from its name, so a row of installed demos is distinguishable at a glance. No image dependency — the PNGs are written with `zlib` and `struct`.

| Stack            | Installable | How                                                            |
| ---------------- | ----------- | -------------------------------------------------------------- |
| `fastapi`        | yes         | app shell + manifest/worker routes at the app root              |
| `static`         | yes         | assets in `public/`, tags injected into Vite's `index.html`     |
| `nextjs`         | yes         | App Router file conventions (`manifest.webmanifest`, `apple-icon.png`) |
| `nextjs-fastapi` | yes         | same as `nextjs`, on the web half                               |
| `streamlit`      | no          | Streamlit owns the document head; there is no supported hook    |
| `bare`           | no          | there is no app yet — call `pwa.write_assets()` once there is   |

Two details are load-bearing and handled once in `pwa.py` rather than per stack:

- **Scope.** A service worker can only control URLs at or below the path it was served from. These apps run at `/` on Fly and under `/<name>` behind the local Tailscale proxy, so the worker derives every URL from `self.registration.scope` and the FastAPI manifest keeps `{{ROOT_PATH}}` as a placeholder substituted per request. A worker served from `/static/` could never control the pages it exists to cache.
- **Caching.** Demo data changes constantly, so `/api/` is never cached and page loads are network-first. The cached shell is an offline fallback, not a speed trick — a stale demo that looks live is worse than one that plainly failed.

The Next.js stacks get a manifest and icons but no service worker: that is enough for the install prompt, and registering one from the App Router needs a client component the scaffolder has no business injecting.

---

## Profiles: demo vs service

Every demo is scaffolded under a **profile** that bundles its Fly auto-stop economics. Pass `--profile <demo|service>` at scaffold or adopt time:

| Profile   | `auto_stop_machines` | `min_machines_running` | When to use                              |
| --------- | -------------------- | ---------------------- | ---------------------------------------- |
| `demo`    | `"stop"`             | `0`                    | Throwaway demos. Default. ~$0 when idle. |
| `service` | `"off"`              | `1`                    | Long-running apps (portfolio, internal). |

```bash
# Throwaway demo (default)
demo-init scaffold static my-experiment

# Always-on service
demo-init scaffold static my-portfolio --profile service

# Adopt an existing always-on Fly app
cd my-existing-service && demo-init adopt --profile service
```

`just sync` reads the profile from `.demo-template-version`, so flipping profiles after the fact means editing that file (or re-running adopt). App-specific build args (e.g. `[build.args] VITE_*`) are *not* part of the profile — keep them in your generated `fly.toml`; Copier's three-way merge leaves them alone.

---

## Deploy targets: Fly vs local

Every demo can ship to one of two **targets**. Fly is the default (cloud, public URL). `local` runs the app as a persistent, always-on container on **your own machine** and exposes it over **Tailscale HTTPS** — tailnet-only, costs nothing, and the data never leaves your disk.

```bash
# Cloud (default) — public on Fly
demo-init scaffold fastapi job-tracker

# Always-on container on this machine, reachable over Tailscale
demo-init scaffold fastapi job-tracker --target local
cd job-tracker && just deploy
# → https://bos-desktop.fish-grouper.ts.net/job-tracker
```

The app image, `Dockerfile`, and app code are **identical** across targets. The only difference is one env var — `ROOT_PATH` — which is empty on Fly (served at `/`) and `/<name>` on local. `ROOT_PATH` keeps `request.url_for(...)` / `request.scope["root_path"]`-built URLs prefixed so the same code works on both. Note: `tailscale serve --set-path /<name>` **strips** the prefix before proxying, so the app runs uvicorn with `--proxy-headers` (so `url_for` emits `https://`, not mixed-content `http://`) and serves static via a route rather than a `StaticFiles` mount (a mount only matches the full, unstripped path).

Both `infra/fly/` and `infra/local/` are generated into **every** project, so switching is one value: edit `target:` in `.demo-template-version` (or `DEMO_TARGET=fly just deploy` for a one-off), then `just deploy`. The same `just` verbs dispatch to whichever target is active — no `-local` variants.

| `just <verb>` | Fly | `local` |
| ------------- | --- | ------- |
| `deploy`  | create app, deploy, cert | `docker compose up -d --build` + register `tailscale serve --set-path /<name>` |
| `stop` / `start` | stop / start machines | stop / start the container |
| `destroy` | destroy app + cert | unregister the serve path + `compose down` (**keeps** `./data`) |
| `status`  | Fly status + URLs | container state + the tailnet path URL + data dir |
| `secret KEY=VAL` | `fly secrets set` | upsert into a gitignored `.env` |
| `db-create` | provision Fly Postgres | N/A — local uses file-based SQLite in `./data` |

**What local requires** (this target only works on Bos-Desktop):

- **Docker Desktop** (WSL2 backend) set to *"Start Docker Desktop when you sign in"* — its `restart: unless-stopped` policy brings the container back after a reboot.
- **Tailscale** running on the Windows host (it starts as a service, pre-login) with HTTPS certificates enabled.
- The shared landing page at `/` must already be served (done when the Tailscale HTTPS services were first set up).

**Admin (UAC) is one-time per app.** Registering a Tailscale serve path needs Windows local admin, so the **first** `just deploy` of an app pops one UAC prompt (approve it). Serve config persists, so every deploy/stop/start after that needs **no** admin — `deploy` detects the existing mount and skips the registration. `just destroy` pops one UAC to deregister. (There's no non-admin serve on Windows; if you decline the prompt, `deploy` prints the exact elevated command to run.)

**Accepted caveat — reboot before login.** Docker Desktop starts only *after* you sign in to Windows. Until then the container is down and the `/<name>` path returns **502** (Tailscale itself is up). This is by design, not a bug.

### Graduating local → Fly (and migrating data)

Because both infra sets always exist, moving a local app to Fly is a flip plus a data copy:

1. Set `target: fly` in `.demo-template-version` (or `DEMO_TARGET=fly just deploy` once).
2. `just deploy` — deploys to Fly, serving at the root of its own hostname. `ROOT_PATH` is empty there, so URLs that were built from `root_path` follow automatically. No app edits.
3. Migrate the SQLite file (manual — do it while the app is stopped to avoid a torn copy):
   ```bash
   # local → Fly
   fly ssh sftp shell -a <name>          # then put ./data/<db>.sqlite into /data
   # Fly → local
   fly ssh sftp get /data/<db>.sqlite ./data/<db>.sqlite && just deploy
   ```

---

## Day-to-day commands

Each scaffolded demo ships with a `justfile` that wraps the platform calls. From inside a demo directory. The table below describes the default **Fly** target; under `--target local` the same verbs act on the local container + Tailscale serve instead — see [Deploy targets: Fly vs local](#deploy-targets-fly-vs-local).

| `just <verb>`           | What it does                                                            |
| ----------------------- | ----------------------------------------------------------------------- |
| `just dev`              | `docker compose up` for local development                               |
| `just build`            | Sanity-check the Docker image locally                                   |
| `just deploy`           | Create the Fly app if needed, deploy, ensure TLS cert                   |
| `just stop`             | Stop all machines (billing → ~$0)                                       |
| `just start`            | Restart machines (~5s warm-up)                                          |
| `just destroy`          | Destroy the Fly app + cert (with confirmation)                          |
| `just logs`             | Tail Fly logs                                                           |
| `just ssh`              | SSH into a running machine                                              |
| `just status`           | Print Fly status + public URLs                                          |
| `just open`             | Open the demo URL in your browser                                       |
| `just secret KEY=VAL`   | Set a Fly secret                                                        |
| `just db-create`        | Provision managed Fly Postgres (stateful stacks only)                   |
| `just sync`             | Pull latest template improvements via `copier update`                   |

---

## Adopt an existing dockerized repo

Got a project with a working `Dockerfile`? Get the same `just deploy` ergonomics without rewriting anything:

```bash
cd my-existing-app
demo-init adopt
just deploy
```

`adopt` auto-detects the stack from `package.json` / `requirements.txt` / `pyproject.toml` and overlays only the missing infra files (`justfile`, `fly.toml`, `infra/fly/*.sh`, `.demo-template-version`). Your `Dockerfile`, app code, and dependencies are preserved.

---

## Manage your fleet

The `demo` CLI works across every demo you've shipped:

```bash
demo list                            # rich table of all demos with URLs and status
demo prune --older-than 14d          # interactive cleanup (per-item y/N)
demo prune --older-than 14d --dry-run # list candidates, destroy nothing
demo prune --older-than 14d --yes    # non-interactive
```

---

## MCP server

Expose every `demo-tools` command to an MCP client (e.g. Claude Code). Each CLI
command is reflected into a tool automatically — add a new command and it shows up
as a tool with no extra wiring.

```bash
# Install with MCP support
uv tool install --editable ".[mcp]"

# Register with Claude Code (stdio). Either form works — execution does not
# depend on the console scripts being on PATH:
claude mcp add demo-tools -- demo-mcp
# …or run straight from a clone, no install needed:
claude mcp add demo-tools -- uv run --directory /path/to/demo-tools demo-mcp
```

`demo.prune` is dry-run by default over MCP; destruction requires explicitly
passing `dry_run: false` and `yes: true`. It is flagged destructive so the client
asks before running it.

---

## Architecture

Two-layer model — clean boundary between what the upstream scaffolders own and what we own:

```
┌──────────────────────────────────────────────────────────────┐
│  App layer                                                   │
│  Maintained by upstream scaffolders. We never touch it.      │ ← create-next-app, create-vite,
│                                                              │   our own FastAPI / Streamlit starters
├──────────────────────────────────────────────────────────────┤
│  Infra overlay (this repo)                                   │
│  Dockerfile + fly.toml + compose.yml + justfile +            │ ← Copier template, swappable per target
│  infra/fly/*.sh + infra/local/*.sh                           │
└──────────────────────────────────────────────────────────────┘
```

**One deliberate exception to "we never touch the app layer":** PWA installability needs assets *inside* the app. Scaffolding adds files to `public/` or `src/app/` and inserts link tags into Vite's `index.html`. It is kept to additions the upstream scaffolders don't own — the Next.js stacks use App Router file conventions rather than patching the generated `layout.tsx`, because a regex edit on somebody else's output breaks silently on their next release. The `index.html` insert is guarded and idempotent.

The `justfile` dispatches every verb to `infra/<target>/<verb>.sh`, where `<target>` is `DEMO_TARGET` (baked at scaffold time from the `target` answer, overridable per-run). Two targets ship today — `fly` and `local` (see [Deploy targets](#deploy-targets-fly-vs-local)). To add another later (e.g. Hetzner + Coolify, or self-hosted k3s), drop a sibling `infra/<target>/` directory with the same script names and set `DEMO_TARGET=<target>`. The `justfile`, `Dockerfile`, and app code are target-portable.

---

## Cost expectations on Fly.io

| Scenario                                   | Approx. monthly cost |
| ------------------------------------------ | -------------------- |
| Mostly auto-stopped, 0–1 always-warm       | ~$2–5                |
| 2 always-warm + ~25 auto-stopped           | ~$8–15               |
| 5+ always-warm                             | ~$20–30 (consider graduating to a Hetzner box) |

DNS, TLS certificates, and `.fly.dev` URLs all cost $0. Volumes bill while they exist (1 GB ≈ $0.15/mo).

---

## DNS automation (Cloudflare)

Each Fly app gets its own dedicated IPs, so a single wildcard `*.demos` record can't validate certs for multiple apps. Two options for the `<name>.demos.<domain>` URLs:

**Recommended — Cloudflare DNS API automation.** `just deploy` will create per-app A + AAAA records automatically before validating the cert.

1. Add your domain to a Cloudflare account (free plan is fine) and switch nameservers at your registrar to Cloudflare's pair.
2. Create an API token at [dash.cloudflare.com/profile/api-tokens](https://dash.cloudflare.com/profile/api-tokens) with permission **Zone → DNS → Edit** scoped to the specific zone.
3. Export the token in your shell — `~/.env` (sourced from `~/.zshrc`) is the typical pattern:
   ```bash
   export CLOUDFLARE_API_TOKEN="<your-token>"
   ```
   For multi-machine setups, wrap with a secret manager — e.g. Bitwarden Secrets Manager: `bws run -- just deploy` injects all project secrets at deploy time.

4. From here, `just deploy` upserts the right records on every deploy. Tear-downs leave the records in place — destroyed apps free up their hostnames automatically when DNS resolves to nothing.

**Manual fallback.** If you skip the Cloudflare step, the deploy still succeeds — the cert just enters "awaiting_configuration" until you add A/AAAA records pointing `<name>.demos.<domain>` at the IPs from `fly ips list -a <name>`.

---

## Auto-deploy on push (GitHub Actions)

Every scaffold ships a `.github/workflows/fly-deploy.yml` workflow that redeploys to Fly on every push to `main`.

**Per-demo setup (one-time after pushing to GitHub):**
```bash
gh repo create my-demo --public --source=. --push
gh secret set FLY_API_TOKEN -b "$(fly auth token)"
# optional, if you use the Cloudflare DNS automation:
gh secret set CLOUDFLARE_API_TOKEN -b "$CLOUDFLARE_API_TOKEN"
```

**To disable auto-deploy** for a specific demo, delete the workflow file:
```bash
rm .github/workflows/fly-deploy.yml
git commit -am "disable auto-deploy" && git push
```

The workflow runs `just deploy` under the hood, so it picks up the same `fly apps create` + `fly deploy` + Cloudflare DNS + cert-add logic as your local invocations.

---

## Development

```bash
git clone https://github.com/BosTheCoder/demo-tools
cd demo-tools

uv sync                               # install dev deps
uv run pytest                         # 77 tests, ~10s
```

### Running a local copy

The `uv tool install git+https://…` in the quick start snapshots a published
commit — it does **not** see local edits. To exercise your working tree, pick
the mode that matches what you're doing:

| Use case | Command | Reflects local edits? |
| -------- | ------- | --------------------- |
| **Iterating / testing changes** (recommended) | `uv run demo-init scaffold static foo` | Always — runs straight from source via the project venv + `uv.lock`. Nothing installed globally. |
| **Using the tool day-to-day while tweaking it** | `uv tool install --editable .` | Live, for `.py` code *and* the bundled `_data/` templates/starters (their paths resolve relative to the source file). Reinstall only when **dependencies**, **entry points**, or the **Python constraint** change. |
| **Pinning a local snapshot** | `uv tool install --reinstall --from . demo-tools` | No — freezes current state; re-run with `--reinstall` to update. |

For most development `uv run` is cleanest: it always reflects your working tree
with zero global side effects. Use `--editable` when you want the real `demo` /
`demo-init` commands on your `PATH` while iterating.

Two caveats:

- **An editable install couples your global commands to your working tree.**
  Leave the repo mid-edit in a broken state and your global `demo` /
  `demo-init` break too. `uv run` avoids this.
- **`just sync` / `copier update` in generated demos always fetch the template
  from GitHub** (`TEMPLATE_GIT_URL` in `_resources.py`), not your local edits.
  Initial scaffolding uses the bundled local templates, so an editable install
  lets you test *scaffolding* against local template changes — but to test the
  *update* flow you must push to GitHub first.

The Copier template lives at `src/demo_tools/_data/template/`. Stack-specific scaffolders live at `src/demo_tools/stacks/`. Tests are pytest with `subprocess.run` mocked for npx/npm calls so they're fast and offline.

---

## Design notes

The full design spec — including alternatives considered (Render, Railway, Coolify on a VPS), why dual-app for `nextjs-fastapi`, how the Copier `_tasks` cleanup works — lives in the companion `tasks` repo:

```
2026-04-29-demo-deployment-template/
  design.md             # 9 sections, ~3k words
  plan.md               # 30-task implementation plan, all done
  fly-cheatsheet.md     # common fly commands you'll need
```

---

## License

No formal license declared. Treat as source-available for personal use; open an issue if you want to use it commercially.

---

<div align="center">
<sub>Built with <a href="https://typer.tiangolo.com/">Typer</a>, <a href="https://copier.readthedocs.io/">Copier</a>, and <a href="https://fly.io">Fly.io</a>.</sub>
</div>
