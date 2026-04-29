# demo-tools

CLI + Copier template for spinning up demo web apps and deploying them to Fly.io.

Each demo gets:
- A `<name>.fly.dev` URL automatically (free, always works)
- A `<name>.demos.buildwithbos.com` URL with TLS (after a one-time wildcard DNS setup)
- Auto-stop billing — idle demos cost ~$0
- A unified `justfile` for `dev`, `deploy`, `stop`, `start`, `destroy`, `logs`, `sync`

## One-time setup

```bash
# Install uv (if needed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install Fly CLI and sign up
curl -L https://fly.io/install.sh | sh
fly auth signup

# Install demo-tools
uv tool install git+https://github.com/BosTheCoder/demo-tools

# After your first deploy, in Namecheap → Advanced DNS, add:
#   *.demos    A     <Fly IPv4 from `fly ips list -a <any-app>`>
#   *.demos    AAAA  <Fly IPv6>
# That covers every future demo's <name>.demos.buildwithbos.com host.
```

## Scaffold a new demo

```bash
demo-init <stack> <name>            # six stacks (see table below)
cd <name>
just dev                            # local docker compose
just deploy                         # ship to Fly + ensure cert
```

Example:

```bash
demo-init nextjs chord-detector
cd chord-detector
just dev          # iterate locally
just deploy       # live at chord-detector.fly.dev + chord-detector.demos.buildwithbos.com
```

## Adopt an existing dockerized repo

If you already have a Docker-based project and want the same `just deploy`/`just stop` ergonomics:

```bash
cd existing-repo
demo-init adopt
just deploy
```

`adopt` mode auto-detects the stack from `package.json`/`requirements.txt` and overlays only the missing infra files (justfile, fly.toml, infra/fly/*.sh, .demo-template-version). Your existing Dockerfile, app code, and dependencies are preserved.

## Manage your fleet

```bash
demo list                           # rich table of all demos and URLs
demo prune --older-than 14d         # interactive cleanup; per-item y/N
demo prune --older-than 14d --yes   # non-interactive (skip prompts)
```

## Pull infra updates into existing demos

```bash
cd my-demo
just sync                           # runs `copier update` under the hood
```

Three-way merges new template improvements onto your demo without touching app code. Conflicts (rare — only if you edited an infra file) are surfaced like a git merge conflict.

## Day-to-day demo operations

| Command | What it does |
|---|---|
| `just dev` | `docker compose up` for local dev |
| `just build` | `docker build` to sanity-check the image |
| `just deploy` | `fly deploy` + ensure TLS cert for `<name>.demos.buildwithbos.com` |
| `just stop` | Stop machines — billing → ~$0 |
| `just start` | Restart machines (~5s warm-up) |
| `just destroy` | Destroy the Fly app + cert (with confirmation) |
| `just logs` | Tail Fly logs |
| `just ssh` | SSH into a running machine |
| `just status` | Print Fly status + public URLs |
| `just open` | Open browser to the demo URL |
| `just secret KEY=VAL` | Set a Fly secret |
| `just db-create` | Provision Fly Postgres (stateful stacks only) |

## Stack reference

| Stack | Default port | DB | Notes |
|---|---|---|---|
| `nextjs` | 3000 | none (opt-in via `just db-create`) | Single Fly app. `npx create-next-app` under the hood. |
| `nextjs-fastapi` | 3000 / 8000 | SQLite + Fly volume on api | Two Fly apps: `<name>-web` (public) + `<name>-api` (`.internal` only). |
| `fastapi` | 8000 | SQLite + Fly volume | Single Fly app. Minimal FastAPI starter. |
| `streamlit` | 8501 | SQLite + Fly volume | Single Fly app. Minimal Streamlit starter. |
| `static` | 80 | none | Multi-stage Vite build → nginx serves the dist/. |
| `bare` | configurable | none | Empty `app/` for ad-hoc stacks; you (or Claude) write the Dockerfile. |

## Architecture

Two-layer model:

```
┌────────────────────────────────────────────┐
│  App layer                                 │
│  Maintained by upstream scaffolders        │  ← create-next-app, degit,
│  We never touch it post-scaffold           │     vite, our own starters
├────────────────────────────────────────────┤
│  Infra overlay (this repo)                 │
│  Dockerfile + fly.toml + compose.yml +     │  ← Copier template,
│  justfile + infra/fly/*.sh                 │     swappable per platform
└────────────────────────────────────────────┘
```

To switch deploy platforms later (e.g. Hetzner + Coolify), drop a sibling `infra/<platform>/` directory with the same script names. The justfile, Dockerfile, and app code are platform-portable.

## Cost expectations on Fly.io

| Scenario | Approx. monthly cost |
|---|---|
| Mostly auto-stopped, 0–1 always-warm | ~$2–5 |
| 2 always-warm + ~25 auto-stopped | ~$8–15 |
| 5+ always-warm | ~$20–30 (consider graduating to a Hetzner box at this point) |

DNS, TLS certificates, `.fly.dev` URLs all cost $0.

## Design

Full design spec lives in the companion `tasks` repo at `2026-04-29-demo-deployment-template/`.

## License

Personal project — no formal license declared.
