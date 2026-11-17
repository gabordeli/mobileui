# Installation and operations

## Compatibility

- **Deluge 2.x** (Python 3.10+); development and the production deployment run
  with **Deluge 2.2.0**, on Python 3.11.
- **Deluge 1.x is not supported** (Python 2, different plugin API).
- 2.0/2.1 use the same plugin API, but are not tested in production; the
  running Deluge version can be checked from the `version` field of the
  `/api/session` response.
- The plugin is a **core plugin** in the `deluged` reactor; no separate service
  is needed. Its own API/SPA listens on 8113, the stock `deluge-web` (8112) is
  untouched.
- The egg is pure Python; the Deluge pluginmanager does not filter on the
  `py3.x` tag, so the unpacked egg loads on the supported Python versions.

## Installation

On the Deluge host, as root, from the repository checkout:

```bash
./scripts/install.sh
```

The script builds the egg with the Deluge venv's Python, **unpacks** it into
the `deluge.plugins` directory (`MobileUi-<version>-py3.x.egg/`), restarts
`deluged`, enables the plugin with `deluge-console`, then checks `/health`.
The unpacked form is required for serving the `data/` static files.
Overridable: `EGG`, `DELUGE_VENV`, `DELUGE_CONFIG_DIR`, `DELUGE_USER`, `SERVICE`,
`PORT`.

The script's defaults are meant for a Debian/Deluge 2.2 installation
(`/opt/deluge-2.2.0`, `/var/lib/deluged/config`, `debian-deluged`); for a
different venv/config/user, specify them with the env variables.

The script also installs optional Python dependencies into the Deluge venv if
they are not present yet: `sentry-sdk` (Sentry) and `pywebpush==2.2.0` +
`py-vapid==1.9.0` + `cryptography<45` (Web Push). The latter must be kept below
45 because of `pyopenssl` 25; if their installation fails, the plugin starts
without Sentry/push. On the browser side, Web Push requires an **HTTPS secure
context** (the push service worker can only be registered on such an origin).

## Portable egg

The `MobileUi-<version>-py3.x.egg` attached to the release and its
`.sha256` can also be installed standalone. With the repo:

```bash
sha256sum -c MobileUi-*.egg.sha256
EGG=/path/MobileUi-*.egg ./scripts/install.sh
```

Unpacking is mandatory, because `static.File` cannot serve from a zip. The
Deluge pluginmanager uses `pkg_resources.Environment(..., python=None)`, so the
pure-Python egg built in CI with the py3.13 tag also loads on the 3.11 target
(the stock plugins are also py3.10/py3.12 eggs on 3.11).

Without the repo, the same by hand: the contents of the egg must be unpacked
into the `.../site-packages/deluge/plugins/MobileUi-<version>-py3.x.egg/`
directory, then `systemctl restart deluged` and
`deluge-console ... "plugin -e MobileUi"`.

## Configuration

`mobileui.conf` in the Deluge config directory (600, owned by the daemon user):

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

The `vapid_subject` is the `sub` claim of the Web Push VAPID; for production
use, enter your own `mailto:` address (some push services validate it).

The `/api/*` endpoints require authentication (except `/health` and the login
endpoints). There are two modes, decided by `auth_mode`:

- `token` – the shared API token above; with an empty token every `/api/*`
  returns 401.
- `password` – Deluge username/password; the client receives an expiring
  session token.
- `both` – both (the static token is break-glass, always admin).

The token never goes into the log. Because of `EventSource`, the SSE
(`/api/events`) also accepts a `?token=<token>` query parameter (the header is
primary; the session token also works in a query parameter).

### Enabling user/password login

The plugin uses the daemon's own `auth` file — the same one `deluge-gtk` and
`deluge-web` log in with. A new account can be added by writing a line into the
file (`username:password:level`, where 1 = read-only, 5 = normal, 10 = admin):

```bash
sudo -u deluged sh -c 'printf "%s\n" "phoneuser:some-password:10" >> /var/lib/deluged/config/auth'
sudo chmod 600 /var/lib/deluged/config/auth
```

The `AuthManager` watches the file's mtime change, so it loads without a
restart, within ~10 s. Then switch the mode (see below), and the **Account**
tab appears on the login screen.

Known limitations: the Deluge `auth` file stores the password in **plaintext**;
the session is lost when `deluged` restarts (the client throws you back to the
login); the login limit is 5 failures/minute/IP. Towards the internet, use it
behind a TLS proxy, because the direct `:8113` is plain HTTP. In the proxy, pass
through the `X-Forwarded-For: $proxy_add_x_forwarded_for` header, otherwise
every client falls under the limit with the proxy's IP.

SSE goes in the `?token=` query string, so in the proxy access log **log
`$uri`**, not `$request`:

```nginx
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

log_format mobileui '$remote_addr - $remote_user [$time_local] '
                    '"$request_method $uri $server_protocol" $status '
                    '$body_bytes_sent "$http_referer" "$http_user_agent"';
access_log /var/log/nginx/mobileui.access.log mobileui;
```

The plugin's own log does not log the request, so the token does not appear
there either.

Left empty, `sentry_dsn` sends no events; when filled in, the plugin sends the
Twisted exceptions to Bugsink (`release` = plugin version, `environment=production`).
The DSN does not go into the log; `set_config` switches it live, `sentry-sdk` is
installed into the Deluge venv by `install.sh`.

Live switching with the `mobileui.set_config` RPC (through `deluge.ui.client` or
the WebUI); the token, `auth_mode`, the port, `enabled` and `sentry_dsn`
take effect immediately, no restart is needed.
If the new port cannot be bound, the plugin restores the old port and returns an
error.

```python
from twisted.internet import defer, reactor
from deluge.ui.client import client


@defer.inlineCallbacks
def main():
    yield client.connect('127.0.0.1', 58846, 'localclient', '<auth-password>')
    print((yield client.mobileui.set_config({'token': '<new-token>'})))
    yield client.disconnect()
    reactor.stop()


reactor.callWhenRunning(main)
reactor.run()
```

The `<auth-password>` comes from the Deluge config `auth` file (the `localclient`
line). After installing a new egg, however, the `deluged` restart is needed (the
plugin code only loads at startup).

## Rollback

Disabling the plugin in the daemon (adjust the `DELUGE_*` values to your
installation; the defaults are meant for Debian/Deluge 2.2):

```bash
DELUGE_VENV="${DELUGE_VENV:-/opt/deluge-2.2.0}"
DELUGE_CONFIG_DIR="${DELUGE_CONFIG_DIR:-/var/lib/deluged/config}"
DELUGE_USER="${DELUGE_USER:-debian-deluged}"

runuser -u "$DELUGE_USER" -- "$DELUGE_VENV/bin/deluge-console" \
  -c "$DELUGE_CONFIG_DIR" "plugin -d MobileUi"
```

Then delete the installed `MobileUi-*.egg/` **directory** from under
`$DELUGE_VENV/lib/python3.*/site-packages/deluge/plugins/` and
`systemctl restart deluged`.
