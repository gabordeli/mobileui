#!/usr/bin/env python3
"""Bump the project version, package.json and CHANGELOG."""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSION_FILE = ROOT / "deluge_mobileui" / "version.py"
PACKAGE_FILE = ROOT / "webui" / "package.json"
LOCK_FILE = ROOT / "webui" / "package-lock.json"
CHANGELOG = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"^__version__ = \"(\d+)\.(\d+)\.(\d+)\"$", re.MULTILINE)


def read_version() -> str:
    match = VERSION_RE.search(VERSION_FILE.read_text(encoding="utf-8"))
    if not match:
        raise SystemExit(f"cannot read version from {VERSION_FILE}")
    return ".".join(match.groups())


def bump(current: str, kind: str) -> str:
    major, minor, patch = (int(part) for part in current.split("."))
    if kind == "major":
        return f"{major + 1}.0.0"
    if kind == "minor":
        return f"{major}.{minor + 1}.0"
    if kind == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise SystemExit("release type must be patch, minor or major")


def update_changelog(version: str) -> None:
    entry = f"## [{version}] - {date.today().isoformat()}\n\n- Release {version}.\n"
    if not CHANGELOG.exists():
        CHANGELOG.write_text(f"# Changelog\n\n{entry}", encoding="utf-8")
        return
    content = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(r"^## \[", content, re.MULTILINE)
    if match:
        content = content[: match.start()] + entry + "\n" + content[match.start() :]
    else:
        content = content.rstrip() + "\n\n" + entry
    CHANGELOG.write_text(content, encoding="utf-8")


def update_package(version: str) -> None:
    package = json.loads(PACKAGE_FILE.read_text(encoding="utf-8"))
    package["version"] = version
    PACKAGE_FILE.write_text(
        json.dumps(package, indent=2) + "\n", encoding="utf-8"
    )
    if LOCK_FILE.exists():
        lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
        lock["version"] = version
        if "" in lock.get("packages", {}):
            lock["packages"][""]["version"] = version
        LOCK_FILE.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=["patch", "minor", "major"])
    parser.add_argument("--version", default="", help="explicit x.y.z override")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    current = read_version()
    version = args.version or bump(current, args.kind)
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise SystemExit("--version must be x.y.z")

    if not args.dry_run:
        VERSION_FILE.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
        update_package(version)
        update_changelog(version)
    print(version)


if __name__ == "__main__":
    sys.exit(main())
