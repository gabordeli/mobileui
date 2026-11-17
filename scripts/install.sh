#!/usr/bin/env bash
# Install / upgrade the MobileUi plugin on the Deluge host (run as root there).
#
#   ./scripts/install.sh
#   EGG=/path/MobileUi-*.egg ./scripts/install.sh
set -euo pipefail

DELUGE_VENV="${DELUGE_VENV:-/opt/deluge-2.2.0}"
DELUGE_CONFIG_DIR="${DELUGE_CONFIG_DIR:-/var/lib/deluged/config}"
DELUGE_USER="${DELUGE_USER:-debian-deluged}"
SERVICE="${SERVICE:-deluged}"
PORT="${PORT:-8113}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$DELUGE_VENV/bin/python"

if [[ "$(id -u)" -ne 0 ]]; then
    echo "Run as root (installs into $DELUGE_VENV and restarts $SERVICE)." >&2
    exit 1
fi

PLUGIN_DIR="$("$PY" -c 'import os, deluge.plugins; print(os.path.dirname(deluge.plugins.__file__))')"

cd "$ROOT"

TMP_DIR=""
cleanup() {
    if [[ -n "$TMP_DIR" ]]; then
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

if [[ -n "${EGG:-}" ]]; then
    EGG="$(realpath "$EGG")"
    if [[ ! -f "$EGG" ]]; then
        echo "EGG not found: $EGG" >&2
        exit 1
    fi
    TMP_DIR="$(mktemp -d)"
    cp "$EGG" "$TMP_DIR/"
    EGG="$TMP_DIR/$(basename "$EGG")"
else
    if [[ ! -f "$ROOT/deluge_mobileui/data/index.html" && -f "$ROOT/webui/package.json" ]]; then
        if command -v npm >/dev/null 2>&1; then
            (cd "$ROOT/webui" && npm ci --silent && npm run build --silent)
        else
            echo "warning: SPA is not built and npm is missing; / will return 404" >&2
        fi
    fi

    rm -rf "$ROOT/build"
    rm -f dist/MobileUi-*.egg
    "$PY" setup.py -q bdist_egg
    EGG="$(ls -t dist/MobileUi-*.egg | head -n1)"
fi

"$PY" - "$EGG" <<'PY'
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
PY

EGG_NAME="$(basename "$EGG")"
EGG_DIR="$PLUGIN_DIR/$EGG_NAME"
EGG_VERSION="$("$PY" - "$EGG" <<'PY'
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as archive:
    for line in archive.read("EGG-INFO/PKG-INFO").decode().splitlines():
        if line.startswith("Version: "):
            print(line.split(": ", 1)[1])
            break
PY
)"
echo "Installing MobileUi ${EGG_VERSION:-unknown} from $EGG_NAME"

find "$PLUGIN_DIR" -maxdepth 1 -type d -name 'MobileUi-*.egg' -exec rm -rf {} +
find "$PLUGIN_DIR" -maxdepth 1 -type f -name 'MobileUi-*.egg' -delete
mkdir -p "$EGG_DIR"
"$PY" -m zipfile -e "$EGG" "$EGG_DIR"

systemctl restart "$SERVICE"
for _ in $(seq 1 15); do
    ss -ltn "sport = :58846" | grep -q LISTEN && break
    sleep 1
done

runuser -u "$DELUGE_USER" -- "$DELUGE_VENV/bin/deluge-console" \
    -c "$DELUGE_CONFIG_DIR" "plugin -e MobileUi"

for _ in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:$PORT/health"; then
        echo
        echo "API token: $DELUGE_CONFIG_DIR/mobileui.conf (empty token => /api returns 401)"
        exit 0
    fi
    sleep 1
done

echo "Health check failed; see: journalctl -u $SERVICE -n 50" >&2
exit 1
