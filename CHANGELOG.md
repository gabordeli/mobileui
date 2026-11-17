# Changelog

## [Unreleased]

- Optional Deluge username/password login next to the static API token
  (`auth_mode`: `token` / `password` / `both`). Sessions are revocable, expire
  after 30 days and map Deluge auth levels, so a read-only (1) account can view
  but not modify torrents. The static token stays as the admin break-glass.
- `/api/auth`, `/api/login` and `/api/logout` endpoints; `403` for read-only
  writes and a per-IP login rate limit (`429`).
- Login gate with account/token tabs, sign-out in the account panel and a
  read-only UI that hides the write actions.

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
