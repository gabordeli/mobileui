# Deluge MobileUi

Mobil-first web UI Deluge-hez, **core pluginként a `deluged`-ben** futva. A saját
HTTP API/SPA a **8113**-as porton hallgat; a gyári `deluge-web` marad az 8112-n.
Deluge **2.x** (Python 3.10+), élesben **2.2.0**-val tesztelve; a CI a backend
suite-ot valódi Deluge 2.0.3 / 2.1.1 / 2.2.0 ellen is futtatja. 1.x nem támogatott.

[![Release](https://img.shields.io/badge/release-v0.1.3-2ea44f?style=flat-square)](https://github.com/gabordeli/mobileui/releases)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square)](https://www.python.org/)
[![Deluge](https://img.shields.io/badge/deluge-2.x-1f6feb?style=flat-square)](https://deluge-torrent.org/)
[![Node](https://img.shields.io/badge/node-22-339933?style=flat-square)](https://nodejs.org/)
[![Release workflow](https://github.com/gabordeli/mobileui/actions/workflows/release.yml/badge.svg)](https://github.com/gabordeli/mobileui/actions/workflows/release.yml)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-support-ff5e5b?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/gabordeli)

## 📱 Képernyőképek

| Lista | Részletek | Hozzáadás |
| --- | --- | --- |
| <img src="docs/assets/screenshot-list.png" width="240" alt="Torrent lista"> | <img src="docs/assets/screenshot-detail.png" width="240" alt="Torrent részletek"> | <img src="docs/assets/screenshot-add.png" width="240" alt="Torrent hozzáadása"> |

Demó adatok a lokális `scripts/dev-daemon.sh`-ból (kitalált nevek), sötét téma.

## 📊 Állapot

Jelenlegi release: **v0.1.3** (GitLab + GitHub), az éles példányon telepítve.

- **M1 / #1 kész:** plugin váz, egg csomagolás, `GET /health`.
- **M1 / #2 kész:** Bearer-token a `/api/*`-ra, JSON 401, 600-as config,
  élő `set_config` (token/port/enabled).
- **M1 / #3 kész:** `/api/session`, `/api/labels`, lapozott/szűrt
  `/api/torrents`, `/api/torrents/{id}`; több száz torrenten p95 14 ms terhelés alatt.
- **M1 / #4 kész:** pause/resume/remove/queue, label PATCH, magnet és `.torrent`
  hozzáadás; az éles példányon eldobható torrenten végigtesztelve.
- **M1 / #5 kész:** `/api/events` SSE, EventManager + 1/s diff, 15 s heartbeat,
  reconnect; a token query paraméterben is adható.
- **M2 / #6 kész:** Vue 3 + Vite + TS SPA a `data/`-ban, 50-es lapok +
  virtualizált végtelen scroll, kereső/szűrők, long-press sheet, SSE élő lista.
- **M2 / #7 kész:** torrent detail (peers/ETA/ratio/útvonal), lapozott
  fájllista, add sheet magnet/.torrent + label + útvonal.
- **M2 / #8 kész:** PWA manifest/ikonok/SW, light/dark téma, HU/EN i18n,
  skeleton/offline/error állapotok, safe-area + a11y alapok.
- **M3 / #10 kész:** CI (lint/test/build + manuális release/deploy),
  `v0.1.2` release, deploy job a Deluge hostra; a #9 public HTTPS kész.
- **M3 / #11 kész:** runner toolchain (python/venv, node/npm, git, jq, curl,
  rsync, docker/trivy), `--check --diff` changed=0, runner restart.
- **M3 / #13 kész:** teljes plugin metadata (author email, URL, license,
  classifiers) az egg/wheel `PKG-INFO`-ban.
- **M3 / #14 kész:** hordozható `.egg` + sha256 a `v0.1.2` release-en,
  `scripts/install.sh` `EGG=...` támogatással; az éles példányon a release
  eggből telepítve.
- **M3 / #15 kész:** a SPA a `/health` válaszából jeleníti meg a plugin
  verzióját (token-kapu + footer); release bump után automatikus.
- **M3 / #9 kész:** publikus HTTPS nginx TLS proxy mögött, token auth, SSE,
  token-mentes access log.
- **CI / SonarQube:** main-branch statikus elemzés + backend/frontend coverage,
  Docker scannerrel, report-only.
- **Bugsink:** backend `sentry-sdk` + frontend `@sentry/vue`, közös DSN;
  a backend `sentry_dsn` élőben állítható.
- **M3 / #12 kész:** privát GitHub tükör (`gabordeli/mobileui`) GitLab push
  mirrorral; `v0.1.3` óta a GitHub Actions release wheel/sdist/egg/sha256
  assetekkel fut, CHANGELOG-alapú note-tal; a GitLab privát marad.
- **Auth:** opcionális Deluge user/jelszó belépés a statikus API-token mellett
  (`auth_mode`), lejáró és visszahívható session tokennel, read-only (1) /
  normal (5) / admin (10) szintekkel; a token break-glass marad.
- **Session sheet:** a fejléc stats sávjáról nyílik; szabad hely, torrentszám,
  rate-ek és egy gombbal az összes torrent pause/resume (read-only nézetben
  gomb nélkül).

## 🧱 Felépítés

```
deluge_mobileui/     Deluge core plugin (Twisted Site a daemon reactorjában)
  core.py             enable()/disable(), config, auth, port bind
  auth.py             session token, login limit, bearer parser
  http.py             Twisted resource-ok (/health, /api végpontok, 401/403)
  read.py             torrent/session/label olvasás (cache-elt státusz)
  write.py            pause/resume/remove/label/queue/add
  events.py           SSE broadcaster (EventManager + 1/s diff)
  data/               SPA build output (a plugin statikusan szolgálja ki)
webui/                Vue 3 + Vite + TS SPA (M2)
  src/                App, API-kliens, virtuális lista, sheet
scripts/dev-daemon.sh Helyi, eldobható konfiggal futó deluged
scripts/package.sh    Hordozható egg + sha256 (SPA-val)
scripts/publish_release.sh  GitLab Release + Generic Package feltöltés
scripts/install.sh    Telepítés/újraépítés a Deluge hoston (root)
tests/                pytest (mock core, valódi Twisted resource-ok)
docs/                 telepítés, API, üzemeltetés és döntések
```

Publikus út (LAN-on a böngésző közvetlenül a Deluge host `:8113`-át éri el):

```mermaid
flowchart LR
    B["📱 Mobil böngésző<br/>SPA + SSE"] -->|"HTTPS :8113"| N["nginx (proxy)<br/>TLS, $uri log"]
    N -->|"proxy :8113"| P["deluged (host)<br/>MobileUi plugin"]
    P --> C["Deluge core<br/>torrentmanager"]
    P --> L["Label plugin<br/>(opcionális)"]
    P --> D["SPA static<br/>data/"]
    P -.->|"opcionális"| S["Bugsink<br/>Sentry"]
    classDef edge fill:#1f6feb,color:#fff,stroke:#1f6feb
    classDef core fill:#2ea44f,color:#fff,stroke:#2ea44f
    classDef ext fill:#8250df,color:#fff,stroke:#8250df
    class N edge
    class P,C,D core
    class S ext
```

## 🛠️ Fejlesztés

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pytest ruff build sentry-sdk

.venv/bin/pytest
.venv/bin/ruff check .
./scripts/package.sh   # dist/MobileUi-<verzió>-py3.x.egg + .sha256

# Helyi smoke: saját config a .dev/ alatt, a felhasználói Deluge-hoz nem nyúl
./scripts/dev-daemon.sh
curl -s http://127.0.0.1:8113/health
curl -s -H 'Authorization: Bearer dev-token' http://127.0.0.1:8113/api
```

A `dev-daemon.sh` első indításnál létrehozza a `.dev/deluge/core.conf`-ot, felveszi
az `enabled_plugins` közé a `MobileUi`-t, a `mobileui.conf`-ba pedig `dev-token`
tokent ír (`MOBILEUI_TOKEN`-nel felülírható), majd elindítja a daemont. A
`http://127.0.0.1:8113/` a SPA-t szolgálja ki.

### SPA fejlesztés

```bash
cd webui
npm ci
npm run build          # deluge_mobileui/data/
npm run test           # Vitest
npm run test:coverage  # webui/coverage/lcov.info
npm run test:e2e       # Playwright smoke (mockolt API)
npm run dev            # proxy: 127.0.0.1:8113 (helyi deluged)
# más gépen futó delugednél:
VITE_API_PROXY=http://<deluge-host>:8113 npm run dev
```

A `test:e2e` első futása előtt `npx playwright install chromium` kell.

A részletek: [docs/webui.md](docs/webui.md).

## 📦 Telepítés

A hoston, rootként, a repó checkoutjából:

```bash
./scripts/install.sh
```

A script egg-et épít, kicsomagolja a `deluge.plugins` alá, újraindítja a
`deluged`-et, engedélyezi a plugint és ellenőrzi a `/health`-t. A SPA
`http://<host>:8113/`, a gyári `deluge-web` marad a 8112-n.

Hordozható egg, config/RPC, a jelenlegi telepítés és a visszaállítás:
[docs/install.md](docs/install.md).

## 📚 Dokumentáció

- [docs/install.md](docs/install.md) – telepítés, hordozható egg, config, visszaállítás
- [docs/api.md](docs/api.md) – API séma
- [docs/perf.md](docs/perf.md) – 833 torrentes mérés és a választott stratégia
- [docs/webui.md](docs/webui.md) – SPA felépítés, lapozás/virtualizáció, SSE
- [docs/ci.md](docs/ci.md) – CI stage-ek, release és deploy
- [docs/decisions.md](docs/decisions.md) – döntések és korlátok
- [AGENTS.md](AGENTS.md) – munkamód ügynököknek

## 🤝 Közreműködés

A GitHub repó a GitLab fejlesztés **egyirányú, read-only tükre**; a fejlesztés a
privát GitLabon folyik. GitHub issue/PR esetén a maintainer portolhatja; a
részletek: [CONTRIBUTING.md](CONTRIBUTING.md).

## ☕ Támogatás

Ha hasznos a projekt, a fejlesztést [Ko-fi](https://ko-fi.com/gabordeli)-val
támogathatod.
