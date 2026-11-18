# API

Base URL: `http://127.0.0.1:8113` (LAN). `/health`, `/api/auth` and
`/api/login` are public; every other `/api/*` endpoint requires authentication.

## Auth

There are two login modes, decided by the `auth_mode` key in `mobileui.conf`
(`token` | `password` | `both`, default `token`):

- **token** – the shared API token configured in the plugin (break-glass, admin level).
- **password** – Deluge username/password from the daemon `auth` file; after
  login the client receives an expiring **session token**, and uses it as
  `Authorization: Bearer`, the same way as the static token.

```http
Authorization: Bearer <token>
```

Successful login:

```http
POST /api/login
Content-Type: application/json

{"username": "admin", "password": "..."}
```

```json
{"token": "…", "username": "admin", "level": 10, "expires": 1797518452}
```

- The session token lives for 30 days, and is lost when `deluged` restarts.
- `level` is the Deluge auth level: 1 = read-only, 5 = normal, 10 = admin.
  The static token is always admin.
- Writing (`POST`/`PATCH`) only with `level >= 5`; for a read-only account
  `403 {"error": "forbidden", "message": "Read-only account"}`.
- `POST /api/logout` invalidates the session token (the static token is not
  revocable; there `{"ok": true, "session": false}`).

Errors:

| Code | Body | When |
| --- | --- | --- |
| 401 | `{"error": "unauthorized", "message": "Missing or invalid credentials"}` | missing/invalid token or password; `WWW-Authenticate: Bearer realm="mobileui"` |
| 403 | `{"error": "forbidden", "message": "Read-only account"}` | write at read-only level |
| 429 | `{"error": "too_many_attempts", …}`, `Retry-After: 60` | 5 failed logins / minute / IP |

- An empty `token` in the config with `auth_mode=token` → every `/api/*` returns 401.
- The token lives in `mobileui.conf` (600); live replacement: `mobileui.set_config`.
- The login limit key is the first address of `X-Forwarded-For`, if present, otherwise the
  peer address. The auth decision is not affected by this.
- The SSE `?token=` parameter also accepts the session token.

## GET /api/auth

Public. Without a token it only returns the modes; when authenticated it also returns the identity:

```json
{"mode": "both", "modes": ["token", "password"], "token_set": true}
```

```json
{
  "mode": "both",
  "modes": ["token", "password"],
  "token_set": true,
  "authenticated": true,
  "username": "admin",
  "level": 10,
  "write": true
}
```

When logged in with the static token, `username` is `"token"`.

## GET /health

Public, even without auth:

```json
{"ok": true, "version": "1.1.0", "port": 8113}
```

## GET /api

Token-protected index:

```json
{
  "version": "1.1.0",
  "endpoints": [
    "/api/auth", "/api/login", "/api/logout", "/api/session",
    "/api/session/pause", "/api/session/resume", "/api/session/limits",
    "/api/session/queue",
    "/api/labels",
    "/api/torrents", "/api/torrents/ids", "/api/torrents/bulk",
    "/api/torrents/{id}", "/api/torrents/{id}/reannounce",
    "/api/torrents/{id}/recheck",
    "/api/torrents/{id}/move", "/api/push/config",
    "/api/push/subscribe", "/api/push/test", "/api/push/subscriptions",
    "/api/events"
  ]
}
```

## GET /api/session

```json
{
  "download_rate": 0.0,
  "upload_rate": 0.0,
  "payload_download_rate": 0.0,
  "payload_upload_rate": 0.0,
  "queue": {
    "max_active_downloading": 0,
    "max_active_seeding": 30,
    "max_active_limit": 0,
    "queue_new_to_top": false
  },
  "num_torrents": 42,
  "version": "2.2.0",
  "download_location": "/data/downloads",
  "paused": false,
  "free_space": 53687091200,
  "max_download_speed": -1.0,
  "max_upload_speed": -1.0
}
```

