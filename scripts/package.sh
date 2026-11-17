#!/usr/bin/env bash
# Build a portable MobileUi .egg (SPA included) into dist/.
#
#   ./scripts/package.sh                 # build SPA + egg
#   SKIP_WEBUI=1 ./scripts/package.sh    # use the existing deluge_mobileui/data/
#   PYTHON=.ci-venv/bin/python ./scripts/package.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
DIST="${DIST:-$ROOT/dist}"
SKIP_WEBUI="${SKIP_WEBUI:-0}"

cd "$ROOT"

if [[ "$SKIP_WEBUI" != "1" ]]; then
    if [[ ! -f "$ROOT/webui/package.json" ]]; then
        echo "webui/package.json not found" >&2
        exit 1
    fi
    if ! command -v npm >/dev/null 2>&1; then
        echo "npm is required to build the SPA (set SKIP_WEBUI=1 to reuse data/)" >&2
        exit 1
    fi
    (cd "$ROOT/webui" && npm ci --silent && npm run build --silent)
fi

if [[ ! -f "$ROOT/deluge_mobileui/data/index.html" ]]; then
    echo "deluge_mobileui/data/index.html missing; build the SPA first" >&2
    exit 1
fi

mkdir -p "$DIST"
rm -rf "$ROOT/build"
rm -f "$DIST"/MobileUi-*.egg "$DIST"/MobileUi-*.egg.sha256
"$PYTHON" setup.py -q bdist_egg --dist-dir "$DIST"

EGG="$(ls -t "$DIST"/MobileUi-*.egg | head -n1)"

"$PYTHON" - "$EGG" <<'PY'
import sys
import zipfile

egg = sys.argv[1]
with zipfile.ZipFile(egg) as archive:
    names = set(archive.namelist())
    required = [
        "EGG-INFO/PKG-INFO",
        "EGG-INFO/entry_points.txt",
        "deluge_mobileui/data/index.html",
    ]
    missing = [name for name in required if name not in names]
    if missing:
        raise SystemExit(f"{egg}: missing {missing}")
    data_files = [name for name in names if name.startswith("deluge_mobileui/data/")]
    print(f"egg: {egg}", file=sys.stderr)
    print(f"files: {len(names)}, SPA data files: {len(data_files)}", file=sys.stderr)
PY

(
    cd "$(dirname "$EGG")"
    sha256sum "$(basename "$EGG")"
) > "$EGG.sha256"

echo "$EGG"
