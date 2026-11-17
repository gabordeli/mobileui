# Web UI (M2)

Vue 3 + Vite + TypeScript SPA, a `webui/` alatt. A build a
`deluge_mobileui/data/` könyvtárba megy, és a plugin statikusan szolgálja ki a
`/` alatt (a `/api/*` és `/health` változatlan).

## Fejlesztés

```bash
cd webui
npm ci
npm run dev          # Vite dev server, /api proxy a 127.0.0.1:8113-ra (helyi deluged)
# más gépen futó delugednél:
VITE_API_PROXY=http://<deluge-host>:8113 npm run dev
npm run build        # typecheck + build a deluge_mobileui/data/-ba
```

A `scripts/install.sh` akkor épít SPA-t a hoston, ha a `data/index.html`
hiányzik és van npm; egyébként a előre buildelt `data/`-t csomagolja.

## Tesztek

- `npm run test` / `npm run test:coverage` — Vitest (App, komponensek, theme,
  api, format, i18n, main); 86 teszt, a coverage threshold a `vite.config.ts`-ben.
- `npm run test:e2e` — Playwright smoke: token-kapu, fiók login, read-only UI,
  lista+detail, add sheet. Az API-t `page.route` mockolja, ezért Deluge nélkül
  fut; az első futás előtt `npx playwright install chromium` kell.
- A CI `webui-e2e` job ugyanezt futtatja; a böngészőt a `webui/.playwright/`
  cache alá tölti.

## Auth

A `GET /api/auth` mondja meg, milyen belépési módok vannak (`token`,
`password` vagy mindkettő); a kapu ennek megfelelően egy vagy két fület mutat.
Sikeres belépés után a kapott token a `localStorage["mobileui.token"]`-ben van,
és minden kérés `Authorization: Bearer` headert kap. Az SSE `?token=` queryt
használ (`EventSource` nem tud headert). 401 esetén a UI visszadobja a kaput,
429-nél a hibaszöveg jelzi a várakozást. Read-only szintnél (`level < 5`) a `+`
gomb, a sheet/detail műveletei és az eltávolítás rejtve vannak; a fejléc ⚙
panelén a belépett identity és a kijelentkezés látszik.

## Verzió

A token-kapu és a fő nézet footerje a `/health` `version` mezőjét mutatja. A
frontend nem ágyazza be a `package.json` verzióját, ezért release bump után
elég az új plugin/daemon; a UI a backend válaszából frissül. Ha a health nem
érhető el, a felirat elmarad, a UI nem törik el.

## Lista: lapozás + virtualizáció

- Az API 50 soros lapokat ad (`limit`), a UI `offset`-tel kér tovább; a teljes
  több száz torrentes lista egyszerre **nem** töltődik le.
- `RecycleScroller` (vue-virtual-scroller) csak a látható sorokat rendereli
  (kb. 10 DOM elem 50 betöltött mellett), a végére érve tölti a következő lapot.
- A keresés 300 ms debounce; a state/label/sort szerveroldali szűrés, a
  `listKey` változásakor a scroller újraindul.
- A sor hosszú nyomása (500 ms, 10 px mozgástolerancia, vibráció ha van)
  context sheetet nyit: pause/resume, queue, label, remove (opcionális adat).

## SSE

`EventSource("/api/events?token=...")`; a `torrent` delták a betöltött sorokat
frissítik, a `session` delta a header számait/rate-jeit. Az `added`/`removed`
események szűrő nélkül a totalt is korrigálják; reconnectet a böngésző intéz.

## Detail és hozzáadás

- A sorra koppintva teljes képernyős detail nyílik (`TorrentDetail.vue`):
  progress, sebességek, peers/seeds, ETA, ratio, méret, mentési útvonal,
  label, műveletek. A hosszú nyomás továbbra is a gyors context sheetet nyitja.
- A fájllista külön, lapozott API-ból jön (`/api/torrents/{id}/files`,
  100-as lapok, max 500); a detail csak a `num_files`-t hozza. 522 fájlos
  torrentnél a „További fájlok” 100→200-at tölt.
- Az add sheet (`AddDialog.vue`) magnetet vagy `.torrent` fájlt fogad, labelt,
  abszolút mentési útvonalat és „szünetelve induljon” opciót. A default útvonal
  a session `download_location` mezőjéből jön. Hibás magnet/fájl/mező esetén a
  backend 400/409 üzenete jelenik meg.
- A detail SSE-ből kapja a progress/rate/state frissítést; a listát és a detailt
  a műveletek után a válasz + SSE szinkronban tartja.

## PWA, téma, i18n

- `manifest.webmanifest` + 192/512/apple ikonok + `public/sw.js`; a SW az app
  shellt cache-eli, a navigációt network-first, az asseteket cache-first kezeli,
  az `/api/*` network-only. Regisztráció csak secure contextben (HTTPS vagy
  localhost) indul; HTTP LAN-on a manifest/ikonok már jók, a SW HTTPS deploy
  után lép életbe.
- Sötét/light téma: `data-theme` a `<html>`-en, localStorage-ban tárolva;
  a `prefers-color-scheme` adja a kezdeti értéket, a fejléc ☀/☾ gombja vált.
- HU/EN i18n: `src/i18n.ts`, localStorage `mobileui.locale`; a fejléc EN/HU
  gombja vált, a state-nevek is fordulnak. Az API értékei (state, label)
  változatlanok.
- Offline banner (`navigator.onLine`), skeleton töltés közben, empty/error
  állapot retry gombbal; safe-area padding a header/filter/row/sheet/detail
  elemeken; `:focus-visible` és Esc a sheet/detail bezárásához.

## Ismert korlátok / következő

- A service worker/offline shell csak HTTPS-en (vagy localhoston) aktív; a #9
  deploy után teljes a PWA telepíthetőség.
- A token/session token a localStorage-ban van (nem httpOnly cookie); a plugin
  LAN-only, TLS a proxy mögött.
- A lista végtelen scrollos, nincs „ugrás N. elemre"; a szűrők ezt kezelik.
- A detail fájllistája „További fájlok” gombbal lapoz, nem virtualizált.
