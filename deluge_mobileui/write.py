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
LABEL_PLUGIN_MISSING = "Label plugin is not enabled"


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
        raise Conflict(LABEL_PLUGIN_MISSING)
    if label in (None, "", NO_LABEL):
        label_id = None
    else:
        if label not in label_plugin.labels:
            raise BadRequest(f"unknown label: {label}")
        label_id = label
    label_plugin.set_torrent(torrent_id, label_id)
    return {"id": torrent_id, "label": label_id or NO_LABEL}


def add_label(label_plugin, label_id):
    if label_plugin is None:
        raise Conflict(LABEL_PLUGIN_MISSING)
    if not isinstance(label_id, str):
        raise BadRequest("label id must be a string")
    name = label_id.strip().lower()
    if not name:
        raise BadRequest("label id must not be empty")
    try:
        label_plugin.add(name)
    except Exception as ex:
        raise BadRequest(str(ex)) from None
    return {"id": name}


def remove_label(label_plugin, label_id):
    if label_plugin is None:
        raise Conflict(LABEL_PLUGIN_MISSING)
    if not isinstance(label_id, str) or not label_id.strip():
        raise BadRequest("label id must not be empty")
    name = label_id.strip().lower()
    try:
        label_plugin.remove(name)
    except Exception as ex:
        raise BadRequest(str(ex)) from None
    return {"id": name, "removed": True}


