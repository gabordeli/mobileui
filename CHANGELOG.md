# Changelog

## [Unreleased]

## [1.2.0] - 2026-11-18

- The torrent list can be sorted by the added date (`time_added`), newest
  first.
- Force recheck from the torrent detail (`POST /api/torrents/{id}/recheck`).
- Active-torrent queue settings in the session sheet
  (`PATCH /api/session/queue`): max active downloading/seeding/total and
  "new torrents to top".
- Torrent options panel in the detail (`GET/PATCH /api/torrents/{id}/options`):
  sequential download, first/last pieces, auto-managed, super seeding, stop
  ratio and the per-torrent connection/upload-slot limits.
- Add torrent from an http(s) URL in the add sheet; Deluge downloads the
  `.torrent` file asynchronously (`POST /api/torrents {"url": ...}`).
- Server-side directory picker for the add and move flows (`GET /api/fs`):
  directory-only listing, `realpath`, 1000-entry cap, off-reactor thread.
- Docs: D15 now describes the server-side file search, and the post-1.0 impact
  study carries a v1.2.0 status note.

## [1.1.1] - 2026-11-18

- Release 1.1.1.

## [1.1.0] - 2026-11-18

- Web Push: language-neutral payloads rendered HU/EN by the service worker, a
  per-device test notification (`POST /api/push/test`), a device list with
  revocation (`GET/DELETE /api/push/subscriptions`), and loopback/private
  endpoint rejection at registration and delivery.
- File search in the torrent detail is server-side (`?q=`), filtering before
  pagination so files outside the first page are found.
- Offline read cache: the service worker keeps the last successful
  `/api/torrents*`, `/api/session` and `/api/labels` responses and serves them
  with a stale marker after an offline reload; logout clears the cache.
- Bulk remove has an explicit “Delete downloaded data too” option, and the
  detail disables pause/remove/move while a torrent is `Moving`.
- Dialogs use a focus trap: `#app` is inert while open, Tab stays inside, and
  focus returns to the trigger on close.
- The release job pushes only the new version tag, so deleted tags stay deleted.
- Post-1.0 impact study in `docs/impact-post-1.0.md`.

## [1.0.0] - 2026-11-17

- Web Push notifications: a toggle in the session sheet subscribes the browser
  (`GET /api/push/config`, `POST|DELETE /api/push/subscribe`), and the plugin
  sends a notification on `TorrentFinishedEvent` and on `TorrentStateChangedEvent`
  (`Error`). The service worker shows the notification and opens the torrent
  detail from the `/?torrent=<id>` deep link. VAPID keys and subscriptions are
  stored next to `mobileui.conf` (600); delivery runs off the reactor thread and
  prunes dead (404/410) subscriptions. Requires HTTPS and the optional
  `pywebpush==2.2.0` / `py-vapid==1.9.0` / `cryptography<45` packages, which
  `install.sh` installs.
- File priorities in the torrent detail: a per-file download toggle and
  "Only this" (`PATCH /api/torrents/{id}/files`), plus a search box over the
  loaded file list.
- Global and per-torrent speed limits (`PATCH /api/session/limits`,
  `PATCH /api/torrents/{id}/limits`) with night-mode and unlimited presets.
- PWA share target (Android): a shared magnet opens the add sheet prefilled;
  the service worker serves `/share` with the app shell.
- Label CRUD from the filter bar (create/delete; deleted labels move torrents
  to No label), plus a tracker list and force reannounce in the detail.
- The torrent list shows an error badge when the state is `Error` or the
  status message is not `OK`; the `Error` filter is available in the UI.
- The add sheet remembers the last path and label (clearable), and the detail
  can copy the magnet link or the infohash to the clipboard.
- The session sheet draws a download/upload sparkline for the last 60 seconds
  from the SSE session deltas.
- The torrent detail is compact on mobile: three primary rate/ETA chips, one
  muted ratio/peers/seeds/size/added line, and a collapsible tracker bar.
- Torrent storage move from the detail (`POST /api/torrents/{id}/move`), using
  Deluge `move_storage`; the UI follows the `Moving` state through SSE.
- The account panel uses a person icon instead of the misleading gear icon.
- English documentation (README, CONTRIBUTING, AGENTS and `docs/*.md`) with a
  new `docs/usage.md` mobile guide and updated screenshots.
- All open SonarQube issues fixed; the main-branch quality gate remains
  blocking with zero new violations.

## [0.2.0] - 2026-11-17

- Optional Deluge username/password login next to the static API token
  (`auth_mode`: `token` / `password` / `both`). Sessions are revocable, expire
  after 30 days and map Deluge auth levels, so a read-only (1) account can view
  but not modify torrents. The static token stays as the admin break-glass.
- `/api/auth`, `/api/login` and `/api/logout` endpoints; `403` for read-only
  writes and a per-IP login rate limit (`429`).
- Login gate with account/token tabs, sign-out in the account panel and a
  read-only UI that hides the write actions.
- Session sheet from the header stats: free space, torrent count, rates and a
  one-tap pause/resume for the whole session (`/api/session/pause|resume`).
  Read-only accounts see the stats without the action.
- Authorization matrix tests for every mutating endpoint (read-only → 403,
  normal → 200/201) and a documented `$uri` proxy log format so the SSE
  `?token=` never reaches access logs.
- `deluge-compat` CI job running the backend suite against real Deluge 2.0.3,
  2.1.1 and 2.2.0.
- Bulk selection: long-press starts selection, the bottom action bar batch
  pauses/resumes/labels/removes torrents (`POST /api/torrents/bulk`), and
  "All" loads every matching id (`GET /api/torrents/ids`, up to 1000). The
  long-press context sheet is replaced by selection mode; single-torrent
  actions stay in the detail.

## [0.1.3] - 2026-11-17

- Release 0.1.3.

## [0.1.2] - 2026-11-17

- Release 0.1.2.

## [0.1.1] - 2026-11-17

- Release 0.1.1.

## [0.1.0] - 2026-11-17

- Deluge `MobileUi` core plugin on port 8113 with token auth.
- Read/write API, paginated torrent list, detail and SSE event stream.
- Vue 3 + Vite mobile SPA: virtualized list, filters, detail, add flow.
- PWA manifest/service worker, dark/light theme and HU/EN UI.
