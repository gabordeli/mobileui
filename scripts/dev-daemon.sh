#!/usr/bin/env bash
# Local development daemon: throws away config under .dev/, so the user's real
# Deluge setup is untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEV_DIR="${DEV_DIR:-$ROOT/.dev}"
CONFIG_DIR="$DEV_DIR/deluge"
PORT="${PORT:-8113}"
if [[ -z "${PY:-}" && -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
    # deluged runs on system python, which on this box has no setuptools metadata;
    # pkg_resources needs it, so expose the venv's setuptools to the daemon.
    VENV_SITE="$("$PY" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}$VENV_SITE"
else
    PY="${PY:-python3}"
fi

if ss -ltn "sport = :$PORT" | grep -q LISTEN; then
    echo "Port $PORT already in use; set PORT=... to pick another one." >&2
    exit 1
fi

mkdir -p "$CONFIG_DIR/plugins" "$DEV_DIR"

cd "$ROOT"
"$PY" setup.py -q bdist_egg
EGG="$(ls -t dist/MobileUi-*.egg | head -n1)"
EGG_DIR="$CONFIG_DIR/plugins/$(basename "$EGG")"
find "$CONFIG_DIR/plugins" -maxdepth 1 -type d -name 'MobileUi-*.egg' -exec rm -rf {} +
mkdir -p "$EGG_DIR"
"$PY" -m zipfile -e "$EGG" "$EGG_DIR"
find "$CONFIG_DIR/plugins" -maxdepth 1 -type f -name 'MobileUi-*.egg' -delete

if [[ ! -f "$CONFIG_DIR/core.conf" ]]; then
    echo "Creating a fresh Deluge config in $CONFIG_DIR ..."
    timeout 10 deluged -d -c "$CONFIG_DIR" -l "$DEV_DIR/daemon.log" -L info || true
fi

"$PY" - "$CONFIG_DIR/core.conf" <<'PY'
import sys

from deluge.config import Config

config = Config(sys.argv[1])
enabled = list(config["enabled_plugins"])
if "MobileUi" not in enabled:
    enabled.append("MobileUi")
    config["enabled_plugins"] = enabled
    config.save()
PY

TOKEN="${MOBILEUI_TOKEN:-dev-token}"
"$PY" - "$CONFIG_DIR/mobileui.conf" "$TOKEN" <<'PY'
import os
import sys

from deluge.config import Config

path, token = sys.argv[1], sys.argv[2]
config = Config(path, defaults={"enabled": True, "port": 8113, "token": ""})
config["token"] = token
config.save()
os.chmod(path, 0o600)
PY

echo "Starting deluged (config: $CONFIG_DIR, log: $DEV_DIR/daemon.log)"
echo "Health: curl -s http://127.0.0.1:$PORT/health"
echo "API:    curl -s -H 'Authorization: Bearer $TOKEN' http://127.0.0.1:$PORT/api"
exec deluged -d -c "$CONFIG_DIR" -l "$DEV_DIR/daemon.log" -L info
