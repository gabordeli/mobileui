# Telepítés és üzemeltetés

## Kompatibilitás

- **Deluge 2.x** (Python 3.10+); a fejlesztés és az éles telepítés
  **Deluge 2.2.0**-val, Python 3.11-en fut.
- **Deluge 1.x nem támogatott** (Python 2, eltérő plugin API).
- A 2.0/2.1 ugyanazt a plugin API-t használja, de nincs élesben tesztelve; a
  futó Deluge verziója a `/api/session` válaszának `version` mezőjéből
  ellenőrizhető.
- A plugin **core plugin** a `deluged` reactorjában; nem kell külön service.
  A saját API/SPA a 8113-on figyel, a gyári `deluge-web` (8112) érintetlen.
- Az egg pure Python; a Deluge pluginmanager a `py3.x` taget nem szűri, ezért a
  kicsomagolt egg a támogatott Python-verziókon betöltődik.

## Telepítés

A Deluge hoston, rootként, a repó checkoutjából:

```bash
./scripts/install.sh
```

A script a Deluge venv Pythonjával épít egg-et, **kicsomagolja** a
`deluge.plugins` könyvtárba (`MobileUi-<verzió>-py3.x.egg/`), újraindítja a
`deluged`-et, `deluge-console`-lal engedélyezi a plugint, majd ellenőrzi a
`/health`-t. A kicsomagolt forma kell a `data/` statikus kiszolgálásához.
Felülírható: `EGG`, `DELUGE_VENV`, `DELUGE_CONFIG_DIR`, `DELUGE_USER`, `SERVICE`,
`PORT`.

A script alapértékei Debian/Deluge 2.2 telepítésre valók (`/opt/deluge-2.2.0`,
`/var/lib/deluged/config`, `debian-deluged`); más venv/config/user esetén az
env változókkal add meg őket.

A script opcionális Python-függőségeket is telepít a Deluge venvbe, ha még
nincsenek: `sentry-sdk` (Sentry) és `pywebpush==2.2.0` + `py-vapid==1.9.0` +
`cryptography<45` (Web Push). Utóbbiakat a `pyopenssl` 25 miatt kell a 45 alatt
tartani; ha a telepítésük elbukik, a plugin a Sentry/push nélkül is elindul.
A Web Push böngészőoldalon **HTTPS secure contextet** igényel (a push
service worker csak ilyen originen regisztrálható).

## Hordozható egg

A release-hez csatolt `MobileUi-<verzió>-py3.x.egg` és a hozzá tartozó
`.sha256` önállóan is telepíthető. Repóval:

```bash
sha256sum -c MobileUi-*.egg.sha256
EGG=/path/MobileUi-*.egg ./scripts/install.sh
```

A kicsomagolás kötelező, mert a `static.File` nem tud zipből szolgálni. A Deluge
pluginmanager `pkg_resources.Environment(..., python=None)`-t használ, ezért a
CI-ben épült py3.13 tagű, pure-Python egg a 3.11-es célon is betöltődik (a
stock pluginek is py3.10/py3.12 eggek a 3.11-en).

Repó nélkül ugyanez kézzel: az egg tartalmát a
`.../site-packages/deluge/plugins/MobileUi-<verzió>-py3.x.egg/` könyvtárba kell
kicsomagolni, majd `systemctl restart deluged` és
`deluge-console ... "plugin -e MobileUi"`.

## Konfiguráció

`mobileui.conf` a Deluge config könyvtárában (600, a daemon user tulajdona):

```json
{
  "enabled": true,
  "port": 8113,
  "token": "",
  "auth_mode": "token",
  "sentry_dsn": "",
  "vapid_subject": "mailto:admin@example.invalid"
}
```

A `vapid_subject` a Web Push VAPID `sub` claimje; éles használatnál írd be a
saját `mailto:` címedet (egyes push szolgáltatások validálják).

A `/api/*` végpontok hitelesítést kérnek (`/health` és a login végpontok
kivételével). Két mód van, az `auth_mode` dönt:

- `token` – a fenti közös API-token; üres token esetén minden `/api/*` 401.
- `password` – Deluge felhasználónév/jelszó; a kliens lejáró session tokent kap.
- `both` – mindkettő (a statikus token break-glass, mindig admin).

A token nem kerül logba. Az SSE (`/api/events`) az `EventSource` miatt
`?token=<token>` query paramétert is elfogad (a header az elsődleges; a session
token is működik query paraméterben).

### User/jelszó belépés bekapcsolása

A plugin a daemon saját `auth` fájlját használja — ugyanazt, amivel a
`deluge-gtk` és a `deluge-web` belép. Új fiók a fájlba írt sorral vehető fel
(`username:password:level`, ahol 1 = read-only, 5 = normal, 10 = admin):

```bash
sudo -u deluged sh -c 'printf "%s\n" "phoneuser:valami-jelszo:10" >> /var/lib/deluged/config/auth'
sudo chmod 600 /var/lib/deluged/config/auth
```

Az `AuthManager` a fájl mtime-változását figyeli, így restart nélkül, ~10 s
alatt betölti. Ezután állítsd át a módot (lásd lent), és a belépőképernyőn
megjelenik a **Fiók** fül.

Ismert korlátok: a Deluge `auth` fájl a jelszót **plaintext** tárolja; a
session a `deluged` restartjakor elveszik (a kliens visszadobja a loginra);
a login limit 5 hiba/perc/IP. Internet felé a TLS proxy mögött használd, mert a
közvetlen `:8113` sima HTTP. A proxyban add át az
`X-Forwarded-For: $proxy_add_x_forwarded_for` headert, különben minden kliens a
proxy IP-jével esik a limit alá.

Az SSE `?token=` query stringben megy, ezért a proxy access logjában **`$uri`-t**
naplózz, ne `$request`-et:

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

log_format mobileui '$remote_addr - $remote_user [$time_local] '
                    '"$request_method $uri $server_protocol" $status '
                    '$body_bytes_sent "$http_referer" "$http_user_agent"';
access_log /var/log/nginx/mobileui.access.log mobileui;
```

A plugin saját logja nem naplózza a requestet, így a token ott sem jelenik meg.

A `sentry_dsn` üresen hagyva nem küld eseményt; kitöltve a plugin a Bugsinkbe
küldi a Twisted kivételeket (`release` = plugin verzió, `environment=production`).
A DSN nem kerül a logba; a `set_config` élőben átállítja, a `sentry-sdk`-t az
`install.sh` telepíti a Deluge venvbe.

Élő átállítás a `mobileui.set_config` RPC-vel (a `deluge.ui.client`-en vagy a
WebUI-n át); a token, az `auth_mode`, a port, az `enabled` és a `sentry_dsn`
azonnal érvényesül, restart nem kell.
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

## Visszaállítás

A plugin letiltása a daemonban (a `DELUGE_*` értékeket a telepítésedhez
igazítsd; az alapértékek Debian/Deluge 2.2-re valók):

```bash
DELUGE_VENV="${DELUGE_VENV:-/opt/deluge-2.2.0}"
DELUGE_CONFIG_DIR="${DELUGE_CONFIG_DIR:-/var/lib/deluged/config}"
DELUGE_USER="${DELUGE_USER:-debian-deluged}"

runuser -u "$DELUGE_USER" -- "$DELUGE_VENV/bin/deluge-console" \
  -c "$DELUGE_CONFIG_DIR" "plugin -d MobileUi"
```

Majd a telepített `MobileUi-*.egg/` **könyvtár** törlése a
`$DELUGE_VENV/lib/python3.*/site-packages/deluge/plugins/` alól és
`systemctl restart deluged`.
