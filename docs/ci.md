# CI / release

`.gitlab-ci.yml` runs with the shell executor, on the project's own GitLab runner host.

## Stages

| Stage | Job | What it does |
| --- | --- | --- |
| lint | `lint` | `ruff check`, SPA `vue-tsc` |
| test | `test` | `pytest` + `pytest-cov`; without Deluge the `tests/stubs/` shims; artifact: `coverage.xml` |
| test | `webui-test` | Vitest + `@vitest/coverage-v8`; artifact: `webui/coverage/lcov.info` |
| test | `webui-e2e` | Playwright smoke in the official Playwright Docker image |
| test | `deluge-compat` | the backend suite against the real Deluge API: 2.0.3 / 2.1.1 / 2.2.0 (Docker) |
| quality | `sonar` | SonarQube main-branch analysis with the Docker scanner; blocking quality gate |
| build | `build` | `npm run build`, `python -m build`, `package.sh`; artifact: `dist/` (sdist/wheel/egg/sha256), `data/` |
| release | `release` | manual; `RELEASE_TYPE=patch|minor|major`; version bump + CHANGELOG + tag + egg upload + GitLab Release |
| deploy | `deploy` | manual; rsync to the deploy host (`DEPLOY_HOST`) + `scripts/install.sh` |

## SonarQube

- The project: **Webui2**, the key is in `sonar-project.properties`.
- CI variables: **`SONAR_TOKEN`** and **`SONAR_HOST_URL`** (masked/protected).
- The scanner is the **`sonarsource/sonar-scanner-cli:latest`** Docker image (Java 21);
  the old 5.0.1 scanner on the runner with JRE 17 fails on the 26.11 server
  with a `Java 17 is not supported` error.
- The `sonar` job only runs on the **main** branch (Community Edition; no PR
  decoration), and is **blocking**: `sonar.qualitygate.wait=true`, 300 s timeout.
  On a red gate the `sonar` job fails, so the `build`/`release`/`deploy` stage
  does not even start. Deploy is still manual (the green gate is only the
  condition).
- The gate uses Sonar "Sonar way" thresholds for new code: coverage ≥ 80%,
  duplication ≤ 3%, new violations = 0. The 0 violations is strict, so code
  landing on main must fix the new smells (existing debt does not block the
  gate, because it filters on the new code period).
- Coverage: the backend `pytest-cov` → `coverage.xml`; the frontend Vitest +
  `@vitest/coverage-v8` → `webui/coverage/lcov.info` (the artifact of
  `webui-test`). The CI normalizes the Cobertura `<source>` to `deluge_mobileui`,
  because in the scanner container the project base is `/usr/src` (the host
  absolute path cannot be resolved).

## Coverage

- The `test` job runs with `--cov-fail-under=80`; the current backend coverage
  is 83% (180 tests).
- The `webui-test` Vitest thresholds: statements 75, branches 65, functions 75,
  lines 78; the current 82.56 / 74.47 / 81.20 / 85.86 (142 tests, with `.vue`
  files).
- GitLab reads the number from the job log with the `coverage:` regex, and
  displays it in the pipeline / MR view — private, no external badge.
- The Sonar gate is blocking on main (see above); `build` only runs after a
  green gate. Deploy is still manual, so a red gate does not deploy, but a
  green gate does not deploy by itself either.
- `types.ts` is type-only, its 0% coverage is normal; it does not need testing.

## Deluge compatibility

The `deluge-compat` job runs the backend suite against **real Deluge**, not the
stubs, on three 2.x versions:

| Deluge | Python image |
| --- | --- |
| 2.0.3 | `python:3.9-slim` |
| 2.1.1 | `python:3.11-slim` |
| 2.2.0 | `python:3.11-slim` |

In the container `pip install deluge==<ver> libtorrent pytest twisted`, then
`pytest -q tests`. This way a change in the `deluge.*` symbols and signatures
used by the plugin (e.g. `AuthManager.authorize`, `Core.pause_session`,
`deluge.common.AUTH_LEVEL_*`) shows up immediately. The local `test` job still
runs with the stubs (fast, without Deluge); the two together give the coverage.

