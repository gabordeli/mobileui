# Performance – read API (M1 #3)

Measurement: 2026-11-17, test instance, Deluge 2.2.0, Twisted 22.4.0,
**833 torrents**, the plugin inside the daemon. The client was on the host at
`127.0.0.1:8113` (localhost), 30 samples (detail: 15); the load was a
background RPC loop (continuous `core.get_torrents_status({}, 10 keys)`,
313 calls / 8 s).

## Results

| Endpoint | n | min | median | p95 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| `GET /api/torrents?limit=50` (idle) | 30 | 6.2 ms | 6.5 ms | **8.6 ms** | 16.7 ms |
| `GET /api/torrents?limit=50` (load) | 50 | 6.3 ms | 8.5 ms | **14.2 ms** | 14.8 ms |
| `GET /api/torrents?limit=50&label=movies` | 30 | 5.7 ms | 5.8 ms | 6.5 ms | 8.0 ms |
| `GET /api/torrents?limit=50&state=Paused` | 30 | 6.2 ms | 6.4 ms | 6.5 ms | 6.9 ms |
| `GET /api/torrents?limit=50&q=dune` | 30 | 5.6 ms | 5.8 ms | 6.3 ms | 6.5 ms |
| `GET /api/torrents?limit=200` | 30 | 6.6 ms | 6.7 ms | 7.0 ms | 8.4 ms |
| `GET /api/torrents/{id}` (detail) | 15 | 0.7 ms | 0.9 ms | 1.2 ms | 1.2 ms |
| `GET /api/session` | 30 | 0.9 ms | 1.1 ms | 1.3 ms | 1.6 ms |
| `GET /health` (load) | 20 | 0.5 ms | 0.7 ms | 10.6 ms | 11.6 ms |

The 50-row response is ~14.7 KB of JSON. The acceptance target (50 rows
p95 < 300 ms) is met; the daemon responded throughout the measurement.

## Baseline measurement: `get_torrents_status`

Over RPC, directly on the daemon (the same 833 torrents, idle):

| Request | Result |
| --- | ---: |
| 4 keys, all | 8–16 ms |
| 10 keys, all | 13 ms |
| 10 keys, `state=Seeding` | 1 ms (0 rows) |
| 10 keys, `label=delete` | 1 ms (0 rows) |

According to the previously known measurement, the **full list of 841 could
take >25 s under load**. `core.get_torrents_status` (as used by the ui) can
trigger a `session.post_torrent_updates()` and waits for the libtorrent alert;
the wait stretches under load. That is why the request path does **not** use
it.

## Chosen strategy

The plugin reads the torrent objects in-process:

1. `torrent.get_status(LIST_KEYS, update=False)` – the cached libtorrent
   status already refreshed by the daemon; no alert wait.
2. Server-side filtering (`state`, `label`, `q`), sorting, then slicing
   (`offset`/`limit`, max 200) – only the requested page goes over the wire.
3. The label comes from the Label plugin's `torrent_labels` map (no separate
   status).
4. The detail (`/api/torrents/{id}`) refreshes for a single torrent only
   (`update=True`), and that is where the file list + per-file progress lives.

Why not a separate index: with 833 torrents a full walk is ~6–14 ms, while
maintaining an event-based index (progress/rate updates) would mean more moving
parts. If the torrent count grows by an order of magnitude (e.g. >5 000), a 1 s
snapshot index might be worth keeping; the current measurement does not yet
justify it.

## Known limits

- If a torrent's cached status is older than 5 s, the `torrent.status` property
  may call libtorrent `handle.status()` per torrent; under normal daemon
  operation this is rare, but it can grow under extreme load.
- The progress of torrents in the `Moving` state performs filesystem
  statistics.
- The detail's `files`/`file_progress` is a large response for a big torrent
  (many files).
- The label count walks the whole torrent dictionary; this is ~1 ms for
  833 entries.
