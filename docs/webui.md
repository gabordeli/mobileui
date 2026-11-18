# Web UI (M2)

Vue 3 + Vite + TypeScript SPA, under `webui/`. The build goes into the
`deluge_mobileui/data/` directory, and the plugin serves it statically under
`/` (`/api/*` and `/health` are unchanged).

## Development

```bash
cd webui
npm ci
npm run dev          # Vite dev server, /api proxy to 127.0.0.1:8113 (local deluged)
# with deluged running on another machine:
VITE_API_PROXY=http://<deluge-host>:8113 npm run dev
npm run build        # typecheck + build into deluge_mobileui/data/
```

`scripts/install.sh` builds the SPA on the host when `data/index.html` is
missing and npm is available; otherwise it packages the pre-built `data/`.

## Sentry DSN

The frontend Sentry DSN is a build-time env variable: `VITE_SENTRY_DSN`. In the
repo `webui/.env.production` provides the default (Bugsink) DSN; `main.ts` only
reads `import.meta.env.VITE_SENTRY_DSN`, there is no hardcode. With another DSN:

```bash
cd webui
VITE_SENTRY_DSN=https://<key>@<host>/<project> npm run build
```

Vite gives precedence to a `VITE_SENTRY_DSN` in the process environment over
`.env.production`. The DSN is a public client key (not a secret); backend
sending is controlled by the `sentry_dsn` field of `mobileui.conf` and can be
set live. With an empty DSN the frontend does not initialize Sentry.

## Tests

- `npm run test` / `npm run test:coverage` — Vitest (App, components, theme,
  api, format, i18n, main, push); 149 tests, the coverage threshold is in
  `vite.config.ts`.
- `npm run test:e2e` — Playwright smoke: token gate, account login, read-only UI,
  list+detail, file priority, session sheet, bulk selection, shared magnet,
  add sheet. The API is mocked with `page.route`, so it runs without Deluge;
  `npx playwright install chromium` is needed before the first run.
- The CI `webui-e2e` job runs the same; it downloads the browser into the
  `webui/.playwright/` cache.

## Auth

`GET /api/auth` reports which login methods exist (`token`, `password`, or
both); the gate shows one or two tabs accordingly. After a successful login the
received token is in `localStorage["mobileui.token"]`, and every request gets
an `Authorization: Bearer` header. SSE uses a `?token=` query (`EventSource`
cannot send a header). On 401 the UI throws back the gate; on 429 the error text
indicates the wait. At read-only level (`level < 5`) the `+` button, the
sheet/detail actions and removal are hidden; the person icon in the header
shows the logged-in identity and logout.

## Version

The token gate and the footer of the main view show the `version` field of
`/health`. The frontend does not embed the `package.json` version, so after a
release bump the new plugin/daemon is enough; the UI updates from the backend
response. If health is unreachable the label is omitted and the UI does not
break.

## List: pagination + virtualization

- The API returns 50-row pages (`limit`), the UI requests further pages with
  `offset`; the full list of several hundred torrents is **not** loaded at once.
- `RecycleScroller` (vue-virtual-scroller) renders only the visible rows
  (about 10 DOM elements with 50 loaded), and loads the next page when the end
  is reached.
- Search is debounced by 300 ms; state/label/sort filtering is server-side, and
  the scroller restarts when `listKey` changes.
- An **Error** badge appears on the row if the `state` is `Error` or the
  `message` is not `OK`; the badge tooltip shows the Deluge message. The
  `Error` state is also available in the filter.
- Long-pressing a row (500 ms, 10 px movement tolerance, vibration if available)
  starts **selection mode** (that row is selected); taps then toggle, while in
  normal mode a tap opens the detail.
- While a selection is active a fixed **bottom action bar** appears: the count,
  “All” (the ids matching the filter from `/api/torrents/ids`, max 1000), plus
  pause/resume/label/remove via `/api/torrents/bulk`. Failing ids do not stop
  the rest; the toast shows an `ok`/`failed` summary. The previous context
  sheet is gone; single-torrent actions remain in the detail.

## SSE

`EventSource("/api/events?token=...")`; `torrent` deltas update the loaded
rows, the `session` delta updates the header counts/rates. The `added`/`removed`
events also correct the total even without a filter; reconnects are handled by
the browser.

## Detail and adding

- Tapping a row opens a full-screen detail (`TorrentDetail.vue`): progress,
  speeds, peers/seeds, ETA, ratio, size, save path, label, actions.
- The file list comes from a separate, paginated API
  (`/api/torrents/{id}/files`, 100-row pages, max 500); the detail only returns
  `num_files`. For a torrent with 522 files, “More files” loads 100→200.
- The file list has a per-file **download checkbox** and **“Only this”**
  (`PATCH /api/torrents/{id}/files`); a skipped file gets a `Skipped` marker.
  The search is server-side (`?q=`), filters before pagination, and shows the
  loaded/total match count.
- The detail also allows a per-torrent **speed limit** (KiB/s; `-1` = the global
  value, `0` = unlimited) via `PATCH /api/torrents/{id}/limits`.
