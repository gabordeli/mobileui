# CI / release

`.gitlab-ci.yml` shell executorral fut, a projekt saját GitLab runner hostján.

## Stage-ek

| Stage | Job | Mit csinál |
| --- | --- | --- |
| lint | `lint` | `ruff check`, SPA `vue-tsc` |
| test | `test` | `pytest` + `pytest-cov`; Deluge nélkül a `tests/stubs/` shimek; artifact: `coverage.xml` |
| test | `webui-test` | Vitest + `@vitest/coverage-v8`; artifact: `webui/coverage/lcov.info` |
| test | `webui-e2e` | Playwright smoke a hivatalos Playwright Docker image-ben |
| test | `deluge-compat` | a backend suite valódi Deluge API ellen: 2.0.3 / 2.1.1 / 2.2.0 (Docker) |
| quality | `sonar` | SonarQube main-branch elemzés a Docker scannerrel; report-only |
| build | `build` | `npm run build`, `python -m build`, `package.sh`; artifact: `dist/` (sdist/wheel/egg/sha256), `data/` |
| release | `release` | manuális; `RELEASE_TYPE=patch|minor|major`; verzióbump + CHANGELOG + tag + egg feltöltés + GitLab Release |
| deploy | `deploy` | manuális; rsync a deploy hostra (`DEPLOY_HOST`) + `scripts/install.sh` |

## SonarQube

- A projekt: **Webui2**, a kulcs a `sonar-project.properties`-ben.
- CI-változók: **`SONAR_TOKEN`** és **`SONAR_HOST_URL`** (masked/protected).
- A scanner a **`sonarsource/sonar-scanner-cli:latest`** Docker image (Java 21);
  a runneren lévő régi 5.0.1-es scanner JRE 17-tel a 26.11-es szerveren
  `Java 17 is not supported` hibával elhasal.
- A `sonar` job csak a **main** ágon fut (Community Edition; PR-dekoráció nincs),
  és **blokkoló**: `sonar.qualitygate.wait=true`, 300 s timeout. Piros gate
  esetén a `sonar` job elhasal, így a `build`/`release`/`deploy` stage el sem
  indul. A deploy továbbra is manuális (a zöld gate csak a feltétel).
- A gate a Sonar „Sonar way” küszöbeit használja az új kódra: coverage ≥ 80%,
  duplikáció ≤ 3%, új violation = 0. A 0 violation szigorú, ezért a main-re
  kerülő kódnak fixálnia kell az új smell-eket (a meglévő adósság nem
  blokkolja a gate-et, mert az új kód periódusára szűr).
- Coverage: a backend `pytest-cov` → `coverage.xml`; a frontend Vitest +
  `@vitest/coverage-v8` → `webui/coverage/lcov.info` (a `webui-test` artifactja).
  A Cobertura `<source>`-ot a CI `deluge_mobileui`-ra normalizálja, mert a
  scanner konténerben a project base `/usr/src` (a host abszolút path nem
  oldható fel).

## Coverage

- A `test` job `--cov-fail-under=80`-cal fut; a mostani backend fedettség 83%
  (165 teszt).
- A `webui-test` Vitest threshold-jei: statements 75, branches 65, functions 75,
  lines 78; a mostani 83.03 / 74.34 / 81.98 / 86.25 (140 teszt, `.vue`-kkal).
- A GitLab a `coverage:` regexszel a joblogból olvassa a számot, és a pipeline /
  MR nézetben jeleníti meg — privát, nincs külső badge.
- A Sonar gate blokkoló a main-en (lásd fent); a `build` csak zöld gate után
  fut. A deploy továbbra is manuális, tehát egy piros gate nem deployol, de
  egy zöld gate sem deployol magától.
- A `types.ts` type-only, 0% coverage-e normális; nem kell tesztelni.

## Deluge kompatibilitás

A `deluge-compat` job a backend suite-ot **valódi Deluge** ellen futtatja, nem a
stubok ellen, három 2.x verzión:

