"""Write-side helpers: pause/resume/remove/label/queue/add."""

import base64
import logging
import os

from deluge.error import AddTorrentError, InvalidTorrentError

from .read import MAX_BULK_IDS, NO_LABEL

log = logging.getLogger(__name__)

QUEUE_ACTIONS = {
    "up": "queue_up",
    "down": "queue_down",
    "top": "queue_top",
    "bottom": "queue_bottom",
}

BULK_ACTIONS = {"pause", "resume", "remove", "label"}


class BadRequest(ValueError):
    pass


class Conflict(RuntimeError):
    pass


def set_session_paused(core, paused):
    if paused:
        core.pause_session()
    else:
        core.resume_session()
    try:
        actual = bool(core.session.is_paused())
    except (AttributeError, KeyError):
        actual = bool(paused)
    return {"paused": actual}


def pause(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    if torrent.state == "Error":
        raise Conflict("Torrent is in Error state; cannot pause")
    core.pause_torrent(torrent_id)
    return {"id": torrent_id, "state": torrent.state}


def resume(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    core.resume_torrent(torrent_id)
    return {"id": torrent_id, "state": torrent.state}


def remove(core, torrent_id, remove_data=False):
    _torrent(core, torrent_id)
    try:
        removed = core.remove_torrent(torrent_id, bool(remove_data))
    except InvalidTorrentError as ex:
        raise KeyError(torrent_id) from ex
    if not removed:
        raise Conflict("Deluge refused to remove the torrent")
    return {"id": torrent_id, "removed": True, "remove_data": bool(remove_data)}


def queue(core, torrent_id, action):
    method = QUEUE_ACTIONS.get(action)
    if method is None:
        raise BadRequest(
            "action must be one of: " + ", ".join(sorted(QUEUE_ACTIONS))
        )
    _torrent(core, torrent_id)
    getattr(core, method)([torrent_id])
    return {"id": torrent_id, "action": action}


def set_label(core, label_plugin, torrent_id, label):
    _torrent(core, torrent_id)
    if label_plugin is None:
        raise Conflict("Label plugin is not enabled")
    if label in (None, "", NO_LABEL):
        label_id = None
    else:
        if label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")
        label_id = label
    label_plugin.set_torrent(torrent_id, label_id)
    return {"id": torrent_id, "label": label_id or NO_LABEL}


def _limit(value, key):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must be a number") from None
    if number < -1:
        raise BadRequest(f"{key} must be -1 or >= 0")
    return number


def set_session_limits(
    core, max_download_speed=None, max_upload_speed=None
):
    updates = {}
    if max_download_speed is not None:
        updates["max_download_speed"] = _limit(
            max_download_speed, "max_download_speed"
        )
    if max_upload_speed is not None:
        updates["max_upload_speed"] = _limit(max_upload_speed, "max_upload_speed")
    if not updates:
        raise BadRequest("at least one speed limit is required")

    core.set_config(updates)
    values = core.get_config_values(list(updates))
    return {key: values[key] for key in updates}


def set_torrent_limits(
    core, torrent_id, max_download_speed=None, max_upload_speed=None
):
    torrent = _torrent(core, torrent_id)
    down = (
        _limit(max_download_speed, "max_download_speed")
        if max_download_speed is not None
        else None
    )
    up = (
        _limit(max_upload_speed, "max_upload_speed")
        if max_upload_speed is not None
        else None
    )
    if down is None and up is None:
        raise BadRequest("at least one speed limit is required")

    if down is not None:
        torrent.set_max_download_speed(down)
    if up is not None:
        torrent.set_max_upload_speed(up)

    status = torrent.get_status(
        ["max_download_speed", "max_upload_speed"], update=False
    )
    return {"id": torrent_id, **status}


def set_file_priorities(core, torrent_id, changes=None, only=None):
    torrent = _torrent(core, torrent_id)
    files = torrent.get_files()
    if not files:
        raise Conflict("Torrent has no file metadata yet")
    priorities = list(torrent.get_file_priorities())
    if len(priorities) != len(files):
        priorities = [4] * len(files)

    if only is not None:
        index = int(only)
        if not 0 <= index < len(files):
            raise BadRequest(f"file index out of range: {only}")
        priorities = [0] * len(files)
        priorities[index] = 4
    else:
        if not isinstance(changes, list) or not changes:
            raise BadRequest("files must be a non-empty list")
        for change in changes:
            if not isinstance(change, dict):
                raise BadRequest("file changes must be objects")
            index = int(change.get("index"))
            priority = int(change.get("priority"))
            if not 0 <= index < len(files):
                raise BadRequest(f"file index out of range: {index}")
            if priority not in (0, 1, 4, 7):
                raise BadRequest("priority must be 0, 1, 4 or 7")
            priorities[index] = priority

    torrent.set_file_priorities(priorities)
    return {"id": torrent_id, "priorities": list(torrent.get_file_priorities())}


def bulk(core, label_plugin, torrent_ids, action, label=None, remove_data=False):
    if action not in BULK_ACTIONS:
        raise BadRequest("action must be one of: " + ", ".join(sorted(BULK_ACTIONS)))
    ids = [str(torrent_id) for torrent_id in torrent_ids or []]
    if not ids:
        raise BadRequest("torrent_ids must not be empty")
    if len(ids) > MAX_BULK_IDS:
        raise BadRequest(f"at most {MAX_BULK_IDS} torrent ids are allowed")
    if action == "label":
        if label_plugin is None:
            raise Conflict("Label plugin is not enabled")
        if label not in (None, "", NO_LABEL) and label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")

    ok = 0
    failed = []
    for torrent_id in ids:
        try:
            if action == "pause":
                pause(core, torrent_id)
            elif action == "resume":
                resume(core, torrent_id)
            elif action == "remove":
                remove(core, torrent_id, remove_data)
            else:
                set_label(core, label_plugin, torrent_id, label)
        except (KeyError, Conflict) as ex:
            error = "unknown torrent" if isinstance(ex, KeyError) else str(ex)
            failed.append({"id": torrent_id, "error": error})
        else:
            ok += 1
    return {"ok": ok, "failed": failed}


def add(
    core,
    label_plugin,
    magnet=None,
    filename=None,
    filedump=None,
    label=None,
    download_location=None,
    add_paused=False,
):
    if bool(magnet) == bool(filedump):
        raise BadRequest("exactly one of magnet or torrent file is required")
    if magnet and not str(magnet).startswith("magnet:?"):
        raise BadRequest("magnet must start with magnet:?")
    if download_location:
        if not os.path.isabs(download_location):
            raise BadRequest("download_location must be an absolute path")
    if not isinstance(add_paused, bool):
        raise BadRequest("add_paused must be a bool")

    label_id = None
    if label and label != NO_LABEL:
        if label_plugin is None:
            raise Conflict("Label plugin is not enabled")
        if label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")
        label_id = label

    options = {}
    if download_location:
        options["download_location"] = download_location
    if add_paused:
        options["add_paused"] = True

    try:
        if magnet:
            torrent_id = core.add_torrent_magnet(magnet, options)
        else:
            encoded = base64.b64encode(filedump).decode("ascii")
            torrent_id = core.add_torrent_file(
                filename or "upload.torrent", encoded, options
            )
    except AddTorrentError as ex:
        message = str(ex)
        if "already" in message.lower():
            raise Conflict(message) from ex
        raise BadRequest(message) from ex
    except (TypeError, ValueError) as ex:
        raise BadRequest(str(ex)) from ex

    if not torrent_id:
        raise Conflict("Deluge did not return a torrent id")

    if label_id:
        label_plugin.set_torrent(torrent_id, label_id)

    return {
        "id": torrent_id,
        "label": label_id or NO_LABEL,
        "download_location": download_location or "",
    }


def _torrent(core, torrent_id):
    if not torrent_id:
        raise KeyError(torrent_id)
    try:
        return core.torrentmanager[torrent_id]
    except KeyError:
        raise KeyError(torrent_id) from None
