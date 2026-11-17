# AGENTS.md

Deluge **2.x** core plugin mobil web UI-hoz. A plugin a `deluged` Twisted
reactorjában fut, saját HTTP szervert indít a **8113**-on. A gyári `deluge-web`
(8112) érintetlen marad.

## Layout

- `deluge_mobileui/` – plugin csomag (`core.py`, `auth.py`, `http.py`,
  `read.py`, `write.py`, `push.py`, `events.py`, `data/`)
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

## Alapelvek

- **Mobile-first:** amit mobilon kényelmes használni, desktopon is működjön
  (long-press, safe-area, egykezes műveletek, reszponzív layout).
- **Kevés, de hibátlan:** kis funkciók, nagy megbízhatóság; inkább kevesebb
  kész, tesztelt dolog, mint sok félkész.
- **Ne duplikáld a Deluge-t:** amit a gyári GUI/daemon tud, csak akkor építjük
  újra, ha a mobil élmény miatt kell.
- **A reactor nem blokkolható:** a handlerek a `deluged` event loopjában futnak;
  olvasás cache-elt státuszból, lapozás/szűrés szerveroldalon.
- **Token soha ne kerüljön naplóba:** az SSE `?token=` query miatt a proxy
  `$uri`-t naplóz (`$request` helyett); a plugin nem naplóz requestet.
- **Jogosultság:** minden módosító endpoint read-only (403) és normal (200/201)
  szinten is tesztelt.
- **Deluge 2.x:** új `deluge.*` importnál a CI `deluge-compat` mátrixa
  (2.0.3 / 2.1.1 / 2.2.0) a mérce; a `tests/stubs` is frissül.
- **Titkok/IP-k:** a repóban nincs host/IP/token; a deploy `$DEPLOY_HOST`,
  a doksik környezetfüggetlenek.

## Szabályok

- A 8112-es `deluge-web`-hez és a meglévő Label/AutoAdd/Scheduler/Execute
  flow-hoz nem nyúlunk.
- A Deluge host módosítása (telepítés, restart) külön jóváhagyás után megy.
- Git művelet (commit/push/merge) csak kifejezett engedéllyel.
- Egy lépés = egy issue, utána rövid státusz; ne hagyj félkész fájlt.

Részletek: [README.md](README.md), [docs/api.md](docs/api.md),
[docs/decisions.md](docs/decisions.md).