- The add sheet (`AddDialog.vue`) accepts a magnet or a `.torrent` file, a label,
  an absolute save path and a “start paused” option. The default path comes from
  the session `download_location` field; the last path/label is remembered in
  localStorage (`mobileui.add.path/label`), and the “Default” button clears the
  saved path. On an invalid magnet/file/field the backend's 400/409 message is
  shown.
- The detail provides **magnet** and **infohash** copy buttons (clipboard API,
  textarea fallback on HTTP); copying shows a toast.
- The detail receives progress/rate/state updates from SSE; after actions the
  response + SSE keep the list and the detail in sync.
- The statistics are compact: 3 primary chips (↓, ↑, ETA) and a thin meta row
  (ratio, peers, seeds, size, added); the tracker is in a collapsible bar
  (host + state + count), the full URL list opens on click. The **Reannounce**
  button calls `POST /api/torrents/{id}/reannounce`.
- The **Move** button opens next to the save path: absolute destination path,
  confirmation, then `POST /api/torrents/{id}/move`; the torrent enters the
  `Moving` state and the files are actually moved (enough free space is
  required).

## Labels

The 🏷 **Labels** button in the filter bar opens a sheet: existing labels with
counts, deletion with confirmation, and adding a new label (`a-z0-9_-`). The
torrents of a deleted label move under `No Label`; the list refreshes after the
action. For a read-only account only the list is visible.

## PWA, theme, i18n

- The service worker caches the app shell, serves navigation network-first,
  assets cache-first, and `/api/*` network-only. Successful `GET /api/torrents*`,
  `/api/session` and `/api/labels` responses are also kept in a separate API
  cache; on a network failure they are served with `X-MobileUi-Stale: 1`, and
  the UI shows a “cached data” banner. Logout clears the API cache.
- Dark/light theme: `data-theme` on `<html>`, stored in localStorage;
  `prefers-color-scheme` provides the initial value, the ☀/☾ button in the
  header switches.
- HU/EN i18n: `src/i18n.ts`, localStorage `mobileui.locale`; the EN/HU button
  in the header switches, state names are translated too. The API values
  (state, label) stay unchanged.
- Offline banner (`navigator.onLine`), skeleton while loading, empty/error
  state with a retry button; safe-area padding on the header/filter/row/sheet/
  detail elements; `:focus-visible` and Esc to close the sheet/detail.
- The sheets/details use `<dialog open>` plus a focus trap (`src/focus.ts`):
  `#app` becomes `inert` while open, Tab/Shift+Tab cycle inside the dialog,
  and focus returns to the trigger on close.

## Session sheet

The stats bar in the header (↓/↑/count) is a button: it opens the session
sheet. It shows the free space of `download_location`, the torrent count, the
down/up rate and the session state; the button pauses or resumes **all**
torrents (`POST /api/session/pause|resume`). The sheet allows setting a
**global speed limit** (KiB/s, -1 or 0 = unlimited), with **Night mode**
(512/128) and **Unlimited** presets, and a **sparkline** shows the down/up
speed of the last 60 s from the SSE session deltas. For a read-only account only
the note is visible. Based on the `paused` field of the response the button
label switches immediately; the list is updated by the SSE delta.

## Notifications (Web Push)

It can be enabled at the bottom of the session sheet, even for a read-only
account (subscribing is not a Deluge modification). Requirements: HTTPS (secure
context), `Notification` permission and `PushManager`. The browser subscribes
with the VAPID public key from `GET /api/push/config`, and
`POST /api/push/subscribe` stores the `PushSubscription.toJSON()`. On disabling,
after the browser's `unsubscribe()` the `DELETE /api/push/subscribe` removes the
server-side endpoint. The service worker's `push` event draws a system
notification, and the click navigates to the `/?torrent=<id>` deep link
(focusing the existing window), which the App opens in the detail sheet. The
setting lives separately per browser and per device; the server stores at most
20 subscriptions. The sheet lists the known devices (host/User-Agent) with a
per-device **Revoke** action (`GET/DELETE /api/push/subscriptions`), so one
browser can be removed without touching the others. Push endpoints are checked
against loopback/private ranges at registration and again at delivery.
If notifications are blocked, the toggle shows an explanation; on an HTTP LAN
host the “HTTPS required” text appears. When enabled, **Test** sends one
notification to the current device via `POST /api/push/test`. The server sends
a language-neutral `kind`/`name`/`message` payload and the service worker
renders HU/EN text from `navigator.language`.

## Sharing (Android)

The manifest's `share_target` points to the `/share` path; the server does not
know it, so the **service worker** serves the `/share` navigation with the app
shell (the query is preserved). The App extracts the `magnet:?` link from the
`text` / `url` / `title` parameter and opens the add sheet pre-filled; it clears
the query from the address bar with `replaceState`. It works only **from an
installed PWA, on Android** (Chrome); iOS Safari does not support share targets.

## Known limits / next

- The service worker/offline shell is active only over HTTPS (or localhost);
  after the #9 deploy PWA installability is complete.
- The token/session token is in localStorage (not an httpOnly cookie); the
  plugin is LAN-only, TLS is behind the proxy.
- The list is infinite-scroll, there is no “jump to item N”; the filters handle
  this.
- The detail's file list pages with a “More files” button, it is not
  virtualized.
