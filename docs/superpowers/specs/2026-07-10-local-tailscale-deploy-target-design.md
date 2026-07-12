# demo-tools: local / Tailscale deploy target — design

**Date:** 2026-07-10
**Status:** Implemented + smoke-tested on Bos-Desktop 2026-07-12 (path-based routing per Kelvin,
2026-07-10 — see §12). **Correction:** the "no admin for path serves" assumption was **false** —
Tailscale 1.98.2 requires Windows local admin for *every* serve-config write (path AND own-port,
verified empirically). The feature accommodates this: `deploy` skips the serve write when the path
is already registered (everyday re-deploys need no admin) and elevates via a UAC prompt only on a
**first-time** registration or `destroy`. See §4.3, §6, §9, §12. **Second correction (2026-07-12):**
the "Tailscale forwards the path unstripped" claim throughout this doc was also **false** —
`tailscale serve --set-path /<name> <port>` **STRIPS** the `/<name>` prefix before proxying; the
container receives `/healthz`, `/static/app.css`, etc, never `/<name>/healthz`. This was confirmed
empirically on Bos-Desktop and broke a real deployed app two ways: (1) uvicorn without
`--proxy-headers` doesn't see `X-Forwarded-Proto: https`, so `url_for()` emits `http://` links that
browsers block as mixed content on the `https://` page; (2) a `StaticFiles` Mount only matches the
full `/<name>/static/...` path, so the stripped `/static/...` request 404s. The fix: keep
`root_path=/<name>` for URL *generation* only, run uvicorn with `--proxy-headers
--forwarded-allow-ips=*`, and serve static assets via a route, not a Mount. See §1, §4.3, §5.4.
**Author:** design session (implementer has NOT seen the originating conversation — this doc is self-contained)

---

## 1. Context & problem

`demo-tools` is a Copier-based CLI (`demo-init`) that scaffolds Dockerized web apps and ships
them to **Fly.io** via `just` recipes. Today **every deploy target is Fly**:

- `src/demo_tools/_data/template/infra/fly/*.sh.jinja` — one small script per operation.
- `fly.toml.jinja` — the Fly app config.
- `compose.yml.jinja` — used only by `just dev` (foreground local dev) and `just build`.
- A `--profile demo|service` choice that only tweaks Fly auto-stop economics
  (`auto_stop_machines`, `min_machines_running`) in `fly.toml`.
- The `justfile` already dispatches per-platform:
  `PLATFORM := env_var_or_default("DEMO_PLATFORM", "fly")` → `bash infra/{{PLATFORM}}/<verb>.sh`.
  The README's Architecture section explicitly documents this seam:
  *"drop a sibling `infra/<platform>/` directory with the same script names and set
  `DEMO_PLATFORM=<platform>`."*

There is **no persistent, always-on, self-hosted target**. `just dev` runs the app in the
foreground and dies when you Ctrl-C; nothing survives a reboot; nothing is reachable off the
machine.

**What Kelvin wants:** a **`local` deploy target** — run the app as a **persistent, always-on
container on his own machine (Bos-Desktop)** and expose it over **Tailscale HTTPS** instead of
Fly. It costs nothing, and the data stays on his machine. **Fly remains the graduation path:**
when he later wants others to access/edit, he flips the target and `just deploy`s to Fly. Local
and Fly must coexist cleanly in the same generated project.

**The downstream driver (design the interface to serve this):** the first real consumer is a
**job-application platform** — a `fastapi`-stack app: SQLite on a local data dir + a phone-first
HTMX approval UI, reached from his phone over Tailscale. Local hosting keeps sensitive PII (home
address, EEO demographics, salary, application history) entirely on his machine. So the local
target must comfortably host an always-on `fastapi` service with a **persistent SQLite
bind-mount** and be **reachable from his phone over Tailscale**.

### Runtime facts verified on Bos-Desktop (2026-07-10)

These are load-bearing — the mechanism below is built on them:

- **Docker:** Docker **Desktop** (WSL2 backend), server v28.3.0. `docker` in WSL talks to the
  Docker Desktop engine. **Docker Desktop publishes container ports to the Windows host's
  `localhost`** — a `-p 8000:8000` container is reachable at `127.0.0.1:8000` on *both* WSL and
  the Windows host. This is the linchpin (see §5.2).
- **Tailscale:** installed on **Windows only** at `C:\Program Files\Tailscale\tailscale.exe`
  (`/mnt/c/Program Files/Tailscale/tailscale.exe` from WSL). There is **no Linux tailscaled in
  WSL**. Tailscale runs as a Windows service (starts at boot, before user login).
- **Tailnet:** `fish-grouper.ts.net`. The Windows host's MagicDNS name is
  **`bos-desktop.fish-grouper.ts.net`**. HTTPS Certificates are enabled in the admin console
  (Let's Encrypt certs for the `*.ts.net` name — no browser warnings).
- **Existing serve setup** (task `2026-06-25-tailscale-https-services`) — the convention this
  feature extends: a **path-based reverse proxy under the single shared host** —
  `…/` → a static landing page, `…/calibre` → `127.0.0.1:8080`. The working per-service
  invocation is `tailscale serve --bg --set-path /calibre 8080` (a **port proxy under a path** —
  **no admin**). The **only** step that needed one-time Windows admin (UAC) was serving the
  landing page's *filesystem path* at `/`; that is a shared-host prerequisite already completed.
  **Tailscale STRIPS the path prefix** before proxying (confirmed empirically 2026-07-12) — the
  backend receives `/...` requests with `/calibre` already removed. This is exactly why the app
  must be base-path aware for URL *generation* (see §5.4) even though incoming routing needs no
  change. Serve config persists in `tailscaled` state across reboots.

---

## 2. Goals / non-goals

### Goals

1. A `local` deploy target that runs the app as an **always-on container** on Bos-Desktop,
   surviving host reboot, exposed over **Tailscale HTTPS** (tailnet-only), **path-based under the
   shared host** — `https://bos-desktop.fish-grouper.ts.net/<name>` — matching Kelvin's existing
   landing-page/Calibre convention.
2. **Clean interface** (the primary quality bar — see §4): the local target reuses the existing
   `just` verb surface via target dispatch; no parallel verb set; no Fly-isms leaking into
   local-mode output.
3. **Persistent SQLite** via a bind-mount to a local `./data` dir (data visible + backup-able on
   the host, gitignored).
4. **Fly stays 100% backward-compatible** — existing projects and tests are unaffected; `target`
   defaults to `fly`.
5. **Clean coexistence + graduation:** both `infra/fly/` and `infra/local/` are generated into
   every project; switching target is flipping one value, then `just deploy`. The base-path env
   var (§5.4) makes local (`/<name>`) and Fly (root) work with **identical app code**.
6. Reachable from Kelvin's phone over Tailscale with a **real HTTPS cert** (no warnings, so HTMX
   / service-worker / PWA features work).