## E2E

The `webui-e2e` job runs `webui/e2e/smoke.spec.ts`: token gate, account
login, read-only UI, list + detail, file priority, session sheet, bulk
selection, shared magnet, add sheet. The API is mocked with `page.route`, so it
runs without Deluge. The job runs in the official
`mcr.microsoft.com/playwright:v1.65.1-jammy` image
(Docker), so no system Chromium libs are needed on the runner. The image tag
must be matched to the `@playwright/test` version (now 1.65.1); for local
running `npx playwright install chromium` is needed. The container runs with
`HOME=/tmp`, because the runner UID has no writable home directory (the npm
cache would fail because of this).

## Release

```bash
./scripts/release.sh patch --dry-run   # only prints the new version
./scripts/release.sh minor             # version.py, package.json, lock, CHANGELOG
```

The CI release job runs with the `RELEASE_TYPE` pipeline variable, then creates
a `chore(release) vX.Y.Z` commit and a `vX.Y.Z` tag, and pushes to
`main`. For the push, the `CI_REPOSITORY_URL` / job token must be allowed.
After the bump the job rebuilds the SPA (`cd webui && npm ci && npm run build`),
because the `build` artifact still contains the old version; `deluge_mobileui/data/`
goes into the release commit, so a fresh clone also gets the current SPA. Then
it builds the egg (`SKIP_WEBUI=1`), uploads it to the Generic Package Registry, and
attaches the egg and the `.sha256` to the `vX.Y.Z` GitLab Release as asset links;
the release description also includes the hash.

Before the release, write the changes into the `## [Unreleased]` section of
`CHANGELOG.md`; `scripts/release.py` moves this into the `## [x.y.z]` section,
and empties the Unreleased. If it is empty, it becomes `- Release x.y.z.`. The
GitHub release uses the same section.

## Release artifact

```bash
./scripts/package.sh                 # SPA + egg + sha256
SKIP_WEBUI=1 ./scripts/package.sh    # with the already built data/
PYTHON=.ci-venv/bin/python ./scripts/package.sh
```

The script writes `MobileUi-<version>-py3.x.egg` and
`MobileUi-<version>-py3.x.egg.sha256` into `dist/`, then checks that the egg
contains `PKG-INFO`, the entry point and `deluge_mobileui/data/index.html`.

The CI uploads the two files under `.../packages/generic/mobileui/<version>/`,
and the release asset links point here too. The downloaded egg:
`EGG=/path/MobileUi-*.egg ./scripts/install.sh` (on the host, as root), or
unpacked by hand under `deluge.plugins`.

The runner's Python is 3.13, the target is 3.11; the Deluge
`pkg_resources.Environment(..., python=None)` call does not filter on the
Python tag, so the py3.13-tagged, pure-Python egg also loads on the 3.11 target
(the stock plugins are also py3.10/py3.12 eggs on 3.11). Unpacking is still
mandatory, because `static.File` cannot serve from a zip.

The upload and the release go with `CI_JOB_TOKEN`; if the job token's
API access is restricted in the project, the release job stops with 401/403.

## GitHub mirror

The `gabordeli/mobileui` **public** GitHub repo is a one-way mirror: development
happens on GitLab, the GitLab push mirror pushes `main` and the tags over. On
GitHub do not commit, because it would diverge.

Setup on GitLab (*Settings → Repository → Mirroring repositories*):

- URL: `https://github.com/gabordeli/mobileui.git`
- Direction: **Push**
- Authentication: username `gabordeli`, password = fine-grained PAT
  (`Contents: Read and write`, `Metadata: Read`, **`Workflows: Read and write`**,
  only for this repo). Without Workflows, GitHub rejects the creation of the
  `.github/workflows/` files with a `without workflow scope` error, and the
  mirror's whole `main` push fails.
