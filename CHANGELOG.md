# Changelog

## [Unreleased]

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