### Non-goals

- **No multi-machine / clustering.** Single host (Bos-Desktop) only.
- **No auth layer.** The trust boundary *is* the tailnet — Tailscale Serve (not Funnel) means
  only Kelvin's devices can reach it. No public exposure, no login page.
- **No Funnel** (public internet). Serve only.
- **No automated data migration** between local and Fly (documented manual steps only — §7).
- **No changes to app code or Dockerfiles per-target beyond one env-driven base path** — app code
  and `Dockerfile` are **identical** across targets; only infra + the value of the `ROOT_PATH`
  env var differ (see §5.4, §8).
- **No boot-before-login always-on.** Accepted: Docker Desktop only starts after Windows sign-in,
  so the container (and thus the `/<name>` backend) is down until Kelvin logs in — Tailscale
  returns 502 in that window. This is an accepted limitation, not a bug (§6).
- **No new always-on daemon** on the host beyond Docker Desktop + Tailscale (both already run).

---

## 3. Solution overview

```
 Kelvin's phone ──HTTPS──►  bos-desktop.fish-grouper.ts.net/<name>/...
 (on the tailnet)                       │
                          Tailscale (Windows service)   tailscale serve --bg --set-path /<name> <internal_port>
                                        │  proxies /<name>/... to 127.0.0.1:<internal_port>/...  (prefix STRIPPED)
                          Docker Desktop published port (Windows localhost)
                                        │
                          app container  (restart: unless-stopped)  FastAPI(root_path="/<name>") listens 0.0.0.0:<internal_port>
                                        │
                          ./data  ──bind-mount──►  /data   (SQLite lives here, persists on host)
```

- Same app image and `Dockerfile` as Fly. The **only** app-visible difference is the `ROOT_PATH`
  env var: `""` on Fly (served at root), `"/<name>"` on local (served under the path prefix).
- `docker compose` (base + a `compose.local.yml` overlay adding `restart: unless-stopped`, the
  `./data` bind-mount, and `ROOT_PATH=/<name>`) runs the container detached.
- `tailscale serve --set-path /<name>` on the Windows host proxies the shared HTTPS host's
  `/<name>` path to the container's published port.
- The `local` target's `just` verbs wrap exactly these two systems (compose + tailscale serve).

---

## 4. Interface design (the centerpiece)

Kelvin's explicit ask: apply **CLEAN code principles to the interface**. Three decisions, each
justified.

### 4.1 Same verbs, dispatch on target (NOT a parallel `*-local` set)

**Decision: reuse the existing verb surface and dispatch on the chosen target.** The justfile
already does this for platforms (`DEMO_PLATFORM` → `infra/<platform>/<verb>.sh`). `local` is
simply another target directory `infra/local/` with the **same script names** as `infra/fly/`.

**Rejected alternative — a parallel `deploy-local` / `stop-local` / … set.** It doubles the verb
count (18 instead of 9), forces the user to remember which suffix they're in, and duplicates the
help text. The single-verb-dispatch model is the repo's established pattern and the CLEAN choice:
each verb has **one responsibility** ("deploy the app", "show status") and the *target* decides
*how*. The trade-off it accepts — you can't act on both targets in one command — is a
non-problem: an app is deployed to exactly one place at a time.

**Rename the dispatch variable `DEMO_PLATFORM` → `DEMO_TARGET`** (and Just var `PLATFORM` →
`TARGET`). "Target" is the user-facing noun in the Copier question and README; "platform" was
Fly-era vocabulary. The default is baked at scaffold time from the `target` answer (see §4.4),
with the env var as an escape hatch for one-off overrides:

```makefile
# generated justfile (justfile.jinja) — top of file
set shell := ["bash", "-cu"]

# Deploy target, baked at scaffold time. Override for one run: DEMO_TARGET=fly just deploy
TARGET := env_var_or_default("DEMO_TARGET", "{{ target }}")
```

Every dispatching recipe is unchanged except the variable name:

```makefile
# Deploy to the configured target (Fly, or a local Tailscale-exposed container)
deploy:
    bash infra/{{TARGET}}/deploy.sh

stop:    bash infra/{{TARGET}}/stop.sh
start:   bash infra/{{TARGET}}/start.sh
destroy: bash infra/{{TARGET}}/destroy.sh
logs:    bash infra/{{TARGET}}/logs.sh
ssh:     bash infra/{{TARGET}}/ssh.sh
status:  bash infra/{{TARGET}}/status.sh
open:    bash infra/{{TARGET}}/open.sh
secret KV:  bash infra/{{TARGET}}/secret.sh "{{KV}}"
db-create:  bash infra/{{TARGET}}/db-create.sh

# target-agnostic — unchanged
dev:   docker compose up
build: docker compose build
sync:  uvx copier update --answers-file .demo-template-version --trust
```

