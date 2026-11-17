# API

Alap URL: `http://127.0.0.1:8113` (LAN). A `/health` publikus, minden más
`/api/*` végpont `Authorization: Bearer <token>`-t kér.

## Auth

```http
Authorization: Bearer <token>
```

- Hiányzó/rossz token → `401`, JSON törzs:
  `{"error": "unauthorized", "message": "Missing or invalid bearer token"}`,
  `WWW-Authenticate: Bearer realm="mobileui"`.
- Üres `token` a configban → minden `/api/*` 401.
- A token a `mobileui.conf`-ban él (600); élő csere: `mobileui.set_config`.

## GET /health

Publikus, auth nélkül is:

```json
{"ok": true, "version": "0.1.0", "port": 8113}
```

## GET /api

Tokenes index:

```json
{
  "version": "0.1.0",
  "endpoints": ["/api/session", "/api/labels", "/api/torrents", "/api/torrents/{id}"]
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
  "num_torrents": 833,
  "version": "2.2.0",
  "paused": false
}
```

A `version` a Deluge verziója; a plugin verziója a `/health`-ben és a `/api`
indexben van.

## GET /api/labels

```json
{
  "labels": [
    {"id": "filmek", "count": 93},
    {"id": "sorozatok", "count": 30}
  ],
  "no_label": 0
}
```

A count csak a létező torrenteket számolja. Ha a Label plugin nincs engedélyezve:
`{"labels": [], "no_label": <összes>}`.

## GET /api/torrents

Query paraméterek:

| Param | Alap | Leírás |
| --- | --- | --- |
| `state` | – | pontos állapot (`Paused`, `Downloading`, …) vagy `All` |
| `label` | – | label id, vagy `No Label` |
| `q` | – | kis-nagybetűtől független részstring a névben |
| `sort` | `name` | `name`, `state`, `progress`, `ratio`, `eta`, `total_size`, `download_payload_rate`, `upload_payload_rate`, `label`; `-` prefix = csökkenő |
| `offset` | `0` | >= 0 |
| `limit` | `50` | 1–200 |

Válasz:

```json
{
  "total": 833,
  "offset": 0,
  "limit": 50,
  "torrents": [
    {
      "id": "b1d2c99a24f841dc7a347ff6680d96c4907ca880",
      "name": "17.Again.2009...",
      "state": "Paused",
      "progress": 100.0,
      "label": "filmek",
      "download_payload_rate": 0,
      "upload_payload_rate": 0,
      "eta": 0,
      "ratio": 0.0,
      "total_size": 11073742312,
      "save_path": "/mnt/usbhdd2/Filmek"
    }
  ]
}
```

`total` a szűrés utáni teljes találatszám, a `torrents` csak a kért oldal.
A `progress` 0–100, a rate-ek byte/s-ban, az `eta` másodperc (`-1` = végtelen),
a `ratio` `-1` = végtelen.

## GET /api/torrents/{id}

Egy torrent részletes státusza. A `get_status` mezői mellett:

| Kulcs | Leírás |
| --- | --- |
| `id` | torrent hash |
| `label` | label id vagy `No Label` |
| `files` | `[{index, path, size, offset}]` |
| `file_progress` | fájlonkénti progress (0–1) |

Ismeretlen id → `404 {"error": "not_found", ...}`. A `files` csak itt van, a
listában nem.

## POST /api/torrents/{id}/pause

Pause egy torrentet. `200 {"id": "...", "state": "Paused"}`; ismeretlen id → 404;
`Error` állapotú torrent → 409.

## POST /api/torrents/{id}/resume

Resume egy torrentet. `200 {"id": "...", "state": "..."}`; ismeretlen id → 404.

## POST /api/torrents/{id}/remove

Body (opcionális):

```json
{"remove_data": false}
```

`200 {"id": "...", "removed": true, "remove_data": false}`. A `remove_data`
alapból `false`; ha a Deluge nem tudja eltávolítani → 409.

## POST /api/torrents/{id}/queue

```json
{"action": "up"}
```

`action`: `up`, `down`, `top`, `bottom`. `200 {"id": "...", "action": "up"}`;
ismeretlen action → 400, ismeretlen torrent → 404.

