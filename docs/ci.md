# CI / release

`.gitlab-ci.yml` shell executorral fut, a `gitlab-runner` hoston (`.26`).

## Stage-ek

| Stage | Job | Mit csinál |
| --- | --- | --- |
| lint | `lint` | `ruff check`, SPA `vue-tsc` |
| test | `test` | `pytest`; Deluge nélkül a `tests/stubs/` shimek |
| build | `build` | `npm run build`, `python -m build`, `bdist_egg`; artifact: `dist/`, `data/` |
| release | `release` | manuális; `RELEASE_TYPE=patch|minor|major`; verzióbump + CHANGELOG + tag |
| deploy | `deploy` | manuális; rsync a `.27`-re + `scripts/install.sh` |

## Release

```bash
./scripts/release.sh patch --dry-run   # csak kiírja az új verziót
./scripts/release.sh minor             # version.py, package.json, lock, CHANGELOG
```

A CI release job a `RELEASE_TYPE` pipeline-változóval fut, majd
`chore(release) vX.Y.Z` commitot és `vX.Y.Z` taget készít, és pushol a
`main`-re. A pushhoz a `CI_REPOSITORY_URL` / job token kell, hogy engedve legyen.

## Deploy

A `deploy` job a build artifact `data/`-ját rsynceli a `.27:/root/webui2`-be,
majd futtatja a `scripts/install.sh`-t. Ehhez a runneren:
- `rsync`,
- `DEPLOY_SSH_KEY` CI-változó (a `.27` root authorized_keysében lévő kulcs),
- host key: `StrictHostKeyChecking=accept-new`.

A #11 toolchain feladata ezeket a runnerre tenni. Amíg nincs kulcs, a deploy
job manuálisan a fejlesztői gépről is futtatható (`scripts/install.sh`).

## Ismert korlát

A runneren nincs Deluge; a tesztek ezért a `tests/stubs/deluge` shimeket
használják. A valós Deluge-verziót a `.27`-en a `/health` és az integrációs
tesztek fedik.