> **Implementation note — Jinja vs Just `{{ }}` collision.** `justfile` is currently *not*
> rendered by Copier (Copier's `_templates_suffix` defaults to `.jinja`, so only `*.jinja` files
> are templated; today's plain `justfile` is copied verbatim, and `{{PLATFORM}}`/`{{KV}}` are
> Just's own interpolation). To bake the `target` default in, rename it to **`justfile.jinja`**
> and wrap everything *except* the one `TARGET :=` default line in `{% raw %}…{% endraw %}` so
> Just's `{{TARGET}}` / `{{KV}}` pass through untouched. Exactly one Jinja interpolation in the
> whole file (`"{{ target }}"`); the rest is raw. This keeps the justfile readable — the CLEAN
> spirit — with no `{{ '{{' }}` escaping soup.

**Verb-by-verb semantics for `local`** (each script does one thing; no Fly vocabulary in output):

| Verb | Fly behaviour | `local` behaviour | Output must NOT say |
|------|---------------|-------------------|---------------------|
| `deploy` | create app, `fly deploy`, cert | `docker compose … up -d --build` **then** register `tailscale serve --set-path /<name>`; print the tailnet path URL | "machines", "cert" |
| `stop` | `fly machines stop` | `docker compose … stop` (container down; the `/<name>` path stays registered but returns 502 until start) | "billing → \$0" |
| `start` | `fly machines start` | `docker compose … start` | "machines" |
| `destroy` | destroy Fly app + cert (confirm) | confirm → `tailscale serve --set-path /<name> off` + `docker compose … down` (**keeps** the `./data` dir); tell the user where the data still is and how to delete it | "cert", "machines" |
| `logs` | `fly logs` | `docker compose … logs -f` | — |
| `ssh` | `fly ssh console` | `docker compose … exec <svc> sh` (shell in the running container) | "machine" |
| `status` | `fly status` + URLs | `docker compose … ps` + Tailscale serve state for this path + **the real tailnet path URL** + health hint | "machines", "region" |
| `open` | open `https://<name>.<domain>` | `xdg-open` the tailnet path URL | — |
| `secret KEY=VAL` | `fly secrets set` | upsert `KEY=VAL` into a gitignored `.env` that compose reads | "fly secrets" |
| `db-create` | provision Fly Postgres (stateful only) | friendly N/A: "local uses file-based SQLite at ./data — nothing to provision" | "postgres cluster" |

Every verb maps cleanly → **no parallel verb set is needed**, confirming the dispatch model.

### 4.2 No Fly-isms in local output (least surprise)

The `infra/local/*.sh` scripts write **local-appropriate** messaging: "container", "Tailscale
path", "data dir", "this machine" — never "machine(s)", "billing", "region", "cert". `just
status` on a local project prints the actual reachable path URL, e.g.:

```
$ just status
Container:  job-tracker  (running, healthy)
Tailscale:  https://bos-desktop.fish-grouper.ts.net/job-tracker  (serving → 127.0.0.1:8000)
Data dir:   ./data  (SQLite persists here across restarts and reboots)
```

### 4.3 Tailscale routing: path-based under the shared host

**Decision (resolved by Kelvin, 2026-07-10): expose each local app at a PATH prefix under the
shared HTTPS host** — `https://bos-desktop.fish-grouper.ts.net/<name>` — via
`tailscale serve --bg --set-path /<name> <internal_port>`. This matches his existing
landing-page + Calibre convention exactly (same host, same `--set-path` form, same bare-port
argument), so a demo-tools app slots in next to `/calibre` under the same front door.

**Mechanics & consequences:**
- **Exact serve command** (verified against the working Calibre invocation in the
  `2026-06-25-tailscale-https-services` task — do **not** invent alternative flags):
  `tailscale serve --bg --set-path /<name> <internal_port>`. The last argument is a **bare port
  number**, not a URL.
- **Admin IS required to register a serve path (CORRECTED 2026-07-12).** Empirically, Tailscale
  1.98.2 rejects *every* serve-config write from a non-admin context — path serves *and* own-port
  serves alike — with `401: must be a Windows local admin to serve a path`. The pre-existing
  `/calibre` and `/` mounts persist in `tailscaled` state from a one-time elevated registration;
  the earlier "no admin" reading was wrong. **Mitigation (what makes this tolerable):** serve
  config persists across reboots, so an app's path only needs registering **once**. `deploy.sh`
  therefore skips the serve write when `TS_PATH` already maps to `127.0.0.1:<port>`
  (`serve_path_registered`), and elevates via `Start-Process -Verb RunAs` (one UAC) only on the
  first registration. `destroy.sh` elevates once to deregister. Net cost: **one UAC per app
  lifecycle**, zero for everyday re-deploys/stops/starts. (A scheduled-task-triggered-elevated
  design was considered for fully-unattended registration and rejected by Kelvin as too heavy.)
- **Tailscale STRIPS the path prefix** before forwarding (confirmed empirically 2026-07-12). The
  container therefore receives requests at `/...` — never `/<name>/...`. Route decorators need no
  change, but **the app must still be base-path aware for URL generation** (outgoing links,
  redirects, `url_for`) — handled cleanly via one env var (§5.4). This is the single seam that
  makes path-based routing work without per-target app code.
- **Own `/` on Fly, `/<name>` on local** — the `ROOT_PATH` env var (`""` vs `"/<name>"`) is the
  only thing that changes; the app image is identical (§8).

### 4.4 Copier questions (minimize surface; good defaults over knobs)

Add **`target`** plus the two answers path-based routing needs. Compose with the existing
`profile` and `stack` questions as follows.

```yaml
# copier.yml (additions)
target:
  type: str
  help: "Deploy target: fly (cloud) | local (always-on container exposed via Tailscale)"
  choices: [fly, local]
  default: fly            # backward-compatible: existing behaviour unchanged

tailscale_host:
  type: str
  help: "MagicDNS name of the machine that runs the container + Tailscale"
  default: "bos-desktop.fish-grouper.ts.net"
  when: "{{ target == 'local' }}"

tailscale_path:
  type: str
  help: "URL path prefix under the shared Tailscale host (Tailscale STRIPS it before proxying; the app is served here)"
  default: "/{{ name }}"
  when: "{{ target == 'local' }}"
```

- `tailscale_path` defaults to `/{{ name }}` (Copier evaluates the default against the already-set
  `name` answer), so the reachable URL is `https://<tailscale_host><tailscale_path>` =
  `https://bos-desktop.fish-grouper.ts.net/<name>` with zero typing. Override only if you want a
  vanity path or to avoid a clash with an existing serve mount (e.g. `/calibre`).
- **No port question** — path-based routing rides the shared host's single HTTPS listener (443);
  there is no per-app port to allocate. (An own-port design would have needed a
  `tailscale_https_port`; path-based removes that knob entirely.)

**Composition with `profile`:** `profile` (demo/service) *only* tweaks Fly auto-stop economics —
it is **meaningless for local**. Rather than add a conditional, keep writing `profile` into the
answers file (harmless; still governs `fly.toml`, which always exists for graduation) but have
the **CLI ignore `--profile` when `--target local`** and say so. No new interaction between the
questions; `stack` is orthogonal (it picks the app + port + statefulness exactly as today).

**Defaults chosen so the common path needs no flags:**
- `target` defaults to `fly` → every existing invocation and test is unchanged.
- `tailscale_host` defaults to Bos-Desktop's real MagicDNS name (from the verified setup) — the
  only machine this feature targets, so the user never types it.
- `tailscale_path` derives from `name` — the user only overrides it to avoid a path clash.

**CLI surface** (mirrors the existing `--profile` option in `cli.py`):

```
demo-init scaffold fastapi job-tracker --target local
demo-init scaffold fastapi job-tracker --target local --tailscale-path /jobs
demo-init adopt --target local            # overlay local infra onto an existing dockerized repo
```

`--target` threads through `_run_scaffold` → `scaffold_demo` → `run_copy(data=…)` and into the
`.demo-template-version` answers file, exactly like `profile` does today
(`scaffold.py`/`adopt.py`).

### 4.5 Generated file layout — `infra/local/` mirrors `infra/fly/`

Small, single-purpose scripts, same names as Fly so dispatch is symmetric:

```
infra/local/
  _lib.sh.jinja        # shared helpers ONLY — sourced by the others (see below)
  deploy.sh.jinja      # compose up -d --build  +  tailscale serve --set-path  +  print URL
  stop.sh.jinja        # compose stop
  start.sh.jinja       # compose start
  destroy.sh.jinja     # confirm → tailscale serve --set-path /<name> off → compose down (KEEP ./data)
  logs.sh.jinja        # compose logs -f
  ssh.sh.jinja         # compose exec <svc> sh
  status.sh.jinja      # compose ps + serve status + real path URL + health
  open.sh.jinja        # xdg-open the tailnet path URL
  secret.sh.jinja      # upsert KEY=VAL into .env
  db-create.sh.jinja   # friendly N/A (SQLite is file-based)
```

**`_lib.sh` is the single source of truth** for everything the other scripts share — the Tailscale
binary path, the host name, the path prefix, the port, the compose invocation, and the pre-flight
checks. This is the CLEAN "don't repeat the wiring" move; each verb script stays a 3–5 line
wrapper.

```bash
# infra/local/_lib.sh.jinja  (sketch — MANAGED BY demo-tools, DO NOT EDIT)
set -euo pipefail
APP="{{ name }}"
INTERNAL_PORT="{{ internal_port }}"
TS_HOST="{{ tailscale_host }}"
TS_PATH="{{ tailscale_path }}"
URL="https://${TS_HOST}${TS_PATH}"

# base compose + the local overlay (restart policy + bind-mount + ROOT_PATH)
COMPOSE=(docker compose -f compose.yml -f compose.local.yml)
{% if stack == "nextjs-fastapi" %}SVC="web"{% else %}SVC="app"{% endif %}

# Resolve the Windows Tailscale CLI from WSL (interop appends Windows PATH,
# but the space in "Program Files" is safer via the explicit /mnt/c path).
resolve_ts() {
  if [[ -x "/mnt/c/Program Files/Tailscale/tailscale.exe" ]]; then
    TS=("/mnt/c/Program Files/Tailscale/tailscale.exe")
  elif command -v tailscale.exe >/dev/null 2>&1; then
    TS=(tailscale.exe)
  else
    echo "ERROR: Tailscale CLI not found. This target only works on Bos-Desktop." >&2
    exit 1
  fi
}

preflight() {
  resolve_ts
  "${TS[@]}" status >/dev/null 2>&1 || { echo "ERROR: Tailscale is not running on the Windows host." >&2; exit 1; }
  docker info >/dev/null 2>&1 || { echo "ERROR: Docker Desktop is not running." >&2; exit 1; }
}
```

```bash
# infra/local/deploy.sh.jinja  (sketch)
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
preflight
echo "==> Building + starting container (detached)"
"${COMPOSE[@]}" up -d --build
echo "==> Registering Tailscale serve: ${TS_PATH} -> 127.0.0.1:${INTERNAL_PORT}"
# Exact form matches the working Calibre invocation; bare port arg, no admin needed.
"${TS[@]}" serve --bg --set-path "${TS_PATH}" "${INTERNAL_PORT}"
echo; echo "Deployed (tailnet-only):"; echo "  ${URL}"
```

```bash
# infra/local/destroy.sh.jinja  (sketch)
HERE="$(cd "$(dirname "$0")" && pwd)"; source "$HERE/_lib.sh"
read -r -p "Destroy ${APP}? Removes the container and unregisters ${TS_PATH}. [y/N] " ans
case "$ans" in [yY]|[yY][eE][sS]) ;; *) echo "Aborted."; exit 0 ;; esac
resolve_ts
"${TS[@]}" serve --set-path "${TS_PATH}" off || true
"${COMPOSE[@]}" down || true
echo "Done. Your data dir ./data was KEPT (SQLite lives there). Delete it manually with: rm -rf ./data"
```

Reuses the fly scripts' header convention verbatim:
`# MANAGED BY demo-tools — DO NOT EDIT. Run \`just sync\` to update.`

> **Teardown-syntax note:** the `--set-path <path> off` idiom removes a serve mapping and mirrors
> the `--set-path <path> <port>` add form; confirm it against the installed Tailscale version
> during step-0 (§11) since the Calibre task only exercised the *add* path.

### 4.6 Discoverability & least surprise

- `just` with no args lists every verb (unchanged) — the same list works for both targets.
- `just status` prints the **actual** path URL (`https://bos-desktop.fish-grouper.ts.net/<name>`),
  not a guess — the discoverability centrepiece.
- README gains a "Deploy targets: Fly vs local" section (§11 step 11).
- One-time shared-host prerequisite (documented once, not per app): the landing page at `/` must
  already be served (it is — set up with a one-time UAC step in the Calibre task). Adding a
  demo-tools app under `/<name>` needs no further admin.

---

## 5. Architecture / how it works

### 5.1 Compose changes — a local overlay, not edits to the shared file

`compose.yml` is shared by `just dev` (foreground, ephemeral) and, indirectly, the local target.
Putting `restart: unless-stopped` in the base file would make a `just dev` container silently come
back after a reboot — surprising. So add a **new overlay** `compose.local.yml.jinja`, applied only
by the local infra scripts (`docker compose -f compose.yml -f compose.local.yml …`):

```yaml
# compose.local.yml.jinja  (single-app stacks; mirror the dual-app branch for nextjs-fastapi)
services:
  {% if stack == "nextjs-fastapi" %}web{% else %}app{% endif %}:
    restart: unless-stopped
    environment:
      ROOT_PATH: "{{ tailscale_path }}"   # e.g. /job-tracker — the app's base path on local
{% if stateful %}    volumes:
      - ./data:/data          # bind-mount: SQLite lives on the host, backup-able, gitignored
{% endif %}
```

- **Base `compose.yml` is unchanged** except the stateful branch keeps its **named volume**
  `app_data:/data` for `just dev` (unchanged behaviour, existing tests pass). The overlay's
  bind-mount `./data:/data` **wins** for the local target (last `-f` wins for the same key),
  giving host-visible persistence exactly where the driver needs it.
- **`ROOT_PATH` is injected here** (overlay only). On `just dev` and on Fly, `ROOT_PATH` is
  unset/empty, so the app serves at `/`; on local it is `/<name>` (§5.4).
- `restart: unless-stopped` → the container is restarted by the Docker daemon on daemon/host
  start, **unless** it was explicitly `docker compose stop`ped (which `just stop` does — the
  semantics line up: a stopped app stays stopped).
- Add `./data/` to the generated `.gitignore` (the template `.gitignore` already exists — append
  a line under a `# local target` comment; keep the diff surgical).

### 5.2 The WSL ⇄ Windows ⇄ container path (the highest-risk detail)

**Verified mechanism (see §1 runtime facts):**

1. `just deploy` runs in **WSL**, invoking `docker compose` against **Docker Desktop**. The
   container's published port (`-p <internal_port>:<internal_port>`) is bound by Docker Desktop
   on the **Windows host's `localhost`** — this is Docker Desktop's default behaviour, distinct
   from a raw dockerd-in-WSL setup. So `127.0.0.1:<internal_port>` is live **on Windows**.
2. The local infra scripts invoke **`tailscale.exe` (Windows)** from WSL via interop (the
   explicit `/mnt/c/Program Files/Tailscale/tailscale.exe` path, quoted). `tailscale serve
   --set-path /<name> <internal_port>` tells the Windows Tailscale to reverse-proxy the shared
   host's `/<name>` path to **`127.0.0.1:<internal_port>` on Windows** (the `/<name>` prefix is
   **stripped** before proxying) — which Docker Desktop is serving. No WSL localhost-forwarding
   subtlety is involved, because *both* the proxy and the published port live on the Windows
   host's loopback.