| Deluge | Python image |
| --- | --- |
| 2.0.3 | `python:3.9-slim` |
| 2.1.1 | `python:3.11-slim` |
| 2.2.0 | `python:3.11-slim` |

A konténerben `pip install deluge==<ver> libtorrent pytest twisted`, majd
`pytest -q tests`. Így a plugin által használt `deluge.*` szimbólumok és
szignatúrák változása (pl. `AuthManager.authorize`, `Core.pause_session`,
`deluge.common.AUTH_LEVEL_*`) azonnal kiderül. A helyi `test` job továbbra is a
stubokkal fut (gyors, Deluge nélkül); a kettő együtt adja a lefedettséget.

## E2E

A `webui-e2e` job a `webui/e2e/smoke.spec.ts`-t futtatja: token-kapu, fiók
login, read-only UI, lista + detail, fájlprioritás, session sheet, bulk
selection, megosztott magnet, add sheet. Az API-t `page.route` mockolja, ezért
Deluge nélkül fut. A job a hivatalos
`mcr.microsoft.com/playwright:v1.65.1-jammy` image-ben fut
(Docker), így a runneren nem kell Chromium rendszerlib. Az image tagjét a
`@playwright/test` verziójához kell igazítani (most 1.65.1); a helyi futtatáshoz
`npx playwright install chromium` kell. A konténer `HOME=/tmp`-vel fut, mert a
runner UID-nak nincs írható home könyvtára (az npm cache emiatt hasalna el).

## Release

```bash
./scripts/release.sh patch --dry-run   # csak kiírja az új verziót
./scripts/release.sh minor             # version.py, package.json, lock, CHANGELOG
```

A CI release job a `RELEASE_TYPE` pipeline-változóval fut, majd
`chore(release) vX.Y.Z` commitot és `vX.Y.Z` taget készít, és pushol a
`main`-re. A pushhoz a `CI_REPOSITORY_URL` / job token kell, hogy engedve legyen.
A bump után a job újraépíti a SPA-t (`cd webui && npm ci && npm run build`),
mert a `build` artifact még a régi verziót tartalmazza; a `deluge_mobileui/data/`
bekerül a release commitba, így a friss clone is az aktuális SPA-t kapja. Ezután
az egg-et (`SKIP_WEBUI=1`) építi, feltölti a Generic Package Registrybe, és a
`vX.Y.Z` GitLab Release-hez asset linkként csatolja az egg-et és a `.sha256`-ot;
a release leírásában a hash is szerepel.

A release előtt a `CHANGELOG.md` `## [Unreleased]` szakaszába írd a
változásokat; a `scripts/release.py` ezt emeli át a `## [x.y.z]` szakaszba, és
üríti az Unreleased-t. Ha üres, `- Release x.y.z.` lesz. A GitHub release
ugyanezt a szakaszt használja.

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

## GitHub tükör

A `gabordeli/mobileui` **privát** GitHub repo egyirányú tükör: a fejlesztés a
GitLabon folyik, a GitLab push mirror tolja át a `main`-t és a tageket. GitHubon
ne commitolj, mert divergál.

Beállítás a GitLabon (*Settings → Repository → Mirroring repositories*):

- URL: `https://github.com/gabordeli/mobileui.git`
- Direction: **Push**
- Authentication: username `gabordeli`, password = fine-grained PAT
  (`Contents: Read and write`, `Metadata: Read`, **`Workflows: Read and write`**,
  csak erre a repóra). Workflows nélkül a GitHub a `.github/workflows/` fájl
  létrehozását `without workflow scope` hibával utasítja el, és a mirror teljes
  `main` pushja elhasal.
- „Only mirror protected branches” **kikapcsolva**: bekapcsolva csak a védett
  brancheket tükrözi (a védetlen `main` kimaradt), a tagek viszont ilyenkor is
  átmennek. Vagy kapcsold ki, vagy vedd fel a `main`-t védett branchnek.

Kezdeti feltöltés (a mirror bekapcsolása előtt vagy kézi fallbackként):

