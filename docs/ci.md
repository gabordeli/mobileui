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
majd futtatja a `scripts/install.sh`-t. A runneren:
- `rsync`,
- a `gitlab-runner` user `~/.ssh/id_ed25519` kulcsa a `.27` root
  `authorized_keys`ében (a jelenlegi setup így megy; `DEPLOY_SSH_KEY` CI-változó
  opcionális felülírásként működik),
- host key: `StrictHostKeyChecking=accept-new`.

A release job pusholásához a projektben be van kapcsolva a
**CI job token push** (`ci_push_repository_for_job_token_allowed=true`), így a
`CI_JOB_TOKEN` a `main`-re tudja tenni a release commitot/taget.

## Igazolt futás

- Pipeline: lint/test/build success; a `v0.1.1` release commit/tag elkészült.
- Deploy job: success; a .27-en `/health` **0.1.1**, 833 torrent, SPA/8112 200.
- A régi egg-verziók takarítása (`find ... -type d -name 'MobileUi-*.egg'`)
  szükséges, különben a régi plugin marad betöltve.

## Ismert korlát

A runneren nincs Deluge; a tesztek ezért a `tests/stubs/deluge` shimeket
használják. A valós Deluge-verziót a `.27`-en a `/health` és az integrációs
tesztek fedik.
