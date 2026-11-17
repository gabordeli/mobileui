# Deluge MobileUi

Mobil-first web UI Deluge-hez, **core pluginként a `deluged`-ben** futva. A saját
HTTP API/SPA a **8113**-as porton hallgat; a gyári `deluge-web` marad az 8112-n.

## Állapot

- **M1 / #1 kész:** plugin váz, egg csomagolás, `GET /health`.
- **M1 / #2 kész:** Bearer-token a `/api/*`-ra, JSON 401, 600-as config,
  élő `set_config` (token/port/enabled).
- **M1 / #3 kész:** `/api/session`, `/api/labels`, lapozott/szűrt
  `/api/torrents`, `/api/torrents/{id}`; 833 torrenten p95 14 ms terhelés alatt.
- **M1 / #4 kész:** pause/resume/remove/queue, label PATCH, magnet és `.torrent`
  hozzáadás; a .27-en eldobható torrenten végigtesztelve.
- **M1 / #5 kész:** `/api/events` SSE, EventManager + 1/s diff, 15 s heartbeat,
  reconnect; a token query paraméterben is adható.
- **M2 / #6 kész:** Vue 3 + Vite + TS SPA a `data/`-ban, 50-es lapok +
  virtualizált végtelen scroll, kereső/szűrők, long-press sheet, SSE élő lista.
- **M2 / #7 kész:** torrent detail (peers/ETA/ratio/útvonal), lapozott
  fájllista, add sheet magnet/.torrent + label + útvonal.
- **M2 / #8 kész:** PWA manifest/ikonok/SW, light/dark téma, HU/EN i18n,
  skeleton/offline/error állapotok, safe-area + a11y alapok.
- **M3 / #10 kész:** GitLab CI (lint/test/build + manuális release/deploy),
  `v0.1.1` release, deploy job a .27-re; a #9 public HTTPS később.
- **M3 / #11 kész:** runner toolchain (python/venv, node/npm, git, jq, curl,
  rsync, docker/trivy), `--check --diff` changed=0, runner restart.
- Következik: M3 / #9 public HTTPS, ha kell.

## Felépítés

```
deluge_mobileui/     Deluge core plugin (Twisted Site a daemon reactorjában)
  core.py             enable()/disable(), config, auth, port bind
  http.py             Twisted resource-ok (/health, /api végpontok, 401)
  read.py             torrent/session/label olvasás (cache-elt státusz)
  write.py            pause/resume/remove/label/queue/add
  events.py           SSE broadcaster (EventManager + 1/s diff)
  data/               SPA build output (a plugin statikusan szolgálja ki)
webui/                Vue 3 + Vite + TS SPA (M2)
  src/                App, API-kliens, virtuális lista, sheet
scripts/dev-daemon.sh Helyi, eldobható konfiggal futó deluged
scripts/install.sh    Telepítés/újraépítés a Deluge hoston (root)
tests/                pytest (mock core, valódi Twisted resource-ok)
docs/                 API és döntések
```

## Fejlesztés

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install pytest ruff build

.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/python setup.py bdist_egg   # dist/MobileUi-<verzió>-py3.x.egg

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
npm run build      # deluge_mobileui/data/
npm run dev        # proxy: 127.0.0.1:8113
VITE_API_PROXY=http://192.168.2.27:8113 npm run dev
```

A részletek: [docs/webui.md](docs/webui.md).

## CI / release

A `.gitlab-ci.yml` stage-ei: `lint` (ruff + vue-tsc), `test` (pytest, Deluge
nélkül stubokkal), `build` (SPA + sdist/wheel/egg, artifact), `release`
(manuális `RELEASE_TYPE=patch|minor|major`) és `deploy` (manuális rsync +
`scripts/install.sh` a .27-re).

```bash
./scripts/release.sh patch --dry-run
./scripts/release.sh minor
```

Részletek: [docs/ci.md](docs/ci.md). A deploy jobhoz a runneren
`DEPLOY_SSH_KEY` és rsync kell (#11).

## Telepítés (cél: cirice, 192.168.2.27)

A hoston, rootként, a repó checkoutjából:

```bash
./scripts/install.sh
```

A script a Deluge venv Pythonjával épít egg-et, **kicsomagolja** a
`deluge.plugins` könyvtárba (`MobileUi-<verzió>-py3.11.egg/`), újraindítja a
`deluged`-et, `deluge-console`-lal engedélyezi a plugint, majd ellenőrzi a
`/health`-t. A kicsomagolt forma kell a `data/` statikus kiszolgálásához.
Felülírható: `DELUGE_VENV`, `DELUGE_CONFIG_DIR`, `DELUGE_USER`, `SERVICE`, `PORT`.

### Jelenlegi telepítés (2026-11-17)

- Host: `cirice` (192.168.2.27), `deluged` systemd alatt; a plugin **enabled**,
  a 8113 LAN-only, a 8112-es `deluge-web` változatlanul fut.
- SPA: `http://192.168.2.27:8113/` (token-kapu), ugyanaz az API a `/api/*` alatt.
- A generált API-token a hoston a `/root/mobileui-token` fájlban van (600);
  a `mobileui.conf` a `debian-deluged` tulajdona, 600.
- A token nem szerepel a daemon logban.

### Konfiguráció

`mobileui.conf` a Deluge config könyvtárában (600, a daemon user tulajdona):

```json
{
  "enabled": true,
  "port": 8113,
  "token": ""
}
```

A `/api/*` végpontok `Authorization: Bearer <token>`-t kérnek; üres token esetén
minden `/api/*` 401-et ad. A `/health` mindig publikus. A token nem kerül logba.
Az SSE (`/api/events`) az `EventSource` miatt `?token=<token>` query paramétert is
elfogad (a header az elsődleges).

Élő átállítás a `mobileui.set_config` RPC-vel (a `deluge.ui.client`-en vagy a
WebUI-n át); a token, a port és az `enabled` azonnal érvényesül, restart nem kell.
Ha az új port nem bindolható, a plugin visszaállítja a régi portot és hibát ad.

```python
from twisted.internet import defer, reactor
from deluge.ui.client import client


@defer.inlineCallbacks
def main():
    yield client.connect('127.0.0.1', 58846, 'localclient', '<auth-jelszó>')
    print((yield client.mobileui.set_config({'token': '<új-token>'})))
    yield client.disconnect()
    reactor.stop()


reactor.callWhenRunning(main)
reactor.run()
```

A `<auth-jelszó>` a Deluge config `auth` fájljából való (`localclient` sor).
Új egg telepítése után viszont kell a `deluged` restart (a plugin kódja csak
indításkor töltődik be).

### Visszaállítás

A plugin letiltása a daemonban:

```bash
runuser -u debian-deluged -- /opt/deluge-2.2.0/bin/deluge-console \
  -c /var/lib/deluged/config "plugin -d MobileUi"
```

Majd a telepített `MobileUi-*.egg/` **könyvtár** törlése a
`/opt/deluge-2.2.0/lib/python3.11/site-packages/deluge/plugins/` alól és
`systemctl restart deluged`.

## Dokumentáció

- [docs/api.md](docs/api.md) – API séma
- [docs/perf.md](docs/perf.md) – 833 torrentes mérés és a választott stratégia
- [docs/webui.md](docs/webui.md) – SPA felépítés, lapozás/virtualizáció, SSE
- [docs/ci.md](docs/ci.md) – CI stage-ek, release és deploy
- [docs/decisions.md](docs/decisions.md) – döntések és korlátok
- [AGENTS.md](AGENTS.md) – munkamód ügynököknek