```bash
GITHUB_TOKEN=... git push \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/gabordeli/mobileui.git" main
```

Ellenőrzés:

```bash
GITHUB_TOKEN=... ./scripts/github_mirror_check.sh
```

A PAT lejárta a mirrort **csendben megállítja**; a script `MIRROR BEHIND` vagy
`MISSING TAG` jelzéssel áll meg. Rotáció: új PAT a GitHubon, csere a GitLab
mirror beállításban, majd ellenőrzés. Kézi fallback:
`git push --mirror https://...`.

A GitHub Release a `.github/workflows/release.yml` workflow-val megy: minden
`v*` tagre (Node 22 + Python 3.11) buildeli a SPA-t, a wheel/sdist/egg-et, és a
`GITHUB_TOKEN`-nel létrehozza a release-t a CHANGELOG megfelelő szakaszával. A
workflow a tag commitjában lévő verziókat ellenőrzi (`version.py`,
`package.json`), és idempotens (újrafuttatva feltölti az asseteket). A régi
tagekhez nem készül release; a workflow csak az új tagtól él.

## Deploy

A `deploy` job a build artifact `data/`-ját rsynceli a `$DEPLOY_HOST:/root/webui2`-be,
majd futtatja a `scripts/install.sh`-t (a hoston épít, változatlanul). A
`DEPLOY_HOST` **kötelező** projekt CI/CD változó (pl. `root@deluge-host`); enélkül
a job elhasal. Kézi telepítéshez a release eggje is használható:
`EGG=/path/MobileUi-*.egg ./scripts/install.sh`. A runneren:
- `rsync`,
- a `gitlab-runner` user `~/.ssh/id_ed25519` kulcsa a deploy host root
  `authorized_keys`ében (a jelenlegi setup így megy; `DEPLOY_SSH_KEY` CI-változó
  opcionális felülírásként működik),
- host key: `StrictHostKeyChecking=accept-new`.

A release job pusholásához a projektben be van kapcsolva a
**CI job token push** (`ci_push_repository_for_job_token_allowed=true`), így a
`CI_JOB_TOKEN` a `main`-re tudja tenni a release commitot/taget.

## Runner toolchain

A `gitlab_runner_toolchain` playbook a shell runnerre telepíti: python3-pip/venv,
nodejs/npm, git, jq, curl, **rsync**, docker/trivy, mariadb-client. A CI saját
venvben teszi fel a `pytest`, `pytest-cov`, `ruff`, `build`, `twisted`,
`sentry-sdk`, `setuptools`, `wheel` csomagokat; a tesztek a `tests/stubs` Deluge
shimekkel futnak. A SonarQube elemzés a Docker image-et használja (nem a runner régi
`sonar-scanner` binaryjét). A deployhoz a `gitlab-runner` user SSH-kulcsa a
deploy host root `authorized_keys`ében van.

Ellenőrzés: `deploy_gitlab_runner_toolchain.yml --limit gitlab-runner
--check --diff` → **changed=0**; a runner restart megtörtént, a CI továbbra is
zöld.

## Igazolt futás

- Pipeline: lint/test/build success; a `v0.1.1` release commit/tag elkészült.
- Deploy job: success; a deploy hoston `/health` **0.1.1**, több száz torrent,
  SPA/8112 200.
- A régi egg-verziók takarítása (`find ... -type d -name 'MobileUi-*.egg'`)
  szükséges, különben a régi plugin marad betöltve.
- GitHub mirror: a `main` és a `v0.1.3` átment; a GitHub Actions `Release` run
  16 lépése success, a `v0.1.3` release 4 assetten (wheel, sdist, egg, sha256).
  A `v0.1.1`/`v0.1.2` tagek fent vannak, de release nélkül (backfill nélkül).

## Ismert korlát

A runneren nincs Deluge; a tesztek ezért a `tests/stubs/deluge` shimeket
használják. A valós Deluge-verziót a deploy hoston a `/health` és az integrációs
tesztek fedik.