- "Only mirror protected branches" **off**: when on, it only mirrors protected
  branches (the unprotected `main` was left out), but the tags go through in
  that case too. Either turn it off, or add `main` as a protected branch.

Initial upload (before enabling the mirror or as a manual fallback):

```bash
GITHUB_TOKEN=... git push \
  "https://x-access-token:${GITHUB_TOKEN}@github.com/gabordeli/mobileui.git" main
```

Check:

```bash
GITHUB_TOKEN=... ./scripts/github_mirror_check.sh
```

The expiry of the PAT **silently stops** the mirror; the script stops with a
`MIRROR BEHIND` or `MISSING TAG` indication. Rotation: a new PAT on GitHub,
replace it in the GitLab mirror settings, then check. Manual fallback:
`git push --mirror https://...`.

The GitHub Release goes with the `.github/workflows/release.yml` workflow: on every
`v*` tag (Node 22 + Python 3.11) it builds the SPA, the wheel/sdist/egg, and with
`GITHUB_TOKEN` creates the release with the corresponding section of the CHANGELOG. The
workflow checks the versions in the tag commit (`version.py`,
`package.json`), and is idempotent (re-running uploads the assets). No release
is made for old tags; the workflow only lives from the new tag.

## Deploy

The `deploy` job rsyncs the build artifact's `data/` into `$DEPLOY_HOST:/root/webui2`,
then runs `scripts/install.sh` (it builds on the host, unchanged). `DEPLOY_HOST` is a
**mandatory** project CI/CD variable (e.g. `root@deluge-host`); without it
the job fails. For manual installation the release egg can also be used:
`EGG=/path/MobileUi-*.egg ./scripts/install.sh`. On the runner:
- `rsync`,
- the `gitlab-runner` user's `~/.ssh/id_ed25519` key in the deploy host root's
  `authorized_keys` (the current setup works this way; the `DEPLOY_SSH_KEY` CI
  variable works as an optional override),
- host key: `StrictHostKeyChecking=accept-new`.

For the release job's push, **CI job token push** is enabled in the project
(`ci_push_repository_for_job_token_allowed=true`), so the `CI_JOB_TOKEN` can put
the release commit/tag onto `main`.

## Runner toolchain

The `gitlab_runner_toolchain` playbook installs onto the shell runner: python3-pip/venv,
nodejs/npm, git, jq, curl, **rsync**, docker/trivy, mariadb-client. The CI
installs `pytest`, `pytest-cov`, `ruff`, `build`, `twisted`,
`sentry-sdk`, `setuptools`, `wheel` into its own venv; the tests run with the
`tests/stubs` Deluge shims. SonarQube analysis uses the Docker image (not the runner's old
`sonar-scanner` binary). For deploy, the `gitlab-runner` user's SSH key is in the
deploy host root's `authorized_keys`.

Check: `deploy_gitlab_runner_toolchain.yml --limit gitlab-runner --check --diff`
→ **changed=0**; the runner restart has happened, the CI is still green.

## Verified run

- Pipeline 6699: `lint`, `test`, `webui-test`, `webui-e2e`, `deluge-compat`,
  `sonar` and `build` success; the release job created `chore(release) v1.0.0`
  and the `v1.0.0` tag; the deploy job succeeded.
- On the deploy host `/health` is **1.0.0**, the SPA is served with the release
  assets; the stock `deluge-web` on 8112 is untouched.
- GitLab and GitHub both expose **v1.0.0 as the first public release**; the
  GitHub release has four assets (wheel, sdist, egg, sha256), and the GitLab
  release links the egg + sha256. The earlier tags/releases were removed from
  both remotes.
- Cleaning up old unpacked egg versions (`find ... -type d -name
  'MobileUi-*.egg'`) remains necessary, otherwise the old plugin stays loaded.
- The GitHub Release workflow (run `44154691183`) completed successfully on the
  `v1.0.0` tag.

## Known limitation

There is no Deluge on the runner; therefore the tests use the `tests/stubs/deluge`
shims. The real Deluge version is covered by `/health` and the integration
tests on the deploy host.
