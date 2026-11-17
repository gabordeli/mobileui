# Web UI (M2)

Vue 3 + Vite + TypeScript SPA, a `webui/` alatt. A build a
`deluge_mobileui/data/` könyvtárba megy, és a plugin statikusan szolgálja ki a
`/` alatt (a `/api/*` és `/health` változatlan).

## Fejlesztés

```bash
cd webui
npm ci
npm run dev          # Vite dev server, /api proxy a 127.0.0.1:8113-ra
VITE_API_PROXY=http://192.168.2.27:8113 npm run dev
npm run build        # typecheck + build a deluge_mobileui/data/-ba
```

A `scripts/install.sh` akkor épít SPA-t a hoston, ha a `data/index.html`
hiányzik és van npm; egyébként a előre buildelt `data/`-t csomagolja.

## Auth

A token a `localStorage["mobileui.token"]`-ben van; a token-kapu bekéri, majd
minden kérés `Authorization: Bearer` headert kap. Az SSE `?token=` queryt használ
(`EventSource` nem tud headert). 401 esetén a UI visszadobja a kaput.

## Lista: lapozás + virtualizáció

- Az API 50 soros lapokat ad (`limit`), a UI `offset`-tel kér tovább; a teljes
  833-as lista egyszerre **nem** töltődik le.
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

## Ismert korlátok / következő

- Detail nézet és add dialógus: #7.
- PWA/manifest, HU/EN i18n, safe-area finomítás: #8.
- A token localStorage-ban van (nem httpOnly cookie); a plugin LAN-only.
- A lista végtelen scrollos, nincs „ugrás N. elemre"; a szűrők ezt kezelik.