3. Tailscale terminates TLS with the tailnet Let's Encrypt cert and serves it on the tailnet at
   `bos-desktop.fish-grouper.ts.net/<name>`.

**Assumption to confirm (§12-Q1):** that Docker Desktop is configured normally (publishing to
host localhost) and not in a mode that binds only inside the WSL distro. In the standard Docker
Desktop + WSL2 configuration this holds; a hardened/rootless or "expose only to WSL" setup would
break step 2 and require binding the container to the WSL IP + a `netsh portproxy` shim on
Windows. **This is the single riskiest integration point — the implementer must smoke-test it on
the real machine before wiring the rest (see §11 checklist step 0).**

### 5.3 How `target` gates infra

- **Both `infra/fly/` and `infra/local/` are generated into every project, always.** They are
  cheap (small scripts) and generating both is what makes graduation frictionless (§7). The
  `target` answer does **not** decide which directory exists; it only sets the **default value of
  the justfile's `TARGET`** dispatch variable.
- `fly.toml` (+ `.github/workflows/fly-deploy.yml`), `compose.local.yml`, and the base-path env
  wiring all always render — a local-first project keeps a ready-to-use `fly.toml` for the day it
  graduates, and a fly-first project can be flipped to local without re-scaffolding.
- The GitHub Actions Fly auto-deploy workflow is Fly-specific; when `target: local` it would
  otherwise run `just deploy` against the local dispatch on CI (wrong). **Set `DEMO_TARGET: fly`
  in the workflow's `env:`** so CI always means Fly regardless of the project's local default.
  (Small edit to the existing workflow file — called out in the checklist.)

