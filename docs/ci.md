# CI / release

`.gitlab-ci.yml` shell executorral fut, a `gitlab-runner` hoston (`.26`).

## Stage-ek

| Stage | Job | Mit csinál |
| --- | --- | --- |
| lint | `lint` | `ruff check`, SPA `vue-tsc` |
| test | `test` | `pytest`; Deluge nélkül a `tests/stubs/` shimek |
| build | `build` | `npm run build`, `python -m build`, `package.sh`; artifact: `dist/` (sdist/wheel/egg/sha256), `data/` |
| release | `release` | manuális; `RELEASE_TYPE=patch|minor|major`; verzióbump + CHANGELOG + tag + egg feltöltés + GitLab Release |
| deploy | `deploy` | manuális; rsync a `.27`-re + `scripts/install.sh` |

## Release

```bash
./scripts/release.sh patch --dry-run   # csak kiírja az új verziót
./scripts/release.sh minor             # version.py, package.json, lock, CHANGELOG
```

A CI release job a `RELEASE_TYPE` pipeline-változóval fut, majd
`chore(release) vX.Y.Z` commitot és `vX.Y.Z` taget készít, és pushol a
`main`-re. A pushhoz a `CI_REPOSITORY_URL` / job token kell, hogy engedve legyen.
A bump után a job újraépíti az egg-et (`SKIP_WEBUI=1`), feltölti a Generic
Package Registrybe, és a `vX.Y.Z` GitLab Release-hez asset linkként csatolja az
egg-et és a `.sha256`-ot; a release leírásában a hash is szerepel.

## Release artifact

```bash
./scripts/package.sh                 # SPA + egg + sha256
SKIP_WEBUI=1 ./scripts/package.sh    # a már buildelt data/-val
PYTHON=.ci-venv/bin/python ./scripts/package.sh
```

A script a `dist/`-be írja a `MobileUi-<verzió>-py3.x.egg` fájlt és a
`MobileUi-<verzió>-py3.x.egg.sha256`-ot, majd ellenőrzi, hogy az eggben benne
van a `PKG-INFO`, az entry point és a `deluge_mobileui/data/index.html`.

A CI a `.../packages/generic/mobileui/<verzió>/` alá tölti fel a két fájlt, és
a release asset linkjei is ide mutatnak. A letöltött egg:
`EGG=/path/MobileUi-*.egg ./scripts/install.sh` (a hoston, rootként), vagy
kézzel kicsomagolva a `deluge.plugins` alá.

A runner Pythonja 3.13, a cél 3.11; a Deluge
`pkg_resources.Environment(..., python=None)` hívása nem szűr Python-tagra, ezért
a py3.13 tagű, pure-Python egg a 3.11-es célon is betöltődik (a stock pluginek
is py3.10/py3.12 eggek a 3.11-en). A kicsomagolás viszont kötelező, mert a
`static.File` nem tud zipből szolgálni.

A feltöltés és a release a `CI_JOB_TOKEN`-nel megy; ha a projektben a job token
API-hozzáférése szűkített, a release job 401/403-mal megáll.

## Deploy

A `deploy` job a build artifact `data/`-ját rsynceli a `.27:/root/webui2`-be,
majd futtatja a `scripts/install.sh`-t (a hoston épít, változatlanul). Kézi
telepítéshez a release eggje is használható:
`EGG=/path/MobileUi-*.egg ./scripts/install.sh`. A runneren:
- `rsync`,
- a `gitlab-runner` user `~/.ssh/id_ed25519` kulcsa a `.27` root
  `authorized_keys`ében (a jelenlegi setup így megy; `DEPLOY_SSH_KEY` CI-változó
  opcionális felülírásként működik),
- host key: `StrictHostKeyChecking=accept-new`.

A release job pusholásához a projektben be van kapcsolva a
**CI job token push** (`ci_push_repository_for_job_token_allowed=true`), így a
`CI_JOB_TOKEN` a `main`-re tudja tenni a release commitot/taget.

## Runner toolchain

A `gitlab_runner_toolchain` playbook a shell runnerre telepíti: python3-pip/venv,
nodejs/npm, git, jq, curl, **rsync**, docker/trivy, mariadb-client. A CI saját
venvben teszi fel a `pytest`, `ruff`, `build`, `twisted`, `setuptools`, `wheel`
csomagokat; a tesztek a `tests/stubs` Deluge shimekkel futnak. A deployhoz a
`gitlab-runner` user SSH-kulcsa a .27 root `authorized_keys`ében van.

Ellenőrzés: `deploy_gitlab_runner_toolchain.yml --limit gitlab-runner
--check --diff` → **changed=0**; a runner restart megtörtént, a CI továbbra is
zöld.

## Igazolt futás

- Pipeline: lint/test/build success; a `v0.1.1` release commit/tag elkészült.
- Deploy job: success; a .27-en `/health` **0.1.1**, 833 torrent, SPA/8112 200.
- A régi egg-verziók takarítása (`find ... -type d -name 'MobileUi-*.egg'`)
  szükséges, különben a régi plugin marad betöltve.

## Ismert korlát

A runneren nincs Deluge; a tesztek ezért a `tests/stubs/deluge` shimeket
használják. A valós Deluge-verziót a `.27`-en a `/health` és az integrációs
tesztek fedik.
