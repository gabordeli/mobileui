# Döntések

## D1 – Core plugin a daemonban, külön porton (2026-11-17)

A UI-t `deluge_mobileui` **core plugin**ként futtatjuk a `deluged` Twisted
reactorjában, saját `Site`-tal a **8113**-on. A 8112-t a standalone `deluge-web`
foglalja; azt nem bántjuk. Így nincs külön service/auth/daemon, és közvetlen
in-process hozzáférés van a torrent managerhez és az EventManagerhez.

Korlát: a handlerek a daemon reactorjában futnak, ezért nem blokkolhatnak
sokáig; a 841 torrentes listát szerveroldalon kell szűrni/szeletelni (#3 spike).

## D2 – Csomagolás: egg + entry point

A Deluge 2.2 `pkg_resources.Environment`-nel szkenneli a
`deluge/plugins/` könyvtárat (és a config `plugins/` alkönyvtárát), ezért a
plugin egg formában készül, entry pointtal:

```
[deluge.plugin.core]
MobileUi = deluge_mobileui:CorePlugin
```

A `setup.py` csak a `bdist_egg` miatt marad; a metaadat a `pyproject.toml`-ban
él. A verzió egy helyen: `deluge_mobileui/version.py`. A telepítés a zip egg-et
**kicsomagolt `.egg/` könyvtárba** teszi: így a `data/` valódi fájlokból
szolgálható ki (zipből a `Path(__file__).parent` nem látja a resource-okat).

A célhost venvje **Twisted 22.4.0**-t használ, ezért a requirement
`Twisted>=22.4`; a plugin csak a 22.4-ben is meglévő Twisted API-kat használja.

## D3 – Config: `mobileui.conf`

`ConfigManager("mobileui.conf", {...})` a Deluge config könyvtárában. Kulcsok:
`enabled`, `port`, `token`, `auth_mode`, `sentry_dsn`. A `/api/*` hitelesítést
kér; a `/health` és a login végpontok (`/api/auth`, `/api/login`) publikusak.

## D4 – SPA helye

A `webui/` Vite build outputja a `deluge_mobileui/data/` alá kerül, és a plugin
resource-a szolgálja ki. A build artifact a csomag része, így a telepítés egy
egg marad.

## D5 – Token: üres = zárt, élő csere (2026-11-17)

A `/api/*` minden kérésnél a config `token` értékét ellenőrzi
(`hmac.compare_digest`), a `/health` kivétel. Üres token esetén **minden**
`/api/*` 401, nem pedig nyitott API – így egy elfelejtett token nem lesz
csendben nyilvános. A config fájlt a plugin `enable()`-kor létrehozza és
`chmod 600`-ra állítja; a token nem kerül logba.

A `mobileui.set_config({"token"|"port"|"enabled": ...})` élőben hat: a token a
következő kérésnél, a port újrabindolással, az `enabled` a listener
indításával/leállításával. Ha az új port foglalt, a plugin visszaállítja a régi
portot és hibát ad. Restart csak új egg telepítése után kell (a kód indításkor
töltődik).


## D6 – Read API: cache-elt státusz, szerveroldali szeletelés (2026-11-17)

A `/api/torrents` nem a `core.get_torrents_status`-ot hívja, mert az
`post_torrent_updates()`-ot válthat ki és libtorrent alertre várhat (a korábbi
mérés szerint terhelés alatt >25 s is lehetett). Helyette a plugin in-process
végigiterál a `torrentmanager.torrents`-en, `torrent.get_status(keys,
update=False)`-kal olvassa a már cache-elt státuszt, szerveroldalon szűr
(`state`, `label`, `q`), rendez és szeletel; csak a kért oldal megy a hálózatra.
A detail egy torrentnél `update=True`-val frissít, és ott van a fájllista.

Mérés (833 torrent, tesztpéldány): 50 soros lista p95 8,6 ms idle, 14,2 ms RPC-terhelés
alatt; a cél <300 ms. Részletek: `docs/perf.md`. Ha a torrentszám >5 000 lesz,
érdemes lehet 1 s-os snapshot-indexet bevezetni; most nem indokolt.

## D7 – Write API: core metódusok, Label plugin, explicit remove_data (2026-11-17)

Az írási végpontok a daemon core metódusait hívják (`pause_torrent`,
`resume_torrent`, `remove_torrent`, `queue_*`), így a GTK/web UI és a plugin
ugyanazt az állapotot látja. A labelváltás a Label plugin `set_torrent`-jén megy
át, hogy a meglévő label-opciók (move_completed, limitek, queue) érvényesüljenek;
az `auto_add`/label flow-t nem módosítjuk.

Az add magnet (`add_torrent_magnet`) vagy `.torrent` (`add_torrent_file`,
base64) útvonalon megy, `download_location` és `add_paused` opcióval. A labelt
az add előtt validáljuk, majd a létrejött torrentre alkalmazzuk. A
`remove_data` csak explicit `true` esetén töröl adatot (alap `false`).

Hibakódok: 400 invalid input, 404 ismeretlen torrent, 409 duplikált torrent /
tiltott állapot / Label plugin nélkül. A tesztpéldányon egy eldobható torrenten a teljes
ciklus (add → pause/resume → queue → label clear/set → remove) lefutott, a
meglévő 833 torrent és a label-countok változatlanok maradtak.

## D8 – SSE: EventManager + 1/s diff, nem kliens-polling (2026-11-17)

A `/api/events` egyetlen daemon-oldali broadcastert használ: az EventManager
`TorrentStateChangedEvent`, `TorrentAddedEvent`, `TorrentRemovedEvent` és
`SessionPausedEvent`/`SessionResumedEvent` eseményeire iratkozik fel, a
progress/rate/session mezőket pedig 1/s-mal diffeli. A Deluge 2.2-ben nincs
`TorrentProgressEvent`, ezért a progress nem eseményből jön; a diff a cache-elt
`torrent.get_status(update=False)`-ot használja (mint a read API).

A tick 1/s, a heartbeat 15 s; a delták egy tickben, külön SSE eventekként mennek
ki. A broadcaster a feliratkozókat `request.notifyFinish()`-nal takarítja, plugin
disablekor `bye` + finish. Az `EventSource` miatt a token query paraméterben is
elfogadott (`?token=`), a header az elsődleges. Nincs esemény-replay: reconnect
után a kliens a read API-ból szinkronizál, majd az új deltákat kapja.

## D9 – SPA: lapozott API + virtualizált scroll (2026-11-17)

A `webui/` Vite buildje a `deluge_mobileui/data/` alá kerül; a plugin a
`/`-on statikusan szolgálja, a `/api/*` és `/health` marad. A zip egg helyett
kicsomagolt `.egg/` könyvtár kell, különben a `data/` nem érhető el
fájlrendszerként (D2).

A lista **nem** tölti le a 833 torrentet egyszerre: 50-es lapokat kér
`offset`-tel, a `RecycleScroller` csak a látható sorokat rendereli, és a
scroller végén tölti a következő lapot. A keresés 300 ms debounce, a
state/label/sort szerveroldali. A token localStorage-ban van; az SSE
`?token=` queryt használ. A hosszú nyomás 500 ms után sheetet nyit
(pause/resume, queue, label, remove), a műveletek a write API-ra mennek.

Ellenőrzés a tesztpéldányon: 833 torrent, 50→100 betöltés scrollra, 360/390 px-en
nincs vízszintes scroll, long-press sheet + label mentés toast, SSE
számláló 834→833, nulla console error.

## D10 – Detail: külön lapozott files API (2026-11-17)

A `GET /api/torrents/{id}` válasza kicsi marad: a fájllista külön
`GET /api/torrents/{id}/files?offset=&limit=` végponton jön, 100-as lapokkal
(max 500), `{index, path, size, offset, progress}` mezőkkel. A detail UI ezt
„További fájlok” gombbal lapozza (522 fájlos torrenten 100→200 ellenőrizve),
így egy nagy torrent detailje nem hozza át egyszerre a teljes listát.

Az add sheet magnetet vagy `.torrent` fájlt küld a write API-nak, labellel,
abszolút `download_location`-nel és opcionális `add_paused`-dal; a default
útvonal a session `download_location`. A tesztpéldányon UI-ból hozzáadott teszt torrent
`Paused`/`filmek`/`/tmp/mobileui-add-test` állapotban jött létre, majd eltávolítva
a 833-as darabszám visszaállt. Tap → detail, long-press → gyors műveletek.

## D11 – PWA, téma, i18n (2026-11-17)

A SPA PWA manifestet (`/manifest.webmanifest`), 192/512/apple ikonokat és
`public/sw.js`-t kapott. A SW app-shell cache + network-first navigáció,
cache-first assetek, `/api/*` network-only. HTTP LAN-on a service worker nem
regisztrál (nem secure context), ezért a teljes offline shell/telepíthetőség a
#9 HTTPS deploy után lesz aktív; a manifest és ikonok már most 200-at adnak.

A téma `data-theme` attribútummal, localStorage-ban tárolva; kezdeti érték a
`prefers-color-scheme`, a fejléc gombja vált. Az i18n `src/i18n.ts`-ben él
(HU/EN, localStorage), a state-nevek is fordulnak; az API értékei változatlanok.
Skeleton, offline banner, error+retry, safe-area padding, `:focus-visible` és
Esc-close került be. A tesztpéldányon 360/390 px-en nincs vízszintes scroll (a keskeny
fejléc brandje rövidül), a HU↔EN és light↔dark váltás ellenőrizve, 0 console
error.

## D12 – Auth: Deluge user/jelszó + visszahívható session (2026-11-17)

A statikus API-token mellé opcionális **Deluge user/jelszó** belépés került
(`auth_mode`: `token` / `password` / `both`). A credential forrása a daemon
`auth` fájlja (`AuthManager.authorize`), nem külön mobileui user-lista: egy
jelszó mindenhol, és a Deluge szintek (1/5/10) ingyen adják a read-only /
normal / admin megkülönböztetést.

A belépés `secrets.token_urlsafe(32)` session tokent ad (30 nap TTL,
memóriában); a kliens ugyanúgy `Authorization: Bearer`-ként használja, ezért a
többi endpoint és az SSE változatlan. A statikus token mindig admin
(break-glass) és nem visszahívható; a session logouttal invalidálható. Írás
csak `level >= 5`, különben 403. A login generikus 401-et ad (nem árulja el,
létezik-e a user), IP-nként 5 hiba/perc után 429; az `X-Forwarded-For` csak a
limit kulcsa.

Korlát: a Deluge `auth` fájl plaintext jelszót tárol; a session a daemon
restartjakor elveszik; a `deluge-web` saját `web.conf` jelszava külön rendszer,
azt nem használjuk.

## D13 – Deluge 2.x kompatibilitás CI-ből (2026-11-17)

A `test` job a `tests/stubs/` shimekkel fut (gyors, Deluge nélkül), ezért a
valódi `deluge.*` API-változásokat külön **`deluge-compat`** job fogja meg:
Dockerben `deluge==2.0.3` (Python 3.9), `2.1.1` és `2.2.0` (Python 3.11) +
`libtorrent`, majd a teljes `tests/` suite. A 2.0.3 a régi Python-igénye miatt
3.9-en fut; a másik kettő 3.11-en. A mátrix a plugin által ténylegesen
használt szimbólumokra épül (`AuthManager.authorize`, `Core.pause_session` /
`resume_session` / `get_free_space`, `Torrent.get_status/files`,
`AUTH_LEVEL_*`).

Az authz mátrix (minden módosító endpoint read-only → 403, normal → 200/201) és
a `?token=` query naplózási szabálya (`$uri`, nem `$request`) ugyanezt a
biztonsági vonalat erősíti; a részletek a `docs/ci.md` és `docs/api.md`
dokumentumban.

## D14 – Bulk selection: long-press + alsó action bar (2026-11-17)

A long-press a D9/D11-ben leírt context sheet helyett **selection módot** indít
(az adott sorral); ilyenkor a tap váltogat, normál módban a tap továbbra is a
detailt nyitja. Az alsó, fix action bar darabszámot, „Összes” kijelölést és
pause/resume/label/remove műveleteket ad; a „Összes” a szűrőre illeszkedő
id-ket tölti be a `GET /api/torrents/ids`-ből (max 1000, a `total` külön
látszik). A `POST /api/torrents/bulk` id-nként dolgozik, a hibákat
összegyűjti (`ok`/`failed`), így egy rossz id nem állítja meg a többit.

A ContextSheet megszűnt (a detail már tudta ugyanazokat a műveleteket); a
single-torrent queue/label/remove a detailben maradt. A v1 nem tud undo-t,
kereszt-szűrős kivételt vagy bulk queue-t.

## D15 – Fájlprioritás: 0/1/4/7, „Csak ez”, kliensoldali kereső (2026-11-17)

A detail fájllistája a Deluge `set_file_priorities`-át használja, amely a
**teljes** listát várja; a handler a jelenlegi prioritásokat olvassa, és csak a
változásokat alkalmazza, így a lapozott lista miatt a kliensnek nem kell az
összes fájlt ismernie. A checkbox 0/4-et vált, a „Csak ez” az összeset 0-ra, a
kiválasztottat 4-re állítja. A kereső kliensoldali, csak a betöltött fájlokra
szűr (a lapozás miatt), és jelzi a betöltött/total arányt. Az 1/7
(alacsony/magas) prioritás az API-ban elérhető, a UI egyelőre 0/4-et használ.

## D16 – Sebességkorlát: globális vs. torrentenkénti (2026-11-17)

A globális limitek a Deluge `core.conf` `max_download_speed` / `max_upload_speed`
kulcsai (KiB/s, `-1` = korlátlan); a `Core.set_config` a PreferencesManager
callbackjein keresztül azonnal alkalmazza. A torrentenkénti érték a
`Torrent.set_max_download_speed` / `set_max_upload_speed` (KiB/s; `-1` = a
globális érték, `0` = korlátlan). A session sheet globális mezőket és
éjszakai (512/128) / korlátlan preseteket ad, a detail torrentenkénti
mezőket. A handler csak a megadott mezőket írja; a validáció `-1` vagy `>= 0`.

## D17 – PWA share target: /share az SW-n, magnet az add sheetben (2026-11-17)

A manifest `share_target` GET-tel a `/share` útvonalra mutat; a szerver nem
ismeri ezt az utat, ezért a service worker a navigációt az app shell-lel
szolgálja ki (a query megmarad). Az App a `text` / `url` / `title` paraméterből
regexszel keresi a `magnet:?` linket, és előtöltve megnyitja az add sheetet; a
címsorból a query-t `replaceState`-csel törli. Android Chrome + **telepített
PWA** kell; az iOS Safari nem támogatja a share targetet.