### 5.4 App base-path coupling (the one place the app is prefix-aware)

**Correction (2026-07-12):** Tailscale `--set-path /<name>` **STRIPS the prefix** before proxying
(§1, §4.3) — the container receives requests at `/...`, never `/<name>/...`. Route decorators
therefore need **no** change between targets (routing was never the issue). But two things still
need the base path, both confirmed broken empirically before this fix:

- **URL generation** — `request.url_for(...)` and redirects need to know the prefix so links sent
  to the *browser* resolve under `/<name>` on local. This is still driven by a single env var:
  - **`ROOT_PATH`** — `""` on Fly and on `just dev` (app served at root), `"/<name>"` on local
    (set by the `compose.local.yml` overlay, §5.1).
- **HTTPS scheme detection** — uvicorn behind Tailscale's proxy only ever sees a plain HTTP
  connection; without `--proxy-headers` it doesn't trust `X-Forwarded-Proto: https`, so
  `url_for()` emits `http://` absolute URLs on an `https://` page, which browsers **block as mixed
  content** (the whole UI loads unstyled/broken — this masked itself on `localhost`, where the
  `http://` URL is directly reachable).

**`fastapi` stack** (the downstream job-app driver): construct the app with `root_path` fed by the
env var, and run uvicorn with `--proxy-headers`:

