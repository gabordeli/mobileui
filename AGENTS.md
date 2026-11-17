# AGENTS.md

Deluge **2.x** core plugin mobil web UI-hoz. A plugin a `deluged` Twisted
reactorjában fut, saját HTTP szervert indít a **8113**-on. A gyári `deluge-web`
(8112) érintetlen marad.

## Layout

- `deluge_mobileui/` – plugin csomag (`core.py`, `auth.py`, `http.py`,
  `read.py`, `write.py`, `events.py`, `data/`)
- `webui/` – Vue 3 + Vite SPA (M2), build a `deluge_mobileui/data/`-ba
- `tests/` – pytest; Deluge nélkül is futó unit tesztek
- `docs/` – `api.md`, `perf.md`, `webui.md`, `ci.md`, `install.md`, `decisions.md`

## Parancsok

```bash
.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python setup.py bdist_egg
./scripts/release.sh patch --dry-run
(cd webui && npm ci && npm run build)
./scripts/dev-daemon.sh        # helyi smoke, .dev/ config
./scripts/install.sh           # célhoston, rootként
```

## Szabályok

- A 8112-es `deluge-web`-hez és a meglévő Label/AutoAdd/Scheduler/Execute
  flow-hoz nem nyúlunk.
- A Deluge host módosítása (telepítés, restart) külön jóváhagyás után megy.
- Git művelet (commit/push/merge) csak kifejezett engedéllyel.
- Egy lépés = egy issue, utána rövid státusz; ne hagyj félkész fájlt.

Részletek: [README.md](README.md), [docs/api.md](docs/api.md),
[docs/decisions.md](docs/decisions.md).