def reannounce(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    return {"id": torrent_id, "reannounced": bool(torrent.force_reannounce())}


def recheck(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    return {"id": torrent_id, "rechecked": bool(torrent.force_recheck())}


def move_storage(core, torrent_id, location):
    torrent = _torrent(core, torrent_id)
    if not isinstance(location, str) or not location.strip():
        raise BadRequest("location must be a non-empty string")
    location = location.strip()
    if not os.path.isabs(location):
        raise BadRequest("location must be an absolute path")
    if torrent.state == "Moving":
        raise Conflict("Torrent is already moving")
    if not torrent.move_storage(location):
        raise Conflict("Deluge could not move the torrent storage")
    return {"id": torrent_id, "destination": location, "moving": True}


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


def _queue_int(value, key):
    if isinstance(value, bool):
        raise BadRequest(f"{key} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise BadRequest(f"{key} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must be an integer") from None
    if not -1 <= number <= 9999:
        raise BadRequest(f"{key} must be between -1 and 9999")
    return number


def set_session_queue(
    core,
    max_active_downloading=None,
    max_active_seeding=None,
    max_active_limit=None,
    queue_new_to_top=None,
):
    updates = {}
    for key, value in (
        ("max_active_downloading", max_active_downloading),
        ("max_active_seeding", max_active_seeding),
        ("max_active_limit", max_active_limit),
    ):
        if value is not None:
            updates[key] = _queue_int(value, key)
    if queue_new_to_top is not None:
        if not isinstance(queue_new_to_top, bool):
            raise BadRequest("queue_new_to_top must be a bool")
        updates["queue_new_to_top"] = queue_new_to_top
    if not updates:
        raise BadRequest("at least one queue setting is required")

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


BOOL_TORRENT_OPTIONS = {
    "sequential_download",
    "prioritize_first_last_pieces",
    "auto_managed",
    "super_seeding",
    "stop_at_ratio",
    "remove_at_ratio",
}
INT_TORRENT_OPTIONS = {"max_connections", "max_upload_slots"}
TORRENT_OPTION_KEYS = (
    "sequential_download",
    "prioritize_first_last_pieces",
    "auto_managed",
    "super_seeding",
    "stop_at_ratio",
    "stop_ratio",
    "remove_at_ratio",
    "max_connections",
    "max_upload_slots",
)


def _torrent_options(torrent):
    options = torrent.get_options()
    return {key: options[key] for key in TORRENT_OPTION_KEYS if key in options}


def get_torrent_options(core, torrent_id):
    torrent = _torrent(core, torrent_id)
    return {"id": torrent_id, "options": _torrent_options(torrent)}


def _option_ratio(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BadRequest("stop_ratio must be a number")
    ratio = float(value)
    if not 0.5 <= ratio <= 100:
        raise BadRequest("stop_ratio must be between 0.5 and 100")
    return ratio


def _option_int(value, key):
    if isinstance(value, bool):
        raise BadRequest(f"{key} must be an integer")
    if isinstance(value, float) and not value.is_integer():
        raise BadRequest(f"{key} must be an integer")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BadRequest(f"{key} must be an integer") from None
    if not -1 <= number <= 9000:
        raise BadRequest(f"{key} must be between -1 and 9000")
    return number


def set_torrent_options(core, torrent_id, options):
    torrent = _torrent(core, torrent_id)
    if not isinstance(options, dict) or not options:
        raise BadRequest("at least one torrent option is required")
    unknown = sorted(set(options) - set(TORRENT_OPTION_KEYS))
    if unknown:
        raise BadRequest(f"unknown torrent option: {unknown[0]}")

    updates = {}
    for key, value in options.items():
        if key in BOOL_TORRENT_OPTIONS:
            if not isinstance(value, bool):
                raise BadRequest(f"{key} must be a bool")
            updates[key] = value
        elif key == "stop_ratio":
            updates[key] = _option_ratio(value)
        elif key in INT_TORRENT_OPTIONS:
            updates[key] = _option_int(value, key)

    torrent.set_options(updates)
    return {"id": torrent_id, "options": _torrent_options(torrent)}


def _apply_file_changes(files, priorities, changes, only):
    if only is not None:
        index = int(only)
        if not 0 <= index < len(files):
            raise BadRequest(f"file index out of range: {only}")
        return [4 if position == index else 0 for position in range(len(files))]

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
    return priorities


def set_file_priorities(core, torrent_id, changes=None, only=None):
    torrent = _torrent(core, torrent_id)
    files = torrent.get_files()
    if not files:
        raise Conflict("Torrent has no file metadata yet")
    priorities = list(torrent.get_file_priorities())
    if len(priorities) != len(files):
        priorities = [4] * len(files)

    priorities = _apply_file_changes(files, priorities, changes, only)
    torrent.set_file_priorities(priorities)
    return {"id": torrent_id, "priorities": list(torrent.get_file_priorities())}


def _bulk_apply(core, label_plugin, torrent_id, action, label, remove_data):
    if action == "pause":
        pause(core, torrent_id)
    elif action == "resume":
        resume(core, torrent_id)
    elif action == "remove":
        remove(core, torrent_id, remove_data)
    else:
        set_label(core, label_plugin, torrent_id, label)


def _bulk_ids(torrent_ids):
    ids = [str(torrent_id) for torrent_id in torrent_ids or []]
    if not ids:
        raise BadRequest("torrent_ids must not be empty")
    if len(ids) > MAX_BULK_IDS:
        raise BadRequest(f"at most {MAX_BULK_IDS} torrent ids are allowed")
    return ids


def _check_bulk_label(label_plugin, action, label):
    if action != "label":
        return
    if label_plugin is None:
        raise Conflict(LABEL_PLUGIN_MISSING)
    if label not in (None, "", NO_LABEL) and label not in label_plugin.labels:
        raise BadRequest(f"unknown label: {label}")


def bulk(core, label_plugin, torrent_ids, action, label=None, remove_data=False):
    if action not in BULK_ACTIONS:
        raise BadRequest("action must be one of: " + ", ".join(sorted(BULK_ACTIONS)))
    ids = _bulk_ids(torrent_ids)
    _check_bulk_label(label_plugin, action, label)

    ok = 0
    failed = []
    for torrent_id in ids:
        try:
            _bulk_apply(core, label_plugin, torrent_id, action, label, remove_data)
        except (KeyError, Conflict) as ex:
            error = "unknown torrent" if isinstance(ex, KeyError) else str(ex)
            failed.append({"id": torrent_id, "error": error})
        else:
            ok += 1
    return {"ok": ok, "failed": failed}


def _add_options(magnet, filedump, download_location, add_paused):
    if bool(magnet) == bool(filedump):
        raise BadRequest("exactly one of magnet or torrent file is required")
    if magnet and not str(magnet).startswith("magnet:?"):
        raise BadRequest("magnet must start with magnet:?")
    if download_location and not os.path.isabs(download_location):
        raise BadRequest("download_location must be an absolute path")
    if not isinstance(add_paused, bool):
        raise BadRequest("add_paused must be a bool")

    options = {}
    if download_location:
        options["download_location"] = download_location
    if add_paused:
        options["add_paused"] = True
    return options


def _add_label_id(label_plugin, label):
    if not label or label == NO_LABEL:
        return None
    if label_plugin is None:
        raise Conflict(LABEL_PLUGIN_MISSING)
    if label not in label_plugin.labels:
        raise BadRequest(f"unknown label: {label}")
    return label


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
    options = _add_options(magnet, filedump, download_location, add_paused)
    label_id = _add_label_id(label_plugin, label)

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