```python
import os
from fastapi import FastAPI

app = FastAPI(root_path=os.getenv("ROOT_PATH", ""))   # "" on Fly/dev, "/job-tracker" on local
```

```
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips=*"]
```

Why routing still works despite the stripped prefix: the starter pins **`fastapi>=0.115`**, whose
Starlette computes the route-matching path via `get_route_path()`, which strips `root_path` from
the incoming path *only if the incoming path actually starts with it*. A stripped request arriving
as `/approve` doesn't start with `root_path="/job-tracker"`, so `get_route_path()` returns
`/approve` unchanged and the route matches directly — exactly as it does with an empty `root_path`
on Fly. **No route decorators change between targets**; `root_path` only affects what
`url_for()`/redirects emit back to the browser.

**HTMX / templates / static assets — the rule for the job-app UI:** every generated URL must
carry the base path so it resolves under `/<name>` on local and under `/` on Fly. Concretely:
- Build links/redirects with `request.url_for(...)` or by prefixing with
  `request.scope["root_path"]` (FastAPI populates `root_path` in the request scope), **not**
  hard-coded absolute paths like `/static/app.css` or `hx-get="/approve"` — those would resolve
  to the **tailnet host root**, bypassing the app.
- Serve static files via a **route** (`@app.get("/static/{path:path}", name="static")` →
  `FileResponse`, with a path-traversal guard), **not** `app.mount("/static", StaticFiles(...))`.
  A Mount only matches the full `/<name>/static/...` path; since the prefix is stripped, the
  incoming request is a bare `/static/...` that the Mount 404s on. A route matches either way, and
  `url_for("static", path=...)` still emits the correctly-prefixed URL for the browser.
- HTMX attributes should use the templated, root_path-prefixed URLs (e.g.
  `hx-get="{{ request.scope.root_path }}/approve"`), keeping the phone UI's partial requests
  inside the app on both targets.

This is the **only** prefix-awareness required; it lives in the app's URL-generation plus the
uvicorn proxy-headers flag, driven by env vars that are empty/absent on Fly — so the "app identical
across targets" invariant (§8) holds.

---

## 6. Persistence & always-on

| Concern | Mechanism | Caveat |
|---------|-----------|--------|
| Container returns after reboot | `restart: unless-stopped` (compose.local overlay) + Docker Desktop set to **"Start Docker Desktop when you sign in"** | Docker Desktop starts **after Windows user login**, not at boot-before-login. Until Kelvin logs in, the container is down and the `/<name>` path returns **502** (Tailscale is up). **Accepted** — non-goal to fix (§2, §12). |
| Tailscale serve returns after reboot | `tailscale serve` config persists in `tailscaled` state; Tailscale is a **Windows service** (starts at boot, pre-login) | None — this side needs no scheduled task. |
| SQLite data survives restart/reboot/recreate | Bind-mount `./data:/data`; the DB file lives on the host filesystem, independent of container lifecycle | `just destroy` deliberately keeps `./data` (see §4.1, §4.5). |

No Windows scheduled task is required — this is simpler than the calibre setup (which needed a
`wst` task for the calibre *backend*), because Docker Desktop's restart policy + Tailscale's
persisted serve config cover both halves.

---

## 7. Graduation path (local ⇄ Fly)

Because both infra sets always exist, **graduation is a one-value flip plus a data copy**:

1. **Flip the target.** Either edit `target:` in `.demo-template-version` (source of truth, and
   what `just sync` reads) or, for a one-off, `DEMO_TARGET=fly just deploy`. For a permanent
   move, edit the answers file so `just status`/`just deploy`/CI all agree.
2. **`just deploy`** — now runs `infra/fly/deploy.sh` (creates the app, cert, DNS) exactly as a
   Fly-native project would. **The path prefix is dropped automatically:** Fly's `fly.toml`
   serves the app at the root of its own hostname, and the Fly deploy sets no `ROOT_PATH`, so the
   app's `root_path` is `""`. Because URLs were generated via `root_path` (§5.4), **no app change
   is needed** — the same code that served under `/<name>` locally now serves at `/` on Fly, and
   HTMX/asset links follow.
3. **Migrate data (manual — non-goal to automate).** SQLite is a single file in `./data`:
   - local → Fly: `fly ssh sftp shell -a <name>` (or `fly ssh console` + `cat`) to copy
     `./data/<db>.sqlite` into the Fly volume at `/data`. Do it while the app is stopped to avoid
     a torn copy.
   - Fly → local: reverse (`fly ssh sftp get`), drop the file into `./data`, `just deploy`.
   Add a short "Migrating data" subsection to the generated README with these commands.
4. **`just sync` implications.** `sync` (`copier update`) is target-agnostic and re-renders
   *both* infra dirs. The new answers (`target`, `tailscale_host`, `tailscale_path`) live in
   `.demo-template-version`, so updates preserve them. Flipping `target` there before a sync is
   safe — it only changes the justfile's default.

Tear-down symmetry: `just destroy` under `local` removes the container + unregisters the
`/<name>` serve path but keeps `./data`; under `fly` it destroys the app + cert. Switching target
then destroying only affects that target — the other target's resources are untouched.

---

## 8. Boundary invariant: app code identical across targets

