# Decisions

## D1 – Core plugin in the daemon, on a separate port (2026-11-17)

We run the UI as the **core plugin** `deluge_mobileui` in the `deluged` Twisted
reactor, with its own `Site` on **8113**. Port 8112 is taken by the standalone
`deluge-web`; we do not touch that. This way there is no separate
service/auth/daemon, and there is direct in-process access to the torrent manager and the EventManager.

Limit: the handlers run in the daemon's reactor, so they must not block for long;
the 841-torrent list must be filtered/sliced server-side (#3 spike).

## D2 – Packaging: egg + entry point

Deluge 2.2 scans the `deluge/plugins/` directory (and the `plugins/` subdirectory of the
config) with `pkg_resources.Environment`, so the plugin is built in egg form, with an
entry point:

```
[deluge.plugin.core]
MobileUi = deluge_mobileui:CorePlugin
```

The `setup.py` stays only because of `bdist_egg`; the metadata lives in the
`pyproject.toml`. The version is in one place: `deluge_mobileui/version.py`. The installation
puts the zip egg into an **unpacked `.egg/` directory**: this way the `data/` can be
served from real files (from a zip, `Path(__file__).parent` does not see the resources).

The target host's venv uses **Twisted 22.4.0**, so the requirement is
`Twisted>=22.4`; the plugin only uses Twisted APIs that also exist in 22.4.

## D3 – Config: `mobileui.conf`

`ConfigManager("mobileui.conf", {...})` in the Deluge config directory. Keys:
`enabled`, `port`, `token`, `auth_mode`, `sentry_dsn`, `vapid_subject`.
`/api/*` requires authentication; `/health` and the login endpoints
(`/api/auth`, `/api/login`) are public.

## D4 – Location of the SPA

The Vite build output of `webui/` goes under `deluge_mobileui/data/`, and the plugin
resource serves it. The build artifact is part of the package, so the installation stays a
single egg.

## D5 – Token: empty = closed, live replacement (2026-11-17)

Every `/api/*` request checks the `token` value of the config
(`hmac.compare_digest`), with the exception of `/health`. With an empty token **every**
`/api/*` returns 401, rather than an open API – so a forgotten token does not
silently become public. The config file is created by the plugin on `enable()` and
set to `chmod 600`; the token is not logged.

The `mobileui.set_config({"token"|"port"|"enabled": ...})` takes effect live: the token on the
next request, the port by rebinding, the `enabled` by starting/stopping the listener.
If the new port is taken, the plugin restores the old
port and returns an error. A restart is only needed after installing a new egg (the code
is loaded at startup).


## D6 – Read API: cached status, server-side slicing (2026-11-17)

`/api/torrents` does not call `core.get_torrents_status`, because that can
trigger `post_torrent_updates()` and may wait for a libtorrent alert (according to the earlier
measurement it could be >25 s under load). Instead the plugin iterates in-process over the
`torrentmanager.torrents`, reads the already cached status with `torrent.get_status(keys,
update=False)`, filters server-side
(`state`, `label`, `q`), sorts and slices; only the requested page goes over the network.
The detail refreshes with `update=True` for one torrent, and the file list is there.

Measurement (833 torrents, test instance): p95 for a 50-row list 8.6 ms idle, 14.2 ms under
RPC load; the target is <300 ms. Details: `docs/perf.md`. If the torrent count becomes >5,000,
it may be worth introducing a 1 s snapshot index; right now it is not justified.

## D7 – Write API: core methods, Label plugin, explicit remove_data (2026-11-17)

The write endpoints call the daemon core methods (`pause_torrent`,
`resume_torrent`, `remove_torrent`, `queue_*`), so the GTK/web UI and the plugin
see the same state. The label switch goes through the Label plugin's `set_torrent`,
so that the existing label options (move_completed, limits, queue) take effect;
we do not modify the `auto_add`/label flow.

Adding goes through the magnet (`add_torrent_magnet`) or `.torrent` (`add_torrent_file`,
base64) path, with the `download_location` and `add_paused` options. The label
is validated before the add, then applied to the created torrent. The
`remove_data` only deletes data with an explicit `true` (default `false`).

Error codes: 400 invalid input, 404 unknown torrent, 409 duplicate torrent /
forbidden state / without the Label plugin. On the test instance, on a disposable torrent the full
cycle (add → pause/resume → queue → label clear/set → remove) ran, the
existing 833 torrents and the label counts remained unchanged.

## D8 – SSE: EventManager + 1/s diff, not client polling (2026-11-17)

`/api/events` uses a single daemon-side broadcaster: it subscribes to the EventManager's
`TorrentStateChangedEvent`, `TorrentAddedEvent`, `TorrentRemovedEvent` and
`SessionPausedEvent`/`SessionResumedEvent` events, and diffs the
progress/rate/session fields at 1/s. Deluge 2.2 has no
`TorrentProgressEvent`, so progress does not come from an event; the diff uses the cached
`torrent.get_status(update=False)` (as the read API).

The tick is 1/s, the heartbeat 15 s; the deltas go out in one tick, as separate SSE events.
The broadcaster cleans up the subscribers with `request.notifyFinish()`, on plugin
disable `bye` + finish. Because of the `EventSource`, the token is also accepted in a query
parameter (`?token=`), the header is primary. There is no event replay: after a reconnect
the client synchronizes from the read API, then receives the new deltas.

## D9 – SPA: paginated API + virtualized scroll (2026-11-17)

The Vite build of `webui/` goes under `deluge_mobileui/data/`; the plugin serves it
statically on `/`, the `/api/*` and `/health` remain. Instead of a zip egg, an
unpacked `.egg/` directory is needed, otherwise the `data/` is not accessible
as files (D2).

The list does **not** download the 833 torrents at once: it requests pages of 50
with `offset`, the `RecycleScroller` renders only the visible rows, and it loads the next page
at the end of the scroller. The search has a 300 ms debounce, the
state/label/sort are server-side. The token is in localStorage; the SSE
uses the `?token=` query. The long press opens a sheet after 500 ms
(pause/resume, queue, label, remove), the actions go to the write API.

Verification on the test instance: 833 torrents, 50→100 load on scroll, at 360/390 px
there is no horizontal scroll, long-press sheet + label save toast, SSE
counter 834→833, zero console errors.

## D10 – Detail: separate paginated files API (2026-11-17)

The response of `GET /api/torrents/{id}` stays small: the file list comes from a separate
`GET /api/torrents/{id}/files?offset=&limit=` endpoint, in pages of 100
(max 500), with `{index, path, size, offset, progress}` fields. The detail UI pages through it
with a "More files" button (verified 100→200 on a torrent with 522 files),
so the detail of a large torrent does not pull the whole list at once.

The add sheet sends a magnet or a `.torrent` file to the write API, with a label,
an absolute `download_location` and an optional `add_paused`; the default
path is the session `download_location`. A test torrent added from the UI on the test instance
was created in `Paused`/`movies`/`/tmp/mobileui-add-test` state, then removed and
the count of 833 was restored. Tap → detail, long-press → quick actions.

## D11 – PWA, theme, i18n (2026-11-17)

The SPA got a PWA manifest (`/manifest.webmanifest`), 192/512/apple icons and
`public/sw.js`. The SW is app-shell cache + network-first navigation,
cache-first assets, `/api/*` network-only. Over HTTP on the LAN the service worker does not
register (not a secure context), so the full offline shell/installability will be active
after the #9 HTTPS deploy; the manifest and icons already return 200.

The theme is via a `data-theme` attribute, stored in localStorage; the initial value is
`prefers-color-scheme`, the header button toggles it. The i18n lives in `src/i18n.ts`
(HU/EN, localStorage), the state names are also translated; the API values are unchanged.
Skeleton, offline banner, error+retry, safe-area padding, `:focus-visible` and
Esc-close were added. On the test instance there is no horizontal scroll at 360/390 px (the narrow
header's brand shortens), the HU↔EN and light↔dark switching was verified, 0 console
errors.

## D12 – Auth: Deluge user/password + revocable session (2026-11-17)

Next to the static API token, an optional **Deluge user/password** login was added
(`auth_mode`: `token` / `password` / `both`). The source of the credential is the daemon's
`auth` file (`AuthManager.authorize`), not a separate mobileui user list: one
password everywhere, and the Deluge levels (1/5/10) give the read-only /
normal / admin distinction for free.

Login returns a `secrets.token_urlsafe(32)` session token (30 day TTL,
in memory); the client uses it as `Authorization: Bearer` the same way, so the
other endpoints and the SSE are unchanged. The static token is always admin
(break-glass) and cannot be revoked; the session can be invalidated with logout. Writing
only with `level >= 5`, otherwise 403. Login returns a generic 401 (it does not reveal
whether the user exists), after 5 failures/minute per IP 429; the `X-Forwarded-For` is only the
limit key.

Limit: the Deluge `auth` file stores plaintext passwords; the session is lost when the daemon
restarts; the password of `deluge-web`'s own `web.conf` is a separate system,
we do not use it.

## D13 – Deluge 2.x compatibility from CI (2026-11-17)

The `test` job runs with the `tests/stubs/` shims (fast, without Deluge), so the
real `deluge.*` API changes are caught by a separate **`deluge-compat`** job:
in Docker `deluge==2.0.3` (Python 3.9), `2.1.1` and `2.2.0` (Python 3.11) +
`libtorrent`, then the full `tests/` suite. 2.0.3 runs on 3.9 because of its old Python
requirement; the other two on 3.11. The matrix is built on the symbols the plugin actually
uses (`AuthManager.authorize`, `Core.pause_session` /
`resume_session` / `get_free_space`, `Torrent.get_status/files`,
`AUTH_LEVEL_*`).

The authz matrix (every modifying endpoint read-only → 403, normal → 200/201) and
the logging rule for the `?token=` query (`$uri`, not `$request`) reinforce the same
security line; the details are in the `docs/ci.md` and `docs/api.md`
documents.

## D14 – Bulk selection: long-press + bottom action bar (2026-11-17)

The long-press starts **selection mode** (with the given row) instead of the context sheet
described in D9/D11; in this mode tap toggles, in normal mode tap still opens the
detail. The bottom, fixed action bar gives the item count, "Select all" and
pause/resume/label/remove operations; "Select all" loads the ids matching the filter
from `GET /api/torrents/ids` (max 1000, the `total` is shown
separately). The `POST /api/torrents/bulk` works id by id, collects the errors
(`ok`/`failed`), so one bad id does not stop the rest.

The ContextSheet is gone (the detail already knew the same operations); the
single-torrent queue/label/remove stayed in the detail. v1 has no undo,
no cross-filter exception and no bulk queue.

## D15 – File priority: 0/1/4/7, "Only this", server-side search (2026-11-17, updated 2026-11-18)

The detail's file list uses the Deluge `set_file_priorities`, which expects the
**complete** list; the handler reads the current priorities, and applies only the
changes, so because of the paginated list the client does not need to know all
files. The checkbox toggles 0/4, "Only this" sets all to 0 and the
selected one to 4. Since v1.1.0 the search is server-side: the `q` parameter of
`GET /api/torrents/{id}/files` filters the full path list **before** pagination,
so files beyond the first page are found, and `total` is the filtered count.
The UI debounces the input (300 ms) and keeps the request sequence so a slower
response cannot overwrite a newer one. The 1/7 (low/high) priority is available
in the API, the UI for now uses 0/4.

## D16 – Speed limit: global vs. per-torrent (2026-11-17)

The global limits are the `max_download_speed` / `max_upload_speed`
keys of the Deluge `core.conf` (KiB/s, `-1` = unlimited); the `Core.set_config` applies them
immediately through the PreferencesManager callbacks. The per-torrent value is set by
`Torrent.set_max_download_speed` / `set_max_upload_speed` (KiB/s; `-1` = the
global value, `0` = unlimited). The session sheet gives global fields and
night (512/128) / unlimited presets, the detail gives per-torrent
fields. The handler writes only the given fields; the validation is `-1` or `>= 0`.

## D17 – PWA share target: /share on the SW, magnet in the add sheet (2026-11-17)

The manifest `share_target` points to the `/share` route with GET; the server does not
know this route, so the service worker serves the navigation with the app shell
(the query is preserved). The App looks for the `magnet:?` link in the `text` / `url` / `title`
parameter with a regex, and opens the add sheet pre-filled; it removes the query
from the address bar with `replaceState`. Android Chrome + **installed
PWA** is required; iOS Safari does not support the share target.

## D18 – Label CRUD from the filter bar, tracker list + reannounce (2026-11-17)

We use the Label plugin's `add()` / `remove()` exports; the plugin's validation
errors (generic `Exception`) are mapped to 400, the absence of the plugin to 409. The
label sheet opens from the 🏷 button of the filter bar, not as a fifth
icon in the header; the plugin's `clean_config` puts the torrents of a deleted label under `No Label`.
The detail shows the `get_status(["trackers", "tracker_status"])` list;
the reannounce calls `Torrent.force_reannounce()`, the `false` result is not an
error, but `200 {reannounced: false}`.

## D19 – Web Push: VAPID + event-based notification (2026-11-17)

Push builds on the stock Deluge events (`TorrentFinishedEvent`,
`TorrentStateChangedEvent`), not a separate poller. The VAPID key is generated next to the
Deluge config, the subscriptions in a separate JSON file (mode 600); the server
stores only the browser's `PushSubscription`, the content is rendered by the `push`
handler of `sw.js`. Sending runs in `deferToThread`, because pywebpush
uses blocking HTTP; the 404/410 "dead" subscriptions are deleted by the send. The
frontend offers the toggle only over HTTPS (secure context); it gets a place in the session
sheet so that it does not increase the header icons. The `vapid_subject`
config provides the VAPID `sub` claim, because the services validate the
`mailto:`/URL format differently.

## D20 – Internal IPs in the git history: accepted (2026-11-17)

The public history contains `192.168.2.x` (RFC1918, behind NAT) in 6 commits;
there is none in the current tracked tree, and the history contains no token
(`glpat-`, `sqp_`, `sntrys_`, `ghp_`). `git filter-repo` + force-push would rewrite the entire
history and the `v0.1.1`–`v0.2.0` tags, which would also affect the GitHub releases and the
push mirror; the benefit of hiding the home-lab IP does not outweigh this
risk. Decision: **accepted**. If it is still needed later, in a separate, approved
force-push issue, with verification of the release assets.
