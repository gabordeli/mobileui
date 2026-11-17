# AGENTS.md

Deluge **2.x** core plugin with a mobile web UI. The plugin runs in the
`deluged` Twisted reactor and starts its own HTTP server on **8113**. The stock
`deluge-web` (8112) stays untouched.

## Layout

- `deluge_mobileui/` – plugin package (`core.py`, `auth.py`, `http.py`,
  `read.py`, `write.py`, `push.py`, `events.py`, `data/`)
- `webui/` – Vue 3 + Vite SPA, built into `deluge_mobileui/data/`
- `tests/` – pytest; unit tests that run without Deluge
- `docs/` – `api.md`, `perf.md`, `webui.md`, `usage.md`, `ci.md`, `install.md`,
  `decisions.md`

## Commands

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python setup.py bdist_egg
./scripts/release.sh patch --dry-run
(cd webui && npm ci && npm run build)
./scripts/dev-daemon.sh        # local smoke, .dev/ config
./scripts/install.sh           # on the target host, as root
```

## Principles

- **Mobile-first:** whatever is comfortable on a phone must also work on desktop
  (long-press, safe-area, one-handed actions, responsive layout).
- **Few, but flawless:** small features, high reliability; prefer fewer
  finished, tested things over many half-done ones.
- **Do not duplicate Deluge:** only rebuild what the stock GUI/daemon already
  does when the mobile experience requires it.
- **The reactor must not block:** handlers run in the `deluged` event loop;
  read from the cached status, paginate/filter on the server.
- **Never log the token:** because of the SSE `?token=` query, the proxy logs
  `$uri` (not `$request`); the plugin does not log requests.
- **Authorization:** every mutating endpoint is tested at read-only (403) and
  normal (200/201) levels.
- **Deluge 2.x:** for any new `deluge.*` import, the CI `deluge-compat` matrix
  (2.0.3 / 2.1.1 / 2.2.0) is the gate; update `tests/stubs` too.
- **Secrets/IPs:** no host/IP/token in the repository; deploy uses
  `$DEPLOY_HOST`, docs stay environment-agnostic.

## Rules

- Do not touch the 8112 `deluge-web` or the existing Label/AutoAdd/Scheduler/
  Execute flows.
- Changing the Deluge host (install, restart) requires separate approval.
- Git operations (commit/push/merge) require explicit approval.
- One step = one issue, followed by a short status; do not leave half-finished
  files.

Details: [README.md](README.md), [docs/api.md](docs/api.md),
[docs/decisions.md](docs/decisions.md).