The `version` is the Deluge version; the plugin version is in `/health` and in the
`/api` index. The `free_space` is the free space of `download_location` in bytes
(if it cannot be measured, `null`). The `max_*_speed` are the global limit in KiB/s;
`-1` = unlimited.

## POST /api/session/pause, /api/session/resume

Pause / resume all torrents (write level required; read-only →
403). The response is the actual state:

```json
{"paused": true}
```

## PATCH /api/session/limits

Global speed limit (KiB/s; `-1` = unlimited). Write level, read-only → 403.
At least one of the fields is required:

```json
{"max_download_speed": 512, "max_upload_speed": 128}
```

`200 {"max_download_speed": 512.0, "max_upload_speed": 128.0}`; `-2` → 400.
It writes into the Deluge `core.conf`, the PreferencesManager callback applies it immediately.

## PATCH /api/session/queue

Active-torrent queue settings (write level, read-only → 403). At least one of the
fields is required; the values match the Deluge `core.conf` ranges
(`-1` = unlimited, max. 9999):

```json
{
  "max_active_downloading": 3,
  "max_active_seeding": 5,
  "max_active_limit": 8,
  "queue_new_to_top": false
}
```

`200` returns the updated fields; the same values are in the `queue` object of
`GET /api/session`. `queue_new_to_top` is a bool, the three counts are integers
(bad field → 400).

## GET /api/labels

```json
{
  "labels": [
    {"id": "movies", "count": 93},
    {"id": "series", "count": 30}
  ],
  "no_label": 0
}
```

The count only counts existing torrents. If the Label plugin is not enabled:
`{"labels": [], "no_label": <total>}`.

## POST /api/labels

New label (write level, read-only → 403). It calls the Label plugin's `add()`; the
name is `[a-z0-9_.-]`, lowercased:

```json
{"id": "new-label"}
```

`201 {"id": "new-label"}`; invalid/duplicate name → 400; without the plugin → 409.

## DELETE /api/labels/{id}

Delete a label (write level). Its torrents move under `No Label`:

`200 {"id": "new-label", "removed": true}`; unknown label → 400; without the
plugin → 409.

## GET /api/torrents

Query parameters:

| Param | Default | Description |
| --- | --- | --- |
| `state` | – | exact state (`Paused`, `Downloading`, …) or `All` |
| `label` | – | label id, or `No Label` |
| `q` | – | case-insensitive substring in the name |
| `sort` | `name` | `name`, `state`, `progress`, `ratio`, `eta`, `total_size`, `time_added`, `download_payload_rate`, `upload_payload_rate`, `label`; `-` prefix = descending |
| `offset` | `0` | >= 0 |
| `limit` | `50` | 1–200 |

Response:

```json
{
  "total": 42,
  "offset": 0,
  "limit": 50,
  "torrents": [
    {
      "id": "b1d2c99a24f841dc7a347ff6680d96c4907ca880",
      "name": "17.Again.2009...",
      "state": "Paused",
      "progress": 100.0,
      "label": "movies",
      "download_payload_rate": 0,
      "upload_payload_rate": 0,
      "eta": 0,
      "ratio": 0.0,
      "total_size": 11073742312,
      "save_path": "/data/downloads",
      "time_added": 1763380000,
      "message": "OK"
    }
  ]
}
```

`total` is the total number of matches after filtering, `torrents` is only the requested page.
The `progress` is 0–100, the rates are in bytes/s, the `eta` in seconds (`-1` = infinite),
the `ratio` `-1` = infinite. The `message` is the Deluge status message; based on the `state`
`Error` and a message that is not `OK`, the UI shows an error badge.

## GET /api/torrents/ids

