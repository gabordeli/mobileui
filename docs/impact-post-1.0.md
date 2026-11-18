# Post-1.0 impact study

Baseline: **v1.0.0** (2026-11-17), live on the Deluge host, 180 backend tests /
83%, 142 frontend tests, 9 E2E, Sonar 0 open issues. This study covers the seven
follow-up ideas opened as **#32–#38**. It was an assessment, not an implementation
plan; at the time of writing no item was started.

**Status (v1.2.0, 2026-11-18):** the seven items shipped in v1.1.0; the
follow-up six (added-date sort, force recheck, queue settings, torrent options,
URL add, directory picker) shipped in v1.2.0. The current suite is 218 backend /
169 frontend tests plus 12 E2E, with Sonar still at zero open issues; the
numbers below remain the v1.0.0 baseline of the study.

## Method

- Code inspection of the current `main` (`d696cfb`) and the v1.0.0 tag.
- Behaviour checked against the existing tests and the live/dev flows used for
  the v1.0.0 verification.
- Effort is relative: **S** = one focused change, **M** = one component plus
  tests/docs, **L** would need a redesign (none of these are L).
- “Assets” means new art/screenshots, not code.

## Summary

| # | Item | Benefit | Cost | Main risk | Assets | Order |
| --- | --- | --- | --- | --- | --- | --- |
| #32 | Release job pushes only the new tag | Prevents old tags reappearing after a release | S | Low; release-only change | None | 1 |
| #38 | Bulk remove data option + Moving guard | Safer destructive action; no conflicting moves | S | Accidental data deletion if UI is unclear | None | 2 |
| #33 | Localized push + test notification | Consistent HU/EN notifications; verifiable setup | S/M | SW update timing; test-target scope | None | 3 |
| #35 | Server-side file search | Finds files beyond the first page; less CPU per query | M | `total` semantics change when `q` is present | None | 4 |
| #34 | True modal dialogs / focus trap | Keyboard and screen-reader correctness | M | `showModal()` vs. Teleport/backdrop layout | None | 5 |
| #36 | Offline read cache | Last known list/session survives a reload | M | Stale/authenticated data in the cache | None | 6 |
| #37 | Push subscription management + endpoint validation | Per-device revoke; smaller SSRF surface | M | Privacy of device metadata; DNS rebinding | None | 7 |

## Details

### #32 – Release job tag push

**Problem.** The release job uses `git push ... --tags`. The runner clone can
retain old local tags, so a release re-pushes tags that were intentionally
deleted. This happened during the v1.0.0 cleanup: v0.1.1–v0.2.0 came back and
had to be removed again.

**Change.** Push only `refs/tags/v${VERSION}` (plus `HEAD:main`). Optionally
prune local tags before tagging.

**Impact.** Release pipeline only; no runtime change. Verification is a release
dry-run plus `git ls-remote --tags` before/after. The fix also protects the
GitHub mirror from resurrecting old tags. Low risk, highest operational value.

### #38 – Bulk remove data + Moving guard

**Problem.** `App.vue:runBulk` always sends `remove_data: false` for bulk
remove, so deleting data requires one-by-one removal. While a torrent is
`Moving`, the detail still offers pause/remove/move, which can conflict with
the storage move.

**Change.** Add an explicit “Delete downloaded data” checkbox to the bulk
confirmation (default off), pass `remove_data` through `runBulk`, and disable
the conflicting detail actions while `state === "Moving"`.

**Impact.** The default stays non-destructive; the risk is a user ticking the
box by mistake, so the confirmation must name the count and “delete data”.
Tests need to assert the payload and the disabled state. Small, high UX value.

### #33 – Localized push + test notification

**Problem.** `core.py` sends Hungarian titles (“Torrent kész”, “Torrent hiba”)
regardless of the UI language. There is no end-to-end way to verify a
subscription.

**Change.** Send a stable `{kind, name, url, tag}` payload; let `sw.js` render
HU/EN using `navigator.language`. Add `POST /api/push/test` and a session-sheet
button that targets the current device.

**Impact.** No delivery-path change. Risks: the old service worker may show old
text until it activates; the test endpoint must not fan out to every device
unless asked. Browser-language detection is best-effort; a per-subscription
locale is the fallback if it proves unreliable.

### #35 – Server-side file search

**Problem.** `read.get_files` builds all file/progress/priority rows and slices
them; the detail search filters only the pages already loaded. A 500+ file
torrent cannot be searched reliably.

**Change.** Add `q` to `GET /api/torrents/{id}/files`, filter before slicing,
return the filtered `total`. The UI switches to debounced server search (or uses
it above a threshold).

**Impact.** Additive API, but `total` changes meaning when `q` is present;
document it. Unfiltered pagination still walks the list, which is acceptable at
the current sizes. Bigger win for large torrents; no storage/schema change.

### #34 – Modal dialogs / focus trap

**Problem.** The sheets use `<dialog open>`, which is non-modal: Tab can reach
the background and focus is not trapped. Sonar is clean, but this is a real
keyboard/screen-reader gap.

**Change.** Call `showModal()` on mount, or add a focus trap if `showModal()`
conflicts with the Teleport/backdrop layout. Return focus to the trigger on
close.

**Impact.** Keyboard behaviour and stacking/backdrop, not the visual design.
`showModal()` may behave differently in happy-dom and mobile Safari; test both.
Medium effort; important after the Sonar/a11y pass.

### #36 – Offline read cache

**Problem.** The SW is network-only for `/api/*`; an offline reload loses the
list/session even though the shell loads.

**Change.** Cache successful `GET /api/torrents*` and `GET /api/session`;
serve on network failure with a stale marker. Never cache login/auth/SSE and do
not queue writes.

**Impact.** Better offline UX, but stale states must be labelled. Cache keys must
exclude the token query; 401/500 must not be cached. Logout should clear the
cache. Medium effort and a clear privacy note (shared device).

### #37 – Push subscription management + endpoint validation

**Problem.** The store only keeps `{endpoint, keys, added}`; the UI shows a
count. Separately, any `https://` endpoint is accepted, so an authenticated
read-only user can make the daemon POST to arbitrary HTTPS hosts (SSRF surface).

**Change.** Store optional UA/created/last-seen/label; add list/revoke
endpoints; show devices in the session sheet. Resolve and reject
loopback/private/link-local push hosts, and re-check at send time (or pin the
resolved address) to limit DNS rebinding.

**Impact.** Additive store schema; old entries remain valid. Device metadata is
privacy-sensitive. SSRF blocking must not reject real public push services.
This is the largest item; if it grows, split “device management” and “SSRF
validation” into separate issues.

## Recommended order

1. **#32** – one line, prevents release mistakes.
2. **#38** – small, destructive-action safety.
3. **#33** – user-facing consistency and a test path.
4. **#35** – large-torrent usability.
5. **#34** – accessibility hardening.
6. **#36** – offline resilience.
7. **#37** – security/device management; consider splitting.

## Not included

- HttpOnly-cookie auth + CSRF (large security redesign; localStorage is
  documented and LAN-scoped today).
- Offline write queue (needs conflict/ordering semantics).
- Full-text index for thousands of torrents (current 833-torrent p95 is well
  below the 300 ms target; revisit above ~5,000).
- File-list virtualization (server-side search is the cheaper first step).

## Verification baseline for any item

- Backend `pytest` + `ruff`, frontend `vue-tsc` + Vitest, E2E 12/12.
- Sonar gate stays blocking with 0 new violations.
- Any mutation endpoint gets the read-only (403) / normal (200/201) authz test.
- Deploy remains manual; release tags only after `git ls-remote --tags` check.