**Rule:** the `app/` directory, the `Dockerfile`, and the app's runtime behaviour are **identical**
whether `target` is `fly` or `local`. The **only** target-driven difference is the value of the
**`ROOT_PATH` env var** (`""` on Fly, `/<name>` on local), read in one place (§5.4). Enforced by:

- The app must listen on `0.0.0.0:<internal_port>` — already true (Dockerfile `CMD`s bind
  `0.0.0.0`).
- The app must read/write persistent state under **`/data`** — already the convention (Dockerfile
  `mkdir -p /data`; Fly mounts a volume there; local bind-mounts `./data` there). The job-app's
  SQLite path must be `/data/<db>.sqlite` so it works unchanged on both.
- The app must construct its base URLs from `root_path` (env-driven), **not** hard-coded absolute
  paths — the one discipline path-based routing imposes (§5.4). Empty on Fly, so Fly behaviour is
  unchanged.
- **No `target`/Tailscale conditionals in app code or Dockerfile.** The single env var is the
  entire coupling.

This preserves the README's existing two-layer model (upstream-owned app layer / demo-tools infra
overlay); the local target is a new sibling in the infra layer, plus one env-driven line in the
app's construction.

---

## 9. Error handling & edge cases

| Situation | Handling |
|-----------|----------|
| Tailscale not installed / not on Bos-Desktop | `_lib.sh resolve_ts` → clear error: "Tailscale CLI not found; this target only works on Bos-Desktop." |
| Tailscale service not running | `preflight`: `tailscale status` non-zero → "Tailscale is not running on the Windows host." |
| Docker Desktop not running | `preflight`: `docker info` non-zero → "Docker Desktop is not running." |
| Path already served (by another app, e.g. `/calibre`) | Before registering, `tailscale serve status` is checked; if `<tailscale_path>` maps to a *different* backend port, error listing the conflict and suggesting `--tailscale-path` at scaffold time. Re-deploying the *same* app is idempotent. |
| Serve registration needs admin | **Every** serve-config write needs Windows admin (Tailscale 1.98.2). `deploy.sh` skips it when the path is already registered; on first registration it elevates via one UAC (`Start-Process -Verb RunAs`). If the UAC is declined or there's no desktop session, it prints the exact elevated command and exits non-zero. |
| Container not up (`logs`/`ssh`/`status`) | Scripts detect via `docker compose ps` and print "container not running — `just deploy` first" instead of a raw Docker error. |
| `"Program Files"` space in path | Always quote the explicit `/mnt/c/Program Files/Tailscale/tailscale.exe`; never rely on an unquoted PATH lookup. |
| Reboot before login | Documented, **accepted** caveat (§6) — container down (502) until Kelvin signs in; Tailscale itself is up. |
| `stateful: false` stack on local | No bind-mount rendered (overlay's volume block is `{% if stateful %}`); `db-create` prints the friendly N/A. |
| App uses hard-coded absolute URLs | Symptom: assets/HTMX 404 under `/<name>` on local. Documented in §5.4 as the one discipline; the generated fastapi starter models the correct `root_path`-driven pattern. |

---

## 10. Testing strategy

**A. Copier render tests** (`tests/test_template_render.py`, same style as the existing
`_render(...)` helper — add `target` to its data dict, default `"fly"`):

- `target=local` renders `infra/local/{deploy,stop,start,destroy,logs,ssh,status,open,secret,db-create}.sh`
  and `_lib.sh`.
- `target=local` renders `compose.local.yml` with `restart: unless-stopped`, `ROOT_PATH:
  "/tmp-demo"`, and (stateful) `./data:/data`.
- `infra/local/deploy.sh` contains `serve --bg --set-path /tmp-demo` and the bare
  `internal_port`; `destroy.sh` contains `--set-path /tmp-demo off`.
- `justfile` `TARGET :=` default is `local` when `target=local`, `fly` when `target=fly` (default).
- `infra/local/*.sh` contain the tailnet path URL
  (`bos-desktop.fish-grouper.ts.net/tmp-demo`) and **do not** contain Fly-isms
  (`assert "fly " not in ...`, `"machines" not in ...`, `"cert" not in ...`).
- **Coexistence:** `target=local` still renders `infra/fly/deploy.sh` and `fly.toml` (both dirs
  exist); `target=fly` still renders `infra/local/` (graduation-ready).
- **Backward-compat:** omitting `target` → default `fly`; existing assertions unchanged
  (`test_justfile_has_all_verbs` etc. keep passing; add the renamed-variable check). Confirm
  `target=fly` renders **no** `ROOT_PATH` env / empty base path.
- Answers-file: `.demo-template-version` contains `target: local`, `tailscale_path: /tmp-demo`,
  `tailscale_host: …` (mirror `test_scaffold_demo_writes_profile_into_answers`).
- fastapi starter: `main.py` constructs `FastAPI(root_path=os.getenv("ROOT_PATH", ""))` (unit
  assert on the starter source; and a behavioural check that a route resolves both at `/healthz`
  with empty root_path and at `/tmp-demo/healthz` with `root_path=/tmp-demo`).
- CLI: `scaffold_demo(..., target="local")` and the `--target` / `--tailscale-path` options
  thread through (mirror the `profile` CLI tests).

**B. Manual smoke checklist** (must run **on Bos-Desktop** — the WSL/Windows/Tailscale path can't
be unit-tested):

1. `demo-init scaffold fastapi smoke-local --target local`
2. `cd smoke-local && just deploy` → prints `https://bos-desktop.fish-grouper.ts.net/smoke-local`.
3. `curl -sk https://bos-desktop.fish-grouper.ts.net/smoke-local/healthz` from WSL → `{"ok":true}`.
4. From **phone on the tailnet**, open the URL → app loads with a valid cert (no warning); HTMX
   partials + static assets resolve under `/smoke-local`.
5. Write a row (once the job-app has a DB) → confirm a file appears in `./data/`.
6. `just status` → shows running container + the path URL + data dir.
7. **Reboot the host, sign in** → container auto-restarts; URL works again; the `./data` row is
   still there. (Before sign-in, expect a 502 — accepted.)
8. `just stop` → 502; `just start` → back up.
9. `just destroy` → confirm; container gone + `/smoke-local` unregistered (`/calibre` and `/`
   untouched); **`./data` still on disk**.
10. Graduation: flip `target: fly`, `just deploy` (needs flyctl auth) → Fly URL works at root, no
    app edits.

---

## 11. Implementation checklist (ordered)

0. **De-risk first:** on Bos-Desktop, manually run a throwaway container `docker run -p 8000:8000
   …`, then `tailscale.exe serve --bg --set-path /smoke 8000`, and hit
   `https://bos-desktop.fish-grouper.ts.net/smoke` from the phone. **Confirm §5.2 (reachability)
   and whether the path forwarding strips the prefix before writing any template code.** Also confirm the
   `--set-path /smoke off` teardown syntax on the installed Tailscale version. If reachability
   fails, resolve §12-Q1 (portproxy shim) before proceeding.
1. `copier.yml`: add `target`, `tailscale_host`, `tailscale_path` questions (§4.4).
2. Rename `justfile` → `justfile.jinja`; add `TARGET := env_var_or_default("DEMO_TARGET",
   "{{ target }}")`; rename `PLATFORM`→`TARGET` in all recipes; wrap recipe bodies in
   `{% raw %}…{% endraw %}` (§4.1). Update the `DEMO_PLATFORM` → `DEMO_TARGET` reference.
3. Create `infra/local/_lib.sh.jinja` + the 10 verb scripts (§4.5), mirroring the fly headers and
   the nextjs-fastapi service-name branch. Use the exact `--set-path <path> <port>` serve form.
4. Add `compose.local.yml.jinja` (§5.1) with `ROOT_PATH`, `restart: unless-stopped`, the
   `./data` bind-mount, and the dual-app branch for `nextjs-fastapi`.
5. Update the **fastapi starter** `main.py` to `FastAPI(root_path=os.getenv("ROOT_PATH", ""))`
   (§5.4) and document the root_path/url_for discipline in a starter comment so the job-app
   inherits it. (Empty env on Fly/dev → no behaviour change there.)
6. Append `./data/` to the template `.gitignore` under a `# local target` comment.
7. `scaffold.py` + `adopt.py`: thread `target` (+ host/path) into `run_copy(data=…)` and the
   `.demo-template-version` writer (mirror how `profile` is handled).
8. `cli.py`: add `--target` (and `--tailscale-path`) options to `scaffold` and `adopt`; ignore
   `--profile` when `target=local` (with a one-line notice).
9. Set `DEMO_TARGET: fly` in `.github/workflows/fly-deploy.yml` `env:` so CI always means Fly (§5.3).
10. Tests: add the §10-A render + CLI + starter tests; update the two assertions that reference
    the old `PLATFORM` variable / `DEMO_PLATFORM`.
11. `README.md`: new "Deploy targets: Fly vs local" section (verb table already applies to both;
    add the tailnet path URL story, the one-time landing-page prerequisite, the reboot/login 502
    caveat, and the "Migrating data" subsection); update `README.md.jinja` so generated projects
    show their real tailnet path URL when `target=local`.
12. Run `uv run pytest`; then the §10-B manual smoke test on Bos-Desktop.

---

## 12. Open questions / assumptions

**Resolved by Kelvin (2026-07-10):**
- **Routing = path-based** under the shared host (`…ts.net/<name>`), matching the
  landing-page/Calibre convention. (Was an open recommendation for own-port; now settled — this
  doc reflects path-based throughout.)
- **Reboot-before-login = accepted**, stays a non-goal; the pre-login 502 window is understood.

**Assumptions made (documented; low-to-medium risk):**
- Docker Desktop publishes container ports to Windows `localhost` in Kelvin's config (§5.2) —
  the standard WSL2-backend behaviour, verified present but not end-to-end proven for `serve`.
- ~~Proxying a *port* under a path needs no admin.~~ **FALSE (2026-07-12).** Every serve-config
  write needs Windows admin on Tailscale 1.98.2. Handled by skip-if-registered + one-time elevated
  registration (§4.3).
- ~~Tailscale forwards the path unstripped.~~ **FALSE (confirmed empirically 2026-07-12).**
  Tailscale **strips** the `/<name>` prefix before proxying. `FastAPI(root_path="/<name>")` still
  routes correctly either way, because Starlette's `get_route_path()` only strips `root_path` from
  the incoming path when the path actually carries it (§5.4) — but `root_path` is required for
  correct `url_for()`/redirect output, and uvicorn needs `--proxy-headers` for `url_for()` to emit
  `https://` links.
- The shared host's landing page at `/` is already served (Calibre task) — the prerequisite for
  adding sibling paths.
- `--set-path <path> off` is the correct teardown form — **CONFIRMED 2026-07-12** (`tailscale serve
  --set-path /smoke-local off` removed only that mount; `/` and `/calibre` untouched).

**Remaining must-verify (highest risk):**

1. ~~The WSL ⇄ Windows ⇄ container reachability (§5.2, step-0).~~ **RESOLVED 2026-07-12.** Smoke
   test on Bos-Desktop passed end-to-end: `demo-init scaffold fastapi smoke-local --target local`
   → `just deploy` → `https://bos-desktop.fish-grouper.ts.net/smoke-local/` served
   `{"hello":"world"}` and `/smoke-local/healthz` served `{"ok":true}` with a valid cert, from
   both WSL `curl` and a **phone on the tailnet**. Docker Desktop published to Windows
   `127.0.0.1:8000` as assumed — no `netsh portproxy` shim needed. The only surprise was the admin
   requirement (§4.3), now handled.

**Lower-priority confirmations:** whether `just secret` writing to `.env` is the desired local
secret story vs a `.env.local`; whether to auto-append `./data/` to `.gitignore` (yes,
recommended); default `tailscale_path` = `/<name>` (override only on a path clash).
