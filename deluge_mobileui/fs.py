"""Directory listing for the mobile path picker."""

import os

from .write import BadRequest

MAX_DIRS = 1000


def list_dirs(path):
    if not isinstance(path, str) or not path:
        raise BadRequest("path is required")
    if not os.path.isabs(path):
        raise BadRequest("path must be an absolute path")

    resolved = os.path.realpath(path)
    if not os.path.isdir(resolved):
        raise BadRequest("not a directory")

    try:
        entries = list(os.scandir(resolved))
    except OSError as ex:
        raise BadRequest(f"cannot list directory: {ex.strerror}") from ex

    dirs = []
    for entry in entries:
        try:
            if not entry.is_dir(follow_symlinks=True):
                continue
        except OSError:
            continue
        dirs.append(
            {
                "name": entry.name,
                "path": os.path.join(resolved, entry.name),
                "writable": os.access(entry.path, os.W_OK),
            }
        )

    dirs.sort(key=lambda item: item["name"].lower())
    parent = os.path.dirname(resolved)
    return {
        "path": resolved,
        "parent": None if parent == resolved else parent,
        "writable": os.access(resolved, os.W_OK),
        "dirs": dirs[:MAX_DIRS],
        "truncated": len(dirs) > MAX_DIRS,
    }
