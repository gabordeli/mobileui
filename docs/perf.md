# Performance – read API (M1 #3)

Mérés: 2026-11-17, `cirice` (192.168.2.27), Deluge 2.2.0, Twisted 22.4.0,
**833 torrent**, a plugin a daemonban. A kliens a hoston `127.0.0.1:8113`
(localhost), 30 minta (detail: 15); a terhelés egy háttér-RPC ciklus volt
(folyamatos `core.get_torrents_status({}, 10 keys)`, 313 hívás / 8 s).

## Eredmények

| Végpont | n | min | medián | p95 | max |
| --- | ---: | ---: | ---: | ---: | ---: |
| `GET /api/torrents?limit=50` (idle) | 30 | 6,2 ms | 6,5 ms | **8,6 ms** | 16,7 ms |
| `GET /api/torrents?limit=50` (load) | 50 | 6,3 ms | 8,5 ms | **14,2 ms** | 14,8 ms |
| `GET /api/torrents?limit=50&label=filmek` | 30 | 5,7 ms | 5,8 ms | 6,5 ms | 8,0 ms |
| `GET /api/torrents?limit=50&state=Paused` | 30 | 6,2 ms | 6,4 ms | 6,5 ms | 6,9 ms |
| `GET /api/torrents?limit=50&q=dune` | 30 | 5,6 ms | 5,8 ms | 6,3 ms | 6,5 ms |
| `GET /api/torrents?limit=200` | 30 | 6,6 ms | 6,7 ms | 7,0 ms | 8,4 ms |
| `GET /api/torrents/{id}` (detail) | 15 | 0,7 ms | 0,9 ms | 1,2 ms | 1,2 ms |
| `GET /api/session` | 30 | 0,9 ms | 1,1 ms | 1,3 ms | 1,6 ms |
| `GET /health` (load) | 20 | 0,5 ms | 0,7 ms | 10,6 ms | 11,6 ms |

Az 50 soros válasz ~14,7 KB JSON. Az elfogadási cél (50 sor p95 < 300 ms)
teljesül; a daemon a mérés alatt végig válaszolt.

## Kiinduló mérés: `get_torrents_status`

RPC-n, közvetlenül a daemonon (ugyanaz a 833 torrent, idle):

| Kérés | Eredmény |
| --- | ---: |
| 4 kulcs, összes | 8–16 ms |
| 10 kulcs, összes | 13 ms |
| 10 kulcs, `state=Seeding` | 1 ms (0 sor) |
| 10 kulcs, `label=delete` | 1 ms (0 sor) |

A korábbi ismert mérés szerint a **teljes 841-es lista terhelés alatt >25 s**
is lehetett. A `core.get_torrents_status` ui. `session.post_torrent_updates()`-ot
válthat ki és a libtorrent alertre vár; a várakozás terhelés alatt megnyúlik.
Ezért a kérésútvonal **nem** ezt használja.

## Választott stratégia

A plugin in-process olvassa a torrent objektumokat:

1. `torrent.get_status(LIST_KEYS, update=False)` – a daemon által már
   frissített, cache-elt libtorrent státusz; nincs alert-várakozás.
2. Szerveroldali szűrés (`state`, `label`, `q`), rendezés, majd szeletelés
   (`offset`/`limit`, max 200) – a hálózatra csak a kért oldal megy.
3. A label a Label plugin `torrent_labels` mapjéből jön (nincs külön státusz).
4. Detail (`/api/torrents/{id}`) csak egy torrentnél frissít (`update=True`),
   és ott van a fájllista + fájlonkénti progress.

Miért nem külön index: 833 torrentnél a teljes bejárás ~6–14 ms, egy
event-alapú index karbantartása (progress/rate frissítések) több mozgó alkatrész
lenne. Ha a torrentszám nagyságrenddel nő (pl. >5 000), érdemes lehet
1 s-os snapshot-indexet vezetni; a mostani mérés ezt még nem indokolja.

## Ismert korlátok

- Ha egy torrent cache-elt státusza 5 s-nél régebbi, a `torrent.status`
  property torrentenként libtorrent `handle.status()`-t hívhat; normál
  daemon-működés mellett ez ritka, de szélsőséges terhelésnél nőhet.
- A `Moving` állapotú torrentek progressze fájlrendszer-statisztikát végez.
- A detail `files`/`file_progress` nagy torrentnél (sok fájl) nagy válasz.
- A label-count a teljes torrentszótárt bejárja; ez ~1 ms 833 elemnél.
