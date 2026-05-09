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
demo-init nextjs chord-detector
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
uv tool install git+https://github.com/BosTheCoder/demo-tools

demo-init <stack> <name>
cd <name>
just dev          # local docker compose
just deploy       # ship to Fly + ensure cert
```

Run `demo-init` with no arguments to see the six stacks listed below, with example invocations.

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

## Day-to-day commands

Each scaffolded demo ships with a `justfile` that wraps the platform calls. From inside a demo directory:

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
demo prune --older-than 14d --yes    # non-interactive
```

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
│  Dockerfile + fly.toml + compose.yml + justfile +            │ ← Copier template, swappable per platform
│  infra/fly/*.sh                                              │
└──────────────────────────────────────────────────────────────┘
```

To switch deploy platforms later (e.g. Hetzner + Coolify, or self-hosted k3s), drop a sibling `infra/<platform>/` directory with the same script names and set `DEMO_PLATFORM=<platform>`. The `justfile`, `Dockerfile`, and app code are platform-portable.

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
3. Export the token in your shell:
   ```bash
   export CLOUDFLARE_API_TOKEN="your-token-here"
   ```
   (Persist by adding it to `~/.zshrc` / `~/.bashrc`.)
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
uv run pytest                         # 58 tests, ~5s

# install your local copy as the live `demo-init` / `demo` binaries:
uv tool install --reinstall --from . demo-tools
```

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