The torrent ids matching the filters (for the client's "Select all").
The same `state`, `label`, `q` parameters as in the list; there is no `sort`/`offset`.
At most 1000 ids:

```json
{"ids": ["b1d2…", "a3f4…"], "total": 847, "limit": 1000}
```

The `total` is the total number of matches; above 1000 the `ids` gives the first 1000.

## GET /api/torrents/{id}

Detailed status of one torrent. In addition to the fields of `get_status`:

| Key | Description |
| --- | --- |
| `id` | torrent hash |
| `label` | label id or `No Label` |
| `trackers` | the tracker list (url, tier, verified, message, …) |
| `tracker_status` | the status message of the current tracker |
| `num_files` | number of files |

Unknown id → `404 {"error": "not_found", ...}`. The file list comes from a separate, paginated
endpoint (see below), so the detail response stays small.

## GET /api/torrents/{id}/files

Paginated file list (detail only; not present in the list):

| Param | Default | Description |
| --- | --- | --- |
| `offset` | `0` | >= 0 |
| `limit` | `100` | 1–500 |
| `q` | – | optional case-insensitive path substring; filters before pagination |

```json
{
  "total": 522,
  "offset": 100,
  "limit": 100,
  "files": [
    {"index": 100, "path": "dir/file.mkv", "size": 12345, "offset": 0, "progress": 1.0, "priority": 4}
  ]
}
```

The `progress` is 0–1. Unknown torrent → 404, invalid limit/offset → 400.
With `q`, `total` is the number of matches after filtering, not the whole file
list. The `priority` is the Deluge file priority (0 = skipped, 1 = low,
4 = normal, 7 = high).

## PATCH /api/torrents/{id}/files

Set file priority (write level, read-only → 403). Two modes:

```json
{"files": [{"index": 0, "priority": 4}, {"index": 1, "priority": 0}]}
```

```json
{"only": 2}
```

- `files`: 1+ items; `priority` only 0, 1, 4 or 7; index within the range of the file list.
- `only`: all files become 0, the given index becomes 4.
- `200 {"id": "...", "priorities": [4, 0, …]}` — the complete, updated list.
- Unknown index / priority → 400; no file metadata (magnet) → 409.
- `set_file_priorities` in Deluge expects the complete list; the handler reads the
  current priorities and applies only the changes.

## POST /api/torrents/{id}/pause

Pause one torrent. `200 {"id": "...", "state": "Paused"}`; unknown id → 404;
a torrent in `Error` state → 409.

## POST /api/torrents/{id}/resume

Resume one torrent. `200 {"id": "...", "state": "..."}`; unknown id → 404.

## POST /api/torrents/{id}/remove

Body (optional):

```json
{"remove_data": false}
```

`200 {"id": "...", "removed": true, "remove_data": false}`. `remove_data`
defaults to `false`; if Deluge cannot remove it → 409.

## POST /api/torrents/{id}/queue

```json
{"action": "up"}
```

`action`: `up`, `down`, `top`, `bottom`. `200 {"id": "...", "action": "up"}`;
unknown action → 400, unknown torrent → 404.

## POST /api/torrents/{id}/reannounce

Force tracker reannounce (write level; read-only → 403):

`200 {"id": "...", "reannounced": true}`; if Deluge could not send it,
`reannounced: false`; unknown torrent → 404.

## POST /api/torrents/{id}/recheck

Force a piece recheck (write level; read-only → 403):

`200 {"id": "...", "rechecked": true}`; if libtorrent could not start it,
`rechecked: false`; unknown torrent → 404. The torrent enters `Checking` and
the UI follows the state through SSE.

## POST /api/torrents/{id}/move

Actual file move with the Deluge `Torrent.move_storage()` (write level;
read-only → 403):

```json
{"location": "/data/downloads/movies"}
```

- An absolute, non-empty path is required; relative path → 400, unknown torrent → 404.
- If the torrent is already `Moving`, or Deluge could not start it → 409.
- `200 {"id": "...", "destination": "...", "moving": true}`; the move
  runs asynchronously in libtorrent, the torrent state becomes `Moving`, and at the end an SSE
  state delta signals completion. The target directory is created by Deluge; the
  operation only needs enough free space, and because of `flags=2` it does not overwrite an
  existing target file.

## PATCH /api/torrents/{id}

```json
{"label": "movies"}
```

- `{"label": "No Label"}` or `{"label": null}` → delete the label.
- Unknown label → 400; without the Label plugin → 409; unknown torrent → 404.
- `200 {"id": "...", "label": "movies"}`.

The label goes through the Label plugin's `set_torrent`, so the label options
(`move_completed`, speed limits, queue) take effect according to the existing logic.

## PATCH /api/torrents/{id}/limits

Per-torrent speed limit (KiB/s): `-1` = the global value, `0` =
unlimited, `>0` = limit. Write level, read-only → 403; at least one of the fields
is required:

```json
{"max_download_speed": 64, "max_upload_speed": 32}
```

`200 {"id": "...", "max_download_speed": 64.0, "max_upload_speed": 32.0}`;
`-2` → 400. The two fields also appear in the `get_torrent` response.

## POST /api/torrents/bulk

One operation on several torrents. Write level required (read-only → 403).

```json
{
  "action": "pause|resume|remove|label",
  "torrent_ids": ["b1d2…", "a3f4…"],
  "label": "movies",
  "remove_data": false
}
```

- `torrent_ids`: 1–1000 ids; empty list → 400.
- `label` only with `action=label`; `No Label`/`null` → delete the label;
  unknown label → 400; without the Label plugin → 409.
- `remove_data` only with `remove` (default false).
- Bad ids do not stop the rest:

```json
{"ok": 2, "failed": [{"id": "missing", "error": "unknown torrent"}]}
```

- `200` even if some ids failed; `failed` contains the reason.

## POST /api/torrents

New torrent from a magnet or a `.torrent` file.

JSON body:

```json
{
  "magnet": "magnet:?xt=urn:btih:...",
  "label": "movies",
  "download_location": "/data/downloads",
  "add_paused": true
}
```

Or the file as base64:

```json
{
  "filename": "x.torrent",
  "file_base64": "<base64>",
  "label": "movies",
  "download_location": "/data/downloads"
}
```

Raw upload (not a JSON content-type), with query parameters:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-bittorrent" \
  --data-binary @x.torrent \
  "http://127.0.0.1:8113/api/torrents?filename=x.torrent&label=movies&download_location=/data/downloads&add_paused=true"
```

- `download_location` must be an absolute path; if not given, the Deluge default.
- `add_paused` is optional (default `false`); with `true` it does not start.
- `201 {"id": "...", "label": "...", "download_location": "..."}`.
- Duplicate torrent → 409; invalid magnet/file/field → 400.

## GET /api/events

SSE (`text/event-stream`) live updates. The token can be given either in the `Authorization: Bearer`
header or in the `?token=<token>` query parameter (the `EventSource`
cannot send a custom header). The stream stays open until the connection is closed.

> **Logging:** the token travels in the query string, so in the proxy access
> log you must log `$uri`, not `$request` (the latter also contains the query).
> The plugin's own log does not log the request; the reverse proxy (nginx)
> uses the `$uri` logformat.

First event:

```text
event: hello
data: {"version":"1.1.0","heartbeat":15,"num_torrents":42}
```

After that torrent deltas (`event: torrent`) and session deltas (`event: session`):

```json
{"type": "state", "id": "<hash>", "fields": {"state": "Paused"}}
{"type": "progress", "id": "<hash>", "fields": {"progress": 42.5, "download_payload_rate": 1024, "upload_payload_rate": 0, "eta": 120}}
{"type": "added", "id": "<hash>", "fields": {}}
{"type": "removed", "id": "<hash>", "fields": {}}
{"type": "session", "id": null, "fields": {"download_rate": 1024.0, "paused": false}}
```

- The state/added/removed events come from the Deluge EventManager; the
  progress/rate/session fields are diffed by the server at 1/s (Deluge 2.2 has no
  `TorrentProgressEvent`), so at most one packet goes out in one tick.
- A `: heartbeat` comment every 15 seconds.
- The `fields` object always contains only the changed fields (except for `hello`).
- Client disconnect → the server removes the subscriber; with `EventSource` the
  browser reconnects automatically (there is no event replay).
- On plugin disable `event: bye`, then the stream closes.

## GET /api/push/config

Returns the Web Push VAPID public key and the number of registered subscriptions.
The browser creates the `PushSubscription` from this key.

```json
{"enabled": true, "public_key": "B...", "subscriptions": 1}
```

The VAPID key pair is generated on the first request
(`mobileui-vapid.pem`, 600), the subscriptions are stored in the `mobileui-push.json` file
(600, atomic write, max. 20).

## POST /api/push/subscribe

Registers a browser's `PushSubscription.toJSON()` object. The same
`endpoint` is idempotent (it is not duplicated).

```json
{"endpoint": "https://push.example/...", "keys": {"p256dh": "...", "auth": "..."}}
```

Response: `201 {"count": 1}`. Invalid input → `400`. The store keeps an
optional `user_agent` for the device list; the request `User-Agent` is used when
present.

## GET /api/push/subscriptions

Lists stored devices without their endpoints/keys (read-only accounts allowed):

```json
{
  "subscriptions": [
    {
      "id": "a1b2c3d4e5f6",
      "host": "push.example",
      "added": 1797518452,
      "last_seen": 1797518452,
      "user_agent": "Mozilla/5.0 …"
    }
  ]
}
```

The `id` is a short hash of the endpoint; use it for revocation. Endpoints that
are loopback/private/link-local are rejected at registration (literal IPs and
localhost); delivery also re-checks the resolved addresses and skips non-public
hosts.

## DELETE /api/push/subscriptions

```json
{"id": "a1b2c3d4e5f6"}
```

`200 {"unsubscribed": true|false}`. Unknown id → `200 false` (idempotent).

## DELETE /api/push/subscribe

```json
{"endpoint": "https://push.example/..."}
```

Response: `200 {"unsubscribed": true|false}`. The deletion does not call the browser's
`unsubscribe()`; the client does that, the server only drops the stored endpoint.

## POST /api/push/test

Queues one test notification to a stored subscription (read-only accounts may
use it):

```json
{"endpoint": "https://push.example/..."}
```

`200 {"queued": true}`; an unknown endpoint → 404, an invalid endpoint → 400.
Delivery runs in `deferToThread`, so the response only confirms queueing.

The server sends a notification to the registered browsers on the `TorrentFinishedEvent` and the
`TorrentStateChangedEvent` (`Error`) events; delivery
runs in `deferToThread`, so that the reactor is not blocked. The payload carries
`kind` (`finished` / `error` / `test`), `name`, `message`, `url` and `tag`; the
service worker renders HU/EN text from `navigator.language` (the `title`/`body`
fields remain as an English fallback). Expired subscriptions that answer
404/410 are removed automatically. The `vapid_subject` config
(default `mailto:admin@example.invalid`) is the VAPID `sub` claim.

## M1 endpoints

All M1 endpoints are implemented: `/health`, `/api/auth`, `/api/login`,
`/api/logout`, `/api/session`, `/api/labels`, `/api/torrents`,
`/api/torrents/{id}` (GET/PATCH), `/api/torrents/{id}/files`, the torrent operations
(`pause`, `resume`, `remove`, `queue`), `POST /api/torrents` and `/api/events`.

## Errors

JSON, at least `{"error": "...", "message": "..."}`:

| Status | `error` | When |
| --- | --- | --- |
| 400 | `bad_request` | invalid query/JSON/field, password mode disabled |
| 401 | `unauthorized` | missing/invalid token or password, expired session |
| 403 | `forbidden` | write by a read-only account |
| 404 | `not_found` | unknown route or torrent id |
| 409 | `conflict` | duplicate torrent, forbidden state, without the Label plugin |
| 429 | `too_many_attempts` | 5 failed logins / minute / IP |
| 500 | `internal_error` | unexpected error in the daemon |
| 503 | `auth_unavailable` | the Deluge `AuthManager` is not available |

Performance: [perf.md](perf.md).