## PATCH /api/torrents/{id}

```json
{"label": "filmek"}
```

- `{"label": "No Label"}` vagy `{"label": null}` → label törlése.
- Ismeretlen label → 400; Label plugin nélkül → 409; ismeretlen torrent → 404.
- `200 {"id": "...", "label": "filmek"}`.

A label a Label plugin `set_torrent`-jén megy át, így a label opciói
(`move_completed`, sebességlimitek, queue) a meglévő logika szerint érvényesülnek.

## POST /api/torrents

Új torrent magnetből vagy `.torrent` fájlból.

JSON body:

```json
{
  "magnet": "magnet:?xt=urn:btih:...",
  "label": "filmek",
  "download_location": "/mnt/usbhdd2/Filmek",
  "add_paused": true
}
```

Vagy fájl base64-ként:

```json
{
  "filename": "x.torrent",
  "file_base64": "<base64>",
  "label": "filmek",
  "download_location": "/mnt/usbhdd2/Filmek"
}
```

Nyers feltöltés (nem JSON content-type), query paraméterekkel:

```bash
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/x-bittorrent" \
  --data-binary @x.torrent \
  "http://127.0.0.1:8113/api/torrents?filename=x.torrent&label=filmek&download_location=/mnt/usbhdd2/Filmek&add_paused=true"
```

- `download_location` abszolút út legyen; ha nincs megadva, a Deluge alapértéke.
- `add_paused` opcionális (alap `false`); `true` esetén nem indul el.
- `201 {"id": "...", "label": "...", "download_location": "..."}`.
- Duplikált torrent → 409; érvénytelen magnet/fájl/mező → 400.

## GET /api/events

SSE (`text/event-stream`) élő frissítés. A token vagy `Authorization: Bearer`
headerben, vagy `?token=<token>` query paraméterben adható (az `EventSource`
nem tud egyedi headert küldeni). A stream a kapcsolat bontásáig nyitva marad.

Első esemény:

```text
event: hello
data: {"version":"0.1.0","heartbeat":15,"num_torrents":833}
```

Utána torrent-delták (`event: torrent`) és session-delták (`event: session`):

```json
{"type": "state", "id": "<hash>", "fields": {"state": "Paused"}}
{"type": "progress", "id": "<hash>", "fields": {"progress": 42.5, "download_payload_rate": 1024, "upload_payload_rate": 0, "eta": 120}}
{"type": "added", "id": "<hash>", "fields": {}}
{"type": "removed", "id": "<hash>", "fields": {}}
{"type": "session", "id": null, "fields": {"download_rate": 1024.0, "paused": false}}
```

- A state/added/removed események a Deluge EventManagerből jönnek; a
  progress/rate/session mezőket a szerver 1/s-mal diffeli (a Deluge 2.2-ben nincs
  `TorrentProgressEvent`), így egy tickben legfeljebb egy csomag megy.
- 15 másodpercenként `: heartbeat` komment.
- A `fields` mindig csak a változott mezőket tartalmazza (a `hello` kivétel).
- Kliens disconnect → a szerver kiveszi a feliratkozót; `EventSource` esetén a
  böngésző automatikusan reconnectel (nincs esemény-replay).
- Plugin disable esetén `event: bye` majd a stream lezár.

## M1 végpontok

Az M1 összes végpontja implementálva: `/health`, `/api/session`, `/api/labels`,
`/api/torrents`, `/api/torrents/{id}` (GET/PATCH), a torrent-műveletek
(`pause`, `resume`, `remove`, `queue`), `POST /api/torrents` és `/api/events`.

## Hibák

JSON, legalább `{"error": "...", "message": "..."}`:

| Státusz | `error` | Mikor |
| --- | --- | --- |
| 400 | `bad_request` | hibás query/JSON/mező |
| 401 | `unauthorized` | hiányzó/rossz token |
| 404 | `not_found` | ismeretlen útvonal vagy torrent id |
| 409 | `conflict` | duplikált torrent, tiltott állapot, Label plugin nélkül |
| 500 | `internal_error` | váratlan hiba a daemonban |

Teljesítmény: [perf.md](perf.md).
