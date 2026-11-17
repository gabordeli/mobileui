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
  `v0.1.2` release, deploy job a .27-re; a #9 public HTTPS kész.
- **M3 / #11 kész:** runner toolchain (python/venv, node/npm, git, jq, curl,
  rsync, docker/trivy), `--check --diff` changed=0, runner restart.
- **M3 / #13 kész:** teljes plugin metadata (author email, URL, license,
  classifiers) az egg/wheel `PKG-INFO`-ban.
- **M3 / #14 kész:** hordozható `.egg` + sha256 a `v0.1.2` release-en,
  `scripts/install.sh` `EGG=...` támogatással; a .27-en a release eggből
  telepítve.
- **M3 / #15 kész:** a SPA a `/health` válaszából jeleníti meg a plugin
  verzióját (token-kapu + footer); release bump után automatikus.
- **M3 / #9 kész:** `https://cirice.ddns.net:8113/` — `.228` nginx TLS a
  meglévő certtel, router WAN TCP 8113 → `192.168.2.228:8113`; token auth,
  SSE, token-mentes access log.
- **CI / SonarQube:** main-branch statikus elemzés + backend coverage
  (`coverage.xml`), Docker scannerrel, report-only.
- Következik: M3 / #12 GitHub tükör, ha kell.

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
scripts/package.sh    Hordozható egg + sha256 (SPA-val)
scripts/publish_release.sh  GitLab Release + Generic Package feltöltés
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
npm run build      # deluge_mobileui/data/
npm run dev        # proxy: 127.0.0.1:8113
VITE_API_PROXY=http://192.168.2.27:8113 npm run dev
```

A részletek: [docs/webui.md](docs/webui.md).

## CI / release

A `.gitlab-ci.yml` stage-ei: `lint` (ruff + vue-tsc), `test` (pytest +
pytest-cov, Deluge nélkül stubokkal, `coverage.xml` artifact), `quality`
(SonarQube main-branch elemzés, report-only), `build` (SPA + sdist/wheel/egg,
artifact), `release` (manuális `RELEASE_TYPE=patch|minor|major`) és `deploy`
(manuális rsync + `scripts/install.sh` a .27-re).

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
`deluge.plugins` könyvtárba (`MobileUi-<verzió>-py3.x.egg/`), újraindítja a
`deluged`-et, `deluge-console`-lal engedélyezi a plugint, majd ellenőrzi a
`/health`-t. A kicsomagolt forma kell a `data/` statikus kiszolgálásához.
Felülírható: `EGG`, `DELUGE_VENV`, `DELUGE_CONFIG_DIR`, `DELUGE_USER`, `SERVICE`,
`PORT`.

### Hordozható egg

A release-hez csatolt `MobileUi-<verzió>-py3.x.egg` és a hozzá tartozó
`.sha256` önállóan is telepíthető. Repóval:

```bash
sha256sum -c MobileUi-*.egg.sha256
EGG=/path/MobileUi-*.egg ./scripts/install.sh
```

A kicsomagolás kötelező, mert a `static.File` nem tud zipből szolgálni. A Deluge
pluginmanager `pkg_resources.Environment(..., python=None)`-t használ, ezért a
runneren épült py3.13 tagű, pure-Python egg a 3.11-es célon is betöltődik (a
stock pluginek is py3.10/py3.12 eggek a 3.11-en).

Repó nélkül ugyanez kézzel: az egg tartalmát a
`.../site-packages/deluge/plugins/MobileUi-<verzió>-py3.x.egg/` könyvtárba kell
kicsomagolni, majd `systemctl restart deluged` és
`deluge-console ... "plugin -e MobileUi"`.

### Jelenlegi telepítés (2026-11-17)

- Host: `cirice` (192.168.2.27), `deluged` systemd alatt; a plugin **enabled**,
  a 8113 LAN-on figyel, a 8112-es `deluge-web` változatlanul fut.
- Publikus: `https://cirice.ddns.net:8113/` a `.228` nginx TLS proxy mögött
  (router WAN TCP 8113 → `192.168.2.228:8113`), token-kapuval.
- SPA: `http://192.168.2.27:8113/` LAN-on, ugyanaz az API a `/api/*` alatt.
- A generált API-token a hoston a `/root/mobileui-token` fájlban van (600);
  a `mobileui.conf` a `debian-deluged` tulajdona, 600.
- A token nem szerepel a daemon logban, és a `.228` nginx access logja is
  `$uri`-t ír, így a `?token=` sem kerül bele.

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
