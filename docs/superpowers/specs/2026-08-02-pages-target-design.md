# GitHub Pages deploy target — design

**Date:** 2026-08-02
**Status:** Approved

## Problem

demo-tools ships to Fly (`--target fly`) or a Tailscale-exposed local container
(`--target local`). Both package the app into a Docker image and run a server.

Some demos don't need a server. Their output is files: HTML, JS, CSS. For those,
GitHub Pages hosts free, always-on, with no cold start and no container. obslink
(built 2026-08-02) is the motivating case — one HTML file, one JS module, one
JSON file, deployed by hand because demo-tools had no path for it.

Two gaps to close: a **target** that publishes to Pages, and a **stack** that
produces the files without a toolchain.

## Target: `pages`

Targets are already a clean extension point. Each is a directory of shell
scripts implementing the same verbs; `justfile` dispatches
`bash infra/{{TARGET}}/<verb>.sh`. Adding `pages` means adding `infra/pages/`,
one more choice in `copier.yml`, and a stack-compatibility guard.

### Two publish paths, chosen by whether the stack builds

`html` has no build step, so the repo root *is* the site — Pages serves `main`
at root and `just deploy` is a push. Nothing to copy, no second branch to drift.

`vite` builds to `dist/`, which cannot live at the repo root, so `just deploy`
builds and pushes that output to a `gh-pages` branch.

This is two code paths in one target, chosen deliberately. Forcing `html`
through a `gh-pages` branch would mean maintaining a branch that is a byte-copy
of `main` — churn that buys nothing. The branching point is a single
`stack_builds` predicate, not a fork through every verb.

Both paths end the same way: ensure the Pages source and custom domain via
`gh api`, then print the URL.

### Verb mapping

Not every verb has a meaning on Pages. Mapping each to its honest analogue
beats leaving a script that silently does nothing.

| Verb | On Pages |
|---|---|
| `deploy` | Push (html) or build + push `dist/` to `gh-pages` (vite), then ensure Pages config + CNAME |
| `status` | Pages state, build status, HTTPS certificate state, resolved URL |
| `logs` | Recent Pages build history (`gh api .../pages/builds`) |
| `open` | Open the URL |
| `destroy` | Disable Pages (confirmed). Does not delete the repo. |
| `stop` / `start` | Exit 0 with a note: Pages is always on and free, so there is nothing to stop |
| `ssh` | Exit non-zero: no server exists to connect to |
| `db-create` | Exit non-zero: no server, no database |
| `secret` | **Exit non-zero.** See below. |

### `secret` must refuse

On Fly, `just secret KEY=VAL` sets a server-side secret. On Pages there is no
server — anything the page can read, a visitor can read. A `secret` verb that
wrote a `.env` would hand someone a way to ship an API key to a public CDN and
believe it was hidden.

So it fails, and the message distinguishes the two cases: public config (an API
base URL, a feature flag, a publishable key) belongs in the source; a real
credential needs a server, which means `--target fly`.

This matters because static pages *do* call external services — that is the
normal case, not an edge case. The refusal is the one place the design has to
say so out loud.

### Stack compatibility

`pages` accepts `html` and `vite`. `fastapi`, `streamlit`, and `nextjs-fastapi`
need a running server, so scaffolding them with `--target pages` fails
immediately — before any files are written — naming the reason and pointing at
`--target fly`. `bare` is allowed: the user supplies their own output.

`nextjs` is rejected for now. It *can* target Pages via `output: 'export'`, but
that silently disables SSR, API routes, and image optimisation — failures that
surface later rather than at scaffold time. Left out until wanted explicitly.

Unlike `fly` and `local` — which are both generated every time so switching is a
flip — `pages` is only generated when compatible, because for half the stacks it
would be a directory of scripts that can never run.

## Stacks: rename `static` → `vite`, add `html`

`static` is currently Vite + React + nginx in Docker. The name is wrong on two
counts: every other stack is named for its tool (`nextjs`, `fastapi`,
`streamlit`), and once a no-build stack exists, *both* are static — the word
stops distinguishing anything. "Static" describes the target axis, not a stack.

The rename is free today: no scaffolded demo uses `static` (checked across
beeper-inbox, buildwithbos.com, calshift, job-tracker, playground-proof). That
window closes the first time one does.

### `html`

The genuinely slim stack: `index.html`, `app.js`, `app.css`, plus the PWA assets
every demo-tools app gets. No `package.json`, no `node_modules`, no Dockerfile.
`just dev` serves the directory over `python3 -m http.server`.

Its value is not disk space — `node_modules` is gitignored and never ships. It
is that **there is no toolchain to rot**. A page with no build step still
deploys unchanged years later; a bundled one depends on a Node version and a
lockfile continuing to resolve. The failure mode isn't "the site broke", it's "I
can no longer deploy a fix to the site", which is worse. For a tool whose pitch
is *ship it and forget it*, that is the point.

Second: the deployed artifact is the source. What is in the repo is what is on
the web — fixable in a browser, debuggable by view-source.

Cross the threshold into JSX, TypeScript, npm libraries, or HMR and the answer
is to scaffold `vite`, not to grow `html` into a bundled app.

Because `html` has no Dockerfile, `--target fly` and `--target local` are not
offered for it. It is a Pages-only stack.

## Testing

Follows the existing suite's shape (145 tests currently green).

- **Template render:** `pages` infra renders for `html` and `vite`; the verb
  scripts are syntactically valid (`bash -n`); `html` renders no Dockerfile.
- **Compatibility guard:** each server-backed stack with `--target pages` exits
  non-zero with a message naming the stack, and writes no files.
- **Stack rename:** `vite` scaffolds via `npm create vite`; `static` is gone
  from `VALID_STACKS`, the copier choices, and `detect_stack`.
- **`html` scaffolder:** writes the starter files and PWA assets, no
  `package.json`, no Dockerfile.
- **`secret` refusal:** exits non-zero and writes no `.env` — the case where a
  silent success would leak a credential.
- **Deploy path selection:** `html` resolves to serve-main, `vite` to gh-pages.

Deploy scripts are tested for structure and dispatch, not by publishing to
GitHub — the same line the existing `fly` and `local` targets draw.

## Out of scope

- **`nextjs` static export** — see above; wanted explicitly or not at all.
- **Custom-domain DNS automation.** The `fly` target has
  `infra/fly/cloudflare_dns.sh`; the Pages equivalent (`CNAME <name> →
  <user>.github.io`, DNS-only) is left manual for now. obslink's record was
  created by hand and is documented in its README.
- **Migrating obslink onto the template.** It works; adopting it is a separate,
  optional follow-up once `html` exists.
